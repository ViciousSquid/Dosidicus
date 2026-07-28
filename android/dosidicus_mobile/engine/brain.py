"""NeuralBrain - the portable STRINg cognitive core.

A faithful, GUI-free port of the learning + neurogenesis logic that lives in
``src/learning.py``, ``src/neurogenesis.py`` and ``src/brain_widget.py`` in the
desktop project, distilled to what the mobile MVP needs:

* an explicit set of neurons with 2-D positions (for the live brain view),
* a symmetric weight map between every pair of neurons, bounded to [-1, 1],
* a continuous **Hebbian** update ("neurons that fire together, wire together")
  plus the original event-driven reinforcement hooks (learn_from_eating, ...),
* **neurogenesis**: sustained novelty / stress / reward grows brand-new neurons
  that wire themselves into the existing network,
* a light NumPy propagation pass so grown neurons develop emergent activation.

Everything is JSON-serialisable so a squid's whole cognitive history persists.
"""

from __future__ import annotations

import math
import time
from typing import Dict, Tuple

import numpy as np

from . import constants
from .personality import Personality, PERSONALITY_LEARNING_MODIFIERS

# Neurons that never form learned connections (status flags, not drives).
EXCLUDED_NEURONS = {"is_sick", "is_eating", "is_sleeping", "pursuing_food"}


