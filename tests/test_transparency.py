"""
Tests for the three things Dosidicus claims to be and now has to prove:

  1. TRANSPARENCY   Every synaptic change and every grown neuron has a recorded
                    cause, and the inspection tools read that record rather than
                    reconstructing an approximation of it.

  2. CAUSALITY      The squid discovers which of ITS OWN actions produce which
                    consequences, measured against the background drift, and
                    the outcome reaches the synapses that caused it.

  3. CAPABILITY     A neuron is grown because the network persistently cannot
                    represent, regulate or express something - not because an
                    event happened.

Plus the structural invariants that keep the above honest: one plasticity rule,
one propagation implementation, one neurogenesis decision, one consolidation
engine, and no plugin monkey-patching any of them.
"""

import os
import sys
import time
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.capability import (CapabilityConfig, CapabilityMonitor, Deficit,  # noqa: E402
                            COMFORT_BANDS)
from src.causal_learning import ActionOutcomeLedger, CausalConfig  # noqa: E402
from src.neural_provenance import CausalLedger, Episode  # noqa: E402


class FakeBrain:
    """The minimum surface the ledger, monitor and causal learner read.

    Deliberately not a BrainWidget: these modules must work against the brain's
    data, not against Qt.
    """

    def __init__(self, weights=None, state=None, positions=None):
        self.weights = dict(weights or {})
        self.state = dict(state or {})
        self.neuron_positions = dict(positions or {n: (0, 0) for n in self.state})
        self.excluded_neurons = []
        self.ledger = CausalLedger(self)
        self.capability = CapabilityMonitor(self)
        self.causal_learning = ActionOutcomeLedger(self)
        self.applied = []

    def apply_weight_change(self, edge, delta=None, value=None, mechanism='manual',
                            detail=None, episode_id=None, create=True, animate=True,
                            directed=True):
        if not directed and edge not in self.weights and (edge[1], edge[0]) in self.weights:
            edge = (edge[1], edge[0])
        if edge not in self.weights and not create:
            return False
        old = float(self.weights.get(edge, 0.0))
        new = float(value) if value is not None else old + float(delta or 0.0)
        new = max(-1.0, min(1.0, new))
        if edge in self.weights and abs(new - old) < 1e-9:
            return False
        self.weights[edge] = new
        self.ledger.record_weight_change(edge, old, new, mechanism, detail, episode_id)
        self.applied.append((edge, mechanism))
        return True

    def find_orphan_neurons(self):
        connected = {n for edge in self.weights for n in edge}
        return [n for n in self.neuron_positions if n not in connected]


