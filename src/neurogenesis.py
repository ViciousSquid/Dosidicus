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
        """Generate specific signatures with action sequences and env deltas"""
        # Filter out ALL binary state neurons (anything starting with 'is_')
        # We only want motivational/drive neurons (hunger, happiness, curiosity, etc.)
        motivational_neurons = {k: v for k, v in self.active_neurons.items() 
                                if not k.startswith('is_')}
        
        # Get top 3 active neurons WITH ranges
        top_neurons = sorted(motivational_neurons.items(), 
                            key=lambda x: abs(x[1] - 50), 
                            reverse=True)[:3]
        
        # Start with trigger and outcome
        pattern = f"{self.trigger_type}_{self.outcome}"
        
        # Add action sequence (last 3 actions)
        recent_actions_str = "_".join(self.recent_actions[-3:]) if self.recent_actions else "none"
        pattern += f"_actions_{recent_actions_str}"
        
        # Add top neurons with their activation ranges
        for neuron, activation in top_neurons:
            # Bin activation into ranges
            if activation < 35:
                level = "low"
            elif activation < 65:
                level = "mid"
            else:
                level = "high"
            pattern += f"_{neuron}_{level}"
        
        # Add environmental deltas (changes, not static values)
        env = self.environmental_state
        if env.get('food_count', 0) == 0:
            pattern += "_nofreshfood"  # More specific than "nofood"
        if env.get('poop_count', 0) > 2:
            pattern += f"_dirty_{env['poop_count']}"  # Include count
        
        return pattern
    
    def get_parent_pattern(self) -> str:
        """
        Get a broader parent pattern for hierarchical grouping.
        This allows you to group related specific patterns together.
        """
        # Filter out ALL binary state neurons (anything starting with 'is_')
        # We only want motivational/drive neurons (hunger, happiness, curiosity, etc.)
        motivational_neurons = {k: v for k, v in self.active_neurons.items() 
                                if not k.startswith('is_')}
        
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
        
    def should_create_specialized_neuron(self, pattern: str, threshold=3) -> bool:
        """Check if a pattern occurs frequently enough to warrant a specialized neuron"""
        return self.pattern_counts.get(pattern, 0) >= threshold
    
    def is_pattern_over_clustered(self, pattern: str, max_occurrences=20) -> bool:
        """
        Check if a pattern has become over-clustered (too many occurrences).
        This suggests the pattern is too generic and grouping unrelated experiences.
        """
        return self.pattern_counts.get(pattern, 0) > max_occurrences
    
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
        Wrapper that records the *first real game tick* and then
        lets the experience buffer begin accepting samples only
        after 5 s have elapsed.
        """
        # Mark the very first real tick (once only)
        if not hasattr(self, '_first_real_tick'):
            self._first_real_tick = time.time()

        # Build the context object regardless
        ctx = ExperienceContext(
            trigger_type=trigger_type,
            active_neurons={k: v for k, v in brain_state.items()
                          if isinstance(v, (int, float))},
            recent_actions=recent_actions[-5:] if recent_actions else [],
            environmental_state=environment,
            outcome='positive' if brain_state.get('happiness', 50) > 60 else
                   'negative' if brain_state.get('anxiety', 50) > 70 else
                   'neutral',
            timestamp=time.time()
        )

        # Buffer it only *after* the 3-second grace period
        if time.time() - self._first_real_tick >= 3.0:
            # Additional filter: Don't capture experiences during peaceful sleep with no actions
            is_sleeping = brain_state.get('is_sleeping', False)
            has_recent_actions = len(recent_actions) > 0 and any(action for action in recent_actions if action != 'none')
            
            # Skip buffering if:
            # 1. Sleeping peacefully (low anxiety, high satisfaction)
            # 2. No recent meaningful actions
            # 3. Stats are all at extremes (nothing changing)
            if is_sleeping and not has_recent_actions:
                anxiety = brain_state.get('anxiety', 50)
                satisfaction = brain_state.get('satisfaction', 50)
                if anxiety < 20 and satisfaction > 80:
                    # Skip this experience - just peaceful sleep
                    return ctx
            
            self.experience_buffer.add_experience(ctx)

        return ctx
    
    def should_create_neuron(self, ctx: ExperienceContext) -> bool:
        """
        Prevents creation in optimal states, adds cooldown verification,
        and validates pattern specificity.
        """
        # 0. Never create on the very first game tick
        if not hasattr(self, '_first_real_tick'):
            return False

        # 0½. Wait at least 10 s after the first real tick
        if time.time() - self._first_real_tick < 10.0:
            return False

        # ===== NEW: BLOCK CREATION IN STABLE/OPTIMAL STATES =====
        # If squid is already perfectly satisfied and calm, don't create neurons
        satisfaction = ctx.active_neurons.get('satisfaction', 50)
        anxiety = ctx.active_neurons.get('anxiety', 50)
        curiosity = ctx.active_neurons.get('curiosity', 50)
        
        # If all key stats are within 20 points of optimal (100/0), block creation
        if (satisfaction > 80 and anxiety < 20 and curiosity > 80):
            print(f"    \033[92mSquid in optimal state\033[0m (sat={satisfaction}, anx={anxiety})")
            return False
        
        # If state hasn't changed meaningfully from baseline, block
        total_deviation = abs(satisfaction - 50) + abs(anxiety - 50) + abs(curiosity - 50)
        if total_deviation < 30:
            #print(f"   ❌ BLOCKED: State too neutral (deviation: {total_deviation})")
            return False
        # ============================================================

        # 4. Hard neuron-count ceiling (check early)
        current_count = len(self.brain_widget.neuron_positions)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_count >= max_neurons:
            #print(f"   ❌ BLOCKED: Max neurons ({max_neurons}) reached")
            return False

        # ===================================================================
        # EMERGENCY BYPASS: Critical stress overrides ALL cooldowns
        # ===================================================================
        is_critical_stress = anxiety >= 95
        if ctx.trigger_type == 'stress' and is_critical_stress:
            print(f"   🚨 EMERGENCY: Anxiety {anxiety:.0f} >= 95")
            pattern = ctx.get_pattern_signature()
            for neuron in self.functional_neurons.values():
                if neuron.creation_context.get_pattern_signature() == pattern:
                    if neuron.utility_score > 0.3:
                        print(f"   ⚠️ {neuron.name} handles this (utility={neuron.utility_score:.2f})")
                        return False
            #print(f"   ✅ Emergency neuron creation ")
            return True
        # ===================================================================

        # ===== NEW: COOLDOWN VERIFICATION WITH EXPLICIT PRINTS =====
        current_time = time.time()
        last_creation = max(
            (n.creation_context.timestamp for n in self.functional_neurons.values()),
            default=0
        )
        global_cooldown = self.config.neurogenesis.get('cooldown', 180)
        
        # Only enforce global cooldown after first 5 minutes
        if (current_time - self._first_real_tick) > 300.0:
            time_since_last = current_time - last_creation
            if time_since_last < global_cooldown:
                remaining = global_cooldown - time_since_last
                #print(f"   ❌ BLOCKED: Global cooldown - {remaining:.1f}s remaining")
                return False
            else:
                print(f"   ✅ Global cooldown OK: {time_since_last:.1f}s elapsed")

        trigger_type = ctx.trigger_type
        last_type_creation = self.last_creation_by_type.get(trigger_type, 0)
        per_type_cooldown = self.config.neurogenesis.get('per_type_cooldown', 30)
        
        time_since_type = current_time - last_type_creation
        if time_since_type < per_type_cooldown:
            remaining = per_type_cooldown - time_since_type
            #print(f"   ❌ BLOCKED: Per-type cooldown - {remaining:.1f}s remaining")
            return False
        else:
            print(f"   ✅ Per-type cooldown OK: {time_since_type:.1f}s elapsed")
        # ============================================================

        # -------------------------------------------------------------------
        # Pattern recurrence checks (only for non-emergency)
        # -------------------------------------------------------------------
        pattern = ctx.get_pattern_signature()
        self._validate_novelty_counter()
        
        # ===== NEW: CHECK PATTERN SPECIFICITY =====
        # If pattern is too generic (few variables), block creation
        pattern_parts = pattern.split('_')
        if len(pattern_parts) < 6:  # Too few distinguishing features
            print(f"   ❌ BLOCKED: Pattern too generic ({len(pattern_parts)} parts)")
            return False
        # ===========================================

        # Novelty-specific tolerance
        if ctx.trigger_type == 'novelty':
            tolerance_threshold = 3 + self.novelty_neuron_count * 2
            pattern_count = self.experience_buffer.pattern_counts.get(pattern, 0)
            if pattern_count < tolerance_threshold:
                #print(f"   ❌ BLOCKED: Novelty pattern count {pattern_count} < threshold {tolerance_threshold}")
                return False
        else:
            recurrence_satisfied = self.experience_buffer.should_create_specialized_neuron(
                pattern, threshold=3
            )
            if not recurrence_satisfied:
                print(f"   ❌ Pattern recurrence threshold not met")
                return False

        # 2. Avoid duplicates unless the old one is under-performing
        for neuron in self.functional_neurons.values():
            if neuron.creation_context.get_pattern_signature() == pattern:
                if neuron.utility_score > 0.3:
                    print(f"   Duplicate pattern with utility {neuron.utility_score:.2f}")
                    return False

        if ctx.trigger_type == 'novelty':
            max_novelty = self.config.neurogenesis.get('max_novelty_neurons', 5)
            if self.novelty_neuron_count >= max_novelty:
                #print(f"   ❌ BLOCKED: Max novelty neurons ({max_novelty}) reached")
                return False

        print(f"   ✅ ALLOWED: All checks passed for {ctx.trigger_type} neuron")
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
        Now includes per-specialization caps to prevent duplicate functional neurons.
        """
        # Preview specialization before creating
        spec = self._preview_specialization(context)
        base_name = f"{context.trigger_type}_{spec}"
        
        # --- NEW: Check specialization cap ---
        if context.trigger_type in ['reward', 'stress']:
            max_per_spec = self.config.neurogenesis.get('max_per_specialization', 3)
            current_count = sum(1 for name in self.brain_widget.neuron_positions.keys() 
                            if name.startswith(f"{context.trigger_type}_{spec}"))
            
            if current_count >= max_per_spec:
                #print(f"❌ Max {spec} neurons ({max_per_spec}) reached, skipping creation")
                # Instead, strengthen existing neuron
                self._strengthen_existing_neuron(context.trigger_type, spec)
                return None
        # --- END NEW ---
        
        # Rest of method continues as before...
        counter = 0
        neuron_name = base_name
        while neuron_name in self.brain_widget.neuron_positions:
            counter += 1
            neuron_name = f"{base_name}_{counter}"

        # Novelty cap check (existing logic)
        if context.trigger_type == 'novelty':
            max_novelty = self.config.neurogenesis.get('max_novelty_neurons', 5)
            self._validate_novelty_counter()
            if self.novelty_neuron_count >= max_novelty:
                #print(f"❌ Max novelty neurons ({max_novelty}) reached, skipping creation of {neuron_name}")
                return None

        # Create and register the functional neuron
        func_neuron = FunctionalNeuron(neuron_name, context.trigger_type, context)
        self.functional_neurons[neuron_name] = func_neuron

        if context.trigger_type == 'novelty':
            self.novelty_neuron_count += 1

        self.last_creation_by_type[context.trigger_type] = time.time()

        # Position, appearance, connections...
        position = self._calculate_functional_position(func_neuron)
        self.brain_widget.neuron_positions[neuron_name] = position
        self._set_neuron_appearance(neuron_name, func_neuron)

        all_neurons = list(self.brain_widget.neuron_positions.keys())
        connections = func_neuron.get_functional_connections(all_neurons)
        for target, weight in connections.items():
            if target in self.brain_widget.neuron_positions:
                self.brain_widget.weights[(neuron_name, target)] = weight
                self.brain_widget.weights[(target, neuron_name)] = weight * 0.3

        self.brain_widget.state[neuron_name] = 50.0

        # Award points and highlight...
        if neuron_name not in self._awarded_neurons:
            self._awarded_neurons.add(neuron_name)
            if hasattr(self.brain_widget, 'statistics_tab'):
                self.brain_widget.statistics_tab.increment_stat('points', 500)

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
        """
        When cap is reached, strengthen the most useful existing neuron
        instead of creating a duplicate.
        """
        # Find existing neurons of this specialization
        existing = []
        for name, neuron in self.functional_neurons.items():
            if name.startswith(f"{trigger_type}_{specialization}"):
                existing.append((name, neuron))
        
        if not existing:
            return
        
        # Pick the one with highest utility score
        existing.sort(key=lambda x: x[1].utility_score, reverse=True)
        best_name, best_neuron = existing[0]
        
        # Boost its utility score (makes it more likely to survive pruning)
        best_neuron.utility_score += 0.1
        print(f"   💪 Strengthened {specialization} neuron: {best_name} (utility: {best_neuron.utility_score:.2f})")
    
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
        return ExperienceContext(
            trigger_type=trigger_type,
            active_neurons=current_state.copy(),
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