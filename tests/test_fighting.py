"""Fights: whether one starts (predisposition) and who wins (ability) are different things.

Held to the rules:
  * a fight is started by a squid's grown `aggression` neuron - 0 placid and
    relaxed, 100 fully aggro - never by its personality label or dice;
  * who wins comes from body, experience and how hard each network commits -
    an attacker with its aggression, a defender with its alarm - so a squid
    quick to fight is not thereby good at it;
  * a fight can mark a squid for good: its resting aggression rises and never
    falls, and every rise says why;
  * how encounters go moves how a squid meets every squid, strangers too, so
    two squid born alike diverge with their lives - each change recorded.
"""
from types import SimpleNamespace

import pytest

from src import fighting
from src.decision_engine import wants
from src.portable_brain import HeadlessBrain
from src.social_learning import learn_from_encounter


def aggressive_brain():
    """A stubborn squid that went at another while alarmed, and grew aggression."""
    brain = HeadlessBrain()
    brain.personality = 'stubborn'
    brain.state['anxiety'] = 75.
    for _ in range(6):
        brain.perceive('squid_in_view', 100.)
        brain.perceive('squid_proximity', 80.)
        brain.propagate()
    assert 'aggression' in brain.positions
    return brain


def test_aggression_is_a_grown_neuron_with_its_cause():
    brain = aggressive_brain()
    origin = brain.ledger.origins['aggression']
    assert origin.deficit_summary == 'It went at another squid while alarmed and had no neuron for that'
    assert brain.neuron_shapes['aggression'] == 'hexagon'
    assert not brain.is_connector_neuron('aggression')


def test_aggression_reads_from_placid_to_fully_aggro():
    brain = aggressive_brain()
    assert fighting.fight_predisposition(brain.state)[0] > fighting.AGGRESSION_THRESHOLD
    brain.state['anxiety'] = 50.
    for _ in range(30):                        # nobody in view, nothing alarming
        brain.perceive('squid_in_view', 0.)
        brain.perceive('squid_proximity', 0.)
        brain.propagate()
    assert brain.state['aggression'] < 5.     # back to placid and relaxed


def test_a_squid_without_an_aggression_neuron_cannot_start_a_fight():
    calm = {'anxiety': 100., 'act_play': 100.}
    assert fighting.fight_predisposition(calm) == (0.0, {'aggression': 0.0, 'grown': False,
                                                          'alarm': 100.0})


def test_ability_is_not_aggression_an_attacked_timid_squid_can_win():
    # Fully aggro, but hurt, hungry and tired.
    attacker_fit, why_a = fighting.fitness(health=45., hunger=90., sleepiness=85.)
    attacker = fighting.side({'aggression': 95.}, attacker_fit, why_a, attacking=True)
    # Never starts fights - no aggression neuron at all - but fit and alarmed.
    defender_fit, why_d = fighting.fitness(health=100., hunger=20., sleepiness=20.)
    defender = fighting.side({'anxiety': 95.}, defender_fit, why_d, attacking=False)
    assert attacker['committed_by'] == 'aggression' and defender['committed_by'] == 'alarm'
    record = fighting.resolve_fight(attacker, defender, rng=lambda: .5)
    assert record['first_chance'] < .3 and not record['first_won']


def test_experience_and_knowing_how_to_fight_count():
    green = fighting.fitness()[0]
    veteran = fighting.fitness(fights_won=6, fights_lost=4)[0]
    assert veteran > green
    alarm_only = fighting.commitment({'anxiety': 60.}, attacking=False)
    trained = fighting.commitment({'anxiety': 60., 'social_fight': 95.}, attacking=False)
    assert trained[0] > alarm_only[0] and trained[1] == 'social_fight'


def test_the_better_squid_usually_wins_but_it_is_not_certain():
    strong = {'ability': 120.}
    weak = {'ability': 60.}
    chance = fighting.resolve_fight(strong, weak, rng=lambda: 0.)['first_chance']
    assert .75 < chance < 1.
    assert not fighting.resolve_fight(strong, weak, rng=lambda: .999)['first_won']