# ===========================================================================
# 1. Provenance
# ===========================================================================
class ProvenanceTests(unittest.TestCase):

    def setUp(self):
        self.brain = FakeBrain(
            weights={('can_see_food', 'satisfaction'): 0.31},
            state={'can_see_food': 100.0, 'satisfaction': 60.0, 'anxiety': 40.0})
        self.ledger = self.brain.ledger

    def test_a_weight_change_records_its_cause(self):
        self.brain.apply_weight_change(
            ('can_see_food', 'satisfaction'), value=0.47, mechanism='hebbian',
            detail={'correlation': 0.62, 'samples': 180})

        history = self.ledger.weight_history(('can_see_food', 'satisfaction'))
        self.assertEqual(len(history), 1)
        event = history[0]
        self.assertAlmostEqual(event.old_weight, 0.31)
        self.assertAlmostEqual(event.new_weight, 0.47)
        self.assertEqual(event.mechanism, 'hebbian')
        self.assertEqual(event.detail['samples'], 180)

    def test_why_did_this_weight_change_from_031_to_047(self):
        self.brain.apply_weight_change(
            ('can_see_food', 'satisfaction'), value=0.47, mechanism='hebbian',
            detail={'correlation': 0.62, 'samples': 180})

        answer = self.ledger.explain_weight(('can_see_food', 'satisfaction'),
                                            from_value=0.31, to_value=0.47)
        self.assertIn("0.310", answer)
        self.assertIn("0.470", answer)
        self.assertIn("kept happening together", answer)
        self.assertIn("180 observations", answer)

    def test_an_unchanged_weight_says_so_rather_than_inventing_a_reason(self):
        answer = self.ledger.explain_weight(('can_see_food', 'satisfaction'))
        self.assertIn("nothing has changed it", answer)

    def test_every_mechanism_is_distinguishable_in_the_record(self):
        edge = ('can_see_food', 'satisfaction')
        for mechanism, value in (('hebbian', 0.40), ('stdp', 0.45),
                                 ('consolidation', 0.55), ('causal_reward', 0.60),
                                 ('reflex', 0.65)):
            self.brain.apply_weight_change(edge, value=value, mechanism=mechanism)

        totals = self.ledger.edge_totals(edge)
        self.assertEqual(set(totals),
                         {'hebbian', 'stdp', 'consolidation', 'causal_reward', 'reflex'})
        answer = self.ledger.explain_weight(edge)
        self.assertIn("Over its whole life", answer)

    def test_a_weight_change_can_name_the_experience_behind_it(self):
        episode = Episode(episode_id='ep1', action='eating', started=time.time(),
                          ended=time.time(), cue={'can_see_food': 100.0},
                          consequence={'hunger': -22.0}, valence=0.4)
        self.ledger.record_episode(episode)
        self.brain.apply_weight_change(
            ('can_see_food', 'satisfaction'), value=0.5, mechanism='causal_reward',
            detail={'valence': 0.4}, episode_id='ep1')

        answer = self.ledger.explain_weight(('can_see_food', 'satisfaction'))
        self.assertIn("Experience:", answer)
        self.assertIn("eating", answer)

    def test_why_does_this_neuron_exist(self):
        self.ledger.record_neuron_birth(
            name='anxiety_regulation', deficit_kind='regulation',
            deficit_summary="anxiety was above its comfortable range for 78% of "
                            "the last 240 ticks and nothing was pulling it back",
            remedy="pull anxiety down whenever the situations that drive it appear",
            wiring=[('anxiety', 'anxiety_regulation', 0.8, 'remedy'),
                    ('anxiety_regulation', 'anxiety', -0.9, 'remedy')],
            neuron_type='stress', specialization='anxiety_regulation',
            display_name='Stress: Anxiety Regulation')

        answer = self.ledger.explain_neuron('anxiety_regulation')
        self.assertIn("could not pull this feeling back", answer)
        self.assertIn("78%", answer)
        self.assertIn("Anxiety Regulation", answer)

    def test_core_neurons_get_an_honest_answer_too(self):
        self.brain.neuron_positions['anxiety'] = (0, 0)
        answer = self.ledger.explain_neuron('anxiety')
        self.assertIn("born with", answer)

    def test_what_does_the_squid_know_about_food(self):
        self.brain.apply_weight_change(
            ('can_see_food', 'satisfaction'), value=0.62, mechanism='hebbian',
            detail={'correlation': 0.7, 'samples': 200})

        items = self.brain.ledger.knowledge('food')
        self.assertTrue(items, "the squid knows nothing about food")
        item = items[0]
        self.assertIn("can see food", item.statement.lower())
        self.assertIn("goes up", item.statement)
        self.assertTrue(item.reason)
        self.assertGreater(item.confidence, 0.0)
        self.assertTrue(item.behaviour)

    def test_an_inhibitory_synapse_reads_as_avoidance(self):
        self.brain.weights[('is_startled', 'curiosity')] = 0.0
        self.brain.state['is_startled'] = 100.0
        self.brain.state['curiosity'] = 30.0
        self.brain.neuron_positions['is_startled'] = (0, 0)
        self.brain.neuron_positions['curiosity'] = (0, 0)
        self.brain.apply_weight_change(('is_startled', 'curiosity'), value=-0.5,
                                       mechanism='hebbian',
                                       detail={'correlation': -0.6, 'samples': 90})
        items = self.brain.ledger.knowledge('curiosity')
        statements = " ".join(i.statement for i in items)
        self.assertIn("goes down", statements)

    def test_confidence_rises_with_consistent_evidence(self):
        edge = ('can_see_food', 'satisfaction')
        weak = FakeBrain(weights={edge: 0.0}, state=dict(self.brain.state))
        weak.apply_weight_change(edge, value=0.2, mechanism='hebbian',
                                 detail={'correlation': 0.2, 'samples': 10})
        weak_conf = weak.ledger.knowledge('food')[0].confidence

        strong = FakeBrain(weights={edge: 0.0}, state=dict(self.brain.state))
        for i in range(6):
            strong.apply_weight_change(edge, value=0.1 * (i + 1), mechanism='hebbian',
                                       detail={'correlation': 0.8, 'samples': 200})
        strong_conf = strong.ledger.knowledge('food')[0].confidence

        self.assertGreater(strong_conf, weak_conf)

    def test_provenance_survives_a_round_trip(self):
        self.brain.apply_weight_change(('can_see_food', 'satisfaction'), value=0.47,
                                       mechanism='hebbian',
                                       detail={'correlation': 0.6, 'samples': 100})
        self.ledger.record_neuron_birth('grown_one', 'representation',
                                        "no neuron told this situation apart")

        payload = self.ledger.to_dict()
        restored = CausalLedger(self.brain)
        restored.from_dict(payload)

        self.assertIn('grown_one', restored.origins)
        self.assertIn("kept happening together",
                      restored.explain_weight(('can_see_food', 'satisfaction')))

    def test_influence_records_how_learning_reached_behaviour(self):
        edge = ('can_see_food', 'anxiety')
        self.brain.weights[edge] = 0.5
        self.brain.apply_weight_change(edge, value=0.6, mechanism='hebbian',
                                       detail={'correlation': 0.5, 'samples': 50})
        for _ in range(5):
            self.ledger.record_influence(edge, 0.12, 'modulation', 'anxiety')
        self.ledger.record_decision("seeking comfort in plant")

        answer = self.ledger.explain_weight(edge)
        self.assertIn("pushed", answer)
        item = [i for i in self.ledger.knowledge('anxiety') if i.edge == edge][0]
        self.assertIn("ticks", item.behaviour)


