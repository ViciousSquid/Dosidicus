"""Stage 1: the remote-mind round trip.

The invariant under test:

    Squid A's brain -> decision -> network -> Squid B's tank -> consequence
        -> network -> Squid A's brain

with no second copy of Squid A's brain running inside Squid B's tank.

Everything here is built from two loopback endpoints - a HostBody and a
VisitorMind wired to each other's inboxes - so a whole visit runs in-process
with no sockets, no Qt and no timing. What crosses between them is exactly
what would cross the wire.

The load-bearing test is `PluginDoesNotChooseBehaviourTests`. Every other test
could pass while the multiplayer layer quietly decided what the visitor did;
that one fails if it does.
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

from src import brain_constants as bc                     # noqa: E402
from src.memory_manager import MemoryManager              # noqa: E402
from src.decision_engine import select_action             # noqa: E402

from plugins.multiplayer.identity import SquidIdentity    # noqa: E402
from plugins.multiplayer.peer_ledger import PeerLedger    # noqa: E402
from plugins.multiplayer.encounter import EncounterSession  # noqa: E402
from plugins.multiplayer.encounter_sensors import (       # noqa: E402
    ConspecificView, EncounterSensors, SENSOR_NAMES,
)
from plugins.multiplayer.consent import (                 # noqa: E402
    ConsentPolicy, MODE_OPEN, MODE_CLOSED,
)
from plugins.multiplayer.host_body import (               # noqa: E402
    HostBody, VisitorActor, GRASP_RANGE,
)
from plugins.multiplayer.visitor_mind import (            # noqa: E402
    VisitorMind, RemotePerception, REMOTE_DRIVEN_SENSORS,
)
from plugins.multiplayer.remote_protocol import (         # noqa: E402
    ActionIntent, Consequence, PerceptionFrame, ProtocolError, VisitEnd,
    CONSEQUENCE_ATE, CONSEQUENCE_BLOCKED, CONSEQUENCE_CONTEST,
    CONSEQUENCE_EJECTED, FORBIDDEN_KEYS, INTENT_LEASE, LINK_TIMEOUT,
    OBSERVABLE_SENSORS, PRIVATE_SENSORS, VISIT_ABANDON_TIMEOUT,
    END_LINK_LOST, new_visit_id,
)

_TMPDIR = None
_PREV_CWD = None

HOST_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VISITOR_UUID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_UUID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"


def setUpModule():
    global _TMPDIR, _PREV_CWD
    _PREV_CWD = os.getcwd()
    _TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-stage1-")
    os.chdir(_TMPDIR.name)


def tearDownModule():
    os.chdir(_PREV_CWD)
    _TMPDIR.cleanup()
    EncounterSensors.release_classification(bc)


# ===========================================================================
# Fakes: a tank, a squid, and a clock we control
# ===========================================================================
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
    def __init__(self, x, y, category='rock', filename='rock.png'):
        self._x, self._y = x, y
        self.category = category
        self.filename = filename

    def sceneBoundingRect(self):
        return FakeRect(self._x, self._y)

    def setPos(self, x, y):
        self._x, self._y = x, y


class FakeScene:
    def __init__(self, items=()):
        self._items = list(items)

    def items(self):
        return list(self._items)

    def removeItem(self, item):
        if item in self._items:
            self._items.remove(item)

    def addItem(self, item):
        self._items.append(item)


class FakeUI:
    def __init__(self, scene):
        self.scene = scene
        self.window_width = 1280
        self.window_height = 900


class FakeSquid:
    """Enough of a squid for the host to see and the visitor to feel."""

    def __init__(self, uuid, name, x=600.0, y=400.0, personality='timid'):
        self.uuid = uuid
        self.name = name
        self.personality = type("P", (), {"value": personality})()
        self.squid_x, self.squid_y = x, y
        self.squid_width, self.squid_height = 60.0, 40.0
        self.squid_direction = 'right'
        self.status = 'exploring'
        self.hunger = self.happiness = self.satisfaction = 50.0
        self.anxiety = self.curiosity = self.cleanliness = self.sleepiness = 50.0
        self.carrying_rock = False
        self.current_rock = None
        self.is_transitioning = False
        self.can_move = True
        self.squid_item = None
        self.memory_manager = MemoryManager()
        self.memory_manager.save_memory = lambda m, p: None
        self.memory_manager.short_term_memory = []
        self.memory_manager.long_term_memory = []


class FakeBrainWidget:
    def __init__(self):
        self.neuron_positions = {}
        self.state = {}


class FakeBrainWindow:
    def __init__(self):
        self.brain_widget = FakeBrainWidget()


class FakeTank:
    """A TamagotchiLogic-shaped object, read only through getattr."""

    def __init__(self, squid, items=(), food=()):
        self.squid = squid
        self.food_items = list(food)
        self.user_interface = FakeUI(FakeScene(list(items) + list(food)))
        self.brain_window = FakeBrainWindow()
        self.conspecific_view = None
        self.messages = []

    def show_message(self, text):
        self.messages.append(text)

    def get_nearby_decorations(self, x, y, radius):
        return [i for i in self.user_interface.scene.items()
                if getattr(i, 'category', '') == 'rock']


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


class Link:
    """A loopback wire between a host and a visitor.

    Records everything that crosses, so a test can assert on the traffic
    itself rather than on its effects.
    """

    def __init__(self):
        self.host_inbox = []
        self.visitor_inbox = []
        self.sent_by_visitor = []
        self.sent_by_host = []
        self.broken = False

    def from_visitor(self, message_type, payload):
        self.sent_by_visitor.append((message_type, payload))
        if not self.broken:
            self.host_inbox.append((message_type, payload))
        return True

    def from_host(self, message_type, payload):
        self.sent_by_host.append((message_type, payload))
        if not self.broken:
            self.visitor_inbox.append((message_type, payload))
        return True


class Encounter:
    """One visit, end to end, in one process.

    HOST side owns the tank and a HostBody. VISITOR side owns a real squid, a
    real brain state, a PeerLedger and a VisitorMind. Nothing is shared
    between them except the Link.
    """

    def __init__(self, host_squid=None, visitor_squid=None, items=(), food=(),
                 clock=None):
        self.clock = clock or Clock()
        self.link = Link()

        self.host_squid = host_squid or FakeSquid(HOST_UUID, "Resident", 600.0, 400.0)
        self.host_tank = FakeTank(self.host_squid, items=items, food=food)
        self.host_view = ConspecificView(clock=self.clock)
        self.host_tank.conspecific_view = self.host_view
        self.host_body = HostBody(self.host_tank, self.host_view, clock=self.clock)

        self.visitor_squid = visitor_squid or FakeSquid(
            VISITOR_UUID, "Traveller", 0.0, 0.0, personality='adventurous')
        self.visitor_tank = FakeTank(self.visitor_squid)
        self.visitor_ledger = PeerLedger(self.visitor_squid.memory_manager)
        self.visitor_mind = VisitorMind(
            tamagotchi_logic=self.visitor_tank,
            peer_ledger=self.visitor_ledger,
            send=self.link.from_visitor,
            clock=self.clock)
        self.visitor_sensors = EncounterSensors(
            ConspecificView(clock=self.clock), self.visitor_ledger,
            clock=self.clock, remote=self.visitor_mind)

        self.identity = SquidIdentity.from_squid(self.visitor_squid)
        self.actor = None

    # -- the visit ------------------------------------------------------
    def admit(self, x=100.0, y=400.0, policy=None):
        policy = policy or ConsentPolicy(mode=MODE_OPEN, clock=self.clock)
        decision = policy.evaluate(self.identity,
                                   current_visitors=len(self.host_body.visitors))
        if not decision.accepted:
            return None
        visit_id = new_visit_id(HOST_UUID, VISITOR_UUID, self.clock())
        self.actor = self.host_body.admit(self.identity, visit_id, x, y)
        self.visitor_mind.begin_visit(SquidIdentity.from_squid(self.host_squid))
        return self.actor

    def host_sends_frame(self):
        frame = self.host_body.build_frame(self.actor)
        self.link.from_host('perception_frame', frame.to_payload())
        return frame

    def visitor_receives(self):
        """Deliver everything waiting for the visitor."""
        delivered = []
        while self.link.visitor_inbox:
            kind, payload = self.link.visitor_inbox.pop(0)
            if kind == 'perception_frame':
                delivered.append(('perception_frame',
                                  self.visitor_mind.on_perception_frame(payload)))
            elif kind == 'consequence':
                delivered.append(('consequence',
                                  self.visitor_mind.on_consequence(payload)))
            elif kind == 'visit_end':
                delivered.append(('visit_end',
                                  self.visitor_mind.on_visit_end(payload)))
        return delivered

    def visitor_decides(self):
        return self.visitor_mind.decide()

    def host_receives(self):
        """Apply everything the visitor asked for."""
        applied = []
        while self.link.host_inbox:
            kind, payload = self.link.host_inbox.pop(0)
            if kind == 'action_intent':
                try:
                    intent = ActionIntent.from_payload(payload)
                except ProtocolError as exc:
                    applied.append(('rejected', str(exc)))
                    continue
                applied.append(('applied',
                                self.host_body.apply_intent(self.actor, intent)))
            elif kind == 'visit_end':
                applied.append(('visit_end', payload))
        return applied

    def host_reports(self):
        for consequence in self.host_body.drain_consequences(self.actor):
            self.link.from_host('consequence', consequence.to_payload())

    def cycle(self):
        """One full round trip."""
        self.host_sends_frame()
        self.visitor_receives()
        intent = self.visitor_decides()
        self.host_receives()
        self.host_reports()
        self.visitor_receives()
        return intent

    def set_brain(self, **activations):
        """Put the visiting squid's network into a given state."""
        self.visitor_tank.brain_window.brain_widget.state.update(activations)


