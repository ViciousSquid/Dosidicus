import io
import json
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.save_manager import SaveManager
from src.squid_statistics import SquidStatistics
from src.tamagotchi_logic import TamagotchiLogic


EXPECTED_PERSISTENCE_KEYS = {
    "distance_swam": "distance_swam",
    "distance_swam_multiplier": "distance_swam_multiplier",
    "sushi_eaten": "sushi_consumed",
    "cheese_eaten": "cheese_consumed",
    "total_memories_formed": "total_memories_formed",
    "max_short_term_memories": "max_short_term_memories",
    "max_long_term_memories": "max_long_term_memories",
    "highest_anxiety": "highest_anxiety",
    "lowest_happiness": "lowest_happiness",
    "highest_satisfaction": "highest_satisfaction",
    "other_squids_encountered": "other_squids_encountered",
    "rocks_thrown": "total_rocks_thrown",
    "poops_thrown": "total_poops_thrown",
    "total_env_interactions": "total_env_interactions",
    "ink_clouds_created": "ink_clouds_created",
    "plants_interacted": "plants_interacted",
    "total_sleep_time": "time_spent_asleep",
    "peak_novelty": "peak_novelty",
    "peak_stress": "peak_stress",
    "peak_reward": "peak_reward",
    "novelty_neurons_created": "novelty_neurons_created",
    "stress_neurons_created": "stress_neurons_created",
    "reward_neurons_created": "reward_neurons_created",
    "poops_created": "poops_created",
    "max_poops_cleaned": "max_poops_cleaned",
    "startles_experienced": "startles_experienced",
    "times_colour_changed": "times_colour_changed",
    "sickness_episodes": "sickness_episodes",
}


class FakeSquid:
    def __init__(self, *, is_sick=False):
        self.anxiety = 10
        self.happiness = 90
        self.satisfaction = 20
        self.is_sleeping = False
        self.is_sick = is_sick


class LoaderSquid(FakeSquid):
    def __init__(self, *, is_sick=False):
        super().__init__(is_sick=is_sick)
        self.statistics = SquidStatistics(self)
        self.memory_manager = SimpleNamespace(
            short_term_memory=[],
            long_term_memory=[],
        )
        self.mental_state_manager = SimpleNamespace(set_state=Mock())

    def load_state(self, state):
        for attribute_name, value in state.items():
            setattr(self, attribute_name, value)


def make_loader_logic(squid):
    logic = object.__new__(TamagotchiLogic)
    logic.squid = squid
    logic.user_interface = SimpleNamespace(
        load_decorations_data=Mock(),
    )
    logic.brain_window = SimpleNamespace(
        brain_widget=SimpleNamespace(),
        set_brain_state=Mock(),
    )
    logic.statistics_window = SimpleNamespace(
        set_score=Mock(),
        update_statistics=Mock(),
    )
    logic.refresh_neuron_count = Mock()
    logic.set_simulation_speed = Mock()
    return logic


