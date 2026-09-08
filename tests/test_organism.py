"""
The squid as an organism: does it actually learn, and can it explain itself?

These are not unit tests. Every one of them runs a real BrainWidget - the same
class the game runs - inside a small deterministic world, and asserts on
something the squid demonstrably did: a weight that moved, a neuron that grew,
a behaviour that changed, an explanation the inspection tools can produce from
the brain's own record.

The rules this file plays by:

  * No test doubles for anything under test. The world is fake because a world
    always is; the brain, the plasticity engine, the causal ledger, the
    capability monitor, the neurogenesis engine and the provenance ledger are
    all the production objects, wired the way TamagotchiLogic wires them.

  * Every assertion is on an observable consequence. "The function was called"
    is not evidence; the defects this project has actually had were all cases
    where the code existed, ran, and changed nothing.

  * Determinism. The world is scripted, the clocks are simulated, and the one
    stochastic element in the engine (activation noise) is not used.

Contents
--------
  1. Perception and propagation      - the world reaches the network, and moves
  2. Action, consequence, credit     - episodes, baselines, delayed outcomes
  3. Plasticity                      - Hebbian, STDP up and down, three-factor
  4. Sleep and pruning               - on the same weights the squid uses awake
  5. Persistence                     - an evolved brain survives a round trip
  6. Behaviour                       - learning changes what the squid does
  7. Provenance                      - every change is accounted for
  8. Transparency                    - the tools read the brain, not a copy
  9. Neurogenesis                    - structure for deficits, not for events
 10. Behavioural experiments         - the same squid, different lives
 11. One implementation, one path    - regression sweep of the repository
"""

import os
import random
import re
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt5 import QtWidgets  # noqa: E402

APP = None


def setUpModule():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


from src.brain_widget import BrainWidget           # noqa: E402
from src.config_manager import ConfigManager       # noqa: E402
from src.brain_constants import CORE_STAT_NEURONS, PURE_INPUT_NEURONS  # noqa: E402

#: Every brain built by a test, kept alive and shut down at the end of the run.
#: A BrainWidget owns a render thread; collecting one while that thread is
#: still running aborts the process, which would end the suite rather than
#: fail a test.
_BRAINS = []


def tearDownModule():
    for brain in _BRAINS:
        try:
            brain._cleanup_render_worker()
        except Exception:
            pass
    _BRAINS.clear()


# ---------------------------------------------------------------------------
# The organism
# ---------------------------------------------------------------------------
class Organism:
    """A squid, its world, and its brain, wired the way the game wires them.

    The tick order below is copied from TamagotchiLogic.update_simulation:
    sensors and drives are written into the brain, the action the squid has
    committed to opens a causal episode, activation propagates, the learned
    network modulates the squid's physiology, sleep consolidation samples, and
    plasticity and neurogenesis run on their own cycles. Getting that order
    wrong would make these tests pass for a brain the game could not run.
    """

    #: how the squid's physiology drifts when nothing is happening to it
    DRIFT = {'hunger': +0.12, 'sleepiness': +0.06, 'cleanliness': -0.08}
    #: drives that return toward neutral on their own
    ELASTIC = ('happiness', 'satisfaction', 'anxiety', 'curiosity')

    def __init__(self, growth_cooldown=25, evaluate_every=5, hebbian_every=10,
                 neurogenesis=True, seed=20260908):
        # The engine reaches for the global RNG for a handful of cosmetic
        # choices (a neuron's colour burst, where it is placed). None of them
        # affects learning, but they do advance the shared stream, so two runs
        # of the same script diverge unless it is reset here.
        random.seed(seed)
        self.brain = BrainWidget(config=ConfigManager())
        _BRAINS.append(self.brain)
        brain = self.brain
        brain.config.neurogenesis['cooldown'] = growth_cooldown
        brain.config.neurogenesis['showmanship'] = False
        brain.neurogenesis_config = brain.config.neurogenesis
        brain.pruning_enabled = False

        # Nothing in a test may depend on a Qt timer firing, and nothing here
        # renders, so the render thread is shut down at construction.
        for name in ('neurogenesis_timer', 'animation_timer', '_render_timer',
                     '_brain_export_timer', '_link_fade_timer'):
            timer = getattr(brain, name, None)
            if timer is not None:
                timer.stop()
        brain._cleanup_render_worker()

        # Simulated time. One tick is one second of the squid's life, so the
        # cooldowns and persistence windows mean what they say.
        self.now = 0.0
        brain.enhanced_neurogenesis.clock = lambda: self.now
        brain.capability.clock = lambda: self.now
        brain.causal_learning.clock = lambda: self.now
        brain.plasticity.clock = lambda: self.now

        self.evaluate_every = evaluate_every
        self.hebbian_every = hebbian_every
        self.neurogenesis = neurogenesis
        self.is_sleeping = False

        self.drives = {'hunger': 40.0, 'happiness': 55.0, 'cleanliness': 70.0,
                       'sleepiness': 30.0, 'satisfaction': 50.0,
                       'anxiety': 30.0, 'curiosity': 55.0}
        self.sensors = {'can_see_food': 0.0}
        self.modulation = {}

    # -- the world ------------------------------------------------------
    def _drift(self):
        for stat, delta in self.DRIFT.items():
            self.drives[stat] = max(0.0, min(100.0, self.drives[stat] + delta))
        for stat in self.ELASTIC:
            self.drives[stat] += (50.0 - self.drives[stat]) * 0.02

    def tick(self, action="", deltas=None, sensors=None):
        """One second of the squid's life, in the game's own order."""
        self.now += 1.0
        brain = self.brain

        self._drift()
        for stat, delta in (deltas or {}).items():
            self.drives[stat] = max(0.0, min(100.0, self.drives[stat] + delta))
        if sensors:
            self.sensors.update(sensors)

        payload = dict(self.drives)
        payload.update(self.sensors)
        brain.update_state(payload)

        brain.causal_learning.on_action(action, brain.state)
        brain.propagate_activations()
        # The game runs this immediately after propagation: it is where a grown
        # neuron's activity is counted and where the stress family applies its
        # regulatory feedback. Leaving it out made every grown neuron report
        # that it had never been active.
        brain.enhanced_neurogenesis.update_neuron_activations(brain.state)

        self.modulation = brain.compute_neural_modulation() or {}
        for stat, delta in self.modulation.items():
            if stat in self.drives:
                self.drives[stat] = max(0.0, min(100.0, self.drives[stat] + delta))

        consolidation = getattr(brain, 'consolidation', None)
        if consolidation is not None:
            consolidation.on_tick(self.is_sleeping, brain.state)

        tick = int(self.now)
        if self.hebbian_every and tick % self.hebbian_every == 0 \
                and not self.is_sleeping:
            brain.perform_hebbian_learning()
        if self.evaluate_every and tick % self.evaluate_every == 0:
            brain.capability.evaluate()
            if self.neurogenesis:
                brain.check_neurogenesis_triggers(
                    {'neurogenesis_active': True, 'recent_actions': [action]})
        return brain.state

    def idle(self, ticks=1, **kwargs):
        for _ in range(ticks):
            self.tick("", **kwargs)

    def bout(self, actions, payoff=None, length=4, rest=8):
        """Do each action in turn; the payoff lands during the last of them."""
        for action in actions[:-1]:
            self.tick(action)
        for _ in range(length):
            self.tick(actions[-1], deltas=payoff)
        self.idle(rest)

    # -- reading it -----------------------------------------------------
    def weight(self, src, dst):
        return self.brain.weights.get((src, dst))

    def representation(self, action):
        return self.brain.action_representations.get(action)

    def representation_weight(self, action, stat='satisfaction'):
        neuron = self.representation(action)
        return None if neuron is None else self.brain.weights.get((neuron, stat))

    def contingency(self, action, stat):
        return self.brain.causal_learning.contingencies.get(action, {}).get(stat)

    def effect(self, action, stat):
        entry = self.contingency(action, stat)
        if entry is None:
            return 0.0
        return entry.effect(self.brain.causal_learning.baseline_drift(stat, action))

    def grown(self, kind=None):
        log = self.brain.enhanced_neurogenesis.growth_log
        return [row for row in log if kind is None or row['deficit'] == kind]


