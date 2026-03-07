"""
Neurogenesis ver3.3_stress_cap

- STRICT 5-neuron cap for 'stress' type.
- Emergency triggers STRENGTHEN existing neurons if cap is reached.
- Anxiety reduction logic based on multipliers.
"""

import time
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Any
from PyQt5.QtCore import QTimer

# Import localisation with robust fallback
try:
    from localisation import loc
except ImportError:
    def loc(key, default=None, **kwargs):
        return default if default is not None else key.replace('_', ' ').title()


@dataclass
class ExperienceContext:
    trigger_type: str
    active_neurons: Dict[str, float]
    recent_actions: List[str]
    environmental_state: Dict[str, any]
    outcome: str
    timestamp: float
    
    def get_pattern_signature(self) -> str:
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
        pattern_parts = [self.trigger_type, self.outcome, primary_neuron, get_range(primary_value)]
        meaningful_actions = [a for a in self.recent_actions[-3:] if a and a != 'none' and a != 'idle']
        if meaningful_actions:
            last_action = meaningful_actions[-1].lower()
            if 'rock' in last_action: pattern_parts.append("rock")
            elif 'poop' in last_action: pattern_parts.append("poop")
            elif 'food' in last_action or 'eat' in last_action: pattern_parts.append("food")
            elif 'sleep' in last_action: pattern_parts.append("sleep")
        return "_".join(pattern_parts)
    
    def get_core_pattern(self) -> str:
        motivational_neurons = {
            k: v for k, v in self.active_neurons.items() 
            if k in ['hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity', 'cleanliness', 'sleepiness']
        }
        if not motivational_neurons: return f"{self.trigger_type}_{self.outcome}"
        primary_neuron, primary_value = max(motivational_neurons.items(), key=lambda x: abs(x[1] - 50))
        intensity = "high" if primary_value > 60 or primary_value < 40 else "mid"
        return f"{self.trigger_type}_{self.outcome}_{primary_neuron}_{intensity}"
    
    def get_parent_pattern(self) -> str:
        motivational_neurons = {k: v for k, v in self.active_neurons.items() 
                                if not k.startswith('is_') and k not in [
                                    'position', 'direction', 'status', 'pursuing_food',
                                    'novelty_exposure', 'sustained_stress', 'recent_rewards', 
                                    'personality', 'neurogenesis_active'
                                ]}
        top_neurons = sorted(motivational_neurons.items(), key=lambda x: abs(x[1] - 50), reverse=True)[:2]
        pattern = f"{self.trigger_type}_{self.outcome}"
        for neuron, activation in top_neurons:
            if activation < 40: pattern += f"_{neuron}_low"
            elif activation > 60: pattern += f"_{neuron}_high"
        return pattern

class ExperienceBuffer:
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
            self.pattern_counts = {k: v for k, v in self.pattern_counts.items() if k in recent_patterns}
        if len(self.parent_pattern_counts) > self._max_pattern_entries // 2:
            recent_parents = {exp.get_parent_pattern() for exp in self.buffer}
            self.parent_pattern_counts = {k: v for k, v in self.parent_pattern_counts.items() if k in recent_parents}
        if len(self.core_pattern_counts) > self._max_pattern_entries // 4:
            recent_cores = {exp.get_core_pattern() for exp in self.buffer}
            self.core_pattern_counts = {k: v for k, v in self.core_pattern_counts.items() if k in recent_cores}
    
    def get_pattern_recurrence(self, context: ExperienceContext) -> Tuple[str, int, str]:
        specific = context.get_pattern_signature()
        parent = context.get_parent_pattern()
        core = context.get_core_pattern()
        specific_count = self.pattern_counts.get(specific, 0)
        parent_count = self.parent_pattern_counts.get(parent, 0)
        core_count = self.core_pattern_counts.get(core, 0)
        
        if specific_count >= 2: return ('specific', specific_count, specific)
        if parent_count >= 3: return ('parent', parent_count, parent)
        if core_count >= 5: return ('core', core_count, core)
        if specific_count >= parent_count and specific_count >= core_count: return ('specific', specific_count, specific)
        elif parent_count >= core_count: return ('parent', parent_count, parent)
        else: return ('core', core_count, core)
    
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
                } for exp in list(self.buffer)
            ]
        }

    @classmethod
    def from_dict(cls, data):
        buf = cls(max_size=data.get('buffer_size', 50))
        buf.pattern_counts = dict(data.get('pattern_counts', {}))
        buf.parent_pattern_counts = dict(data.get('parent_pattern_counts', {}))
        buf.core_pattern_counts = dict(data.get('core_pattern_counts', {}))
        for exp in data.get('recent_experiences', []):
            ctx = ExperienceContext(
                trigger_type=exp['trigger_type'],
                active_neurons={k: float(v) if isinstance(v, (int, float)) else 50.0 for k, v in exp.get('active_neurons', {}).items()},
                recent_actions=exp.get('recent_actions', []),
                environmental_state=exp.get('environmental_state', {}),
                outcome=exp.get('outcome', 'neutral'),
                timestamp=exp.get('timestamp', time.time())
            )
            buf.buffer.append(ctx)
        return buf

