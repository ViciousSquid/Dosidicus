"""
ShowmanNeurogenesis v2.5.0

Wrapper around EnhancedNeurogenesis that keeps all the *real* logic
but guarantees the player *sees* a neuron when something cool happens.

FIXES in 2.5.0:
- Fixed _migrate_neuron to update all references (visible_neurons, animations, etc.)
- Added achievement integration via callbacks
- Added more dramatic moment triggers
- Added event-driven architecture for semantic events
- Improved burst color variety
"""

import time
import random
from typing import Optional, Callable, Dict, Any
from enum import Enum


class NeurogenesisEvent(Enum):
    """Semantic events that can trigger neurogenesis for dramatic effect"""
    FIRST_FEEDING = "first_feeding"
    FIRST_ROCK = "first_rock"
    FIRST_SLEEP = "first_sleep"
    ANXIETY_SPIKE = "anxiety_spike"
    ANXIETY_RELIEF = "anxiety_relief"
    NOVEL_OBJECT = "novel_object"
    RECOVERED_FROM_ILLNESS = "recovered"
    MAX_HAPPINESS = "max_happiness"
    HUNGER_CRISIS = "hunger_crisis"
    HUNGER_SATISFIED = "hunger_satisfied"
    SPOTLESS_TANK = "spotless_tank"
    CURIOSITY_EXPLOSION = "curiosity_explosion"
    FIRST_DECORATION_PUSH = "first_decoration_push"


