"""Squid can throw poop at one another - and poop is not a rock.

  * a poop throw is aimed and powered by the squid's own network, as a rock
    is: its play neuron decides throw or drop, it aims at the nearest squid
    in view, and a hit is swept and reported once - with 'what': 'poop';
  * poop does no harm (no health lost, no startle) but the struck squid is
    dirtied - cleanliness falls - its anxiety rises and its happiness falls;
  * and it is the worse mark: a rock might have been play, nobody takes being
    splattered kindly - a poop hit costs an encounter more than a rock's;
  * the thrower's reasons never travel: only the fact, what and how hard.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest                                                        # noqa: E402
from PyQt5 import QtGui, QtWidgets                                   # noqa: E402

from src.throwing import HIT_EFFECTS, feel_hit                       # noqa: E402
from plugins.multiplayer.encounter import EncounterSession          # noqa: E402
from plugins.multiplayer.identity import SquidIdentity               # noqa: E402
from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin    # noqa: E402
from plugins.multiplayer.remote_protocol import CONSEQUENCE_HIT, Consequence  # noqa: E402
from test_remote_mind_stage1 import Encounter, quiet_brain           # noqa: E402

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
PEER = SquidIdentity(uuid='bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', name='Manuel')


def body(**stats):
    return NS(**dict(dict(health=100., cleanliness=80., anxiety=40., happiness=60.),
                     **stats))


def test_poop_does_no_harm_but_is_horrible():
    squid, startled = body(), []
    changed = feel_hit(squid, 'poop', startle=startled.append)
    assert squid.health == 100. and startled == []
    assert changed == {'cleanliness': HIT_EFFECTS['poop']['cleanliness'],
                       'anxiety': HIT_EFFECTS['poop']['anxiety'],
                       'happiness': HIT_EFFECTS['poop']['happiness']}
    assert squid.cleanliness < 80. and squid.anxiety > 40. and squid.happiness < 60.


def test_a_rock_knocks_and_startles():
    squid, startled = body(), []
    assert feel_hit(squid, 'rock', startle=startled.append) == {'health': -2.0}
    assert startled == ['rock_hit']
    assert (squid.cleanliness, squid.anxiety, squid.happiness) == (80., 40., 60.)


def test_being_splattered_is_the_worse_mark_on_an_encounter():
    drives = {'happiness': 50., 'anxiety': 50.}
    by_rock = EncounterSession(PEER, drives, now=0.)
    by_rock.note_hit(taken=True)
    by_poop = EncounterSession(PEER, drives, now=0.)
    by_poop.note_hit(taken=True, what='poop')
    rock, poop = by_rock.close(drives=drives, now=5.), by_poop.close(drives=drives, now=5.)
    assert poop.valence < rock.valence < 0
    detail = poop.to_memory_value()['detail']
    assert (detail['poop_taken'], detail['hits_taken']) == (1, 0)


def test_a_visitor_splattered_in_the_host_tank_feels_it_at_home():
    meeting = Encounter(); meeting.admit()
    meeting.host_sends_frame(); meeting.visitor_receives()
    mind, squid = meeting.visitor_mind, meeting.visitor_squid
    squid.health, squid.cleanliness, squid.anxiety, squid.happiness = 100., 80., 40., 60.
    meeting.visitor_tank.startle_squid = Mock()
    mind.on_consequence(Consequence(mind.visit_id, CONSEQUENCE_HIT, detail={
        'what': 'poop', 'speed': 12., 'throw_id': 'p1'}).to_payload())
    assert squid.health == 100. and squid.cleanliness == 60.
    assert squid.anxiety == 55. and squid.happiness == 50.
    meeting.visitor_tank.startle_squid.assert_not_called()
    assert (mind.session.poop_taken, mind.session.hits_taken) == (1, 0)


def test_the_host_reports_what_hit_never_why():
    meeting = Encounter(); actor = meeting.admit()
    plugin = object.__new__(MultiplayerPlugin)
    plugin.host_body, plugin.tamagotchi_logic = meeting.host_body, meeting.host_tank
    plugin.open_encounters = {}
    assert plugin.handle_rock_hit(actor.uuid, {'throw_id': 'p1', 'what': 'poop', 'speed': 11.,
                                               'aimed_at': 'Traveller', 'driven_by': 'aggression'})
    [fact] = meeting.host_body.drain_consequences(actor)
    assert fact.detail['what'] == 'poop'
    assert set(fact.detail) == {'what', 'speed', 'throw_id', 'taken', 'peer_uuid'}
    assert plugin.open_encounters[actor.uuid].poop_given == 1


@pytest.fixture
def poop_tank():
    from src.interactions2 import PoopInteractionManager
    scene = QtWidgets.QGraphicsScene(0, 0, 900, 500)
    kept = []

    def item(x, y, category='', name=''):
        pix = QtGui.QPixmap(20, 20)
        pix.fill(QtGui.QColor('white'))
        obj = scene.addPixmap(pix)
        obj.setPos(x - 10, y - 10)
        obj.category, obj.squid_name = category, name
        kept.append(obj)
        return obj
    class Body(NS):         # as Squid: carrying_poop mirrors is_carrying_poop
        carrying_poop = property(lambda s: getattr(s, 'is_carrying_poop', False),
                                 lambda s, v: setattr(s, 'is_carrying_poop', v))
    squid = Body(squid_item=item(100, 200, 'squid', 'Resident'), uuid='u-res',
               squid_x=90, squid_y=190, squid_width=20, squid_height=20,
               squid_direction='right', current_view_angle=0., status='roaming',
               happiness=60., satisfaction=60., anxiety=30.,
               memory_manager=NS(add_short_term_memory=Mock()))
    logic = NS(squid=squid, brain_window=NS(brain_widget=NS(state=quiet_brain(act_play=100.))),
               statistics_window=NS(award=Mock()), track_poop_thrown=Mock(),
               on_rock_hit=Mock(), plugin_manager=NS(plugins={}))
    config = NS(get_poop_config=lambda: dict(min_carry_duration=3., max_carry_duration=3.,
                                             cooldown_after_throw=10.))
    manager = PoopInteractionManager(squid, logic, scene, Mock(), config)
    poop = item(100, 200, 'poop')
    poop.filename = 'poop1.png'
    assert manager.attach_poop_to_squid(poop)
    yield NS(item=item, squid=squid, logic=logic, manager=manager, poop=poop)
    manager.cleanup()
    manager.throw_animation_timer.timeout.disconnect()
    manager.poop_test_timer.timeout.disconnect()
    for obj in kept:
        if obj.scene() is scene:
            scene.removeItem(obj)


def test_a_poop_throw_is_aimed_by_the_network_and_strikes_once(poop_tank):
    target = poop_tank.item(400, 200, 'squid', 'Visitor')
    assert poop_tank.manager.throw_poop()
    throw = poop_tank.manager.current_throw
    assert throw['what'] == 'poop' and throw['aimed_at'] == 'Visitor'
    assert throw['driven_by'] == 'act_play' and poop_tank.manager.throw_velocity_x > 0
    for _ in range(80):
        if poop_tank.manager.flying_poop is None:
            break
        poop_tank.manager.update_throw_animation()
    poop_tank.logic.on_rock_hit.assert_called_once()
    struck, fact = poop_tank.logic.on_rock_hit.call_args.args
    assert struck is target and fact['what'] == 'poop'


def test_not_playing_it_puts_the_poop_down(poop_tank):
    poop_tank.logic.brain_window.brain_widget.state = quiet_brain()
    poop_tank.manager.decide_poop_action()
    assert poop_tank.manager.current_throw is None
    assert not getattr(poop_tank.squid, 'is_carrying_poop', False)
