"""
Controls for the cup-and-food experiment.

The experiment's headline result is a NULL - the squid does not learn which cup
the food is under - and a null result is worth nothing unless the instrument
that produced it can be shown to work. So most of what is below is aimed at the
ways a null could be an artefact:

  * the cups might not be properly randomised;
  * the answer might be leaking into the squid through something nobody meant
    to add;
  * `can_see_food` might not mean what it says;
  * the apparatus might not sit at 1/3 to begin with;
  * a fixed strategy might beat it, in which case a good score proves nothing;
  * the scoring might be too blunt to detect an improvement that is really there;
  * the "frozen" evaluation might not be frozen;
  * the improvement might not correspond to anything actually changing inside.

Each of those is a test. The last group is the one that turns the null into a
finding: the learning arm and the learning-disabled arm score the same, while
the learning arm's provenance ledger shows the network really did change.
"""

import math
import os
import random
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (_REPO_ROOT, os.path.join(_REPO_ROOT, 'headless')):
    if path not in sys.path:
        sys.path.insert(0, path)

from src.brain_neuron_hooks import DEFAULT_INPUT_SENSORS  # noqa: E402
from src.brain_constants import newborn_neurons  # noqa: E402
from src.cup_experiment import (  # noqa: E402
    CUP_IDENTITIES, Comparison, CupExperiment, CupLayout, DriveComparison,
    Perception, Phase, TrialRecord, binomial_tail, chance_rate,
    fixed_strategy_scores, omission_bias, permutation_p, persistence_values,
    score_block, two_proportion_p, wilson_interval,
)
from src.vision_worker import SceneObject, SquidVisionState, VisionWorker  # noqa: E402

from cup_experiment_runner import (  # noqa: E402
    CupWorld, TrialSettings, floor_slots, run_paired,
)
from headless_trainer import TrainingConfig  # noqa: E402


#: Short phases, so the suite runs in seconds. The protocol itself is
#: unchanged - every step still happens, in order - and the two settings the
#: result actually depends on are NOT shortened: `hidden_ticks` is the memory
#: demand and `start_clearance` is the control that stops the squid choosing
#: the cup it is already standing on. Shortening either would buy speed by
#: weakening the experiment.
FAST = dict(bait_ticks=60, bait_dwell=6, shuffle_ticks=10,
            choice_ticks=200, outcome_ticks=4)


def fast_settings(**overrides) -> TrialSettings:
    return TrialSettings(**{**FAST, **overrides})


def make_world(seed=0, growth=False, **overrides) -> CupWorld:
    """A world with neurogenesis off unless asked for.

    Growth is part of the architecture and the CLI runs with it on, but a
    grown neuron arrives wired to everything at +/-0.8 and swamps the effect
    these tests are trying to measure. Switching it off isolates plasticity;
    `NoNewStructureTests` covers what happens when it is on.
    """
    config = TrainingConfig(seed=seed)
    config.neurogenesis_enabled = bool(growth)
    return CupWorld(seed=seed, settings=fast_settings(**overrides),
                    config=config)