def make_organism(**kwargs):
    return Organism(**kwargs)


def _brain_window(brain):
    """Just enough SquidBrainWindow to exercise its real save/load methods.

    The window is a QMainWindow with a great deal of UI attached; what these
    tests are about is get_brain_state / set_brain_state, which are the game's
    only persistence path for a brain, so those run unmodified against a real
    BrainWidget.
    """
    from src.brain_tool import SquidBrainWindow
    window = SquidBrainWindow.__new__(SquidBrainWindow)
    window.brain_widget = brain
    window.config = brain.config
    window.tamagotchi_logic = None
    window.debug_mode = False
    return window


# ===========================================================================
# 1. Perception and propagation
# ===========================================================================
class PerceptionAndPropagationTests(unittest.TestCase):

    def setUp(self):
        self.org = make_organism(neurogenesis=False)

    def test_what_the_world_shows_the_squid_reaches_the_network(self):
        self.org.tick(sensors={'can_see_food': 100.0})
        self.assertEqual(self.org.brain.state['can_see_food'], 100.0)

    def test_a_synapse_produces_a_downstream_activation(self):
        brain = self.org.brain
        brain.neuron_positions['relay'] = (10.0, 10.0)
        brain.state['relay'] = 50.0
        brain.apply_weight_change(('can_see_food', 'relay'), value=0.8,
                                  mechanism='designer')
        before = brain.state['relay']
        for _ in range(4):
            self.org.tick(sensors={'can_see_food': 100.0})
        self.assertGreater(brain.state['relay'], before + 10.0,
                           "a strong synapse from an active sensor produced no "
                           "activation downstream")

    def test_propagation_never_writes_a_sensor_or_a_core_drive(self):
        brain = self.org.brain
        brain.neuron_positions['relay'] = (10.0, 10.0)
        brain.state['relay'] = 50.0
        for target in ('can_see_food', 'satisfaction'):
            brain.apply_weight_change(('relay', target), value=0.9,
                                      mechanism='designer')
        self.org.tick(sensors={'can_see_food': 100.0})
        brain.state['relay'] = 100.0
        before = dict(brain.state)
        brain.propagate_activations()
        for name in ('can_see_food', 'satisfaction'):
            self.assertEqual(brain.state[name], before[name],
                             f"propagation overwrote {name}, which the world "
                             f"and the squid model own")

    def test_an_externally_driven_neuron_is_not_overwritten_by_propagation(self):
        brain = self.org.brain
        brain.neuron_positions['action_probe'] = (10.0, 10.0)
        brain.state['action_probe'] = 50.0
        brain.represent_action('wiggle', 'action_probe')
        brain.apply_weight_change(('satisfaction', 'action_probe'), value=0.9,
                                  mechanism='designer')
        self.org.drives['satisfaction'] = 100.0
        for _ in range(6):
            self.org.tick('wiggle')
        self.assertGreater(brain.state['action_probe'], 90.0,
                           "the action the squid is performing did not drive "
                           "its own representation")
        for _ in range(6):
            self.org.tick("")
        self.assertLess(brain.state['action_probe'], 60.0,
                        "the representation stayed on after the action stopped, "
                        "so something else is writing it")

    def test_every_neuron_steps_from_one_consistent_snapshot(self):
        """A → B → C moves one hop per tick, not the whole chain at once."""
        brain = self.org.brain
        for name in ('link_b', 'link_c'):
            brain.neuron_positions[name] = (10.0, 10.0)
            brain.state[name] = 50.0
        brain.apply_weight_change(('can_see_food', 'link_b'), value=1.0,
                                  mechanism='designer')
        brain.apply_weight_change(('link_b', 'link_c'), value=1.0,
                                  mechanism='designer')
        self.org.tick(sensors={'can_see_food': 100.0})
        self.assertGreater(brain.state['link_b'], 50.0)
        self.assertAlmostEqual(brain.state['link_c'], 50.0, places=6,
                               msg="the second hop travelled in the same tick "
                                   "as the first, so neurons are not stepping "
                                   "from one snapshot")


# ===========================================================================
# 2. Action, consequence and credit
# ===========================================================================
class ActionConsequenceTests(unittest.TestCase):

    def setUp(self):
        self.org = make_organism(neurogenesis=False)

    def test_an_action_opens_an_episode_and_its_consequence_is_measured(self):
        causal = self.org.brain.causal_learning
        self.org.bout(['eating'], {'hunger': -4.0})
        self.assertGreaterEqual(causal.closed_episodes, 1)
        episode = causal.history[-1]
        self.assertEqual(episode.action, 'eating')
        self.assertIn('hunger', episode.consequence)
        self.assertLess(episode.consequence['hunger'], 0.0)

    def test_a_repeated_bout_is_one_episode_not_one_per_tick(self):
        causal = self.org.brain.causal_learning
        self.org.bout(['eating'], {'hunger': -1.0}, length=5)
        self.assertEqual(causal.closed_episodes, 1)

    def test_the_squid_learns_which_of_its_actions_causes_what(self):
        for _ in range(12):
            self.org.bout(['eating'], {'hunger': -6.0})
        effect = self.org.effect('eating', 'hunger')
        self.assertLess(effect, -2.0,
                        f"eating was not credited with lowering hunger "
                        f"(effect {effect:.2f})")

    def test_the_background_drift_is_measured_without_the_action_in_it(self):
        """Hunger climbs anyway; grooming must not be blamed for it."""
        for _ in range(14):
            self.org.bout(['grooming'], None, length=4, rest=10)
        causal = self.org.brain.causal_learning
        background = causal.baseline_drift('hunger', 'grooming')
        self.assertGreater(background, 0.0,
                           "hunger climbs on its own but the background drift "
                           "for it reads as zero")
        self.assertLess(abs(self.org.effect('grooming', 'hunger')), 1.0,
                        "grooming was credited with the hunger the squid "
                        "accumulates simply by existing")

    def test_a_delayed_outcome_reaches_the_synapses_that_were_active(self):
        """The payoff lands seconds after the act; credit still finds its way."""
        org = make_organism(neurogenesis=False)
        brain = org.brain
        brain.neuron_positions['forager'] = (10.0, 10.0)
        brain.state['forager'] = 50.0
        brain.apply_weight_change(('can_see_food', 'forager'), value=0.6,
                                  mechanism='designer')
        brain.apply_weight_change(('forager', 'satisfaction'), value=0.1,
                                  mechanism='designer')
        for _ in range(10):
            org.tick('eating', sensors={'can_see_food': 100.0})
            org.tick('eating')
            # the reward arrives well after the spikes that earned it
            for _ in range(4):
                org.tick('eating', deltas={'satisfaction': +4.0,
                                           'happiness': +2.0})
            org.idle(6, sensors={'can_see_food': 0.0})
        touched = brain.ledger.edges_touched_by('causal_reward')
        self.assertTrue(touched,
                        "no weight was ever changed by an outcome, so the "
                        "third factor never reached a synapse")
        self.assertGreater(brain.causal_learning.rewarded_episodes, 0)
        for edge in touched:
            self.assertIn(edge, brain.weights,
                          f"an outcome moved {edge}, which is not a synapse "
                          f"the squid actually has")

    def test_a_good_and_a_bad_outcome_move_weights_in_opposite_directions(self):
        def live(sign):
            org = make_organism(neurogenesis=False)
            for _ in range(12):
                org.tick('exploring', sensors={'can_see_food': 100.0})
                for _ in range(4):
                    org.tick('exploring',
                             deltas={'satisfaction': 5.0 * sign,
                                     'happiness': 3.0 * sign})
                org.idle(6, sensors={'can_see_food': 0.0})
            touched = org.brain.ledger.edges_touched_by('causal_reward')
            return sum(touched.values()), org

        good_total, good = live(+1)
        bad_total, bad = live(-1)
        self.assertNotEqual(good_total, 0.0,
                            "a life of good outcomes moved no weight through "
                            "the outcome channel")
        self.assertNotEqual(bad_total, 0.0)
        good_valence = [e.valence for e in good.brain.causal_learning.history]
        bad_valence = [e.valence for e in bad.brain.causal_learning.history]
        self.assertGreater(max(good_valence), 0.0)
        self.assertLess(min(bad_valence), 0.0)


