"""
Neurogenesis ver3_unified | 3.0.0

UNIFIED neuron creation system - ALL neurons go through this module.
EnhancedNeurogenesis is the SINGLE AUTHORITY for creating neurons.

Key changes from 2.5.0:
- Single create_neuron() entry point for ALL neuron creation
- All neurons are FunctionalNeurons (even "simple" ones)
- Removed duplicate creation paths
- brain_widget delegates ALL creation here
- BrainWorker results processed through this system
"""

import time
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Any
from PyQt5.QtCore import QTimer


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
        """Generate SIMPLER patterns that are more likely to repeat."""
        motivational_neurons = {
            k: v for k, v in self.active_neurons.items() 
            if k in ['hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity', 'cleanliness', 'sleepiness']
        }
        
        if not motivational_neurons:
            return f"{self.trigger_type}_{self.outcome}"
        
        primary_neuron, primary_value = max(motivational_neurons.items(), key=lambda x: abs(x[1] - 50))
        
        def get_range(value):
            if value < 35: return "low"
            elif value > 65: return "high"
            else: return "mid"
        
        pattern_parts = [
            self.trigger_type,
            self.outcome,
            primary_neuron,
            get_range(primary_value)
        ]
        
        meaningful_actions = [a for a in self.recent_actions[-3:] if a and a != 'none' and a != 'idle']
        if meaningful_actions:
            last_action = meaningful_actions[-1].lower()
            if 'rock' in last_action:
                pattern_parts.append("rock")
            elif 'poop' in last_action:
                pattern_parts.append("poop")
            elif 'food' in last_action or 'eat' in last_action:
                pattern_parts.append("food")
            elif 'sleep' in last_action:
                pattern_parts.append("sleep")
        
        return "_".join(pattern_parts)
    
    def get_core_pattern(self) -> str:
        """Minimal pattern for fuzzy matching."""
        motivational_neurons = {
            k: v for k, v in self.active_neurons.items() 
            if k in ['hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity', 'cleanliness', 'sleepiness']
        }
        
        if not motivational_neurons:
            return f"{self.trigger_type}_{self.outcome}"
        
        primary_neuron, primary_value = max(motivational_neurons.items(), key=lambda x: abs(x[1] - 50))
        intensity = "high" if primary_value > 60 or primary_value < 40 else "mid"
        
        return f"{self.trigger_type}_{self.outcome}_{primary_neuron}_{intensity}"
    
    def get_parent_pattern(self) -> str:
        """Get a broader parent pattern for hierarchical grouping."""
        motivational_neurons = {k: v for k, v in self.active_neurons.items() 
                                if not k.startswith('is_') and k not in [
                                    'position', 'direction', 'status', 'pursuing_food',
                                    'novelty_exposure', 'sustained_stress', 'recent_rewards', 
                                    'personality', 'neurogenesis_active'
                                ]}
        
        top_neurons = sorted(motivational_neurons.items(), 
                            key=lambda x: abs(x[1] - 50), 
                            reverse=True)[:2]
        
        pattern = f"{self.trigger_type}_{self.outcome}"
        for neuron, activation in top_neurons:
            if activation < 40:
                pattern += f"_{neuron}_low"
            elif activation > 60:
                pattern += f"_{neuron}_high"
        
        return pattern


