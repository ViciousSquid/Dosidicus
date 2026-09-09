"""Stage 0 of the multiplayer encounter work.

Stage 0 is not a social AI. It is the architectural seam underneath one: the
point of these tests is that meeting another squid has become a first-class
sensory experience that the machinery already in STRINg can learn from.

The claim each section checks:

  1. A sensor registered at RUNTIME is a genuine pure input - not just a value
     in brain_state, but a sense organ to every system that reasons about one.
  2. Its value reaches the capability monitor and the causal ledger, which is
     what makes a representational deficit possible later without anything
     having to special-case an encounter.
  3. Encounters with two different individuals are two different experiences.
  4. The same individual is recognised again, across a restart.
  5. act_contest exists, and is unwired - the squid can contest and has not
     learned to.
  6. A contest changes the tank, so its outcome is something both squid can
     perceive.
  7. A refused visitor does not enter.
  8. An accepted visitor does.
  9. A filename from the network cannot name a file outside the game's assets.

None of these assert that the squid does anything social. That is the point:
Stage 0 gives the existing architecture the ability to have the experience,
and leaves what to make of it to the existing architecture.
"""

import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _path in (_REPO_ROOT, os.path.join(_REPO_ROOT, "headless")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from src import brain_constants as bc            # noqa: E402
from src import propagation                       # noqa: E402
from src.memory_manager import MemoryManager      # noqa: E402

from plugins.multiplayer.identity import SquidIdentity  # noqa: E402
from plugins.multiplayer.peer_ledger import PeerLedger  # noqa: E402
from plugins.multiplayer.encounter import EncounterSession  # noqa: E402
from plugins.multiplayer.encounter_sensors import (  # noqa: E402
    ConspecificView, EncounterSensors, SENSOR_NAMES, SENSOR_SPECS,
)
from plugins.multiplayer.consent import (  # noqa: E402
    ConsentPolicy, MODE_OPEN, MODE_CLOSED, MODE_KNOWN,
    REASON_ACCEPTED, REASON_CLOSED, REASON_UNKNOWN_PEER, REASON_BAD_IDENTITY,
)
from plugins.multiplayer.asset_paths import (  # noqa: E402
    safe_asset_name, resolve_local_asset, is_inside_assets,
)

_TMPDIR = None
_PREV_CWD = None

UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"
UUID_C = "33333333-3333-4333-8333-333333333333"


def setUpModule():
    """Memory files are written relative to the working directory."""
    global _TMPDIR, _PREV_CWD
    _PREV_CWD = os.getcwd()
    _TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-encounter-")
    os.chdir(_TMPDIR.name)


def tearDownModule():
    os.chdir(_PREV_CWD)
    _TMPDIR.cleanup()
    # These sets are module-level state shared with every other test file.
    EncounterSensors.release_classification(bc)


def identity(uuid, name="Peer", personality="timid"):
    return SquidIdentity(uuid=uuid, name=name, personality=personality)


class FakeMemoryManager(MemoryManager):
    """A real MemoryManager that never touches the filesystem.

    Subclassed rather than mocked because the behaviour under test IS
    MemoryManager's: the (category, key) identity rule, the importance bump on
    a repeat, and the promotion to long-term storage.
    """

    def __init__(self):
        super().__init__()
        self.short_term_memory = []
        self.long_term_memory = []

    def save_memory(self, memory, file_path):
        return None


# ===========================================================================
# 1. A sensor registered at runtime is a genuine pure input
# ===========================================================================
class RuntimeSensorRegistrationTests(unittest.TestCase):
    """The seam. Everything else in Stage 0 stands on this."""

    SENSOR = "unit_test_probe_sensor"

    def tearDown(self):
        bc.unregister_input_sensor(self.SENSOR)

    def test_an_unregistered_name_is_not_a_sensor(self):
        """The control condition: without registration, none of this holds."""
        self.assertNotIn(self.SENSOR, bc.PURE_INPUT_NEURONS)
        self.assertEqual(propagation.baseline_of(self.SENSOR), propagation.BASELINE)
        self.assertTrue(bc.is_network_driven(self.SENSOR))
        self.assertTrue(bc.is_learning_target(self.SENSOR))

    def test_a_runtime_sensor_is_recognised_by_every_system(self):
        bc.register_input_sensor(self.SENSOR, binary=False, owner="test")

        with self.subTest("classified as a pure input"):
            self.assertIn(self.SENSOR, bc.PURE_INPUT_NEURONS)
            self.assertIn(self.SENSOR, bc.NON_PROPAGATED_NEURONS)

        with self.subTest("propagation.baseline_of: rests at zero"):
            self.assertEqual(propagation.baseline_of(self.SENSOR), 0.0)

        with self.subTest("propagation never writes it"):
            self.assertFalse(bc.is_network_driven(self.SENSOR))

        with self.subTest("is_learning_target: no inert synapses into it"):
            self.assertFalse(bc.is_learning_target(self.SENSOR))

        with self.subTest("capability.situation_signature sees the same set"):
            from src.capability import PURE_INPUT_NEURONS as capability_set
            self.assertIn(self.SENSOR, capability_set)

        with self.subTest("causal_learning._capture_cue sees the same set"):
            from src.causal_learning import PURE_INPUT_NEURONS as causal_set
            self.assertIn(self.SENSOR, causal_set)

    def test_a_binary_sensor_is_registered_as_binary(self):
        bc.register_input_sensor(self.SENSOR, binary=True, owner="test")
        self.assertIn(self.SENSOR, bc.BINARY_NEURONS)
        self.assertNotIn(self.SENSOR, bc.ANALOGUE_SENSORS)
        self.assertEqual(bc.normalise_activation(self.SENSOR, 80.0), 100.0)

    def test_registration_is_reversible_and_leaves_no_trace(self):
        bc.register_input_sensor(self.SENSOR, binary=False, owner="test")
        self.assertTrue(bc.unregister_input_sensor(self.SENSOR))
        self.assertNotIn(self.SENSOR, bc.PURE_INPUT_NEURONS)
        self.assertNotIn(self.SENSOR, bc.NON_PROPAGATED_NEURONS)
        self.assertEqual(propagation.baseline_of(self.SENSOR), propagation.BASELINE)
        self.assertFalse(bc.unregister_input_sensor(self.SENSOR))

    def test_a_built_in_sensor_cannot_be_reclassified_or_removed(self):
        """A plugin may supply a built-in's value; it may not redefine it."""
        self.assertFalse(bc.register_input_sensor("can_see_food", binary=True))
        self.assertFalse(bc.unregister_input_sensor("can_see_food"))
        self.assertIn("can_see_food", bc.PURE_INPUT_NEURONS)

    def test_a_core_stat_or_action_neuron_cannot_be_made_a_sensor(self):
        for name in ("hunger", "act_flee"):
            with self.subTest(neuron=name):
                with self.assertRaises(ValueError):
                    bc.register_input_sensor(name)

    def test_the_registration_is_generic_not_encounter_specific(self):
        """Nothing in the seam knows what a conspecific is.

        The fix has to be a mechanism, not a special case, or the next plugin
        that adds a sensor hits exactly the same wall.
        """
        import inspect
        source = inspect.getsource(bc.register_input_sensor)
        source += inspect.getsource(propagation._follow_sensor_registration)
        self.assertNotIn("conspecific", source.lower())
        self.assertNotIn("squid", source.lower())
        self.assertNotIn("multiplayer", source.lower())


# ===========================================================================
# 2. The value reaches the learning and capability pipeline
# ===========================================================================
class SensorReachesThePipelineTests(unittest.TestCase):
    """A registered sensor must be usable as evidence, not just visible.

    Runs on the headless brain - the real CapabilityMonitor, the real
    ActionOutcomeLedger, the real propagation - with no Qt.
    """

    SENSOR = "unit_test_pipeline_sensor"

    def setUp(self):
        from headless_trainer import HeadlessBrain, TrainingConfig
        bc.register_input_sensor(self.SENSOR, binary=True, owner="test")
        self.brain = HeadlessBrain(TrainingConfig(seed=7))
        self.brain.positions[self.SENSOR] = (500.0, 500.0)
        self.brain.state[self.SENSOR] = 0.0

    def tearDown(self):
        bc.unregister_input_sensor(self.SENSOR)

    def _run(self, ticks, value):
        for _ in range(ticks):
            self.brain.state[self.SENSOR] = value
            self.brain.advance_clock(1.0)
            self.brain.propagate()

    def test_propagation_does_not_overwrite_the_registered_sensor(self):
        """The world owns a sense organ. Two writers on one neuron is the bug."""
        self._run(40, 100.0)
        self.assertEqual(self.brain.state[self.SENSOR], 100.0)

    def test_the_sensor_names_the_situation_it_defines(self):
        """capability.situation_signature() must be able to say it is here.

        Without this the capability monitor can never raise a representation
        deficit about the situation, because it cannot name the situation.
        """
        self._run(60, 100.0)
        signature = self.brain.capability.situation_signature(self.brain.state)
        self.assertIn(self.SENSOR, signature)

    def test_the_situation_is_recorded_and_can_be_evaluated(self):
        self._run(80, 100.0)
        self.brain.capability.evaluate()
        signatures = [s for s in self.brain.capability._signatures
                      if self.SENSOR in s]
        self.assertTrue(signatures,
                        "the capability monitor never recorded the situation")

    def test_the_sensor_can_be_the_cue_of_a_causal_claim(self):
        """causal_learning._capture_cue() keeps only PURE_INPUT sensors.

        A sensor it cannot see can never be the antecedent of anything the
        squid works out, so no expression deficit could ever name it.
        """
        self.brain.state[self.SENSOR] = 100.0
        cue = self.brain.causal_learning._capture_cue(self.brain.state)
        self.assertIn(self.SENSOR, cue)

    def test_a_silent_registered_sensor_contributes_nothing(self):
        """Zero has to mean 'nothing to report', or a stranger is a signal."""
        from src.propagation import signal_of
        self.assertEqual(signal_of(self.SENSOR, 0.0), 0.0)


# ===========================================================================
# 3 & 4. Individual identity
# ===========================================================================
class PersistentIdentityTests(unittest.TestCase):
    """'I remember THAT squid' needs an identity that outlives the process."""

    def test_identity_comes_from_the_squids_persisted_uuid(self):
        import uuid as uuid_module

        class FakeSquid:
            uuid = uuid_module.UUID(UUID_A)
            name = "Nautilus"
            personality = type("P", (), {"value": "timid"})()

        found = SquidIdentity.from_squid(FakeSquid())
        self.assertEqual(found.uuid, UUID_A)
        self.assertEqual(found.name, "Nautilus")
        self.assertEqual(found.memory_key, f"peer:{UUID_A}")

    def test_a_malformed_remote_identity_is_rejected(self):
        """A peer uuid becomes a memory key, so junk must not get that far."""
        for payload in ({}, {'uuid': ''}, {'uuid': '../../etc/passwd'},
                        {'uuid': 'not-a-uuid'}, {'uuid': 42}, None):
            with self.subTest(payload=payload):
                self.assertIsNone(SquidIdentity.from_payload(payload))

    def test_a_remote_name_cannot_carry_markup_into_a_memory(self):
        built = SquidIdentity.from_payload(
            {'uuid': UUID_B, 'name': '<b>evil</b>' + 'x' * 200})
        self.assertNotIn('<', built.name)
        self.assertLessEqual(len(built.name), 32)


class EncounterMemoryTests(unittest.TestCase):
    """Two encounters with two squid must be two experiences."""

    def setUp(self):
        self.memory = FakeMemoryManager()
        self.ledger = PeerLedger(self.memory)

    def _encounter(self, peer, valence_drives, first=True, items_lost=0):
        session = EncounterSession(
            peer, {'happiness': 50.0, 'anxiety': 50.0, 'satisfaction': 50.0},
            first_meeting=first, now=1000.0)
        session.observe(action="exploring", proximity=80.0, now=1001.0)
        for _ in range(items_lost):
            session.note_item_lost()
        record = session.close(drives=valence_drives, now=1010.0)
        self.ledger.record(record)
        return record

    def test_two_different_squid_produce_two_memories(self):
        """The collision this replaces: every encounter shared one key.

        add_short_term_memory identifies a memory by (category, key), and the
        old code always passed key='squid_detection' - so meeting a hundred
        squid produced one record whose importance kept going up.
        """
        self._encounter(identity(UUID_B, "Nautilus"),
                        {'happiness': 70.0, 'anxiety': 40.0, 'satisfaction': 60.0})
        self._encounter(identity(UUID_C, "Kraken"),
                        {'happiness': 30.0, 'anxiety': 80.0, 'satisfaction': 40.0})

        social = [m for m in self.memory.short_term_memory + self.memory.long_term_memory
                  if m.get('category') == 'social']
        keys = {m['key'] for m in social}
        self.assertEqual(keys, {f"peer:{UUID_B}", f"peer:{UUID_C}"})

    def test_the_two_memories_hold_different_experiences(self):
        good = self._encounter(identity(UUID_B, "Nautilus"),
                               {'happiness': 70.0, 'anxiety': 40.0, 'satisfaction': 60.0})
        bad = self._encounter(identity(UUID_C, "Kraken"),
                              {'happiness': 30.0, 'anxiety': 80.0, 'satisfaction': 40.0})
        self.assertGreater(good.valence, 0.0)
        self.assertLess(bad.valence, 0.0)
        self.assertNotEqual(good.outcome, bad.outcome)
        self.assertNotEqual(self.ledger.recalled_good(UUID_B), 0.0)
        self.assertNotEqual(self.ledger.recalled_bad(UUID_C), 0.0)
        self.assertEqual(self.ledger.recalled_bad(UUID_B), 0.0)

    def test_a_stranger_reads_zero_everywhere(self):
        """Never met is not a default guess; it is nothing to report."""
        self.assertEqual(self.ledger.familiarity(UUID_C), 0.0)
        self.assertEqual(self.ledger.recalled_good(UUID_C), 0.0)
        self.assertEqual(self.ledger.recalled_bad(UUID_C), 0.0)

    def test_the_same_squid_is_more_familiar_the_second_time(self):
        peer = identity(UUID_B, "Nautilus")
        self.assertEqual(self.ledger.familiarity(UUID_B), 0.0)
        self._encounter(peer, {'happiness': 55.0, 'anxiety': 50.0, 'satisfaction': 52.0})
        after_one = self.ledger.familiarity(UUID_B)
        self._encounter(peer, {'happiness': 58.0, 'anxiety': 50.0, 'satisfaction': 55.0},
                        first=False)
        after_two = self.ledger.familiarity(UUID_B)
        self.assertGreater(after_one, 0.0)
        self.assertGreater(after_two, after_one)

    def test_a_frightening_encounter_is_promoted_to_long_term_memory(self):
        """Persistence is MemoryManager's existing rule, not a new one.

        should_transfer_to_long_term() promotes at importance >= 7, and an
        encounter's importance is scaled from how far it moved the squid.
        """
        record = self._encounter(
            identity(UUID_B, "Nautilus"),
            {'happiness': 20.0, 'anxiety': 95.0, 'satisfaction': 25.0},
            items_lost=1)
        self.assertGreaterEqual(record.importance, 7.0)
        long_term_keys = {m['key'] for m in self.memory.long_term_memory}
        self.assertIn(f"peer:{UUID_B}", long_term_keys)

    def test_recognition_survives_a_restart(self):
        """A new session, a new ledger, the same individual.

        This is the Stage 0 definition of done in one assertion: the squid
        comes back with the experience it had, and reads it off the peer it is
        looking at rather than off anything that was kept in memory.
        """
        self._encounter(identity(UUID_B, "Nautilus"),
                        {'happiness': 20.0, 'anxiety': 92.0, 'satisfaction': 25.0},
                        items_lost=1)
        persisted = list(self.memory.long_term_memory)
        self.assertTrue(persisted, "nothing survived to be remembered")

        # A completely fresh session: new manager, new ledger, only the
        # long-term file carried across.
        reborn_memory = FakeMemoryManager()
        reborn_memory.long_term_memory = persisted
        reborn = PeerLedger(reborn_memory)

        self.assertGreater(reborn.familiarity(UUID_B), 0.0)
        self.assertGreater(reborn.recalled_bad(UUID_B), 0.0)
        self.assertEqual(reborn.familiarity(UUID_C), 0.0,
                         "a squid never met must still read as a stranger")

    def test_memory_lookup_by_peer_prefix(self):
        self._encounter(identity(UUID_B), {'happiness': 60.0})
        found = self.memory.get_memories_by_key_prefix('social', f'peer:{UUID_B}')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['value']['peer_uuid'], UUID_B)
        self.assertIn('detail', found[0]['value'])


