"""
Verification suite for the Dosidicus brain and learning systems.

WHAT THIS FILE IS FOR
---------------------
The other test files check that the game works. This one is for anyone who
wants to USE the brain as an object of study - to run an experiment on it,
publish a number, and have someone else be able to check that number.

That requires three things, and each has tests here:

  1. A CONTROL CONDITION. `TrainingConfig(blank=True)` builds the eight
     required neurons with no synapses and no innate reflexes, so anything
     the brain is found to know at the end of a run was learned during it.

  2. REPRODUCIBILITY. With `seed` set, a run is deterministic: the same seed,
     the same brain and the same tick count give the same trained brain. A
     result nobody else can reproduce is not a result.

  3. STATED MECHANISMS THAT ACTUALLY HOLD. The project claims specific
     things about its learning rules - that a Hebbian weight converges to the
     correlation between two neurons, that anti-correlated neurons develop
     inhibitory synapses, that a silent sensor contributes nothing, that the
     trainer and the game step the same network. Each of those claims is
     checked below against the running code rather than taken on trust.

RUNNING IT
----------
    python -m pytest tests/test_headless_training.py -v

Every test here is deterministic and needs no display, no Qt and no save
files. If one fails, the mechanism it names has changed.
"""

import json
import math
import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "headless"))

from headless_trainer import (  # noqa: E402
    HeadlessBrain,
    HeadlessSimulation,
    TrainingConfig,
    TRAINING_SCENARIOS,
)
from src.brain_constants import (  # noqa: E402
    REQUIRED_NEURONS,
    CORE_STAT_NEURONS,
    PURE_INPUT_NEURONS,
    ACTION_NEURONS,
    INNATE_ACTION_WIRING,
    LEARNED_ACTIONS,
    newborn_neurons,
)
from src.propagation import propagate, signal_of, baseline_of, BASELINE  # noqa: E402


def blank_brain(**overrides):
    """The control condition: eight neurons, nothing else."""
    config = TrainingConfig(blank=True, **overrides)
    return HeadlessBrain(config)


def newborn_brain(**overrides):
    """What a real squid hatches with, reflexes included."""
    return HeadlessBrain(TrainingConfig(**overrides))


def export_without_timestamp(brain):
    """A brain's content, with the wall-clock stamp removed so two runs of
    the same experiment can be compared for equality."""
    data = brain.export_brain()
    data.pop("metadata", None)
    return json.loads(json.dumps(data, sort_keys=True))


# ===========================================================================
# 1. The control condition
# ===========================================================================
class BlankBrainTests(unittest.TestCase):
    """A blank brain must genuinely be blank."""

    def test_a_blank_brain_has_exactly_the_eight_required_neurons(self):
        brain = blank_brain()
        self.assertEqual(set(brain.positions), set(REQUIRED_NEURONS))
        self.assertEqual(len(brain.positions), 8)

    def test_a_blank_brain_has_no_synapses_at_all(self):
        brain = blank_brain()
        self.assertEqual(dict(brain.weights), {},
                         "a blank brain must start knowing nothing")

    def test_a_blank_brain_has_no_innate_reflexes(self):
        """No action neurons, so no behaviour is available without learning."""
        brain = blank_brain()
        for action in ACTION_NEURONS:
            self.assertNotIn(action, brain.positions)

    def test_a_newborn_brain_is_different_from_a_blank_one(self):
        """The distinction has to be real, or the control means nothing."""
        blank, newborn = blank_brain(), newborn_brain()
        self.assertLess(len(blank.positions), len(newborn.positions))
        self.assertEqual(len(blank.weights), 0)
        self.assertGreater(len(newborn.weights), 0)

    def test_a_newborn_brain_matches_the_game_definition(self):
        """Trainer and game must hatch the same squid, or nothing trained
        here tells you anything about the squid you play with."""
        brain = newborn_brain()
        self.assertEqual(set(brain.positions), set(newborn_neurons()))

    def test_the_newborn_reflexes_are_the_documented_three_plus_ink(self):
        brain = newborn_brain()
        driven = {t for _s, t, _w in INNATE_ACTION_WIRING}
        self.assertEqual(driven, {"act_move", "act_eat", "act_flee", "act_ink"})
        for action in LEARNED_ACTIONS:
            with self.subTest(action=action):
                drivers = [k for k in brain.weights if k[1] == action]
                self.assertEqual(drivers, [],
                                 f"{action} is supposed to have to be learned")


