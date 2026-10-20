"""Rock flight, neural provenance and irreversible multiplayer consequences."""
import math
import os
from types import SimpleNamespace as NS
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from src.throwing import plan_throw, throw_or_drop, swept_hit, flight_step
from src.interactions import RockInteractionManager
from src.plugin_manager import PluginManager
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
from plugins.multiplayer.remote_protocol import Consequence, CONSEQUENCE_HIT, CONSEQUENCE_THROWN
from test_remote_mind_stage1 import Encounter, quiet_brain

_APP = None


@pytest.fixture
def tank():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    scene = QtWidgets.QGraphicsScene(0, 0, 900, 500)
    objects = []  # retain Python metadata on scene-owned Qt items
    def item(x, y, category='', name=''):
        pix = QtGui.QPixmap(20, 20)
        pix.fill(QtGui.QColor('white'))
        obj = scene.addPixmap(pix)
        obj.setPos(x-10, y-10)
        obj.category, obj.squid_name = category, name
        objects.append(obj)
        return obj
    class Body:
        carrying_rock = property(lambda s: s.is_carrying_rock,
                                 lambda s, v: setattr(s, 'is_carrying_rock', v))
    body = Body()
    body.squid_item = item(100, 200, 'squid', 'Resident')
    body.uuid, body.name = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Resident'
    body.squid_x, body.squid_y = 90, 190
    body.squid_width = body.squid_height = 20
    body.squid_direction, body.current_view_angle = 'right', 0.
    body.happiness = body.satisfaction = body.anxiety = 50.
    body.health = 100.
    body.is_sleeping = body.is_carrying_rock = False
    body.carried_rock, body.status = None, 'roaming'
    body.memory_manager = NS(add_short_term_memory=Mock())
    state = quiet_brain(act_play=100.)
    logic = NS(squid=body, brain_window=NS(brain_widget=NS(state=state)),
               statistics_window=NS(award=Mock()), track_rock_thrown=Mock(),
               on_rock_hit=Mock())
    config = dict(min_carry_duration=3., max_carry_duration=3.,
                  happiness_boost=5, satisfaction_boost=3, anxiety_reduction=2)
    manager = RockInteractionManager(body, logic, scene, Mock(), NS(get_rock_config=lambda: config))
    body.throw_rock = manager.throw_rock
    rock = item(100, 200, 'rock')
    rock.filename = 'rock.png'
    assert manager.attach_rock_to_squid(rock)
    yield NS(scene=scene, item=item, body=body, logic=logic, manager=manager, rock=rock, state=state)
    manager.cleanup()
    manager.rock_test_timer.timeout.disconnect()
    manager.throw_animation_timer.timeout.disconnect()
    body.throw_rock = None
    for obj in objects:
        if obj.scene() is scene:
            scene.removeItem(obj)


def test_neural_competition_not_dice_decides_throw_or_drop(monkeypatch):
    def no_dice(*a, **k):
        raise AssertionError('a throw decision rolled dice')
    monkeypatch.setattr('random.uniform', no_dice)
    assert throw_or_drop(quiet_brain(act_play=90.))
    assert not throw_or_drop(quiet_brain(act_play=60., act_flee=100.))
    assert not throw_or_drop(quiet_brain())


@pytest.mark.parametrize('drive,by,speed', [(60., 'act_play', 14.4), (100., 'act_play', 20.)])
def test_speed_and_provenance_follow_actual_activation(drive, by, speed):
    plan = plan_throw({'act_play': drive}, (0, 0), .4, [], slowest=6, fastest=20, gravity=.3)
    assert math.hypot(plan['vx'], plan['vy']) == pytest.approx(speed)
    assert plan['driven_by'] == by
    assert plan['angle'] == pytest.approx(round(math.degrees(.4), 1))
    hard = plan_throw({'act_play': 60., 'aggression': 95.}, (0, 0), 0, [], slowest=6, fastest=20, gravity=.3)
    assert hard['driven_by'] == 'aggression' and hard['speed'] > plan['speed'] if drive == 60 else True


@pytest.mark.parametrize('start,end,centre,radius,expected', [
    ((0, 0), (200, 0), (100, 0), 10, .45),
    ((0, 0), (200, 0), (100, 10), 10, .5),
    ((0, 0), (200, 0), (100, 11), 10, None),
    ((0, 0), (0, 0), (0, 0), 10, 0.),
    ((0, 0), (0, 0), (100, 0), 10, None),
])
def test_swept_collision(start, end, centre, radius, expected):
    actual = swept_hit(start, end, centre, radius)
    assert actual == pytest.approx(expected) if expected is not None else actual is None


def test_floor_clips_at_actual_contact_not_the_projected_x():
    end, velocity, landed = flight_step((0, 90), (100, 20), (0, 500, 0, 100))
    assert end == (50., 100.) and velocity == (0., 0.) and landed
    assert swept_hit((0, 90), end, (90, 100), 10) is None


