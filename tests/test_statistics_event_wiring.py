import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.brain_about_tab import AboutTab
from src.brain_widget import BrainWidget
from src.interactions import RockInteractionManager
from src.interactions2 import PoopInteractionManager
from src.neurogenesis import EnhancedNeurogenesis
from src.squid import Squid
from src.squid_statistics import SquidStatistics
from src.tamagotchi_logic import TamagotchiLogic


class RecordingSignal:
    def __init__(self):
        self.events = []

    def emit(self, neuron_name):
        self.events.append(neuron_name)


class ConnectableSignal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self, slot):
        try:
            self.slots.remove(slot)
        except ValueError as error:
            raise TypeError("slot is not connected") from error

    def emit(self, *args):
        for slot in list(self.slots):
            slot(*args)


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
    def test_live_neurogenesis_triggers_update_lifetime_peaks(self):
        squid = FakeSquid()
        squid.anxiety = 80
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.neurogenesis_triggers = {
            "novel_objects": 1.5,
            "high_stress_cycles": 20,
            "positive_outcomes": 3,
        }
        logic.new_object_encountered = True
        logic.recent_positive_outcome = True
        logic.add_thought = Mock()
        logic.debug_mode = False

        with patch("src.tamagotchi_logic.random.random", return_value=1):
            logic.track_neurogenesis_triggers()

        self.assertEqual(squid.statistics.peak_novelty, 2.5)
        self.assertEqual(squid.statistics.peak_stress, 2.1)
        self.assertEqual(squid.statistics.peak_reward, 4)

        squid.anxiety = 10
        logic.new_object_encountered = False
        logic.recent_positive_outcome = False
        logic.track_neurogenesis_triggers()

        self.assertEqual(squid.statistics.peak_novelty, 2.5)
        self.assertEqual(squid.statistics.peak_stress, 2.1)
        self.assertEqual(squid.statistics.peak_reward, 4)

    def test_stop_disconnects_the_old_neurogenesis_listener(self):
        signal = ConnectableSignal()
        old_logic = object.__new__(TamagotchiLogic)
        new_logic = object.__new__(TamagotchiLogic)
        old_handler = Mock()
        new_handler = Mock()
        old_logic._on_neurogenesis_icon_and_memory = old_handler
        new_logic._on_neurogenesis_icon_and_memory = new_handler
        old_logic.brain_window = SimpleNamespace(
            brain_widget=SimpleNamespace(neuronCreated=signal),
        )
        signal.connect(old_handler)
        signal.connect(new_handler)

        old_logic.stop()
        old_logic.stop()
        signal.emit("novelty_after_restart")

        old_handler.assert_not_called()
        new_handler.assert_called_once_with("novelty_after_restart")

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

    def test_synchronous_fallback_real_check_creates_one_birth_without_delegating(
        self,
    ):
        signal = RecordingSignal()
        delegated_results = []

        controller = SimpleNamespace(
            _pending_neurogenesis_check=False,
            neuronCreated=signal,
            state={
                "neurogenesis_active": True,
                "anxiety": 95,
                "recent_actions": [],
            },
            _use_threaded_processing=False,
            _on_neurogenesis_complete=delegated_results.append,
            experience_buffer=SimpleNamespace(add_experience=Mock()),
            pruning_enabled=False,
        )
        controller.enhanced_neurogenesis = NotifyingNeurogenesis(
            controller,
            "stress_synchronous",
        )
        controller.check_neurogenesis_triggers = lambda state: (
            BrainWidget.check_neurogenesis_triggers(controller, state)
        )

        with redirect_stdout(io.StringIO()):
            BrainWidget._periodic_neurogenesis_check(controller)

        self.assertEqual(signal.events, ["stress_synchronous"])
        self.assertEqual(delegated_results, [])
        self.assertFalse(controller._pending_neurogenesis_check)

    def test_one_argument_neuron_creation_preserves_compatibility(self):
        squid = FakeSquid()
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.statistics_window = None
        logic.brain_window = SimpleNamespace(statistics_tab=None)

        logic.track_neuron_creation("novelty")

        self.assertEqual(squid.statistics.novelty_neurons_created, 1)
        self.assertEqual(squid.statistics.current_neurons, 9)

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

    def test_discrete_events_do_not_depend_on_statistics_tab(self):
        squid = FakeSquid()
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=None)
        logic.poop_items = [object(), object(), object()]

        logic.track_food_consumed(SimpleNamespace(is_sushi=True))
        logic.track_food_consumed(SimpleNamespace(is_sushi=False))
        logic.track_poop_created()
        logic.track_poop_thrown()
        logic.track_rock_thrown()
        logic.track_plant_interaction()
        logic.track_colour_changed()
        logic.track_distance(80)

        self.assertEqual(squid.statistics.sushi_consumed, 1)
        self.assertEqual(squid.statistics.cheese_consumed, 1)
        self.assertEqual(squid.statistics.poops_created, 1)
        self.assertEqual(squid.statistics.max_poops_cleaned, 3)
        self.assertEqual(squid.statistics.total_poops_thrown, 1)
        self.assertEqual(squid.statistics.total_rocks_thrown, 1)
        self.assertEqual(squid.statistics.plants_interacted, 1)
        self.assertEqual(squid.statistics.times_colour_changed, 1)
        self.assertEqual(squid.statistics.distance_swam, 80)

    def test_real_ink_cloud_path_is_safe_without_statistics_tab(self):
        squid = FakeSquid()
        squid.squid_x = 0
        squid.squid_y = 0
        squid.squid_width = 20
        squid.squid_height = 20
        squid.ui = SimpleNamespace(
            scene=SimpleNamespace(addItem=Mock()),
        )

        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=None)
        logic.statistics_window = SimpleNamespace(award=Mock())

        pixmap = Mock()
        pixmap.width.return_value = 10
        pixmap.height.return_value = 10
        ink_cloud_item = Mock()
        opacity_effect = Mock()
        animation = Mock()

        with (
            patch(
                "src.tamagotchi_logic.QtGui.QPixmap",
                return_value=pixmap,
            ),
            patch(
                "src.tamagotchi_logic.QtWidgets.QGraphicsPixmapItem",
                return_value=ink_cloud_item,
            ),
            patch(
                "src.tamagotchi_logic.QtWidgets.QGraphicsOpacityEffect",
                return_value=opacity_effect,
            ),
            patch(
                "src.tamagotchi_logic.QtCore.QPropertyAnimation",
                return_value=animation,
            ),
            patch(
                "src.tamagotchi_logic.QtCore.QTimer.singleShot"
            ) as single_shot,
        ):
            logic.create_ink_cloud()

        self.assertEqual(squid.statistics.ink_clouds_created, 1)
        logic.statistics_window.award.assert_called_once_with(-250)
        squid.ui.scene.addItem.assert_called_once_with(ink_cloud_item)
        single_shot.assert_called_once()
        self.assertEqual(single_shot.call_args.args[0], 10000)

    def test_legacy_peak_memory_and_age_updates_are_model_owned(self):
        squid = FakeSquid()
        squid.memory_manager = SimpleNamespace(
            short_term_memory=[1, 2, 3],
            long_term_memory=[1, 2, 3, 4],
        )
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=None)

        logic.update_squid_age()
        logic.update_highest_anxiety(75)
        logic.update_highest_anxiety(50)
        logic.update_lowest_happiness(20)
        logic.update_lowest_happiness(40)
        logic.update_max_memories()

        squid.memory_manager.short_term_memory.clear()
        squid.memory_manager.long_term_memory.clear()
        logic.update_max_memories()

        persisted = squid.statistics.to_dict()
        self.assertEqual(persisted["highest_anxiety"], 75)
        self.assertEqual(persisted["lowest_happiness"], 20)
        self.assertEqual(persisted["max_short_term_memories"], 3)
        self.assertEqual(persisted["max_long_term_memories"], 4)

    def test_rock_throw_delivers_one_model_event(self):
        squid = FakeSquid()
        rock_rect = SimpleNamespace(
            width=lambda: 2,
            height=lambda: 4,
        )
        rock = SimpleNamespace(
            filename="rock.png",
            setParentItem=Mock(),
            boundingRect=lambda: rock_rect,
            setPos=Mock(),
            setVisible=Mock(),
        )
        squid.carried_rock = rock
        squid.status = "roaming"
        squid.happiness = 50
        squid.satisfaction = 50
        squid.anxiety = 50
        squid.squid_item = SimpleNamespace(
            sceneBoundingRect=lambda: SimpleNamespace(
                center=lambda: SimpleNamespace(
                    x=lambda: 10,
                    y=lambda: 20,
                )
            )
        )
        squid.memory_manager = SimpleNamespace(
            add_short_term_memory=Mock(),
        )

        statistics_tab = SimpleNamespace(
            increment_stat=lambda name, amount=1: squid.statistics.increment(
                name,
                amount,
            ),
            update_statistics=Mock(),
        )
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=statistics_tab)
        logic.statistics_window = SimpleNamespace(award=Mock())

        manager = object.__new__(RockInteractionManager)
        manager.squid = squid
        manager.logic = logic
        manager.rock_config = {
            "happiness_boost": 5,
            "satisfaction_boost": 3,
            "anxiety_reduction": 2,
        }
        manager.throw_animation_timer = Mock()
        manager.throw_animation_timer.isActive.return_value = False
        manager.multiplayer_plugin = None

        self.assertTrue(manager.throw_rock())
        self.assertEqual(squid.statistics.total_rocks_thrown, 1)
        statistics_tab.update_statistics.assert_called_once_with()

    def test_poop_throw_delivers_one_model_event(self):
        squid = FakeSquid()
        poop_rect = SimpleNamespace(
            width=lambda: 2,
            height=lambda: 4,
        )
        poop = SimpleNamespace(
            filename="poop.png",
            setParentItem=Mock(),
            boundingRect=lambda: poop_rect,
            setPos=Mock(),
            setVisible=Mock(),
        )
        squid.carried_poop = poop
        squid.status = "roaming"
        squid.happiness = 50
        squid.satisfaction = 50
        squid.anxiety = 50
        squid.squid_item = SimpleNamespace(
            sceneBoundingRect=lambda: SimpleNamespace(
                center=lambda: SimpleNamespace(
                    x=lambda: 10,
                    y=lambda: 20,
                )
            )
        )
        squid.memory_manager = SimpleNamespace(
            add_short_term_memory=Mock(),
        )

        statistics_tab = SimpleNamespace(update_statistics=Mock())
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=statistics_tab)
        logic.statistics_window = SimpleNamespace(award=Mock())

        manager = object.__new__(PoopInteractionManager)
        manager.squid = squid
        manager.logic = logic
        manager.poop_config = {}
        manager.throw_animation_timer = Mock()
        manager.throw_animation_timer.isActive.return_value = False
        manager.multiplayer_plugin = None

        self.assertTrue(manager.throw_poop())
        self.assertEqual(squid.statistics.total_poops_thrown, 1)
        statistics_tab.update_statistics.assert_called_once_with()

    def test_plant_completion_delivers_one_model_event(self):
        squid = FakeSquid()
        squid.curiosity = 10
        squid.memory_manager = SimpleNamespace(
            add_short_term_memory=Mock(),
            add_long_term_memory=Mock(),
            plant_interaction_count={},
        )
        squid.push_animation = object()

        statistics_tab = SimpleNamespace(
            increment_stat=Mock(),
            update_statistics=Mock(),
        )
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=statistics_tab)
        logic.recent_positive_outcome = False
        logic.show_message = Mock()
        squid.tamagotchi_logic = logic

        Squid._on_push_complete(
            squid,
            SimpleNamespace(category="plant", filename="fern.png"),
        )
        Squid._on_push_complete(
            squid,
            SimpleNamespace(category="rock", filename="rock.png"),
        )

        self.assertEqual(squid.statistics.plants_interacted, 1)
        statistics_tab.increment_stat.assert_not_called()
        statistics_tab.update_statistics.assert_called_once_with()

    def test_colour_change_delivers_one_model_event_without_tab(self):
        squid = FakeSquid()
        squid.apply_tint = Mock()
        logic = object.__new__(TamagotchiLogic)
        logic.squid = squid
        logic.brain_window = SimpleNamespace(statistics_tab=None)
        controller = SimpleNamespace(tamagotchi_logic=logic)
        colour = SimpleNamespace(isValid=lambda: True)

        with patch(
            "src.brain_about_tab.QtWidgets.QColorDialog.getColor",
            return_value=colour,
        ):
            AboutTab.open_color_picker(controller)

        squid.apply_tint.assert_called_once_with(colour)
        self.assertEqual(squid.statistics.times_colour_changed, 1)

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

    def test_click_wake_records_one_accepted_startle(self):
        squid = object.__new__(Squid)
        squid.is_sleeping = True
        squid.happiness = 90
        squid.anxiety = 10
        squid.status = "sleeping"
        squid.statistics_window = SimpleNamespace(award=Mock())
        squid.tamagotchi_logic = SimpleNamespace(
            track_startle=Mock(),
            show_message=Mock(),
            create_ink_cloud=Mock(),
        )
        squid.show_startled_icon = Mock()

        with (
            patch("src.squid.random.random", return_value=1.0),
            patch("src.squid.QtCore.QTimer"),
        ):
            squid.startle_awake()
            squid.startle_awake()

        self.assertFalse(squid.is_sleeping)
        squid.tamagotchi_logic.track_startle.assert_called_once_with()

    def test_poop_is_counted_only_after_a_successful_spawn(self):
        for created in (False, True):
            with self.subTest(created=created):
                squid = object.__new__(Squid)
                squid.squid_x = 100
                squid.squid_y = 200
                squid.squid_width = 20
                squid.squid_height = 30
                squid.tamagotchi_logic = SimpleNamespace(
                    spawn_poop=Mock(return_value=created),
                    track_poop_created=Mock(),
                )

                result = squid.create_poop()

                self.assertIs(result, created)
                if created:
                    squid.tamagotchi_logic.track_poop_created.assert_called_once_with()
                else:
                    squid.tamagotchi_logic.track_poop_created.assert_not_called()

    def test_spawn_poop_reports_capacity_rejection(self):
        logic = object.__new__(TamagotchiLogic)
        logic.poop_items = [object()]
        logic.max_poop = 1
        logic.squid = SimpleNamespace()

        self.assertFalse(logic.spawn_poop(100, 200))

    def test_spawn_poop_reports_success_after_scene_insertion(self):
        logic = object.__new__(TamagotchiLogic)
        logic.poop_items = []
        logic.max_poop = 1
        logic.squid = SimpleNamespace(
            poop_images=[object()],
            poop_width=20,
            mark_scene_objects_dirty=Mock(),
        )
        logic.user_interface = SimpleNamespace(
            scene=SimpleNamespace(addItem=Mock()),
        )
        logic.brain_hooks = SimpleNamespace(on_object_spawned=Mock())
        poop_item = SimpleNamespace(setPos=Mock())

        with patch(
            "src.tamagotchi_logic.ResizablePixmapItem",
            return_value=poop_item,
        ):
            created = logic.spawn_poop(100, 200)

        self.assertTrue(created)
        self.assertEqual(logic.poop_items, [poop_item])
        poop_item.setPos.assert_called_once_with(90, 200)
        logic.user_interface.scene.addItem.assert_called_once_with(poop_item)
        logic.brain_hooks.on_object_spawned.assert_called_once_with("poop")
        logic.squid.mark_scene_objects_dirty.assert_called_once_with()

    def test_direct_approach_records_actual_distance(self):
        squid = object.__new__(Squid)
        squid.squid_x = 100
        squid.squid_y = 100
        squid.squid_width = 20
        squid.squid_height = 20
        squid.base_squid_speed = 90
        squid.base_vertical_speed = 45
        squid.animation_speed = 1
        squid.current_frame = 0
        squid.squid_item = SimpleNamespace(
            sceneBoundingRect=lambda: SimpleNamespace(
                center=lambda: SimpleNamespace(
                    x=lambda: 100,
                    y=lambda: 100,
                ),
            ),
            setPos=Mock(),
        )
        squid.ui = SimpleNamespace(window_width=1000, window_height=800)
        squid.update_squid_image = Mock()
        squid.tamagotchi_logic = SimpleNamespace(track_distance=Mock())

        remaining_distance = squid.move_toward_position((300, 100))

        self.assertEqual(remaining_distance, 200)
        self.assertEqual((squid.squid_x, squid.squid_y), (190, 100))
        squid.tamagotchi_logic.track_distance.assert_called_once_with(90)

    def test_diagonal_approach_records_euclidean_distance(self):
        squid = object.__new__(Squid)
        squid.squid_x = 100
        squid.squid_y = 100
        squid.squid_width = 20
        squid.squid_height = 20
        squid.base_squid_speed = 5
        squid.base_vertical_speed = 5
        squid.animation_speed = 1
        squid.current_frame = 0
        squid.squid_item = SimpleNamespace(
            sceneBoundingRect=lambda: SimpleNamespace(
                center=lambda: SimpleNamespace(
                    x=lambda: 100,
                    y=lambda: 100,
                ),
            ),
            setPos=Mock(),
        )
        squid.ui = SimpleNamespace(window_width=1000, window_height=800)
        squid.update_squid_image = Mock()
        squid.tamagotchi_logic = SimpleNamespace(track_distance=Mock())

        remaining_distance = squid.move_toward_position((106, 108))

        self.assertEqual(remaining_distance, 10)
        self.assertEqual((squid.squid_x, squid.squid_y), (103, 104))
        squid.tamagotchi_logic.track_distance.assert_called_once_with(5)

    def test_normal_and_clipped_movement_record_post_clamp_distance(self):
        for direction, start, expected_position, expected_distance in (
            ("down", (100, 100), (100, 145), 45),
            ("right", (840, 100), (850, 100), 10),
        ):
            with self.subTest(direction=direction):
                squid = object.__new__(Squid)
                squid.squid_x, squid.squid_y = start
                squid.squid_width = 100
                squid.squid_height = 20
                squid.base_squid_speed = 90
                squid.base_vertical_speed = 45
                squid.animation_speed = 1
                squid.is_sleeping = False
                squid.squid_direction = direction
                squid.current_frame = 0
                squid.pursuing_food = False
                squid.last_view_cone_change = 0
                squid.view_cone_change_interval = 100_000_000
                squid.ui = SimpleNamespace(
                    window_width=1000,
                    window_height=800,
                )
                squid.tamagotchi_logic = SimpleNamespace(
                    track_distance=Mock(),
                )
                squid.squid_item = SimpleNamespace(
                    setPixmap=Mock(),
                    setPos=Mock(),
                )
                squid.get_visible_food = Mock(return_value=[])
                squid.move_randomly = Mock()
                squid.change_direction = Mock()
                squid.current_image = Mock(return_value=None)
                squid.update_view_cone = Mock()
                squid.update_sick_icon_position = Mock()

                squid.move_squid()

                self.assertEqual(
                    (squid.squid_x, squid.squid_y),
                    expected_position,
                )
                squid.tamagotchi_logic.track_distance.assert_called_once_with(
                    expected_distance,
                )

    def test_sleeping_movement_records_actual_distance(self):
        squid = object.__new__(Squid)
        squid.squid_x = 100
        squid.squid_y = 100
        squid.squid_width = 100
        squid.squid_height = 20
        squid.base_vertical_speed = 45
        squid.animation_speed = 1
        squid.is_sleeping = True
        squid.current_frame = 0
        squid.ui = SimpleNamespace(
            window_width=1000,
            window_height=800,
        )
        squid.tamagotchi_logic = SimpleNamespace(
            track_distance=Mock(),
        )
        squid.squid_item = SimpleNamespace(setPos=Mock())
        squid.update_squid_image = Mock()

        squid.move_squid()

        self.assertEqual((squid.squid_x, squid.squid_y), (100, 145))
        squid.tamagotchi_logic.track_distance.assert_called_once_with(45)


if __name__ == "__main__":
    unittest.main()
