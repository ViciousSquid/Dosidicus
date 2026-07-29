import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from src.brain_widget import BrainWidget
from src.neurogenesis import EnhancedNeurogenesis
from src.squid_statistics import SquidStatistics
from src.tamagotchi_logic import TamagotchiLogic


class RecordingSignal:
    def __init__(self):
        self.events = []

    def emit(self, neuron_name):
        self.events.append(neuron_name)


class NotifyingNeurogenesis:
    def __init__(self, brain_widget, neuron_name):
        self.brain_widget = brain_widget
        self.neuron_name = neuron_name

    def capture_experience_context(self, **_kwargs):
        return object()

    def should_create_neuron(self, _context):
        return True

    def create_functional_neuron(self, _context, **_kwargs):
        EnhancedNeurogenesis._notify_neuron_created(self, self.neuron_name)
        return self.neuron_name


class FakeSquid:
    def __init__(self):
        self.anxiety = 10
        self.happiness = 90
        self.satisfaction = 20
        self.is_sleeping = False
        self.is_sick = False
        self.statistics = SquidStatistics(self)


class RecordingMentalStateManager:
    def __init__(self):
        self.states = []

    def set_state(self, state_name, is_active):
        self.states.append((state_name, is_active))


class StatisticsEventWiringTests(unittest.TestCase):
    def test_threaded_completion_does_not_duplicate_engine_notification(self):
        signal = RecordingSignal()
        controller = SimpleNamespace(
            _pending_neurogenesis_check=True,
            neuronCreated=signal,
            pruning_enabled=False,
            update=lambda: None,
        )
        controller.enhanced_neurogenesis = NotifyingNeurogenesis(
            controller,
            "novelty_threaded",
        )

        with redirect_stdout(io.StringIO()):
            BrainWidget._on_neurogenesis_complete(
                controller,
                {
                    "should_create": True,
                    "neuron_type": "novelty",
                    "state_context": {},
                },
            )

        self.assertEqual(signal.events, ["novelty_threaded"])

    def test_synchronous_fallback_does_not_delegate_an_already_created_birth(self):
        signal = RecordingSignal()
        delegated_results = []

        def create_synchronously(_state):
            signal.emit("stress_synchronous")
            return {"should_create": True}

        controller = SimpleNamespace(
            _pending_neurogenesis_check=False,
            enhanced_neurogenesis=SimpleNamespace(),
            state={},
            _use_threaded_processing=False,
            check_neurogenesis_triggers=create_synchronously,
            _on_neurogenesis_complete=delegated_results.append,
        )

        BrainWidget._periodic_neurogenesis_check(controller)

        self.assertEqual(signal.events, ["stress_synchronous"])
        self.assertEqual(delegated_results, [])
        self.assertFalse(controller._pending_neurogenesis_check)

    def test_orphan_rescue_emits_one_completed_birth(self):
        signal = RecordingSignal()
        brain_widget = SimpleNamespace(
            neuronCreated=signal,
            neuron_positions={
                "orphan": (100, 100),
                "hunger": (300, 300),
            },
            state={
                "orphan": 50.0,
                "hunger": 50.0,
            },
            excluded_neurons=[],
            weights={},
            visible_neurons=set(),
            neuron_shapes={},
            state_colors={},
            log_neurogenesis_event=lambda *_args, **_kwargs: None,
        )
        neurogenesis = object.__new__(EnhancedNeurogenesis)
        neurogenesis.brain_widget = brain_widget
        neurogenesis.functional_neurons = {}

        with (
            redirect_stdout(io.StringIO()),
            patch("src.neurogenesis.random.randint", return_value=0),
            patch("src.neurogenesis.random.uniform", return_value=0.5),
            patch("src.neurogenesis.random.random", return_value=0.75),
        ):
            neurogenesis.rescue_orphan("orphan")

        self.assertEqual(signal.events, ["connector_rescue"])

    def test_one_birth_signal_updates_the_model_once_without_the_tab(self):
        squid = FakeSquid()
        neuron_name = "reward_test"
        brain_widget = SimpleNamespace(
            neuron_positions={f"neuron_{index}": (0, 0) for index in range(9)},
            enhanced_neurogenesis=SimpleNamespace(
                functional_neurons={
                    neuron_name: SimpleNamespace(neuron_type="reward"),
                }
            ),
            neurogenesis_data={},
        )
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(
            brain_widget=brain_widget,
            statistics_tab=None,
        )

        with patch("src.tamagotchi_logic.QtCore.QTimer.singleShot") as single_shot:
            logic._on_neurogenesis_icon_and_memory(neuron_name)

        self.assertEqual(squid.statistics.reward_neurons_created, 1)
        self.assertEqual(squid.statistics.current_neurons, 9)
        self.assertEqual(squid.statistics.max_neurons_reached, 9)
        single_shot.assert_called_once_with(
            0,
            logic._observe_current_neuron_count,
        )

    def test_sickness_funnel_keeps_state_and_transition_count_aligned(self):
        squid = FakeSquid()
        squid.mental_state_manager = RecordingMentalStateManager()
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid

        logic._set_sickness_state(True)
        logic._set_sickness_state(True)
        logic._set_sickness_state(False)
        logic._set_sickness_state(True)

        self.assertTrue(squid.is_sick)
        self.assertEqual(squid.statistics.sickness_episodes, 2)
        self.assertEqual(
            squid.mental_state_manager.states,
            [
                ("sick", True),
                ("sick", True),
                ("sick", False),
                ("sick", True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
