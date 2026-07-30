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

                self.assertTrue(logic.record_statistic_event("cheese_eaten"))
                logic.track_distance(4321)
                logic.squid.statistics.observe_neuron_count(13)
                logic._refresh_statistics_tab()

                labels = window.statistics_tab.stat_labels
                self.assertEqual(logic.squid.statistics.cheese_consumed, 1)
                self.assertEqual(logic.squid.statistics.distance_swam, 4321.0)
                self.assertEqual(logic.squid.statistics.max_neurons_reached, 13)
                self.assertEqual(labels["cheese_eaten"].text(), "1")
                self.assertEqual(labels["distance_swam"].text(), "4,321")
                self.assertEqual(labels["current_neurons"].text(), "13")
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
