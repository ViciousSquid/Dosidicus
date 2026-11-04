"""Descriptive robustness sweep of the newborn action bank, not an optimiser.

144 fixed snapshots: 6 threat levels x 4 anxieties x 3 hungers x 2 food states.
The exact same input passes through original and edited shared propagation.
"""
from __future__ import annotations
import argparse
import json
import os
from collections import defaultdict
from itertools import product
from pathlib import Path

from src.brain_constants import ACTION_FIRING_THRESHOLDS
from .experiment import make_pair, probe_state

THREATS = (0, 15, 30, 50, 75, 100)
ANXIETIES = (20, 50, 80, 95)
HUNGERS = (40, 80, 95)
FOODS = (0, 100)

def decision(actions):
    eat = actions["act_eat"] >= ACTION_FIRING_THRESHOLDS["act_eat"]
    flee = actions["act_flee"] >= ACTION_FIRING_THRESHOLDS["act_flee"]
    if eat and flee:
        return "both"
    if eat:
        return "eat_only"
    if flee:
        return "flee_only"
    return "neither"

def sweep():
    original, candidate = make_pair()
    cases = []
    totals = defaultdict(lambda: defaultdict(int))
    for threat, anxiety, hunger, food in product(THREATS, ANXIETIES, HUNGERS, FOODS):
        readings = {"threat_level": threat, "anxiety": anxiety,
                    "hunger": hunger, "can_see_food": food}
        record = {"inputs": readings}
        for label, brain in (("baseline", original), ("candidate", candidate)):
            actions = probe_state(brain, readings)
            outcome = decision(actions)
            record[label] = {"outcome": outcome,
                             "eat_activation": round(actions["act_eat"], 5),
                             "flee_activation": round(actions["act_flee"], 5)}
            totals[f"threat={threat},food={food}"][label + ":" + outcome] += 1
        cases.append(record)
    return {
        "experiment": "descriptive_newborn_input_grid_v1",
        "source_commit": os.environ.get("GITHUB_SHA", "not-set"),
        "method": "unlabelled fixed-state grid; no optimisation, learning, game or random perturbation",
        "grid": {"threat_levels": THREATS, "anxiety_levels": ANXIETIES,
                 "hunger_levels": HUNGERS, "food_visible": FOODS},
        "case_count": len(cases),
        "outcome_categories": ["eat_only", "flee_only", "both", "neither"],
        "totals_by_stratum": {k: dict(v) for k, v in totals.items()},
        "cases": cases,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = sweep()
    print("THREAT  FOOD  | BASELINE: eat flee both neither | EDITED: eat flee both neither")
    for threat, food in product(THREATS, FOODS):
        counts = report["totals_by_stratum"][f"threat={threat},food={food}"]
        def block(label):
            return " ".join(str(counts.get(label + ":" + kind, 0)).rjust(2)
                            for kind in ("eat_only", "flee_only", "both", "neither"))
        print(f"{threat:6} {food:5}  | {block('baseline')} | {block('candidate')}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    assert report["case_count"] == 144

if __name__ == "__main__":
    main()
