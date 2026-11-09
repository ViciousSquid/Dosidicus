#!/usr/bin/env python3
"""
save_special_squid.py - preserve the run-9 supernova.

Transformer seed 222 (CI run 9) is the only run of any condition that
ever ate during the frozen evaluations: 463 foods on 880 approaches in
training, all five held-out delayed-consequence trials (latency 2
ticks), 18 foods during the stress-adaptation phase, and 131 foods in
frozen retention. This script re-trains that exact (mode, seed, world)
combination through the real trainer - everything is seeded, so the
re-run reproduces run 9's training trajectory bit for bit - and saves
the organism as portable artifacts:

  brain_222.json               the grown network, standard game format
  predictive_cortex_222.json   the transformer's weights (state dict)
  cortex_report_222.json       the cortex's telemetry at save time
  metadata.json                provenance, the run-9 record it
                               reproduces, and the verification

The brain and weights are snapshotted immediately after training,
BEFORE anything else runs. Artifact validation (which constructs a
fresh simulation and so perturbs engine state) and the verification
evaluations run afterwards, so the deterministic evaluations replay
run 9's tape exactly.

What can and cannot verify, honestly:

  strict fields      the training record, object permanence and the
                     delayed-consequence evaluation are deterministic
                     replays of run 9; they must match bit for bit.
  stochastic tape    the adaptation and retention evaluations roll
                     chance (5% startles, 6% food spawns) on a random
                     tape that depends on process history, so a fresh
                     process cannot replay run 9's exact rolls; those
                     fields are reported but not counted.

Usage:
    python experiments/save_special_squid.py --full
    python experiments/save_special_squid.py --quick --output /tmp/smoke
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from predictive_cognition_experiments import (  # noqa: E402
    AMBIENT_STARTLE_CHANCE, CONTINGENCY_INTERVAL, CONTINGENCY_START,
    FOOD_DELAY, NEAR_SIGHT_OFFSET, eval_adaptation,
    eval_delayed_consequence, eval_object_permanence, eval_retention,
    make_sim, quiet, train_condition)

MODE = 'transformer'
SEED = 222
TRAIN_TICKS = 24000
QUICK_TICKS = 1500

# Where CI run 9's published record lives (committed on this branch).
RUN9_RESULTS = Path(__file__).resolve().parent.parent / \
    'ci-logs/9/results/full_results.json'
RUN9_PUBLISH = '5e4cd2f0'
RUN9_TRIGGER = '38be60ba'

# Field-by-field verification against the run-9 record:
# (path, tolerance, kind). Tolerance 0 means exact equality.
# 'strict' fields must match: they are deterministic replays.
# 'stochastic' fields depend on chance rolls whose random tape is
# process-history-dependent: reported, never counted.
COMPARISONS = [
    (('train', 'food_eaten'), 0, 'strict'),
    (('train', 'food_approaches'), 0, 'strict'),
    (('train', 'startles'), 0, 'strict'),
    (('train', 'escaped_startles'), 0, 'strict'),
    (('train', 'unavoided_startle_ticks'), 0, 'strict'),
    (('train', 'neurons_created'), 0, 'strict'),
    (('train', 'hebbian_updates'), 0, 'strict'),
    (('train', 'predictive', 'train_steps'), 0, 'strict'),
    (('train', 'predictive', 'sleep_train_steps'), 0, 'strict'),
    (('train', 'predictive', 'loss_ema'), 1e-9, 'strict'),
    (('train', 'predictive', 'delta_mae'), 1e-9, 'strict'),
    (('train', 'predictive', 'action_top1'), 1e-9, 'strict'),
    (('train', 'predictive', 'uncertainty'), 1e-9, 'strict'),
    (('train', 'predictive', 'brain_effect',
      'synapses_from_predictions'), 0, 'strict'),
    (('train', 'predictive', 'brain_effect',
      'total_abs_weight_from_predictions'), 1e-4, 'strict'),
    (('object_permanence', 'mean_alignment'), 1e-6, 'strict'),
    (('object_permanence', 'coverage'), 1e-6, 'strict'),
    (('object_permanence', 'refeed_ticks'), 0, 'strict'),
    (('delayed_consequence', 'mean_baseline_pred_food_ahead'), 1e-6, 'strict'),
    (('delayed_consequence', 'mean_anticipation_early'), 1e-6, 'strict'),
    (('delayed_consequence', 'mean_anticipation_late'), 1e-6, 'strict'),
    (('delayed_consequence', 'mean_rise_early'), 1e-6, 'strict'),
    (('delayed_consequence', 'mean_eat_latency'), 0, 'strict'),
    (('delayed_consequence', 'eat_rate'), 0, 'strict'),
    (('adaptation', 'startles'), 0, 'stochastic'),
    (('adaptation', 'escaped_startles'), 0, 'stochastic'),
    (('adaptation', 'escape_ratio'), 1e-9, 'stochastic'),
    (('adaptation', 'peak_anxiety_rise'), 1e-6, 'stochastic'),
    (('adaptation', 'final_anxiety'), 0, 'stochastic'),
    (('adaptation', 'food_eaten'), 0, 'stochastic'),
    (('retention', 'food_eaten'), 0, 'stochastic'),
    (('retention', 'food_approaches'), 0, 'stochastic'),
]


def _dig(record, path):
    node = record
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None, False
        node = node[key]
    return node, True


def load_run9_record():
    try:
        with open(RUN9_RESULTS) as f:
            data = json.load(f)
        return data['runs']['transformer']['222'], True
    except (OSError, KeyError, ValueError) as exc:
        print(f"run-9 reference unavailable ({exc}); "
              f"verification will record the fresh values only")
        return None, False


def squid_snapshot(sim):
    squid = sim.squid
    fields = ('x', 'y', 'hunger', 'happiness', 'cleanliness',
              'sleepiness', 'satisfaction', 'anxiety', 'curiosity')
    return {name: round(float(getattr(squid, name, 0.0)), 4)
            for name in fields}


def _param_checksum(model) -> float:
    return float(sum(float(np.asarray(v, dtype=np.float64).sum())
                     for v in model.params.values()))


def validate_artifacts(outdir, saved_checksum):
    """Reload the saved weights into a fresh cortex and confirm the
    artifacts parse: a copy you cannot load is not a copy. Runs AFTER
    the verification evaluations (constructing a fresh simulation
    perturbs engine state, and nothing may sit between training and
    the deterministic evaluations)."""
    checks = {}
    with open(outdir / 'brain_222.json') as f:
        brain_data = json.load(f)
    checks['brain_json_parses'] = True
    checks['brain_top_level_keys'] = sorted(brain_data.keys())
    neurons = brain_data.get('neurons')
    if isinstance(neurons, dict):
        checks['brain_neuron_count'] = len(neurons)
    weights_path = str(outdir / 'predictive_cortex_222.json')
    fresh = make_sim(MODE, SEED)
    ok = fresh.predictive.load_weights(weights_path)
    checks['weights_reload_ok'] = bool(ok)
    if ok:
        after = _param_checksum(fresh.predictive._model)
        checks['weights_checksum_saved'] = round(saved_checksum, 6)
        checks['weights_checksum_reloaded'] = round(after, 6)
        checks['weights_round_trip_exact'] = \
            abs(saved_checksum - after) < 1e-6
        checks['weights_train_steps'] = fresh.predictive._model.train_steps
    return checks


def verify_against_run9(record, reference):
    rows = []
    for path, tol, kind in COMPARISONS:
        expected, ok_e = _dig(reference, path)
        actual, ok_a = _dig(record, path)
        if not (ok_e and ok_a):
            rows.append({'field': '.'.join(path), 'kind': kind,
                         'expected': expected, 'actual': actual,
                         'status': 'missing'})
            continue
        if expected is None and actual is None:
            matched = True
        elif isinstance(expected, (int, float)) and \
                isinstance(actual, (int, float)):
            matched = abs(expected - actual) <= max(tol, 1e-12)
        else:
            matched = expected == actual
        if kind == 'stochastic':
            status = 'stochastic tape (not counted)'
        else:
            status = 'match' if matched else 'MISMATCH'
        rows.append({'field': '.'.join(path), 'kind': kind,
                     'expected': expected, 'actual': actual,
                     'status': status})
    n_match = sum(1 for r in rows if r['status'] == 'match')
    n_bad = sum(1 for r in rows if r['status'] == 'MISMATCH')
    n_missing = sum(1 for r in rows if r['status'] == 'missing')
    n_stoch = sum(1 for r in rows if r['kind'] == 'stochastic')
    return {'rows': rows, 'matches': n_match, 'mismatches': n_bad,
            'missing': n_missing, 'stochastic_reported': n_stoch}


def print_verification(verification):
    print("\n## Squid 222 verification against run 9\n")
    print("| field | kind | run 9 | this run | status |")
    print("|---|---|---|---|---|")
    for r in verification['rows']:
        e = r['expected']
        a = r['actual']

        def fmt(v):
            return ('-' if v is None else
                    f"{v:.6g}" if isinstance(v, float) else str(v))
        print(f"| {r['field']} | {r['kind']} | {fmt(e)} | {fmt(a)} "
              f"| {r['status']} |")
    print(f"\n{verification['matches']} strict match, "
          f"{verification['mismatches']} strict mismatch, "
          f"{verification['missing']} missing; "
          f"{verification['stochastic_reported']} stochastic-tape "
          f"fields reported uncounted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quick', action='store_true',
                       help='Smoke run: short life, wiring validated, '
                            'artifacts written to the output dir only')
    group.add_argument('--full', action='store_true',
                       help='The real thing: 24,000 ticks, run-9 '
                            'verification, artifacts to experiments/results')
    parser.add_argument('--output', type=str, default=None,
                        help='Output directory (default: '
                            'experiments/results/squid_222)')
    args = parser.parse_args()

    quick = args.quick or not args.full
    ticks = QUICK_TICKS if quick else TRAIN_TICKS
    outdir = Path(args.output) if args.output else (
        Path(__file__).resolve().parent / 'results/squid_222')
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Preserving squid 222: mode={MODE} seed={SEED} "
          f"ticks={ticks} output={outdir}")
    sim, train = train_condition(MODE, SEED, ticks)
    print(f"trained: {train['food_eaten']} eaten, "
          f"{train['food_approaches']} approaches, "
          f"{train['hebbian_updates']} hebbian updates, "
          f"{train['ticks_per_second']} t/s")

    # Snapshot the organism IMMEDIATELY after training: nothing may run
    # between training and the deterministic evaluations, and the
    # adaptation evaluation (which trains live) must not modify the copy.
    squid_state = squid_snapshot(sim)
    brain_path = str(outdir / 'brain_222.json')
    weights_path = str(outdir / 'predictive_cortex_222.json')
    report_path = str(outdir / 'cortex_report_222.json')
    ok_brain = sim.brain.save_brain(brain_path)
    ok_weights = sim.predictive.save_weights(weights_path)
    ok_report = sim.predictive.save_report(report_path)
    saved_checksum = _param_checksum(sim.predictive._model)
    print(f"saved: brain={ok_brain} weights={ok_weights} "
          f"report={ok_report}")

    # Re-run the held-out evaluations to verify the copy. The training
    # record, object permanence and delayed consequence are
    # deterministic replays of run 9; the adaptation and retention
    # evaluations roll chance on a process-history-dependent tape.
    record = {'train': train}
    with quiet():
        record['object_permanence'] = eval_object_permanence(sim)
        record['delayed_consequence'] = eval_delayed_consequence(sim)
        record['adaptation'] = eval_adaptation(sim)
        record['retention'] = eval_retention(sim)
    print(f"held-out: op={record['object_permanence']['mean_alignment']}, "
          f"dc eat_rate={record['delayed_consequence']['eat_rate']}, "
          f"adapt food={record['adaptation']['food_eaten']}, "
          f"retention={record['retention']['food_eaten']}")

    # Only now may anything else touch engine state.
    artifact_checks = validate_artifacts(outdir, saved_checksum)
    print("artifact validation:", json.dumps(artifact_checks, indent=1))

    verification = None
    if not quick:
        reference, ref_ok = load_run9_record()
        if ref_ok:
            verification = verify_against_run9(record, reference)
            print_verification(verification)

    meta = {
        'what': 'the run-9 supernova: transformer seed 222, preserved',
        'mode': MODE,
        'seed': SEED,
        'train_ticks': ticks,
        'quick': quick,
        'provenance': {
            'run': 9,
            'run9_trigger_commit': RUN9_TRIGGER,
            'run9_publish_commit': RUN9_PUBLISH,
            'run9_reference': str(RUN9_RESULTS),
            'rebuilt_at_commit': os.environ.get('GITHUB_SHA'),
            'ci_run_number': os.environ.get('GITHUB_RUN_NUMBER'),
        },
        'world': {
            'contingency_start': CONTINGENCY_START,
            'contingency_interval': CONTINGENCY_INTERVAL,
            'food_delay': FOOD_DELAY,
            'near_sight_offset': NEAR_SIGHT_OFFSET,
            'ambient_startle_chance': AMBIENT_STARTLE_CHANCE,
        },
        'squid_final_state_after_training': squid_state,
        'artifacts': {
            'brain_222.json': 'the grown network, standard game '
                              '(Designer/custom_brain_loader) format; '
                              'prediction sensors ride along as inert '
                              'input neurons',
            'predictive_cortex_222.json': 'the transformer state dict; '
                                          'restore with '
                                          'PredictiveCortex.load_weights()',
            'cortex_report_222.json': 'cortex telemetry at save time',
            'note': 'the experience buffer is not preserved; a restored '
                    'cortex starts predicting again after two ticks of '
                    'fresh experience',
        },
        'verification_note': 'strict fields (training record, object '
                             'permanence, delayed consequence) are '
                             'deterministic replays of run 9 and must '
                             'match; stochastic-tape fields '
                             '(adaptation, retention) roll chance on a '
                             'process-history-dependent tape and are '
                             'reported, not counted',
        'artifact_checks': artifact_checks,
        'verification': verification,
    }
    with open(outdir / 'metadata.json', 'w') as f:
        json.dump(meta, f, indent=2,
                  default=lambda o: float(o) if isinstance(
                      o, (np.floating, np.integer)) else str(o))
    print(f"metadata written to {outdir / 'metadata.json'}")
    if verification:
        verdict = ('REPRODUCED' if verification['mismatches'] == 0
                   and verification['missing'] == 0 else 'DIVERGED')
        print(f"\nVerdict: {verdict} "
              f"({verification['matches']} strict fields match, "
              f"{verification['mismatches']} strict mismatch, "
              f"{verification['missing']} missing; "
              f"{verification['stochastic_reported']} stochastic-tape "
              f"fields reported uncounted)")


if __name__ == '__main__':
    main()
