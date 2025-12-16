from enum import Enum, auto
import random

# --- Enums ---
class NeuronType(Enum):
    INPUT = auto()
    OUTPUT = auto()
    HIDDEN = auto()
    CORE = auto()
    SENSOR = auto()
    CONNECTOR = auto()

# --- Visual Constants ---
CORE_NEURON_RING_COLOR = (255, 215, 0)
INPUT_SENSOR_RING_COLOR = (100, 149, 237)
CUSTOM_NEURON_RING_COLOR = (180, 180, 180)
CONNECTOR_COLOR = (0, 0, 000)
PROTECTED_RING_WIDTH = 3
NORMAL_RING_WIDTH = 2
DEFAULT_LAYER_HEIGHT = 120
DEFAULT_LAYER_SPACING = 150

DEFAULT_COLORS = {
    'core': (150, 150, 220),
    'required': (100, 180, 100),
    'input': (100, 200, 150),
    'output': (220, 150, 150),
    'hidden': (180, 180, 200),
    'sensor': (150, 200, 220),
    'connector': (000, 0, 0)
    
}

LAYER_COLORS = {
    'input': {'fill': (200, 255, 200, 80), 'border': (150, 220, 150, 120)},
    'output': {'fill': (255, 200, 200, 80), 'border': (220, 150, 150, 120)},
    'hidden': {'fill': (230, 230, 255, 80), 'border': (200, 200, 240, 120)}
}

# --- Logic Constants ---
CORE_NEURONS = {
    "hunger": (127, 81), "happiness": (361, 81), "cleanliness": (627, 81),
    "sleepiness": (840, 81), "satisfaction": (271, 380), "anxiety": (491, 389),
    "curiosity": (701, 386),
}
MANDATORY_SENSOR = {"can_see_food": (50, 200)}
REQUIRED_NEURONS = {**CORE_NEURONS, **MANDATORY_SENSOR}
CORE_NEURON_NAMES = list(CORE_NEURONS.keys())
REQUIRED_NEURON_NAMES = CORE_NEURON_NAMES + ["can_see_food"]

INPUT_SENSORS = {
    "external_stimulus": (50, 50), "plant_proximity": (50, 250),
    "threat_level": (50, 350), "pursuing_food": (150, 50),
    "is_sick": (150, 150), "is_fleeing": (150, 250),
    "is_eating": (150, 350), "is_sleeping": (250, 50),
    "is_startled": (250, 150),
}

BINARY_NEURONS = {
    'can_see_food', 'is_eating', 'is_sleeping', 'is_sick',
    'pursuing_food', 'is_fleeing', 'is_startled', 'external_stimulus'
}

def is_core_neuron(name): return name in CORE_NEURONS
def is_required_neuron(name): return name in REQUIRED_NEURONS
def is_input_sensor(name): return name in INPUT_SENSORS
def is_binary_neuron(name): return name in BINARY_NEURONS
def is_protected_neuron(name): return is_required_neuron(name)
def get_neuron_category(name):
    if is_core_neuron(name): return 'core'
    elif name == 'can_see_food': return 'required'
    elif is_input_sensor(name): return 'sensor'
    return 'custom'
def get_missing_required(existing): return [n for n in REQUIRED_NEURONS if n not in existing]

# --- Default Connections ---
DEFAULT_SENSOR_CONNECTIONS = {
    'can_see_food': [('hunger', 0.4, 1.0), ('happiness', 0.2, 0.5), ('satisfaction', 0.15, 0.2)],
    'external_stimulus': [('curiosity', 0.35, 1.0), ('anxiety', 0.15, 0.3)],
    'threat_level': [('anxiety', 0.6, 1.0), ('happiness', -0.3, 0.7), ('curiosity', -0.2, 0.4)],
    'plant_proximity': [('happiness', 0.2, 1.0), ('curiosity', 0.15, 0.5)],
    'is_sick': [('happiness', -0.5, 1.0), ('anxiety', 0.4, 0.8), ('sleepiness', 0.3, 0.6)],
    'is_fleeing': [('anxiety', 0.4, 1.0), ('curiosity', -0.3, 0.7)],
    'is_eating': [('satisfaction', 0.5, 1.0), ('happiness', 0.3, 0.8), ('hunger', -0.4, 1.0)],
    'is_sleeping': [('sleepiness', -0.5, 1.0), ('anxiety', -0.2, 0.6)],
    'is_startled': [('anxiety', 0.5, 1.0), ('curiosity', 0.2, 0.4)],
    'pursuing_food': [('hunger', 0.2, 1.0), ('curiosity', 0.25, 0.5)],
}

def get_default_connections_for_sensor(sensor_name: str) -> list:
    if sensor_name not in DEFAULT_SENSOR_CONNECTIONS:
        return []
    connections = []
    for target, weight, probability in DEFAULT_SENSOR_CONNECTIONS[sensor_name]:
        if random.random() < probability:
            connections.append((target, weight))
    return connections