class ExperienceBuffer:
    """Maintains a rolling buffer of recent experiences"""
    
    def __init__(self, max_size=50):
        self.buffer = deque(maxlen=max_size)
        self.pattern_counts = {}
        self.parent_pattern_counts = {}
        self.core_pattern_counts = {}
        self._max_pattern_entries = 500
        
    def add_experience(self, context: ExperienceContext):
        self.buffer.append(context)
        
        pattern = context.get_pattern_signature()
        self.pattern_counts[pattern] = self.pattern_counts.get(pattern, 0) + 1
        
        parent = context.get_parent_pattern()
        self.parent_pattern_counts[parent] = self.parent_pattern_counts.get(parent, 0) + 1
        
        core = context.get_core_pattern()
        self.core_pattern_counts[core] = self.core_pattern_counts.get(core, 0) + 1
        
        self._prune_pattern_counts_if_needed()
        
    def _prune_pattern_counts_if_needed(self):
        if len(self.pattern_counts) > self._max_pattern_entries:
            recent_patterns = {exp.get_pattern_signature() for exp in self.buffer}
            self.pattern_counts = {k: v for k, v in self.pattern_counts.items() 
                                  if k in recent_patterns}
            
        if len(self.parent_pattern_counts) > self._max_pattern_entries // 2:
            recent_parents = {exp.get_parent_pattern() for exp in self.buffer}
            self.parent_pattern_counts = {k: v for k, v in self.parent_pattern_counts.items() 
                                         if k in recent_parents}
            
        if len(self.core_pattern_counts) > self._max_pattern_entries // 4:
            recent_cores = {exp.get_core_pattern() for exp in self.buffer}
            self.core_pattern_counts = {k: v for k, v in self.core_pattern_counts.items() 
                                       if k in recent_cores}
    
    def get_pattern_recurrence(self, context: ExperienceContext) -> Tuple[str, int, str]:
        specific = context.get_pattern_signature()
        parent = context.get_parent_pattern()
        core = context.get_core_pattern()
        
        specific_count = self.pattern_counts.get(specific, 0)
        parent_count = self.parent_pattern_counts.get(parent, 0)
        core_count = self.core_pattern_counts.get(core, 0)
        
        if specific_count >= 2:
            return ('specific', specific_count, specific)
        if parent_count >= 3:
            return ('parent', parent_count, parent)
        if core_count >= 5:
            return ('core', core_count, core)
        
        if specific_count >= parent_count and specific_count >= core_count:
            return ('specific', specific_count, specific)
        elif parent_count >= core_count:
            return ('parent', parent_count, parent)
        else:
            return ('core', core_count, core)
    
    def to_dict(self):
        return {
            'pattern_counts': dict(self.pattern_counts),
            'parent_pattern_counts': dict(self.parent_pattern_counts),
            'core_pattern_counts': dict(self.core_pattern_counts),
            'buffer_size': len(self.buffer),
            'recent_experiences': [
                {
                    'trigger_type': exp.trigger_type,
                    'active_neurons': exp.active_neurons,
                    'recent_actions': exp.recent_actions,
                    'environmental_state': exp.environmental_state,
                    'outcome': exp.outcome,
                    'timestamp': exp.timestamp
                }
                for exp in list(self.buffer)
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ExperienceBuffer':
        buffer = cls()
        buffer.pattern_counts = data.get('pattern_counts', {})
        buffer.parent_pattern_counts = data.get('parent_pattern_counts', {})
        buffer.core_pattern_counts = data.get('core_pattern_counts', {})
        
        for exp_data in data.get('recent_experiences', []):
            ctx = ExperienceContext(
                trigger_type=exp_data['trigger_type'],
                active_neurons=exp_data['active_neurons'],
                recent_actions=exp_data['recent_actions'],
                environmental_state=exp_data['environmental_state'],
                outcome=exp_data['outcome'],
                timestamp=exp_data['timestamp']
            )
            buffer.buffer.append(ctx)
        
        return buffer


class FunctionalNeuron:
    """Represents a neuron with a specific functional role.
    
    ALL neurons in the system are FunctionalNeurons - this is the unified type.
    """
    
    def __init__(self, name: str, neuron_type: str, creation_context: ExperienceContext):
        self.name = name
        self.neuron_type = neuron_type
        self.creation_context = creation_context
        self.specialization = self._determine_specialization()
        self.activation_count = 0
        self.last_activated = 0
        self.utility_score = 0.0
        self.strength_multiplier = 1.0

    
    @classmethod
    def from_dict(cls, data):
        # Support both 'active_neurons' (correct) and 'brain_state' (legacy) keys
        creation_ctx = data['creation_context']
        active_neurons_data = creation_ctx.get('active_neurons') or creation_ctx.get('brain_state', {})
        
        ctx = ExperienceContext(
            trigger_type=creation_ctx['trigger_type'],
            active_neurons=active_neurons_data,
            recent_actions=creation_ctx['recent_actions'],
            environmental_state=creation_ctx['environmental_state'],
            outcome=creation_ctx['outcome'],
            timestamp=creation_ctx['timestamp'],
        )

        neuron = cls.__new__(cls)
        neuron.name = data['name']
        neuron.neuron_type = data['neuron_type']
        neuron.creation_context = ctx
        neuron.specialization = data['specialization']
        neuron.activation_count = data['activation_count']
        neuron.last_activated = data['last_activated']
        neuron.utility_score = data['utility_score']
        neuron.strength_multiplier = data['strength_multiplier']
        return neuron

    def to_dict(self):
        return {
            'name': self.name,
            'neuron_type': self.neuron_type,
            'specialization': self.specialization,
            'activation_count': self.activation_count,
            'last_activated': self.last_activated,
            'utility_score': self.utility_score,
            'strength_multiplier': self.strength_multiplier,
            'creation_context': {
                'trigger_type': self.creation_context.trigger_type,
                'timestamp': self.creation_context.timestamp,
                'active_neurons': self.creation_context.active_neurons,
                'recent_actions': self.creation_context.recent_actions,
                'environmental_state': self.creation_context.environmental_state,
                'outcome': self.creation_context.outcome,
            }
        }

    def _determine_specialization(self):
        ctx = self.creation_context
        
        if ctx.trigger_type == 'reward':
            if ctx.environmental_state.get('is_eating', False):
                return 'feeding_satisfaction'
            elif ctx.active_neurons.get('cleanliness', 50) > 70 and ctx.outcome == 'positive':
                return 'cleanliness_reward'
            elif ctx.active_neurons.get('sleepiness', 50) < 30 and ctx.outcome == 'positive':
                return 'rest_reward'
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
            if ctx.environmental_state.get('has_rock', False) or 'rock' in str(ctx.environmental_state):
                return 'object_investigation'
            elif 'new_location' in ctx.recent_actions:
                return 'exploration_memory'
            else:
                return 'general_novelty_processing'
                
        return 'undefined'
    
    def get_functional_connections(self, all_neurons: List[str]) -> Dict[str, float]:
        """Determine which neurons this should connect to based on its function."""
        connections = {}
        ctx = self.creation_context
        
        # Connect strongly to neurons that were highly active during creation
        for neuron, activation in ctx.active_neurons.items():
            if neuron in all_neurons:
                deviation = abs(activation - 50)
                if deviation > 20:
                    weight = (deviation / 50) * 0.8
                    if activation < 50:
                        weight = -weight
                    connections[neuron] = weight
        
        spec_connections = self._get_specialization_connections(all_neurons)
        connections.update(spec_connections)
        
        return connections
    
    def _get_specialization_connections(self, all_neurons: List[str]) -> Dict[str, float]:
        connections = {}
        
        if self.specialization == 'feeding_satisfaction':
            if 'hunger' in all_neurons:
                connections['hunger'] = -0.7
            if 'happiness' in all_neurons:
                connections['happiness'] = 0.6
            if 'satisfaction' in all_neurons:
                connections['satisfaction'] = 0.8
                
        elif self.specialization == 'hunger_stress_response':
            if 'hunger' in all_neurons:
                connections['hunger'] = 0.7
            if 'anxiety' in all_neurons:
                connections['anxiety'] = 0.5
            if 'curiosity' in all_neurons:
                connections['curiosity'] = 0.4
                
        elif self.specialization == 'filth_avoidance':
            if 'cleanliness' in all_neurons:
                connections['cleanliness'] = -0.8
            if 'anxiety' in all_neurons:
                connections['anxiety'] = 0.6
        
        elif self.specialization == 'anxiety_regulation':
            if 'anxiety' in all_neurons:
                connections['anxiety'] = -0.8
            if 'happiness' in all_neurons:
                connections['happiness'] = 0.4
            if 'satisfaction' in all_neurons:
                connections['satisfaction'] = 0.3
                
        elif self.specialization == 'object_investigation':
            if 'curiosity' in all_neurons:
                connections['curiosity'] = 0.7
            if 'anxiety' in all_neurons:
                connections['anxiety'] = -0.4
                
        elif self.specialization == 'rest_reward':
            if 'sleepiness' in all_neurons:
                connections['sleepiness'] = -0.6
            if 'satisfaction' in all_neurons:
                connections['satisfaction'] = 0.5
            if 'happiness' in all_neurons:
                connections['happiness'] = 0.4
                
        elif self.specialization == 'cleanliness_reward':
            if 'cleanliness' in all_neurons:
                connections['cleanliness'] = 0.6
            if 'satisfaction' in all_neurons:
                connections['satisfaction'] = 0.5
            if 'anxiety' in all_neurons:
                connections['anxiety'] = -0.3
        
        return connections
    
    def calculate_activation(self, brain_state: Dict[str, float], 
                       weights: Dict[Tuple[str, str], float]) -> float:
        activation = 50.0
        
        for (source, target), weight in weights.items():
            if target == self.name and source in brain_state:
                # Safety: force float even if something weird slipped in (legacy saves, etc.)
                source_activation = float(brain_state[source])
                influence = (source_activation - 50.0) * weight
                activation += influence
        
        # Apply strength multiplier
        activation = 50.0 + (activation - 50.0) * self.strength_multiplier
        activation = max(0.0, min(100.0, activation))
        
        if abs(activation - 50.0) > 15.0:
            self.activation_count += 1
            self.last_activated = time.time()
            
        return activation
    
    def update_utility_score(self, outcome_value: float):
        alpha = 0.3
        self.utility_score = alpha * outcome_value + (1 - alpha) * self.utility_score
    
    def to_dict(self):
        return {
            'name': self.name,
            'neuron_type': self.neuron_type,
            'specialization': self.specialization,
            'activation_count': self.activation_count,
            'last_activated': self.last_activated,
            'utility_score': self.utility_score,
            'strength_multiplier': self.strength_multiplier,
            'creation_context': {
                'trigger_type': self.creation_context.trigger_type,
                'timestamp': self.creation_context.timestamp,
                'active_neurons': self.creation_context.active_neurons,
                'recent_actions': self.creation_context.recent_actions,
                'environmental_state': self.creation_context.environmental_state,
                'outcome': self.creation_context.outcome,
            }
        }
    
    @classmethod
    def from_dict(cls, data):
        # Support both 'active_neurons' (correct) and 'brain_state' (legacy) keys
        creation_ctx = data['creation_context']
        active_neurons_data = creation_ctx.get('active_neurons') or creation_ctx.get('brain_state', {})
        
        context = ExperienceContext(
            trigger_type=creation_ctx['trigger_type'],
            active_neurons=active_neurons_data,
            recent_actions=creation_ctx['recent_actions'],
            environmental_state=creation_ctx['environmental_state'],
            outcome=creation_ctx['outcome'],
            timestamp=creation_ctx['timestamp']
        )
        
        neuron = cls(
            name=data['name'],
            neuron_type=data['neuron_type'],
            creation_context=context
        )
        
        neuron.specialization = data.get('specialization', neuron.specialization)
        neuron.activation_count = data.get('activation_count', 0)
        neuron.last_activated = data.get('last_activated', 0)
        neuron.utility_score = data.get('utility_score', 0.0)
        neuron.strength_multiplier = data.get('strength_multiplier', 1.0)
        
        return neuron


class EnhancedNeurogenesis:
    """
    UNIFIED neuron creation system.
    
    This is the SINGLE AUTHORITY for creating ALL neurons in the brain.
    All creation requests must go through create_neuron() or create_functional_neuron().
    """
    
    def __init__(self, brain_widget, config):
        self.brain_widget = brain_widget
        self.config = config
        self.experience_buffer = ExperienceBuffer()
        self.functional_neurons: Dict[str, FunctionalNeuron] = {}
        self.novelty_neuron_count = 0
        self._awarded_neurons = set()
        self.last_neurogenesis_time = 0
        self.neurons_created_this_session = 0
        self.last_creation_by_type = {'novelty': 0, 'stress': 0, 'reward': 0}
        self._first_real_tick = None
        
        self.recent_actions = deque(maxlen=10)
        self.last_states = deque(maxlen=5)
        
        self._on_neuron_created_callback = None
        self._on_neuron_leveled_callback = None

    # =========================================================================
    # UNIFIED CREATION API - All neurons go through here
    # =========================================================================
    
    def create_neuron(self, 
                      neuron_type: str,
                      context: Optional[ExperienceContext] = None,
                      brain_state: Optional[Dict[str, float]] = None,
                      environment: Optional[Dict[str, Any]] = None,
                      trigger_value: Optional[float] = None) -> Optional[str]:
        """
        UNIFIED neuron creation entry point.
        
        This is the ONLY method that should be called to create neurons.
        All other creation methods are internal helpers.
        
        Args:
            neuron_type: 'novelty', 'stress', or 'reward'
            context: Optional pre-built ExperienceContext
            brain_state: Current brain state (used if no context provided)
            environment: Environmental data (used if no context provided)
            trigger_value: Optional value for logging
            
        Returns:
            Name of created neuron, or None if creation was blocked
        """
        # Build context if not provided
        if context is None:
            if brain_state is None:
                brain_state = dict(self.brain_widget.state)
            if environment is None:
                environment = {}
            
            context = self._build_context(neuron_type, brain_state, environment)
        
        # Delegate to internal creation
        return self._create_neuron_internal(context, trigger_value)
    
    def _make_reciprocal_connections(self, new_neuron: str):
        """
        Ensure every outgoing connection ≥ 0.2 abs gets a matching
        incoming connection so the new neuron can *activate* as well as
        *be activated*.  Runs once immediately after the neuron is created.
        """
        bw = self.brain_widget
        created = []                       # just for console log
        MIN_RECIPROCAL = 0.2               # tunable

        # 1.  collect outgoing weights we care about
        outgoing = [(tgt, w) for (src, tgt), w in bw.weights.items()
                    if src == new_neuron and abs(w) >= MIN_RECIPROCAL]

        # 2.  add the reverse link (same magnitude, same sign)
        for target, w in outgoing:
            if (target, new_neuron) in bw.weights:        # already exists → skip
                continue
            bw.weights[(target, new_neuron)] = w
            created.append(f"{target}→{new_neuron}:{w:+.2f}")

        if created:
            print(f"   🔗 Reciprocal links added: {', '.join(created)}")
    
    def create_functional_neuron(self, ctx: ExperienceContext, is_emergency: bool = False) -> Optional[str]:
        """
        Create a functional neuron from an experience context.
        This is the standard entry point used by the neurogenesis system.
        """
        return self._create_neuron_internal(ctx, is_emergency=is_emergency)
    
    def _build_context(self, trigger_type: str, brain_state: Dict[str, float], 
                       environment: Dict[str, Any]) -> ExperienceContext:
        """Build an ExperienceContext from raw data."""
        # Clean neurons - remove binary flags and system values
        clean_neurons = {
            k: float(v) if isinstance(v, (int, float)) else 50.0
            for k, v in brain_state.items()
            if not k.startswith('is_') and k not in [
                'novelty_exposure', 'sustained_stress', 'recent_rewards',
                'neurogenesis_active', 'personality', 'pursuing_food',
                'position', 'direction', 'status'
            ]
        }
        
        # Determine outcome from state
        happiness = brain_state.get('happiness', 50)
        anxiety = brain_state.get('anxiety', 50)
        if happiness > 60:
            outcome = 'positive'
        elif anxiety > 70:
            outcome = 'negative'
        else:
            outcome = 'neutral'
        
        return ExperienceContext(
            trigger_type=trigger_type,
            active_neurons=clean_neurons,
            recent_actions=list(self.recent_actions)[-5:],
            environmental_state=environment,
            outcome=outcome,
            timestamp=time.time()
        )
    
    def _create_neuron_internal(self, ctx: ExperienceContext,
                            trigger_value_for_log: Optional[float] = None,
                            is_emergency: bool = False) -> Optional[str]:
        """
        Internal unified neuron creation.

        Caps enforced:
        - max_per_type (hard limit per neuron_type, survives renaming)
        - max_per_specialization (soft limit per spec, name-based)
        - max_neurons (global network size)
        Emergency mode only skips cooldown / pattern requirements.
        """
        trigger_type = ctx.trigger_type

        # 1. HARD TYPE CAP  (authoritative, survives showman renames)
        max_per_type = self.config.neurogenesis.get('max_per_type', {
            'stress': 5,
            'novelty': 6,
            'reward': 6
        })
        max_for_this_type = max_per_type.get(trigger_type, 5)
        current_type_count = len([
            name for name, fn in self.functional_neurons.items()
            if fn.neuron_type == trigger_type
        ])
        if current_type_count >= max_for_this_type:
            print(f"   Type cap reached for {trigger_type} "
                f"({current_type_count}/{max_for_this_type}), strengthening existing")
            self._strengthen_existing_neuron(trigger_type, self._preview_specialization(ctx))
            return None

        # 2. SPECIALIZATION CAP  (name-based, optional extra guard)
        spec = self._preview_specialization(ctx)
        base_name = f"{trigger_type}_{spec}"
        max_per_spec = self.config.neurogenesis.get('max_per_specialization', 5)
        current_spec_count = len([
            name for name in self.brain_widget.neuron_positions.keys()
            if name.startswith(base_name)
        ])
        if current_spec_count >= max_per_spec:
            print(f"   Specialization cap reached for {base_name}, strengthening existing")
            self._strengthen_existing_neuron(trigger_type, spec)
            return None

        # 3. GLOBAL NEURON LIMIT
        current_total = len(self.brain_widget.neuron_positions) - len(self.brain_widget.excluded_neurons)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_total >= max_neurons:
            print(f"   Max neurons reached ({current_total}/{max_neurons})")
            return None

        # ---------- creation proceeds ----------
        neuron_name = self._get_unique_neuron_name(base_name)
        func_neuron = FunctionalNeuron(neuron_name, trigger_type, ctx)
        self.functional_neurons[neuron_name] = func_neuron

        # counters
        if trigger_type == 'novelty':
            self.novelty_neuron_count += 1
        self.last_creation_by_type[trigger_type] = time.time()
        self.neurons_created_this_session += 1

        # ----- inject into brain_widget -----
        position = self._calculate_functional_position(func_neuron)
        self.brain_widget.neuron_positions[neuron_name] = position
        self._set_neuron_appearance(neuron_name, func_neuron)
        self.brain_widget.state[neuron_name] = 50.0

        # functional connections
        all_neurons = list(self.brain_widget.neuron_positions.keys())
        connections = func_neuron.get_functional_connections(all_neurons)
        for target, weight in connections.items():
            self.brain_widget.weights[(neuron_name, target)] = weight

        # bidirectional anxiety ↔ stress link
        if func_neuron.neuron_type == 'stress' and 'anxiety' in all_neurons:
            self.brain_widget.weights[(neuron_name, 'anxiety')] = -0.8
            self.brain_widget.weights[('anxiety', neuron_name)] = 0.9
            print(f"   📎 Added bidirectional link: anxiety ↔ {neuron_name}")

        # weak exploratory web
        for target in all_neurons:
            if target == neuron_name or target in self.brain_widget.excluded_neurons:
                continue
            if (neuron_name, target) in self.brain_widget.weights:
                continue
            seed = random.uniform(-0.08, 0.08)
            self.brain_widget.weights[(neuron_name, target)] = seed
            self.brain_widget.weights[(target, neuron_name)] = seed * 0.5

        # ===== NEW: make them reciprocal =====
        self._make_reciprocal_connections(neuron_name)

        # visuals & bookkeeping
        if hasattr(self.brain_widget, 'visible_neurons'):
            self.brain_widget.visible_neurons.add(neuron_name)
        self.brain_widget.communication_events[neuron_name] = time.time()
        self.brain_widget.neurogenesis_highlight = {
            'neuron': neuron_name,
            'start_time': time.time(),
            'duration': 5.0,
            'pulse_phase': 0
        }

        # logging
        self._log_neuron_creation(neuron_name, trigger_type, spec, trigger_value_for_log)
        details = self.brain_widget.neurogenesis_data.setdefault('new_neurons_details', {})
        details[neuron_name] = {
            'created_at': ctx.timestamp,
            'trigger_type': trigger_type,
            'trigger_value_at_creation': trigger_value_for_log or 0,
            'specialisation': spec
        }

        if self._on_neuron_created_callback:
            try:
                self._on_neuron_created_callback(neuron_name, trigger_type)
            except Exception as e:
                print(f"Neuron creation callback error: {e}")

        print(f"✨ Created neuron: {neuron_name} (spec: {spec})")
        return neuron_name
    
    def _on_neuron_created(self, neuron_name: str, neuron_type: str):
        """Called when a new neuron is created"""        
        # Trigger link toggle effect for visual feedback
        self._trigger_link_toggle_effect()
    
    def _get_unique_neuron_name(self, base_name: str) -> str:
        """Generate unique name, checking both functional_neurons AND brain_widget."""
        if base_name not in self.brain_widget.neuron_positions:
            return base_name
        
        counter = 2
        while True:
            candidate = f"{base_name}_{counter}"
            if candidate not in self.brain_widget.neuron_positions:
                return candidate
            counter += 1

    def _rebuild_new_neurons_details(self):
        """Make sure every functional neuron is listed in
        neurogenesis_data['new_neurons_details'] so the Laboratory
        ‘newest neurogenesis neurons’ card can see it."""
        core = {'hunger', 'happiness', 'cleanliness', 'sleepiness',
                'satisfaction', 'anxiety', 'curiosity'}
        details = self.brain_widget.neurogenesis_data.setdefault('new_neurons_details', {})

        for name, fn in self.functional_neurons.items():
            if name in core or name in self.brain_widget.excluded_neurons:
                continue
            if name not in details:          # missing ➜ add it
                details[name] = {
                    'created_at': fn.creation_context.timestamp,
                    'trigger_type': fn.neuron_type,
                    'trigger_value_at_creation': 0,   # we don’t have the original value
                    'specialisation': fn.specialization
                }

    def _rebuild_new_neurons_details_for_lab(self):
        """Back-fill missing entries so the Laboratory 'newest' card works."""
        core = {'hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity'}
        details = self.brain_widget.neurogenesis_data.setdefault('new_neurons_details', {})
        
        for name, fn in self.functional_neurons.items():
            if name in core or name in getattr(self.brain_widget, 'excluded_neurons', []):
                continue
            # Only add if missing
            if name not in details:
                details[name] = {
                    'created_at': fn.creation_context.timestamp,
                    'trigger_type': fn.neuron_type,
                    'specialisation': fn.specialization
                }
    
    def _preview_specialization(self, ctx: ExperienceContext) -> str:
        """Preview what specialization a neuron would get without creating it."""
        if ctx.trigger_type == 'reward':
            if ctx.environmental_state.get('is_eating', False):
                return 'feeding_satisfaction'
            if ctx.active_neurons.get('cleanliness', 50) > 70 and ctx.outcome == 'positive':
                return 'cleanliness_reward'
            if ctx.active_neurons.get('sleepiness', 50) < 30 and ctx.outcome == 'positive':
                return 'rest_reward'
            return 'general_reward'

        if ctx.trigger_type == 'stress':
            if ctx.active_neurons.get('hunger', 50) > 70:
                return 'hunger_stress_response'
            if ctx.active_neurons.get('cleanliness', 50) < 30:
                return 'filth_avoidance'
            if ctx.active_neurons.get('anxiety', 50) > 70:
                return 'anxiety_regulation'
            return 'general_stress_coping'

        if ctx.trigger_type == 'novelty':
            if ctx.environmental_state.get('has_rock', False) or 'rock' in str(ctx.environmental_state):
                return 'object_investigation'
            if 'new_location' in ctx.recent_actions:
                return 'exploration_memory'
            return 'general_novelty_processing'

        return 'undefined'
    
    def _calculate_functional_position(self, func_neuron: FunctionalNeuron) -> Tuple[float, float]:
        """Position neuron based on its functional relationships."""
        all_neurons = list(self.brain_widget.neuron_positions.keys())
        connections = func_neuron.get_functional_connections(all_neurons)
        
        if not connections:
            return (random.randint(100, 900), random.randint(100, 600))
        
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
            
            offset_x = random.randint(-80, 80)
            offset_y = random.randint(-80, 80)
            
            x = max(50, min(974, center_x + offset_x))
            y = max(50, min(668, center_y + offset_y))
            
            return (x, y)
        
        return (random.randint(100, 900), random.randint(100, 600))
    
    def _set_neuron_appearance(self, name: str, func_neuron: FunctionalNeuron):
        """Set visual appearance based on function."""
        spec = func_neuron.specialization
        neuron_type = func_neuron.neuron_type
        
        # Shape based on type
        shape_map = {
            'novelty': 'diamond',
            'stress': 'square',
            'reward': 'triangle'
        }
        self.brain_widget.neuron_shapes[name] = shape_map.get(neuron_type, 'circle')
        
        # Color based on type and specialization
        if 'stress' in spec or 'anxiety' in spec:
            self.brain_widget.state_colors[name] = (255, 150, 150)
        elif 'reward' in spec or 'satisfaction' in spec:
            self.brain_widget.state_colors[name] = (150, 255, 150)
        elif 'investigation' in spec or 'exploration' in spec:
            self.brain_widget.state_colors[name] = (255, 215, 0)
        else:
            color_map = {
                'novelty': (255, 255, 150),
                'stress': (255, 0, 0),
                'reward': (173, 216, 230)
            }
            self.brain_widget.state_colors[name] = color_map.get(neuron_type, (200, 200, 255))
    
    def _log_neuron_creation(self, name: str, trigger_type: str, spec: str, trigger_value: Optional[float]):
        """Log neuron creation event."""
        self.brain_widget.log_neurogenesis_event(
            name, "created",
            details={
                'trigger_type': trigger_type,
                'trigger_value': trigger_value or 0,
                'specialization': spec
            }
        )
    
    def _strengthen_existing_neuron(self, trigger_type: str, specialization: str):
        """Strengthen existing neuron instead of creating duplicate."""
        prefix = f"{trigger_type}_{specialization}"
        
        existing = [(name, neuron) for name, neuron in self.functional_neurons.items()
                    if name.startswith(prefix)]
        
        if not existing:
            # Check if brain widget has neurons we need to convert
            brain_neurons = [name for name in self.brain_widget.neuron_positions.keys()
                            if name.startswith(prefix)]
            if brain_neurons:
                # Convert first one to functional
                self._ensure_functional_neuron(brain_neurons[0], trigger_type, specialization)
                if brain_neurons[0] in self.functional_neurons:
                    existing = [(brain_neurons[0], self.functional_neurons[brain_neurons[0]])]
        
        if not existing:
            return
        
        # Strengthen the one with highest utility
        existing.sort(key=lambda x: x[1].utility_score, reverse=True)
        best_name, best_neuron = existing[0]
        
        best_neuron.strength_multiplier += 0.5
        best_neuron.utility_score += 0.1
        
        self.brain_widget.communication_events[best_name] = time.time()
        
        # Force immediate visual update
        self.brain_widget.update()
        
        print(f"   💪 Strengthened: {best_name} (multiplier: {best_neuron.strength_multiplier:.1f}x)")
        
        if self._on_neuron_leveled_callback:
            try:
                self._on_neuron_leveled_callback(best_name, best_neuron.strength_multiplier)
            except Exception as e:
                print(f"Level callback error: {e}")
        
        self.brain_widget.update()
    
    # =========================================================================
    # Neuron Conversion - Ensure all neurons are FunctionalNeurons
    # =========================================================================
    
    def _ensure_functional_neuron(self, name: str, neuron_type: str = None, 
                                   specialization: str = None) -> Optional[FunctionalNeuron]:
        """
        Ensure a neuron exists as a FunctionalNeuron.
        Converts existing brain widget neurons if needed.
        """
        if name in self.functional_neurons:
            return self.functional_neurons[name]
        
        if name not in self.brain_widget.neuron_positions:
            return None
        
        # Infer type from name if not provided
        if neuron_type is None:
            if name.startswith('novelty'):
                neuron_type = 'novelty'
            elif name.startswith('stress'):
                neuron_type = 'stress'
            elif name.startswith('reward'):
                neuron_type = 'reward'
            else:
                neuron_type = 'novelty'  # Default
        
        # Build minimal context
        ctx = ExperienceContext(
            trigger_type=neuron_type,
            active_neurons=dict(self.brain_widget.state),
            recent_actions=[],
            environmental_state={},
            outcome='neutral',
            timestamp=time.time()
        )
        
        # Create functional neuron
        func_neuron = FunctionalNeuron(name, neuron_type, ctx)
        if specialization:
            func_neuron.specialization = specialization
        
        self.functional_neurons[name] = func_neuron
        print(f"   Converted {name} to FunctionalNeuron")
        
        return func_neuron
    
    def ensure_all_neurons_functional(self, force_sync=False):
        """
        Synchronize functional_neurons with brain_widget after loading a save.
        
        This method does two things:
        1. Ensures neurons in brain_widget.neuron_positions have functional_neuron entries
        2. Ensures neurons in functional_neurons are present in brain_widget structures
        
        Call this after loading a save or when synchronizing state.
        
        Args:
            force_sync: If True, always update appearance even if neuron already exists
        """
        core_neurons = ['hunger', 'happiness', 'cleanliness', 'sleepiness',
                        'satisfaction', 'anxiety', 'curiosity']
        excluded = getattr(self.brain_widget, 'excluded_neurons', [])

        # 1. Ensure neurons in neuron_positions have functional_neuron entries
        for name in list(self.brain_widget.neuron_positions.keys()):
            if name in core_neurons or name in excluded:
                continue
            if name not in self.functional_neurons:
                self._ensure_functional_neuron(name)

        # 2. CRITICAL: Ensure functional_neurons are restored to brain_widget structures
        restored_positions = 0
        restored_states = 0
        restored_visible = 0
        
        for name, fn in self.functional_neurons.items():
            if name in core_neurons or name in excluded:
                continue
            
            # Add to neuron_positions if missing
            if name not in self.brain_widget.neuron_positions:
                position = self._calculate_functional_position(fn)
                self.brain_widget.neuron_positions[name] = position
                restored_positions += 1
                print(f"   ↪ Restored position for {name}: {position}")
            
            # Add to state if missing
            if name not in self.brain_widget.state:
                self.brain_widget.state[name] = 50.0
                restored_states += 1
                print(f"   ↪ Restored state for {name}")
            
            # ALWAYS add to visible_neurons (this is idempotent for sets)
            if hasattr(self.brain_widget, 'visible_neurons'):
                if name not in self.brain_widget.visible_neurons:
                    restored_visible += 1
                self.brain_widget.visible_neurons.add(name)
            
            # ALWAYS set appearance (color/shape) - ensures correct rendering after load
            self._set_neuron_appearance(name, fn)
            
            # Restore connections if missing
            all_neurons = list(self.brain_widget.neuron_positions.keys())
            connections = fn.get_functional_connections(all_neurons)
            for target, weight in connections.items():
                if (name, target) not in self.brain_widget.weights:
                    self.brain_widget.weights[(name, target)] = weight

        # 3. Back-fill missing origin stories in neurogenesis_data
        details = self.brain_widget.neurogenesis_data.setdefault('new_neurons_details', {})
        for name, fn in self.functional_neurons.items():
            if name in core_neurons or name in excluded:
                continue
            if name not in details:
                details[name] = {
                    'created_at': fn.creation_context.timestamp,
                    'trigger_type': fn.neuron_type,
                    'trigger_value_at_creation': 0,   # unknown for legacy neurons
                    'specialisation': fn.specialization
                }
        
        # 4. CRITICAL: Rebuild new_neurons list from functional_neurons
        # This list is used for drawing connections and identifying neurogenesis neurons
        new_neurons_list = self.brain_widget.neurogenesis_data.setdefault('new_neurons', [])
        restored_to_list = 0
        for name, fn in self.functional_neurons.items():
            if name in core_neurons or name in excluded:
                continue
            if name not in new_neurons_list:
                new_neurons_list.append(name)
                restored_to_list += 1
        if restored_to_list > 0:
            print(f"   ↪ Restored {restored_to_list} neurons to new_neurons list")
        
        restored_count = len([n for n in self.functional_neurons if n not in core_neurons and n not in excluded])
        if restored_count > 0:
            print(f"✅ Neurogenesis sync complete: {restored_count} functional neurons")
            if restored_positions > 0 or restored_states > 0 or restored_visible > 0:
                print(f"   Restored: {restored_positions} positions, {restored_states} states, {restored_visible} visibility flags")
    
    def set_achievement_callbacks(self, on_created=None, on_leveled=None):
        self._on_neuron_created_callback = on_created
        self._on_neuron_leveled_callback = on_leveled

    def get_global_cooldown_remaining(self) -> float:
        if not self.functional_neurons:
            return 0.0
        
        current_time = time.time()
        last_creation = max(n.creation_context.timestamp for n in self.functional_neurons.values())
        global_cooldown = self.config.neurogenesis.get('cooldown', 60)
        time_since_last = current_time - last_creation
        remaining = global_cooldown - time_since_last
        return max(0.0, remaining)

    def track_action(self, action: str):
        self.recent_actions.append(action)

    def track_state_change(self, state: dict):
        self.last_states.append(state.copy())

    def check_and_capture_experience(self, brain_state: dict, environment: dict):
        """
        Convenience method for automatic experience detection and capturing.
        Analyzes brain state and environment to determine trigger types and capture experiences.
        """
        # Detect trigger type based on state changes and environment
        trigger_type = self._detect_trigger_type(brain_state, environment)
        
        if trigger_type:
            # Capture the experience with the detected trigger
            self.capture_experience_context(
                trigger_type=trigger_type,
                brain_state=brain_state,
                recent_actions=list(self.recent_actions),
                environment=environment
            )
    
    def _detect_trigger_type(self, brain_state: dict, environment: dict) -> Optional[str]:
        """
        Analyze brain state and environment to detect what kind of experience trigger this is.
        Returns: 'novelty', 'stress', 'reward', or None
        """
        # Get key values
        anxiety = brain_state.get('anxiety', 50)
        satisfaction = brain_state.get('satisfaction', 50)
        curiosity = brain_state.get('curiosity', 50)
        happiness = brain_state.get('happiness', 50)
        
        # Check for stress trigger (high anxiety)
        if anxiety > 75:
            return 'stress'
        
        # Check for novelty trigger (high curiosity, new objects)
        if environment.get('new_object_encountered', False) or curiosity > 70:
            return 'novelty'
        
        # Check for reward trigger (positive outcomes, satisfaction, happiness)
        if environment.get('recent_positive_outcome', False) or satisfaction > 70 or happiness > 70:
            return 'reward'
        
        # Check for stress relief (anxiety dropped significantly)
        if len(self.last_states) > 0:
            prev_anxiety = self.last_states[-1].get('anxiety', 50)
            if prev_anxiety > 60 and anxiety < 40:
                return 'stress'  # Stress relief is still a stress-related trigger
        
        # No clear trigger detected
        return None

    def capture_experience_context(self, trigger_type: str, brain_state: dict,
                               recent_actions: list, environment: dict) -> ExperienceContext:
        if self._first_real_tick is None:
            self._first_real_tick = time.time()
        
        # FIX: Ensure recent_actions is a list to prevent TypeError
        if not isinstance(recent_actions, list):
            print(f"⚠️ Warning: recent_actions was {type(recent_actions)}, expected list. Using empty list.")
            recent_actions = []
        
        ctx = self._build_context(trigger_type, brain_state, environment)
        ctx.recent_actions = recent_actions[-5:] if recent_actions else []
        
        # Grace period
        elapsed = time.time() - self._first_real_tick
        if elapsed < 1.5:
            return ctx
        
        # Don't buffer peaceful sleep
        is_sleeping = brain_state.get('is_sleeping', False)
        anxiety = brain_state.get('anxiety', 50)
        satisfaction = brain_state.get('satisfaction', 50)
        if is_sleeping and anxiety < 15 and satisfaction > 85:
            return ctx
        
        self.experience_buffer.add_experience(ctx)
        return ctx
    
    def should_create_neuron(self, ctx: ExperienceContext) -> bool:
        """Check if conditions allow neuron creation."""
        current_time = time.time()
        
        # Emergency bypass
        if ctx.trigger_type == 'stress' and ctx.active_neurons.get('anxiety', 50) >= 95:
            print("🚨 EMERGENCY: Critical anxiety - forcing stress neuron!")
            return True
        
        # Grace period
        if self._first_real_tick is None:
            return False
        elapsed = current_time - self._first_real_tick
        if elapsed < 5.0:
            return False
        
        # Pattern specificity
        pattern = ctx.get_pattern_signature()
        if len(pattern.split('_')) < 4:
            return False
        
        # Over-clustering
        if self.experience_buffer.pattern_counts.get(pattern, 0) > 20:
            return False
        
        # Max neurons
        current_count = len(self.brain_widget.neuron_positions)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_count >= max_neurons:
            return False
        
        # Global cooldown
        global_cooldown = self.config.neurogenesis.get('cooldown', 60)
        default_time = self._first_real_tick or time.time()
        last_creation = max(
            (n.creation_context.timestamp for n in self.functional_neurons.values()),
            default=default_time
        )
        if current_time - last_creation < global_cooldown:
            return False
        
        # Pattern recurrence
        pattern_level, count, _ = self.experience_buffer.get_pattern_recurrence(ctx)
        thresholds = {'specific': 2, 'parent': 3, 'core': 5}
        if count < thresholds.get(pattern_level, 2):
            return False
        
        return True
    
    def update_neuron_activations(self, brain_state: Dict[str, float]) -> None:
        """
        Update functional-neuron values + emit **very slow, very subtle** one-way pulses.
        """

        # ---------- 1.  sanitise ----------
        for key in list(brain_state.keys()):
            if not isinstance(brain_state[key], (int, float)):
                try:
                    brain_state[key] = float(brain_state[key])
                except (ValueError, TypeError):
                    brain_state[key] = 50.0

        # ---------- 2.  forward activation ----------
        for name, func_neuron in self.functional_neurons.items():
            if name in self.brain_widget.state:
                activation = func_neuron.calculate_activation(brain_state,
                                                            self.brain_widget.weights)
                self.brain_widget.state[name] = activation

        # ---------- 3.  stress-neuron anxiety suppression ----------
        if 'anxiety' in brain_state:
            current_anxiety = brain_state['anxiety']
            total_reduction   = 0.0
            total_stress_power = 0.0

            for name, fn in self.functional_neurons.items():
                if getattr(fn, 'neuron_type', '') == 'stress':
                    multiplier = getattr(fn, 'strength_multiplier', 1.0)
                    total_stress_power += multiplier

                    driven = 50.0 + (current_anxiety - 50.0) * 0.8
                    driven = max(50.0, min(100.0, driven))
                    current_val = self.brain_widget.state.get(name, 50.0)
                    self.brain_widget.state[name] = max(current_val, driven)

                    act = self.brain_widget.state[name]
                    infl = max(0.0, (act - 50.0) / 50.0)
                    total_reduction += (12.0 * multiplier) * (1.0 + infl)

            if total_stress_power:
                ceiling = max(25.0, 100.0 - total_stress_power * 12.0)
                if current_anxiety > ceiling:
                    total_reduction += (current_anxiety - ceiling) * 0.8
                brain_state['anxiety'] = max(0.0, current_anxiety - total_reduction)

        # ---------- 4.  SUBTLE SLOW PULSES  (animations may be disabled) ----------
        if not getattr(self.brain_widget, 'animations_enabled', True):
            return
        if not hasattr(self.brain_widget, 'trigger_activation_pulse'):
            return

        now = time.time()
        for (src, dst), weight in self.brain_widget.weights.items():
            if abs(weight) < 0.15:
                continue

            # ---- per-link personality ----
            seed   = hash((src, dst)) % 1_000_000 / 1_000_000.0
            excite = seed * 0.85 + 0.15
            if excite < 0.22:                      # ~22 % completely mute
                continue
            skip   = int(3 + seed * 9)             # 3-12 frame skip  →  slower cadence
            if int(now * 60) % skip != 0:
                continue

            src_act   = brain_state.get(src, 50.0)
            influence = (src_act - 50.0) * weight
            if abs(influence) < 6.0:               # only clear signals
                continue

            # ---- desaturated, darker palette ----
            if influence > 0:                       # excitatory (olive → moss)
                base_hue = 65 + seed * 25
                sat = 70 + seed * 40                # 70-110  (soft)
                val = 120 + seed * 30               # 120-150 (dim)
            else:                                   # inhibitory (rust → wine)
                base_hue = 5 + seed * 20
                sat = 75 + seed * 35
                val = 115 + seed * 30

            rgb   = self._hsv_to_rgb(base_hue, sat, val)
            alpha = 80 + int(seed * 60)             # 80-140  (very translucent)
            colour = (*rgb, alpha)

            # ---- slow motion ----
            duration = 1.5 + seed * 1.5             # 1.5 – 3.0 s
            speed    = 0.3 + seed * 0.3             # 0.3 – 0.6×  (languid drift)

            # ---- emit one-way pulse ----
            self.brain_widget.weight_animations.append({
                'pair': (src, dst),
                'start_time': now,
                'duration': duration,
                'start_weight': weight,
                'end_weight': weight,
                'neuron1': src,
                'neuron2': dst,
                'color': colour,
                'pulse_speed': speed
            })

    # ---------- helper ----------
    def _hsv_to_rgb(self, h, s, v):
        """Fast HSV→RGB 0-255"""
        s, v = s / 255.0, v / 255.0
        c = v * s
        x = c * (1 - abs((h / 60.0) % 2 - 1))
        m = v - c
        if h < 60:   r, g, b = c, x, 0
        elif h <120: r, g, b = x, c, 0
        elif h <180: r, g, b = 0, c, x
        elif h <240: r, g, b = 0, x, c
        elif h <300: r, g, b = x, 0, c
        else:        r, g, b = c, 0, x
        return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    
    def intelligent_pruning(self) -> Optional[str]:
        """Prune neurons based on utility."""
        candidates = []
        
        for name, func_neuron in self.functional_neurons.items():
            if time.time() - func_neuron.creation_context.timestamp < 300:
                continue
            
            score = 0.0
            score += func_neuron.utility_score * 0.4
            
            recency = time.time() - func_neuron.last_activated
            if recency < 300:
                score += 0.3
            elif recency < 1800:
                score += 0.15
            
            similar_count = sum(1 for n in self.functional_neurons.values() 
                              if n.specialization == func_neuron.specialization)
            if similar_count == 1:
                score += 0.3
            
            total_strength = sum(
                abs(w) for (a, b), w in self.brain_widget.weights.items()
                if a == name or b == name
            )
            score += min(total_strength / 5.0, 0.3)
            
            candidates.append((name, score))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[1])
        neuron_to_prune = candidates[0][0]
        
        # Remove from brain widget
        if neuron_to_prune in self.brain_widget.neuron_positions:
            del self.brain_widget.neuron_positions[neuron_to_prune]
        if neuron_to_prune in self.brain_widget.state:
            del self.brain_widget.state[neuron_to_prune]
        
        # Remove connections
        for conn in list(self.brain_widget.weights.keys()):
            if neuron_to_prune in conn:
                del self.brain_widget.weights[conn]
        
        # Remove from functional neurons
        if neuron_to_prune in self.functional_neurons:
            fn = self.functional_neurons[neuron_to_prune]
            if fn.neuron_type == 'novelty':
                self.novelty_neuron_count -= 1
            del self.functional_neurons[neuron_to_prune]
        
        print(f"🗑️ Pruned: {neuron_to_prune}")
        return neuron_to_prune
    
    def to_dict(self) -> dict:
        return {
            'functional_neurons': {
                name: neuron.to_dict() 
                for name, neuron in self.functional_neurons.items()
            },
            'experience_buffer': self.experience_buffer.to_dict(),
            'novelty_neuron_count': self.novelty_neuron_count,
            'neurons_created_this_session': self.neurons_created_this_session,
            'last_creation_by_type': self.last_creation_by_type.copy(),
            'awarded_neurons': list(self._awarded_neurons)
        }
    
    def from_dict(self, data: dict):
        self.functional_neurons = {}
        for name, neuron_data in data.get('functional_neurons', {}).items():
            self.functional_neurons[name] = FunctionalNeuron.from_dict(neuron_data)
        
        if 'experience_buffer' in data:
            self.experience_buffer = ExperienceBuffer.from_dict(data['experience_buffer'])
        
        self.novelty_neuron_count = data.get('novelty_neuron_count', 0)
        self.neurons_created_this_session = data.get('neurons_created_this_session', 0)
        self.last_creation_by_type = data.get('last_creation_by_type', 
                                              {'novelty': 0, 'stress': 0, 'reward': 0})
        self._awarded_neurons = set(data.get('awarded_neurons', []))
        
        # ensure all loaded neurons are in functional_neurons
        self.ensure_all_neurons_functional()

        # Rebuild the lab view data
        self._rebuild_new_neurons_details_for_lab()
    
    def reset_state(self):
        self.functional_neurons.clear()
        self.experience_buffer = ExperienceBuffer()
        self.novelty_neuron_count = 0
        self.neurons_created_this_session = 0
        self.last_creation_by_type = {'novelty': 0, 'stress': 0, 'reward': 0}
        self._awarded_neurons.clear()
        self._first_real_tick = None
        print("🔄 Neurogenesis state reset")


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
        # Don't trigger during sleep
        if current.get('is_sleeping', False):
            return False
        
        current_curiosity = current.get('curiosity', 50)
        previous_curiosity = previous.get('curiosity', 50)
        curiosity_delta = current_curiosity - previous_curiosity
        
        # Ignore if curiosity is at extremes
        if current_curiosity >= 99 or current_curiosity <= 1:
            return False
        
        # Check if we encountered a new object
        new_object = getattr(self.logic, 'new_object_encountered', False)
        
        # Require a significant spike AND curiosity to be reasonably high
        meaningful_spike = curiosity_delta > 15 and current_curiosity > 40
        
        return meaningful_spike or new_object
    
    def _detect_stress_experience(self, current, previous) -> bool:
        """Detect sustained or intense stress"""
        # Don't trigger during peaceful sleep
        if current.get('is_sleeping', False) and current.get('anxiety', 50) < 40:
            return False
        
        current_anxiety = current.get('anxiety', 50)
        previous_anxiety = previous.get('anxiety', 50)
        current_hunger = current.get('hunger', 50)
        # FIX: Removed stray 'a' that was here
        
        # Ignore if anxiety is at minimum
        if current_anxiety <= 5:
            return False
        
        # High anxiety sustained
        anxiety_high = current_anxiety > 65 and previous_anxiety > 60
        
        # Sudden anxiety spike
        anxiety_spike = (current_anxiety - previous_anxiety) > 15 and current_anxiety > 50
        
        # Hunger crisis
        hunger_crisis = current_hunger > 85 and (current_hunger - previous.get('hunger', 50)) >= 0
        
        return anxiety_high or anxiety_spike or hunger_crisis
    
    def _detect_reward_experience(self, current, previous) -> bool:
        """Detect positive outcome experiences"""
        # Don't trigger during sleep with maxed stats
        if current.get('is_sleeping', False):
            happiness = current.get('happiness', 50)
            satisfaction = current.get('satisfaction', 50)
            if happiness >= 90 and satisfaction >= 90:
                return False
        
        current_happiness = current.get('happiness', 50)
        previous_happiness = previous.get('happiness', 50)
        current_satisfaction = current.get('satisfaction', 50)
        previous_satisfaction = previous.get('satisfaction', 50)
        
        happiness_delta = current_happiness - previous_happiness
        satisfaction_delta = current_satisfaction - previous_satisfaction
        
        # Ignore if stats are already maxed out
        if (current_happiness >= 99 and previous_happiness >= 99) or \
           (current_satisfaction >= 99 and previous_satisfaction >= 99):
            return False
        
        # Ignore tiny fluctuations when stats are very high
        if current_happiness >= 95 and happiness_delta < 3:
            return False
        if current_satisfaction >= 95 and satisfaction_delta < 3:
            return False
        
        # Check if positive outcome flag is set
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
                            'is_startled', 'is_fleeing', 'is_sick']}
        
        return ExperienceContext(
            trigger_type=trigger_type,
            active_neurons=filtered_neurons,
            recent_actions=list(self.recent_actions),
            environmental_state={
                'food_count': len(self.logic.food_items),
                'poop_count': len(self.logic.poop_items),
                'is_sick': self.logic.squid.is_sick,
                'is_eating': current_state.get('is_eating', False),
                'has_rock': hasattr(self.logic, 'rock_items') and len(self.logic.rock_items) > 0
            },
            outcome='neutral',
            timestamp=time.time()
        )