def quiet_brain(**overrides):
    """An action-neuron state with nothing above threshold except what is given."""
    state = {name: 0.0 for name in bc.ACTION_NEURONS}
    state['act_move'] = 0.0
    state.update(overrides)
    return state


# ===========================================================================
# 1-2. Consent, and perception generated by the host
# ===========================================================================
class AdmissionAndPerceptionTests(unittest.TestCase):

    def test_a_visitor_enters_only_after_consent(self):
        meeting = Encounter()
        closed = ConsentPolicy(mode=MODE_CLOSED, clock=meeting.clock)
        self.assertIsNone(meeting.admit(policy=closed))
        self.assertEqual(meeting.host_body.visitors, {})

    def test_an_accepted_visitor_gets_a_body_and_no_brain(self):
        meeting = Encounter()
        actor = meeting.admit()
        self.assertIsInstance(actor, VisitorActor)
        self.assertIn(VISITOR_UUID, meeting.host_body.visitors)
        # A body has a position and a lease. It has no policy, no state
        # machine and nothing that could decide anything.
        for attribute in ('state', 'brain', 'decide', 'update', 'explore',
                          'seek_food', 'personality'):
            with self.subTest(attribute=attribute):
                self.assertFalse(hasattr(actor, attribute),
                                 f"a visitor's body must not have '{attribute}'")

    def test_the_host_generates_the_visitors_perception(self):
        meeting = Encounter(food=[FakeItem(350.0, 400.0, category='food')])
        meeting.admit(x=300.0, y=400.0)   # inside SIGHT_RANGE of the resident
        frame = meeting.host_body.build_frame(meeting.actor)

        self.assertEqual(frame.sensors['can_see_food'], 100.0)
        self.assertEqual(frame.sensors['conspecific_visible'], 100.0)
        self.assertGreater(frame.sensors['conspecific_proximity'], 0.0)
        self.assertEqual(frame.resident.uuid, HOST_UUID)

    def test_the_host_never_asserts_what_the_visitor_remembers(self):
        """Familiarity and recalled valence are the visitor's, not the host's."""
        meeting = Encounter()
        meeting.admit()
        frame = meeting.host_body.build_frame(meeting.actor)
        for name in PRIVATE_SENSORS:
            with self.subTest(sensor=name):
                self.assertNotIn(name, frame.sensors)
                self.assertNotIn(name, frame.to_payload()['sensors'])

    def test_a_host_claiming_to_know_the_visitors_memory_is_rejected(self):
        payload = PerceptionFrame('v1').to_payload()
        payload['sensors']['conspecific_familiarity'] = 100.0
        with self.assertRaises(ProtocolError):
            PerceptionFrame.from_payload(payload)


