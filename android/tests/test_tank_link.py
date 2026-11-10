"""A phone's tank on the desktop game's own network.

The platform must not matter: a phone's squid visits a computer's tank and a
computer's squid visits a phone's, linked the same way (a friend code) and
speaking the same protocol (plugins/multiplayer/docs/protocol.md). So the
phone is tested here against that protocol as the desktop sends and reads
it - the message shapes a desktop game produces, sent from a bare network
node standing where the desktop would be - and against another phone, over
real sockets on this machine. tools/test_phone_desktop_visit.py runs the
same thing against a whole desktop game.
"""
import json
import socket
import sys
import time
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from dosidicus_mobile.engine import Simulation, Squid                 # noqa: E402
from dosidicus_mobile.engine.personality import Personality          # noqa: E402
from dosidicus_mobile.engine.tank_link import TankLink                # noqa: E402
from plugins.multiplayer import friend_link                           # noqa: E402
from plugins.multiplayer.identity import ENCOUNTER_PROTOCOL_VERSION   # noqa: E402
from plugins.multiplayer.mp_network_node import NetworkNode           # noqa: E402
from plugins.multiplayer.remote_protocol import (ActionIntent, PerceptionFrame,  # noqa: E402
                                                 VisitEnd)

DESKTOP_SQUID = {'uuid': 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d', 'name': 'Inky',
                 'personality': 'timid', 'protocol': ENCOUNTER_PROTOCOL_VERSION,
                 'tint': [255, 105, 180]}


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def tank(name='Pocket', store=None):
    sim = Simulation(squid=Squid(Personality.ADVENTUROUS))
    sim.hatching = False
    sim.squid.name = name
    link = TankLink(sim, port=free_port(), stun_server='', store=store)
    assert link.start()
    return sim, link


def linked(a, b):
    """Each player has entered the other's code (on one machine: its port)."""
    for mine, theirs in ((a, b), (b, a)):
        peer = getattr(theirs, 'node', theirs)
        getattr(mine, 'node', mine).add_friend('127.0.0.1', peer.port, peer.invitation)


