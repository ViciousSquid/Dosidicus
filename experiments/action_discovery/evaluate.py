"""Controlled, falsifiable opt-in discovery of voluntary rest.

Three arms start from the SAME 3.2.0 newborn synaptic prior:

  A. ordinary Hebbian/STDP/causal learning, no motor probes;
  B. motor probes, but NO outcome-gated synapse teaching (placebo);
  C. identical motor probe rate, with outcome-gated synapse teaching.

Each trained brain then gets its synaptic weights copied into a fresh frozen
brain. The new aquarium is not taught or prompted; we measure whether the
neural rest pathway can actually act before exhaustion.

Training is a deliberately enriched *fatigue curriculum*: repeated externally
set high-sleepiness starts. Every injection interrupts pending causal credit,
so the brain cannot be rewarded for the artificial state change. Evaluation
has just one initially sleepy brain and absolutely no interventions after
initialisation. This is not a claim of ecological validity.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from experiments.weight_space.trainer_transfer import (
    new_simulation, transfer_weights_only,
)

PROFILES = ("ordinary_learning", "motor_probes_only", "motor_probe_teaching")
TRAIN_SEEDS = (11, 29, 53, 71)
EVAL_SEEDS = (101, 103, 107, 109)
BOUTS = 22
TICKS_PER_BOUT = 32
EVAL_TICKS = 48

NO_DISTRACTIONS = {
    "food_spawn_chance": 0.0,
    "poop_spawn_chance": 0.0,
    "startle_chance": 0.0,
}


def new_brain(seed, profile, *, learning_enabled=True):
    rate = 0.0 if profile == "ordinary_learning" else 0.45
    teaching = profile == "motor_probe_teaching"
    return new_simulation(
        seed, "original", learning_enabled,
        action_discovery_rate=rate,
        action_discovery_teaching=teaching,
        **NO_DISTRACTIONS,
    )


def train(seed, profile, bouts=BOUTS, ticks_per_bout=TICKS_PER_BOUT):
    sim = new_brain(seed, profile, learning_enabled=True)
    initial = dict(sim.brain.weights)
    for bout in range(bouts):
        # This is a controlled *intervention*, not a squid decision. Cancel
        # pending credit before the change as in the normal scenario events.
        sim.brain.causal_learning.discard_pending_outcomes(
            reason="fatigue_curriculum_new_bout")
        sim.squid.sleepiness = 94.0
        sim.squid.anxiety = 10.0
        sim.squid.hunger = 50.0
        sim.squid.is_sleeping = False
        sim.squid.sleep_ticks = 0
        sim.squid.status = "roaming"
        for i in range(ticks_per_bout):
            sim.tick = bout * ticks_per_bout + i
            sim._simulation_step()

    # Flush already settled outcomes and discard incomplete tail windows.
    if sim.action_discovery:
        sim.action_discovery.process_closed()
    edges = set(initial) | set(sim.brain.weights)
    changed = sum(initial.get(e) != sim.brain.weights.get(e) for e in edges)
    summary = {
        "changed_edges": changed,
        "rest_weight": sim.brain.weights.get(("sleepiness", "act_rest"), 0.0),
        "rest_actions": sim.stats["actions_selected"].get("sleeping", 0),
        "play_actions": sim.stats["actions_selected"].get("playing", 0),
        "shelter_actions": sim.stats["actions_selected"].get("approaching_plant", 0),
        "hebbian_updates": sim.stats["hebbian_updates"],
        "causal_episodes_closed": sim.brain.causal_learning.closed_episodes,
        "interventions_interrupting_credit":
            sim.brain.causal_learning.interrupted_episodes,
        "discovery": sim.action_discovery.statistics() if sim.action_discovery else None,
    }
    return sim, summary


def evaluate_frozen(source, seed, ticks=EVAL_TICKS):
    sim = new_brain(seed, "ordinary_learning", learning_enabled=False)
    sim.squid.sleepiness = 94.0
    transfer_weights_only(source.brain, sim.brain)
    before = dict(sim.brain.weights)
    for i in range(ticks):
        sim.tick = i
        sim._simulation_step()
    assert before == dict(sim.brain.weights)
    assert sim.stats["hebbian_updates"] == 0
    assert sim.brain.causal_learning.closed_episodes == 0
    return {
        "rest_actions": sim.stats["actions_selected"].get("sleeping", 0),
        "collapse_actions": sim.stats["actions_selected"].get("exhausted", 0),
        "final_sleepiness": round(sim.squid.sleepiness, 4),
        "selected_actions": dict(sim.stats["actions_selected"]),
        "final_health": round(sim.squid.health, 4),
    }


def experiment(train_seeds=TRAIN_SEEDS, eval_seeds=EVAL_SEEDS,
               bouts=BOUTS, ticks_per_bout=TICKS_PER_BOUT,
               eval_ticks=EVAL_TICKS):
    result = {
        "description": "Weight-only transfer after causal motor exploration",
        "train_seeds": list(train_seeds), "eval_seeds": list(eval_seeds),
        "bouts": bouts, "ticks_per_bout": ticks_per_bout,
        "eval_ticks": eval_ticks, "arms": list(PROFILES),
        "controls": "same original innate priors; matched seed; frozen evaluation",
        "runs": [], "summary": {},
    }
    for arm in PROFILES:
        for train_seed in train_seeds:
            trained, train_stats = train(train_seed, arm, bouts, ticks_per_bout)
            result["runs"].append({
                "phase": "training", "arm": arm, "train_seed": train_seed,
                "metrics": train_stats})
            for eval_seed in eval_seeds:
                metrics = evaluate_frozen(trained, eval_seed, eval_ticks)
                result["runs"].append({
                    "phase": "evaluation", "arm": arm,
                    "train_seed": train_seed, "eval_seed": eval_seed,
                    "metrics": metrics})
    for arm in PROFILES:
        train_rows = [r["metrics"] for r in result["runs"]
                      if r["phase"] == "training" and r["arm"] == arm]
        eval_rows = [r["metrics"] for r in result["runs"]
                     if r["phase"] == "evaluation" and r["arm"] == arm]
        result["summary"][arm] = {
            "mean_new_rest_edge": round(
                sum(r["rest_weight"] for r in train_rows) / len(train_rows), 5),
            "mean_frozen_rest_actions": round(
                sum(r["rest_actions"] for r in eval_rows) / len(eval_rows), 5),
            "frozen_episodes_with_voluntary_rest": sum(
                r["rest_actions"] > 0 for r in eval_rows),
            "total_frozen_episodes": len(eval_rows),
            "mean_final_sleepiness": round(
                sum(r["final_sleepiness"] for r in eval_rows) / len(eval_rows), 5),
            "mean_training_changed_edges": round(
                sum(r["changed_edges"] for r in train_rows) / len(train_rows), 3),
            "motor_connections_taught": sum(
                (r["discovery"] or {}).get("motor_connections_taught", 0)
                for r in train_rows),
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--bouts", type=int, default=BOUTS)
    parser.add_argument("--ticks-per-bout", type=int, default=TICKS_PER_BOUT)
    parser.add_argument("--eval-ticks", type=int, default=EVAL_TICKS)
    args = parser.parse_args()
    result = experiment(
        bouts=args.bouts, ticks_per_bout=args.ticks_per_bout,
        eval_ticks=args.eval_ticks)
    for arm, metrics in result["summary"].items():
        print(f"{arm:20}  rest-edge={metrics['mean_new_rest_edge']:+.3f} "
              f"frozen resting episodes="
              f"{metrics['frozen_episodes_with_voluntary_rest']}/"
              f"{metrics['total_frozen_episodes']} "
              f"mean rest actions={metrics['mean_frozen_rest_actions']:.2f} "
              f"final sleepiness={metrics['mean_final_sleepiness']:.2f}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
