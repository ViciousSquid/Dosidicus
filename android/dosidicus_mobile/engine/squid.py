"""Squid - portable pet state, needs dynamics and decision making.

Distilled from ``src/squid.py``, ``src/tamagotchi_logic.py`` and
``src/decision_engine.py`` with all PyQt5 (QGraphicsItem, QTimer, scene) removed.
The squid lives in an abstract tank of ``tank_size`` pixels; the Kivy layer maps
that onto the actual screen. Stats drift over time and are steered by the
neural-first decision engine, which reads the brain state exactly like the
desktop DecisionEngine v4.0 does.
"""

from __future__ import annotations

import math
import random

from .personality import Personality, PERSONALITY_STAT_MODIFIERS
from .brain import NeuralBrain
from .memory import MemoryManager


class Squid:
    def __init__(self, personality: Personality = None, tank_size=(900, 500), brain: NeuralBrain = None):
        self.personality = Personality.from_value(personality) if personality else random.choice(list(Personality))
        self.tank_size = tank_size
        self.brain = brain or NeuralBrain(self.personality)
        self.memory = MemoryManager()

        # Core stats mirror the brain's core neurons (0-100).
        self.hunger = self.brain.state["hunger"]
        self.happiness = self.brain.state["happiness"]
        self.cleanliness = self.brain.state["cleanliness"]
        self.sleepiness = self.brain.state["sleepiness"]
        self.satisfaction = self.brain.state["satisfaction"]
        self.anxiety = self.brain.state["anxiety"]
        self.curiosity = self.brain.state["curiosity"]

        # Body / motion.
        w, h = tank_size
        self.x = w * 0.5
        self.y = h * 0.5
        self.direction = "right"
        self.base_speed = 90.0
        self.is_sleeping = False
        self.is_sick = False
        self.is_eating = False
        self.status = "just hatched"
        self.age_seconds = 0.0
        self.last_decision = {}  # trace of the most recent decision (for the UI)

        # Rock play: the squid can pick up a rock decoration, carry it, then
        # throw it (a form of play). Physics live in the Simulation.
        self.carrying_rock = False
        self.carried_rock_id = None
        self._carry_until = 0.0
        self.wants_to_play = False

    # ----------------------------------------------------------------- stats
    CORE_STATS = ("hunger", "happiness", "cleanliness", "sleepiness",
                  "satisfaction", "anxiety", "curiosity")

    def _clamp_stats(self):
        for name in self.CORE_STATS:
            setattr(self, name, max(0.0, min(100.0, getattr(self, name))))

    def _stat_mod(self, key, default=1.0):
        return PERSONALITY_STAT_MODIFIERS.get(self.personality, {}).get(key, default)

    def update_needs(self, dt: float):
        """Drift the needs over ``dt`` seconds, personality-weighted."""
        hunger_rate = 1.6 * self._stat_mod("hunger_growth")
        energy_rate = 1.1 * self._stat_mod("energy_drain")

        self.hunger += hunger_rate * dt
        self.cleanliness -= 0.8 * dt
        if self.is_sleeping:
            self.sleepiness -= 6.0 * dt
            self.happiness += 0.4 * dt
        else:
            self.sleepiness += energy_rate * dt

        # Derived emotional stats.
        if self.hunger > 75 or self.cleanliness < 25:
            self.happiness -= 1.2 * dt
            self.anxiety += 1.0 * dt * self._stat_mod("anxiety_growth")
        else:
            self.happiness += 0.3 * dt
            self.anxiety -= 0.6 * dt

        if self.cleanliness < 20 and random.random() < 0.02 * dt:
            self.is_sick = True
        if self.is_sick:
            self.happiness -= 1.5 * dt
            self.anxiety += 1.5 * dt
            if self.cleanliness > 60:
                self.is_sick = False

        # Curiosity mean-reverts toward a personality-weighted baseline, so it
        # stays alive (exploring/playing spike it above baseline, boredom pulls
        # it back down) rather than draining to zero.
        curiosity_baseline = 50.0 * self._stat_mod("curiosity_growth")
        self.curiosity += (curiosity_baseline - self.curiosity) * 0.06 * dt
        self.satisfaction -= 0.5 * dt * self._stat_mod("satisfaction_decay")

        # Wake up if fully rested.
        if self.is_sleeping and self.sleepiness <= 5:
            self.is_sleeping = False
            self.status = "waking up"

        self._clamp_stats()
        self.age_seconds += dt

    def sync_stats_to_brain(self, can_see_food: bool = False):
        """Push the 7 core stats + sensors into the brain as clamped inputs."""
        clamped = {name: getattr(self, name) for name in self.CORE_STATS}
        clamped["can_see_food"] = 100.0 if can_see_food else 0.0
        clamped["is_sick"] = 100.0 if self.is_sick else 0.0
        clamped["is_sleeping"] = 100.0 if self.is_sleeping else 0.0
        clamped["is_eating"] = 100.0 if self.is_eating else 0.0
        clamped["pursuing_food"] = 100.0 if self.status.startswith(("approaching", "eyeing")) else 0.0
        clamped["anxiety_stimulus"] = min(100.0, self.anxiety)
        return clamped

    def pull_core_from_brain(self):
        """After propagation, let the brain nudge the derived stats a little so
        grown/rewired neurons actually influence mood (emergent behaviour)."""
        for name in ("happiness", "satisfaction", "anxiety", "curiosity"):
            brain_val = self.brain.state.get(name)
            if brain_val is not None:
                blended = 0.85 * getattr(self, name) + 0.15 * brain_val
                setattr(self, name, blended)
        self._clamp_stats()

    # ------------------------------------------------------------- memory
    def remember(self, category, key, text, raw_value=None, importance=1.0, related=None):
        self.memory.add_short_term(category, key, text, raw_value=raw_value,
                                   importance=importance, related_neurons=related,
                                   now=self.brain.sim_time)

    # ------------------------------------------------------------- care API
    def feed(self, food_type: str = "sushi"):
        if self.is_sleeping:
            return "zzz... too sleepy to eat"
        self.is_eating = True
        self.hunger = max(0.0, self.hunger - 45.0)
        self.satisfaction = min(100.0, self.satisfaction + 25.0)
        self.happiness = min(100.0, self.happiness + 12.0)
        self.brain.learn_from_eating(food_type)
        self.status = f"munching {food_type}"
        self.remember("food", food_type, f"Ate {food_type}",
                      {"hunger": -45, "satisfaction": 25, "happiness": 12},
                      importance=2.0, related=["hunger", "satisfaction"])
        return self.status

    def clean(self):
        self.cleanliness = min(100.0, self.cleanliness + 55.0)
        self.happiness = min(100.0, self.happiness + 8.0)
        self.anxiety = max(0.0, self.anxiety - 10.0)
        self.is_sick = False
        self.brain.learn_from_cleaning()
        self.status = "sparkling clean"
        self.remember("care", "clean", "Tank cleaned",
                      {"cleanliness": 55, "happiness": 8}, importance=1.5,
                      related=["cleanliness", "happiness"])
        return self.status

    def play(self):
        if self.is_sleeping:
            return "zzz... don't wake me"
        self.satisfaction = min(100.0, self.satisfaction + 20.0)
        self.happiness = min(100.0, self.happiness + 18.0)
        self.curiosity = min(100.0, self.curiosity + 15.0)
        self.sleepiness = min(100.0, self.sleepiness + 8.0)
        self.brain.learn_from_playing()
        self.status = "playing happily"
        self.remember("play", "play", "Played",
                      {"satisfaction": 20, "happiness": 18, "curiosity": 15},
                      importance=1.5, related=["satisfaction", "curiosity"])
        return self.status

    def toggle_sleep(self):
        self.is_sleeping = not self.is_sleeping
        self.status = "going to sleep" if self.is_sleeping else "waking up"
        return self.status

    def give_medicine(self):
        self.is_sick = False
        self.happiness = max(0.0, self.happiness - 5.0)  # medicine tastes bad
        self.anxiety = max(0.0, self.anxiety - 15.0)
        self.status = "recovering"
        return self.status

    # ------------------------------------------------------ decision engine
    def decide(self, brain_state: dict, food_items):
        """Neural-first decision, ported from DecisionEngine.make_decision.
        Returns a human-readable status string and steers movement."""
        if self.sleepiness >= 95 and not self.is_sleeping:
            self.is_sleeping = True
            self.status = "exhausted, collapsing to sleep"
            return self.status
        if self.is_sleeping:
            self.status = "sleeping peacefully"
            return self.status

        hunger = brain_state.get("hunger", 50)
        sleepiness = brain_state.get("sleepiness", 50)
        can_see_food = brain_state.get("can_see_food", 0)
        threat = brain_state.get("anxiety", 50)

        weights = {}
        weights["exploring"] = brain_state.get("curiosity", 50) * max(0.1, 1.0 - threat / 140.0)
        weights["eating"] = hunger * (3.0 if can_see_food > 80 else 0.3) * math.pow(1.6, hunger / 25.0)
        weights["comfort"] = (brain_state.get("anxiety", 50) / 40.0) * (4.0 if self.personality == Personality.TIMID else 1.5)
        weights["playing"] = brain_state.get("satisfaction", 50) * brain_state.get("curiosity", 50) / 50.0
        weights["sleeping"] = sleepiness * math.pow(1.7, sleepiness / 25.0) * 0.5

        # Memory influence (ported from DecisionEngine): recent lived experience
        # tilts the odds. Positive food memories make eating more attractive,
        # decoration memories invite exploring/comfort, distress makes the squid
        # seek comfort and explore less.
        memory_mod = {"eating": 1.0, "playing": 1.0, "exploring": 1.0, "comfort": 1.0}
        for mem in self.memory.get_active_memories_data(self.brain.sim_time, 6):
            cat = mem.get("category")
            if cat == "food":                    # eating was rewarding
                memory_mod["eating"] *= 1.2
            elif cat == "play":                  # play was fun
                memory_mod["playing"] *= 1.2
            elif cat == "decoration":            # something new to investigate
                memory_mod["exploring"] *= 1.1
                memory_mod["comfort"] *= 1.15
            elif cat == "mental_state":          # remembered distress
                memory_mod["comfort"] *= 1.3
                memory_mod["exploring"] *= 0.8
        for action, mod in memory_mod.items():
            if action in weights:
                weights[action] *= mod

        # Personality flavour (ported subset).
        p = self.personality
        if p == Personality.ADVENTUROUS:
            weights["exploring"] *= 1.4; weights["playing"] *= 1.3
        elif p == Personality.TIMID:
            weights["exploring"] *= 0.6; weights["comfort"] *= 1.5
        elif p == Personality.GREEDY:
            weights["eating"] *= 1.6
        elif p == Personality.LAZY:
            weights["playing"] *= 0.5; weights["exploring"] *= 0.7
        elif p == Personality.ENERGETIC:
            weights["playing"] *= 1.5; weights["exploring"] *= 1.2

        for k in weights:
            weights[k] *= random.uniform(0.88, 1.12)

        decision = max(weights, key=weights.get) if any(weights.values()) else "exploring"

        # While carrying a rock, stay in play mode so the squid follows through
        # and throws it. Expose the play intent for the Simulation's rock physics.
        if self.carrying_rock:
            decision = "playing"
        self.wants_to_play = (decision == "playing")

        # Store a trace for the Decisions tab: sorted candidate weights +
        # confidence (how decisively the winner beat the runner-up).
        ordered = sorted(weights.values(), reverse=True)
        confidence = 1.0 if len(ordered) < 2 or ordered[0] == 0 else (ordered[0] - ordered[1]) / ordered[0]
        self.last_decision = {
            "weights": dict(weights),
            "chosen": decision,
            "confidence": confidence,
            "memory_mod": memory_mod,
        }
        return self._execute(decision, food_items, can_see_food)

    def _execute(self, decision, food_items, can_see_food):
        if decision == "eating" and can_see_food and food_items:
            target = min(food_items, key=lambda f: self._dist(f["x"], f["y"]))
            self.move_towards(target["x"], target["y"])
            d = self._dist(target["x"], target["y"])
            if d < 45:
                self.status = "eyeing food"
            else:
                self.status = "approaching food"
            return self.status
        if decision == "sleeping":
            self.is_sleeping = True
            self.status = "settling down to sleep"
            return self.status
        if decision == "comfort":
            self.move_slowly()
            self.status = "seeking comfort"
            self.brain.learn_from_anxiety()
            return self.status
        if decision == "playing":
            self.move_erratically()
            self.status = random.choice(["frolicking", "chasing bubbles", "doing loops"])
            self.brain.learn_from_playing()
            return self.status
        # explore
        self.curiosity = min(100.0, self.curiosity + 3.0)  # activity feeds curiosity
        self.brain.learn_from_curiosity()
        flavours = {
            Personality.TIMID: ["cautiously peeking", "nervously watching"],
            Personality.ADVENTUROUS: ["boldly exploring", "seeking adventure"],
            Personality.GREEDY: ["hunting for food", "scouting"],
            Personality.LAZY: ["lounging", "drifting lazily"],
            Personality.ENERGETIC: ["zooming around", "bouncing about"],
            Personality.STUBBORN: ["patrolling territory", "standing ground"],
        }.get(self.personality, ["wandering", "exploring curiously"])
        style = random.choice(flavours)
        if "zoom" in style or "bounc" in style:
            self.move_erratically()
        elif "loung" in style or "drift" in style:
            self.move_slowly()
        else:
            self.move_randomly()
        self.status = style
        return self.status

    # -------------------------------------------------------------- movement
    def _dist(self, x, y):
        return math.hypot(self.x - x, self.y - y)

    def _step(self, dx, dy, speed_mult=1.0):
        speed = self.base_speed * self._stat_mod("movement_speed") * speed_mult
        length = math.hypot(dx, dy) or 1.0
        self.x += (dx / length) * speed * self._last_dt
        self.y += (dy / length) * speed * self._last_dt
        w, h = self.tank_size
        margin = 30
        self.x = max(margin, min(w - margin, self.x))
        self.y = max(margin, min(h - margin, self.y))
        self.direction = "right" if dx >= 0 else "left"

    def move_towards(self, x, y):
        self._step(x - self.x, y - self.y, 1.2)

    def move_randomly(self):
        self._step(random.uniform(-1, 1), random.uniform(-0.4, 0.4), 1.0)

    def move_slowly(self):
        self._step(random.uniform(-1, 1), random.uniform(-0.3, 0.3), 0.4)

    def move_erratically(self):
        self._step(random.uniform(-1, 1), random.uniform(-1, 1), 1.6)

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "personality": self.personality.value,
            "stats": {name: getattr(self, name) for name in self.CORE_STATS},
            "x": self.x, "y": self.y, "direction": self.direction,
            "is_sleeping": self.is_sleeping, "is_sick": self.is_sick,
            "status": self.status, "age_seconds": self.age_seconds,
            "carrying_rock": self.carrying_rock, "carried_rock_id": self.carried_rock_id,
            "brain": self.brain.to_dict(),
            "memory": self.memory.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, tank_size=(900, 500)) -> "Squid":
        brain = NeuralBrain.from_dict(data["brain"]) if "brain" in data else None
        squid = cls(Personality.from_value(data.get("personality")), tank_size, brain)
        if "memory" in data:
            squid.memory = MemoryManager.from_dict(data["memory"])
        for name, val in data.get("stats", {}).items():
            setattr(squid, name, float(val))
        squid.x = data.get("x", squid.x)
        squid.y = data.get("y", squid.y)
        squid.direction = data.get("direction", "right")
        squid.is_sleeping = data.get("is_sleeping", False)
        squid.is_sick = data.get("is_sick", False)
        squid.carrying_rock = data.get("carrying_rock", False)
        squid.carried_rock_id = data.get("carried_rock_id")
        squid.status = data.get("status", "resurfacing")
        squid.age_seconds = data.get("age_seconds", 0.0)
        return squid

    _last_dt = 0.033  # updated by the simulation each tick
