"""
Neurogenesis ver2_nov25 |   2.4.5.0

Context-aware neurogenesis where new neurons:
1. Encode specific experiences and patterns
2. Have functional roles in decision-making
3. Form connections based on what triggered their creation
4. Specialize over time based on usage

squid will develop specialized neurons for:

 Feeding satisfaction
 Play excitement
 Recovery relief
 Discovery joy
 Cleanliness motivation

"""

import time
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

@dataclass
class ExperienceContext:
    """Captures the full context when a neuron is created"""
    trigger_type: str  # 'novelty', 'stress', 'reward'
    active_neurons: Dict[str, float]  # Which neurons were active
    recent_actions: List[str]  # What the squid was doing
    environmental_state: Dict[str, any]  # Food, poop, etc.
    outcome: str  # 'positive', 'negative', 'neutral'
    timestamp: float
    
    def get_pattern_signature(self) -> str:
        """
        Generate HIGHLY SPECIFIC patterns that capture meaningful variation.
        """
        # Use CORE motivational neurons only (remove the over-filtering)
        motivational_neurons = {
            k: v for k, v in self.active_neurons.items() 
            if k in ['hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity', 'cleanliness', 'sleepiness']
        }
        
        if not motivational_neurons:
            return f"{self.trigger_type}_{self.outcome}_neutral"
        
        # Get the MOST active neuron (primary drive) - but keep its actual value
        primary_neuron, primary_value = max(motivational_neurons.items(), key=lambda x: abs(x[1] - 50))
        
        # Get SECONDARY driver for more specificity
        secondary = sorted(motivational_neurons.items(), key=lambda x: abs(x[1] - 50), reverse=True)
        secondary_neuron = secondary[1][0] if len(secondary) > 1 else "none"
        secondary_value = secondary[1][1] if len(secondary) > 1 else 50
        
        # Use VALUE RANGES for specificity (not just high/low)
        def get_range(value):
            if value < 20: return "critical_low"
            elif value < 40: return "low"
            elif value > 80: return "critical_high"
            elif value > 60: return "high"
            else: return "mid"
        
        # Build pattern with MORE distinguishing features
        pattern_parts = [
            self.trigger_type,
            self.outcome,
            f"primary_{primary_neuron}_{get_range(primary_value)}",
            f"secondary_{secondary_neuron}_{get_range(secondary_value)}"
        ]
        
        # Add MEANINGFUL action context (not just "none")
        meaningful_actions = [a for a in self.recent_actions[-3:] if a and a != 'none' and a != 'idle']
        if meaningful_actions:
            last_action = meaningful_actions[-1].lower()
            # Categorize more specifically
            if 'rock' in last_action:
                pattern_parts.append("rock_interaction")
            elif 'poop' in last_action:
                pattern_parts.append("waste_avoidance")
            elif 'food' in last_action or 'eat' in last_action:
                pattern_parts.append("food_consumption")
            elif 'plant' in last_action:
                pattern_parts.append("comfort_seeking")
            elif 'sleep' in last_action:
                pattern_parts.append("rest_behavior")
            else:
                pattern_parts.append(f"action_{last_action[:20]}")
        
        # Add environmental context if relevant
        env = self.environmental_state
        if env.get('food_count', 0) > 0 and 'hunger' in motivational_neurons:
            pattern_parts.append("food_present")
        if env.get('poop_count', 0) > 2:
            pattern_parts.append("filthy_environment")
        if env.get('has_rock', False) and 'curiosity' in motivational_neurons:
            pattern_parts.append("rock_present")
        
        pattern = "_".join(pattern_parts)
        #print(f"    📊 Generated pattern: {pattern}")  # DEBUG LOG
        return pattern
    
    
    def get_parent_pattern(self) -> str:
        """
        Get a broader parent pattern for hierarchical grouping.
        This allows you to group related specific patterns together.
        """
        # Filter out ALL binary state neurons (anything starting with 'is_')
        # We only want motivational/drive neurons (hunger, happiness, curiosity, etc.)
        motivational_neurons = {k: v for k, v in self.active_neurons.items() 
                                if not k.startswith('is_') and k not in [
                                    'position', 'direction', 'status',
                                    'pursuing_food',
                                    'novelty_exposure', 'sustained_stress', 'recent_rewards', 'personality',
                                    'neurogenesis_active'
                                ]}
        
        # Get top 2 neurons (instead of 3) for broader matching
        top_neurons = sorted(motivational_neurons.items(), 
                            key=lambda x: abs(x[1] - 50), 
                            reverse=True)[:2]
        
        pattern = f"{self.trigger_type}_{self.outcome}"
        for neuron, activation in top_neurons:
            # Use broader ranges: low (0-40), high (60-100), omit mid
            if activation < 40:
                pattern += f"_{neuron}_low"
            elif activation > 60:
                pattern += f"_{neuron}_high"
            # Skip mid-range activations for parent pattern
        
        return pattern


