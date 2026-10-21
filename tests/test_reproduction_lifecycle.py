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

from PyQt5 import QtWidgets, QtCore, QtGui                                  # noqa: E402

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
from src.ui import ResizablePixmapItem                       # noqa: E402

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
        self.replaced = []

    def hatch_egg(self, egg_id):
        self.hatched.append(egg_id)
        return True

    def replace_dead_squid(self, death_id):
        self.replaced.append(death_id)
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

    def close(self):
        self.is_connected = False
        self.socket = None

    def send_message(self, message_type, payload):
        self.sent.append((message_type, payload))
        return True


class FakeEntities:
    def __init__(self):
        self.removed = []
        self.hearts = []

    def show_mating_heart(self, key, x, y):
        self.hearts.append((key, x, y))
        return True

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
            # Neglect is fatal - but it is never a parent's starvation: no
            # reproduction, no egg, and the tank's health loss, which is a
            # parent's alone, was never applied.
            self.assertTrue(squid.lifecycle.is_dead)
            self.assertIn(squid.lifecycle.death_cause, ('neglected', 'sickness'))
            self.assertIsNone(squid.lifecycle.reproduction)
            self.assertEqual(squid.health, 100.0)
            self.assertEqual(eggs_in(logic), [])
            self.assertIn("on_squid_died", logic.plugin_manager.triggered)

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
        brief = DEFAULT_CONFIG['mating_contact_seconds'] - 0.5
        matings = self._visits(200, contact_seconds=brief, chance=1.0)
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

    def test_one_heart_is_drawn_over_the_pair_when_a_mating_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=1.0)
            self.assertTrue(visit.arrive())
            visit.hold_contact(6.0)
            visit.hold_contact(6.0)        # contact goes on; still one mating

            resident, actor = visit.resident, visit.actor
            centre_x = (resident.squid_x + actor.x + resident.squid_width) / 2
            centre_y = (resident.squid_y + actor.y + resident.squid_height) / 2
            self.assertEqual(visit.plugin.entity_manager.hearts,
                             [(VISITOR_UUID, centre_x, centre_y)])

    def test_no_heart_when_the_roll_is_not_a_mating(self):
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp, chance=0.0)
            self.assertTrue(visit.arrive())
            visit.hold_contact(6.0)
            self.assertEqual(visit.resident.lifecycle.stage, STAGE_LIVING)
            self.assertEqual(visit.plugin.entity_manager.hearts, [])

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
        # A player who gives medicine: a starving parent falls sick, and left
        # untreated that kills it first. These tests are about starvation.
        logic.lifecycle_config = dict(logic.lifecycle_config, sickness_seconds=1e9)
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
            for tick in range(3000):
                if tick % 100 == 0:
                    # Fed and cleaned: left alone it would die of neglect, or
                    # fall sick in its dirt and die of that.
                    bystander.hunger, bystander.cleanliness = 25.0, 100.0
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