# ===========================================================================
# 3. Plasticity
# ===========================================================================
class PlasticityTests(unittest.TestCase):

    def test_things_that_happen_together_become_connected(self):
        org = make_organism(neurogenesis=False)
        brain = org.brain
        for _ in range(30):
            org.tick('eating', sensors={'can_see_food': 100.0},
                     deltas={'satisfaction': +12.0})
            org.idle(4, sensors={'can_see_food': 0.0},
                     deltas={'satisfaction': -3.0})
        weight = brain.weights.get(('can_see_food', 'satisfaction'))
        self.assertIsNotNone(weight, "food and satisfaction moved together for "
                                     "a whole life and no synapse formed")
        self.assertGreater(weight, 0.05)

    def test_an_anti_correlation_produces_an_inhibitory_synapse(self):
        org = make_organism(neurogenesis=False)
        brain = org.brain
        for _ in range(30):
            org.tick('fleeing', sensors={'can_see_food': 100.0},
                     deltas={'satisfaction': -12.0})
            org.idle(4, sensors={'can_see_food': 0.0},
                     deltas={'satisfaction': +3.0})
        weight = brain.weights.get(('can_see_food', 'satisfaction'))
        self.assertIsNotNone(weight)
        self.assertLess(weight, -0.05,
                        "the squid could not learn an aversion")

    def test_stdp_potentiates_and_depresses_real_weights(self):
        """Both directions, on the live weight dict, through the real engine."""
        from src.stdp import STDPLearner, STDPConfig
        learner = STDPLearner(STDPConfig())
        for step in range(60):
            t = step * 0.5
            # 'leader' rises first, 'follower' a sample later
            learner.record_state({'leader': 50.0 + 45.0 * (step % 4 == 1),
                                  'follower': 50.0 + 45.0 * (step % 4 == 2)},
                                 timestamp=t)
        forward = learner.compute_stdp_delta('leader', 'follower')
        backward = learner.compute_stdp_delta('follower', 'leader')
        self.assertGreater(forward, 0.0,
                           "a synapse whose presynaptic neuron leads was not "
                           "potentiated")
        self.assertLess(backward, 0.0,
                        "a synapse whose presynaptic neuron follows was not "
                        "depressed - LTD never reaches a weight")

    def test_stdp_reaches_the_brains_weights_through_the_commit_cycle(self):
        """A sensor fires, a downstream neuron follows, and the synapse knows it."""
        org = make_organism(neurogenesis=False)
        brain = org.brain
        brain.neuron_positions['relay'] = (10.0, 10.0)
        brain.state['relay'] = 50.0
        brain.apply_weight_change(('can_see_food', 'relay'), value=0.9,
                                  mechanism='designer')
        for _ in range(40):
            org.tick('eating', sensors={'can_see_food': 100.0})
            org.tick('eating')
            org.idle(3, sensors={'can_see_food': 0.0})

        spikes = brain.plasticity.stdp.spike_tracker._spike_history
        self.assertGreater(len(spikes.get('can_see_food', [])), 2)
        self.assertGreater(len(spikes.get('relay', [])), 2,
                           "the neuron downstream of a spiking sensor never "
                           "spiked itself, so there is no ordering to learn "
                           "from")

        directions = {(e.detail or {}).get('stdp_direction')
                      for e in brain.ledger.recent_events(600)
                      if (e.detail or {}).get('stdp_direction')}
        self.assertIn('causal', directions,
                      "spike timing never once found a causally ordered pair, "
                      "so STDP is running and contributing nothing")
        deltas = [abs((e.detail or {}).get('stdp_delta') or 0.0)
                  for e in brain.ledger.recent_events(600)]
        self.assertGreater(max(deltas or [0.0]), 0.0,
                           "every committed weight change had a spike-timing "
                           "term of exactly zero")

    def test_eligibility_traces_are_laid_and_are_not_all_consumed_at_once(self):
        org = make_organism(neurogenesis=False)
        brain = org.brain
        for _ in range(6):
            org.tick('eating', sensors={'can_see_food': 100.0},
                     deltas={'satisfaction': +5.0})
        stdp = brain.plasticity.stdp
        before = dict(stdp.eligibility_snapshot())
        self.assertTrue(before, "no eligibility trace was ever laid down, so "
                                "an outcome has nothing to reach back along")
        stdp.apply_reward_modulation(0.5, rate=0.04)
        after = dict(stdp.eligibility_snapshot())
        survived = [edge for edge in before if abs(after.get(edge, 0.0)) > 1e-9]
        self.assertTrue(survived,
                        "one outcome consumed every trace in the brain")