class ExperienceBuffer:
    """Maintains a rolling buffer of recent experiences"""
    
    def __init__(self, max_size=50):
        self.buffer = deque(maxlen=max_size)
        self.pattern_counts = {}  # Track frequency of specific patterns
        self.parent_pattern_counts = {}  # Track frequency of parent patterns
        
    def add_experience(self, context: ExperienceContext):
        """Add a new experience and update pattern tracking"""
        self.buffer.append(context)
        
        # Track specific pattern
        pattern = context.get_pattern_signature()
        self.pattern_counts[pattern] = self.pattern_counts.get(pattern, 0) + 1
        
        # Track parent pattern
        parent = context.get_parent_pattern()
        self.parent_pattern_counts[parent] = self.parent_pattern_counts.get(parent, 0) + 1
        
    def should_create_specialized_neuron(self, pattern: str, threshold=5) -> bool:
        """Check if a pattern occurs frequently enough to warrant a specialized neuron"""
        return self.pattern_counts.get(pattern, 0) >= threshold
    
    # In neurogenesis.py, replace is_pattern_over_clustered and add pattern validation:

    def is_pattern_over_clustered(self, pattern: str, max_occurrences: int = 20) -> bool:
        """
        STRICT check - if pattern appears more than max_occurrences, BLOCK it.
        """
        count = self.pattern_counts.get(pattern, 0)
        is_over = count > max_occurrences
        
        if is_over:
            print(f"      ⚠️ Pattern '{pattern}' appears {count} times (limit: {max_occurrences})")
            # Clear old entries to prevent infinite growth
            if count > max_occurrences * 2:
                self.pattern_counts[pattern] = max_occurrences
        
        return is_over


    def should_create_specialized_neuron(self, pattern: str, threshold: int = 5) -> bool:
        """
        Check if pattern is recurring ENOUGH but not over-clustered.
        """
        count = self.pattern_counts.get(pattern, 0)
        
        # Too few = not significant
        if count < threshold:
            print(f"      Pattern '{pattern}' count: {count}/{threshold} (too low)")
            return False
        
        # Too many = over-clustered
        if self.is_pattern_over_clustered(pattern):
            return False
        
        print(f"      ✅ Pattern '{pattern}' passed: {count}/{threshold} reps")
        return True
    
    def get_pattern_specificity(self, context: ExperienceContext) -> str:
        """
        Determine if we should use specific or parent pattern.
        Returns 'specific', 'parent', or 'too_generic'.
        """
        specific = context.get_pattern_signature()
        parent = context.get_parent_pattern()
        
        specific_count = self.pattern_counts.get(specific, 0)
        parent_count = self.parent_pattern_counts.get(parent, 0)
        
        # If parent pattern is over-clustered, this whole category is too generic
        if parent_count > 50:
            return 'too_generic'
        
        # If specific pattern is over-clustered, use parent instead
        if specific_count > 20:
            return 'parent'
        
        # Otherwise use specific pattern
        return 'specific'
    
    def get_recent_similar_experiences(self, context: ExperienceContext, 
                                       lookback=10) -> List[ExperienceContext]:
        """Find similar recent experiences"""
        target_pattern = context.get_pattern_signature()
        similar = []
        
        for exp in list(self.buffer)[-lookback:]:
            if exp.get_pattern_signature() == target_pattern:
                similar.append(exp)
                
        return similar


class FunctionalNeuron:
    """Represents a neuron with a specific functional role"""
    
    def __init__(self, name: str, neuron_type: str, creation_context: ExperienceContext):
        self.name = name
        self.neuron_type = neuron_type
        self.creation_context = creation_context
        self.specialization = self._determine_specialization()
        self.activation_count = 0
        self.last_activated = 0
        self.utility_score = 0.0
        self.strength_multiplier = 1.0
        
    def _determine_specialization(self) -> str:
        """Determine what this neuron specializes in based on creation context"""
        # Example specializations:
        # - "hunger_relief" for reward neurons created after eating
        # - "poop_avoidance" for stress neurons created near poop
        # - "rock_curiosity" for novelty neurons created when discovering rocks
        
        ctx = self.creation_context
        
        if ctx.trigger_type == 'reward':
            if 'is_eating' in ctx.active_neurons:
                return 'feeding_satisfaction'
            elif 'cleanliness' in ctx.active_neurons and ctx.outcome == 'positive':
                return 'cleanliness_reward'
            else:
                return 'general_reward'
                
        elif ctx.trigger_type == 'stress':
            if ctx.active_neurons.get('hunger', 50) > 70:
                return 'hunger_stress_response'
            elif ctx.active_neurons.get('cleanliness', 50) < 30:
                return 'filth_avoidance'
            elif ctx.active_neurons.get('anxiety', 50) > 70:
                return 'anxiety_regulation'
            else:
                return 'general_stress_coping'
                
        elif ctx.trigger_type == 'novelty':
            # Check what was novel
            if 'rock' in str(ctx.environmental_state):
                return 'object_investigation'
            elif 'new_location' in ctx.recent_actions:
                return 'exploration_memory'
            else:
                return 'general_novelty_processing'
                
        return 'undefined'
    
    def get_functional_connections(self, all_neurons: List[str]) -> Dict[str, float]:
        """
        Determine which neurons this should connect to based on its function.
        Returns dict of {neuron_name: weight}
        """
        connections = {}
        ctx = self.creation_context
        
        # Connect strongly to neurons that were highly active during creation
        for neuron, activation in ctx.active_neurons.items():
            if neuron in all_neurons:
                # Weight based on how far from baseline (50) the neuron was
                deviation = abs(activation - 50)
                if deviation > 20:  # Only connect if significant activation
                    weight = (deviation / 50) * 0.8  # Scale to 0-0.8
                    if activation < 50:
                        weight = -weight  # Negative connection for inhibition
                    connections[neuron] = weight
        
        # Add specialization-specific connections
        spec_connections = self._get_specialization_connections(all_neurons)
        connections.update(spec_connections)
        
        return connections
    
    def _get_specialization_connections(self, all_neurons: List[str]) -> Dict[str, float]:
        """Get connections based on neuron's specialization"""
        connections = {}
        
        if self.specialization == 'feeding_satisfaction':
            # Should inhibit hunger and boost happiness
            if 'hunger' in all_neurons:
                connections['hunger'] = -0.7
            if 'happiness' in all_neurons:
                connections['happiness'] = 0.6
            if 'satisfaction' in all_neurons:
                connections['satisfaction'] = 0.8
                
        elif self.specialization == 'hunger_stress_response':
            # Should activate when hungry and trigger food-seeking
            if 'hunger' in all_neurons:
                connections['hunger'] = 0.7
            if 'anxiety' in all_neurons:
                connections['anxiety'] = 0.5
            if 'curiosity' in all_neurons:
                connections['curiosity'] = 0.4  # Look for food
                
        elif self.specialization == 'filth_avoidance':
            # Should activate when dirty and promote movement
            if 'cleanliness' in all_neurons:
                connections['cleanliness'] = -0.8  # Strongly anticorrelated
            if 'anxiety' in all_neurons:
                connections['anxiety'] = 0.6
        
        elif self.specialization == 'anxiety_regulation':
            # Emergency stress neuron - calms the squid down
            if 'anxiety' in all_neurons:
                connections['anxiety'] = -0.8  # Strong inhibitory effect
            if 'happiness' in all_neurons:
                connections['happiness'] = 0.4  # Mild calming boost
            if 'satisfaction' in all_neurons:
                connections['satisfaction'] = 0.3  # Sense of coping
                
        elif self.specialization == 'object_investigation':
            # Should boost curiosity and reduce anxiety around objects
            if 'curiosity' in all_neurons:
                connections['curiosity'] = 0.7
            if 'anxiety' in all_neurons:
                connections['anxiety'] = -0.4
                
        # Add more specializations as needed
        
        return connections
    
    def calculate_activation(self, brain_state: Dict[str, float], 
                           weights: Dict[Tuple[str, str], float]) -> float:
        """
        Calculate how activated this neuron should be based on current brain state.
        This determines the neuron's current value.
        """
        activation = 50.0  # Baseline
        
        # Get all connections to this neuron
        for (source, target), weight in weights.items():
            if target == self.name and source in brain_state:
                # Apply weighted input from connected neuron
                source_activation = brain_state[source]
                # Use deviation from baseline
                influence = (source_activation - 50) * weight
                activation += influence
        
        # Clamp to valid range
        activation = max(0, min(100, activation))
        
        # Track usage
        if abs(activation - 50) > 15:  # Significant activation
            self.activation_count += 1
            self.last_activated = time.time()
            
        return activation
    
    def update_utility_score(self, outcome_value: float):
        """
        Update how useful this neuron has been based on outcomes.
        Used for pruning decisions.
        """
        # Exponential moving average
        alpha = 0.3
        self.utility_score = alpha * outcome_value + (1 - alpha) * self.utility_score


