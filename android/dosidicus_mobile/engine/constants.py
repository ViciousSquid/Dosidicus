"""Canonical neuron definitions for the mobile brain.

Ported from ``src/brain_constants.py`` in the desktop project. Positions are
kept on a 0-1000 virtual canvas so the Kivy brain view can rescale them to any
screen size. The 7 core stat neurons plus the mandatory ``can_see_food`` sensor
are the minimum viable brain; input sensors are driven by game state.
"""

# --- Core stat neurons (7). Values live on a 0-100 scale. ---
CORE_NEURONS = {
    "hunger": (127, 81),
    "happiness": (361, 81),
    "cleanliness": (627, 81),
    "sleepiness": (840, 81),
    "satisfaction": (271, 380),
    "anxiety": (491, 389),
    "curiosity": (701, 386),
}

CORE_NEURON_NAMES = [
    "hunger", "happiness", "cleanliness", "sleepiness",
    "satisfaction", "anxiety", "curiosity",
]

# --- Mandatory sensor: the squid must be able to see food. ---
MANDATORY_SENSOR = {
    "can_see_food": (50, 200),
}

# --- Optional input sensors, fed from game/simulation state. ---
INPUT_SENSORS = {
    "pursuing_food": (150, 50),
    "is_sick": (150, 150),
    "is_sleeping": (250, 50),
    "is_eating": (150, 350),
    "anxiety_stimulus": (50, 350),
}

REQUIRED_NEURONS = {**CORE_NEURONS, **MANDATORY_SENSOR}
REQUIRED_NEURON_NAMES = CORE_NEURON_NAMES + ["can_see_food"]

# Sensor neurons receive their activation from state, not from propagation.
SENSOR_NEURONS = set(MANDATORY_SENSOR) | set(INPUT_SENSORS)

# Neurons that read as on/off rather than a gradient.
BINARY_NEURONS = {
    "can_see_food", "is_eating", "is_sleeping", "is_sick", "pursuing_food",
}

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

VIRTUAL_CANVAS = (900, 500)  # width, height that the positions above map onto


def is_core_neuron(name: str) -> bool:
    return name in CORE_NEURONS


def is_sensor(name: str) -> bool:
    return name in SENSOR_NEURONS


def is_binary(name: str) -> bool:
    return name in BINARY_NEURONS
