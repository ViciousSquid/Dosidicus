#!/usr/bin/env python3
"""
Growth-study experiment: does the brain stop growing because it is
forbidden to, or because it no longer needs to?

Research design (branch research/transformer-predictive-cognition,
docs/brain_growth.md):

  A much longer life than any previous run (240,000 ticks: 10x the
  24k of runs 6-9), with the live neuron count sampled every 250 ticks
  alongside everything the capability monitor and the neurogenesis
  engine decide along the way.

  The distinction this experiment is built to expose:

    forbidden plateau   growth stops while the permission structure
                        still allows it (type caps stress 5 / novelty
                        6 / reward 6 / connector 10, global ceiling
                        100, cooldown - none binding) and actionable
                        deficits keep being stood down.

    satisfied plateau   growth stops because the capability monitor no
                        longer finds anything worth structure, while
                        synaptic plasticity (Hebbian updates, weight
                        churn) and behaviour keep improving.

  The world changes under the squid mid-life, so that "solving new
  problems by modifying existing synapses rather than adding neurons"
  is a measurement, not an interpretation:

    phase east       0..60k     the runs-8/9 world unchanged
    phase west      60k..120k   the same contingency, mirrored
    phase fouling  120k..180k   east again, heavily fouled water: a
                                genuinely new problem (cleanliness)
    phase retention 180k..240k   clean water again: retention

  Telemetry comes from the engine's own bookkeeping (growth_log,
  stood_down, the monitor's resolved ledger) plus a per-tick drive
  reading. Nothing is inferred from outside; the squid itself only ever
  receives its ordinary senses.

Usage:
    python experiments/growth_experiment.py --quick
    python experiments/growth_experiment.py --full
"""

import argparse
import io
import json
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.portable_brain import TrainingConfig  # noqa: E402
from src.propagation import signal_of  # noqa: E402
from predictive_cognition_experiments import (  # noqa: E402
    ExperimentSimulation, MODES, NEAR_SIGHT_OFFSET, contingency_events)

GROWTH_SEEDS = [11]            # n=1 per mode: growth dynamics, not statistics
GROWTH_TICKS = 240000           # 10x the 24k of runs 6-9
QUICK_TICKS = 6000
SAMPLE_EVERY = 250
QUICK_SAMPLE_EVERY = 100
SOFT_DEADLINE_S = 40 * 60      # per (mode, seed): always publish something
PROGRESS_EVERY = 5000

# The permission structure itself, recorded in the output so the analysis
# can check which bound (if any) a plateau coincided with.
TYPE_CAPS = {'stress': 5, 'novelty': 6, 'reward': 6, 'connector': 10}
GLOBAL_CAP = 100

FOULING_POOP_CHANCE = 0.06     # the "new problem": persistent fouling


def _scaled_phases(total):
    """Four equal phases; the last boundary is exactly the run length."""
    quarter = total // 4
    specs = [
        ('east', False, 'the runs-8/9 world: food lands 0.2 east'),
        ('west', False, 'the same contingency mirrored: food lands 0.2 west'),
        ('fouling', True, 'east again, heavily fouled water: a new problem'),
        ('retention', False, 'clean water again: does the east behaviour survive?'),
    ]
    phases = []
    for i, (name, fouling, label) in enumerate(specs):
        phases.append({
            'name': name, 'from': i * quarter, 'until': (i + 1) * quarter,
            'side': 'west' if name == 'west' else 'east',
            'fouling': fouling, 'label': label,
        })
    return phases


