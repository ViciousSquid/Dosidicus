#!/usr/bin/env python3
"""
Predictive-cognition experiments: does a small transformer improve the
squid's memory, temporal reasoning, prediction, spatial awareness and
ability to learn from experience?

Research design (branch research/transformer-predictive-cognition):

  Three conditions, identical in every respect except the predictive
  cortex:

    off         the baseline engine, untouched (control of record)
    linear      a simple exponential-smoothing temporal predictor,
                run through the SAME interface, writing the SAME senses
                - the "is it the plumbing or the modelling?" control
    transformer 2 layers, 4 heads, 64-dim, trained on the squid's own
                perceptual experience only

  Each condition x seed pair is trained on the same delayed-reward
  contingency (a startle is followed 16 ticks later by food
  appearing within sight, just east of the squid), then evaluated on
  HELD-OUT scenarios the transformer never
  trained on:

    object permanence    food seen, then the squid is teleported away;
                         does the prediction still point at it?
    delayed consequence  does anything anticipate the food that follows
                         a startle (pred_food_ahead rising BEFORE the
                         food appears)?
    adaptation           a stress phase with learning live; how well does
                         each condition cope?
    retention           frozen afterwards: does learned feeding
                         behaviour survive?
    overhead             wall-clock cost per condition.

  Scoring of predictions happens OUTSIDE the squid: the analysis reads
  the cortex's telemetry directly. The squid itself only ever receives
  unsigned 0-100 sensor values through the standard sensor interface,
  and can only learn to trust them through its normal plasticity.

Usage:
    python experiments/predictive_cognition_experiments.py --quick
    python experiments/predictive_cognition_experiments.py --full
"""

import argparse
import io
import json
import math
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.portable_brain import TrainingConfig  # noqa: E402
from headless.headless_trainer import HeadlessSimulation  # noqa: E402

MODES = ('off', 'linear', 'transformer')
FULL_SEEDS = [11, 22, 33, 44, 55, 66, 77, 88, 99, 111, 222, 333]
QUICK_SEEDS = [11, 22]

# The training contingency: a startle, then food 16 ticks later.
# Run-6 post-mortem: startles every 150 ticks pinned anxiety at 100 (no
# behavioural dynamic range), and food at a fixed far spot (0.8, 0.5)
# was almost never inside the 0.32 sight radius, so the contingency the
# experiment trains on barely existed in the squid's own percept
# stream. This world fixes both confounds.
CONTINGENCY_START = 150
CONTINGENCY_INTERVAL = 700      # spaced: anxiety decays between events
FOOD_DELAY = 16                # a longer horizon to anticipate
NEAR_SIGHT_OFFSET = 0.2        # food lands inside the 0.32 sight radius
AMBIENT_STARTLE_CHANCE = 0.0   # run-8 fix: stress only from the contingency


@contextmanager
def quiet():
    """Swallow the trainer's chatter; we keep the returned stats."""
    real = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = real


class ExperimentSimulation(HeadlessSimulation):
    """The real trainer, plus one scripted event type: food placement.

    Placing food is an environmental act, not a reward: the squid still
    has to see it, swim to it and choose to eat it. No pending causal
    outcomes are discarded - the squid keeps whatever credit it earned.
    """

    def _execute_event(self, event):
        if event.get('type') == 'place_food':
            if event.get('near_squid'):
                self.food_items.append(self._nearby_food_spot())
            else:
                self.food_items.append({'x': float(event.get('x', 0.5)),
                                        'y': float(event.get('y', 0.5))})
            return
        super()._execute_event(event)

    def _nearby_food_spot(self):
        """A deterministic food spot INSIDE the squid's sight radius
        (run-6 fix: food at a fixed far spot was almost never
        perceivable). Prefers east of the squid, west near the east
        wall; never outside the tank."""
        x, y = float(self.squid.x), float(self.squid.y)
        if x + NEAR_SIGHT_OFFSET <= 1.0:
            fx = x + NEAR_SIGHT_OFFSET
        else:
            fx = x - NEAR_SIGHT_OFFSET
        return {'x': fx, 'y': min(1.0, max(0.0, y))}


