"""Reproducible real-trainer experiment and genuine weight-only transfer."""
from experiments.weight_space.trainer_transfer import (
    EVAL_WORLDS, PROFILES, evaluate, new_simulation, transfer_weights_only,
)


def test_original_and_candidate_indeed_have_distinct_birth_synapses():
    original = new_simulation(101, "original", False)
    edited = new_simulation(101, "three_edit", False)
    assert original.brain.positions == edited.brain.positions
    diffs = {
        k for k in set(original.brain.weights) | set(edited.brain.weights)
        if original.brain.weights.get(k) != edited.brain.weights.get(k)
    }
    assert diffs == {
        ("threat_level", "act_flee"),
        ("anxiety", "act_flee"),
        ("threat_level", "act_eat"),
    }


def test_transfer_copies_weights_not_causal_memory():
    source = new_simulation(111, "original", True)
    target = new_simulation(222, "original", False)
    edge = ("can_see_food", "act_eat")
    source.brain.apply_weight_change(edge, value=0.65, mechanism="test")
    assert source.brain.weights[edge] != target.brain.weights[edge]
    transfer_weights_only(source.brain, target.brain)
    assert source.brain.weights == target.brain.weights
    assert target.brain.causal_learning.closed_episodes == 0


def test_small_protocol_runs_with_clean_frozen_evaluation():
    report = evaluate(train_ticks=30, eval_ticks=35,
                      train_seeds=(31,), eval_seeds=(10001,))
    assert set(report["summary"]) == set(PROFILES)
    assert len([r for r in report["runs"] if r["kind"] == "evaluation"]) == (
        len(PROFILES) * len(EVAL_WORLDS) * 2)
    for entry in report["runs"]:
        if entry["kind"] == "evaluation":
            assert entry["metrics"]["hebbian_updates"] == 0
            assert entry["metrics"]["manual_feedings"] == 0
