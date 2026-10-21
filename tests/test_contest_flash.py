"""The object two squid fight over flashes dark red.

When a fight arises from a contest over an object, the object is tinted dark
red and flashes from 2 s before the scuffle - a lead-in after the fight is
decided, before the bodies come together - until 2 s after it. A drawing only:
it changes nothing about the object or either squid, and any tint the object
had is put back.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5 import QtCore, QtGui, QtWidgets                          # noqa: E402
from PyQt5.QtTest import QTest                                       # noqa: E402

from plugins.multiplayer.remote_entity_manager import RemoteEntityManager  # noqa: E402
from src.lifecycle import Lifecycle                                  # noqa: E402

_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def tank():
    scene = QtWidgets.QGraphicsScene()
    entities = RemoteEntityManager(scene, 1280, 900)
    entities.position_update_timer.stop()
    entities.swim_timer.stop()
    entities.CONTEST_FLASH_MS = 20
    pixmap = QtGui.QPixmap(40, 40)
    pixmap.fill(QtCore.Qt.gray)
    rock = scene.addPixmap(pixmap)
    return scene, entities, rock


def test_the_object_flashes_dark_red_then_is_put_back_as_it_was():
    scene, entities, rock = tank()
    assert entities.flash_contested(rock, 200)
    effect = rock.graphicsEffect()
    assert isinstance(effect, QtWidgets.QGraphicsColorizeEffect)
    assert effect.color() == QtGui.QColor(*RemoteEntityManager.CONTEST_RED)
    strengths = set()
    for _ in range(6):
        QTest.qWait(25)
        strengths.add(rock.graphicsEffect().strength() if rock.graphicsEffect() else None)
    assert {0.0, 1.0} <= strengths                     # it flashes
    QTest.qWait(250)
    assert rock.graphicsEffect() is None


def test_an_objects_own_tint_comes_back():
    scene, entities, rock = tank()
    tint = QtWidgets.QGraphicsColorizeEffect()
    tint.setColor(QtGui.QColor(255, 120, 120))
    tint.setStrength(0.3)
    rock.setGraphicsEffect(tint)
    assert entities.flash_contested(rock, 60)
    QTest.qWait(150)
    assert rock.graphicsEffect() is tint
    assert tint.color() == QtGui.QColor(255, 120, 120) and abs(tint.strength() - 0.3) < 1e-6


def test_another_kind_of_effect_is_left_alone_and_a_gone_object_stops():
    scene, entities, rock = tank()
    rock.setGraphicsEffect(QtWidgets.QGraphicsOpacityEffect())
    assert not entities.flash_contested(rock, 100)
    _, entities, food = tank()
    assert entities.flash_contested(food, 1000)
    food.scene().removeItem(food)                      # eaten mid-fight
    QTest.qWait(60)
    assert not entities._contest_flashes


def _bodies(scene):
    pixmap = QtGui.QPixmap(253, 147)
    resident = SimpleNamespace(squid_x=400., squid_y=350., can_move=True,
                               squid_item=scene.addPixmap(pixmap), lifecycle=Lifecycle())
    return resident, SimpleNamespace(x=620., y=350.), {'visual': scene.addPixmap(pixmap)}


def test_a_fight_over_an_object_waits_for_its_lead_in_before_the_bodies_meet():
    scene, entities, rock = tank()
    entities.CONTEST_LEAD_MS = 80
    resident, actor, guest = _bodies(scene)
    entities.remote_squids['guest'] = guest
    assert entities.start_fight_sequence('peer', 'guest', resident, actor, contested=rock)
    assert resident.can_move and resident.squid_x == 400.      # still its own
    assert isinstance(rock.graphicsEffect(), QtWidgets.QGraphicsColorizeEffect)
    QTest.qWait(200)
    assert not resident.can_move and resident.squid_x > 400.  # closing in now
    entities._end_scuffle('peer')
    assert resident.can_move


def test_a_fight_ended_during_its_lead_in_never_starts():
    scene, entities, rock = tank()
    entities.CONTEST_LEAD_MS = 60
    resident, actor, guest = _bodies(scene)
    entities.remote_squids['guest'] = guest
    finished = []
    entities.start_fight_sequence('peer', 'guest', resident, actor,
                                  on_finished=lambda: finished.append(True), contested=rock)
    entities._end_scuffle('peer')
    QTest.qWait(150)
    assert resident.can_move and resident.squid_x == 400. and 'peer' not in entities._scuffles


def test_a_fight_over_nothing_starts_at_once():
    scene, entities, _ = tank()
    resident, actor, guest = _bodies(scene)
    entities.remote_squids['guest'] = guest
    assert entities.start_fight_sequence('peer', 'guest', resident, actor)
    assert not resident.can_move
    entities._end_scuffle('peer')


def test_the_host_passes_the_contested_object_and_holds_the_visitor_through_the_lead_in():
    from plugins.multiplayer.encounter_sensors import ConspecificView
    from plugins.multiplayer.identity import SquidIdentity
    from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
    import logging
    scene, entities, rock = tank()
    clock = lambda: 1000.                                   # noqa: E731
    resident = SimpleNamespace(uuid='r', squid_x=600., squid_y=400., squid_width=0.,
                               squid_height=0.)
    plugin = MultiplayerPlugin()
    plugin.logger = logging.getLogger('contest-flash-test')
    plugin.tamagotchi_logic = SimpleNamespace(squid=resident, brain_window=SimpleNamespace(
        brain_widget=SimpleNamespace(state={'aggression': 90.})))
    actor = SimpleNamespace(last_intent=None, body_busy_until=0.)
    plugin.host_body = SimpleNamespace(visitor=lambda uuid: actor, clock=clock, visitors={})
    calls = []
    entities.start_fight_sequence = lambda *a, **kw: calls.append(kw) or True
    plugin.entity_manager = entities
    plugin.visit_node_ids = {}
    plugin.conspecific_view = ConspecificView(clock=clock)
    plugin.conspecific_view.on_contest = plugin.show_fight_cloud
    presence = plugin.conspecific_view.observe_peer(
        SquidIdentity(uuid='v', name='Guest'), x=650., y=400., observer_x=600., observer_y=400.)
    plugin.conspecific_view.note_contest(presence, rock, taken=True, by='peer')
    assert calls and calls[0]['contested'] is rock
    assert actor.body_busy_until == 1000. + RemoteEntityManager.CONTEST_LEAD_MS / 1000. + 3.2