def make_sim(mode, seed, learning=True, **overrides):
    # Run-6 post-mortem: 374 gradient steps left the transformer's
    # object-permanence signal unstable across seeds. Halve the train
    # interval on top of the doubled tick budget (~1500 steps).
    # Run-8 post-mortem: the ambient random startle chance (0.005/tick)
    # fired ~120 startles per 24k ticks and kept anxiety pinned at 100
    # in every condition. Training silences it: stress arrives only
    # through the spaced contingency, so anxiety can recover.
    config = TrainingConfig(learning_enabled=learning, seed=seed,
                            predictive_mode=mode, predictive_seed=seed,
                            predictive_train_interval=32,
                            startle_chance=AMBIENT_STARTLE_CHANCE)
    for key, value in overrides.items():
        setattr(config, key, value)
    return ExperimentSimulation(config)


def contingency_events(from_tick, to_tick):
    events = []
    t = CONTINGENCY_START
    while t + FOOD_DELAY < to_tick:
        if t >= from_tick:
            events.append({'tick': t, 'type': 'startle'})
            events.append({'tick': t + FOOD_DELAY, 'type': 'place_food',
                           'near_squid': True})
        t += CONTINGENCY_INTERVAL
    return events


def step_n(sim, n, events=None):
    """Advance n ticks through the real engine loop (quietly)."""
    if events:
        sim.event_queue.extend(events)
    for _ in range(n):
        sim.tick += 1
        sim._process_events()
        sim._simulation_step()
    sim.stats['ticks_completed'] = sim.tick + 1


def train_condition(mode, seed, ticks, quick=False):
    """Phase 1: the delayed-reward contingency, learning live."""
    sim = make_sim(mode, seed, learning=True)
    sim.event_queue = contingency_events(0, ticks)
    sim.stats['target_ticks'] = ticks
    with quiet():
        stats = sim.run(ticks=ticks, progress_interval=0)
    predictive = stats.get('predictive') or {}
    return sim, {
        'ticks': ticks,
        'food_eaten': stats['food_eaten'],
        'food_approaches': stats['food_approaches'],
        'startles': stats['startles'],
        'escaped_startles': stats['escaped_startles'],
        'unavoided_startle_ticks': stats['unavoided_startle_ticks'],
        'neurons_created': stats['neurons_created'],
        'hebbian_updates': stats['hebbian_updates'],
        'ticks_per_second': round(stats.get('ticks_per_second', 0.0), 1),
        'predictive': {
            'mode': predictive.get('mode'),
            'train_steps': predictive.get('train_steps', 0),
            'sleep_train_steps': predictive.get('sleep_train_steps', 0),
            'loss_ema': predictive.get('loss_ema'),
            'mae': predictive.get('mae'),
            'delta_mae': predictive.get('delta_mae'),
            'action_top1': predictive.get('action_top1'),
            'uncertainty': predictive.get('uncertainty'),
            'inference_seconds': predictive.get('inference_seconds'),
            'train_seconds': predictive.get('train_seconds'),
            'brain_effect': predictive.get('brain_effect'),
        },
    }


# ---------------------------------------------------------------------------
# Held-out evaluation 1: object permanence
# ---------------------------------------------------------------------------

