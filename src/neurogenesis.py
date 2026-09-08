"""
Neurogenesis ver4.0 - capability-driven structural plasticity.

The old model was "something happened, therefore grow". Anxiety crossed 75 and
a stress neuron appeared; curiosity crossed 70 and a novelty neuron appeared.
Growth was a reflex to an event, and the network it grew into had no say in
whether the structure was needed.

The model now is: the existing network cannot usefully represent, respond to
or express something, and that failure has persisted, so it develops structure
capable of doing so. The diagnosis lives in capability.py; this module is the
growth itself:

  * take an actionable Deficit from the CapabilityMonitor,
  * grow one neuron wired specifically to remedy it,
  * write the reason into the provenance ledger so it can always be answered,
  * and stand down (strengthening what already exists) when the network has
    enough structure of that kind already.

Everything that was here before is still here - functional specialisation,
per-type caps, the stress-neuron anxiety cap, reciprocal wiring, positional
placement, appearance, pruning, achievements, save/load. What changed is the
question that starts it.
"""

import time
import math
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Set, Any

from .capability import Deficit, regulation_specialisation

# Localisation. The package-relative import is the one that works when the
# game runs; the flat fallback covers running this module standalone. The old
# fallback dropped **kwargs, so every localised string with a placeholder came
# out literally - which is why grown neurons were displayed to the player as
# "{type}: {spec}{suffix}".
try:
    from .localisation import loc
except ImportError:  # pragma: no cover - standalone use
    try:
        from localisation import loc
    except ImportError:
        def loc(key, default=None, **kwargs):
            text = default if default is not None else key.replace('_', ' ').title()
            if kwargs:
                try:
                    return text.format(**kwargs)
                except (KeyError, ValueError, IndexError):
                    return text
            return text


# Evocative names for grown neurons. Purely presentational: config.ini
# [Neurogenesis] showmanship decides whether a neuron is called
# "anxiety_reduction" or "stress_anxiety_regulation". The name is chosen once,
# at birth, by the engine - there is no second system that renames a neuron
# afterwards and has to migrate every dictionary that referenced it.
#
# Keyed by SPECIALISATION, because that is what the neuron actually does. A
# pool keyed by type produced neurons called "food_reward" whose job was stress
# coping, which is worse than no flavour at all.
# A grown neuron may be deepened rather than duplicated when its type cap is
# reached, but only so far: past this the neuron's output saturates every
# target it touches on any input at all.
MAX_STRENGTH_MULTIPLIER = 4.0

EVOCATIVE_NAMES: Dict[str, List[str]] = {
    # reward family
    'feeding_satisfaction':        ["food_reward", "feeding_payoff"],
    'cleanliness_reward':          ["cleanliness_reward", "fresh_water_joy"],
    'rest_reward':                 ["rest_reward", "restfulness"],
    'general_reward':              ["contentment_signal", "satisfaction_burst"],
    # stress family
    'anxiety_regulation':          ["anxiety_reduction", "calm_restore"],
    'hunger_stress_response':      ["hunger_alarm", "foraging_urgency"],
    'filth_avoidance':             ["filth_avoidance", "squalor_alarm"],
    'general_stress_coping':       ["comfort_seeking", "fear_dampener"],
    # novelty family
    'object_investigation':        ["encountered_novel_object", "wonder_trigger"],
    'exploration_memory':          ["exploration_reward", "place_memory"],
    'general_novelty_processing':  ["new_experience", "discovery_satisfaction"],
    'role_separation':             ["role_separation", "second_opinion"],
    # learned expectation
    'learned_expectation':         ["learned_expectation", "anticipation"],
    # connectivity
    'network_bridge':              ["relay_bridge", "crossroads"],
    'connectivity_bridge':         ["relay_bridge", "waypoint"],
}