# ===========================================================================
# 2. Action -> consequence -> outcome
# ===========================================================================
class CausalLearningTests(unittest.TestCase):

    def setUp(self):
        self.brain = FakeBrain(state={'hunger': 80.0, 'happiness': 50.0,
                                      'anxiety': 50.0, 'satisfaction': 50.0,
                                      'cleanliness': 50.0, 'sleepiness': 50.0,
                                      'curiosity': 50.0, 'can_see_food': 100.0})
        self.causal = self.brain.causal_learning
        self.causal.config = CausalConfig(outcome_window=1.0)

    def _episode(self, action, before, after, t0):
        """Run one action episode with a controlled before/after state."""
        self.brain.state.update(before)
        self.causal.on_action(action, self.brain.state, now=t0)
        self.brain.state.update(after)
        return self.causal.on_tick(self.brain.state, now=t0 + 1.5)

    def test_an_action_episode_records_its_consequence(self):
        closed = self._episode('eating', {'hunger': 80.0}, {'hunger': 55.0}, 1000.0)
        self.assertEqual(len(closed), 1)
        episode = closed[0]
        self.assertEqual(episode.action, 'eating')
        self.assertAlmostEqual(episode.consequence['hunger'], -25.0)
        self.assertGreater(episode.valence, 0.0)

    def test_the_squid_learns_which_of_its_actions_causes_what(self):
        for i in range(6):
            self._episode('eating', {'hunger': 80.0}, {'hunger': 56.0},
                          1000.0 + i * 10)

        known = self.causal.known_contingencies()
        self.assertTrue(known, "no contingency reached confidence")
        entry, effect, confidence = known[0]
        self.assertEqual(entry.action, 'eating')
        self.assertEqual(entry.stat, 'hunger')
        self.assertLess(effect, 0.0)
        self.assertGreater(confidence, 0.3)

    def test_the_claim_is_stated_in_plain_english(self):
        for i in range(6):
            self._episode('eating', {'hunger': 80.0}, {'hunger': 56.0},
                          1000.0 + i * 10)
        items = self.causal.knowledge_items()
        self.assertTrue(items)
        item = items[0]
        self.assertIn("eating", item.statement)
        self.assertIn("hunger", item.statement)
        self.assertEqual(item.action, 'eating')
        self.assertTrue(item.consequence)
        self.assertIn("background drift", item.reason)

    def _idle_window(self, before, after, t0):
        """One outcome window in which the squid does nothing at all."""
        self.brain.state.update(before)
        self.causal.on_tick(self.brain.state, now=t0)
        self.brain.state.update(after)
        self.causal.on_tick(self.brain.state, now=t0 + 1.5)

    def test_contingency_is_measured_against_the_background_drift(self):
        """Something that happens anyway is not caused by the action."""
        # Every window, hunger rises 5 whether or not the squid explores.
        t = 1000.0
        for _ in range(8):
            self._idle_window({'hunger': 50.0}, {'hunger': 55.0}, t)
            t += 3.0
        for _ in range(6):
            self._episode('exploring', {'hunger': 50.0}, {'hunger': 55.0}, t)
            t += 10.0

        table = self.causal.contingencies.get('exploring', {})
        self.assertIn('hunger', table)
        entry = table['hunger']
        baseline = self.causal.baseline_drift('hunger', 'exploring')
        self.assertGreater(baseline, 0.0, "baseline drift was never measured")
        self.assertLess(abs(entry.effect(baseline)), abs(entry.mean_delta),
                        "the background drift was not subtracted")

    def test_a_single_observation_is_never_confident(self):
        self._episode('eating', {'hunger': 90.0}, {'hunger': 10.0}, 1000.0)
        self.assertEqual(self.causal.known_contingencies(min_confidence=0.01), [])

    def test_credit_reaches_the_synapses_that_were_causally_active(self):
        """The reward broadcast is the temporal credit assignment step."""
        class FakeSTDP:
            def __init__(self):
                self.rewarded = None

            def apply_reward_modulation(self, signal, rate=None):
                self.rewarded = signal
                self.rate = rate
                return {('can_see_food', 'satisfaction'): 0.02 * signal}

        stdp = FakeSTDP()
        self.brain.plasticity = type('P', (), {'stdp': stdp})()
        self.brain.weights[('can_see_food', 'satisfaction')] = 0.1

        self._episode('eating', {'hunger': 90.0}, {'hunger': 40.0}, 1000.0)

        self.assertIsNotNone(stdp.rewarded, "no reward was broadcast")
        self.assertGreater(stdp.rewarded, 0.0)
        self.assertGreater(self.brain.weights[('can_see_food', 'satisfaction')], 0.1)
        edge, mechanism = self.brain.applied[-1]
        self.assertEqual(mechanism, 'causal_reward')
        event = self.brain.ledger.weight_history(edge)[-1]
        self.assertEqual(event.detail['action'], 'eating')

    def test_causal_state_survives_a_round_trip(self):
        for i in range(6):
            self._episode('eating', {'hunger': 80.0}, {'hunger': 56.0},
                          1000.0 + i * 10)
        payload = self.causal.to_dict()
        restored = ActionOutcomeLedger(self.brain)
        restored.from_dict(payload)
        self.assertEqual(restored.contingencies['eating']['hunger'].n,
                         self.causal.contingencies['eating']['hunger'].n)


