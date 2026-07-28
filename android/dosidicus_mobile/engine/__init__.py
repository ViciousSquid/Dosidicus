"""Portable, GUI-free port of the Dosidicus STRINg cognitive engine.

Nothing in this package imports PyQt5 (or Kivy). It is pure Python + NumPy so
it can be exercised in tests, in a headless trainer, or driven by any UI.
"""

from .personality import Personality, PERSONALITY_LEARNING_MODIFIERS
from .brain import NeuralBrain
from .squid import Squid
from .simulation import Simulation
from .achievements import AchievementManager, ACHIEVEMENTS

__all__ = [
    "Personality",
    "PERSONALITY_LEARNING_MODIFIERS",
    "NeuralBrain",
    "Squid",
    "Simulation",
    "AchievementManager",
    "ACHIEVEMENTS",
]
