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
            
        for name, neuron in design.neurons.items():
            # Skip required/core neurons to keep the brain structure recognizable
            # but allow custom neurons (connectors, neurogenesis types) to move
            if neuron.is_required or neuron.is_core:
                continue
            
            # Ensure position is valid
            if neuron.position is None:
                continue
                
            x, y = neuron.position
            
            # Add Gaussian noise scaled by variance
            # Using a larger base scale (100px) so variance=0.2 moves things visibly (~20px)
            noise_scale = variance * 100 
            new_x = x + rng.gauss(0, noise_scale)
            new_y = y + rng.gauss(0, noise_scale)
            
            # Clamp to view bounds to keep them on canvas
            new_x = max(min_x, min(max_x, new_x))
            new_y = max(min_y, min(max_y, new_y))
            
            neuron.position = (new_x, new_y)

    def add_random_sensors(self, design, probability: float = 0.3):
        """
        Randomly add input sensors to the design based on specific game rules.
        
        Rules:
        - 'can_see_food' is required (handled by design validation, but implicitly part of valid set)
        - 'plant_proximity': 20% chance
        - 'is_fleeing': 10% chance
        - No other sensors are generated.
        
        Args:
            design: BrainDesign to modify
            probability: Ignored. Probabilities are hardcoded per requirements.
        
        Returns:
            Number of sensors added
        """
        # Specific probabilities requested
        sensor_rules = {
            'plant_proximity': 0.20,
            'is_fleeing': 0.10
        }
        
        added = 0
        for sensor_name, chance in sensor_rules.items():
            # Skip if already present
            if sensor_name in design.neurons:
                continue

            # Roll the dice
            if self.rng.random() < chance:
                # add_sensor handles both creation and sensible wiring via defaults
                success, _ = design.add_sensor(sensor_name, create_default_connections=True)
                if success:
                    added += 1
                    
        return added

    def remove_non_core_neurons(self, design) -> int:
        """
        Remove all non-core neurons from the design.
        
        Core neurons are: hunger, happiness, cleanliness, sleepiness,
                          satisfaction, anxiety, curiosity, can_see_food
        
        Args:
            design: BrainDesign to modify
            
        Returns:
            Number of neurons removed
        """
        from designer_constants import is_core_neuron, is_required_neuron
        
        # Find neurons to remove (not core and not can_see_food)
        to_remove = []
        for name in list(design.neurons.keys()):
            if not is_core_neuron(name) and not is_required_neuron(name):
                to_remove.append(name)
        
        # Remove them
        removed = 0
        for name in to_remove:
            success, _ = design.remove_neuron(name)
            if success:
                removed += 1
        
        return removed
    
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
        Generate connections between neurons with a strong preference 
        for bidirectional (reciprocal) relationships.
        """
        connections = []
        created_pairs = set()
        
        # 1. First Pass: Create Forward Connections from Templates
        for template in self.templates:
            if not self._should_create_connection(template, density):
                continue
            
            # Generate noisy weight based on variance and global noise multiplier
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

            # 2. Immediate Reciprocal Generation: Ensure Bidirectional Flow
            # If we created A -> B, try to create B -> A immediately if it makes biological sense.
            # We use a slightly inverted weight of the original to create a feedback loop.
            if include_feedback_loops:
                # Higher base probability for reciprocal connections to ensure they "always exist"
                # while still respecting the density setting.
                reciprocal_prob = 0.85 * density 
                
                if (template.target, template.source) not in created_pairs:
                    if self.rng.random() < reciprocal_prob:
                        # Feedback is often inhibitory or dampening (negative of forward)
                        fb_weight_base = -0.2 if weight > 0 else 0.1
                        fb_noise = self.rng.gauss(0, 0.1 * weight_noise)
                        fb_weight = round(max(-1.0, min(1.0, fb_weight_base + fb_noise)), 3)
                        
                        if abs(fb_weight) >= 0.02:
                            connections.append((template.target, template.source, fb_weight))
                            created_pairs.add((template.target, template.source))

        # 3. Dedicated Biological Feedback Loops
        # These handle specific relationships like Hunger ↔ Satisfaction loops.
        if include_feedback_loops:
            feedback_candidates = [
                ("satisfaction", "hunger", -0.25, 0.9),  # Strong satiety loop
                ("happiness", "sleepiness", -0.15, 0.7), # Mood suppressing fatigue
                ("anxiety", "hunger", 0.15, 0.6),        # Stress-induced hunger
                ("curiosity", "anxiety", 0.10, 0.5),     # Exploration tension
                ("happiness", "satisfaction", 0.20, 0.8) # Positive reinforcement
            ]
            
            for source, target, base_w, prob in feedback_candidates:
                # Only add if not already created by the reciprocal logic above
                if (source, target) in created_pairs:
                    continue
                    
                if self.rng.random() < prob * density:
                    noise = self.rng.gauss(0, 0.05 * weight_noise)
                    weight = round(max(-1.0, min(1.0, base_w + noise)), 3)
                    if abs(weight) >= 0.02:
                        connections.append((source, target, weight))
                        created_pairs.add((source, target))
        
        # Shuffle to avoid predictable order in the UI/data structures
        self.rng.shuffle(connections)
        
        return connections
    
    def generate_for_design(self, design, 
                            clear_existing: bool = True,
                            clear_non_core_neurons: bool = False,
                            density: float = 1.0,
                            include_feedback: bool = True,
                            weight_noise: float = 1.0,        # ADDED to match call sig
                            position_variance: float = 0.0,   # ADDED to fix Error
                            sensor_probability: float = 0.0,  # ADDED to match call sig
                            bounds: Tuple[float, float, float, float] = (-400, -150, 900, 750),
                            seed: Optional[int] = None,
                            silent: bool = False) -> Tuple[int, List[str]]:
        """
        Generate and apply sparse network to a BrainDesign.
        
        Args:
            design: BrainDesign instance to modify
            clear_existing: If True, removes existing connections first
            clear_non_core_neurons: If True, removes all non-core neurons first
            density: Connection density multiplier
            include_feedback: Include feedback loops
            weight_noise: Multiplier for random weight variance
            position_variance: If > 0, randomly moves neurons (perturbation)
            sensor_probability: Chance to add random input sensors
            bounds: (min_x, min_y, max_x, max_y) to constrain neurons within view window
            seed: Optional seed for reproducible generation.
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
        
        # 0. Remove non-core neurons if requested (do this first!)
        if clear_non_core_neurons:
            removed = self.remove_non_core_neurons(design)
            if removed > 0 and not silent:
                actions.append(f"Removed {removed} non-core neurons")
        
        # Ensure required neurons exist
        missing = design.get_missing_required_neurons()
        if missing:
            design.add_missing_required_neurons()
            if not silent:
                actions.append(f"Added missing required neurons: {', '.join(missing)}")
        
        # 1. Handle Random Sensors (if requested)
        if sensor_probability > 0:
            added_sensors = self.add_random_sensors(design, sensor_probability)
            if added_sensors > 0 and not silent:
                actions.append(f"Added {added_sensors} random input sensors")

        # 2. Handle Position Perturbation (if requested)
        if position_variance > 0:
            self.perturb_positions(design, variance=position_variance, bounds=bounds)
            if not silent:
                actions.append(f"Perturbed neuron positions (variance: {position_variance})")

        # 3. Clear existing connections (if requested)
        if clear_existing:
            old_count = len(design.connections)
            design.connections.clear()
            if old_count > 0 and not silent:
                actions.append(f"Cleared {old_count} existing connections")
        
        # 4. Generate new connections
        connections = self.generate_connections(
            density=density,
            include_feedback_loops=include_feedback,
            weight_noise=weight_noise
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