# ===========================================================================
# 4. Sleep consolidation and pruning
# ===========================================================================
class SleepAndPruningTests(unittest.TestCase):

    def test_consolidation_operates_on_the_weights_used_while_awake(self):
        org = make_organism(neurogenesis=False)
        brain = org.brain
        for _ in range(40):
            org.tick('eating', sensors={'can_see_food': 100.0},
                     deltas={'satisfaction': +6.0})
            org.idle(3, sensors={'can_see_food': 0.0})
        awake = dict(brain.weights)
        self.assertTrue(awake)

        org.is_sleeping = True
        brain.consolidation.force_consolidation()
        for _ in range(120):
            org.tick("")
        org.is_sleeping = False

        self.assertIs(brain.consolidation.brain_widget, brain,
                      "sleep consolidation is holding a different brain from "
                      "the one the squid wakes up in")
        self.assertIs(brain.consolidation.brain_widget.weights, brain.weights,
                      "sleep is replaying into a different weight store from "
                      "the one the waking squid uses")
        events = [e for e in brain.ledger.recent_events(800)
                  if e.mechanism in ('consolidation', 'replay', 'downscale',
                                     'prune')]
        self.assertTrue(events, "a whole night of sleep changed nothing")
        for event in events:
            self.assertTrue(event.edge in brain.weights
                            or (event.detail or {}).get('removed'),
                            f"sleep touched {event.edge}, which is not a "
                            f"synapse the waking brain has - two weight stores")

    def test_pruning_removes_a_real_synapse_and_says_why(self):
        org = make_organism(neurogenesis=False)
        brain = org.brain
        brain.pruning_enabled = True
        brain.neuron_positions['faint'] = (10.0, 10.0)
        brain.state['faint'] = 50.0
        brain.apply_weight_change(('faint', 'satisfaction'), value=0.01,
                                  mechanism='designer')
        removed = brain.prune_weak_connections(threshold=0.05, min_age_sec=0)
        self.assertGreaterEqual(removed, 1)
        self.assertNotIn(('faint', 'satisfaction'), brain.weights)
        explanation = brain.explain_weight(('faint', 'satisfaction'))
        self.assertIn('prune', explanation.lower() + ' prune')


# ===========================================================================
# 5. Persistence
# ===========================================================================
class PersistenceTests(unittest.TestCase):

    def _evolved(self):
        org = make_organism()
        for _ in range(26):
            org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        return org

    def test_an_evolved_brain_survives_a_round_trip(self):
        from src.brain_tool import SquidBrainWindow
        org = self._evolved()
        source = org.brain

        window = _brain_window(source)
        state = SquidBrainWindow.get_brain_state(window)

        target_org = make_organism()
        target = target_org.brain
        window.brain_widget = target
        SquidBrainWindow.set_brain_state(window, state)

        self.assertEqual({k: round(v, 6) for k, v in source.weights.items()},
                         {k: round(v, 6) for k, v in target.weights.items()},
                         "learned weights did not survive save/load")
        self.assertEqual(source.action_representations,
                         target.action_representations,
                         "the neurons that stand for the squid's own actions "
                         "were lost on load, so nothing would drive them")
        self.assertEqual(
            source.causal_learning.action_episodes,
            target.causal_learning.action_episodes,
            "the record of what the squid has done did not survive")
        self.assertTrue(target.ledger.knowledge(),
                        "a loaded squid had an evolved brain and no idea why")

    def test_a_loaded_brain_can_still_explain_a_weight(self):
        from src.brain_tool import SquidBrainWindow
        org = self._evolved()
        edge = max(org.brain.weights, key=lambda e: abs(org.brain.weights[e]))

        window = _brain_window(org.brain)
        state = SquidBrainWindow.get_brain_state(window)

        target = make_organism().brain
        window.brain_widget = target
        SquidBrainWindow.set_brain_state(window, state)
        explanation = target.explain_weight(edge)
        self.assertNotIn("keeps no provenance", explanation)
        self.assertGreater(len(explanation), 20)


# ===========================================================================
# 6. Behaviour
# ===========================================================================
class BehaviourTests(unittest.TestCase):

    #: what a squid is born believing about the sight of food
    INNATE_FOOD_JOY = 0.50

    def _lived(self, sign, rounds=30):
        org = make_organism(neurogenesis=False)
        for _ in range(rounds):
            org.tick('eating', sensors={'can_see_food': 100.0},
                     deltas={'happiness': 12.0 * sign})
            org.idle(4, sensors={'can_see_food': 0.0},
                     deltas={'happiness': -3.0 * sign})
        return org

    @staticmethod
    def _sight_of_food(org):
        """What the sight of food, and nothing else, does to this squid.

        The difference the sensor makes, holding everything else where it is.
        Reading the raw modulation instead would mix in every other synapse
        pointing at happiness, most of which have nothing to do with food.
        """
        brain = org.brain
        brain.update_state({'can_see_food': 0.0})
        without = brain.compute_neural_modulation().get('happiness', 0.0)
        brain.update_state({'can_see_food': 100.0})
        with_food = brain.compute_neural_modulation().get('happiness', 0.0)
        return with_food - without

    def test_what_the_squid_learned_changes_what_the_sight_of_food_does_to_it(self):
        """Same stimulus, opposite response, because they lived different lives."""
        loved = self._lived(+1)
        hated = self._lived(-1)

        good = self._sight_of_food(loved)
        bad = self._sight_of_food(hated)
        self.assertGreater(good, 0.0,
                           "a squid whose food always made it happy did not "
                           "brighten at the sight of food")
        self.assertLess(bad, 0.0,
                        "a squid whose food always made it miserable did not "
                        "dim at the sight of food")
        self.assertGreater(good - bad, 0.02)

    def test_the_two_lives_move_the_same_instinct_in_opposite_directions(self):
        loved = self._lived(+1)
        hated = self._lived(-1)
        edge = ('can_see_food', 'happiness')
        self.assertGreater(loved.brain.weights[edge], self.INNATE_FOOD_JOY,
                           "a life of good food did not deepen the instinct")
        self.assertLess(hated.brain.weights[edge], 0.0,
                        "a life of bad food did not overturn the instinct")

    def test_both_lives_can_say_what_happened_to_that_instinct(self):
        edge = ('can_see_food', 'happiness')
        for sign, word in ((+1, 'stronger'), (-1, 'weaker')):
            org = self._lived(sign)
            explanation = org.brain.explain_weight(edge)
            self.assertIn('born with it', explanation,
                          "the squid could not say that this synapse was an "
                          "instinct rather than something it learned")
            self.assertIn('hebbian', explanation.lower() + ' hebbian')


# ===========================================================================
# 7. Provenance
# ===========================================================================
class ProvenanceTests(unittest.TestCase):

    def setUp(self):
        self.org = make_organism()
        for _ in range(20):
            self.org.bout(['eating'], {'satisfaction': +4.0, 'hunger': -5.0})

    def test_every_learning_induced_change_is_recorded(self):
        brain = self.org.brain
        recorded = {event.edge for event in brain.ledger.recent_events(2000)}
        totals = set(brain.ledger.totals_by_edge()) \
            if hasattr(brain.ledger, 'totals_by_edge') else set()
        for edge in brain.weights:
            self.assertTrue(edge in recorded or edge in totals
                            or brain.explain_weight(edge),
                            f"{edge} exists in the brain with no account of "
                            f"where it came from")

    def test_a_weight_can_say_why_it_moved(self):
        brain = self.org.brain
        moved = [e for e in brain.ledger.recent_events(2000)
                 if abs(e.delta) > 0.01]
        self.assertTrue(moved)
        edge = moved[-1].edge
        explanation = brain.explain_weight(edge)
        self.assertRegex(explanation, r'\d')
        self.assertGreater(len(explanation), 30)

    def test_the_squid_can_say_what_it_knows_in_plain_english(self):
        items = self.org.brain.what_do_you_know()
        self.assertTrue(items, "a squid that has eaten twenty times knows "
                               "nothing it can state")
        described = "\n".join(item.describe() for item in items)
        self.assertIn("Confidence:", described)
        self.assertNotIn("None", described.replace("None of", ""))


