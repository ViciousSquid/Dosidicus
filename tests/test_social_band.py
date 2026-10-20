"""The social network has a band of its own in the brain - once it exists.

A squid that never meets another has no social neuron, and no SOCIAL band.
When the first social sense or neuron grows, the band appears on the bottom
growth row, its members laid out in canonical order (senses, then neurons),
and the other grown neurons use the rows above. Social neurons are pruned like
anything else when they are not useful and grow again when they matter -
except can_see_squid, and except a neuron life has marked for good.
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import brain_constants as bc                                # noqa: E402
from src.neurogenesis import ExperienceContext, FunctionalNeuron     # noqa: E402
from src.portable_brain import HeadlessBrain                         # noqa: E402


def test_no_band_until_something_social_has_grown():
    assert 'social' not in bc.display_rows(['hunger', 'novelty_1', 'stress_2'])
    rows = bc.display_rows(['hunger', 'can_see_squid'])
    assert rows['social'] is bc.SOCIAL_ROW and rows['social']['label'] == 'SOCIAL'


def test_social_members_sit_on_their_band_in_canonical_order():
    grown = ['novelty_1', 'aggression', 'stress_2', 'can_see_squid', 'social_play',
             'aquarium_nearby']
    positions = bc.growth_positions(grown)
    social = [n for n in grown if bc.is_social_member(n)]
    assert {positions[n][1] for n in social} == {bc.SOCIAL_ROW['y']}
    by_x = sorted(social, key=lambda n: positions[n][0])
    assert by_x == [n for n in bc.SOCIAL_MEMBERS if n in social]   # senses, then neurons
    assert {positions[n][1] for n in ('novelty_1', 'stress_2')} <= set(bc.GROWTH_ROW_YS_BESIDE_SOCIAL)
    top, bottom = bc.SOCIAL_ROW['band']
    assert top < bc.SOCIAL_ROW['y'] < bottom
    # Without any social member, all three growth rows are free as before.
    many = [f'novelty_{i}' for i in range(20)]
    assert {y for _, y in bc.growth_positions(many).values()} == set(bc.GROWTH_ROW_YS)


def test_social_neurons_have_the_social_rows_colour():
    for name in ('can_see_squid', 'aquarium_nearby', 'aggression', 'social_flee'):
        assert bc.neuron_row(name) == 'social'
        assert bc.neuron_row_color(name) == bc.ROW_COLORS['social']
    assert bc.neuron_row('novelty_1') is None and bc.neuron_row('hunger') == 'core'


def grow(brain, name, concept=None, age=3600.0):
    ctx = ExperienceContext('social' if concept else 'novelty', {}, [], {}, 'neutral',
                            time.time() - age)
    neuron = FunctionalNeuron(name, ctx.trigger_type, ctx,
                              origin_deficit={'evidence': {'concept': concept}} if concept else {})
    brain.enhanced_neurogenesis.functional_neurons[name] = neuron
    brain.positions[name] = (0., 0.)
    brain.state[name] = 0.
    return neuron


def test_a_headless_brain_lays_its_grown_neurons_out_as_the_desktop_does():
    brain = HeadlessBrain()
    newborn = dict(brain.positions)
    grow(brain, 'novelty_1')
    grow(brain, 'can_see_squid', 'can_see_squid')
    brain.relayout_grown_neurons()
    assert brain.positions['can_see_squid'][1] == bc.SOCIAL_ROW['y']
    assert brain.positions['novelty_1'][1] in bc.GROWTH_ROW_YS_BESIDE_SOCIAL
    assert all(brain.positions[n] == p for n, p in newborn.items())     # never moved
    # A loader that says what the brain was born with is believed.
    brain.innate_neurons = set(brain.positions)
    assert 'novelty_1' in brain.innate_neurons


def pruned(brain, rounds=10):
    gone = []
    for _ in range(rounds):
        name = brain.enhanced_neurogenesis.intelligent_pruning()
        if name is None:
            break
        gone.append(name)
    return gone


def test_unused_social_neurons_are_pruned_but_not_can_see_squid_or_a_scar():
    brain = HeadlessBrain()
    grow(brain, 'can_see_squid', 'can_see_squid')
    grow(brain, 'social_play', 'social_play')
    grow(brain, 'aggression', 'aggression').resting_level = 30.0    # a fight's mark
    grow(brain, 'curious_thing', 'some_other_concept')               # not social: kept
    gone = pruned(brain)
    assert gone == ['social_play']
    assert 'social_play' not in brain.positions
    assert {'can_see_squid', 'aggression', 'curious_thing'} <= set(brain.positions)
    [record] = [o for o in brain.ledger.pruned if o.name == 'social_play']   # with why
    assert 'lowest utility' in record.prune_reason