# Fallback when a specialisation has no pool of its own.
EVOCATIVE_NAMES_BY_TYPE: Dict[str, List[str]] = {
    'novelty':   ["investigation_drive", "curiosity_spark"],
    'stress':    ["safety_signal", "tension_release"],
    'reward':    ["play_reward", "achievement_signal"],
    'connector': ["junction", "waypoint"],
}


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
    def __init__(self, name: str, neuron_type: str, creation_context: ExperienceContext,
                 origin_deficit: Optional[Dict[str, Any]] = None):
        self.name = name
        self.neuron_type = neuron_type
        self.creation_context = creation_context
        self.specialization = self._determine_specialization()
        self.activation_count = 0
        self.last_activated = 0
        self.utility_score = 0.0
        self.strength_multiplier = 1.0
        # The capability deficit this neuron was grown to remedy. This is the
        # authoritative answer to "why does this neuron exist?" and travels
        # with the neuron through save/load.
        self.origin_deficit: Dict[str, Any] = dict(origin_deficit or {})

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
        neuron.origin_deficit = dict(data.get('origin_deficit') or {})
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
            'origin_deficit': dict(self.origin_deficit),
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
        # The table below used to stop here, so a neuron with any other
        # specialisation - general_reward, general_novelty_processing,
        # exploration_memory, learned_expectation, role_separation - got
        # nothing at all, and in a brain sitting near neutral it was born
        # with ZERO synapses: counted, drawn, capped against, and unable to
        # do anything. The connectivity detector would then "rescue" it,
        # which is the architecture patching a defect it created at birth.
        # Every specialisation the engine can produce now says what it does.
        elif self.specialization == 'general_reward':
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.7
            if 'happiness' in all_neurons: connections['happiness'] = 0.5
        elif self.specialization == 'general_novelty_processing':
            if 'curiosity' in all_neurons: connections['curiosity'] = 0.6
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.3
        elif self.specialization == 'exploration_memory':
            if 'curiosity' in all_neurons: connections['curiosity'] = 0.5
            if 'anxiety' in all_neurons: connections['anxiety'] = -0.3
        elif self.specialization == 'learned_expectation':
            # Wired specifically by the expression deficit that grew it; this
            # keeps it viable if it was created without one.
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.4
            if 'curiosity' in all_neurons: connections['curiosity'] = 0.3
        elif self.specialization == 'role_separation':
            # Its real inputs come from the differentiation deficit; this is
            # only what it does with them.
            if 'satisfaction' in all_neurons: connections['satisfaction'] = 0.3
            if 'happiness' in all_neurons: connections['happiness'] = 0.3
        elif self.specialization in ('network_bridge', 'connectivity_bridge'):
            # A connector's whole job is the orphan it was grown for; the
            # connectivity remedy supplies that wiring.
            pass
        return connections
    
    def calculate_activation(self, brain_state: Dict[str, float], weights: Dict[Tuple[str, str], float]) -> float:
        """The transfer function, for inspection tools and tests.

        This is NOT the simulation's propagation step - BrainWidget.
        propagate_activations() is, and it implements exactly this formula for
        every neuron in the network. Kept here so a tool can ask "what would
        this neuron do given that state?" without stepping the brain.
        """
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
        self._last_growth_at = 0.0
        self.recent_actions = deque(maxlen=10)
        self.last_states = deque(maxlen=5)
        self._on_neuron_created_callback = None
        self._on_neuron_leveled_callback = None

        # The deficit the next creation is meant to remedy. Set by
        # should_create_neuron(), consumed by create_functional_neuron(), so
        # there is exactly one place a growth decision is made and exactly one
        # place it is carried out.
        self.pending_deficit: Optional[Deficit] = None
        self.growth_log: deque = deque(maxlen=40)
        self.stood_down: deque = deque(maxlen=20)

        # Growth pacing reads the clock through here. In the game that is wall
        # clock; the headless trainer runs thousands of simulated seconds per
        # real second, so it substitutes simulated time and the cooldowns mean
        # what they say instead of blocking every growth in the run.
        self.clock = time.time

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
        return self._create_neuron_internal(context, trigger_value, is_emergency,
                                            deficit=self.pending_deficit)
    
    def _make_reciprocal_connections(self, new_neuron: str,
                                     deficit: Optional[Deficit] = None
                                     ) -> List[Tuple[str, str, float, str]]:
        """Give the new neuron a way to be driven by what it drives.

        A neuron with only outgoing synapses can never be activated by the
        network, so it can never express anything it was grown for.
        """
        from .brain_constants import is_learning_target
        bw = self.brain_widget
        created = []
        wiring: List[Tuple[str, str, float, str]] = []
        MIN_RECIPROCAL = 0.2
        # The return path is DAMPED, not a copy of the forward weight.
        #
        # Copying it made every grown neuron half of a self-amplifying loop:
        # satisfaction drives the neuron, the neuron drives satisfaction, and a
        # correlational rule that converges a synapse to the correlation
        # between its endpoints then pinned both at the clamp. The squid's
        # "strongest knowledge" ended up being tautologies about neurons it had
        # just grown. config.ini has declared reciprocal_strength since 2.4 and
        # nothing read it; it is what this is for.
        props = self.config.neurogenesis.get('neuron_properties', {}) or {}
        damping = float(props.get('reciprocal_strength', 0.15) or 0.15)
        outgoing = [(tgt, w) for (src, tgt), w in bw.weights.items()
                    if src == new_neuron and abs(w) >= MIN_RECIPROCAL]
        for target, w in outgoing:
            if (target, new_neuron) in bw.weights: continue
            # The reverse edge must be readable. A synapse pointing into a
            # sensor is inert - the world overwrites that neuron every tick.
            if not is_learning_target(new_neuron):
                continue
            back = w * damping
            if self._wire(target, new_neuron, back, 'reciprocal', deficit):
                created.append(f"{target}→{new_neuron}:{back:+.2f}")
                wiring.append((target, new_neuron, float(back), 'reciprocal'))
        if created: print(f"   🔗 {loc('log_reciprocal_links', default='Reciprocal links added')}: {', '.join(created)}")
        return wiring
    
    def create_functional_neuron(self, ctx: ExperienceContext, is_emergency: bool = False,
                                 deficit: Optional[Deficit] = None) -> Optional[str]:
        """Grow one neuron to remedy a deficit. The single creation entry point."""
        return self._create_neuron_internal(ctx, is_emergency=is_emergency,
                                            deficit=deficit or self.pending_deficit)
    
    def _build_context(self, trigger_type: str, brain_state: Dict[str, float], environment: Dict[str, Any]) -> ExperienceContext:
        clean_neurons = {k: float(v) if isinstance(v, (int, float)) else 50.0 for k, v in brain_state.items() if not k.startswith('is_') and k not in ['novelty_exposure', 'sustained_stress', 'recent_rewards', 'neurogenesis_active', 'personality', 'pursuing_food', 'position', 'direction', 'status']}
        happiness = brain_state.get('happiness', 50)
        anxiety = brain_state.get('anxiety', 50)
        if happiness > 60: outcome = 'positive'
        elif anxiety > 70: outcome = 'negative'
        else: outcome = 'neutral'
        return ExperienceContext(trigger_type=trigger_type, active_neurons=clean_neurons, recent_actions=list(self.recent_actions)[-5:], environmental_state=environment, outcome=outcome, timestamp=time.time())
    
    def _create_neuron_internal(self, ctx: ExperienceContext,
                                trigger_value_for_log: Optional[float] = None,
                                is_emergency: bool = False,
                                deficit: Optional[Deficit] = None) -> Optional[str]:
        """Grow one neuron. The only place in the project that creates one.

        `deficit` is the functional deficiency the neuron is being grown to
        remedy; it decides the type, the specialisation and - crucially - the
        wiring, so the new structure is capable of the thing the network could
        not do. Without one (a direct call from the Designer or a test) the
        experience context still supplies a sensible default.
        """
        deficit = deficit or self.pending_deficit
        trigger_type = (deficit.suggested_type if deficit is not None
                        else ctx.trigger_type)
        # The engine only knows four structural families; anything else is a
        # novelty-class representation neuron.
        if trigger_type not in ('stress', 'novelty', 'reward', 'connector'):
            trigger_type = 'novelty'

        # 0. EMERGENCY: a maximum-severity deficit is an emergency by
        #    definition - the squid is in trouble the network cannot get it out
        #    of. Acute anxiety remains an emergency for backward compatibility.
        if not is_emergency:
            if deficit is not None and deficit.severity >= 1.0:
                is_emergency = True
            elif trigger_type == 'stress' and ctx.active_neurons.get('anxiety', 50) >= 90:
                is_emergency = True
                print(f"🚨 {loc('log_emergency_context', default='Emergency context detected (Anxiety > 90)')}")

        # 1. HARD TYPE CAP & STRENGTHENING LOGIC
        # A cap that has been reached is itself an answer: the brain already
        # has structure of this kind, so deepen it rather than duplicating it.
        default_caps = {'stress': 5, 'novelty': 6, 'reward': 6, 'connector': 10}
        max_for_this_type = self.config.neurogenesis.get('max_per_type', default_caps).get(trigger_type, 5)

        # Ensure stress is strictly 5
        if trigger_type == 'stress': max_for_this_type = 5

        current_type_count = len([name for name, fn in self.functional_neurons.items() if fn.neuron_type == trigger_type])

        spec = (deficit.specialization if deficit is not None
                else self._preview_specialization(ctx))

        # IF CAP REACHED: STRENGTHEN EXISTING (Even in Emergency)
        if current_type_count >= max_for_this_type:
            msg = loc('log_type_cap_reached', default="Type cap reached for {type} ({count}/{max}), strengthening existing", type=trigger_type, count=current_type_count, max=max_for_this_type)
            print(f"   {msg}")

            # If emergency, we perform a strengthening action as the coping mechanism
            if is_emergency:
                print(f"   💪 Emergency: Boosting stress tolerance via existing neurons.")
                if 'anxiety' in self.brain_widget.state:
                    self._apply_anxiety_relief(15.0, "Emergency strengthen", is_emergency=True)

            self._strengthen_existing_neuron(trigger_type, spec)
            # Deepening existing structure is a growth action and is paced like
            # one. Without this the engine strengthened on every single
            # evaluation once a type cap was reached.
            self._last_growth_at = self.clock()
            self.stood_down.append((time.time(),
                                    deficit.key if deficit else trigger_type,
                                    f"already has {current_type_count} {trigger_type} "
                                    f"neurons; strengthened one instead"))
            return None

        # 2. GLOBAL NEURON LIMIT
        current_total = len(self.brain_widget.neuron_positions) - len(self.brain_widget.excluded_neurons)
        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        if current_total >= max_neurons and not is_emergency:
            print(f"   Max neurons reached ({current_total}/{max_neurons})")
            return None
        elif is_emergency and current_total >= max_neurons:
             print(f"⚠️ {loc('log_global_cap_bypass', default='Emergency override: Bypassing global neuron limit!')}")

        # 3. NAME. Showmanship (config.ini [Neurogenesis] showmanship) gives the
        #    neuron an evocative name instead of type_specialisation. It is a
        #    presentation choice made once, here, rather than a wrapper that
        #    renames the neuron after the fact and has to migrate a dozen
        #    dictionaries to do it.
        base_name = self._choose_name(trigger_type, spec)
        neuron_name = self._get_unique_neuron_name(base_name)

        func_neuron = FunctionalNeuron(neuron_name, trigger_type, ctx,
                                       origin_deficit=deficit.to_dict() if deficit else {})
        func_neuron.specialization = spec
        self.functional_neurons[neuron_name] = func_neuron
        if trigger_type == 'novelty': self.novelty_neuron_count += 1
        self.last_creation_by_type[trigger_type] = time.time()
        self._last_growth_at = self.clock()
        self.neurons_created_this_session += 1

        position = self._calculate_functional_position(func_neuron)
        self.brain_widget.neuron_positions[neuron_name] = position
        self._set_neuron_appearance(neuron_name, func_neuron)
        self.brain_widget.state[neuron_name] = 50.0

        # Immediate anxiety relief on growing a coping neuron, scaled by how
        # many the squid already has. This is the structure taking effect, not
        # a reward for the event that produced it.
        if trigger_type == 'stress' and 'anxiety' in self.brain_widget.state:
            new_anxiety = self._apply_anxiety_relief(
                15.0, f"Stress Neuron '{neuron_name}' created", is_emergency=is_emergency)
            print(f"   📉 Stress Neuron Created: Anxiety now at {new_anxiety:.1f} (cap: {self._get_anxiety_cap():.0f})")

        # 4. WIRING. Specialisation wiring first (what a neuron of this kind
        #    always does), then the remedy wiring the deficit specifically
        #    calls for, which overrides it.
        #    The two plans are merged BEFORE anything is written, so each
        #    synapse is created once with its final value. Writing the
        #    specialisation weight and then overwriting it with the remedy
        #    weight put three meaningless intermediate values in the neuron's
        #    permanent record.
        plan: Dict[Tuple[str, str], Tuple[float, str]] = {}
        connections = func_neuron.get_functional_connections(list(self.brain_widget.neuron_positions.keys()))
        for target, weight in connections.items():
            if abs(weight) < 0.05: continue
            plan[(neuron_name, target)] = (float(weight), 'specialisation')
        for src, dst, weight, purpose in self._remedy_wiring(neuron_name, deficit, func_neuron):
            plan[(src, dst)] = (float(weight), purpose)

        wiring: List[Tuple[str, str, float, str]] = []
        for (src, dst), (weight, purpose) in plan.items():
            if self._wire(src, dst, weight, purpose, deficit):
                wiring.append((src, dst, weight, purpose))
        wiring.extend(self._make_reciprocal_connections(neuron_name, deficit))

        # A neuron that cannot be driven, or cannot drive anything, is not a
        # neuron - it is an entry in a dictionary. Growing one is worse than
        # growing nothing, because it counts against the caps and has to be
        # rescued later. Check the post-condition here, where it can still be
        # met, rather than leaving the connectivity detector to find it.
        wiring.extend(self._ensure_viable(neuron_name, func_neuron, deficit))

        if hasattr(self.brain_widget, 'visible_neurons'): self.brain_widget.visible_neurons.add(neuron_name)
        self.brain_widget.neurogenesis_highlight = {
            'neuron': neuron_name, 'start_time': time.time(),
            'duration': 8.0 if trigger_type == 'connector' else 4.0,
            'pulse_phase': 0,
            'is_emergency': is_emergency,
            'color_burst': self._burst_colour(trigger_type)}

        self._record_origin(neuron_name, func_neuron, deficit, wiring)
        self._log_neuron_creation(neuron_name, trigger_type, spec, trigger_value_for_log)
        self._record_neurogenesis_memory(neuron_name)

        # The deficit has been answered; stop counting it against the network
        # so growth does not chase the same gap twice.
        monitor = self.capability
        if monitor is not None and deficit is not None:
            monitor.clear(deficit.key, f"grew {neuron_name}")
        self.pending_deficit = None
        self.growth_log.append({
            'neuron': neuron_name, 'at': time.time(),
            'deficit': deficit.kind if deficit else 'unclassified',
            'because': deficit.summary if deficit else 'created directly',
        })

        self._notify_neuron_created(neuron_name)
        return neuron_name

    # ------------------------------------------------------------------
    # Wiring helpers
    # ------------------------------------------------------------------
    def _wire(self, src: str, dst: str, weight: float, purpose: str,
              deficit: Optional[Deficit]) -> bool:
        """Create one synapse, through the brain so it lands in the ledger."""
        from .brain_constants import is_learning_target
        bw = self.brain_widget
        if src == dst:
            return False
        positions = getattr(bw, 'neuron_positions', {})
        if src not in positions or dst not in positions:
            return False
        if not is_learning_target(dst):
            return False      # a synapse into a sensor can never do anything

        note = (f"wired at birth to {purpose}"
                + (f" — {deficit.remedy}" if deficit and purpose == 'remedy' else ""))
        # No fallback: a brain that cannot record a synapse has no business
        # growing one. Both BrainWidget and the headless trainer implement this.
        return bool(bw.apply_weight_change(
            (src, dst), value=float(weight), mechanism='neurogenesis',
            detail={'purpose': purpose, 'note': note,
                    'deficit': deficit.key if deficit else ''},
            create=True))

    def _remedy_wiring(self, neuron_name: str, deficit: Optional[Deficit],
                       func_neuron: 'FunctionalNeuron'
                       ) -> List[Tuple[str, str, float, str]]:
        """The connections that make the new neuron capable of the missing thing.

        This is what separates capability-driven growth from decorative growth:
        the neuron is not merely born near the action, it is born wired to do
        the specific job the network could not do.
        """
        if deficit is None:
            return []
        plan: List[Tuple[str, str, float, str]] = []
        state = getattr(self.brain_widget, 'state', {}) or {}

        if deficit.kind == 'regulation':
            stat = deficit.target
            direction = deficit.evidence.get('direction', 'down')
            corrective = -0.9 if direction == 'down' else 0.9
            # Driven by the drive it regulates (and whatever predicts it), so
            # it comes on exactly when the problem is present...
            plan.append((stat, neuron_name, 0.8, 'remedy'))
            for source in deficit.sources:
                if source != stat and source in state:
                    plan.append((source, neuron_name, 0.5, 'remedy'))
            # ...and pushes back on it when it does.
            plan.append((neuron_name, stat, corrective, 'remedy'))

        elif deficit.kind == 'representation':
            # Take the sensors that define the situation as its inputs, signed
            # by how they present, so this neuron and nothing else fires for it.
            for source in deficit.sources:
                if source not in state:
                    continue
                value = state.get(source)
                if isinstance(value, bool):
                    value = 100.0 if value else 0.0
                if not isinstance(value, (int, float)):
                    continue
                weight = max(-0.9, min(0.9, (float(value) - 50.0) / 50.0 * 0.8))
                if abs(weight) < 0.2:
                    weight = 0.6
                plan.append((source, neuron_name, weight, 'remedy'))

        elif deficit.kind == 'expression':
            cue = deficit.evidence.get('cue')
            stat = deficit.target
            wanted = float(deficit.evidence.get('wanted_sign', 1.0))
            if cue:
                plan.append((cue, neuron_name, 0.8, 'remedy'))
            if stat:
                plan.append((neuron_name, stat, 0.7 * wanted, 'remedy'))

        elif deficit.kind == 'differentiation':
            # Take the conflicting driver off the overloaded neuron and give it
            # its own representation, then let the new one feed the target.
            offload = deficit.sources[0] if deficit.sources else None
            target = deficit.target
            if offload:
                plan.append((offload, neuron_name, 0.8, 'remedy'))
                old = self.brain_widget.weights.get((offload, target))
                if old is not None:
                    plan.append((neuron_name, target, float(old), 'remedy'))
                    self._retire_edge((offload, target),
                                      f"handed over to {neuron_name}")

        elif deficit.kind == 'connectivity':
            orphan = deficit.target
            if orphan:
                plan.append((neuron_name, orphan, 0.7, 'remedy'))
                plan.append((orphan, neuron_name, 0.7, 'remedy'))
        return plan

    def _ensure_viable(self, neuron_name: str, func_neuron: 'FunctionalNeuron',
                       deficit: Optional[Deficit]
                       ) -> List[Tuple[str, str, float, str]]:
        """Guarantee the new neuron can be driven and can drive something.

        Its specialisation says what it is for; if the wiring so far has not
        connected it to the drives that specialisation names, connect it now.
        Falls back to whatever the squid's state was actually doing at the
        moment of birth, which is the most relevant thing available.
        """
        from .brain_constants import CORE_STAT_NEURONS
        bw = self.brain_widget
        incoming = [e for e in bw.weights if e[1] == neuron_name]
        outgoing = [e for e in bw.weights if e[0] == neuron_name]
        if incoming and outgoing:
            return []

        added: List[Tuple[str, str, float, str]] = []
        present = set(getattr(bw, 'neuron_positions', {}))

        # What this kind of neuron is supposed to touch.
        targets = list(func_neuron._get_specialization_connections(list(present)))
        if deficit is not None and deficit.target in present:
            targets.insert(0, deficit.target)
        # Otherwise: the drives that were furthest from neutral when it was born.
        if not targets:
            ranked = sorted(
                ((abs(float(v) - 50.0), k) for k, v in bw.state.items()
                 if k in CORE_STAT_NEURONS and isinstance(v, (int, float))
                 and not isinstance(v, bool)), reverse=True)
            targets = [k for _, k in ranked[:2]]

        for target in targets[:2]:
            if target == neuron_name:
                continue
            if not outgoing and self._wire(neuron_name, target, 0.5,
                                           'viability', deficit):
                added.append((neuron_name, target, 0.5, 'viability'))
                outgoing.append((neuron_name, target))
            if not incoming and self._wire(target, neuron_name, 0.5,
                                           'viability', deficit):
                added.append((target, neuron_name, 0.5, 'viability'))
                incoming.append((target, neuron_name))
        if added:
            partners = sorted({n for edge in added for n in edge[:2]
                               if n != neuron_name})
            print(f"   \U0001f9ea {neuron_name} would have been born inert; "
                  f"wired it to {', '.join(partners)}")
        return added

    def _retire_edge(self, edge: Tuple[str, str], reason: str) -> None:
        bw = self.brain_widget
        if edge not in getattr(bw, 'weights', {}):
            return
        bw.remove_weight(edge, mechanism='neurogenesis', reason=reason)

    def _choose_name(self, trigger_type: str, spec: str) -> str:
        """type_specialisation, or an evocative name when showmanship is on.

        The evocative name must still describe what the neuron does, so it is
        drawn from the specialisation's pool first.
        """
        if not self._showmanship_enabled():
            return f"{trigger_type}_{spec}"
        pool = list(EVOCATIVE_NAMES.get(spec) or []) + \
            list(EVOCATIVE_NAMES_BY_TYPE.get(trigger_type) or [])
        taken = set(self.functional_neurons) | set(
            getattr(self.brain_widget, 'neuron_positions', {}))
        for candidate in pool:
            if candidate not in taken:
                return candidate
        return f"{trigger_type}_{spec}"

    def _showmanship_enabled(self) -> bool:
        cfg = getattr(self.config, 'neurogenesis', None)
        if isinstance(cfg, dict):
            return bool(cfg.get('showmanship', True))
        return True

    @staticmethod
    def _burst_colour(trigger_type: str) -> tuple:
        base = {'novelty': (255, 215, 0), 'stress': (255, 100, 100),
                'reward': (100, 255, 100), 'connector': (150, 150, 255)
                }.get(trigger_type, (200, 200, 255))
        return tuple(max(0, min(255, c + random.randint(-20, 20))) for c in base)

    def _record_origin(self, neuron_name: str, func_neuron: 'FunctionalNeuron',
                       deficit: Optional[Deficit],
                       wiring: List[Tuple[str, str, float, str]]) -> None:
        """Write the birth record. This is the answer to 'why does it exist?'."""
        ledger = getattr(self.brain_widget, 'ledger', None)
        if ledger is None:
            return
        episode_ids = []
        causal = getattr(self.brain_widget, 'causal_learning', None)
        if causal is not None:
            episode_ids = [e.episode_id for e in list(getattr(causal, 'history', []))[-2:]]
        ledger.record_neuron_birth(
            name=neuron_name,
            deficit_kind=deficit.kind if deficit else 'representation',
            deficit_summary=(deficit.summary if deficit else
                             "grown directly, without a recorded deficit"),
            evidence=dict(deficit.evidence) if deficit else {},
            remedy=(deficit.remedy if deficit else ""),
            wiring=wiring, episode_ids=episode_ids,
            neuron_type=func_neuron.neuron_type,
            specialization=func_neuron.specialization,
            display_name=func_neuron.display_name)

    def _notify_neuron_created(self, neuron_name: str):
        """Emit one completed-birth event from the creation source."""
        signal = getattr(self.brain_widget, 'neuronCreated', None)
        if signal is not None:
            signal.emit(neuron_name)

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
        callback = getattr(self.brain_widget, '_trigger_link_toggle_effect', None)
        if callable(callback):
            callback()
    
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

    @staticmethod
    def _orient_new_edge(a: str, b: str):
        """Point a fresh synapse at an end that can actually read it.

        Direction used to be a coin flip, which produced edges into sensors -
        neurons the world rewrites every tick, so the synapse could never do
        anything.
        """
        from .brain_constants import is_learning_target
        import random as _random
        a_ok, b_ok = is_learning_target(a), is_learning_target(b)
        if a_ok and b_ok:
            return (a, b) if _random.random() > 0.5 else (b, a)
        if b_ok:
            return (a, b)
        return (b, a)

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
        deficit = Deficit(
            kind='connectivity', key=f"connectivity:{orphan_name}",
            summary=(f"{orphan_name.replace('_', ' ')} had no working connections, so "
                     f"nothing it computed could reach the rest of the brain"),
            target=orphan_name, sources=[orphan_name],
            remedy=f"give {orphan_name.replace('_', ' ')} a route back into the network",
            severity=0.9, evidence={'orphan': orphan_name},
            suggested_type='connector', specialization='network_bridge')
        func_neuron.origin_deficit = deficit.to_dict()

        wiring = []
        weight = random.uniform(0.5, 0.9)
        edge = self._orient_new_edge(neuron_name, orphan_name)
        if self._wire(edge[0], edge[1], weight, 'remedy', deficit):
            wiring.append((edge[0], edge[1], float(weight), 'remedy'))
        for target in targets:
            w = random.uniform(-0.5, 0.8)
            if abs(w) < 0.2: w = 0.3
            edge = self._orient_new_edge(neuron_name, target)
            if self._wire(edge[0], edge[1], w, 'remedy', deficit):
                wiring.append((edge[0], edge[1], float(w), 'remedy'))
        self._record_origin(neuron_name, func_neuron, deficit, wiring)
        monitor = self.capability
        if monitor is not None:
            monitor.clear(deficit.key, f"grew {neuron_name}")
        self._set_neuron_appearance(neuron_name, func_neuron)
        if hasattr(self.brain_widget, 'visible_neurons'): self.brain_widget.visible_neurons.add(neuron_name)
        self.brain_widget.neurogenesis_highlight = {'neuron': neuron_name, 'start_time': time.time(), 'duration': 8.0, 'pulse_phase': 0}
        self.brain_widget.log_neurogenesis_event(neuron_name, "created", details={'trigger_type': 'connector', 'trigger_value': 1.0, 'specialization': 'orphan_rescue', 'display_name': func_neuron.display_name})
        self._record_neurogenesis_memory(neuron_name)
        self._notify_neuron_created(neuron_name)
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

        # Strengthening is bounded. It used to add 0.5 every time the cap was
        # reached with no ceiling, which produced multipliers in the hundreds -
        # a neuron whose output saturated the whole network on any input, and
        # a squid whose brain was one screaming neuron.
        ceiling = float(self.config.neurogenesis.get('max_strength_multiplier',
                                                     MAX_STRENGTH_MULTIPLIER))
        before = best_neuron.strength_multiplier
        best_neuron.strength_multiplier = min(ceiling, before + 0.5)
        best_neuron.utility_score = min(1.0, best_neuron.utility_score + 0.1)
        if best_neuron.strength_multiplier <= before:
            print(f"   {best_neuron.display_name} is already as strong as it can get "
                  f"({ceiling:.1f}x)")
            return
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
        # Only network-driven neurons may become FunctionalNeurons. The old
        # list named the 7 core stats but not the sensors, so after a save/load
        # can_see_food was promoted into functional_neurons and would have had
        # its live sensor reading overwritten by a computed value.
        from .brain_constants import NON_PROPAGATED_NEURONS, CORE_STAT_NEURONS
        core_neurons = NON_PROPAGATED_NEURONS
        excluded = getattr(self.brain_widget, 'excluded_neurons', [])
        for name in list(self.brain_widget.neuron_positions.keys()):
            if name in core_neurons or name in excluded: continue
            if name not in self.functional_neurons: self._ensure_functional_neuron(name)
        restored_positions = 0
        restored_states = 0
        restored_visible = 0
        for name, fn in self.functional_neurons.items():
            if name in core_neurons or name in excluded: continue
            was_missing = name not in self.brain_widget.neuron_positions
            if was_missing:
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
            # Only wire a neuron that had to be RESTORED. This block used to run
            # for every functional neuron on every load, so each save/load cycle
            # silently added synapses to a network the user had designed - and
            # some of them pointed INTO sensors, which can never be driven by
            # the network at all.
            if not was_missing:
                continue
            all_neurons = list(self.brain_widget.neuron_positions.keys())
            connections = fn.get_functional_connections(all_neurons)
            for target, weight in connections.items():
                if target in core_neurons and target not in CORE_STAT_NEURONS:
                    continue  # never create an edge into a sensor
                if (name, target) not in self.brain_widget.weights:
                    self.brain_widget.weights[(name, target)] = weight
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
        if not self._last_growth_at: return 0.0
        global_cooldown = float(self.config.neurogenesis.get('cooldown', 60))
        return max(0.0, global_cooldown - (self.clock() - self._last_growth_at))

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
        if self._first_real_tick is None: self._first_real_tick = self.clock()
        if not isinstance(recent_actions, list): recent_actions = []
        ctx = self._build_context(trigger_type, brain_state, environment)
        ctx.recent_actions = recent_actions[-5:] if recent_actions else []
        elapsed = self.clock() - self._first_real_tick
        if elapsed < 1.5: return ctx
        is_sleeping = brain_state.get('is_sleeping', False)
        anxiety = brain_state.get('anxiety', 50)
        satisfaction = brain_state.get('satisfaction', 50)
        if is_sleeping and anxiety < 15 and satisfaction > 85: return ctx
        self.experience_buffer.add_experience(ctx)
        return ctx
    
    # ==================================================================
    # THE GROWTH DECISION
    #
    # A neuron appears because the network has a persistent functional
    # deficiency it cannot handle with the structure it has - never because a
    # particular event occurred. The diagnosis is CapabilityMonitor's; this is
    # the part that decides whether it is worth spending structure on, and it
    # is the only place in the project that makes that call.
    # ==================================================================
    @property
    def capability(self):
        return getattr(self.brain_widget, 'capability', None)

    def find_deficit(self, brain_state: Optional[Dict[str, float]] = None
                     ) -> Optional[Deficit]:
        """The most severe thing this brain currently cannot do.

        Prefers the monitor's evidence-backed diagnosis. Falls back to an
        acute reading of the live state so a squid in genuine, immediate
        trouble is not left waiting for a statistical window to fill.
        """
        monitor = self.capability
        if monitor is not None:
            actionable = monitor.actionable()
            if actionable:
                return actionable[0]
        return self._acute_deficit(brain_state)

    def _acute_deficit(self, brain_state: Optional[Dict[str, float]] = None
                       ) -> Optional[Deficit]:
        """A drive pinned at an extreme with nothing in the network correcting it.

        This is still a capability claim, not an event trigger: it fires on the
        *absence of corrective structure* while a drive is stuck, and it does
        not fire at all if the network already has synapses pulling the drive
        back.
        """
        from .capability import COMFORT_BANDS, MIN_CORRECTIVE_PUSH, SATURATION

        state = brain_state if brain_state is not None else getattr(
            self.brain_widget, 'state', {})
        weights = getattr(self.brain_widget, 'weights', {}) or {}

        worst: Optional[Deficit] = None
        for stat, (low, high) in COMFORT_BANDS.items():
            value = state.get(stat)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            value = float(value)
            if high < 100.0 and value >= min(95.0, high + 25.0):
                too_high = True
            elif low > 0.0 and value <= max(5.0, low - 25.0):
                too_high = False
            else:
                continue

            needed = -1.0 if too_high else 1.0
            corrective = 0.0
            saturated = 0
            for (src, dst), weight in weights.items():
                if dst != stat:
                    continue
                src_value = state.get(src)
                if isinstance(src_value, bool):
                    src_value = 100.0 if src_value else 0.0
                if not isinstance(src_value, (int, float)):
                    continue
                push = ((float(src_value) - 50.0) / 100.0) * float(weight)
                if push * needed > 0:
                    corrective += abs(push)
                    if abs(float(weight)) >= SATURATION:
                        saturated += 1
            # Acute means the drive is pinned at an extreme right now. The
            # only thing that excuses it is structure that is already pulling
            # it back hard; anything less is a capability gap, whatever events
            # produced it.
            if corrective >= MIN_CORRECTIVE_PUSH and saturated == 0:
                continue

            direction = 'down' if too_high else 'up'
            if corrective < 0.05:
                gap = "nothing in the network is pulling it back"
            elif saturated:
                gap = (f"the {saturated} synapse(s) pulling it back are already at "
                       f"full strength and it is still stuck")
            else:
                gap = (f"the network is only supplying {corrective:.2f} of "
                       f"corrective push, and it needs at least "
                       f"{MIN_CORRECTIVE_PUSH:.2f}")
            deficit = Deficit(
                kind='regulation', key=f"regulation:{stat}:{direction}:acute",
                summary=(f"{stat} is pinned at {value:.0f} and {gap}"),
                target=stat,
                sources=[stat],
                remedy=f"pull {stat} {direction} while it is stuck at this extreme",
                severity=1.0,
                evidence={'stat': stat, 'value': round(value, 1), 'acute': True,
                          'corrective_push': round(corrective, 3),
                          'saturated_synapses': saturated, 'direction': direction},
                suggested_type=('stress' if (too_high and stat in ('anxiety', 'hunger', 'sleepiness'))
                                or (not too_high and stat == 'cleanliness') else 'reward'),
                specialization=regulation_specialisation(stat, too_high))
            deficit.first_seen = deficit.last_seen = time.time()
            deficit.observations = 1
            deficit.initial_severity = 1.0
            if worst is None:
                worst = deficit
        return worst

    def should_create_neuron(self, ctx: Optional[ExperienceContext] = None,
                             deficit: Optional[Deficit] = None) -> bool:
        """Is there a deficit worth spending a neuron on, and may we spend one?

        `ctx` is kept for the existing callers (and for the birth record) but no
        longer decides anything: pattern recurrence describes experience, and
        experience is not by itself a reason to grow.
        """
        deficit = deficit or self.find_deficit(
            ctx.active_neurons if ctx is not None else None)
        if deficit is None:
            self.pending_deficit = None
            return False

        reason = self._growth_blocked(deficit)
        if reason:
            self.stood_down.append((time.time(), deficit.key, reason))
            self.pending_deficit = None
            return False

        self.pending_deficit = deficit
        return True

    def _growth_blocked(self, deficit: Deficit) -> Optional[str]:
        """Reasons a real deficit still does not get new structure."""
        now = self.clock()

        if self._first_real_tick is None:
            return "the brain has not started living yet"
        if now - self._first_real_tick < 5.0:
            return "the brain has only just started"

        max_neurons = self.config.neurogenesis.get('max_neurons', 32)
        current_count = len(self.brain_widget.neuron_positions) - len(
            getattr(self.brain_widget, 'excluded_neurons', []))
        if current_count >= max_neurons and deficit.severity < 1.0:
            return f"the brain is already at its {max_neurons}-neuron ceiling"

        cooldown = float(self.config.neurogenesis.get('cooldown', 60))
        remaining = self.get_global_cooldown_remaining()
        if remaining > 0:
            # A maximum-severity deficit is a genuine emergency and may grow
            # sooner - but not instantly. Without a floor, a squid whose drives
            # are all pinned grows a burst of neurons in a few seconds, which is
            # the event-driven behaviour this rewrite exists to remove.
            if deficit.severity >= 1.0:
                elapsed = cooldown - remaining
                emergency_floor = max(10.0, cooldown * 0.25)
                if elapsed < emergency_floor:
                    return (f"an emergency, but only {elapsed:.0f}s since the last "
                            f"neuron (needs {emergency_floor:.0f}s)")
            else:
                return f"only {remaining:.0f}s into the {cooldown:.0f}s growth cooldown"
        return None

    def growth_report(self) -> Dict[str, Any]:
        """What the engine is currently thinking about growing, and why not."""
        monitor = self.capability
        return {
            'pending': self.pending_deficit.to_dict() if self.pending_deficit else None,
            'deficits': monitor.report() if monitor is not None else {},
            'cooldown_remaining': round(self.get_global_cooldown_remaining(), 1),
            'stood_down': [{'at': at, 'deficit': key, 'because': why}
                           for at, key, why in list(self.stood_down)[-6:]],
            'grown': list(self.growth_log),
        }


    def update_neuron_activations(self, brain_state: Dict[str, float]) -> None:
            # 1. Normalize inputs
            for key in list(brain_state.keys()):
                if not isinstance(brain_state[key], (int, float)):
                    try: brain_state[key] = float(brain_state[key])
                    except (ValueError, TypeError): brain_state[key] = 50.0

            # 2. Activation is NOT recomputed here.
            #    BrainWidget.propagate_activations() is the project's single
            #    forward-propagation implementation and has already run this
            #    tick. This used to recompute every functional neuron with a
            #    second, subtly different transfer function and overwrite the
            #    propagated value, so a neurogenesis neuron and a Designer
            #    neuron behaved differently for no reason anyone could see.
            #    All that remains here is bookkeeping and the regulatory
            #    feedback below, which propagation deliberately does not do.
            now_ts = time.time()
            for name, func_neuron in self.functional_neurons.items():
                value = self.brain_widget.state.get(name)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if abs(float(value) - 50.0) > 15.0:
                        func_neuron.activation_count += 1
                        func_neuron.last_activated = now_ts

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
        prune_reason = (f"lowest utility of {len(candidates)} candidates "
                        f"(score {candidates[0][1]:.2f}) while the brain was at "
                        f"its size limit")
        for conn in list(self.brain_widget.weights.keys()):
            if neuron_to_prune in conn:
                self.brain_widget.remove_weight(
                    conn, mechanism='prune',
                    reason=f"{neuron_to_prune} was pruned - {prune_reason}")
        if neuron_to_prune in self.functional_neurons:
            fn = self.functional_neurons[neuron_to_prune]
            if fn.neuron_type == 'novelty': self.novelty_neuron_count -= 1
            del self.functional_neurons[neuron_to_prune]
        ledger = getattr(self.brain_widget, 'ledger', None)
        if ledger is not None:
            ledger.record_neuron_pruned(neuron_to_prune, reason=prune_reason)
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
        self._last_growth_at = 0.0
        print("🔄 Neurogenesis state reset")

# NeurogenesisTriggerSystem was removed in v4.0.
#
# It was a second, parallel detector of "significant experience" (novelty
# spikes, stress surges, reward rebounds) that nothing instantiated - the
# engine, the worker and the widget each had their own copy of the same
# thresholds. Its job is now done properly by capability.CapabilityMonitor,
# which asks what the network cannot do rather than what just happened, and
# there is exactly one of it.
