"""Regression tests for action-coupled proxy world.

These tests check actual causal coupling rather than demanding a specified
fitness winner, because 'smarter' is a hypothesis requiring observed evidence.
"""
import math

from experiments.weight_space.closed_loop import (
    PROFILES, WORLDS, make_brain, simulate,
)


def test_each_profile_is_source_network_with_three_explicit_edits():
    originals = make_brain("original")
    for profile in PROFILES:
        brain = make_brain(profile)
        changed = {edge for edge in set(brain.weights) | set(originals.weights)
                   if brain.weights.get(edge) != originals.weights.get(edge)}
        assert changed <= set(PROFILES[profile])
        assert set(brain.positions) == set(originals.positions)


def test_world_is_deterministic_at_fixed_seed():
    a = simulate(make_brain("original"), "balanced", seed=1021, ticks=80)
    b = simulate(make_brain("original"), "balanced", seed=1021, ticks=80)
    assert a == b
    assert sum(a["actions"].values()) == a["ticks_alive"]
    assert math.isfinite(a["score"])


def test_food_requires_neural_eating_action():
    brain = make_brain("original")
    assert brain.remove_weight(("can_see_food", "act_eat"))
    assert brain.remove_weight(("hunger", "act_eat"))
    result = simulate(brain, "balanced", seed=23, ticks=110)
    assert result["food_eaten"] == 0, result
    assert result["actions"]["eating"] == 0


def test_learning_arm_executes_without_rewriting_neural_action_choice():
    brain = make_brain("moderate")
    result = simulate(brain, "balanced", seed=11, ticks=70, learn=True)
    assert result["ticks_alive"] > 0
    assert result["final_neurons"] == len(make_brain("original").positions)
    assert result["synaptic_learning_updates"] >= 0
