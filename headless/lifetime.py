#!/usr/bin/env python3
"""Does a squid get better at living, the longer it has lived?

The one measurement that says whether learning in this engine is worth
anything. A squid is raised in the headless tank; at intervals a FROZEN copy
of its brain - nothing about it can change - is dropped into worlds it has
never seen, and what happens to it is recorded: how hungry, anxious, happy and healthy it
stayed, how much it ate, how often exhaustion dropped it. Its own newborn self
is scored in the same worlds. If experience is doing its job the curve rises,
and if it falls the engine is un-teaching the squid what it was born knowing.

Three things make the comparison mean something:

  * FROZEN. The copy does not learn or grow during the test, so the score is
    what the brain knows, not what it picks up on the way.
  * THE SAME WORLD. Food, startles and plants come from the world's own
    random stream (TrainingConfig.world_seed), which is drawn from identically
    whatever the squid does. Two brains scored on one world seed met the same
    food at the same moments.
  * ITS OWN NEWBORN SELF. Not a tuned baseline: the brain it was hatched with.

Run it:

    python headless/lifetime.py --seeds 6 --life 20000

Nothing here is used by the game. It imports the same engine the game runs.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from headless.headless_trainer import (HeadlessSimulation, HeadlessSquid,  # noqa: E402
                                       Personality)
from src.portable_brain import TrainingConfig  # noqa: E402

#: What a frozen trial reports. Every one is either a statistic the squid
#: really has (averaged over the trial) or a count of something its own brain
#: chose to do. There is deliberately NO combined score: a number made by
#: averaging hunger with happiness is not a thing the squid has, and a result
#: stated in it cannot be checked against the tank.
STATISTICS = ('hunger', 'anxiety', 'happiness', 'health')
COUNTS = ('food_eaten', 'collapses', 'chosen_rests', 'sheltered_ticks',
          'unavoided_startle_ticks')
METRICS = STATISTICS + COUNTS

#: Which way is better for the squid, for each one. Used only to word a
#: comparison ("fed better", "hurt more"), never to merge them.
BETTER_WHEN_LOWER = frozenset({'hunger', 'anxiety', 'collapses',
                               'unavoided_startle_ticks'})

#: Worlds no squid in a study is raised in.
HELD_OUT_WORLDS = (9001, 9002, 9003)


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def new_tank(seed: int, *, world_seed: Optional[int] = None,
             personality: Personality = Personality.ADVENTUROUS,
             **overrides) -> HeadlessSimulation:
    """A tank with one newborn in it. The personality is fixed so that a
    difference between two runs is never just a different temperament."""
    config = TrainingConfig(seed=seed, world_seed=world_seed, **overrides)
    tank = _quiet(HeadlessSimulation, config)
    tank.squid = HeadlessSquid(personality, rng=tank.body_rng)
    tank.brain.personality = personality.value
    return tank


def frozen_trial(brain_document: Optional[Dict], world_seed: int, ticks: int = 3000,
                 personality: Personality = Personality.ADVENTUROUS,
                 **overrides) -> Dict[str, float]:
    """Score one brain, unable to change, on one world.

    `brain_document` is HeadlessBrain.export_brain() output; None scores a
    newborn.
    """
    tank = new_tank(world_seed, world_seed=world_seed, personality=personality,
                    learning_enabled=False, neurogenesis_enabled=False, **overrides)
    if brain_document is not None:
        if not _quiet(tank.brain.load_brain, brain_document):
            raise ValueError('brain document did not load')
    before = dict(tank.brain.weights)
    neurons = set(tank.brain.positions)

    totals = dict.fromkeys(STATISTICS, 0.0)
    for tick in range(ticks):
        tank.tick = tick
        _quiet(tank._simulation_step)
        for name in totals:
            totals[name] += float(getattr(tank.squid, name))

    # The whole point of a frozen trial. Checked every time rather than
    # trusted, because a trial that quietly learns is measuring something else.
    if dict(tank.brain.weights) != before or set(tank.brain.positions) != neurons:
        raise AssertionError('a frozen brain changed during its trial')

    result = {name: total / ticks for name, total in totals.items()}
    for name in COUNTS:
        result[name] = float(tank.stats.get(name, 0))
    result['actions'] = dict(tank.stats['actions_selected'])
    return result


def score(brain_document: Optional[Dict], worlds: Iterable[int] = HELD_OUT_WORLDS,
          ticks: int = 3000, **overrides) -> Dict[str, float]:
    """Mean of each metric over several held-out worlds."""
    trials = [frozen_trial(brain_document, world, ticks, **overrides) for world in worlds]
    return {name: statistics.mean(t[name] for t in trials) for name in METRICS}


def live(seed: int, checkpoints: Iterable[int], *, worlds=HELD_OUT_WORLDS,
         trial_ticks: int = 3000, **overrides) -> List[Dict]:
    """Raise one squid, scoring a frozen copy of it at each checkpoint.

    Returns one row per checkpoint, the first at tick 0 (the newborn).
    """
    tank = new_tank(seed, **overrides)
    rows, lived = [], 0
    for checkpoint in sorted(set([0, *checkpoints])):
        while lived < checkpoint:
            tank.tick = lived
            _quiet(tank._process_events)
            _quiet(tank._simulation_step)
            lived += 1
        document = _quiet(tank.brain.export_brain)
        row = score(document, worlds, trial_ticks)
        row.update(tick=checkpoint, seed=seed,
                   neurons=len(tank.brain.positions),
                   grown=sorted(tank.brain.enhanced_neurogenesis.functional_neurons),
                   synapses=len(tank.brain.weights))
        rows.append(row)
    return rows


def summarise(lives: List[List[Dict]]) -> List[Dict]:
    """Mean over squids at each checkpoint."""
    out = []
    for rows in zip(*lives):
        entry = {'tick': rows[0]['tick'], 'squids': len(rows),
                 'neurons': statistics.mean(r['neurons'] for r in rows)}
        for name in METRICS:
            entry[name] = statistics.mean(r[name] for r in rows)
        out.append(entry)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--seeds', type=int, default=6, help='how many squid to raise')
    parser.add_argument('--life', type=int, default=20000, help='ticks each one lives')
    parser.add_argument('--checkpoints', type=int, default=4,
                        help='frozen tests per life, evenly spaced')
    parser.add_argument('--trial-ticks', type=int, default=3000)
    parser.add_argument('--json', type=str, default='', help='write every row here')
    args = parser.parse_args(argv)

    step = max(1, args.life // max(1, args.checkpoints))
    checkpoints = list(range(step, args.life + 1, step))
    lives = []
    for seed in range(1, args.seeds + 1):
        lives.append(live(seed, checkpoints, trial_ticks=args.trial_ticks))
        last = lives[-1][-1]
        first = lives[-1][0]
        print(f"squid {seed}: food eaten {first['food_eaten']:.1f} -> "
              f"{last['food_eaten']:.1f}, hunger {first['hunger']:.0f} -> "
              f"{last['hunger']:.0f}, anxiety {first['anxiety']:.0f} -> "
              f"{last['anxiety']:.0f}, health {first['health']:.0f} -> "
              f"{last['health']:.0f}, grew {len(last['grown'])}", flush=True)

    print(f"\n{'tick':>7} {'neurons':>7} " + ' '.join(f"{m[:10]:>10}" for m in METRICS))
    for row in summarise(lives):
        print(f"{row['tick']:>7} {row['neurons']:>7.1f} "
              + ' '.join(f"{row[m]:>10.2f}" for m in METRICS))
    if args.json:
        Path(args.json).write_text(json.dumps(lives, indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
