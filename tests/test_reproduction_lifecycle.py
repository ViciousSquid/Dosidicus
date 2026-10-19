"""Reproduction, parental starvation and the egg.

The lifecycle under test:

    a visit -> sustained contact in the HOST tank -> one roll per visit
        -> (rarely) a mating, decided and recorded by the host
            -> the resident becomes a parent, its egg is laid, ONE save
                -> the visitor is told, and remembers it once
            -> the parent no longer eats, starves on the ordinary metabolism
                -> it dies once -> its egg hatches once

Everything here runs the real code: Lifecycle, TamagotchiLogic's own methods
(update_statistics, record_reproduction, save_game, load_game, the hatch
trigger), the real SaveManager zip files, HostBody and VisitorMind speaking the
real protocol, and the multiplayer plugin's own handlers. The fakes are only
the edges with no bearing on the lifecycle: the squid's body and UI, the
brain window, the socket.

The hatch itself - the new game it starts - is in test_new_game_and_hatch.py,
against the real main window.
"""

import json
import logging
import os
import random
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from PyQt5 import QtWidgets                                  # noqa: E402

from src.lifecycle import (                                  # noqa: E402
    DEFAULT_CONFIG, EGG_HATCHING, EGG_INCUBATING, Lifecycle,
    STAGE_DEAD, STAGE_LIVING, STAGE_PARENT,
)
from src.memory_manager import MemoryManager                 # noqa: E402
from src.personality import Personality                      # noqa: E402
from src.save_manager import SaveManager                     # noqa: E402
from src.squid import Squid                                  # noqa: E402
from src.squid_statistics import SquidStatistics             # noqa: E402
from src.tamagotchi_logic import TamagotchiLogic             # noqa: E402

from plugins.multiplayer.consent import REASON_CLOSED        # noqa: E402
from plugins.multiplayer.encounter_sensors import ConspecificView  # noqa: E402
from plugins.multiplayer.host_body import (                  # noqa: E402
    HostBody, MATED_ANNOUNCEMENTS, MATING_CONTACT_RANGE,
)
from plugins.multiplayer.identity import SquidIdentity       # noqa: E402
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin  # noqa: E402
from plugins.multiplayer.peer_ledger import PeerLedger       # noqa: E402
from plugins.multiplayer.remote_entity_manager import RemoteEntityManager  # noqa: E402
from plugins.multiplayer.remote_protocol import (            # noqa: E402
    ActionIntent, Consequence, CONSEQUENCE_MATED, FORBIDDEN_KEYS,
    VISIT_ABANDON_TIMEOUT, mating_id_for,
)
from plugins.multiplayer.visitor_mind import VisitorMind     # noqa: E402

APP = None
_TMPDIR = None
_PREV_CWD = None

RESIDENT_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
VISITOR_UUID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_UUID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

#: One frame of a GIF, for drawing the fight cloud without the real artwork.
TINY_GIF = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff'
            b'!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01'
            b'\x00\x00\x02\x02D\x01\x00;')


def setUpModule():
    global APP, _TMPDIR, _PREV_CWD
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _PREV_CWD = os.getcwd()
    # MemoryManager writes to ./_memory; keep it out of the working tree.
    _TMPDIR = tempfile.TemporaryDirectory(prefix="dosidicus-lifecycle-")
    os.chdir(_TMPDIR.name)
    logging.getLogger("lifecycle-test").addHandler(logging.NullHandler())


def tearDownModule():
    os.chdir(_PREV_CWD)
    _TMPDIR.cleanup()