def test_a_fight_marks_aggression_for_good_and_says_why():
    brain = aggressive_brain()
    growth = brain.enhanced_neurogenesis
    for n in range(40):
        fighting.scar(brain, n % 3 == 0, f'fight {n}')
    record = growth.functional_neurons['aggression']
    assert record.resting_level == fighting.AGGRESSION_SCAR_CEILING
    rises = [entry['to'] for entry in record.resting_history]
    assert rises == sorted(rises) and record.resting_history[0]['cause'] == 'fight 0'
    # Nothing lowers it: not a raise of nothing, not a reload.
    assert growth.raise_resting_level('aggression', -10, 'calm') == 0.
    reloaded = HeadlessBrain()
    assert reloaded.load_brain(brain.export_brain())
    assert reloaded.enhanced_neurogenesis.functional_neurons['aggression'].resting_level == \
        fighting.AGGRESSION_SCAR_CEILING
    brain.state['anxiety'] = 50.
    for _ in range(30):                        # nobody about: it settles at its mark
        brain.perceive('squid_in_view', 0.)
        brain.perceive('squid_proximity', 0.)
        brain.propagate()
    assert brain.state['aggression'] == pytest.approx(fighting.AGGRESSION_SCAR_CEILING, abs=1.)


def test_consequences_are_applied_and_reported():
    squid = SimpleNamespace(health=50., happiness=50., anxiety=50., satisfaction=50.)
    applied = fighting.apply_consequences(squid, False)
    assert applied == {k: v for k, v in fighting.CONSEQUENCES[False].items()}
    assert squid.health == 42.


@pytest.mark.parametrize('history, approaches', [([-25.] * 6, False), ([20.] * 6, True)])
def test_two_squid_born_alike_diverge_with_their_lives(history, approaches):
    brain = HeadlessBrain()
    brain.personality = 'adventurous'
    brain.perceive('squid_in_view', 100.)
    brain.propagate()
    for valence in history:
        learn_from_encounter(brain, valence, 'bad' if valence < 0 else 'good', 'Manuel')
    went = False
    for _ in range(10):                           # then it meets a stranger
        brain.perceive('squid_in_view', 100.)
        brain.propagate()
        went = went or wants('act_play', brain.state['act_play'])
    assert went is approaches
    events = [e for e in brain.ledger._recent if e.mechanism == 'encounter']
    assert events and all(e.detail['peer'] == 'Manuel' for e in events)


def test_a_mild_encounter_teaches_nothing():
    brain = HeadlessBrain()
    brain.perceive('squid_in_view', 100.)
    brain.propagate()
    before = dict(brain.weights)
    assert learn_from_encounter(brain, 1.0, 'quiet') == []
    assert brain.weights == before


def test_the_visitor_files_a_fight_with_everything_behind_it():
    from plugins.multiplayer.encounter import FIGHT_MEMORY_PREFIX, remember_fight
    from src.memory_manager import MemoryManager
    memory = MemoryManager()
    memory.save_memory = lambda *args: None
    record = fighting.resolve_fight({'role': 'attacker', 'ability': 90., 'commitment': 80.},
                                    {'role': 'defender', 'ability': 70.}, rng=lambda: 0.)
    record.update(fight_id='f1', opponent='Manuel', why={'aggression': 80.},
                  consequences={'health': -3.})
    assert remember_fight(memory, record)
    (filed,) = [m for m in memory.long_term_memory
                if m['key'] == FIGHT_MEMORY_PREFIX + 'f1']
    value = filed['value']
    assert value['outcome'] == 'won' and value['detail']['started_it']
    assert value['detail']['why_started'] == {'aggression': 80.}
    assert value['summary'].startswith('Won a fight it started (aggression 80): ability 90')