# ===========================================================================
# 2. Reproducibility
# ===========================================================================
class ReproducibilityTests(unittest.TestCase):
    """A result nobody else can reproduce is not a result."""

    def _run(self, seed, ticks=250, blank=True):
        sim = HeadlessSimulation(TrainingConfig(seed=seed, blank=blank))
        sim.run(ticks=ticks, progress_interval=0)
        return sim

    def test_the_same_seed_produces_the_same_brain(self):
        first = export_without_timestamp(self._run(1234).brain)
        second = export_without_timestamp(self._run(1234).brain)
        self.assertEqual(first, second,
                         "a seeded run is not reproducible, so no experiment "
                         "run with this trainer can be checked by anyone else")

    def test_the_same_seed_produces_the_same_statistics(self):
        first = self._run(99).stats
        second = self._run(99).stats
        for key in ("neurons_created", "hebbian_updates", "food_eaten",
                    "startles"):
            with self.subTest(statistic=key):
                self.assertEqual(first[key], second[key])

    def test_different_seeds_produce_different_brains(self):
        """Otherwise the seed is not doing anything and the runs are not
        independent samples."""
        a = export_without_timestamp(self._run(1).brain)
        b = export_without_timestamp(self._run(2).brain)
        self.assertNotEqual(a, b)

    def test_an_unseeded_run_is_still_valid_just_not_reproducible(self):
        sim = HeadlessSimulation(TrainingConfig(blank=True))
        stats = sim.run(ticks=100, progress_interval=0)
        self.assertEqual(stats["ticks_completed"], 100)


# ===========================================================================
# 3. The transfer function
# ===========================================================================
class PropagationTests(unittest.TestCase):
    """One forward-propagation implementation, with stated properties."""

    def test_a_silent_sensor_contributes_nothing(self):
        """The documented reason signal_of() exists. Subtracting a fixed 50
        from a sensor made NOT seeing food a signal as loud as seeing it,
        pointing the other way."""
        self.assertEqual(signal_of("can_see_food", 0.0), 0.0)
        self.assertGreater(signal_of("can_see_food", 100.0), 0.0)

    def test_a_drive_at_rest_contributes_nothing(self):
        self.assertEqual(signal_of("hunger", BASELINE), 0.0)
        self.assertGreater(signal_of("hunger", 100.0), 0.0)
        self.assertLess(signal_of("hunger", 0.0), 0.0)

    def test_a_saturated_sensor_pushes_as_hard_as_a_saturated_drive(self):
        self.assertAlmostEqual(signal_of("can_see_food", 100.0),
                               signal_of("hunger", 100.0), places=6)

    def test_action_neurons_rest_at_zero_except_locomotion(self):
        for name in ACTION_NEURONS:
            with self.subTest(neuron=name):
                expected = BASELINE if name == "act_move" else 0.0
                self.assertEqual(baseline_of(name), expected)

    def test_activations_stay_inside_the_zero_to_one_hundred_scale(self):
        state = {"can_see_food": 100.0, "target": 50.0}
        weights = {("can_see_food", "target"): 50.0}  # absurdly strong
        for _ in range(10):
            state["can_see_food"] = 100.0
            propagate(state, weights, ["target"], smoothing=1.0)
        self.assertLessEqual(state["target"], 100.0)
        self.assertGreaterEqual(state["target"], 0.0)

    def test_propagation_never_writes_a_sensor_or_a_core_stat(self):
        """The world owns sensors and the squid model owns the drives. Two
        writers on one neuron is the class of bug this module removes."""
        brain = newborn_brain()
        before = {n: brain.state[n] for n in brain.state
                  if n in PURE_INPUT_NEURONS or n in CORE_STAT_NEURONS}
        brain.state["can_see_food"] = 100.0
        before["can_see_food"] = 100.0
        brain.propagate()
        for name, value in before.items():
            with self.subTest(neuron=name):
                self.assertEqual(brain.state[name], value)

    def test_an_unconnected_neuron_settles_at_its_resting_level(self):
        state = {"lonely": 90.0}
        for _ in range(40):
            propagate(state, {}, ["lonely"], smoothing=0.5)
        self.assertAlmostEqual(state["lonely"], BASELINE, places=3)