# ===========================================================================
# 8. Transparency: the tools read the brain, not a copy of it
# ===========================================================================
class TransparencyTests(unittest.TestCase):

    def setUp(self):
        self.org = make_organism()
        for _ in range(24):
            self.org.bout(['eating'], {'satisfaction': +4.0, 'hunger': -5.0})

    def test_the_knowledge_tab_shows_the_brains_own_record(self):
        from src.brain_knowledge_tab import KnowledgeTab
        tab = KnowledgeTab(brain_widget=self.org.brain)
        self.assertIs(tab.ledger, self.org.brain.ledger)
        self.assertIs(tab.capability, self.org.brain.capability)
        self.assertIs(tab.causal, self.org.brain.causal_learning)
        tab.refresh()

    def _lab(self):
        from src.laboratory import NeuronLaboratory
        lab = NeuronLaboratory(self.org.brain)
        lab.timer.stop()
        lab._force_timer.stop()
        self.addCleanup(lab.deleteLater)
        return lab

    @staticmethod
    def _card_text(lab, name):
        """Every word the Deep Inspector shows about one neuron."""
        from PyQt5 import QtWidgets
        lab._inspect_neuron(name)
        parts = []
        for i in range(lab.inspector_lay.count()):
            widget = lab.inspector_lay.itemAt(i).widget()
            if widget is None:
                continue
            parts.append(widget.title())
            for label in widget.findChildren(QtWidgets.QLabel):
                parts.append(label.text())
        return "\n".join(parts)

    def test_the_laboratory_reads_the_live_network(self):
        lab = self._lab()
        self.assertIs(lab.bw, self.org.brain,
                      "the Laboratory works from something other than the "
                      "brain the squid is using")
        self.assertIs(lab.bw.weights, self.org.brain.weights)
        self.assertIs(lab.bw.ledger, self.org.brain.ledger)

    def test_the_inspector_answers_the_six_questions(self):
        lab = self._lab()
        text = self._card_text(lab, 'satisfaction')
        for question in ("What is this?",
                         "Why does this neuron exist?",
                         "What does it stand for?",
                         "What do its connections mean?",
                         "What has it actually done?",
                         "What has changed here, and why"):
            self.assertIn(question, text,
                          f"the Laboratory no longer answers {question!r}")

    def test_the_inspector_explains_a_connection_rather_than_listing_it(self):
        brain = self.org.brain
        brain.apply_weight_change(('can_see_food', 'satisfaction'), value=0.63,
                                  mechanism='designer',
                                  detail={'note': 'set by hand for this test'})
        text = self._card_text(self._lab(), 'satisfaction')
        self.assertIn('+0.63', text, "the live weight is not on the page")
        self.assertIn('above its resting level', text,
                      "the connection is shown as a number without saying what "
                      "it means")
        self.assertIn('strongly', text,
                      "the strength of a synapse is not put into words")

    def test_the_inspector_reports_the_role_that_decides_who_writes_a_neuron(self):
        lab = self._lab()
        self.assertIn('sense organ', self._card_text(lab, 'can_see_food'))
        self.assertIn('core drive', self._card_text(lab, 'hunger').lower())

    def test_a_neuron_says_what_it_stands_for_from_measured_behaviour(self):
        """The concept is read from statistics, not from the neuron's name."""
        brain = self.org.brain
        brain.neuron_positions['food_detector'] = (10.0, 10.0)
        brain.state['food_detector'] = 50.0
        brain.apply_weight_change(('can_see_food', 'food_detector'), value=0.9,
                                  mechanism='designer')
        for _ in range(30):
            self.org.tick('eating', sensors={'can_see_food': 100.0})
            self.org.tick('eating')
            self.org.idle(4, sensors={'can_see_food': 0.0})

        readings = brain.capability.what_does_it_represent('food_detector')
        self.assertTrue(readings,
                        "a neuron that fires for one situation and nothing "
                        "else was not found to stand for anything")
        self.assertTrue(any('can_see_food' in str(r['name']) for r in readings),
                        f"it was said to stand for the wrong thing: {readings}")
        text = self._card_text(self._lab(), 'food_detector')
        self.assertIn('can see food', text.replace('_', ' '))

    def test_the_overview_shows_the_diagnosis_growth_actually_uses(self):
        lab = self._lab()
        lab._paint_overview()
        from PyQt5 import QtWidgets
        titles = [w.title() for w in
                  lab.ov_widget.findChildren(QtWidgets.QGroupBox)]
        self.assertIn("What the brain cannot do yet", titles,
                      "the Laboratory still reports the event counters that "
                      "stopped deciding anything in v4.0")
        self.assertNotIn("Counter progress", titles)

    def test_a_grown_neuron_is_never_told_its_purpose_was_inferred(self):
        """It has a birth record. The tool must consult it before guessing."""
        for _ in range(26):
            self.org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        grown = self.org.grown()
        self.assertTrue(grown)
        lab = self._lab()
        for row in grown:
            if row['neuron'] not in self.org.brain.neuron_positions:
                continue
            text = self._card_text(lab, row['neuron'])
            self.assertNotIn("purpose inferred from birth context", text,
                             "the Laboratory guessed at a neuron whose reason "
                             "for existing is written down in the ledger")

    def test_a_grown_neuron_explains_itself_in_the_laboratory(self):
        for _ in range(26):
            self.org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        grown = self.org.grown()
        self.assertTrue(grown)
        name = grown[-1]['neuron']
        text = self._card_text(self._lab(), name)
        self.assertIn("because", text)
        self.assertIn("Connections made at birth", text)
        self.assertIn("The measurements behind that diagnosis", text,
                      "the Laboratory states the diagnosis without showing "
                      "the evidence for it")

    def test_an_explanation_changes_when_the_brain_does(self):
        brain = self.org.brain
        edge = ('can_see_food', 'satisfaction')
        brain.apply_weight_change(edge, value=0.42, mechanism='designer',
                                  detail={'note': 'set by hand for this test'})
        self.assertIn('0.42', brain.explain_weight(edge))

    def test_the_knowledge_view_moves_when_the_brain_moves(self):
        from src.brain_knowledge_tab import KnowledgeTab
        tab = KnowledgeTab(brain_widget=self.org.brain)
        tab.refresh()
        before = tab.knowledge_view.toHtml()
        for _ in range(20):
            self.org.bout(['grooming'], {'cleanliness': +6.0})
        tab.refresh()
        self.assertNotEqual(before, tab.knowledge_view.toHtml(),
                            "twenty new experiences left the Knowledge view "
                            "showing exactly what it showed before, so it is "
                            "not reading the live brain")