def eval_object_permanence(sim, show_ticks=12, blind_ticks=30,
                           refeed_limit=150):
    """Food is seen, then the squid is teleported out of sight of it.

    The squid's own percept during the blind phase is empty: can_see_food
    is 0, the food channels are 0. We score, from OUTSIDE, whether the
    prediction senses still point toward the food's true location, and
    how quickly the squid eats once it can see again.
    """
    sim.config.learning_enabled = False          # frozen evaluation
    sim.config.food_spawn_chance = 0.0           # the evaluator owns this world
    sim.config.startle_chance = 0.0
    sim.food_items.clear()
    sim.event_queue = []
    food = {'x': 0.75, 'y': 0.5}
    sim.food_items.append(dict(food))
    sim.squid.x, sim.squid.y = 0.5, 0.5

    # Phase A: see the food. If the squid eats it mid-observation,
    # replace it - the analysis, not the squid, owns this world.
    for _ in range(show_ticks):
        sim.tick += 1
        sim._simulation_step()
        if not sim.food_items:
            sim.food_items.append(dict(food))

    # Phase B: teleported away; the food is far outside the sight radius.
    sim.squid.x, sim.squid.y = 0.05, 0.05
    alignments = []
    coverages = []
    for _ in range(blind_ticks):
        sim.tick += 1
        sim._simulation_step()
        fx, fy = food['x'] - sim.squid.x, food['y'] - sim.squid.y
        norm = math.hypot(fx, fy)
        if norm < 1e-9:
            continue
        true_dir = (fx / norm, fy / norm)
        pred = sim.predictive.prediction_direction()
        if pred is None:
            continue
        px, py = pred
        pmag = math.hypot(px, py)
        coverages.append(1.0 if pmag > 5.0 else 0.0)
        if pmag < 1e-9:
            alignments.append(0.0)
            continue
        alignments.append((px / pmag) * true_dir[0] + (py / pmag) * true_dir[1])

    # Phase C: re-sighted. How long until it eats, with learning frozen?
    sim.squid.x, sim.squid.y = 0.55, 0.5
    refeed_ticks = None
    for i in range(refeed_limit):
        eaten_before = sim.stats['food_eaten']
        sim.tick += 1
        sim._simulation_step()
        if sim.stats['food_eaten'] > eaten_before:
            refeed_ticks = i + 1
            break

    return {
        'mean_alignment': (sum(alignments) / len(alignments)
                           if alignments else None),
        'coverage': (sum(coverages) / len(coverages)
                    if coverages else None),
        'refeed_ticks': refeed_ticks,
    }


# ---------------------------------------------------------------------------
# Held-out evaluation 2: delayed consequences
# ---------------------------------------------------------------------------

def eval_delayed_consequence(sim, trials=5, baseline_ticks=20):
    """A held-out schedule of the training contingency's structure:
    startle at t0, food FOOD_DELAY (16) ticks later. Does pred_food_ahead
    rise BEFORE the food exists, in an early (t0+1..t0+7) and a late
    (t0+8..t0+14) anticipation window? And is the now-visible food
    eaten, and how fast?

    Run-6 fix: this eval used to queue its startle/food events without
    ever calling _process_events(), so the trials silently ran in an
    empty world and eat rate was structurally zero.
    """
    sim.config.learning_enabled = False
    sim.config.food_spawn_chance = 0.0
    sim.config.startle_chance = 0.0
    sim.event_queue = []

    records = []
    for trial in range(trials):
        sim.food_items.clear()          # the evaluator owns this world
        sim.squid.x, sim.squid.y = 0.5, 0.5
        # baseline window: no events, nothing to anticipate
        for _ in range(baseline_ticks):
            sim.tick += 1
            sim._process_events()
            sim._simulation_step()
        base_ahead = _pred_now(sim, 'pred_food_ahead')
        # the trial: a startle, then food FOOD_DELAY ticks later,
        # placed within sight of the squid. The tick loop mirrors the
        # real engine loop: process events, then step.
        t0 = sim.tick + 1
        sim.event_queue.extend([
            {'tick': t0, 'type': 'startle'},
            {'tick': t0 + FOOD_DELAY, 'type': 'place_food',
             'near_squid': True},
        ])
        timecourse = []
        for _ in range(FOOD_DELAY):
            sim.tick += 1
            sim._process_events()
            sim._simulation_step()
            timecourse.append(_pred_now(sim, 'pred_food_ahead'))
        # An off-mode squid has no prediction senses at all, so the
        # timecourse can contain None values; _mean() treats those as
        # missing observations rather than crashing.
        anti_early = _mean(timecourse[1:8])    # ticks t0+1 .. t0+7
        anti_late = _mean(timecourse[8:15])    # ticks t0+8 .. t0+14
        # the food appears now; measure the eat latency
        eaten_at = None
        for i in range(80):
            eaten_before = sim.stats['food_eaten']
            sim.tick += 1
            sim._process_events()
            sim._simulation_step()
            if sim.stats['food_eaten'] > eaten_before:
                eaten_at = i + 1
                break
        records.append({
            'baseline_ahead': base_ahead,
            'anticipation_early': anti_early,
            'anticipation_late': anti_late,
            'eat_latency': eaten_at,
        })
    # only trials where the food was eventually eaten contribute latency
    latencies = [r['eat_latency'] for r in records if r['eat_latency']]
    rises_early, rises_late = [], []
    for r in records:
        if r['baseline_ahead'] is not None:
            if r['anticipation_early'] is not None:
                rises_early.append(r['anticipation_early']
                                   - r['baseline_ahead'])
            if r['anticipation_late'] is not None:
                rises_late.append(r['anticipation_late']
                                  - r['baseline_ahead'])
    return {
        'mean_baseline_pred_food_ahead': _mean(
            [r['baseline_ahead'] for r in records]),
        'mean_anticipation_early': _mean(
            [r['anticipation_early'] for r in records]),
        'mean_anticipation_late': _mean(
            [r['anticipation_late'] for r in records]),
        'mean_rise_early': _mean(rises_early),
        'mean_rise_late': _mean(rises_late),
        'mean_eat_latency': _mean(latencies),
        'eat_rate': len(latencies) / max(1, len(records)),
        'trials': records,
    }


