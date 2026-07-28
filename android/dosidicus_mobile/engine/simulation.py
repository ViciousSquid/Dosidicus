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
from .personality import Personality


class Simulation:
    def __init__(self, tank_size=(900, 500), squid: Squid = None):
        self.tank_size = tank_size
        self.squid = squid or Squid(tank_size=tank_size)
        self.squid.tank_size = tank_size
        self.food_items = []          # list of {"x","y","type"}
        self.poop_items = []          # list of {"x","y"}
        # Decorations placed by the caretaker. Each: {id, type (asset file),
        # category (plant/rock/...), x, y (centre, tank coords), scale}.
        self.decorations = []
        self._food_id = 0
        self._decoration_id = 0
        self._poop_timer = 0.0
        self._decision_timer = 0.0
        self._decision_interval = 1.0  # squid re-decides roughly once a second
        self.last_status = self.squid.status
        self.newborn_neuron = None     # set for one tick when neurogenesis fires
        self._prev_can_see_food = False
        self._was_anxious = False
        self._rock_velocities = {}     # deco_id -> [vx, vy] for thrown rocks

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

    # ------------------------------------------------------- decorations API
    def add_decoration(self, type, category, x, y, scale=1.0):
        """Place a decoration; a new object in the tank is a novel stimulus."""
        self._decoration_id += 1
        deco = {"id": self._decoration_id, "type": type, "category": category,
                "x": float(x), "y": float(y), "scale": float(scale)}
        self.decorations.append(deco)
        self.squid.brain.register_novelty(2.5)
        self.squid.curiosity = min(100.0, self.squid.curiosity + 5.0)
        self.squid.remember("decoration", category, f"New {category} appeared",
                            {"curiosity": 5}, importance=1.5)
        return deco

    def update_decoration(self, deco_id, x=None, y=None, scale=None):
        for d in self.decorations:
            if d["id"] == deco_id:
                if x is not None:
                    d["x"] = float(x)
                if y is not None:
                    d["y"] = float(y)
                if scale is not None:
                    d["scale"] = float(scale)
                return d
        return None

    def remove_decoration(self, deco_id):
        self.decorations = [d for d in self.decorations if d["id"] != deco_id]

    # --------------------------------------------------------- rock play
    def _rock_decorations(self):
        return [d for d in self.decorations if d.get("category") == "rock"]

    def _deco_by_id(self, deco_id):
        return next((d for d in self.decorations if d["id"] == deco_id), None)

    def _update_rock_play(self, dt):
        """The squid can approach a rock, pick it up, carry it, then throw it.

        Ported from the desktop rock interaction: pick up within ~45px when not
        sleeping, carry for a few seconds, then fling it — a rewarding form of
        play (extra reward for GREEDY squids)."""
        squid = self.squid
        now = squid.brain.sim_time

        # Fly any thrown rocks: gravity pulls them down to the sandy floor.
        floor = self.tank_size[1] - 40
        for rid, vel in list(self._rock_velocities.items()):
            rock = self._deco_by_id(rid)
            if rock is None:
                self._rock_velocities.pop(rid, None)
                continue
            vel[1] += 500.0 * dt                       # gravity (y grows downward)
            rock["x"] += vel[0] * dt
            rock["y"] += vel[1] * dt
            vel[0] *= (1.0 - 1.2 * dt)                 # air/water drag on x
            w = self.tank_size[0]
            if rock["x"] < 20 or rock["x"] > w - 20:   # bounce off the walls
                rock["x"] = max(20, min(w - 20, rock["x"]))
                vel[0] = -vel[0] * 0.5
            if rock["y"] >= floor:                     # landed
                rock["y"] = floor
                self._rock_velocities.pop(rid, None)

        if squid.is_sleeping:
            return

        # Carrying: the rock rides just above the squid until it's thrown.
        if squid.carrying_rock:
            rock = self._deco_by_id(squid.carried_rock_id)
            if rock is None:
                squid.carrying_rock = False
                squid.carried_rock_id = None
                return
            rock["x"] = squid.x
            rock["y"] = squid.y - 26
            if now >= squid._carry_until:
                direction = random.choice([-1.0, 1.0])
                self._rock_velocities[rock["id"]] = [direction * 260.0, -140.0]
                squid.carrying_rock = False
                squid.carried_rock_id = None
                squid.satisfaction = min(100.0, squid.satisfaction + 18.0)
                squid.happiness = min(100.0, squid.happiness + 15.0)
                squid.curiosity = min(100.0, squid.curiosity + 8.0)
                if squid.personality == Personality.GREEDY:
                    squid.satisfaction = min(100.0, squid.satisfaction + 6.0)
                squid.brain.learn_from_playing()
                squid.remember("play", "rock_throw", "Threw a rock",
                               {"satisfaction": 18, "happiness": 15},
                               importance=2.0, related=["satisfaction", "curiosity"])
                self.last_status = "playfully tossing a rock"
            return

        # Not carrying: if the squid wants to play and a settled rock is around,
        # go for it (ignore rocks still in flight so it doesn't re-grab its throw).
        rocks = [r for r in self._rock_decorations() if r["id"] not in self._rock_velocities]
        if not (squid.wants_to_play and rocks):
            return
        target = min(rocks, key=lambda r: squid._dist(r["x"], r["y"]))
        dist = squid._dist(target["x"], target["y"])
        if dist < 45:
            squid.carrying_rock = True
            squid.carried_rock_id = target["id"]
            squid._carry_until = now + random.uniform(3.0, 7.0)
            self.last_status = "picked up a rock!"
        elif dist < 320:
            squid.move_towards(target["x"], target["y"])
            self.last_status = "going for a rock"

    def _decoration_effects(self, dt):
        """Being near decorations shapes mood: plants soothe, rocks intrigue."""
        s = self.squid
        for d in self.decorations:
            if math.hypot(s.x - d["x"], s.y - d["y"]) < 120 * d.get("scale", 1.0):
                cat = d["category"]
                if cat == "plant":
                    s.anxiety = max(0.0, s.anxiety - 3.0 * dt)
                    s.satisfaction = min(100.0, s.satisfaction + 1.5 * dt)
                elif cat == "rock":
                    s.curiosity = min(100.0, s.curiosity + 2.5 * dt)

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
        # A spike into high anxiety is a memorable (negative) mental state.
        if squid.anxiety > 85 and not self._was_anxious:
            squid.remember("mental_state", "anxious", "Felt very anxious",
                           {"anxiety": 20, "happiness": -10}, importance=2.0,
                           related=["anxiety"])
        self._was_anxious = squid.anxiety > 85
        clamped = squid.sync_stats_to_brain(can_see_food=can_see)
        squid.brain.propagate(clamped)
        # keep brain's core neurons in lock-step with the authoritative stats
        for name in squid.CORE_STATS:
            squid.brain.state[name] = getattr(squid, name)

        # 3) Learning: continuous Hebbian + STDP + neurogenesis housekeeping.
        squid.brain.hebbian_step(dt)
        squid.brain.stdp_step()
        squid.brain.decay_neurogenesis_counters(dt)
        born = squid.brain.check_neurogenesis()
        if born:
            self.newborn_neuron = born
            kind = born.rsplit("_", 1)[0]
            squid.remember("neurogenesis", born, f"Grew a {kind} neuron",
                           None, importance=3.0)
        squid.memory.periodic(squid.brain.sim_time)

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
        self._update_rock_play(dt)
        self._decoration_effects(dt)
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
            "decorations": self.decorations,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Simulation":
        tank = tuple(data.get("tank_size", (900, 500)))
        squid = Squid.from_dict(data["squid"], tank)
        sim = cls(tank, squid)
        sim.food_items = data.get("food_items", [])
        sim.poop_items = data.get("poop_items", [])
        sim.decorations = data.get("decorations", [])
        sim._decoration_id = max([d["id"] for d in sim.decorations], default=0)
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