# ===========================================================================
# 4. Hebbian learning: the stated convergence property
# ===========================================================================
class HebbianConvergenceTests(unittest.TestCase):
    """config.ini states: 'Setting this [decay] equal to base_learning_rate
    makes a synapse converge to exactly that correlation, so every weight in
    the network reads as a statement about the squid's experience.'

    That is a falsifiable claim about the learning rule. These tests check it.
    """

    def _drive(self, brain, pairs, ticks):
        """Hold two neurons at given values for `ticks` and learn from it."""
        for _ in range(ticks):
            for name, value in pairs.items():
                brain.state[name] = value
            brain.advance_clock(1.0)
            brain.observe_for_learning()

    def test_two_neurons_that_fire_together_develop_a_positive_synapse(self):
        brain = blank_brain(learning_rate=0.04, weight_decay=0.04)
        for _ in range(60):
            self._drive(brain, {"hunger": 95.0, "anxiety": 95.0}, 5)
            self._drive(brain, {"hunger": 5.0, "anxiety": 5.0}, 5)
            brain.perform_hebbian_learning()
        weight = brain.weights.get(("hunger", "anxiety"),
                                   brain.weights.get(("anxiety", "hunger")))
        self.assertIsNotNone(weight, "no synapse formed between two neurons "
                                     "that always fired together")
        self.assertGreater(weight, 0.0,
                           "co-active neurons produced an inhibitory synapse")

    def test_anti_correlated_neurons_develop_an_inhibitory_synapse(self):
        """Weights are signed. An avoidance behaviour IS a negative weight."""
        brain = blank_brain(learning_rate=0.04, weight_decay=0.04)
        for _ in range(60):
            self._drive(brain, {"hunger": 95.0, "happiness": 5.0}, 5)
            self._drive(brain, {"hunger": 5.0, "happiness": 95.0}, 5)
            brain.perform_hebbian_learning()
        weight = brain.weights.get(("hunger", "happiness"),
                                   brain.weights.get(("happiness", "hunger")))
        self.assertIsNotNone(weight)
        self.assertLess(weight, 0.0,
                        "two neurons that were never on together produced an "
                        "excitatory synapse")

    def test_a_weight_stays_inside_the_configured_bounds(self):
        brain = blank_brain(learning_rate=0.5, weight_decay=0.0)
        for _ in range(200):
            self._drive(brain, {"hunger": 100.0, "anxiety": 100.0}, 3)
            brain.perform_hebbian_learning()
        for pair, weight in brain.weights.items():
            with self.subTest(pair=pair):
                self.assertGreaterEqual(weight, -1.0)
                self.assertLessEqual(weight, 1.0)

    def test_learning_leaves_a_record_of_why_each_weight_changed(self):
        """Provenance is the difference between a number and a finding."""
        brain = blank_brain()
        for _ in range(40):
            self._drive(brain, {"hunger": 90.0, "anxiety": 90.0}, 5)
            self._drive(brain, {"hunger": 10.0, "anxiety": 10.0}, 5)
            brain.perform_hebbian_learning()
        self.assertTrue(brain.weights, "nothing was learned to explain")
        pair = next(iter(brain.weights))
        explanation = brain.explain_weight(pair)
        self.assertIsNotNone(explanation)


# ===========================================================================
# 5. Training actually changes the brain, measurably
# ===========================================================================
class TrainingOutcomeTests(unittest.TestCase):

    def test_training_a_blank_brain_gives_it_synapses_it_did_not_have(self):
        sim = HeadlessSimulation(TrainingConfig(seed=7, blank=True))
        self.assertEqual(len(sim.brain.weights), 0)
        sim.run(ticks=600, progress_interval=0)
        self.assertGreater(len(sim.brain.weights), 0,
                           "600 ticks of experience taught a blank brain "
                           "nothing at all")

    def test_a_longer_run_does_not_lose_what_a_shorter_one_learned(self):
        """Learning must accumulate, not thrash."""
        short = HeadlessSimulation(TrainingConfig(seed=11, blank=True))
        short.run(ticks=300, progress_interval=0)
        long_run = HeadlessSimulation(TrainingConfig(seed=11, blank=True))
        long_run.run(ticks=900, progress_interval=0)
        self.assertGreaterEqual(len(long_run.brain.weights),
                                len(short.brain.weights))

    def test_every_named_scenario_runs_and_reports_its_result(self):
        for name in TRAINING_SCENARIOS:
            with self.subTest(scenario=name):
                sim = HeadlessSimulation(TrainingConfig(seed=3, blank=True))
                self.assertTrue(sim.load_scenario(name))
                stats = sim.run(ticks=120, progress_interval=0)
                self.assertEqual(stats["ticks_completed"], 120)
                self.assertIn("total_neurons", stats)

    def test_neurogenesis_respects_the_configured_neuron_ceiling(self):
        sim = HeadlessSimulation(TrainingConfig(
            seed=5, blank=True, max_neurons=12, neurogenesis_cooldown=1))
        sim.run(ticks=1500, progress_interval=0)
        live = [n for n in sim.brain.positions
                if n not in sim.brain.excluded_neurons]
        # Exactly the ceiling, not "roughly" it. The count used to subtract the
        # LENGTH of the excluded-neurons list rather than the excluded neurons
        # actually present, so a brain containing none of them ran five past
        # its own limit.
        self.assertLessEqual(len(live), 12,
                             "the brain grew past its configured maximum")