class EnhancedNeurogenesis:
    """
    Main neurogenesis controller that creates functional neurons
    """
    
    def __init__(self, brain_widget, config):
        self.brain_widget = brain_widget
        self.config = config
        self.experience_buffer = ExperienceBuffer()
        self.functional_neurons = {}  # name -> FunctionalNeuron
        self.novelty_neuron_count = 0
        self._awarded_neurons = set()
        
        # Track last creation time per trigger type to prevent rapid-fire creation
        self.last_creation_by_type = {
            'novelty': 0,
            'stress': 0,
            'reward': 0
        }
        
    def capture_experience_context(self, trigger_type: str,
                           brain_state: dict,
                           recent_actions: list,
                           environment: dict) -> ExperienceContext:
        """
        Capture experience but DON'T buffer during first 3 seconds.
        """
        # Initialize first tick marker
        if not hasattr(self, '_first_real_tick'):
            self._first_real_tick = time.time()
            print(f"   ⏱️ First real tick recorded at t=0")
        
        # Helper for safe number conversion
        def _num(v):
            try:
                return float(v)
            except Exception:
                return 50.0
        
        # Clean neurons AT SOURCE - remove ALL binary flags and neurogenesis metrics
        clean_neurons = {
            k: _num(v)
            for k, v in brain_state.items()
            if not k.startswith('is_') and k not in [
                'novelty_exposure', 'sustained_stress', 'recent_rewards',
                'neurogenesis_active', 'personality', 'pursuing_food',
                'position', 'direction', 'status'
            ]
        }
        
        ctx = ExperienceContext(
            trigger_type=trigger_type,
            active_neurons=clean_neurons,
            recent_actions=recent_actions[-5:] if recent_actions else [],
            environmental_state=environment,
            outcome='positive' if brain_state.get('happiness', 50) > 60 else
                    'negative' if brain_state.get('anxiety', 50) > 70 else
                    'neutral',
            timestamp=time.time()
        )
        
        # === GRACE PERIOD ENFORCEMENT ===
        elapsed = time.time() - self._first_real_tick
        if elapsed < 3.0:
            print(f"   ⏳ Grace period: {elapsed:.1f}s elapsed, NOT buffering")
            return ctx
        
        # === FILTER PEACEFUL SLEEP ===
        # Don't create neurons during restful sleep with no significant actions
        is_sleeping = brain_state.get('is_sleeping', False)
        anxiety = brain_state.get('anxiety', 50)
        satisfaction = brain_state.get('satisfaction', 50)
        
        # Check if truly peaceful (low anxiety) sleep
        if is_sleeping and anxiety < 20 and satisfaction > 80:
            print(f"   😴 Peaceful sleep detected, NOT buffering")
            return ctx
        
        # === BUFFER THE EXPERIENCE ===
        #print(f"   📝 Buffering experience: {ctx.get_pattern_signature()}")
        self.experience_buffer.add_experience(ctx)
        
        return ctx
    
    def _get_unique_neuron_name(self, base_name: str) -> str:
        """
        Generate truly unique names without creating duplicates.
        Checks both functional_neurons AND brain_widget.neuron_positions
        """
        # First check if base name exists exactly
        if base_name not in self.brain_widget.neuron_positions:
            return base_name
        
        # Find the next available number (start from 2, not 1)
        counter = 2
        while True:
            candidate = f"{base_name}_{counter}"
            if candidate not in self.brain_widget.neuron_positions:
                return candidate
            counter += 1

    
    def should_create_neuron(self, ctx: ExperienceContext) -> bool:
        """
        STRICT checking with explicit logging for every failure reason.
        """
        current_time = time.time()
        
        # === BLOCK 0: Grace Period & Basic Checks ===
        if not hasattr(self, '_first_real_tick'):
            print("   ❌ BLOCKED: No first tick recorded")
            return False
            
        elapsed_since_start = current_time - self._first_real_tick
        if elapsed_since_start < 10.0:
            print(f"   ❌ BLOCKED: Only {elapsed_since_start:.1f}s elapsed (need 10s)")
            return False
        
        # === BLOCK 1: Pattern Specificity Check ===
        pattern = ctx.get_pattern_signature()
        if len(pattern.split('_')) < 5:  # Require at least 5 parts for specificity
            print(f"   ❌ BLOCKED: Pattern too generic ({len(pattern.split('_'))} parts)")
            return False
        
        # === BLOCK 2: Over-Clustering Check (AGGRESSIVE) ===
        pattern_count = self.experience_buffer.pattern_counts.get(pattern, 0)
        if pattern_count > 20:  # STRICTLY enforce the 20 limit
            print(f"   ❌ BLOCKED: Pattern over-clustered ({pattern_count} > 20)")
            print(f"      Pattern: {pattern}")
            return False
        
        # === BLOCK 3: Parent Pattern Check ===
        parent = ctx.get_parent_pattern()
        parent_count = self.experience_buffer.parent_pattern_counts.get(parent, 0)
        if parent_count > 50:
            print(f"   ❌ BLOCKED: Parent pattern over-clustered ({parent_count} > 50)")
            return False
        
        # === BLOCK 4: Optimal State Check ===
        satisfaction = ctx.active_neurons.get('satisfaction', 50)
        anxiety = ctx.active_neurons.get('anxiety', 50)
        
        # If squid is perfectly content, no need for new neurons
        if satisfaction > 85 and anxiety < 15:
            print(f"   ❌ BLOCKED: Optimal state (sat={satisfaction}, anx={anxiety})")
            return False
        
        # === BLOCK 5: Max Neurons Check ===
        current_count = len(self.brain_widget.neuron_positions)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_count >= max_neurons:
            print(f"   ❌ BLOCKED: Max neurons reached ({current_count}/{max_neurons})")
            return False
        
        # === BLOCK 6: Cooldown Checks (ENFORCED) ===
        global_cooldown = self.config.neurogenesis.get('cooldown', 120)
        last_creation = max(
            (n.creation_context.timestamp for n in self.functional_neurons.values()),
            default=self._first_real_tick
        )
        
        time_since_last = current_time - last_creation
        if time_since_last < global_cooldown:
            remaining = global_cooldown - time_since_last
            #print(f"   ❌ BLOCKED: Global cooldown ({remaining:.1f}s left)")
            return False
        
        # Per-type cooldown
        last_type = self.last_creation_by_type.get(ctx.trigger_type, 0)
        per_type_cooldown = self.config.neurogenesis.get('per_type_cooldown', 30)
        time_since_type = current_time - last_type
        
        if time_since_type < per_type_cooldown:
            remaining = per_type_cooldown - time_since_type
            print(f"   ❌ BLOCKED: Per-type cooldown ({remaining:.1f}s left)")
            return False
        
        # === BLOCK 7: Recurrence Threshold (VARIES BY TYPE) ===
        if ctx.trigger_type == 'novelty':
            # Novelty needs MORE repetition to be significant
            needed = 5 + (self.novelty_neuron_count * 2)
            if pattern_count < needed:
                print(f"   ❌ BLOCKED: Novelty needs {needed} reps (has {pattern_count})")
                return False
        else:  # stress/reward
            if pattern_count < 5:
                print(f"   ❌ BLOCKED: Need 5 reps (has {pattern_count})")
                return False
        
        # === BLOCK 8: Duplicate Prevention ===
        for existing_name, existing_neuron in self.functional_neurons.items():
            if existing_neuron.creation_context.get_pattern_signature() == pattern:
                if existing_neuron.utility_score > 0.3:
                    print(f"   ❌ BLOCKED: Duplicate with utility {existing_neuron.utility_score:.2f}")
                    return False
        
        # === BLOCK 9: Personality Starter Neuron Cap ===
        if ctx.trigger_type == 'personality_starter':
            # Only allow ONE starter neuron
            starters = [n for n in self.functional_neurons.values() 
                    if n.creation_context.trigger_type == 'personality_starter']
            if len(starters) >= 1:
                print(f"   ❌ BLOCKED: Already have personality starter")
                return False
        
        # === ALLOW CREATION ===
        print(f"   ✅ ALLOWED: All checks passed for '{pattern}'")
        return True
    
    def _preview_specialisation(self, ctx: ExperienceContext) -> str:
        """
        Return the specialisation a neuron would receive *without* creating it.
        Keeps the same rules as FunctionalNeuron._determine_specialisation
        but can be called before birth.
        """
        # ----- reward branch -----
        if ctx.trigger_type == 'reward':
            if ctx.active_neurons.get('is_eating', 0) > 50:          # MUST have eaten
                return 'feeding_satisfaction'
            if ctx.active_neurons.get('cleanliness', 50) < 30 and ctx.outcome == 'positive':
                return 'cleanliness_reward'
            return 'general_reward'

        # ----- stress branch -----
        if ctx.trigger_type == 'stress':
            if ctx.active_neurons.get('hunger', 50) > 70:
                return 'hunger_stress_response'
            if ctx.active_neurons.get('cleanliness', 50) < 30:
                return 'filth_avoidance'
            if ctx.active_neurons.get('anxiety', 50) > 70:
                return 'anxiety_regulation'
            return 'general_stress_coping'

        # ----- novelty branch -----
        if ctx.trigger_type == 'novelty':
            if 'rock' in str(ctx.environmental_state):
                return 'object_investigation'
            if 'new_location' in ctx.recent_actions:
                return 'exploration_memory'
            return 'general_novelty_processing'

        return 'undefined'
    
    def create_functional_neuron(self, context: ExperienceContext) -> Optional[str]:
        """
        Create a new neuron with a specific function based on experience context.
        Now includes per-specialization caps for ALL trigger types.
        Also strengthens existing neurons when caps are reached.
        """
        # Preview specialization before creating
        spec = self._preview_specialization(context)
        base_name = f"{context.trigger_type}_{spec}"
        
        # FIX: Apply specialization cap to ALL trigger types including novelty
        max_per_spec = self.config.neurogenesis.get('max_per_specialization', 3)
        current_count = sum(1 for name in self.brain_widget.neuron_positions.keys() 
                            if name.startswith(f"{context.trigger_type}_{spec}"))
        
        if current_count >= max_per_spec:
            # Strengthen existing neuron instead of creating duplicate
            self._strengthen_existing_neuron(context.trigger_type, spec)
            return None  # Skip creation
        
        # Novelty-specific cap check (existing logic)
        if context.trigger_type == 'novelty':
            max_novelty = self.config.neurogenesis.get('max_novelty_neurons', 5)
            self._validate_novelty_counter()
            if self.novelty_neuron_count >= max_novelty:
                return None

        # Create unique neuron name
        counter = 0
        neuron_name = self._get_unique_neuron_name(base_name)

        # Create and register the functional neuron
        func_neuron = FunctionalNeuron(neuron_name, context.trigger_type, context)
        self.functional_neurons[neuron_name] = func_neuron

        # Update novelty counter
        if context.trigger_type == 'novelty':
            self.novelty_neuron_count += 1

        # Record creation time
        self.last_creation_by_type[context.trigger_type] = time.time()

        # Calculate position, appearance, and connections
        position = self._calculate_functional_position(func_neuron)
        self.brain_widget.neuron_positions[neuron_name] = position
        self._set_neuron_appearance(neuron_name, func_neuron)

        # Build connections
        all_neurons = list(self.brain_widget.neuron_positions.keys())
        connections = func_neuron.get_functional_connections(all_neurons)
        for target, weight in connections.items():
            if target in self.brain_widget.neuron_positions:
                self.brain_widget.weights[(neuron_name, target)] = weight
                self.brain_widget.weights[(target, neuron_name)] = weight * 0.3

        # Initialize state
        self.brain_widget.state[neuron_name] = 50.0

        # Award points for new neuron creation
        if neuron_name not in self._awarded_neurons:
            self._awarded_neurons.add(neuron_name)
            if hasattr(self.brain_widget, 'statistics_tab'):
                self.brain_widget.statistics_tab.increment_stat('points', 500)

        # Set up visual highlight
        is_emergency = context.trigger_type == 'stress' and context.active_neurons.get('anxiety', 50) > 80
        self.brain_widget.neurogenesis_highlight = {
            'neuron': neuron_name,
            'start_time': time.time(),
            'duration': 8.0 if is_emergency else 5.0,
            'pulse_phase': 0,
            'is_emergency': is_emergency
        }

        print(f"🧠 Created functional neuron: {neuron_name}")
        print(f"   Specialisation: {func_neuron.specialization}")
        print(f"   Connections: {len(connections)}")

        return neuron_name
    
    def _strengthen_existing_neuron(self, trigger_type: str, specialization: str):
        """Strengthen existing neuron instead of creating duplicate"""
        existing = []
        for name, neuron in self.functional_neurons.items():
            if name.startswith(f"{trigger_type}_{specialization}"):
                existing.append((name, neuron))
        
        if not existing:
            return
        
        # Pick the one with highest utility
        existing.sort(key=lambda x: x[1].utility_score, reverse=True)
        best_name, best_neuron = existing[0]
        
        # Increase multiplier by 0.5x (so 1.0 → 1.5 → 2.0 → etc.)
        best_neuron.strength_multiplier += 0.5
        best_neuron.utility_score += 0.1
        
        # Add visual pulse effect
        self.brain_widget.communication_events[best_name] = time.time()
        
        print(f"   💪 Strengthened {specialization} neuron: {best_name}")
        print(f"      New multiplier: {best_neuron.strength_multiplier:.1f}x")
        
        # Force visual update
        self.brain_widget.update()
    
    def _preview_specialization(self, context: ExperienceContext) -> str:
        """Preview what specialization a neuron would get"""
        temp_neuron = FunctionalNeuron("temp", context.trigger_type, context)
        return temp_neuron.specialization
    
    def _calculate_functional_position(self, func_neuron: FunctionalNeuron) -> Tuple[float, float]:
        """
        Position neuron based on its functional relationships.
        Neurons with similar functions should be near each other.
        """
        # Get positions of strongly connected neurons
        all_neurons = list(self.brain_widget.neuron_positions.keys())
        connections = func_neuron.get_functional_connections(all_neurons)
        
        if not connections:
            # Fallback to random position
            return (random.randint(100, 900), random.randint(100, 600))
        
        # Calculate center of mass of connected neurons
        total_weight = 0
        center_x, center_y = 0, 0
        
        for target, weight in connections.items():
            if target in self.brain_widget.neuron_positions:
                pos = self.brain_widget.neuron_positions[target]
                abs_weight = abs(weight)
                center_x += pos[0] * abs_weight
                center_y += pos[1] * abs_weight
                total_weight += abs_weight
        
        if total_weight > 0:
            center_x /= total_weight
            center_y /= total_weight
            
            # Add some randomness but keep it near the functional cluster
            offset_x = random.randint(-80, 80)
            offset_y = random.randint(-80, 80)
            
            x = max(50, min(974, center_x + offset_x))
            y = max(50, min(668, center_y + offset_y))
            
            return (x, y)
        
        return (random.randint(100, 900), random.randint(100, 600))
    
    def _set_neuron_appearance(self, name: str, func_neuron: FunctionalNeuron):
        """Set visual appearance based on function"""
        # Shape based on specialization
        if 'stress' in func_neuron.specialization or 'anxiety' in func_neuron.specialization:
            self.brain_widget.neuron_shapes[name] = 'square'
            self.brain_widget.state_colors[name] = (255, 150, 150)
        elif 'reward' in func_neuron.specialization or 'satisfaction' in func_neuron.specialization:
            self.brain_widget.neuron_shapes[name] = 'triangle'
            self.brain_widget.state_colors[name] = (150, 255, 150)
        elif 'investigation' in func_neuron.specialization or 'exploration' in func_neuron.specialization:
            self.brain_widget.neuron_shapes[name] = 'diamond'
            self.brain_widget.state_colors[name] = (255, 215, 0)
        else:
            self.brain_widget.neuron_shapes[name] = 'circle'
            self.brain_widget.state_colors[name] = (200, 200, 255)
    
    def update_neuron_activations(self, brain_state: Dict[str, float]):
        """Update all functional neurons based on current brain state"""
        # First, update all functional neuron activations
        for name, func_neuron in self.functional_neurons.items():
            if name in self.brain_widget.state:
                # Check if this is a full FunctionalNeuron object with methods
                if hasattr(func_neuron, 'calculate_activation'):
                    activation = func_neuron.calculate_activation(
                        brain_state, 
                        self.brain_widget.weights
                    )
                else:
                    # Fallback for FunctionalNeuronData or other simple objects
                    # Use a simple weighted sum calculation
                    activation = 50.0  # Baseline
                    for (source, target), weight in self.brain_widget.weights.items():
                        if target == name and source in brain_state:
                            source_activation = brain_state[source]
                            influence = (source_activation - 50) * weight
                            activation += influence
                    activation = max(0, min(100, activation))
                
                self.brain_widget.state[name] = activation
        
        # COPING MECHANISM: Apply direct anxiety reduction from stress neurons
        # Count active stress/anxiety_regulation neurons
        stress_neurons = [
            (name, func_neuron) 
            for name, func_neuron in self.functional_neurons.items() 
            if hasattr(func_neuron, 'specialization') and 
               func_neuron.specialization == 'anxiety_regulation'
        ]
        
        if stress_neurons and 'anxiety' in brain_state:
            # Each stress neuron provides a "numbing" effect
            base_reduction_per_neuron = 8.0  # Base reduction per neuron
            
            # Calculate total reduction based on:
            # 1. Number of stress neurons (cumulative coping mechanisms)
            # 2. How activated they are (stronger when anxiety is high)
            total_reduction = 0.0
            for name, func_neuron in stress_neurons:
                neuron_activation = self.brain_widget.state.get(name, 50)
                # Neuron is more active when anxiety is high (it responds to stress)
                activation_factor = (neuron_activation - 50) / 50  # 0 to 1 scale
                activation_factor = max(0, activation_factor)  # Only positive influence
                
                # Each neuron contributes based on how active it is
                reduction = base_reduction_per_neuron * (0.5 + 0.5 * activation_factor)
                total_reduction += reduction
            
            # Cap the maximum reduction to prevent anxiety going negative
            # But allow strong reduction with multiple neurons
            max_reduction = min(total_reduction, brain_state['anxiety'] * 0.95)
            
            # Apply the reduction directly to anxiety
            new_anxiety = brain_state['anxiety'] - max_reduction
            brain_state['anxiety'] = max(0, new_anxiety)
            
            # Also update the brain widget state
            if 'anxiety' in self.brain_widget.state:
                self.brain_widget.state['anxiety'] = brain_state['anxiety']
            
            # Slight satisfaction boost from coping (learned to manage stress)
            if 'satisfaction' in brain_state:
                coping_satisfaction = min(5.0 * len(stress_neurons), 15.0)
                brain_state['satisfaction'] = min(100, brain_state['satisfaction'] + coping_satisfaction)
                if 'satisfaction' in self.brain_widget.state:
                    self.brain_widget.state['satisfaction'] = brain_state['satisfaction']
    
    def intelligent_pruning(self) -> Optional[str]:
        """
        Prune neurons based on utility, not just weak connections.
        Keep neurons that are:
        1. Frequently used
        2. Have positive utility scores
        3. Serve unique functions
        """
        candidates = []
        
        for name, func_neuron in self.functional_neurons.items():
            # Don't prune recently created neurons
            if time.time() - func_neuron.creation_context.timestamp < 300:  # 5 minutes
                continue
            
            # Calculate pruning score (lower = more likely to prune)
            score = 0.0
            
            # Factor 1: Utility score
            score += func_neuron.utility_score * 0.4
            
            # Factor 2: Usage frequency
            recency = time.time() - func_neuron.last_activated
            if recency < 300:  # Used in last 5 minutes
                score += 0.3
            elif recency < 1800:  # Used in last 30 minutes
                score += 0.15
            
            # Factor 3: Unique specialization
            similar_count = sum(1 for n in self.functional_neurons.values() 
                              if n.specialization == func_neuron.specialization)
            if similar_count == 1:
                score += 0.3  # Keep unique specialists
            
            # Factor 4: Connection strength
            total_connection_strength = sum(
                abs(w) for (a, b), w in self.brain_widget.weights.items()
                if a == name or b == name
            )
            score += min(total_connection_strength / 5.0, 0.3)
            
            candidates.append((name, score))
        
        if not candidates:
            return None
        
        # Prune the neuron with the lowest score
        candidates.sort(key=lambda x: x[1])
        neuron_to_prune = candidates[0][0]
        
        # Remove from brain
        if neuron_to_prune in self.brain_widget.neuron_positions:
            del self.brain_widget.neuron_positions[neuron_to_prune]
        if neuron_to_prune in self.brain_widget.state:
            del self.brain_widget.state[neuron_to_prune]
        
        # Remove connections
        for conn in list(self.brain_widget.weights.keys()):
            if neuron_to_prune in conn:
                del self.brain_widget.weights[conn]
        
        # Remove from functional neurons - FIX: Update novelty counter
        if neuron_to_prune in self.functional_neurons:
            func_neuron = self.functional_neurons[neuron_to_prune]
            if func_neuron.neuron_type == 'novelty':
                self.novelty_neuron_count -= 1  # Decrement counter when pruning novelty neuron
            del self.functional_neurons[neuron_to_prune]

        print(f"🗑️ Pruned: {neuron_to_prune} (score: {candidates[0][1]:.2f})")
        if func_neuron.neuron_type == 'novelty':
            print(f"   └─ Novelty counter decremented to: {self.novelty_neuron_count}")

        return neuron_to_prune
    
    def _validate_novelty_counter(self):
        """Ensure novelty_neuron_count matches actual novelty neurons in the brain"""
        # Count directly from brain widget (source of truth)
        actual_count = sum(1 for name in self.brain_widget.neuron_positions.keys() 
                        if name.startswith('novelty_'))
        
        if self.novelty_neuron_count != actual_count:
            print(f"⚠️ Novelty counter mismatch: tracked={self.novelty_neuron_count}, actual={actual_count}")
            self.novelty_neuron_count = actual_count
            print(f"   └─ Counter corrected to: {actual_count}")
    
    def create_personality_starter_neuron(self, personality_type: str, brain_state: Dict[str, float]):
        """
        Creates a specialized starting neuron based on the squid's personality.
        This gives each personality type the "best start in life" with a neuron 
        that supports their natural tendencies.
        
        Args:
            personality_type: The personality type string (e.g., 'timid', 'greedy')
            brain_state: Current brain state to use for context
        
        Returns:
            Name of the created neuron, or None if invalid personality
        """
        personality_lower = personality_type.lower()
        
        # Define personality-specific neuron templates
        personality_neurons = {
            'timid': {
                'name': 'timid_caution',
                'specialization': 'anxiety_heightening',
                'description': 'Makes the squid naturally anxious and cautious',
                'trigger_type': 'stress',
                'outcome': 'neutral',
                'active_neurons': {
                    'anxiety': 65,  # Slightly elevated baseline
                    'curiosity': 35,  # Lower curiosity
                    'satisfaction': 45
                },
                'connections': {
                    'anxiety': 0.6,  # Amplifies anxiety
                    'curiosity': -0.5,  # Inhibits curiosity
                    'satisfaction': -0.3  # Slight dissatisfaction
                }
            },
            'adventurous': {
                'name': 'explorer_drive',
                'specialization': 'exploration_motivation',
                'description': 'Drives the squid to explore and investigate',
                'trigger_type': 'novelty',
                'outcome': 'positive',
                'active_neurons': {
                    'curiosity': 70,  # High curiosity
                    'happiness': 60,  # Enjoys exploring
                    'anxiety': 35  # Lower anxiety
                },
                'connections': {
                    'curiosity': 0.7,  # Strong curiosity boost
                    'happiness': 0.4,  # Happiness from exploration
                    'anxiety': -0.4  # Reduces anxiety
                }
            },
            'lazy': {
                'name': 'energy_conservation',
                'specialization': 'activity_suppression',
                'description': 'Conserves energy and reduces movement drive',
                'trigger_type': 'stress',
                'outcome': 'neutral',
                'active_neurons': {
                    'sleepiness': 60,  # More sleepy
                    'satisfaction': 55,  # Content doing nothing
                    'curiosity': 40  # Lower activity drive
                },
                'connections': {
                    'sleepiness': 0.5,  # Encourages rest
                    'satisfaction': 0.4,  # Happy being lazy
                    'curiosity': -0.6  # Suppresses exploration
                }
            },
            'energetic': {
                'name': 'restless_activity',
                'specialization': 'hyperactivity_drive',
                'description': 'Drives constant movement and activity',
                'trigger_type': 'novelty',
                'outcome': 'neutral',
                'active_neurons': {
                    'curiosity': 65,  # High activity
                    'sleepiness': 35,  # Resists sleep
                    'happiness': 55  # Energized
                },
                'connections': {
                    'curiosity': 0.6,  # Drives exploration
                    'sleepiness': -0.7,  # Strongly resists sleep
                    'anxiety': 0.3  # Slight restlessness
                }
            },
            'introvert': {
                'name': 'solitude_preference',
                'specialization': 'solitude_comfort',
                'description': 'Finds comfort in solitude and avoids stimulation',
                'trigger_type': 'stress',
                'outcome': 'positive',
                'active_neurons': {
                    'satisfaction': 60,  # Content alone
                    'anxiety': 55,  # Slightly anxious in stimulation
                    'curiosity': 45  # Moderate curiosity
                },
                'connections': {
                    'satisfaction': 0.5,  # Happy when alone
                    'anxiety': 0.4,  # Anxious with too much going on
                    'happiness': 0.3  # Content in peace
                }
            },
            'greedy': {
                'name': 'insatiable_hunger',
                'specialization': 'food_obsession',
                'description': 'Always drives hunger and food-seeking behavior',
                'trigger_type': 'stress',
                'outcome': 'negative',
                'active_neurons': {
                    'hunger': 65,  # Always hungry
                    'curiosity': 60,  # Looking for food
                    'satisfaction': 40  # Never quite satisfied
                },
                'connections': {
                    'hunger': 0.7,  # Strong hunger drive
                    'curiosity': 0.5,  # Food-seeking
                    'satisfaction': -0.6  # Hard to satisfy
                }
            },
            'stubborn': {
                'name': 'sushi_preference',
                'specialization': 'food_selectivity',
                'description': 'Strong preference for sushi, rejection of cheese',
                'trigger_type': 'stress',
                'outcome': 'negative',
                'active_neurons': {
                    'satisfaction': 40,  # Picky and dissatisfied
                    'hunger': 60,  # Often hungry due to pickiness
                    'anxiety': 55  # Stress from unfulfilled preferences
                },
                'connections': {
                    'satisfaction': -0.5,  # Hard to please
                    'hunger': 0.6,  # Food-focused
                    'happiness': -0.4  # Grumpy when not getting sushi
                }
            }
        }
        
        # Get the personality template
        if personality_lower not in personality_neurons:
            print(f"⚠️ Unknown personality type: {personality_type}")
            return None
        
        template = personality_neurons[personality_lower]
        
        # Create experience context for this starter neuron
        context = ExperienceContext(
            trigger_type=template['trigger_type'],
            active_neurons=template['active_neurons'].copy(),
            recent_actions=['birth', 'initialization'],
            environmental_state={'food_count': 0, 'poop_count': 0, 'is_sick': False, 'is_eating': False},
            outcome=template['outcome'],
            timestamp=time.time()
        )
        
        # Create the functional neuron
        func_neuron = FunctionalNeuron(
            name=template['name'],
            neuron_type=template['trigger_type'],
            creation_context=context
        )
        
        # Override specialization with our custom one
        func_neuron.specialization = template['specialization']
        
        # Store it
        self.functional_neurons[template['name']] = func_neuron
        
        # Add to brain widget - position, appearance, and state
        position = self._calculate_functional_position(func_neuron)
        self.brain_widget.neuron_positions[template['name']] = position
        self._set_neuron_appearance(template['name'], func_neuron)
        self.brain_widget.state[template['name']] = 50.0
        
        # Set up connections based on template
        for target_neuron, weight in template['connections'].items():
            if target_neuron in self.brain_widget.state:
                self.brain_widget.weights[(template['name'], target_neuron)] = weight
                self.brain_widget.weights[(target_neuron, template['name'])] = weight * 0.5
        
        # Award points for this special neuron
        if hasattr(self.brain_widget, 'statistics_tab'):
            self.brain_widget.statistics_tab.increment_stat('points', 500)
        
        # Add highlight effect
        self.brain_widget.neurogenesis_highlight = {
            'neuron': template['name'],
            'start_time': time.time(),
            'duration': 8.0,  # Longer highlight for personality neuron
            'pulse_phase': 0,
            'is_emergency': False
        }
        
        print(f"🧬 Created personality starter neuron: {template['name']}")
        print(f"   └─ {template['description']}")
        
        return template['name']



