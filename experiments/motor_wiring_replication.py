#!/usr/bin/env python3
"""Motor-wiring replication: independent seeds, paired control and intervention.

Continuation of run 22. Runs existing *unchanged* engine or opt-in birth-context
motor-edge exclusion. No artificial food, no action forcing, and original seeds
are reset before each run. Seeds 22/33/44 deliberately exclude discovery seed 11
and exceptional historical seed 222 from the confirmatory sample.
"""
import argparse
import json
import statistics
from pathlib import Path

from motor_wiring_intervention import condition
from predictive_cognition_experiments import MODES


def summarize(record):
    """Keep small files while preserving the mechanistic ledger and trajectory."""
    snapshots = [s for s in record['samples']
                 if s['tick'] in (100, 300, 500, 700, 900, 1500, 3000, 6000)]
    return {
        'mode': record['mode'],
        'seed': record['seed'],
        'context_motor_autowiring': record['context_motor_autowiring'],
        'food_eaten': record['food_eaten'],
        'food_approaches': record['food_approaches'],
        'food_seen_ticks': record['food_seen_ticks'],
        'actions': record['actions'],
        'final_neurons': record['final_neurons'],
        'grown_neurons': record['grown_neurons'],
        'motor_edges_from_grown': record['motor_edges_from_grown'],
        'innate_provenance': record['innate_provenance'],
        'sampled_trajectory': snapshots,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds', default='22,33,44')
    p.add_argument('--ticks', type=int, default=6000)
    p.add_argument('--output', default='experiments/results/motor_wiring_replication.json')
    args = p.parse_args()
    seeds = [int(x.strip()) for x in args.seeds.split(',') if x.strip()]
    if not seeds or len(set(seeds)) != len(seeds):
        p.error('seeds must be a non-empty list of unique integers')
    runs = {}
    for mode in MODES:
        runs[mode] = {}
        for seed in seeds:
            runs[mode][str(seed)] = {}
            for enabled in (True, False):
                arm = 'historical' if enabled else 'no_incidental_motor_edges'
                print(f"[motor-repl] {mode}/{arm}/seed{seed} start", flush=True)
                record = summarize(condition(mode, seed, args.ticks, enabled))
                runs[mode][str(seed)][arm] = record
                print(f"  food={record['food_eaten']} approaches={record['food_approaches']} "
                      f"explore={record['actions'].get('exploring',0)} "
                      f"idle={record['actions'].get('idle',0)}", flush=True)
    summary = {}
    for mode in MODES:
        controls = [runs[mode][str(seed)]['historical']['food_eaten'] for seed in seeds]
        interventions = [runs[mode][str(seed)]['no_incidental_motor_edges']['food_eaten']
                         for seed in seeds]
        deltas = [y - x for x, y in zip(controls, interventions)]
        summary[mode] = {
            'n': len(seeds), 'control_food': controls,
            'intervention_food': interventions, 'paired_deltas': deltas,
            'mean_control': round(statistics.mean(controls), 3),
            'mean_intervention': round(statistics.mean(interventions), 3),
            'median_delta': statistics.median(deltas),
            'seeds_helped': sum(d > 0 for d in deltas),
            'seeds_harmed': sum(d < 0 for d in deltas),
        }
    obj = {
        'design': {
            'seeds': seeds, 'ticks': args.ticks, 'modes': list(MODES),
            'excluded_from_replication': [11, 222],
            'seed_11_results': 'ci-logs/22/results/motor_wiring_study.json',
            'intervention': 'Exclude incidental newborn-to-motor context edges only',
            'caveat': 'RNG is seeded per arm; diverging motor actions can change the later '
                      'global RNG draw order, so ambient random events are not a frozen tape.',
            'no_artificial_food': True,
        },
        'summary': summary,
        'runs': runs,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')
    print('[motor-repl] aggregate:', json.dumps(summary, sort_keys=True), flush=True)
    print('[motor-repl] results:', out, flush=True)


if __name__ == '__main__':
    main()