# ===========================================================================
# The tank: real TamagotchiLogic methods over a small body and UI
# ===========================================================================
class Clock:
    def __init__(self, now=10_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now


class LiteSquid:
    """The parts of a squid the lifecycle, the tick and the save touch."""

    def __init__(self, uuid, name, x=600.0, y=400.0,
                 personality=Personality.LAZY):
        self.uuid = uuid
        self.name = name
        self.personality = personality
        self.squid_x, self.squid_y = float(x), float(y)
        self.squid_width, self.squid_height = 60.0, 40.0
        self.squid_direction = 'right'
        self.hunger, self.sleepiness = 25.0, 30.0
        self.happiness, self.cleanliness = 100.0, 100.0
        self.satisfaction, self.anxiety, self.curiosity = 50.0, 10.0, 50.0
        self.health = 100.0
        self.is_sick = False
        self.is_sleeping = False
        self.is_fleeing = False
        self.pursuing_food = False
        self.status = 'roaming'
        self.can_move = True
        self.is_transitioning = False
        self.carrying_rock = False
        self.current_rock = None
        self.squid_item = None
        self.neural_drive = None
        self.lifecycle = Lifecycle()
        self.statistics = SquidStatistics(self)
        self.memory_manager = MemoryManager()
        self.memory_manager.save_memory = lambda memory, path: None
        self.memory_manager.short_term_memory = []
        self.memory_manager.long_term_memory = []
        self.mental_state_manager = SimpleNamespace(set_state=lambda *a: None)

    def is_near_plant(self):
        return False

    def clear_neural_drive(self):
        self.neural_drive = None


class Hooks:
    """PluginManager's hook surface, recording what the core announces."""

    def __init__(self):
        self.plugins = {}
        self.hooks = {}
        self.triggered = []

    def register_hook(self, name):
        self.hooks.setdefault(name, [])

    def subscribe(self, name, callback):
        self.hooks.setdefault(name, []).append(callback)

    def trigger_hook(self, name, **kwargs):
        self.triggered.append(name)
        return [callback(**kwargs) for callback in self.hooks.get(name, [])]


class FakeWindow:
    """Stands in for MainWindow.hatch_egg; the real one is tested elsewhere."""

    def __init__(self):
        self.hatched = []

    def hatch_egg(self, egg_id):
        self.hatched.append(egg_id)
        return True


def make_tank(save_dir, squid, window=None):
    logic = object.__new__(TamagotchiLogic)
    logic.squid = squid
    logic.user_interface = SimpleNamespace(
        scene=QtWidgets.QGraphicsScene(),
        window_width=1280, window_height=900,
        get_decorations_data=lambda: [],
        load_decorations_data=lambda data: None,
        update_dirty_text=lambda value: None,
        cleanliness_overlay=SimpleNamespace(setBrush=lambda brush: None),
        window=window or FakeWindow(),
    )
    logic.brain_window = SimpleNamespace(brain_widget=SimpleNamespace(),
                                         get_brain_state=lambda: {},
                                         set_brain_state=lambda state: None)
    logic.statistics_window = SimpleNamespace(score=0,
                                              set_score=lambda score: None,
                                              update_statistics=lambda: None)
    logic.save_manager = SaveManager(save_dir)
    logic.plugin_manager = Hooks()
    logic.lifecycle_config = dict(DEFAULT_CONFIG)
    logic.simulation_speed = 1
    logic.cleanliness_threshold_time = 0
    logic.hunger_threshold_time = 0
    logic.last_clean_time = 0
    logic.plant_calming_effect_counter = 0
    logic.hebbian_learning = None
    logic.refresh_neuron_count = lambda: None
    logic.set_simulation_speed = lambda speed: None
    logic.egg_item = None
    logic.messages = []
    logic.show_message = logic.messages.append
    return logic


def eggs_in(logic):
    return [item for item in logic.user_interface.scene.items()
            if getattr(item, 'category', '') == 'egg']


def saved_game_state(logic):
    """game_state.json from the newest save, read straight out of the zip."""
    path = logic.save_manager.get_latest_save()
    with zipfile.ZipFile(path) as archive:
        return json.loads(archive.read('game_state.json').decode('utf-8'))


def tick_until(logic, condition, limit):
    for ticks in range(1, limit + 1):
        logic.update_statistics()
        if condition():
            return ticks
    return None


# ===========================================================================
# A visit: a resident tank (with the real multiplayer plugin's handlers) and
# a visiting squid's mind, joined by a loopback wire
# ===========================================================================
class FakeNode:
    def __init__(self):
        self.sent = []
        self.is_connected = False
        self.socket = None
        self.node_id = 'squid_host01'

    def send_message(self, message_type, payload):
        self.sent.append((message_type, payload))
        return True


class FakeEntities:
    def __init__(self):
        self.removed = []

    def update_remote_squid(self, node_id, payload, is_new_arrival=False):
        return True

    def get_last_calculated_entry_details(self, node_id):
        return None

    def remove_remote_squid(self, node_id):
        self.removed.append(node_id)

    def show_notice_icon(self, node_id):
        return True

    def cleanup_all(self):
        pass


class Visit:
    """Resident tank + plugin as host, a VisitorMind as the visitor's home."""

    def __init__(self, tmp, chance=1.0, contact_seconds=5.0, rng=None,
                 visitor_uuid=VISITOR_UUID, visitor_name="Traveller",
                 resident=None, logic=None, clock=None, visitor_memory=None):
        self.clock = clock or Clock()
        self.resident = resident or LiteSquid(RESIDENT_UUID, "Resident")
        self.logic = logic or make_tank(os.path.join(tmp, 'host_saves'), self.resident)

        plugin = MultiplayerPlugin()
        plugin.logger = logging.getLogger("lifecycle-test")
        plugin.tamagotchi_logic = self.logic
        plugin.local_identity = SquidIdentity.from_squid(self.resident)
        plugin.peer_ledger = PeerLedger(self.resident.memory_manager)
        plugin.conspecific_view = ConspecificView(clock=self.clock)
        plugin.network_node = FakeNode()
        plugin.entity_manager = FakeEntities()
        plugin._show_exit_arrow = lambda direction: None
        # Wired exactly as install_encounter_sensors wires it.
        plugin.host_body = HostBody(
            tamagotchi_logic=self.logic, conspecific_view=plugin.conspecific_view,
            clock=self.clock, logger=plugin.logger, mating_chance=chance,
            mating_contact_seconds=contact_seconds,
            rng=rng or random.Random(7).random, on_mating=plugin.record_mating)
        self.logic.plugin_manager.subscribe("on_squid_died",
                                            plugin.handle_resident_died)
        self.plugin = plugin
        self.host = plugin.host_body

        self.visitor_squid = LiteSquid(visitor_uuid, visitor_name, 0.0, 0.0,
                                       personality=Personality.ADVENTUROUS)
        if visitor_memory is not None:
            self.visitor_squid.memory_manager = visitor_memory
        self.visitor_tank = SimpleNamespace(squid=self.visitor_squid,
                                            brain_window=None)
        self.visitor_ledger = PeerLedger(self.visitor_squid.memory_manager)
        self.visitor_mind = VisitorMind(tamagotchi_logic=self.visitor_tank,
                                        peer_ledger=self.visitor_ledger,
                                        send=lambda t, p: True, clock=self.clock)
        self.identity = SquidIdentity.from_squid(self.visitor_squid)
        self.actor = None
        self.seq = 0

    def arrive(self, x=None, y=None):
        """Through the plugin's own entry handler: consent, body, first frame."""
        message = {'payload': {'payload': {
            'node_id': 'squid_vis001', 'direction': 'left',
            'identity': self.identity.to_payload()}}}
        admitted = self.plugin.handle_squid_exit_message(None, message, ('lan', 0))
        self.actor = self.host.visitor(self.identity.uuid)
        if self.actor is not None:
            self.actor.x = self.resident.squid_x + 20 if x is None else x
            self.actor.y = self.resident.squid_y if y is None else y
            self.visitor_mind.begin_visit(SquidIdentity.from_squid(self.resident))
            self.deliver_frame()
        return admitted

    def deliver_frame(self):
        frame = self.host.build_frame(self.actor).to_payload()
        self.visitor_mind.on_perception_frame(frame)

    def intent(self, action='act_rest', seq=None):
        """An intent as it would arrive: through the protocol's validation."""
        self.seq = self.seq + 1 if seq is None else seq
        payload = ActionIntent(self.actor.visit_id, action, seq=self.seq,
                               sent_at=self.clock()).to_payload()
        return self.host.apply_intent(self.actor,
                                      ActionIntent.from_payload(payload))

    def hold_contact(self, seconds, step=0.5):
        elapsed = 0.0
        while elapsed <= seconds:
            self.intent()
            self.clock.advance(step)
            elapsed += step

    def round_trip(self, deliver=True):
        """The host's cadence: housekeeping, then consequences to the visitor."""
        ending = self.host.tick()
        sent = []
        for actor in list(self.host.visitors.values()):
            for consequence in self.host.drain_consequences(actor):
                payload = consequence.to_payload()
                sent.append(payload)
                if deliver:
                    self.visitor_mind.on_consequence(payload)
        return ending, sent

    def visitor_mating_memories(self):
        return [m for m in self.visitor_squid.memory_manager.get_memories_by_key_prefix(
                    'social', 'peer:') if ':mating:' in m.get('key', '')]


# ===========================================================================
# 1. A squid that never meets another squid
# ===========================================================================
class IsolatedSquidTests(unittest.TestCase):

    def test_an_isolated_squid_never_reproduces_or_starves(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid = LiteSquid(RESIDENT_UUID, "Alone")
            logic = make_tank(tmp, squid)
            random.seed(3)
            for _ in range(3000):            # fifty minutes of neglect
                logic.update_statistics()
            self.assertEqual(squid.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(squid.hunger, 100)
            # Health never moved: the starvation rule is a parent's alone, and
            # the tank's health loss was never applied to anyone before it.
            self.assertEqual(squid.health, 100.0)
            self.assertEqual(eggs_in(logic), [])
            self.assertNotIn("on_squid_died", logic.plugin_manager.triggered)

    def test_reproduction_has_no_path_outside_a_visit(self):
        """Only HostBody ever calls record_reproduction, and only for a visitor."""
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            # The resident moves about its own tank for a long time, with no
            # visitor: no contact can exist, so no roll is ever made.
            for _ in range(100):
                visit.host.tick()
                visit.clock.advance(0.5)
            self.assertEqual(visit.resident.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(eggs_in(visit.logic), [])


# ===========================================================================
# 2. Rarity
# ===========================================================================
class RarityTests(unittest.TestCase):

    def _visits(self, count, contact_seconds, chance, seed=1234):
        """`count` independent visits with sustained contact; how many mated."""
        matings = []
        rng = random.Random(seed).random
        clock = Clock()
        tank = SimpleNamespace(squid=LiteSquid(RESIDENT_UUID, "Resident"),
                               user_interface=SimpleNamespace(window_width=1280,
                                                              window_height=900))
        host = HostBody(tank, ConspecificView(clock=clock), clock=clock,
                        mating_chance=chance, rng=rng,
                        on_mating=lambda actor, mid: matings.append(mid) or True)
        identity = SquidIdentity(uuid=VISITOR_UUID, name="Traveller")
        for n in range(count):
            actor = host.admit(identity, f"visit{n}", 620.0, 400.0)
            seq = 0
            elapsed = 0.0
            while elapsed <= contact_seconds:
                seq += 1
                host.apply_intent(actor, ActionIntent(actor.visit_id, 'act_rest',
                                                      seq=seq, sent_at=clock()))
                clock.advance(0.5)
                elapsed += 0.5
            host.remove(identity.uuid)
        return matings

    def test_sustained_contact_rarely_produces_a_mating(self):
        matings = self._visits(1000, contact_seconds=6.0,
                               chance=DEFAULT_CONFIG['mating_chance'])
        # About 2%: one roll per visit, at the configured chance.
        self.assertGreater(len(matings), 5)
        self.assertLess(len(matings), 45)

    def test_brief_contact_is_never_a_mating_even_at_certainty(self):
        matings = self._visits(200, contact_seconds=4.0, chance=1.0)
        self.assertEqual(matings, [])

    def test_one_roll_per_visit_however_long_it_lasts(self):
        rolls = []
        clock = Clock()
        tank = SimpleNamespace(squid=LiteSquid(RESIDENT_UUID, "Resident"),
                               user_interface=None)

        def rng():
            rolls.append(1)
            return 0.99                     # never a mating

        host = HostBody(tank, ConspecificView(clock=clock), clock=clock,
                        mating_chance=0.02, rng=rng)
        actor = host.admit(SquidIdentity(uuid=VISITOR_UUID), "v1", 620.0, 400.0)
        for seq in range(1, 400):           # over three minutes in contact
            host.apply_intent(actor, ActionIntent("v1", 'act_rest', seq=seq,
                                                  sent_at=clock()))
            clock.advance(0.5)
        self.assertEqual(len(rolls), 1)

    def test_contact_needs_the_bodies_within_reach(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive(x=visit.resident.squid_x + MATING_CONTACT_RANGE + 50)
            visit.hold_contact(30.0)
            self.assertEqual(visit.resident.lifecycle.stage, STAGE_LIVING)

    def test_a_resident_away_on_its_own_visit_cannot_mate_at_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.resident.is_transitioning = True   # its body is elsewhere
            visit.resident.can_move = False
            visit.hold_contact(10.0)
            self.assertEqual(visit.resident.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(eggs_in(visit.logic), [])


# ===========================================================================
# 3. A mating: exactly one egg, in the resident's tank, recorded on both sides
# ===========================================================================
class MatingTests(unittest.TestCase):

    def test_a_mating_lays_exactly_one_egg_in_the_resident_tank(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            self.assertTrue(visit.arrive())
            visit.hold_contact(6.0)

            lifecycle = visit.resident.lifecycle
            self.assertEqual(lifecycle.stage, STAGE_PARENT)
            self.assertEqual(lifecycle.mate_uuid, VISITOR_UUID)
            self.assertEqual(lifecycle.mating_id, mating_id_for(visit.actor.visit_id))
            self.assertEqual(len(eggs_in(visit.logic)), 1)
            self.assertEqual(lifecycle.egg_state, EGG_INCUBATING)
            # Nothing happened to the visitor's own body or lifecycle.
            self.assertEqual(visit.visitor_squid.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(visit.visitor_squid.hunger, 25.0)

    def test_the_mating_and_the_egg_are_saved_together_before_the_visitor_hears(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            # Not yet told: the consequence goes out on the next round trip...
            self.assertEqual(visit.visitor_mind.consequences, [])
            # ...but the save already holds the parent AND its egg, in the one
            # record, so a crash now cannot keep one without the other.
            state = saved_game_state(visit.logic)['lifecycle']
            self.assertEqual(state['stage'], STAGE_PARENT)
            self.assertEqual(state['egg']['state'], EGG_INCUBATING)
            self.assertEqual(state['egg']['egg_id'], state['reproduction']['mating_id'])

    def test_the_visitor_remembers_the_mating_once_however_often_it_is_told(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            told = []
            for _ in range(MATED_ANNOUNCEMENTS + 3):
                told.extend(p for p in visit.round_trip()[1]
                            if p['kind'] == CONSEQUENCE_MATED)
            self.assertEqual(len(told), MATED_ANNOUNCEMENTS)
            # A packet replayed on the wire after the fact changes nothing.
            visit.visitor_mind.on_consequence(told[0])
            visit.visitor_mind.end_visit(notify=False)

            memories = visit.visitor_mating_memories()
            self.assertEqual(len(memories), 1)
            self.assertEqual(memories[0]['value']['outcome'], 'mated')
            self.assertTrue(visit.visitor_ledger.has_mated(visit.resident.lifecycle.mating_id))
            # Remembered as an encounter with THAT individual.
            self.assertTrue(memories[0]['key'].startswith(f"peer:{RESIDENT_UUID}:"))

    def test_the_resident_files_the_mating_against_the_visitor(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            visit.plugin.close_encounter(VISITOR_UUID)
            memories = [m for m in visit.resident.memory_manager.get_memories_by_key_prefix(
                'social', 'peer:') if ':mating:' in m['key']]
            self.assertEqual(len(memories), 1)
            self.assertEqual(memories[0]['value']['detail']['mating_id'],
                             visit.resident.lifecycle.mating_id)

    def test_what_crosses_the_wire_is_an_id_and_nothing_private(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            _, sent = visit.round_trip(deliver=False)
            mated = [p for p in sent if p['kind'] == CONSEQUENCE_MATED]
            self.assertEqual(len(mated), 1)
            self.assertEqual(set(mated[0]['detail']), {'mating_id'})
            parsed = Consequence.from_payload(mated[0])     # passes validation
            self.assertEqual(parsed.kind, CONSEQUENCE_MATED)
            self.assertFalse(FORBIDDEN_KEYS & set(json.dumps(mated[0]).split('"')))

    def test_a_malformed_mating_id_is_ignored_by_the_visitor(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=0.0)
            visit.arrive()
            visit.visitor_mind.on_consequence(Consequence(
                visit.actor.visit_id, CONSEQUENCE_MATED,
                detail={'mating_id': '../../etc'}).to_payload())
            visit.visitor_mind.end_visit(notify=False)
            self.assertEqual(visit.visitor_mating_memories(), [])


# ===========================================================================
# 4. Repeats, retransmissions, disconnects, resets
# ===========================================================================
class IdempotencyTests(unittest.TestCase):

    def test_a_retransmitted_intent_cannot_lay_a_second_egg(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            last = visit.seq
            # The same packet again, and again out of order: rejected by seq.
            self.assertFalse(visit.intent(seq=last))
            self.assertFalse(visit.intent(seq=1))
            # And a long time more in contact: the visit has had its roll.
            visit.hold_contact(30.0)
            self.assertEqual(len(eggs_in(visit.logic)), 1)

    def test_recording_the_same_mating_twice_lays_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid = LiteSquid(RESIDENT_UUID, "Resident")
            logic = make_tank(tmp, squid)
            self.assertTrue(logic.record_reproduction("v1-mate", VISITOR_UUID, "T"))
            self.assertFalse(logic.record_reproduction("v1-mate", VISITOR_UUID, "T"))
            self.assertFalse(logic.record_reproduction("v2-mate", OTHER_UUID, "O"))
            self.assertEqual(len(eggs_in(logic)), 1)
            self.assertEqual(squid.lifecycle.mating_id, "v1-mate")

    def test_a_later_visit_cannot_make_a_parent_reproduce_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Visit(tmp, chance=1.0)
            first.arrive()
            first.hold_contact(6.0)
            first.plugin.end_visit_as_host(first.actor)
            second = Visit(tmp, chance=1.0, visitor_uuid=OTHER_UUID,
                           visitor_name="Other", resident=first.resident,
                           logic=first.logic, clock=first.clock)
            self.assertTrue(second.arrive())
            second.hold_contact(30.0)
            self.assertEqual(len(eggs_in(first.logic)), 1)
            self.assertEqual(first.resident.lifecycle.mate_uuid, VISITOR_UUID)

    def test_a_lost_link_after_the_mating_keeps_it_and_the_mate_hears_next_time(self):
        """The crash/disconnect window: recorded, but the news never arrived."""
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryManager()
            memory.save_memory = lambda m, p: None
            memory.short_term_memory, memory.long_term_memory = [], []
            visit = Visit(tmp, chance=1.0, visitor_memory=memory)
            visit.arrive()
            visit.hold_contact(6.0)
            mating_id = visit.resident.lifecycle.mating_id

            # Every announcement is lost, and the host gives up on the visit.
            for _ in range(MATED_ANNOUNCEMENTS):
                visit.round_trip(deliver=False)
            visit.clock.advance(VISIT_ABANDON_TIMEOUT + 1)
            ending, _ = visit.round_trip(deliver=False)
            for actor, reason in ending:
                visit.plugin.end_visit_as_host(actor, reason)
            visit.visitor_mind.end_visit(notify=False)
            self.assertEqual(visit.host.visitors, {})
            self.assertEqual(visit.visitor_mating_memories(), [])
            # The host's record is untouched by the lost link.
            self.assertEqual(visit.resident.lifecycle.stage, STAGE_PARENT)
            self.assertEqual(len(eggs_in(visit.logic)), 1)

            # The same individual comes back: it is told, and files it once.
            again = Visit(tmp, chance=1.0, resident=visit.resident,
                          logic=visit.logic, clock=visit.clock,
                          visitor_memory=memory)
            again.arrive()
            for _ in range(MATED_ANNOUNCEMENTS + 2):
                again.round_trip()
            again.visitor_mind.end_visit(notify=False)
            memories = again.visitor_mating_memories()
            self.assertEqual(len(memories), 1)
            self.assertEqual(memories[0]['value']['detail']['mating_id'], mating_id)

            # And a third visit, after the visitor already knows, adds nothing.
            third = Visit(tmp, chance=1.0, resident=visit.resident,
                          logic=visit.logic, clock=visit.clock,
                          visitor_memory=memory)
            third.arrive()
            for _ in range(MATED_ANNOUNCEMENTS + 2):
                third.round_trip()
            third.visitor_mind.end_visit(notify=False)
            self.assertEqual(len(third.visitor_mating_memories()), 1)
            self.assertEqual(len(eggs_in(visit.logic)), 1)

    def test_a_plugin_reset_ends_visits_and_leaves_the_lifecycle_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            node = visit.plugin.network_node
            visit.plugin.is_setup = True
            visit.plugin.shutdown()           # what PluginManager.unload calls
            self.assertEqual(visit.host.visitors, {})
            self.assertIn('visit_end', [t for t, _ in node.sent])
            self.assertIsNone(visit.plugin.network_node)   # closed and released
            self.assertFalse(visit.plugin.is_setup)        # sync thread stops
            self.assertEqual(visit.resident.lifecycle.stage, STAGE_PARENT)
            self.assertEqual(len(eggs_in(visit.logic)), 1)

    def test_shutting_down_a_plugin_that_never_started_does_nothing(self):
        plugin = MultiplayerPlugin()
        plugin.shutdown()                   # no logger, never set up
        self.assertFalse(plugin.is_setup)


# ===========================================================================
# 5. The parent: stops eating, starves, dies once
# ===========================================================================
class ParentStarvationTests(unittest.TestCase):

    def _parent(self, tmp):
        squid = LiteSquid(RESIDENT_UUID, "Parent")
        logic = make_tank(tmp, squid)
        self.assertTrue(logic.record_reproduction("v1-mate", VISITOR_UUID, "Mate"))
        return squid, logic

    def test_a_parent_refuses_food_through_the_one_eating_path(self):
        squid = object.__new__(Squid)       # the real Squid.eat, no body needed
        squid.lifecycle = Lifecycle()
        squid.lifecycle.record_reproduction("v1-mate", VISITOR_UUID)
        food = object()
        self.assertFalse(squid.eat(food))
        self.assertFalse(squid.lifecycle.can_eat)
        self.assertFalse(squid.lifecycle.can_visit)

    def test_a_visiting_squids_meal_does_not_feed_a_parent(self):
        visitor = LiteSquid(VISITOR_UUID, "Parent", personality=Personality.LAZY)
        visitor.lifecycle.record_reproduction("v1-mate", OTHER_UUID)
        visitor.hunger = 95.0
        mind = VisitorMind(tamagotchi_logic=SimpleNamespace(squid=visitor),
                           send=lambda t, p: True)
        mind.visit_id = 'v9'
        mind.on_consequence({'visit_id': 'v9', 'kind': 'ate', 'at': 1.0,
                             'detail': {'ok': True}})
        self.assertEqual(visitor.hunger, 95.0)

    def test_a_parent_starves_to_death_on_the_ordinary_metabolism(self):
        with tempfile.TemporaryDirectory() as tmp:
            random.seed(11)
            squid, logic = self._parent(tmp)
            ticks = tick_until(logic, lambda: squid.lifecycle.is_dead, 20_000)
            self.assertIsNotNone(ticks)
            self.assertEqual(squid.health, 0.0)
            self.assertGreaterEqual(squid.hunger, DEFAULT_CONFIG['starvation_hunger'])
            self.assertEqual(logic.plugin_manager.triggered.count("on_squid_died"), 1)
            self.assertFalse(squid.can_move)
            self.assertEqual(squid.status, "dead")
            # A dead squid has no metabolism and does not die again.
            hunger = squid.hunger
            for _ in range(200):
                logic.update_statistics()
            self.assertEqual(squid.hunger, hunger)
            self.assertEqual(logic.plugin_manager.triggered.count("on_squid_died"), 1)
            self.assertEqual(saved_game_state(logic)['lifecycle']['stage'], STAGE_DEAD)

    def test_starvation_takes_the_expected_time_at_normal_speed(self):
        """At speed 1 one tick is one second. Measured, not assumed.

        Hunger rises 0.1 per waking tick, so from a fed 25 it reaches the
        starvation line of 90 in 650 ticks; health then falls by the tank's
        own 0.1 (0.2 once happiness and cleanliness are both below 20) per
        tick from 100.
        """
        with tempfile.TemporaryDirectory() as tmp:
            random.seed(5)
            squid, logic = self._parent(tmp)
            starving = tick_until(
                logic, lambda: squid.hunger >= DEFAULT_CONFIG['starvation_hunger'], 5000)
            self.assertAlmostEqual(starving, 650, delta=2)   # float steps of 0.1
            # Nothing lost before the line; the tick that crosses it loses one.
            self.assertGreaterEqual(squid.health, 99.85)
            dying = tick_until(logic, lambda: squid.lifecycle.is_dead, 5000)
            minutes = (starving + dying) / 60.0
            # 10.8 minutes to starve, then between 8.3 and 16.7 minutes to die.
            self.assertGreaterEqual(dying, 500)
            self.assertLessEqual(dying, 1000)
            self.assertTrue(19.0 <= minutes <= 28.0, minutes)

    def test_sleep_pauses_starvation_as_it_pauses_hunger(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic = self._parent(tmp)
            squid.hunger = 99.0
            squid.is_sleeping = True
            for _ in range(500):
                logic.update_statistics()
            self.assertEqual(squid.health, 100.0)
            self.assertEqual(squid.lifecycle.stage, STAGE_PARENT)

    def test_the_starvation_line_is_configurable(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic = self._parent(tmp)
            logic.lifecycle_config['starvation_hunger'] = 30.0
            squid.hunger = 31.0
            logic.update_statistics()
            self.assertLess(squid.health, 100.0)

    def test_the_mate_and_bystanders_are_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            bystander = LiteSquid(OTHER_UUID, "Bystander")
            bystander_tank = make_tank(os.path.join(tmp, 'other'), bystander)
            random.seed(2)
            for _ in range(3000):
                visit.logic.update_statistics()
                bystander_tank.update_statistics()
            self.assertTrue(visit.resident.lifecycle.is_dead)
            self.assertEqual(bystander.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(bystander.health, 100.0)
            self.assertEqual(visit.visitor_squid.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(visit.visitor_squid.health, 100.0)


# ===========================================================================
# 6. Death and multiplayer: nothing left dangling
# ===========================================================================
class DeathAndVisitsTests(unittest.TestCase):

    def test_a_dead_resident_ends_its_visits_and_refuses_new_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            visit.arrive()
            visit.hold_contact(6.0)
            visit.resident.health = 0.0
            visit.resident.hunger = 100.0
            visit.logic.update_statistics()         # the death, through the tick
            self.assertTrue(visit.resident.lifecycle.is_dead)
            self.assertEqual(visit.host.visitors, {})
            self.assertEqual(visit.plugin.open_encounters, {})
            sent = [t for t, _ in visit.plugin.network_node.sent]
            self.assertIn('visit_end', sent)

            latecomer = Visit(tmp, chance=1.0, visitor_uuid=OTHER_UUID,
                              resident=visit.resident, logic=visit.logic,
                              clock=visit.clock)
            self.assertFalse(latecomer.arrive())
            response = [p for t, p in latecomer.plugin.network_node.sent
                        if t == 'visit_response'][-1]
            self.assertFalse(response['accepted'])
            self.assertEqual(response['reason'], REASON_CLOSED)
            self.assertEqual(latecomer.host.visitors, {})


# ===========================================================================
# 7. Save, load, and the hatch trigger
# ===========================================================================
class PersistenceTests(unittest.TestCase):

    def test_a_starving_parent_and_its_egg_survive_a_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid = LiteSquid(RESIDENT_UUID, "Parent")
            logic = make_tank(tmp, squid)
            logic.record_reproduction("v1-mate", VISITOR_UUID, "Mate")
            squid.hunger, squid.health = 95.0, 40.0
            logic.save_game()

            reloaded = LiteSquid(OTHER_UUID, "Fresh")
            tank = make_tank(tmp, reloaded)
            self.assertTrue(tank.load_game())
            self.assertEqual(reloaded.lifecycle.stage, STAGE_PARENT)
            self.assertEqual(reloaded.lifecycle.mating_id, "v1-mate")
            self.assertEqual(reloaded.health, 40.0)
            self.assertFalse(reloaded.lifecycle.can_eat)
            eggs = eggs_in(tank)
            self.assertEqual(len(eggs), 1)
            self.assertEqual(eggs[0].egg_id, "v1-mate")
            # Loading twice still leaves one egg in the tank.
            tank.load_game()
            self.assertEqual(len(eggs_in(tank)), 1)
            # And starvation carries on from where it was.
            random.seed(4)
            self.assertIsNotNone(tick_until(tank, lambda: reloaded.lifecycle.is_dead, 5000))

    def test_an_old_save_with_no_lifecycle_is_a_living_squid(self):
        self.assertEqual(Lifecycle.from_dict(None).stage, STAGE_LIVING)
        self.assertEqual(Lifecycle.from_dict({'stage': 'dead'}).stage, STAGE_LIVING)
        self.assertEqual(Lifecycle.from_dict({'stage': 'parent', 'reproduction':
                                              {'mating_id': '../x'}}).stage,
                         STAGE_LIVING)

    def test_the_egg_hatches_once_across_reloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = FakeWindow()
            squid = LiteSquid(RESIDENT_UUID, "Parent")
            logic = make_tank(tmp, squid, window)
            logic.record_reproduction("v1-mate", VISITOR_UUID, "Mate")
            squid.health, squid.hunger = 0.0, 100.0
            logic.update_statistics()
            self.assertTrue(squid.lifecycle.is_dead)

            self.assertTrue(logic.begin_egg_hatching())
            self.assertEqual(window.hatched, ["v1-mate"])
            self.assertEqual(saved_game_state(logic)['lifecycle']['egg']['state'],
                             EGG_HATCHING)
            # A second trigger in the same life finds the egg already hatching:
            # it does not move the lifecycle again, it only re-asks the window,
            # which is the party that refuses a second hatch (tested against
            # the real window in test_new_game_and_hatch).
            self.assertFalse(squid.lifecycle.begin_hatching())

            # Closed mid-hatch: the reload resumes the SAME egg.
            reloaded = LiteSquid(OTHER_UUID, "Fresh")
            tank = make_tank(tmp, reloaded, window)
            tank.load_game()
            self.assertTrue(reloaded.lifecycle.is_dead)
            self.assertEqual(reloaded.lifecycle.egg_state, EGG_HATCHING)
            self.assertFalse(reloaded.lifecycle.begin_hatching())
            tank.begin_egg_hatching()
            self.assertEqual(set(window.hatched), {"v1-mate"})

    def test_nothing_hatches_from_a_living_parent(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = FakeWindow()
            squid = LiteSquid(RESIDENT_UUID, "Parent")
            logic = make_tank(tmp, squid, window)
            logic.record_reproduction("v1-mate", VISITOR_UUID, "Mate")
            self.assertFalse(logic.begin_egg_hatching())
            self.assertEqual(window.hatched, [])


# ===========================================================================
# 8. The fight cloud
# ===========================================================================
class FightCloudTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scene = QtWidgets.QGraphicsScene()
        self.entities = RemoteEntityManager(self.scene, 1280, 900)
        self.addCleanup(self.entities.position_update_timer.stop)
        self.entities.images_folder_root_path = self.tmp.name

    def _install_gif(self):
        with open(os.path.join(self.tmp.name, RemoteEntityManager.FIGHT_CLOUD_FILE), 'wb') as f:
            f.write(TINY_GIF)

    def _clouds(self):
        return [i for i in self.scene.items() if i.zValue() == 600]

    def _plugin(self, peer_x):
        clock = Clock()
        resident = LiteSquid(RESIDENT_UUID, "Resident", x=600.0, y=400.0)
        plugin = MultiplayerPlugin()
        plugin.logger = logging.getLogger("lifecycle-test")
        plugin.tamagotchi_logic = SimpleNamespace(squid=resident)
        plugin.entity_manager = self.entities
        plugin.conspecific_view = ConspecificView(clock=clock)
        plugin.conspecific_view.on_contest = plugin.show_fight_cloud
        identity = SquidIdentity(uuid=VISITOR_UUID, name="Traveller")
        presence = plugin.conspecific_view.observe_peer(
            identity, x=peer_x, y=420.0, observer_x=600.0, observer_y=400.0)
        return plugin, presence

    def test_one_cloud_for_the_pair_when_a_contest_breaks_out_close_by(self):
        self._install_gif()
        plugin, presence = self._plugin(peer_x=700.0)
        plugin.conspecific_view.note_contest(presence, None, taken=False, by='peer')
        plugin.conspecific_view.note_contest(presence, None, taken=True, by='peer')
        self.assertEqual(len(self._clouds()), 1)
        self.entities.hide_fight_cloud(VISITOR_UUID)
        self.assertEqual(self._clouds(), [])

    def test_no_cloud_for_a_contest_across_the_tank(self):
        self._install_gif()
        plugin, presence = self._plugin(peer_x=1200.0)
        plugin.conspecific_view.note_contest(presence, None, taken=False)
        self.assertEqual(self._clouds(), [])

    def test_a_missing_gif_draws_nothing_and_breaks_nothing(self):
        plugin, presence = self._plugin(peer_x=700.0)
        plugin.conspecific_view.note_contest(presence, None, taken=False)
        self.assertEqual(self._clouds(), [])
        self.assertEqual(len(plugin.conspecific_view.drain_contests()), 1)


if __name__ == '__main__':
    unittest.main()