class GrowthSimulation(ExperimentSimulation):
    """The experiment world, plus one new degree of freedom: the side the
    food lands on can flip mid-life, and the water can foul."""

    food_side = 'east'

    def _nearby_food_spot(self):
        x, y = float(self.squid.x), float(self.squid.y)
        if self.food_side == 'west':
            fx = (x - NEAR_SIGHT_OFFSET if x - NEAR_SIGHT_OFFSET >= 0.0
                  else x + NEAR_SIGHT_OFFSET)
        else:
            fx = (x + NEAR_SIGHT_OFFSET if x + NEAR_SIGHT_OFFSET <= 1.0
                  else x - NEAR_SIGHT_OFFSET)
        return {'x': fx, 'y': min(1.0, max(0.0, y))}

    def _process_events(self):
        """The stock loop scans the whole queue every tick, which is
        quadratic over 240k ticks. Contingency events are generated in
        tick order, so keep a popleft-able queue and stop early."""
        queue = self.event_queue
        if not queue:
            return
        while queue:
            event = queue[0]
            when = event.get('tick', 0)
            if when > self.tick:
                return
            queue.popleft()
            if when == self.tick:
                self._execute_event(event)


def make_growth_sim(mode, seed, learning=True, context_motor_autowiring=True):
    config = TrainingConfig(learning_enabled=learning, seed=seed,
                            predictive_mode=mode, predictive_seed=seed,
                            predictive_train_interval=32,
                            context_motor_autowiring=context_motor_autowiring,
                            startle_chance=0.0)
    return GrowthSimulation(config)


def _trunc(text, limit=64):
    text = str(text)
    return text if len(text) <= limit else text[:limit]


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return round(sum(values) / len(values), 3) if values else None



def _motor_synaptic_probe(brain, target):
    """Read-only, post-step approximation of signed inputs to one motor.

    No inference or propagation is rerun.  The source states are those
    recorded *after* this tick's update, so these contributions diagnose
    persistent inhibition, not exact same-tick propagation arithmetic.
    """
    positive, negative = [], []
    for pair, weight in brain.weights.items():
        if not isinstance(pair, tuple) or len(pair) != 2:
            continue
        source, destination = pair
        if destination != target:
            continue
        activation = brain.state.get(source)
        if not isinstance(activation, (int, float)):
            continue
        contribution = float(signal_of(source, activation)) * float(weight)
        record = (str(source), round(float(weight), 4),
                  round(contribution, 3))
        if contribution > 0.01:
            positive.append(record)
        elif contribution < -0.01:
            negative.append(record)
    positive.sort(key=lambda item: item[2], reverse=True)
    negative.sort(key=lambda item: item[2])
    return {
        'positive_total': round(sum(p[2] for p in positive), 2),
        'negative_total': round(sum(p[2] for p in negative), 2),
        'top_positive': positive[:3],
        'top_negative': negative[:3],
    }


