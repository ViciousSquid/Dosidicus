import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.squid_statistics import (
    DEFAULT_NEURON_COUNT,
    DISTANCE_ROLLOVER_LIMIT,
    SquidStatistics,
)


class FakeSquid:
    def __init__(self):
        self.anxiety = 10
        self.happiness = 90
        self.satisfaction = 20
        self.is_sleeping = False
        self.is_sick = False


class SquidStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.squid = FakeSquid()
        self.statistics = SquidStatistics(self.squid)

    def test_default_neuron_count_matches_the_standard_brain(self):
        # Checked against what a newborn brain actually contains rather than a
        # literal, which went stale the moment a squid started hatching with
        # the sensors and action neurons its innate reflexes need.
        from src.brain_constants import newborn_neurons, EXCLUDED_NEURONS
        expected = len(set(newborn_neurons()) - set(EXCLUDED_NEURONS))
        self.assertEqual(DEFAULT_NEURON_COUNT, expected)
        self.assertEqual(self.statistics.current_neurons, DEFAULT_NEURON_COUNT)
        self.assertEqual(
            self.statistics.max_neurons_reached,
            DEFAULT_NEURON_COUNT,
        )

    def test_sleep_time_uses_explicit_elapsed_time(self):
        self.squid.is_sleeping = True
        self.statistics.update(elapsed_seconds=2.5)

        self.squid.is_sleeping = False
        self.statistics.update(elapsed_seconds=10)

        self.squid.is_sleeping = True
        self.statistics.update(elapsed_seconds=0.25)

        self.assertEqual(self.statistics.time_spent_asleep, 2.75)

    def test_zero_argument_update_preserves_one_second_compatibility(self):
        self.squid.is_sleeping = True

        self.statistics.update()

        self.assertEqual(self.statistics.time_spent_asleep, 1)

    def test_sickness_counts_only_false_to_true_transitions(self):
        self.statistics.record_sickness_state(False)
        self.statistics.record_sickness_state(True)
        self.statistics.record_sickness_state(True)
        self.statistics.record_sickness_state(False)
        self.statistics.record_sickness_state(False)
        self.statistics.record_sickness_state(True)

        self.assertEqual(self.statistics.sickness_episodes, 2)

    def test_neuron_birth_updates_type_and_lifetime_maximum_once(self):
        # Counts are expressed relative to what the squid starts with, so this
        # keeps testing "three neurons were grown" rather than three literals
        # that only meant that when a newborn had eight neurons.
        start = DEFAULT_NEURON_COUNT
        self.statistics.record_neuron_birth("novelty", current_count=start + 1)
        self.statistics.record_neuron_birth("stress", current_count=start + 2)
        self.statistics.record_neuron_birth("connector", current_count=start + 3)

        self.assertEqual(self.statistics.novelty_neurons_created, 1)
        self.assertEqual(self.statistics.stress_neurons_created, 1)
        self.assertEqual(self.statistics.reward_neurons_created, 0)
        self.assertEqual(self.statistics.current_neurons, start + 3)
        self.assertEqual(self.statistics.max_neurons_reached, start + 3)

    def test_lifetime_maximum_never_decreases_with_current_count(self):
        start = DEFAULT_NEURON_COUNT
        self.statistics.observe_neuron_count(start + 4)
        self.statistics.observe_neuron_count(start)
        self.statistics.record_neuron_birth("reward", current_count=start + 1)

        self.assertEqual(self.statistics.current_neurons, start + 1)
        self.assertEqual(self.statistics.max_neurons_reached, start + 4)
        self.assertEqual(self.statistics.reward_neurons_created, 1)

    def test_reset_preserves_current_and_lifetime_neuron_counts(self):
        start = DEFAULT_NEURON_COUNT
        self.statistics.observe_neuron_count(start + 4)
        self.statistics.observe_neuron_count(start + 1)
        self.statistics.cheese_consumed = 3

        self.statistics.reset()

        self.assertEqual(self.statistics.current_neurons, start + 1)
        self.assertEqual(self.statistics.max_neurons_reached, start + 4)
        self.assertEqual(self.statistics.cheese_consumed, 0)

    def test_other_lifetime_maxima_never_decrease(self):
        self.statistics.observe_poop_count(5)
        self.statistics.observe_poop_count(2)
        self.statistics.observe_memory_counts(3, 7)
        self.statistics.observe_memory_counts(1, 4)

        self.assertEqual(self.statistics.max_poops_cleaned, 5)
        self.assertEqual(self.statistics.max_short_term_memories, 3)
        self.assertEqual(self.statistics.max_long_term_memories, 7)

    def test_the_distance_counter_has_no_ceiling(self):
        """It used to wrap at ~1 billion pixels and count the wraps separately,
        so a well-travelled squid's distance read as a small remainder with a
        multiplier in front of it. It is one unbounded integer now."""
        show_message = Mock()
        self.squid.tamagotchi_logic = SimpleNamespace(
            show_message=show_message,
        )
        self.statistics.distance_swam = DISTANCE_ROLLOVER_LIMIT - 10

        self.statistics.update_distance(DISTANCE_ROLLOVER_LIMIT * 2 + 10, 0)

        self.assertEqual(self.statistics.distance_swam,
                         DISTANCE_ROLLOVER_LIMIT * 3)
        self.assertEqual(self.statistics.distance_swam_multiplier, 1)
        self.assertEqual(self.statistics.get_distance_display(),
                         f"{DISTANCE_ROLLOVER_LIMIT * 3:,}")
        show_message.assert_not_called()

    def test_distance_is_stored_as_whole_pixels(self):
        """A float total serialised to ~17 significant digits every save."""
        self.statistics.add_distance(1234.56789012345)
        saved = self.statistics.to_dict()["distance_swam"]
        self.assertIsInstance(saved, int)
        self.assertEqual(saved, 1234)

    def test_sub_pixel_movement_is_carried_not_discarded(self):
        """Rounding each step would lose almost all of a slow squid's travel."""
        for _ in range(1000):
            self.statistics.add_distance(0.4)
        self.assertEqual(self.statistics.distance_swam, 400)

    def test_a_legacy_rolled_over_save_is_folded_into_one_total(self):
        self.statistics.load_statistics({
            "distance_swam": 500,
            "distance_swam_multiplier": 4,
        })
        self.assertEqual(self.statistics.distance_swam,
                         500 + 3 * DISTANCE_ROLLOVER_LIMIT)
        self.assertEqual(self.statistics.distance_swam_multiplier, 1)

    def test_unknown_event_is_logged_without_mutating_counters(self):
        with self.assertLogs("src.squid_statistics", level="DEBUG") as logs:
            accepted = self.statistics.increment("misspelled_event")

        self.assertFalse(accepted)
        self.assertIn("misspelled_event", logs.output[0])
        self.assertEqual(self.statistics.cheese_consumed, 0)


if __name__ == "__main__":
    unittest.main()
