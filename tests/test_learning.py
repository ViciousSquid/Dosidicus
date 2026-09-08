"""
Behavioural tests for plasticity, STDP, sleep consolidation and neurogenesis.

The claim under test is the project's own: a squid that is well cared for and
stimulated should develop a different brain from one that is neglected. These
tests therefore assert on the STRUCTURE that experience produces, not on
whether a learning function was called.
"""

import math
import os
import random
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.neural_provenance import CausalLedger, RecordedSynapses  # noqa: E402
from src.plasticity import PlasticityEngine, PlasticityConfig  # noqa: E402


def run_window(engine, samples, commits=1, weights=None, neurons=None):
    """Feed samples, then commit. Returns the resulting weight dict."""
    weights = {} if weights is None else weights
    neurons = neurons or sorted({k for s in samples for k in s})
    for _ in range(commits):
        for sample in samples:
            engine.observe(sample, neurons)
        result = engine.commit(weights=weights, neuron_names=neurons)
        for edge, info in result['weight_updates'].items():
            weights[edge] = info['new_weight']
    return weights


class CorrelationRuleTests(unittest.TestCase):
    """delta = lr * r(a, b): signed, scale-free, and zero for the unrelated."""

    def setUp(self):
        cfg = PlasticityConfig()
        cfg.stdp_enabled = False          # isolate the Hebbian term
        cfg.min_pairs_per_cycle = 32
        self.engine = PlasticityEngine(cfg)

    def _samples(self, n, fn):
        return [fn(i) for i in range(n)]

    def test_correlated_pair_becomes_excitatory(self):
        samples = self._samples(60, lambda i: {
            'sensor': 100.0 if i % 4 == 0 else 0.0,
            'target': 90.0 if i % 4 == 0 else 20.0,
        })
        weights = run_window(self.engine, samples, commits=30)
        edge = ('sensor', 'target')
        self.assertIn(edge, weights)
        self.assertGreater(weights[edge], 0.5,
                           "a reliably co-varying pair did not become excitatory")

    def test_anticorrelated_pair_becomes_inhibitory(self):
        """The headline capability: weights must be able to go negative.

        An avoidance behaviour is an inhibitory synapse. The previous rule
        (delta = lr * a1 * a2) was never negative, so no amount of experience
        could produce one.
        """
        samples = self._samples(60, lambda i: {
            'sensor': 100.0 if i % 4 == 0 else 0.0,
            'target': 10.0 if i % 4 == 0 else 85.0,
        })
        weights = run_window(self.engine, samples, commits=30)
        edge = ('sensor', 'target')
        self.assertIn(edge, weights)
        self.assertLess(weights[edge], -0.5,
                        "an inverse association failed to produce inhibition")

    def test_unrelated_pair_stays_near_zero(self):
        rng = random.Random(7)
        samples = self._samples(120, lambda i: {
            'sensor': 100.0 if i % 4 == 0 else 0.0,
            'target': rng.uniform(40.0, 60.0),
        })
        weights = run_window(self.engine, samples, commits=30)
        value = weights.get(('sensor', 'target'), 0.0)
        self.assertLess(abs(value), 0.35,
                        "an unrelated pair drifted; the old rule saturated these to +1")

    def test_a_constant_neuron_teaches_nothing(self):
        samples = self._samples(60, lambda i: {
            'sensor': 100.0 if i % 3 == 0 else 0.0,
            'target': 50.0,          # never moves
        })
        weights = run_window(self.engine, samples, commits=20)
        self.assertAlmostEqual(weights.get(('sensor', 'target'), 0.0), 0.0, places=6)

    def test_rule_is_scale_free(self):
        """A small but reliable swing must learn as strongly as a large one."""
        big = run_window(PlasticityEngine(self.engine.config),
                         self._samples(60, lambda i: {
                             'a': 100.0 if i % 4 == 0 else 0.0,
                             'b': 100.0 if i % 4 == 0 else 0.0}),
                         commits=20)
        small = run_window(PlasticityEngine(self.engine.config),
                           self._samples(60, lambda i: {
                               'a': 55.0 if i % 4 == 0 else 45.0,
                               'b': 55.0 if i % 4 == 0 else 45.0}),
                           commits=20)
        self.assertAlmostEqual(big[('a', 'b')], small[('a', 'b')], delta=0.05)

    def test_brief_events_survive_the_window(self):
        """A 1-in-30 event still learns; a 30s snapshot would never see it.

        Measured against the real game: can_see_food was ON for 7 ticks in 300,
        and a 30-second sampler caught 0 of them.
        """
        samples = self._samples(120, lambda i: {
            'flash': 100.0 if i % 30 == 0 else 0.0,
            'target': 95.0 if i % 30 == 0 else 30.0,
        })
        weights = run_window(self.engine, samples, commits=25)
        self.assertGreater(weights.get(('flash', 'target'), 0.0), 0.5)


