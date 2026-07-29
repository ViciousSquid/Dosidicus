import io
import tempfile
import unittest
from contextlib import redirect_stdout

from src.save_manager import SaveManager
from src.squid_statistics import SquidStatistics


class FakeSquid:
    def __init__(self, *, is_sick=False):
        self.anxiety = 10
        self.happiness = 90
        self.satisfaction = 20
        self.is_sleeping = False
        self.is_sick = is_sick


class StatisticsPersistenceTests(unittest.TestCase):
    def test_statistics_survive_save_archive_round_trip(self):
        squid = FakeSquid()
        statistics = SquidStatistics(squid)
        squid.is_sleeping = True
        statistics.update(elapsed_seconds=12.5)
        statistics.record_sickness_state(True)
        statistics.record_sickness_state(True)
        statistics.record_neuron_birth("novelty", current_count=8)
        statistics.record_neuron_birth("reward", current_count=9)
        statistics.observe_neuron_count(8)

        with tempfile.TemporaryDirectory() as save_directory:
            manager = SaveManager(save_directory)
            with redirect_stdout(io.StringIO()):
                archive_path = manager.save_game(
                    {
                        "game_state": {
                            "squid": {
                                "uuid": "00000000-0000-0000-0000-000000000026",
                            }
                        },
                        "statistics": statistics.to_dict(),
                    }
                )
            self.assertIsNotNone(archive_path)
            loaded_archive = manager.load_game()

        restored_squid = FakeSquid(is_sick=True)
        restored = SquidStatistics(restored_squid)
        restored.load_statistics(loaded_archive["statistics"])

        self.assertEqual(restored.time_spent_asleep, 12.5)
        self.assertEqual(restored.sickness_episodes, 1)
        self.assertEqual(restored.novelty_neurons_created, 1)
        self.assertEqual(restored.reward_neurons_created, 1)
        self.assertEqual(restored.current_neurons, 8)
        self.assertEqual(restored.max_neurons_reached, 9)

        restored.record_sickness_state(True)
        self.assertEqual(restored.sickness_episodes, 1)

    def test_legacy_current_count_repairs_an_invalid_lifetime_maximum(self):
        for saved_maximum in (None, 0, 5):
            with self.subTest(saved_maximum=saved_maximum):
                restored = SquidStatistics(FakeSquid())
                saved_statistics = {
                    "current_neurons": 11,
                    "novelty_neurons_created": 2,
                }
                if saved_maximum is not None:
                    saved_statistics["max_neurons_reached"] = saved_maximum

                restored.load_statistics(saved_statistics)

                self.assertEqual(restored.current_neurons, 11)
                self.assertEqual(restored.max_neurons_reached, 11)
                self.assertEqual(restored.novelty_neurons_created, 2)

    def test_load_preserves_a_lifetime_maximum_above_current_count(self):
        restored = SquidStatistics(FakeSquid())

        restored.load_statistics(
            {
                "current_neurons": 8,
                "max_neurons_reached": 15,
            }
        )

        self.assertEqual(restored.current_neurons, 8)
        self.assertEqual(restored.max_neurons_reached, 15)


if __name__ == "__main__":
    unittest.main()