class ArrivalCatchesTheEyeTests(unittest.TestCase):
    """A squid appearing in the tank turns the resident's view cone onto it;
    a peer that is merely online puts nothing in the tank to look at."""

    def test_an_admitted_visitor_swings_the_residents_view_cone_onto_it(self):
        import math
        from types import MethodType
        from src.vision_cone import in_view_cone
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp)
            resident = visit.resident
            # The real attention code, on the test's light squid.
            for name in ('notice', '_look_at_noticed'):
                setattr(resident, name, MethodType(getattr(Squid, name), resident))
            resident.update_view_cone = lambda: None
            resident.current_view_angle = 0.0          # looking right...
            scene = QtWidgets.QGraphicsScene()
            body = scene.addRect(0, 0, 60, 40)
            body.setPos(100.0, 380.0)                  # ...and it comes in on the left
            visit.plugin.entity_manager.remote_squids = {'squid_vis001': {'visual': body}}

            self.assertTrue(visit.arrive())
            centre = body.sceneBoundingRect().center()
            sees = lambda: in_view_cone(          # noqa: E731
                resident.squid_x + 30, resident.squid_y + 20,
                resident.current_view_angle, math.pi / 2.5, 2000,
                centre.x(), centre.y())
            self.assertTrue(sees())
            # The cone stays on it while the gaze holds, wherever it swims.
            body.setPos(600.0, 100.0)
            centre = body.sceneBoundingRect().center()
            Squid.change_view_cone_direction(resident)
            self.assertTrue(sees())

    def test_a_sleeping_resident_does_not_look(self):
        from types import MethodType
        with tempfile.TemporaryDirectory() as tmp:
            visit = Visit(tmp)
            resident = visit.resident
            resident.is_sleeping = True
            resident.notice = MethodType(Squid.notice, resident)
            visit.plugin.entity_manager.remote_squids = {
                'squid_vis001': {'visual': QtWidgets.QGraphicsRectItem(0, 0, 60, 40)}}
            self.assertTrue(visit.arrive())
            self.assertIsNone(getattr(resident, '_noticed', None))

    def test_a_peer_that_is_only_online_is_not_drawn_in_the_tank(self):
        scene = QtWidgets.QGraphicsScene()
        entities = RemoteEntityManager(scene, 1280, 900)
        self.addCleanup(entities.position_update_timer.stop)
        plugin = MultiplayerPlugin()
        plugin.logger = logging.getLogger("lifecycle-test")
        plugin.entity_manager = entities
        plugin.network_node = FakeNode()
        plugin.network_node.known_nodes = {}
        heartbeat = {'payload': {'node_id': 'squid_peer01', 'status': 'active',
                                 'squid_pos': (100.0, 200.0)}}
        for _ in range(3):
            plugin.handle_heartbeat(plugin.network_node, heartbeat, ('lan', 0))
        self.assertEqual(entities.remote_squids, {})
        self.assertEqual([i for i in scene.items()
                          if getattr(i, 'category', None) == 'squid'], [])


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

    def _plugin(self, peer_x, resident_aggression=0.0, visitor_aggression=0.0):
        """A resident and a visitor in contact, each with an aggression
        neuron reading as given (0 placid .. 100 fully aggro)."""
        clock = Clock()
        resident = LiteSquid(RESIDENT_UUID, "Resident", x=600.0, y=400.0)
        plugin = MultiplayerPlugin()
        plugin.logger = logging.getLogger("lifecycle-test")
        brain = SimpleNamespace(state={'aggression': resident_aggression, 'anxiety': 50.0})
        plugin.tamagotchi_logic = SimpleNamespace(
            squid=resident, brain_window=SimpleNamespace(brain_widget=brain))
        visitor = SimpleNamespace(last_intent=SimpleNamespace(aggression=visitor_aggression))
        plugin.host_body = SimpleNamespace(visitor=lambda uuid: visitor,
                                           clock=clock, visitors={})
        # The decision and the cloud, not the scuffle that brings two drawn
        # bodies together (test_bodies_approach_before_one_shared_cloud...).
        self.entities.start_fight_sequence = None
        plugin.entity_manager = self.entities
        plugin.conspecific_view = ConspecificView(clock=clock)
        plugin.conspecific_view.on_contest = plugin.show_fight_cloud
        identity = SquidIdentity(uuid=VISITOR_UUID, name="Traveller")
        presence = plugin.conspecific_view.observe_peer(
            identity, x=peer_x, y=420.0, observer_x=600.0, observer_y=400.0)
        return plugin, presence

    def test_one_cloud_for_the_pair_when_an_aggro_squid_is_in_contact(self):
        self._install_gif()
        plugin, presence = self._plugin(peer_x=700.0, visitor_aggression=80.)
        plugin.conspecific_view.note_contest(presence, None, taken=False, by='peer')
        plugin.conspecific_view.note_contest(presence, None, taken=True, by='peer')
        self.assertEqual(len(self._clouds()), 1)
        self.entities.hide_fight_cloud(VISITOR_UUID)
        self.assertEqual(self._clouds(), [])

    def test_contact_between_placid_squid_is_not_a_fight(self):
        """Playing, competing, perhaps mating - but nobody is aggro."""
        self._install_gif()
        plugin, presence = self._plugin(peer_x=700.0, resident_aggression=30.,
                                        visitor_aggression=45.)
        plugin.conspecific_view.note_contest(presence, None, taken=False, by='peer')
        self.assertEqual(self._clouds(), [])

    def test_whichever_squid_is_aggro_starts_it_whatever_its_personality(self):
        """No personality rule: a timid squid that has grown aggression can
        start a fight, and a bold one with none cannot."""
        from dataclasses import replace
        self._install_gif()
        for local, peer, mine, theirs, expected in (
                ('timid', 'adventurous', 80., 0., 'resident'),
                ('adventurous', 'timid', 0., 80., 'visitor'),
                ('adventurous', 'adventurous', 0., 0., None)):
            with self.subTest(local=local, peer=peer):
                plugin, presence = self._plugin(peer_x=700., resident_aggression=mine,
                                                visitor_aggression=theirs)
                plugin.tamagotchi_logic.squid.personality = local
                presence.identity = replace(presence.identity, personality=peer)
                start = plugin._who_starts_a_fight(VISITOR_UUID)
                self.assertEqual(start and start['attacker'], expected)
                plugin.conspecific_view.note_contest(presence, by='local')
                self.assertEqual(len(self._clouds()), 1 if expected else 0)
                self.entities.hide_fight_cloud(VISITOR_UUID)

    def test_no_cloud_for_a_contest_across_the_tank(self):
        self._install_gif()
        plugin, presence = self._plugin(peer_x=1200.0, resident_aggression=90.)
        plugin.conspecific_view.note_contest(presence, None, taken=False)
        self.assertEqual(self._clouds(), [])

    def test_a_missing_gif_draws_nothing_and_breaks_nothing(self):
        plugin, presence = self._plugin(peer_x=700.0)
        plugin.conspecific_view.note_contest(presence, None, taken=False)
        self.assertEqual(self._clouds(), [])
        self.assertEqual(len(plugin.conspecific_view.drain_contests()), 1)

    def test_bodies_approach_before_one_shared_cloud_and_repeated_events_reuse_it(self):
        from PyQt5.QtTest import QTest
        self._install_gif()
        pixmap = QtGui.QPixmap(253, 147)
        pixmap.fill(QtCore.Qt.blue)
        resident = SimpleNamespace(squid_x=400., squid_y=350., can_move=True,
                                  squid_item=self.scene.addPixmap(pixmap), lifecycle=Lifecycle())
        actor = SimpleNamespace(x=620., y=350.)
        self.entities.remote_squids['guest'] = {'visual': self.scene.addPixmap(pixmap)}
        self.assertTrue(self.entities.start_fight_sequence(VISITOR_UUID, 'guest', resident, actor))
        self.assertEqual(self._clouds(), [])
        QTest.qWait(750)
        self.assertLessEqual(abs(resident.squid_x-actor.x), 41)
        self.assertEqual(len(self._clouds()), 1)
        self.entities.start_fight_sequence(VISITOR_UUID, 'guest', resident, actor)
        self.assertEqual(len(self._clouds()), 1)
        self.entities._end_scuffle(VISITOR_UUID)
        self.assertTrue(resident.can_move)
        self.assertEqual(self._clouds(), [])


class MatingHeartTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scene = QtWidgets.QGraphicsScene()
        self.entities = RemoteEntityManager(self.scene, 1280, 900)
        self.addCleanup(self.entities.position_update_timer.stop)
        self.entities.images_folder_root_path = self.tmp.name

    def _install_gif(self):
        with open(os.path.join(self.tmp.name, RemoteEntityManager.MATING_HEART_FILE), 'wb') as f:
            f.write(TINY_GIF)

    def _overlays(self):
        return [i for i in self.scene.items() if i.zValue() == 600]

    def test_one_heart_for_the_pair_at_the_gifs_own_size(self):
        self._install_gif()
        self.assertTrue(self.entities.show_mating_heart(VISITOR_UUID, 500.0, 400.0))
        self.assertTrue(self.entities.show_mating_heart(VISITOR_UUID, 510.0, 400.0))
        self.assertEqual(len(self._overlays()), 1)
        # Not rescaled, so the pixel heart stays crisp.
        movie = self.entities._mating_hearts[VISITOR_UUID]['movie']
        self.assertFalse(movie.scaledSize().isValid())
        self.entities.cleanup_all()
        self.assertEqual(self._overlays(), [])

    def test_a_missing_gif_draws_nothing(self):
        self.assertFalse(self.entities.show_mating_heart(VISITOR_UUID, 500.0, 400.0))
        self.assertEqual(self._overlays(), [])

    def test_an_earlier_hearts_timer_leaves_a_later_heart_alone(self):
        from PyQt5.QtTest import QTest
        self._install_gif()
        self.entities.show_mating_heart(VISITOR_UUID, 500.0, 400.0, duration_ms=50)
        self.entities.hide_mating_heart(VISITOR_UUID)
        self.entities.show_mating_heart(VISITOR_UUID, 500.0, 400.0, duration_ms=5000)
        QTest.qWait(150)
        self.assertEqual(len(self._overlays()), 1)
        self.entities.hide_mating_heart(VISITOR_UUID)

    def test_the_shipped_heart_is_an_animated_gif_with_a_clear_background(self):
        movie = QtGui.QMovie(os.path.join(_REPO_ROOT, 'images',
                                          RemoteEntityManager.MATING_HEART_FILE))
        self.assertTrue(movie.isValid())
        self.assertGreater(movie.frameCount(), 1)
        self.assertTrue(movie.jumpToFrame(0))
        frame = movie.currentImage()
        self.assertEqual(frame.pixelColor(0, 0).alpha(), 0)
        centre = frame.pixelColor(frame.width() // 2, frame.height() // 2)
        self.assertEqual((centre.red(), centre.green(), centre.blue(), centre.alpha()),
                         (255, 255, 255, 255))


# ===========================================================================
# 9. Death of any cause, and the headstone it leaves
# ===========================================================================
def headstones_in(logic):
    return [item for item in logic.user_interface.scene.items()
            if getattr(item, 'is_headstone', False)]


class DeathAndHeadstoneTests(unittest.TestCase):

    def setUp(self):
        # The game finds its images from its own folder, headstones included.
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(_REPO_ROOT)

    def _tank(self, tmp, squid=None, sickness=True):
        squid = squid or LiteSquid(RESIDENT_UUID, "Manuel")
        window = FakeWindow()
        logic = make_tank(tmp, squid, window)
        if not sickness:
            logic.lifecycle_config['sickness_seconds'] = 1e9
        return squid, logic, window

    def test_a_squid_with_no_health_left_dies_of_its_injuries_even_asleep(self):
        """Rocks and fights take health and nothing gives it back; at none
        the squid dies of its injuries, as on Android."""
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic, window = self._tank(tmp, sickness=False)
            squid.health = 1.0
            logic.update_statistics()
            self.assertFalse(squid.lifecycle.is_dead)
            squid.health, squid.is_sleeping = 0.0, True
            logic.update_statistics()
            self.assertEqual(squid.lifecycle.death_cause, 'injured')
            self.assertEqual(logic.messages[-1], "Manuel has died of its injuries.")
            [stone] = headstones_in(logic)
            self.assertEqual(stone.headstone['died_of'], 'injured')

    def test_a_neglected_squid_dies_and_leaves_a_headstone_bearing_its_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            random.seed(4)
            squid, logic, window = self._tank(tmp)
            squid.hunger = 100.0
            ticks = tick_until(logic, lambda: squid.lifecycle.is_dead, 1000)
            self.assertEqual(ticks, DEFAULT_CONFIG['neglect_seconds'])
            self.assertEqual(squid.lifecycle.death_cause, 'neglected')
            self.assertEqual(logic.messages[-1], "Manuel has died of neglect.")
            self.assertEqual(squid.status, "dead")
            self.assertFalse(squid.can_move)

            [stone] = headstones_in(logic)
            self.assertEqual(stone.deceased, "Manuel")
            # Its epitaph: name, how long it lived, its fights - on hover too.
            self.assertTrue(stone.epitaph().startswith("<span>RIP Manuel<br>Lived "))
            self.assertIn("Fights won: 0, lost: 0", stone.epitaph())
            self.assertEqual(stone.toolTip(), stone.epitaph())
            self.assertEqual(stone.headstone['died_of'], 'neglected')
            # A decoration: seen and pushed like any, never carried or thrown.
            self.assertEqual(stone.category, 'decoration')
            self.assertFalse(stone.can_be_picked_up)
            # Never bigger than 80% of the squid, and on the tank floor.
            self.assertLessEqual(stone.pixmap().width(), squid.squid_width * 0.8)
            self.assertLessEqual(stone.pixmap().height(), squid.squid_height * 0.8)
            self.assertEqual(stone.pos().y() + stone.pixmap().height(), 900 - 120)

            # Dead is final: no second death, no second headstone.
            for _ in range(500):
                logic.update_statistics()
            self.assertEqual(logic.plugin_manager.triggered.count("on_squid_died"), 1)
            self.assertEqual(len(headstones_in(logic)), 1)
            # With no egg, a new squid follows - once the window says so.
            self.assertTrue(logic.continue_after_death())
            self.assertEqual(window.replaced, [RESIDENT_UUID])
            self.assertEqual(window.hatched, [])

    def test_a_meal_starts_the_neglect_count_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic, _ = self._tank(tmp, sickness=False)
            seconds = int(DEFAULT_CONFIG['neglect_seconds'])
            squid.hunger = 100.0
            for _ in range(seconds - 1):
                logic.update_statistics()
            squid.hunger = 40.0                  # fed, just in time
            logic.update_statistics()
            squid.hunger = 100.0
            for _ in range(seconds - 1):
                logic.update_statistics()
            self.assertFalse(squid.lifecycle.is_dead)

    def test_untreated_sickness_kills_and_medicine_starts_the_count_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic, _ = self._tank(tmp)
            seconds = int(DEFAULT_CONFIG['sickness_seconds'])

            def sick_for(ticks):
                for tick in range(ticks):
                    if tick % 100 == 0:
                        squid.hunger = 25.0      # fed: only the sickness can kill
                    logic.update_statistics()

            squid.is_sick = True
            sick_for(seconds - 1)
            squid.is_sick = False                # medicine
            logic.update_statistics()
            squid.is_sick = True
            sick_for(seconds - 1)
            self.assertFalse(squid.lifecycle.is_dead)
            logic.update_statistics()
            self.assertEqual(squid.lifecycle.death_cause, 'sickness')
            self.assertEqual(logic.messages[-1], "Manuel has died of sickness.")
            self.assertEqual(len(headstones_in(logic)), 1)

    def test_a_sick_parent_dies_of_it_and_its_egg_still_hatches(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic, window = self._tank(tmp)
            self.assertTrue(logic.record_reproduction("v1-mate", VISITOR_UUID, "Mate"))
            squid.is_sick = True
            tick_until(logic, lambda: squid.lifecycle.is_dead, 1000)
            self.assertEqual(squid.lifecycle.death_cause, 'sickness')
            self.assertEqual(len(headstones_in(logic)), 1)
            self.assertTrue(logic.continue_after_death())
            self.assertEqual(window.hatched, ["v1-mate"])
            self.assertEqual(window.replaced, [])

    def test_the_cause_and_the_counts_survive_a_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            squid, logic, _ = self._tank(tmp, sickness=False)
            squid.hunger = 100.0
            for _ in range(120):
                logic.update_statistics()
            logic.save_game()
            reloaded = LiteSquid(RESIDENT_UUID, "Manuel")
            tank = make_tank(tmp, reloaded)
            tank.load_game()
            self.assertEqual(reloaded.lifecycle.neglected_seconds, 120.0)
            squid.hunger = 100.0
            tick_until(logic, lambda: squid.lifecycle.is_dead, 1000)
            logic.save_game()
            dead = LiteSquid(RESIDENT_UUID, "Manuel")
            tank = make_tank(tmp, dead)
            tank.load_game()
            self.assertEqual(dead.lifecycle.death_cause, 'neglected')
            # The reload lays it to rest; the headstone comes back with the
            # decorations, not as a second one.
            self.assertEqual(dead.status, "dead")
            self.assertEqual(headstones_in(tank), [])


class HeadstoneDecorationTests(unittest.TestCase):
    """The headstone as a decoration, through the real Ui methods."""

    def setUp(self):
        from src.ui import HEADSTONE_DIR
        self.scene = QtWidgets.QGraphicsScene()
        self.squid = SimpleNamespace(squid_width=253.0, squid_height=147.0)
        self.ui = SimpleNamespace(scene=self.scene, awarded_decorations=set(),
                                  tamagotchi_logic=SimpleNamespace(squid=self.squid),
                                  show_floating_score=lambda *a, **k: None)
        path = os.path.join(_REPO_ROOT, HEADSTONE_DIR, 'headstone02.png')
        self.stone = ResizablePixmapItem(QtGui.QPixmap(path), path)
        self.stone.deceased = "Manuel"
        self.stone.limit_headstone(self.squid)
        self.scene.addItem(self.stone)

    def test_every_headstone_is_a_transparent_image_the_game_can_load(self):
        from src.ui import HEADSTONE_DIR
        stones = sorted(os.listdir(os.path.join(_REPO_ROOT, HEADSTONE_DIR)))
        self.assertEqual(len(stones), 10)
        for name in stones:
            image = QtGui.QImage(os.path.join(_REPO_ROOT, HEADSTONE_DIR, name))
            self.assertFalse(image.isNull(), name)
            self.assertEqual(image.pixelColor(0, 0).alpha(), 0, name)

    def test_it_cannot_be_deleted_but_a_plant_can(self):
        from src.ui import Ui
        plant = ResizablePixmapItem(QtGui.QPixmap(10, 10), 'images/decoration/plant01.png')
        self.scene.addItem(plant)
        self.stone.setSelected(True)
        plant.setSelected(True)
        Ui.delete_selected_items(self.ui)
        self.assertIn(self.stone, self.scene.items())
        self.assertNotIn(plant, self.scene.items())

    def test_it_never_grows_past_80_percent_of_the_squid(self):
        self.stone.setSelected(True)
        grow = SimpleNamespace(angleDelta=lambda: QtCore.QPoint(0, 120),
                               accept=lambda: None)
        for _ in range(20):
            self.stone.wheelEvent(grow)
        self.assertLessEqual(self.stone.pixmap().width(), 253 * 0.8)
        self.assertLessEqual(self.stone.pixmap().height(), 147 * 0.8)
        self.assertGreaterEqual(self.stone.pixmap().height(), int(147 * 0.8) - 1)

    def test_an_old_stone_bears_its_name_alone(self):
        self.assertEqual(self.stone.epitaph(), "<span>RIP Manuel</span>")

    def test_its_epitaph_survives_a_save(self):
        from src.ui import Ui
        self.stone.set_epitaph({'deceased': 'Manuel', 'age_seconds': 7260.,
                                'fights_won': 4, 'fights_lost': 2, 'died_of': 'starved'})
        saved = Ui.get_decorations_data(self.ui)
        self.scene.removeItem(self.stone)
        Ui.add_decorations_data(self.ui, saved)
        [stone] = [i for i in self.scene.items() if getattr(i, 'is_headstone', False)]
        self.assertEqual(stone.epitaph(),
                         "<span>RIP Manuel<br>Lived 2h 1m<br>Fights won: 4, lost: 2</span>")
        self.assertEqual(stone.toolTip(), stone.epitaph())

    def test_its_name_and_limit_survive_a_save(self):
        from src.ui import Ui
        saved = Ui.get_decorations_data(self.ui)
        self.assertEqual(saved[0]['deceased'], "Manuel")
        self.scene.removeItem(self.stone)
        smaller = SimpleNamespace(squid_width=100.0, squid_height=60.0)
        self.ui.tamagotchi_logic.squid = smaller      # e.g. a lower DPI now
        Ui.add_decorations_data(self.ui, saved)
        [stone] = [i for i in self.scene.items() if getattr(i, 'is_headstone', False)]
        self.assertEqual(stone.deceased, "Manuel")
        self.assertLessEqual(stone.pixmap().height(), 60 * 0.8)


class RoundTripTimerTests(unittest.TestCase):
    def test_sync_timer_actually_runs_on_the_qt_thread_and_can_be_stopped(self):
        from PyQt5.QtTest import QTest
        plugin = MultiplayerPlugin()
        calls = []
        plugin.sync_game_state = lambda: calls.append(QtCore.QThread.currentThread())
        plugin.start_sync_timer()
        timer = plugin.sync_timer
        self.addCleanup(timer.stop)
        plugin.start_sync_timer()
        self.assertIs(plugin.sync_timer, timer)
        QTest.qWait(650)
        self.assertTrue(calls, 'a live timer must drive perception and action intents')
        self.assertTrue(all(thread == QtWidgets.QApplication.instance().thread() for thread in calls))
        timer.stop()


if __name__ == '__main__':
    unittest.main()
