import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
            neuron_positions={
                **{f"neuron_{index}": (0, 0) for index in range(9)},
                "is_sick": (0, 0),
            },
            excluded_neurons=[
                "is_sick",
                "is_eating",
                "pursuing_food",
                "direction",
                "is_sleeping",
            ],
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
        logic.statistics_window = SimpleNamespace(
            add_score_for_neuron_creation=Mock(),
        )

        with patch("src.tamagotchi_logic.QtCore.QTimer.singleShot") as single_shot:
            logic._on_neurogenesis_icon_and_memory(neuron_name)

        self.assertEqual(squid.statistics.reward_neurons_created, 1)
        self.assertEqual(squid.statistics.current_neurons, 9)
        self.assertEqual(squid.statistics.max_neurons_reached, 9)
        logic.statistics_window.add_score_for_neuron_creation.assert_called_once_with()
        single_shot.assert_called_once_with(
            0,
            logic.refresh_neuron_count,
        )

    def test_live_neuron_count_filters_only_excluded_position_keys(self):
        logic = object.__new__(TamagotchiLogic)
        logic.brain_window = SimpleNamespace(
            brain_widget=SimpleNamespace(
                neuron_positions={
                    **{f"core_{index}": (0, 0) for index in range(8)},
                    "is_sick": (0, 0),
                },
                excluded_neurons=[
                    "is_sick",
                    "is_eating",
                    "pursuing_food",
                    "direction",
                    "is_sleeping",
                ],
            )
        )

        self.assertEqual(logic._live_neuron_count(), 8)

    def test_sleep_elapsed_time_stays_wall_clock_at_faster_speeds(self):
        logic = object.__new__(TamagotchiLogic)

        for speed in (1, 2, 3):
            with self.subTest(speed=speed):
                interval_ms = 1000 // speed
                logic.simulation_timer = SimpleNamespace(
                    interval=lambda value=interval_ms: value
                )
                elapsed = sum(
                    logic._statistics_elapsed_seconds()
                    for _ in range(speed)
                )
                self.assertAlmostEqual(elapsed, 1.0, places=2)

    def test_one_startle_creates_at_most_one_ink_cloud(self):
        cases = (
            ("first startle", "environment", False, 0.0, 1),
            ("later successful roll", "environment", True, 0.0, 1),
            ("later failed roll", "environment", True, 0.99, 0),
            ("awakened later successful roll", "startled_awake", True, 0.0, 1),
        )

        for name, source, already_startled, ink_roll, expected_clouds in cases:
            with self.subTest(name=name):
                squid = FakeSquid()
                squid.status = "roaming"
                squid.is_fleeing = False
                squid.personality = None
                squid.mental_state_manager = RecordingMentalStateManager()
                squid.memory_manager = SimpleNamespace(
                    add_short_term_memory=Mock(),
                )

                logic = object.__new__(TamagotchiLogic)
                logic.mental_states_enabled = True
                logic.initial_startle_allowed = True
                logic.startle_cooldown_max = 10
                logic.squid = squid
                logic.statistics_window = SimpleNamespace(award=Mock())
                logic.brain_window = SimpleNamespace(
                    brain_widget=SimpleNamespace(
                        get_stress_neuron_count=lambda: 0,
                    ),
                    statistics_tab=None,
                )
                logic.create_ink_cloud = Mock()
                logic.show_message = Mock()

                if already_startled:
                    logic._has_startled_before = True

                with (
                    patch(
                        "src.tamagotchi_logic.random.random",
                        return_value=ink_roll,
                    ),
                    patch(
                        "src.tamagotchi_logic.random.choice",
                        return_value="right",
                    ),
                    patch(
                        "src.tamagotchi_logic.QtCore.QTimer.singleShot"
                    ) as single_shot,
                ):
                    logic.startle_squid(source)

                self.assertEqual(
                    logic.create_ink_cloud.call_count,
                    expected_clouds,
                )
                self.assertEqual(squid.statistics.startles_experienced, 1)
                squid.memory_manager.add_short_term_memory.assert_called_once()
                self.assertEqual(single_shot.call_count, 1)

    def test_startle_count_does_not_depend_on_statistics_tab(self):
        squid = FakeSquid()
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=None)

        logic.track_startle()

        self.assertEqual(squid.statistics.startles_experienced, 1)

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