def test_view_filters_self_hidden_and_behind(tank):
    tank.item(200, 200, 'squid', 'Seen')
    tank.item(20, 200, 'squid', 'Behind')
    tank.item(150, 200, 'squid', 'Hidden').hide()
    assert tank.manager.throw_rock()
    assert tank.manager.current_throw['aimed_at'] == 'Seen'
    assert tank.manager.current_throw['vy'] < 0  # gravity compensation


def test_throw_releases_possession_and_carry_cleanup_keeps_flight(tank):
    m = tank.manager
    m.target_rock = tank.rock
    m.rock_test_phase, m.rock_carry_duration = 1, 0.
    m.update_rock_test()
    assert m.throw_animation_timer.isActive()
    assert m.flying_rock is tank.rock
    assert tank.body.carried_rock is None and not tank.body.carrying_rock
    before = tank.rock.pos()
    m.update_throw_animation()
    assert tank.rock.pos() != before
    assert not m.attach_rock_to_squid(tank.rock)
    assert not m.throw_rock()
    tank.logic.track_rock_thrown.assert_called_once()


def test_drop_clears_parent_flags_and_stays_inside_floor(tank):
    tank.state['act_play'] = 0.
    tank.manager.decide_rock_action()
    assert tank.rock.parentItem() is None and not tank.rock.is_being_carried
    assert not tank.body.carrying_rock and tank.body.carried_rock is None
    assert tank.rock.sceneBoundingRect().bottom() <= 450.
    assert not tank.manager.can_pick_up_rock(tank.rock)
    assert not tank.manager.throw_animation_timer.isActive()


def test_custom_output_uses_firing_neuron_even_without_play(tank):
    tank.state['act_play'] = 0.
    assert tank.manager.throw_rock(cause=('grown_motor', 88.))
    assert tank.manager.current_throw['driven_by'] == 'grown_motor'
    assert tank.manager.current_throw['drive'] == 88.


@pytest.mark.parametrize('landing', [False, True])
def test_fast_projectile_hits_first_body_once_even_on_landing(tank, landing):
    near = tank.item(170, 430 if landing else 200, 'squid', 'Near')
    tank.item(240, 430 if landing else 200, 'squid', 'Far')
    assert tank.manager.throw_rock()
    tank.rock.setPos(90, 390 if landing else 190)
    tank.manager.throw_velocity_x = 200.
    tank.manager.throw_velocity_y = 80. if landing else 0.
    tank.manager.update_throw_animation()
    tank.manager.update_throw_animation()
    tank.logic.on_rock_hit.assert_called_once()
    assert tank.logic.on_rock_hit.call_args.args[0] is near


def test_duplicate_hit_replays_do_not_repeat_damage_startle_or_memory():
    meeting = Encounter()
    meeting.admit()
    meeting.host_sends_frame(); meeting.visitor_receives()
    mind = meeting.visitor_mind
    meeting.visitor_squid.health = 100.
    meeting.visitor_tank.startle_squid = Mock()
    payload = Consequence(mind.visit_id, CONSEQUENCE_HIT,
                          detail={'throw_id': 'unique', 'speed': 18.}).to_payload()
    assert mind.on_consequence(payload)
    payload['at'] += 1.  # even a re-enveloped packet is the same impact
    assert mind.on_consequence(payload) is None
    assert meeting.visitor_squid.health == 98.
    meeting.visitor_tank.startle_squid.assert_called_once_with(source='rock_hit')
    assert mind.session.hits_taken == 1
    record = mind.close_session()
    assert record.hits_taken == 1 and record.valence <= -4
    memories = meeting.visitor_squid.memory_manager.short_term_memory + meeting.visitor_squid.memory_manager.long_term_memory
    assert len([m for m in memories if m['category'] == 'social']) == 1


def test_hit_given_and_throw_replay_do_not_damage_the_thrower():
    meeting = Encounter(); meeting.admit(); meeting.host_sends_frame(); meeting.visitor_receives()
    mind = meeting.visitor_mind
    meeting.visitor_squid.health = 100.
    meeting.visitor_tank.track_rock_thrown = Mock()
    for kind, detail in [(CONSEQUENCE_HIT, {'taken': False}), (CONSEQUENCE_THROWN, {'drive': 90.})]:
        payload = Consequence(mind.visit_id, kind, detail=dict(detail, throw_id='one')).to_payload()
        mind.on_consequence(payload); mind.on_consequence(payload)
    assert mind.session.hits_given == 1 and mind.session.hits_taken == 0
    assert meeting.visitor_squid.health == 100.
    meeting.visitor_tank.track_rock_thrown.assert_called_once()


def test_real_registered_hook_routes_hit_without_transmitting_intent(tank):
    meeting = Encounter(); actor = meeting.admit()
    plugin = object.__new__(MultiplayerPlugin)
    plugin.host_body, plugin.tamagotchi_logic = meeting.host_body, meeting.host_tank
    plugin.open_encounters = {}
    pm = object.__new__(PluginManager)
    pm.logger, pm.hooks = Mock(), {}
    pm.core_subscribers, pm.enabled_plugins = set(), {'multiplayer'}
    pm._initialize_hooks()
    assert pm.subscribe_to_hook('on_rock_hit', 'multiplayer', plugin.handle_rock_hit)
    throw = dict(throw_id='one', speed=17., aimed_at='Traveller', driven_by='aggression', drive=95.)
    for _ in range(2):
        pm.trigger_hook('on_rock_hit', target_uuid=actor.uuid, throw=throw)
    consequences = meeting.host_body.drain_consequences(actor)
    assert len(consequences) == 1
    assert set(consequences[0].detail) == {'what', 'speed', 'throw_id', 'taken', 'peer_uuid'}
    assert plugin.open_encounters[actor.uuid].hits_given == 1