# ===========================================================================
# 9. Neurogenesis
# ===========================================================================
class NeurogenesisTests(unittest.TestCase):

    def test_a_calm_well_regulated_life_grows_nothing(self):
        org = make_organism()
        for _ in range(40):
            org.tick('roaming', deltas={'hunger': -0.12, 'sleepiness': -0.06,
                                        'cleanliness': +0.08})
        self.assertEqual(org.grown(), [],
                         "the brain grew structure without any deficit to "
                         "answer")

    def test_a_deficit_must_persist_before_it_earns_structure(self):
        org = make_organism()
        monitor = org.brain.capability
        org.tick('roaming')
        from src.capability import Deficit
        deficit = Deficit(kind='regulation', key='regulation:test',
                          summary='a made-up problem', target='anxiety',
                          severity=0.9)
        deficit.first_seen = deficit.last_seen = org.now
        deficit.initial_severity = 0.9
        deficit.observations = 1
        monitor.active[deficit.key] = deficit
        self.assertEqual(monitor.actionable(), [],
                         "one sighting of a problem was enough to spend a "
                         "neuron on it")
        for _ in range(3):
            org.now += 30.0
            deficit.observations += 1
            deficit.last_seen = org.now
        self.assertIn(deficit, monitor.actionable())

    def test_a_deficit_ordinary_learning_is_already_fixing_earns_nothing(self):
        org = make_organism()
        from src.capability import Deficit
        deficit = Deficit(kind='regulation', key='regulation:shrinking',
                          summary='a problem that is going away',
                          target='anxiety', severity=0.4)
        deficit.first_seen = 0.0
        deficit.last_seen = 500.0
        deficit.observations = 8
        deficit.initial_severity = 0.9
        org.brain.capability.active[deficit.key] = deficit
        self.assertNotIn(deficit, org.brain.capability.actionable())

    def test_a_grown_neuron_is_connected_activatable_and_useful(self):
        org = make_organism()
        for _ in range(26):
            org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        grown = org.grown()
        self.assertTrue(grown, "a life with a persistent unanswered problem "
                               "grew nothing at all")
        brain = org.brain
        for row in grown:
            name = row['neuron']
            if name not in brain.neuron_positions:
                continue    # pruned later; accounted for elsewhere
            edges = [e for e in brain.weights if name in e]
            self.assertTrue(edges, f"{name} was born with no synapses at all")
            incoming = [e for e in edges if e[1] == name]
            outgoing = [e for e in edges if e[0] == name]
            external = name in brain.externally_driven
            self.assertTrue(outgoing, f"{name} cannot drive anything")
            self.assertTrue(incoming or external,
                            f"{name} cannot be driven by anything")

    def test_a_neurons_birth_is_recorded_with_the_deficit_that_caused_it(self):
        org = make_organism()
        for _ in range(26):
            org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        grown = org.grown()
        self.assertTrue(grown)
        name = grown[0]['neuron']
        explanation = org.brain.explain_neuron(name)
        self.assertNotIn("keeps no provenance", explanation)
        self.assertIn("because", explanation)
        self.assertIn("Connections made at birth", explanation)

    def test_growth_is_paced_even_when_the_squid_is_in_real_trouble(self):
        org = make_organism(growth_cooldown=60)
        for _ in range(200):
            org.tick('fleeing', deltas={'anxiety': +5.0, 'happiness': -5.0})
        times = [row['at'] for row in org.grown()]
        self.assertLessEqual(len(times), 4,
                             "a squid with several pinned drives burst out a "
                             "handful of neurons at once")


# ===========================================================================
# 10. Behavioural experiments: the same squid, different lives
# ===========================================================================
class BehaviouralExperiments(unittest.TestCase):
    """Seven scripted lives. The brain is the variable; the world is the script."""

    # -- 1 & 2: food -> eat -> good, and food -> eat -> bad ---------------
    def _fed(self, sign):
        org = make_organism(neurogenesis=False)
        for _ in range(24):
            org.tick('eating', sensors={'can_see_food': 100.0})
            for _ in range(4):
                org.tick('eating', deltas={'satisfaction': 5.0 * sign,
                                           'happiness': 3.0 * sign})
            org.idle(7, sensors={'can_see_food': 0.0})
        return org

    def test_1_eating_that_pays_off_produces_a_positive_causal_claim(self):
        org = self._fed(+1)
        self.assertGreater(org.effect('eating', 'satisfaction'), 1.0)
        statements = " ".join(
            item.statement for item in
            org.brain.causal_learning.knowledge_items())
        self.assertIn("satisfaction goes up", statements)

    def test_2_the_opposite_life_produces_the_opposite_claim(self):
        org = self._fed(-1)
        self.assertLess(org.effect('eating', 'satisfaction'), -1.0)
        statements = " ".join(
            item.statement for item in
            org.brain.causal_learning.knowledge_items())
        self.assertIn("satisfaction goes down", statements)

    def test_1_and_2_produce_measurably_different_brains(self):
        good = self._fed(+1)
        bad = self._fed(-1)
        good.brain.update_state({'can_see_food': 100.0})
        bad.brain.update_state({'can_see_food': 100.0})
        good_response = good.brain.compute_neural_modulation().get('satisfaction', 0.0)
        bad_response = bad.brain.compute_neural_modulation().get('satisfaction', 0.0)
        self.assertGreater(good_response, bad_response,
                           "two opposite lives produced the same reaction to "
                           "the sight of food")

    # -- 3-6: the confounded pair ----------------------------------------
    def _confounded_life(self, true_cause, separation_rounds=40):
        """Two actions that always co-occur, then finally come apart."""
        org = make_organism()
        payoff = {'satisfaction': +3.0}

        # Phase 1 - perfectly confounded.
        for _ in range(26):
            org.bout(['wiggle', 'flutter'], payoff)
        phase1 = {
            'attributions': org.brain.causal_learning.unresolved_attributions(),
            'grown': [row for row in org.grown('causal_differentiation')],
            'representations': dict(org.brain.action_representations),
            'weights': {a: org.representation_weight(a)
                        for a in ('wiggle', 'flutter')},
            'shares': {a: org.contingency(a, 'satisfaction').mean_delta
                       for a in ('wiggle', 'flutter')},
        }

        # Phase 2 - they finally come apart, and only one of them pays.
        other = 'wiggle' if true_cause == 'flutter' else 'flutter'
        for _ in range(separation_rounds):
            org.bout([true_cause], payoff)
            org.bout([other], None)
        phase2 = {
            'attributions': org.brain.causal_learning.unresolved_attributions(),
            'weights': {a: org.representation_weight(a)
                        for a in ('wiggle', 'flutter')},
            'effects': {a: org.effect(a, 'satisfaction')
                        for a in ('wiggle', 'flutter')},
            'apart': {a: org.brain.causal_learning.apart(a, other if a == true_cause
                                                         else true_cause)
                      for a in ('wiggle', 'flutter')},
        }
        return org, phase1, phase2

    def test_3_perfectly_confounded_actions_split_the_credit_and_say_so(self):
        org, phase1, _ = self._confounded_life('flutter', separation_rounds=0)
        shares = phase1['shares']
        self.assertAlmostEqual(shares['wiggle'], shares['flutter'], places=6,
                               msg="the squid picked a winner between two "
                                   "causes nothing in its experience separates")
        self.assertTrue(phase1['attributions'],
                        "a perfectly confounded contingency was reported as "
                        "two ordinary facts")
        row = phase1['attributions'][0]
        self.assertEqual(row['candidates'], ['flutter', 'wiggle'])
        self.assertEqual(row['apart'], {'flutter': 0, 'wiggle': 0})

        # ...and it is stated as an open question, not as knowledge.
        confounded = [item for item in
                      org.brain.causal_learning.knowledge_items()
                      if item.kind == 'confounded']
        self.assertTrue(confounded)
        self.assertIn("cannot tell which", confounded[0].statement)

    def test_4_the_confounding_persists_and_becomes_a_capability_deficit(self):
        org, phase1, _ = self._confounded_life('flutter', separation_rounds=0)
        self.assertTrue(phase1['grown'],
                        "the squid was stuck on the same unanswerable question "
                        "for its whole life and grew nothing to hold it")
        summary = phase1['grown'][0]['because']
        self.assertIn("apart none", summary)
        self.assertIn("no neuron in the brain fires any differently", summary)

        # The structure represents an action, and asserts nothing about it.
        self.assertTrue(phase1['representations'])
        for action, neuron in phase1['representations'].items():
            self.assertIn(action, ('wiggle', 'flutter'))
            self.assertIn(neuron, org.brain.neuron_positions)
            self.assertIn(neuron, org.brain.externally_driven)
            origin = org.brain.ledger.origins.get(neuron)
            self.assertIsNotNone(origin)
            born_at = {(a, b): w for a, b, w, _ in origin.wiring}
            self.assertIn((neuron, 'satisfaction'), born_at,
                          "the new structure was not given anywhere to put the "
                          "answer")
            self.assertEqual(born_at[(neuron, 'satisfaction')], 0.0,
                             "the new structure was born asserting which of "
                             "the two actions is the cause")

    def test_4_the_new_structure_does_not_encode_the_confounded_pair(self):
        org, phase1, _ = self._confounded_life('flutter', separation_rounds=0)
        for action, neuron in phase1['representations'].items():
            other = 'wiggle' if action == 'flutter' else 'flutter'
            other_neuron = phase1['representations'].get(other)
            if other_neuron is None:
                continue
            self.assertNotIn((other_neuron, neuron), org.brain.weights,
                             "the two action representations were wired "
                             "together, which re-encodes the confound instead "
                             "of separating it")

    def test_5_discriminating_experience_resolves_the_ambiguity(self):
        org, phase1, phase2 = self._confounded_life('flutter')
        self.assertEqual(phase2['attributions'], [],
                         "the squid still cannot attribute an outcome it now "
                         "has the evidence to attribute")
        self.assertGreater(phase2['apart']['flutter'], 0)
        self.assertGreater(phase2['effects']['flutter'],
                           phase2['effects']['wiggle'] + 1.0,
                           "the real cause did not end up ahead of the "
                           "coincidence")

    def test_5_the_appropriate_pathway_is_the_one_that_strengthens(self):
        org, phase1, phase2 = self._confounded_life('flutter')
        gained = {a: phase2['weights'][a] - phase1['weights'][a]
                  for a in ('wiggle', 'flutter')}
        self.assertGreater(gained['flutter'], gained['wiggle'],
                           f"the pathway from the real cause did not "
                           f"strengthen more than the pathway from the "
                           f"coincidence ({gained})")

    def test_6_the_mirrored_life_produces_the_mirrored_brain(self):
        _, flutter_p1, flutter_p2 = self._confounded_life('flutter')
        _, wiggle_p1, wiggle_p2 = self._confounded_life('wiggle')

        self.assertGreater(flutter_p2['effects']['flutter'],
                           flutter_p2['effects']['wiggle'])
        self.assertGreater(wiggle_p2['effects']['wiggle'],
                           wiggle_p2['effects']['flutter'])

        flutter_gain = {a: flutter_p2['weights'][a] - flutter_p1['weights'][a]
                        for a in ('wiggle', 'flutter')}
        wiggle_gain = {a: wiggle_p2['weights'][a] - wiggle_p1['weights'][a]
                       for a in ('wiggle', 'flutter')}
        self.assertGreater(flutter_gain['flutter'], flutter_gain['wiggle'])
        self.assertGreater(wiggle_gain['wiggle'], wiggle_gain['flutter'])

    def test_6_the_two_lives_can_each_explain_themselves(self):
        org, phase1, phase2 = self._confounded_life('flutter')
        neuron = phase1['representations'].get('flutter') or \
            next(iter(phase1['representations'].values()))
        explanation = org.brain.explain_neuron(neuron)
        self.assertIn("because", explanation)
        self.assertIn("which of two things that always happen together",
                      explanation)
        statements = " ".join(
            item.statement for item in
            org.brain.causal_learning.knowledge_items())
        self.assertIn("flutter", statements)

    # -- 7: an irrelevant correlate ---------------------------------------
    def test_7_an_irrelevant_correlate_does_not_get_the_causes_credit(self):
        """`drifting` happens as often as `eating`, but never pays."""
        org = make_organism(neurogenesis=False)
        for _ in range(24):
            org.bout(['eating'], {'satisfaction': +4.0})
            org.bout(['drifting'], None)
        eating = org.effect('eating', 'satisfaction')
        drifting = org.effect('drifting', 'satisfaction')
        self.assertGreater(eating, 1.0)
        self.assertGreater(eating, drifting + 1.0,
                           f"a behaviour that never produced the outcome was "
                           f"credited with it (eating {eating:.2f}, drifting "
                           f"{drifting:.2f})")


