"""
Sparse Neural Network Generator for Dosidicus-2

Generates realistic, biologically-inspired connections between the core neurons
with random noise so no two generations are identical.
"""

import random
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

from designer_constants import CORE_NEURONS, REQUIRED_NEURON_NAMES


@dataclass
class ConnectionTemplate:
    """Template for a potential connection with probability and weight range."""
    source: str
    target: str
    base_weight: float  # Central weight value
    weight_variance: float  # +/- variance
    probability: float  # Chance this connection is created (0.0 - 1.0)
    description: str = ""


# ============================================================================
# BIOLOGICALLY-INSPIRED CONNECTION TEMPLATES
# These define the "tendencies" of the neural network - realistic relationships
# between hunger, emotions, and sensory input
# ============================================================================

CORE_CONNECTION_TEMPLATES = [
    # === HUNGER dynamics ===
    # Hunger creates dissatisfaction and negative mood
    ConnectionTemplate("hunger", "satisfaction", -0.35, 0.15, 0.85,
                      "Being hungry reduces satisfaction"),
    ConnectionTemplate("hunger", "happiness", -0.25, 0.12, 0.70,
                      "Hunger negatively affects mood"),
    ConnectionTemplate("hunger", "anxiety", 0.20, 0.10, 0.60,
                      "Hunger can cause anxiety"),
    ConnectionTemplate("hunger", "curiosity", 0.15, 0.10, 0.45,
                      "Hunger may drive food-seeking curiosity"),
    
    # === HAPPINESS dynamics ===
    # Happiness is calming and promotes exploration
    ConnectionTemplate("happiness", "anxiety", -0.30, 0.12, 0.80,
                      "Being happy reduces anxiety"),
    ConnectionTemplate("happiness", "curiosity", 0.25, 0.10, 0.65,
                      "Happy creatures are more curious"),
    ConnectionTemplate("happiness", "satisfaction", 0.20, 0.08, 0.55,
                      "Happiness contributes to satisfaction"),
    
    # === CLEANLINESS dynamics ===
    # Being clean improves mood and reduces stress
    ConnectionTemplate("cleanliness", "happiness", 0.25, 0.10, 0.75,
                      "Being clean improves mood"),
    ConnectionTemplate("cleanliness", "anxiety", -0.20, 0.08, 0.60,
                      "Cleanliness reduces stress"),
    ConnectionTemplate("cleanliness", "satisfaction", 0.15, 0.08, 0.50,
                      "Cleanliness contributes to overall satisfaction"),
    
    # === SLEEPINESS dynamics ===
    # Tiredness affects cognition and mood negatively
    ConnectionTemplate("sleepiness", "curiosity", -0.30, 0.12, 0.70,
                      "Tiredness suppresses curiosity"),
    ConnectionTemplate("sleepiness", "happiness", -0.20, 0.10, 0.65,
                      "Being tired affects mood"),
    ConnectionTemplate("sleepiness", "anxiety", 0.15, 0.08, 0.55,
                      "Sleep deprivation increases anxiety"),
    ConnectionTemplate("sleepiness", "satisfaction", -0.15, 0.08, 0.45,
                      "Tiredness reduces satisfaction"),
    
    # === SATISFACTION dynamics ===
    # Satisfaction is calming and mood-boosting
    ConnectionTemplate("satisfaction", "happiness", 0.35, 0.12, 0.85,
                      "Satisfaction promotes happiness"),
    ConnectionTemplate("satisfaction", "anxiety", -0.25, 0.10, 0.75,
                      "Being satisfied reduces anxiety"),
    ConnectionTemplate("satisfaction", "curiosity", 0.10, 0.08, 0.40,
                      "Satisfied creatures may explore more"),
    
    # === ANXIETY dynamics ===
    # Anxiety suppresses positive states and exploration
    ConnectionTemplate("anxiety", "curiosity", -0.35, 0.12, 0.80,
                      "Anxiety suppresses exploration"),
    ConnectionTemplate("anxiety", "happiness", -0.25, 0.10, 0.70,
                      "Anxiety reduces happiness"),
    ConnectionTemplate("anxiety", "satisfaction", -0.15, 0.08, 0.50,
                      "Anxiety reduces overall satisfaction"),
    ConnectionTemplate("anxiety", "sleepiness", 0.10, 0.08, 0.35,
                      "Anxiety can cause fatigue"),
    
    # === CURIOSITY dynamics ===
    # Curiosity promotes positive mood and engagement
    ConnectionTemplate("curiosity", "happiness", 0.20, 0.10, 0.60,
                      "Curiosity brings joy"),
    ConnectionTemplate("curiosity", "satisfaction", 0.15, 0.08, 0.45,
                      "Exploration satisfies"),
    ConnectionTemplate("curiosity", "anxiety", -0.10, 0.08, 0.35,
                      "Curiosity can reduce anxiety through engagement"),
    
    # === CAN_SEE_FOOD dynamics (vision input) ===
    # Seeing food triggers hunger awareness and emotional responses
    ConnectionTemplate("can_see_food", "hunger", 0.30, 0.12, 0.90,
                      "Seeing food activates hunger awareness"),
    ConnectionTemplate("can_see_food", "happiness", 0.25, 0.10, 0.75,
                      "Food sighting is exciting"),
    ConnectionTemplate("can_see_food", "curiosity", 0.20, 0.10, 0.65,
                      "Food triggers investigative behavior"),
    ConnectionTemplate("can_see_food", "satisfaction", 0.15, 0.08, 0.50,
                      "Food sight brings anticipatory satisfaction"),
    ConnectionTemplate("can_see_food", "anxiety", -0.10, 0.08, 0.40,
                      "Food sighting may reduce food-seeking anxiety"),
]


