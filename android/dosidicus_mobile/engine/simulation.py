"""Simulation - the tick loop that binds squid, brain and world together.

This is the mobile analogue of ``TamagotchiLogic``: it owns the food in the
tank, advances time, runs the brain (propagate -> Hebbian learn ->
neurogenesis), lets the squid decide and move, and handles save/load. It has no
UI dependency, so it can be driven by Kivy's Clock, a test, or a headless loop.
"""

from __future__ import annotations

import json
import math
import os
import random
import time

from .squid import Squid


class Simulation:
    def __init__(self, tank_size=(900, 500), squid: Squid = None):
        self.tank_size = tank_size
        self.squid = squid or Squid(tank_size=tank_size)
        self.squid.tank_size = tank_size
        self.food_items = []          # list of {"x","y","type"}
        self.poop_items = []          # list of {"x","y"}
        self._food_id = 0
        self._poop_timer = 0.0
        self._decision_timer = 0.0
        self._decision_interval = 1.0  # squid re-decides roughly once a second
        self.last_status = self.squid.status
        self.newborn_neuron = None     # set for one tick when neurogenesis fires
        self._prev_can_see_food = False

    # ------------------------------------------------------------- world API
    def food_visible(self):
        """Squid can see food within a perception radius."""
        radius = 260
        return any(
            math.hypot(self.squid.x - f["x"], self.squid.y - f["y"]) <= radius
            for f in self.food_items
        )

    def drop_food(self, x=None, y=None, food_type="sushi"):
        w, h = self.tank_size
        self._food_id += 1
        self.food_items.append({
            "x": x if x is not None else random.uniform(40, w - 40),
            "y": y if y is not None else 40,
            "type": food_type,
            "id": self._food_id,
        })

    def _settle_food(self, dt):
        floor = self.tank_size[1] - 40
        for f in self.food_items:
            if f["y"] < floor:
                f["y"] = min(floor, f["y"] + 120 * dt)

    def _try_eat(self):
        eaten = []
        for f in self.food_items:
            if math.hypot(self.squid.x - f["x"], self.squid.y - f["y"]) < 45:
                self.squid.feed(f["type"])
                eaten.append(f)
        for f in eaten:
            self.food_items.remove(f)
        return bool(eaten)

    # ---------------------------------------------------------------- update
    def update(self, dt: float):
        """Advance the whole simulation by ``dt`` seconds."""
        self.newborn_neuron = None
        self.squid._last_dt = dt
        squid = self.squid

        # 1) Needs drift.
        squid.update_needs(dt)

        # 2) Perception + brain forward pass.
        can_see = self.food_visible()
        # Rising edge = a genuinely novel stimulus entered perception.
        if can_see and not self._prev_can_see_food:
            squid.brain.register_novelty(2.0)
        self._prev_can_see_food = can_see
        # Sustained distress feeds the stress trigger, weighted by how anxious.
        if squid.anxiety > 60:
            squid.brain.register_stress((squid.anxiety - 60) / 40.0 * dt)
        clamped = squid.sync_stats_to_brain(can_see_food=can_see)
        squid.brain.propagate(clamped)
        # keep brain's core neurons in lock-step with the authoritative stats
        for name in squid.CORE_STATS:
            squid.brain.state[name] = getattr(squid, name)

        # 3) Learning: continuous Hebbian + neurogenesis housekeeping.
        squid.brain.hebbian_step(dt)
        squid.brain.decay_neurogenesis_counters(dt)
        born = squid.brain.check_neurogenesis()
        if born:
            self.newborn_neuron = born

        # 4) Let rewired/grown neurons nudge mood, then decide + move.
        squid.pull_core_from_brain()
        self._decision_timer += dt
        if self._decision_timer >= self._decision_interval:
            self._decision_timer = 0.0
            self.last_status = squid.decide(squid.brain.state, self.food_items)
        else:
            # keep drifting on the current decision
            if not squid.is_sleeping:
                if squid.status.startswith(("approaching", "eyeing")) and self.food_items:
                    target = min(self.food_items, key=lambda f: squid._dist(f["x"], f["y"]))
                    squid.move_towards(target["x"], target["y"])

        # 5) World interactions.
        self._settle_food(dt)
        if self._try_eat():
            squid.is_eating = True
        else:
            squid.is_eating = False

        # Occasional poop when well-fed, which lowers cleanliness.
        self._poop_timer += dt
        if self._poop_timer > 20 and squid.hunger < 40 and random.random() < 0.05:
            self._poop_timer = 0.0
            self.poop_items.append({"x": squid.x, "y": squid.y + 20})
            squid.cleanliness = max(0.0, squid.cleanliness - 8.0)

        return self.last_status

    def clean_tank(self):
        self.poop_items.clear()
        return self.squid.clean()

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "version": 1,
            "saved_at": time.time(),
            "tank_size": list(self.tank_size),
            "squid": self.squid.to_dict(),
            "food_items": self.food_items,
            "poop_items": self.poop_items,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Simulation":
        tank = tuple(data.get("tank_size", (900, 500)))
        squid = Squid.from_dict(data["squid"], tank)
        sim = cls(tank, squid)
        sim.food_items = data.get("food_items", [])
        sim.poop_items = data.get("poop_items", [])
        return sim

    def save(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        os.replace(tmp, path)  # atomic write so a crash can't corrupt the save

    @classmethod
    def load(cls, path: str) -> "Simulation":
        with open(path) as f:
            return cls.from_dict(json.load(f))
