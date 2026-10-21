"""The protocol problems found while writing plugins/multiplayer/docs/protocol.md.

Each test is one finding, fixed:

- the presence broadcast (object_sync) carried the squid's hunger and
  happiness to every tank, although both are private cognitive state;
- datagrams over 1472 bytes were cut short on receipt, and a compressed one
  could inflate without bound;
- de-duplication keyed on (node, timestamp) dropped different messages sent
  back to back on a coarse clock;
- remote-mind messages were matched on visit id alone, which every frame
  carries in the open: a visitor adopted any host's frame, and anyone could
  steer, end or impregnate a visit;
- legacy handlers (squid_return, rock_throw, squid_move) still acted on
  whatever any peer said;
- an 'ejected' consequence was queued and then dropped with its visitor;
- a gamete was not sent again when a mating was retold on a later visit;
- a refusal for an unreadable identity was ignored, so the squid kept asking;
- an intent's lease was measured across two machines' clocks;
- a visitor was drawn where its frozen home body was, not where its body
  in the host tank was - and the resident's eyes see the drawing.
"""
import json
import os
import sys
import zlib
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5 import QtWidgets                                          # noqa: E402

from plugins.multiplayer import mp_constants                         # noqa: E402
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin    # noqa: E402
from plugins.multiplayer.remote_protocol import (                    # noqa: E402
    ActionIntent, Consequence, CONSEQUENCE_EJECTED, INTENT_LEASE, _reject_private)

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def plugin():
    import logging
    p = MultiplayerPlugin()
    p.logger = logging.getLogger('protocol-hardening-test')
    return p


def test_the_presence_broadcast_carries_no_drives():
    p = plugin()
    squid = SimpleNamespace(squid_x=10., squid_y=20., squid_direction='left', hunger=80.,
                            happiness=10., status='exploring', squid_width=60, squid_height=40)
    p.tamagotchi_logic = SimpleNamespace(squid=squid)
    p.network_node = SimpleNamespace(node_id='squid_me0000')
    p.local_identity = None
    state = p._get_squid_state()
    assert 'hunger' not in state and 'happiness' not in state
    _reject_private(state)                    # nothing private, at any depth


def test_a_large_datagram_is_read_whole_and_a_bomb_is_refused():
    from plugins.multiplayer.network_utilities import NetworkUtilities
    assert mp_constants.RECEIVE_BUFFER_SIZE >= 65507       # any UDP datagram
    message = {'node_id': 'squid_peer01', 'type': 'gamete', 'payload': {'g': 'x' * 3000}}
    assert NetworkUtilities.decompress_message(zlib.compress(json.dumps(message).encode()))['type'] == 'gamete'
    bomb = zlib.compress(b'{"a": "' + b'0' * (mp_constants.MAX_MESSAGE_BYTES * 4) + b'"}')
    assert len(bomb) < 65507
    assert NetworkUtilities.decompress_message(bomb) == {'error': 'message_too_large'}


def test_copies_are_dropped_but_different_messages_with_one_timestamp_are_not():
    from plugins.multiplayer.mp_network_node import NetworkNode
    node = NetworkNode(node_id='squid_me0000')
    try:
        frame = {'node_id': 'squid_peer01', 'timestamp': 5.0, 'type': 'perception_frame',
                 'payload': {'seq': 1}}
        consequence = dict(frame, type='consequence', payload={'kind': 'hit'})
        for message in (frame, frame, consequence):         # one copy per interface
            node.incoming_queue.put({'raw_data': zlib.compress(json.dumps(message).encode()),
                                     'addr': ('192.0.2.9', 10000)})
        assert [m['type'] for m, _ in node.receive_messages()] == ['perception_frame', 'consequence']
    finally:
        node.close()


def visitor_plugin():
    p = plugin()
    seen = []
    p.visitor_mind = SimpleNamespace(on_perception_frame=lambda pl: seen.append('frame') or True,
                                     on_consequence=lambda pl: seen.append('consequence') or {},
                                     on_visit_end=lambda pl: seen.append('end') or True)
    p._asked_to_visit = 'squid_host01'
    return p, seen


def test_a_visitor_hears_only_the_host_it_asked():
    p, seen = visitor_plugin()
    for handler in (p.handle_perception_frame, p.handle_consequence, p.handle_visit_end):
        assert not handler(None, {'node_id': 'squid_other1', 'payload': {}}, None)
    assert seen == []
    assert p.handle_perception_frame(None, {'node_id': 'squid_host01', 'payload': {}}, None)
    assert p.handle_consequence(None, {'node_id': 'squid_host01', 'payload': {}}, None)
    assert seen == ['frame', 'consequence']


