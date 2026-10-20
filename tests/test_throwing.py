"""Rock throws are aimed and powered by the squid's own network; a hit is only felt.

Held to the rules:
  * whether to throw (or drop) is the squid's play neuron - not dice;
  * it aims at what it attends to: the nearest squid in its view cone,
    leading for the drop and drag, else along its gaze;
  * how hard comes from its play neuron, or its aggression if stronger;
  * a struck squid only feels it - a startle and a knock - and is never told
    whether it was play or an attack.
"""
import math
import os
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                           # noqa: E402
from PyQt5 import QtWidgets                             # noqa: E402

from src import throwing                                # noqa: E402

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_throw_or_drop_is_the_play_neuron():
    assert throwing.throw_or_drop({'act_play': 90.})
    assert not throwing.throw_or_drop({'act_play': 5.})


def test_the_harder_drive_throws_and_says_which():
    assert throwing.throw_drive({'act_play': 40.}) == (40., 'act_play')
    assert throwing.throw_drive({'act_play': 40., 'aggression': 90.}) == (90., 'aggression')
    gentle, _ = throwing.throw_speed({'act_play': 20.}, 6., 20.)
    hard, why = throwing.throw_speed({'act_play': 20., 'aggression': 100.}, 6., 20.)
    assert gentle < hard == 20. and why['driven_by'] == 'aggression'


def test_with_nobody_in_view_it_throws_along_its_gaze():
    angle, target, why = throwing.aim((0, 0), 1.2, [], 10., .3)
    assert (angle, target, why['aimed_at']) == (1.2, None, None)


def test_it_aims_at_the_nearest_squid_in_view_leading_for_the_drop():
    angle, target, why = throwing.aim((0, 0), math.pi, [('Far', 500, 0), ('Near', 200, 0)],
                                      15., .3, .02)
    assert target == 'Near'
    assert angle < 0 and why['lead_for_drop'] > 0       # aimed above, to fall onto it


@pytest.mark.parametrize('distance', [150., 300., 450.])
def test_a_hard_throw_lands_on_its_target_under_the_real_physics(distance):
    plan = throwing.plan_throw({'act_play': 100.}, (0, 0), 0.,
                               [('Visitor', distance, 0.)], slowest=6., fastest=20.,
                               gravity=.3, drag=.02)
    x = y = 0.
    vx, vy = plan['vx'], plan['vy']
    closest = math.inf
    for _ in range(300):                                # the desktop's own steps
        x, y = x + vx, y + vy
        vy += .3
        vx *= .98
        closest = min(closest, math.hypot(x - distance, y))
    assert closest <= 45.                               # interactions.HIT_RADIUS


def test_a_desktop_throw_is_aimed_and_a_hit_is_reported_once():
    from src.interactions import RockInteractionManager
    scene = QtWidgets.QGraphicsScene(0, 0, 1280, 900)
    me = scene.addRect(0, 0, 60, 40)
    me.setPos(300, 400)
    visitor = scene.addRect(0, 0, 60, 40)
    visitor.setPos(560, 400)
    visitor.category, visitor.squid_name, visitor.peer_uuid = 'squid', 'Manuel', 'uuid-m'
    rock = scene.addRect(0, 0, 20, 20)
    hits = []
    squid = SimpleNamespace(squid_item=me, carried_rock=rock, current_view_angle=0.0,
                            happiness=50, satisfaction=50, anxiety=50, status='',
                            memory_manager=SimpleNamespace(add_short_term_memory=mock.Mock()))
    logic = SimpleNamespace(
        brain_window=SimpleNamespace(brain_widget=SimpleNamespace(
            state={'act_play': 95., 'aggression': 0.})),
        statistics_window=SimpleNamespace(award=lambda points: None),
        on_rock_hit=lambda item, throw: hits.append((item.squid_name, throw)))
    manager = object.__new__(RockInteractionManager)
    manager.squid, manager.logic, manager.scene = squid, logic, scene
    manager.show_message = None
    manager.rock_config = {'happiness_boost': 0, 'satisfaction_boost': 0,
                           'anxiety_reduction': 0, 'cooldown_after_throw': 0}
    manager.throw_animation_timer = mock.Mock()
    manager.throw_animation_timer.isActive.return_value = False
    manager.multiplayer_plugin = None
    manager.cleanup_after_throw = lambda: None

    assert manager.throw_rock()
    assert manager.current_throw['aimed_at'] == 'Manuel'
    assert manager.throw_velocity_x > 0                 # towards it, not a coin flip
    assert 'at Manuel' in squid.status
    for _ in range(60):
        manager.update_throw_animation()
    assert [name for name, _ in hits] == ['Manuel']     # struck once
    assert hits[0][1]['driven_by'] == 'act_play'
    memory = squid.memory_manager.add_short_term_memory.call_args.args[2]
    assert memory['throw']['aimed_at'] == 'Manuel'


