"""Canonical neuron definitions for the mobile brain.

Ported from ``src/brain_constants.py`` in the desktop project. Positions are
kept on a 0-1000 virtual canvas so the Kivy brain view can rescale them to any
screen size. The 7 core stat neurons plus the mandatory ``can_see_food`` sensor
are the minimum viable brain; input sensors are driven by game state.
"""

from . import shared  # locate the desktop source package
from src.brain_constants import (
    CORE_STAT_NEURONS as CORE_NEURON_NAMES, REQUIRED_NEURONS,
    INPUT_SENSORS, PURE_INPUT_NEURONS, BINARY_NEURONS, LOGICAL_CANVAS,
    is_social_neuron,
)

CORE_NEURONS = {name: REQUIRED_NEURONS[name] for name in CORE_NEURON_NAMES}
MANDATORY_SENSOR = {"can_see_food": REQUIRED_NEURONS["can_see_food"]}
REQUIRED_NEURON_NAMES = list(REQUIRED_NEURONS)
SENSOR_NEURONS = set(PURE_INPUT_NEURONS)

# Default starting stat values for a freshly hatched squid.
DEFAULT_STATE = {
    "hunger": 25.0,
    "happiness": 80.0,
    "cleanliness": 90.0,
    "sleepiness": 20.0,
    "satisfaction": 70.0,
    "anxiety": 10.0,
    "curiosity": 60.0,
}

VIRTUAL_CANVAS = LOGICAL_CANVAS  # width, height that the positions above map onto


def is_core_neuron(name: str) -> bool:
    return name in CORE_NEURONS


def is_sensor(name: str) -> bool:
    # The live set: a squid can grow sense organs (can_see_squid and the rest).
    return name in PURE_INPUT_NEURONS


def is_social(name: str) -> bool:
    """A grown social neuron - drawn as a hexagon."""
    return is_social_neuron(name)


def is_binary(name: str) -> bool:
    return name in BINARY_NEURONS