class FunctionalNeuron:
    def __init__(self, name: str, neuron_type: str, creation_context: ExperienceContext):
        self.name = name
        self.neuron_type = neuron_type
        self.creation_context = creation_context
        self.specialization = self._determine_specialization()
        self.activation_count = 0
        self.last_activated = 0
        self.utility_score = 0.0
        self.strength_multiplier = 1.0

    @property
    def display_name(self) -> str:
        type_key = f"neuron_type_{self.neuron_type}"
        type_default = self.neuron_type.capitalize()
        type_str = loc(type_key, default=type_default)
        spec_key = f"spec_{self.specialization}"
        spec_default = self.specialization.replace('_', ' ').title()
        spec_str = loc(spec_key, default=spec_default)
        parts = self.name.split('_')
        suffix = ""
        if parts[-1].isdigit(): suffix = f" {parts[-1]}"
        return loc("neuron_name_format", default="{type}: {spec}{suffix}", type=type_str, spec=spec_str, suffix=suffix)

    @classmethod
    def from_dict(cls, data):
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
            if ctx.environmental_state.get('is_eating', False): return 'feeding_satisfaction'
            elif ctx.active_neurons.get('cleanliness', 50) > 70 and ctx.outcome == 'positive': return 'cleanliness_reward'
            elif ctx.active_neurons.get('sleepiness', 50) < 30 and ctx.outcome == 'positive': return 'rest_reward'
            else: return 'general_reward'
        elif ctx.trigger_type == 'stress':
            if ctx.active_neurons.get('hunger', 50) > 70: return 'hunger_stress_response'
            elif ctx.active_neurons.get('cleanliness', 50) < 30: return 'filth_avoidance'
            elif ctx.active_neurons.get('anxiety', 50) > 70: return 'anxiety_regulation'
            else: return 'general_stress_coping'
        elif ctx.trigger_type == 'novelty':
            if ctx.environmental_state.get('has_rock', False) or 'rock' in str(ctx.environmental_state): return 'object_investigation'
            elif 'new_location' in ctx.recent_actions: return 'exploration_memory'
            else: return 'general_novelty_processing'
        return 'undefined'
    
    def get_functional_connections(self, all_neurons: List[str]) -> Dict[str, float]:
        connections = {}
        ctx = self.creation_context
        for neuron, activation in ctx.active_neurons.items():
            if neuron in all_neurons:
                try: activation_value = float(activation) if isinstance(activation, (int, float, str)) else 50.0
                except (ValueError, TypeError): activation_value = 50.0
                deviation = abs(activation_value - 50)
                if deviation > 20:
                    weight = (deviation / 50) * 0.8
                    if activation_value < 50: weight = -weight
                    connections[neuron] = weight
        spec_connections = self._get_specialization_connections(all_neurons)
        connections.update(spec_connections)
        return connections
    
    def _get_specialization_connections(self, all_neurons: List[str]) -> Dict[str, float]:
        connections = {}
        
        # === STRESS SPECIFIC LOGIC FOR INHIBITING ANXIETY ===
        if self.neuron_type == 'stress':
             # All stress neurons should naturally inhibit anxiety to simulate coping
             if 'anxiety' in all_neurons: connections['anxiety'] = -1.0
             
        if self.specialization == 'feeding_satisfaction':
            if 'hunger' in all_neurons: connections['hunger'] = -0.7
            if 'happiness' in all_neurons: connections['happiness'] = 0.6
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.8
        elif self.specialization == 'hunger_stress_response':
            if 'hunger' in all_neurons: connections['hunger'] = 0.7
            if 'anxiety' in all_neurons: connections['anxiety'] = -0.8 # Inhibition
            if 'curiosity' in all_neurons: connections['curiosity'] = 0.4
        elif self.specialization == 'filth_avoidance':
            if 'cleanliness' in all_neurons: connections['cleanliness'] = -0.8
            if 'anxiety' in all_neurons: connections['anxiety'] = 0.6 # This causes anxiety
        elif self.specialization == 'anxiety_regulation':
            if 'anxiety' in all_neurons: connections['anxiety'] = -1.0 # Strong inhibition
            if 'happiness' in all_neurons: connections['happiness'] = 0.4
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.3
        elif self.specialization == 'general_stress_coping':
             if 'anxiety' in all_neurons: connections['anxiety'] = -0.9
        elif self.specialization == 'object_investigation':
            if 'curiosity' in all_neurons: connections['curiosity'] = 0.7
            if 'anxiety' in all_neurons: connections['anxiety'] = -0.4
        elif self.specialization == 'rest_reward':
            if 'sleepiness' in all_neurons: connections['sleepiness'] = -0.6
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.5
            if 'happiness' in all_neurons: connections['happiness'] = 0.4
        elif self.specialization == 'cleanliness_reward':
            if 'cleanliness' in all_neurons: connections['cleanliness'] = 0.6
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.5
            if 'anxiety' in all_neurons: connections['anxiety'] = -0.3
        return connections
    
    def calculate_activation(self, brain_state: Dict[str, float], weights: Dict[Tuple[str, str], float]) -> float:
        activation = 50.0
        for (source, target), weight in weights.items():
            if target == self.name and source in brain_state:
                source_activation = float(brain_state[source])
                influence = (source_activation - 50.0) * weight
                activation += influence
        activation = 50.0 + (activation - 50.0) * self.strength_multiplier
        activation = max(0.0, min(100.0, activation))
        if abs(activation - 50.0) > 15.0:
            self.activation_count += 1
            self.last_activated = time.time()
        return activation
    
    def update_utility_score(self, outcome_value: float):
        alpha = 0.3
        self.utility_score = alpha * outcome_value + (1 - alpha) * self.utility_score

