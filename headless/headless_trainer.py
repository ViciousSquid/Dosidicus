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
# CONSTANTS (from brain_worker.py and brain_constants.py)
# ============================================================================

PURE_INPUTS = {
    "can_see_food", "is_eating", "is_sleeping", "is_sick",
    "pursuing_food", "is_fleeing", "is_startled", "external_stimulus",
    "plant_proximity"
}

CORE_NEURONS = {
    "hunger", "happiness", "cleanliness", "sleepiness",
    "satisfaction", "anxiety", "curiosity"
}

INPUT_SENSORS = {
    "can_see_food", "is_eating", "is_sleeping", "is_sick",
    "pursuing_food", "is_fleeing", "is_startled", "external_stimulus",
    "plant_proximity"
}


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

class HeadlessBrain:
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
        
        # Custom neurons tracking
        self.custom_neurons: Set[str] = set()
        self.new_neurons: Set[str] = set()
        self.connector_neurons: Set[str] = set()
        
        # Learning tracking
        self.last_hebbian_pairs: List[Tuple[str, str]] = []
        self.weight_history: List[Dict] = []
        
        # Neurogenesis tracking
        self.neurogenesis_data = {
            'new_neurons': [],
            'last_neuron_time': 0,
            'neurons_created': 0,
            'functional_neurons': {},
        }
        self.last_neurogenesis_tick = 0
        self.stress_neuron_count = 0
        self.novelty_neuron_count = 0
        self.reward_neuron_count = 0
        
        # Output bindings (for behaviors)
        self.output_bindings: List[Dict] = []
        
        # Initialize default state
        self._initialize_default_state()
        
    def _initialize_default_state(self):
        """Initialize with default neuron structure"""
        default_positions = {
            "can_see_food": (50, 200),
            "hunger": (127, 81),
            "happiness": (361, 81),
            "cleanliness": (627, 81),
            "sleepiness": (840, 81),
            "satisfaction": (271, 380),
            "anxiety": (491, 389),
            "curiosity": (701, 386),
        }
        
        for name, pos in default_positions.items():
            self.positions[name] = pos
            if name in CORE_NEURONS:
                self.state[name] = 50.0
            elif name in INPUT_SENSORS:
                self.state[name] = 0.0
            else:
                self.state[name] = 50.0
                
        # Default connections
        default_connections = [
            ("hunger", "satisfaction", -0.3),
            ("happiness", "satisfaction", 0.4),
            ("anxiety", "satisfaction", -0.35),
            ("cleanliness", "happiness", 0.2),
            ("sleepiness", "happiness", -0.15),
            ("curiosity", "happiness", 0.25),
        ]
        
        for src, dst, weight in default_connections:
            self.weights[(src, dst)] = weight
            
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
                        
            # Load shapes
            self.neuron_shapes = brain_data.get('neuron_shapes', {})
            
            # Load output bindings
            self.output_bindings = brain_data.get('output_bindings', [])
            
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
            'output_bindings': self.output_bindings,
            'state': {k: v for k, v in self.state.items()},
            'neurogenesis_data': {
                'neurons_created': self.neurogenesis_data.get('neurons_created', 0),
                'stress_neurons':  self.stress_neuron_count,
                'novelty_neurons': self.novelty_neuron_count,
                'reward_neurons':  self.reward_neuron_count,
            },
        }
        
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
            
    def update_state(self, squid_state: Dict[str, Any]):
        """Update brain state from squid state"""
        for key, value in squid_state.items():
            if key in self.positions or key in self.state:
                if isinstance(value, bool):
                    self.state[key] = 100.0 if value else 0.0
                elif isinstance(value, (int, float)):
                    self.state[key] = float(value)
                    
    def propagate(self):
        """Propagate activations through connections"""
        updates = {}
        
        for (src, dst), weight in self.weights.items():
            if src in self.state and dst in self.state:
                if dst in PURE_INPUTS:
                    continue
                    
                src_val = self.state[src]
                effect = src_val * weight * 0.1
                updates[dst] = updates.get(dst, 0) + effect
                
        # Apply updates with decay
        for neuron, delta in updates.items():
            if neuron in self.state and neuron not in PURE_INPUTS:
                old_val = self.state[neuron]
                new_val = old_val * self.config.decay_rate + delta
                new_val += random.uniform(-self.config.noise_range, self.config.noise_range)
                self.state[neuron] = max(-100, min(100, new_val))
                
    def perform_hebbian_learning(self) -> List[Tuple[str, str]]:
        """Perform Hebbian learning update"""
        # Get learning candidates
        excluded = set(PURE_INPUTS) | self.connector_neurons
        candidates = [n for n in self.positions.keys() if n not in excluded]
        
        if len(candidates) < 2:
            return []
            
        # Score pairs
        scored_pairs = []
        for i, n1 in enumerate(candidates):
            for n2 in candidates[i+1:]:
                v1 = self._get_neuron_value(self.state.get(n1, 50))
                v2 = self._get_neuron_value(self.state.get(n2, 50))
                score = v1 + v2 + random.uniform(0, 40)
                
                # Penalize recent pairs
                pair_key = tuple(sorted((n1, n2)))
                if pair_key in self.last_hebbian_pairs:
                    score -= 500
                    
                # Boost custom neurons
                if n1 in self.custom_neurons or n2 in self.custom_neurons:
                    score += 15
                    
                scored_pairs.append((score, n1, n2, v1, v2))
                
        # Select top pairs
        top_pairs = nlargest(self.config.max_hebbian_pairs, scored_pairs)
        self.last_hebbian_pairs = [tuple(sorted((n1, n2))) for _, n1, n2, _, _ in top_pairs]
        
        updated_pairs = []
        for _, n1, n2, v1, v2 in top_pairs:
            pair = (n1, n2)
            reverse_pair = (n2, n1)
            
            # Find existing connection
            if pair in self.weights:
                use_pair = pair
            elif reverse_pair in self.weights:
                use_pair = reverse_pair
            else:
                use_pair = pair
                self.weights[use_pair] = 0.0
                
            old_w = self.weights[use_pair]
            
            # Calculate learning rate with boosts
            lr = self.config.learning_rate
            if n1 in self.new_neurons or n2 in self.new_neurons:
                lr *= 2.0
            if n1 in self.custom_neurons or n2 in self.custom_neurons:
                lr *= 1.5
                
            # Hebbian update
            delta = lr * (v1 / 100.0) * (v2 / 100.0)
            new_w = old_w + delta - (old_w * self.config.weight_decay)
            new_w = max(-1.0, min(1.0, new_w))
            
            self.weights[use_pair] = new_w
            updated_pairs.append(use_pair)
            
            # Track history
            self.weight_history.append({
                'pair': use_pair,
                'old': old_w,
                'new': new_w,
                'tick': time.time()
            })
            
        return updated_pairs
        
    def check_neurogenesis(self, squid_state: Dict, tick: int) -> Optional[str]:
        """Check if neurogenesis should occur"""
        if not self.config.neurogenesis_enabled:
            return None
            
        if tick - self.last_neurogenesis_tick < self.config.neurogenesis_cooldown:
            return None
            
        if len(self.positions) >= self.config.max_neurons:
            return None
            
        # Check triggers
        anxiety = squid_state.get('anxiety', 50)
        curiosity = squid_state.get('curiosity', 50)
        happiness = squid_state.get('happiness', 50)
        satisfaction = squid_state.get('satisfaction', 50)
        
        trigger_type = None
        
        # Stress trigger
        if anxiety > 70 or (anxiety > 50 and squid_state.get('is_fleeing', False)):
            if self.stress_neuron_count < 5:  # Cap stress neurons
                trigger_type = 'stress'
                
        # Novelty trigger
        elif curiosity > 75:
            trigger_type = 'novelty'
            
        # Reward trigger
        elif happiness > 80 and satisfaction > 70:
            trigger_type = 'reward'
            
        if trigger_type:
            neuron_name = self._create_neuron(trigger_type, squid_state)
            self.last_neurogenesis_tick = tick
            return neuron_name
            
        return None
        
    def _create_neuron(self, neuron_type: str, context: Dict) -> str:
        """Create a new neuron"""
        # Generate unique name
        count = self.neurogenesis_data.get('neurons_created', 0) + 1
        self.neurogenesis_data['neurons_created'] = count
        
        neuron_name = f"{neuron_type}_{count}"
        
        # Find position (spread from existing neurons)
        existing_positions = list(self.positions.values())
        if existing_positions:
            avg_x = sum(p[0] for p in existing_positions) / len(existing_positions)
            avg_y = sum(p[1] for p in existing_positions) / len(existing_positions)
            
            # Add some randomness
            new_x = avg_x + random.uniform(-100, 100)
            new_y = avg_y + random.uniform(-100, 100)
        else:
            new_x = random.uniform(100, 800)
            new_y = random.uniform(100, 400)
            
        self.positions[neuron_name] = (new_x, new_y)
        self.state[neuron_name] = 50.0
        self.custom_neurons.add(neuron_name)
        self.new_neurons.add(neuron_name)
        
        # Set shape based on type
        shape_map = {'stress': 'hexagon', 'novelty': 'triangle', 'reward': 'circle'}
        self.neuron_shapes[neuron_name] = shape_map.get(neuron_type, 'circle')
        
        # Create connections based on type
        if neuron_type == 'stress':
            self.stress_neuron_count += 1
            self.weights[(neuron_name, 'anxiety')] = -0.3
            self.weights[('anxiety', neuron_name)] = 0.4
            
        elif neuron_type == 'novelty':
            self.novelty_neuron_count += 1
            self.weights[(neuron_name, 'curiosity')] = 0.3
            self.weights[('curiosity', neuron_name)] = 0.3
            
        elif neuron_type == 'reward':
            self.reward_neuron_count += 1
            self.weights[(neuron_name, 'satisfaction')] = 0.35
            self.weights[(neuron_name, 'happiness')] = 0.25
            
        self.neurogenesis_data['new_neurons'].append(neuron_name)
        
        return neuron_name
        
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
        self.brain = HeadlessBrain(config)
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
        
        # 3. Update brain with squid state
        squid_state = self.squid.get_state_dict()
        self.brain.update_state(squid_state)
        
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