# ===========================================================================
# The sensors themselves
# ===========================================================================
class ConspecificSensorTests(unittest.TestCase):
    """What the brain is actually told about another squid."""

    def setUp(self):
        self.now = 1000.0
        self.view = ConspecificView(clock=lambda: self.now)
        self.memory = FakeMemoryManager()
        self.ledger = PeerLedger(self.memory)
        self.sensors = EncounterSensors(self.view, self.ledger,
                                        clock=lambda: self.now)

    def _see(self, peer, x, y, facing='right', status=""):
        return self.view.observe_peer(peer, x=x, y=y, observer_x=0.0,
                                      observer_y=0.0, facing=facing,
                                      status=status, now=self.now)

    def test_every_sensor_reads_zero_with_no_other_squid(self):
        for name, handler in self.sensors.handlers().items():
            with self.subTest(sensor=name):
                self.assertEqual(handler(), 0.0)

    def test_presence_and_proximity(self):
        self._see(identity(UUID_B), 100.0, 0.0)
        self.assertEqual(self.sensors.visible(), 100.0)
        near = self.sensors.proximity()
        self.view.clear()
        self._see(identity(UUID_B), 380.0, 0.0)
        self.assertGreater(near, self.sensors.proximity())

    def test_relative_direction_reads_high_only_when_it_is_in_front(self):
        self._see(identity(UUID_B), 100.0, 0.0, facing='right')
        ahead = self.sensors.ahead()
        self.view.clear()
        self._see(identity(UUID_B), -100.0, 0.0, facing='right')
        behind = self.sensors.ahead()
        self.assertGreater(ahead, 90.0)
        self.assertLess(behind, 10.0)

    def test_closing_and_receding_are_separate_sensors(self):
        """Push-pull, because a sensor at rest must mean nothing to report.

        One signed sensor would have to read 50 for 'not moving', and 50 is a
        real mid-strength signal to signal_of() - a squid alone in its tank
        would be born feeling half of something.
        """
        peer = identity(UUID_B)
        self._see(peer, 300.0, 0.0)
        self.now += 1.0
        self._see(peer, 200.0, 0.0)
        self.assertGreater(self.sensors.closing(), 0.0)
        self.assertEqual(self.sensors.receding(), 0.0)

        self.now += 1.0
        self._see(peer, 350.0, 0.0)
        self.assertEqual(self.sensors.closing(), 0.0)
        self.assertGreater(self.sensors.receding(), 0.0)

    def test_familiarity_distinguishes_a_stranger_from_an_acquaintance(self):
        stranger, known = identity(UUID_B), identity(UUID_C, "Kraken")
        session = EncounterSession(known, {'happiness': 50.0}, now=1.0)
        self.ledger.record(session.close(drives={'happiness': 62.0}, now=9.0))

        self._see(stranger, 100.0, 0.0)
        self.assertEqual(self.sensors.familiarity(), 0.0)
        self.view.clear()
        self._see(known, 100.0, 0.0)
        self.assertGreater(self.sensors.familiarity(), 0.0)

    def test_a_presence_that_stops_updating_goes_away(self):
        self._see(identity(UUID_B), 100.0, 0.0)
        self.assertEqual(self.sensors.visible(), 100.0)
        self.now += 10.0
        self.assertEqual(self.sensors.visible(), 0.0)

    def test_the_sensors_register_through_the_normal_paths(self):
        """All three registrations, because all three are load-bearing."""
        class FakePluginManager:
            def __init__(self):
                self.handlers = {}

            def register_neuron_handler(self, neuron_name, handler,
                                        plugin_name, metadata=None):
                self.handlers[neuron_name] = handler
                return True

            def unregister_neuron_handler(self, neuron_name, plugin_name):
                return self.handlers.pop(neuron_name, None) is not None

        class FakeBrainWidget:
            def __init__(self):
                self.neuron_positions = {}
                self.state = {}

        pm, widget = FakePluginManager(), FakeBrainWidget()
        try:
            self.sensors.register(pm, bc, plugin_name='Multiplayer',
                                  brain_widget=widget)
            for name in SENSOR_NAMES:
                with self.subTest(sensor=name):
                    self.assertIn(name, pm.handlers)          # value
                    self.assertIn(name, bc.PURE_INPUT_NEURONS)  # classification
                    self.assertIn(name, widget.neuron_positions)  # neuron
                    self.assertEqual(widget.state[name], 0.0)
                    self.assertEqual(propagation.baseline_of(name), 0.0)
        finally:
            self.sensors.unregister(pm, plugin_name='Multiplayer')
            EncounterSensors.release_classification(bc)

    def test_disabling_the_plugin_leaves_the_neurons_classified(self):
        """Un-classifying live neurons would hand them back to propagation."""
        class FakePluginManager:
            def __init__(self):
                self.handlers = {}

            def register_neuron_handler(self, neuron_name, handler,
                                        plugin_name, metadata=None):
                self.handlers[neuron_name] = handler
                return True

            def unregister_neuron_handler(self, neuron_name, plugin_name):
                return self.handlers.pop(neuron_name, None) is not None

        pm = FakePluginManager()
        try:
            self.sensors.register(pm, bc, plugin_name='Multiplayer')
            self.sensors.unregister(pm, plugin_name='Multiplayer')
            self.assertEqual(pm.handlers, {}, "values must stop")
            for name in SENSOR_NAMES:
                with self.subTest(sensor=name):
                    self.assertIn(name, bc.PURE_INPUT_NEURONS)
                    self.assertFalse(bc.is_network_driven(name))
        finally:
            EncounterSensors.release_classification(bc)


