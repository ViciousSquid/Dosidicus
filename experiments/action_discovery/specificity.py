"""Falsification check: does newly acquired rest respond to *fatigue*?

The earlier learned-rest benchmark only tested a fatigued animal. A network
that sleeps indiscriminately would pass it. This protocol trains each arm with
the same controlled fatigue curriculum, then asks three fresh frozen brains:
rested, moderately tired, and near exhaustion. No trial exploration runs
during those evaluations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.action_discovery.evaluate import (
    EVAL_SEEDS, EVAL_TICKS, PROFILES, TRAIN_SEEDS, new_brain, train,
)
from experiments.weight_space.trainer_transfer import transfer_weights_only

FATIGUE_LEVELS = (22.0, 65.0, 94.0)


def evaluate_fatigue(brain, seed, initial_sleepiness, ticks=EVAL_TICKS):
    sim = new_brain(seed, "ordinary_learning", learning_enabled=False)
    transfer_weights_only(brain.brain, sim.brain)
    sim.squid.sleepiness = float(initial_sleepiness)
    initial_weights = dict(sim.brain.weights)
    rest_started = 0
    first_rest_tick = None
    for tick in range(ticks):
        was_sleeping = sim.squid.is_sleeping
        sim.tick = tick
        sim._simulation_step()
        if (not was_sleeping and sim.squid.is_sleeping
                and sim.squid.status == "sleeping"):
            rest_started += 1
            if first_rest_tick is None:
                first_rest_tick = tick
    assert initial_weights == dict(sim.brain.weights), "evaluation was not frozen"
    return {
        "voluntary_rest_starts": rest_started,
        "first_rest_tick": first_rest_tick,
        "selected_sleep_ticks": sim.stats["actions_selected"].get("sleeping", 0),
        "selected_collapse_ticks": sim.stats["actions_selected"].get("exhausted", 0),
        "final_sleepiness": round(sim.squid.sleepiness, 4),
        "final_health": round(sim.squid.health, 4),
    }


def run_experiment(train_seeds=TRAIN_SEEDS, eval_seeds=EVAL_SEEDS,
                   fatigue_levels=FATIGUE_LEVELS, bouts=22, ticks_per_bout=32,
                   eval_ticks=EVAL_TICKS):
    rows = []
    learned_paths = []
    for arm in PROFILES:
        for train_seed in train_seeds:
            trained, metrics = train(
                train_seed, arm, bouts=bouts, ticks_per_bout=ticks_per_bout)
            incoming = [
                (src, round(float(weight), 5))
                for (src, dst), weight in trained.brain.weights.items()
                if dst == "act_rest"
            ]
            learned_paths.append({
                "arm": arm, "train_seed": train_seed,
                "incoming": sorted(incoming, key=lambda x: -abs(x[1])),
                "learning": metrics,
            })
            for eval_seed in eval_seeds:
                for initial_sleepiness in fatigue_levels:
                    outcome = evaluate_fatigue(
                        trained, eval_seed, initial_sleepiness, eval_ticks)
                    rows.append({
                        "arm": arm, "train_seed": train_seed,
                        "evaluation_seed": eval_seed,
                        "starting_sleepiness": initial_sleepiness,
                        **outcome,
                    })

    summary = {}
    n = len(train_seeds) * len(eval_seeds)
    for arm in PROFILES:
        for level in fatigue_levels:
            selected = [r for r in rows
                        if r["arm"] == arm and r["starting_sleepiness"] == level]
            assert len(selected) == n
            key = str(int(level))
            summary.setdefault(arm, {})[key] = {
                "episodes": len(selected),
                "episodes_with_voluntary_rest": sum(
                    1 for r in selected if r["voluntary_rest_starts"] > 0),
                "mean_rest_initiations": round(
                    sum(r["voluntary_rest_starts"] for r in selected) / n, 4),
                "mean_final_sleepiness": round(
                    sum(r["final_sleepiness"] for r in selected) / n, 4),
            }
    return {
        "question": "Does learned rest depend on fatigue or fire indiscriminately?",
        "fatigue_levels": list(fatigue_levels),
        "arms": list(PROFILES),
        "train_seeds": list(train_seeds),
        "eval_seeds": list(eval_seeds),
        "training_bouts": bouts,
        "ticks_per_bout": ticks_per_bout,
        "evaluation_ticks": eval_ticks,
        "summary": summary,
        "learned_paths": learned_paths,
        "runs": rows,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", type=Path)
    args = p.parse_args()
    data = run_experiment()
    for arm, by_fatigue in data["summary"].items():
        bits = [f"{level}: {row['episodes_with_voluntary_rest']}/{row['episodes']}"
                for level, row in by_fatigue.items()]
        print(f"{arm:20} voluntary-rest-by-initial-sleepiness = {', '.join(bits)}")
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