# ===========================================================================
# 3-4. Perception reaches the normal input path; the visitor's brain decides
# ===========================================================================
class PerceptionReachesTheBrainTests(unittest.TestCase):

    def setUp(self):
        self.meeting = Encounter(food=[FakeItem(350.0, 400.0, category='food')])
        self.meeting.admit(x=300.0, y=400.0)
        self.meeting.host_sends_frame()
        self.meeting.visitor_receives()

    def test_the_frame_arrives_through_the_conspecific_sensors(self):
        """The same sense organs the squid uses at home, pointed elsewhere."""
        sensors = self.meeting.visitor_sensors
        self.assertEqual(sensors.visible(), 100.0)
        self.assertGreater(sensors.proximity(), 0.0)

    def test_the_built_in_sensors_report_the_host_tank_while_away(self):
        """can_see_food must mean the food over THERE, not the food at home."""
        overrides = self.meeting.visitor_mind.sensor_overrides(
            {name: (lambda: 0.0) for name in REMOTE_DRIVEN_SENSORS})
        self.assertEqual(overrides['can_see_food'](), 100.0)

    def test_the_same_sensors_report_home_again_once_the_visit_ends(self):
        overrides = self.meeting.visitor_mind.sensor_overrides(
            {'can_see_food': (lambda: 42.0),
             'plant_proximity': (lambda: 0.0),
             'external_stimulus': (lambda: 0.0)})
        self.assertEqual(overrides['can_see_food'](), 100.0)
        self.meeting.visitor_mind.end_visit(notify=False)
        self.assertEqual(overrides['can_see_food'](), 42.0)

    def test_the_visitors_own_brain_selects_the_action(self):
        """The intent must be what select_action says about THIS brain state.

        Not "an action that looks plausible" - the specific one the squid's
        own network wants, chosen by the engine's own rule.
        """
        self.meeting.set_brain(**quiet_brain(act_flee=95.0))
        intent = self.meeting.visitor_decides()
        self.assertIsNotNone(intent)
        self.assertEqual(intent.action, 'act_flee')

    def test_a_brain_that_wants_nothing_sends_no_intent(self):
        """Silence is a real answer, and the body simply stops."""
        self.meeting.set_brain(**quiet_brain())
        self.assertIsNone(self.meeting.visitor_decides())

    def test_the_recalled_sensors_are_computed_at_home(self):
        session = EncounterSession(SquidIdentity.from_squid(self.meeting.host_squid),
                                   {'happiness': 50.0}, now=1.0)
        self.meeting.visitor_ledger.record(
            session.close(drives={'happiness': 20.0, 'anxiety': 90.0}, now=9.0))
        recalled = self.meeting.visitor_mind.recalled_sensors()
        self.assertGreater(recalled['conspecific_familiarity'], 0.0)
        self.assertGreater(recalled['conspecific_recalled_bad'], 0.0)


