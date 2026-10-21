"""A hatchling inherits half its weights from each parent (src/inheritance.py).

The gamete is half of a brain's synapses between the neurons every newborn has
- nothing grown; whatever arrives from a peer is reduced to exactly that; at
hatch both halves overlay the newborn's wiring, a few mutated, each recorded
with the parent it came from. The egg keeps one gamete per parent, once, only
for its own mating, until it hatches.
"""
import json
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest                                                        # noqa: E402

from src import inheritance                                          # noqa: E402
from src.brain_constants import newborn_neurons                      # noqa: E402
from src.lifecycle import Lifecycle                                  # noqa: E402
from src.portable_brain import HeadlessBrain                         # noqa: E402

INNATE = set(newborn_neurons())


def brain():
    return HeadlessBrain()


def innate_edges(weights):
    return [e for e in weights if e[0] in INNATE and e[1] in INNATE]


def test_a_gamete_is_half_the_innate_synapses_and_nothing_grown():
    parent = brain()
    parent.weights[('hunger', 'grown_neuron')] = .7            # grown: never inherited
    genes = inheritance.gamete(parent.weights, random.Random(1))
    edges = innate_edges(parent.weights)
    assert len(genes) == len(edges) // 2
    assert all(k.split('->')[0] in INNATE and k.split('->')[1] in INNATE for k in genes)
    assert 'hunger->grown_neuron' not in genes
    for key, weight in genes.items():
        assert parent.weights[tuple(key.split('->'))] == pytest.approx(weight, abs=1e-4)
    # A different half each time.
    assert genes != inheritance.gamete(parent.weights, random.Random(2))


@pytest.mark.parametrize('sent, kept', [
    ('not a dict', {}),
    ({'hunger->happiness': 2.5}, {'hunger->happiness': 1.0}),        # clamped
    ({'hunger->happiness': -7}, {'hunger->happiness': -1.0}),
    ({'hunger->hunger': .3}, {}),                                    # self-loop
    ({'hunger->grown_neuron': .3}, {}),                              # not innate
    ({'hunger': .3, 'a->b->c': .3}, {}),                             # malformed
    ({'hunger->happiness': True}, {}),                               # not a weight
    ({'hunger->happiness': '0.5'}, {}),
    ({'hunger->happiness': float('nan')}, {}),                       # never +1
    ({'hunger->happiness': float('inf')}, {}),
])
def test_whatever_arrives_is_reduced_to_what_a_gamete_may_be(sent, kept):
    assert inheritance.clean_gamete(sent) == kept


def test_a_nan_from_the_wire_is_dropped():
    sent = json.loads('{"hunger->happiness": NaN, "hunger->satisfaction": 0.25}')
    assert inheritance.clean_gamete(sent) == {'hunger->satisfaction': .25}


def test_no_more_than_max_genes_entries_are_even_looked_at():
    flood = {f'junk{i}->x': .1 for i in range(inheritance.MAX_GENES)}
    flood['hunger->happiness'] = .5                 # past the limit: never read
    assert inheritance.clean_gamete(flood) == {}
    names = sorted(INNATE)
    every = {f'{a}->{b}': .1 for a in names for b in names if a != b}
    assert len(inheritance.clean_gamete(every)) == min(len(every), inheritance.MAX_GENES)


def test_a_hatchling_overlays_both_halves_with_provenance():
    mother, father, child = brain(), brain(), brain()
    for edge in innate_edges(mother.weights):
        mother.weights[edge] = .9
        father.weights[edge] = -.9
    genes = {'Ma': inheritance.gamete(mother.weights, random.Random(3)),
             'Pa': inheritance.gamete(father.weights, random.Random(4))}
    records = inheritance.inherit(child, genes, random.Random(5))
    assert records and {r['parent'] for r in records} == {'Ma', 'Pa'}
    for record in records:
        offered = [genes[p][f'{record["synapse"][0]}->{record["synapse"][1]}']
                   for p in genes if f'{record["synapse"][0]}->{record["synapse"][1]}' in genes[p]]
        assert child.weights[record['synapse']] == pytest.approx(record['weight'])
        if not record['mutated']:
            assert record['weight'] in [round(w, 4) for w in offered]
        else:
            assert min(abs(record['weight'] - w) for w in offered) <= inheritance.MUTATION_SIZE + 1e-9
        assert -1. <= record['weight'] <= 1.
        events = child.ledger.weight_history(record['synapse'])
        assert events[-1].mechanism == 'inheritance'
        assert events[-1].detail['parent'] == record['parent']
    share = sum(r['mutated'] for r in records) / len(records)
    assert 0. < share < .3                                         # about a tenth