def sample_growth(sim, tick, phase_idx):
    """One row of the live time series, read straight from the engine."""
    brain = sim.brain
    eng = brain.enhanced_neurogenesis
    fn = eng.functional_neurons
    grown_types = {'stress': 0, 'novelty': 0, 'reward': 0,
                   'connector': 0, 'other': 0}
    deepened = 0
    strength_sum = 0.0
    for neuron in fn.values():
        kind = getattr(neuron, 'neuron_type', '')
        grown_types[kind if kind in grown_types else 'other'] += 1
        mult = float(getattr(neuron, 'strength_multiplier', 1.0) or 1.0)
        strength_sum += mult
        if mult > 1.001:
            deepened += 1
    cap = brain.capability
    active = sorted(cap.active.values(), key=lambda d: -d.severity)
    squid = sim.squid
    motor_inputs = {
        name: _motor_synaptic_probe(brain, name)
        for name in ('act_eat', 'act_move')
    }
    return {
        'tick': tick,
        'phase': phase_idx,
        'neurons': len(brain.positions),
        'synapses': len(brain.weights),
        'grown': len(fn),
        'grown_types': grown_types,
        'deepened': deepened,
        'strength_sum': round(strength_sum, 2),
        'neurons_created': sim.stats['neurons_created'],
        'hebbian_updates': sim.stats['hebbian_updates'],
        'weight_updates': len(brain.weight_history),
        'actionable': [_trunc(d.key) for d in cap.actionable()[:5]],
        'active': [[d.kind, _trunc(d.key, 48), round(float(d.severity), 2),
                    int(d.observations)] for d in active[:8]],
        'active_count': len(active),
        'cooldown_s': round(eng.get_global_cooldown_remaining(), 1),
        'food_eaten': sim.stats['food_eaten'],
        'food_approaches': sim.stats['food_approaches'],
        'anxiety': round(float(squid.anxiety), 1),
        'hunger': round(float(squid.hunger), 1),
        'cleanliness': round(float(squid.cleanliness), 1),
        'satisfaction': round(float(squid.satisfaction), 1),
        'happiness': round(float(squid.happiness), 1),
        'sleeping': bool(squid.is_sleeping),
        # Read-only behavioural-collapse probe. No RNG or action policy calls:
        # reading the network after its choice cannot change any decisions.
        'food_visible': bool(squid.food_visible),
        'food_items': len(sim.food_items),
        'food_seen_ticks': sim.stats.get('food_seen_ticks', 0),
        'action_counts': dict(sim.stats.get('actions_selected') or {}),
        'motor_activation': {
            name: round(float(brain.state.get(name, 0.0)), 3)
            for name in ('act_eat', 'act_move', 'act_collapse',
                         'act_rest', 'act_flee')
        },
        'motor_synaptic_inputs': motor_inputs,
        'innate_motor_weights': {
            'food_eat': round(float(brain.weights.get(
                ('can_see_food', 'act_eat'), 0.0)), 4),
            'hunger_eat': round(float(brain.weights.get(
                ('hunger', 'act_eat'), 0.0)), 4),
            'curiosity_move': round(float(brain.weights.get(
                ('curiosity', 'act_move'), 0.0)), 4),
        },
    }


def merge_evidence(sim, tick, seen_births, seen_standdowns, seen_resolved):
    """Drain the engine's bounded evidence deques into per-run event
    logs, keyed so nothing is counted twice. Sampled far more often
    than the deques can churn (the 60s growth cooldown bounds births;
    stand-downs fire at most once per evaluation cycle)."""
    eng = sim.brain.enhanced_neurogenesis
    cap = sim.brain.capability
    births, standdowns, resolutions = [], [], []
    for entry in list(eng.growth_log):
        key = (entry.get('at'), entry.get('neuron'))
        if key not in seen_births:
            seen_births.add(key)
            births.append({'tick': tick, 'neuron': entry.get('neuron'),
                           'deficit': entry.get('deficit'),
                           'because': _trunc(entry.get('because'), 160)})
    for at, dkey, why in list(eng.stood_down):
        key = (at, dkey)
        if key not in seen_standdowns:
            seen_standdowns.add(key)
            standdowns.append({'tick': tick, 'deficit': _trunc(dkey, 64),
                               'because': _trunc(why, 160)})
    for at, kind, why in list(cap.resolved):
        why = str(why)
        key = (at, kind, why[:80])
        if key not in seen_resolved:
            seen_resolved.add(key)
            resolutions.append({'tick': tick, 'kind': kind,
                                'why': _trunc(why, 160)})
    return births, standdowns, resolutions


def final_state(sim):
    brain = sim.brain
    eng = brain.enhanced_neurogenesis
    grown = []
    for name, neuron in eng.functional_neurons.items():
        origin = getattr(neuron, 'origin_deficit', None) or {}
        grown.append({
            'name': name,
            'type': getattr(neuron, 'neuron_type', ''),
            'specialization': getattr(neuron, 'specialization', ''),
            'strength_multiplier': getattr(neuron, 'strength_multiplier', 1.0),
            'utility_score': getattr(neuron, 'utility_score', None),
            'origin_kind': origin.get('kind'),
            'origin_summary': _trunc(origin.get('summary'), 140),
        })
    stats = brain.get_statistics()
    kept = {k: sim.stats.get(k) for k in (
        'neurons_created', 'hebbian_updates', 'food_eaten',
        'food_approaches', 'startles', 'escaped_startles',
        'unavoided_startle_ticks', 'flee_actions', 'actions_selected')}
    return {
        'total_neurons': stats.get('total_neurons'),
        'total_connections': stats.get('total_connections'),
        'grown_neurons': grown,
        'growth_report': eng.growth_report(),
        'stats': kept,
    }