class RecordingState(dict):
    """A state dict that remembers who wrote to it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.writes = []

    def __setitem__(self, key, value):
        self.writes.append(key)
        super().__setitem__(key, value)

    def update(self, *args, **kwargs):
        for key in dict(*args, **kwargs):
            self.writes.append(key)
        super().update(*args, **kwargs)


# ===========================================================================
# 1. The cups are properly randomised
# ===========================================================================
class RandomisationTests(unittest.TestCase):

    def setUp(self):
        self.layout = CupLayout(floor_slots(), CUP_IDENTITIES,
                                random.Random(11))

    def test_three_cups_give_a_one_in_three_chance(self):
        self.assertEqual(self.layout.cups, 3)
        self.assertAlmostEqual(chance_rate(self.layout.cups), 1 / 3)

    def test_every_arrangement_of_the_cups_occurs(self):
        seen = set()
        for _ in range(600):
            seen.add(tuple(sorted(self.layout.shuffle().items())))
        self.assertEqual(len(seen), math.factorial(3),
                         "the shuffle does not reach every arrangement")

    def test_each_cup_lands_in_each_slot_about_equally_often(self):
        counts = {(name, slot): 0 for name in CUP_IDENTITIES for slot in range(3)}
        trials = 3000
        for _ in range(trials):
            for name, slot in self.layout.shuffle().items():
                counts[(name, slot)] += 1
        expected = trials / 3
        for key, count in counts.items():
            self.assertLess(abs(count - expected), 4 * math.sqrt(expected),
                            f"{key} came up {count} times, expected ~{expected:.0f}")

    def test_the_baited_cup_is_drawn_uniformly(self):
        world = make_world(seed=2)
        counts = {name: 0 for name in CUP_IDENTITIES}
        slots = {slot: 0 for slot in range(3)}
        for _ in range(900):
            record = world.experiment.begin_trial("probe")
            world.experiment.shuffle()
            counts[record.truth_baited_identity] += 1
            slots[record.truth_baited_slot] += 1
            world.experiment.current = None
        for tally in (counts, slots):
            for key, count in tally.items():
                self.assertLess(abs(count - 300), 4 * math.sqrt(300),
                                f"{key}: {count} of 900")


# ===========================================================================
# 2. The answer never reaches the squid
# ===========================================================================
class NoLeakTests(unittest.TestCase):
    """The ghost marker is the experimenter's. Nothing the squid reads knows."""

    def test_the_experiment_never_writes_to_brain_state(self):
        world = make_world(seed=3)
        world.brain.state = RecordingState(world.brain.state)
        experiment = world.experiment

        experiment.begin_trial("probe")
        experiment.shuffle()
        experiment.hide()
        experiment.open_choice()
        experiment.observe((100.0, 100.0), "exploring")
        experiment.force_choice(0)
        experiment.resolve(ate=False)

        self.assertEqual(world.brain.state.writes, [],
                         "CupExperiment wrote into the squid's brain state: "
                         f"{world.brain.state.writes}")

    def test_freezing_touches_only_the_growth_flag(self):
        world = make_world(seed=3)
        world.brain.state = RecordingState(world.brain.state)
        world.experiment.set_learning_frozen(True)
        world.experiment.set_learning_frozen(False)
        self.assertEqual(set(world.brain.state.writes), {'neurogenesis_active'})

    def test_where_the_food_is_hidden_changes_nothing_the_brain_sees(self):
        """The decisive one: same trial, different answer, identical inputs.

        Two worlds seeded identically are stepped through an identical bait,
        shuffle and hide, differing ONLY in which cup the food ends up under.
        If any channel carried the answer - a sensor, a leftover scene object,
        a drive target - the two brain states would diverge. They must not.
        """
        streams = []
        for baited_slot in (0, 2):
            # `decision_engine.select_action` adds its tie-breaking jitter from
            # the global `random` module, so the two streams have to start from
            # the same global seed as well as the same world seed - otherwise
            # this compares two different coin-flip sequences and fails for a
            # reason that has nothing to do with leakage.
            random.seed(20260915)
            world = make_world(seed=5)
            world.food_items = []
            world.experiment.begin_trial("probe")
            world.experiment.hide()
            # The experimenter knows. Nothing else is told.
            world.experiment.current.truth_baited_slot = baited_slot
            frames = []
            for _ in range(40):
                frames.append({k: round(float(v), 9)
                               for k, v in world.step(learn=False).items()
                               if isinstance(v, (int, float))})
            streams.append(frames)

        self.assertEqual(streams[0], streams[1],
                         "the brain state depended on where the food was hidden")

    def test_no_food_object_exists_while_the_food_is_hidden(self):
        world = make_world(seed=6)
        record = world.experiment.begin_trial("probe")
        world.food_items = [world.layout.position_of_slot(record.truth_baited_slot)]
        world.step(learn=False)
        world.food_items = []
        world.experiment.hide()
        for _ in range(20):
            state = world.step(learn=False)
            self.assertEqual(world.food_items, [])
            self.assertEqual(state['can_see_food'], 0.0)

    def test_recorded_trials_keep_truth_and_perception_apart(self):
        """Every experimenter-only field is named `truth_*` and nothing the
        squid perceived is stored beside it."""
        record = TrialRecord(index=1)
        truth = {f for f in vars(record) if f.startswith('truth_')}
        self.assertTrue(truth)
        perceived = set(vars(Perception(phase='hidden', t=0.0)))
        self.assertFalse(truth & perceived)
        for field in perceived:
            self.assertNotIn('cup', field)
            self.assertNotIn('slot', field)
            self.assertNotIn('bait', field)