def test_a_synapse_to_a_neuron_the_newborn_lacks_is_not_inherited():
    child = brain()
    child.neuron_positions.pop('curiosity', None)
    records = inheritance.inherit(child, {'Ma': {'curiosity->happiness': .5,
                                                 'hunger->happiness': .5}}, random.Random(0))
    assert [r['synapse'] for r in records] == [('hunger', 'happiness')]


def test_the_egg_keeps_one_gamete_per_parent_once_and_only_its_own():
    life = Lifecycle()
    assert life.record_reproduction('mating-1', 'mate-uuid', 'Pa', 10., 20.)
    assert not life.add_genes('mating-2', 'Pa', {'hunger->happiness': .5})   # not its egg
    assert life.add_genes('mating-1', 'Ma', {'hunger->happiness': .5})
    assert not life.add_genes('mating-1', 'Ma', {'hunger->happiness': -.5})  # once
    assert not life.add_genes('mating-1', 'Pa', {'not->innate': .5})         # nothing left
    assert life.add_genes('mating-1', 'Pa', {'hunger->satisfaction': -.25})
    restored = Lifecycle.from_dict(json.loads(json.dumps(life.to_dict())))
    assert restored.egg_genes == {'Ma': {'hunger->happiness': .5},
                                  'Pa': {'hunger->satisfaction': -.25}}
    assert restored.die('starved') and restored.begin_hatching()
    assert not restored.add_genes('mating-1', 'Other', {'hunger->happiness': .5})


def test_a_tampered_save_keeps_at_most_two_clean_parents():
    life = Lifecycle()
    life.record_reproduction('mating-1', 'mate-uuid', 'Pa')
    data = life.to_dict()
    data['egg']['genes'] = {'A': {'hunger->happiness': 9}, 'B': {'x->y': 1}, 'C': {}}
    restored = Lifecycle.from_dict(data)
    assert len(restored.egg_genes) <= 2
    assert restored.egg_genes['A'] == {'hunger->happiness': 1.0}


def test_the_host_keeps_a_gamete_only_from_its_mate_on_that_visit():
    from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
    from plugins.multiplayer.remote_protocol import Gamete
    import logging
    plugin = MultiplayerPlugin()
    plugin.logger = logging.getLogger('inheritance-test')
    life = Lifecycle()
    life.record_reproduction('visit-1-mate', 'mate-uuid', 'Mate')
    kept = []
    plugin.tamagotchi_logic = SimpleNamespace(
        squid=SimpleNamespace(lifecycle=life),
        add_mate_genes=lambda m, n, g: kept.append((m, n)) or life.add_genes(m, n, g))
    mate = SimpleNamespace(visit_id='visit-1', uuid='mate-uuid',
                           identity=SimpleNamespace(name='Mate'))
    other = SimpleNamespace(visit_id='visit-2', uuid='other-uuid',
                            identity=SimpleNamespace(name='Other'))
    plugin.host_body = SimpleNamespace(visitors={'mate-uuid': mate, 'other-uuid': other})

    def send(visit_id, mating_id='visit-1-mate'):
        return plugin.handle_gamete(message={'payload': Gamete(
            visit_id, mating_id, {'hunger->happiness': .5}).to_payload()})
    assert not send('visit-2')                     # the other visitor
    assert not send('visit-1', 'visit-9-mate')     # another mating
    assert send('visit-1')
    assert not send('visit-1')                     # once
    assert kept[0] == ('visit-1-mate', 'Mate') and 'Mate' in life.egg_genes
