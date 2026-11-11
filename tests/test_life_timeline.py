"""A squid's life in order (issue 30): built only from what the game records.

src/life_timeline.py puts in order what is already recorded - when each
neuron grew and why, when each synapse first formed and how, each memory,
the life-cycle record - and the save carries it as timeline.json.
"""
import inspect

from src.life_timeline import build

BORN = 1_000_000.0


def _save():
    """A squid 600 s old that learned, grew two neurons, met and fought
    another squid, mated and died."""
    return {
        'game_state': {
            'squid': {'name': 'Inky', 'personality': 'timid', 'uuid': 'u-1',
                      'tint_color': [120, 170, 255],
                      'lineage': {'parents': ['Ziggy', 'Pesto'],
                                  'inherited': [{'synapse': ['hunger', 'satisfaction'], 'parent': 'Ziggy',
                                                 'weight': -0.3, 'mutated': True}]}},
            'lifecycle': {'stage': 'dead',
                          'reproduction': {'mating_id': 'm1', 'mate_name': 'Bolt', 'at': BORN + 500},
                          'egg': {'state': 'incubating'},
                          'death': {'cause': 'starved', 'at': BORN + 600}},
        },
        'statistics': {'total_age_seconds': 600},
        'brain_state': {
            'neuron_positions': {'hunger': [0, 0], 'satisfaction': [10, 0], 'curiosity': [20, 0],
                                 'act_move': [30, 0], 'can_see_squid': [40, 0], 'aggression': [50, 0]},
            'weights_list': [['hunger', 'satisfaction', -0.3], ['curiosity', 'satisfaction', 0.2],
                             ['can_see_squid', 'act_move', 0.4], ['aggression', 'act_move', 0.1]],
            'provenance': {
                'origins': {
                    'can_see_squid': {'created_at': BORN + 200, 'deficit_summary': 'Other squid encountered!',
                                      'remedy': 'represent "I see another squid"'},
                    'aggression': {'created_at': BORN + 300,
                                   'deficit_summary': 'It went at another squid while its anxiety was high'}},
                'totals': [
                    {'edge': ['hunger', 'satisfaction'], 'counts': {'innate': 1}, 'totals': {'innate': -0.3},
                     'first_seen': BORN},
                    {'edge': ['curiosity', 'satisfaction'], 'counts': {'causal_reward': 4},
                     'totals': {'causal_reward': 0.2}, 'first_seen': BORN + 60},
                    {'edge': ['can_see_squid', 'act_move'], 'counts': {'neurogenesis': 1},
                     'totals': {'neurogenesis': 0.4}, 'first_seen': BORN + 200},
                    {'edge': ['aggression', 'act_move'], 'counts': {'hebbian': 2},
                     'totals': {'hebbian': 0.1}, 'first_seen': BORN + 100}],      # older than its neuron
                'pruned': []},
        },
        'LongTerm': [
            {'category': 'social', 'key': 'peer:abc', 'timestamp': BORN + 250,
             'value': {'valence': -12.2, 'peer_name': 'Ziggy', 'outcome': 'bad',
                       'detail': {'first_meeting': True, 'duration': 180}}},
            {'category': 'social', 'key': 'fight:f1', 'timestamp': BORN + 320,
             'value': {'summary': 'Won a fight when it was attacked: ability 105 against 99, '
                                  'so it had a 53% chance.', 'opponent': 'Ziggy', 'outcome': 'won',
                       'detail': {'started_it': False, 'chance': 0.53, 'consequences': {'health': -3}}}},
            {'category': 'belief', 'key': 'belief:fleeing:can_see_squid', 'timestamp': BORN + 150,
             'value': {'statement': 'fleeing makes squid go out of sight', 'summary': 'Came to believe it'}},
            {'category': 'belief', 'key': 'revised:fleeing:can_see_squid:3', 'timestamp': BORN + 180,
             'value': {'statement': 'fleeing makes squid go out of sight', 'changed_mind': True}},
            {'category': 'neurogenesis', 'key': 'grew_neuron_aggression', 'timestamp': BORN + 300,
             'value': 'GREW A NEW NEURON!: aggression'},
        ],
        'ShortTerm': [],
    }