# ===========================================================================
# 5 & 6. act_contest
# ===========================================================================
class ActContestTests(unittest.TestCase):
    """The squid can contest an object, and has not learned to."""

    def test_act_contest_is_an_action_neuron_the_squid_is_born_with(self):
        self.assertIn("act_contest", bc.ACTION_NEURONS)
        self.assertIn("act_contest", bc.newborn_neurons())
        self.assertIn("act_contest", bc.ACTION_BEHAVIOURS)
        self.assertEqual(bc.ACTION_BEHAVIOURS["act_contest"], "contesting")

    def test_act_contest_is_unwired(self):
        """No innate pathway: nothing drives it until experience does.

        This is the same standing act_play and act_shelter already have - a
        squid that never meets another squid never learns to contest anything,
        exactly as one that never meets a rock never learns to play.
        """
        self.assertIn("act_contest", bc.LEARNED_ACTIONS)
        drivers = [row for row in bc.INNATE_ACTION_WIRING if row[1] == "act_contest"]
        self.assertEqual(drivers, [])

    def test_act_contest_rests_at_zero_and_has_a_reachable_threshold(self):
        self.assertEqual(propagation.baseline_of("act_contest"), 0.0)
        threshold = bc.ACTION_THRESHOLDS["act_contest"]
        self.assertGreater(threshold, 0.0)
        self.assertLessEqual(threshold, 50.0,
                             "a threshold above what a learned pathway can "
                             "reach is a behaviour that can never happen")

    def test_act_contest_takes_part_in_the_action_competition(self):
        """Lateral inhibition is the arbiter, so it has to be in the contest."""
        self.assertIn("act_contest", bc.COMPETING_ACTIONS)
        wiring = bc.action_competition_wiring()
        inhibits = [row for row in wiring if row[0] == "act_contest"]
        inhibited_by = [row for row in wiring if row[1] == "act_contest"]
        self.assertTrue(inhibits)
        self.assertTrue(inhibited_by)

    def test_act_contest_is_bound_to_an_actuator(self):
        bindings = [b for b in bc.innate_bindings() if b[0] == "act_contest"]
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0][1], "neuron_output_contest")
        from src.brain_neuron_outputs import STANDARD_OUTPUT_HOOKS
        self.assertIn("neuron_output_contest", STANDARD_OUTPUT_HOOKS)


