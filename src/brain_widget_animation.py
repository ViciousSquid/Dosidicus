"""The brain view's animations: styles, pulses and glows along connections,
weight changes, and a new neuron being revealed.

Presentation only - what is animated has already happened in the brain.
"""
import time
import math
import random
from PyQt5 import QtCore
from .localisation import Localisation
from .animation_styles import (
    get_animation_style, get_available_styles, get_style_info
)

# Performance tracking for Task Manager
try:
    from .task_manager import perf_tracker
    _PERF_TRACKING_AVAILABLE = True
except ImportError:
    _PERF_TRACKING_AVAILABLE = False


class BrainAnimationMixin:
    """Part of BrainWidget (see brain_widget.py); not used on its own."""

    def _has_active_animations(self) -> bool:
        """Check if there are active animations requiring re-render"""
        current_time = time.time()
        
        # Check communication events (connection animations)
        for neuron, event_time in self.communication_events.items():
            if current_time - event_time < 0.5:  # 500ms animation
                return True
        
        # Check link fade animations
        for key, opacity in getattr(self, '_link_opacities', {}).items():
            target = getattr(self, '_link_targets', {}).get(key, opacity)
            if abs(opacity - target) > 0.01:
                return True
        
        return False

    # =========================================================================
    # ANIMATION STYLE METHODS
    # =========================================================================
    
    def _build_animation_palette(self):
        """
        Load visual settings from the current animation style.
        Called during init and when style changes.
        """
        style = self._animation_style
        
        # Connection line settings
        self.anim_line_base_width = style.line_base_width
        self.anim_line_col_pos = style.line_colour_positive
        self.anim_line_col_neg = style.line_colour_negative
        self.anim_line_alpha = style.line_alpha
        self.anim_use_thick_lines = style.use_thick_lines
        
        # [NEW] Weight-based thickness settings (MISSING IN PREVIOUS VERSION)
        self.weight_thickness_enabled = getattr(style, 'weight_thickness_enabled', False)
        self.weight_thickness_min = getattr(style, 'weight_thickness_min', 1.0)
        self.weight_thickness_max = getattr(style, 'weight_thickness_max', 2.0)
        self.weight_thickness_power = getattr(style, 'weight_thickness_power', 1.0)
        
        # Stress-anxiety connection
        self.anim_stress_width = style.stress_anxiety_width
        self.anim_stress_colour = style.stress_anxiety_colour
        self.anim_stress_dashed = style.stress_anxiety_dashed
        
        # Pulse/travelling dot settings
        self.anim_pulse_enabled = style.pulse_enabled
        self.anim_pulse_colour = style.pulse_colour
        self.anim_pulse_alpha = style.pulse_alpha
        self.anim_pulse_duration = style.pulse_duration
        self.anim_pulse_speed = style.pulse_speed
        self.anim_pulse_diameter = style.pulse_diameter
        
        # Glow effect settings
        self.anim_glow_enabled = style.glow_enabled
        self.anim_glow_colour = style.glow_colour
        self.anim_glow_alpha = style.glow_alpha
        self.anim_glow_fade_threshold = style.glow_fade_threshold
        
        # Hover effect settings
        self.anim_hover_enabled = style.hover_enabled
        self.anim_hover_scale = style.hover_scale
        self.anim_hover_duration = style.hover_animation_duration
        
        # Activity highlight settings
        self.anim_activity_enabled = style.activity_highlight_enabled
        self.anim_activity_colour = style.activity_highlight_colour
        self.anim_activity_alpha = style.activity_highlight_alpha
        self.anim_activity_pulse_speed = style.activity_pulse_speed
        
        # Neurogenesis highlight settings
        self.anim_neurogenesis_colour = style.neurogenesis_highlight_colour
        self.anim_neurogenesis_alpha = style.neurogenesis_highlight_alpha
        self.anim_neurogenesis_duration = style.neurogenesis_highlight_duration
        
        # Background color
        self.anim_background_colour = style.background_colour
        
        # ===== VIBRANT STYLE: AMBIENT PULSING =====
        self.anim_ambient_pulse_enabled = style.ambient_pulse_enabled
        self.anim_ambient_pulse_width_range = style.ambient_pulse_width_range
        self.anim_ambient_pulse_alpha_range = style.ambient_pulse_alpha_range
        self.anim_ambient_pulse_freq_range = style.ambient_pulse_freq_range
        self.anim_ambient_pulse_phase_drift = style.ambient_pulse_phase_drift
        
        # ===== SUBTLE STYLE: COMMUNICATION GLOWS =====
        self.anim_comm_glow_enabled = style.comm_glow_enabled
        self.anim_comm_glow_colour = style.comm_glow_colour
        self.anim_comm_glow_alpha = style.comm_glow_alpha
        self.anim_comm_glow_size = style.comm_glow_size
        self.anim_comm_glow_tail_length = style.comm_glow_tail_length
        self.anim_comm_glow_speed_range = style.comm_glow_speed_range
        self.anim_comm_glow_fade_in = style.comm_glow_fade_in
        self.anim_comm_glow_fade_out = style.comm_glow_fade_out
        self.anim_comm_glow_spawn_on_activity = style.comm_glow_spawn_on_activity
        self.anim_comm_glow_spawn_on_weight_change = style.comm_glow_spawn_on_weight_change
        self.anim_comm_glow_max_per_connection = style.comm_glow_max_per_connection

        # ===== SUBTLE STYLE: SCROLLING DOTS =====
        # [NEW] Ensure scrolling settings are mapped
        self.anim_scroll_enabled = getattr(style, 'scroll_enabled', False)
        self.anim_scroll_dot_count = getattr(style, 'scroll_dot_count', 3)
        self.anim_scroll_dot_size = getattr(style, 'scroll_dot_size', 6.0)
        self.anim_scroll_dot_colour = getattr(style, 'scroll_dot_colour', (255, 255, 255))
        self.anim_scroll_dot_alpha = getattr(style, 'scroll_dot_alpha', 200)
        self.anim_scroll_speed_range = getattr(style, 'scroll_speed_range', (1.5, 4.0))
        
        # ===== NEURAL STYLE: ACTIVATION PULSES =====
        self.anim_neural_pulse_enabled = style.neural_pulse_enabled
        self.anim_neural_pulse_duration = style.neural_pulse_duration
        self.anim_neural_pulse_width = style.neural_pulse_width
        self.anim_neural_pulse_colour_pos = style.neural_pulse_colour_positive
        self.anim_neural_pulse_colour_neg = style.neural_pulse_colour_negative
        self.anim_neural_weight_thickness = style.neural_weight_thickness
        self.anim_neural_weight_thickness_mult = style.neural_weight_thickness_mult
        self.anim_neural_base_colour_pos = style.neural_base_colour_positive
        self.anim_neural_base_colour_neg = style.neural_base_colour_negative
        self.anim_neural_base_alpha = style.neural_base_alpha
        
        # Initialize style-specific animation state
        self._init_style_animation_state()
        
        print(f"🎨 Animation palette built for style: {style.display_name}")

    def get_animation_style(self) -> str:
        """Get the current animation style name."""
        return self._animation_style_name

    def get_animation_style_info(self) -> tuple:
        """Get (name, display_name, description) for current style."""
        style = self._animation_style
        return (style.name, style.display_name, style.description)

    def set_animation_style(self, style_name: str) -> bool:
        """
        Switch to a different animation style at runtime.
        
        Args:
            style_name: One of 'classic', 'vibrant', or 'subtle'
            
        Returns:
            True if style was changed, False if style name is invalid
        """
        try:
            new_style = get_animation_style(style_name)
        except KeyError:
            print(f"⚠️ Unknown animation style: {style_name}. "
                  f"Available: {get_available_styles()}")
            return False
        
        if style_name == self._animation_style_name:
            return True  # Already using this style
        
        old_style = self._animation_style_name
        self._animation_style_name = style_name
        self._animation_style = new_style
        self._build_animation_palette()
        
        # Trigger repaint with new style
        self.update()
        
        # Emit signal for any listeners
        self.animationStyleChanged.emit(style_name)
        
        print(f"🎨 Animation style changed: {old_style} → {style_name}")
        return True

    @staticmethod
    def get_available_animation_styles() -> list:
        """Get list of available animation style names."""
        return get_available_styles()

    @staticmethod
    def get_animation_styles_info() -> list:
        """Get list of (name, display_name, description) for all styles."""
        return get_style_info()

    def _init_style_animation_state(self):
        """
        Initialize state tracking for style-specific animations.
        Called when style changes or on startup.
        """
        # ===== VIBRANT: Ambient pulse state =====
        # Each connection gets its own phase and frequency for organic pulsing
        if not hasattr(self, '_ambient_pulse_state'):
            self._ambient_pulse_state = {}  # key: (src, dst) -> {phase, freq, phase_drift_dir}
        
        # ===== SUBTLE: Communication glow state =====
        # Each connection has a list of traveling glow packets
        if not hasattr(self, '_comm_glow_packets'):
            self._comm_glow_packets = {}  # key: (src, dst) -> [{progress, speed, direction}]
        
        # Track last spawn times to prevent glow spam
        if not hasattr(self, '_comm_glow_last_spawn'):
            self._comm_glow_last_spawn = {}  # key: (src, dst) -> timestamp
        
        # ===== NEURAL: Activation pulse state =====
        # Tracks traveling activation pulses for the neural style
        if not hasattr(self, '_neural_pulses'):
            self._neural_pulses = {}  # key: (src, dst) -> [{start_time, color}]

    def _get_or_create_ambient_pulse(self, conn_key):
        """
        Get or create ambient pulse state for a connection.
        Each connection pulses at its own unique rate.
        """
        if conn_key not in self._ambient_pulse_state:
            # Assign random frequency and starting phase
            freq_min, freq_max = self.anim_ambient_pulse_freq_range
            self._ambient_pulse_state[conn_key] = {
                'phase': random.uniform(0, 2 * math.pi),  # Random starting phase
                'freq': random.uniform(freq_min, freq_max),  # Random frequency
                'phase_drift_dir': random.choice([-1, 1]),  # Drift direction
                'drift_timer': random.uniform(0, 5)  # When to change drift
            }
        return self._ambient_pulse_state[conn_key]

    def _update_ambient_pulses(self, dt):
        """
        Update all ambient pulse phases. Called from update_animations().
        Each connection's phase advances at its own rate with subtle drift.
        """
        if not self.anim_ambient_pulse_enabled:
            return
        
        for conn_key, state in self._ambient_pulse_state.items():
            # Advance phase based on frequency
            state['phase'] += 2 * math.pi * state['freq'] * dt
            
            # Keep phase in reasonable range
            if state['phase'] > 100 * math.pi:
                state['phase'] -= 100 * math.pi
            
            # Occasionally change drift direction for organic feel
            state['drift_timer'] -= dt
            if state['drift_timer'] <= 0:
                state['phase_drift_dir'] = random.choice([-1, 1])
                state['drift_timer'] = random.uniform(3, 8)
            
            # Apply subtle phase drift
            state['phase'] += state['phase_drift_dir'] * self.anim_ambient_pulse_phase_drift * dt

    def _spawn_comm_glow(self, source, target):
        """
        Spawn a new communication glow packet traveling from source to target.
        """
        if not self.anim_comm_glow_enabled:
            return
        
        conn_key = (source, target)
        current_time = time.time()
        
        # Check spawn cooldown (min 0.1 seconds between spawns on same connection)
        last_spawn = self._comm_glow_last_spawn.get(conn_key, 0)
        if current_time - last_spawn < 0.1:
            return
        
        # Initialize packet list if needed
        if conn_key not in self._comm_glow_packets:
            self._comm_glow_packets[conn_key] = []
        
        # Check max packets per connection
        if len(self._comm_glow_packets[conn_key]) >= self.anim_comm_glow_max_per_connection:
            return
        
        # Create new packet with random speed (for chaotic, organic movement)
        speed_min, speed_max = self.anim_comm_glow_speed_range
        duration = random.uniform(speed_min, speed_max)
        
        self._comm_glow_packets[conn_key].append({
            'progress': 0.0,  # 0 = at source, 1 = at target
            'speed': 1.0 / duration,  # Progress per second
            'start_time': current_time
        })
        
        self._comm_glow_last_spawn[conn_key] = current_time

    def _update_comm_glows(self, dt):
        """
        Update all communication glow packets. Called from update_animations().
        """
        if not self.anim_comm_glow_enabled:
            return
        
        # Update each connection's glow packets
        for conn_key in list(self._comm_glow_packets.keys()):
            packets = self._comm_glow_packets[conn_key]
            
            # Update each packet
            surviving_packets = []
            for packet in packets:
                packet['progress'] += packet['speed'] * dt
                
                # Keep packet if not yet complete
                if packet['progress'] < 1.0:
                    surviving_packets.append(packet)
            
            # Update packet list (remove completed ones)
            if surviving_packets:
                self._comm_glow_packets[conn_key] = surviving_packets
            else:
                del self._comm_glow_packets[conn_key]

    def _spawn_activity_glows(self, current_time):
        """
        Spawn communication glows based on neuron activity.
        Called from update_animations() when in subtle mode.
        """
        if not self.anim_comm_glow_spawn_on_activity:
            return
        
        # Check which neurons are currently active (significant deviation from baseline)
        active_neurons = []
        for neuron, value in self.state.items():
            if isinstance(value, (int, float)) and neuron in self.neuron_positions:
                if neuron not in self.excluded_neurons:
                    # Consider active if significantly away from baseline (50)
                    if abs(value - 50) > 25:
                        active_neurons.append(neuron)
        
        # For active neurons, randomly spawn glows on their connections
        for neuron in active_neurons:
            # Random chance to spawn (don't spam every frame)
            if random.random() > 0.02:  # ~2% chance per frame per active neuron
                continue
            
            # Find connections involving this neuron
            for (src, dst), weight in self.weights.items():
                if src == neuron or dst == neuron:
                    # Determine glow direction based on weight sign and which end is active
                    if src == neuron:
                        self._spawn_comm_glow(src, dst)
                    else:
                        self._spawn_comm_glow(dst, src)

    def _spawn_neural_pulse(self, source, target, color=None):
        """
        Spawn a neural activation pulse traveling from source to target.
        Used by the Neural style.
        """
        if not self.anim_neural_pulse_enabled:
            return
        
        conn_key = (source, target)
        current_time = time.time()
        
        # Initialize pulse list if needed
        if conn_key not in self._neural_pulses:
            self._neural_pulses[conn_key] = []
        
        # Limit concurrent pulses per connection
        if len(self._neural_pulses[conn_key]) >= 3:
            return
        
        # Determine pulse color based on weight if not specified
        if color is None:
            weight = self.weights.get(conn_key, self.weights.get((target, source), 0))
            if weight >= 0:
                color = self.anim_neural_pulse_colour_pos
            else:
                color = self.anim_neural_pulse_colour_neg
        
        self._neural_pulses[conn_key].append({
            'start_time': current_time,
            'color': color
        })

    def _update_neural_pulses(self, current_time):
        """
        Update neural activation pulses, removing completed ones.
        """
        if not self.anim_neural_pulse_enabled:
            return
        
        duration = self.anim_neural_pulse_duration
        
        for conn_key in list(self._neural_pulses.keys()):
            pulses = self._neural_pulses[conn_key]
            
            # Filter out completed pulses
            surviving = [p for p in pulses if (current_time - p['start_time']) < duration]
            
            if surviving:
                self._neural_pulses[conn_key] = surviving
            else:
                del self._neural_pulses[conn_key]

    def _spawn_neural_pulses_from_activity(self, current_time):
        """
        Spawn neural pulses based on neuron activity and weight changes.
        """
        if not self.anim_neural_pulse_enabled:
            return
        
        # Spawn pulses from weight change events
        if hasattr(self, 'weight_change_events'):
            for neuron, event_time in list(self.weight_change_events.items()):
                # Only process recent events (within last 0.1 seconds)
                if current_time - event_time > 0.1:
                    continue
                
                # Find connections from this neuron
                for (src, dst), weight in self.weights.items():
                    if src == neuron:
                        self._spawn_neural_pulse(src, dst)

    def is_neuron_revealed(self, name):
        """Return True if the neuron has finished its reveal animation.
        Only checks revealed tracking during tutorial mode."""
        # In normal gameplay (not tutorial), all neurons are considered revealed
        if not self.is_tutorial_mode:
            return True
            
        # During tutorial, check if neuron has completed its animation
        if name not in self.neuron_reveal_animations:
            return name in self.visible_neurons  # never animated = already visible
        from .brain_constants import NEURON_REVEAL_DURATION
        anim = self.neuron_reveal_animations[name]
        elapsed = time.time() - anim['start_time']
        return elapsed >= NEURON_REVEAL_DURATION

    def _advance_link_fades(self):
        """Called every 16 ms while any line is still moving."""
        dt = 0.016
        still_animating = False
        now = time.time()

        for key, target in list(self._link_targets.items()):
            # Check if this link's delay has passed
            start_time = self._link_start_times.get(key, 0)
            if now < start_time:
                still_animating = True
                continue
                
            current = self._link_opacities.get(key, 0.0)
            # Use per-link speed for individual animation timing
            speed = self._link_fade_speeds.get(key, 3.0)
            step = speed * dt
            
            if abs(target - current) <= step:        # arrived
                self._link_opacities[key] = target
                del self._link_targets[key]          # stop tracking this one
                if key in self._link_start_times:
                    del self._link_start_times[key]
                if key in self._link_fade_speeds:
                    del self._link_fade_speeds[key]
            else:                                    # move one step
                self._link_opacities[key] = current + step * (1 if target > current else -1)
                still_animating = True

        self.update()                                # repaint with new alphas

        if not still_animating:                      # all lines finished
            self._link_fade_timer.stop()

    def update_animations(self):
        """Update all animation states with smarter dirty-checking."""
        
        current_lang = Localisation.instance().current_language
        if getattr(self, '_last_lang', None) != current_lang:
            self._last_lang = current_lang
            self.mark_render_dirty()
            self.update()

        if self.is_paused:
            return

        current_time = time.time()
        
        # Performance tracking (keep if using task manager)
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _anim_start = time.perf_counter()
            perf_tracker.increment("animation_frames")
        
        # Frame rate limiting - skip if called too soon
        if hasattr(self, '_last_animation_update'):
            elapsed = current_time - self._last_animation_update
            if elapsed < 0.04:  # 25fps cap (40ms) - reduced from 30fps
                return
        self._last_animation_update = current_time
        
        # Calculate dt
        if not hasattr(self, '_last_animation_time'):
            self._last_animation_time = current_time
        dt = min(current_time - self._last_animation_time, 0.1)
        self._last_animation_time = current_time

        # SMARTER dirty tracking
        needs_repaint = False

        # 1. Neurogenesis pulse - only repaint if active
        if self.neurogenesis_highlight['neuron']:
            elapsed = current_time - self.neurogenesis_highlight['start_time']
            if elapsed < self.neurogenesis_highlight['duration']:
                self.neurogenesis_highlight['pulse_phase'] = elapsed * 15
                needs_repaint = True
            else:
                self.neurogenesis_highlight['neuron'] = None
                needs_repaint = True  # One final repaint to clear

        # 2. Neuron reveal animations - only if we have any
        if self.neuron_reveal_animations:
            from .brain_constants import (NEURON_REVEAL_DURATION,
                                          reveal_progress)

            completed_reveals = []
            for neuron_name, anim_data in self.neuron_reveal_animations.items():
                elapsed = current_time - anim_data['start_time']
                if elapsed >= NEURON_REVEAL_DURATION:
                    anim_data['progress'] = 1.0
                    completed_reveals.append(neuron_name)
                else:
                    # Linear 0..1. The SIZE curve (which overshoots past 1) is
                    # applied by the renderer from the same elapsed time, so
                    # the two cannot disagree about where the reveal is up to.
                    anim_data['progress'] = reveal_progress(elapsed)

            for neuron_name in completed_reveals:
                del self.neuron_reveal_animations[neuron_name]

            needs_repaint = True
            # The reveal is drawn INSIDE the cached frame, so a repaint alone
            # re-blits the same picture. Without this the neurons' sizes only
            # ever changed on a frame something else happened to dirty, which
            # is why the expand animation reveal_neuron() has always claimed
            # to do was never visible.
            self.mark_render_dirty()

            if not self.neuron_reveal_animations:
                self._set_render_fps(self.IDLE_RENDER_FPS)

            # Enable links after last reveal
            if (len(self.visible_neurons) == len(self.original_neurons) and
                not self.neuron_reveal_animations and not self.show_links):
                self._enable_links_after_reveal()

        # 3. Weight animations - check if any are active
        if self.weight_animations:
            old_count = len(self.weight_animations)
            self.weight_animations = [
                anim for anim in self.weight_animations
                if current_time - anim['start_time'] < anim['duration']
            ]
            if self.weight_animations or old_count > 0:
                needs_repaint = True
        
        # 4. VIBRANT: Ambient pulses - only update if enabled AND we have connections
        if self.anim_ambient_pulse_enabled and self._ambient_pulse_state:
            self._update_ambient_pulses(dt)
            needs_repaint = True
        
        # 5. SUBTLE: Communication glows - only if packets exist
        if self.anim_comm_glow_enabled:
            had_packets = bool(self._comm_glow_packets)
            self._update_comm_glows(dt)
            self._spawn_activity_glows(current_time)
            # Only repaint if we had or now have packets
            if had_packets or self._comm_glow_packets:
                needs_repaint = True
        
        # 6. NEURAL: Activation pulses - only if pulses exist  
        if self.anim_neural_pulse_enabled:
            had_pulses = bool(self._neural_pulses)
            self._update_neural_pulses(current_time)
            self._spawn_neural_pulses_from_activity(current_time)
            if had_pulses or self._neural_pulses:
                needs_repaint = True
        
        # Only trigger repaint when needed
        if needs_repaint:
            self.update()
        
        # Performance tracking end
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _anim_elapsed = (time.perf_counter() - _anim_start) * 1000
            perf_tracker.record("update_animations", _anim_elapsed)

    def reveal_neuron(self, neuron_name, delay: float = None):
        """Reveal a neuron with an expand animation - forces links OFF during reveal.

        `delay` is seconds to wait before the expand starts. The caller sets
        the pace because the caller is the one synchronising with something -
        the hatching splash's frames, or a fixed run for a loaded game. Left
        unset it falls back to staggering by how many neurons are already up.
        """
        import time

        if neuron_name not in self.innate_neurons:
            return
        if neuron_name in self.visible_neurons:
            return
        if neuron_name not in self.neuron_positions:
            print(f"❌ ERROR: Neuron {neuron_name} has no position defined!")
            return

        # First reveal → force links OFF
        if not self.visible_neurons:
            self.show_links = False
            if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
                nt = self.parent().network_tab
                nt.checkbox_links.setChecked(False)
                nt.checkbox_links.setEnabled(False)

        if delay is None:
            delay = len(self.visible_neurons) * 0.4

        self.visible_neurons.add(neuron_name)

        # Track this neuron as revealed for count display (tutorial only)
        if self.is_tutorial_mode:
            self.revealed_neurons.add(neuron_name)
            self._reveal_connections_for_neuron(neuron_name)

        # Trigger immediate metrics update
        self._update_network_metrics()

        self.neuron_reveal_animations[neuron_name] = {
            'start_time': time.time() + delay,
            'progress': 0.0
        }

        self._set_render_fps(self.REVEAL_RENDER_FPS)
        self.mark_render_dirty()

    def grow_into_place(self, neuron_name):
        """A neuron the squid has just grown swells into place.

        The same expand the hatching neurons make (the renderer draws any
        neuron listed in neuron_reveal_animations at reveal_scale of its full
        size), started now. A grown neuron used simply to be there on the
        next frame; growth is the most important thing that happens in this
        window, and it should look like something happening.

        Unlike reveal_neuron this never touches the links: the rest of the
        brain is already drawn, and stays drawn.
        """
        import time

        if neuron_name not in self.neuron_positions:
            return
        self.visible_neurons.add(neuron_name)
        self.neuron_reveal_animations[neuron_name] = {
            'start_time': time.time(),
            'progress': 0.0,
        }
        self._set_render_fps(self.REVEAL_RENDER_FPS)
        self.mark_render_dirty()

    def play_birth_sequence(self, duration: float = 5.0):
        """Reveal every neuron the squid is born with, spread over `duration`.

        For callers that are not synchronised to anything - a loaded game, or
        a brain window opened after the fact. The splash-driven hatch paces
        itself against its own frames instead.
        """
        sequence = list(self.original_neurons)
        if not sequence:
            return
        step = duration / len(sequence)
        for index, name in enumerate(sequence):
            self.reveal_neuron(name, delay=index * step)

    def relayout_grown_neurons(self):
        """Spread every grown neuron evenly along the growth rows.

        Run after each birth, so the arrangement is a property of HOW MANY
        neurons the squid has grown rather than of the order chance happened
        to place them in. Neurons the squid was born with are never moved -
        their rows are structure.
        """
        from .brain_constants import growth_positions

        grown = [name for name in self.neuron_positions
                 if name not in self.innate_neurons]
        if not grown:
            return
        self.neuron_positions.update(growth_positions(grown))
        self.mark_render_dirty()

    def _enable_links_after_reveal(self):
        """Re-enable checkbox, tick it, and kick off the existing link-fade engine."""
        self.show_links = True
        
        # Populate link targets for all weights
        for key in self.weights.keys():
            self._link_targets[key] = 1.0
            if key not in self._link_opacities:
                self._link_opacities[key] = 0.0
        
        # Set fade speed
        self._link_fade_speed = 3.0
        
        # Re-enable and check the checkbox
        if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
            nt = self.parent().network_tab
            nt.checkbox_links.setEnabled(True)
            nt.checkbox_links.setChecked(True)

        # Start the fade timer
        if not self._link_fade_timer.isActive():
            self._link_fade_timer.start()
        
        self.mark_render_dirty()

    def reveal_all_core_neurons(self):
        """Make all core neurons visible immediately (for loaded games)"""
        for neuron_name in self.original_neurons:
            self.visible_neurons.add(neuron_name)
        # For loaded games, remove tracking attributes immediately
        if hasattr(self, 'revealed_neurons'):
            delattr(self, 'revealed_neurons')
        if hasattr(self, 'revealed_connections'):
            delattr(self, 'revealed_connections')
        # Ensure tutorial mode is disabled for loaded games
        self.is_tutorial_mode = False
        
        # Mark render dirty and trigger update
        self.mark_render_dirty()
        self.update()

    def _reveal_connections_for_neuron(self, neuron_name):
        """Reveal connections between this neuron and other revealed neurons
        NOTE: This should only be called during tutorial mode"""
        if not self.is_tutorial_mode:
            return
        if not hasattr(self, 'weights'):
            return
        if not hasattr(self, 'revealed_neurons') or not hasattr(self, 'revealed_connections'):
            return
            
        # Check all weights to find connections involving this neuron
        for (source, target), weight in self.weights.items():
            # If both ends of the connection are revealed, track it
            if source in self.revealed_neurons and target in self.revealed_neurons:
                edge_key = f"{source}->{target}"
                if edge_key not in self.revealed_connections:
                    self.revealed_connections.add(edge_key)

    def finish_reveal_animation(self):
        """Called when the reveal animation completes - cleanup tracking attributes"""
        # Remove reveal tracking so normal counting resumes
        if hasattr(self, 'revealed_neurons'):
            delattr(self, 'revealed_neurons')
        if hasattr(self, 'revealed_connections'):
            delattr(self, 'revealed_connections')

        # Exit tutorial mode
        self.is_tutorial_mode = False

        # AUTO-ENABLE links now that all neurons are revealed
        self.show_links = True
        if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
            nt = self.parent().network_tab
            nt.checkbox_links.setEnabled(True)
            nt.checkbox_links.setChecked(True)      # tick the box

        # Fade-in the links smoothly
        if self.show_links and self._link_targets:
            self._auto_fade_links_pending = True
            if not self._link_fade_timer.isActive():
                self._advance_link_fades()

    def add_weight_animation(self, neuron1, neuron2, old_weight, new_weight, 
                         custom_color=None, custom_duration=3.0):
        """Add animation for a weight change with organic staggering through connectors"""
        current_time = time.time()
        
        # Determine color based on weight change direction if not custom
        if custom_color:
            color = custom_color
        else:
            color = (0, 255, 0) if new_weight > old_weight else (255, 0, 0)
        
        # Check if there's a connector neuron in the path
        # A connector is in the path if:
        # 1. It has connections to both neuron1 and neuron2
        # 2. It's a connector type neuron
        connector_in_path = None
        possible_connectors = []
        
        # Find all connector neurons that connect to both
        for (src, dst), weight in self.weights.items():
            # Check if this is a connector neuron connection
            is_connector = self.is_connector_neuron(src)
            
            if is_connector:
                # Check if connector connects to both neurons
                conn_to_n1 = (src == neuron1 or dst == neuron1)
                conn_to_n2 = (src == neuron2 or dst == neuron2)
                
                if conn_to_n1 and conn_to_n2:
                    # This connector is between our two neurons
                    connector_in_path = src if src.startswith('connector_') else dst
                    break
        
        # Create staggered animations for organic feel
        if connector_in_path:
            # Two-segment animation: neuron1 → connector → neuron2
            # Add random delay at connector for organic relay effect
            
            # First segment: neuron1 → connector
            self.weight_animations.append({
                'pair': (neuron1, connector_in_path),
                'start_time': current_time,
                'duration': custom_duration * 0.45,  # Slightly shorter for first half
                'start_weight': old_weight,
                'end_weight': new_weight,
                'neuron1': neuron1,
                'neuron2': connector_in_path,
                'color': color,
                'is_segment': True,
                'final_target': neuron2
            })
            
            # Second segment: connector → neuron2 (with stagger delay)
            stagger_delay = random.uniform(0.15, 0.25)  # 150-250ms pause at connector
            self.weight_animations.append({
                'pair': (connector_in_path, neuron2),
                'start_time': current_time + stagger_delay,
                'duration': custom_duration * 0.45,
                'start_weight': old_weight,
                'end_weight': new_weight,
                'neuron1': connector_in_path,
                'neuron2': neuron2,
                'color': color,
                'is_segment': True,
                'final_target': neuron2,
                'stagger_delay': stagger_delay
            })
            
            print(f"🎨 Staggered animation: {neuron1} → {connector_in_path} → {neuron2} "
                f"(delay: {stagger_delay:.2f}s)")
        else:
            # Direct connection - single animation as before
            self.weight_animations.append({
                'pair': (neuron1, neuron2),
                'start_time': current_time,
                'duration': custom_duration,
                'start_weight': old_weight,
                'end_weight': new_weight,
                'neuron1': neuron1,
                'neuron2': neuron2,
                'color': color,
                'is_segment': False
            })
        
        # Record communication events
        self.weight_change_events[neuron1] = current_time
        self.weight_change_events[neuron2] = current_time
        
        # Add to recently updated pairs (store original pair)
        if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
        (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
            self.recently_updated_neuron_pairs.append((neuron1, neuron2))
        
        # Mark render dirty immediately
        self.mark_render_dirty()
        self.update()

    def _update_communication_events(self):
        """Clean up old communication events that have expired"""
        current_time = time.time()
        # Remove events older than the highlight duration
        expired_neurons = [
            neuron for neuron, event_time in self.communication_events.items()
            if current_time - event_time > self.communication_highlight_duration
        ]
        for neuron in expired_neurons:
            del self.communication_events[neuron]

    def reset_animation_state(self):
        """
        Reset all animation and reveal tracking attributes for a new game.
        This ensures the neuron reveal animation can run properly.
        """
        # Enable tutorial mode for new game reveal animation
        self.is_tutorial_mode = True
        
        # Reset visible neurons
        self.visible_neurons = set()
        
        # Reset reveal tracking (recreate if deleted)
        self.revealed_neurons = set()
        self.revealed_connections = set()
        
        # Clear reveal animations
        self.neuron_reveal_animations = {}
        
        print("🔄 Animation state reset for new game (tutorial mode enabled)")

    def start_tutorial_glow(self, duration_ms=5000):
        """Start a glowing, pulsing border effect for tutorial purposes"""
        self.tutorial_glow_active = True
        self._tutorial_glow_opacity = 0.0
        
        # Create animation for pulsing effect
        self.tutorial_glow_animation = QtCore.QPropertyAnimation(self, b"tutorial_glow_opacity")
        self.tutorial_glow_animation.setDuration(500)  # 0.5 second pulse
        self.tutorial_glow_animation.setStartValue(0.0)
        self.tutorial_glow_animation.setEndValue(1.0)
        self.tutorial_glow_animation.setLoopCount(-1)  # Infinite loop
        self.tutorial_glow_animation.setEasingCurve(QtCore.QEasingCurve.InOutSine)
        
        # Start the animation
        self.tutorial_glow_animation.start()
        
        # Set timer to stop after duration
        self.tutorial_glow_timer = QtCore.QTimer()
        self.tutorial_glow_timer.setSingleShot(True)
        self.tutorial_glow_timer.timeout.connect(self.stop_tutorial_glow)
        self.tutorial_glow_timer.start(duration_ms)

    def stop_tutorial_glow(self):
        """Stop the tutorial glow effect"""
        self.tutorial_glow_active = False
        if self.tutorial_glow_animation:
            self.tutorial_glow_animation.stop()
            self.tutorial_glow_animation = None
        if self.tutorial_glow_timer:
            self.tutorial_glow_timer.stop()
            self.tutorial_glow_timer = None
        self.update()
