"""
End-to-end behavioural tests for the Dosidicus cognitive loop.

These are deliberately NOT unit tests of individual functions. Each one boots
the real application (offscreen Qt, real TamagotchiLogic / BrainWidget / Squid)
and asserts an observable effect on the squid, because the defects these cover
were all cases where the code existed, was called, and still changed nothing.

Covered:
  1. Synaptic propagation          - a weight produces a downstream activation
  2. Designer neuron control       - a custom neuron drives a real behaviour
  3. Every output handler          - runs against a real squid, no silent break
  4. Save / load                   - an evolved brain survives a round trip
  5. Neurogenesis                  - a generated neuron's activation responds
  6. Designer round trip           - designer -> game preserves net + bindings
  7. Sensor ranges                 - every sensor stays inside its stated range
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt5 import QtWidgets, QtGui  # noqa: E402

APP = None
WINDOW = None
LOGIC = None
BRAIN = None
SQUID = None
_TMPDIR = None
_PREV_CWD = None


def setUpModule():
    """Boot the real application once; every test shares it."""
    global APP, WINDOW, LOGIC, BRAIN, SQUID, _TMPDIR, _PREV_CWD

    _PREV_CWD = os.getcwd()
    os.chdir(_REPO_ROOT)

    # Keep saves out of the working tree and guarantee a fresh simulation.
    _TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-test-")
    from src import save_manager
    _orig_init = save_manager.SaveManager.__init__

    def _tmp_init(self, save_directory="saves"):
        _orig_init(self, os.path.join(_TMPDIR.name, "saves"))

    save_manager.SaveManager.__init__ = _tmp_init

    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    for name in ("question", "information", "critical", "warning"):
        setattr(QtWidgets.QMessageBox, name, staticmethod(lambda *a, **k: 0))
    QtWidgets.QDialog.exec_ = lambda self: 0

    import main as main_module
    WINDOW = main_module.MainWindow(specified_personality=None, debug_mode=False)
    LOGIC = WINDOW.tamagotchi_logic
    BRAIN = WINDOW.brain_window.brain_widget
    SQUID = LOGIC.squid

    # Hebbian learning rewrites weights on a timer; tests assert on exact
    # weights, so pin them for determinism.
    if hasattr(WINDOW.brain_window, "hebbian_timer"):
        WINDOW.brain_window.hebbian_timer.stop()


def tearDownModule():
    try:
        if BRAIN is not None:
            BRAIN.stop_worker()
    except Exception:
        pass
    if _PREV_CWD:
        os.chdir(_PREV_CWD)
    if _TMPDIR is not None:
        _TMPDIR.cleanup()


def tick(n=1):
    for _ in range(n):
        LOGIC.update_simulation()
        APP.processEvents()


class NeuralPipelineTestCase(unittest.TestCase):
    """Shared reset so tests do not leak state into one another."""

    def setUp(self):
        SQUID.is_fleeing = False
        SQUID.is_sleeping = False
        SQUID.is_eating = False
        SQUID.status = "roaming"
        SQUID.happiness = 50.0
        SQUID.curiosity = 50.0
        SQUID.anxiety = 50.0
        SQUID.hunger = 50.0
        SQUID.tint_color = None
        SQUID.current_speed = SQUID.base_speed
        SQUID.pursuing_food = False
        SQUID.neural_drive = None
        LOGIC.neuron_output_monitor.bindings = []

    def add_neuron(self, name, position=(400, 400), activation=50.0):
        BRAIN.neuron_positions[name] = position
        BRAIN.state[name] = activation
        BRAIN.visible_neurons.add(name)
        self.addCleanup(self._drop_neuron, name)
        return name

    def _drop_neuron(self, name):
        BRAIN.neuron_positions.pop(name, None)
        BRAIN.state.pop(name, None)
        BRAIN.visible_neurons.discard(name)
        for key in [k for k in BRAIN.weights if name in k]:
            BRAIN.weights.pop(key, None)

    def bind(self, neuron, hook, threshold=70.0, mode=None, cooldown=0.0, **params):
        from src.brain_neuron_outputs import NeuronOutputBinding, OutputTriggerMode
        binding = NeuronOutputBinding(
            neuron_name=neuron,
            output_hook=hook,
            threshold=threshold,
            trigger_mode=mode or OutputTriggerMode.THRESHOLD_ABOVE,
            cooldown=cooldown,
            hook_params=params,
        )
        LOGIC.neuron_output_monitor.bindings.append(binding)
        return binding


# ---------------------------------------------------------------------------
# 1. Synaptic propagation
# ---------------------------------------------------------------------------
class SynapticPropagationTests(NeuralPipelineTestCase):

    def test_positive_weight_raises_downstream_activation(self):
        """A known source activation and weight must move a downstream neuron."""
        self.add_neuron("prop_target", activation=50.0)
        BRAIN.weights[("anxiety", "prop_target")] = 0.9
        BRAIN.state["anxiety"] = 100.0

        BRAIN.propagate_activations()

        self.assertGreater(
            BRAIN.state["prop_target"], 50.0,
            "excitatory synapse from a saturated source left the target unchanged",
        )

    def test_activation_converges_on_the_transfer_function(self):
        """target == 50 + (source-50)*weight, per FunctionalNeuron semantics."""
        self.add_neuron("prop_converge", activation=50.0)
        BRAIN.weights[("anxiety", "prop_converge")] = 0.8
        BRAIN.state["anxiety"] = 100.0

        for _ in range(40):
            BRAIN.propagate_activations()

        self.assertAlmostEqual(BRAIN.state["prop_converge"], 90.0, delta=0.5)

    def test_negative_weight_is_inhibitory(self):
        self.add_neuron("prop_inhib", activation=50.0)
        BRAIN.weights[("anxiety", "prop_inhib")] = -0.8
        BRAIN.state["anxiety"] = 100.0

        for _ in range(40):
            BRAIN.propagate_activations()

        self.assertAlmostEqual(BRAIN.state["prop_inhib"], 10.0, delta=0.5)

    def test_propagation_never_overwrites_sensors_or_core_stats(self):
        """Inputs are owned by the world; the network must not write them."""
        self.add_neuron("prop_source", activation=100.0)
        BRAIN.weights[("prop_source", "anxiety")] = 1.0
        BRAIN.weights[("prop_source", "can_see_food")] = 1.0
        BRAIN.state["anxiety"] = 20.0
        BRAIN.state["can_see_food"] = 0.0

        BRAIN.propagate_activations()

        self.assertEqual(BRAIN.state["anxiety"], 20.0)
        self.assertEqual(BRAIN.state["can_see_food"], 0.0)

    def test_propagation_runs_as_part_of_the_simulation_tick(self):
        """Not just callable - actually wired into update_simulation()."""
        self.add_neuron("prop_ticked", activation=50.0)
        BRAIN.weights[("anxiety", "prop_ticked")] = 0.9
        SQUID.anxiety = 100.0

        tick(3)

        self.assertGreater(BRAIN.state["prop_ticked"], 55.0)

    def test_there_is_exactly_one_propagation_implementation(self):
        self.assertTrue(hasattr(BRAIN, "propagate_activations"))
        self.assertFalse(
            hasattr(BRAIN, "_perform_state_update_sync"),
            "the unreachable duplicate propagation path is back",
        )


# ---------------------------------------------------------------------------
# 2. Designer neuron control  (the headline capability)
# ---------------------------------------------------------------------------
class DesignerNeuronControlTests(NeuralPipelineTestCase):

    def test_custom_neuron_can_drive_the_squid(self):
        """anxiety -> urge_flee -> neuron_output_flee -> squid actually flees."""
        from src.brain_neuron_outputs import OutputTriggerMode

        self.add_neuron("urge_flee", activation=50.0)
        BRAIN.weights[("anxiety", "urge_flee")] = 0.9
        self.bind("urge_flee", "neuron_output_flee", threshold=80.0,
                  mode=OutputTriggerMode.THRESHOLD_RISING, cooldown=0.0)

        self.assertFalse(SQUID.is_fleeing)
        for _ in range(8):
            SQUID.anxiety = 100.0
            tick()

        self.assertGreater(BRAIN.state["urge_flee"], 80.0,
                           "the custom neuron never reached its threshold")
        self.assertTrue(SQUID.is_fleeing, "the binding fired but the squid did not flee")
        self.assertEqual(SQUID.status, "fleeing")
        self.assertAlmostEqual(SQUID.speed_multiplier(), 2.0, places=2)

    def test_custom_neuron_below_threshold_does_not_fire(self):
        from src.brain_neuron_outputs import OutputTriggerMode

        self.add_neuron("urge_quiet", activation=50.0)
        BRAIN.weights[("anxiety", "urge_quiet")] = 0.1
        self.bind("urge_quiet", "neuron_output_flee", threshold=90.0,
                  mode=OutputTriggerMode.THRESHOLD_RISING)

        # Assert on the BINDING, not on squid.is_fleeing: now that the
        # DecisionEngine drives the squid it can also decide to flee (anxiety
        # pinned at 100 makes that likely), so the flag has two legitimate
        # writers and no longer isolates the binding.
        LOGIC.neuron_output_monitor.total_fires = 0
        for _ in range(8):
            SQUID.anxiety = 100.0
            tick()

        self.assertLess(BRAIN.state["urge_quiet"], 90.0)
        self.assertEqual(LOGIC.neuron_output_monitor.total_fires, 0,
                         "a sub-threshold neuron fired its binding")

    def test_inhibited_neuron_controls_a_different_actuator(self):
        """A second full path, to show the mechanism is general."""
        self.add_neuron("urge_happy", activation=50.0)
        BRAIN.weights[("curiosity", "urge_happy")] = 1.0
        self.bind("urge_happy", "neuron_output_boost_happiness", threshold=60.0)

        SQUID.happiness = 20.0
        for _ in range(6):
            SQUID.curiosity = 100.0
            tick()

        self.assertGreater(BRAIN.state["urge_happy"], 60.0)
        self.assertGreater(SQUID.happiness, 20.0)


# ---------------------------------------------------------------------------
# 3. Every exposed output handler
# ---------------------------------------------------------------------------
class OutputHandlerTests(NeuralPipelineTestCase):

    def test_every_offered_hook_has_a_subscribed_handler(self):
        from src.brain_neuron_outputs import get_available_output_hooks
        for hook in get_available_output_hooks():
            with self.subTest(hook=hook):
                subs = LOGIC.plugin_manager.hooks.get(hook, [])
                self.assertTrue(subs, f"{hook} is offered to the user but has no handler")

    def test_handlers_are_subscribed_exactly_once(self):
        """A duplicate subscription doubled every stat change."""
        from src.brain_neuron_outputs import STANDARD_OUTPUT_HOOKS
        for hook in STANDARD_OUTPUT_HOOKS:
            with self.subTest(hook=hook):
                mine = [s for s in LOGIC.plugin_manager.hooks.get(hook, [])
                        if s["plugin"] == "NeuronOutputMonitor"]
                self.assertLessEqual(len(mine), 1)

    def test_hooks_without_a_handler_are_hidden_from_the_designer(self):
        from src.brain_neuron_outputs import (
            STANDARD_OUTPUT_HOOKS, get_available_output_hooks)
        offered = get_available_output_hooks()
        for hook, info in STANDARD_OUTPUT_HOOKS.items():
            if info.get("requires_plugin") and not LOGIC.plugin_manager.hooks.get(hook):
                self.assertNotIn(hook, offered,
                                 f"{hook} has no handler yet is still selectable")

    def test_no_handler_raises_against_a_real_squid(self):
        from src.brain_neuron_outputs import STANDARD_OUTPUT_HOOKS
        for hook in sorted(STANDARD_OUTPUT_HOOKS):
            subs = [s for s in LOGIC.plugin_manager.hooks.get(hook, [])
                    if s["plugin"] == "NeuronOutputMonitor"]
            if not subs:
                continue
            with self.subTest(hook=hook):
                try:
                    subs[0]["callback"](neuron_name="probe", activation=95.0,
                                        threshold=50.0, squid=SQUID,
                                        tamagotchi_logic=LOGIC)
                except Exception as exc:  # pragma: no cover - this is the assertion
                    self.fail(f"{hook} raised {type(exc).__name__}: {exc}")

    def test_stat_handlers_apply_their_documented_magnitude(self):
        SQUID.happiness = 50.0
        LOGIC.plugin_manager.trigger_hook(
            "neuron_output_boost_happiness", neuron_name="p", activation=80.0,
            threshold=50.0, squid=SQUID, tamagotchi_logic=LOGIC)
        self.assertAlmostEqual(SQUID.happiness, 50.0 + (80.0 / 100.0) * 5, places=4)

    def test_reduce_anxiety_relief_scales_with_activation(self):
        """Stronger firing must mean more relief, not less."""
        SQUID.anxiety = 80.0
        LOGIC.plugin_manager.trigger_hook(
            "neuron_output_reduce_anxiety", neuron_name="p", activation=20.0,
            threshold=50.0, squid=SQUID, tamagotchi_logic=LOGIC)
        weak_drop = 80.0 - SQUID.anxiety

        SQUID.anxiety = 80.0
        LOGIC.plugin_manager.trigger_hook(
            "neuron_output_reduce_anxiety", neuron_name="p", activation=100.0,
            threshold=50.0, squid=SQUID, tamagotchi_logic=LOGIC)
        strong_drop = 80.0 - SQUID.anxiety

        self.assertGreater(strong_drop, weak_drop)

    def test_movement_hooks_install_a_neural_drive(self):
        """Movement outputs must reach move_squid, not be overwritten by it."""
        SQUID.neural_drive = None
        LOGIC.plugin_manager.trigger_hook(
            "neuron_output_wander", neuron_name="p", activation=90.0,
            threshold=50.0, squid=SQUID, tamagotchi_logic=LOGIC)
        drive = SQUID.get_neural_drive()
        self.assertIsNotNone(drive)
        self.assertEqual(drive["action"], "wander")

    def test_movement_drives_actually_move_the_squid_toward_a_target(self):
        """A drive must steer movement, not just be recorded."""
        import math

        # The offscreen window is smaller than the squid, so boundary clamping
        # would dominate; give the tank a realistic size for this test.
        prev = (SQUID.ui.window_width, SQUID.ui.window_height)
        SQUID.ui.window_width, SQUID.ui.window_height = 1280, 900
        self.addCleanup(lambda: setattr(SQUID.ui, "window_width", prev[0]))
        self.addCleanup(lambda: setattr(SQUID.ui, "window_height", prev[1]))

        target = (900.0, 620.0)

        def distance():
            return math.hypot(target[0] - (SQUID.squid_x + SQUID.squid_width / 2),
                              target[1] - (SQUID.squid_y + SQUID.squid_height / 2))

        for action in ("seek_food", "seek_plant", "approach_rock"):
            with self.subTest(action=action):
                SQUID.squid_x, SQUID.squid_y = 200.0, 300.0
                SQUID.squid_item.setPos(SQUID.squid_x, SQUID.squid_y)
                start = distance()
                for _ in range(12):
                    SQUID.set_neural_drive(action, duration=6.0, target=target)
                    SQUID.move_squid()
                self.assertLess(distance(), start - 20,
                                f"{action} drive did not move the squid toward its target")

    def test_neural_drive_expires(self):
        """A one-shot firing must not trap the squid in a permanent state."""
        SQUID.set_neural_drive("wander", duration=0.15)
        self.assertIsNotNone(SQUID.get_neural_drive())
        import time as _time
        _time.sleep(0.2)
        self.assertIsNone(SQUID.get_neural_drive())

    def test_bindings_fire_without_the_plugin_enable_gate(self):
        """The monitor is engine, not plugin: clearing plugins must not mute it."""
        LOGIC.plugin_manager.enabled_plugins.clear()
        SQUID.happiness = 10.0
        self.add_neuron("gate_probe", activation=100.0)
        self.bind("gate_probe", "neuron_output_boost_happiness", threshold=50.0)

        LOGIC.neuron_output_monitor.process_outputs()

        self.assertGreater(SQUID.happiness, 10.0)


# ---------------------------------------------------------------------------
# 4. Save / load of an evolved brain
# ---------------------------------------------------------------------------
class PersistenceTests(NeuralPipelineTestCase):

    def test_evolved_brain_survives_a_round_trip(self):
        from src.brain_neuron_outputs import OutputTriggerMode

        self.add_neuron("persist_neuron", position=(321, 654), activation=50.0)
        BRAIN.weights[("anxiety", "persist_neuron")] = 0.77
        self.bind("persist_neuron", "neuron_output_flee", threshold=64.0,
                  mode=OutputTriggerMode.THRESHOLD_BELOW, cooldown=2.5,
                  red=1, green=2, blue=3)

        before_positions = set(BRAIN.neuron_positions)
        before_weights = dict(BRAIN.weights)
        before_functional = set(BRAIN.enhanced_neurogenesis.functional_neurons)

        LOGIC.save_game(is_autosave=False)
        LOGIC.load_game()

        self.assertEqual(set(BRAIN.neuron_positions), before_positions)
        self.assertEqual(BRAIN.weights, before_weights)
        self.assertEqual(BRAIN.weights[("anxiety", "persist_neuron")], 0.77)
        self.assertTrue(before_functional <= set(BRAIN.enhanced_neurogenesis.functional_neurons))

    def test_cognitive_history_survives_a_round_trip(self):
        """A save file is a cognitive history, or it is just a snapshot.

        The weights alone tell you what the squid became; the provenance tells
        you why, and that is the thing the project is actually about.
        """
        self.add_neuron("provenance_neuron", position=(222, 333))
        BRAIN.apply_weight_change(("anxiety", "provenance_neuron"), value=0.42,
                                  mechanism='hebbian',
                                  detail={'correlation': 0.55, 'samples': 123})
        BRAIN.ledger.record_neuron_birth(
            "provenance_neuron", 'representation',
            "nothing in the network told this situation apart",
            remedy="fire when it happens", neuron_type='novelty',
            specialization='general_novelty_processing',
            display_name='Novelty: General Novelty Processing')

        before = BRAIN.ledger.summary()
        before_reason = BRAIN.explain_weight(("anxiety", "provenance_neuron"))

        LOGIC.save_game(is_autosave=False)
        LOGIC.load_game()

        after = BRAIN.ledger.summary()
        self.assertEqual(after['weight_changes'], before['weight_changes'])
        self.assertIn("provenance_neuron", BRAIN.ledger.origins)
        self.assertIn("123 observations",
                      BRAIN.explain_weight(("anxiety", "provenance_neuron")))
        self.assertIn("kept happening together", before_reason)

    def test_a_grown_neuron_can_always_say_why_it_exists(self):
        neuro = BRAIN.enhanced_neurogenesis
        name = neuro.create_neuron("novelty", brain_state=dict(BRAIN.state),
                                   environment={})
        if name is None:
            self.skipTest("novelty neuron capped by neurogenesis limits")
        self.addCleanup(self._drop_neuron, name)

        answer = BRAIN.explain_neuron(name)
        self.assertTrue(answer)
        self.assertNotIn("There is no neuron", answer)
        self.assertIn("grown", answer.lower())

    def test_every_weight_change_lands_in_the_ledger(self):
        """Nothing may move a synapse without saying why."""
        self.add_neuron("audited_neuron")
        before = BRAIN.ledger.summary()['weight_changes']
        BRAIN.apply_weight_change(("anxiety", "audited_neuron"), value=0.3,
                                  mechanism='designer')
        BRAIN.strengthen_connection("anxiety", "audited_neuron", 0.1)
        BRAIN.remove_weight(("anxiety", "audited_neuron"), reason="test cleanup")
        self.assertEqual(BRAIN.ledger.summary()['weight_changes'], before + 3)

    def test_output_bindings_survive_a_round_trip(self):
        from src.brain_neuron_outputs import OutputTriggerMode

        self.add_neuron("persist_bind", activation=50.0)
        self.bind("persist_bind", "neuron_output_change_color", threshold=41.0,
                  mode=OutputTriggerMode.THRESHOLD_BELOW, cooldown=3.0,
                  red=10, green=20, blue=30)

        LOGIC.save_game(is_autosave=False)
        LOGIC.load_game()

        bindings = LOGIC.neuron_output_monitor.bindings
        self.assertEqual(len(bindings), 1)
        restored = bindings[0]
        self.assertEqual(restored.neuron_name, "persist_bind")
        self.assertEqual(restored.output_hook, "neuron_output_change_color")
        self.assertEqual(restored.threshold, 41.0)
        self.assertEqual(restored.trigger_mode, OutputTriggerMode.THRESHOLD_BELOW)
        self.assertEqual(restored.cooldown, 3.0)
        self.assertEqual(restored.hook_params, {"red": 10, "green": 20, "blue": 30})

    def test_saved_brain_state_carries_the_bindings_key(self):
        self.add_neuron("persist_key", activation=50.0)
        self.bind("persist_key", "neuron_output_flee")
        state = WINDOW.brain_window.get_brain_state()
        self.assertIn("output_bindings", state)
        self.assertEqual(len(state["output_bindings"]), 1)

    def test_core_stats_are_restored_from_the_squid_on_load(self):
        LOGIC.save_game(is_autosave=False)
        LOGIC.load_game()
        for stat in ("hunger", "happiness", "anxiety", "curiosity"):
            self.assertIn(stat, BRAIN.state)

    def test_sensors_are_not_promoted_to_functional_neurons(self):
        LOGIC.save_game(is_autosave=False)
        LOGIC.load_game()
        functional = set(BRAIN.enhanced_neurogenesis.functional_neurons)
        from src.brain_constants import NON_PROPAGATED_NEURONS
        self.assertFalse(functional & NON_PROPAGATED_NEURONS)

    def test_widget_bindings_mirror_the_monitor(self):
        """One source of truth: no second copy to drift out of date."""
        self.add_neuron("persist_mirror", activation=50.0)
        self.bind("persist_mirror", "neuron_output_flee")
        self.assertEqual(len(BRAIN.output_bindings),
                         len(LOGIC.neuron_output_monitor.bindings))
        LOGIC.neuron_output_monitor.clear_bindings()
        self.assertEqual(BRAIN.output_bindings, [])


# ---------------------------------------------------------------------------
# 5. Neurogenesis
# ---------------------------------------------------------------------------
class NeurogenesisTests(NeuralPipelineTestCase):

    def test_generated_neuron_activation_responds_to_its_inputs(self):
        neuro = BRAIN.enhanced_neurogenesis
        name = neuro.create_neuron("stress", brain_state=dict(BRAIN.state),
                                   environment={})
        self.assertIsNotNone(name, "neurogenesis did not create a neuron")
        self.addCleanup(self._drop_neuron, name)

        # Drive it from a single known synapse.
        for key in [k for k in BRAIN.weights if k[1] == name]:
            BRAIN.weights.pop(key)
        BRAIN.weights[("anxiety", name)] = 0.9
        BRAIN.state[name] = 50.0
        BRAIN.state["anxiety"] = 100.0

        for _ in range(40):
            BRAIN.propagate_activations()

        self.assertGreater(BRAIN.state[name], 80.0,
                           "a neurogenesis neuron stayed frozen at its birth value")

    def test_generated_neuron_participates_in_the_tick(self):
        neuro = BRAIN.enhanced_neurogenesis
        name = neuro.create_neuron("novelty", brain_state=dict(BRAIN.state),
                                   environment={})
        if name is None:
            self.skipTest("novelty neuron capped by neurogenesis limits")
        self.addCleanup(self._drop_neuron, name)

        for key in [k for k in BRAIN.weights if k[1] == name]:
            BRAIN.weights.pop(key)
        BRAIN.weights[("anxiety", name)] = 0.9
        BRAIN.state[name] = 50.0

        start = BRAIN.state[name]
        for _ in range(6):
            SQUID.anxiety = 100.0
            tick()

        self.assertNotAlmostEqual(BRAIN.state[name], start, places=3)


# ---------------------------------------------------------------------------
# 5b. Acquiring a concrete fact, and explaining it
# ---------------------------------------------------------------------------
class ConcreteKnowledgeTests(NeuralPipelineTestCase):
    """The headline claim: it learns something nameable, and can say why."""

    EDGE = ("can_see_food", "satisfaction")

    def _live(self, kind, ticks=600):
        """Run a controlled life and return the synapse it produced.

        kind='cared'  - seeing food is followed by satisfaction rising
        kind='harmed' - seeing food is followed by satisfaction falling
        """
        BRAIN.weights[self.EDGE] = 0.0
        BRAIN.ledger.reset()
        BRAIN.plasticity.reset()
        for i in range(ticks):
            seeing = (i % 12) < 4
            BRAIN.state["can_see_food"] = 100.0 if seeing else 0.0
            good = seeing if kind == "cared" else not seeing
            SQUID.satisfaction = 80.0 if good else 25.0
            BRAIN.state["satisfaction"] = SQUID.satisfaction
            BRAIN.observe_for_learning()
            if i % 40 == 39:
                BRAIN.perform_hebbian_learning()
        return BRAIN.weights.get(self.EDGE, 0.0)

    def test_the_same_brain_learns_opposite_things_from_opposite_lives(self):
        cared = self._live("cared")
        harmed = self._live("harmed")
        self.assertGreater(cared, 0.15,
                           "a squid fed whenever it saw food learned nothing good about food")
        self.assertLess(harmed, -0.15,
                        "a squid that suffered whenever it saw food learned no aversion")

    def test_the_learned_fact_can_be_explained_in_plain_english(self):
        self._live("cared")
        knowledge = [k for k in BRAIN.what_do_you_know("food") if k.edge == self.EDGE]
        self.assertTrue(knowledge, "the squid cannot say what it learned about food")
        item = knowledge[0]
        self.assertIn("can see food", item.statement.lower())
        self.assertIn("goes up", item.statement)
        self.assertTrue(item.experience, "no experience was named")
        self.assertIn("correlation", item.reason)
        self.assertGreater(item.confidence, 0.5)

    def test_every_individual_weight_change_behind_it_is_recoverable(self):
        final = self._live("cared")
        history = BRAIN.ledger.weight_history(self.EDGE, limit=50)
        self.assertGreater(len(history), 3,
                           "the changes that produced the fact were not recorded")

        # The recorded steps must actually add up to the weight it now has.
        self.assertAlmostEqual(history[-1].new_weight, final, places=6)
        for event in history:
            self.assertEqual(event.mechanism, "hebbian")
            self.assertIsNotNone(event.detail.get("correlation"))
            self.assertTrue(event.detail.get("samples"))

        answer = BRAIN.explain_weight(self.EDGE)
        self.assertIn("0.000", answer)
        self.assertIn("kept happening together", answer)
        self.assertIn("observations", answer)

    def test_the_laboratory_reconstructs_the_same_account(self):
        """The inspection tool must read the brain, not re-derive it."""
        from src.laboratory import NeuronLaboratory

        self._live("cared")
        lab = NeuronLaboratory(BRAIN)
        lab.select_neuron_by_name("satisfaction")
        APP.processEvents()

        shown = []
        for i in range(lab.inspector_lay.count()):
            widget = lab.inspector_lay.itemAt(i).widget()
            if widget is None:
                continue
            shown.extend(label.text() for label in widget.findChildren(QtWidgets.QLabel))
        blob = " ".join(shown)

        self.assertIn("can_see_food", blob, "the synapse is missing from the inspector")
        self.assertIn("kept happening together", blob,
                      "the Laboratory shows the weight but not why it is that value")


# ---------------------------------------------------------------------------
# 6. Designer round trip
# ---------------------------------------------------------------------------
class DesignerRoundTripTests(NeuralPipelineTestCase):

    def test_designer_to_game_preserves_network_and_bindings(self):
        from src.designer_core import DesignerNeuron, DesignerConnection
        from src.designer_constants import NeuronType
        from src.brain_neuron_outputs import NeuronOutputBinding, OutputTriggerMode

        window = WINDOW.brain_window
        window.switch_to_designer_mode()
        designer = window.designer_view
        self.assertIsNotNone(designer)

        try:
            designer.design.add_neuron(
                DesignerNeuron(name="rt_neuron", neuron_type=NeuronType.HIDDEN,
                               position=(360, 360)))
            designer.design.connections.append(
                DesignerConnection("anxiety", "rt_neuron", 0.8))
            designer.outputs_panel.bindings.append(
                NeuronOutputBinding("rt_neuron", "neuron_output_boost_curiosity",
                                    60.0, OutputTriggerMode.THRESHOLD_ABOVE, 0.0))
        finally:
            window.switch_to_game_mode()

        self.addCleanup(self._drop_neuron, "rt_neuron")

        self.assertIn("rt_neuron", BRAIN.neuron_positions)
        self.assertIn("rt_neuron", BRAIN.visible_neurons,
                      "a Designer neuron that the renderer will never draw")
        self.assertEqual(BRAIN.weights.get(("anxiety", "rt_neuron")), 0.8)
        self.assertEqual(set(BRAIN.connections), set(BRAIN.weights.keys()))
        self.assertEqual(
            [(b.neuron_name, b.output_hook) for b in LOGIC.neuron_output_monitor.bindings],
            [("rt_neuron", "neuron_output_boost_curiosity")])

    def test_round_tripped_neuron_then_controls_the_squid(self):
        """The whole point: build it in the Designer, watch it work."""
        SQUID.curiosity = 10.0
        self.add_neuron("rt_live", activation=50.0)
        BRAIN.weights[("anxiety", "rt_live")] = 1.0
        self.bind("rt_live", "neuron_output_boost_curiosity", threshold=70.0)

        for _ in range(8):
            SQUID.anxiety = 100.0
            tick()

        self.assertGreater(BRAIN.state["rt_live"], 70.0)
        self.assertGreater(SQUID.curiosity, 10.0)


# ---------------------------------------------------------------------------
# 7a. Behaviour arbitration: urge > innate food reflex > decision > wander
# ---------------------------------------------------------------------------
class BehaviourArbitrationTests(NeuralPipelineTestCase):
    """The squid is driven by the DecisionEngine, output bindings override it,
    and seeing food in the view cone is an innate reflex that needs no brain."""

    def setUp(self):
        super().setUp()
        import math
        self._prev_window = (SQUID.ui.window_width, SQUID.ui.window_height)
        SQUID.ui.window_width, SQUID.ui.window_height = 1280, 900
        self.addCleanup(lambda: setattr(SQUID.ui, "window_width", self._prev_window[0]))
        self.addCleanup(lambda: setattr(SQUID.ui, "window_height", self._prev_window[1]))
        SQUID.neural_drive = None
        SQUID.squid_x, SQUID.squid_y = 300.0, 300.0
        SQUID.squid_item.setPos(SQUID.squid_x, SQUID.squid_y)

    def _place_food(self, dx=300.0, dy=0.0):
        import math
        point = (SQUID.squid_x + SQUID.squid_width / 2 + dx,
                 SQUID.squid_y + SQUID.squid_height / 2 + dy)
        SQUID.get_visible_food = lambda: [point]
        self.addCleanup(lambda: SQUID.__dict__.pop("get_visible_food", None))

        def distance():
            return math.hypot(point[0] - (SQUID.squid_x + SQUID.squid_width / 2),
                              point[1] - (SQUID.squid_y + SQUID.squid_height / 2))
        return point, distance

    # -- tier 3 -------------------------------------------------------------
    def test_decision_engine_drives_the_squid(self):
        result = LOGIC.run_decision_engine()
        self.assertIsInstance(result, str)
        drive = SQUID.get_neural_drive()
        self.assertIsNotNone(drive, "the engine made a decision but installed no drive")
        self.assertEqual(drive["priority"], SQUID.DRIVE_DECISION)

    def test_engine_decision_reaches_squid_status(self):
        SQUID.is_eating = False
        result = LOGIC.run_decision_engine()
        self.assertEqual(SQUID.status, result)

    def test_engine_is_skipped_while_a_drive_is_running(self):
        """Gives a decision time to play out instead of dithering every tick."""
        LOGIC.run_decision_engine()
        self.assertIsNotNone(SQUID.get_neural_drive())
        self.assertIsNone(LOGIC.run_decision_engine())

    # -- tier 1 -------------------------------------------------------------
    def test_urge_overrides_a_decision(self):
        LOGIC.run_decision_engine()
        self.assertEqual(SQUID.get_neural_drive()["priority"], SQUID.DRIVE_DECISION)

        LOGIC.plugin_manager.trigger_hook(
            "neuron_output_flee", neuron_name="p", activation=95.0,
            threshold=50.0, squid=SQUID, tamagotchi_logic=LOGIC)

        drive = SQUID.get_neural_drive()
        self.assertEqual(drive["action"], "flee")
        self.assertEqual(drive["priority"], SQUID.DRIVE_URGE)
        self.assertTrue(SQUID.has_urge())

    def test_a_decision_cannot_displace_a_running_urge(self):
        SQUID.set_neural_drive("flee", duration=5.0, priority=SQUID.DRIVE_URGE)
        SQUID.set_neural_drive("wander", duration=5.0, priority=SQUID.DRIVE_DECISION)
        drive = SQUID.get_neural_drive()
        self.assertEqual(drive["action"], "flee")
        self.assertEqual(drive["priority"], SQUID.DRIVE_URGE)

    def test_engine_does_not_run_while_an_urge_holds(self):
        SQUID.set_neural_drive("flee", duration=5.0, priority=SQUID.DRIVE_URGE)
        self.assertIsNone(LOGIC.run_decision_engine())

    # -- tier 2 -------------------------------------------------------------
    def test_innate_food_reflex_needs_no_brain(self):
        """No bindings, no decision - just a view cone and food."""
        SQUID.neural_drive = None
        LOGIC.neuron_output_monitor.bindings = []
        _, distance = self._place_food()
        start = distance()
        for _ in range(8):
            SQUID.move_squid()
        self.assertLess(distance(), start - 20)
        self.assertTrue(SQUID.pursuing_food)

    def test_food_reflex_interrupts_deliberation(self):
        LOGIC.run_decision_engine()
        self.assertEqual(SQUID.get_neural_drive()["priority"], SQUID.DRIVE_DECISION)
        _, distance = self._place_food()
        start = distance()
        for _ in range(8):
            SQUID.move_squid()
        self.assertLess(distance(), start - 20,
                        "a deliberate drive suppressed the innate food reflex")

    def test_urge_overrides_even_the_food_reflex(self):
        point, distance = self._place_food()
        away = (SQUID.squid_x - 250, SQUID.squid_y)
        SQUID.set_neural_drive("seek_plant", duration=8.0, target=away,
                               priority=SQUID.DRIVE_URGE)
        start = distance()
        for _ in range(8):
            SQUID.move_squid()
        self.assertGreater(distance(), start,
                           "an irresistible urge lost to the food reflex")

    # -- tuning -------------------------------------------------------------
    def test_a_neutral_squid_does_not_choose_sleep(self):
        """The sleeping weight used to beat everything at sleepiness 50."""
        SQUID.is_sleeping = False
        SQUID.hunger, SQUID.sleepiness, SQUID.anxiety = 40.0, 50.0, 20.0
        SQUID.curiosity, SQUID.satisfaction = 60.0, 55.0
        BRAIN.update_state({"hunger": 40.0, "sleepiness": 50.0, "anxiety": 20.0,
                            "curiosity": 60.0, "satisfaction": 55.0,
                            "can_see_food": 0.0})
        SQUID.make_decision()
        weights = SQUID._decision_engine.get_decision_data()["base_weights"]
        self.assertEqual(weights["sleeping"], 0.0)
        self.assertGreater(max(weights["exploring"], weights["playing"]), 0.0)
        SQUID.is_sleeping = False

    def test_a_drowsy_squid_does_choose_sleep(self):
        SQUID.is_sleeping = False
        SQUID.hunger, SQUID.sleepiness, SQUID.anxiety = 40.0, 90.0, 20.0
        SQUID.curiosity, SQUID.satisfaction = 60.0, 55.0
        BRAIN.update_state({"hunger": 40.0, "sleepiness": 90.0, "anxiety": 20.0,
                            "curiosity": 60.0, "satisfaction": 55.0,
                            "can_see_food": 0.0})
        SQUID.make_decision()
        weights = SQUID._decision_engine.get_decision_data()["base_weights"]
        self.assertEqual(max(weights, key=weights.get), "sleeping")
        SQUID.is_sleeping = False

    # -- previously-missing actuators ---------------------------------------
    def test_flee_from_center_exists_and_installs_a_drive(self):
        SQUID.neural_drive = None
        SQUID.flee_from_center()
        drive = SQUID.get_neural_drive()
        self.assertIsNotNone(drive)
        self.assertEqual(drive["action"], "flee")
        self.assertTrue(SQUID.is_fleeing)

    def test_repeated_slow_movement_does_not_paralyse_the_squid(self):
        """move_slowly() used to permanently halve the squid's base speed.

        90 -> 45 -> 22 -> 11 -> 5 -> 2 -> 1 -> 0 with integer division and no
        restore, so seven "lounging" decisions left the squid unable to move
        for the rest of the session. Wiring the DecisionEngine in made that
        reachable in ordinary play.
        """
        base = SQUID.base_squid_speed
        vertical = SQUID.base_vertical_speed
        for _ in range(10):
            SQUID.move_slowly()
        self.assertEqual(SQUID.base_squid_speed, base,
                         "move_slowly permanently damaged the squid's base speed")
        self.assertEqual(SQUID.base_vertical_speed, vertical)
        self.assertAlmostEqual(SQUID.speed_multiplier(), 1.0, places=6)

    def test_erratic_movement_restores_speed(self):
        SQUID.current_speed = SQUID.base_speed
        for _ in range(5):
            SQUID.move_erratically()
        self.assertAlmostEqual(SQUID.speed_multiplier(), 1.0, places=6)

    def test_squid_delegates_throw_poop(self):
        self.assertTrue(hasattr(SQUID, "throw_poop"))
        self.assertFalse(SQUID.throw_poop("left"))  # nothing carried


# ---------------------------------------------------------------------------
# 7b. DecisionEngine - callable, but deliberately not wired (see report)
# ---------------------------------------------------------------------------
class DecisionEngineTests(NeuralPipelineTestCase):
    """The engine carried three crash bugs, each masked by the one before it.

    It is still not called by the running simulation - the neural pipeline is
    the authoritative brain -> squid path - but it must at least be callable,
    because the Decisions tab reads its trace when present.
    """

    def test_make_decision_runs_without_raising(self):
        SQUID.hunger, SQUID.curiosity, SQUID.anxiety, SQUID.sleepiness = 90.0, 20.0, 30.0, 20.0
        try:
            result = SQUID.make_decision()
        except Exception as exc:  # pragma: no cover - this is the assertion
            self.fail(f"make_decision raised {type(exc).__name__}: {exc}")
        self.assertIsInstance(result, str)

    def test_make_decision_survives_a_zero_weight(self):
        """personality_modifiers divided each weight by itself and blew up on 0."""
        SQUID.hunger, SQUID.curiosity, SQUID.anxiety = 0.0, 0.0, 0.0
        SQUID.sleepiness, SQUID.satisfaction = 0.0, 0.0
        SQUID.make_decision()
        mods = SQUID._decision_engine.get_decision_data()["personality_modifiers"]
        self.assertTrue(mods)
        for action, factor in mods.items():
            with self.subTest(action=action):
                self.assertIsInstance(factor, float)

    def test_squid_exposes_carrying_poop(self):
        """PoopInteractionManager and DecisionEngine both read this property."""
        self.assertFalse(SQUID.carrying_poop)
        SQUID.carrying_poop = True
        self.addCleanup(setattr, SQUID, "carrying_poop", False)
        self.assertTrue(SQUID.carrying_poop)
        self.assertTrue(SQUID.is_carrying_poop)


# ---------------------------------------------------------------------------
# 7. Sensor ranges
# ---------------------------------------------------------------------------
class SensorRangeTests(NeuralPipelineTestCase):

    def test_every_sensor_stays_within_its_declared_range(self):
        from src.designer_constants import INPUT_SENSORS
        from src.brain_constants import BINARY_NEURONS

        for name, position in INPUT_SENSORS.items():
            BRAIN.neuron_positions.setdefault(name, position)
            BRAIN.state.setdefault(name, 0.0)
            self.addCleanup(BRAIN.neuron_positions.pop, name, None)
        BRAIN.excluded_neurons = [n for n in BRAIN.excluded_neurons
                                  if n not in INPUT_SENSORS]
        tick(2)

        values = LOGIC.brain_hooks.get_input_neuron_values()
        for name, value in values.items():
            with self.subTest(sensor=name):
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 100.0)
                if name in BINARY_NEURONS:
                    self.assertIn(value, (0.0, 100.0))

    def test_analogue_sensors_are_not_quantised_into_the_state(self):
        """plant_proximity / external_stimulus must keep their gradient."""
        from src.brain_constants import ANALOGUE_SENSORS, BINARY_NEURONS
        for name in ANALOGUE_SENSORS:
            with self.subTest(sensor=name):
                self.assertNotIn(name, BINARY_NEURONS)

        BRAIN.neuron_positions.setdefault("plant_proximity", (50, 250))
        self.addCleanup(BRAIN.neuron_positions.pop, "plant_proximity", None)
        BRAIN.update_state({"plant_proximity": 37.5})
        self.assertAlmostEqual(BRAIN.state["plant_proximity"], 37.5, places=3)

    def test_boolean_state_is_stored_on_the_zero_to_one_hundred_scale(self):
        """A percent threshold in the Designer must be crossable."""
        BRAIN.update_state({"is_sleeping": True})
        self.assertEqual(BRAIN.state["is_sleeping"], 100.0)
        BRAIN.update_state({"is_sleeping": False})
        self.assertEqual(BRAIN.state["is_sleeping"], 0.0)

    def test_binary_definition_has_a_single_source(self):
        from src.brain_constants import BINARY_NEURONS as CANON
        from src.designer_constants import BINARY_NEURONS as VIA_DESIGNER
        self.assertIs(CANON, VIA_DESIGNER)
        for name in CANON:
            self.assertTrue(BRAIN.is_binary_neuron(name))


if __name__ == "__main__":
    unittest.main()