class FakeRect:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def center(self):
        return self

    def x(self):
        return self._x

    def y(self):
        return self._y


class FakeItem:
    def __init__(self, x, y, filename="rock.png"):
        self._x, self._y = x, y
        self.category = 'rock'
        self.filename = filename

    def sceneBoundingRect(self):
        return FakeRect(self._x, self._y)


class FakeSquid:
    DRIVE_URGE = 2

    def __init__(self):
        self.squid_x, self.squid_y = 0.0, 0.0
        self.squid_width, self.squid_height = 0.0, 0.0
        self.carrying_rock = False
        self.current_rock = None
        self.status = ""
        self.drives = []

    def set_neural_drive(self, name, duration=0.0, target=None, priority=0):
        self.drives.append((name, target))

    def pick_up_rock(self, rock):
        self.carrying_rock = True
        self.current_rock = rock
        return True


class FakeLogic:
    def __init__(self, items, view=None):
        self.items = items
        self.conspecific_view = view

    def get_nearby_decorations(self, x, y, radius):
        return list(self.items)


class ContestConsequenceTests(unittest.TestCase):
    """A contest has to change the tank, or nothing can be learned from it."""

    def setUp(self):
        from src.brain_neuron_outputs import NeuronOutputMonitor
        self.now = 500.0
        self.view = ConspecificView(clock=lambda: self.now)
        self.squid = FakeSquid()
        # Constructed without __init__: the monitor's constructor wires itself
        # into a plugin manager, and this is a test of one actuator.
        self.monitor = object.__new__(NeuronOutputMonitor)
        self.monitor.logic = None

    def _rival_at(self, x, y):
        peer = identity(UUID_B, "Nautilus")
        self.view.observe_peer(peer, x=x, y=y, observer_x=self.squid.squid_x,
                               observer_y=self.squid.squid_y, now=self.now)
        return peer

    def test_a_contest_transfers_an_object_that_was_the_rivals(self):
        # Rival at 150, object at 100: 50 from the rival, 100 from us, and
        # inside the 120px reach at which an object can actually be taken.
        self._rival_at(150.0, 0.0)
        contested = FakeItem(100.0, 0.0)
        logic = FakeLogic([contested], self.view)

        self.monitor._handle_contest("act_contest", 60.0, self.squid,
                                     tamagotchi_logic=logic)

        self.assertTrue(self.squid.carrying_rock,
                        "a contest that wins must actually change the tank")
        self.assertIs(self.squid.current_rock, contested)
        self.assertEqual(self.squid.status, "contesting")

    def test_the_contest_is_perceptible_to_the_other_squid(self):
        """The outcome has to reach a sense organ, or it teaches nobody."""
        self._rival_at(150.0, 0.0)
        logic = FakeLogic([FakeItem(100.0, 0.0)], self.view)
        sensors = EncounterSensors(self.view, None, clock=lambda: self.now)

        self.assertEqual(sensors.contesting(), 0.0)
        self.monitor._handle_contest("act_contest", 60.0, self.squid,
                                     tamagotchi_logic=logic)
        self.assertEqual(sensors.contesting(), 100.0)

    def test_the_contest_is_recorded_for_the_encounter_to_file(self):
        self._rival_at(150.0, 0.0)
        logic = FakeLogic([FakeItem(100.0, 0.0)], self.view)
        self.monitor._handle_contest("act_contest", 60.0, self.squid,
                                     tamagotchi_logic=logic)
        log = self.view.drain_contests()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0]['peer_uuid'], UUID_B)
        self.assertTrue(log[0]['taken'])

    def test_nothing_happens_with_no_other_squid_present(self):
        """A solitary squid can be born able to contest and never do it."""
        logic = FakeLogic([FakeItem(100.0, 0.0)], self.view)
        self.monitor._handle_contest("act_contest", 90.0, self.squid,
                                     tamagotchi_logic=logic)
        self.assertFalse(self.squid.carrying_rock)
        self.assertEqual(self.squid.status, "")

    def test_an_object_nearer_to_us_than_to_the_rival_is_not_contested(self):
        """Ordinary foraging is not a contest."""
        self._rival_at(400.0, 0.0)
        logic = FakeLogic([FakeItem(20.0, 0.0)], self.view)
        self.monitor._handle_contest("act_contest", 60.0, self.squid,
                                     tamagotchi_logic=logic)
        self.assertFalse(self.squid.carrying_rock)

    def test_an_encounter_records_a_contested_item_as_an_outcome(self):
        peer = identity(UUID_B, "Nautilus")
        session = EncounterSession(peer, {'happiness': 50.0}, now=1.0)
        session.note_item_lost()
        record = session.close(drives={'happiness': 50.0}, now=5.0)
        self.assertEqual(record.outcome, "robbed")
        self.assertLess(record.valence, 0.0)
        self.assertTrue(session.is_memorable(now=2.0),
                        "an item changing hands is an experience however brief")