# ===========================================================================
# 3. Capability-driven neurogenesis
# ===========================================================================
class CapabilityTests(unittest.TestCase):

    def _monitor(self, brain, **overrides):
        monitor = brain.capability
        cfg = CapabilityConfig(**overrides) if overrides else CapabilityConfig()
        monitor.config = cfg
        return monitor

    def test_a_drive_the_network_is_bringing_back_is_not_a_deficit(self):
        """The test is whether the drive is recovering, not how big the synapse is.

        Any threshold on corrective push is a magic number, and one that
        compared a 240-tick complaint against a single-moment defence. What
        matters is whether existing structure is getting on top of it.
        """
        brain = FakeBrain(
            weights={('coping', 'anxiety'): -0.7},
            state={'anxiety': 95.0, 'coping': 100.0, 'hunger': 40.0,
                   'happiness': 60.0, 'satisfaction': 60.0, 'cleanliness': 60.0,
                   'sleepiness': 40.0, 'curiosity': 50.0})
        monitor = self._monitor(brain)
        # Out of band throughout, but steadily coming back down.
        for i in range(120):
            brain.state['anxiety'] = 95.0 - (i * 0.4)
            monitor.observe(brain.state)
        deficits = [d for d in monitor.evaluate() if d.kind == 'regulation']
        self.assertEqual(deficits, [],
                         "grew a deficit for a drive that was already recovering")

    def test_a_drive_that_is_stuck_despite_a_synapse_is_still_a_deficit(self):
        """Structure that exists but is not working is a capability gap."""
        brain = FakeBrain(
            weights={('coping', 'anxiety'): -0.7},
            state={'anxiety': 80.0, 'coping': 100.0, 'hunger': 40.0,
                   'happiness': 60.0, 'satisfaction': 60.0, 'cleanliness': 60.0,
                   'sleepiness': 40.0, 'curiosity': 50.0})
        monitor = self._monitor(brain)
        for _ in range(120):
            monitor.observe(brain.state)
        deficits = [d for d in monitor.evaluate() if d.kind == 'regulation']
        self.assertTrue(deficits, "a drive stuck out of band despite a synapse "
                                  "went undiagnosed")
        self.assertIn("not coming back", deficits[0].summary)

    def test_an_unregulated_drive_produces_a_regulation_deficit(self):
        """Same anxiety, but nothing in the network corrects it."""
        brain = FakeBrain(
            weights={('curiosity', 'happiness'): 0.3},
            state={'anxiety': 85.0, 'hunger': 40.0, 'happiness': 60.0,
                   'satisfaction': 60.0, 'cleanliness': 60.0, 'sleepiness': 40.0,
                   'curiosity': 50.0})
        monitor = self._monitor(brain)
        for _ in range(120):
            monitor.observe(brain.state)
        deficits = [d for d in monitor.evaluate() if d.kind == 'regulation']
        self.assertTrue(deficits, "a drive stuck out of range went undiagnosed")
        deficit = deficits[0]
        self.assertEqual(deficit.target, 'anxiety')
        self.assertIn("no synapse at all", deficit.summary)
        self.assertEqual(deficit.suggested_type, 'stress')

    def test_a_saturated_corrective_synapse_still_counts_as_a_deficit(self):
        """The structure exists, is doing all it can, and it is not enough."""
        brain = FakeBrain(
            weights={('coping', 'anxiety'): -1.0},
            state={'anxiety': 95.0, 'coping': 100.0, 'hunger': 40.0,
                   'happiness': 60.0, 'satisfaction': 60.0, 'cleanliness': 60.0,
                   'sleepiness': 40.0, 'curiosity': 50.0})
        monitor = self._monitor(brain)
        for _ in range(120):
            monitor.observe(brain.state)
        deficits = [d for d in monitor.evaluate() if d.kind == 'regulation']
        self.assertTrue(deficits)
        self.assertIn("full strength", deficits[0].summary)

    def test_a_deficit_must_persist_before_it_earns_structure(self):
        brain = FakeBrain(
            weights={},
            state={'anxiety': 90.0, 'hunger': 40.0, 'happiness': 60.0,
                   'satisfaction': 60.0, 'cleanliness': 60.0, 'sleepiness': 40.0,
                   'curiosity': 50.0})
        monitor = self._monitor(brain, min_observations=3, min_age=10.0)
        for _ in range(120):
            monitor.observe(brain.state)

        monitor.evaluate()
        self.assertEqual(monitor.actionable(), [],
                         "one sighting was enough to grow structure")

        deficit = next(iter(monitor.active.values()))
        deficit.observations = 5
        deficit.first_seen = deficit.last_seen - 30.0
        self.assertTrue(monitor.actionable())

    def test_a_deficit_that_learning_is_already_fixing_is_not_actionable(self):
        deficit = Deficit(kind='regulation', key='k', summary='s', severity=0.4,
                          initial_severity=1.0)
        self.assertFalse(deficit.unresolved)
        deficit.severity = 0.95
        self.assertTrue(deficit.unresolved)

    def test_a_recurring_situation_nothing_represents_is_a_deficit(self):
        brain = FakeBrain(
            state={'can_see_food': 100.0, 'hunger': 90.0, 'happiness': 50.0,
                   'anxiety': 50.0, 'satisfaction': 50.0, 'cleanliness': 50.0,
                   'sleepiness': 50.0, 'curiosity': 50.0, 'hidden': 50.0},
            positions={'can_see_food': (0, 0), 'hunger': (0, 0), 'happiness': (0, 0),
                       'anxiety': (0, 0), 'satisfaction': (0, 0),
                       'cleanliness': (0, 0), 'sleepiness': (0, 0),
                       'curiosity': (0, 0), 'hidden': (0, 0)})
        monitor = self._monitor(brain)
        # The same situation, over and over, with nothing in the network
        # responding differently when it happens.
        for i in range(60):
            brain.state['can_see_food'] = 100.0 if i % 2 == 0 else 0.0
            monitor.observe(brain.state)
        deficits = [d for d in monitor.evaluate() if d.kind == 'representation']
        self.assertTrue(deficits, "a recurring, unrepresented situation went unnoticed")
        self.assertIn("no neuron in the brain", deficits[0].summary)

    def test_a_situation_an_existing_neuron_discriminates_is_not_a_deficit(self):
        brain = FakeBrain(
            state={'can_see_food': 0.0, 'hunger': 50.0, 'happiness': 50.0,
                   'anxiety': 50.0, 'satisfaction': 50.0, 'cleanliness': 50.0,
                   'sleepiness': 50.0, 'curiosity': 50.0, 'food_detector': 50.0},
            positions={n: (0, 0) for n in
                       ('can_see_food', 'hunger', 'happiness', 'anxiety',
                        'satisfaction', 'cleanliness', 'sleepiness', 'curiosity',
                        'food_detector')})
        monitor = self._monitor(brain)
        for i in range(60):
            present = i % 2 == 0
            brain.state['can_see_food'] = 100.0 if present else 0.0
            # food_detector already does the job this deficit would be about.
            brain.state['food_detector'] = 95.0 if present else 5.0
            monitor.observe(brain.state)
        deficits = [d for d in monitor.evaluate() if d.kind == 'representation']
        self.assertEqual(deficits, [],
                         "proposed growing a neuron for something already represented")

    def test_an_orphan_is_a_connectivity_deficit(self):
        brain = FakeBrain(weights={('a', 'b'): 0.5},
                          state={'a': 50.0, 'b': 50.0, 'stranded': 50.0})
        monitor = self._monitor(brain)
        deficits = [d for d in monitor.evaluate() if d.kind == 'connectivity']
        self.assertTrue(deficits)
        self.assertEqual(deficits[0].target, 'stranded')

    def test_the_diagnosis_reads_as_english(self):
        brain = FakeBrain(weights={}, state={'anxiety': 92.0, 'hunger': 40.0,
                                             'happiness': 60.0, 'satisfaction': 60.0,
                                             'cleanliness': 60.0, 'sleepiness': 40.0,
                                             'curiosity': 50.0})
        monitor = self._monitor(brain)
        for _ in range(120):
            monitor.observe(brain.state)
        monitor.evaluate()
        text = monitor.describe()
        self.assertIn("anxiety", text)
        self.assertIn("severity", text)

    def test_capability_state_survives_a_round_trip(self):
        brain = FakeBrain(weights={}, state={'anxiety': 92.0, 'hunger': 40.0,
                                             'happiness': 60.0, 'satisfaction': 60.0,
                                             'cleanliness': 60.0, 'sleepiness': 40.0,
                                             'curiosity': 50.0})
        monitor = self._monitor(brain)
        for _ in range(120):
            monitor.observe(brain.state)
        monitor.evaluate()

        payload = monitor.to_dict()
        restored = CapabilityMonitor(brain)
        restored.from_dict(payload)
        self.assertEqual(set(restored.active), set(monitor.active))
        self.assertEqual(restored.ticks, monitor.ticks)

    def test_regulator_wiring_keeps_both_directions(self):
        """drive -> regulator and regulator -> drive are different synapses.

        Collapsing them onto one undirected edge destroys the inhibition that
        is the entire reason the neuron was grown.
        """
        from src.brain_widget import BrainWidget
        import inspect
        source = inspect.getsource(BrainWidget.apply_weight_change)
        self.assertIn("directed", source,
                      "the write path can silently merge a synapse with its reverse")

    def test_every_comfort_band_names_a_real_drive(self):
        from src.brain_constants import CORE_STAT_NEURONS
        self.assertEqual(set(COMFORT_BANDS), set(CORE_STAT_NEURONS))