class NeuralBrain:
    def __init__(self, personality: Personality = Personality.ADVENTUROUS, config: dict = None):
        self.personality = Personality.from_value(personality)
        self.config = {
            "base_learning_rate": 0.1,         # per second (scaled by dt)
            "co_activation_threshold": 0.6,    # both neurons must fire above this
            "weight_decay": 0.02,              # per-second relaxation of idle links
            "min_weight": -1.0,
            "max_weight": 1.0,
            # neurogenesis
            "novelty_threshold": 6.0,
            "stress_threshold": 5.0,
            "reward_threshold": 5.0,
            "cooldown": 90.0,                  # seconds of simulated life between births
            "decay_rate": 0.98,                # per-second counter decay (slow burn)
            "new_neuron_connection_strength": 0.5,
            "max_new_neurons": 8,
            # STDP (spike-timing-dependent plasticity)
            "stdp_lr": 0.06,                   # potentiation per spike pairing
            "stdp_tau": 2.0,                   # timing sensitivity (sim seconds)
            "stdp_window": 3.0,                # max pre->post gap that still wires
        }
        if config:
            self.config.update(config)

        # Neuron activations on a 0-100 scale.
        self.state: Dict[str, float] = {}
        # Virtual-canvas positions for rendering.
        self.neuron_positions: Dict[str, Tuple[float, float]] = {}
        # Symmetric weights, keyed by ordered pair (a, b) with a < b canonical,
        # but stored both ways for O(1) lookup like the desktop app does.
        self.weights: Dict[Tuple[str, str], float] = {}

        # Neurogenesis bookkeeping.
        self.neurogenesis = {
            "new_neurons": [],
            "novelty_counter": 0.0,
            "stress_counter": 0.0,
            "reward_counter": 0.0,
        }
        self.neurogenesis_active = False
        # Neurogenesis timing runs on an internal simulation clock (seconds of
        # simulated life), not wall-clock, so fast-forward and tests behave the
        # same as real-time play.
        self.sim_time = 0.0
        self._neurogenesis_boost_until = 0.0
        self.last_neurogenesis_time = 0.0

        # STDP bookkeeping: when each neuron last "spiked" (crossed the
        # co-activation threshold on a rising edge) in simulation seconds.
        self.last_spike = {}
        self._prev_spike = {}
        self.stdp_potentiations = 0  # count of STDP weight strengthenings (lifetime)

        # A trace of the most recent learning events for the UI to surface.
        self.recent_events = []

        self._init_default_neurons()

    # ------------------------------------------------------------------ setup
    def _init_default_neurons(self):
        for name, pos in constants.REQUIRED_NEURONS.items():
            self.neuron_positions[name] = tuple(pos)
            self.state[name] = constants.DEFAULT_STATE.get(name, 0.0)
        for name, pos in constants.INPUT_SENSORS.items():
            self.neuron_positions[name] = tuple(pos)
            self.state[name] = 0.0
        # Seed a few weak innate connections so the graph isn't empty at birth.
        seeds = [
            ("hunger", "satisfaction", 0.15),
            ("cleanliness", "happiness", 0.1),
            ("curiosity", "happiness", 0.12),
            ("anxiety", "cleanliness", -0.1),
            ("sleepiness", "happiness", -0.1),
            ("can_see_food", "hunger", 0.2),
        ]
        for a, b, w in seeds:
            self.set_weight(a, b, w)

    # ---------------------------------------------------------------- weights
    def set_weight(self, a: str, b: str, value: float):
        value = max(self.config["min_weight"], min(self.config["max_weight"], value))
        self.weights[(a, b)] = value
        self.weights[(b, a)] = value

    def get_weight(self, a: str, b: str) -> float:
        return self.weights.get((a, b), 0.0)

    @property
    def neuron_names(self):
        return list(self.neuron_positions.keys())

    # ------------------------------------------------------------ propagation
    def propagate(self, clamped: dict):
        """One NumPy forward pass.

        ``clamped`` maps neuron name -> activation for neurons whose value is
        dictated by the outside world (the 7 core stats + sensors). Every other
        neuron (grown by neurogenesis) settles to a sigmoid of its weighted
        input, giving emergent activation that the brain view can display.
        """
        names = self.neuron_names
        idx = {n: i for i, n in enumerate(names)}
        n = len(names)

        v = np.array([self.state.get(name, 0.0) for name in names], dtype=float) / 100.0
        for name, val in clamped.items():
            if name in idx:
                v[idx[name]] = max(0.0, min(1.0, val / 100.0))

        # Weight matrix.
        W = np.zeros((n, n), dtype=float)
        for (a, b), w in self.weights.items():
            if a in idx and b in idx:
                W[idx[a], idx[b]] = w

        clamped_mask = np.array(
            [name in clamped or constants.is_sensor(name) for name in names]
        )
        # Settle free neurons with a couple of relaxation steps.
        for _ in range(2):
            net = W.dot(v)
            settled = 1.0 / (1.0 + np.exp(-4.0 * (net - 0.0)))
            v = np.where(clamped_mask, v, settled)

        for name in names:
            self.state[name] = float(np.clip(v[idx[name]] * 100.0, 0.0, 100.0))
        return v, idx

    # -------------------------------------------------------------- learning
    def _personality_lr(self, a: str, b: str, lr: float) -> float:
        mods = PERSONALITY_LEARNING_MODIFIERS.get(self.personality, {})
        if self.personality == Personality.TIMID:
            lr *= mods.get("learning_rate_reduction", 1.0)
        elif self.personality == Personality.ADVENTUROUS:
            lr *= mods.get("learning_rate_boost", 1.0)
        if self.personality == Personality.GREEDY:
            priority = mods.get("connection_prioritization", [])
            if a in priority or b in priority:
                lr *= 1.3
        if self.personality == Personality.STUBBORN:
            lr *= mods.get("unlearning_resistance", 1.0)
        return lr

    def strengthen_connection(self, a: str, b: str, amount: float):
        """Event-driven reinforcement, ported from learning.strengthen_connection."""
        if a in EXCLUDED_NEURONS or b in EXCLUDED_NEURONS or a == b:
            return
        if a not in self.state or b not in self.state:
            return
        amount = self._personality_lr(a, b, amount)
        if self.neurogenesis_active:
            amount *= 1.5
        prev = self.get_weight(a, b)
        self.set_weight(a, b, prev + amount)
        self._log_event(a, b, self.get_weight(a, b) - prev)

    def hebbian_step(self, dt: float = 1.0):
        """Continuous Hebbian learning across all eligible neuron pairs.

        dw = lr * (vi - t) * (vj - t) * dt when both neurons fire above the
        threshold, otherwise the weight relaxes toward zero. Scaling by ``dt``
        keeps learning framerate-independent and gradual, so you actually watch
        connections strengthen over tens of seconds rather than snapping to 1.0.
        """
        self.sim_time += dt
        lr = self.config["base_learning_rate"]
        t = self.config["co_activation_threshold"]
        decay = self.config["weight_decay"] * dt
        names = [n for n in self.neuron_names if n not in EXCLUDED_NEURONS]

        for i, a in enumerate(names):
            va = self.state.get(a, 0.0) / 100.0
            for b in names[i + 1:]:
                vb = self.state.get(b, 0.0) / 100.0
                prev = self.get_weight(a, b)
                if va > t and vb > t:
                    rate = self._personality_lr(a, b, lr)
                    if self.neurogenesis_active:
                        rate *= 1.5
                    dw = rate * (va - t) * (vb - t) * dt
                    self.set_weight(a, b, prev + dw)
                    if abs(dw) > 1e-4:
                        self._log_event(a, b, self.get_weight(a, b) - prev)
                elif prev != 0.0:
                    # Relax unused connections toward zero.
                    self.set_weight(a, b, prev * (1.0 - decay))

    def stdp_step(self):
        """Spike-timing-dependent plasticity.

        A neuron "spikes" when its activation crosses the co-activation
        threshold on a rising edge. When neuron B spikes shortly after A, the
        A-B connection is potentiated by the STDP kernel lr * exp(-Δt/tau)
        (pre-before-post causal strengthening). Because the network stores
        undirected weights, this reinforces the pair; the closer in time two
        neurons fire, the more they wire together.
        """
        t = self.config["co_activation_threshold"]
        lr = self.config["stdp_lr"]
        tau = self.config["stdp_tau"]
        window = self.config["stdp_window"]
        now = self.sim_time

        # A neuron "spikes" on a burst of activity: it crosses the threshold on
        # a rising edge, OR its activation jumps sharply while already active
        # (e.g. satisfaction leaping when the squid eats). Bursts are what create
        # the temporally-clustered firing STDP keys off.
        spiked = []
        for name in self.neuron_names:
            if name in EXCLUDED_NEURONS:
                continue
            v = self.state.get(name, 0.0) / 100.0
            prev = self._prev_spike.get(name, v)
            rising_cross = v > t and prev <= t
            burst = v > 0.5 and (v - prev) > 0.05
            if rising_cross or burst:
                spiked.append(name)
            self._prev_spike[name] = v

        for b in spiked:
            for a, ts in list(self.last_spike.items()):
                if a == b or a in EXCLUDED_NEURONS or a not in self.state:
                    continue
                dt_spike = now - ts
                if 0.0 <= dt_spike <= window:
                    dw = lr * math.exp(-dt_spike / tau)
                    if dw > 0.004:
                        prev = self.get_weight(a, b)
                        self.set_weight(a, b, prev + dw)
                        self.stdp_potentiations += 1
                        self._log_event(a, b, self.get_weight(a, b) - prev, stdp=True)
            self.last_spike[b] = now

    def _log_event(self, a: str, b: str, dw: float, stdp: bool = False):
        self.recent_events.append({
            "a": a, "b": b, "dw": round(dw, 4),
            "weight": round(self.get_weight(a, b), 4),
            "t": time.time(), "stdp": stdp,
        })
        if len(self.recent_events) > 40:
            self.recent_events = self.recent_events[-40:]

    # Ported behavioural learning hooks -----------------------------------
    def learn_from_eating(self, food_type: str = None):
        lr = self.config["base_learning_rate"]
        self.strengthen_connection("hunger", "satisfaction", lr * 2.0)
        self.strengthen_connection("hunger", "happiness", lr * 1.5)
        p = self.personality
        if p == Personality.GREEDY:
            self.strengthen_connection("hunger", "satisfaction", lr * 3.0)
            self.strengthen_connection("satisfaction", "happiness", lr * 2.0)
        elif p == Personality.TIMID:
            self.strengthen_connection("hunger", "anxiety", lr * 0.5)
        elif p == Personality.ADVENTUROUS:
            self.strengthen_connection("hunger", "curiosity", lr * 1.8)
        self.neurogenesis["reward_counter"] += 1.0

    def learn_from_playing(self):
        lr = self.config["base_learning_rate"]
        self.strengthen_connection("curiosity", "satisfaction", lr * 1.5)
        self.strengthen_connection("curiosity", "happiness", lr)
        if self.personality == Personality.ENERGETIC:
            self.strengthen_connection("curiosity", "happiness", lr * 2.0)
        self.neurogenesis["reward_counter"] += 0.6

    def learn_from_cleaning(self):
        lr = self.config["base_learning_rate"]
        self.strengthen_connection("cleanliness", "happiness", lr * 1.5)
        self.strengthen_connection("cleanliness", "satisfaction", lr)

    def learn_from_curiosity(self):
        # Routine exploration strengthens links but is NOT treated as novelty;
        # only genuinely new stimuli (see register_novelty) drive neurogenesis,
        # so an idle wanderer's brain grows differently from an engaged one.
        lr = self.config["base_learning_rate"]
        self.strengthen_connection("curiosity", "happiness", lr)
        self.strengthen_connection("curiosity", "satisfaction", lr)

    def register_novelty(self, amount: float = 2.0):
        """A genuinely new stimulus appeared (e.g. fresh food dropped in)."""
        self.neurogenesis["novelty_counter"] += amount

    def register_stress(self, amount: float):
        """Sustained distress accumulates toward a defensive neuron."""
        self.neurogenesis["stress_counter"] += amount

    def learn_from_anxiety(self):
        lr = self.config["base_learning_rate"]
        self.strengthen_connection("anxiety", "cleanliness", lr)
        if self.personality == Personality.TIMID:
            self.strengthen_connection("anxiety", "happiness", -lr * 0.5)

    # ------------------------------------------------------------ neurogenesis
    def decay_neurogenesis_counters(self, dt: float = 1.0):
        # decay_rate is expressed per-second; raise to dt for framerate independence.
        r = self.config["decay_rate"] ** dt
        for key in ("novelty_counter", "stress_counter", "reward_counter"):
            self.neurogenesis[key] *= r

    def check_neurogenesis(self):
        """Grow a neuron if a sustained trigger crosses threshold. Ported from
        HebbianLearning.check_neurogenesis_conditions + create_new_neuron."""
        now = self.sim_time
        if now >= self._neurogenesis_boost_until:
            self.neurogenesis_active = False
        if now - self.last_neurogenesis_time < self.config["cooldown"]:
            return None
        if len(self.neurogenesis["new_neurons"]) >= self.config["max_new_neurons"]:
            return None

        triggers = [
            ("novelty", self.neurogenesis["novelty_counter"], self.config["novelty_threshold"]),
            ("stress", self.neurogenesis["stress_counter"], self.config["stress_threshold"]),
            ("reward", self.neurogenesis["reward_counter"], self.config["reward_threshold"]),
        ]
        for kind, value, threshold in triggers:
            if value > threshold:
                return self._grow_neuron(kind)
        return None

    def _grow_neuron(self, kind: str):
        base = {"novelty": "novel", "stress": "defense", "reward": "reward"}.get(kind, "new")
        name = f"{base}_{len(self.neurogenesis['new_neurons'])}"

        # Place it near the neuron it is most associated with.
        anchor = {"novelty": "curiosity", "stress": "anxiety", "reward": "satisfaction"}[kind]
        ax, ay = self.neuron_positions.get(anchor, (450, 250))
        # Golden-angle spiral so successive grown neurons fan out rather than pile up.
        i = len(self.neurogenesis["new_neurons"])
        angle = i * 2.399963  # golden angle in radians
        radius = 70 + 16 * i
        self.neuron_positions[name] = (
            max(20, min(880, ax + radius * math.cos(angle))),
            max(20, min(480, ay + radius * math.sin(angle))),
        )
        self.state[name] = 50.0
        self.neurogenesis["new_neurons"].append(name)

        strength = self.config["new_neuron_connection_strength"]
        for other in list(self.neuron_positions.keys()):
            if other == name:
                continue
            w = strength * (1.5 if other == anchor else 1.0)
            self.set_weight(name, other, w)

        # Reset the trigger that fired and start a learning boost.
        self.neurogenesis[f"{kind}_counter"] = 0.0
        self.neurogenesis_active = True
        self._neurogenesis_boost_until = self.sim_time + 10.0
        self.last_neurogenesis_time = self.sim_time
        self.recent_events.append({
            "a": name, "b": anchor, "dw": strength,
            "weight": strength, "t": time.time(), "born": kind,
        })
        return name

    # ---------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "personality": self.personality.value,
            "state": self.state,
            "neuron_positions": {k: list(v) for k, v in self.neuron_positions.items()},
            "weights": {f"{a}|{b}": w for (a, b), w in self.weights.items()},
            "neurogenesis": self.neurogenesis,
            "sim_time": self.sim_time,
            "last_neurogenesis_time": self.last_neurogenesis_time,
            "last_spike": self.last_spike,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NeuralBrain":
        brain = cls(Personality.from_value(data.get("personality", "adventurous")),
                    config=data.get("config"))
        brain.state = {k: float(v) for k, v in data.get("state", {}).items()}
        brain.neuron_positions = {
            k: tuple(v) for k, v in data.get("neuron_positions", {}).items()
        }
        brain.weights = {}
        for key, w in data.get("weights", {}).items():
            a, b = key.split("|", 1)
            brain.weights[(a, b)] = float(w)
        ng = data.get("neurogenesis")
        if ng:
            brain.neurogenesis.update(ng)
        brain.sim_time = float(data.get("sim_time", 0.0))
        brain.last_neurogenesis_time = float(data.get("last_neurogenesis_time", 0.0))
        brain.last_spike = {k: float(v) for k, v in data.get("last_spike", {}).items()}
        return brain