# ===========================================================================
# 7 & 8. Consent
# ===========================================================================
class ConsentTests(unittest.TestCase):
    """Entry is something the host agrees to."""

    def setUp(self):
        self.now = 100.0
        self.policy = ConsentPolicy(mode=MODE_OPEN, clock=lambda: self.now)
        self.visitor = identity(UUID_B, "Nautilus")

    def test_an_accepted_visitor_can_enter(self):
        decision = self.policy.evaluate(self.visitor)
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.reason, REASON_ACCEPTED)
        self.assertTrue(self.policy.is_admitted(UUID_B))

    def test_a_refused_visitor_cannot_enter(self):
        self.policy.set_mode(MODE_CLOSED)
        decision = self.policy.evaluate(self.visitor)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, REASON_CLOSED)
        self.assertFalse(self.policy.is_admitted(UUID_B))

    def test_a_visitor_who_never_asked_is_not_admitted(self):
        """Arriving is not the same as being let in."""
        self.assertFalse(self.policy.is_admitted(UUID_B))

    def test_known_mode_admits_only_the_allow_list(self):
        self.policy.set_mode(MODE_KNOWN)
        self.assertFalse(self.policy.evaluate(self.visitor).accepted)
        self.assertEqual(self.policy.last_decision(UUID_B).reason,
                         REASON_UNKNOWN_PEER)
        self.policy.allow(UUID_B)
        self.assertTrue(self.policy.evaluate(self.visitor).accepted)

    def test_a_blocked_peer_is_refused_even_in_open_mode(self):
        self.policy.block(UUID_B)
        self.assertFalse(self.policy.evaluate(self.visitor).accepted)

    def test_a_visitor_without_a_usable_identity_is_refused(self):
        decision = self.policy.evaluate(None)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, REASON_BAD_IDENTITY)

    def test_the_tank_can_be_full(self):
        policy = ConsentPolicy(mode=MODE_OPEN, max_visitors=1,
                               clock=lambda: self.now)
        self.assertTrue(policy.evaluate(self.visitor, current_visitors=0).accepted)
        self.assertFalse(policy.evaluate(identity(UUID_C), current_visitors=1).accepted)

    def test_permission_expires(self):
        """A grant is not indefinite; a visitor has to be current."""
        from plugins.multiplayer.consent import DECISION_TTL
        self.policy.evaluate(self.visitor)
        self.assertTrue(self.policy.is_admitted(UUID_B))
        self.now += DECISION_TTL + 1.0
        self.assertFalse(self.policy.is_admitted(UUID_B))

    def test_an_incompatible_protocol_is_refused(self):
        stranger = SquidIdentity(uuid=UUID_C, name="Future", protocol=99)
        self.assertFalse(self.policy.evaluate(stranger).accepted)

    def test_a_visit_response_is_a_valid_packet(self):
        from plugins.multiplayer.packet_validator import PacketValidator
        decision = self.policy.evaluate(self.visitor)
        ok, error = PacketValidator.validate_visit('visit_response',
                                                   decision.to_payload())
        self.assertTrue(ok, error)