def phase_summaries(samples, births, phases):
    """Behaviour and structure change per world phase, from the samples."""
    out = []
    for i, ph in enumerate(phases):
        rows = [s for s in samples if s['phase'] == i]
        if not rows:
            continue
        first, last = rows[0], rows[-1]
        out.append({
            'name': ph['name'],
            'ticks': [first['tick'], last['tick']],
            'food_eaten': last['food_eaten'] - first['food_eaten'],
            'food_approaches': (last['food_approaches']
                                - first['food_approaches']),
            'births': sum(1 for b in births
                          if first['tick'] <= b['tick'] <= last['tick']),
            'neurons_end': last['neurons'],
            'synapses_end': last['synapses'],
            'synapses_added': last['synapses'] - first['synapses'],
            'weight_updates': last['weight_updates'] - first['weight_updates'],
            'mean_anxiety': _mean([s['anxiety'] for s in rows]),
            'mean_hunger': _mean([s['hunger'] for s in rows]),
            'mean_cleanliness': _mean([s['cleanliness'] for s in rows]),
        })
    return out


def run_growth(mode, seed, total_ticks, phases, sample_every,
               soft_deadline_s, log):
    sim = make_growth_sim(mode, seed, learning=True)
    sim.event_queue = deque(contingency_events(0, total_ticks))
    default_poop = float(getattr(sim.config, 'poop_spawn_chance', 0.01)
                         or 0.01)

    samples = []
    births, standdowns, resolutions = [], [], []
    seen_births, seen_standdowns, seen_resolved = set(), set(), set()
    phase_idx = -1
    truncated_at = None

    real = sys.stdout
    sys.stdout = io.StringIO()
    start = time.time()
    try:
        for _ in range(total_ticks):
            sim.tick += 1
            for i, ph in enumerate(phases):
                if sim.tick < ph['until']:
                    if i != phase_idx:
                        phase_idx = i
                        sim.food_side = ph['side']
                        sim.config.poop_spawn_chance = (
                            FOULING_POOP_CHANCE if ph['fouling']
                            else default_poop)
                        print(f"[growth] tick {sim.tick}: phase {i} "
                              f"({ph['name']}) - {ph['label']}", file=real)
                    break
            sim._process_events()
            sim._simulation_step()
            if sim.tick % sample_every == 0:
                samples.append(sample_growth(sim, sim.tick, phase_idx))
                b, sd, rs = merge_evidence(
                    sim, sim.tick, seen_births, seen_standdowns,
                    seen_resolved)
                births.extend(b)
                standdowns.extend(sd)
                resolutions.extend(rs)
            if sim.tick % PROGRESS_EVERY == 0:
                s = samples[-1] if samples else {}
                elapsed = time.time() - start
                print(f"[growth] {mode}/{seed} tick {sim.tick}: "
                      f"neurons={s.get('neurons')} grown={s.get('grown')} "
                      f"synapses={s.get('synapses')} "
                      f"churn={s.get('weight_updates')} "
                      f"eaten={s.get('food_eaten')} "
                      f"({sim.tick / max(elapsed, 0.001):.0f} t/s)",
                      file=real)
            if time.time() - start > soft_deadline_s:
                truncated_at = sim.tick
                print(f"[growth] {mode}/{seed}: soft deadline "
                      f"({soft_deadline_s}s) at tick {sim.tick}", file=real)
                break
    finally:
        sys.stdout = real

    if not samples or samples[-1]['tick'] != sim.tick:
        samples.append(sample_growth(sim, sim.tick, phase_idx))
    b, sd, rs = merge_evidence(sim, sim.tick, seen_births,
                               seen_standdowns, seen_resolved)
    births.extend(b)
    standdowns.extend(sd)
    resolutions.extend(rs)

    elapsed = time.time() - start
    record = {
        'ticks_completed': sim.tick,
        'truncated_at': truncated_at,
        'elapsed_seconds': round(elapsed, 1),
        'ticks_per_second': round(sim.tick / elapsed, 1) if elapsed else 0,
        'samples': samples,
        'births': births,
        'stood_down': standdowns,
        'resolutions': resolutions,
        'phases': phase_summaries(samples, births, phases),
        'final': final_state(sim),
        'predictive': (sim.predictive.get_stats()
                       if sim.predictive.enabled else None),
    }
    last = samples[-1] if samples else {}
    print(f"[growth] {mode}/{seed} done: {sim.tick} ticks, "
          f"neurons={last.get('neurons')} grown={last.get('grown')} "
          f"births={len(births)} churn={last.get('weight_updates')}", file=log)
    return record


