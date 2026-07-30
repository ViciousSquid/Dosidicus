import io
import os
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtCore, QtWidgets

import src.brain_tool as brain_tool_module
import src.brain_widget as brain_widget_module
from src.squid_statistics import SquidStatistics
from src.tamagotchi_logic import TamagotchiLogic


class FakeSignal:
    def connect(self, *_args):
        pass

    def disconnect(self, *_args):
        pass

    def emit(self, *_args):
        pass


class FakeRenderWorker:
    def __init__(self, *_args, **_kwargs):
        self.render_complete = FakeSignal()

    def start(self):
        pass

    def stop(self):
        pass

    def wait(self, *_args):
        return True

    def request_render(self, *_args, **_kwargs):
        pass


class FakeBrainWorker:
    def __init__(self, *_args, **_kwargs):
        self.neurogenesis_result = FakeSignal()
        self.hebbian_result = FakeSignal()
        self.state_update_result = FakeSignal()
        self.error_occurred = FakeSignal()

    def start(self):
        pass

    def stop(self):
        pass

    def wait(self, *_args):
        return True

    def isRunning(self):
        return False

    def update_cache(self, *_args, **_kwargs):
        pass


class FakeTaskManager(QtWidgets.QWidget):
    def __init__(self, _worker, parent=None):
        super().__init__(parent)


class FakeSquid:
    def __init__(self):
        self.anxiety = 10
        self.happiness = 90
        self.satisfaction = 20
        self.is_sleeping = False
        self.is_sick = False
        self.statistics = SquidStatistics(self)


class StatisticsTabLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_late_logic_wiring_projects_model_statistics_into_real_tab(self):
        window = None
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    brain_widget_module,
                    "BrainRenderWorker",
                    FakeRenderWorker,
                )
            )
            stack.enter_context(
                patch.object(brain_widget_module, "_HAS_BRAIN_BRIDGE", False)
            )
            stack.enter_context(
                patch.object(brain_tool_module, "BrainWorker", FakeBrainWorker)
            )
            stack.enter_context(
                patch.object(
                    brain_tool_module,
                    "TaskManagerWindow",
                    FakeTaskManager,
                )
            )
            stack.enter_context(
                patch.object(brain_tool_module, "_HAS_BRAIN_BRIDGE", False)
            )
            stack.enter_context(redirect_stdout(io.StringIO()))

            try:
                window = brain_tool_module.SquidBrainWindow(
                    None,
                    debug_mode=False,
                    config=None,
                )
                self.assertEqual(window.tabs.count(), 7)
                self.assertGreaterEqual(
                    window.tabs.indexOf(window.statistics_tab),
                    0,
                )
                self.assertIsNone(window.statistics_tab.tamagotchi_logic)

                logic = object.__new__(TamagotchiLogic)
                logic.squid = FakeSquid()
                logic.brain_window = window
                logic.neuron_output_monitor = None

                prebound_stats = logic.squid.statistics
                self.assertTrue(prebound_stats.increment("cheese_eaten"))
                prebound_stats.add_distance(1000)
                prebound_stats.sushi_consumed = 2
                prebound_stats.poops_created = 3
                prebound_stats.max_poops_cleaned = 4
                prebound_stats.startles_experienced = 5
                prebound_stats.ink_clouds_created = 6
                prebound_stats.times_colour_changed = 7
                prebound_stats.total_rocks_thrown = 8
                prebound_stats.plants_interacted = 9
                prebound_stats.time_spent_asleep = 125
                prebound_stats.sickness_episodes = 10
                prebound_stats.novelty_neurons_created = 11
                prebound_stats.stress_neurons_created = 12
                prebound_stats.reward_neurons_created = 13
                prebound_stats.observe_neuron_count(14)
                prebound_stats.total_age_seconds = 15 * 60

                window.set_tamagotchi_logic(logic)

                for tab_name in (
                    "network_tab",
                    "nn_viz_tab",
                    "memory_tab",
                    "decisions_tab",
                    "personality_tab",
                    "statistics_tab",
                    "about_tab",
                ):
                    self.assertIs(
                        getattr(window, tab_name).tamagotchi_logic,
                        logic,
                    )

                labels = window.statistics_tab.stat_labels
                expected_initial_labels = {
                    "squid_age_minutes": "15",
                    "distance_swam": "1,000",
                    "cheese_eaten": "1",
                    "sushi_eaten": "2",
                    "poops_created": "3",
                    "max_poops_cleaned": "4",
                    "startles_experienced": "5",
                    "ink_clouds_created": "6",
                    "times_colour_changed": "7",
                    "rocks_thrown": "8",
                    "plants_interacted": "9",
                    "total_sleep_time": "125",
                    "sickness_episodes": "10",
                    "novelty_neurons_created": "11",
                    "stress_neurons_created": "12",
                    "reward_neurons_created": "13",
                    "current_neurons": "14",
                }
                for label_name, expected_text in (
                    expected_initial_labels.items()
                ):
                    with self.subTest(
                        phase="initial bind",
                        label_name=label_name,
                    ):
                        self.assertEqual(
                            labels[label_name].text(),
                            expected_text,
                        )

                prebound_stats.reset()
                self.assertTrue(logic.record_statistic_event("cheese_eaten"))
                logic.track_distance(4321)
                logic.squid.statistics.observe_neuron_count(15)
                logic._refresh_statistics_tab()

                self.assertEqual(logic.squid.statistics.cheese_consumed, 1)
                self.assertEqual(logic.squid.statistics.distance_swam, 4321.0)
                self.assertEqual(logic.squid.statistics.max_neurons_reached, 15)
                self.assertEqual(labels["cheese_eaten"].text(), "1")
                self.assertEqual(labels["distance_swam"].text(), "4,321")
                self.assertEqual(labels["current_neurons"].text(), "15")

                window.set_tamagotchi_logic(None)
                self.assertIsNone(window.tamagotchi_logic)
                self.assertIsNone(window.brain_widget.tamagotchi_logic)
                for tab_name in (
                    "network_tab",
                    "nn_viz_tab",
                    "memory_tab",
                    "decisions_tab",
                    "personality_tab",
                    "statistics_tab",
                    "about_tab",
                ):
                    self.assertIsNone(
                        getattr(window, tab_name).tamagotchi_logic
                    )

                replacement_logic = object.__new__(TamagotchiLogic)
                replacement_logic.squid = FakeSquid()
                replacement_logic.brain_window = window
                replacement_logic.neuron_output_monitor = None
                replacement_stats = replacement_logic.squid.statistics
                replacement_stats.increment("cheese_eaten", 21)
                replacement_stats.add_distance(2000)
                replacement_stats.sushi_consumed = 22
                replacement_stats.poops_created = 23
                replacement_stats.max_poops_cleaned = 24
                replacement_stats.startles_experienced = 25
                replacement_stats.ink_clouds_created = 26
                replacement_stats.times_colour_changed = 27
                replacement_stats.total_rocks_thrown = 28
                replacement_stats.plants_interacted = 29
                replacement_stats.time_spent_asleep = 240
                replacement_stats.sickness_episodes = 30
                replacement_stats.novelty_neurons_created = 31
                replacement_stats.stress_neurons_created = 32
                replacement_stats.reward_neurons_created = 33
                replacement_stats.observe_neuron_count(34)
                replacement_stats.total_age_seconds = 35 * 60

                window.set_tamagotchi_logic(replacement_logic)

                for tab_name in (
                    "network_tab",
                    "nn_viz_tab",
                    "memory_tab",
                    "decisions_tab",
                    "personality_tab",
                    "statistics_tab",
                    "about_tab",
                ):
                    self.assertIs(
                        getattr(window, tab_name).tamagotchi_logic,
                        replacement_logic,
                    )
                expected_replacement_labels = {
                    "squid_age_minutes": "35",
                    "distance_swam": "2,000",
                    "cheese_eaten": "21",
                    "sushi_eaten": "22",
                    "poops_created": "23",
                    "max_poops_cleaned": "24",
                    "startles_experienced": "25",
                    "ink_clouds_created": "26",
                    "times_colour_changed": "27",
                    "rocks_thrown": "28",
                    "plants_interacted": "29",
                    "total_sleep_time": "240",
                    "sickness_episodes": "30",
                    "novelty_neurons_created": "31",
                    "stress_neurons_created": "32",
                    "reward_neurons_created": "33",
                    "current_neurons": "34",
                }
                for label_name, expected_text in (
                    expected_replacement_labels.items()
                ):
                    with self.subTest(
                        phase="replacement bind",
                        label_name=label_name,
                    ):
                        self.assertEqual(
                            labels[label_name].text(),
                            expected_text,
                        )
            finally:
                if window is not None:
                    for timer in window.findChildren(QtCore.QTimer):
                        timer.stop()
                    window.close()
                    window.deleteLater()
                    QtCore.QCoreApplication.sendPostedEvents(
                        None,
                        QtCore.QEvent.DeferredDelete,
                    )
                    self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