# ===========================================================================
# 3. can_see_food keeps its meaning
# ===========================================================================
class VisionTests(unittest.TestCase):
    """100 when the food is there to be seen, 0 when it genuinely is not."""

    def _look(self, angle, food):
        world = make_world(seed=8)
        world.body.current_view_angle = angle
        return world.body.look(food)

    def test_visible_food_reads_one_hundred(self):
        world = make_world(seed=8)
        food = world.layout.position_of_slot(1)
        cx, cy = world.body.centre
        world.body.current_view_angle = math.atan2(
            food[1] + 32 - cy, food[0] + 32 - cx)
        world.food_items = [food]
        state = world.step(learn=False)
        self.assertTrue(world.body.look([food]).can_see_food)
        self.assertEqual(state['can_see_food'], 100.0)

    def test_hidden_food_reads_zero(self):
        world = make_world(seed=8)
        food = world.layout.position_of_slot(1)
        cx, cy = world.body.centre
        world.body.current_view_angle = math.atan2(
            food[1] + 32 - cy, food[0] + 32 - cx)
        world.food_items = []          # under a cup: not among visible objects
        state = world.step(learn=False)
        self.assertEqual(state['can_see_food'], 0.0)

    def test_food_outside_the_cone_is_not_seen(self):
        """Occlusion is not the only way to stop seeing something, and the
        sensor already handles the other way. Nothing here is special-cased."""
        world = make_world(seed=8)
        food = world.layout.position_of_slot(1)
        cx, cy = world.body.centre
        towards = math.atan2(food[1] + 32 - cy, food[0] + 32 - cx)
        self.assertTrue(self._look(towards, [food]).can_see_food)
        self.assertFalse(self._look(towards + math.pi, [food]).can_see_food)

    def test_the_sensor_is_the_shipping_vision_worker(self):
        """`CupSquidBody.look` calls VisionWorker's own method, unbound.

        If someone replaces it with a private copy of the cone arithmetic this
        fails, because the two would then be free to disagree.
        """
        squid = SquidVisionState(squid_x=100, squid_y=100,
                                 window_width=1280, window_height=900,
                                 current_view_angle=0.0)
        objects = [SceneObject(x=400, y=110, category='food')]
        direct = VisionWorker._calculate_visibility(None, squid, objects)
        self.assertTrue(direct.can_see_food)

        world = make_world(seed=9)
        world.body.squid_x, world.body.squid_y = 100, 100
        world.body.current_view_angle = 0.0
        via_body = world.body.look([(400, 110)])
        self.assertEqual(via_body.can_see_food, direct.can_see_food)


# ===========================================================================
# 4. No new neurons, no new sensors
# ===========================================================================
class NoNewStructureTests(unittest.TestCase):

    #: The names the experiment is forbidden to introduce, and the general
    #: shapes of the same idea.
    FORBIDDEN = (
        'food_accessible', 'food_under_cup', 'cup_left', 'cup_middle',
        'cup_right', 'cup_id', 'correct_cup', 'hidden_food', 'food_location',
        'baited_cup', 'cup_sensor',
    )

    def test_the_sensor_block_is_exactly_the_existing_sensors(self):
        world = make_world(seed=10)
        vision = world.body.look([])
        sensors = world._sensors(vision)
        self.assertEqual(set(sensors), set(DEFAULT_INPUT_SENSORS),
                         "the experiment writes a sensor the game does not have")

    def test_no_forbidden_name_appears_in_the_experiment_code(self):
        sources = [
            os.path.join(_REPO_ROOT, 'src', 'cup_experiment.py'),
            os.path.join(_REPO_ROOT, 'headless', 'cup_experiment_runner.py'),
            os.path.join(_REPO_ROOT, 'src', 'cup_game_ui.py'),
        ]
        for path in sources:
            if not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as handle:
                # Strip the docstrings and comments that DISCUSS the forbidden
                # names; what matters is that none of them is ever a symbol.
                code = "\n".join(line.split('#', 1)[0]
                                 for line in handle.read().splitlines())
            for name in self.FORBIDDEN:
                self.assertNotIn(f"'{name}'", code, f"{path} names {name}")
                self.assertNotIn(f'"{name}"', code, f"{path} names {name}")
                self.assertNotIn(f"{name} =", code, f"{path} defines {name}")

    def test_a_run_without_growth_adds_no_neuron_at_all(self):
        world = make_world(seed=11, growth=False)
        before = world.experiment.neuron_names()
        report = world.run(train=4, evaluate=4, naive=4)
        self.assertEqual(report['neurons_added'], [])
        self.assertEqual(world.experiment.neuron_names(), before)

    def test_every_neuron_the_newborn_had_is_still_there(self):
        world = make_world(seed=12, growth=True)
        world.run(train=4, evaluate=4, naive=4)
        after = world.experiment.neuron_names()
        for name in newborn_neurons():
            self.assertIn(name, after)

    def test_any_neuron_that_appears_was_grown_by_the_squid(self):
        """Growth is allowed - it is part of the architecture - but only
        through neurogenesis, with a birth record. Nothing is installed."""
        world = make_world(seed=13, growth=True)
        report = world.run(train=6, evaluate=4, naive=4)
        origins = set(world.brain.ledger.origins)
        for name in report['neurons_added']:
            self.assertIn(name, origins,
                          f"{name} appeared with no recorded birth")


