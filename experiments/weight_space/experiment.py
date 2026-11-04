"""Paired, deterministic neural-state experiment on actual Dosidicus propagation.

Usage: python -m experiments.weight_space.experiment --json results.json
These are threshold probes, NOT closed-loop survival/learning experiments.
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import random
from pathlib import Path
from collections import defaultdict

import numpy as np
from src.brain_constants import ACTION_NEURONS, ACTION_FIRING_THRESHOLDS
from src.portable_brain import HeadlessBrain, TrainingConfig
from src.propagation import baseline_of, propagate

# Verified from the unmodified 3.2.0_LatestVersion parent.
BASELINE_EDGES = {
    ("threat_level", "act_flee"): 0.55,
    ("anxiety", "act_flee"): 0.25,
    ("threat_level", "act_eat"): None,
}
CANDIDATE_EDGES = {
    ("threat_level", "act_flee"): 1.00,
    ("anxiety", "act_flee"): 0.65,
    ("threat_level", "act_eat"): -0.55,
}
STEPS = 32
SEED_SETS = {
    "development": tuple(range(32)),
    "holdout": tuple(range(10_000, 10_032)),
}
# Expected threshold crossings. These are author-specified requirements,
# not learned/optimised labels and not an external measure of intelligence.
PROBES = (
    {"name": "safe_hungry_food", "readings": {"can_see_food": 100, "hunger": 90, "anxiety": 20, "threat_level": 0},
     "expected": {"act_eat": True, "act_flee": False}, "category": "safety"},
    {"name": "safe_content_food", "readings": {"can_see_food": 100, "hunger": 50, "anxiety": 30, "threat_level": 0},
     "expected": {"act_eat": True, "act_flee": False}, "category": "safety"},
    {"name": "safe_nothing_visible", "readings": {"can_see_food": 0, "hunger": 80, "anxiety": 30, "threat_level": 0},
     "expected": {"act_eat": False, "act_flee": False}, "category": "safety"},
    {"name": "mild_threat_food", "readings": {"can_see_food": 100, "hunger": 85, "anxiety": 60, "threat_level": 15},
     "expected": {"act_eat": True, "act_flee": False}, "category": "safety"},
    {"name": "anxiety_without_threat", "readings": {"can_see_food": 0, "hunger": 60, "anxiety": 95, "threat_level": 0},
     "expected": {"act_eat": False, "act_flee": False}, "category": "safety"},
    {"name": "high_threat_with_food", "readings": {"can_see_food": 100, "hunger": 90, "anxiety": 90, "threat_level": 100},
     "expected": {"act_eat": False, "act_flee": True}, "category": "threat"},
    {"name": "moderate_threat_with_food", "readings": {"can_see_food": 100, "hunger": 90, "anxiety": 90, "threat_level": 75},
     "expected": {"act_eat": False, "act_flee": True}, "category": "threat"},
    {"name": "sustained_threat_without_food", "readings": {"can_see_food": 0, "hunger": 70, "anxiety": 85, "threat_level": 100},
     "expected": {"act_eat": False, "act_flee": True}, "category": "threat"},
    {"name": "startle_without_food", "readings": {"can_see_food": 0, "hunger": 60, "anxiety": 80, "is_startled": 100, "threat_level": 100},
     "expected": {"act_flee": True}, "category": "threat"},
    {"name": "sleep_blocks_feeding", "readings": {"can_see_food": 100, "hunger": 90, "anxiety": 30, "is_sleeping": 100, "threat_level": 0},
     "expected": {"act_eat": False, "act_flee": False}, "category": "safety"},
    {"name": "exhaustion_collapse", "readings": {"sleepiness": 100, "can_see_food": 0, "anxiety": 30, "threat_level": 0},
     "expected": {"act_collapse": True}, "category": "safety"},
)

def make_pair():
    """Use genuine newborn initialisation; reverse precisely 3 edges for control."""
    baseline = HeadlessBrain(TrainingConfig(neurogenesis_enabled=False))
    candidate = HeadlessBrain(TrainingConfig(neurogenesis_enabled=False))
    assert baseline.positions == candidate.positions
    assert baseline.weights == candidate.weights
    for edge, value in CANDIDATE_EDGES.items():
        current = candidate.weights.get(edge)
        assert current is not None and abs(current - value) < 1e-10, (edge, current, value)
    for edge, value in BASELINE_EDGES.items():
        if value is None:
            assert edge in baseline.weights
            baseline.remove_weight(edge, mechanism="experimental_control",
                                   reason="restore absent edge from 3.2.0 parent")
        else:
            baseline.apply_weight_change(edge, value=value,
                                         mechanism="experimental_control",
                                         detail={"source": "3.2.0_LatestVersion"})
    changed = {e for e in set(baseline.weights) | set(candidate.weights)
               if baseline.weights.get(e) != candidate.weights.get(e)}
    assert changed == set(CANDIDATE_EDGES), changed
    return baseline, candidate

def varied_readings(probe, seed, index):
    rng = random.Random(seed * 1_000_003 + index)
    values = dict(probe["readings"])
    for key in ("hunger", "anxiety", "sleepiness", "threat_level"):
        if key in values and values[key] != 0:
            values[key] = max(0.0, min(100.0, values[key] + rng.uniform(-3, 3)))
    return values

def probe_state(brain, readings):
    state = {name: baseline_of(name) for name in brain.positions}
    state.update(readings)
    # Simultaneous neural update using Dosidicus's real shared transfer function.
    for _ in range(STEPS):
        propagate(state, brain.weights, ACTION_NEURONS, smoothing=0.5)
    return {name: float(state[name]) for name in ACTION_NEURONS}

def scored(state, expected):
    return all((state[name] >= ACTION_FIRING_THRESHOLDS[name]) == wanted
               for name, wanted in expected.items())

def evaluate(seeds=SEED_SETS):
    control, candidate = make_pair()
    datasets = {}
    for split, sequence in seeds.items():
        rows = []
        for index, probe in enumerate(PROBES):
            passing = {"baseline": 0, "candidate": 0}
            observed = defaultdict(list)
            for seed in sequence:
                readings = varied_readings(probe, seed, index)
                for label, brain in (("baseline", control), ("candidate", candidate)):
                    actions = probe_state(brain, readings)
                    passing[label] += int(scored(actions, probe["expected"]))
                    for name in probe["expected"]:
                        observed[label, name].append(actions[name])
            rows.append({
                "probe": probe["name"], "category": probe["category"],
                "expected_threshold_crossings": probe["expected"],
                "trials": len(sequence), "passes": passing,
                "mean_activations": {
                    label: {name: round(sum(observed[label, name]) / len(sequence), 5)
                            for name in probe["expected"]}
                    for label in ("baseline", "candidate")
                }
            })
        datasets[split] = {
            "seeds": list(sequence), "total_cases": len(rows) * len(sequence),
            "passed": {label: sum(row["passes"][label] for row in rows)
                       for label in ("baseline", "candidate")},
            "rows": rows,
        }
    return {
        "experiment": "newborn_weights_threat_food_v1",
        "source_ref": "3.2.0_LatestVersion",
        "github_sha": os.environ.get("GITHUB_SHA", "not-set"),
        "python": platform.python_version(), "numpy": np.__version__,
        "protocol": {"steps_per_snapshot": STEPS, "smoothing": 0.5,
                     "learning": False, "neurogenesis": False,
                     "action_outcomes_simulated": False},
        "baseline_weights": {"->".join(k): v for k, v in BASELINE_EDGES.items()},
        "candidate_weights": {"->".join(k): v for k, v in CANDIDATE_EDGES.items()},
        "datasets": datasets,
    }

def checks(report):
    """Predeclared gates, not proof of general cognitive improvement."""
    for split, data in report["datasets"].items():
        assert data["passed"]["candidate"] > data["passed"]["baseline"], (split, data["passed"])
        for row in data["rows"]:
            assert row["passes"]["candidate"] >= row["passes"]["baseline"], (
                split, "regression", row["probe"], row["passes"])

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="write machine-readable full results")
    args = parser.parse_args()
    report = evaluate()
    for split, data in report["datasets"].items():
        print(f"{split}: {data['passed']['baseline']}/{data['total_cases']} baseline; "
              f"{data['passed']['candidate']}/{data['total_cases']} candidate")
        for row in data["rows"]:
            print(f"  {row['probe']:32s} {row['passes']['baseline']}/{row['trials']} -> "
                  f"{row['passes']['candidate']}/{row['trials']}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8")
    checks(report)
    print("PASS: predefined neural-state probe gates met")

if __name__ == "__main__":
    main()