# ===========================================================================
# 4. Structural invariants - one implementation of each mechanism
# ===========================================================================
class SingleSourceOfTruthTests(unittest.TestCase):

    def _source(self, relative_path):
        with open(os.path.join(_REPO_ROOT, relative_path), encoding='utf-8') as f:
            return f.read()

    def _plugin_sources(self):
        """Every plugin's Python, whichever plugins happen to be installed.

        This used to name plugins/stdp/main.py and plugins/sleep_replay/main.py
        directly. Both are gone - the mechanisms they wrapped are core engine
        features now - but the thing those tests protected is not about those
        two plugins: NO plugin may carry a second copy of a learning mechanism,
        because then a squid's behaviour depends on which plugins are loaded
        and the network stops being one explainable object.
        """
        import glob
        root = os.path.join(_REPO_ROOT, 'plugins')
        for path in glob.glob(os.path.join(root, '**', '*.py'), recursive=True):
            if '__pycache__' in path:
                continue
            with open(path, encoding='utf-8') as handle:
                yield os.path.relpath(path, _REPO_ROOT), handle.read()

    def test_no_plugin_monkey_patches_the_learning_rule(self):
        for path, source in self._plugin_sources():
            with self.subTest(plugin=path):
                self.assertNotIn("_perform_hebbian_learning =", source,
                                 f"{path} patches the worker's learning rule")

    def test_no_plugin_builds_a_second_learning_engine(self):
        """One STDP learner and one replay engine per brain, both core-owned."""
        for path, source in self._plugin_sources():
            for constructor in ("STDPLearner(", "SleepReplayEngine(",
                                "PlasticityEngine(", "ConsolidationManager("):
                with self.subTest(plugin=path, constructor=constructor):
                    self.assertNotIn(constructor, source,
                                     f"{path} built its own {constructor[:-1]}")

    def test_stdp_and_consolidation_are_not_plugins_any_more(self):
        """They are always on. There is nothing left to enable or disable."""
        for folder in ('stdp', 'sleep_replay'):
            with self.subTest(plugin=folder):
                self.assertFalse(
                    os.path.isdir(os.path.join(_REPO_ROOT, 'plugins', folder)),
                    f"plugins/{folder} is back; the engine already does this")
        import src.stdp             # noqa: F401
        import src.consolidation    # noqa: F401

    def test_there_is_one_neurogenesis_trigger_system(self):
        source = self._source('src/neurogenesis.py')
        self.assertNotIn("class NeurogenesisTriggerSystem", source)

    def test_neurogenesis_does_not_recompute_activations(self):
        """Propagation is BrainWidget's job; a second copy diverges silently."""
        source = self._source('src/neurogenesis.py')
        self.assertNotIn("self.brain_widget.state[name] = activation", source)

    def test_the_worker_carries_no_second_neurogenesis_rule(self):
        source = self._source('src/brain_worker.py')
        # The names may survive in the docstring explaining what was removed;
        # what must not survive is code that reads them.
        self.assertNotIn("state.get('novelty_exposure'", source)
        self.assertNotIn("state.get('sustained_stress'", source)
        self.assertNotIn("neuro_config.get(", source)

    def test_the_showman_wrapper_is_gone(self):
        self.assertFalse(
            os.path.exists(os.path.join(_REPO_ROOT, 'src', 'neurogenesis_show.py')),
            "the neurogenesis wrapper that renamed neurons after the fact is back")

    def test_reflexes_do_not_carry_their_own_weight_formula(self):
        source = self._source('src/learning.py')
        self.assertNotIn("self.brain_window.brain_widget.weights[pair] =", source)
        self.assertIn("brain_widget.strengthen_connection(", source)

    def test_the_learning_tab_reads_the_ledger_not_its_own_cache(self):
        source = self._source('src/brain_learning_tab.py')
        self.assertNotIn("self._last_seen_weights.get(", source,
                         "the Learning tab is reconstructing weight changes again")
        self.assertIn("recent_events", source)

    def test_the_knowledge_tab_computes_nothing_itself(self):
        source = self._source('src/brain_knowledge_tab.py')
        for forbidden in ("self.brain_widget.weights[", "def _compute_",
                          "self._weights ="):
            self.assertNotIn(forbidden, source,
                             "the Knowledge tab is building its own model of the brain")


