"""Real-trainer learning-transfer evaluation, reporting outcomes not an IQ score.

Unlike the earlier synthetic aquarium, this uses HeadlessSimulation's normal
world, bodily actions, food positions, neural action selection and learning.

The production 3.2.0 innate weights are reconstructed exactly on the control
brain, because the experimental branch itself contains the three failed edits.

    python -m experiments.weight_space.trainer_transfer --json /tmp/transfer.json
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from collections import defaultdict
from pathlib import Path

from headless.headless_trainer import HeadlessSimulation
from src.portable_brain import TrainingConfig
from .experiment import BASELINE_EDGES, CANDIDATE_EDGES

TRAIN_SEEDS = (11, 29, 53)
EVAL_SEEDS = (10_001, 10_033, 10_061)
TRAIN_TICKS = 450
EVAL_TICKS = 300
PROFILES = ("original", "three_edit")
# Reproduction case: same food availability; unfamiliar case: more or less food,
# and more frequent startles. All are real headless settings, not new rules.
EVAL_WORLDS = {
    "balanced": {"food_spawn_chance": .025, "startle_chance": .005},
    "scarce": {"food_spawn_chance": .008, "startle_chance": .005},
    "stress": {"food_spawn_chance": .025, "startle_chance": .035},
}
OBSERVABLES = (
    "food_eaten", "food_approaches", "food_seen_ticks", "flee_actions",
    "escaped_startles", "unavoided_startle_ticks", "manual_feedings",
)


def new_simulation(seed, profile, learning_enabled, **world):
    settings = TrainingConfig(
        seed=seed, learning_enabled=learning_enabled,
        neurogenesis_enabled=False, **world,
    )
    sim = HeadlessSimulation(settings)
    if profile == "original":
        for edge, weight in BASELINE_EDGES.items():
            if weight is None:
                sim.brain.remove_weight(
                    edge, mechanism="experimental_control",
                    reason="restore absent original 3.2.0 synapse")
            else:
                sim.brain.apply_weight_change(
                    edge, value=weight, mechanism="experimental_control",
                    detail={"source": "3.2.0_LatestVersion"}, create=True)
    elif profile == "three_edit":
        for edge, weight in CANDIDATE_EDGES.items():
            assert sim.brain.weights.get(edge) == weight
    else:
        raise ValueError(profile)
    return sim


def transfer_weights_only(source, dest):
    """Transfer only directed synaptic weights. No experience or body state."""
    assert source.positions == dest.positions, (
        "This benchmark intentionally disables neurogenesis")
    for edge in set(dest.weights) - set(source.weights):
        dest.remove_weight(edge, mechanism="transfer",
                           reason="edge absent from trained network")
    for edge, value in source.weights.items():
        dest.apply_weight_change(
            edge, value=value, mechanism="transfer", create=True)
    assert dict(dest.weights) == dict(source.weights)


def run(sim, ticks):
    with contextlib.redirect_stdout(io.StringIO()):
        sim.run(ticks=ticks, progress_interval=0)
    assert sim.stats["ticks_completed"] == ticks
    return sim


def observation(sim):
    return {
        **{key: sim.stats[key] for key in OBSERVABLES},
        "health": round(sim.squid.health, 4),
        "hunger": round(sim.squid.hunger, 4),
        "position": [round(sim.squid.x, 4), round(sim.squid.y, 4)],
        "actions": dict(sim.stats["actions_selected"]),
        "synapse_count": len(sim.brain.weights),
        "hebbian_updates": sim.stats["hebbian_updates"],
        "neurogenesis": sim.stats["neurons_created"],
    }


def evaluate(train_ticks=TRAIN_TICKS, eval_ticks=EVAL_TICKS,
             train_seeds=TRAIN_SEEDS, eval_seeds=EVAL_SEEDS):
    report = {
        "protocol": "Real HeadlessSimulation action-coupled training and frozen evaluation",
        "train_ticks": train_ticks, "eval_ticks": eval_ticks,
        "train_seeds": list(train_seeds), "evaluation_seeds": list(eval_seeds),
        "evaluation_worlds": EVAL_WORLDS,
        "profiles": list(PROFILES),
        "learning_during_evaluation": False,
        "runs": [], "summary": {},
    }
    for profile in PROFILES:
        for train_seed in train_seeds:
            trained = new_simulation(train_seed, profile, True)
            initial = dict(trained.brain.weights)
            run(trained, train_ticks)
            actual = {
                "initial_synapses": len(initial),
                "learned_synapses": len(trained.brain.weights),
                "changed_edges": sum(
                    initial.get(edge) != trained.brain.weights.get(edge)
                    for edge in set(initial) | set(trained.brain.weights)),
                "hebbian_updates": trained.stats["hebbian_updates"],
                "causal_episodes": trained.brain.causal_learning.closed_episodes,
                **observation(trained),
            }
            report["runs"].append({
                "kind": "training", "profile": profile,
                "train_seed": train_seed, "metrics": actual,
            })
            for world_name, overrides in EVAL_WORLDS.items():
                for evaluation_seed in eval_seeds:
                    # Every comparison starts from identical body/seed/world.
                    # Only the initial directed synaptic weights differ.
                    for condition in ("untrained", "trained_weights"):
                        evaluated = new_simulation(evaluation_seed, profile,
                                                   False, **overrides)
                        if condition == "trained_weights":
                            transfer_weights_only(trained.brain, evaluated.brain)
                        beginning = dict(evaluated.brain.weights)
                        run(evaluated, eval_ticks)
                        assert dict(evaluated.brain.weights) == beginning, (
                            "Frozen evaluation unexpectedly rewrote synapses")
                        assert evaluated.stats["hebbian_updates"] == 0
                        report["runs"].append({
                            "kind": "evaluation", "profile": profile,
                            "train_seed": train_seed,
                            "world": world_name,
                            "eval_seed": evaluation_seed,
                            "condition": condition,
                            "metrics": observation(evaluated),
                        })
    # Paired deltas, primary metrics not an arbitrary scalar transfer score.
    for profile in PROFILES:
        for world in EVAL_WORLDS:
            rows = [r for r in report["runs"] if r["kind"] == "evaluation"
                    and r["profile"] == profile and r["world"] == world]
            indexed = defaultdict(dict)
            for row in rows:
                indexed[(row["train_seed"], row["eval_seed"])][row["condition"]] = row["metrics"]
            assert len(indexed) == len(train_seeds) * len(eval_seeds)
            metrics = ("food_eaten", "health", "hunger",
                       "flee_actions", "escaped_startles",
                       "unavoided_startle_ticks")
            report["summary"].setdefault(profile, {})[world] = {}
            for metric in metrics:
                pairs = [
                    (item["untrained"][metric], item["trained_weights"][metric])
                    for item in indexed.values()
                ]
                report["summary"][profile][world][metric] = {
                    "untrained_mean": round(sum(a for a, b in pairs) / len(pairs), 5),
                    "trained_mean": round(sum(b for a, b in pairs) / len(pairs), 5),
                    "paired_delta": round(sum(b-a for a, b in pairs) / len(pairs), 5),
                }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--train-ticks", type=int, default=TRAIN_TICKS)
    parser.add_argument("--eval-ticks", type=int, default=EVAL_TICKS)
    args = parser.parse_args()
    report = evaluate(args.train_ticks, args.eval_ticks)
    print("Real headless trainer, mean paired learned-minus-untrained outcomes:")
    for profile in PROFILES:
        for world, scores in report["summary"][profile].items():
            print(f"{profile:12s} {world:9s} "
                  f"meals={scores['food_eaten']['paired_delta']:+.3f} "
                  f"health={scores['health']['paired_delta']:+.3f} "
                  f"unavoided_startle_ticks={scores['unavoided_startle_ticks']['paired_delta']:+.3f}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")


if __name__ == "__main__":
    main()