class StatisticsPersistenceTests(unittest.TestCase):
    def test_persistence_schema_keeps_every_canonical_field(self):
        statistics = SquidStatistics(FakeSquid())

        self.assertEqual(
            statistics._PERSISTENCE_KEYS,
            EXPECTED_PERSISTENCE_KEYS,
        )
        self.assertEqual(
            set(statistics.to_dict()),
            set(EXPECTED_PERSISTENCE_KEYS)
            | {
                "total_age_seconds",
                "squid_age_minutes",
                "max_neurons_reached",
                "current_neurons",
            },
        )

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

    def test_partial_load_replaces_absent_live_session_values(self):
        statistics = SquidStatistics(FakeSquid())
        statistics.sushi_consumed = 9
        statistics.distance_swam = 500
        statistics.sickness_episodes = 4
        statistics.observe_neuron_count(12)

        statistics.load_statistics({"cheese_eaten": 2})

        self.assertEqual(statistics.cheese_consumed, 2)
        self.assertEqual(statistics.sushi_consumed, 0)
        self.assertEqual(statistics.distance_swam, 0)
        self.assertEqual(statistics.sickness_episodes, 0)
        self.assertEqual(statistics.current_neurons, 8)
        self.assertEqual(statistics.max_neurons_reached, 8)

    def test_empty_load_replaces_the_entire_live_session(self):
        statistics = SquidStatistics(FakeSquid())
        statistics.cheese_consumed = 2
        statistics.sushi_consumed = 9
        statistics.distance_swam = 500
        statistics.sickness_episodes = 4
        statistics.observe_neuron_count(12)

        statistics.load_statistics({})

        self.assertEqual(statistics.cheese_consumed, 0)
        self.assertEqual(statistics.sushi_consumed, 0)
        self.assertEqual(statistics.distance_swam, 0)
        self.assertEqual(statistics.sickness_episodes, 0)
        self.assertEqual(statistics.current_neurons, 8)
        self.assertEqual(statistics.max_neurons_reached, 8)

    def test_malformed_numeric_values_fall_back_without_poisoning_model(self):
        squid = FakeSquid()
        statistics = SquidStatistics(squid)

        statistics.load_statistics(
            {
                "total_age_seconds": "12.5",
                "distance_swam": "42.25",
                "total_sleep_time": None,
                "sickness_episodes": "not-a-number",
                "highest_anxiety": float("inf"),
                "cheese_eaten": True,
                "peak_stress": "1.75",
                "current_neurons": "9",
                "max_neurons_reached": "invalid",
            }
        )

        self.assertEqual(statistics.total_age_seconds, 12.5)
        self.assertEqual(statistics.distance_swam, 42.25)
        self.assertEqual(statistics.time_spent_asleep, 0)
        self.assertEqual(statistics.sickness_episodes, 0)
        self.assertEqual(statistics.highest_anxiety, 0)
        self.assertEqual(statistics.cheese_consumed, 0)
        self.assertEqual(statistics.peak_stress, 1.75)
        self.assertEqual(statistics.current_neurons, 9)
        self.assertEqual(statistics.max_neurons_reached, 9)

        squid.is_sleeping = True
        statistics.update(elapsed_seconds=0.5)
        statistics.add_distance(0.75)
        statistics.increment("cheese_eaten")

        self.assertEqual(statistics.time_spent_asleep, 0.5)
        self.assertEqual(statistics.distance_swam, 43)
        self.assertEqual(statistics.cheese_consumed, 1)

    def test_malformed_neuron_counts_fall_back_to_the_live_default(self):
        malformed_counts = (
            None,
            True,
            -1,
            9.5,
            "9.5",
            float("nan"),
            float("inf"),
            [],
            {},
        )

        for malformed_count in malformed_counts:
            with self.subTest(malformed_count=malformed_count):
                statistics = SquidStatistics(FakeSquid())
                statistics.load_statistics(
                    {
                        "current_neurons": malformed_count,
                        "max_neurons_reached": malformed_count,
                    }
                )

                self.assertEqual(statistics.current_neurons, 8)
                self.assertEqual(statistics.max_neurons_reached, 8)

    def test_both_public_loaders_accept_malformed_numeric_statistics(self):
        malformed_statistics = {
            "distance_swam": "not-a-number",
            "total_sleep_time": None,
            "sickness_episodes": "4",
            "current_neurons": "9",
            "max_neurons_reached": "invalid",
        }

        apply_squid = LoaderSquid()
        apply_logic = make_loader_logic(apply_squid)
        save_data = {
            "game_state": {
                "squid": {"is_sick": False},
                "decorations": [],
                "tamagotchi_logic": {
                    "cleanliness_threshold_time": 1,
                    "hunger_threshold_time": 2,
                    "last_clean_time": 3,
                    "points": 4,
                },
            },
            "statistics": malformed_statistics,
        }

        with (
            redirect_stdout(io.StringIO()),
            patch(
                "src.tamagotchi_logic.show_custom_brain_load_warning",
                return_value=True,
            ),
        ):
            self.assertTrue(apply_logic._apply_save_data(save_data))

        self.assertEqual(apply_squid.statistics.distance_swam, 0)
        self.assertEqual(apply_squid.statistics.time_spent_asleep, 0)
        self.assertEqual(apply_squid.statistics.sickness_episodes, 4)
        self.assertEqual(apply_squid.statistics.current_neurons, 9)
        self.assertEqual(apply_squid.statistics.max_neurons_reached, 9)

        zip_squid = LoaderSquid()
        zip_logic = make_loader_logic(zip_squid)
        with tempfile.TemporaryDirectory() as save_directory:
            archive_path = f"{save_directory}/malformed-statistics.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "game_state.json",
                    json.dumps(
                        {
                            "squid": {"is_sick": False},
                            "decorations": [],
                            "tamagotchi_logic": {"points": 7},
                        }
                    ),
                )
                archive.writestr(
                    "statistics.json",
                    json.dumps(malformed_statistics),
                )

            zip_logic.save_manager = SimpleNamespace(
                get_latest_save=lambda: archive_path,
            )
            with redirect_stdout(io.StringIO()):
                self.assertTrue(zip_logic.load_game())

        self.assertEqual(zip_squid.statistics.distance_swam, 0)
        self.assertEqual(zip_squid.statistics.time_spent_asleep, 0)
        self.assertEqual(zip_squid.statistics.sickness_episodes, 4)
        self.assertEqual(zip_squid.statistics.current_neurons, 9)
        self.assertEqual(zip_squid.statistics.max_neurons_reached, 9)

    def test_zip_loader_preserves_model_for_nested_legacy_statistics(self):
        squid = LoaderSquid()
        original_statistics = squid.statistics
        logic = make_loader_logic(squid)

        with tempfile.TemporaryDirectory() as save_directory:
            archive_path = f"{save_directory}/nested-statistics.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "game_state.json",
                    json.dumps(
                        {
                            "squid": {
                                "is_sick": False,
                                "statistics": {"distance_swam": 7},
                            },
                            "decorations": [],
                            "tamagotchi_logic": {"points": 0},
                        }
                    ),
                )

            logic.save_manager = SimpleNamespace(
                get_latest_save=lambda: archive_path,
            )
            with redirect_stdout(io.StringIO()):
                loaded = logic.load_game()

        self.assertTrue(loaded)
        self.assertIs(squid.statistics, original_statistics)
        self.assertEqual(squid.statistics.distance_swam, 7)

    def test_apply_save_data_replaces_absent_live_statistics(self):
        squid = LoaderSquid()
        squid.statistics.sushi_consumed = 9
        squid.statistics.distance_swam = 500
        squid.statistics.sickness_episodes = 4
        logic = make_loader_logic(squid)
        save_data = {
            "game_state": {
                "squid": {"is_sick": True},
                "decorations": [],
                "tamagotchi_logic": {
                    "cleanliness_threshold_time": 1,
                    "hunger_threshold_time": 2,
                    "last_clean_time": 3,
                    "points": 4,
                },
            },
            "statistics": {"cheese_eaten": 2},
        }

        with (
            redirect_stdout(io.StringIO()),
            patch(
                "src.tamagotchi_logic.show_custom_brain_load_warning",
                return_value=True,
            ),
        ):
            loaded = logic._apply_save_data(save_data)

        self.assertTrue(loaded)
        self.assertEqual(squid.statistics.cheese_consumed, 2)
        self.assertEqual(squid.statistics.sushi_consumed, 0)
        self.assertEqual(squid.statistics.distance_swam, 0)
        self.assertEqual(squid.statistics.sickness_episodes, 0)
        squid.mental_state_manager.set_state.assert_called_once_with(
            "sick",
            True,
        )
        logic.statistics_window.set_score.assert_called_once_with(4)
        logic.statistics_window.update_statistics.assert_called_once_with()

    def test_zip_load_replaces_absent_live_statistics(self):
        squid = LoaderSquid()
        squid.statistics.sushi_consumed = 9
        squid.statistics.distance_swam = 500
        squid.statistics.sickness_episodes = 4
        logic = make_loader_logic(squid)

        with tempfile.TemporaryDirectory() as save_directory:
            archive_path = (
                f"{save_directory}/partial-statistics.zip"
            )
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "game_state.json",
                    json.dumps(
                        {
                            "squid": {"is_sick": True},
                            "decorations": [],
                            "tamagotchi_logic": {"points": 7},
                        }
                    ),
                )
                archive.writestr(
                    "statistics.json",
                    json.dumps({"cheese_eaten": 2}),
                )

            logic.save_manager = SimpleNamespace(
                get_latest_save=lambda: archive_path,
            )
            with redirect_stdout(io.StringIO()):
                loaded = logic.load_game()

        self.assertTrue(loaded)
        self.assertEqual(squid.statistics.cheese_consumed, 2)
        self.assertEqual(squid.statistics.sushi_consumed, 0)
        self.assertEqual(squid.statistics.distance_swam, 0)
        self.assertEqual(squid.statistics.sickness_episodes, 0)
        squid.mental_state_manager.set_state.assert_called_once_with(
            "sick",
            True,
        )
        logic.statistics_window.set_score.assert_called_once_with(7)
        logic.statistics_window.update_statistics.assert_called_once_with()

    def test_apply_save_data_without_statistics_resets_live_values(self):
        squid = LoaderSquid()
        squid.statistics.cheese_consumed = 2
        squid.statistics.sushi_consumed = 9
        squid.statistics.distance_swam = 500
        squid.statistics.sickness_episodes = 4
        logic = make_loader_logic(squid)
        save_data = {
            "game_state": {
                "squid": {"is_sick": False},
                "decorations": [],
                "tamagotchi_logic": {
                    "cleanliness_threshold_time": 1,
                    "hunger_threshold_time": 2,
                    "last_clean_time": 3,
                    "points": 4,
                },
            },
        }

        with (
            redirect_stdout(io.StringIO()),
            patch(
                "src.tamagotchi_logic.show_custom_brain_load_warning",
                return_value=True,
            ),
        ):
            loaded = logic._apply_save_data(save_data)

        self.assertTrue(loaded)
        self.assertEqual(squid.statistics.cheese_consumed, 0)
        self.assertEqual(squid.statistics.sushi_consumed, 0)
        self.assertEqual(squid.statistics.distance_swam, 0)
        self.assertEqual(squid.statistics.sickness_episodes, 0)

    def test_zip_load_without_statistics_resets_live_values(self):
        squid = LoaderSquid()
        squid.statistics.cheese_consumed = 2
        squid.statistics.sushi_consumed = 9
        squid.statistics.distance_swam = 500
        squid.statistics.sickness_episodes = 4
        logic = make_loader_logic(squid)

        with tempfile.TemporaryDirectory() as save_directory:
            archive_path = f"{save_directory}/no-statistics.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "game_state.json",
                    json.dumps(
                        {
                            "squid": {"is_sick": False},
                            "decorations": [],
                            "tamagotchi_logic": {"points": 7},
                        }
                    ),
                )

            logic.save_manager = SimpleNamespace(
                get_latest_save=lambda: archive_path,
            )
            with redirect_stdout(io.StringIO()):
                loaded = logic.load_game()

        self.assertTrue(loaded)
        self.assertEqual(squid.statistics.cheese_consumed, 0)
        self.assertEqual(squid.statistics.sushi_consumed, 0)
        self.assertEqual(squid.statistics.distance_swam, 0)
        self.assertEqual(squid.statistics.sickness_episodes, 0)

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

    def test_reset_neuron_counts_survive_save_archive_round_trip(self):
        statistics = SquidStatistics(FakeSquid())
        statistics.observe_neuron_count(12)
        statistics.observe_neuron_count(9)
        statistics.reset()

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

        restored = SquidStatistics(FakeSquid())
        restored.load_statistics(loaded_archive["statistics"])

        self.assertEqual(restored.current_neurons, 9)
        self.assertEqual(restored.max_neurons_reached, 12)

    def test_every_canonical_persistence_key_round_trips(self):
        statistics = SquidStatistics(FakeSquid())
        expected_attributes = {}
        for index, attribute_name in enumerate(
            statistics._PERSISTENCE_KEYS.values(),
            start=1,
        ):
            value = index + 0.25
            setattr(statistics, attribute_name, value)
            expected_attributes[attribute_name] = value

        restored = SquidStatistics(FakeSquid())
        restored.load_statistics(statistics.to_dict())

        for attribute_name, expected_value in expected_attributes.items():
            with self.subTest(attribute_name=attribute_name):
                self.assertEqual(
                    getattr(restored, attribute_name),
                    expected_value,
                )


if __name__ == "__main__":
    unittest.main()
