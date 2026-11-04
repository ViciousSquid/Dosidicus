"""Predeclared guardrails for the high-fatigue voluntary-rest experiment.

This catches (a) the old false metric which counted sleeping after collapse,
(b) spontaneous resting in the untrained/placebo arms,
(c) unnecessary resting while well-rested, and
(d) the spurious high-cleanliness shortcut found in the first experiment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(report: dict) -> None:
    expected_levels = {"22", "65", "94"}
    assert set(report["summary"]) == {
        "ordinary_learning", "motor_probes_only", "motor_probe_teaching",
    }
    for arm, levels in report["summary"].items():
        assert set(levels) == expected_levels
        assert all(levels[k]["episodes"] == 16 for k in expected_levels)
        assert levels["22"]["episodes_with_voluntary_rest"] == 0, (
            arm, "unnecessary voluntary rest while already well rested")
        if arm != "motor_probe_teaching":
            assert all(levels[k]["episodes_with_voluntary_rest"] == 0
                       for k in expected_levels), (
                arm, "the control learned voluntary rest without the mechanism")
        else:
            assert levels["94"]["episodes_with_voluntary_rest"] >= 12, (
                "the experimental learned rest response failed to transfer")
            assert levels["65"]["episodes_with_voluntary_rest"] == 0, (
                "learned rest overgeneralised to moderate fatigue")

    for entry in report["learned_paths"]:
        if entry["arm"] != "motor_probe_teaching":
            continue
        learned = dict(entry["incoming"])
        assert learned.get("sleepiness", 0.0) >= 0.75, (
            entry["train_seed"], "no usable fatigue-to-rest pathway")
        assert learned.get("cleanliness", 0.0) <= 0.0, (
            entry["train_seed"], "training confound: clean tank taught resting")
        # A learned association must be a consequence of actual action trials.
        stats = entry["learning"]["discovery"]
        assert stats["motor_trials_closed"] >= 3
        assert stats["motor_connections_taught"] >= 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    result = json.loads(args.report.read_text())
    validate(result)
    print("Experimental motor discovery guardrails: PASSED")


if __name__ == "__main__":
    main()
