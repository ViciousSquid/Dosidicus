import unittest

from src.squid_statistics import DEFAULT_NEURON_COUNT, SquidStatistics


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
        self.assertEqual(DEFAULT_NEURON_COUNT, 8)
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

    def test_sickness_counts_only_false_to_true_transitions(self):
        self.statistics.record_sickness_state(False)
        self.statistics.record_sickness_state(True)
        self.statistics.record_sickness_state(True)
        self.statistics.record_sickness_state(False)
        self.statistics.record_sickness_state(False)
        self.statistics.record_sickness_state(True)

        self.assertEqual(self.statistics.sickness_episodes, 2)

    def test_neuron_birth_updates_type_and_lifetime_maximum_once(self):
        self.statistics.record_neuron_birth("novelty", current_count=8)
        self.statistics.record_neuron_birth("stress", current_count=9)
        self.statistics.record_neuron_birth("connector", current_count=10)

        self.assertEqual(self.statistics.novelty_neurons_created, 1)
        self.assertEqual(self.statistics.stress_neurons_created, 1)
        self.assertEqual(self.statistics.reward_neurons_created, 0)
        self.assertEqual(self.statistics.current_neurons, 10)
        self.assertEqual(self.statistics.max_neurons_reached, 10)

    def test_lifetime_maximum_never_decreases_with_current_count(self):
        self.statistics.observe_neuron_count(12)
        self.statistics.observe_neuron_count(8)
        self.statistics.record_neuron_birth("reward", current_count=9)

        self.assertEqual(self.statistics.current_neurons, 9)
        self.assertEqual(self.statistics.max_neurons_reached, 12)
        self.assertEqual(self.statistics.reward_neurons_created, 1)


if __name__ == "__main__":
    unittest.main()