# ===========================================================================
# 5-6. The apparatus sits at chance, and no fixed rule beats it
# ===========================================================================
class BaselineTests(unittest.TestCase):
    """The no-information arm: the squid is never shown the bait.

    Nothing it does can beat 1 in 3, so this measures what chance looks like in
    this apparatus - the geometry, the body, the wander and all - rather than
    taking 33.3% on faith from the arithmetic of three cups.
    """

    @classmethod
    def setUpClass(cls):
        cls.records = []
        for seed in range(4):
            world = make_world(seed=seed)
            world.experiment.set_learning_frozen(True)
            for _ in range(45):
                cls.records.append(
                    world.run_trial("naive", learn=False, show_bait=False))
        cls.stats = score_block(cls.records, "naive")

    def test_baseline_is_one_in_three(self):
        self.assertGreater(self.stats.committed, 80,
                           "too few played trials to say anything")
        self.assertLessEqual(self.stats.ci_low, 1 / 3)
        self.assertGreaterEqual(self.stats.ci_high, 1 / 3)
        self.assertAlmostEqual(self.stats.rate, 1 / 3, delta=0.09,
                               msg=f"baseline is {self.stats.rate:.1%}, not ~33.3%")

    def test_no_fixed_strategy_beats_chance(self):
        """Always the left cup; always cup B; any of them. All must be ~1/3,
        or a good score could be a habit rather than knowledge."""
        for name, rate in fixed_strategy_scores(self.records).items():
            self.assertAlmostEqual(rate, 1 / 3, delta=0.10,
                                   msg=f"{name} would have scored {rate:.1%}")

    def test_omissions_do_not_depend_on_the_answer(self):
        """Accuracy is scored over played trials, which is only sound if
        whether the squid plays is unrelated to which cup was baited."""
        bias = omission_bias(self.records)
        self.assertLess(bias['spread'], 0.25,
                        f"play rate varies with the answer: {bias}")

    def test_the_squid_saw_no_food_before_choosing_in_this_arm(self):
        """Nothing was visible up to and including the choice.

        After the choice the cup comes off, and on a correct trial the food is
        revealed and eaten - the reveal is step 6 of the protocol and must
        happen, or the squid would never get its reward. What the arm
        guarantees is that nothing was on show while the answer still mattered.
        """
        before_reveal = {Phase.BAIT.value, Phase.SHUFFLE.value,
                         Phase.HIDDEN.value, Phase.CHOICE.value}
        for record in self.records:
            self.assertTrue(
                all(p.can_see_food == 0.0 for p in record.perceptions
                    if p.phase in before_reveal),
                "the no-information arm showed the squid food before it chose")