def growth_curve_summary(record):
    """The shape questions: when did growth stop, and did learning
    continue afterwards?"""
    samples = record.get('samples') or []
    if not samples:
        return {}
    last = samples[-1]
    births = record.get('births') or []
    last_birth = max((b['tick'] for b in births), default=None)
    change_ticks = [s['tick'] for prev, s in zip(samples, samples[1:])
                    if s['neurons'] != prev['neurons']]
    post = [s for s in samples
            if last_birth is not None and s['tick'] > last_birth]
    return {
        'final_neurons': last['neurons'],
        'final_grown': last['grown'],
        'final_grown_types': last['grown_types'],
        'final_deepened': last['deepened'],
        'final_synapses': last['synapses'],
        'total_weight_updates': last['weight_updates'],
        'births': len(births),
        'standdowns': len(record.get('stood_down') or []),
        'resolutions': len(record.get('resolutions') or []),
        'last_birth_tick': last_birth,
        'last_neuron_change_tick': (change_ticks[-1] if change_ticks
                                    else samples[0]['tick']),
        'type_caps': TYPE_CAPS,
        'global_cap': GLOBAL_CAP,
        'caps_at_end': {k: last['grown_types'].get(k, 0) for k in TYPE_CAPS},
        'weight_updates_after_last_birth': (
            post[-1]['weight_updates'] - post[0]['weight_updates']
            if len(post) >= 2 else 0),
        'food_eaten_after_last_birth': (
            post[-1]['food_eaten'] - post[0]['food_eaten']
            if len(post) >= 2 else 0),
        'food_eaten_total': last['food_eaten'],
        'ticks_per_second': record.get('ticks_per_second'),
        'truncated_at': record.get('truncated_at'),
    }


def summarise(results):
    summary = {}
    for mode, runs in results['runs'].items():
        rows = [growth_curve_summary(r) for r in runs.values()]
        phases = []
        for i, ph in enumerate(results['meta']['phases']):
            cells = []
            for r in runs.values():
                p = next((p for p in (r.get('phases') or [])
                          if p['name'] == ph['name']), None)
                cells.append(p['food_eaten'] if p else 0)
            phases.append({'name': ph['name'], 'food_eaten': _mean(cells)})
        summary[mode] = {
            'n': len(rows),
            'final_neurons': _mean([r.get('final_neurons') for r in rows]),
            'final_grown': _mean([r.get('final_grown') for r in rows]),
            'final_deepened': _mean([r.get('final_deepened') for r in rows]),
            'births': _mean([r.get('births') for r in rows]),
            'standdowns': _mean(
                [r.get('standdowns') for r in rows]),
            'resolutions': _mean(
                [r.get('resolutions') for r in rows]),
            'last_birth_tick': _mean([r.get('last_birth_tick') for r in rows]),
            'final_synapses': _mean([r.get('final_synapses') for r in rows]),
            'total_weight_updates': _mean(
                [r.get('total_weight_updates') for r in rows]),
            'weight_updates_after_last_birth': _mean(
                [r.get('weight_updates_after_last_birth') for r in rows]),
            'food_eaten_after_last_birth': _mean(
                [r.get('food_eaten_after_last_birth') for r in rows]),
            'ticks_per_second': _mean([r.get('ticks_per_second') for r in rows]),
            'phases': phases,
            'runs': rows,
        }
    return summary


