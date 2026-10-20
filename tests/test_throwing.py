"""The throw planner: aimed and powered by the squid's own network.

  * it aims at what it attends to: the nearest squid in its view cone,
    leading for the drop and the drag, else along its gaze;
  * how hard comes from its play neuron, or its aggression if stronger.

Throwing in the tank - possession, flight, hits, what a struck squid feels -
is specified in tests/test_rock_throwing.py and
android/tests/test_rock_throwing_mobile.py.
"""
import math

import pytest

from src import throwing


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


@pytest.mark.parametrize('distance', [150., 300., 450., 600.])
def test_a_hard_throw_lands_on_its_target_under_the_shared_physics(distance):
    """Aim leads for drop AND drag, so it lands under flight_step - the one
    flight both platforms run - with the desktop's own constants."""
    from src.interactions import RockInteractionManager as R
    plan = throwing.plan_throw({'act_play': 100.}, (0, 400.), 0.,
                               [('Visitor', distance, 400.)], slowest=R.THROW_SLOWEST,
                               fastest=R.THROW_FASTEST, gravity=R.THROW_GRAVITY,
                               drag=R.THROW_DRAG)
    position, velocity = (0., 400.), (plan['vx'], plan['vy'])
    bounds = (-1e4, 1e4, -1e4, 1e4)
    closest = math.inf
    for _ in range(300):
        end, velocity, _ = throwing.flight_step(position, velocity, bounds,
                                                gravity=R.THROW_GRAVITY)
        if throwing.swept_hit(position, end, (distance, 400.), R.HIT_RADIUS) is not None:
            closest = 0.
            break
        position = end
    assert closest == 0.


def _hit_rate(practice, distance, seed=7, throws=400):
    import random as _random
    rng, hits = _random.Random(seed), 0
    for _ in range(throws):
        plan = throwing.plan_throw({'act_play': 100.}, (0., 400.), 0.,
                                   [('Visitor', distance, 400.)], slowest=6., fastest=20.,
                                   gravity=.3, drag=.02, practice=practice, rng=rng)
        hits += throwing.reaches((0., 400.), (distance, 400.), plan['vx'], plan['vy'], .3)
    return hits / throws


def test_throws_do_not_always_land_and_practice_makes_them_land_more():
    novice, practised, seasoned = (_hit_rate(n, 400.) for n in (0, 25, 400))
    assert novice < 0.75                      # a beginner misses a good deal
    assert novice < practised < seasoned      # it gets better with every throw
    assert seasoned < 1.0 or _hit_rate(400, 600.) < 1.0   # never perfect at range


def test_how_far_a_throw_strays_narrows_with_practice_but_never_to_nothing():
    assert throwing.spread(0) == (throwing.NOVICE_ANGLE_SD, throwing.NOVICE_SPEED_SD)
    wide, narrower, narrowest = (throwing.spread(n)[0] for n in (0, 12, 10000))
    assert wide > narrower > narrowest > throwing.SKILLED_ANGLE_SD - 1e-9
    assert throwing.skill(throwing.PRACTICE_SCALE) == 0.5


def test_it_judges_reach_on_the_throw_it_means_and_records_how_it_strayed():
    import random as _random
    plan = throwing.plan_throw({'act_play': 100.}, (0., 400.), 0., [('V', 300., 400.)],
                               slowest=6., fastest=20., gravity=.3, drag=.02,
                               practice=0, rng=_random.Random(3))
    meant = throwing.plan_throw({'act_play': 100.}, (0., 400.), 0., [('V', 300., 400.)],
                                slowest=6., fastest=20., gravity=.3, drag=.02)
    assert plan['reaches'] == meant['reaches'] and plan['angle'] == meant['angle']
    assert (plan['vx'], plan['vy']) != (meant['vx'], meant['vy'])
    assert plan['practice'] == 0 and plan['aim_error'] != 0


def test_practice_is_its_own_record_of_throws_counted_once():
    from types import SimpleNamespace as NS
    desktop = NS(total_rocks_thrown=7, total_poops_thrown=3)
    assert throwing.practice_of(desktop) == 10
    mobile = NS(rocks_thrown=5)
    assert throwing.practice_of(mobile, mobile, None) == 5