def test_a_host_takes_intents_only_from_the_node_a_visitor_came_from():
    p = plugin()
    applied = []
    actor = SimpleNamespace(uuid='visitor-uuid', visit_id='visit-1')
    p.host_body = SimpleNamespace(visitors={'visitor-uuid': actor},
                                  apply_intent=lambda a, i: applied.append(i.seq) or True)
    p.visit_node_ids = {'visitor-uuid': 'squid_vis001'}
    intent = ActionIntent('visit-1', 'act_move', seq=1, heading='left').to_payload()
    assert not p.handle_action_intent(None, {'node_id': 'squid_other1', 'payload': intent}, None)
    assert p.handle_action_intent(None, {'node_id': 'squid_vis001', 'payload': intent}, None)
    assert applied == [1]


def test_legacy_messages_are_no_longer_listened_for():
    p = plugin()
    registered = []
    p.plugin_manager = SimpleNamespace(register_hook=registered.append,
                                       subscribe_to_hook=lambda *a: None)
    p.network_node = None
    p._register_hooks()
    for legacy in ('squid_return', 'rock_throw', 'squid_move'):
        assert f'on_network_{legacy}' not in registered
    assert 'on_network_action_intent' in registered and 'on_network_gamete' in registered


def test_what_happened_to_a_visitor_reaches_it_before_it_is_sent_away():
    p = plugin()
    sent = []
    p._send = lambda kind, payload: sent.append(kind) or True
    actor = SimpleNamespace(uuid='visitor-uuid', visit_id='visit-1', identity='Traveller')
    p.host_body = SimpleNamespace(
        drain_consequences=lambda a: [Consequence('visit-1', CONSEQUENCE_EJECTED,
                                                  detail={'reason': 'link_lost'})],
        remove=lambda uuid: None)
    p.close_encounter = lambda uuid: None
    p.end_visit_as_host(actor, 'link_lost')
    assert sent == ['consequence', 'visit_end']


def test_a_refusal_for_an_unreadable_identity_still_sends_the_squid_home():
    p = plugin()
    ended = []
    p.visitor_mind = SimpleNamespace(end_visit=lambda **kw: ended.append(kw))
    p.tamagotchi_logic = SimpleNamespace(squid=SimpleNamespace(uuid='my-uuid'))
    p.network_node = SimpleNamespace(node_id='squid_me0000')
    p._asked_to_visit = 'squid_host01'
    refusal = {'node_id': 'squid_host01',
               'payload': {'accepted': False, 'reason': 'bad_identity', 'peer_uuid': '',
                           'to': 'squid_me0000'}}
    assert p.handle_visit_response(None, refusal, None) and ended
    # Someone else's refusal is still someone else's.
    ended.clear()
    refusal['payload']['to'] = 'squid_other1'
    assert not p.handle_visit_response(None, refusal, None) and not ended


def test_a_mating_retold_on_a_later_visit_sends_the_gamete_again():
    from test_remote_mind_stage1 import Encounter
    meeting = Encounter()
    meeting.admit()
    meeting.host_sends_frame()
    meeting.visitor_receives()
    mind = meeting.visitor_mind
    from src.portable_brain import HeadlessBrain
    meeting.visitor_tank.brain_window = SimpleNamespace(brain_widget=HeadlessBrain())
    mind.peer_ledger.has_mated = lambda mating_id: True         # already remembered
    before = len(meeting.link.sent_by_visitor)
    assert not mind._note_mated('visit-1-mate')                  # not filed twice...
    assert any(kind == "gamete" for kind, _ in meeting.link.sent_by_visitor[before:])  # ...but resent


def test_an_intent_lease_holds_whatever_the_visitors_clock_says():
    from test_remote_mind_stage1 import Encounter
    meeting = Encounter()
    actor = meeting.admit()
    skewed = meeting.clock() - 120.0                             # its clock is 2 minutes behind
    first = ActionIntent(actor.visit_id, 'act_move', seq=1, sent_at=skewed, heading='right')
    assert meeting.host_body.apply_intent(actor, first)
    assert actor.is_under_control(meeting.clock())
    meeting.clock.advance(INTENT_LEASE + .1)
    assert not actor.is_under_control(meeting.clock())          # and still expires
    late = ActionIntent(actor.visit_id, 'act_move', seq=2,
                        sent_at=skewed + .1 - 5.0, heading='right')  # delayed 5 s more
    assert not meeting.host_body.apply_intent(actor, late)


def test_a_visitor_is_drawn_where_its_body_is_in_this_tank():
    from plugins.multiplayer.remote_entity_manager import RemoteEntityManager
    entities = RemoteEntityManager(QtWidgets.QGraphicsScene(), 1280, 900)
    entities.position_update_timer.stop()
    entities.swim_timer.stop()
    entities.update_remote_squid('squid_vis001', {'x': 0., 'y': 300., 'image_direction_key': 'left'},
                                 is_new_arrival=True)
    info = entities.remote_squids['squid_vis001']
    assert entities.follow_body('squid_vis001', 640., 420., 'right')
    entities.update_remote_squid('squid_vis001', {'x': 0., 'y': 300., 'image_direction_key': 'left'})
    assert (info['network_target_x'], info['network_target_y']) == (640., 420.)
    assert info['current_image_name'].startswith('right')
