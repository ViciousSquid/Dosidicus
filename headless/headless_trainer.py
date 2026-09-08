#!/usr/bin/env python3
"""
Dosidicus-2 Headless Brain Trainer

Allows training custom neural network brains without GUI overhead.
Supports accelerated time, custom brain loading, and state persistence.

Usage:
    python headless_trainer.py --brain custom_brain.json --ticks 10000 --output trained_brain.json
    python headless_trainer.py --brain custom_brain.json --duration 3600 --speed 100
    python headless_trainer.py --list-scenarios
    python headless_trainer.py --brain my_brain.json --scenario stress_test

Author: Headless training system for Dosidicus-2
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from heapq import nlargest

# ============================================================================
# THE REAL ENGINE
#
# The trainer used to carry its own copies of everything: its own neuron
# categories, its own propagation (src_val * weight * 0.1, no neutral baseline,
# clamped to -100..100), its own Hebbian rule (a non-negative product, so it
# could never learn an aversion) and its own neurogenesis thresholds. A brain
# trained here therefore did not behave the same way when the squid ran it,
# which makes headless training worse than useless.
#
# It now imports the same modules the game does. None of them need Qt.
# ============================================================================
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.brain_constants import (  # noqa: E402
    CORE_STAT_NEURONS as CORE_NEURONS,
    PURE_INPUT_NEURONS as PURE_INPUTS,
    INPUT_SENSORS as _INPUT_SENSOR_POSITIONS,
    INNATE_CONNECTIONS,
    INNATE_ACTION_WIRING,
    action_competition_wiring,
    ACTION_NEURONS,
    newborn_neurons,
    action_resting_level,
    is_network_driven,
)
from src.propagation import ExternallyDriven, propagate  # noqa: E402
from src.plasticity import PlasticityEngine, PlasticityConfig  # noqa: E402
from src.capability import CapabilityMonitor  # noqa: E402
from src.causal_learning import ActionOutcomeLedger  # noqa: E402
from src.neural_provenance import CausalLedger, RecordedSynapses  # noqa: E402
from src.consolidation import ConsolidationManager  # noqa: E402
from src.neurogenesis import EnhancedNeurogenesis  # noqa: E402
from src.learning import LearningConfig  # noqa: E402

INPUT_SENSORS = set(_INPUT_SENSOR_POSITIONS) | {"can_see_food"}


class Personality(Enum):
    """Squid personality types"""
    TIMID = "timid"
    ADVENTUROUS = "adventurous"
    GREEDY = "greedy"
    STUBBORN = "stubborn"
    ENERGETIC = "energetic"


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class TrainingConfig:
    """Configuration for headless training"""
    # Learning parameters
    learning_rate: float = 0.1
    weight_decay: float = 0.01
    max_hebbian_pairs: int = 2
    hebbian_interval: int = 30  # ticks between hebbian updates
    
    # Neurogenesis parameters
    neurogenesis_enabled: bool = True
    neurogenesis_cooldown: int = 60  # ticks
    max_neurons: int = 100
    novelty_threshold: float = 3.0
    stress_threshold: float = 1.2
    reward_threshold: float = 3.5
    
    # Simulation parameters
    decay_rate: float = 0.95
    noise_range: float = 0.5
    
    # Scenarios
    food_spawn_chance: float = 0.02
    poop_spawn_chance: float = 0.01
    startle_chance: float = 0.005

    # Reproducibility. With a seed set, a run is deterministic: the same seed,
    # brain and tick count produce the same trained brain, byte for byte. That
    # is what makes a result here something another person can check rather
    # than something they have to take your word for.
    seed: Optional[int] = None

    # Hatch with no synapses and only the eight required neurons, instead of
    # the full newborn brain with its innate reflexes. A blank brain is the
    # control condition: anything it ends up knowing, it learned here.
    blank: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrainingConfig':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TrainingScenario:
    """Predefined training scenarios"""
    name: str
    description: str
    duration_ticks: int
    config_overrides: Dict = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)


TRAINING_SCENARIOS = {
    "balanced": TrainingScenario(
        name="Balanced Training",
        description="Standard balanced training with normal event rates",
        duration_ticks=10000,
        config_overrides={},
        events=[]
    ),
    "stress_test": TrainingScenario(
        name="Stress Test",
        description="High anxiety/stress conditions to develop resilience neurons",
        duration_ticks=5000,
        config_overrides={
            "startle_chance": 0.02,
            "food_spawn_chance": 0.005,
        },
        events=[
            {"tick": 100, "type": "set_state", "state": {"anxiety": 80}},
            {"tick": 500, "type": "startle"},
            {"tick": 1000, "type": "set_state", "state": {"hunger": 90}},
        ]
    ),
    "reward_rich": TrainingScenario(
        name="Reward-Rich Environment",
        description="Frequent positive outcomes to develop reward pathways",
        duration_ticks=8000,
        config_overrides={
            "food_spawn_chance": 0.08,
            "poop_spawn_chance": 0.001,
        },
        events=[
            {"tick": 200, "type": "feed"},
            {"tick": 600, "type": "feed"},
            {"tick": 1200, "type": "feed"},
        ]
    ),
    "novelty_exploration": TrainingScenario(
        name="Novelty Exploration",
        description="High curiosity environment with new objects",
        duration_ticks=6000,
        config_overrides={
            "startle_chance": 0.001,
        },
        events=[
            {"tick": 100, "type": "set_state", "state": {"curiosity": 85}},
            {"tick": 300, "type": "new_object"},
            {"tick": 800, "type": "new_object"},
            {"tick": 1500, "type": "new_object"},
        ]
    ),
    "endurance": TrainingScenario(
        name="Endurance Training",
        description="Long-duration training with varied conditions",
        duration_ticks=50000,
        config_overrides={},
        events=[]
    ),
}


# ============================================================================
# HEADLESS SQUID (minimal state tracking)
# ============================================================================

class HeadlessSquid:
    """Minimal squid implementation for headless training"""
    
    def __init__(self, personality: Personality = None):
        self.personality = personality or random.choice(list(Personality))
        
        # Core stats (0-100)
        self.hunger = 50.0
        self.happiness = 50.0
        self.cleanliness = 80.0
        self.sleepiness = 20.0
        self.health = 100.0
        
        # Goal neurons
        self.satisfaction = 50.0
        self.anxiety = 10.0
        self.curiosity = 55.0
        
        # Boolean states
        self.is_sick = False
        self.is_sleeping = False
        self.is_eating = False
        self.is_fleeing = False
        self.is_startled = False
        self.pursuing_food = False
        
        # Position (normalized 0-1)
        self.x = 0.5
        self.y = 0.5
        self.direction = "right"
        
        # Status
        self.status = "roaming"
        
        # Tracking
        self.food_visible = False
        self.plant_nearby = False
        self.time_since_ate = 0
        self.time_since_slept = 0
        
    def get_state_dict(self) -> Dict[str, Any]:
        """Get current state as dictionary for brain updates"""
        return {
            "hunger": self.hunger,
            "happiness": self.happiness,
            "cleanliness": self.cleanliness,
            "sleepiness": self.sleepiness,
            "satisfaction": self.satisfaction,
            "anxiety": self.anxiety,
            "curiosity": self.curiosity,
            "is_sick": self.is_sick,
            "is_sleeping": self.is_sleeping,
            "is_eating": self.is_eating,
            "pursuing_food": self.pursuing_food,
            "is_fleeing": self.is_fleeing,
            "is_startled": self.is_startled,
            "can_see_food": 100.0 if self.food_visible else 0.0,
            "plant_proximity": 100.0 if self.plant_nearby else 0.0,
            "external_stimulus": 0.0,
            "direction": self.direction,
            "position": (self.x, self.y),
            "personality": self.personality.value,
            "status": self.status,
        }
    
    def update(self, dt: float = 1.0):
        """Update squid state for one tick"""
        # Natural stat changes
        self.hunger = min(100, self.hunger + 0.1 * dt)
        self.sleepiness = min(100, self.sleepiness + 0.05 * dt)
        self.cleanliness = max(0, self.cleanliness - 0.02 * dt)
        
        # Update time trackers
        self.time_since_ate += dt
        if not self.is_sleeping:
            self.time_since_slept += dt
        
        # Personality effects
        if self.personality == Personality.GREEDY:
            self.hunger = min(100, self.hunger + 0.05 * dt)
        elif self.personality == Personality.ENERGETIC:
            self.sleepiness = max(0, self.sleepiness - 0.02 * dt)
        elif self.personality == Personality.TIMID:
            if self.plant_nearby:
                self.anxiety = max(0, self.anxiety - 0.1 * dt)
        
        # Anxiety from needs
        if self.hunger > 70:
            self.anxiety = min(100, self.anxiety + 0.1 * dt)
        if self.cleanliness < 30:
            self.anxiety = min(100, self.anxiety + 0.05 * dt)
            
        # Satisfaction from good states
        if self.hunger < 30 and self.cleanliness > 70:
            self.satisfaction = min(100, self.satisfaction + 0.1 * dt)
        else:
            self.satisfaction = max(0, self.satisfaction - 0.02 * dt)
            
        # Happiness dynamics
        if self.anxiety > 50:
            self.happiness = max(0, self.happiness - 0.1 * dt)
        elif self.satisfaction > 60:
            self.happiness = min(100, self.happiness + 0.05 * dt)
            
        # Curiosity wanders
        self.curiosity += random.uniform(-0.5, 0.5) * dt
        self.curiosity = max(0, min(100, self.curiosity))
        
        # Clear temporary states
        if self.is_startled:
            if random.random() < 0.1:
                self.is_startled = False
                self.is_fleeing = False
                
        if self.is_eating:
            if random.random() < 0.2:
                self.is_eating = False
                self.pursuing_food = False
                
        # Sleep behavior
        if self.sleepiness > 90 and not self.is_sleeping:
            self.is_sleeping = True
            self.status = "sleeping"
        elif self.is_sleeping and self.sleepiness < 20:
            self.is_sleeping = False
            self.time_since_slept = 0
            self.status = "roaming"
            
        # Movement simulation
        if not self.is_sleeping and not self.is_eating:
            self.x += random.uniform(-0.02, 0.02)
            self.y += random.uniform(-0.02, 0.02)
            self.x = max(0, min(1, self.x))
            self.y = max(0, min(1, self.y))
            
    def feed(self):
        """Feed the squid"""
        self.hunger = max(0, self.hunger - 30)
        self.happiness = min(100, self.happiness + 10)
        self.satisfaction = min(100, self.satisfaction + 15)
        self.is_eating = True
        self.time_since_ate = 0
        self.status = "eating"
        
    def startle(self):
        """Startle the squid"""
        self.is_startled = True
        self.is_fleeing = True
        self.anxiety = min(100, self.anxiety + 20)
        self.happiness = max(0, self.happiness - 10)
        self.status = "fleeing!"
        
    def clean(self):
        """Clean the environment"""
        self.cleanliness = min(100, self.cleanliness + 40)
        self.anxiety = max(0, self.anxiety - 5)


# ============================================================================
# HEADLESS BRAIN
# ============================================================================

class HeadlessBrain(RecordedSynapses, ExternallyDriven):
    """
    Neural network brain without GUI dependencies.
    Handles state updates, Hebbian learning, and neurogenesis.
    """
    
    def __init__(self, config: TrainingConfig = None):
        self.config = config or TrainingConfig()

        # Neural state
        self.state: Dict[str, float] = {}
        self.weights: Dict[Tuple[str, str], float] = {}
        self.positions: Dict[str, Tuple[float, float]] = {}
        self.neuron_shapes: Dict[str, str] = {}
        self.state_colors: Dict[str, tuple] = {}

        # Custom neurons tracking
        self.custom_neurons: Set[str] = set()
        self.new_neurons: Set[str] = set()
        self.connector_neurons: Set[str] = set()
        self.visible_neurons: Set[str] = set()

        # Learning tracking
        self.last_hebbian_pairs: List[Tuple[str, str]] = []
        self.weight_history: List[Dict] = []

        # Neurogenesis tracking
        self.neurogenesis_data = {
            'new_neurons': [],
            'last_neuron_time': 0,
            'neurons_created': 0,
            'functional_neurons': {},
            'new_neurons_details': {},
        }
        self.neurogenesis_highlight = {'neuron': None, 'start_time': 0, 'duration': 0}
        self.communication_events: Dict[str, float] = {}
        self.weight_animations: List[Dict] = []
        self.excluded_neurons: List[str] = ['is_sick', 'is_eating', 'pursuing_food',
                                            'direction', 'is_sleeping']
        # Neurons written from outside the forward pass - see
        # src/propagation.ExternallyDriven.
        self.action_representations: Dict[str, str] = {}
        self.externally_driven: Set[str] = set()
        self.last_neurogenesis_tick = 0
        # One tick is one second of the squid's life. The trainer runs
        # thousands of them per real second, so every pacing rule expressed in
        # seconds reads this instead of the wall clock - otherwise a whole
        # training run finishes inside one growth cooldown and the brain can
        # never develop.
        self.sim_seconds = 0.0
        self.pruning_enabled = True
        self.tamagotchi_logic = None
        self.learning_rate = self.config.learning_rate

        # Output bindings (for behaviors)
        self.output_bindings: List[Dict] = []

        # ---- the engine, exactly as the game runs it ----------------------
        learning_config = LearningConfig()
        learning_config.hebbian['base_learning_rate'] = self.config.learning_rate
        learning_config.hebbian['weight_decay'] = self.config.weight_decay
        learning_config.neurogenesis['max_neurons'] = self.config.max_neurons
        learning_config.neurogenesis['cooldown'] = self.config.neurogenesis_cooldown
        self.learning_config = learning_config

        self.ledger = CausalLedger(self)
        self.capability = CapabilityMonitor(self)
        self.causal_learning = ActionOutcomeLedger(self)
        self.plasticity = PlasticityEngine(
            PlasticityConfig.from_learning_config(learning_config))
        self.consolidation = ConsolidationManager(self)
        self.enhanced_neurogenesis = EnhancedNeurogenesis(self, learning_config)
        self.enhanced_neurogenesis.clock = lambda: self.sim_seconds
        # The monitor reads the same simulated clock, so "a deficit must
        # persist for 20 seconds" means 20 simulated seconds rather than being
        # switched off - which is what the trainer used to have to do.
        self.capability.clock = lambda: self.sim_seconds
        self.causal_learning.clock = lambda: self.sim_seconds
        # Spike timing is the one mechanism that is ABOUT time. On the wall
        # clock a trainer stepping 1 500 ticks a second presents every spike as
        # arriving under a millisecond after the last, and STDP computes
        # exactly zero for every synapse.
        self.plasticity.clock = lambda: self.sim_seconds
        self.experience_buffer = self.enhanced_neurogenesis.experience_buffer

        # Initialize default state
        self._initialize_default_state()

    # ------------------------------------------------------------------
    # The surface the shared engine reads. A BrainWidget provides these
    # through Qt; here they are plain data and no-ops, which is the whole
    # point of keeping the engine Qt-free.
    # ------------------------------------------------------------------
    @property
    def neuron_positions(self) -> Dict[str, Tuple[float, float]]:
        """The engine's name for `positions`. One dict, two names."""
        return self.positions

    @neuron_positions.setter
    def neuron_positions(self, value):
        self.positions = value

    def update(self):
        pass

    def mark_render_dirty(self):
        pass

    def sync_connections_from_weights(self):
        pass

    def log_neurogenesis_event(self, neuron_name, event_type, reason=None, details=None):
        self.weight_history.append({'event': event_type, 'neuron': neuron_name,
                                    'details': details or {}, 'tick': time.time()})

    def is_connector_neuron(self, name: str) -> bool:
        return name in self.connector_neurons or self.neuron_shapes.get(name) == 'hexagon'

    def is_new_neuron(self, name: str, newness_duration_sec: float = 300) -> bool:
        return name in self.new_neurons

    def get_neuron_degree(self, name: str) -> int:
        return sum(1 for edge in self.weights if name in edge)

    def find_orphan_neurons(self) -> List[str]:
        connected = {n for edge in self.weights for n in edge}
        return [n for n in self.positions
                if n not in connected and n not in self.excluded_neurons]

    def add_weight_animation(self, *args, **kwargs):
        pass

    # apply_weight_change / remove_weight / explain_* come from
    # RecordedSynapses. The trainer used to carry its own copy of the write
    # path, which is the same duplication in miniature that this refactor
    # exists to remove.
    def _connector_neuron_names(self) -> Set[str]:
        return {name for name, fn in
                self.enhanced_neurogenesis.functional_neurons.items()
                if getattr(fn, 'neuron_type', '') == 'connector'}
        
    def _initialize_default_state(self):
        """Initialize with default neuron structure.

        Hatched from brain_constants.newborn_neurons(), the same definition the
        game uses, so "a brain trained without the GUI starts from the same
        place the squid does" stays true. This used to carry its own copy of
        the eight default positions, which silently stopped matching the game
        the moment a squid started hatching with action neurons - and a brain
        trained here would then have had no way to express a behaviour at all.
        """
        if self.config.blank:
            self._initialize_blank_state()
            return

        for name, pos in newborn_neurons().items():
            self.positions[name] = pos
            if name in CORE_NEURONS:
                self.state[name] = 50.0
            elif name in ACTION_NEURONS:
                self.state[name] = action_resting_level(name)
            elif name in INPUT_SENSORS:
                self.state[name] = 0.0
            else:
                self.state[name] = 50.0

        # The instincts of the species, from the one table that holds them.
        innate = (tuple(INNATE_CONNECTIONS) + tuple(INNATE_ACTION_WIRING)
                  + action_competition_wiring())
        for src, dst, weight in innate:
            if src in self.positions and dst in self.positions:
                self.apply_weight_change(
                    (src, dst), value=float(weight), mechanism='innate',
                    detail={'note': "this squid was born with it"}, create=True)
            
    def _initialize_blank_state(self):
        """The eight required neurons, no synapses, no instincts.

        The control condition for an experiment: a brain that has been given
        nothing, so that anything it is found to know at the end of a run was
        learned during that run. Contrast _initialize_default_state(), which
        hatches the newborn a real squid gets - reflexes included.
        """
        from src.brain_constants import REQUIRED_NEURONS

        for name, pos in REQUIRED_NEURONS.items():
            self.positions[name] = pos
            self.state[name] = 0.0 if name in INPUT_SENSORS else 50.0

    def load_brain(self, brain_data: Dict) -> bool:
        """Load a brain from dictionary (JSON structure)"""
        try:
            # Clear existing
            self.state.clear()
            self.weights.clear()
            self.positions.clear()
            self.custom_neurons.clear()
            
            # Load positions/neurons — accept both 'positions' (headless export)
            # and 'neurons' (Designer / game format).
            positions_raw = brain_data.get('positions', brain_data.get('neurons', {}))
            for name, pos in positions_raw.items():
                if isinstance(pos, dict):
                    # Designer format: {'position': [x, y], 'is_custom': bool}
                    # Headless export format: {'x': float, 'y': float, 'is_custom': bool}
                    if 'position' in pos:
                        p = pos['position']
                        self.positions[name] = (float(p[0]), float(p[1]))
                    elif 'x' in pos and 'y' in pos:
                        self.positions[name] = (float(pos['x']), float(pos['y']))
                    else:
                        self.positions[name] = (0.0, 0.0)
                    if pos.get('is_custom', False):
                        self.custom_neurons.add(name)
                elif isinstance(pos, (list, tuple)) and len(pos) >= 2:
                    self.positions[name] = (float(pos[0]), float(pos[1]))
                else:
                    # Fallback: unknown shape — park at origin rather than
                    # storing a raw unsupported value.
                    self.positions[name] = (0.0, 0.0)
                    
                # Initialize state
                if name in CORE_NEURONS:
                    self.state[name] = 50.0
                elif name in INPUT_SENSORS:
                    self.state[name] = 0.0
                else:
                    self.state[name] = 50.0
                    self.custom_neurons.add(name)
                    
            # Load weights/connections
            # Accept list format (Designer) and dict format (headless export).
            weights_data = brain_data.get('weights', brain_data.get('connections', {}))
            if isinstance(weights_data, dict):
                for key, weight in weights_data.items():
                    # Handle string keys like "hunger,satisfaction" or "hunger->satisfaction"
                    if isinstance(key, str):
                        if '->' in key:
                            parts = key.split('->')
                        else:
                            parts = key.replace('(', '').replace(')', '').replace("'", "").split(',')
                        if len(parts) >= 2:
                            src = parts[0].strip()
                            dst = parts[1].strip()
                            self.weights[(src, dst)] = float(weight)
                    else:
                        self.weights[tuple(key)] = float(weight)
            elif isinstance(weights_data, list):
                for conn in weights_data:
                    if isinstance(conn, dict):
                        src = conn.get('source', conn.get('from', ''))
                        dst = conn.get('target', conn.get('to', ''))
                        w = conn.get('weight', 0.5)
                        if src and dst:
                            self.weights[(src, dst)] = float(w)
                    elif isinstance(conn, (list, tuple)) and len(conn) >= 2:
                        self.weights[(conn[0], conn[1])] = float(conn[2]) if len(conn) > 2 else 0.5
                        
            # Load the brain's account of itself, so a loaded brain can still
            # be asked why it is the way it is.
            self._load_provenance(brain_data)

            # Load shapes
            self.neuron_shapes = brain_data.get('neuron_shapes', {})
            
            # Load output bindings
            self.output_bindings = brain_data.get('output_bindings', [])

            self.action_representations = {}
            self.externally_driven = set()
            for action, neuron in (brain_data.get('action_representations') or {}).items():
                if neuron in self.positions:
                    self.represent_action(str(action), str(neuron))
            
            # Load neurogenesis data if present
            if 'neurogenesis_data' in brain_data:
                self.neurogenesis_data.update(brain_data['neurogenesis_data'])
                
            print(f"✓ Loaded brain: {len(self.positions)} neurons, {len(self.weights)} connections")
            return True
            
        except Exception as e:
            print(f"✗ Error loading brain: {e}")
            return False
            
    def load_brain_file(self, filepath: str) -> bool:
        """Load brain from JSON file"""
        try:
            with open(filepath, 'r') as f:
                brain_data = json.load(f)
            return self.load_brain(brain_data)
        except Exception as e:
            print(f"✗ Error loading brain file: {e}")
            return False
            
    def export_brain(self) -> Dict:
        """
        Export brain in the Designer/game format understood by
        custom_brain_loader.BrainLoader._parse() (Format 2: neurons dict +
        connections list).  This ensures trained brains can be loaded
        straight back into the game without any manual conversion.
        """
        # neurons dict — position as list, is_custom flag
        neurons = {}
        for name, pos in self.positions.items():
            neurons[name] = {
                'position': [pos[0], pos[1]],
                'is_custom': name in self.custom_neurons,
            }

        # connections as a list of {source, target, weight} dicts
        # (BrainLoader._parse() Format 2 expects this exact structure)
        connections = []
        for (src, dst), w in self.weights.items():
            connections.append({'source': src, 'target': dst, 'weight': float(w)})

        return {
            'metadata': {
                'exported_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'exported_by': 'headless_trainer',
                'neuron_count': len(self.positions),
                'connection_count': len(self.weights),
                'custom_neuron_count': len(self.custom_neurons),
            },
            # ── game-loader-compatible keys ──────────────────────────────────
            'neurons': neurons,        # _parse() checks for 'neurons' key
            'connections': connections, # _parse() Format 2: list of dicts
            # ────────────────────────────────────────────────────────────────
            'neuron_shapes': dict(self.neuron_shapes),
            # Which neurons stand for which of the squid's own actions. A brain
            # that grew one of these to resolve a confounded cause needs it, or
            # the neuron arrives with nothing driving it.
            'action_representations': dict(self.action_representations),
            'output_bindings': self.output_bindings,
            'state': {k: v for k, v in self.state.items()},
            'neurogenesis_data': {
                'neurons_created': self.neurogenesis_data.get('neurons_created', 0),
                'stress_neurons':  self.stress_neuron_count,
                'novelty_neurons': self.novelty_neuron_count,
                'reward_neurons':  self.reward_neuron_count,
            },
            # The brain's account of ITSELF, under the same keys the game's
            # save uses. Without these a brain trained here arrives with an
            # evolved network and no idea why any of it is the way it is: you
            # could read its weights but not ask it what it learned, from what
            # experience, or what it still cannot do. For a trainer whose whole
            # point is producing brains other people examine, that is the more
            # important half of the file.
            **self._export_provenance(),
        }

    _PROVENANCE_PARTS = (
        ('provenance', 'ledger'),
        ('causal_learning', 'causal_learning'),
        ('capability', 'capability'),
        ('plasticity', 'plasticity'),
        ('consolidation', 'consolidation'),
    )

    def _export_provenance(self) -> Dict:
        """Serialise every part of the brain that can explain itself."""
        out = {}
        for key, attribute in self._PROVENANCE_PARTS:
            owner = getattr(self, attribute, None)
            if owner is None or not hasattr(owner, 'to_dict'):
                continue
            try:
                out[key] = owner.to_dict()
            except Exception as exc:
                print(f"⚠️  Could not export {key}: {type(exc).__name__}: {exc}")
        return out

    def _load_provenance(self, brain_data: Dict) -> None:
        """Restore the brain's account of itself from a file."""
        for key, attribute in self._PROVENANCE_PARTS:
            payload = brain_data.get(key)
            owner = getattr(self, attribute, None)
            if not payload or owner is None or not hasattr(owner, 'from_dict'):
                continue
            try:
                owner.from_dict(payload)
            except Exception as exc:
                print(f"⚠️  Could not restore {key}: {type(exc).__name__}: {exc}")
        
    def save_brain(self, filepath: str) -> bool:
        """Save brain to JSON file"""
        try:
            brain_data = self.export_brain()
            with open(filepath, 'w') as f:
                json.dump(brain_data, f, indent=2)
            print(f"✓ Saved brain to {filepath}")
            return True
        except Exception as e:
            print(f"✗ Error saving brain: {e}")
            return False
            
    def advance_clock(self, seconds: float = 1.0) -> float:
        """One tick is one second of the squid's life.

        Everything paced in seconds - growth cooldowns, how long a deficit must
        persist - reads this rather than the wall clock, so a run of 100 000
        ticks is a hundred thousand seconds of living even though it finishes
        in under a minute.
        """
        self.sim_seconds += float(seconds)
        return self.sim_seconds

    def update_state(self, squid_state: Dict[str, Any]):
        """Update brain state from squid state"""
        for key, value in squid_state.items():
            if key in self.positions or key in self.state:
                if isinstance(value, bool):
                    self.state[key] = 100.0 if value else 0.0
                elif isinstance(value, (int, float)):
                    self.state[key] = float(value)
                    
    def propagate(self):
        """One timestep, through the project's single transfer function."""
        # Neurons the world writes go first, then learning evidence, exactly
        # as BrainWidget does it, so a brief event contributes to the next
        # commit instead of being invisible.
        self.drive_external_neurons()
        self.observe_for_learning()

        targets = [n for n in self.positions
                   if is_network_driven(n) and n not in self.excluded_neurons
                   and n not in self.externally_driven]
        if not targets:
            return {}

        strengths = {name: getattr(fn, 'strength_multiplier', 1.0)
                     for name, fn in
                     self.enhanced_neurogenesis.functional_neurons.items()}
        return propagate(self.state, self.weights, targets, strengths=strengths)

    def observe_for_learning(self) -> int:
        """Feed one tick of evidence to every learning mechanism."""
        try:
            self.capability.observe(self.state)
        except Exception:
            pass
        try:
            self.causal_learning.on_tick(self.state)
        except Exception:
            pass
        candidates = self.plasticity.eligible_neurons(
            self.positions.keys(), self.excluded_neurons,
            self._connector_neuron_names())
        return self.plasticity.observe(self.state, candidates)

    def perform_hebbian_learning(self) -> List[Tuple[str, str]]:
        """Commit one plasticity cycle, using the game's own rule.

        The old body scored pairs by v1 + v2 + random noise and applied
        delta = lr * (v1/100) * (v2/100), which is never negative - so a brain
        trained here could not develop a single inhibitory synapse, and an
        avoidance behaviour IS an inhibitory synapse.
        """
        result = self.plasticity.commit(
            weights=self.weights,
            neuron_names=list(self.positions.keys()),
            excluded=self.excluded_neurons,
            connectors=self._connector_neuron_names(),
            new_neurons=self.new_neurons,
            externally_driven=self.externally_driven)

        updated = []
        for edge, update in (result.get('weight_updates') or {}).items():
            mechanism = 'stdp' if abs(update.get('stdp_delta', 0.0) or 0.0) > \
                abs(update.get('hebbian_delta', 0.0) or 0.0) else 'hebbian'
            if self.apply_weight_change(
                    edge, value=update['new_weight'], mechanism=mechanism,
                    detail={'correlation': update.get('mean_covariance'),
                            'samples': update.get('samples'),
                            'hebbian_delta': update.get('hebbian_delta'),
                            'stdp_delta': update.get('stdp_delta'),
                            'stdp_direction': update.get('stdp_direction')},
                    create=True):
                updated.append(edge)
                self.weight_history.append({
                    'pair': edge, 'old': update['old_weight'],
                    'new': update['new_weight'], 'tick': time.time()})

        self.last_hebbian_pairs = [tuple(sorted(e)) for e in updated]
        return updated

    def consolidate(self, is_sleeping: bool):
        """Sleep replay and synaptic homeostasis, same engine as the game."""
        try:
            return self.consolidation.on_tick(is_sleeping, self.state)
        except Exception:
            return None

    def check_neurogenesis(self, squid_state: Dict, tick: int) -> Optional[str]:
        """Grow structure when the network persistently cannot cope.

        The old body asked "is anxiety over 70? is curiosity over 75?" - a
        fourth copy of the event thresholds the game has since abandoned. It
        now asks the same question the game does, through the same monitor and
        the same engine: what can this network not represent, regulate or
        express?
        """
        if not self.config.neurogenesis_enabled:
            return None

        if tick - self.last_neurogenesis_tick < self.config.neurogenesis_cooldown:
            return None

        try:
            self.capability.evaluate()
        except Exception as exc:
            print(f"[Capability] evaluation failed: {type(exc).__name__}: {exc}")
            return None

        engine = self.enhanced_neurogenesis
        deficit = engine.find_deficit(self.state)
        if deficit is None:
            return None

        context = engine.capture_experience_context(
            trigger_type=deficit.suggested_type,
            brain_state=self.state,
            recent_actions=[squid_state.get('status', 'roaming')],
            environment={'headless': True})
        # Pass the diagnosis through rather than letting the engine re-run it,
        # exactly as BrainWidget.check_neurogenesis_triggers does. A second
        # reading of a state that has moved on could disagree with the first,
        # and then the birth record would name a different deficit from the one
        # that actually justified the growth.
        if not engine.should_create_neuron(context, deficit=deficit):
            return None

        name = engine.create_functional_neuron(context, deficit=deficit)
        if name:
            self.last_neurogenesis_tick = tick
            self.custom_neurons.add(name)
            self.new_neurons.add(name)
            self.neurogenesis_data['neurons_created'] = \
                self.neurogenesis_data.get('neurons_created', 0) + 1
            if name not in self.neurogenesis_data['new_neurons']:
                self.neurogenesis_data['new_neurons'].append(name)
        return name

    # Counts are derived from the engine so they can never drift out of step
    # with the neurons that actually exist.
    def _count_type(self, neuron_type: str) -> int:
        return sum(1 for fn in self.enhanced_neurogenesis.functional_neurons.values()
                   if getattr(fn, 'neuron_type', '') == neuron_type)

    @property
    def stress_neuron_count(self) -> int:
        return self._count_type('stress')

    @property
    def novelty_neuron_count(self) -> int:
        return self._count_type('novelty')

    @property
    def reward_neuron_count(self) -> int:
        return self._count_type('reward')

    def _create_neuron(self, neuron_type: str, context: Dict) -> Optional[str]:
        """Delegate to the one creation path.

        The old body invented its own names, shapes and a fixed three-synapse
        wiring pattern per type, none of which matched what the game builds -
        so a neuron grown during training was a different kind of object from
        one grown in play.
        """
        name = self.enhanced_neurogenesis.create_neuron(
            neuron_type, brain_state=dict(self.state), environment=context or {})
        if name:
            self.custom_neurons.add(name)
            self.new_neurons.add(name)
        return name

    def _get_neuron_value(self, val) -> float:
        """Convert value to float for calculations"""
        if isinstance(val, bool):
            return 100.0 if val else 0.0
        if isinstance(val, (int, float)):
            return float(val)
        return 0.0
        
    def get_statistics(self) -> Dict:
        """Get brain statistics"""
        return {
            'total_neurons': len(self.positions),
            'total_connections': len(self.weights),
            'custom_neurons': len(self.custom_neurons),
            'stress_neurons': self.stress_neuron_count,
            'novelty_neurons': self.novelty_neuron_count,
            'reward_neurons': self.reward_neuron_count,
            'weight_updates': len(self.weight_history),
            'avg_weight': sum(self.weights.values()) / len(self.weights) if self.weights else 0,
        }