# ===========================================================================
# 7. The instrument can detect an improvement that is really there
# ===========================================================================
class SensitivityTests(unittest.TestCase):
    """A null result means nothing from a dead instrument.

    These feed the scoring a squid that DOES know the answer and check that it
    says so - so when the real run comes back at chance, that is a fact about
    the squid rather than about the statistics.
    """

    @staticmethod
    def _synthetic(n, accuracy, block="eval", rng=None):
        rng = rng or random.Random(4)
        records = []
        for i in range(n):
            baited = rng.randrange(3)
            correct = rng.random() < accuracy
            chosen = baited if correct else rng.choice(
                [s for s in range(3) if s != baited])
            record = TrialRecord(index=i + 1, block=block)
            record.truth_baited_slot = baited
            record.truth_baited_identity = CUP_IDENTITIES[baited]
            record.truth_slot_of_identity = {
                name: s for s, name in enumerate(CUP_IDENTITIES)}
            record.chosen_slot = chosen
            record.committed = True
            record.correct = (chosen == baited)
            records.append(record)
        return records

    def test_a_squid_that_knows_is_reported_as_above_chance(self):
        stats = score_block(self._synthetic(60, 0.75), "eval")
        self.assertTrue(stats.above_chance)
        self.assertLess(stats.p_above_chance, 0.001)
        self.assertGreater(stats.ci_low, 1 / 3)

    def test_a_squid_that_guesses_is_not(self):
        stats = score_block(self._synthetic(60, 1 / 3), "eval")
        self.assertFalse(stats.above_chance)

    def test_a_real_improvement_between_two_blocks_is_detected(self):
        before = score_block(self._synthetic(60, 1 / 3, rng=random.Random(1)),
                             "control")
        after = score_block(self._synthetic(60, 0.70, rng=random.Random(2)),
                            "eval")
        comparison = Comparison("sensitivity check", after, before)
        self.assertTrue(comparison.significant)
        self.assertGreater(comparison.difference, 0.2)

    def test_two_guessing_blocks_are_not_reported_as_different(self):
        a = score_block(self._synthetic(60, 1 / 3, rng=random.Random(1)), "eval")
        b = score_block(self._synthetic(60, 1 / 3, rng=random.Random(2)), "control")
        self.assertFalse(Comparison("null check", a, b).significant)

    def test_a_real_difference_in_drive_is_detected(self):
        strong = [0.8, 0.75, 0.9, 0.85, 0.7, 0.95, 0.82, 0.78, 0.88, 0.73]
        weak = [0.4, 0.35, 0.45, 0.3, 0.42, 0.38, 0.41, 0.33, 0.44, 0.36]
        self.assertTrue(DriveComparison("check", strong, weak).significant)

    def test_two_identical_drive_samples_are_not(self):
        a = [0.5, 0.45, 0.55, 0.52, 0.48, 0.51, 0.47, 0.53, 0.49, 0.5]
        b = [0.51, 0.46, 0.54, 0.5, 0.49, 0.52, 0.48, 0.5, 0.47, 0.53]
        self.assertFalse(DriveComparison("check", a, b).significant)

    def test_persistence_values_skips_trials_that_have_none(self):
        blank = TrialRecord(index=1)
        self.assertEqual(persistence_values([blank]), [])
        self.assertEqual(permutation_p([], [1.0]), 1.0)

    def test_the_statistics_themselves(self):
        self.assertAlmostEqual(binomial_tail(0, 10, 1 / 3), 1.0)
        self.assertAlmostEqual(binomial_tail(11, 10, 1 / 3),
                               binomial_tail(10, 10, 1 / 3))
        low, high = wilson_interval(5, 15)
        self.assertLess(low, 1 / 3)
        self.assertGreater(high, 1 / 3)
        self.assertEqual(wilson_interval(0, 0), (0.0, 1.0))
        self.assertAlmostEqual(two_proportion_p(30, 60, 30, 60), 1.0, places=6)


