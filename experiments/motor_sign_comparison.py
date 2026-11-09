#!/usr/bin/env python3
"""Compare historical, negative-only, and all-off birth-context motor wiring.

Run 27: tests if negative INCIDENTAL context-to-motor synapses alone cause
behavioural collapse, while preserving beneficial positive context signals.
Controls have the same seed and identical action/learning implementation.
The production flags retain their historical defaults.
"""
import argparse
import json
import statistics
from pathlib import Path

from motor_wiring_intervention import condition
from predictive_cognition_experiments import MODES


ARMS = {
    'historical': (True, False),
    'block_negative_only': (True, True),
    'block_all_context_motor': (False, False),
}


def brief(r):
    return {
        'food_eaten': r['food_eaten'],
        'food_approaches': r['food_approaches'],
        'food_seen_ticks': r['food_seen_ticks'],
        'final_neurons': r['final_neurons'],
        'actions': r['actions'],
        'motor_edges_from_grown': r['motor_edges_from_grown'],
        'hunger_eat_present': r['innate_edge_provenance'].get(
            'hunger -> act_eat', {}).get('present'),
        'checkpoints': [{
            'tick': s['tick'], 'food': s['food_eaten'],
            'eat': s['act_eat'], 'move': s['act_move']
        } for s in r['samples'] if s['tick'] in (100, 300, 500, 900, 1500, 3000, 6000)],
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds', default='11,22,33,44')
    p.add_argument('--ticks', type=int, default=6000)
    p.add_argument('--output', default='experiments/results/motor_sign_comparison.json')
    a=p.parse_args()
    seeds=[int(x.strip()) for x in a.seeds.split(',') if x.strip()]
    if not seeds or len(seeds)!=len(set(seeds)):
        p.error('seed values must be unique non-empty integers')
    results={}
    summary={}
    for mode in MODES:
        results[mode]={}
        for seed in seeds:
            results[mode][str(seed)]={}
            for name,(auto,only_negative) in ARMS.items():
                print(f'[motor-sign] {mode}/seed{seed}/{name}',flush=True)
                r=condition(mode,seed,a.ticks,auto,
                            preserve_innate_motor_offload=False,
                            exclude_negative_context_motor_targets=only_negative)
                results[mode][str(seed)][name]=brief(r)
                print(f'  earned_food={r["food_eaten"]} '
                      f'explore={r["actions"].get("exploring",0)} '
                      f'idle={r["actions"].get("idle",0)}',flush=True)
        control=[results[mode][str(seed)]['historical']['food_eaten'] for seed in seeds]
        negative=[results[mode][str(seed)]['block_negative_only']['food_eaten'] for seed in seeds]
        alloff=[results[mode][str(seed)]['block_all_context_motor']['food_eaten'] for seed in seeds]
        summary[mode]={
            'n':len(seeds),'control':control,'negative_only':negative,'all_off':alloff,
            'negative_minus_control':[b-a for a,b in zip(control,negative)],
            'negative_minus_all_off':[b-a for a,b in zip(alloff,negative)],
            'negative_only_mean':round(statistics.mean(negative),3),
            'negative_only_helped':sum(b>a for a,b in zip(control,negative)),
            'negative_only_harmed':sum(b<a for a,b in zip(control,negative)),
        }
    payload={
        'design':{
            'seeds':seeds,'ticks':a.ticks,'arms':ARMS,
            'intervention':'Skip only negative newborn birth-context outputs to action neurons',
            'explicit_remedy_and_innate_edges':'unchanged',
            'no_forced_actions_or_meals':True,
            'warning':'The global seed is reset, but random world events can diverge after policy differences.'
        },
        'summary':summary,'runs':results,
    }
    out=Path(a.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    print('[motor-sign] summary',json.dumps(summary,sort_keys=True),flush=True)
    print('[motor-sign] results',out,flush=True)


if __name__=='__main__':
    main()