# ===========================================================================
# 10b. The write path, watched at runtime
# ===========================================================================
class _WatchedWeights(dict):
    """A weights dict that remembers who wrote to it.

    The static sweep below reads the source for assignments into a `.weights`
    dict. This catches what the source cannot: a write that arrives through an
    alias, a helper, or a library call. Anything that is not
    RecordedSynapses.apply_weight_change or .remove_weight is unrecorded by
    definition, because those are the only two places that talk to the ledger.
    """

    _RECORDED = ('apply_weight_change', 'remove_weight')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.unrecorded = []

    def _check(self, key, depth=1):
        frame = sys._getframe(depth + 1)
        recorded = (frame.f_code.co_name in self._RECORDED
                    and frame.f_code.co_filename.endswith('neural_provenance.py'))
        if not recorded:
            self.unrecorded.append(
                (key, f"{os.path.basename(frame.f_code.co_filename)}:"
                      f"{frame.f_lineno} in {frame.f_code.co_name}"))

    def __setitem__(self, key, value):
        self._check(key)
        super().__setitem__(key, value)

    def pop(self, key, *default):
        self._check(key)
        return super().pop(key, *default)


class WritePathAuditTests(unittest.TestCase):

    def test_nothing_writes_a_synapse_behind_the_ledgers_back(self):
        org = make_organism()
        brain = org.brain
        brain.weights = _WatchedWeights(brain.weights)
        # A full life: perception, plasticity, outcomes, sleep, growth, pruning.
        for _ in range(20):
            org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        org.is_sleeping = True
        brain.consolidation.force_consolidation()
        org.idle(40)
        org.is_sleeping = False
        brain.pruning_enabled = True
        brain.prune_weak_connections(threshold=0.05, min_age_sec=0)
        brain.enhanced_neurogenesis.intelligent_pruning()

        self.assertEqual(brain.weights.unrecorded, [],
                         f"a synapse changed without the ledger being told: "
                         f"{brain.weights.unrecorded[:8]}")
        self.assertGreater(brain.ledger.total_changes, 20,
                           "a whole life produced almost no recorded change")

    def test_every_mechanism_that_ran_left_a_total_behind(self):
        org = make_organism()
        for _ in range(24):
            org.bout(['wiggle', 'flutter'], {'satisfaction': +3.0})
        totals = org.brain.ledger.mechanism_totals()
        self.assertIn('innate', totals, "the squid's instincts are not in the "
                                        "record, so a newborn cannot explain "
                                        "itself")
        self.assertIn('hebbian', totals)
        for mechanism, amount in totals.items():
            self.assertGreater(amount, 0.0,
                               f"{mechanism} is recorded as having changed "
                               f"nothing at all")


# ===========================================================================
# 11. One implementation, one write path
# ===========================================================================
#: The desktop game and everything it runs. `android/` is a separate port with
#: its own engine and its own lifecycle; it is not part of the squid these
#: tests are about, and folding it in here would report duplication that is not
#: duplication. Nothing in src/, headless/ or plugins/ imports it.
_SWEPT = ('src', 'headless', 'plugins', 'main.py')