# ===========================================================================
# THE ARCHITECTURAL TEST
# ===========================================================================
class PluginDoesNotChooseBehaviourTests(unittest.TestCase):
    """The one test that fails if the multiplayer layer picks the behaviour.

    Every other test in this file could pass while the plugin quietly decided
    what a visitor did. These cannot: the same tank, the same frame, the same
    identity, the same code path - and the only thing that differs is what is
    in each visitor's own network.
    """

    def _visit_with_brain(self, **activations):
        meeting = Encounter(items=[FakeItem(120.0, 400.0)],
                            food=[FakeItem(150.0, 400.0, category='food')])
        meeting.admit(x=100.0, y=400.0)
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(**activations))
        return meeting, meeting.visitor_decides()

    def test_two_different_brains_produce_different_actions_from_one_frame(self):
        frightened, flee_intent = self._visit_with_brain(act_flee=95.0)
        hungry, eat_intent = self._visit_with_brain(act_eat=95.0)

        self.assertEqual(flee_intent.action, 'act_flee')
        self.assertEqual(eat_intent.action, 'act_eat')
        # Same tank, same resident, same position, same perception.
        self.assertEqual(
            frightened.host_body.build_frame(frightened.actor).sensors,
            hungry.host_body.build_frame(hungry.actor).sensors)

    def test_the_action_is_the_one_the_engines_own_rule_chose(self):
        """Not merely different - identical to what the engine would pick.

        Run select_action over the same state with the jitter off and the
        intent must name the same behaviour. If the plugin were applying any
        policy of its own, this is where the two would part company.
        """
        for activations in ({'act_flee': 90.0}, {'act_eat': 90.0},
                            {'act_shelter': 90.0}, {'act_play': 90.0}):
            with self.subTest(brain=activations):
                meeting, intent = self._visit_with_brain(**activations)
                state = meeting.visitor_tank.brain_window.brain_widget.state
                behaviour, _confidence, _urgency = select_action(state, jitter=False)
                self.assertEqual(bc.ACTION_BEHAVIOURS[intent.action], behaviour)

    def test_the_visitors_identity_is_not_consulted_when_deciding(self):
        """A timid visitor and an adventurous one with the SAME brain state
        must produce the same intent.

        Personality in this engine is a birth-time tilt on synapses, so by the
        time a brain state exists it has already had its say. Anything reading
        the personality string at decision time would be a second, hidden
        policy - and this is where it would show.
        """
        timid = FakeSquid(VISITOR_UUID, "Timid", personality='timid')
        bold = FakeSquid(VISITOR_UUID, "Bold", personality='adventurous')
        actions = []
        for squid in (timid, bold):
            meeting = Encounter(visitor_squid=squid)
            meeting.admit()
            meeting.host_sends_frame()
            meeting.visitor_receives()
            meeting.set_brain(**quiet_brain(act_flee=90.0))
            actions.append(meeting.visitor_decides().action)
        self.assertEqual(actions[0], actions[1])

    def test_the_host_has_no_branch_on_who_the_visitor_is(self):
        """Read the host's dispatch and prove it cannot be personalised."""
        import inspect
        from plugins.multiplayer import host_body as module
        source = inspect.getsource(module.HostBody.apply_intent)
        for handler in module.HostBody._ACTIONS.values():
            source += inspect.getsource(handler)
        for forbidden in ('personality', 'timid', 'adventurous', 'greedy',
                          'familiarity', 'recalled', 'ledger', 'memory'):
            with self.subTest(term=forbidden):
                self.assertNotIn(forbidden, source.lower())

    def test_the_hosts_whole_vocabulary_is_the_squids_own_actions(self):
        """The host cannot be asked for anything a squid's network cannot want."""
        from plugins.multiplayer.host_body import HostBody
        self.assertTrue(set(HostBody._ACTIONS).issubset(set(bc.ACTION_NEURONS)))

    def test_an_action_that_is_not_an_action_neuron_is_refused(self):
        payload = ActionIntent('v1', 'act_move').to_payload()
        payload['action'] = 'act_dominate'
        with self.assertRaises(ProtocolError):
            ActionIntent.from_payload(payload)