class SynapseOrientationTests(unittest.TestCase):
    """No synapse may point at a sensor; core stats are valid targets."""

    def setUp(self):
        self.engine = PlasticityEngine(PlasticityConfig())

    def test_never_points_into_a_sensor(self):
        edge = self.engine.orient(('anxiety', 'can_see_food'), {})
        self.assertEqual(edge, ('can_see_food', 'anxiety'))

    def test_two_sensors_produce_no_synapse(self):
        self.assertIsNone(self.engine.orient(('can_see_food', 'is_startled'), {}))

    def test_core_stats_are_valid_targets(self):
        """Otherwise a default eight-neuron brain could never learn anything."""
        edge = self.engine.orient(('can_see_food', 'happiness'), {})
        self.assertEqual(edge, ('can_see_food', 'happiness'))

    def test_existing_edges_keep_their_direction(self):
        weights = {('happiness', 'anxiety'): 0.3}
        self.assertEqual(self.engine.orient(('anxiety', 'happiness'), weights),
                         ('happiness', 'anxiety'))

    def test_coverage_scales_with_the_brain(self):
        """A fixed 2 pairs/cycle meant a 20-neuron brain barely learned."""
        self.assertGreaterEqual(self.engine.pairs_per_cycle(21), 10)
        self.assertGreaterEqual(self.engine.pairs_per_cycle(190), 60)


class DivergentUpbringingTests(unittest.TestCase):
    """The project's central claim, as an executable assertion."""

    @staticmethod
    def _life(regime, ticks=900, seed=1):
        cfg = PlasticityConfig()
        cfg.stdp_enabled = False
        cfg.min_pairs_per_cycle = 32
        engine = PlasticityEngine(cfg)
        rng = random.Random(seed)
        weights = {}
        neurons = ['can_see_food', 'hunger', 'happiness', 'satisfaction',
                   'anxiety', 'cleanliness', 'curiosity']
        for t in range(ticks):
            engine.observe(regime(t, rng), neurons)
            if (t + 1) % 30 == 0:
                result = engine.commit(weights=weights, neuron_names=neurons)
                for edge, info in result['weight_updates'].items():
                    weights[edge] = info['new_weight']
        return weights

    @staticmethod
    def _cared(t, rng):
        fed = (t % 40) < 6
        return {'can_see_food': 100.0 if fed else 0.0,
                'hunger': 20.0 if fed else 55.0,
                'satisfaction': 90.0 if fed else 55.0,
                'happiness': 85.0 + rng.uniform(-4, 4),
                'cleanliness': 90.0 + rng.uniform(-4, 4),
                'anxiety': 15.0 + rng.uniform(-4, 4),
                'curiosity': 75.0 + rng.uniform(-6, 6)}

    @staticmethod
    def _neglected(t, rng):
        startled = (t % 17) < 4
        # Being startled spikes anxiety AND crushes happiness/curiosity: a real
        # aversive contingency, which should leave inhibitory structure behind.
        return {'can_see_food': 0.0,
                'hunger': 85.0 + rng.uniform(-4, 4),
                'satisfaction': 20.0 + rng.uniform(-4, 4),
                'happiness': (8.0 if startled else 30.0) + rng.uniform(-3, 3),
                'cleanliness': 15.0 + rng.uniform(-4, 4),
                'anxiety': (90.0 if startled else 45.0) + rng.uniform(-3, 3),
                'curiosity': (10.0 if startled else 35.0) + rng.uniform(-3, 3)}

    def test_care_and_neglect_produce_different_brains(self):
        cared = self._life(self._cared)
        neglected = self._life(self._neglected)

        keys = set(cared) | set(neglected)
        self.assertTrue(keys, "neither squid formed any synapses")
        differences = [abs(cared.get(k, 0.0) - neglected.get(k, 0.0)) for k in keys]
        self.assertGreater(max(differences), 0.25,
                           "two very different lives produced near-identical brains")

    def test_the_cared_for_squid_learns_that_food_means_satisfaction(self):
        cared = self._life(self._cared)
        edge = ('can_see_food', 'satisfaction')
        self.assertIn(edge, cared)
        self.assertGreater(cared[edge], 0.25,
                           "food reliably preceded satisfaction and was not learned")

    def test_the_neglected_squid_learns_no_such_thing(self):
        neglected = self._life(self._neglected)
        value = neglected.get(('can_see_food', 'satisfaction'), 0.0)
        self.assertLess(abs(value), 0.15,
                        "a squid that never saw food still formed a food association")

    def test_a_squid_that_is_startled_learns_an_aversive_association(self):
        """Anxiety spikes should leave inhibitory structure behind."""
        neglected = self._life(self._neglected)
        inhibitory = [v for v in neglected.values() if v < -0.2]
        self.assertTrue(inhibitory,
                        "a stressful life produced no inhibitory synapses at all")


