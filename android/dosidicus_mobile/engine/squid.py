"""Squid - portable pet state, needs dynamics and decision making.

Distilled from ``src/squid.py``, ``src/tamagotchi_logic.py`` and
``src/decision_engine.py`` with all PyQt5 (QGraphicsItem, QTimer, scene) removed.
The squid lives in an abstract tank of ``tank_size`` pixels; the Kivy layer maps
that onto the actual screen. Stats drift over time and are steered by the
shared neural decision engine, which reads the brain state exactly like the
desktop DecisionEngine v5.0 does.
"""

from __future__ import annotations

import math
import random
import uuid as _uuid

from .personality import Personality, PERSONALITY_STAT_MODIFIERS
from .brain import NeuralBrain
from .memory import MemoryManager


class Squid:
    def __init__(self, personality: Personality = None, tank_size=(900, 500), brain: NeuralBrain = None):
        self.personality = Personality.from_value(personality) if personality else random.choice(list(Personality))
        self.uuid = str(_uuid.uuid4())
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
        self.is_dead = False       # set when the squid starves (game over)
        self.color_tint = None     # (r,g,b) floats 0-1, or None for natural colour
        self.name = 'Squid'
        self.status = "just hatched"
        self.age_seconds = 0.0
        self._movement_action = 'idle'
        self._wander_until = 0.0
        self._wander_vector = (1.0, .1)
        self._bound_action = None
        self._bound_until = 0.0
        self.last_decision = {}  # trace of the most recent decision (for the UI)

        # Rock play: the squid can pick up a rock decoration, carry it, then
        # throw it (a form of play). Physics live in the Simulation.
        self.carrying_rock = False
        self.carried_rock_id = None
        self._carry_until = 0.0
        self.wants_to_play = False
        self.play_at = None        # (x, y) of a squid in view that play goes at

        # Startle / flee (a fright response, optionally releasing an ink cloud).
        self.is_startled = False
        self.is_fleeing = False
        self.fighting = False        # transient: in a fight with a visitor (drawn red)
        self._startle_until = 0.0
        self._last_dt = 0.0
        self.plant_targets = []
        self._flee_dir = (1.0, 0.0)

    # ----------------------------------------------------------------- stats
    CORE_STATS = ("hunger", "happiness", "cleanliness", "sleepiness",
                  "satisfaction", "anxiety", "curiosity")

    def _clamp_stats(self):
        for name in self.CORE_STATS:
            setattr(self, name, max(0.0, min(100.0, getattr(self, name))))

    def _stat_mod(self, key, default=1.0):
        return PERSONALITY_STAT_MODIFIERS.get(self.personality, {}).get(key, default)

    def update_needs(self, dt: float):
        """Drift the needs over ``dt`` seconds, personality-weighted.

        Rates are deliberately gentle so a squid takes minutes (not seconds) to
        grow hungry or tired — care should feel unhurried, not frantic.
        """
        hunger_rate = 0.55 * self._stat_mod("hunger_growth")
        energy_rate = 0.45 * self._stat_mod("energy_drain")

        self.hunger += hunger_rate * dt
        self.cleanliness -= 0.32 * dt
        if self.is_sleeping:
            self.sleepiness -= 5.0 * dt
            self.happiness += 0.25 * dt
        else:
            self.sleepiness += energy_rate * dt

        # Derived emotional stats.
        if self.hunger > 75 or self.cleanliness < 25:
            self.happiness -= 0.55 * dt
            self.anxiety += 0.45 * dt * self._stat_mod("anxiety_growth")
        else:
            self.happiness += 0.18 * dt
            self.anxiety -= 0.3 * dt

        if self.cleanliness < 20 and random.random() < 0.01 * dt:
            self.is_sick = True
        if self.is_sick:
            self.happiness -= 0.7 * dt
            self.anxiety += 0.7 * dt
            if self.cleanliness > 60:
                self.is_sick = False

        # Curiosity mean-reverts toward a personality-weighted baseline, so it
        # stays alive (exploring/playing spike it above baseline, boredom pulls
        # it back down) rather than draining to zero.
        curiosity_baseline = 50.0 * self._stat_mod("curiosity_growth")
        self.curiosity += (curiosity_baseline - self.curiosity) * 0.05 * dt
        self.satisfaction -= 0.25 * dt * self._stat_mod("satisfaction_decay")

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
        clamped["is_startled"] = 100.0 if self.is_startled else 0.0
        clamped["pursuing_food"] = 100.0 if self.status.startswith(("approaching", "eyeing")) else 0.0
        clamped["threat_level"] = 100.0 if self.is_startled else 0.0
        clamped["plant_proximity"] = max((max(0.0, 100.0 - self._dist(p['x'], p['y']) / 3)
                                          for p in self.plant_targets), default=0.0)
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
        self.brain.causal_learning.on_action('eating', self.sync_stats_to_brain(True))
        self.is_eating = True
        # Two foods, like the desktop: sushi is the healthy staple; cheese is a
        # richer treat — tastier (more satisfaction/happiness) but greasier, so
        # it fills a little less and dirties the tank a touch.
        if food_type == "cheese":
            dh, ds, dp_, dc = -38.0, 30.0, 16.0, -6.0
        else:  # sushi (default)
            dh, ds, dp_, dc = -45.0, 25.0, 12.0, 0.0
        self.hunger = max(0.0, self.hunger + dh)
        self.satisfaction = min(100.0, self.satisfaction + ds)
        self.happiness = min(100.0, self.happiness + dp_)
        if dc:
            self.cleanliness = max(0.0, self.cleanliness + dc)
        self.brain.learn_from_eating(food_type)
        self.status = f"munching {food_type}"
        self.remember("food", food_type, f"Ate {food_type}",
                      {"hunger": dh, "satisfaction": ds, "happiness": dp_},
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

    def startle(self, source="ambient"):
        """A fright: the squid bolts and its anxiety spikes. Ported from the
        desktop startle_squid — a woken squid is startled awake."""
        self.is_sleeping = False
        self.is_startled = True
        self._startle_until = self.brain.sim_time + random.uniform(2.5, 4.0)
        self.anxiety = min(100.0, self.anxiety + 30.0)
        self.happiness = max(0.0, self.happiness - 8.0)
        self.satisfaction = max(0.0, self.satisfaction - 6.0)
        self._flee_dir = (random.uniform(-1, 1), random.uniform(-1, 1))
        self.status = "hiding" if self.personality == Personality.TIMID else "startled!"
        return self.status

    def flee_step(self):
        """Fast, erratic escape movement while fleeing."""
        self._step(self._flee_dir[0], self._flee_dir[1], 2.4)
        self.status = "fleeing!"

    def give_medicine(self):
        self.is_sick = False
        self.happiness = max(0.0, self.happiness - 5.0)  # medicine tastes bad
        self.anxiety = max(0.0, self.anxiety - 15.0)
        self.status = "recovering"
        return self.status

    # ------------------------------------------------------ decision engine
    def decide(self, brain_state: dict, food_items):
        """Read action neurons with the desktop's exact threshold/ranking rule."""
        from src.decision_engine import select_action, action_activations, wants
        from src.brain_constants import FALLBACK_ACTION
        decision, confidence, urgency = select_action(brain_state)
        if self._bound_action and self.brain.sim_time < self._bound_until:
            decision = self._bound_action
        if decision is None:
            decision = "exploring" if wants(FALLBACK_ACTION, brain_state.get(FALLBACK_ACTION, 0)) else "idle"
        self._movement_action = decision
        self.wants_to_play = decision == "playing"
        self.last_decision = {
            "weights": action_activations(brain_state),
            "base_weights": action_activations(brain_state),
            "chosen": decision, "confidence": confidence,
            "urgency": urgency, "engine": "3.1 neural actions",
        }
        self.brain.causal_learning.on_action(decision, brain_state)
        self.brain.current_action = decision
        return self._execute(decision, food_items)

    def _execute(self, decision, food_items, can_see_food=None):
        self.is_fleeing = decision == 'fleeing'
        if decision == "eating" and food_items:
            target = min(food_items, key=lambda f: self._dist(f["x"], f["y"]))
            self.move_towards(target["x"], target["y"])
            self.status = "eyeing food" if self._dist(target["x"], target["y"]) < 45 else "approaching food"
        elif decision in ("sleeping", "exhausted"):
            self.is_sleeping = True
            self.status = "settling down to sleep"
        elif decision == "fleeing":
            self.is_fleeing = True
            self.flee_step()
        elif decision == "approaching_plant":
            plants = getattr(self, 'plant_targets', [])
            if plants:
                target = min(plants, key=lambda d: self._dist(d['x'], d['y']))
                self.move_towards(target['x'], target['y'])
            else:
                self.move_slowly()
            self.status = "seeking shelter"
        elif decision == "playing":
            if getattr(self, 'play_at', None) is not None:
                self.move_towards(*self.play_at)      # at the squid in view
                self.status = "approaching squid"
            else:
                self.move_erratically()
                self.status = "playing"
        elif decision == "exploring":
            self.move_randomly()
            self.status = "exploring"
        else:
            self.status = "sleeping peacefully" if self.is_sleeping else "resting"
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
        if not self.noticing:   # a held gaze is not turned away by swimming
            self.direction = "right" if dx >= 0 else "left"

    # ------------------------------------------------------------ attention
    #: How long something that has just appeared holds the squid's gaze.
    NOTICE_SECONDS = 4.0
    _gaze_until = 0.0

    def notice(self, x, seconds=NOTICE_SECONDS):
        """Something has just appeared at x: turn to look at it, and hold the gaze.

        The desktop squid's view cone swings onto a newcomer (src/squid.py
        notice); this squid sees the way it faces, so it turns to face it.
        Asleep, it notices nothing. Returns whether it looked.
        """
        if self.is_sleeping:
            return False
        self._gaze_until = self.brain.sim_time + seconds
        self.look_towards(x)
        return True

    @property
    def noticing(self):
        return self.brain.sim_time < self._gaze_until

    def look_towards(self, x):
        self.direction = "right" if x >= self.x else "left"

    def stop_noticing(self):
        self._gaze_until = 0.0

    def move_towards(self, x, y):
        self._step(x - self.x, y - self.y, 1.2)

    def move_randomly(self):
        if self.brain.sim_time >= self._wander_until:
            self._wander_vector = (random.uniform(-1, 1), random.uniform(-.4, .4))
            self._wander_until = self.brain.sim_time + random.uniform(1.5, 4)
        dx, dy = self._wander_vector
        if self.x <= 31 or self.x >= self.tank_size[0] - 31:
            dx = -dx
        if self.y <= 31 or self.y >= self.tank_size[1] - 31:
            dy = -dy
        self._wander_vector = (dx, dy)
        self._step(dx, dy, 1.0)

    def move_slowly(self):
        self._step(random.uniform(-1, 1), random.uniform(-0.3, 0.3), 0.4)

    def move_erratically(self):
        self._step(random.uniform(-1, 1), random.uniform(-1, 1), 1.6)

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "personality": self.personality.value,
            "uuid": self.uuid,
            "name": self.name,
            "stats": {name: getattr(self, name) for name in self.CORE_STATS},
            "x": self.x, "y": self.y, "direction": self.direction,
            "is_sleeping": self.is_sleeping, "is_sick": self.is_sick,
            "is_dead": self.is_dead,
            "color_tint": list(self.color_tint) if self.color_tint else None,
            # desktop compatibility: it stores tint_color as 0-255 ints
            "tint_color": ([int(c * 255) for c in self.color_tint]
                           if self.color_tint else None),
            "status": self.status, "age_seconds": self.age_seconds,
            "carrying_rock": self.carrying_rock, "carried_rock_id": self.carried_rock_id,
            "brain": self.brain.to_dict(),
            "memory": self.memory.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict, tank_size=(900, 500)) -> "Squid":
        brain = NeuralBrain.from_dict(data["brain"]) if "brain" in data else None
        squid = cls(Personality.from_value(data.get("personality")), tank_size, brain)
        if data.get("uuid"):
            squid.uuid = data["uuid"]
        squid.name = str(data.get('name') or 'Squid').strip()[:32] or 'Squid'
        if "memory" in data:
            squid.memory = MemoryManager.from_dict(data["memory"])
        for name, val in data.get("stats", {}).items():
            setattr(squid, name, float(val))
        squid.x = data.get("x", squid.x)
        squid.y = data.get("y", squid.y)
        squid.direction = data.get("direction", "right")
        squid.is_sleeping = data.get("is_sleeping", False)
        squid.is_sick = data.get("is_sick", False)
        squid.is_dead = data.get("is_dead", False)
        if data.get("color_tint"):
            squid.color_tint = tuple(data["color_tint"])
        elif data.get("tint_color"):   # desktop archive (0-255 ints)
            squid.color_tint = tuple(c / 255.0 for c in data["tint_color"])
        squid.carrying_rock = data.get("carrying_rock", False)
        squid.carried_rock_id = data.get("carried_rock_id")
        squid.status = data.get("status", "resurfacing")
        squid.age_seconds = data.get("age_seconds", 0.0)
        return squid

    _last_dt = 0.033  # updated by the simulation each tick