def _pred_now(sim, name):
    sensors = sim.predictive.last_sensors()
    return float(sensors.get(name, 0.0)) if sensors else None


def _mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


# ---------------------------------------------------------------------------
# Held-out evaluation 3: adaptation under stress (learning live)
# ---------------------------------------------------------------------------

def eval_adaptation(sim, ticks=1500):
    """An unfamiliar harsh phase. Learning stays ON: this measures how
    well each condition copes with, and adapts to, sustained stress."""
    sim.config.learning_enabled = True
    sim.config.startle_chance = 0.05
    sim.config.food_spawn_chance = 0.02   # restored: earlier evals zeroed it
    sim.food_items.clear()
    sim.event_queue = []
    before = {k: sim.stats.get(k, 0) for k in
              ('startles', 'escaped_startles', 'unavoided_startle_ticks',
               'food_eaten', 'neurons_created')}
    anxiety_before = sim.squid.anxiety
    peak = anxiety_before
    for _ in range(ticks):
        sim.tick += 1
        sim._simulation_step()
        peak = max(peak, sim.squid.anxiety)
    sim.config.startle_chance = 0.005
    startles = sim.stats['startles'] - before['startles']
    escaped = sim.stats['escaped_startles'] - before['escaped_startles']
    return {
        'startles': startles,
        'escaped_startles': escaped,
        'escape_ratio': (escaped / startles) if startles else None,
        'peak_anxiety_rise': peak - anxiety_before,
        'final_anxiety': sim.squid.anxiety,
        'food_eaten': sim.stats['food_eaten'] - before['food_eaten'],
        'neurons_created': sim.stats['neurons_created'] - before['neurons_created'],
    }


# ---------------------------------------------------------------------------
# Held-out evaluation 4: retention of learned behaviour (frozen)
# ---------------------------------------------------------------------------

def eval_retention(sim, ticks=2500):
    """Frozen brain, ordinary world: does the feeding behaviour each
    condition learned during training survive intact?"""
    sim.config.learning_enabled = False
    sim.config.food_spawn_chance = 0.06
    sim.config.startle_chance = 0.0    # calm world: measure feeding, not stress
    sim.food_items.clear()
    sim.event_queue = []
    before = {k: sim.stats.get(k, 0) for k in
              ('food_eaten', 'food_approaches')}
    for _ in range(ticks):
        sim.tick += 1
        sim._simulation_step()
    return {
        'food_eaten': sim.stats['food_eaten'] - before['food_eaten'],
        'food_approaches': (sim.stats['food_approaches']
                            - before['food_approaches']),
    }