# ============================================================================
# HEADLESS SIMULATION
# ============================================================================

class HeadlessSimulation:
    """
    Headless simulation runner for brain training.
    Runs the simulation loop without GUI, with accelerated time.
    """
    
    def __init__(self, config: TrainingConfig = None):
        self.config = config or TrainingConfig()
        # Seed BEFORE anything random happens - HeadlessSquid picks its
        # personality in its constructor - so a seeded run is reproducible from
        # the very first draw.
        if self.config.seed is not None:
            random.seed(self.config.seed)
        self.brain = HeadlessBrain(self.config)
        self.squid = HeadlessSquid()
        
        # Simulation state
        self.tick = 0
        self.running = False
        
        # Environment
        self.food_items: List[Dict] = []
        self.poop_items: List[Dict] = []
        
        # Statistics
        self.stats = {
            'ticks_completed': 0,
            'neurons_created': 0,
            'hebbian_updates': 0,
            'food_eaten': 0,
            'startles': 0,
            'peak_anxiety': 0,
            'peak_happiness': 0,
        }
        
        # Event queue (for scenarios)
        self.event_queue: List[Dict] = []
        
        # Progress callback
        self.progress_callback = None
        
    def load_brain(self, filepath: str) -> bool:
        """Load a brain from file"""
        return self.brain.load_brain_file(filepath)
        
    def load_scenario(self, scenario_name: str) -> bool:
        """Load a predefined training scenario"""
        if scenario_name not in TRAINING_SCENARIOS:
            print(f"✗ Unknown scenario: {scenario_name}")
            print(f"  Available: {list(TRAINING_SCENARIOS.keys())}")
            return False
            
        scenario = TRAINING_SCENARIOS[scenario_name]
        print(f"✓ Loading scenario: {scenario.name}")
        print(f"  Description: {scenario.description}")
        print(f"  Duration: {scenario.duration_ticks} ticks")
        
        # Apply config overrides
        for key, value in scenario.config_overrides.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                
        # Queue events
        self.event_queue = list(scenario.events)
        
        return True
        
    def run(self, ticks: int = 1000, progress_interval: int = 100) -> Dict:
        """
        Run the simulation for specified number of ticks.
        
        Args:
            ticks: Number of simulation ticks to run
            progress_interval: How often to report progress
            
        Returns:
            Dictionary with final statistics
        """
        self.running = True
        start_time = time.time()
        
        print(f"\n🚀 Starting headless training: {ticks} ticks")
        print(f"   Brain: {len(self.brain.positions)} neurons, {len(self.brain.weights)} connections")
        print()
        
        for self.tick in range(ticks):
            if not self.running:
                break
                
            # Process queued events
            self._process_events()
            
            # Simulation step
            self._simulation_step()
            
            # Progress report
            if progress_interval > 0 and (self.tick + 1) % progress_interval == 0:
                elapsed = time.time() - start_time
                tps = (self.tick + 1) / elapsed if elapsed > 0 else 0
                self._report_progress(tps)
                
        # Final statistics
        elapsed = time.time() - start_time
        self.stats['ticks_completed'] = self.tick + 1
        self.stats['elapsed_seconds'] = elapsed
        self.stats['ticks_per_second'] = (self.tick + 1) / elapsed if elapsed > 0 else 0
        
        print(f"\n✓ Training complete!")
        print(f"  Ticks: {self.stats['ticks_completed']}")
        print(f"  Time: {elapsed:.2f}s ({self.stats['ticks_per_second']:.1f} ticks/sec)")
        print(f"  Neurons created: {self.stats['neurons_created']}")
        print(f"  Hebbian updates: {self.stats['hebbian_updates']}")
        
        brain_stats = self.brain.get_statistics()
        print(f"\n  Brain Statistics:")
        print(f"    Total neurons: {brain_stats['total_neurons']}")
        print(f"    Connections: {brain_stats['total_connections']}")
        print(f"    Custom neurons: {brain_stats['custom_neurons']}")
        
        return {**self.stats, **brain_stats}
        
    def _simulation_step(self):
        """Execute one simulation tick"""
        # 1. Update squid state
        self.squid.update()
        
        # 2. Environment events
        self._update_environment()
        
        # 3. Update brain with squid state. One tick is one second of the
        #    squid's life, and every pacing rule reads that clock.
        self.brain.advance_clock(1.0)
        squid_state = self.squid.get_state_dict()
        self.brain.update_state(squid_state)

        # Open a causal episode for whatever the squid has committed to doing,
        # exactly as TamagotchiLogic does in the game. Without this the trainer
        # ran the causal machinery with no actions in it, so a brain trained
        # headlessly could never learn what its own behaviour does.
        self.brain.causal_learning.on_action(str(squid_state.get('status', '')))
        
        # 4. Propagate brain activations
        self.brain.propagate()
        
        # 5. Hebbian learning (periodic)
        if self.tick % self.config.hebbian_interval == 0:
            updated = self.brain.perform_hebbian_learning()
            if updated:
                self.stats['hebbian_updates'] += len(updated)
                
        # 6. Neurogenesis check
        new_neuron = self.brain.check_neurogenesis(squid_state, self.tick)
        if new_neuron:
            self.stats['neurons_created'] += 1
            print(f"  🧠 Tick {self.tick}: Created neuron '{new_neuron}'")
            
        # 7. Track statistics
        self.stats['peak_anxiety'] = max(self.stats['peak_anxiety'], self.squid.anxiety)
        self.stats['peak_happiness'] = max(self.stats['peak_happiness'], self.squid.happiness)
        
    def _update_environment(self):
        """Update environment (spawn/despawn items, random events)"""
        # Food spawning
        if random.random() < self.config.food_spawn_chance:
            self.food_items.append({'x': random.random(), 'y': random.random()})
            self.squid.food_visible = True
            
        # Food consumption
        if self.squid.food_visible and random.random() < 0.1:
            self.squid.feed()
            self.stats['food_eaten'] += 1
            if self.food_items:
                self.food_items.pop(0)
            self.squid.food_visible = len(self.food_items) > 0
            
        # Poop spawning
        if random.random() < self.config.poop_spawn_chance:
            self.poop_items.append({'x': random.random(), 'y': random.random()})
            self.squid.cleanliness = max(0, self.squid.cleanliness - 5)
            
        # Random startle
        if random.random() < self.config.startle_chance:
            self.squid.startle()
            self.stats['startles'] += 1
            
        # Plant proximity (random for now)
        self.squid.plant_nearby = random.random() < 0.2
        
    def _process_events(self):
        """Process queued scenario events"""
        events_to_remove = []
        
        for event in self.event_queue:
            if event.get('tick', 0) == self.tick:
                self._execute_event(event)
                events_to_remove.append(event)
                
        for event in events_to_remove:
            self.event_queue.remove(event)
            
    def _execute_event(self, event: Dict):
        """Execute a scenario event"""
        event_type = event.get('type', '')
        
        if event_type == 'set_state':
            state = event.get('state', {})
            for key, value in state.items():
                if hasattr(self.squid, key):
                    setattr(self.squid, key, value)
            print(f"  📋 Tick {self.tick}: Set state {state}")
            
        elif event_type == 'feed':
            self.squid.feed()
            self.stats['food_eaten'] += 1
            print(f"  🍕 Tick {self.tick}: Fed squid")
            
        elif event_type == 'startle':
            self.squid.startle()
            self.stats['startles'] += 1
            print(f"  ⚡ Tick {self.tick}: Startled squid")
            
        elif event_type == 'clean':
            self.squid.clean()
            print(f"  🧹 Tick {self.tick}: Cleaned environment")
            
        elif event_type == 'new_object':
            self.squid.curiosity = min(100, self.squid.curiosity + 20)
            print(f"  🆕 Tick {self.tick}: New object encountered")
            
    def _report_progress(self, tps: float):
        """Report training progress"""
        stats = self.brain.get_statistics()
        squid = self.squid
        
        progress_pct = (self.tick + 1) / max(1, self.stats.get('target_ticks', self.tick + 1)) * 100
        
        print(f"  [{self.tick+1:6d}] {tps:6.1f} t/s | "
              f"Neurons: {stats['total_neurons']:2d} | "
              f"H:{squid.hunger:5.1f} A:{squid.anxiety:5.1f} S:{squid.satisfaction:5.1f} | "
              f"Created: {self.stats['neurons_created']}")
              
    def stop(self):
        """Stop the simulation"""
        self.running = False