# ===========================================================================
# 4b. The defects the architecture audit found, so they cannot come back
# ===========================================================================
class AuditRegressionTests(unittest.TestCase):
    """One case per defect the validation pass turned up by measurement."""

    # -- credit assignment ---------------------------------------------
    def _ledger(self, window=2.0):
        brain = FakeBrain(state={'hunger': 60.0, 'happiness': 50.0, 'anxiety': 50.0,
                                 'satisfaction': 50.0, 'cleanliness': 50.0,
                                 'sleepiness': 50.0, 'curiosity': 50.0})
        return brain, ActionOutcomeLedger(brain, CausalConfig(outcome_window=window))

    def _trial(self, causal, base, actions, after, t):
        for offset, action in enumerate(actions):
            causal.on_action(action, dict(base), now=t + offset * 0.1)
        snapshot = dict(base); snapshot.update(after)
        causal.on_tick(snapshot, now=t + 2.2)
        causal.on_tick(snapshot, now=t + 2.6)

    def test_two_actions_that_always_co_occur_split_the_credit(self):
        """Nothing can separate perfectly confounded causes; claiming otherwise lies."""
        brain, causal = self._ledger()
        base = dict(brain.state)
        t = 1000.0
        for _ in range(12):
            self._trial(causal, base, ['drifting', 'eating'], {'hunger': 35.0}, t)
            t += 6.0
        eat = causal.contingencies['eating']['hunger'].mean_delta
        drift = causal.contingencies['drifting']['hunger'].mean_delta
        self.assertAlmostEqual(eat, drift, delta=1.0,
                               msg="a perfect confound was resolved by invention")
        self.assertGreater(abs(eat), 5.0, "neither action learned anything")

    def test_an_action_that_sometimes_occurs_alone_is_corrected(self):
        """The moment the confound dissociates, the real cause absorbs the effect."""
        brain, causal = self._ledger()
        base = dict(brain.state)
        t = 1000.0
        for i in range(30):
            if i % 2 == 0:
                self._trial(causal, base, ['drifting', 'eating'], {'hunger': 35.0}, t)
            else:
                self._trial(causal, base, ['drifting'], {}, t)
            t += 6.0
        eat = causal.contingencies['eating']['hunger'].mean_delta
        drift = causal.contingencies['drifting']['hunger'].mean_delta
        self.assertLess(eat, drift - 8.0,
                        "the passenger action kept as much credit as the cause")

    def test_credit_does_not_depend_on_which_episode_closes_first(self):
        results = []
        for order in (['drifting', 'eating'], ['eating', 'drifting']):
            brain, causal = self._ledger()
            base = dict(brain.state)
            t = 1000.0
            for i in range(20):
                if i % 2 == 0:
                    self._trial(causal, base, order, {'hunger': 35.0}, t)
                else:
                    self._trial(causal, base, ['drifting'], {}, t)
                t += 6.0
            results.append(round(causal.contingencies['eating']['hunger'].mean_delta, 3))
        self.assertEqual(results[0], results[1],
                         "settlement depended on deque order, not on evidence")

    def test_a_null_outcome_corrects_a_mistaken_belief(self):
        """Extinction. 'I did that and nothing happened' has to teach something."""
        brain, causal = self._ledger()
        base = dict(brain.state)
        t = 1000.0
        for _ in range(6):
            self._trial(causal, base, ['eating'], {'hunger': 35.0}, t)
            t += 6.0
        learned = causal.contingencies['eating']['hunger'].mean_delta
        for _ in range(20):
            self._trial(causal, base, ['eating'], {}, t)
            t += 6.0
        after = causal.contingencies['eating']['hunger'].mean_delta
        self.assertGreater(after, learned + 5.0,
                           "a belief that stopped being true was never revised")

    def test_valence_is_surprise_not_raw_change(self):
        """An expected outcome must not keep paying out reward."""
        brain, causal = self._ledger()
        base = dict(brain.state)
        t = 1000.0
        first = None
        for i in range(14):
            self._trial(causal, base, ['eating'], {'hunger': 35.0}, t)
            t += 6.0
            if causal.history:
                if first is None:
                    first = abs(causal.history[-1].valence)
                last = abs(causal.history[-1].valence)
        self.assertIsNotNone(first)
        self.assertLess(last, first,
                        "a fully predicted outcome still generated a reward signal")

    # -- STDP ----------------------------------------------------------
    def test_stdp_depresses_a_synapse_whose_own_ordering_is_acausal(self):
        from src.plasticity import PlasticityEngine, PlasticityConfig

        def run(pre_leads):
            eng = PlasticityEngine(PlasticityConfig(stdp_weight=0.9, learning_rate=0.4,
                                                    min_pairs_per_cycle=8))
            eng.stdp.config.refractory_period = 0.0
            weights = {('pre', 'post'): 0.0}
            t = 0.0
            for _ in range(40):
                eng.observe({'pre': 10., 'post': 10.}, ['pre', 'post'], timestamp=t); t += 0.05
                if pre_leads:
                    eng.observe({'pre': 95., 'post': 10.}, ['pre', 'post'], timestamp=t); t += 0.05
                else:
                    eng.observe({'pre': 10., 'post': 95.}, ['pre', 'post'], timestamp=t); t += 0.05
                eng.observe({'pre': 95., 'post': 95.}, ['pre', 'post'], timestamp=t); t += 0.05
                eng.observe({'pre': 10., 'post': 10.}, ['pre', 'post'], timestamp=t); t += 0.30
            return eng.commit(weights, ['pre', 'post'])['weight_updates'].get(('pre', 'post'))

        causal = run(True)
        acausal = run(False)
        self.assertGreater(causal['stdp_delta'], 0.0, "no potentiation for a causal pair")
        self.assertLess(acausal['stdp_delta'], 0.0,
                        "LTD never reaches a weight: the symmetric maximum is back")

    def test_stdp_works_at_the_cadence_the_game_actually_ticks_at(self):
        """One sample per simulated second, as TamagotchiLogic supplies."""
        from src.plasticity import PlasticityEngine, PlasticityConfig
        eng = PlasticityEngine(PlasticityConfig(stdp_weight=0.5, learning_rate=0.2,
                                                min_pairs_per_cycle=8))
        weights = {('can_see_food', 'satisfaction'): 0.0}
        t = 0.0
        for i in range(60):
            eng.observe({'can_see_food': 100.0 if (i % 6) in (0, 1) else 0.0,
                         'satisfaction': 85.0 if (i % 6) in (1, 2) else 40.0},
                        ['can_see_food', 'satisfaction'], timestamp=t)
            t += 1.0
        stats = eng.stdp.get_stats()
        self.assertGreater(stats['ltp_events'] + stats['ltd_events'], 0,
                           "spike timing is silent at the rate the game runs")
        self.assertAlmostEqual(eng.stdp.spike_tracker.sample_interval, 1.0, delta=0.2)

    def test_an_outcome_finds_traces_to_reach(self):
        """Eligibility is participation, not a rare spike coincidence."""
        from src.plasticity import PlasticityEngine, PlasticityConfig
        eng = PlasticityEngine(PlasticityConfig())
        t = 0.0
        for _ in range(5):
            eng.observe({'can_see_food': 90.0, 'satisfaction': 80.0, 'hunger': 20.0},
                        ['can_see_food', 'satisfaction', 'hunger'], timestamp=t)
            t += 1.0
        self.assertTrue(eng.stdp.eligibility_snapshot(),
                        "nothing was eligible, so no outcome could ever reach a synapse")

    def test_one_outcome_does_not_consume_every_trace(self):
        from src.stdp import STDPLearner, STDPConfig
        learner = STDPLearner(STDPConfig())
        learner.update_eligibility_trace('a', 'b', 0.5)
        first = learner.apply_reward_modulation(0.4)
        second = learner.apply_reward_modulation(0.4)
        self.assertTrue(first)
        self.assertTrue(second, "the first outcome to land took all the credit")

    def test_broader_eligibility_does_not_mean_more_learning(self):
        """If everything was active, no synapse in particular is responsible."""
        from src.stdp import STDPLearner, STDPConfig

        def total(n):
            learner = STDPLearner(STDPConfig())
            for i in range(n):
                learner.update_eligibility_trace(f'a{i}', f'b{i}', 1.0)
            return sum(abs(v) for v in learner.apply_reward_modulation(1.0, rate=0.04).values())

        self.assertLess(total(80), total(8) * 2.0,
                        "one outcome delivered more learning the wider it spread")

    # -- neurogenesis --------------------------------------------------
    def test_a_neuron_is_never_born_unable_to_participate(self):
        from src.neurogenesis import EnhancedNeurogenesis
        from src.learning import LearningConfig

        class Brain(FakeBrain):
            def __init__(self):
                super().__init__(state={'hunger': 50.0, 'happiness': 50.0,
                                        'anxiety': 50.0, 'satisfaction': 50.0,
                                        'cleanliness': 50.0, 'sleepiness': 50.0,
                                        'curiosity': 50.0})
                self.neuron_shapes = {}
                self.state_colors = {}
                self.visible_neurons = set()
                self.neurogenesis_data = {'new_neurons': [], 'new_neurons_details': {}}
                self.neurogenesis_highlight = {}
                self.communication_events = {}
                self.weight_animations = []
                self.tamagotchi_logic = None

            def log_neurogenesis_event(self, *a, **k):
                pass

            def update(self):
                pass

        brain = Brain()
        engine = EnhancedNeurogenesis(brain, LearningConfig())
        for neuron_type in ('novelty', 'reward', 'stress'):
            name = engine.create_neuron(neuron_type, brain_state=dict(brain.state),
                                        environment={})
            if name is None:
                continue
            incoming = [e for e in brain.weights if e[1] == name]
            outgoing = [e for e in brain.weights if e[0] == name]
            self.assertTrue(incoming, f"{name} cannot be driven by anything")
            self.assertTrue(outgoing, f"{name} cannot drive anything")

    def test_a_grown_neuron_is_not_half_of_a_runaway_loop(self):
        """The return path is damped, per config.ini's reciprocal_strength."""
        from src.learning import LearningConfig
        config = LearningConfig()
        damping = config.neurogenesis.get('neuron_properties', {}).get(
            'reciprocal_strength')
        self.assertIsNotNone(damping,
                             "config.ini declares reciprocal_strength and the engine "
                             "still cannot see it")
        self.assertLess(float(damping), 1.0)