# ---------------------------------------------------------------------------
# The experiment
# ---------------------------------------------------------------------------

def run_experiment(seeds, train_ticks, quick=False):
    results = {'meta': {
        'modes': list(MODES),
        'seeds': list(seeds),
        'train_ticks': train_ticks,
        'contingency': {
            'start': CONTINGENCY_START,
            'interval': CONTINGENCY_INTERVAL,
            'food_delay': FOOD_DELAY,
            'food_placement': 'near_squid',
            'near_sight_offset': NEAR_SIGHT_OFFSET,
            'ambient_startle_chance': AMBIENT_STARTLE_CHANCE,
        },
        'quick': quick,
    }, 'runs': {}}
    for mode in MODES:
        results['runs'][mode] = {}
        for seed in seeds:
            sim, train = train_condition(mode, seed, train_ticks, quick)
            record = {'train': train}
            # Evaluations run the same engine loop and so produce the
            # same chatter; keep it out of the published logs.
            with quiet():
                if not quick:
                    record['object_permanence'] = eval_object_permanence(sim)
                    record['delayed_consequence'] = eval_delayed_consequence(sim)
                else:
                    record['object_permanence'] = eval_object_permanence(
                        sim, show_ticks=8, blind_ticks=15, refeed_limit=80)
                    record['delayed_consequence'] = eval_delayed_consequence(
                        sim, trials=3)
                record['adaptation'] = eval_adaptation(
                    sim, ticks=600 if quick else 1500)
                record['retention'] = eval_retention(
                    sim, ticks=800 if quick else 2500)
            results['runs'][mode][str(seed)] = record
            print(f"  {mode:12s} seed {seed}: "
                  f"trained {train['food_eaten']} eaten, "
                  f"op={record['object_permanence'].get('mean_alignment')}, "
                  f"retain={record['retention']['food_eaten']}")
    results['summary'] = summarise(results)
    return results


def summarise(results):
    """Aggregate per condition across seeds, with the honest numbers."""
    summary = {}
    for mode in MODES:
        runs = list(results['runs'].get(mode, {}).values())
        if not runs:
            continue
        def agg(path):
            values = []
            for run in runs:
                node = run
                for key in path:
                    node = node.get(key) if isinstance(node, dict) else None
                if isinstance(node, (int, float)):
                    values.append(node)
            return round(sum(values) / len(values), 4) if values else None
        summary[mode] = {
            'n': len(runs),
            'train_food_eaten': agg(('train', 'food_eaten')),
            'train_food_approaches': agg(('train', 'food_approaches')),
            'train_escape_ratio': _ratio_mean(
                runs, ('train', 'escaped_startles'), ('train', 'startles')),
            'train_neurons_created': agg(('train', 'neurons_created')),
            'ticks_per_second': agg(('train', 'ticks_per_second')),
            'op_alignment': agg(('object_permanence', 'mean_alignment')),
            'op_coverage': agg(('object_permanence', 'coverage')),
            'op_refeed_ticks': agg(('object_permanence', 'refeed_ticks')),
            'dc_rise_early': agg(('delayed_consequence', 'mean_rise_early')),
            'dc_rise_late': agg(('delayed_consequence', 'mean_rise_late')),
            'dc_anticipation_late': agg(
                ('delayed_consequence', 'mean_anticipation_late')),
            'dc_eat_latency': agg(('delayed_consequence', 'mean_eat_latency')),
            'dc_eat_rate': agg(('delayed_consequence', 'eat_rate')),
            'adapt_escape_ratio': agg(('adaptation', 'escape_ratio')),
            'adapt_peak_anxiety_rise': agg(
                ('adaptation', 'peak_anxiety_rise')),
            'adapt_food_eaten': agg(('adaptation', 'food_eaten')),
            'retention_food_eaten': agg(('retention', 'food_eaten')),
            'retention_food_approaches': agg(
                ('retention', 'food_approaches')),
            'pred_mae': {g: _mean([r['train']['predictive']['mae'].get(g)
                                   for r in runs
                                   if r['train']['predictive'].get('mae')])
                         for g in (runs[0]['train']['predictive']
                                   .get('mae') or {}).keys()},
            'pred_action_top1': agg(('train', 'predictive', 'action_top1')),
            'synapses_from_predictions': _mean([
                ((r['train']['predictive'].get('brain_effect') or {})
                 .get('synapses_from_predictions')) for r in runs]),
            'inference_seconds': agg(
                ('train', 'predictive', 'inference_seconds')),
            'train_seconds_predictive': agg(
                ('train', 'predictive', 'train_seconds')),
        }
    return summary