# ===========================================================================
# 5-8. Apply, resolve, report, and back into the senses
# ===========================================================================
class RoundTripTests(unittest.TestCase):

    def test_the_host_validates_and_applies_a_movement(self):
        meeting = Encounter()
        meeting.admit(x=100.0, y=400.0)
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(act_move=90.0))

        before = meeting.actor.x
        meeting.visitor_decides()
        applied = meeting.host_receives()
        self.assertEqual(applied, [('applied', True)])
        self.assertNotEqual(meeting.actor.x, before)

    def test_a_stale_visit_id_is_refused(self):
        meeting = Encounter()
        meeting.admit()
        intent = ActionIntent('some-other-visit', 'act_move',
                              seq=1, sent_at=meeting.clock())
        self.assertFalse(meeting.host_body.apply_intent(meeting.actor, intent))
        self.assertEqual(meeting.host_body.rejected_intents, 1)

    def test_a_replayed_intent_is_refused(self):
        meeting = Encounter()
        meeting.admit()
        intent = ActionIntent(meeting.actor.visit_id, 'act_move', seq=5,
                              sent_at=meeting.clock(), heading='right')
        self.assertTrue(meeting.host_body.apply_intent(meeting.actor, intent))
        self.assertFalse(meeting.host_body.apply_intent(meeting.actor, intent))

    def test_a_contest_is_resolved_and_reported(self):
        """act_play at an object the resident had a claim to."""
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])   # near the resident
        meeting.admit(x=500.0, y=400.0)
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(act_play=95.0))

        meeting.visitor_decides()
        meeting.host_receives()
        self.assertEqual(meeting.actor.items_taken, 1)

        meeting.host_reports()
        meeting.visitor_receives()
        won = [c for c in meeting.visitor_mind.consequences
               if c.kind == CONSEQUENCE_CONTEST]
        self.assertTrue(won)
        self.assertTrue(won[0].detail['won'])

    def test_the_contest_outcome_reaches_the_visitors_drives(self):
        """The consequence has to move something the causal ledger measures."""
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        meeting.admit(x=500.0, y=400.0)
        before = meeting.visitor_squid.satisfaction
        meeting.visitor_mind.visit_id = 'v1'
        meeting.visitor_mind.on_consequence(
            Consequence('v1', CONSEQUENCE_CONTEST, detail={'won': True}).to_payload())
        self.assertGreater(meeting.visitor_squid.satisfaction, before)

    def test_a_lost_contest_raises_the_visitors_anxiety(self):
        meeting = Encounter()
        meeting.visitor_mind.visit_id = 'v1'
        before = meeting.visitor_squid.anxiety
        meeting.visitor_mind.on_consequence(
            Consequence('v1', CONSEQUENCE_CONTEST, detail={'won': False}).to_payload())
        self.assertGreater(meeting.visitor_squid.anxiety, before)

    def test_the_contest_is_perceptible_to_the_resident(self):
        """Both squid are in the encounter, so both must be able to feel it."""
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        meeting.admit(x=500.0, y=400.0)
        resident_sensors = EncounterSensors(meeting.host_view, None,
                                            clock=meeting.clock)
        self.assertEqual(resident_sensors.contesting(), 0.0)

        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(act_play=95.0))
        meeting.visitor_decides()
        meeting.host_receives()
        self.assertEqual(resident_sensors.contesting(), 100.0)

    def test_eating_in_the_host_tank_relieves_the_visitors_hunger(self):
        meeting = Encounter(food=[FakeItem(110.0, 400.0, category='food')])
        meeting.admit(x=100.0, y=400.0)
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(act_eat=95.0))
        before = meeting.visitor_squid.hunger

        meeting.visitor_decides()
        meeting.host_receives()
        meeting.host_reports()
        meeting.visitor_receives()
        self.assertLess(meeting.visitor_squid.hunger, before)
        self.assertEqual(meeting.host_tank.food_items, [])

    def test_a_full_cycle_leaves_the_visitor_somewhere_new(self):
        meeting = Encounter()
        meeting.admit(x=100.0, y=400.0)
        meeting.set_brain(**quiet_brain(act_move=90.0))
        start = (meeting.actor.x, meeting.actor.y)
        for _ in range(3):
            meeting.cycle()
            meeting.clock.advance(0.5)
        self.assertNotEqual((meeting.actor.x, meeting.actor.y), start)
        self.assertGreaterEqual(meeting.visitor_mind.intents_sent, 3)


# ===========================================================================
# 9-11. Encounter memory, across the round trip
# ===========================================================================
class EncounterMemoryAcrossTheLinkTests(unittest.TestCase):

    def _remember(self, meeting, drives):
        session = EncounterSession(
            SquidIdentity.from_squid(meeting.host_squid),
            {'happiness': 50.0, 'anxiety': 50.0, 'satisfaction': 50.0},
            now=meeting.clock())
        session.observe(action='exploring', now=meeting.clock() + 3.0)
        record = session.close(drives=drives, now=meeting.clock() + 5.0)
        meeting.visitor_ledger.record(record)
        return record

    def test_the_encounter_is_filed_against_the_individual(self):
        meeting = Encounter()
        meeting.admit()
        record = self._remember(meeting, {'happiness': 25.0, 'anxiety': 85.0,
                                          'satisfaction': 30.0})
        self.assertEqual(record.memory_key, f"peer:{HOST_UUID}")
        keys = {m['key'] for m in
                meeting.visitor_squid.memory_manager.short_term_memory
                + meeting.visitor_squid.memory_manager.long_term_memory}
        self.assertIn(f"peer:{HOST_UUID}", keys)

    def test_a_second_visit_recalls_the_individual_before_deciding(self):
        """The order matters: recalled BEFORE the action is chosen."""
        meeting = Encounter()
        meeting.admit()
        self._remember(meeting, {'happiness': 20.0, 'anxiety': 90.0,
                                 'satisfaction': 25.0})

        again = Encounter(host_squid=meeting.host_squid,
                          visitor_squid=meeting.visitor_squid)
        again.visitor_ledger.refresh()
        again.admit()
        again.host_sends_frame()
        again.visitor_receives()

        recalled = again.visitor_mind.recalled_sensors()
        self.assertGreater(recalled['conspecific_familiarity'], 0.0)
        self.assertGreater(recalled['conspecific_recalled_bad'], 0.0)
        self.assertEqual(again.visitor_mind.intents_sent, 0,
                         "memory has to be available before the first decision")

    def test_a_stranger_stays_distinguishable_from_a_remembered_peer(self):
        meeting = Encounter()
        meeting.admit()
        self._remember(meeting, {'happiness': 20.0, 'anxiety': 90.0,
                                 'satisfaction': 25.0})

        stranger = FakeSquid(OTHER_UUID, "Nobody", 600.0, 400.0)
        elsewhere = Encounter(host_squid=stranger,
                              visitor_squid=meeting.visitor_squid)
        elsewhere.visitor_ledger.refresh()
        elsewhere.admit()
        elsewhere.host_sends_frame()
        elsewhere.visitor_receives()

        recalled = elsewhere.visitor_mind.recalled_sensors()
        self.assertEqual(recalled['conspecific_familiarity'], 0.0)
        self.assertEqual(recalled['conspecific_recalled_bad'], 0.0)

    def test_the_recalled_values_reach_the_sensors_the_brain_reads(self):
        meeting = Encounter()
        meeting.admit()
        self._remember(meeting, {'happiness': 20.0, 'anxiety': 90.0,
                                 'satisfaction': 25.0})
        meeting.visitor_ledger.refresh()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        self.assertGreater(meeting.visitor_sensors.recalled_bad(), 0.0)
        self.assertGreater(meeting.visitor_sensors.familiarity(), 0.0)