# ===========================================================================
# 8. Frozen evaluation really is frozen
# ===========================================================================
class FreezeTests(unittest.TestCase):

    def test_a_frozen_brain_refuses_every_synaptic_write(self):
        world = make_world(seed=20)
        edge = ('can_see_food', 'act_eat')
        world.experiment.set_learning_frozen(True)
        self.assertFalse(world.brain.apply_weight_change(edge, delta=0.1))
        self.assertFalse(world.brain.apply_weight_change(('hunger', 'anxiety'),
                                                         value=0.5, create=True))
        self.assertFalse(world.brain.remove_weight(edge))
        self.assertIn(edge, world.brain.weights)

    def test_freezing_also_stops_structural_growth(self):
        world = make_world(seed=20, growth=True)
        world.experiment.set_learning_frozen(True)
        self.assertFalse(world.brain.state['neurogenesis_active'])
        world.experiment.set_learning_frozen(False)
        self.assertTrue(world.brain.state['neurogenesis_active'])

    def test_nothing_changes_during_the_evaluation_block(self):
        world = make_world(seed=21)
        for _ in range(6):
            world.run_trial("train", learn=True)
        world.experiment.set_learning_frozen(True)
        weights = dict(world.brain.weights)
        changes = int(world.brain.ledger.total_changes)
        neurons = world.experiment.neuron_names()
        for _ in range(6):
            world.run_trial("eval", learn=False)
        self.assertEqual(dict(world.brain.weights), weights,
                         "a weight moved during the frozen evaluation block")
        self.assertEqual(int(world.brain.ledger.total_changes), changes)
        self.assertEqual(world.experiment.neuron_names(), neurons)

    def test_the_runner_reports_whether_the_freeze_held(self):
        world = make_world(seed=22)
        report = world.run(train=4, evaluate=4, naive=0)
        self.assertTrue(report['evaluation_was_frozen'])

    def test_thawing_restores_plasticity(self):
        world = make_world(seed=23)
        world.experiment.set_learning_frozen(True)
        world.experiment.set_learning_frozen(False)
        self.assertTrue(world.brain.apply_weight_change(
            ('can_see_food', 'act_eat'), delta=0.01))