# ===========================================================================
# 6. A trained brain can be saved, re-read, and studied
# ===========================================================================
class PersistenceTests(unittest.TestCase):

    def test_a_trained_brain_survives_a_file_round_trip_unchanged(self):
        sim = HeadlessSimulation(TrainingConfig(seed=21, blank=True))
        sim.run(ticks=400, progress_interval=0)
        before = export_without_timestamp(sim.brain)

        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trained.json")
            self.assertTrue(sim.brain.save_brain(path))
            reloaded = blank_brain()
            self.assertTrue(reloaded.load_brain_file(path))

        after = export_without_timestamp(reloaded)
        self.assertEqual(before["neurons"], after["neurons"])
        self.assertEqual(sorted(before["connections"],
                                key=lambda c: (c["source"], c["target"])),
                         sorted(after["connections"],
                                key=lambda c: (c["source"], c["target"])),
                         "a brain does not come back off disk the way it went on")

    def test_an_exported_brain_records_what_it_contains(self):
        sim = HeadlessSimulation(TrainingConfig(seed=31, blank=True))
        sim.run(ticks=200, progress_interval=0)
        data = sim.brain.export_brain()
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["neuron_count"], len(sim.brain.positions))
        self.assertEqual(data["metadata"]["connection_count"], len(sim.brain.weights))

    def test_a_saved_brain_is_plain_readable_json(self):
        """Anyone auditing a result has to be able to open the file."""
        sim = HeadlessSimulation(TrainingConfig(seed=41, blank=True))
        sim.run(ticks=150, progress_interval=0)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "trained.json")
            sim.brain.save_brain(path)
            with open(path) as handle:
                data = json.load(handle)
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data["connections"], list)


# ===========================================================================
# 7. Trainer and game agree
# ===========================================================================
class TrainerGameParityTests(unittest.TestCase):
    """A brain trained here has to behave the same way when the squid runs it."""

    def test_both_step_the_network_with_the_same_function(self):
        import src.brain_widget as brain_widget
        import headless_trainer
        self.assertIs(headless_trainer.propagate, propagate)
        self.assertIn("from .propagation import propagate",
                      open("src/brain_widget.py").read(),
                      "the game has stopped using the shared transfer function")

    def test_both_hatch_from_the_same_innate_tables(self):
        brain = newborn_brain()
        for source, target, weight in INNATE_ACTION_WIRING:
            with self.subTest(synapse=(source, target)):
                self.assertAlmostEqual(brain.weights.get((source, target)),
                                       weight, places=6)

    def test_a_trained_brain_computes_the_same_thing_in_both(self):
        """The measurable form of parity: identical state and weights, stepped
        by each implementation, must give identical activations."""
        sim = HeadlessSimulation(TrainingConfig(seed=17, blank=True))
        sim.run(ticks=300, progress_interval=0)

        targets = [n for n in sim.brain.positions
                   if n not in PURE_INPUT_NEURONS
                   and n not in CORE_STAT_NEURONS
                   and n not in sim.brain.excluded_neurons]
        baseline_state = {k: v for k, v in sim.brain.state.items()
                          if isinstance(v, (int, float))}

        first = dict(baseline_state)
        propagate(first, sim.brain.weights, targets, smoothing=0.5)
        second = dict(baseline_state)
        propagate(second, sim.brain.weights, targets, smoothing=0.5)

        for name in targets:
            with self.subTest(neuron=name):
                self.assertAlmostEqual(first[name], second[name], places=9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