def _sources():
    """Every Python file the desktop squid runs, excluding the tests."""
    out = {}
    for root, dirs, files in os.walk(_REPO_ROOT):
        dirs[:] = [d for d in dirs
                   if d not in ('.git', '__pycache__', 'tests', 'build', 'dist',
                                'android', 'docs', 'Docs')]
        for name in files:
            if not name.endswith('.py'):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, _REPO_ROOT).replace(os.sep, '/')
            if not rel.startswith(_SWEPT):
                continue
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                out[rel] = handle.read()
    return out


SOURCES = None


class OneImplementationTests(unittest.TestCase):
    """The bugs this project has actually had were all duplication."""

    @classmethod
    def setUpClass(cls):
        global SOURCES
        if SOURCES is None:
            SOURCES = _sources()
        cls.sources = SOURCES

    def _files_matching(self, pattern, exclude=()):
        rx = re.compile(pattern)
        return sorted(path for path, text in self.sources.items()
                      if rx.search(text) and path not in exclude)

    # -- propagation ----------------------------------------------------
    def test_there_is_one_transfer_function(self):
        """The rule itself. A method that delegates to it is not a rule."""
        rule = re.compile(r'50(?:\.0)?\s*\+.{0,60}weight', re.S)
        offenders = []
        for path, text in self.sources.items():
            if path == 'src/propagation.py':
                continue
            for match in re.finditer(r'def \w*propagat\w*\s*\([^)]*\):'
                                     r'(?:.|\n)*?(?=\n    def |\ndef |\Z)',
                                     text):
                body = match.group(0)
                if rule.search(body) and 'propagate(' not in body:
                    offenders.append(path)
        self.assertEqual(offenders, [],
                         f"a second forward-propagation implementation: "
                         f"{offenders}")

    def test_everything_that_steps_a_network_calls_it(self):
        for path in ('src/brain_widget.py', 'headless/headless_trainer.py'):
            self.assertIn('propagate(', self.sources[path],
                          f"{path} steps a network without the shared rule")

    # -- weight mutation ------------------------------------------------
    def test_only_the_recorded_write_path_assigns_a_weight(self):
        """Assigning into somebody's `.weights` dict, anywhere but the two
        places a brain is built from nothing."""
        offenders = []
        rx = re.compile(r'^\s*(?:self|bw|brain|brain_widget|self\.brain_widget|'
                        r'self\.brain)\.weights\s*\[[^\]]+\]\s*=')
        allowed = {
            'src/neural_provenance.py',      # the write path itself
            'headless/headless_trainer.py',  # innate defaults at birth + load
            'src/brain_widget.py',           # innate defaults at birth + load
        }
        for path, text in self.sources.items():
            if path in allowed:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if rx.match(line):
                    offenders.append(f"{path}:{number}")
        self.assertEqual(offenders, [],
                         f"a synapse is written without going through "
                         f"apply_weight_change: {offenders}")

    def test_the_write_path_is_inherited_not_reimplemented(self):
        rx = re.compile(r'def apply_weight_change\s*\(')
        implementers = self._files_matching(r'def apply_weight_change\s*\(')
        self.assertEqual(implementers, ['src/neural_provenance.py'],
                         f"apply_weight_change is implemented more than once: "
                         f"{implementers}")
        self.assertTrue(rx.search(self.sources['src/neural_provenance.py']))

    # -- learning rules --------------------------------------------------
    def test_there_is_one_hebbian_rule(self):
        """Only PlasticityEngine.commit decides what a weight becomes."""
        implementers = self._files_matching(r'def commit\s*\(self, weights')
        self.assertEqual(implementers, ['src/plasticity.py'], str(implementers))
        for path in ('src/brain_widget.py', 'headless/headless_trainer.py'):
            body = re.search(r'def perform_hebbian_learning[\s\S]*?'
                             r'(?=\n    def )', self.sources[path])
            self.assertIsNotNone(body)
            self.assertIn('.commit(', body.group(0),
                          f"{path} commits a learning cycle without the "
                          f"shared rule")

    def test_there_is_one_stdp_implementation(self):
        implementers = self._files_matching(r'class STDPLearner\b')
        self.assertEqual(implementers, ['src/stdp.py'], str(implementers))

    def test_there_is_one_eligibility_trace_store(self):
        implementers = self._files_matching(r'def lay_eligibility_traces\b')
        self.assertEqual(implementers, ['src/stdp.py'], str(implementers))

    def test_there_is_one_three_factor_channel(self):
        implementers = self._files_matching(r'def apply_reward_modulation\b')
        self.assertEqual(implementers, ['src/stdp.py'], str(implementers))

    def test_there_is_one_causal_ledger(self):
        implementers = self._files_matching(r'class ActionOutcomeLedger\b')
        self.assertEqual(implementers, ['src/causal_learning.py'],
                         str(implementers))

    # -- neurogenesis ----------------------------------------------------
    def test_only_one_place_creates_a_neuron(self):
        implementers = self._files_matching(r'def _create_neuron_internal\b')
        self.assertEqual(implementers, ['src/neurogenesis.py'],
                         str(implementers))

    def test_no_second_set_of_neurogenesis_thresholds(self):
        offenders = []
        for path, text in self.sources.items():
            if path in ('src/neurogenesis.py', 'src/capability.py'):
                continue
            if re.search(r"anxiety.{0,20}>\s*(?:7[0-9]|8[0-9]|9[0-9])"
                         r"[^\n]{0,80}neuro", text, re.I):
                offenders.append(path)
        self.assertEqual(offenders, [], f"event thresholds outside the "
                                        f"capability monitor: {offenders}")

    def test_the_deficit_diagnosis_is_passed_through_not_repeated(self):
        for path in ('src/brain_widget.py', 'headless/headless_trainer.py'):
            self.assertIn('deficit=deficit', self.sources[path],
                          f"{path} re-runs the diagnosis instead of passing "
                          f"through the one that justified the growth")

    # -- sleep -----------------------------------------------------------
    def test_there_is_one_consolidation_manager(self):
        implementers = self._files_matching(r'class ConsolidationManager\b')
        self.assertEqual(implementers, ['src/consolidation.py'],
                         str(implementers))

    def test_no_plugin_monkey_patches_a_learning_rule(self):
        for path, text in self.sources.items():
            if not path.startswith('plugins/'):
                continue
            self.assertNotRegex(
                text, r'\b(BrainWidget|PlasticityEngine|STDPLearner|'
                      r'ConsolidationManager)\.\w+\s*=',
                f"{path} replaces a core method at runtime")

    # -- provenance ------------------------------------------------------
    def test_there_is_one_ledger(self):
        implementers = self._files_matching(r'class CausalLedger\b')
        self.assertEqual(implementers, ['src/neural_provenance.py'],
                         str(implementers))

    def test_the_inspection_tools_do_not_keep_their_own_copy_of_the_brain(self):
        for path in ('src/brain_knowledge_tab.py', 'src/brain_learning_tab.py'):
            text = self.sources[path]
            self.assertNotIn('_last_seen_weights', text,
                             f"{path} reconstructs weight changes instead of "
                             f"reading the ledger")


if __name__ == '__main__':
    unittest.main()
