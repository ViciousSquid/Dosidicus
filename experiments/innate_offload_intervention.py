#!/usr/bin/env python3
"""Run 25: does innate-connection offloading explain transformer feeding failure?

Hold the earlier validated incidental motor-birth-wiring guard ON in BOTH arms.
The ONLY intervention is preserving existing innate direct motor synapses
during differentiation handoff. All 3 predictive modes are matched within
seed 11 and each simulation uses the real shared neural action engine.
"""
import argparse
import json
from pathlib import Path

from motor_wiring_intervention import condition
from predictive_cognition_experiments import MODES

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=6000)
    p.add_argument('--seed', type=int, default=11)
    p.add_argument('--output', default='experiments/results/innate_offload_study.json')
    args = p.parse_args()
    records = {}
    for mode in MODES:
        records[mode] = {}
        for guard in (False, True):
            name = 'offload_historical' if not guard else 'preserve_innate'
            print(f"[innate-study] {mode}/{name} seed {args.seed}: begin", flush=True)
            data = condition(mode, args.seed, args.ticks, False,
                             preserve_innate_motor_offload=guard)
            records[mode][name] = data
            hunger = data['innate_edge_provenance'].get('hunger -> act_eat', {})
            print(f"  earned_food={data['food_eaten']} "
                  f"exploring={data['actions'].get('exploring',0)} "
                  f"idle={data['actions'].get('idle',0)} "
                  f"hunger_link={hunger.get('final_weight')} "
                  f"neurons={data['final_neurons']}", flush=True)
    meta = {
        'design': {
            'seed': args.seed,
            'ticks': args.ticks,
            'modes': list(MODES),
            'fixed_in_both_arms': 'context_motor_autowiring=False',
            'one_intervention': 'Retain direct INNATE motor connections when differentiation offloads their drivers',
            'not_changed': 'Intentional remedy transfers, sensory inputs, motor thresholds, learning rules, hunger, food placement, action choice.',
            'no_artificial_food': True,
            'caveat': 'Single-seed causal ablation; random sequence may diverge after trajectories differ'
        },
        'runs': records,
    }
    dst=Path(args.output)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(meta, indent=2)+'\n',encoding='utf-8')
    print('[innate-study] saved',dst,flush=True)

if __name__=='__main__':
    main()