def test_exact_threshold_tie_is_deterministic_and_does_not_divide_by_zero():
    from src.brain_constants import ACTION_THRESHOLDS
    from src.decision_engine import select_action
    state = quiet_brain(act_play=ACTION_THRESHOLDS['act_play'],
                        act_eat=ACTION_THRESHOLDS['act_eat'])
    chosen, confidence, _ = select_action(state, jitter=False)
    assert chosen in ('playing', 'eating') and confidence == 0.
    assert throw_or_drop(state) == (chosen == 'playing')


def test_distinct_rock_encounters_survive_reload_and_record_replay_is_idempotent(tmp_path, monkeypatch):
    from plugins.multiplayer.encounter import EncounterSession
    from plugins.multiplayer.peer_ledger import PeerLedger
    from plugins.multiplayer.identity import SquidIdentity
    from src.memory_manager import MemoryManager
    monkeypatch.chdir(tmp_path)
    memory = MemoryManager()
    ledger = PeerLedger(memory)
    identity = SquidIdentity('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Peer')
    for stamp, count in [(1000., 1), (1100., 2)]:
        session = EncounterSession(identity, {}, now=stamp)
        for _ in range(count):
            session.note_hit(taken=True)
        record = session.close(now=stamp+1)
        assert ledger.record(record)
        assert not ledger.record(record)
    ledger.refresh()
    assert ledger.summary(identity.uuid).hits_taken == 3
    restored = PeerLedger(MemoryManager())
    assert restored.summary(identity.uuid).hits_taken == 3
    assert restored.summary(identity.uuid).encounters == 2


def test_departed_visitors_projectile_still_hurts_and_is_remembered_once():
    from plugins.multiplayer.peer_ledger import PeerLedger
    meeting = Encounter(); actor = meeting.admit()
    plugin = object.__new__(MultiplayerPlugin)
    plugin.host_body, plugin.tamagotchi_logic = meeting.host_body, meeting.host_tank
    plugin.open_encounters = {}
    plugin.peer_ledger = PeerLedger(meeting.host_squid.memory_manager)
    meeting.host_squid.health = 100.
    meeting.host_tank.startle_squid = Mock()
    throw = dict(throw_id='late-impact', speed=18., source_uuid=actor.uuid,
                 source_identity=actor.identity.to_payload())
    meeting.host_body.remove(actor.uuid)
    assert plugin.handle_rock_hit(target_uuid=meeting.host_squid.uuid, throw=throw)
    assert not plugin.handle_rock_hit(target_uuid=meeting.host_squid.uuid, throw=throw)
    assert meeting.host_squid.health == 98.
    meeting.host_tank.startle_squid.assert_called_once_with(source='rock_hit')
    plugin.peer_ledger.refresh()
    assert plugin.peer_ledger.summary(actor.uuid).hits_taken == 1
    assert not meeting.host_body.visitors


def test_remote_ink_is_parallel_and_fires_once_per_neural_crossing():
    meeting = Encounter(); meeting.admit(); meeting.host_sends_frame(); meeting.visitor_receives()
    meeting.host_tank.ink_visitor = Mock()
    meeting.set_brain(**quiet_brain(act_rest=100., act_ink=100.))
    for _ in range(2):
        meeting.visitor_mind.tick(); meeting.host_receives()
    meeting.host_tank.ink_visitor.assert_called_once_with(meeting.actor)
    assert meeting.actor.last_intent.action == 'act_rest'
    meeting.set_brain(**quiet_brain(act_rest=100., act_ink=0.))
    meeting.visitor_mind.tick(); meeting.host_receives()
    meeting.set_brain(**quiet_brain(act_rest=100., act_ink=100.))
    meeting.visitor_mind.tick(); meeting.host_receives()
    assert meeting.host_tank.ink_visitor.call_count == 2


def test_transport_disable_cannot_cancel_or_duplicate_resident_impact(tank):
    from types import MethodType
    from src.tamagotchi_logic import TamagotchiLogic
    logic = tank.logic
    logic.feel_rock_hit = MethodType(TamagotchiLogic.feel_rock_hit, logic)
    logic.startle_squid = Mock()
    logic.plugin_manager = NS(trigger_hook=lambda *a, **k: [])
    throw = {'throw_id': 'after-disable', 'source_uuid': 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'}
    for _ in range(2):
        TamagotchiLogic.on_rock_hit(logic, tank.body.squid_item, throw)
    assert tank.body.health == 98.
    logic.startle_squid.assert_called_once_with(source='rock_hit')
    tank.body.memory_manager.add_short_term_memory.assert_called_once()