# ===========================================================================
# 9-10. The finding: learning moved the network, but not this behaviour
# ===========================================================================
class LearningArmTests(unittest.TestCase):
    """The comparison the whole design exists to make.

    A squid finishes a trial near the cup it last saw the food at, and the cup
    it then swims to is the nearest one - so BOTH arms score above the
    no-information baseline without knowing anything. The learning-disabled arm
    is that free gift with plasticity switched off. If training taught the
    squid the task, the learning arm would beat it.
    """

    @classmethod
    def setUpClass(cls):
        cls.paired = run_paired(seed=31, naive=24, train=34, evaluate=34,
                                settings=fast_settings(), growth=False)

    def _block(self, arm, name):
        for stats in self.paired[arm]['blocks']:
            if stats.block == name:
                return stats
        raise AssertionError(f"no {name} block in {arm}")

    def test_the_learning_arm_really_did_learn_something(self):
        """Not about cups - about anything. If the network never changed, the
        comparison below would be two identical brains and would prove nothing.
        """
        brain = self.paired['worlds'][0].brain
        self.assertGreater(brain.ledger.total_changes, 0)
        mechanisms = brain.ledger.mechanism_totals()
        self.assertGreater(mechanisms.get('hebbian', 0.0), 0.0,
                           "plasticity committed nothing at all")

    def test_the_control_arm_changed_nothing(self):
        control = self.paired['worlds'][1].brain
        innate_only = {m for m in control.ledger.mechanism_totals()} <= {'innate'}
        self.assertTrue(innate_only,
                        f"the frozen arm still learned: "
                        f"{control.ledger.mechanism_totals()}")

    def test_the_two_arms_started_from_the_same_brain(self):
        """The frozen arm still HAS the brain both arms hatched with.

        Its weights are the innate table and nothing else - a freeze refuses
        every write, so no synapse was added or moved - and the learning arm's
        network is that same brain plus whatever experience built on it.
        """
        learning, control = self.paired['worlds']
        fresh = make_world(seed=31)
        self.assertEqual(sorted(control.brain.weights), sorted(fresh.brain.weights),
                         "the frozen arm's connectivity is not the newborn's")
        self.assertTrue(set(learning.brain.weights) >= set(control.brain.weights),
                        "training lost a synapse the squid was born with")

    def test_the_arms_diverged_in_weights_but_not_in_score(self):
        learning, control = self.paired['worlds']
        moved = sum(1 for edge, weight in learning.brain.weights.items()
                    if abs(weight - control.brain.weights.get(edge, 0.0)) > 1e-6)
        self.assertGreater(moved, 0, "training changed no synapse")

        comparison = Comparison(
            "eval", self._block('learning', 'eval'), self._block('control', 'eval'))
        self.assertFalse(
            comparison.significant,
            "The learning arm beat the frozen control. That would mean the "
            "squid DID learn which cup - a result this architecture is not "
            "expected to produce (see src/cup_experiment.py). Re-run across "
            "seeds before believing it, then update the documented finding.")

    def test_choice_accuracy_is_not_driven_above_chance_by_training(self):
        """Stated as a comparison, not as a distance from 1/3.

        The apparatus gives points away - a squid that ends a trial near the
        right cup scores above chance knowing nothing - so "eval beat 1/3" is
        not evidence of learning and this must not test for it. What would be
        evidence is eval beating the arm with plasticity switched off, and the
        test above covers that. This one guards the weaker claim the finding
        actually rests on: training does not produce competence.
        """
        learning = self._block('learning', 'eval')
        control = self._block('control', 'eval')
        self.assertLessEqual(
            learning.rate - control.rate, 0.25,
            f"the learning arm scored {learning.rate:.1%} against the frozen "
            f"arm's {control.rate:.1%}. That gap is what learning the task "
            "would look like - re-run across seeds before believing it, then "
            "update the documented finding in src/cup_experiment.py.")

    def test_the_drive_measure_is_produced_and_comparable(self):
        """The second measure exists and is being computed for both arms.

        It does NOT assert that the drive rose. One seed of this experiment can
        show a large, highly significant rise in occlusion persistence and the
        next can show nothing; see `docs/cup_experiment.md` for the multi-seed
        replication and what it concluded. Asserting a single seed's effect here
        would be the exact mistake the replication was run to catch.

        What is worth pinning down is that the instrument produces the numbers
        at all, so that `--seeds` can go and check whether they replicate.
        """
        comparison = next(c for c in self.paired['drive_comparisons']
                          if c.label.startswith("eval: "))
        self.assertIsNotNone(comparison.a_mean,
                             "the learning arm produced no persistence values")
        self.assertIsNotNone(comparison.b_mean,
                             "the control arm produced no persistence values")
        self.assertGreaterEqual(comparison.p_value, 0.0)
        self.assertLessEqual(comparison.p_value, 1.0)

    def test_the_control_arm_could_not_have_learned_anything(self):
        """The control arm's guarantee is mechanical, not statistical.

        The tempting assertion here is "the frozen arm's drive did not drift",
        and it would be wrong: the five-seed replication in
        `docs/cup_experiment.md` found the control arm's own drive moving
        significantly in one seed out of five - which is roughly what a 5%
        threshold buys you, and exactly why the documented finding rests on
        pooled trials rather than on any one run.

        What IS guaranteed every time is the mechanism: a frozen arm cannot
        have learned, because every synaptic write was refused. That is what
        this asserts, and it is what makes the arm a control at all.
        """
        control = self.paired['worlds'][1].brain
        mechanisms = set(control.ledger.mechanism_totals())
        self.assertLessEqual(
            mechanisms, {'innate'},
            f"the frozen arm's network changed: {control.ledger.mechanism_totals()}")
        comparison = next(c for c in self.paired['drive_comparisons']
                          if c.label.startswith("control arm: "))
        self.assertGreaterEqual(comparison.p_value, 0.0)

    def test_every_recorded_improvement_has_machinery_behind_it(self):
        """Trials in the learning arm carry the weight deltas and provenance
        events that happened during them; trials in the frozen arm carry none.
        """
        learning, control = self.paired['worlds']
        trained = [r for r in learning.experiment.trials if r.block == "train"]
        frozen = [r for r in control.experiment.trials if r.block == "train"]
        self.assertTrue(any(r.weight_deltas for r in trained),
                        "no trial in the learning arm recorded a weight change")
        self.assertTrue(any(r.plasticity_events for r in trained),
                        "no trial in the learning arm recorded a ledger event")
        for record in frozen:
            self.assertEqual(record.weight_deltas, {})
            self.assertEqual(record.plasticity_events, [])

    def test_the_trials_carry_what_the_squid_perceived(self):
        record = next(r for r in self.paired['worlds'][0].experiment.trials
                      if r.block == "train")
        self.assertTrue(record.perceptions)
        self.assertTrue(any(p.can_see_food == 100.0 for p in record.perceptions),
                        "the squid never saw the bait")
        hidden = [p for p in record.perceptions
                  if p.phase in (Phase.HIDDEN.value, Phase.CHOICE.value)]
        self.assertTrue(hidden)
        self.assertTrue(all(p.can_see_food == 0.0 for p in hidden))


if __name__ == '__main__':
    unittest.main()