# Integration example for TamagotchiLogic
class NeurogenesisTriggerSystem:
    """
    Replaces simple counter-based triggers with context-aware experience tracking
    """
    
    def __init__(self, tamagotchi_logic):
        self.logic = tamagotchi_logic
        self.recent_actions = deque(maxlen=10)
        self.last_states = deque(maxlen=5)
        
    def track_action(self, action: str):
        """Track what the squid is doing"""
        self.recent_actions.append(action)
    
    def track_state_change(self, state: Dict[str, float]):
        """Track brain state changes"""
        self.last_states.append(state.copy())
    
    def check_for_significant_experience(self) -> Optional[Tuple[str, ExperienceContext]]:
        """
        Check if something significant happened that warrants neurogenesis.
        Returns (trigger_type, context) or None.
        """
        if len(self.last_states) < 2:
            return None
        
        current = self.last_states[-1]
        previous = self.last_states[-2]
        
        # Additional filter: Ignore experiences when stats haven't changed meaningfully
        # Calculate total state change magnitude
        state_change = 0
        for key in ['hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity']:
            if key in current and key in previous:
                state_change += abs(current.get(key, 50) - previous.get(key, 50))
        
        # If total change is too small, nothing significant happened
        if state_change < 5 and not getattr(self.logic, 'new_object_encountered', False):
            return None
        
        # Check for significant novelty
        if self._detect_novelty_experience(current, previous):
            context = self._build_context('novelty', current)
            return ('novelty', context)
        
        # Check for significant stress
        if self._detect_stress_experience(current, previous):
            context = self._build_context('stress', current)
            return ('stress', context)
        
        # Check for significant reward
        if self._detect_reward_experience(current, previous):
            context = self._build_context('reward', current)
            return ('reward', context)
        
        return None
    
    def _detect_novelty_experience(self, current, previous) -> bool:
        """Detect if something novel happened"""
        # Don't trigger during sleep - sleeping squid shouldn't have novelty experiences
        if current.get('is_sleeping', False):
            return False
        
        # Check if curiosity spiked significantly (not just maxed out)
        current_curiosity = current.get('curiosity', 50)
        previous_curiosity = previous.get('curiosity', 50)
        curiosity_delta = current_curiosity - previous_curiosity
        
        # Ignore if curiosity is at extremes (0 or 100) - no meaningful change possible
        if current_curiosity >= 99 or current_curiosity <= 1:
            return False
        
        # Check if we encountered a new object (from logic flags)
        new_object = getattr(self.logic, 'new_object_encountered', False)
        
        # Require a significant spike AND curiosity to be reasonably high (not just tiny change)
        meaningful_spike = curiosity_delta > 15 and current_curiosity > 40
        
        return meaningful_spike or new_object
    
    def _detect_stress_experience(self, current, previous) -> bool:
        """Detect sustained or intense stress"""
        # Don't trigger during peaceful sleep (low anxiety + sleeping)
        if current.get('is_sleeping', False) and current.get('anxiety', 50) < 40:
            return False
        
        current_anxiety = current.get('anxiety', 50)
        previous_anxiety = previous.get('anxiety', 50)
        current_hunger = current.get('hunger', 50)
        a
        # Ignore if anxiety is at minimum (0-5) - can't go lower
        if current_anxiety <= 5:
            return False
        
        # High anxiety sustained (both readings must be genuinely high)
        anxiety_high = current_anxiety > 65 and previous_anxiety > 60
        
        # Sudden anxiety spike (must be substantial and anxiety must be high)
        anxiety_spike = (current_anxiety - previous_anxiety) > 15 and current_anxiety > 50
        
        # Hunger crisis - but only if it's actively increasing or very high
        hunger_crisis = current_hunger > 85 and (current_hunger - previous.get('hunger', 50)) >= 0
        
        return anxiety_high or anxiety_spike or hunger_crisis
    
    def _detect_reward_experience(self, current, previous) -> bool:
        """Detect positive outcome experiences"""
        # Don't trigger during sleep with maxed stats - that's just baseline contentment
        if current.get('is_sleeping', False):
            happiness = current.get('happiness', 50)
            satisfaction = current.get('satisfaction', 50)
            # If already very content while sleeping, this isn't a reward experience
            if happiness >= 90 and satisfaction >= 90:
                return False
        
        # Get current and previous values
        current_happiness = current.get('happiness', 50)
        previous_happiness = previous.get('happiness', 50)
        current_satisfaction = current.get('satisfaction', 50)
        previous_satisfaction = previous.get('satisfaction', 50)
        
        # Calculate deltas
        happiness_delta = current_happiness - previous_happiness
        satisfaction_delta = current_satisfaction - previous_satisfaction
        
        # Ignore if stats are already maxed out (99-100) - no reward to gain
        if (current_happiness >= 99 and previous_happiness >= 99) or \
           (current_satisfaction >= 99 and previous_satisfaction >= 99):
            return False
        
        # Ignore tiny fluctuations when stats are very high (95+)
        if current_happiness >= 95 and happiness_delta < 3:
            return False
        if current_satisfaction >= 95 and satisfaction_delta < 3:
            return False
        
        # Check if positive outcome flag is set (explicit reward action like feeding)
        positive_outcome = getattr(self.logic, 'recent_positive_outcome', False)
        
        # Require significant increases OR explicit positive action
        significant_happiness = happiness_delta > 15 and current_happiness > 40
        significant_satisfaction = satisfaction_delta > 15 and current_satisfaction > 40
        
        return significant_happiness or significant_satisfaction or positive_outcome
    
    def _build_context(self, trigger_type: str, current_state: Dict) -> ExperienceContext:
        """Build experience context from current situation"""
        # Filter out binary state neurons AND neurogenesis metrics
        filtered_neurons = {k: v for k, v in current_state.items() 
                        if not k.startswith('is_') and k not in [
                            'novelty_exposure', 'sustained_stress', 'recent_rewards', 
                            'neurogenesis_active', 'personality', 'pursuing_food', 'direction',  
                            'is_startled', 'is_fleeing', 'is_sick']}  # Add all binary flags here
        
        return ExperienceContext(
            trigger_type=trigger_type,
            active_neurons=filtered_neurons,  # Now clean!
            recent_actions=list(self.recent_actions),
            environmental_state={
                'food_count': len(self.logic.food_items),
                'poop_count': len(self.logic.poop_items),
                'is_sick': self.logic.squid.is_sick,
                'is_eating': current_state.get('is_eating', False)
            },
            outcome='neutral',  # Will be determined by neurogenesis system
            timestamp=time.time()
        )