class SparseNetworkGenerator:
    """
    Generates sparse neural networks with biologically-inspired connections.
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize generator with optional seed for reproducibility.
        
        Args:
            seed: Random seed. If None, uses system entropy.
        """
        self.seed = seed
        self.rng = random.Random(seed)
        self.templates = CORE_CONNECTION_TEMPLATES.copy()
    
    def set_seed(self, seed: int):
        """Set random seed for reproducible generation."""
        self.seed = seed
        self.rng = random.Random(seed)
    
    def _generate_weight(self, template: ConnectionTemplate) -> float:
        """Generate a noisy weight from a template."""
        # Gaussian noise centered on base_weight
        noise = self.rng.gauss(0, template.weight_variance)
        weight = template.base_weight + noise
        
        # Clamp to valid range and round
        weight = max(-1.0, min(1.0, weight))
        return round(weight, 3)

    def perturb_positions(self, design, variance: float = 0.3,
                     bounds: Tuple[float, float, float, float] = (-400, -150, 900, 750)):
        """
        Randomly perturb neuron positions with organic variance.
        
        Args:
            design: BrainDesign to modify
            variance: Variance multiplier (0.3 = ±30% from original position)
            bounds: (min_x, min_y, max_x, max_y) to constrain neurons within view window
        """
        if variance <= 0:
            return
            
        min_x, min_y, max_x, max_y = bounds
        rng = self.rng
        
        # Calculate center for organic spreading
        if not design.neurons:
            return
            
        center_x = sum(n.position[0] for n in design.neurons.values()) / len(design.neurons)
        center_y = sum(n.position[1] for n in design.neurons.values()) / len(design.neurons)
        
        for name, neuron in design.neurons.items():
            # Skip required neurons (core and can_see_food) to keep them stable
            if neuron.is_required:
                continue
                
            x, y = neuron.position
            
            # Add Gaussian noise scaled by variance
            noise_scale = variance * 60  # 60px standard deviation at variance=1.0
            new_x = x + rng.gauss(0, noise_scale)
            new_y = y + rng.gauss(0, noise_scale)
            
            # Clamp to view bounds
            new_x = max(min_x, min(max_x, new_x))
            new_y = max(min_y, min(max_y, new_y))
            
            neuron.position = (new_x, new_y)

    def add_random_sensors(self, design, probability: float = 0.3):
        """
        Randomly add input sensors to the design with sensible wiring.
        
        Args:
            design: BrainDesign to modify
            probability: Probability of adding each available sensor (0.0 to 1.0)
        
        Returns:
            Number of sensors added
        """
        from designer_sensor_discovery import get_all_available_sensors
        
        all_sensors = get_all_available_sensors()
        # Exclude already-present sensors and the required can_see_food
        available_sensors = [
            name for name in all_sensors.keys() 
            if name not in design.neurons and name != 'can_see_food'
        ]
        
        added = 0
        for sensor_name in available_sensors:
            if self.rng.random() < probability:
                # add_sensor handles both creation and sensible wiring via defaults
                success, _ = design.add_sensor(sensor_name, create_default_connections=True)
                if success:
                    added += 1
                    
        return added
    
    def _should_create_connection(self, template: ConnectionTemplate, 
                                   density_multiplier: float = 1.0) -> bool:
        """Decide if a connection should be created based on probability."""
        adjusted_prob = min(1.0, template.probability * density_multiplier)
        return self.rng.random() < adjusted_prob
    
    def generate_connections(self, 
                              density: float = 1.0,
                              include_feedback_loops: bool = True,
                              weight_noise: float = 1.0
                              ) -> List[Tuple[str, str, float]]:
        """
        Generate sparse connections between core neurons.
        
        Args:
            density: Multiplier for connection probability (0.5 = sparser, 1.5 = denser)
            include_feedback_loops: If True, may add some bidirectional connections
            weight_noise: Multiplier for weight variance (0.5 = less noise, 2.0 = more noise)
        
        Returns:
            List of (source, target, weight) tuples
        """
        connections = []
        created_pairs = set()
        
        # Process each template
        for template in self.templates:
            if not self._should_create_connection(template, density):
                continue
            
            # Generate noisy weight
            adjusted_template = ConnectionTemplate(
                template.source, template.target,
                template.base_weight,
                template.weight_variance * weight_noise,
                template.probability,
                template.description
            )
            weight = self._generate_weight(adjusted_template)
            
            # Skip very weak connections
            if abs(weight) < 0.02:
                continue
            
            connections.append((template.source, template.target, weight))
            created_pairs.add((template.source, template.target))
        
        # Optionally add feedback loops (reverse connections)
        if include_feedback_loops:
            feedback_candidates = [
                ("satisfaction", "hunger", -0.15, 0.4),  # Being satisfied reduces hunger drive
                ("happiness", "sleepiness", -0.10, 0.3),  # Being happy reduces tiredness
                ("anxiety", "hunger", 0.10, 0.25),  # Stress eating?
                ("curiosity", "anxiety", 0.08, 0.2),  # Exploration can be slightly stressful
            ]
            
            for source, target, base_w, prob in feedback_candidates:
                # Don't create if forward connection doesn't exist or reverse already exists
                if (target, source) not in created_pairs:
                    continue
                if (source, target) in created_pairs:
                    continue
                    
                if self.rng.random() < prob * density:
                    noise = self.rng.gauss(0, 0.05 * weight_noise)
                    weight = round(max(-1.0, min(1.0, base_w + noise)), 3)
                    if abs(weight) >= 0.02:
                        connections.append((source, target, weight))
                        created_pairs.add((source, target))
        
        # Shuffle to avoid predictable order
        self.rng.shuffle(connections)
        
        return connections
    
    def generate_for_design(self, design, 
                            clear_existing: bool = True,
                            density: float = 1.0,
                            include_feedback: bool = True,
                            seed: Optional[int] = None,
                            silent: bool = False) -> Tuple[int, List[str]]:
        """
        Generate and apply sparse network to a BrainDesign.
        
        Args:
            design: BrainDesign instance to modify
            clear_existing: If True, removes existing connections first
            density: Connection density multiplier
            include_feedback: Include feedback loops
            seed: Optional seed for reproducible generation. If provided, regenerates the RNG.
            silent: If True, suppresses generation of action description strings
        
        Returns:
            Tuple of (connections_created, list of action descriptions)
        """
        actions = []
        
        # Apply seed if provided
        if seed is not None:
            self.set_seed(seed)
            if not silent:
                actions.append(f"Using seed: {seed}")
        
        # Ensure required neurons exist
        missing = design.get_missing_required_neurons()
        if missing:
            design.add_missing_required_neurons()
            if not silent:
                actions.append(f"Added missing required neurons: {', '.join(missing)}")
        
        # Clear existing if requested
        if clear_existing:
            old_count = len(design.connections)
            design.connections.clear()
            if old_count > 0 and not silent:
                actions.append(f"Cleared {old_count} existing connections")
        
        # Generate new connections
        connections = self.generate_connections(
            density=density,
            include_feedback_loops=include_feedback
        )
        
        # Apply to design
        created = 0
        for source, target, weight in connections:
            # Verify both neurons exist in design
            if source not in design.neurons or target not in design.neurons:
                continue
            
            if design.add_connection(source, target, weight):
                created += 1
                if not silent:
                    sign = "+" if weight > 0 else ""
                    actions.append(f"  {source} → {target} ({sign}{weight:.3f})")
        
        return created, actions
    
    def get_preset_styles(self) -> Dict[str, Dict]:
        """Return preset generation styles with new variance and sensor options."""
        return {
            'balanced': {
                'name': '⚖️ Balanced',
                'description': 'Standard density, moderate noise, slight position variance',
                'density': 1.0,
                'include_feedback': True,
                'weight_noise': 1.0,
                'position_variance': 0.2,
                'sensor_probability': 0.15
            },
            'sparse': {
                'name': '🔬 Minimal',
                'description': 'Fewer connections, minimal position variance',
                'density': 0.5,
                'include_feedback': False,
                'weight_noise': 0.7,
                'position_variance': 0.1,
                'sensor_probability': 0.0
            },
            'dense': {
                'name': '🕸️ Dense',
                'description': 'More connections, rich dynamics, moderate sensors',
                'density': 1.4,
                'include_feedback': True,
                'weight_noise': 1.2,
                'position_variance': 0.3,
                'sensor_probability': 0.3
            },
            'chaotic': {
                'name': '🌀 Chaotic',
                'description': 'High noise, unpredictable, high position variance',
                'density': 1.1,
                'include_feedback': True,
                'weight_noise': 2.5,
                'position_variance': 0.5,
                'sensor_probability': 0.4
            },
            'calm': {
                'name': '🧘 Calm',
                'description': 'Weaker connections, stable, low variance',
                'density': 0.8,
                'include_feedback': True,
                'weight_noise': 0.5,
                'position_variance': 0.1,
                'sensor_probability': 0.0
            },
            'wild': {
                'name': '🌿 Wild',
                'description': 'Organic positions, many sensors, natural feel',
                'density': 1.2,
                'include_feedback': True,
                'weight_noise': 1.5,
                'position_variance': 0.4,
                'sensor_probability': 0.5
            }
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_sparse_core_network(density: float = 1.0, 
                                  seed: Optional[int] = None) -> List[Tuple[str, str, float]]:
    """
    Convenience function to generate sparse network connections.
    
    Args:
        density: How dense the network should be (0.5 = sparse, 1.5 = dense)
        seed: Random seed for reproducibility
    
    Returns:
        List of (source, target, weight) tuples
    """
    generator = SparseNetworkGenerator(seed)
    return generator.generate_connections(density=density)


def describe_connection(source: str, target: str, weight: float) -> str:
    """Generate a human-readable description of a connection."""
    effect = "excites" if weight > 0 else "inhibits"
    strength = abs(weight)
    
    if strength < 0.15:
        strength_word = "weakly"
    elif strength < 0.35:
        strength_word = "moderately"
    elif strength < 0.6:
        strength_word = "strongly"
    else:
        strength_word = "powerfully"
    
    return f"{source} {strength_word} {effect} {target}"
