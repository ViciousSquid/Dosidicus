"""Closed-loop *proxy* test: network action selection changes future world state.

Unlike headless_trainer._update_environment (where food is awarded by a random
draw even when the network chooses no eating), this experiment connects real
HeadlessBrain propagation + decision_engine.select_action to food, damage,
threat escape and the squid's subsequent homeostatic drives. This is NOT
the full graphical game, and is not a claim of general intelligence.

The experiment is observational, with equal environment seeds and explicit
food scarcity, predator pressure, false alarms and delayed learning. No
'human correct answer' threshold labels are used in the fitness objective.

Execute: python -m experiments.weight_space.closed_loop --json /tmp/loop.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path

from src.brain_constants import ACTION_FIRING_THRESHOLDS
from src.decision_engine import select_action
from src.portable_brain import HeadlessBrain, TrainingConfig
from .experiment import BASELINE_EDGES, CANDIDATE_EDGES

PROFILES = {
    "original": BASELINE_EDGES,
    "three_edit": CANDIDATE_EDGES,
    # These are named candidate hypotheses, not retrospectively selected winners.
    "threat_only": {("threat_level", "act_flee"): 1.0,
                    ("anxiety", "act_flee"): 0.25,
                    ("threat_level", "act_eat"): None},
    "moderate": {("threat_level", "act_flee"): 0.90,
                 ("anxiety", "act_flee"): 0.35,
                 ("threat_level", "act_eat"): -0.20},
}
# Predefined scenarios. These parameters generate a world, not normative action labels.
WORLDS = {
    "balanced": {"food": 0.12, "predator": 0.022, "false_alarm": 0.03},
    "scarce_food": {"food": 0.045, "predator": 0.022, "false_alarm": 0.03},
    "dangerous": {"food": 0.12, "predator": 0.055, "false_alarm": 0.03},
    "false_alarms": {"food": 0.12, "predator": 0.014, "false_alarm": 0.13},
}
TRAIN_SEEDS = (11, 23, 37, 51)
EVAL_SEEDS = (1009, 1021, 1033, 1051)
HELD_OUT_SEEDS = (4001, 4013, 4027, 4051)
TICKS = 250
TRAIN_TICKS = 200

def make_brain(profile):
    brain = HeadlessBrain(TrainingConfig(neurogenesis_enabled=False, learning_rate=0.1))
    expected = CANDIDATE_EDGES
    for edge, current in expected.items():
        assert brain.weights.get(edge) == current, (edge, brain.weights.get(edge), current)
    for edge, value in PROFILES[profile].items():
        if value is None:
            brain.remove_weight(edge, mechanism="experiment_profile", reason=profile)
        else:
            brain.apply_weight_change(
                edge, value=value, mechanism="experiment_profile",
                detail={"variant": profile}, create=True)
    return brain

@dataclass
class Aquarium:
    hunger: float = 58
    anxiety: float = 23
    sleepiness: float = 26
    health: float = 100
    food_timer: int = 0
    threat_timer: int = 0
    sleep_timer: int = 0
    food_eaten: int = 0
    attacks: int = 0
    damage: float = 0
    successful_escapes: int = 0
    false_flees: int = 0
    excess_hunger: int = 0
    collapses: int = 0
    active_ticks: int = 0

    def observations(self, false_alarm, startled):
        threat = (100.0 if self.threat_timer else false_alarm)
        return {
            "hunger": self.hunger,
            "anxiety": self.anxiety,
            "sleepiness": self.sleepiness,
            "happiness": max(0.0, 82.0 - 0.42 * self.hunger - 0.24 * self.anxiety),
            "satisfaction": max(0.0, 84.0 - 0.45 * self.hunger),
            "cleanliness": 80.0,
            "curiosity": 62.0,
            "can_see_food": 100.0 if self.food_timer else 0.0,
            "threat_level": threat,
            "is_startled": 100.0 if startled else 0.0,
            "is_sleeping": 100.0 if self.sleep_timer else 0.0,
        }

def simulate(brain, world_name, seed, ticks=TICKS, learn=False):
    world = WORLDS[world_name]
    rng = random.Random(seed)
    tank = Aquarium()
    first_weight_count = len(brain.weight_history)
    actions = {"eating": 0, "fleeing": 0, "exploring": 0, "sleeping": 0, "other": 0}
    for tick in range(ticks):
        if tank.health <= 0:
            break
        tank.active_ticks += 1
        # Environmental randomness is local, deterministic and seeded;
        # never contingent on global RNG used by neural learning.
        food_draw, predator_draw, alarm_draw = rng.random(), rng.random(), rng.random()
        flee_draw, approach_draw = rng.random(), rng.random()
        if tank.food_timer == 0 and food_draw < world["food"]:
            tank.food_timer = 13
        started_threat = tank.threat_timer == 0 and predator_draw < world["predator"]
        if started_threat:
            tank.threat_timer = 7
        false_alarm = 35.0 if tank.threat_timer == 0 and alarm_draw < world["false_alarm"] else 0.0

        tank.anxiety = max(0.0, tank.anxiety - 0.65)
        tank.hunger = min(100.0, tank.hunger + 0.30)
        tank.sleepiness = min(100.0, tank.sleepiness + 0.15)
        if tank.hunger >= 85:
            tank.excess_hunger += 1
            tank.health -= 0.35

        observations = tank.observations(false_alarm, started_threat)
        brain.advance_clock(1.0)
        brain.update_state(observations)
        brain.propagate()
        chosen, _confidence, _urgency = select_action(brain.state, jitter=False)
        action = chosen or "exploring"
        if tank.sleep_timer:
            action = "sleeping"
        actions[action if action in actions else "other"] += 1

        # Consequences are caused by the actual neural action; a passive
        # random food event never feeds the animal.
        if action == "eating" and tank.food_timer:
            tank.food_eaten += 1
            tank.hunger = max(0.0, tank.hunger - 27.0)
            tank.health = min(100.0, tank.health + 1.2)
            tank.food_timer = 0
        elif action == "exploring" and tank.food_timer == 0 and approach_draw < 0.08:
            tank.food_timer = 13

        if action == "fleeing" and not tank.threat_timer:
            tank.false_flees += 1
            tank.hunger = min(100.0, tank.hunger + 0.18)
        if tank.threat_timer:
            if action == "fleeing":
                if flee_draw >= 0.12:
                    tank.successful_escapes += 1
                    tank.threat_timer = 0
                else:
                    tank.damage += 1.0
                    tank.health -= 1.0
            elif action == "sleeping":
                tank.damage += 7.0
                tank.health -= 7.0
            elif action == "eating":
                tank.damage += 6.0
                tank.health -= 6.0
            else:
                tank.damage += 4.0
                tank.health -= 4.0

        # Reflex collapse and learned rest share the animal's sleep actuator.
        collapse = (brain.state.get("act_collapse", 0.0) >=
                    ACTION_FIRING_THRESHOLDS["act_collapse"])
        if (collapse or (action == "sleeping" and not tank.sleep_timer)):
            if collapse:
                tank.collapses += 1
            tank.sleep_timer = 9
        if tank.sleep_timer:
            tank.sleepiness = max(0, tank.sleepiness - 7)
            tank.sleep_timer -= 1
        if tank.threat_timer:
            tank.threat_timer -= 1
            tank.anxiety = min(100.0, tank.anxiety + 1.0)
        if tank.food_timer:
            tank.food_timer -= 1

        if learn:
            brain.causal_learning.on_action(action)
            if tick % 30 == 29:
                brain.perform_hebbian_learning()
            brain.consolidate(bool(tank.sleep_timer))
    # Explicit utility measured using consequential outcomes, not threshold
    # agreement. Weighted score is illustrative, not a validated welfare measure.
    # Do not optimise this score and then call the same seeds a fair test.
    score = (tank.active_ticks / ticks * 100.0
             + 3.0 * tank.food_eaten
             + 1.0 * tank.successful_escapes
             - 0.75 * tank.damage
             - 0.12 * tank.false_flees
             - 0.18 * tank.excess_hunger
             - 0.5 * tank.collapses)
    return {
        "ticks_alive": tank.active_ticks, "health": round(max(0.0, tank.health), 4),
        "food_eaten": tank.food_eaten, "attacks_suffered": tank.attacks,
        "damage": round(tank.damage, 4),
        "successful_escapes": tank.successful_escapes,
        "false_flees": tank.false_flees,
        "excess_hunger_ticks": tank.excess_hunger,
        "collapses": tank.collapses,
        "synaptic_learning_updates": len(brain.weight_history) - first_weight_count,
        "final_neurons": len(brain.positions),
        "score": round(score, 4), "actions": actions,
    }

def evaluate():
    report = {
        "method": "Action-coupled simplified aquarium; same Dosidicus HeadlessBrain propagation and select_action",
        "status": "proxy, NOT integrated full-game simulation",
        "training": {"seeds": TRAIN_SEEDS, "ticks": TRAIN_TICKS, "learning": True},
        "evaluation": {"dev_seeds": EVAL_SEEDS, "holdout_seeds": HELD_OUT_SEEDS,
                       "ticks": TICKS, "learning": False},
        "profiles": {"->".join(e): {p: PROFILES[p].get(e) for p in PROFILES}
                     for e in CANDIDATE_EDGES},
        "runs": [], "summary": {},
    }
    for profile in PROFILES:
        rows = []
        for world in WORLDS:
            for split, seeds in (("development", EVAL_SEEDS), ("holdout", HELD_OUT_SEEDS)):
                for seed in seeds:
                    # Fresh untrained brain for every evaluation; no tuned
                    # conditions or evolved weights leak into holdout.
                    brain = make_brain(profile)
                    data = simulate(brain, world, seed, learn=False)
                    rows.append({"profile": profile, "world": world,
                                 "split": split, "seed": seed, "training": False, **data})
        report["runs"].extend(rows)
        for split in ("development", "holdout"):
            relevant = [r for r in rows if r["split"] == split]
            report["summary"].setdefault(split, {})[profile] = {
                name: round(sum(r[name] for r in relevant) / len(relevant), 4)
                for name in ("score", "ticks_alive", "food_eaten", "health",
                             "damage", "successful_escapes", "false_flees", "excess_hunger_ticks")}
        # Learning experiment: retain weights between training and new eval.
        # Training episodes see a different fixed set of seeds than evaluation.
        train_rows, transfer_rows = [], []
        for seed in TRAIN_SEEDS:
            brain = make_brain(profile)
            for world in WORLDS:
                # In this arm neuroplasticity actually runs, including
                # correlation-learning and consolidation.
                data = simulate(brain, world, seed, ticks=TRAIN_TICKS, learn=True)
                train_rows.append({"profile": profile, "world": world, "seed": seed, **data})
            # Evaluate retained weights on an unseen seed / world.
            # Reset volatile activations, but not weights or learner state.
            from src.propagation import baseline_of
            brain.state = {name: baseline_of(name) for name in brain.positions}
            data = simulate(brain, "balanced", 80_000 + seed, learn=False)
            transfer_rows.append({"profile": profile, "seed": seed, **data})
        report["summary"].setdefault("learning_transfer", {})[profile] = {
            "mean_score": round(sum(r["score"] for r in transfer_rows) / len(transfer_rows), 4),
            "mean_learned_updates": round(sum(r["synaptic_learning_updates"]
                                               for r in train_rows) / len(TRAIN_SEEDS), 4),
        }
        report["runs"].extend({**r, "split": "train", "training": True} for r in train_rows)
        report["runs"].extend({**r, "split": "transfer", "training": False} for r in transfer_rows)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = evaluate()
    for split in ("development", "holdout"):
        print(split)
        for profile, summary in report["summary"][split].items():
            print(f" {profile:12s} score={summary['score']:8.2f} "
                  f"food={summary['food_eaten']:6.2f} "
                  f"damage={summary['damage']:7.2f} "
                  f"false_flees={summary['false_flees']:6.2f} "
                  f"alive={summary['ticks_alive']:6.1f}")
    print("Learning transfer:", report["summary"]["learning_transfer"])
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")

if __name__ == "__main__":
    main()