# ===========================================================================
# 9. Remote filenames
# ===========================================================================
class AssetPathTests(unittest.TestCase):
    """A name from the network may only ever pick a local asset."""

    MALICIOUS = (
        "../../../../etc/passwd.png",
        "..\\..\\windows\\system32\\config.png",
        "/etc/shadow.png",
        "images/../../../secret.png",
        "....//....//etc/passwd.png",
        "subdir/nested/../../escape.png",
    )

    def test_a_traversing_filename_is_reduced_to_its_basename(self):
        for name in self.MALICIOUS:
            with self.subTest(filename=name):
                safe = safe_asset_name(name)
                if safe is None:
                    continue
                self.assertNotIn("..", safe)
                self.assertNotIn("/", safe)
                self.assertNotIn("\\", safe)
                self.assertFalse(os.path.isabs(safe))

    def test_a_traversing_filename_never_resolves(self):
        """The end-to-end claim: only local assets are ever opened."""
        for name in self.MALICIOUS:
            with self.subTest(filename=name):
                resolved = resolve_local_asset(name)
                self.assertTrue(resolved is None or is_inside_assets(resolved),
                                f"{name} resolved outside the asset roots")

    def test_non_image_and_junk_names_are_rejected(self):
        for name in ("evil.py", "payload.sh", "", "   ", None, 42,
                     ".hidden.png", "..", "."):
            with self.subTest(filename=name):
                self.assertIsNone(safe_asset_name(name))

    def test_a_real_asset_still_resolves(self):
        """The fix must not break carrying an ordinary item home."""
        root = os.path.join(_REPO_ROOT, "images")
        if not os.path.isdir(root):
            self.skipTest("no images directory in this checkout")
        previous = os.getcwd()
        os.chdir(_REPO_ROOT)
        try:
            names = [f for f in os.listdir(root)
                     if f.lower().endswith(('.png', '.jpg'))]
            if not names:
                self.skipTest("no image assets in this checkout")
            resolved = resolve_local_asset(names[0])
            self.assertIsNotNone(resolved)
            self.assertTrue(is_inside_assets(resolved))
        finally:
            os.chdir(previous)

    def test_the_resolver_is_what_the_plugin_actually_calls(self):
        """Guards against the old candidate list coming back."""
        import inspect
        from plugins.multiplayer import mp_plugin_logic
        source = inspect.getsource(mp_plugin_logic.MultiplayerPlugin
                                   .recreate_carried_items_in_tank)
        self.assertIn("resolve_local_asset", source)
        self.assertNotIn("original_filename # If original_filename", source)


