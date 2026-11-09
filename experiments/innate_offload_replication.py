#!/usr/bin/env python3
"""Independent-seed replication of the run-25 innate motor-offload guard.

Both arms disable incidental newborn-to-motor context wiring. The sole
variable is whether innate direct motor edges survive differentiation.
The discovery seed 11 and exceptional seed 222 are excluded. Outcomes
are earned food and neural action decisions, not scripted feeding.
"""
import argparse
import json
import statistics
from pathlib import Path

from motor_wiring_intervention import condition
from predictive_cognition_experiments import MODES


def compact(r):
    link = r['innate_edge_provenance'].get('hunger -> act_eat', {})
    events = [
        {'mechanism': e['mechanism'], 'note': str(e.get('detail', {}).get('note','')),
         'old': e['old'], 'new': e['new']}
        for e in link.get('narrated_events', []) if e['mechanism'] == 'neurogenesis'
    ]
    return {
        'food_eaten': r['food_eaten'], 'food_approaches': r['food_approaches'],
        'food_seen_ticks': r['food_seen_ticks'],
        'actions': r['actions'], 'final_neurons': r['final_neurons'],
        'grown_neurons': r['grown_neurons'],
        'innate_hunger_to_eat': {'present': link.get('present'),
                                 'final_weight': link.get('final_weight'),
                                 'neurogenesis_events': events},
        'motor_edges_from_grown': r['motor_edges_from_grown'],
        'checkpoints': [
            {'tick': s['tick'], 'food': s['food_eaten'],
             'eat_activation': s['act_eat'],
             'move_activation': s['act_move'],
             'food_visible': s['food_visible'],
             'eat_negative': s['eat_negative'],
             'move_negative': s['move_negative']}
            for s in r['samples']
            if s['tick'] in (100, 300, 500, 700, 900, 1500, 3000, 6000)
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds', default='22,33,44')
    p.add_argument('--ticks', type=int, default=6000)
    p.add_argument('--output', default='experiments/results/innate_offload_replication.json')
    a = p.parse_args()
    seeds = [int(v.strip()) for v in a.seeds.split(',') if v.strip()]
    if not seeds or len(seeds) != len(set(seeds)):
        p.error('provide non-empty, unique integer seeds')
    records, aggregates = {}, {}
    for mode in MODES:
        records[mode] = {}
        for seed in seeds:
            records[mode][str(seed)] = {}
            for guard in (False, True):
                name = 'offload_historical' if not guard else 'preserve_innate'
                print(f'[innate-repl] {mode}/seed{seed}/{name}', flush=True)
                run = condition(mode, seed, a.ticks, False,
                                preserve_innate_motor_offload=guard)
                records[mode][str(seed)][name] = compact(run)
                print(f'  eaten={run["food_eaten"]}, exploring='
                      f'{run["actions"].get("exploring",0)}, '
                      f'idle={run["actions"].get("idle",0)}', flush=True)
        control = [records[mode][str(s)]['offload_historical']['food_eaten']
                   for s in seeds]
        guarded = [records[mode][str(s)]['preserve_innate']['food_eaten']
                   for s in seeds]
        deltas = [y - x for x,y in zip(control,guarded)]
        aggregates[mode] = {
            'control_food': control, 'preserved_food': guarded,
            'delta': deltas,
            'mean_delta': round(statistics.mean(deltas), 3),
            'median_delta': statistics.median(deltas),
            'helped': sum(v>0 for v in deltas),
            'harmed': sum(v<0 for v in deltas),
            'unchanged': sum(v==0 for v in deltas),
        }
    result={
        'design':{
            'seeds':seeds,'ticks':a.ticks,'discovery_seed_excluded':11,
            'special_seed_excluded':222,
            'base_guard_all_arms':'context_motor_autowiring=False',
            'isolated_intervention':'preserve_innate_motor_offload=True',
            'no_artificial_food':True,
            'caveat':'Simulation uses shared seeded random stream, not frozen environmental random tape. '
                     'Diverging actions may change later environmental draws; biological outcomes are measured, '
                     'not assumed to be unchanged between arms.'
        },
        'aggregates':aggregates, 'runs':records}
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('[innate-repl] aggregate:',json.dumps(aggregates,sort_keys=True),flush=True)
    print('[innate-repl] saved',out,flush=True)


if __name__=='__main__':
    main()
