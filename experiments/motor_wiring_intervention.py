#!/usr/bin/env python3
"""Run 22: paired, seed-matched motor-birth-wiring counterfactual.

The same real headless brain runs without artificial actions, feeds or
policy overrides. The *only* intervention excludes incidental birth-context
edges INTO motor neurons; explicitly diagnosed remedy edges remain enabled.
Run default engine and opt-in intervention in each predictive-cortex mode.
"""
import argparse
import contextlib
import io
import json
from collections import deque
from pathlib import Path

from growth_experiment import make_growth_sim, sample_growth
from predictive_cognition_experiments import MODES, contingency_events

def condition(mode, seed, ticks, context_motor_autowiring):
    sim = make_growth_sim(
        mode, seed, learning=True,
        context_motor_autowiring=context_motor_autowiring)
    sim.event_queue = deque(contingency_events(0, ticks))
    sim.food_side = 'east'
    records = []
    with contextlib.redirect_stdout(io.StringIO()):
        for tick in range(1, ticks + 1):
            sim.tick += 1
            sim._process_events()
            sim._simulation_step()
            if tick % 100 == 0 or tick == ticks:
                s = sample_growth(sim, tick, 0)
                records.append({
                    'tick': tick,
                    'neurons': s['neurons'],
                    'food_eaten': s['food_eaten'],
                    'food_approaches': s['food_approaches'],
                    'food_seen_ticks': s['food_seen_ticks'],
                    'food_visible': s['food_visible'],
                    'food_items': s['food_items'],
                    'actions': s['action_counts'],
                    'act_eat': s['motor_activation']['act_eat'],
                    'act_move': s['motor_activation']['act_move'],
                    'eat_positive': s['motor_synaptic_inputs']['act_eat']['positive_total'],
                    'eat_negative': s['motor_synaptic_inputs']['act_eat']['negative_total'],
                    'move_positive': s['motor_synaptic_inputs']['act_move']['positive_total'],
                    'move_negative': s['motor_synaptic_inputs']['act_move']['negative_total'],
                    'innate_motor_weights': s['innate_motor_weights'],
                    'eat_top_negative': s['motor_synaptic_inputs']['act_eat']['top_negative'],
                    'move_top_negative': s['motor_synaptic_inputs']['act_move']['top_negative'],
                })
    grown = sim.brain.enhanced_neurogenesis.functional_neurons
    innate_edges = (
        ('can_see_food', 'act_eat'), ('hunger', 'act_eat'),
        ('curiosity', 'act_move'),
    )
    innate_provenance = {}
    for edge in innate_edges:
        history = sim.brain.ledger.weight_history(edge, limit=20)
        innate_provenance[' -> '.join(edge)] = {
            'current_weight': sim.brain.weights.get(edge),
            'exists': edge in sim.brain.weights,
            'events': [{
                'old': round(float(event.old_weight), 5),
                'new': round(float(event.new_weight), 5),
                'mechanism': event.mechanism,
                'note': str(event.detail.get('note', '')),
                'purpose': str(event.detail.get('purpose', '')),
            } for event in history],
        }
    by_motor = {}
    for target in ('act_eat', 'act_move'):
        edges = [(src, weight) for (src, dst), weight in sim.brain.weights.items()
                 if dst == target and src in grown]
        by_motor[target] = {
            'grown_source_edges': len(edges),
            'grown_source_negative_edges': sum(1 for _, w in edges if w < 0),
            'grown_source_negative_weight_sum': round(
                sum(w for _, w in edges if w < 0), 4)
        }
    return {
        'mode': mode,
        'seed': seed,
        'context_motor_autowiring': context_motor_autowiring,
        'ticks': ticks,
        'final_neurons': len(sim.brain.positions),
        'grown_neurons': len(grown),
        'food_eaten': sim.stats['food_eaten'],
        'food_approaches': sim.stats['food_approaches'],
        'food_seen_ticks': sim.stats['food_seen_ticks'],
        'actions': sim.stats['actions_selected'],
        'motor_edges_from_grown': by_motor,
        'innate_provenance': innate_provenance,
        'samples': records,
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ticks', type=int, default=6000)
    p.add_argument('--seed', type=int, default=11)
    p.add_argument('--output', default='experiments/results/motor_wiring_study.json')
    args = p.parse_args()
    runs = {}
    for mode in MODES:
        runs[mode] = {}
        for enabled in (True, False):
            arm = 'historical' if enabled else 'no_incidental_motor_edges'
            print(f"[motor-study] {mode}/{arm} seed={args.seed} ticks={args.ticks}", flush=True)
            r = condition(mode, args.seed, args.ticks, enabled)
            runs[mode][arm] = r
            print(f"  earned-food={r['food_eaten']} exploring={r['actions'].get('exploring', 0)} "
                  f"idle={r['actions'].get('idle', 0)} neurons={r['final_neurons']} "
                  f"motor-neg={r['motor_edges_from_grown']}", flush=True)
    result = {
        'design': {
            'ticks': args.ticks, 'seed': args.seed, 'modes': list(MODES),
            'arm_order': ['historical', 'no_incidental_motor_edges'],
            'intervention': 'Exclude only automatic birth-context outputs to motor targets.',
            'unchanged': 'Innate synapses, explicit deficit remedy wiring, action selection, '
                         'environment, learning machinery and feeding rules.',
            'analysis_warning': 'n=1 per condition; signed inputs approximate post-step contributions.'
        },
        'runs': runs,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"[motor-study] complete; results: {out}", flush=True)

if __name__ == '__main__':
    main()