# ============================================================================
# COMMAND LINE INTERFACE
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Dosidicus-2 Headless Brain Trainer',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Train a brain for 10000 ticks:
    python headless_trainer.py --brain my_brain.json --ticks 10000 --output trained.json
    
  Run a stress test scenario:
    python headless_trainer.py --brain my_brain.json --scenario stress_test --output stress_trained.json
    
  List available scenarios:
    python headless_trainer.py --list-scenarios
    
  Quick training with default brain:
    python headless_trainer.py --ticks 5000 --output quick_trained.json
        """
    )
    
    parser.add_argument('--brain', '-b', type=str, help='Path to brain JSON file to load')
    parser.add_argument('--seed', type=int,
                        help='Random seed. With one set the run is reproducible: '
                             'the same seed, brain and tick count give the same '
                             'trained brain every time.')
    parser.add_argument('--blank', action='store_true',
                        help='Start from a blank 8-neuron brain (the eight '
                             'required neurons, no synapses, no innate reflexes) '
                             'instead of the newborn brain a real squid gets. '
                             'The control condition for an experiment.')
    parser.add_argument('--output', '-o', type=str, help='Path to save trained brain')
    parser.add_argument('--ticks', '-t', type=int, default=10000, help='Number of ticks to train (default: 10000)')
    parser.add_argument('--scenario', '-s', type=str, help='Training scenario to use')
    parser.add_argument('--list-scenarios', action='store_true', help='List available training scenarios')
    parser.add_argument('--progress', '-p', type=int, default=500, help='Progress report interval (default: 500)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')
    
    # Config overrides
    parser.add_argument('--learning-rate', type=float, help='Hebbian learning rate')
    parser.add_argument('--neurogenesis', type=bool, help='Enable neurogenesis')
    parser.add_argument('--max-neurons', type=int, help='Maximum neurons allowed')
    
    args = parser.parse_args()
    
    # List scenarios
    if args.list_scenarios:
        print("\nAvailable Training Scenarios:")
        print("-" * 60)
        for name, scenario in TRAINING_SCENARIOS.items():
            print(f"\n  {name}:")
            print(f"    {scenario.description}")
            print(f"    Duration: {scenario.duration_ticks} ticks")
            if scenario.config_overrides:
                print(f"    Config overrides: {scenario.config_overrides}")
        print()
        return
        
    # Build config
    config = TrainingConfig()
    if args.learning_rate:
        config.learning_rate = args.learning_rate
    if args.neurogenesis is not None:
        config.neurogenesis_enabled = args.neurogenesis
    if args.max_neurons:
        config.max_neurons = args.max_neurons
    if args.seed is not None:
        config.seed = args.seed
    if args.blank:
        config.blank = True
        
    # Create simulation
    sim = HeadlessSimulation(config)
    
    # Load brain
    if args.brain:
        if not os.path.exists(args.brain):
            print(f"✗ Brain file not found: {args.brain}")
            sys.exit(1)
        if not sim.load_brain(args.brain):
            sys.exit(1)
    else:
        print("ℹ Using default brain architecture")
        
    # Load scenario
    ticks = args.ticks
    if args.scenario:
        if not sim.load_scenario(args.scenario):
            sys.exit(1)
        # Use scenario duration if longer
        scenario = TRAINING_SCENARIOS.get(args.scenario)
        if scenario and scenario.duration_ticks > ticks:
            ticks = scenario.duration_ticks
            
    # Run training
    progress = 0 if args.quiet else args.progress
    sim.stats['target_ticks'] = ticks
    
    try:
        stats = sim.run(ticks=ticks, progress_interval=progress)
    except KeyboardInterrupt:
        print("\n\n⚠ Training interrupted by user")
        sim.stop()
        stats = sim.stats
        
    # Save output
    if args.output:
        sim.brain.save_brain(args.output)
    else:
        # Default output name
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        output_name = f"trained_brain_{timestamp}.json"
        sim.brain.save_brain(output_name)
        
    print("\n✓ Done!")


if __name__ == '__main__':
    main()