# ===========================================================================
# The encounter, as a whole
# ===========================================================================
class EncounterSessionTests(unittest.TestCase):
    """The bout, not the tick, is the unit that gets remembered."""

    def setUp(self):
        self.peer = identity(UUID_B, "Nautilus")

    def test_the_outcome_is_measured_not_scored_from_a_table(self):
        """Two identical action sequences can end differently."""
        actions = ["exploring", "contesting"]
        records = []
        for closing in ({'happiness': 75.0, 'anxiety': 35.0},
                        {'happiness': 25.0, 'anxiety': 85.0}):
            session = EncounterSession(
                self.peer, {'happiness': 50.0, 'anxiety': 50.0}, now=0.0)
            for action in actions:
                session.observe(action=action, now=1.0)
            records.append(session.close(drives=closing, now=10.0))

        self.assertEqual(records[0].actions, records[1].actions)
        self.assertGreater(records[0].valence, 0.0)
        self.assertLess(records[1].valence, 0.0)

    def test_a_repeated_action_is_one_thing_not_eighty(self):
        session = EncounterSession(self.peer, {'happiness': 50.0}, now=0.0)
        for _ in range(40):
            session.observe(action="fleeing", now=1.0)
        session.observe(action="exploring", now=2.0)
        record = session.close(drives={'happiness': 50.0}, now=5.0)
        self.assertEqual(record.actions, ["fleeing", "exploring"])

    def test_a_glimpse_across_the_tank_is_not_an_experience(self):
        session = EncounterSession(self.peer, {'happiness': 50.0}, now=0.0)
        session.observe(action="exploring", now=0.5)
        self.assertFalse(session.is_memorable(now=1.0))

    def test_an_encounter_closes_when_the_other_squid_is_gone(self):
        from plugins.multiplayer.encounter import LOST_SIGHT_GRACE
        session = EncounterSession(self.peer, {'happiness': 50.0}, now=0.0)
        session.observe(action="exploring", visible=True, now=1.0)
        self.assertFalse(session.should_close(now=2.0))
        self.assertTrue(session.should_close(now=1.0 + LOST_SIGHT_GRACE + 1.0))

    def test_the_memory_value_is_a_dict_the_memory_tab_can_colour(self):
        """format_memory() colours a memory by summing its numeric values.

        So valence has to be the only number at the top level. A raw anxiety
        delta of +30 sitting beside it would make being frightened read as a
        good outcome, and the duration in seconds would read as happiness.
        """
        session = EncounterSession(
            self.peer, {'happiness': 50.0, 'anxiety': 50.0}, now=0.0)
        session.observe(action="fleeing", now=1.0)
        record = session.close(drives={'happiness': 30.0, 'anxiety': 80.0}, now=9.0)
        value = record.to_memory_value()

        self.assertEqual(value['peer_uuid'], UUID_B)
        numeric = [v for v in value.values() if isinstance(v, (int, float))]
        self.assertEqual(numeric, [value['valence']],
                         "only valence may be a top-level number")
        self.assertLess(sum(numeric), 0, "a frightening encounter must read red")
        self.assertEqual(value['detail']['drive_deltas']['anxiety'], 30.0)

    def test_a_first_meeting_is_marked_as_one(self):
        first = EncounterSession(self.peer, {'happiness': 50.0},
                                 first_meeting=True, now=0.0)
        again = EncounterSession(self.peer, {'happiness': 50.0},
                                 first_meeting=False, now=0.0)
        self.assertTrue(first.close(now=5.0).first_meeting)
        self.assertFalse(again.close(now=5.0).first_meeting)


