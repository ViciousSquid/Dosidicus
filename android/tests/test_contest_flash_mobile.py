"""Mobile: a fight over a rock opens with the rock flashing dark red.

A fight starts on contact when one squid is aggro; if either holds a rock, that
rock is what they fight over. It flashes from 2 s before the scuffle - the two
squaring up, still - until 2 s after. The renderer draws it; nothing changes.
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from dosidicus_mobile.engine import Simulation                       # noqa: E402


def advance(sim, seconds, dt=.1):
    flashes = []
    for _ in range(int(round(seconds / dt))):
        sim.squid.brain.sim_time += dt
        sim._update_fight(dt)
        flashes.append(sim.contested_flash())
    return flashes


def meeting(holding=True):
    sim = Simulation()
    sim._fight_cooldown = 0.
    v = sim.add_visitor(Simulation().to_dict(), name='Thief')
    v.update(x=sim.squid.x + 30., y=sim.squid.y, leaving=False)
    rock = sim.add_decoration('rock01.png', 'rock', v['x'], v['y'])
    if holding:
        v['carried_rock'] = rock['id']
    sim.squid.brain.state['aggression'] = 95.
    return sim, v, rock


def test_a_fight_over_a_rock_squares_up_with_the_rock_flashing_then_scuffles():
    sim, v, rock = meeting()
    sim._update_fight(.1)
    assert sim.fight['phase'] == 'squaring'
    where = (sim.squid.x, v['x'])
    flashes = advance(sim, 1.5)
    assert (sim.squid.x, v['x']) == where                     # facing off, still
    assert {lit for _, lit in flashes} == {True, False}       # it flashes
    assert all(did == rock['id'] for did, _ in flashes)
    advance(sim, .6)
    assert sim.fight['phase'] in ('approaching', 'fighting')
    for _ in range(200):                                      # scuffle, result, over
        if sim.fight is None:
            break
        advance(sim, .1)
    assert sim.fight is None and sim.contested_flash()[0] == rock['id']   # still after
    advance(sim, Simulation.CONTEST_AFTER - .3)
    assert sim.contested_flash()[0] == rock['id']
    advance(sim, .5)
    assert sim.contested_flash() == (None, False)


def test_a_fight_over_nothing_starts_at_once_and_nothing_flashes():
    sim, v, _ = meeting(holding=False)
    sim._update_fight(.1)
    assert sim.fight['phase'] == 'approaching' and sim.contested_flash() == (None, False)