def _ratio_mean(runs, num_path, den_path):
    ratios = []
    for run in runs:
        num = run
        den = run
        for key in num_path:
            num = num.get(key) if isinstance(num, dict) else None
        for key in den_path:
            den = den.get(key) if isinstance(den, dict) else None
        if isinstance(num, (int, float)) and isinstance(den, (int, float)) \
                and den > 0:
            ratios.append(num / den)
    return round(sum(ratios) / len(ratios), 4) if ratios else None


def print_markdown_summary(results):
    s = results['summary']
    print("\n## Predictive-cognition experiment results\n")
    print("| metric | off | linear | transformer |")
    print("|---|---|---|---|")
    rows = [
        ('train: food eaten', 'train_food_eaten'),
        ('train: escape ratio', 'train_escape_ratio'),
        ('train: neurons created', 'train_neurons_created'),
        ('train: ticks/sec', 'ticks_per_second'),
        ('object permanence: alignment', 'op_alignment'),
        ('object permanence: coverage', 'op_coverage'),
        ('object permanence: refeed ticks', 'op_refeed_ticks'),
        ('delayed consequence: rise early (t+1..t+7)', 'dc_rise_early'),
        ('delayed consequence: rise late (t+8..t+14)', 'dc_rise_late'),
        ('delayed consequence: eat latency', 'dc_eat_latency'),
        ('delayed consequence: eat rate', 'dc_eat_rate'),
        ('adaptation: escape ratio', 'adapt_escape_ratio'),
        ('adaptation: peak anxiety rise', 'adapt_peak_anxiety_rise'),
        ('adaptation: food eaten', 'adapt_food_eaten'),
        ('retention: food eaten', 'retention_food_eaten'),
        ('prediction: action top-1', 'pred_action_top1'),
        ('synapses grown from predictions', 'synapses_from_predictions'),
    ]
    for label, key in rows:
        cells = []
        for mode in MODES:
            v = s.get(mode, {}).get(key)
            cells.append('-' if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v)))
        print(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--quick', action='store_true',
                      help='Smoke run: 2 seeds, short phases (CI)')
    mode.add_argument('--full', action='store_true',
                      help='Full run: 12 seeds x 24k ticks (the paper run)')
    parser.add_argument('--seeds', type=int, nargs='*', default=None)
    parser.add_argument('--ticks', type=int, default=None)
    parser.add_argument('--output', '-o', type=str,
                        default='experiments/results/predictive_cognition_results.json')
    args = parser.parse_args()

    if args.quick:
        seeds, ticks = QUICK_SEEDS, 1500
    else:
        seeds = args.seeds or FULL_SEEDS
        ticks = args.ticks or 24000

    print(f"Predictive-cognition experiment: {len(MODES)} modes x "
          f"{len(seeds)} seeds x {ticks} training ticks")
    results = run_experiment(seeds, ticks, quick=args.quick)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out}")

    print_markdown_summary(results)


if __name__ == '__main__':
    main()