class EnhancedNeurogenesis:
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

    def _get_stress_neuron_count(self) -> int:
        """Count current stress neurons."""
        return len([n for n, fn in self.functional_neurons.items() 
                    if getattr(fn, 'neuron_type', '') == 'stress'])
    
    def _get_anxiety_cap(self) -> float:
        """
        Calculate the maximum anxiety allowed based on stress neuron count.
        Each stress neuron reduces the cap by 10, representing growing resilience.
        
        0 neurons: cap = 100 (no protection)
        1 neuron:  cap = 90
        2 neurons: cap = 80
        3 neurons: cap = 70
        4 neurons: cap = 60
        5 neurons: cap = 50 (maximum resilience - anxiety can never exceed 50!)
        """
        stress_count = self._get_stress_neuron_count()
        cap = 100.0 - (stress_count * 10.0)
        return max(50.0, cap)  # Floor at 50 even if somehow more than 5 neurons
    
    def _get_scaled_relief(self, base_amount: float, is_emergency: bool = False) -> float:
        """
        Calculate anxiety relief that scales with existing stress neuron count.
        More neurons = stronger relief (cumulative coping mechanisms).
        
        Base formula: base_amount * (1 + 0.5 * stress_count)
        - 0 neurons: 1.0x multiplier
        - 1 neuron:  1.5x multiplier  
        - 2 neurons: 2.0x multiplier
        - 3 neurons: 2.5x multiplier
        - 4 neurons: 3.0x multiplier
        - 5 neurons: 3.5x multiplier
        
        Emergency adds an additional 1.5x multiplier.
        """
        stress_count = self._get_stress_neuron_count()
        multiplier = 1.0 + (0.5 * stress_count)
        
        if is_emergency:
            multiplier *= 1.5
            
        return base_amount * multiplier

    def _apply_anxiety_relief(self, base_drop: float, source: str = "stress_neuron", 
                               is_emergency: bool = False) -> float:
        """
        Apply scaled anxiety relief to BOTH the brain_widget state AND the actual squid.
        Relief scales with stress neuron count, and respects the anxiety cap.
        
        Args:
            base_drop: Base amount to reduce anxiety by (will be scaled)
            source: Description for logging
            is_emergency: Whether this is an emergency situation (extra multiplier)
            
        Returns:
            The new anxiety value
        """
        old_anxiety = self.brain_widget.state.get('anxiety', 50)
        stress_count = self._get_stress_neuron_count()
        anxiety_cap = self._get_anxiety_cap()
        scaled_drop = self._get_scaled_relief(base_drop, is_emergency)
        
        # Apply the drop
        new_anxiety = max(0.0, old_anxiety - scaled_drop)
        
        # Also enforce the cap (in case anxiety was already above it)
        new_anxiety = min(new_anxiety, anxiety_cap)
        
        # 1. Update brain_widget state (for visualization)
        self.brain_widget.state['anxiety'] = new_anxiety
        
        # 2. CRITICAL: Also update the actual squid's anxiety!
        if (hasattr(self.brain_widget, 'tamagotchi_logic') and 
            self.brain_widget.tamagotchi_logic and
            hasattr(self.brain_widget.tamagotchi_logic, 'squid') and
            self.brain_widget.tamagotchi_logic.squid):
            squid = self.brain_widget.tamagotchi_logic.squid
            squid.anxiety = new_anxiety
            emergency_str = " [EMERGENCY]" if is_emergency else ""
            print(f"   ✅ {source}{emergency_str}: Anxiety {old_anxiety:.1f} → {new_anxiety:.1f} "
                  f"(drop: -{scaled_drop:.1f}, cap: {anxiety_cap:.0f}, neurons: {stress_count})")
        else:
            print(f"   ⚠️ {source}: Could not access squid - relief only applied to brain_widget!")
        
        return new_anxiety
    
    def enforce_anxiety_cap(self) -> None:
        """
        Enforce the anxiety cap based on current stress neuron count.
        Call this periodically to ensure anxiety never exceeds the cap.
        """
        anxiety_cap = self._get_anxiety_cap()
        
        # Enforce on brain_widget state
        if 'anxiety' in self.brain_widget.state:
            current = self.brain_widget.state['anxiety']
            if current > anxiety_cap:
                self.brain_widget.state['anxiety'] = anxiety_cap
        
        # Enforce on actual squid
        if (hasattr(self.brain_widget, 'tamagotchi_logic') and 
            self.brain_widget.tamagotchi_logic and
            hasattr(self.brain_widget.tamagotchi_logic, 'squid') and
            self.brain_widget.tamagotchi_logic.squid):
            squid = self.brain_widget.tamagotchi_logic.squid
            if squid.anxiety > anxiety_cap:
                old = squid.anxiety
                squid.anxiety = anxiety_cap
                print(f"   🛡️ Anxiety cap enforced: {old:.1f} → {anxiety_cap:.1f} (stress neurons: {self._get_stress_neuron_count()})")

    def create_neuron(self, neuron_type: str, context: Optional[ExperienceContext] = None, brain_state: Optional[Dict[str, float]] = None, environment: Optional[Dict[str, Any]] = None, trigger_value: Optional[float] = None, is_emergency: bool = False) -> Optional[str]:
        if context is None:
            if brain_state is None: brain_state = dict(self.brain_widget.state)
            if environment is None: environment = {}
            context = self._build_context(neuron_type, brain_state, environment)
        return self._create_neuron_internal(context, trigger_value, is_emergency)
    
    def _make_reciprocal_connections(self, new_neuron: str):
        bw = self.brain_widget
        created = []                       
        MIN_RECIPROCAL = 0.2               
        outgoing = [(tgt, w) for (src, tgt), w in bw.weights.items() if src == new_neuron and abs(w) >= MIN_RECIPROCAL]
        for target, w in outgoing:
            if (target, new_neuron) in bw.weights: continue
            bw.weights[(target, new_neuron)] = w
            created.append(f"{target}→{new_neuron}:{w:+.2f}")
        if created: print(f"   🔗 {loc('log_reciprocal_links', default='Reciprocal links added')}: {', '.join(created)}")
    
    def create_functional_neuron(self, ctx: ExperienceContext, is_emergency: bool = False) -> Optional[str]:
        return self._create_neuron_internal(ctx, is_emergency=is_emergency)
    
    def _build_context(self, trigger_type: str, brain_state: Dict[str, float], environment: Dict[str, Any]) -> ExperienceContext:
        clean_neurons = {k: float(v) if isinstance(v, (int, float)) else 50.0 for k, v in brain_state.items() if not k.startswith('is_') and k not in ['novelty_exposure', 'sustained_stress', 'recent_rewards', 'neurogenesis_active', 'personality', 'pursuing_food', 'position', 'direction', 'status']}
        happiness = brain_state.get('happiness', 50)
        anxiety = brain_state.get('anxiety', 50)
        if happiness > 60: outcome = 'positive'
        elif anxiety > 70: outcome = 'negative'
        else: outcome = 'neutral'
        return ExperienceContext(trigger_type=trigger_type, active_neurons=clean_neurons, recent_actions=list(self.recent_actions)[-5:], environmental_state=environment, outcome=outcome, timestamp=time.time())
    
    def _create_neuron_internal(self, ctx: ExperienceContext, trigger_value_for_log: Optional[float] = None, is_emergency: bool = False) -> Optional[str]:
        trigger_type = ctx.trigger_type
        
        # 0. CHECK EMERGENCY CONTEXT
        if not is_emergency and trigger_type == 'stress':
            if ctx.active_neurons.get('anxiety', 50) >= 90:
                is_emergency = True
                print(f"🚨 {loc('log_emergency_context', default='Emergency context detected (Anxiety > 90)')}")

        # 1. HARD TYPE CAP & STRENGTHENING LOGIC
        # FORCE CAP OF 5 FOR STRESS NEURONS
        default_caps = {'stress': 5, 'novelty': 6, 'reward': 6, 'connector': 10}
        max_for_this_type = self.config.neurogenesis.get('max_per_type', default_caps).get(trigger_type, 5)
        
        # Ensure stress is strictly 5
        if trigger_type == 'stress': max_for_this_type = 5

        current_type_count = len([name for name, fn in self.functional_neurons.items() if fn.neuron_type == trigger_type])

        # IF CAP REACHED: STRENGTHEN EXISTING (Even in Emergency)
        if current_type_count >= max_for_this_type:
            msg = loc('log_type_cap_reached', default="Type cap reached for {type} ({count}/{max}), strengthening existing", type=trigger_type, count=current_type_count, max=max_for_this_type)
            print(f"   {msg}")
            
            # If emergency, we perform a strengthening action as the coping mechanism
            if is_emergency:
                print(f"   💪 Emergency: Boosting stress tolerance via existing neurons.")
                # [FIXED] Apply SCALED relief to BOTH brain_widget AND squid
                if 'anxiety' in self.brain_widget.state:
                    self._apply_anxiety_relief(15.0, "Emergency strengthen", is_emergency=True)
                
            self._strengthen_existing_neuron(trigger_type, self._preview_specialization(ctx))
            return None

        # 2. SPECIALIZATION
        spec = self._preview_specialization(ctx)
        base_name = f"{trigger_type}_{spec}"

        # 3. GLOBAL NEURON LIMIT
        current_total = len(self.brain_widget.neuron_positions) - len(self.brain_widget.excluded_neurons)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_total >= max_neurons and not is_emergency:
            print(f"   Max neurons reached ({current_total}/{max_neurons})")
            return None
        elif is_emergency and current_total >= max_neurons:
             print(f"⚠️ {loc('log_global_cap_bypass', default='Emergency override: Bypassing global neuron limit!')}")

        neuron_name = self._get_unique_neuron_name(base_name)
        func_neuron = FunctionalNeuron(neuron_name, trigger_type, ctx)
        self.functional_neurons[neuron_name] = func_neuron
        if trigger_type == 'novelty': self.novelty_neuron_count += 1
        self.last_creation_by_type[trigger_type] = time.time()
        self.neurons_created_this_session += 1
        
        position = self._calculate_functional_position(func_neuron)
        self.brain_widget.neuron_positions[neuron_name] = position
        self._set_neuron_appearance(neuron_name, func_neuron)
        self.brain_widget.state[neuron_name] = 50.0
        
        # [FIXED] Immediate Anxiety Relief upon creation - SCALED based on existing neurons!
        if trigger_type == 'stress' and 'anxiety' in self.brain_widget.state:
            base_drop = 15.0  # Base drop amount (will be scaled by helper)
            new_anxiety = self._apply_anxiety_relief(base_drop, f"Stress Neuron '{neuron_name}' created", is_emergency=is_emergency)
            print(f"   📉 Stress Neuron Created: Anxiety now at {new_anxiety:.1f} (cap: {self._get_anxiety_cap():.0f})")

        connections = func_neuron.get_functional_connections(list(self.brain_widget.neuron_positions.keys()))
        for target, weight in connections.items():
            if abs(weight) < 0.05: continue
            self.brain_widget.weights[(neuron_name, target)] = weight
        self._make_reciprocal_connections(neuron_name)
        
        if hasattr(self.brain_widget, 'visible_neurons'): self.brain_widget.visible_neurons.add(neuron_name)
        self.brain_widget.neurogenesis_highlight = {'neuron': neuron_name, 'start_time': time.time(), 'duration': 8.0 if trigger_type == 'connector' else 4.0, 'pulse_phase': 0}
        self._log_neuron_creation(neuron_name, trigger_type, spec, trigger_value_for_log)
        self._record_neurogenesis_memory(neuron_name)
        return neuron_name

    def _record_neurogenesis_memory(self, neuron_name: str):
        """Permanently records a new neuron growth event in long-term memory."""
        try:
            if (hasattr(self.brain_widget, 'tamagotchi_logic') and
                    self.brain_widget.tamagotchi_logic and
                    hasattr(self.brain_widget.tamagotchi_logic, 'squid') and
                    self.brain_widget.tamagotchi_logic.squid and
                    hasattr(self.brain_widget.tamagotchi_logic.squid, 'memory_manager')):
                mm = self.brain_widget.tamagotchi_logic.squid.memory_manager
                mm.add_long_term_memory(
                    'neurogenesis',
                    f'grew_neuron_{neuron_name}',
                    f'GREW A NEW NEURON!: {neuron_name}'
                )
        except Exception as e:
            print(f"⚠️ Could not record neurogenesis memory: {e}")

    def _on_neuron_created(self, neuron_name: str, neuron_type: str):
        self._trigger_link_toggle_effect()
    
    def _get_unique_neuron_name(self, base_name: str) -> str:
        if base_name not in self.brain_widget.neuron_positions: return base_name
        counter = 2
        while True:
            candidate = f"{base_name}_{counter}"
            if candidate not in self.brain_widget.neuron_positions: return candidate
            counter += 1

    def _rebuild_new_neurons_details(self):
        core = {'hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity'}
        details = self.brain_widget.neurogenesis_data.setdefault('new_neurons_details', {})
        for name, fn in self.functional_neurons.items():
            if name in core or name in self.brain_widget.excluded_neurons: continue
            if name not in details:
                details[name] = {'created_at': fn.creation_context.timestamp, 'trigger_type': fn.neuron_type, 'trigger_value_at_creation': 0, 'specialisation': fn.specialization, 'display_name': fn.display_name}
            details[name]['display_name'] = fn.display_name

    def _rebuild_new_neurons_details_for_lab(self):
        self._rebuild_new_neurons_details()
    
    def _preview_specialization(self, ctx: ExperienceContext) -> str:
        if ctx.trigger_type == 'reward':
            if ctx.environmental_state.get('is_eating', False): return 'feeding_satisfaction'
            if ctx.active_neurons.get('cleanliness', 50) > 70 and ctx.outcome == 'positive': return 'cleanliness_reward'
            if ctx.active_neurons.get('sleepiness', 50) < 30 and ctx.outcome == 'positive': return 'rest_reward'
            return 'general_reward'
        if ctx.trigger_type == 'stress':
            if ctx.active_neurons.get('hunger', 50) > 70: return 'hunger_stress_response'
            if ctx.active_neurons.get('cleanliness', 50) < 30: return 'filth_avoidance'
            if ctx.active_neurons.get('anxiety', 50) > 70: return 'anxiety_regulation'
            return 'general_stress_coping'
        if ctx.trigger_type == 'novelty':
            if ctx.environmental_state.get('has_rock', False) or 'rock' in str(ctx.environmental_state): return 'object_investigation'
            if 'new_location' in ctx.recent_actions: return 'exploration_memory'
            return 'general_novelty_processing'
        return 'undefined'
    
    def _calculate_functional_position(self, func_neuron: FunctionalNeuron) -> Tuple[float, float]:
        all_neurons = list(self.brain_widget.neuron_positions.keys())
        connections = func_neuron.get_functional_connections(all_neurons)
        if not connections: return (random.randint(100, 900), random.randint(100, 600))
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

    def rescue_orphan(self, orphan_name: str):
        connector_type = 'connector'
        neuron_name = self._get_unique_neuron_name(f"{connector_type}_rescue")
        ctx = ExperienceContext(trigger_type=connector_type, active_neurons=self.brain_widget.state.copy(), recent_actions=[], environmental_state={'orphan_rescue': True}, outcome='neutral', timestamp=time.time())
        func_neuron = FunctionalNeuron(neuron_name, connector_type, ctx)
        func_neuron.specialization = 'network_bridge'
        self.functional_neurons[neuron_name] = func_neuron
        orphan_pos = self.brain_widget.neuron_positions.get(orphan_name, (500, 300))
        center_x, center_y = 512, 384
        new_x = (orphan_pos[0] + center_x) / 2 + random.randint(-50, 50)
        new_y = (orphan_pos[1] + center_y) / 2 + random.randint(-50, 50)
        self.brain_widget.neuron_positions[neuron_name] = (new_x, new_y)
        self.brain_widget.state[neuron_name] = 50.0
        binary_neurons = {"can_see_food", "is_eating", "is_sleeping", "is_sick", "is_fleeing", "pursuing_food", "is_startled", "external_stimulus", "plant_proximity"}
        candidates = [n for n in self.brain_widget.neuron_positions.keys() if n != orphan_name and n != neuron_name and n not in self.brain_widget.excluded_neurons and n not in binary_neurons]
        targets = []
        if candidates:
            def get_dist_sq(n_name):
                pos = self.brain_widget.neuron_positions[n_name]
                return (pos[0] - orphan_pos[0])**2 + (pos[1] - orphan_pos[1])**2
            candidates.sort(key=get_dist_sq)
            targets.append(candidates.pop(0))
            if candidates: targets.append(random.choice(candidates))
        weight = random.uniform(0.5, 0.9)
        if random.random() > 0.5: self.brain_widget.weights[(neuron_name, orphan_name)] = weight
        else: self.brain_widget.weights[(orphan_name, neuron_name)] = weight
        for target in targets:
            w = random.uniform(-0.5, 0.8)
            if abs(w) < 0.2: w = 0.3
            if random.random() > 0.5: self.brain_widget.weights[(neuron_name, target)] = w
            else: self.brain_widget.weights[(target, neuron_name)] = w
        self._set_neuron_appearance(neuron_name, func_neuron)
        if hasattr(self.brain_widget, 'visible_neurons'): self.brain_widget.visible_neurons.add(neuron_name)
        self.brain_widget.neurogenesis_highlight = {'neuron': neuron_name, 'start_time': time.time(), 'duration': 8.0, 'pulse_phase': 0}
        self.brain_widget.log_neurogenesis_event(neuron_name, "created", details={'trigger_type': 'connector', 'trigger_value': 1.0, 'specialization': 'orphan_rescue', 'display_name': func_neuron.display_name})
        self._record_neurogenesis_memory(neuron_name)
        print(f"🔗 Connector neuron {neuron_name} created to rescue {orphan_name} (connected to closest: {targets[0] if targets else 'None'})")
    
    def _set_neuron_appearance(self, name: str, func_neuron: FunctionalNeuron):
        spec = func_neuron.specialization
        neuron_type = func_neuron.neuron_type
        shape_map = {'novelty': 'diamond', 'stress': 'square', 'reward': 'triangle', 'connector': 'hexagon'}
        assigned_shape = shape_map.get(neuron_type, 'circle')
        self.brain_widget.neuron_shapes[name] = assigned_shape
        print(f"🔧 SET NEURON APPEARANCE: {name} -> type={neuron_type}, shape={assigned_shape}")
        if neuron_type == 'connector': self.brain_widget.state_colors[name] = (50, 51, 100)
        elif 'stress' in spec or 'anxiety' in spec: self.brain_widget.state_colors[name] = (255, 150, 150)
        elif 'reward' in spec or 'satisfaction' in spec: self.brain_widget.state_colors[name] = (150, 255, 150)
        elif 'investigation' in spec or 'exploration' in spec: self.brain_widget.state_colors[name] = (255, 215, 0)
        else:
            color_map = {'novelty': (255, 255, 150), 'stress': (255, 0, 0), 'reward': (173, 216, 230)}
            self.brain_widget.state_colors[name] = color_map.get(neuron_type, (200, 200, 255))
    
    def _log_neuron_creation(self, name: str, trigger_type: str, spec: str, trigger_value: Optional[float]):
        display_name = self.functional_neurons[name].display_name
        self.brain_widget.log_neurogenesis_event(name, "created", details={'trigger_type': trigger_type, 'trigger_value': trigger_value or 0, 'specialization': spec, 'display_name': display_name})
    
    def _strengthen_existing_neuron(self, trigger_type: str, specialization: str):
        prefix = f"{trigger_type}_{specialization}"
        existing = [(name, neuron) for name, neuron in self.functional_neurons.items() if name.startswith(prefix)]
        if not existing:
            brain_neurons = [name for name in self.brain_widget.neuron_positions.keys() if name.startswith(prefix)]
            if brain_neurons:
                self._ensure_functional_neuron(brain_neurons[0], trigger_type, specialization)
                if brain_neurons[0] in self.functional_neurons: existing = [(brain_neurons[0], self.functional_neurons[brain_neurons[0]])]
        
        # If no specific specialization match, fallback to any neuron of the same type
        # This ensures coping mechanisms upgrade ANY stress neuron if the specific one is missing
        if not existing and trigger_type == 'stress':
             existing = [(name, neuron) for name, neuron in self.functional_neurons.items() if neuron.neuron_type == 'stress']

        if not existing: return
        
        existing.sort(key=lambda x: x[1].utility_score, reverse=True)
        best_name, best_neuron = existing[0]
        
        best_neuron.strength_multiplier += 0.5
        best_neuron.utility_score += 0.1
        self.brain_widget.communication_events[best_name] = time.time()
        self.brain_widget.update()
        
        # We manually format the string to ensure the variables are injected
        raw_msg = loc('log_strengthened_neuron', default="Strengthened: {name} (multiplier: {mult}x)")
        formatted_msg = raw_msg.format(name=best_neuron.display_name, mult=f"{best_neuron.strength_multiplier:.1f}")
        print(f"   💪 {formatted_msg}")
        
        if self._on_neuron_leveled_callback:
            try: self._on_neuron_leveled_callback(best_name, best_neuron.strength_multiplier)
            except Exception as e: print(f"Level callback error: {e}")
        self.brain_widget.update()
    
    def _ensure_functional_neuron(self, name: str, neuron_type: str = None, specialization: str = None) -> Optional[FunctionalNeuron]:
        if name in self.functional_neurons: return self.functional_neurons[name]
        if name not in self.brain_widget.neuron_positions: return None
        if neuron_type is None:
            if name.startswith('novelty'): neuron_type = 'novelty'
            elif name.startswith('stress'): neuron_type = 'stress'
            elif name.startswith('reward'): neuron_type = 'reward'
            else: neuron_type = 'novelty'
        ctx = ExperienceContext(trigger_type=neuron_type, active_neurons=dict(self.brain_widget.state), recent_actions=[], environmental_state={}, outcome='neutral', timestamp=time.time())
        func_neuron = FunctionalNeuron(name, neuron_type, ctx)
        if specialization: func_neuron.specialization = specialization
        self.functional_neurons[name] = func_neuron
        print(f"   {loc('log_converted_neuron', default='Converted {name} to FunctionalNeuron', name=name)}")
        return func_neuron
    
    def ensure_all_neurons_functional(self, force_sync=False):
        core_neurons = ['hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity']
        excluded = getattr(self.brain_widget, 'excluded_neurons', [])
        for name in list(self.brain_widget.neuron_positions.keys()):
            if name in core_neurons or name in excluded: continue
            if name not in self.functional_neurons: self._ensure_functional_neuron(name)
        restored_positions = 0
        restored_states = 0
        restored_visible = 0
        for name, fn in self.functional_neurons.items():
            if name in core_neurons or name in excluded: continue
            if name not in self.brain_widget.neuron_positions:
                position = self._calculate_functional_position(fn)
                self.brain_widget.neuron_positions[name] = position
                restored_positions += 1
            if name not in self.brain_widget.state:
                self.brain_widget.state[name] = 50.0
                restored_states += 1
            if hasattr(self.brain_widget, 'visible_neurons'):
                if name not in self.brain_widget.visible_neurons: restored_visible += 1
                self.brain_widget.visible_neurons.add(name)
            self._set_neuron_appearance(name, fn)
            all_neurons = list(self.brain_widget.neuron_positions.keys())
            connections = fn.get_functional_connections(all_neurons)
            for target, weight in connections.items():
                if (name, target) not in self.brain_widget.weights: self.brain_widget.weights[(name, target)] = weight
        self._rebuild_new_neurons_details()
        new_neurons_list = self.brain_widget.neurogenesis_data.setdefault('new_neurons', [])
        restored_to_list = 0
        for name, fn in self.functional_neurons.items():
            if name in core_neurons or name in excluded: continue
            if name not in new_neurons_list:
                new_neurons_list.append(name)
                restored_to_list += 1
        restored_count = len([n for n in self.functional_neurons if n not in core_neurons and n not in excluded])
        if restored_count > 0: print(f"✅ {loc('log_sync_complete', default='Neurogenesis sync complete')}: {restored_count}")
    
    def set_achievement_callbacks(self, on_created=None, on_leveled=None):
        self._on_neuron_created_callback = on_created
        self._on_neuron_leveled_callback = on_leveled

    def get_global_cooldown_remaining(self) -> float:
        if not self.functional_neurons: return 0.0
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
        trigger_type = self._detect_trigger_type(brain_state, environment)
        if trigger_type:
            self.capture_experience_context(trigger_type=trigger_type, brain_state=brain_state, recent_actions=list(self.recent_actions), environment=environment)
    
    def _detect_trigger_type(self, brain_state: dict, environment: dict) -> Optional[str]:
        anxiety = brain_state.get('anxiety', 50)
        satisfaction = brain_state.get('satisfaction', 50)
        curiosity = brain_state.get('curiosity', 50)
        happiness = brain_state.get('happiness', 50)
        if anxiety > 75: return 'stress'
        if environment.get('new_object_encountered', False) or curiosity > 70: return 'novelty'
        if environment.get('recent_positive_outcome', False) or satisfaction > 70 or happiness > 70: return 'reward'
        if len(self.last_states) > 0:
            prev_anxiety = self.last_states[-1].get('anxiety', 50)
            if prev_anxiety > 60 and anxiety < 40: return 'stress'
        return None

    def capture_experience_context(self, trigger_type: str, brain_state: dict, recent_actions: list, environment: dict) -> ExperienceContext:
        if self._first_real_tick is None: self._first_real_tick = time.time()
        if not isinstance(recent_actions, list): recent_actions = []
        ctx = self._build_context(trigger_type, brain_state, environment)
        ctx.recent_actions = recent_actions[-5:] if recent_actions else []
        elapsed = time.time() - self._first_real_tick
        if elapsed < 1.5: return ctx
        is_sleeping = brain_state.get('is_sleeping', False)
        anxiety = brain_state.get('anxiety', 50)
        satisfaction = brain_state.get('satisfaction', 50)
        if is_sleeping and anxiety < 15 and satisfaction > 85: return ctx
        self.experience_buffer.add_experience(ctx)
        return ctx
    
    def should_create_neuron(self, ctx: ExperienceContext) -> bool:
        current_time = time.time()
        if ctx.trigger_type == 'stress' and ctx.active_neurons.get('anxiety', 50) >= 95:
            print(f"🚨 {loc('log_emergency_forcing_neuron', default='EMERGENCY: Critical anxiety - forcing stress neuron!')}")
            return True
        if self._first_real_tick is None: return False
        elapsed = current_time - self._first_real_tick
        if elapsed < 5.0: return False
        pattern = ctx.get_pattern_signature()
        if len(pattern.split('_')) < 4: return False
        if self.experience_buffer.pattern_counts.get(pattern, 0) > 20: return False
        current_count = len(self.brain_widget.neuron_positions)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_count >= max_neurons: return False
        global_cooldown = self.config.neurogenesis.get('cooldown', 60)
        default_time = self._first_real_tick or time.time()
        last_creation = max((n.creation_context.timestamp for n in self.functional_neurons.values()), default=default_time)
        if current_time - last_creation < global_cooldown: return False
        pattern_level, count, _ = self.experience_buffer.get_pattern_recurrence(ctx)
        thresholds = {'specific': 2, 'parent': 3, 'core': 5}
        if count < thresholds.get(pattern_level, 2): return False
        return True
    
    def update_neuron_activations(self, brain_state: Dict[str, float]) -> None:
            # 1. Normalize inputs
            for key in list(brain_state.keys()):
                if not isinstance(brain_state[key], (int, float)):
                    try: brain_state[key] = float(brain_state[key])
                    except (ValueError, TypeError): brain_state[key] = 50.0

            # 2. Standard Neural Activation
            for name, func_neuron in self.functional_neurons.items():
                if name in self.brain_widget.state:
                    activation = func_neuron.calculate_activation(brain_state, self.brain_widget.weights)
                    self.brain_widget.state[name] = activation

            # 3. === SCALED STRESS REDUCTION MECHANIC ===
            # Each stress neuron contributes to anxiety suppression, with scaling based on count
            if 'anxiety' in brain_state:
                current_anxiety = brain_state['anxiety']
                stress_count = self._get_stress_neuron_count()
                anxiety_cap = self._get_anxiety_cap()
                
                # First, enforce the cap - anxiety should never exceed the cap
                if current_anxiety > anxiety_cap:
                    current_anxiety = anxiety_cap
                    brain_state['anxiety'] = anxiety_cap
                    self.brain_widget.state['anxiety'] = anxiety_cap
                
                total_reduction = 0.0
                
                for name, fn in self.functional_neurons.items():
                    if getattr(fn, 'neuron_type', '') == 'stress':
                        multiplier = getattr(fn, 'strength_multiplier', 1.0)
                        
                        # Force stress neuron to activate proportionally to anxiety
                        driven = 50.0 + (current_anxiety - 50.0) * 1.2
                        driven = max(50.0, min(100.0, driven))
                        
                        current_val = self.brain_widget.state.get(name, 50.0)
                        final_val = max(current_val, driven)
                        self.brain_widget.state[name] = final_val
                        
                        if final_val > 55:
                            infl = (final_val - 50.0) / 50.0 
                            # Base force per neuron, scaled by strength multiplier
                            reduction_force = 25.0 * multiplier * infl
                            total_reduction += reduction_force

                if total_reduction > 0:
                    # Scale reduction based on stress neuron count (cumulative resilience)
                    # More neurons = faster anxiety reduction
                    count_multiplier = 1.0 + (0.3 * stress_count)  # 1.0 to 2.5x
                    total_reduction *= count_multiplier
                    
                    # Crisis response multipliers
                    if current_anxiety > 80:
                        total_reduction *= 3.0  # Strong crisis response
                    elif current_anxiety > 60:
                        total_reduction *= 1.5
                    
                    # Apply reduction with timestep factor
                    reduction_amount = total_reduction * 0.3
                    new_anxiety = max(0.0, current_anxiety - reduction_amount)
                    
                    # Enforce cap again after reduction
                    new_anxiety = min(new_anxiety, anxiety_cap)
                    
                    # Apply to brain state dictionaries
                    brain_state['anxiety'] = new_anxiety
                    self.brain_widget.state['anxiety'] = new_anxiety
                    
                    # CRITICAL: Also apply to the actual squid!
                    if (hasattr(self.brain_widget, 'tamagotchi_logic') and 
                        self.brain_widget.tamagotchi_logic and
                        hasattr(self.brain_widget.tamagotchi_logic, 'squid') and
                        self.brain_widget.tamagotchi_logic.squid):
                        squid = self.brain_widget.tamagotchi_logic.squid
                        
                        # Also enforce cap on squid's current anxiety before we compare
                        if squid.anxiety > anxiety_cap:
                            squid.anxiety = anxiety_cap
                        
                        old_squid_anxiety = squid.anxiety
                        squid.anxiety = new_anxiety
                        
                        if reduction_amount > 1.0:  # Only log significant reductions
                            print(f"   🧘 Stress suppression ({stress_count} neurons): "
                                  f"{old_squid_anxiety:.1f} → {new_anxiety:.1f} "
                                  f"(-{reduction_amount:.1f}, cap: {anxiety_cap:.0f})")

            # 4. Visualizations
            if not getattr(self.brain_widget, 'animations_enabled', True): return
            if not hasattr(self.brain_widget, 'trigger_activation_pulse'): return

            now = time.time()
            for (src, dst), weight in self.brain_widget.weights.items():
                if abs(weight) < 0.15: continue
                seed = hash((src, dst)) % 1_000_000 / 1_000_000.0
                excite = seed * 0.85 + 0.15
                if excite < 0.22: continue
                skip = int(3 + seed * 9)
                if int(now * 60) % skip != 0: continue

                src_act = brain_state.get(src, 50.0)
                influence = (src_act - 50.0) * weight
                if abs(influence) < 6.0: continue

                if influence > 0:
                    base_hue = 65 + seed * 25; sat = 70 + seed * 40; val = 120 + seed * 30
                else:
                    base_hue = 5 + seed * 20; sat = 75 + seed * 35; val = 115 + seed * 30

                rgb = self._hsv_to_rgb(base_hue, sat, val)
                alpha = 80 + int(seed * 60)
                colour = (*rgb, alpha)
                duration = 1.5 + seed * 1.5
                speed = 0.3 + seed * 0.3

                self.brain_widget.weight_animations.append({
                    'pair': (src, dst), 'start_time': now, 'duration': duration,
                    'start_weight': weight, 'end_weight': weight,
                    'neuron1': src, 'neuron2': dst, 'color': colour, 'pulse_speed': speed
                })

    def _hsv_to_rgb(self, h, s, v):
        s, v = s / 255.0, v / 255.0
        c = v * s
        x = c * (1 - abs((h / 60.0) % 2 - 1))
        m = v - c
        if h < 60: r, g, b = c, x, 0
        elif h <120: r, g, b = x, c, 0
        elif h <180: r, g, b = 0, c, x
        elif h <240: r, g, b = 0, x, c
        elif h <300: r, g, b = x, 0, c
        else: r, g, b = c, 0, x
        return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    
    def intelligent_pruning(self) -> Optional[str]:
        candidates = []
        for name, func_neuron in self.functional_neurons.items():
            if func_neuron.neuron_type == 'connector': continue
            if time.time() - func_neuron.creation_context.timestamp < 300: continue
            score = 0.0
            score += func_neuron.utility_score * 0.4
            recency = time.time() - func_neuron.last_activated
            if recency < 300: score += 0.3
            elif recency < 1800: score += 0.15
            similar_count = sum(1 for n in self.functional_neurons.values() if n.specialization == func_neuron.specialization)
            if similar_count == 1: score += 0.3
            total_strength = sum(abs(w) for (a, b), w in self.brain_widget.weights.items() if a == name or b == name)
            score += min(total_strength / 5.0, 0.3)
            candidates.append((name, score))
        if not candidates: return None
        candidates.sort(key=lambda x: x[1])
        neuron_to_prune = candidates[0][0]
        if neuron_to_prune in self.brain_widget.neuron_positions: del self.brain_widget.neuron_positions[neuron_to_prune]
        if neuron_to_prune in self.brain_widget.state: del self.brain_widget.state[neuron_to_prune]
        for conn in list(self.brain_widget.weights.keys()):
            if neuron_to_prune in conn: del self.brain_widget.weights[conn]
        if neuron_to_prune in self.functional_neurons:
            fn = self.functional_neurons[neuron_to_prune]
            if fn.neuron_type == 'novelty': self.novelty_neuron_count -= 1
            del self.functional_neurons[neuron_to_prune]
        print(f"🗑️ {loc('log_pruned', default='Pruned')}: {neuron_to_prune}")
        return neuron_to_prune
    
    def to_dict(self) -> dict:
        return {
            'functional_neurons': {name: neuron.to_dict() for name, neuron in self.functional_neurons.items()},
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
        self.last_creation_by_type = data.get('last_creation_by_type', {'novelty': 0, 'stress': 0, 'reward': 0})
        self._awarded_neurons = set(data.get('awarded_neurons', []))
        self.ensure_all_neurons_functional()
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

class NeurogenesisTriggerSystem:
    def __init__(self, tamagotchi_logic):
        self.logic = tamagotchi_logic
        self.recent_actions = deque(maxlen=10)
        self.last_states = deque(maxlen=5)
        
    def track_action(self, action: str):
        self.recent_actions.append(action)
    
    def track_state_change(self, state: Dict[str, float]):
        self.last_states.append(state.copy())
    
    def check_for_significant_experience(self) -> Optional[Tuple[str, ExperienceContext]]:
        if len(self.last_states) < 2: return None
        current = self.last_states[-1]
        previous = self.last_states[-2]
        state_change = 0
        for key in ['hunger', 'happiness', 'satisfaction', 'anxiety', 'curiosity']:
            if key in current and key in previous:
                state_change += abs(current.get(key, 50) - previous.get(key, 50))
        if state_change < 5 and not getattr(self.logic, 'new_object_encountered', False): return None
        if self._detect_novelty_experience(current, previous):
            context = self._build_context('novelty', current)
            return ('novelty', context)
        if self._detect_stress_experience(current, previous):
            context = self._build_context('stress', current)
            return ('stress', context)
        if self._detect_reward_experience(current, previous):
            context = self._build_context('reward', current)
            return ('reward', context)
        return None
    
    def _detect_novelty_experience(self, current, previous) -> bool:
        if current.get('is_sleeping', False): return False
        current_curiosity = current.get('curiosity', 50)
        previous_curiosity = previous.get('curiosity', 50)
        curiosity_delta = current_curiosity - previous_curiosity
        if current_curiosity >= 99 or current_curiosity <= 1: return False
        new_object = getattr(self.logic, 'new_object_encountered', False)
        meaningful_spike = curiosity_delta > 15 and current_curiosity > 40
        return meaningful_spike or new_object
    
    def _detect_stress_experience(self, current, previous) -> bool:
        if current.get('is_sleeping', False) and current.get('anxiety', 50) < 40: return False
        current_anxiety = current.get('anxiety', 50)
        previous_anxiety = previous.get('anxiety', 50)
        current_hunger = current.get('hunger', 50)
        if current_anxiety <= 5: return False
        anxiety_high = current_anxiety > 65 and previous_anxiety > 60
        anxiety_spike = (current_anxiety - previous_anxiety) > 15 and current_anxiety > 50
        hunger_crisis = current_hunger > 85 and (current_hunger - previous.get('hunger', 50)) >= 0
        return anxiety_high or anxiety_spike or hunger_crisis
    
    def _detect_reward_experience(self, current, previous) -> bool:
        if current.get('is_sleeping', False):
            happiness = current.get('happiness', 50)
            satisfaction = current.get('satisfaction', 50)
            if happiness >= 90 and satisfaction >= 90: return False
        current_happiness = current.get('happiness', 50)
        previous_happiness = previous.get('happiness', 50)
        current_satisfaction = current.get('satisfaction', 50)
        previous_satisfaction = previous.get('satisfaction', 50)
        happiness_delta = current_happiness - previous_happiness
        satisfaction_delta = current_satisfaction - previous_satisfaction
        if (current_happiness >= 99 and previous_happiness >= 99) or \
           (current_satisfaction >= 99 and previous_satisfaction >= 99): return False
        if current_happiness >= 95 and happiness_delta < 3: return False
        if current_satisfaction >= 95 and satisfaction_delta < 3: return False
        positive_outcome = getattr(self.logic, 'recent_positive_outcome', False)
        significant_happiness = happiness_delta > 15 and current_happiness > 40
        significant_satisfaction = satisfaction_delta > 15 and current_satisfaction > 40
        return significant_happiness or significant_satisfaction or positive_outcome
    
    def _build_context(self, trigger_type: str, current_state: Dict) -> ExperienceContext:
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
