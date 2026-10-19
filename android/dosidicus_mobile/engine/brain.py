"""Kivy data adapter over the desktop 3.1 neural engine.

Propagation, signed/directed plasticity, causal credit, capability-driven
neurogenesis, provenance and sleep consolidation all execute shared src code.
"""
from __future__ import annotations

import math
import time
from types import SimpleNamespace

from .shared import HeadlessBrain, TrainingConfig
from .personality import Personality
from src.brain_constants import ACTION_NEURONS, REQUIRED_NEURONS, innate_bindings
from src.learning import HebbianLearning, LearningConfig
from src.personality import Personality as CorePersonality
from src.neuron_binding import NeuronOutputBinding, OutputTriggerMode


class NeuralBrain(HeadlessBrain):
    def __init__(self, personality=Personality.ADVENTUROUS, config=None):
        self.personality = Personality.from_value(personality)
        settings = LearningConfig()
        overrides = config or {}
        training = TrainingConfig(
            learning_rate=overrides.get('base_learning_rate', settings.hebbian['base_learning_rate']),
            weight_decay=overrides.get('weight_decay', settings.hebbian['weight_decay']),
            hebbian_interval=max(1, int(settings.hebbian['learning_interval'] / 1000)),
            neurogenesis_cooldown=overrides.get('cooldown', settings.neurogenesis['cooldown']),
            max_neurons=overrides.get('max_neurons', settings.neurogenesis.get('max_neurons', 32)),
        )
        super().__init__(training)
        self.last_modulation = {}
        self._tick_remainder = 0.0
        self._learning_elapsed = 0.0
        self.last_consolidation = None
        self.neurogenesis_active = False
        self._bindings = []
        self.install_bindings()
        self._reflexes = HebbianLearning(
            SimpleNamespace(personality=CorePersonality(self.personality.value)),
            SimpleNamespace(brain_widget=self), self.learning_config)

    @property
    def sim_time(self):
        return self.sim_seconds

    @sim_time.setter
    def sim_time(self, value):
        self.sim_seconds = float(value)

    @property
    def neuron_names(self):
        return list(self.positions)

    @property
    def neurogenesis(self):
        return self.neurogenesis_data

    @property
    def recent_events(self):
        return [dict(a=e.edge[0], b=e.edge[1], dw=e.delta, weight=e.new_weight,
                     t=e.timestamp, stdp=e.mechanism == 'stdp',
                     replay=e.mechanism == 'consolidation', mechanism=e.mechanism)
                for e in self.ledger.recent_events(limit=40)]

    @property
    def stdp_potentiations(self):
        learner = self.plasticity.stdp
        return int(learner.get_stats()['ltp_events']) if learner is not None else 0

    def set_weight(self, a, b, value):
        # A -> B and B -> A are different synapses, including after import.
        return self.apply_weight_change((a, b), value=value,
                                        mechanism='manual', create=True)

    def get_weight(self, a, b):
        return self.weights.get((a, b), 0.0)

    def strengthen_connection(self, a, b, amount, mechanism="reflex", reason=None):
        if (a, b) not in self.weights and (b, a) not in self.weights:
            if any(self.is_connector_neuron(name) and self.get_neuron_degree(name) >= 3
                   for name in (a, b)):
                return
        return self.apply_weight_change((a, b), delta=amount,
                                        mechanism=mechanism,
                                        detail={'note': reason or 'an innate response to what just happened'},
                                        create=True, directed=False)

    def propagate(self, clamped=None):
        if clamped is not None:
            self.update_state(clamped)
        return super().propagate()

    def advance(self, dt, clamped, sleeping=False):
        """One cognitive tick per simulated second, independent of render FPS."""
        if not math.isfinite(dt) or dt < 0:
            raise ValueError('Simulation dt must be finite and nonnegative')
        self._tick_remainder += dt
        born = []
        self.last_modulation = {}
        while self._tick_remainder >= 1.0 - 1e-9:
            self._tick_remainder = max(0.0, self._tick_remainder - 1.0)
            self.advance_clock()
            self.propagate(clamped)
            for stat, delta in self.compute_neural_modulation().items():
                self.last_modulation[stat] = self.last_modulation.get(stat, 0.0) + delta
            self._learning_elapsed += 1.0
            if self._learning_elapsed >= self.config.hebbian_interval:
                self.perform_hebbian_learning()
                self._learning_elapsed = 0.0
            if 'external_stimulus' in self.state:
                self.state['external_stimulus'] *= 0.8
            name = self.check_neurogenesis(clamped, int(self.sim_time))
            if name:
                born.append(name)
            summary = self.consolidate(sleeping)
            if summary:
                self.last_consolidation = summary
        return born

    def learn_from_eating(self, food_type=None):
        self._reflexes.learn_from_eating()

    def learn_from_playing(self):
        self._reflexes.learn_from_decoration_interaction('rock')

    def learn_from_cleaning(self):
        self._reflexes.learn_from_organization()

    def learn_from_curiosity(self):
        self._reflexes.learn_from_curiosity()

    def learn_from_anxiety(self):
        self._reflexes.learn_from_anxiety()

    def register_novelty(self, amount=2.0):
        from src.brain_constants import INPUT_SENSORS
        self.positions.setdefault('external_stimulus', INPUT_SENSORS['external_stimulus'])
        self.state['external_stimulus'] = min(100.0, amount * 30.0)

    def register_stress(self, amount):
        self.state['threat_level'] = min(100.0,
            self.state.get('threat_level', 0.0) + amount * 20.0)

    def install_bindings(self):
        self._bindings = [NeuronOutputBinding.from_dict(d) for d in self.output_bindings]
        for neuron, hook, threshold, cooldown, probability in innate_bindings():
            if neuron in self.positions and not any(b.neuron_name == neuron for b in self._bindings):
                self._bindings.append(NeuronOutputBinding(neuron, hook,
                    threshold=threshold, trigger_mode=OutputTriggerMode.THRESHOLD_RISING,
                    cooldown=cooldown, probability=probability))
        self.output_bindings = [b.to_dict() for b in self._bindings]

    def to_dict(self):
        data = self.export_brain()
        data.update(engine_version='3.1', personality=self.personality.value,
                    sim_time=self.sim_time, tick_remainder=self._tick_remainder,
                    clock={'kind': 'simulation', 'now': self.sim_time},
                    last_neurogenesis_tick=self.last_neurogenesis_tick,
                    growth_clock={'last_growth_at': self.enhanced_neurogenesis._last_growth_at,
                                  'first_real_tick': self.enhanced_neurogenesis._first_real_tick},
                    learning_elapsed=self._learning_elapsed,
                    config=dict(base_learning_rate=self.config.learning_rate,
                        weight_decay=self.config.weight_decay,
                        cooldown=self.config.neurogenesis_cooldown,
                        max_neurons=self.config.max_neurons),
                    neurogenesis_data=self.neurogenesis_data,
                    enhanced_neurogenesis=self.enhanced_neurogenesis.to_dict(),
                    functional_neurons={n: fn.to_dict() for n, fn in
                        self.enhanced_neurogenesis.functional_neurons.items()})
        return data

    @classmethod
    def from_dict(cls, data):
        from .brain_io import normalise_brain
        from src.brain_clock import rebase_cognitive_state
        target_time = float(data.get('sim_time', 0.0))
        payload = rebase_cognitive_state(normalise_brain(data), target_time, kind='simulation')
        brain = cls(data.get('personality', 'adventurous'), data.get('config'))
        if not brain.load_brain(payload):
            raise ValueError('Cannot load brain')
        brain.state.update(payload.get('state', {}))
        brain.sim_time = target_time
        brain.capability._decay_last = target_time
        brain.last_neurogenesis_tick = int(payload.get('last_neurogenesis_tick', 0))
        brain._tick_remainder = float(data.get('tick_remainder', 0.0))
        brain._learning_elapsed = float(data.get('learning_elapsed', 0.0))
        brain.install_bindings()
        growth = data.get('enhanced_neurogenesis') or {'functional_neurons': data.get('functional_neurons', {})}
        brain.enhanced_neurogenesis.from_dict(payload.get('enhanced_neurogenesis') or growth)
        brain.new_neurons = set(brain.neurogenesis_data.get('new_neurons', []))
        for key, attribute in (('last_growth_at', '_last_growth_at'), ('first_real_tick', '_first_real_tick')):
            if key in payload.get('growth_clock', {}):
                setattr(brain.enhanced_neurogenesis, attribute, payload['growth_clock'][key])
        return brain