def test_a_struck_visitor_only_feels_it_at_home():
    from plugins.multiplayer.encounter import EncounterSession
    from plugins.multiplayer.identity import SquidIdentity
    from plugins.multiplayer.remote_protocol import CONSEQUENCE_HIT, Consequence
    from plugins.multiplayer.visitor_mind import VisitorMind
    squid = SimpleNamespace(health=100., statistics=None)
    startled = []
    logic = SimpleNamespace(squid=squid, startle_squid=lambda source: startled.append(source))
    mind = VisitorMind(tamagotchi_logic=logic, send=lambda *a: True, clock=lambda: 10.)
    mind.visit_id = 'v1'
    mind.session = EncounterSession(SquidIdentity(uuid='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
                                                  name='Resident'), {}, now=0.)
    mind.on_consequence(Consequence('v1', CONSEQUENCE_HIT,
                                    detail={'what': 'rock', 'speed': 18.}).to_payload())
    assert startled == ['rock_hit']
    assert squid.health == 100. - VisitorMind.HIT_HEALTH_COST
    assert mind.session.hits_taken == 1
    record = mind.session.close(drives={}, now=5.)
    assert record.valence < 0 and record.to_memory_value()['detail']['hits_taken'] == 1


def test_the_host_reports_the_fact_never_the_intent():
    from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
    from plugins.multiplayer.remote_protocol import CONSEQUENCE_HIT
    reported = []
    actor = SimpleNamespace(uuid='uuid-m')
    plugin = MultiplayerPlugin()
    plugin.host_body = SimpleNamespace(
        visitor=lambda uuid: actor if uuid == 'uuid-m' else None,
        _report=lambda who, kind, detail: reported.append((kind, detail)))
    plugin.open_encounters = {}
    assert plugin.handle_rock_hit('uuid-m', {'speed': 17.6, 'driven_by': 'aggression',
                                             'aimed_at': 'Manuel'})
    assert reported == [(CONSEQUENCE_HIT, {'what': 'rock', 'speed': 17.6})]
    assert not plugin.handle_rock_hit('someone-else', {})


def test_mobile_throws_are_aimed_powered_and_felt():
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    sim = Simulation()
    sim._fight_cooldown = 1e9
    squid = sim.squid
    squid.x, squid.y, squid.direction = 300., 400., 'right'
    visitor = sim.add_visitor(Simulation().to_dict(), name='Guest')
    visitor['x'], visitor['y'] = 560., 400.
    rock = {'id': 'r1', 'category': 'rock', 'x': squid.x, 'y': squid.y - 26}
    sim.decorations.append(rock)
    squid.carrying_rock, squid.carried_rock_id, squid._carry_until = True, 'r1', 0.
    squid.brain.state['act_play'] = 100.
    startled = []
    sim._visitor_minds[visitor['id']].startle = lambda source: startled.append(source)
    sim._update_rock_play(1 / 30)
    plan = sim._rock_throws['r1']
    assert plan['aimed_at'] == 'Guest' and sim._rock_velocities['r1'][0] > 0
    for _ in range(90):
        sim._update_rock_play(1 / 30)
    assert plan['hit'] == 'Guest' and startled == ['rock_hit']
    assert visitor['hits_taken'] == 1


def test_mobile_squid_that_is_not_playing_puts_the_rock_down():
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    sim = Simulation()
    squid = sim.squid
    sim.decorations.append({'id': 'r1', 'category': 'rock', 'x': squid.x, 'y': squid.y})
    squid.carrying_rock, squid.carried_rock_id, squid._carry_until = True, 'r1', 0.
    squid.brain.state['act_play'] = 0.
    sim._update_rock_play(1 / 30)
    assert not squid.carrying_rock and 'r1' not in sim._rock_velocities
