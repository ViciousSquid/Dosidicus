"""Exact-edits, deterministic probes, safety gates and newborn invariants."""
from experiments.weight_space.experiment import (
    BASELINE_EDGES, CANDIDATE_EDGES, PROBES, SEED_SETS, checks, evaluate,
    make_pair, probe_state, varied_readings,
)
from src.brain_constants import ACTION_NEURONS, INNATE_ACTION_WIRING, LEARNED_ACTIONS

def test_exactly_three_directed_synapses_differ():
    original, candidate = make_pair()
    changed = {e for e in set(original.weights) | set(candidate.weights)
               if original.weights.get(e) != candidate.weights.get(e)}
    assert changed == set(CANDIDATE_EDGES) == set(BASELINE_EDGES)
    for edge in changed:
        assert original.weights.get(edge) == BASELINE_EDGES[edge]
        assert candidate.weights.get(edge) == CANDIDATE_EDGES[edge]
        assert edge[0] in candidate.positions and edge[1] in candidate.positions

def test_candidate_is_real_newborn_wiring_and_learned_actions_still_unwired():
    original, candidate = make_pair()
    assert any(src == "threat_level" and dst == "act_eat" and weight == -0.55
               for src, dst, weight in INNATE_ACTION_WIRING)
    assert {"act_play", "act_shelter", "act_rest"} <= set(LEARNED_ACTIONS)
    assert set(ACTION_NEURONS) <= set(candidate.positions)
    assert original.positions == candidate.positions
    assert not any(target in ("act_play", "act_shelter", "act_rest")
                   for _, target, _ in INNATE_ACTION_WIRING)

def test_same_seed_produces_identical_action_state():
    baseline, candidate = make_pair()
    probe = PROBES[5]
    readings = varied_readings(probe, 17, 5)
    assert readings == varied_readings(probe, 17, 5)
    assert probe_state(baseline, readings) == probe_state(baseline, readings)
    assert probe_state(candidate, readings) == probe_state(candidate, readings)

def test_synaptic_provenance_remains_active():
    baseline, candidate = make_pair()
    assert baseline.ledger is not None and candidate.ledger is not None
    assert len(candidate.weights) == len(baseline.weights) + 1

def test_development_and_holdout_no_regressions():
    report = evaluate()
    checks(report)
    assert set(report["datasets"]) == set(SEED_SETS)
    for split in report["datasets"].values():
        assert all(row["trials"] == 32 for row in split["rows"])
        assert any(row["category"] == "threat" and
                   row["passes"]["candidate"] > row["passes"]["baseline"]
                   for row in split["rows"])