def pump(until, *sims, seconds=6.0, also=None):
    """Run the tanks in real time until `until()` is true."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        for sim in sims:
            sim.update(1 / 30)
        if also:
            also()
        if until():
            return True
        time.sleep(1 / 60)
    return False


class Desktop:
    """Where a desktop game would be: its network node, sending what a
    desktop sends (protocol.md section 4) and keeping what it is sent."""

    def __init__(self):
        self.node = NetworkNode('squid_b71e03', port=free_port())
        self.node.auto_reconnect = False
        assert self.node.start_listening()
        self.got = []

    def hear(self):
        for message, _addr in self.node.receive_messages():
            self.got.append(message)

    def of(self, kind):
        return [m['payload'] for m in self.got if m.get('type') == kind]

    def heartbeat(self):
        self.node.send_message('heartbeat', {'node_id': self.node.node_id, 'status': 'active',
                                             'squid_pos': [640.0, 410.5]})

    def squid_exit(self, to, identity=DESKTOP_SQUID, direction='right'):
        self.node.send_message('squid_exit', {'payload': {
            'node_id': self.node.node_id, 'direction': direction,
            'position': {'x': 1224.0, 'y': 388.5}, 'color': [171, 100, 233],
            'squid_width': 56, 'squid_height': 56,
            'window_width': 1280, 'window_height': 900,
            'identity': identity, 'to': to}})


@pytest.fixture
def phone():
    sim, link = tank()
    yield sim, link
    link.stop()


@pytest.fixture
def desktop():
    made = Desktop()
    yield made
    made.node.close()


# ------------------------------------------------------------- friend codes
def test_a_phone_has_the_same_kind_of_friend_code_as_a_computer(phone):
    _sim, link = phone
    code = link.friend_code()
    where = friend_link.parse_friend(code)
    assert len(code.replace('-', '')) == friend_link.CODE_LENGTH == 15
    assert where.port == link.node.port and where.invitation == link.node.invitation
    old = link.node.invitation
    assert link.new_friend_code() != code and link.node.invitation != old


def test_entering_a_code_links_the_tank_and_is_remembered(tmp_path, desktop):
    store = str(tmp_path / 'friends.json')
    sim, link = tank(store=store)
    try:
        ok, said = link.connect_to_friend('not a code')
        assert not ok and said.endswith('.')
        code = friend_link.encode_friend_code('86.12.34.56', 51234, 4242)
        ok, said = link.connect_to_friend(code.lower().replace('-', ' '))
        assert ok and '86.12.34.56:51234' in said
        assert link.friends()[0]['state'] == 'no answer yet'
        assert json.loads(Path(store).read_text())['friends'] == [['86.12.34.56', 51234, 4242]]
    finally:
        link.stop()
    again_sim, again = tank(store=store)                 # the app is opened another day
    try:
        assert [(f['ip'], f['port']) for f in again.friends()] == [('86.12.34.56', 51234)]
        assert again.forget_friend('86.12.34.56', 51234)
        assert json.loads(Path(store).read_text())['friends'] == []
    finally:
        again.stop()


# -------------------------------------------------- hearing another aquarium
def test_a_desktop_tank_heard_through_the_link_is_an_aquarium_nearby(phone, desktop):
    sim, link = phone
    assert sim.squid.why_not_venturing() == 'it senses no other aquarium'
    linked(link, desktop.node)
    desktop.heartbeat()
    assert pump(lambda: link.tanks_heard(), sim)
    assert link.visit_destination() == desktop.node.node_id
    # Its own percept; the sense for it is grown by its own neurogenesis.
    assert pump(lambda: 'aquarium_nearby' in sim.squid.brain.positions, sim,
                also=desktop.heartbeat, seconds=8.0)
    desktop.hear()
    assert desktop.of('heartbeat')[0]['node_id'] == link.node.node_id   # and it says so too


def test_with_the_link_off_no_aquarium_is_nearby_and_the_squid_stays_in(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.heartbeat()
    assert pump(lambda: link.tanks_heard(), sim)
    link.stop()
    assert not link.running and sim.tank_link is None
    assert sim.squid.why_not_venturing() == 'multiplayer is off'
    assert not sim.squid.is_venturing()


def test_a_squid_goes_to_the_side_only_while_its_own_network_takes_it_out():
    sim = Simulation(squid=Squid(Personality.ADVENTUROUS))
    squid = sim.squid
    squid._last_dt = 1 / 30
    squid._execute('exploring', [])
    assert squid.at_side is None and squid.status == 'exploring'      # multiplayer off
    squid.can_venture = True
    squid.why_not_venturing = lambda: None                            # its network says go
    squid.x = 500.0
    for _ in range(600):
        squid._execute('exploring', [])
    assert squid.status == 'venturing out' and squid.at_side == 'right'
    assert squid.x == squid.tank_size[0] - squid.SIDE_MARGIN
    squid._execute('eating', [])                                      # something else wins
    assert squid.at_side is None


# ------------------------------------------- a desktop squid visits the phone
def test_a_desktop_squid_is_let_in_given_a_body_and_steered_from_its_home(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.heartbeat()
    desktop.squid_exit(to=link.node.node_id)
    assert pump(lambda: desktop.hear() or desktop.of('perception_frame'), sim)

    answer = desktop.of('visit_response')[0]
    assert answer == {'accepted': True, 'reason': 'accepted',
                      'peer_uuid': DESKTOP_SQUID['uuid'], 'to': desktop.node.node_id}
    frame = PerceptionFrame.from_payload(desktop.of('perception_frame')[0])
    assert frame.resident.name == 'Pocket' and frame.visit_id
    assert desktop.of('perception_frame')[0]['tank'] == [float(v) for v in sim.tank_size]

    [body] = [v for v in sim.visitors if v.get('remote')]
    assert body['name'] == 'Inky' and body['x'] == 80.0               # in by the other side
    assert tuple(round(c * 255) for c in body['tint'][:3]) == (255, 105, 180)   # still pink

    # Its brain is at home: the phone moves the body only as it is told to.
    _node, visit = link.hosted[DESKTOP_SQUID['uuid']]
    start = visit.actor.x
    seq = [0]

    def explore():
        seq[0] += 1
        desktop.node.send_message('action_intent', ActionIntent(
            frame.visit_id, 'act_move', seq=seq[0], sent_at=time.time(),
            activation=80.0).to_payload())
    assert pump(lambda: abs(visit.actor.x - start) > 20, sim, also=explore)

    # Asking again while it is in changes nothing but the answer said twice.
    desktop.squid_exit(to=link.node.node_id)
    assert pump(lambda: desktop.hear() or len(desktop.of('visit_response')) >= 2, sim)
    assert link.hosted[DESKTOP_SQUID['uuid']][1] is visit and len(sim.visitors) == 1

    desktop.node.send_message('visit_end', VisitEnd(frame.visit_id, 'departed').to_payload())
    assert pump(lambda: not link.hosted, sim)
    assert visit.closed and body not in sim.visitors


def test_an_exit_addressed_to_another_tank_is_not_answered(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.squid_exit(to='squid_000000')
    assert not pump(lambda: desktop.hear() or desktop.of('visit_response'), sim, seconds=1.0)
    assert not link.hosted and not sim.visitors


@pytest.mark.parametrize('spoil, reason', [
    (lambda sim: setattr(sim, 'hatching', True), 'tank_closed'),
    (lambda sim: sim.squid.lifecycle.die('neglected', 0.0), 'tank_closed'),
])
def test_a_tank_with_nobody_to_visit_says_no(phone, desktop, spoil, reason):
    sim, link = phone
    linked(link, desktop.node)
    spoil(sim)
    desktop.squid_exit(to=link.node.node_id)
    deadline = time.time() + 4.0
    while time.time() < deadline and not desktop.of('visit_response'):
        link.tick()
        desktop.hear()
        time.sleep(0.02)
    answer = desktop.of('visit_response')[0]
    assert answer['accepted'] is False and answer['reason'] == reason
    assert answer['to'] == desktop.node.node_id and not link.hosted


def test_a_squid_speaking_another_protocol_is_refused_as_a_desktop_refuses_it(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.squid_exit(to=link.node.node_id, identity=dict(DESKTOP_SQUID, protocol=1))
    assert pump(lambda: desktop.hear() or desktop.of('visit_response'), sim)
    assert desktop.of('visit_response')[0]['reason'] == 'protocol_mismatch'
    assert not sim.visitors


def test_a_phone_holds_its_own_squid_and_up_to_three_visitors(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    for index in range(4):
        uuid = f'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c{index:02d}'
        desktop.squid_exit(to=link.node.node_id, identity=dict(DESKTOP_SQUID, uuid=uuid))
        assert pump(lambda: desktop.hear() or len(desktop.of('visit_response')) > index, sim)
    answers = desktop.of('visit_response')
    assert [a['accepted'] for a in answers] == [True, True, True, False]
    assert answers[3]['reason'] == 'tank_full' and len(link.hosted) == 3


# ------------------------------------------- the phone's squid visits a desktop
def test_the_phone_squid_asks_the_tank_it_heard_and_follows_that_tanks_frames(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.heartbeat()
    assert pump(lambda: link.tanks_heard(), sim)
    squid = sim.squid
    squid.why_not_venturing = lambda: None          # its network is taking it out,
    squid.color_tint = (1.0, 105 / 255, 180 / 255)

    def at_the_side():                               # and it has reached the side
        if link.away is None:
            squid.at_side = 'right'
        desktop.hear()
    assert pump(lambda: desktop.of('squid_exit'), sim, also=at_the_side)

    asked = desktop.of('squid_exit')[0]['payload']
    assert asked['to'] == desktop.node.node_id and asked['node_id'] == link.node.node_id
    assert asked['direction'] == 'right' and asked['identity']['uuid'] == squid.uuid
    assert asked['identity']['tint'] == [255, 105, 180]        # a pink squid, there too
    assert asked['identity']['protocol'] == ENCOUNTER_PROTOCOL_VERSION
    assert {'position', 'squid_width', 'squid_height', 'window_width',
            'window_height', 'color'} <= set(asked)
    assert link.away is None and sim.visiting() is None        # asked; not gone

    # The desktop lets it in and names the visit in its first frame.
    visit_id = '3f2a9c1e-a1b2c3d4-19a0146abfb'
    resident = {'uuid': '3f2a9c1e-7b4d-4e8a-9c21-5d6f0a1b2c3d', 'name': 'Manuel',
                'personality': 'adventurous', 'protocol': ENCOUNTER_PROTOCOL_VERSION}
    seq = [0]

    def frame():
        seq[0] += 1
        desktop.node.send_message('perception_frame', {
            'visit_id': visit_id, 'seq': seq[0], 'sent_at': time.time(),
            'x': 312.5, 'y': 401.25, 'tank': [1280.0, 900.0], 'facing': 'left',
            'sensors': {'can_see_food': 0.0, 'external_stimulus': 0.0, 'plant_in_view': 0.0,
                        'squid_in_view': 100.0, 'squid_proximity': 61.3, 'in_fight': 0.0},
            'resident': resident, 'items': []})
        desktop.hear()
    desktop.node.send_message('visit_response', {
        'accepted': True, 'reason': 'accepted', 'peer_uuid': squid.uuid,
        'to': link.node.node_id})
    frame()
    assert pump(lambda: link.away is not None and link.away.mind.visit_id == visit_id, sim,
                also=frame)
    assert sim.visiting_text() == "Pocket is visiting Manuel's tank"

    # Its own brain, on the phone, says what its body over there does.
    squid.hunger, squid.sleepiness, squid.anxiety = 15.0, 5.0, 15.0
    assert pump(lambda: desktop.of('action_intent'), sim, also=frame, seconds=10.0)
    intent = ActionIntent.from_payload(desktop.of('action_intent')[0])
    assert intent.visit_id == visit_id and intent.action.startswith('act_')

    # The desktop ends it; the squid is home, and remembers whose tank it was in.
    desktop.node.send_message('visit_end', VisitEnd(visit_id, 'ejected').to_payload())
    assert pump(lambda: link.away is None, sim)
    assert sim.visiting() is None and 'home again' in link.events[-1][1]


def test_a_refusal_leaves_the_squid_at_home(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.heartbeat()
    assert pump(lambda: link.tanks_heard(), sim)
    sim.squid.why_not_venturing = lambda: None

    def at_the_side():
        sim.squid.at_side = 'left'
        desktop.hear()
    assert pump(lambda: desktop.of('squid_exit'), sim, also=at_the_side)
    desktop.node.send_message('visit_response', {
        'accepted': False, 'reason': 'tank_full', 'peer_uuid': sim.squid.uuid,
        'to': link.node.node_id})
    assert pump(lambda: any('said no' in text for _at, text in link.events), sim)
    assert link.away is None and sim.visiting() is None


def test_an_answer_from_a_tank_it_did_not_ask_is_ignored(phone, desktop):
    sim, link = phone
    linked(link, desktop.node)
    desktop.node.send_message('visit_response', {
        'accepted': True, 'reason': 'accepted', 'peer_uuid': sim.squid.uuid,
        'to': link.node.node_id})
    assert not pump(lambda: link.away is not None, sim, seconds=1.0)


# ------------------------------------------------------------ phone to phone
def test_two_phones_linked_by_code_visit_each_other():
    home, home_link = tank('Ziggy')
    host, host_link = tank('Pesto')
    try:
        linked(home_link, host_link)
        host.squid.why_not_venturing = lambda: 'held at home for this test'
        home.squid.why_not_venturing = lambda: None

        def at_the_side():
            if home_link.away is None:
                home.squid.at_side = 'right'
        assert pump(lambda: home_link.away is not None and host_link.hosted, home, host,
                    also=at_the_side, seconds=20.0)
        _node, visit = next(iter(host_link.hosted.values()))
        assert visit.actor.identity.name == 'Ziggy'
        assert pump(lambda: home.visiting() is not None
                    and home.visiting_text() == "Ziggy is visiting Pesto's tank", home, host)
        home_link.stop()                              # the player turns multiplayer off
        assert home.visiting() is None
        assert pump(lambda: not host_link.hosted, host)
        assert not [v for v in host.visitors if v.get('remote') and not v['leaving']]
    finally:
        home_link.stop()
        host_link.stop()