# ===========================================================================
# 14. The network is unreliable
# ===========================================================================
class LinkFailureTests(unittest.TestCase):

    def test_an_intent_expires_so_a_visitor_cannot_run_on_forever(self):
        """The bug this prevents: the last packet before a drop was 'go left'."""
        meeting = Encounter()
        meeting.admit(x=100.0, y=400.0)
        intent = ActionIntent(meeting.actor.visit_id, 'act_move', seq=1,
                              sent_at=meeting.clock(), heading='right')
        self.assertTrue(meeting.host_body.apply_intent(meeting.actor, intent))

        meeting.clock.advance(INTENT_LEASE + 0.1)
        self.assertFalse(meeting.actor.is_under_control(meeting.clock()))
        later = ActionIntent(meeting.actor.visit_id, 'act_move', seq=2,
                             sent_at=meeting.clock() - INTENT_LEASE - 1.0,
                             heading='right')
        self.assertFalse(meeting.host_body.apply_intent(meeting.actor, later))

    def test_a_silent_visitor_stops_rather_than_carrying_on(self):
        meeting = Encounter()
        meeting.admit(x=100.0, y=400.0)
        meeting.clock.advance(LINK_TIMEOUT + 0.1)
        meeting.host_body.tick()
        self.assertEqual(meeting.actor.action, 'stalled')
        position = (meeting.actor.x, meeting.actor.y)
        meeting.clock.advance(1.0)
        meeting.host_body.tick()
        self.assertEqual((meeting.actor.x, meeting.actor.y), position,
                         "a stalled visitor must not drift")

    def test_a_visitor_that_never_speaks_again_is_sent_home(self):
        meeting = Encounter()
        meeting.admit()
        meeting.clock.advance(VISIT_ABANDON_TIMEOUT + 0.1)
        ending = meeting.host_body.tick()
        self.assertEqual([reason for _actor, reason in ending], ['link_lost'])

    def test_a_visitor_whose_host_goes_quiet_comes_home(self):
        """The one unrecoverable state: in nobody's tank. It must be impossible."""
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        self.assertTrue(meeting.visitor_mind.perception.away)
        self.assertFalse(meeting.visitor_squid.can_move)

        meeting.link.broken = True
        meeting.clock.advance(LINK_TIMEOUT + 0.1)
        meeting.visitor_mind.tick()

        self.assertFalse(meeting.visitor_mind.perception.away)
        self.assertTrue(meeting.visitor_squid.can_move)
        self.assertFalse(meeting.visitor_squid.is_transitioning)

    def test_a_dropped_frame_does_not_end_the_visit(self):
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.clock.advance(LINK_TIMEOUT * 0.5)
        meeting.visitor_mind.tick()
        self.assertTrue(meeting.visitor_mind.perception.away)

    def test_frames_that_arrive_out_of_order_are_ignored(self):
        meeting = Encounter()
        meeting.admit()
        first = meeting.host_body.build_frame(meeting.actor)
        second = meeting.host_body.build_frame(meeting.actor)
        self.assertTrue(meeting.visitor_mind.on_perception_frame(second.to_payload()))
        self.assertFalse(meeting.visitor_mind.on_perception_frame(first.to_payload()))

    def test_ending_a_visit_always_restores_the_squid(self):
        """Every failure path in the round trip ends here."""
        for reason in ('departed', 'ejected', 'link_lost'):
            with self.subTest(reason=reason):
                meeting = Encounter()
                meeting.admit()
                meeting.host_sends_frame()
                meeting.visitor_receives()
                meeting.visitor_mind.end_visit(reason=reason, notify=False)
                self.assertTrue(meeting.visitor_squid.can_move)
                self.assertFalse(meeting.visitor_squid.is_transitioning)
                self.assertEqual(meeting.visitor_mind.visit_id, '')

    def test_the_host_ending_a_visit_brings_the_visitor_home(self):
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.link.from_host(
            'visit_end',
            VisitEnd(meeting.actor.visit_id, END_LINK_LOST).to_payload())
        meeting.visitor_receives()
        self.assertTrue(meeting.visitor_squid.can_move)


