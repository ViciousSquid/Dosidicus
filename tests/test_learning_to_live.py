"""Does the squid get better at living, and can it be shown?

Two halves.

THE RULES (fast). What each learning mechanism is and is not allowed to do,
checked on the real brain one mechanism at a time:

  * a synapse into an action neuron is moved by what came of the action, and
    by nothing else - not co-activation, not the reward broadcast, not sleep;
  * a neuron is grown only for something the squid cannot represent;
  * a neuron grown for a combination is silent until everything it stands for
    is present, and is taken back if nothing ever comes to depend on it;
  * no drive is lowered by arithmetic.

THE LIFE (a few seconds each). A squid is raised in the headless tank, a
frozen copy of its brain is put in worlds it has never seen, and what happens
to it is compared with what happens to its own newborn self in the same
worlds. Stated in the squid's real statistics - anxiety, hunger, health, food
eaten - never in a combined score.

The headline, which every test in the second half is a control for:

    A squid learns to manage its anxiety by hiding in a plant. Nobody tells it
    to. It sees a plant and grows a sense for one; it tries sheltering, at
    first for no reason; it finds that sheltering helps when it is frightened
    AND a plant is in sight and not otherwise; having no neuron for that
    combination, it grows one; and from then on it hides when frightened.
"""
import contextlib
import io
import unittest

from headless import lifetime
from headless.headless_trainer import HeadlessSimulation
from src.action_discovery import ActionDiscovery, PRESENT
from src.brain_constants import (ACTION_NEURONS, INNATE_ACTION_WIRING, PLANT_SENSOR,
                                 is_motor_synapse, newborn_neurons)
from src.capability import (Deficit, NEURON_WORTHY, combination_signature,
                            signature_parts)
from src.neurogenesis import PROBATION_SECONDS, combination_name
from src.portable_brain import HeadlessBrain, TrainingConfig
from src.propagation import rests_at_zero, signal_of

SHELTER_NEURON = 'anxiety_high_and_sees_plant'


def quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def brain(**config):
    return quiet(HeadlessBrain, TrainingConfig(seed=7, **config))


def innate_motor_weights(b):
    return {edge: w for edge, w in b.weights.items() if is_motor_synapse(edge)}


def grow_combination(b, parts, motor=None):
    """Grow a neuron for a combination the way the engine does: from a
    representation deficit carrying the evidence."""
    growth = b.enhanced_neurogenesis
    signature = combination_signature(parts)
    evidence = {'signature': signature, 'combination': [list(p) for p in parts],
                'found_by': 'its own trials'}
    if motor:
        evidence['motor'] = motor
    deficit = Deficit(kind='representation', key=f'representation:{signature}',
                      summary='test combination', target=signature,
                      sources=[p[0] for p in parts], remedy='fire for both',
                      severity=0.8, evidence=evidence, suggested_type='novelty',
                      specialization='situation')
    context = growth._build_context('novelty', b.state, {})
    return quiet(growth._create_neuron_internal, context, deficit=deficit)


def settle(b, values, ticks=30):
    for name, value in values.items():
        if name in b.state:
            b.state[name] = float(value)
    for _ in range(ticks):
        for name, value in values.items():
            if name in b.state:
                b.state[name] = float(value)
        b.propagate(observe_learning=False)
    return b.state