# ===========================================================================
# 5. The headless trainer and the game are the same brain
# ===========================================================================
class HeadlessParityTests(unittest.TestCase):
    """A brain trained without the GUI must behave identically inside it.

    The trainer used to carry its own propagation (no neutral baseline, a
    0.1 timestep, clamped to -100..100), its own Hebbian rule (a non-negative
    product) and its own neurogenesis thresholds, so headless training produced
    a brain the game then ran differently. These tests pin the shared core.
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(_REPO_ROOT, 'headless'))
        import importlib
        cls.trainer = importlib.import_module('headless_trainer')

    def test_the_trainer_uses_the_shared_transfer_function(self):
        import inspect
        source = inspect.getsource(self.trainer.HeadlessBrain.propagate)
        self.assertIn("propagate(self.state", source)
        self.assertNotIn("* 0.1", source,
                         "the trainer's own timestep is back")

    def test_the_trainer_uses_the_shared_plasticity_rule(self):
        import inspect
        source = inspect.getsource(self.trainer.HeadlessBrain.perform_hebbian_learning)
        self.assertIn("self.plasticity.commit", source)
        self.assertNotIn("v1 / 100.0", source,
                         "the trainer's non-negative Hebbian product is back")

    def test_the_trainer_asks_the_capability_monitor_to_grow(self):
        import inspect
        source = inspect.getsource(self.trainer.HeadlessBrain.check_neurogenesis)
        self.assertIn("find_deficit", source)
        self.assertNotIn("anxiety > 70", source)
        self.assertNotIn("curiosity > 75", source)

    def test_the_same_network_steps_identically_in_both(self):
        from src.propagation import propagate

        brain = self.trainer.HeadlessBrain()
        brain.positions['hidden'] = (0, 0)
        brain.state['hidden'] = 50.0
        brain.weights[('anxiety', 'hidden')] = 0.8
        brain.state['anxiety'] = 100.0

        reference_state = dict(brain.state)
        for _ in range(20):
            brain.propagate()
            propagate(reference_state, brain.weights, ['hidden'])

        self.assertAlmostEqual(brain.state['hidden'], reference_state['hidden'],
                               places=6)
        self.assertGreater(brain.state['hidden'], 80.0,
                           "an excitatory synapse failed to drive its target")

    def test_the_trainer_records_provenance_too(self):
        brain = self.trainer.HeadlessBrain()
        brain.apply_weight_change(('hunger', 'satisfaction'), value=0.5,
                                  mechanism='hebbian',
                                  detail={'correlation': 0.6, 'samples': 40})
        self.assertIn("kept happening together",
                      brain.explain_weight(('hunger', 'satisfaction')))

    def test_strengthening_a_neuron_is_bounded(self):
        """An unbounded multiplier makes one neuron saturate the whole brain."""
        from src.neurogenesis import MAX_STRENGTH_MULTIPLIER
        brain = self.trainer.HeadlessBrain()
        engine = brain.enhanced_neurogenesis
        name = engine.create_neuron('stress', brain_state=dict(brain.state),
                                    environment={})
        self.assertIsNotNone(name)
        for _ in range(50):
            engine._strengthen_existing_neuron('stress', engine.functional_neurons[name].specialization)
        self.assertLessEqual(engine.functional_neurons[name].strength_multiplier,
                             MAX_STRENGTH_MULTIPLIER)


if __name__ == '__main__':
    unittest.main()