# ===========================================================================
# 15. Private state never crosses
# ===========================================================================
class PrivacyTests(unittest.TestCase):
    """The host must never receive the visitor's cognitive state."""

    def test_nothing_the_visitor_sends_carries_private_state(self):
        meeting = Encounter(items=[FakeItem(560.0, 400.0)],
                            food=[FakeItem(150.0, 400.0, category='food')])
        meeting.admit(x=500.0, y=400.0)
        meeting.set_brain(**quiet_brain(act_play=95.0))
        for _ in range(4):
            meeting.cycle()
            meeting.clock.advance(0.5)
        meeting.visitor_mind.end_visit(reason='departed')

        self.assertTrue(meeting.link.sent_by_visitor)
        for kind, payload in meeting.link.sent_by_visitor:
            with self.subTest(message=kind):
                self._assert_clean(payload)

    def _assert_clean(self, value, path='payload'):
        if isinstance(value, dict):
            for key, inner in value.items():
                self.assertNotIn(str(key).lower(), FORBIDDEN_KEYS,
                                 f"{path}.{key} is private cognitive state")
                self._assert_clean(inner, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, inner in enumerate(value):
                self._assert_clean(inner, f"{path}[{index}]")

    def test_an_intent_carries_only_a_decision(self):
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.set_brain(**quiet_brain(act_flee=95.0))
        payload = meeting.visitor_decides().to_payload()
        self.assertEqual(
            set(payload),
            {'visit_id', 'seq', 'sent_at', 'action', 'activation',
             'confidence', 'heading', 'target_id', 'lease'})

    def test_a_message_carrying_private_state_is_refused_on_arrival(self):
        for key in ('weights', 'memory', 'anxiety', 'neurogenesis'):
            with self.subTest(key=key):
                payload = ActionIntent('v1', 'act_move').to_payload()
                payload[key] = {'anything': 1}
                with self.assertRaises(ProtocolError):
                    ActionIntent.from_payload(payload)

    def test_private_state_nested_deeper_is_also_refused(self):
        payload = ActionIntent('v1', 'act_move').to_payload()
        payload['target_id'] = 'item0'
        payload['detail'] = {'inner': {'weights': [1, 2, 3]}}
        with self.assertRaises(ProtocolError):
            ActionIntent.from_payload(payload)

    def test_the_host_cannot_reach_the_visitors_ledger(self):
        """Structural, not a promise: the host is not given one."""
        meeting = Encounter()
        meeting.admit()
        self.assertIsNone(getattr(meeting.host_body, 'peer_ledger', None))
        self.assertIsNone(getattr(meeting.actor, 'memory_manager', None))

    def test_a_visitor_cannot_name_a_file(self):
        """Item references are ids the host issued, never paths."""
        for value in ('../../etc/passwd', 'images/rock.png', '/tmp/x.png'):
            with self.subTest(target=value):
                payload = ActionIntent('v1', 'act_play').to_payload()
                payload['target_id'] = value
                self.assertEqual(ActionIntent.from_payload(payload).target_id, '')

    def test_an_invented_item_id_resolves_to_nothing(self):
        meeting = Encounter(items=[FakeItem(560.0, 400.0)])
        meeting.admit(x=500.0, y=400.0)
        intent = ActionIntent(meeting.actor.visit_id, 'act_play', seq=1,
                              sent_at=meeting.clock(), target_id='item999')
        meeting.host_body.apply_intent(meeting.actor, intent)
        self.assertEqual(meeting.actor.items_taken, 0)

    def test_a_visitor_cannot_grant_itself_an_endless_lease(self):
        payload = ActionIntent('v1', 'act_move').to_payload()
        payload['lease'] = 999999.0
        self.assertLessEqual(ActionIntent.from_payload(payload).lease, INTENT_LEASE)


# ===========================================================================
# No second brain
# ===========================================================================
class NoSecondBrainTests(unittest.TestCase):
    """The invariant, stated as tests rather than as a comment."""

    def test_the_host_builds_no_controller_for_a_visitor(self):
        import inspect
        from plugins.multiplayer import mp_plugin_logic
        source = inspect.getsource(
            mp_plugin_logic.MultiplayerPlugin.handle_squid_exit_message)
        self.assertNotIn("RemoteSquidController(", source,
                         "a visitor must not be given a stand-in brain")
        self.assertIn("host_body.admit", source)

    def test_the_host_holds_no_brain_state_for_a_visitor(self):
        meeting = Encounter()
        meeting.admit()
        for _ in range(3):
            meeting.cycle()
            meeting.clock.advance(0.5)
        held = vars(meeting.actor) if hasattr(meeting.actor, '__dict__') else {
            slot: getattr(meeting.actor, slot, None)
            for slot in meeting.actor.__slots__}
        for name in held:
            with self.subTest(field=name):
                self.assertNotIn(name.lower(), FORBIDDEN_KEYS)

    def test_the_visitors_decision_needs_its_own_brain_to_be_present(self):
        """With no brain state there is no decision - nothing substitutes."""
        meeting = Encounter()
        meeting.admit()
        meeting.host_sends_frame()
        meeting.visitor_receives()
        meeting.visitor_tank.brain_window.brain_widget.state = {}
        self.assertIsNone(meeting.visitor_decides())


if __name__ == "__main__":
    unittest.main()


# ===========================================================================
# The first-sight indicator
# ===========================================================================
class NoticingAnotherSquidTests(unittest.TestCase):
    """Both squid show that they have seen each other, once, for 3 seconds."""

    class FakeMentalStates:
        def __init__(self):
            self.active = {}
            self.history = []

        def set_state(self, name, is_active):
            self.active[name] = is_active
            self.history.append((name, is_active))

        def is_state_active(self, name):
            return bool(self.active.get(name))

    def _squid_with_states(self):
        from src.squid import Squid
        squid = FakeSquid(HOST_UUID, "Resident")
        squid.mental_state_manager = self.FakeMentalStates()
        squid.is_sleeping = False
        squid._seen_squids = set()
        squid.show_noticed_squid_icon = lambda: Squid.show_noticed_squid_icon(squid)
        squid.hide_noticed_squid_icon = lambda: Squid.hide_noticed_squid_icon(squid)
        squid.process_squid_detection = (
            lambda peer, visible=True: Squid.process_squid_detection(squid, peer, visible))
        return squid

    def test_the_notice_state_is_not_the_curious_state(self):
        """Sharing the icon must not mean sharing the state.

        The real curious state is set by the squid being curious. If this
        display reused it, a visitor arriving would switch genuine curiosity
        on - and, three seconds later, switch it off again underneath the
        thing that had actually set it.
        """
        from src.mental_states import MentalStateManager
        states = MentalStateManager.__new__(MentalStateManager)
        self.assertIn('noticed_squid', MentalStateManager(
            type("S", (), {})(), None).mental_states)
        manager = MentalStateManager(type("S", (), {})(), None)
        self.assertNotEqual(manager.mental_states['noticed_squid'],
                            manager.mental_states['curious'])
        self.assertEqual(manager.mental_states['noticed_squid'].icon_filename,
                         manager.mental_states['curious'].icon_filename)

    def test_noticing_does_not_disturb_a_genuinely_curious_squid(self):
        squid = self._squid_with_states()
        squid.mental_state_manager.set_state("curious", True)
        squid.process_squid_detection(VISITOR_UUID, True)
        self.assertTrue(squid.mental_state_manager.is_state_active("curious"))
        squid.hide_noticed_squid_icon()
        self.assertTrue(squid.mental_state_manager.is_state_active("curious"),
                        "clearing the notice must not clear real curiosity")

    def test_the_resident_notices_a_visitor_once(self):
        squid = self._squid_with_states()
        squid.process_squid_detection(VISITOR_UUID, True)
        self.assertTrue(squid.mental_state_manager.is_state_active("noticed_squid"))

        squid.hide_noticed_squid_icon()
        squid.process_squid_detection(VISITOR_UUID, True)
        self.assertFalse(squid.mental_state_manager.is_state_active("noticed_squid"),
                         "an encounter is noticed once, not on every tick")

    def test_a_different_squid_is_noticed_separately(self):
        squid = self._squid_with_states()
        squid.process_squid_detection(VISITOR_UUID, True)
        squid.hide_noticed_squid_icon()
        squid.process_squid_detection(OTHER_UUID, True)
        self.assertTrue(squid.mental_state_manager.is_state_active("noticed_squid"))

    def test_the_host_makes_the_resident_notice_its_visitor(self):
        meeting = Encounter()
        noticed = []
        meeting.host_squid.process_squid_detection = (
            lambda peer, visible=True: noticed.append(peer))
        meeting.admit()
        self.assertEqual(noticed, [VISITOR_UUID])

        meeting.host_body.build_frame(meeting.actor)
        self.assertEqual(noticed, [VISITOR_UUID], "only the first sighting")

    def test_the_host_records_the_visitors_own_first_sight(self):
        """The visitor's icon is driven by when it could first SEE the resident."""
        meeting = Encounter()
        meeting.admit(x=300.0, y=400.0)          # inside sight range
        self.assertEqual(meeting.host_body.drain_first_sightings(), [])
        meeting.host_body.build_frame(meeting.actor)
        self.assertEqual([a.uuid for a in meeting.host_body.drain_first_sightings()],
                         [VISITOR_UUID])
        meeting.host_body.build_frame(meeting.actor)
        self.assertEqual(meeting.host_body.drain_first_sightings(), [],
                         "first sight happens once")

    def test_a_visitor_too_far_away_has_not_seen_anything_yet(self):
        meeting = Encounter()
        meeting.admit(x=0.0, y=0.0)              # well outside sight range
        meeting.host_body.build_frame(meeting.actor)
        self.assertEqual(meeting.host_body.drain_first_sightings(), [])
        self.assertFalse(meeting.actor.has_seen_resident)
