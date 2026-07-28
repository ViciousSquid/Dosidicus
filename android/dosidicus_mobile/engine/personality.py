"""Personality types and their learning modifiers.

Ported from ``src/personality.py``, ``src/personality_traits.py`` and the
``personality_learning_modifiers`` block in ``src/learning.py``. Kept as plain
data so both the brain (learning) and the decision engine can consult it
without any Qt dependency.
"""

from enum import Enum


class Personality(Enum):
    TIMID = "timid"
    ADVENTUROUS = "adventurous"
    LAZY = "lazy"
    ENERGETIC = "energetic"
    INTROVERT = "introvert"
    GREEDY = "greedy"
    STUBBORN = "stubborn"

    @classmethod
    def from_value(cls, value):
        if isinstance(value, cls):
            return value
        for p in cls:
            if p.value == value:
                return p
        return cls.ADVENTUROUS


# Modifiers applied inside Hebbian learning (see brain.strengthen_connection).
PERSONALITY_LEARNING_MODIFIERS = {
    Personality.TIMID: {
        "learning_rate_reduction": 0.5,
        "novelty_sensitivity": 0.3,
        "connection_stability": 0.8,
    },
    Personality.ADVENTUROUS: {
        "learning_rate_boost": 1.5,
        "novelty_sensitivity": 1.2,
        "connection_plasticity": 1.2,
    },
    Personality.GREEDY: {
        "reward_learning_boost": 1.3,
        "exploration_penalty": 0.7,
        "connection_prioritization": ["satisfaction", "hunger"],
    },
    Personality.STUBBORN: {
        "unlearning_resistance": 0.9,
        "new_connection_threshold": 0.6,
        "preference_reinforcement": 1.2,
    },
}

# How quickly each personality's needs drift, ported from the trait modifiers.
PERSONALITY_STAT_MODIFIERS = {
    Personality.TIMID: {"anxiety_growth": 1.3, "curiosity_growth": 0.7},
    Personality.ADVENTUROUS: {"curiosity_growth": 1.5},
    Personality.LAZY: {"energy_drain": 0.6, "movement_speed": 0.8},
    Personality.ENERGETIC: {"energy_drain": 1.4, "movement_speed": 1.3},
    Personality.GREEDY: {"hunger_growth": 1.3, "satisfaction_decay": 1.2},
    Personality.STUBBORN: {"adaptability": 0.3},
    Personality.INTROVERT: {},
}


def describe(personality: Personality) -> str:
    return {
        Personality.TIMID: "Cautious and easily startled; seeks comfort.",
        Personality.ADVENTUROUS: "Bold and curious; learns fast from novelty.",
        Personality.LAZY: "Low energy; drifts and rests often.",
        Personality.ENERGETIC: "Restless and playful; always on the move.",
        Personality.INTROVERT: "Quiet and even-tempered.",
        Personality.GREEDY: "Food-driven; forms strong reward connections.",
        Personality.STUBBORN: "Resists change; slow to rewire.",
    }.get(personality, "")