def _phase_of(tick, phases):
    for i, ph in enumerate(phases):
        if ph['from'] <= tick < ph['until']:
            return i
    return len(phases) - 1 if phases else 0


def write_compact_outputs(results, out_path):
    """Downloadable-size siblings of the full JSON: a per-mode CSV time
    series (every 4th stored sample), per-mode event records, and a
    summary-only JSON. The full JSON stays the record of everything;
    these exist so the analysis can fetch the curve without paging
    through a multi-megabyte file. Births are rare and kept whole;
    stand-downs and resolutions fire constantly (the quick smoke logged
    ~1,000 stand-downs in 6,000 ticks), so they are aggregated into
    counts, per-phase tallies and reason histograms with a few
    verbatim examples."""
    out = Path(out_path)
    base = out.parent
    base.mkdir(parents=True, exist_ok=True)
    phases = results['meta']['phases']

    def _empty_flow():
        return {'count': 0, 'first_tick': None, 'last_tick': None,
                'examples': [], 'per_phase': {}}

    for mode, runs in results['runs'].items():
        rows = ['# tick,phase,neurons,synapses,grown,deepened,'
                'strength_sum,weight_updates,food_eaten,'
                'food_approaches,anxiety,cleanliness,active_count,'
                'top_actionable,food_seen_ticks,food_items,food_visible,'
                'act_eat,act_move,act_collapse,act_rest,act_flee,'
                'count_idle,count_exploring,count_eating,'
                'count_exhausted,count_sleeping,'
                'w_food_eat,w_hunger_eat,w_curiosity_move,'
                'eat_pos,eat_neg,eat_top_pos,eat_top_neg,'
                'move_pos,move_neg,move_top_pos,move_top_neg']
        events = {'births': [], 'stood_down': _empty_flow(),
                  'resolutions': _empty_flow()}
        for seed, r in sorted(runs.items()):
            for s in (r.get('samples') or [])[::4]:
                act = '-'
                if s.get('actionable'):
                    act = str(s['actionable'][0])[:28].replace(',', ';')
                rows.append(','.join([
                    str(s.get('tick')), str(s.get('phase')),
                    str(s.get('neurons')), str(s.get('synapses')),
                    str(s.get('grown')), str(s.get('deepened')),
                    str(s.get('strength_sum')),
                    str(s.get('weight_updates')),
                    str(s.get('food_eaten')),
                    str(s.get('food_approaches')),
                    str(s.get('anxiety')), str(s.get('cleanliness')),
                    str(s.get('active_count')), act,
                    str(s.get('food_seen_ticks', 0)),
                    str(s.get('food_items', 0)),
                    str(int(bool(s.get('food_visible', False)))),
                    *[str((s.get('motor_activation') or {}).get(name, 0))
                      for name in ('act_eat', 'act_move', 'act_collapse',
                                   'act_rest', 'act_flee')],
                    *[str((s.get('action_counts') or {}).get(name, 0))
                      for name in ('idle', 'exploring', 'eating',
                                   'exhausted', 'sleeping')],
                    *[str((s.get('innate_motor_weights') or {}).get(k, 0))
                      for k in ('food_eat', 'hunger_eat', 'curiosity_move')],
                    *[value for motor in ('act_eat', 'act_move')
                      for value in (
                          str((s.get('motor_synaptic_inputs') or {})
                              .get(motor, {}).get('positive_total', 0)),
                          str((s.get('motor_synaptic_inputs') or {})
                              .get(motor, {}).get('negative_total', 0)),
                          '|'.join(':'.join(str(v) for v in triple)
                                   for triple in (s.get('motor_synaptic_inputs') or {})
                                   .get(motor, {}).get('top_positive', [])),
                          '|'.join(':'.join(str(v) for v in triple)
                                   for triple in (s.get('motor_synaptic_inputs') or {})
                                   .get(motor, {}).get('top_negative', []))
                      )]]))
            for b in r.get('births') or []:
                events['births'].append([
                    b.get('tick'), _trunc(str(b.get('neuron')), 16),
                    _trunc(str(b.get('deficit')), 48),
                    _trunc(str(b.get('because')), 64)])
            for sd in r.get('stood_down') or []:
                e = events['stood_down']
                tick = sd.get('tick')
                e['count'] += 1
                if e['first_tick'] is None or (tick is not None
                                               and tick < e['first_tick']):
                    e['first_tick'] = tick
                if e['last_tick'] is None or (tick is not None
                                              and tick > e['last_tick']):
                    e['last_tick'] = tick
                why = _trunc(str(sd.get('because')), 64)
                dkey = _trunc(str(sd.get('deficit')), 32)
                e.setdefault('by_reason', {})
                e['by_reason'][why] = e['by_reason'].get(why, 0) + 1
                e.setdefault('by_deficit', {})
                e['by_deficit'][dkey] = e['by_deficit'].get(dkey, 0) + 1
                ph = _phase_of(tick, phases)
                e['per_phase'][ph] = e['per_phase'].get(ph, 0) + 1
                if len(e['examples']) < 25:
                    e['examples'].append([tick, dkey, why])
            for rs in r.get('resolutions') or []:
                e = events['resolutions']
                tick = rs.get('tick')
                e['count'] += 1
                if e['first_tick'] is None or (tick is not None
                                               and tick < e['first_tick']):
                    e['first_tick'] = tick
                if e['last_tick'] is None or (tick is not None
                                              and tick > e['last_tick']):
                    e['last_tick'] = tick
                why = _trunc(str(rs.get('why')), 64)
                kind = _trunc(str(rs.get('kind')), 24)
                e.setdefault('by_reason', {})
                e['by_reason'][why] = e['by_reason'].get(why, 0) + 1
                e.setdefault('by_kind', {})
                e['by_kind'][kind] = e['by_kind'].get(kind, 0) + 1
                ph = _phase_of(tick, phases)
                e['per_phase'][ph] = e['per_phase'].get(ph, 0) + 1
                if len(e['examples']) < 25:
                    e['examples'].append([tick, kind, why])
        (base / f'growth_timeseries_{mode}.csv').write_text(
            '\n'.join(rows) + '\n')
        (base / f'growth_events_{mode}.json').write_text(
            json.dumps(events))

    compact = {
        'meta': results['meta'],
        'summary': results['summary'],
        'per_run': {},
    }
    for mode, runs in results['runs'].items():
        compact['per_run'][mode] = {}
        for seed, r in sorted(runs.items()):
            curve = growth_curve_summary(r)
            curve['phases'] = r.get('phases')
            curve['final_grown_census'] = r.get(
                'final', {}).get('grown_neurons')
            curve['growth_report'] = r.get('final', {}).get('growth_report')
            curve['final_stats'] = r.get('final', {}).get('stats')
            curve['elapsed_seconds'] = r.get('elapsed_seconds')
            curve['ticks_completed'] = r.get('ticks_completed')
            compact['per_run'][mode][str(seed)] = curve
    (base / 'growth_summary.json').write_text(json.dumps(compact))
    print(f"Compact outputs written beside {out}: growth_summary.json, "
          f"per-mode timeseries CSVs and event lists")