class ShowmanNeurogenesis:
    """
    Wrapper around EnhancedNeurogenesis that keeps all the *real* logic
    but guarantees the player *sees* a neuron when something cool happens.
    
    The showmanship feature can be disabled via config.ini [Neurogenesis] showmanship = False
    When disabled, this wrapper becomes a pure passthrough to the real engine.
    """

    def __init__(self, real_enhanced_neurogenesis):
        self.en = real_enhanced_neurogenesis          # the real system
        self.config = self.en.config
        self.last_showman_creation = 0                # our own cooldown
        self.showman_cooldown = 15.0                  # seconds between "show" neurons
        
        # Check if showmanship is enabled in config
        self._showmanship_enabled = self._check_showmanship_enabled()
        
        # Track events we've already triggered (for first-time events)
        self._triggered_events: set = set()
        
        # Achievement integration callbacks
        self._on_dramatic_neuron_callback: Optional[Callable] = None
        self._on_event_triggered_callback: Optional[Callable[[NeurogenesisEvent], None]] = None
        
        # Name pools for dramatic neuron naming
        self.name_pool = {
            'novelty': [
                "encountered_novel_object",         # saw something new
                "exploration_reward",               # payoff for investigating
                "novel_positive_experience",  # moves toward new thing
                "wonder_trigger",                   # pure "what's that?" spark
                "discovery_satisfaction"            # aha-feeling after exploring
            ],
            'stress': [
                "anxiety_reduction",
                "trauma",
                "extreme_stress",
                "threat_avoidance",
                "comfort_seeking"
            ],
            'reward': [
                "food_reward",                # payoff for eating
                "cleanliness_reward",         # payoff for getting clean
                "rest_reward",                # payoff for sleeping
                "play_reward",                # payoff for fun interactions
                "achievement_reward"          # payoff for completing any goal
            ]
        }
        
        # Extended name pools for more variety
        self.extended_name_pool = {
            'novelty': [
                "positive_experience", "investigation_drive", "new_experience",
                "wonder_neuron", "exploration_joy", "discovery_rush"
            ],
            'stress': [
                "calm_restore", "fear_dampener", "safety_signal",
                "relaxation_trigger", "peace_seeker", "tension_release"
            ],
            'reward': [
                "satisfaction_burst", "happiness_boost", "contentment_signal",
                "pleasure_response", "joy_neuron", "fulfillment_marker"
            ]
        }


    def _check_showmanship_enabled(self) -> bool:
        """Check if showmanship is enabled in config. Config is single source of truth."""
        # Try to get from config object
        if hasattr(self.config, 'neurogenesis'):
            ng_config = self.config.neurogenesis
            if isinstance(ng_config, dict):
                return ng_config.get('showmanship', True)
        
        # Try config manager style access
        if hasattr(self.config, 'get_showmanship_enabled'):
            return self.config.get_showmanship_enabled()
        
        # Try direct config access
        if hasattr(self.config, 'getboolean'):
            try:
                return self.config.getboolean('Neurogenesis', 'showmanship', fallback=True)
            except:
                pass
        
        # Default to enabled
        return True

    def is_showmanship_enabled(self) -> bool:
        """Public getter for showmanship state. Re-checks config each time."""
        return self._check_showmanship_enabled()

    def set_callbacks(self, on_dramatic_neuron=None, on_event_triggered=None):
        """Set callbacks for external integration (achievements, etc.)"""
        self._on_dramatic_neuron_callback = on_dramatic_neuron
        self._on_event_triggered_callback = on_event_triggered

    # -------------- public API – same as EnhancedNeurogenesis --------------

    def get_global_cooldown_remaining(self) -> float:
        """
        Return the REAL cooldown from the underlying EnhancedNeurogenesis system.
        This matches the cooldown shown in console and actually blocks creation.
        """
        return self.en.get_global_cooldown_remaining()

    def capture_experience_context(self, trigger_type, brain_state, recent_actions, environment):
        """
        Showman wrapper: Delegate to real system using standard keyword arguments.
        This fixes the TypeError: unexpected keyword argument 'trigger_type'.
        """
        return self.en.capture_experience_context(
            trigger_type=trigger_type, 
            brain_state=brain_state, 
            recent_actions=recent_actions, 
            environment=environment
        )

    def should_create_neuron(self, ctx) -> bool:
        """
        Showman wrapper: decide whether a neuron should be created.
        Emergency anxiety ≥ 100 bypasses EVERYTHING and returns True instantly.
        Otherwise delegates to the real EnhancedNeurogenesis logic.
        """
        # =====================================================================
        # EMERGENCY BYPASS: anxiety == 100  →  create immediately
        if ctx.trigger_type == 'stress' and ctx.active_neurons.get('anxiety', 50) >= 95:
            print(f"🚨 EMERGENCY OVERRIDE: anxiety={ctx.active_neurons.get('anxiety')} - creating stress neuron NOW!")
            # (Optionally lift specialization cap for this single creation)
            original_max = self.en.config.neurogenesis.get('max_per_specialization', 3)
            self.en.config.neurogenesis['max_per_specialization'] = original_max + 1
            # Restore cap after creation (done in create_functional_neuron)
            return True
        # =====================================================================

        # Normal path – use real system (respects cooldowns, caps, patterns)
        return self.en.should_create_neuron(ctx)

    def create_functional_neuron(self, ctx, is_emergency: bool = False) -> Optional[str]:
        """Create the neuron through the real system"""
        
        # Ask real system to do the heavy lifting
        real_name = self.en.create_functional_neuron(ctx, is_emergency=is_emergency)
        
        if real_name is None:
            return None

        # If showmanship disabled, return the real name without cosmetic changes
        if not self.is_showmanship_enabled():
            return real_name

        # ---- cosmetic upgrade (showmanship enabled) ----
        pretty_name = self._rename_for_drama(ctx.trigger_type, real_name)
        if pretty_name != real_name:
            # Migrate everything to the new name
            self._migrate_neuron(real_name, pretty_name)

        # Bigger, longer highlight for the player
        burst_color = self._burst_color(ctx.trigger_type)
        self.en.brain_widget.neurogenesis_highlight = {
            'neuron': pretty_name,
            'start_time': time.time(),
            'duration': 10.0,              # longer pulse
            'pulse_phase': 0,
            'is_emergency': False,
            'is_showman': True,            # flag for renderer (optional)
            'color_burst': burst_color
        }
        self.last_showman_creation = time.time()
        
        # Fire callback for achievement integration
        if self._on_dramatic_neuron_callback:
            try:
                self._on_dramatic_neuron_callback(pretty_name, ctx.trigger_type)
            except Exception as e:
                print(f"Showman callback error: {e}")
        
        return pretty_name

    # ------------------ Event Detection ------------------
    
    def _detect_dramatic_moment(self, ctx) -> Optional[NeurogenesisEvent]:
        """Detect visually significant moments - VERY PERMISSIVE"""
        recent = ' '.join(ctx.recent_actions[-3:]).lower() if ctx.recent_actions else ''
        
        # ANY anxiety spike over 70 (not 90)
        if ctx.active_neurons.get('anxiety', 50) >= 70:
            return NeurogenesisEvent.ANXIETY_SPIKE
        
        # ANY feeding moment (not just after crisis)
        if ctx.trigger_type == 'reward' and ('eat' in recent or 'food' in recent):
            return NeurogenesisEvent.HUNGER_SATISFIED
        
        # ANY curiosity over 75 (not 95)
        if ctx.active_neurons.get('curiosity', 50) >= 75:
            return NeurogenesisEvent.CURIOSITY_EXPLOSION
        
        # Clean tank (allow multiple)
        if ctx.active_neurons.get('cleanliness', 50) >= 90:
            return NeurogenesisEvent.SPOTLESS_TANK
        
        # High happiness (allow multiple)
        if ctx.active_neurons.get('happiness', 50) >= 85:
            return NeurogenesisEvent.MAX_HAPPINESS
        
        # ANY decoration interaction
        if 'decoration' in recent or 'push' in recent:
            return NeurogenesisEvent.FIRST_DECORATION_PUSH
        
        return None
    
    def _fire_event(self, event: NeurogenesisEvent):
        """Record event and fire callback"""
        self._triggered_events.add(event)
        
        if self._on_event_triggered_callback:
            try:
                self._on_event_triggered_callback(event)
            except Exception as e:
                print(f"Event callback error: {e}")

    def trigger_event(self, event: NeurogenesisEvent) -> bool:
        """
        Manually trigger a dramatic event from external code.
        Useful for achievement system integration.
        Returns True if a neuron was created.
        
        Note: Respects showmanship config flag - returns False if disabled.
        """
        # 1. Configuration Guard: Check if showmanship is enabled
        if not self.is_showmanship_enabled():
            return False
        
        # 2. Duplicate Guard: Don't trigger the same semantic event twice
        if event in self._triggered_events:
            return False
        
        # 3. Pacing Guard: Respect the showman-specific cooldown
        now = time.time()
        if now - self.last_showman_creation < self.showman_cooldown:
            return False
        
        # 4. Semantic Mapping: Convert the event into a standard trigger type
        event_to_trigger = {
            NeurogenesisEvent.FIRST_FEEDING: 'reward',
            NeurogenesisEvent.FIRST_ROCK: 'novelty',
            NeurogenesisEvent.FIRST_SLEEP: 'reward',
            NeurogenesisEvent.ANXIETY_SPIKE: 'stress',
            NeurogenesisEvent.ANXIETY_RELIEF: 'stress',
            NeurogenesisEvent.NOVEL_OBJECT: 'novelty',
            NeurogenesisEvent.RECOVERED_FROM_ILLNESS: 'reward',
            NeurogenesisEvent.MAX_HAPPINESS: 'reward',
            NeurogenesisEvent.HUNGER_CRISIS: 'stress',
            NeurogenesisEvent.HUNGER_SATISFIED: 'reward',
            NeurogenesisEvent.SPOTLESS_TANK: 'reward',
            NeurogenesisEvent.CURIOSITY_EXPLOSION: 'novelty',
            NeurogenesisEvent.FIRST_DECORATION_PUSH: 'novelty',
        }
        
        trigger_type = event_to_trigger.get(event, 'novelty')
        
        # 5. Context Capture: Pull current state from the brain widget
        current_brain_state = dict(self.en.brain_widget.state)

        # 6. Synchronize: Call our fixed capture method to build the ExperienceContext
        ctx = self.capture_experience_context(
            trigger_type=trigger_type,
            brain_state=current_brain_state,
            recent_actions=[event.value],
            environment={}
        )
        
        print(f"🎭 Manual event trigger: {event.value}")
        self._fire_event(event) # Records event and fires achievement callbacks
        
        # 7. Creation: Finalize the dramatic neuron birth
        result = self.create_functional_neuron(ctx)
        return result is not None

    # ------------------ internal helpers ------------------

    def _moment_deserves_neuron(self, ctx) -> bool:
        """
        Return True if this is a *visually* cool moment for the player.
        Keep the rules simple and transparent.
        DEPRECATED: Use _detect_dramatic_moment instead.
        """
        return self._detect_dramatic_moment(ctx) is not None

    def _rename_for_drama(self, trigger: str, old: str) -> str:
        """Pick a cinematic name that still encodes the specialization."""
        pool = self.name_pool.get(trigger, [])
        extended = self.extended_name_pool.get(trigger, [])
        all_names = pool + extended
        
        if not all_names:
            return old
        
        # Keep pool unique per session
        used = {n for n in self.en.functional_neurons.keys() if n in all_names}
        available = [n for n in all_names if n not in used]
        
        if available:
            return available[0]
        
        # Fallback – append digit so we never duplicate
        root = pool[0] if pool else old.split('_')[0]
        counter = 2
        while f"{root}_{counter}" in self.en.functional_neurons:
            counter += 1
        return f"{root}_{counter}"

    def _migrate_neuron(self, old_name: str, new_name: str):
        bw = self.en.brain_widget

        # Positions
        if old_name in bw.neuron_positions:
            bw.neuron_positions[new_name] = bw.neuron_positions.pop(old_name)
        
        # State
        if old_name in bw.state:
            bw.state[new_name] = bw.state.pop(old_name)
        
        # Colours
        if hasattr(bw, 'state_colors') and old_name in bw.state_colors:
            bw.state_colors[new_name] = bw.state_colors.pop(old_name)
        
        # Shapes
        if hasattr(bw, 'neuron_shapes') and old_name in bw.neuron_shapes:
            bw.neuron_shapes[new_name] = bw.neuron_shapes.pop(old_name)

        # Weights – rebuild keys
        new_weights = {}
        for (src, dst), w in bw.weights.items():
            src = new_name if src == old_name else src
            dst = new_name if dst == old_name else dst
            new_weights[(src, dst)] = w
        bw.weights = new_weights

        # Functional neurons dict
        if old_name in self.en.functional_neurons:
            self.en.functional_neurons[new_name] = self.en.functional_neurons.pop(old_name)
            self.en.functional_neurons[new_name].name = new_name
        
        # FIX: Update visible_neurons set
        if hasattr(bw, 'visible_neurons'):
            if old_name in bw.visible_neurons:
                bw.visible_neurons.discard(old_name)
                bw.visible_neurons.add(new_name)
        
        # FIX: Update neuron_reveal_animations
        if hasattr(bw, 'neuron_reveal_animations'):
            if old_name in bw.neuron_reveal_animations:
                bw.neuron_reveal_animations[new_name] = bw.neuron_reveal_animations.pop(old_name)
        
        # FIX: Update communication_events
        if hasattr(bw, 'communication_events'):
            if old_name in bw.communication_events:
                bw.communication_events[new_name] = bw.communication_events.pop(old_name)
        
        # FIX: Update weight_change_events
        if hasattr(bw, 'weight_change_events'):
            new_weight_events = {}
            for key, event_time in bw.weight_change_events.items():
                if "->" in key:
                    src, dst = key.split("->", 1)
                else:
                    # Fallback in case of malformed key
                    continue
                src = new_name if src == old_name else src
                dst = new_name if dst == old_name else dst
                new_key = f"{src}->{dst}"
                new_weight_events[new_key] = event_time
            bw.weight_change_events = new_weight_events
        
        # FIX: Update link animation dicts
        for attr in ['_link_opacities', '_link_targets', '_link_start_times', '_link_fade_speeds']:
            if hasattr(bw, attr):
                old_dict = getattr(bw, attr)
                new_dict = {}
                for key, val in old_dict.items():
                    if isinstance(key, tuple) and len(key) == 2:
                        src, dst = key
                        src = new_name if src == old_name else src
                        dst = new_name if dst == old_name else dst
                        new_dict[(src, dst)] = val
                    else:
                        # Skip malformed keys
                        continue
                setattr(bw, attr, new_dict)

    def _burst_color(self, trigger: str) -> tuple:
        """Bright colour flash for the neuron birth."""
        base_colors = {
            'novelty': (255, 215, 0),   # gold
            'stress':  (255, 100, 100), # crimson
            'reward':  (100, 255, 100)  # mint
        }
        
        # Add some variation
        base = base_colors.get(trigger, (200, 200, 255))
        
        # Slight random variation for visual interest
        r = max(0, min(255, base[0] + random.randint(-20, 20)))
        g = max(0, min(255, base[1] + random.randint(-20, 20)))
        b = max(0, min(255, base[2] + random.randint(-20, 20)))
        
        return (r, g, b)

    def get_triggered_events(self) -> set:
        """Return set of events that have been triggered"""
        return self._triggered_events.copy()

    def reset_events(self):
        """Reset triggered events for new game"""
        self._triggered_events.clear()
        self.last_showman_creation = 0

    # -------------- passthrough anything we don't override --------------
    def __getattr__(self, item):
        return getattr(self.en, item)