class ConsolidationTests(unittest.TestCase):
    """Sleep replays the day's structure and prunes what never mattered."""

    class _FakeBrain(RecordedSynapses):
        """A brain with no Qt, but the real write path.

        Inheriting RecordedSynapses is deliberate: a double that implements its
        own weight-setting would let consolidation pass a test against a path
        the game does not have.
        """

        def __init__(self):
            self.weights = {('a', 'b'): 0.5, ('c', 'd'): -0.4, ('e', 'f'): 0.01}
            self.neurogenesis_data = {'new_neurons': []}
            self.enhanced_neurogenesis = None
            self.tamagotchi_logic = None
            self.ledger = CausalLedger(self)

        def mark_render_dirty(self):
            pass

        def sync_connections_from_weights(self):
            pass

        def add_weight_animation(self, *args, **kwargs):
            pass

    def _run_night(self):
        from src.consolidation import ConsolidationManager
        brain = self._FakeBrain()
        manager = ConsolidationManager(brain)
        for _ in range(60):
            manager.on_tick(False, {'a': 90.0, 'b': 88.0,
                                    'c': 92.0, 'd': 10.0,
                                    'e': 50.0, 'f': 50.0})
        summary = None
        for _ in range(120):
            summary = manager.on_tick(True, {}) or summary
            if summary:
                break
        return brain, manager, summary

    def test_sleep_strengthens_the_days_coactivations(self):
        brain, _, summary = self._run_night()
        self.assertIsNotNone(summary, "a night of sleep produced no consolidation")
        self.assertGreater(brain.weights[('a', 'b')], 0.5)

    def test_sleep_prunes_connections_that_never_mattered(self):
        brain, _, summary = self._run_night()
        self.assertNotIn(('e', 'f'), brain.weights)
        self.assertGreaterEqual(summary['pruned'], 1)

    def test_replay_never_flips_an_associations_sign(self):
        """Consolidation deepens what was learned; it must not invert it."""
        brain, _, _ = self._run_night()
        self.assertLess(brain.weights[('c', 'd')], 0.0)

    def test_consolidation_is_a_core_module(self):
        import src.consolidation  # noqa: F401
        import src.sleep_consolidation  # noqa: F401
        self.assertFalse(
            os.path.exists(os.path.join(_REPO_ROOT, 'plugins', 'sleep_replay',
                                        'replay_core.py')),
            "the algorithm still has a second copy under plugins/")


class CoreIntegrationTests(unittest.TestCase):
    """STDP and the config are wired in, not bolted on."""

    def test_stdp_is_a_core_module(self):
        import src.stdp  # noqa: F401
        self.assertFalse(
            os.path.exists(os.path.join(_REPO_ROOT, 'plugins', 'stdp',
                                        'stdp_core.py')),
            "the STDP algorithm still has a second copy under plugins/")

    def test_plasticity_attaches_stdp_by_default(self):
        engine = PlasticityEngine()
        self.assertIsNotNone(engine.stdp, "STDP is core and should be attached")

    def test_config_ini_hebbian_section_is_actually_read(self):
        """It was dead: base_learning_rate = 0.20 in the file ran as 0.1."""
        from src.config_manager import ConfigManager
        from src.learning import LearningConfig

        raw = ConfigManager().config
        self.assertTrue(raw.has_section('Hebbian'))
        expected = float(raw.get('Hebbian', 'base_learning_rate'))
        self.assertAlmostEqual(LearningConfig().hebbian['base_learning_rate'],
                               expected, places=6)

    def test_learning_interval_is_converted_to_milliseconds(self):
        """config.ini expresses seconds; the timers want ms."""
        from src.learning import LearningConfig
        interval = LearningConfig().hebbian['learning_interval']
        self.assertGreaterEqual(interval, 1000,
                                "a seconds value reached the timer unconverted")

    def test_equilibrium_weight_equals_the_correlation(self):
        """lr == decay is what makes every weight readable."""
        from src.learning import LearningConfig
        hebb = LearningConfig().hebbian
        self.assertAlmostEqual(hebb['base_learning_rate'], hebb['weight_decay'],
                               places=6)


if __name__ == "__main__":
    unittest.main()
