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
from .statistics import Statistics


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
        self._rock_velocities = {}     # deco_id -> [vx, vy] for thrown rocks
        self.sweep_x = None            # x of the cleaning sweep bar (None = idle)
        self.stats = Statistics()
        self._prev_pos = (self.squid.x, self.squid.y)
        self._was_sick = self.squid.is_sick
        self._near_plants = set()
        self.ink_clouds = []           # [{x, y, t (sim_time), ttl}]
        self._startle_cooldown = 0.0
        # Egg hatching: a new game begins as an egg that plays its frames
        # (1/second) before the squid emerges.
        self.hatching = False
        self.hatch_t = 0.0
        self.hatch_frames = 6          # anim01..anim06, one per second

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

        # Fly any thrown rocks: gravity pulls them down to the sandy floor. A
        # rock thrown hard enough can leave the play area, and is then deleted.
        floor = self.tank_size[1] - 40
        w = self.tank_size[0]
        margin = 70
        for rid, vel in list(self._rock_velocities.items()):
            rock = self._deco_by_id(rid)
            if rock is None:
                self._rock_velocities.pop(rid, None)
                continue
            vel[1] += 520.0 * dt                       # gravity (y grows downward)
            rock["x"] += vel[0] * dt
            rock["y"] += vel[1] * dt
            vel[0] *= (1.0 - 0.4 * dt)                 # light drag on x
            if rock["x"] < -margin or rock["x"] > w + margin or rock["y"] < -margin:
                self.remove_decoration(rock["id"])     # left the tank -> gone
                self._rock_velocities.pop(rid, None)
                continue
            if rock["y"] >= floor:                     # landed
                rock["y"] = floor
                self._rock_velocities.pop(rid, None)
            elif (self._startle_cooldown <= 0 and not squid.is_fleeing
                  and math.hypot(squid.x - rock["x"], squid.y - rock["y"]) < 55):
                self.startle("rock")           # a rock whizzed past — fright!

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
                # Variable strength: gentle lobs stay in the tank, hard throws
                # can sail out of the play area (and get cleaned up).
                vx = direction * random.uniform(220.0, 560.0)
                vy = -random.uniform(120.0, 340.0)
                self._rock_velocities[rock["id"]] = [vx, vy]
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
                self.stats.on_rock_thrown()
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

    # --------------------------------------------------------- startle / ink
    def startle(self, source="ambient"):
        """Trigger a fright: flee, spike anxiety, ~25% release an ink cloud."""
        squid = self.squid
        squid.startle(source)
        self.stats.on_startle()
        self._startle_cooldown = 8.0
        squid.remember("mental_state", "startled", "Startled!",
                       {"anxiety": 30, "happiness": -8}, importance=2.0,
                       related=["anxiety"])
        if random.random() < 0.25:
            self._create_ink_cloud()

    def _create_ink_cloud(self):
        squid = self.squid
        self.ink_clouds.append({"x": squid.x, "y": squid.y,
                                "t": squid.brain.sim_time, "ttl": 3.0})
        self.stats.on_ink_cloud()
        squid.remember("behaviour", "ink_cloud", "Startled — released an ink cloud!",
                       None, importance=1.5)

    def _update_startle(self, dt):
        squid = self.squid
        now = squid.brain.sim_time
        if self._startle_cooldown > 0:
            self._startle_cooldown -= dt

        # End a flee once its timer runs out.
        if squid.is_fleeing and now >= squid._startle_until:
            squid.is_fleeing = False
            squid.is_startled = False
            squid.status = "recovering"
        if squid.is_fleeing:
            squid.flee_step()
            return  # fleeing overrides normal movement

        # Ambient chance of a fright, more likely when anxious (desktop rule).
        if self._startle_cooldown <= 0 and not squid.is_sleeping:
            rate = 0.02                       # per second base chance
            if squid.anxiety > 70:
                rate *= squid.anxiety / 50.0
            if random.random() < rate * dt:
                self.startle("ambient")

    def _update_ink(self, dt):
        now = self.squid.brain.sim_time
        self.ink_clouds = [c for c in self.ink_clouds if now - c["t"] < c["ttl"]]

    def _decoration_effects(self, dt):
        """Being near decorations shapes mood: plants soothe, rocks intrigue."""
        s = self.squid
        near_now = set()
        for d in self.decorations:
            if math.hypot(s.x - d["x"], s.y - d["y"]) < 120 * d.get("scale", 1.0):
                cat = d["category"]
                if cat == "plant":
                    s.anxiety = max(0.0, s.anxiety - 3.0 * dt)
                    s.satisfaction = min(100.0, s.satisfaction + 1.5 * dt)
                    near_now.add(d["id"])
                    if d["id"] not in self._near_plants:
                        self.stats.on_plant_interaction()
                elif cat == "rock":
                    s.curiosity = min(100.0, s.curiosity + 2.5 * dt)
        self._near_plants = near_now

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
                self.stats.on_eat(f["type"])
                eaten.append(f)
        for f in eaten:
            self.food_items.remove(f)
        return bool(eaten)

    # ---------------------------------------------------------------- update
    def start_hatching(self):
        self.hatching = True
        self.hatch_t = 0.0
        self.last_status = "an egg... something stirs inside"

    def update(self, dt: float):
        """Advance the whole simulation by ``dt`` seconds."""
        self.newborn_neuron = None
        self.squid._last_dt = dt
        squid = self.squid

        # While hatching, freeze the squid and just advance the egg animation
        # (one frame per second) until all frames have played.
        if self.hatching:
            self.hatch_t += dt
            if self.hatch_t >= self.hatch_frames:
                self.hatching = False
                self.last_status = "your squid has hatched!"
            return self.last_status

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
        if squid.is_sick and not self._was_sick:
            self.stats.on_sickness()
        self._was_sick = squid.is_sick
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
            self.stats.on_neuron_born(kind)
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
        self._update_startle(dt)
        self._update_ink(dt)
        self._update_rock_play(dt)
        self._update_sweep(dt)
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
            self.stats.on_poop(len(self.poop_items))

        # Lifetime statistics: distance moved this tick + per-tick accumulation.
        moved = math.hypot(squid.x - self._prev_pos[0], squid.y - self._prev_pos[1])
        self._prev_pos = (squid.x, squid.y)
        self.stats.tick(dt, squid, squid.brain, moved)

        return self.last_status

    def clean_tank(self):
        # Start a right-to-left sweep that removes food and poop as it passes
        # (mirrors the desktop cleaning line). The stat boost applies now.
        if self.sweep_x is None:
            self.sweep_x = float(self.tank_size[0])
        return self.squid.clean()

    def _update_sweep(self, dt):
        if self.sweep_x is None:
            return
        self.sweep_x -= (self.tank_size[0] / 1.2) * dt   # ~1.2s to cross the tank
        x = self.sweep_x
        # Everything the bar has passed (to its right) is swept away.
        self.food_items = [f for f in self.food_items if f["x"] < x]
        self.poop_items = [p for p in self.poop_items if p["x"] < x]
        if self.sweep_x <= 0:
            self.sweep_x = None
            self.food_items = []
            self.poop_items = []

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
            "statistics": self.stats.to_dict(),
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
        sim.stats = Statistics.from_dict(data.get("statistics"))
        sim._prev_pos = (sim.squid.x, sim.squid.y)
        sim._was_sick = sim.squid.is_sick
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
