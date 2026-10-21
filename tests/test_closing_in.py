"""A squid sees how far the squid it is aiming at is - and closes in if needed.

The network decides whether to throw (play) and how hard (play or aggression);
whether that is far enough is what the squid sees. A throw that would not
reach the squid it is aiming at is not thrown: the squid keeps hold of the
rock (or poop), swims at its target, and looks again shortly - so a calm
squid only lobs at close targets, while an aggro one can reach across the
tank. With nobody in view it throws along its gaze, as before; a throw a
bound output neuron fires is that neuron's decision, and goes regardless.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import throwing                                        # noqa: E402
from test_rock_throwing import tank                             # noqa: E402,F401  (fixture)
from test_remote_mind_stage1 import quiet_brain                 # noqa: E402

TANK = (10., 890., 10., 440.)


def plan(drive, distance):
    return throwing.plan_throw({'act_play': float(drive)}, (100., 200.), 0.,
                               [('Visitor', 100. + distance, 200.)], slowest=6.,
                               fastest=20., gravity=.3, drag=.02, bounds=TANK)


def test_how_far_a_throw_reaches_depends_on_how_hard_the_network_throws():
    assert plan(40, 300)['reaches'] and not plan(40, 500)['reaches']
    assert plan(100, 500)['reaches']
    assert throwing.out_of_reach(plan(40, 500)) and not throwing.out_of_reach(plan(100, 500))


def test_with_nobody_in_view_there_is_nothing_to_reach():
    gazing = throwing.plan_throw({'act_play': 90.}, (100., 200.), 0., [], slowest=6.,
                                 fastest=20., gravity=.3)
    assert 'reaches' not in gazing and not throwing.out_of_reach(gazing)


def test_reaching_is_judged_by_the_real_flight_landing_included():
    assert throwing.reaches((0., 200.), (380., 250.), 15., -3., .3)
    # The same throw, with the sand at 220: it lands short of the target.
    assert not throwing.reaches((0., 200.), (380., 250.), 15., -3., .3,
                                bounds=(-1e9, 1e9, -1e9, 220.))


def test_a_calm_squid_closes_in_on_a_far_squid_instead_of_throwing(tank):
    far = tank.item(700, 200, 'squid', 'Visitor')
    tank.state.clear(); tank.state.update(quiet_brain(act_play=50.))
    thoughts, drives = [], []
    tank.logic.brain_window.add_thought = thoughts.append
    tank.body.DRIVE_DECISION = 'decision'
    tank.body.set_neural_drive = lambda action, **kw: drives.append((action, kw['target']))
    assert not tank.manager.throw_rock()
    assert tank.body.carried_rock is tank.rock                   # still holding it
    assert tank.manager.flying_rock is None
    assert drives and drives[0][0] == 'approach_squid'
    assert drives[0][1][0] > 600                                 # towards the far squid
    assert tank.body.status == 'closing in on Visitor'
    assert thoughts == ['Visitor is too far to reach: closing in.']
    assert not tank.body.rock_decision_made                      # it will look again
    assert not tank.manager.throw_rock() and len(thoughts) == 1  # said once
    assert far is not None


def test_an_aggro_squid_throws_from_where_it_is(tank):
    tank.item(600, 200, 'squid', 'Visitor')
    tank.state.clear(); tank.state.update(quiet_brain(act_play=50., aggression=100.))
    assert tank.manager.throw_rock()
    assert tank.manager.current_throw['aimed_at'] == 'Visitor'
    assert tank.manager.current_throw['reaches'] is True


def test_a_visitors_body_closes_in_on_the_host_side_too():
    from test_remote_mind_stage1 import Encounter
    from plugins.multiplayer.remote_protocol import ActionIntent
    meeting = Encounter()
    actor = meeting.admit(x=100., y=400.)
    actor.held_item = held = object()
    meeting.host_tank.throw_visitor_rock = lambda a, item, intent: {
        'closing_in': True, 'target_at': (600., 400.), 'aimed_at': 'Resident'}
    x0 = actor.x
    meeting.host_body.apply_intent(actor, ActionIntent(actor.visit_id, 'act_play', seq=1,
                                                       sent_at=meeting.clock(),
                                                       activation=50.))
    assert actor.held_item is held and actor.x > x0          # kept it, swam at it


def test_a_mobile_squid_closes_in_then_throws():
    sys.path.append(str(Path(__file__).resolve().parents[1] / 'android'))
    from dosidicus_mobile.engine import Simulation
    sim = Simulation()
    sim._fight_cooldown = 1e9
    squid = sim.squid
    squid.x, squid.y, squid.direction = 100., 300., 'right'
    visitor = sim.add_visitor(Simulation().to_dict(), name='Guest')
    visitor['x'], visitor['y'] = 100. + 650., 300.
    sim.decorations.append({'id': 'r1', 'category': 'rock', 'x': squid.x, 'y': squid.y - 26})
    squid.carrying_rock, squid.carried_rock_id, squid._carry_until = True, 'r1', 0.
    squid.brain.state.update(quiet_brain(act_play=50.))
    sim._update_rock_play(1 / 30)
    assert squid.carrying_rock and 'r1' not in sim._rock_velocities
    assert sim.last_status == 'closing in on Guest'
    visitor['x'] = squid.x + 250.                             # now within its reach
    squid._carry_until = 0.
    sim._update_rock_play(1 / 30)
    assert 'r1' in sim._rock_throws and sim._rock_throws['r1']['aimed_at'] == 'Guest'