# ===========================================================================
# THE RULES
# ===========================================================================
class MotorSynapsesLearnOnlyFromOutcomes(unittest.TestCase):
    """The collapse this fixes: a squid that had learned for 20,000 ticks ate
    nothing, because the correlational rule and stray birth wiring had been
    rewriting the synapses that decide what it does."""

    def test_co_activation_never_moves_a_synapse_into_an_action_neuron(self):
        b = brain()
        before = innate_motor_weights(b)
        # Food comes and goes, and the eating neuron follows it - exactly the
        # correlation that used to drive can_see_food -> act_eat to the clamp.
        for tick in range(400):
            b.advance_clock(1.0)
            seen = 100.0 if (tick // 10) % 2 else 0.0
            b.update_state({'can_see_food': seen, 'hunger': 60.0 + (tick % 7)})
            b.propagate()
            if tick % 20 == 0:
                b.perform_hebbian_learning()
        self.assertEqual(innate_motor_weights(b), before,
                         "co-activation changed what the squid does")
        # ...while it went on learning about the world as before.
        self.assertTrue(any(not is_motor_synapse(e) for e in b.weights
                            if e not in before),
                        "the correlational rule learned nothing at all")

    def test_the_reward_broadcast_leaves_motor_synapses_alone(self):
        b = brain()
        before = innate_motor_weights(b)
        for tick in range(60):
            b.advance_clock(1.0)
            b.update_state({'can_see_food': 100.0, 'hunger': 80.0})
            b.propagate()
        episode = type('E', (), {'valence': 0.9, 'action': 'eating',
                                 'episode_id': 'test'})()
        b.causal_learning._assign_credit(episode)
        self.assertEqual(innate_motor_weights(b), before)

    def test_a_nights_sleep_does_not_wear_an_instinct_away(self):
        b = brain()
        before = innate_motor_weights(b)
        for tick in range(200):
            b.advance_clock(1.0)
            b.update_state({'can_see_food': 100.0 if tick % 9 < 4 else 0.0})
            b.propagate()
            b.consolidate(False)
        for _ in range(3):
            quiet(b.consolidation.force_consolidation)
        self.assertEqual(innate_motor_weights(b), before)

    def test_every_innate_reflex_is_a_motor_synapse_so_all_of_them_are_covered(self):
        for source, target, _weight in INNATE_ACTION_WIRING:
            self.assertTrue(is_motor_synapse((source, target)))
            self.assertIn(target, ACTION_NEURONS)


class OnlyWhatCannotBeRepresentedEarnsANeuron(unittest.TestCase):

    def test_the_kinds_of_deficit_a_neuron_answers(self):
        self.assertEqual(set(NEURON_WORTHY),
                         {'representation', 'causal_differentiation'})

    def test_a_drive_stuck_at_an_extreme_grows_nothing(self):
        """It used to grow an 'emergency' stress neuron. A squid in trouble
        needs to DO something; a neuron does not do anything."""
        b = brain()
        growth = b.enhanced_neurogenesis
        growth._first_real_tick = 0.0
        for tick in range(400):
            b.advance_clock(1.0)
            b.update_state({'anxiety': 99.0, 'hunger': 97.0, 'cleanliness': 2.0})
            b.propagate()
            if tick % 5 == 0:
                quiet(b.check_neurogenesis, {'status': 'roaming'}, tick)
        self.assertEqual(set(b.positions) - set(newborn_neurons()), set(),
                         "a stuck drive was answered with a neuron")
        self.assertIsNone(growth.find_deficit(b.state))
        # The diagnosis is still made, and still shown - it is just not a
        # reason to grow.
        self.assertTrue(any(d.kind == 'regulation'
                            for d in b.capability.active.values()))

    def test_asked_directly_for_a_regulator_it_says_why_not(self):
        b = brain()
        growth = b.enhanced_neurogenesis
        growth._first_real_tick = -100.0
        deficit = Deficit(kind='regulation', key='regulation:anxiety:down',
                          summary='anxiety stuck', target='anxiety',
                          severity=1.0, evidence={'direction': 'down'},
                          suggested_type='stress')
        self.assertFalse(growth.should_create_neuron(deficit=deficit))
        self.assertIn('synapse', growth.stood_down[-1][2])

    def test_a_situation_that_merely_recurs_grows_nothing(self):
        b = brain()
        growth = b.enhanced_neurogenesis
        growth._first_real_tick = -100.0
        recurring = Deficit(kind='representation',
                            key='representation:can_see_food|hunger-high',
                            summary='keeps coming round',
                            target='can_see_food|hunger-high', severity=0.8,
                            evidence={'signature': 'can_see_food|hunger-high',
                                      'occurrences': 40})
        self.assertFalse(growth.should_create_neuron(deficit=recurring))
        self.assertIn('nothing the squid does', growth.stood_down[-1][2])

    def test_no_newborn_is_given_a_neuron_for_its_personality(self):
        self.assertFalse(hasattr(b := brain().enhanced_neurogenesis,
                                 'create_personality_starter_neuron'), b)

    def test_there_is_no_quota_per_kind_of_neuron(self):
        b = brain()
        b.learning_config.neurogenesis['max_per_type'] = {'novelty': 0}
        name = grow_combination(b, [['can_see_food', 1], ['hunger', 1]])
        self.assertIsNotNone(name, "a per-type quota still blocks growth")


class ACombinationNeuronIsSilentUntilItsSituationHolds(unittest.TestCase):

    def setUp(self):
        self.b = brain()
        quiet(self.b.perceive, 'plant_in_view', 100.0)
        quiet(self.b.propagate)
        self.name = grow_combination(self.b, [[PLANT_SENSOR, 1], ['anxiety', 1]])
        self.neuron = self.b.enhanced_neurogenesis.functional_neurons[self.name]

    def _reading(self, plant, anxiety):
        self.b.perceive('plant_in_view', 100.0 if plant else 0.0)
        state = settle(self.b, {'anxiety': anxiety})
        return state[self.name]

    def test_it_is_named_for_what_it_stands_for(self):
        self.assertEqual(self.name, SHELTER_NEURON)
        self.assertEqual(combination_name([['can_see_food', 1], ['hunger', -1]]),
                         'sees_food_and_hunger_low')
        self.assertEqual(signature_parts('can_see_food|hunger-low'),
                         [['can_see_food', 1], ['hunger', -1]])

    def test_it_fires_for_both_and_for_neither_alone(self):
        self.assertGreater(self._reading(plant=True, anxiety=90.0), 90.0)
        self.assertEqual(self._reading(plant=True, anxiety=30.0), 0.0)
        self.assertEqual(self._reading(plant=False, anxiety=90.0), 0.0)
        self.assertEqual(self._reading(plant=False, anxiety=30.0), 0.0)

    def test_silent_means_it_contributes_exactly_nothing(self):
        """The old neurons rested at 50 and pushed everything they touched the
        wrong way whenever they were below it: a +0.40 synapse was measured
        delivering -19.97 to the eating neuron."""
        self.assertTrue(rests_at_zero(self.name))
        self._reading(plant=False, anxiety=30.0)
        self.assertEqual(signal_of(self.name, self.b.state[self.name]), 0.0)
        self.b.apply_weight_change((self.name, 'act_eat'), value=0.4,
                                   mechanism='test', create=True)
        before = settle(self.b, {'can_see_food': 100.0, 'hunger': 60.0})['act_eat']
        self.b.remove_weight((self.name, 'act_eat'))
        after = settle(self.b, {'can_see_food': 100.0, 'hunger': 60.0})['act_eat']
        self.assertAlmostEqual(before, after, places=6)

    def test_it_is_born_asserting_nothing(self):
        self.assertEqual([e for e in self.b.weights if e[0] == self.name], [])
        self.assertEqual({e[0] for e in self.b.weights if e[1] == self.name},
                         {PLANT_SENSOR, 'anxiety'})
        self.assertFalse(self.neuron.established)

    def test_what_feeds_it_is_what_it_means_and_does_not_drift(self):
        inputs = {e: w for e, w in self.b.weights.items() if e[1] == self.name}
        for tick in range(300):
            self.b.advance_clock(1.0)
            self.b.perceive('plant_in_view', 100.0 if tick % 7 < 3 else 0.0)
            self.b.update_state({'anxiety': 40.0 + (tick % 50),
                                 'hunger': 30.0 + (tick % 40)})
            self.b.propagate()
            if tick % 20 == 0:
                self.b.perform_hebbian_learning()
        self.assertEqual({e: w for e, w in self.b.weights.items()
                          if e[1] == self.name}, inputs)
        # ...and it has not been wired back onto the things that define it,
        # which would make it half of a self-amplifying loop.
        self.assertNotIn((self.name, 'anxiety'), self.b.weights)

    def test_it_survives_a_save_and_a_load_as_the_same_neuron(self):
        document = quiet(self.b.export_brain)
        restored = brain()
        self.assertTrue(quiet(restored.load_brain, document))
        again = restored.enhanced_neurogenesis.functional_neurons[self.name]
        self.assertTrue(again.quiet)
        self.assertEqual(again.threshold, self.neuron.threshold)
        self.assertEqual(again.combination, self.neuron.combination)
        restored.perceive('plant_in_view', 100.0)
        self.assertGreater(settle(restored, {'anxiety': 90.0})[self.name], 90.0)

    def test_a_neuron_from_before_v5_keeps_the_behaviour_it_was_saved_with(self):
        """A squid someone has already raised must not wake up different."""
        b = brain()
        growth = b.enhanced_neurogenesis
        context = growth._build_context('stress', b.state, {})
        old = quiet(growth._create_neuron_internal, context)      # no deficit
        neuron = growth.functional_neurons[old]
        self.assertFalse(neuron.quiet)
        self.assertEqual(neuron.threshold, 0.0)
        self.assertFalse(rests_at_zero(old))
        self.assertEqual(signal_of(old, 50.0), 0.0)      # rests at the midpoint
        self.assertEqual(signal_of(old, 20.0), -30.0)    # signed, as it always was


class ANeuronHasToComeToMatter(unittest.TestCase):

    def setUp(self):
        self.b = brain()
        self.growth = self.b.enhanced_neurogenesis
        self.name = grow_combination(self.b, [['can_see_food', 1], ['hunger', 1]])

    def test_one_nothing_depends_on_is_taken_back_and_not_grown_again_soon(self):
        self.b.sim_seconds += PROBATION_SECONDS - 1
        self.assertIsNone(quiet(self.growth.review_probation))
        self.assertIn(self.name, self.b.positions)

        self.b.sim_seconds += 2
        self.assertEqual(quiet(self.growth.review_probation), self.name)
        self.assertNotIn(self.name, self.b.positions)
        self.assertEqual([e for e in self.b.weights if self.name in e], [])
        declined = self.b.capability.declined
        self.assertGreater(declined['representation:can_see_food|hunger-high'],
                           self.b.sim_seconds)

    def test_one_that_became_the_cue_for_an_action_is_kept(self):
        self.b.apply_weight_change((self.name, 'act_rest'), value=0.6,
                                   mechanism='causal_motor_discovery', create=True)
        self.b.sim_seconds += PROBATION_SECONDS * 3
        self.assertIsNone(quiet(self.growth.review_probation))
        self.assertIn(self.name, self.b.positions)
        self.assertTrue(self.growth.functional_neurons[self.name].established)

    def test_at_the_size_limit_room_is_made_only_from_neurons_that_do_not_matter(self):
        self.b.learning_config.neurogenesis['max_neurons'] = \
            self.growth._live_neuron_count()
        second = grow_combination(self.b, [['can_see_food', 1], ['anxiety', 1]])
        self.assertIsNotNone(second)
        self.assertNotIn(self.name, self.b.positions, "the unproven neuron stayed")

        self.b.apply_weight_change((second, 'act_rest'), value=0.6,
                                   mechanism='causal_motor_discovery', create=True)
        self.growth.functional_neurons[second].established = True
        third = grow_combination(self.b, [['can_see_food', 1], ['sleepiness', 1]])
        self.assertIsNone(third, "a neuron that had earned its place was displaced")
        self.assertIn(second, self.b.positions)


class NoDriveIsLoweredByArithmetic(unittest.TestCase):

    def test_stress_neurons_no_longer_subtract_anxiety_or_cap_it(self):
        b = brain()
        growth = b.enhanced_neurogenesis
        for _ in range(5):
            context = growth._build_context('stress', b.state, {})
            quiet(growth._create_neuron_internal, context)
        b.state['anxiety'] = 95.0
        quiet(growth.update_neuron_activations, b.state)
        self.assertEqual(b.state['anxiety'], 95.0)


# ===========================================================================
# Learning from its own actions: the evidence rule, in isolation
# ===========================================================================
def trial(b, learner, *, action='approaching_plant', before, after, moment):
    """One real action and its real outcome, settled by the causal ledger."""
    state = dict(b.state)
    state.update(before)
    episode_id = b.causal_learning.on_action(action, state, now=moment)
    learner.committed(episode_id, None, action, state)
    later = dict(state)
    later.update(after)
    b.causal_learning.on_tick(later, now=moment + 7.0)
    learner.process_closed()


class WhatTheEvidenceRuleConcludes(unittest.TestCase):

    def setUp(self):
        self.b = brain(neurogenesis_enabled=False)
        quiet(self.b.perceive, 'plant_in_view', 100.0)
        quiet(self.b.propagate)
        self.learner = ActionDiscovery(self.b, rate=0.0)
        self.b.action_discovery = self.learner
        self.clock = 0.0

    def _shelter(self, plant, anxious, times=1, helps=None):
        """Sheltering relieves anxiety only when frightened AND at a plant,
        unless `helps` says otherwise."""
        relief = (plant and anxious) if helps is None else helps
        for _ in range(times):
            self.clock += 10.0
            start = 90.0 if anxious else 30.0
            trial(self.b, self.learner, moment=self.clock,
                  before={PLANT_SENSOR: 100.0 if plant else 0.0, 'anxiety': start},
                  after={'anxiety': start - (40.0 if relief else 0.0)})

    def _mixed_experience(self, rounds=8):
        for _ in range(rounds):
            self._shelter(plant=True, anxious=True)
            self._shelter(plant=True, anxious=False)
            self._shelter(plant=False, anxious=True)
            self._shelter(plant=False, anxious=False)

    def test_it_finds_the_combination_it_has_no_neuron_for(self):
        self._mixed_experience()
        wanted = self.learner.wanted_combinations()
        self.assertEqual([w['cues'] for w in wanted], [['anxiety', PLANT_SENSOR]])
        self.assertEqual(wanted[0]['motor'], 'act_shelter')
        self.assertGreater(wanted[0]['benefit_together'], 0.2)

    def test_one_cue_being_enough_is_not_a_combination(self):
        """If frightened is all it takes, an ordinary synapse can say so."""
        for _ in range(8):
            self._shelter(plant=True, anxious=True, helps=True)
            self._shelter(plant=False, anxious=True, helps=True)
            self._shelter(plant=True, anxious=False, helps=False)
            self._shelter(plant=False, anxious=False, helps=False)
        self.assertEqual(self.learner.wanted_combinations(), [])
        self.assertGreater(self.b.weights[('anxiety', 'act_shelter')], 0.5)

    def test_a_cue_that_was_merely_always_there_is_credited_with_nothing(self):
        self.b.state['cleanliness'] = 80.0
        self._mixed_experience()
        self.assertNotIn(('cleanliness', 'act_shelter'), self.b.weights)

    def test_the_weight_follows_the_evidence_back_down(self):
        """What was true and stops being true is unlearned - by the same rule,
        on the record, not by decay."""
        for _ in range(8):
            self._shelter(plant=True, anxious=True, helps=True)
            self._shelter(plant=True, anxious=False, helps=False)
        learned = self.b.weights[('anxiety', 'act_shelter')]
        self.assertGreater(learned, 0.5)
        # It does not let go at once. What it learned from striking experiences
        # outweighs a run of uneventful ones for a good while - a belief is
        # sticky - but enough of them and it goes.
        for _ in range(20):
            self._shelter(plant=True, anxious=True, helps=False)
            self._shelter(plant=True, anxious=False, helps=False)
        self.assertGreater(self.b.weights[('anxiety', 'act_shelter')], 0.5,
                           "one disappointing spell undid it")
        for _ in range(160):
            self._shelter(plant=True, anxious=True, helps=False)
            self._shelter(plant=True, anxious=False, helps=False)
        self.assertLess(abs(self.b.weights[('anxiety', 'act_shelter')]), 0.15)
        notes = [event.detail.get('note', '') for event in
                 self.b.ledger.weight_history(('anxiety', 'act_shelter'), limit=200)]
        self.assertTrue(any('stopped making a difference' in n for n in notes))

    def test_an_action_that_goes_worse_with_a_cue_becomes_an_avoidance(self):
        """An aversion IS an inhibitory synapse."""
        self.b.apply_weight_change(('anxiety', 'act_shelter'), value=0.3,
                                   mechanism='test', create=True)
        for _ in range(10):
            self.clock += 10.0
            trial(self.b, self.learner, moment=self.clock,
                  before={'anxiety': 90.0}, after={'anxiety': 100.0, 'happiness': 20.0})
            self.clock += 10.0
            trial(self.b, self.learner, moment=self.clock,
                  before={'anxiety': 30.0}, after={'anxiety': 30.0})
        self.assertLess(self.b.weights[('anxiety', 'act_shelter')], 0.0)

    def test_once_a_combination_neuron_exists_it_takes_the_credit(self):
        self._mixed_experience()
        name = grow_combination(self.b, [[PLANT_SENSOR, 1], ['anxiety', 1]],
                                motor='act_shelter')
        self.assertGreater(self.b.weights[(name, 'act_shelter')], 0.0,
                           "the evidence it was grown on was not handed over")
        for _ in range(12):
            for plant, anxious in ((True, True), (True, False), (False, True)):
                self.clock += 10.0
                start = 90.0 if anxious else 30.0
                both = plant and anxious
                trial(self.b, self.learner, moment=self.clock,
                      before={PLANT_SENSOR: 100.0 if plant else 0.0,
                              'anxiety': start, name: 100.0 if both else 0.0},
                      after={'anxiety': start - (40.0 if both else 0.0)})
        self.assertGreater(self.b.weights[(name, 'act_shelter')], 0.9)
        for alone in ('anxiety', PLANT_SENSOR):
            self.assertLess(abs(self.b.weights.get((alone, 'act_shelter'), 0.0)), 0.2,
                            f"{alone} alone still takes credit for the combination")

    def test_what_it_has_found_out_is_saved_with_it(self):
        self._mixed_experience()
        restored = ActionDiscovery(self.b, rate=0.0)
        restored.from_dict(self.learner.to_dict())
        self.assertEqual(restored.wanted_combinations(),
                         self.learner.wanted_combinations())
        self.assertEqual(restored.describe('anxiety', 'act_shelter'),
                         self.learner.describe('anxiety', 'act_shelter'))

    def test_it_can_say_what_it_found_in_words(self):
        self._mixed_experience()
        said = self.learner.describe(PLANT_SENSOR, 'act_shelter')
        self.assertIn('Approaching plant', said)
        self.assertIn('with', said)
        self.assertIn('not tried', self.learner.describe('hunger', 'act_play'))

    def test_curiosity_and_distress_both_make_it_try_more(self):
        learner = ActionDiscovery(self.b, rate=0.05)
        calm = {'curiosity': 50.0, 'anxiety': 20.0, 'hunger': 20.0, 'sleepiness': 20.0}
        base = learner.explore_probability(calm)
        self.assertGreater(learner.explore_probability(dict(calm, curiosity=95.0)), base)
        self.assertLess(learner.explore_probability(dict(calm, curiosity=5.0)), base)
        self.assertGreater(learner.explore_probability(dict(calm, anxiety=95.0)), base)

    def test_it_loses_interest_in_what_it_already_knows(self):
        state = dict(self.b.state, anxiety=30.0)
        state[PLANT_SENSOR] = 0.0
        fresh = self.learner._unfamiliarity('act_shelter', state)
        self._shelter(plant=False, anxious=False, times=40)
        self.assertLess(self.learner._unfamiliarity('act_shelter', state), fresh)
        # ...but a moment it has not tried the action in is new again.
        frightened = dict(state, anxiety=95.0)
        self.assertEqual(self.learner._unfamiliarity('act_shelter', frightened), 1.0)
        self.assertGreaterEqual(PRESENT, 50.0)


# ===========================================================================
# The tank: sheltering is a thing the body does, with a real consequence
# ===========================================================================
def still_water(**overrides):
    tank = quiet(HeadlessSimulation, TrainingConfig(
        seed=7, learning_enabled=False, neurogenesis_enabled=False, plants=0,
        food_spawn_chance=0, startle_chance=0, poop_spawn_chance=0, **overrides))
    return tank


class ShelterIsEarnedInTheTank(unittest.TestCase):
    """Ported from the CANARY branch's shelter affordance tests."""

    def test_relief_needs_the_choice_the_approach_and_the_plant(self):
        tank = still_water()
        tank.plants = [{'x': 0.70, 'y': 0.50}]
        tank.squid.anxiety = 90.0
        start = (tank.squid.x, tank.squid.y)

        tank._act_on_neural_decision("exploring")
        tank.squid.update()
        self.assertEqual(tank.stats['sheltered_ticks'], 0)

        tank.squid.x, tank.squid.y = start
        tank.squid.anxiety = 90.0
        tank._act_on_neural_decision("approaching_plant")      # one step closer
        self.assertEqual(tank.stats['shelter_approaches'], 1)
        self.assertEqual(tank.stats['sheltered_ticks'], 0)
        tank.squid.update()
        self.assertGreater(tank.squid.anxiety, 89.5)      # no relief on the way

        for _ in range(4):
            tank._act_on_neural_decision("approaching_plant")
        self.assertGreater(tank.stats['sheltered_ticks'], 0)
        before = tank.squid.anxiety
        tank.squid.update()
        self.assertLess(tank.squid.anxiety, before)

    def test_no_plant_or_one_out_of_sight_never_gives_relief(self):
        for plants in ([], [{'x': 0.99, 'y': 0.99}]):
            tank = still_water()
            tank.plants = plants
            tank.squid.anxiety = 90.0
            for _ in range(10):
                tank._act_on_neural_decision("approaching_plant")
                tank.squid.update()
            self.assertEqual(tank.stats['sheltered_ticks'], 0)
            self.assertGreaterEqual(tank.squid.anxiety, 89.0)

    def test_a_plant_nearby_is_not_free_calm(self):
        tank = still_water()
        tank.plants = [{'x': 0.51, 'y': 0.50}]
        tank.squid.anxiety = 90.0
        for tick in range(25):
            tank.tick = tick
            quiet(tank._simulation_step)
        self.assertEqual(tank.stats['sheltered_ticks'], 0)
        self.assertGreater(tank.squid.anxiety, 85.0)

    def test_hiding_gets_it_out_of_a_fright(self):
        tank = still_water()
        tank.plants = [{'x': 0.52, 'y': 0.50}]
        tank.squid.startle()
        tank._act_on_neural_decision("approaching_plant")
        self.assertFalse(tank.squid.is_startled)
        self.assertEqual(tank.stats['hidden_startles'], 1)

    def test_wanting_food_with_none_in_sight_sends_it_looking(self):
        tank = still_water()
        start = (tank.squid.x, tank.squid.y)
        tank._act_on_neural_decision("eating")
        self.assertNotEqual((tank.squid.x, tank.squid.y), start)
        self.assertEqual(tank.stats['food_eaten'], 0)

    def test_the_same_world_seed_is_the_same_world_whatever_the_squid_does(self):
        """Without this, "this squid did better than that one" means nothing."""
        def world(blank):
            tank = quiet(HeadlessSimulation, TrainingConfig(
                seed=3, world_seed=77, blank=blank, learning_enabled=False))
            events = []
            for tick in range(400):
                tank.tick = tick
                food, startles = len(tank.food_items), tank.stats['startles']
                tank.squid.update()
                tank._update_environment()
                events.append((len(tank.food_items) - food,
                               tank.stats['startles'] - startles))
                tank.food_items.clear()
            return tank.plants, events
        self.assertEqual(world(blank=False), world(blank=True))


# ===========================================================================
# THE LIFE
# ===========================================================================
LIFE = 12000          # ticks the test squid lives
TRIAL = 2500          # ticks of each frozen trial
WORLDS = (9001, 9002, 9003)


def raise_squid(seed=1, ticks=LIFE, **config):
    tank = lifetime.new_tank(seed, **config)
    for tick in range(ticks):
        tank.tick = tick
        quiet(tank._simulation_step)
    return tank


class ASquidLearnsToHideWhenFrightened(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tank = raise_squid()
        cls.brain = cls.tank.brain
        cls.document = quiet(cls.brain.export_brain)
        cls.newborn = lifetime.score(None, WORLDS, TRIAL)
        cls.grown_up = lifetime.score(cls.document, WORLDS, TRIAL)

    # -- what it grew, and why --------------------------------------------
    def test_it_grew_a_sense_for_plants_and_a_neuron_for_frightened_by_a_plant(self):
        grown = set(self.brain.enhanced_neurogenesis.functional_neurons)
        self.assertEqual(grown, {PLANT_SENSOR, SHELTER_NEURON},
                         "it grew something other than what it had reason to")

    def test_the_new_neuron_can_say_why_it_exists(self):
        origin = self.brain.ledger.origins[SHELTER_NEURON]
        self.assertEqual(origin.evidence['found_by'], 'its own trials')
        self.assertEqual(origin.evidence['motor'], 'act_shelter')
        self.assertIn('approaching plant pays off', origin.deficit_summary)
        self.assertIn('because', self.brain.explain_neuron(SHELTER_NEURON).lower())

    def test_the_synapse_it_learned_can_say_what_taught_it(self):
        edge = (SHELTER_NEURON, 'act_shelter')
        self.assertGreater(self.brain.weights[edge], 0.76,
                           "the path is too weak to move it by itself")
        events = self.brain.ledger.weight_history(edge, limit=50)
        self.assertTrue(events)
        self.assertTrue(all(e.mechanism == 'causal_motor_discovery' for e in events))
        self.assertIn('benefit_contrast', events[-1].detail)

    def test_neither_cue_alone_was_left_holding_the_credit(self):
        for alone in ('anxiety', PLANT_SENSOR, 'can_see_food'):
            self.assertLess(abs(self.brain.weights.get((alone, 'act_shelter'), 0.0)),
                            0.3, f"{alone} alone drives sheltering")

    # -- what it does about it, frozen, in worlds it never saw -------------
    def test_a_newborn_never_shelters(self):
        self.assertEqual(self.newborn['sheltered_ticks'], 0)

    def test_it_shelters_and_is_less_anxious_for_it(self):
        self.assertGreater(self.grown_up['sheltered_ticks'], 10)
        self.assertLess(self.grown_up['anxiety'], self.newborn['anxiety'] - 8.0,
                        f"anxiety {self.newborn['anxiety']:.1f} at birth, "
                        f"{self.grown_up['anxiety']:.1f} after a life of learning")

    def test_learning_cost_it_nothing_it_was_born_able_to_do(self):
        """The regression this whole change exists to end. On the engine it
        replaces, the same test gave hunger 34 -> 77 and health 96 -> 63."""
        self.assertGreaterEqual(self.grown_up['food_eaten'],
                                self.newborn['food_eaten'] - 1.0)
        self.assertLessEqual(self.grown_up['hunger'], self.newborn['hunger'] + 5.0)
        self.assertGreaterEqual(self.grown_up['health'], self.newborn['health'] - 3.0)

    def test_its_instincts_are_as_it_was_born_with_them(self):
        newborn = brain()
        for source, target, _w in INNATE_ACTION_WIRING:
            self.assertEqual(self.brain.weights.get((source, target)),
                             newborn.weights.get((source, target)),
                             f"{source} -> {target} drifted")

    # -- and the proof that it is the grown structure doing it -------------
    def test_cut_the_one_learned_synapse_and_the_ability_is_gone(self):
        lesioned = dict(self.document)
        lesioned['connections'] = [
            c for c in self.document['connections']
            if not (c['source'] == SHELTER_NEURON and c['target'] == 'act_shelter')]
        result = lifetime.score(lesioned, WORLDS, TRIAL)
        self.assertEqual(result['sheltered_ticks'], 0)
        self.assertGreater(result['anxiety'], self.grown_up['anxiety'] + 5.0)

    def test_a_frozen_trial_changes_nothing_about_the_brain(self):
        """lifetime.frozen_trial raises if it does; this is that guard firing."""
        tank = lifetime.new_tank(5, learning_enabled=False)
        tank.brain.apply_weight_change(('hunger', 'happiness'), value=0.5,
                                       mechanism='test', create=True)
        self.assertIsNotNone(lifetime.frozen_trial(self.document, 9001, 200))


class TheControls(unittest.TestCase):
    """Each removes one thing the result depends on, and the result goes."""

    def test_in_a_tank_with_no_plants_there_is_nothing_to_learn(self):
        tank = raise_squid(ticks=6000, plants=0)
        self.assertEqual(set(tank.brain.enhanced_neurogenesis.functional_neurons), set())
        self.assertFalse(any(e[1] == 'act_shelter' and w > 0.3
                             for e, w in tank.brain.weights.items()
                             if not e[0].startswith('act_')))

    def test_trying_things_without_learning_from_them_teaches_nothing(self):
        """The placebo: it explores exactly as much, and nothing is filed."""
        tank = raise_squid(ticks=6000, action_discovery_teaching=False)
        discovery = tank.brain.action_discovery
        self.assertGreater(discovery.executed_probes, 20)
        self.assertEqual(discovery.connections_taught, 0)
        self.assertNotIn(SHELTER_NEURON, tank.brain.positions)
        self.assertEqual([e for e in tank.brain.weights
                          if e[1] in ('act_shelter', 'act_rest', 'act_play')
                          and e[0] in (PLANT_SENSOR, 'anxiety', 'sleepiness')], [])

    def test_without_exploration_an_unwired_action_is_never_tried(self):
        tank = raise_squid(ticks=4000, action_discovery_rate=0.0)
        self.assertEqual(tank.stats['actions_selected'].get('approaching_plant', 0), 0)
        self.assertNotIn(SHELTER_NEURON, tank.brain.positions)



# ===========================================================================
# Its own model of the world - which nothing checks
# ===========================================================================
def see_squid(b, seen=True):
    quiet(b.perceive, 'squid_in_view', 100.0 if seen else 0.0)
    quiet(b.propagate)


class TheSquidBelievesWhatItsOwnExperienceSuggests(unittest.TestCase):
    """There is no truth anywhere in the squid for a belief to be checked
    against. These tests supply a coincidence and check that the squid makes
    of it exactly what an animal with only its own experience would."""

    def setUp(self):
        self.b = brain(neurogenesis_enabled=True)
        self.ledger = self.b.causal_learning
        self.memories = []
        memory = type('M', (), {'add_long_term_memory':
                                lambda _s, category, key, value:
                                self.memories.append((category, key, value))})()
        self.b.tamagotchi_logic = type('G', (), {})()
        self.b.tamagotchi_logic.squid = type('S', (), {'memory_manager': memory})()
        see_squid(self.b)                       # it grows can_see_squid
        self.clock = 100.0

    def _act(self, action, squid_before, squid_after, **after):
        self.clock += 20.0
        state = dict(self.b.state, can_see_squid=100.0 if squid_before else 0.0)
        self.ledger.on_action(action, state, now=self.clock)
        later = dict(state, can_see_squid=100.0 if squid_after else 0.0, **after)
        self.ledger.on_tick(later, now=self.clock + 7.0)

    def test_one_coincidence_is_a_belief(self):
        """It inked; the other squid, which was going home anyway, left."""
        for _ in range(6):                                  # an ordinary life:
            self._act('exploring', True, True)              # squid stay in view
        self.assertEqual(self.ledger.beliefs(), [])
        self._act('inking', True, False)                    # ...and then this
        beliefs = self.ledger.beliefs()
        self.assertEqual(len(beliefs), 1)
        belief = beliefs[0]
        self.assertEqual(belief['statement'], 'inking makes squid go out of sight')
        self.assertEqual(belief['occasions'], 1)
        self.assertGreater(belief['confidence'], 0.0)

    def test_it_thinks_it_and_remembers_it_as_its_own_belief(self):
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        thought = self.b.social_thoughts[-1][1]
        self.assertIn('I think inking makes squid go out of sight', thought)
        self.assertIn('once', thought)
        category, key, value = [m for m in self.memories if m[0] == 'belief'][-1]
        self.assertEqual((category, key), ('belief', 'belief:inking:can_see_squid'))
        self.assertIn('Came to believe', value['summary'])
        # Thought and remembered once, not every time it is confirmed.
        self._act('inking', True, False)
        self.assertEqual([m[1] for m in self.memories if m[0] == 'belief'],
                         ['belief:inking:can_see_squid'])

    def test_nothing_marks_it_true_or_false_only_how_it_came_to_think_so(self):
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        item = [i for i in self.ledger.knowledge_items() if i.kind == 'belief'][0]
        self.assertTrue(item.statement.startswith('It believes that'))
        self.assertIn('one occasion', item.experience)
        self.assertIn('cannot know', item.reason)
        for word in ('true', 'false', 'correct', 'wrong', 'actually'):
            self.assertNotIn(word, item.describe().lower())

    def test_it_is_only_as_lasting_as_its_own_later_experience(self):
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        for _ in range(8):                      # it inks, and they stay
            self._act('inking', True, True)
        self.assertEqual(self.ledger.beliefs(), [])

    def test_a_squid_that_never_tests_it_again_goes_on_believing_it(self):
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        for _ in range(40):
            self._act('exploring', True, True)
        self.assertEqual([b['statement'] for b in self.ledger.beliefs()],
                         ['inking makes squid go out of sight'])

    def test_what_its_own_body_does_is_not_a_belief_about_the_world(self):
        self.clock += 20.0
        state = dict(self.b.state, is_sleeping=0.0)
        self.ledger.on_action('sleeping', state, now=self.clock)
        self.ledger.on_tick(dict(state, is_sleeping=100.0), now=self.clock + 7.0)
        self.assertEqual(self.ledger.beliefs(), [])

    def test_its_beliefs_are_saved_with_it_and_are_not_news_when_it_is_loaded(self):
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        restored = brain()
        restored.causal_learning.from_dict(self.ledger.to_dict())
        self.assertEqual(restored.causal_learning.beliefs(), self.ledger.beliefs())
        self.assertIn(('inking', 'can_see_squid'), restored.causal_learning._held)

    def test_and_it_acts_on_it(self):
        """Relief that followed inking at a squid makes it ink at squid - the
        behavioural half of the same belief, through an ordinary synapse."""
        learner = ActionDiscovery(self.b, rate=0.0)
        self.b.action_discovery = learner
        clock = 500.0
        for _ in range(3):                       # inked with nobody about: nothing
            clock += 20.0
            trial(self.b, learner, action='inking', moment=clock,
                  before={'can_see_squid': 0.0, 'anxiety': 80.0},
                  after={'anxiety': 80.0})
        clock += 20.0                            # inked at a squid, ONCE, and
        trial(self.b, learner, action='inking', moment=clock,      # felt much better
              before={'can_see_squid': 100.0, 'anxiety': 90.0},
              after={'anxiety': 40.0})
        self.assertGreater(self.b.weights.get(('can_see_squid', 'act_ink'), 0.0), 0.3)
        self.assertIn('Inking works better with can see squid',
                      learner.describe('can_see_squid', 'act_ink'))

    # -- the whole story: believe it, act on it, find out, remember ----------
    def _wary(self):
        """A squid that minds the sight of other squid (as a timid one is born,
        and as any squid becomes after bad encounters)."""
        self.b.apply_weight_change(('can_see_squid', 'anxiety'), value=0.5,
                                   mechanism='test', create=True)
        self.b.apply_weight_change(('can_see_squid', 'act_flee'), value=0.6,
                                   mechanism='test', create=True)
        for edge in (('can_see_squid', 'act_play'), ('can_see_squid', 'curiosity')):
            self.b.remove_weight(edge)
        self.learner = ActionDiscovery(self.b, rate=0.0)
        self.b.action_discovery = self.learner

    def _inks_on_sight(self):
        state = settle(self.b, {'can_see_squid': 100.0, 'anxiety': 40.0,
                                'is_startled': 0.0, 'threat_level': 0.0}, ticks=12)
        from src.brain_constants import ACTION_THRESHOLDS
        return state['act_ink'] >= ACTION_THRESHOLDS['act_ink']

    def test_believing_ink_drives_squid_off_it_inks_the_moment_one_appears(self):
        self._wary()
        self.assertFalse(self._inks_on_sight())            # not before
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)                   # the coincidence
        self._act('inking', True, False)                   # ...and again
        for _ in range(4):
            self.learner.follow_beliefs()
        self.assertGreater(self.b.weights[('can_see_squid', 'act_ink')], 0.8)
        self.assertTrue(self._inks_on_sight())
        said = self.b.explain_weight(('can_see_squid', 'act_ink'))
        self.assertIn('believes', said)

    def test_a_squid_that_likes_other_squid_does_not_ink_at_them_for_believing_it(self):
        learner = ActionDiscovery(self.b, rate=0.0)        # adventurous: drawn to squid
        self.b.action_discovery = learner
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        self._act('inking', True, False)
        learner.follow_beliefs()
        self.assertNotIn(('can_see_squid', 'act_ink'), self.b.weights)

    def test_and_when_the_squid_does_not_leave_it_finds_out_it_was_wrong(self):
        """It inks as soon as another squid appears - and the squid stays."""
        self._wary()
        for _ in range(6):
            self._act('exploring', True, True)
        self._act('inking', True, False)
        self._act('inking', True, False)
        for _ in range(4):
            self.learner.follow_beliefs()
        self.assertTrue(self._inks_on_sight())

        for _ in range(8):                                 # it inks; they stay
            self._act('inking', True, True)
            self.learner.follow_beliefs()
        self.assertEqual(self.ledger.beliefs(), [])
        for _ in range(8):
            self.learner.follow_beliefs()
        self.assertLess(self.b.weights.get(('can_see_squid', 'act_ink'), 0.0), 0.1)
        self.assertFalse(self._inks_on_sight())

        # It knows it was wrong, says so, and remembers it.
        self.assertIn('I used to think inking makes squid go out of sight',
                      ' '.join(text for _at, text in self.b.social_thoughts))
        revised = [m for m in self.memories if m[1].startswith('revised:')]
        self.assertEqual(len(revised), 1)
        self.assertTrue(revised[0][2]['changed_mind'])
        self.assertIn('Stopped believing', revised[0][2]['summary'])
        item = [i for i in self.ledger.knowledge_items() if i.kind == 'revised'][0]
        self.assertIn('It used to believe that inking makes squid go out of sight',
                      item.statement)
        self.assertIn('found out', item.reason)
        notes = [e.detail.get('note', '') for e in
                 self.b.ledger.weight_history(('can_see_squid', 'act_ink'), limit=100)]
        self.assertTrue(any('no longer believes' in n for n in notes))

    def test_giving_up_a_habit_that_stopped_paying_is_remembered_too(self):
        learner = ActionDiscovery(self.b, rate=0.0)
        self.b.action_discovery = learner
        clock = 2000.0

        def shelter(anxious, helps):
            nonlocal clock
            clock += 20.0
            start = 90.0 if anxious else 30.0
            trial(self.b, learner, moment=clock, before={'anxiety': start},
                  after={'anxiety': start - (40.0 if helps else 0.0)})

        for _ in range(8):
            shelter(True, True)
            shelter(False, False)
        self.assertIn(('anxiety', 'act_shelter'), learner.habits)
        for _ in range(200):
            shelter(True, False)
            shelter(False, False)
        self.assertNotIn(('anxiety', 'act_shelter'), learner.habits)
        thoughts = ' '.join(text for _at, text in self.b.social_thoughts)
        self.assertIn('I have found that approaching plant helps when anxiety', thoughts)
        self.assertIn('I used to think approaching plant helped when anxiety', thoughts)
        keys = [m[1] for m in self.memories]
        self.assertTrue(any(k.startswith('learned:anxiety:act_shelter') for k in keys))
        self.assertTrue(any(k.startswith('unlearned:anxiety:act_shelter') for k in keys))

    def test_a_mild_outcome_has_to_be_repeated_a_striking_one_does_not(self):
        learner = ActionDiscovery(self.b, rate=0.0)
        self.b.action_discovery = learner
        clock = 900.0
        for _ in range(3):
            clock += 20.0
            trial(self.b, learner, action='inking', moment=clock,
                  before={'can_see_squid': 0.0, 'anxiety': 80.0}, after={'anxiety': 80.0})
        clock += 20.0
        trial(self.b, learner, action='inking', moment=clock,
              before={'can_see_squid': 100.0, 'anxiety': 80.0}, after={'anxiety': 76.0})
        self.assertNotIn(('can_see_squid', 'act_ink'), self.b.weights)


if __name__ == '__main__':
    unittest.main()


# ===========================================================================
# The game loop's side of it
# ===========================================================================
class TheGameCreditsTheSquidsOwnActions(unittest.TestCase):
    """The game spreads a decision over several ticks and systems; these are
    the two calls it makes, and the rule for what counts as a trial."""

    def setUp(self):
        self.b = brain(neurogenesis_enabled=False, action_discovery_rate=1.0)
        self.learner = self.b.action_discovery

    def test_which_learned_action_is_under_way(self):
        from src.action_discovery import behaviour_under_way
        self.assertEqual(behaviour_under_way('seek_plant', False, False),
                         'approaching_plant')
        self.assertEqual(behaviour_under_way('approach_rock', False, False), 'playing')
        self.assertIsNone(behaviour_under_way('seek_food', False, False))
        self.assertIsNone(behaviour_under_way(None, False, True))

    def test_collapsing_is_never_filed_as_a_trial_of_resting(self):
        """Both end in sleep. Only one of them is something the squid did."""
        from src.action_discovery import behaviour_under_way
        self.assertEqual(behaviour_under_way(None, True, True), 'sleeping')
        self.assertIsNone(behaviour_under_way(None, True, False))

    def test_a_spontaneous_urge_is_a_spike_the_network_then_decides_about(self):
        state = self.b.state
        for name in ('act_flee', 'act_eat', 'act_collapse'):
            state[name] = 0.0
        urge = self.learner.tick(state)
        self.assertIn(urge, ('act_rest', 'act_shelter', 'act_play'))
        self.assertEqual(state[urge], 96.0)
        self.assertEqual(self.learner.urge, urge)
        self.assertEqual(self.learner.executed_probes, 0)      # nothing done yet

    def test_asleep_or_away_it_tries_nothing(self):
        self.assertIsNone(self.learner.tick(self.b.state, asleep=True))
        self.assertEqual(self.learner.probes, 0)

    def test_acting_on_the_urge_opens_one_trial_however_long_it_lasts(self):
        from src.brain_constants import ACTION_BEHAVIOURS
        for name in ('act_flee', 'act_eat', 'act_collapse'):
            self.b.state[name] = 0.0
        urge = self.learner.tick(self.b.state)
        behaviour = ACTION_BEHAVIOURS[urge]
        first = self.learner.acted(behaviour, self.b.state)
        self.assertIsNotNone(first)
        self.assertIn(first, self.learner.pending)
        self.assertEqual(self.learner.executed_probes, 1)
        self.assertIsNone(self.learner.acted(behaviour, self.b.state))   # same bout
        self.assertEqual(len(self.learner.pending), 1)
        self.assertIsNone(self.learner.urge)

    def test_the_game_names_going_to_a_plant_and_hiding_in_it_as_one_action(self):
        from src.tamagotchi_logic import TamagotchiLogic
        normalise = TamagotchiLogic._normalize_action_name
        for status in ("seeking comfort in plant", "hiding behind plant",
                       "seeking_plant"):
            self.assertEqual(normalise(None, status), 'approaching_plant')

    def test_the_game_files_a_shelter_drive_as_a_trial(self):
        from types import SimpleNamespace
        from src.tamagotchi_logic import TamagotchiLogic
        squid = SimpleNamespace(is_sleeping=False,
                                get_neural_drive=lambda: {'action': 'seek_plant'})
        game = SimpleNamespace(squid=squid)
        self.assertTrue(TamagotchiLogic._note_learned_action(game, self.b))
        self.assertEqual(self.b.causal_learning.current_action, 'approaching_plant')
        self.assertEqual(len(self.learner.pending), 1)
        squid.get_neural_drive = lambda: {'action': 'seek_food'}
        self.assertFalse(TamagotchiLogic._note_learned_action(game, self.b))

    def test_the_game_calms_a_hiding_squid_enough_for_it_to_notice(self):
        from src.tamagotchi_logic import PLANT_CALM_PER_TICK
        window = self.b.causal_learning.config.outcome_window
        relief = PLANT_CALM_PER_TICK * window / 2          # half the window, arriving
        self.assertGreater(1.0 * relief / 100.0, 2 * self.learner.minimum_benefit)