def test_every_event_is_in_order_and_from_the_squids_own_records():
    life = build(_save())
    kinds = [event['kind'] for event in life['events']]
    assert kinds == ['hatched', 'association', 'belief', 'belief_dropped', 'neuron', 'encounter',
                     'neuron', 'fight', 'egg', 'death']
    assert [event['age'] for event in life['events']] == [0, 60, 150, 180, 200, 250, 300, 320, 500, 600]
    grew = [e for e in life['events'] if e['kind'] == 'neuron']
    assert grew[0]['text'] == 'Other squid encountered!'              # why, in its own record's words
    assert grew[1]['title'] == 'Grew a neuron: aggression'
    fight = next(e for e in life['events'] if e['kind'] == 'fight')
    assert fight['title'] == 'Won a fight with Ziggy' and '53% chance' in fight['text']
    assert life['events'][0]['text'].startswith('From the egg of Ziggy and Pesto')
    # A neuron's birth is one event, not two: its memory is not repeated.
    assert sum('aggression' in e['title'] for e in life['events']) == 1
    assert life['counts']['neurons_grown'] == 2 and life['counts']['neurons_at_birth'] == 4


def test_the_brain_can_be_drawn_as_it_was_at_any_moment():
    life = build(_save())
    born = {n['name']: n['born'] for n in life['neurons']}
    assert born['hunger'] is None and born['aggression'] == BORN + 300
    since = {(c['source'], c['target']): c['since'] for c in life['connections']}
    assert since[('hunger', 'satisfaction')] is None                  # born with it
    assert since[('curiosity', 'satisfaction')] == BORN + 60
    # A synapse is never older than a neuron it joins.
    assert since[('aggression', 'act_move')] == BORN + 300

    def brain_at(moment):
        neurons = {n['name'] for n in life['neurons'] if not n['born'] or n['born'] <= moment}
        edges = {(c['source'], c['target']) for c in life['connections']
                 if (not c['since'] or c['since'] <= moment)
                 and c['source'] in neurons and c['target'] in neurons}
        return neurons, edges
    assert brain_at(BORN) == ({'hunger', 'satisfaction', 'curiosity', 'act_move'},
                              {('hunger', 'satisfaction')})
    assert len(brain_at(BORN + 250)[0]) == 5 and len(brain_at(BORN + 600)[1]) == 4


def test_the_stages_of_a_life_follow_from_what_happened_in_it():
    life = build(_save())
    # Its first grown neuron was a sense for other squid, so growing neurons
    # and being among other squid began at the same moment: one stage.
    assert [era['key'] for era in life['eras']] == ['hatchling', 'learning', 'social', 'parent', 'dead']
    assert [era['age'] for era in life['eras']] == [0, 60, 200, 500, 600]
    assert all(a['to'] == b['from'] for a, b in zip(life['eras'], life['eras'][1:]))
    assert {event['era'] for event in life['events']} <= {era['key'] for era in life['eras']}
    # A squid that never met another has no chapter for it.
    alone = _save()
    alone['LongTerm'] = []
    alone['game_state']['lifecycle'] = {'stage': 'living'}
    alone['brain_state']['provenance']['origins'] = {}
    alone['brain_state']['neuron_positions'].pop('can_see_squid')
    alone['brain_state']['neuron_positions'].pop('aggression')
    assert [era['key'] for era in build(alone)['eras']] == ['hatchling', 'learning']


def test_it_never_fails_on_a_save_it_does_not_understand():
    for odd in ({}, None, {'brain_state': 'nonsense', 'LongTerm': [None, 3, {'key': 5}]},
                {'game_state': {'squid': None, 'lifecycle': []}, 'statistics': {'total_age_seconds': 'x'}}):
        life = build(odd)
        assert life['events'][0]['kind'] == 'hatched' and life['version'] == 1


def test_the_game_writes_it_and_a_hatchlings_lineage_into_every_save():
    from src.tamagotchi_logic import TamagotchiLogic
    from src.squid import Squid
    saving = inspect.getsource(TamagotchiLogic.save_game)
    assert "save_data['timeline'] = build_timeline(" in saving
    assert "'lineage': getattr(self.squid, 'lineage', None)" in saving
    assert "state.get('lineage')" in inspect.getsource(Squid)