def print_markdown_summary(results):
    s = results['summary']
    print("\n## Growth-study results\n")
    print("| metric | off | linear | transformer |")
    print("|---|---|---|---|")
    rows = [
        ('final neuron count', 'final_neurons', '{:.0f}'),
        ('grown tissue (of type caps 5/6/6/10)', 'final_grown', '{:.1f}'),
        ('deepened (strength-multiplied) neurons', 'final_deepened', '{:.1f}'),
        ('births during life', 'births', '{:.1f}'),
        ('growth proposals stood down', 'standdowns', '{:.0f}'),
        ('deficits resolved without growth', 'resolutions', '{:.0f}'),
        ('tick of last birth', 'last_birth_tick', '{:.0f}'),
        ('synapses at end', 'final_synapses', '{:.0f}'),
        ('weight updates (total)', 'total_weight_updates', '{:.0f}'),
        ('weight updates AFTER last birth', 'weight_updates_after_last_birth', '{:.0f}'),
        ('food eaten AFTER last birth', 'food_eaten_after_last_birth', '{:.1f}'),
        ('ticks/sec', 'ticks_per_second', '{:.1f}'),
    ]
    for label, key, fmt in rows:
        cells = []
        for mode in MODES:
            v = s.get(mode, {}).get(key)
            cells.append('-' if v is None else fmt.format(v))
        print(f"| {label} | {cells[0]} | {cells[1]} | {cells[2]} |")
    print("\n### food eaten per world phase\n")
    print("| phase | off | linear | transformer |")
    print("|---|---|---|---|")
    names = [p['name'] for p in next(iter(s.values())).get('phases', [])]
    for name in names:
        cells = []
        for mode in MODES:
            v = next((p['food_eaten'] for p in s.get(mode, {}).get('phases', [])
                      if p['name'] == name), None)
            cells.append('-' if v is None else f"{v:.1f}")
        print(f"| {name} | {cells[0]} | {cells[1]} | {cells[2]} |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--quick', action='store_true',
                       help='Smoke run: short life, all wiring exercised')
    group.add_argument('--full', action='store_true',
                       help='Full run: 3 modes x 1 seed x 240k ticks')
    parser.add_argument('--seeds', type=int, nargs='*', default=None)
    parser.add_argument('--ticks', type=int, default=None)
    parser.add_argument('--output', '-o', type=str,
                       default='experiments/results/growth_results.json')
    args = parser.parse_args()

    if args.quick:
        seeds = [11]
        total = QUICK_TICKS
        sample_every = QUICK_SAMPLE_EVERY
    else:
        seeds = args.seeds or GROWTH_SEEDS
        total = args.ticks or GROWTH_TICKS
        sample_every = SAMPLE_EVERY
    phases = _scaled_phases(total)

    print(f"Growth study: {len(MODES)} modes x {len(seeds)} seed(s) x "
          f"{total} ticks, sampled every {sample_every}")
    results = {'meta': {
        'modes': list(MODES),
        'seeds': list(seeds),
        'train_ticks': total,
        'sample_every': sample_every,
        'phases': phases,
        'type_caps': TYPE_CAPS,
        'global_cap': GLOBAL_CAP,
        'soft_deadline_seconds': SOFT_DEADLINE_S,
        'quick': args.quick,
    }, 'runs': {}}
    for mode in MODES:
        results['runs'][mode] = {}
        for seed in seeds:
            results['runs'][mode][str(seed)] = run_growth(
                mode, seed, total, phases, sample_every, SOFT_DEADLINE_S,
                sys.stdout)
    results['summary'] = summarise(results)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to {out}")
    write_compact_outputs(results, out)
    print_markdown_summary(results)


if __name__ == '__main__':
    main()