if __name__ == "__main__":
    unittest.main()


# ===========================================================================
# Regressions found while building Stage 0
# ===========================================================================
class EncounterLifecycleRegressionTests(unittest.TestCase):
    """Two bugs the first cut of this had, kept as tests."""

    def test_a_long_visit_is_still_written_down(self):
        """A peer that never leaves must not produce one unwritten encounter.

        The close check was originally skipped entirely while the peer was
        still present, so a squid that shared its tank for an hour accumulated
        no experience at all until the visitor left.
        """
        from plugins.multiplayer.encounter import MAX_ENCOUNTER_DURATION
        peer = identity(UUID_B)
        session = EncounterSession(peer, {'happiness': 50.0}, now=0.0)
        session.observe(action="exploring", visible=True,
                        now=MAX_ENCOUNTER_DURATION + 1.0)
        self.assertTrue(session.should_close(now=MAX_ENCOUNTER_DURATION + 1.0),
                        "an encounter has to end even if the visitor does not")

    def test_a_session_measures_against_its_opening_drives_by_default(self):
        """close() with no drives must not silently measure zero change."""
        session = EncounterSession(self.__class__ and identity(UUID_B),
                                   {'happiness': 50.0, 'anxiety': 50.0}, now=0.0)
        session.observe(drives={'happiness': 80.0, 'anxiety': 30.0}, now=1.0)
        record = session.close(now=9.0)
        self.assertGreater(record.valence, 0.0,
                           "the last observed drives are what closing means")
