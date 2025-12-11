import sys
import csv
import os
import time
import math
import random
import numpy as np
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QPixmap, QFont
from datetime import datetime
from .neurogenesis import EnhancedNeurogenesis, ExperienceBuffer
from .brain_tooltips import EnhancedBrainTooltips
from .brain_constants import CORE_NEURONS, INPUT_SENSORS, is_core_neuron
from .personality import Personality
from .learning import LearningConfig
from .laboratory import NeuronLaboratory
from .brain_worker import BrainWorker  # Threading support
from typing import Dict, Optional

# Brain state bridge for designer communication
try:
    from .brain_state_bridge import (
        export_brain_state,
        set_game_running,
        update_brain_state_from_widget
    )
    _HAS_BRAIN_BRIDGE = True
except ImportError:
    try:
        # Try without relative import for standalone testing
        from brain_state_bridge import (
            export_brain_state,
            set_game_running,
            update_brain_state_from_widget
        )
        _HAS_BRAIN_BRIDGE = True
    except ImportError:
        _HAS_BRAIN_BRIDGE = False
        print("[BrainWidget] Warning: brain_state_bridge not found, designer sync disabled")

from .animation_styles import (
    AnimationStyle, VibrantStyle, SubtleStyle,
    get_animation_style, get_available_styles, get_style_info,
    ANIMATION_STYLES
)

# Performance tracking for Task Manager
try:
    from .task_manager import perf_tracker
    _PERF_TRACKING_AVAILABLE = True
except ImportError:
    _PERF_TRACKING_AVAILABLE = False

class BrainWidget(QtWidgets.QWidget):
    """
    Neural network visualization widget with theming support.
    
    Supports 3 animation styles:
    - 'classic': Original clean animation style (default)
    - 'vibrant': Enhanced colors with hover effects
    - 'subtle': Muted tones with smooth transitions
    
    Switch styles at runtime using set_animation_style().
    """
    
    neuronClicked = QtCore.pyqtSignal(str)
    animationStyleChanged = QtCore.pyqtSignal(str)  # Emitted when style changes
    neuronCreated = QtCore.pyqtSignal(str)  # Emitted when neurogenesis creates a new neuron

    def __init__(self, config=None, debug_mode=False, tamagotchi_logic=None,
                 animation_style: str = "vibrant"):
        self.resolution_scale = 1.0  # Default resolution scale
        self.config = config if config else LearningConfig()
        self._laboratory = None
        
        # ===== ANIMATION STYLE INITIALIZATION =====
        self._animation_style_name = animation_style
        self._animation_style: AnimationStyle = get_animation_style(animation_style)
        self.layers = []

        # State update batching
        self._pending_state_update = False
        self.state_update_queue = []
        
        # Caches for neuron data
        self.neurons = {}
        self.state_colors = {}
        
        # Hover tracking
        self.hovered_neuron = None
        self.hover_value_display_active = False
        self.hover_value_opacity = 0.0
        self.hover_value_animation_time = 0.0
        self.hover_animation_time = 0
        if not hasattr(self.config, 'hebbian'): #
            self.config.hebbian = { #
                'learning_interval': 30000, #
                'weight_decay': 0.01, #
                'active_threshold': 50 #
            }
        super().__init__() #

        self.base_font_size = 10

        # Tutorial glow effect properties
        self.tutorial_glow_active = False
        self.tutorial_glow_timer = None
        self.tutorial_glow_animation = None
        self._tutorial_glow_opacity = 0.0
        self._link_fade_speeds = {}        # (src,dst) → fade speed per link
        self._link_start_times = {}        # (src,dst) → when this link should start

        from .neurogenesis_show import ShowmanNeurogenesis
        real_engine                 = EnhancedNeurogenesis(self, config)
        self.enhanced_neurogenesis  = ShowmanNeurogenesis(real_engine)
        self.excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping']
        
        # Build animation palette from selected style
        self._build_animation_palette()
        
        self.hebbian_countdown_seconds = 30  # Default duration
        self.learning_active = True #
        self.pruning_enabled = True #
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.is_paused = False #
        self.weights = {}           # Init weights early
        self.last_hebbian_time = time.time() #
        self.last_neurogenesis_type = None
        self.tamagotchi_logic = tamagotchi_logic #
        self.recently_updated_neuron_pairs = [] #
        self.neuron_shapes = {} #
        

        # Neural communication tracking system
        self.communication_events = {} #
        self.communication_highlight_duration = 0.5 #
        self.weight_change_events = {} #
        self.activity_duration = 0.5 #

        # ADDED IN 2.4.5.0: Replace simple neurogenesis_data with enhanced system
        self.enhanced_neurogenesis = EnhancedNeurogenesis(self, self.config)
        self.experience_buffer = self.enhanced_neurogenesis.experience_buffer

        # Ensure neurogenesis config exists
        if not hasattr(self.config, 'neurogenesis'): #
            self.config.neurogenesis = {
                'decay_rate': 0.75,  # Default decay rate if not specified
                'novelty_threshold': 3.0, #
                'stress_threshold': 1.2, #
                'reward_threshold': 3.5, #
                'cooldown': 180, #
                'highlight_duration': 5.0, #
                'max_neurons': 50
            }

        self.neurogenesis_config = self.config.neurogenesis 
        self.neurogenesis_data = {
            'new_neurons': [],
            'last_neuron_time': time.time(),
            'new_neurons_details': {}   # used by inspector / logging
        }

        # Neural state initialization
        self.state = { #
            "can_see_food": 0,
            "hunger": 50, #
            "happiness": 50, #
            "cleanliness": 50, #
            "sleepiness": 50, #
            "satisfaction": 50, #
            "anxiety": 50, #
            "curiosity": 50, #
            "is_sick": False, #
            "is_eating": False, #
            "is_sleeping": False, #
            "pursuing_food": False, #
            "direction": "up", #
            "position": (0, 0), #
            "is_startled": False, #
            "is_fleeing": False, #
            'neurogenesis_active': True
        }

        # Neuron position configuration
        self.original_neuron_positions = { #
            "can_see_food": (50, 200),
            "hunger": (127, 81), #
            "happiness": (361, 81), #
            "cleanliness": (627, 81), #
            "sleepiness": (840, 81), #
            "satisfaction": (271, 380), #
            "anxiety": (491, 389), #
            "curiosity": (701, 386) #
        }
        self.neuron_positions = self.original_neuron_positions.copy() #

        # Ensure connection to hunger exists (always)
        self.weights[("can_see_food", "hunger")] = 0.2  # Seeing food increases hunger slightly

        # Random chance (50%) for happiness connection
        if random.random() < 0.5:
            self.weights[("can_see_food", "happiness")] = 0.5  # Seeing food can increase happiness

        # Track which neurons are visible (for animated reveal on new game)
        self.visible_neurons = set()
        # List of core neurons in reveal order
        self.original_neurons = ["can_see_food", "hunger", "happiness", "cleanliness", "sleepiness", 
                                 "satisfaction", "anxiety", "curiosity"]
        # Animation state for neuron reveals
        self.neuron_reveal_animations = {}  # {neuron_name: {'start_time': float, 'progress': float}}
        # --- link fade animation ---
        self._link_opacities = {}          # (src,dst) → current opacity 0.0-1.0
        self._link_targets   = {}          # (src,dst) → target opacity  0 or 1
        self._link_fade_timer = QtCore.QTimer(self)
        self._link_fade_timer.setInterval(16)          # ~60 FPS
        self._link_fade_timer.timeout.connect(self._advance_link_fades)
        self._auto_fade_links_pending = False 
        
        # Tutorial mode flag
        self.is_tutorial_mode = False
        
        # Track revealed neurons and connections for synced count display during animation
        # NOTE: These should ONLY be used when is_tutorial_mode is True
        self.revealed_neurons = set()
        self.revealed_connections = set()

        # Initialize communication events for all neurons
        for neuron in self.neuron_positions.keys(): #
            self.communication_events[neuron] = 0 #

        # Animation control variables
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self.update_animations)

        # ===== PERFORMANCE FIX: Don't create BrainWorker here =====
        # BrainWorker will be provided externally via set_brain_worker()
        # This prevents multiple worker threads competing for CPU
        self.brain_worker = None  # Will be set by SquidBrainWindow
        print("🧵 BrainWorker will be set externally")
        
        # Threading control flags
        self._use_threaded_processing = True
        self._pending_neurogenesis_check = False
        self._pending_hebbian_learning = False

        # NEUROGENESIS FIX: Start monitoring timer
        self.neurogenesis_timer = QtCore.QTimer(self)
        self.neurogenesis_timer.timeout.connect(self._periodic_neurogenesis_check)
        self.neurogenesis_timer.start(2000)  # Check every 2 seconds
        print("🧬 Neurogenesis monitoring timer started")
        
        # Brain state bridge: export state for designer synchronization
        if _HAS_BRAIN_BRIDGE:
            self._brain_export_timer = QtCore.QTimer(self)
            self._brain_export_timer.timeout.connect(self._export_brain_state_for_designer)
            self._brain_export_timer.start(5000)  # Export every 5 seconds
            set_game_running(True)  # Mark game as running
            print("🔗 Brain state export enabled for designer sync")
        
        self.animation_timer.start(40)  # 2.5.0.0 performance fix
        self._last_animation_update = 0  # For throttling
        
        # ===== PERFORMANCE FIX: Cache for expensive paint objects =====
        self._cached_fonts = {}
        self._cached_pens = {}
        
        self.neuron_sizes = {}  # For smooth size transitions
        self.weight_animations = []  # Track multiple weight changes
        self.neurogenesis_highlight = {
            'neuron': None,
            'start_time': 0,
            'duration': 5.0,
            'pulse_phase': 0
        }

        # Add neurogenesis visualization tracking
        self.neurogenesis_highlight = { #
            'neuron': None, #
            'start_time': 0, #
            'duration': 5.0  # seconds
        }

        # Connection and weight initialization
        self.connections = self.initialize_connections() #
        self.initialize_weights()  # Populate weights
        
        self.show_links = True #
        self.frozen_weights = None #
        self.history = [] #
        self.training_data = [] #
        self.associations = np.zeros((len(self.neuron_positions), len(self.neuron_positions))) #
        self.learning_rate = 0.1 #
        self.capture_training_data_enabled = False #
        self.dragging = False #
        self.dragged_neuron = None #
        self.drag_start_pos = None #
        self.tooltip_manager = EnhancedBrainTooltips(self)
        self.setMouseTracking(True)
        self.show_weights = False

        # Ensure connections to hunger and happiness exist with initial weights
        self.weights[("can_see_food", "hunger")] = 0.2  # Seeing food increases hunger slightly
        self.weights[("can_see_food", "happiness")] = 0.5
        _link_fade_speed = 3.0   # opacity units per second (tweak for faster/slower)

    def set_brain_worker(self, worker):
        """Accept an external BrainWorker instance."""
        
        self.brain_worker = worker  # Always set the new worker
        
        # Reconnect signals (disconnect old ones first to avoid duplicates)
        if hasattr(self, 'brain_worker'):
            try:
                self.brain_worker.neurogenesis_result.disconnect(self._on_neurogenesis_complete)
                self.brain_worker.hebbian_result.disconnect(self._on_hebbian_complete)
                self.brain_worker.state_update_result.disconnect(self._on_state_update_complete)
                self.brain_worker.error_occurred.disconnect(self._on_worker_error)
            except:
                pass  # Ignore if signals weren't connected
        
        # Connect new signals
        self.brain_worker.neurogenesis_result.connect(self._on_neurogenesis_complete)
        self.brain_worker.hebbian_result.connect(self._on_hebbian_complete)
        self.brain_worker.state_update_result.connect(self._on_state_update_complete)
        self.brain_worker.error_occurred.connect(self._on_worker_error)
        
        print("🧵 BrainWidget received external BrainWorker")

    # =========================================================================
    # BRAIN STATE BRIDGE METHODS (for designer synchronization)
    # =========================================================================
    
    def _export_brain_state_for_designer(self):
        """
        Export current brain state to shared file for designer import.
        Called periodically by timer when brain_state_bridge is available.
        """
        if not _HAS_BRAIN_BRIDGE:
            return
        
        try:
            update_brain_state_from_widget(self)
        except Exception as e:
            # Silent failure - don't spam console
            pass
    
    def cleanup_brain_bridge(self):
        """
        Clean up brain bridge files when widget is destroyed.
        Should be called when the game exits.
        """
        if _HAS_BRAIN_BRIDGE:
            try:
                set_game_running(False)
                print("🔗 Brain state bridge cleaned up")
            except Exception:
                pass
    
    def closeEvent(self, event):
        """Handle widget close - clean up brain bridge."""
        self.cleanup_brain_bridge()
        super().closeEvent(event) if hasattr(super(), 'closeEvent') else None
        event.accept()



    def set_debug_mode(self, enabled):
        """Set debug mode without causing circular callbacks"""
        # Only proceed if there's an actual change
        if self.debug_mode == enabled:
            return

        # Update our own state
        self.debug_mode = enabled

        # Update brain widget
        if hasattr(self, 'brain_widget'):
            self.brain_widget.debug_mode = enabled

        # Update tabs
        for tab_name in ['network_tab', 'nn_viz_tab', 'memory_tab', 'decisions_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'debug_mode'):
                    tab.debug_mode = enabled

        # Enable/disable debug-specific UI elements
        if hasattr(self, 'stimulate_button'):
            self.stimulate_button.setEnabled(enabled)

        print(f"Brain window debug mode set to: {enabled}")

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

    def is_binary_neuron(self, neuron_name: str) -> bool:
        """Return True if neuron represents a binary (on/off) state."""
        binary_neurons = {
            'can_see_food',
            'is_eating',
            'is_sleeping',
            'is_sick',
            'pursuing_food',
            'is_fleeing',
            'is_startled',
            'external_stimulus',   # usually high/low, treat as binary-ish
            'plant_proximity',     # 2.6.0.2 consider this could be analog
        }
        return neuron_name in binary_neurons
    
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
    
    def _draw_comm_glows_for_connection(self, painter, scale, conn_key, start_point, end_point):
        """
        Draw all communication glow packets traveling along a connection.
        Each glow is a soft glowing orb that travels from source to target.
        """
        # Check both directions for packets
        reverse_key = (conn_key[1], conn_key[0])
        
        for key, direction in [(conn_key, 1), (reverse_key, -1)]:
            if key not in self._comm_glow_packets:
                continue
            
            packets = self._comm_glow_packets[key]
            
            for packet in packets:
                progress = packet['progress']
                
                # Calculate fade based on position (fade in at start, fade out at end)
                if progress < self.anim_comm_glow_fade_in:
                    # Fade in
                    alpha_mult = progress / self.anim_comm_glow_fade_in
                elif progress > (1.0 - self.anim_comm_glow_fade_out):
                    # Fade out
                    alpha_mult = (1.0 - progress) / self.anim_comm_glow_fade_out
                else:
                    alpha_mult = 1.0
                
                # Clamp alpha multiplier
                alpha_mult = max(0.0, min(1.0, alpha_mult))
                
                # Calculate position along the line
                if direction == 1:
                    # Forward direction
                    glow_x = start_point.x() + progress * (end_point.x() - start_point.x())
                    glow_y = start_point.y() + progress * (end_point.y() - start_point.y())
                else:
                    # Reverse direction (packet traveling backward)
                    glow_x = end_point.x() + progress * (start_point.x() - end_point.x())
                    glow_y = end_point.y() + progress * (start_point.y() - end_point.y())
                
                glow_pos = QtCore.QPointF(glow_x, glow_y)
                
                # Draw the glow with multiple layers for soft appearance
                glow_size = self.anim_comm_glow_size * scale
                r, g, b = self.anim_comm_glow_colour
                
                # Outer glow (larger, more transparent)
                outer_alpha = int(self.anim_comm_glow_alpha * 0.3 * alpha_mult)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, outer_alpha)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(glow_pos, glow_size * 1.5, glow_size * 1.5)
                
                # Middle glow
                mid_alpha = int(self.anim_comm_glow_alpha * 0.6 * alpha_mult)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, mid_alpha)))
                painter.drawEllipse(glow_pos, glow_size, glow_size)
                
                # Inner core (brightest)
                inner_alpha = int(self.anim_comm_glow_alpha * alpha_mult)
                # Slightly whiter core
                core_r = min(255, r + 50)
                core_g = min(255, g + 50)
                core_b = min(255, b + 50)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(core_r, core_g, core_b, inner_alpha)))
                painter.drawEllipse(glow_pos, glow_size * 0.5, glow_size * 0.5)
                
                # Draw tail (trailing glow particles)
                if self.anim_comm_glow_tail_length > 0:
                    tail_steps = 3
                    for i in range(1, tail_steps + 1):
                        tail_progress = progress - (self.anim_comm_glow_tail_length * i / tail_steps)
                        if tail_progress < 0:
                            continue
                        
                        # Calculate tail position
                        if direction == 1:
                            tail_x = start_point.x() + tail_progress * (end_point.x() - start_point.x())
                            tail_y = start_point.y() + tail_progress * (end_point.y() - start_point.y())
                        else:
                            tail_x = end_point.x() + tail_progress * (start_point.x() - end_point.x())
                            tail_y = end_point.y() + tail_progress * (start_point.y() - end_point.y())
                        
                        tail_pos = QtCore.QPointF(tail_x, tail_y)
                        
                        # Tail gets smaller and more transparent
                        tail_size = glow_size * 0.6 * (1.0 - i / (tail_steps + 1))
                        tail_alpha = int(outer_alpha * (1.0 - i / (tail_steps + 1)))
                        
                        painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, tail_alpha)))
                        painter.drawEllipse(tail_pos, tail_size, tail_size)
    
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
    
    def _draw_neural_connections(self, painter, scale):
        """
        Draw connections in Neural style with weight-based thickness
        and traveling activation pulses.
        """
        if not self.show_links:
            return
        
        current_time = time.time()
        duration = self.anim_neural_pulse_duration
        
        # Pre-calculate scaled positions
        scaled_positions = {}
        for name, (x, y) in self.neuron_positions.items():
            if name not in self.excluded_neurons:
                scaled_positions[name] = (x * scale, y * scale)
        
        # === 1. Draw all static connections (base layer) ===
        for (src, dst), weight in self.weights.items():
            if src not in scaled_positions or dst not in scaled_positions:
                continue
            
            x1, y1 = scaled_positions[src]
            x2, y2 = scaled_positions[dst]
            
            # Base opacity from toggle fade system
            base_opacity = self._link_opacities.get((src, dst), 1.0)
            if base_opacity <= 0:
                continue
            
            # Weight-based thickness
            if self.anim_neural_weight_thickness:
                thickness = max(1.0, abs(weight) * self.anim_neural_weight_thickness_mult)
            else:
                thickness = self.anim_line_base_width
            pen_width = max(1, int(thickness * scale))
            
            # Color based on weight sign
            alpha = int(self.anim_neural_base_alpha * base_opacity)
            if weight >= 0:
                r, g, b = self.anim_neural_base_colour_pos
            else:
                r, g, b = self.anim_neural_base_colour_neg
            
            color = QtGui.QColor(r, g, b, alpha)
            pen = QtGui.QPen(color, pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QtCore.QLineF(x1, y1, x2, y2))
        
        # === 2. Draw activation pulses on top (traveling lights) ===
        for (src, dst), pulses in self._neural_pulses.items():
            if src not in scaled_positions or dst not in scaled_positions:
                continue
            
            x1, y1 = scaled_positions[src]
            x2, y2 = scaled_positions[dst]
            
            for pulse in pulses:
                elapsed = current_time - pulse['start_time']
                progress = elapsed / duration
                
                if progress > 1.0:
                    continue
                
                # Sinusoidal fade (glow in → peak → fade out)
                opacity = math.sin(progress * math.pi)
                
                # Get pulse color
                r, g, b = pulse['color']
                final_alpha = int(255 * opacity * 0.95)
                
                pulse_color = QtGui.QColor(r, g, b, final_alpha)
                
                # Thick glowing pulse line
                pulse_width = max(1, int(self.anim_neural_pulse_width * scale))
                pen = QtGui.QPen(pulse_color, pulse_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
                painter.setPen(pen)
                
                # Traveling light effect - pulse moves along connection
                segment_progress = progress * 1.35
                if segment_progress <= 1.0:
                    # First phase: light travels from source toward destination
                    t = min(1.0, segment_progress)
                    px = x1 + t * (x2 - x1)
                    py = y1 + t * (y2 - y1)
                    painter.drawLine(QtCore.QLineF(x1, y1, px, py))
                else:
                    # Second phase: light "drains" toward destination
                    t = min(1.0, segment_progress - 0.35)
                    px = x1 + t * (x2 - x1)
                    py = y1 + t * (y2 - y1)
                    painter.drawLine(QtCore.QLineF(px, py, x2, y2))


    # =========================================================================
    # Worker thread signal handlers
    # =========================================================================
    
    def _on_neurogenesis_complete(self, result: dict):
        """Handle neurogenesis result from worker thread (called on main thread).
        
        The worker thread performs preliminary checks and signals whether creation
        should proceed. Actual neuron creation happens here on the main thread
        via the EnhancedNeurogenesis system.
        """
        self._pending_neurogenesis_check = False
        
        # Check if worker signaled that we should create a neuron
        if not result.get('should_create', False):
            return
        
        # Get the context from worker result
        neuron_type = result.get('neuron_type')
        trigger_value = result.get('trigger_value', 0)
        state_context = result.get('state_context', {})
        is_emergency = result.get('is_emergency', False)
        
        if not neuron_type:
            return
        
        # print(f"🧵 Worker signaled neurogenesis: type={neuron_type}, emergency={is_emergency}")
        
        # Build environment from state context
        environment = {
            'food_count': state_context.get('food_count', 0),
            'poop_count': state_context.get('poop_count', 0),
            'is_sick': state_context.get('is_sick', False),
            'is_eating': state_context.get('is_eating', False),
            'has_rock': state_context.get('carrying_rock', False),
            'new_object_encountered': state_context.get('new_object_encountered', False),
            'recent_positive_outcome': state_context.get('recent_positive_outcome', False)
        }
        
        # Use the EnhancedNeurogenesis system to create the neuron properly
        try:
            # Capture experience context
            context = self.enhanced_neurogenesis.capture_experience_context(
                trigger_type=neuron_type,
                brain_state=state_context,
                recent_actions=state_context.get('recent_actions', []),
                environment=environment
            )
            
            # For emergency creation, skip the normal checks
            if is_emergency:
                neuron_name = self.enhanced_neurogenesis.create_functional_neuron(context, is_emergency=True)
            else:
                # Normal path: check if we should create based on pattern recurrence
                if self.enhanced_neurogenesis.should_create_neuron(context):
                    neuron_name = self.enhanced_neurogenesis.create_functional_neuron(context)
                else:
                    # Experience captured but not enough pattern recurrence yet
                    return
            
            if neuron_name:
                print(f"✨ Main thread: Created neuron {neuron_name}")
                
                # Emit signal to notify listeners (e.g., NetworkTab) of new neuron
                self.neuronCreated.emit(neuron_name)
                
                # Handle pruning if needed
                if self.pruning_enabled:
                    current_count = len(self.neuron_positions) - len(self.excluded_neurons)
                    max_neurons = self.neurogenesis_config.get('max_neurons', 32)
                    if current_count > max_neurons * 0.85:
                        self.enhanced_neurogenesis.intelligent_pruning()
                
                self.update()
                
        except Exception as e:
            print(f"⚠️ Error during neuron creation on main thread: {e}")
            import traceback
            traceback.print_exc()
            
    def _on_hebbian_complete(self, result: dict):
        """Handle Hebbian learning result from worker thread (called on main thread)."""
        self._pending_hebbian_learning = False
        
        # Always reset the timer so countdown restarts properly
        self.last_hebbian_time = time.time()
        
        updated_pairs = result.get('updated_pairs', [])
        weight_updates = result.get('weight_updates', {})
        
        if not weight_updates:
            self.update()
            return
            
        # Apply the weight updates (main thread only)
        for pair_str, update_data in weight_updates.items():
            # Convert string key back to tuple if needed
            if isinstance(pair_str, str):
                pair = tuple(pair_str.split(','))
            else:
                pair = pair_str
                
            if pair in self.weights:
                old_weight = update_data['old_weight']
                new_weight = update_data['new_weight']
                self.weights[pair] = new_weight
                
                # Add animation for visual feedback
                n1, n2 = pair
                self.add_weight_animation(n1, n2, old_weight, new_weight)
                
        # Update tracking (convert lists to tuples for consistency)
        self.recently_updated_neuron_pairs = [tuple(p) if isinstance(p, list) else p for p in updated_pairs]
        self.last_hebbian_time = time.time()
        
        # Console output
        if updated_pairs:
            COLORS = ["\033[96m", "\033[93m", "\033[95m", "\033[92m", "\033[94m"]
            RESET = "\033[0m"
            colored = []
            for i, pair in enumerate(updated_pairs):
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    a, b = pair
                    color = COLORS[i % len(COLORS)]
                    colored.append(f"{color}{a} ↔ {b}{RESET}")
            if colored:
                print("     Hebbian learning chosen pairs: " + "  ".join(colored))
            
        self.update()
        

    def _on_state_update_complete(self, result: dict):
        """Handle state-update results from the worker thread (main thread)."""
        self._pending_state_update = False

        # heartbeat packet – just record activity and return
        if result.get('health_check'):
            return

        # apply the processed state
        processed_state = result.get('processed_state', {})
        self.state.update(processed_state)          # ← self, NOT self.brain_widget

        # update communication events for glow effects
        comm_events = result.get('communication_events', {})
        self.communication_events.update(comm_events)

        # optional decay pre-application
        decay_updates = result.get('decay_updates', {})
        if decay_updates and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'brain_hooks'):
                for neuron, decayed_val in decay_updates.items():
                    if neuron in self.state:
                        self.state[neuron] = decayed_val

        # functional-neuron update
        if hasattr(self, 'enhanced_neurogenesis') and \
        getattr(self.enhanced_neurogenesis, 'functional_neurons', None):
            self.enhanced_neurogenesis.update_neuron_activations(self.state)

        self.update()          # repaint

        # queue next update if any
        if self.state_update_queue:
            next_data = self.state_update_queue.pop(0)
            if hasattr(self, 'brain_worker') and self.brain_worker:
                self.brain_worker.queue_state_update(next_data)
                self._pending_state_update = True
        
    def _on_worker_error(self, error_msg: str):
        """Handle errors from the worker thread."""
        print(f"⚠️ BrainWorker error: {error_msg}")
        
    def _update_worker_cache(self):
        """Update the worker's cached data for thread-safe access."""
        if hasattr(self, 'brain_worker') and self.brain_worker:
            # Gather new neurons for learning rate boost
            new_neurons = set()
            if hasattr(self, 'new_neurons'):
                new_neurons = set(self.new_neurons.keys()) if isinstance(self.new_neurons, dict) else set(self.new_neurons)
            
            self.brain_worker.update_cache(
                self.state,
                self.weights,
                self.neuron_positions,
                self.config,
                excluded_neurons=getattr(self, 'excluded_neurons', set()),
                learning_rate=getattr(self, 'learning_rate', 0.1),
                new_neurons=new_neurons
            )
            
    def stop_worker(self):
        """Stop the worker thread gracefully (call on application exit)."""
        if hasattr(self, 'brain_worker') and self.brain_worker:
            self.brain_worker.stop()
            self.brain_worker.wait(2000)  # Wait up to 2 seconds
            print("🧵 BrainWorker thread stopped")
    
    # =========================================================================
    # End worker thread signal handlers
    # =========================================================================

        
    def is_neuron_revealed(self, name):
        """Return True if the neuron has finished its reveal animation.
        Only checks revealed tracking during tutorial mode."""
        # In normal gameplay (not tutorial), all neurons are considered revealed
        if not self.is_tutorial_mode:
            return True
            
        # During tutorial, check if neuron has completed its animation
        if name not in self.neuron_reveal_animations:
            return name in self.visible_neurons  # never animated = already visible
        anim = self.neuron_reveal_animations[name]
        elapsed = time.time() - anim['start_time']
        return elapsed >= 0.4  # same duration used in draw_neurons
    

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
        # === NEW: Freeze animations when paused ===
        if self.is_paused:
            return
        # ==========================================

        current_time = time.time()
        
        # Performance tracking (keep if using task manager)
        if _PERF_TRACKING_AVAILABLE:
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
            completed_reveals = []
            for neuron_name, anim_data in self.neuron_reveal_animations.items():
                elapsed = current_time - anim_data['start_time']
                if elapsed >= 0.4:
                    anim_data['progress'] = 1.0
                    completed_reveals.append(neuron_name)
                else:
                    anim_data['progress'] = 1 - (1 - elapsed / 0.4) ** 3

            for neuron_name in completed_reveals:
                del self.neuron_reveal_animations[neuron_name]
            
            needs_repaint = True
            
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
        if _PERF_TRACKING_AVAILABLE:
            _anim_elapsed = (time.perf_counter() - _anim_start) * 1000
            perf_tracker.record("update_animations", _anim_elapsed)

    def _get_cached_font(self, size, bold=False):
        """Return cached QFont to avoid recreation every paint."""
        key = (size, bold)
        if key not in self._cached_fonts:
            font = QtGui.QFont("Arial", size)
            if bold:
                font.setBold(True)
            self._cached_fonts[key] = font
        return self._cached_fonts[key]
    
    def _get_cached_pen(self, color_tuple, width=1):
        """Return cached QPen to avoid recreation every paint."""
        key = (*color_tuple, width)
        if key not in self._cached_pens:
            color = QtGui.QColor(*color_tuple[:3])
            if len(color_tuple) > 3:
                color.setAlpha(color_tuple[3])
            self._cached_pens[key] = QtGui.QPen(color, width)
        return self._cached_pens[key]

    def reveal_neuron(self, neuron_name):
        """Reveal a neuron with an expand animation – forces links OFF during reveal."""
        if neuron_name not in self.original_neurons:
            return
        if neuron_name in self.visible_neurons:
            return
        if neuron_name not in self.neuron_positions:
            print(f"❌ ERROR: Neuron {neuron_name} has no position defined!")
            return

        # ┌----------------------------------------------------------┐
        # │ 1.  FIRST REVEAL → force links OFF  (any game mode)      │
        # └----------------------------------------------------------┘
        if not self.visible_neurons:                       # very first neuron
            self.show_links = False
            if hasattr(self, 'parent') and hasattr(self.parent(), 'network_tab'):
                nt = self.parent().network_tab
                nt.checkbox_links.setChecked(False)
                nt.checkbox_links.setEnabled(False)      # user can’t turn it on

        # ---------- staggered start ----------
        stagger = 0.4
        delay = len(self.visible_neurons) * stagger

        self.visible_neurons.add(neuron_name)

        # Track this neuron as revealed for count display (tutorial only)
        if self.is_tutorial_mode:
            self.revealed_neurons.add(neuron_name)
            # Reveal connections between already-revealed neurons
            self._reveal_connections_for_neuron(neuron_name)

        # Trigger immediate metrics update to show new counts
        self._update_network_metrics()

        self.neuron_reveal_animations[neuron_name] = {
            'start_time': time.time() + delay,
            'progress': 0.0
        }

        pos = self.neuron_positions[neuron_name]
        # (any existing logging / diagnostics you had can stay here)

    def _enable_links_after_reveal(self):
        """Re-enable checkbox, tick it, and kick off the existing link-fade engine."""
        self.show_links = True
        
        # Populate link targets for all weights (like toggle_links does)
        for key in self.weights.keys():
            self._link_targets[key] = 1.0  # Target full opacity
            # Initialize opacity if not already set
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
        #print("🧠 All core neurons revealed")
    
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
    
    def _update_network_metrics(self):
        """Update the network tab metrics display"""
        try:
            # Try to get the parent window (SquidBrainWindow)
            parent = self.parent()
            if parent and hasattr(parent, 'network_tab'):
                parent.network_tab.update_metrics_display()
        except Exception as e:
            pass  # Silently fail if we can't update - not critical
    
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

    def add_weight_animation(self, neuron1, neuron2, old_weight, new_weight):
        """Add animation for a weight change without modifying the weight itself"""
        current_time = time.time()
        pair = (neuron1, neuron2)
        
        # Add to animations list
        self.weight_animations.append({
            'pair': pair,
            'start_time': current_time,
            'duration': 2.0,
            'start_weight': old_weight,
            'end_weight': new_weight,
            'neuron1': neuron1,
            'neuron2': neuron2,
            'color': (0, 255, 0) if new_weight > old_weight else (255, 0, 0),
            'pulse_speed': 0.5
        })
        
        # Record communication events
        self.weight_change_events[neuron1] = current_time
        self.weight_change_events[neuron2] = current_time
        
        # Add to recently updated pairs
        if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
        (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
            self.recently_updated_neuron_pairs.append((neuron1, neuron2))
        
        # ===== SUBTLE STYLE: Spawn communication glow on weight change =====
        if hasattr(self, 'anim_comm_glow_enabled') and self.anim_comm_glow_enabled:
            if hasattr(self, 'anim_comm_glow_spawn_on_weight_change') and self.anim_comm_glow_spawn_on_weight_change:
                # Spawn bidirectional glows for weight changes
                self._spawn_comm_glow(neuron1, neuron2)
                self._spawn_comm_glow(neuron2, neuron1)
        
        # ===== NEURAL STYLE: Spawn activation pulse on weight change =====
        if hasattr(self, 'anim_neural_pulse_enabled') and self.anim_neural_pulse_enabled:
            # Determine color based on weight change direction
            if new_weight > old_weight:
                color = self.anim_neural_pulse_colour_pos
            else:
                color = self.anim_neural_pulse_colour_neg
            self._spawn_neural_pulse(neuron1, neuron2, color)

    def is_neurogenesis_neuron(self, neuron_name: str) -> bool:
        """
        Check if a neuron was created through neurogenesis (and can be dragged).
        TO BE REMOVED IN FUTURE VERSION - depreceted
        """
        
        if not neuron_name:
            return False
        
        # Core neurons that should NOT be draggable
        if neuron_name in self.original_neurons:
            return False
        
        # ANY neuron not in original_neurons is draggable (including circular ones)
        return True

    def _periodic_neurogenesis_check(self):
        """Periodic check for neurogenesis triggers (every 2 seconds)."""
        if not hasattr(self, 'check_neurogenesis_triggers'):
            return
            
        # Skip if a check is already pending
        if self._pending_neurogenesis_check:
            return
        
        # Build state with context
        state_with_context = self.state.copy()

        # FIX: Ensure recent_actions is always a list before sending to worker
        if 'recent_actions' in state_with_context:
            if not isinstance(state_with_context['recent_actions'], list):
                state_with_context['recent_actions'] = []
        else:
            state_with_context['recent_actions'] = []
        
        # Add environmental data if available
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            logic = self.tamagotchi_logic
            if hasattr(logic, 'food_items'):
                state_with_context['food_count'] = len(logic.food_items)
            if hasattr(logic, 'poop_items'):
                state_with_context['poop_count'] = len(logic.poop_items)
            if hasattr(logic, 'squid'):
                state_with_context['carrying_rock'] = getattr(logic.squid, 'carrying_rock', False)
        
        # CRITICAL: Ensure cache is updated before queueing
        self._update_worker_cache()
        
        if self._use_threaded_processing and hasattr(self, 'brain_worker'):
            # Queue the work to the background thread
            self._pending_neurogenesis_check = True
            self.brain_worker.queue_neurogenesis_check(state_with_context)
        else:
            # Fallback: synchronous processing (original behavior)
            try:
                created = self.check_neurogenesis_triggers(state_with_context)
                if created:
                    print(f"✨ Neurogenesis triggered! New neuron created.")
            except Exception as e:
                print(f"⚠️ Neurogenesis check error: {e}")

    def toggle_pruning(self, enabled):
        """Enable or disable the pruning mechanisms for neurogenesis"""
        previous = self.pruning_enabled
        self.pruning_enabled = enabled

        if previous != enabled:
            print(f"\x1b[{'42' if enabled else '41'}mPruning {'enabled' if enabled else 'disabled'}\x1b[0m - Neurogenesis {'constrained' if enabled else 'unconstrained'}")

            if not enabled:
                print("\x1b[31mWARNING: Disabling pruning may lead to network instability\x1b[0m")

        return self.pruning_enabled
    
    def get_stress_neuron_count(self):
        """Counts the number of neurons that start with the name 'stress'."""
        return len([name for name in self.neuron_positions if name.startswith('stress')])

    def stop_hebbian_learning(self):
        """Stop Hebbian learning immediately"""
        self.learning_active = False
        self.hebbian_countdown_seconds = 0
        print("++ Hebbian learning stopped")

    def start_hebbian_learning(self, duration_seconds=30):
        """Start Hebbian learning with a specified duration"""
        self.hebbian_countdown_seconds = duration_seconds
        self.learning_active = True
        self.is_paused = False
        print(f"++ Hebbian learning started for {duration_seconds} seconds")

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

    def get_neuron_value(self, value):
        """
        Convert a neuron value to a numerical format for Hebbian learning.

        Args:
            value: The value of the neuron, which can be int, float, bool, or str.

        Returns:
            float: The numerical value of the neuron.
        """
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            # For string values (like 'direction'), return a default value
            return 75.0
        else:
            return 0.0
        
    def is_new_neuron(self, neuron_name, newness_duration_sec=300): # 300s = 5 minutes
        """Check if a neuron was created within the newness duration."""
        # Check if it's in the primary neurogenesis data
        if neuron_name in self.neurogenesis_data.get('new_neurons', []):
            details = self.neurogenesis_data.get('new_neurons_details', {}).get(neuron_name)
            if details:
                created_at = details.get('created_at')
                if created_at and (time.time() - created_at) < newness_duration_sec:
                    return True # It's new based on details
            else:
                 # If no details but in list, assume it might be new (fallback)
                 # You might want to refine this based on how 'new_neurons' is managed.
                 # For now, if it's in the list and < 5 mins, assume new.
                 # A better check is needed if 'new_neurons' isn't pruned.
                 # Let's rely *only* on details for a stricter check.
                 pass
        return False


    def update_connection(self, neuron1, neuron2, value1, value2):
        """Update connection weight and trigger animations"""
        current_time = time.time()
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)

        # Check if the pair or its reverse exists in weights, if not, initialize it
        if pair not in self.weights and reverse_pair not in self.weights:
            # Only add if both neurons exist
            if neuron1 in self.neuron_positions and neuron2 in self.neuron_positions:
                self.weights[pair] = 0.0  # Start with 0 weight
                print(f"      🆕 Created new connection: {neuron1} ↔ {neuron2}")
            else:
                print(f"      ⚠️  Cannot create connection: {neuron1} or {neuron2} doesn't exist in neuron_positions")
                return  # Don't create connection if a neuron doesn't exist

        # Use the correct pair order
        use_pair = pair if pair in self.weights else reverse_pair
        
        # Ensure the pair still exists before proceeding (might be pruned)
        if use_pair not in self.weights:
            print(f"      ⚠️  Connection was pruned, skipping update for {neuron1} ↔ {neuron2}")
            return

        prev_weight = self.weights[use_pair]

        # --- Learning Rate Calculation ---
        base_lr = self.learning_rate
        newness_boost = 2.0  # New neurons learn 2x faster
        effective_lr = base_lr

        is_n1_new = self.is_new_neuron(neuron1)
        is_n2_new = self.is_new_neuron(neuron2)

        if is_n1_new or is_n2_new:
            effective_lr = base_lr * newness_boost
        # --- End Learning Rate ---

        # Calculate weight change (basic Hebbian)
        weight_change = effective_lr * (value1 / 100.0) * (value2 / 100.0)
        
        # Add weight decay (optional but good for stability)
        decay_rate = self.config.hebbian.get('weight_decay', 0.01) * 0.1  # Slow decay during learning
        new_weight = prev_weight + weight_change - (prev_weight * decay_rate)
        
        # Clamp weight to [-1, 1] range
        new_weight = min(max(new_weight, -1.0), 1.0)
        self.weights[use_pair] = new_weight

        # Add animation using helper method
        self.add_weight_animation(neuron1, neuron2, prev_weight, new_weight)

        # Record weight change time for both neurons
        if abs(new_weight - prev_weight) > 0.001:  # Only if significant change
            self.weight_change_events[neuron1] = current_time
            self.weight_change_events[neuron2] = current_time
            
            # Add to recently updated for visualization/logging
            if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
            (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
                self.recently_updated_neuron_pairs.append((neuron1, neuron2))
            
            # Trigger visual update
            self.update()

        # Record communication time for both neurons
        self.communication_events[neuron1] = current_time
        self.communication_events[neuron2] = current_time

        # Debug output with color coding
        lr_indicator = " (\x1b[35mBOOSTED\x1b[0m)" if effective_lr > base_lr else ""
        direction = "\x1b[32m↑\x1b[0m" if new_weight > prev_weight else "\x1b[31m↓\x1b[0m"
        print(f"      \x1b[42mUpdated\x1b[0m {direction} {neuron1} ↔ {neuron2}: "
            f"\x1b[31m{prev_weight:.3f}\x1b[0m → \x1b[32m{new_weight:.3f}\x1b[0m "
            f"(Δ={weight_change:.3f}, LR={effective_lr:.3f}{lr_indicator})")

    def prune_weak_connections(self, threshold=0.05, min_age_sec=600): # Prune if < 0.05 abs weight & > 10 mins old
        """Removes connections with absolute weight below the threshold, ignoring new neurons."""
        if not self.pruning_enabled: # Respect the global pruning flag
            return 0

        current_time = time.time()
        to_delete = []

        # Iterate over a copy of keys to allow deletion during iteration
        for pair, weight in list(self.weights.items()):
            # Ensure pair is a valid tuple
            if not (isinstance(pair, tuple) and len(pair) == 2):
                # print(f"Skipping invalid weight key during pruning: {pair}") # Optional Debug
                continue

            neuron1, neuron2 = pair

            # Don't prune if either neuron is "new" (gives them time to establish)
            if self.is_new_neuron(neuron1, min_age_sec) or self.is_new_neuron(neuron2, min_age_sec):
                continue
            
            # Don't prune connections involving core/original neurons (optional, but safer)
            # if neuron1 in self.original_neuron_positions or neuron2 in self.original_neuron_positions:
            #    continue

            # Check if absolute weight is below the threshold
            if abs(weight) < threshold:
                to_delete.append(pair)

        for pair in to_delete:
            if pair in self.weights:
                del self.weights[pair]

        if len(to_delete) > 0:
            print(f"\x1b[33mPruned {len(to_delete)} weak connections (Threshold: {threshold}).\x1b[0m")
            self.update() # Update visualization if connections changed
        
        return len(to_delete) # Return how many were pruned


    def perform_hebbian_learning(self):
        """
        One full Hebbian update cycle.
        Queues work to background thread for non-blocking operation.
        """
        # Skip if already pending
        if self._pending_hebbian_learning:
            return
        
        # CRITICAL: Update cache BEFORE queueing work
        self._update_worker_cache()
        
        # Update worker cache with current data
        # self._update_worker_cache()  # Already called above
        
        if self._use_threaded_processing and hasattr(self, 'brain_worker') and self.brain_worker.isRunning():
            # Queue the work to the background thread
            self._pending_hebbian_learning = True
            self.brain_worker.queue_hebbian_learning()
        else:
            # Fallback: synchronous processing
            self._perform_hebbian_learning_sync()

    def _perform_hebbian_learning_sync(self):
        """Original synchronous Hebbian learning (fallback if threading disabled)."""
        from heapq import nlargest

        print(f"++ [Sync] Hebbian learning cycle triggered")

        COLORS = ["\033[96m", "\033[93m", "\033[95m", "\033[92m", "\033[94m"]
        RESET = "\033[0m"

        if not hasattr(self, 'weights'):
            self.weights = {}
        self.recently_updated_neuron_pairs.clear()

        neurons = [n for n in self.neuron_positions.keys() if n not in self.excluded_neurons]
        print(f"   [Sync] Neurons available: {len(neurons)}, Weights tracked: {len(self.weights)}")

        scored_pairs = []
        for i, n1 in enumerate(neurons):
            for n2 in neurons[i + 1:]:
                v1 = self.get_neuron_value(self.state.get(n1, 50))
                v2 = self.get_neuron_value(self.state.get(n2, 50))
                score = v1 + v2
                scored_pairs.append((score, n1, n2, v1, v2))

        top_k = self.config.neurogenesis.get('max_hebbian_pairs', 2)
        top_pairs = nlargest(top_k, scored_pairs)
        print(f"   [Sync] Top {top_k} pairs selected from {len(scored_pairs)} candidates")

        updated_pairs = []

        for _, n1, n2, v1, v2 in top_pairs:
            base_lr = self.learning_rate
            decay_rate = self.config.hebbian.get('weight_decay', 0.01)

            if self.is_new_neuron(n1) or self.is_new_neuron(n2):
                base_lr *= 2.0

            delta = base_lr * (v1 / 100.0) * (v2 / 100.0)

            pair = (n1, n2)
            reverse_pair = (n2, n1)
            use_pair = pair if pair in self.weights else reverse_pair

            if use_pair not in self.weights:
                print(f"   [Sync] Skipping pair {n1}-{n2}: not in weights dict")
                continue

            old_w = self.weights[use_pair]
            new_w = old_w + delta - (old_w * decay_rate)
            new_w = max(self.config.hebbian.get('min_weight', -1.0),
                        min(self.config.hebbian.get('max_weight', 1.0), new_w))

            self.weights[use_pair] = new_w
            self.add_weight_animation(n1, n2, old_w, new_w)
            updated_pairs.append((n1, n2))

        if updated_pairs:
            colored = []
            for i, (a, b) in enumerate(updated_pairs):
                color = COLORS[i % len(COLORS)]
                colored.append(f"{color}{a} ↔ {b}{RESET}")
            print("     Hebbian learning chosen pairs: " + "  ".join(colored))
        else:
            print("   [Sync] No pairs were updated this cycle")

        self.recently_updated_neuron_pairs = updated_pairs
        self.last_hebbian_time = time.time()
        self.update()


    def get_recently_updated_neurons(self):
        """Return the list of neuron pairs updated in the last learning cycle"""
        return self.recently_updated_neuron_pairs


    def resizeEvent(self, event):
        """Handle window resize events - startles squid and enforces minimum size"""
        super().resizeEvent(event)

        # Only trigger startle if we're actually resizing (not just moving)
        old_size = event.oldSize()
        if (old_size.isValid() and
            hasattr(self, 'tamagotchi_logic') and
            self.tamagotchi_logic):

            new_size = event.size()
            width_change = abs(new_size.width() - old_size.width())
            height_change = abs(new_size.height() - old_size.height())

            # Only startle if change is significant (>50px)
            if width_change > 50 or height_change > 50:
                # Check if first resize
                if not hasattr(self, '_has_resized_before'):
                    source = "first_resize"
                    self._has_resized_before = True
                else:
                    source = "window_resize"

                #self.tamagotchi_logic.startle_squid(source=source) #STARTLE WHEN WINDOW RESIZE

                if self.debug_mode:
                    print(f"Squid startled by {source}")

        # Enforce minimum window size (1280x900)
        min_width, min_height = 1280, 900
        if event.size().width() < min_width or event.size().height() < min_height:
            self.resize(
                max(event.size().width(), min_width),
                max(event.size().height(), min_height)
            )

    def closeEvent(self, event):
        """Handle window close event - save state and clean up resources"""
        # Stop the worker thread first
        self.stop_worker()
        
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            # Save current brain state
            try:
                brain_state = self.save_brain_state()
                with open('last_brain_state.json', 'w') as f:
                    json.dump(brain_state, f)
            except Exception as e:
                print(f"Error saving brain state: {e}")

            # Clean up timers
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.stop()
            if hasattr(self, 'countdown_timer'):
                self.countdown_timer.stop()
            if hasattr(self, 'memory_update_timer'):
                self.memory_update_timer.stop()

        # Close any child windows
        if hasattr(self, '_inspector') and self._inspector: 
            self._inspector.close()
            
        if hasattr(self, '_laboratory') and self._laboratory:
            self._laboratory.close()
        
        # Accept the close event 
        event.accept()

    def save_brain_state(self):
        return {
            'weights': self.weights,
            'neuron_positions': self.neuron_positions,
            'neuron_states': self.state
        }

    def load_brain_state(self, state):
        """Load the brain state from a saved state dictionary"""
        self.weights = state['weights']
        self.neuron_positions = state['neuron_positions']
        # Load neuron states, defaulting to empty dict if not present
        self.state = state.get('neuron_states', {})
        
        # NEW: Load layer structure if present (from custom brain designs)
        self.layers = state.get('layer_structure', [])

        # Ensure all neurons in neuron_positions exist in state
        for neuron in self.neuron_positions:
            if neuron not in self.state:
                # Initialize missing neurons with default value
                self.state[neuron] = 50  # Default activation value

        # Explicitly update excluded neurons if they exist in positions
        for neuron in self.excluded_neurons:
            if neuron in self.neuron_positions and neuron not in self.state:
                self.state[neuron] = False  # Default boolean state

        # Ensure visible_neurons is complete
        # For loaded games, ALL neurons should be visible (not just original_neurons)
        if not self.is_tutorial_mode:
            # Add all core neurons
            self.visible_neurons = set(self.original_neurons)
            # Also add any neurogenesis neurons from neuron_positions
            for neuron in self.neuron_positions:
                if neuron not in self.excluded_neurons and neuron not in self.original_neurons:
                    self.visible_neurons.add(neuron)
            print(f"📊 Loaded {len(self.neuron_positions)} neurons, {len(self.visible_neurons)} visible")



    def create_initial_state(self):
        """
        Create and return the initial brain state for a new game.
        Returns a dictionary with all core neurons set to their default values.
        Also resets animation tracking attributes.
        """
        # Reset animation tracking attributes
        self.reset_animation_state()
        
        initial_state = {
            "can_see_food": 0,
            "hunger": 50,
            "happiness": 50,
            "cleanliness": 50,
            "sleepiness": 50,
            "satisfaction": 50,
            "anxiety": 50,
            "curiosity": 50,
            "is_sick": False,
            "is_eating": False,
            "is_sleeping": False,
            "pursuing_food": False,
            "direction": "up",
            "position": (0, 0),
            "is_startled": False,
            "is_fleeing": False,
            'neurogenesis_active': True
        }
        return initial_state
    
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

    def initialize_connections(self):
        connections = []
        neurons = list(self.neuron_positions.keys())
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                connections.append((neurons[i], neurons[j]))
        return connections

    def initialize_weights(self):
        neurons = list(self.neuron_positions.keys())
        # Create sparse random connections (40% density)
        connection_probability = 0.4
        
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                if random.random() < connection_probability:
                    self.weights[(neurons[i], neurons[j])] = random.uniform(-1, 1)

    def get_neuron_count(self):
        """Returns the actual count of neurons in the network positions."""
        return len(self.neuron_positions)

    def get_edge_count(self):
        """Returns the actual count of connections (weights) in the network."""
        return len(self.weights) # MODIFIED: Use self.weights

    def get_weakest_connections(self, n=3):
        """Return the n weakest connections by absolute weight"""
        if not hasattr(self, 'weights') or not self.weights:
            return []

        sorted_weights = sorted(self.weights.items(), key=lambda x: abs(x[1]))
        return sorted_weights[:n]  # Returns list of ((source, target), weight) tuples

    def get_extreme_neurons(self, n=3):
        """Return neurons deviating most from baseline (50)"""
        neurons = [(k, v) for k, v in self.state.items()
                if isinstance(v, (int, float)) and k in self.neuron_positions]
        most_positive = sorted(neurons, key=lambda x: -x[1])[:n]
        most_negative = sorted(neurons, key=lambda x: x[1])[:n]
        return {'overactive': most_positive, 'underactive': most_negative}

    def get_unbalanced_connections(self, n=3):
        """Return connections with largest weight disparities"""
        unbalanced = []
        for (a, b), w1 in self.weights.items():
            w2 = self.weights.get((b, a), 0)
            if abs(w1 - w2) > 0.3:  # Only consider significant differences
                unbalanced.append(((a, b), (w1, w2), abs(w1 - w2)))
        return sorted(unbalanced, key=lambda x: -x[2])[:n]

    def calculate_network_health(self):
        """Calculate network health based on connection weights and neuron activity"""
        total_weight = sum(abs(w) for w in self.weights.values())
        avg_weight = total_weight / len(self.weights) if self.weights else 0
        health = min(100, max(0, avg_weight * 100))
        return health

    def calculate_network_efficiency(self):
        """Calculate network efficiency based on connection distribution"""
        if not self.connections:
            return 0
        reciprocal_count = 0
        for conn in self.connections:
            reverse_conn = (conn[1], conn[0])
            if reverse_conn in self.connections:
                reciprocal_count += 1
        efficiency = (reciprocal_count / len(self.connections)) * 100
        return efficiency

    def log_neurogenesis_event(self, neuron_name, event_type, reason=None, details=None):
        """Log neurogenesis events in a human-readable paragraph format."""
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = ""

        if event_type == "created" and details:
            neuron_type = details.get("trigger_type")
            trigger_value = details.get("trigger_value", 0.0)

            if not neuron_type:
                return # Cannot log without a neuron type

            # General creation message
            log_entry += f"{timestamp} - a {neuron_type.upper()} neuron ({neuron_name}) was created because {neuron_type} counter was {trigger_value:.2f}\n"

            # Specific details for stress neurons
            if neuron_type == "stress":
                log_entry += "An inhibitory connection was made to ANXIETY\n"
                log_entry += "Maximum anxiety value has been permanently reduced by 10\n"

        elif event_type == "pruned":
            # A more consistent format for pruned events
            timestamp_full = datetime.now().strftime("%H:%M:%S")
            log_entry = f"{timestamp_full} - a neuron ({neuron_name}) was PRUNED due to {reason if reason else 'unknown reason'}\n"

        if log_entry:
            try:
                with open('neurogenesis_log.txt', 'a', encoding='utf-8') as f:
                    f.write(log_entry)
                    # Always add the separator after an entry
                    f.write("\n-------------------------------\n\n")
            except Exception as e:
                print(f"\x1b[31mNeurogenesis logging failed: {str(e)}\x1b[0m")

    def update_state(self, new_state: Optional[Dict[str, float]] = None):
        """
        Update neuron activations based on connections and random noise,
        but also accept an external `new_state` dict to overwrite widget state.

        If `new_state` is provided, it will be merged into self.state with
        strict handling for binary neurons (keeps them 0 or 100). If None,
        the original neuron activation update logic runs (preserved below).
        """

        # If an external state is supplied, merge it and update bookkeeping
        if new_state is not None:
            # Merge incoming state into internal state with binary handling
            for k, v in (new_state.items() if isinstance(new_state, dict) else []):
                if k in self.neuron_positions and self.is_binary_neuron(k):
                    # Binary neurons must be exactly 0 or 100
                    if isinstance(v, bool):
                        self.state[k] = 100.0 if v else 0.0
                    elif isinstance(v, (int, float)):
                        self.state[k] = 100.0 if float(v) > 50.0 else 0.0
                    else:
                        # Preserve non-numeric values (fallback)
                        self.state[k] = v
                else:
                    # Non-binary neurons: store as-is (numeric/bool converted)
                    if isinstance(v, bool):
                        self.state[k] = 100.0 if v else 0.0
                    elif isinstance(v, (int, float)):
                        self.state[k] = float(v)
                    else:
                        self.state[k] = v

            # Update communication events (for glows/highlights)
            current_time = time.time()
            for neuron in list(self.state.keys()):
                if neuron not in self.communication_events:
                    self.communication_events[neuron] = 0
                neuron_value = self.get_neuron_value(self.state[neuron])
                if abs(neuron_value - 50) > 20:
                    self.communication_events[neuron] = current_time

            # Update functional neurons if neurogenesis system is present
            if hasattr(self, 'enhanced_neurogenesis') and getattr(self.enhanced_neurogenesis, 'functional_neurons', None):
                try:
                    self.enhanced_neurogenesis.update_neuron_activations(self.state)
                except Exception:
                    # Defensive: don't allow neurogenesis failures to crash update
                    pass

            # CRITICAL: After updating internal state, refresh worker cache
            if hasattr(self, 'brain_worker') and self.brain_worker:
                self._update_worker_cache()

            # Trigger a repaint to reflect new state
            self.update()
            return

        # -----------------------
        # Original internal logic
        # -----------------------
        # (Preserved exactly from the previous implementation:
        # update neuron activations based on self.neurons, connections, decay, noise.)
        # List of neurons that must stay strictly binary (0 or 100)
        BINARY_NEURONS = {"can_see_food"}

        updated = {}

        # First pass: calculate raw new activations
        for neuron, props in self.neurons.items():
            value = props.get('activation', 0.0)

            # Protect binary neurons from ANY modification
            if neuron in BINARY_NEURONS:
                updated[neuron] = value  # Keep EXACTLY 0 or 100
                continue

            # Standard neurons get noise & decay
            decay = props.get('decay', 1.0)
            noise = props.get('noise', 0.0)

            value *= decay
            value += random.uniform(-noise, noise)

            updated[neuron] = value

        # Second pass: apply connection effects
        for conn in self.connections:
            src = conn.get("from")
            dst = conn.get("to")
            weight = conn.get("weight", 0)

            # Defensive checks for keys
            if src not in updated or dst not in updated:
                # Skip if positions missing (pruned/unknown)
                continue

            # Skip binary neurons—they must not be influenced
            if dst in BINARY_NEURONS:
                continue

            try:
                updated[dst] += updated[src] * weight
            except Exception:
                # Defensive: skip malformed connections
                continue

        # Final pass: clamp values and write back
        for neuron, val in updated.items():

            # Binary neurons must remain 0 or 100 EXACTLY
            if neuron in BINARY_NEURONS:
                # Ensure it's exactly 0 or 100 (snap)
                snap = 100.0 if val > 50 else 0.0
                try:
                    self.neurons[neuron]["activation"] = snap
                except Exception:
                    # If neurons dict doesn't have the expected structure, store safely
                    if neuron in self.state:
                        self.state[neuron] = snap
                    else:
                        self.neurons.setdefault(neuron, {})['activation'] = snap
                continue

            clamped = max(min(val, 100), -100)
            # Write back to neurons dict if present, otherwise to state
            if isinstance(self.neurons.get(neuron, {}).get('activation', None), (int, float)):
                self.neurons[neuron]['activation'] = clamped
            else:
                # Fallback to self.state
                self.state[neuron] = clamped

        # Also add cache update at the end if state changed
        state_changed = bool(updated)  # Simple check - True if any neurons updated
        if state_changed and hasattr(self, 'brain_worker') and self.brain_worker:
            self._update_worker_cache()


    def _fast_apply_external_state(self, new_state):
        """Quickly apply externally provided state (plugin updates, etc.)"""
        for k, v in new_state.items():
            if k in self.neuron_positions:
                if self.is_binary_neuron(k):
                    self.state[k] = 100.0 if (v if isinstance(v, bool) else float(v) > 50) else 0.0
                else:
                    self.state[k] = float(v) if isinstance(v, (int, float, bool)) else v
        
        # Update communication events for glow effects
        current_time = time.time()
        for neuron, val in self.state.items():
            if isinstance(val, (int, float)) and abs(val - 50) > 20:
                self.communication_events[neuron] = current_time
        
        self.update()

    def _perform_state_update_sync(self):
        """Synchronous fallback when worker is unavailable"""
        import random
        
        updated = {}
        BINARY_NEURONS = {"can_see_food"}
        
        # First pass: decay and noise
        for neuron, props in self.neurons.items():
            if neuron in self.excluded_neurons:
                continue
            value = props.get('activation', 0)
            decay = props.get('decay', 1.0)
            noise = props.get('noise', 0.0)
            value *= decay
            value += random.uniform(-noise, noise)
            updated[neuron] = value
        
        # Second pass: connection effects
        for conn in self.connections:
            src = conn.get("from")
            dst = conn.get("to")
            weight = conn.get("weight", 0)
            if src in updated and dst in updated:
                updated[dst] += updated[src] * weight
        
        # Final pass: clamping
        for neuron, val in updated.items():
            if neuron in BINARY_NEURONS:
                updated[neuron] = 100.0 if val > 50 else 0.0
            else:
                updated[neuron] = max(min(val, 100), -100)
        
        self.state.update(updated)
        self.update()


    def provide_outcome_feedback(self, outcome_value: float):
        """
        Provide feedback to recently activated neurons.
        outcome_value: 1.0 = very positive, 0.0 = neutral, -1.0 = very negative
        """
        if not hasattr(self, 'enhanced_neurogenesis'):
            return
        
        current_time = time.time()
        
        # Update utility scores for recently active neurons
        for name, func_neuron in self.enhanced_neurogenesis.functional_neurons.items():
            # Was this neuron recently active?
            # Check if func_neuron has the last_activated attribute (for FunctionalNeuron objects)
            if hasattr(func_neuron, 'last_activated') and current_time - func_neuron.last_activated < 30:  # 30 seconds
                if hasattr(func_neuron, 'update_utility_score'):
                    func_neuron.update_utility_score(outcome_value)


    
    
    def check_neurogenesis_triggers(self, state):
        """Enhanced neurogenesis check with proper trigger priority"""
        if not state.get('neurogenesis_active', True):
            return False
        
        # Build experience context
        recent_actions = state.get('recent_actions', [])
        environment = {
            'food_count': state.get('food_count', 0),
            'poop_count': state.get('poop_count', 0),
            'has_rock': state.get('carrying_rock', False)
        }
        
        # ===== FIX: PROPER TRIGGER PRIORITY WITH EMERGENCY OVERRIDE =====
        trigger_type = None
        
        # 🚨 HIGHEST PRIORITY: Emergency stress (overrides everything)
        if state.get('anxiety', 50) >= 95:
            trigger_type = 'stress'
            print(f"🚨 EMERGENCY: Critical anxiety level ({state.get('anxiety', 50):.1f})!")
        
        # HIGH PRIORITY: Stress (anxiety or sustained stress)
        elif state.get('anxiety', 50) > 75 or state.get('sustained_stress', 0) > 1:
            trigger_type = 'stress'
        
        # MEDIUM PRIORITY: Novelty (curiosity or new objects)
        elif state.get('curiosity', 50) > 70 or state.get('novelty_exposure', 0) > 2:
            trigger_type = 'novelty'
        
        # LOW PRIORITY: Reward (satisfaction or positive outcomes)
        elif state.get('satisfaction', 50) > 70 or state.get('recent_rewards', 0) > 2:
            trigger_type = 'reward'
        # ================================================================
        
        if trigger_type:
            # Capture full experience context
            context = self.enhanced_neurogenesis.capture_experience_context(
                trigger_type=trigger_type,
                brain_state=self.state,
                recent_actions=recent_actions,
                environment=environment
            )
            
            # Add to experience buffer
            self.experience_buffer.add_experience(context)
            
            # Check if we should create a neuron
            if self.enhanced_neurogenesis.should_create_neuron(context):
                neuron_name = self.enhanced_neurogenesis.create_functional_neuron(context)
                
                if neuron_name and self.pruning_enabled:
                    # Check if we need to prune
                    current_count = len(self.neuron_positions) - len(self.excluded_neurons)
                    max_neurons = self.neurogenesis_config.get('max_neurons', 32)
                    
                    if current_count > max_neurons * 0.85:
                        self.enhanced_neurogenesis.intelligent_pruning()
                
                return neuron_name is not None
        
        return False

    def get_neurogenesis_threshold(self, trigger_type):
        """Safely get threshold for a trigger type with fallback defaults"""
        try:
            return self.neurogenesis_config['triggers'][trigger_type]['threshold']
        except KeyError:
            defaults = {'novelty': 0.7, 'stress': 0.8, 'reward': 0.6}
            return defaults.get(trigger_type, 1.0)

    def stimulate_brain(self, stimulation_values):
        """Handle brain stimulation with validation"""
        if not isinstance(stimulation_values, dict):
            return
        filtered_update = {}
        for key in self.state.keys():
            if key in stimulation_values:
                filtered_update[key] = stimulation_values[key]
        self.update_state(filtered_update)

    def get_adjusted_threshold(self, base_threshold, trigger_type):
        """Scale threshold based on network size to prevent runaway neurogenesis"""
        original_count = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        new_neuron_count = current_count - original_count
        baseline = original_count + 3
        if new_neuron_count <= 0 or current_count <= baseline:
            return base_threshold
        scaling_factors = {'novelty': 0.25, 'stress': 0.1, 'reward': 0.08}
        scaling_factor = scaling_factors.get(trigger_type, 0.15)
        multiplier = 1.0 + (scaling_factor * (new_neuron_count - baseline + 1))
        adjusted = base_threshold * multiplier
        return adjusted

    def prune_weak_neurons(self):
        """Remove weakly connected or inactive neurons to maintain network stability"""
        min_neurons = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        if current_count <= min_neurons:
            return False

        candidates = []
        for neuron in list(self.neuron_positions.keys()):
            if neuron in self.original_neuron_positions or neuron in self.excluded_neurons:
                continue
            connections = [abs(w) for (a, b), w in self.weights.items() if (a == neuron or b == neuron)]
            activity = self.state.get(neuron, 0)
            activity_score = 0 if isinstance(activity, bool) else abs(activity - 50)
            if not connections or sum(connections) / len(connections) < 0.2:
                candidates.append((neuron, 1))
            elif activity_score < 10:
                candidates.append((neuron, 2))
        candidates.sort(key=lambda x: x[1])

        if candidates:
            neuron_to_remove = candidates[0][0]
            if neuron_to_remove in self.neuron_positions: del self.neuron_positions[neuron_to_remove]
            if neuron_to_remove in self.state: del self.state[neuron_to_remove]
            for conn in list(self.weights.keys()):
                if isinstance(conn, tuple) and (conn[0] == neuron_to_remove or conn[1] == neuron_to_remove):
                    del self.weights[conn]
            if neuron_to_remove in self.neurogenesis_data.get('new_neurons', []):
                self.neurogenesis_data['new_neurons'].remove(neuron_to_remove)
            reason = "weak connections/activity"
            self.log_neurogenesis_event(neuron_to_remove, "pruned", reason)
            return True
        return False

    def apply_repulsion_force(self, iterations=15, strength=0.6, threshold=120.0):
        """Applies a repulsion force between nearby neurons to spread them out."""

        neuron_list = [name for name in self.neuron_positions.keys() if name not in self.excluded_neurons]

        for _ in range(iterations):
            displacements = {name: [0.0, 0.0] for name in neuron_list}

            for i in range(len(neuron_list)):
                for j in range(i + 1, len(neuron_list)):
                    neuron1 = neuron_list[i]
                    neuron2 = neuron_list[j]

                    pos1 = self.neuron_positions[neuron1]
                    pos2 = self.neuron_positions[neuron2]

                    dx = pos1[0] - pos2[0]
                    dy = pos1[1] - pos2[1]

                    distance_sq = dx*dx + dy*dy

                    if 0 < distance_sq < threshold*threshold:
                        distance = math.sqrt(distance_sq)
                        force = strength * (threshold - distance) / distance
                        move_x = (dx / distance) * force
                        move_y = (dy / distance) * force
                        displacements[neuron1][0] += move_x
                        displacements[neuron1][1] += move_y
                        displacements[neuron2][0] -= move_x
                        displacements[neuron2][1] -= move_y

            damping = 0.5
            moved = False
            for name in neuron_list:
                if name in self.original_neuron_positions:
                   continue

                pos = self.neuron_positions[name]
                disp = displacements[name]

                if abs(disp[0]) > 0.1 or abs(disp[1]) > 0.1:
                    new_x = pos[0] + disp[0] * damping
                    new_y = pos[1] + disp[1] * damping
                    new_x = max(50, min(974, new_x))
                    new_y = max(50, min(668, new_y))
                    self.neuron_positions[name] = (new_x, new_y)
                    moved = True

            if not moved:
                break
        if moved:
           self.update()

    def update_weights(self):
        """
        Update weights by adding small random noise. 
        WARNING: This adds noise and might counteract Hebbian learning.
        """
        if self.frozen_weights is not None:
            return

        # --- MODIFIED: Iterate over a copy of the actual weight keys ---
        for conn in list(self.weights.keys()):
            # Check if the connection still exists (it might be pruned concurrently)
            if conn in self.weights:
                # Add a very small amount of noise/drift
                self.weights[conn] += random.uniform(-0.01, 0.01) # Reduced noise
                # Clamp the weight to stay within [-1, 1]
                self.weights[conn] = max(-1, min(1, self.weights[conn]))

    def freeze_weights(self):
        self.frozen_weights = self.weights.copy()

    def unfreeze_weights(self):
        self.frozen_weights = None

    def strengthen_connection(self, neuron1, neuron2, amount):
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)
        if pair not in self.weights and reverse_pair not in self.weights:
            self.weights[pair] = 0.0
        use_pair = pair if pair in self.weights else reverse_pair
        self.weights[use_pair] += amount
        self.weights[use_pair] = max(-1, min(1, self.weights[use_pair]))
        self.update()

    def capture_training_data(self, state):
        training_sample = [state[neuron] for neuron in self.neuron_positions.keys()]
        self.training_data.append(training_sample)
        print("Captured training data:", training_sample)

    def train_hebbian(self):
        print("Starting Hebbian training...")
        for sample in self.training_data:
            for i in range(len(sample)):
                for j in range(i+1, len(sample)):
                    self.associations[i][j] += self.learning_rate * sample[i] * sample[j]
                    self.associations[j][i] = self.associations[i][j]
        self.training_data = []

    def get_association_strength(self, neuron1, neuron2):
        idx1 = list(self.neuron_positions.keys()).index(neuron1)
        idx2 = list(self.neuron_positions.keys()).index(neuron2)
        return self.associations[idx1][idx2]
    
    def draw_layers(self, painter, scale):
        """Draw background rectangles for custom layers (matches BrainDesigner)."""
        if not self.layers:                       # ← already stored by load_brain_state
            return

        for layer in self.layers:
            y_pos   = layer.get('y_position', 0)
            name    = layer.get('name', 'Layer')
            l_type  = layer.get('layer_type', 'hidden')

            # ---- same metrics as BrainDesigner ----
            rect_height = 120
            rect_top    = y_pos - rect_height / 2
            rect_left   = -200
            rect_width  = 2000

            # ---- same colours / alpha ----
            if l_type == 'input':
                color = QtGui.QColor(200, 255, 200, 80)
                border_color = QtGui.QColor(150, 220, 150, 120)
            elif l_type == 'output':
                color = QtGui.QColor(255, 200, 200, 80)
                border_color = QtGui.QColor(220, 150, 150, 120)
            else:   # hidden
                color = QtGui.QColor(230, 230, 255, 80)
                border_color = QtGui.QColor(200, 200, 240, 120)

            # ---- filled background ----
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(QtCore.QRectF(rect_left, rect_top,
                                         rect_width, rect_height))

            # ---- top & bottom border lines ----
            painter.setPen(QtGui.QPen(border_color, 2))
            painter.drawLine(QtCore.QLineF(rect_left, rect_top,
                                         rect_left + rect_width, rect_top))
            painter.drawLine(QtCore.QLineF(rect_left, rect_top + rect_height,
                                         rect_left + rect_width, rect_top + rect_height))

            # ---- layer label ----
            font = painter.font()
            font.setPointSize(int(10 * scale))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(100, 100, 120))
            painter.drawText(QtCore.QPointF(10, rect_top + 20),
                           f"{name} ({l_type})")

    def draw_connections(self, painter, scale):
        """Draw connections with extended 2-second weight-change animations.
        Links are forced INVISIBLE while core neurons are still being revealed."""
        if not self.show_links:
            return

        # ===== PERFORMANCE FIX: Skip if widget is hidden =====
        if not self.isVisible():
            return

        # ===== PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE:
            _conn_start = time.perf_counter()

        # absolutely no connections until every core neuron is completely revealed (tutorial mode guard). 
        if self.is_tutorial_mode and len(self.visible_neurons) < len(self.original_neurons):
            return
        
        # ===== NEURAL STYLE: Use dedicated neural renderer =====
        if self.anim_neural_pulse_enabled:
            self._draw_neural_connections(painter, scale)
            return

        current_time = time.time()
        connections_drawn = 0
        connections_skipped = 0

        for key, weight in self.weights.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            source, target = key

            # skip tutorial-only connections when not in tutorial
            tutorial_mode = getattr(self.parent(), 'tutorial_active', False)
            is_tutorial_conn = (source.startswith('tutorial_neuron_') or
                                target.startswith('tutorial_neuron_'))
            if is_tutorial_conn and not tutorial_mode:
                continue

            # skip if either neuron is still revealing (tutorial safety)
            if self.is_tutorial_mode and (
                    not self.is_neuron_revealed(source) or
                    not self.is_neuron_revealed(target)):
                connections_skipped += 1
                continue

            if (source not in self.neuron_positions or
                target not in self.neuron_positions or
                source in self.excluded_neurons or
                target in self.excluded_neurons):
                continue

            # skip connections involving non-visible core neurons (tutorial)
            if self.is_tutorial_mode:
                if source in self.original_neurons and source not in self.visible_neurons:
                    connections_skipped += 1
                    continue
                if target in self.original_neurons and target not in self.visible_neurons:
                    connections_skipped += 1
                    continue

            start = self.neuron_positions[source]
            end   = self.neuron_positions[target]
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point   = QtCore.QPointF(float(end[0]),   float(end[1]))

            # special styling:  Stress ↔ Anxiety  (uses animation style params)
            is_stress_to_anxiety = (
                (source.lower().startswith('stress') and target.lower() == 'anxiety') or
                (target.lower().startswith('stress') and source.lower() == 'anxiety'))
            if is_stress_to_anxiety:
                pen = QtGui.QPen(QtGui.QColor(*self.anim_stress_colour))
                pen.setWidth(int(self.anim_stress_width))
                if self.anim_stress_dashed:
                    pen.setStyle(QtCore.Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(start_point, end_point)
                continue   # skip default drawing for this pair

            # default appearance (uses animation style params)
            anim_weight = weight
            base_width  = self.anim_line_base_width * scale
            line_width  = base_width
            pen_style   = QtCore.Qt.SolidLine
            animating   = False
            pulse_progress = 0.0

            # check for active weight-change animations (2-second window)
            for anim in self.weight_animations:
                if anim['pair'] == key:
                    elapsed = current_time - anim['start_time']
                    if elapsed < anim['duration']:
                        progress = elapsed / anim['duration']
                        anim_weight = anim['start_weight'] + progress * (
                            anim['end_weight'] - anim['start_weight'])

                        # growing / shrinking line width
                        if progress < 0.5:
                            line_width = base_width + (6.0 * scale * progress * 2)
                        else:
                            line_width = base_width + (6.0 * scale * (1 - progress) * 2)

                        pulse_progress = progress * anim['pulse_speed']
                        animating = True
                        break

            # colour & alpha
            if animating:
                r, g, b = anim['color']
                alpha = int(255 * (1 - pulse_progress ** 2))
                color = QtGui.QColor(r, g, b, alpha)
            else:
                base_alpha = int(self._link_opacities.get(key, 0.0) * 255)
                
                # ===== VIBRANT STYLE: Apply ambient pulse =====
                if self.anim_ambient_pulse_enabled and base_alpha > 0:
                    pulse_state = self._get_or_create_ambient_pulse(key)
                    phase = pulse_state['phase']
                    
                    # Sinusoidal oscillation (0 to 1 range)
                    pulse_factor = (math.sin(phase) + 1.0) / 2.0
                    
                    # Interpolate width
                    w_min, w_max = self.anim_ambient_pulse_width_range
                    width_mult = w_min + pulse_factor * (w_max - w_min)
                    line_width = base_width * width_mult
                    
                    # Interpolate alpha
                    a_min, a_max = self.anim_ambient_pulse_alpha_range
                    pulse_alpha = int(a_min + pulse_factor * (a_max - a_min))
                    # Combine with base opacity
                    final_alpha = int((base_alpha / 255.0) * pulse_alpha)
                    
                    if weight > 0:
                        color = QtGui.QColor(self.anim_line_col_pos[0], 
                                           self.anim_line_col_pos[1], 
                                           self.anim_line_col_pos[2], final_alpha)
                    else:
                        color = QtGui.QColor(self.anim_line_col_neg[0], 
                                           self.anim_line_col_neg[1], 
                                           self.anim_line_col_neg[2], final_alpha)
                else:
                    # Standard coloring (classic style or opacity 0)
                    color = (QtGui.QColor(0, int(255 * abs(weight)), 0, base_alpha) if weight > 0 else
                            QtGui.QColor(int(255 * abs(weight)), 0, 0, base_alpha))

            # line style
            if is_tutorial_conn and tutorial_mode:
                color = QtGui.QColor(255, 255, 0, 180)
                line_width = 3
                pen_style = QtCore.Qt.DashLine
            else:
                pen_style = (QtCore.Qt.DashLine if weight < 0 else
                            QtCore.Qt.SolidLine)
                if abs(anim_weight) < 0.1:
                    pen_style = QtCore.Qt.DotLine

            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start_point, end_point)

            # pulse circle travelling along the wire (uses animation style params)
            if self.anim_pulse_enabled and animating and pulse_progress < 1.0:
                pulse_pos = pulse_progress
                pulse_x = start_point.x() + pulse_pos * (end_point.x() - start_point.x())
                pulse_y = start_point.y() + pulse_pos * (end_point.y() - start_point.y())
                pulse_size = self.anim_pulse_diameter * scale * (1 - pulse_progress ** 2)

                painter.setBrush(QtGui.QBrush(QtGui.QColor(*self.anim_pulse_colour, self.anim_pulse_alpha)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(pulse_x, pulse_y),
                                    pulse_size, pulse_size)

            # glow around the line (uses animation style params)
            if self.anim_glow_enabled and animating and progress < self.anim_glow_fade_threshold:
                glow_progress = progress / self.anim_glow_fade_threshold
                glow_width = line_width + 4 * scale * (1 - glow_progress)
                glow_color = QtGui.QColor(*self.anim_glow_colour, self.anim_glow_alpha)
                painter.setPen(QtGui.QPen(glow_color, glow_width, pen_style))
                painter.drawLine(start_point, end_point)
            
            # ===== SUBTLE STYLE: Draw communication glow packets =====
            if self.anim_comm_glow_enabled:
                self._draw_comm_glows_for_connection(
                    painter, scale, key, start_point, end_point
                )

            # weight text (optional)
            if self.show_weights and abs(weight) > 0.1:
                midpoint = QtCore.QPointF((start_point.x() + end_point.x()) / 2,
                                        (start_point.y() + end_point.y()) / 2)
                text_area_width  = 80.0 * scale
                text_area_height = 22.0 * scale
                font = painter.font()
                font.setPointSize(max(8, int(8 * scale)))
                painter.setFont(font)
                rect = QtCore.QRectF(midpoint.x() - text_area_width / 2,
                                    midpoint.y() - text_area_height / 2,
                                    text_area_width, text_area_height)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawRect(rect)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
                painter.drawText(rect, QtCore.Qt.AlignCenter, f"{weight:.2f}")

            connections_drawn += 1

        # debug guard: warn only when something looks wrong
        if connections_drawn == 0 and len(self.weights) > 0:
            print(f"🔴 NO CONNECTIONS DRAWN! tutorial_mode={self.is_tutorial_mode}, "
                f"visible_neurons={len(self.visible_neurons)}, original_neurons={len(self.original_neurons)}, "
                f"total_weights={len(self.weights)}, skipped={connections_skipped}")
        
        # ===== END PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE:
            _conn_elapsed = (time.perf_counter() - _conn_start) * 1000
            perf_tracker.record("draw_connections", _conn_elapsed)

    def _get_logical_coords(self, widget_pos):
        """Maps widget QPoint/QPointF to logical neuron coordinates."""
        indicator_space = 60
        base_width_logical = 1024
        base_height_logical = 768 - indicator_space
        scale_x = self.width() / base_width_logical
        scale_y = (self.height() - indicator_space) / base_height_logical
        scale = min(scale_x, max(0.1, scale_y))
        translate_y = indicator_space
        lx = widget_pos.x() / scale
        ly = (widget_pos.y() - translate_y) / scale
        return QtCore.QPointF(lx, ly)

    def get_neuron_at_pos(self, widget_pos):
        """Finds a neuron at the given QPoint widget coordinates."""
        logical_pos = self._get_logical_coords(widget_pos)
        neuron_radius = 50  # Increased to 50 for better click detection on all neurons
        for name, pos in self.neuron_positions.items():
            dist_sq = (logical_pos.x() - pos[0])**2 + (logical_pos.y() - pos[1])**2
            if dist_sq <= neuron_radius**2:
                return name
        return None


    # ------------------------------------------------------------------
    # Binary neuron detection
    # ------------------------------------------------------------------
    def is_binary_neuron(self, name: str) -> bool:
        """Neurons that are strictly on/off (not continuous stats)."""
        return name in {
            'can_see_food', 'is_eating', 'is_sleeping', 'is_sick',
            'pursuing_food', 'is_fleeing', 'is_startled',
            'external_stimulus', 'plant_proximity'
        }

    # ------------------------------------------------------------------

    def paintEvent(self, event):
        # ===== PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE:
            _paint_start = time.perf_counter()
            perf_tracker.increment("paint_calls")

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)

        # Fill background (uses animation style color)
        bg_color = QtGui.QColor(*self.anim_background_colour)
        painter.fillRect(self.rect(), bg_color)

        # HIDDEN: Deprecated State indicator pills (functionality retained, display disabled)
        indicator_y_position = 10
        indicator_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        painter.setFont(indicator_font)
        font_metrics = painter.fontMetrics()

        active_indicators_data = []
        if self.state.get('is_fleeing', False): 
            active_indicators_data.append({"text": "Fleeing!", "color": QtGui.QColor(220, 20, 60)})
        if self.state.get('is_startled', False): 
            active_indicators_data.append({"text": "Startled!", "color": QtGui.QColor(255, 165, 0)})
        if self.state.get('pursuing_food', False): 
            active_indicators_data.append({"text": "Pursuing Food", "color": QtGui.QColor(60, 179, 113)})

        status_value = self.state.get('status', '')
        squid_status = str(status_value).lower() if status_value is not None else ''
        if self.state.get('is_eating', False) or 'eating' in squid_status:
            active_indicators_data.append({"text": "Eating", "color": QtGui.QColor(46, 204, 113)})
        if self.state.get('is_sleeping', False):
            active_indicators_data.append({"text": "Sleeping", "color": QtGui.QColor(142, 68, 173)})
        if 'rock' in squid_status or 'play' in squid_status:
            active_indicators_data.append({"text": "Playing", "color": QtGui.QColor(241, 196, 15)})
        if 'hiding' in squid_status:
            active_indicators_data.append({"text": "Hiding", "color": QtGui.QColor(22, 160, 133)})
        if self.state.get('anxiety', 0) > 70 or 'anxious' in squid_status:
            active_indicators_data.append({"text": "Anxious", "color": QtGui.QColor(231, 76, 60)})
        if self.state.get('curiosity', 0) > 80 or 'curious' in squid_status:
            active_indicators_data.append({"text": "Curious", "color": QtGui.QColor(52, 152, 219)})

        indicators_to_display = active_indicators_data[:3]

        painter.save()

        # Calculate space - no indicators displayed, so no space needed
        fixed_indicator_area_height = 0
        indicator_space_at_top = indicator_y_position + fixed_indicator_area_height

        base_width_logical = 1024
        base_height_logical = 768 - indicator_space_at_top
        if base_height_logical <= 0: 
            base_height_logical = 1

        scale_x = self.width() / base_width_logical
        drawable_height_for_neurons = self.height() - indicator_space_at_top
        if drawable_height_for_neurons <= 0: 
            drawable_height_for_neurons = 1

        scale_y = drawable_height_for_neurons / base_height_logical
        scale_y = max(0.01, scale_y)

        scale = max(0.01, min(scale_x, scale_y))

        # Center horizontally if letterboxed
        offset_x = 0
        if scale_x > scale_y:
            content_width = base_width_logical * scale
            offset_x = (self.width() - content_width) / 2

        painter.translate(offset_x, indicator_space_at_top)
        painter.scale(scale, scale)

        # === DRAW LAYERS ===
        self.draw_layers(painter, 1.0)

        # === DRAW NEURONS (with hover value label) ===
        current_time = time.time()

        for name, pos in self.neuron_positions.items():
            x_logical, y_logical = pos
            x = x_logical
            y = y_logical

            value = self.state.get(name, 50.0)
            if not isinstance(value, (int, float)):
                value = 50.0

            # === HOVER VALUE LABEL
            if getattr(self, 'hovered_neuron', None) == name and getattr(self, 'hover_value_display_active', False):
                
                if name == 'can_see_food':
                    value_str = "ON" if value > 50 else "OFF"
                else:
                    value_str = f"{value:.1f}"

                # Smooth fade-in
                elapsed = current_time - getattr(self, 'hover_animation_time', current_time)
                opacity = min(1.0, elapsed * 5.0)  # Fast fade-in (200ms)

                label_y = y - 50  # Position above neuron

                font = QtGui.QFont("Arial", 16, QtGui.QFont.Bold)
                painter.setFont(font)
                fm = painter.fontMetrics()
                text_width = fm.horizontalAdvance(value_str)

                padding = 12
                badge_width = text_width + 2 * padding
                badge_height = fm.height() + 12

                badge_rect = QtCore.QRectF(
                    x - badge_width / 2,
                    label_y - badge_height / 2,
                    badge_width,
                    badge_height
                )

                # Background badge (dark semi-transparent)
                bg_color = QtGui.QColor(0, 0, 0, int(220 * opacity))
                border_color = QtGui.QColor(100, 255, 150, int(255 * opacity))
                painter.setBrush(QtGui.QBrush(bg_color))
                painter.setPen(QtGui.QPen(border_color, 3))
                painter.drawRoundedRect(badge_rect, 12, 12)

                # Value text
                text_color = QtGui.QColor(255, 255, 255, int(255 * opacity))
                painter.setPen(text_color)
                painter.drawText(badge_rect, QtCore.Qt.AlignCenter, value_str)

                # Optional: subtle pulse glow under the badge
                if opacity > 0.8:
                    pulse = 0.5 + 0.5 * math.sin(elapsed * 10)
                    glow_alpha = int(60 * pulse * opacity)
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(100, 255, 150, glow_alpha)))
                    painter.setPen(QtCore.Qt.NoPen)
                    painter.drawEllipse(QtCore.QPointF(x, y), 30, 30)

            # Continue with normal neuron drawing (your existing method)
            self.draw_neurons(painter, 1.0)  # This will draw the actual neuron

        # === DRAGGING INDICATOR ===
        if self.dragging and self.dragged_neuron:
            pos = self.neuron_positions.get(self.dragged_neuron, (0, 0))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3 / scale))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]), 30, 30)

        # === NEUROGENESIS HIGHLIGHTS ===
        self.draw_neurogenesis_highlights(painter, 1.0)

        # === CONNECTIONS ===
        if self.show_links:
            self.draw_connections(painter, 1.0)

        # === STRENGTH MULTIPLIERS ===
        self.draw_strength_multiplier(painter, 1.0)

        painter.restore()

        # === TUTORIAL GLOW OVERLAY (full-screen pulse) ===
        if self.tutorial_glow_active:
            painter.save()
            glow_color = QtGui.QColor(48, 197, 255)
            alpha = int(100 * self._tutorial_glow_opacity)
            glow_color.setAlpha(alpha)
            painter.setBrush(glow_color)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(0, 0, self.width(), self.height())
            painter.restore()

        # ===== END PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE:
            _paint_elapsed = (time.perf_counter() - _paint_start) * 1000
            perf_tracker.record("paint_event", _paint_elapsed)

    def draw_neurons(self, painter, scale=1.0):
        """Main neuron drawing routine."""
        # ------------------------------------------------------------------
        # Explicit list of true binary (on/off) neurons
        # ------------------------------------------------------------------
        BINARY_NEURONS = {
            "can_see_food", "is_eating", "is_sleeping",
            "is_sick", "is_fleeing", "pursuing_food", "is_startled",
        }

        label_font = QtGui.QFont("Arial", int(self.base_font_size * scale))
        label_font.setBold(True)
        painter.setFont(label_font)
        font_metrics = painter.fontMetrics()

        for name, pos in self.neuron_positions.items():
            if name not in self.visible_neurons and not self.is_tutorial_mode:
                continue
            if name in self.excluded_neurons:
                continue

            x_logical, y_logical = pos
            x = x_logical * scale
            y = y_logical * scale
            radius = 20 * scale

            # ------------------------------------------------------------------
            # 1. HANDLE BINARY NEURONS (ALWAYS SQUARES, RED/GREEN)
            # ------------------------------------------------------------------
            if name in BINARY_NEURONS or name == "can_see_food":
                # Calculate Value
                raw_value = self.state.get(name, 0)
                
                if name == "can_see_food":
                    # Real-time vision check
                    if (hasattr(self, "tamagotchi_logic") and
                        self.tamagotchi_logic and
                        self.tamagotchi_logic.squid):
                        sees_food = bool(self.tamagotchi_logic.squid.get_visible_food())
                        value = 100.0 if sees_food else 0.0
                    else:
                        value = 100.0 if float(raw_value) > 50 else 0.0
                else:
                    value = 100.0 if float(raw_value) > 50 else 0.0

                # Determine Color (Red/Green)
                is_active = value > 50
                color = QtGui.QColor(0, 255, 0) if is_active else QtGui.QColor(255, 0, 0)

                # Draw Square
                painter.setBrush(QtGui.QBrush(color))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
                
                # Draw centered square
                size = radius * 1.8  # Slight adjustment to visually match circle size
                painter.drawRect(QtCore.QRectF(x - size/2, y - size/2, size, size))

                # Draw Label
                self._draw_standard_label(painter, x, y, radius, name, scale, font_metrics)
                continue

            # ------------------------------------------------------------------
            # 2. HANDLE CUSTOM SHAPES (Neurogenesis Neurons)
            # ------------------------------------------------------------------
            shape = self.neuron_shapes.get(name, 'circle')
            
            if shape != 'circle':
                if shape == 'diamond':
                    self.draw_diamond_neuron(painter, x, y, radius, name, scale)
                elif shape == 'square':
                    self.draw_square_neuron(painter, x, y, radius, name, scale)
                elif shape == 'triangle':
                    self.draw_triangular_neuron(painter, x, y, radius, name, scale)
                else:
                    self.draw_circular_neuron(painter, x, y, 0, name, scale)
                continue

            # ------------------------------------------------------------------
            # 3. STANDARD CIRCLE DRAWING (Continuous Core Neurons)
            # ------------------------------------------------------------------
            raw_value = self.state.get(name, 0)
            value = float(raw_value) if isinstance(raw_value, (int, float, bool)) else 50.0
            value = max(0, min(100, value))

            # Color logic
            if name in self.state_colors:
                color = QtGui.QColor(*self.state_colors[name])
            else:
                color = QtGui.QColor(64, 64, 64)  # Dark grey

            # Draw Circle
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)

            # Draw Label
            self._draw_standard_label(painter, x, y, radius, name, scale, font_metrics)

    def _draw_standard_label(self, painter, x, y, radius, name, scale, font_metrics):
        """Helper to draw the standardized label below neurons."""
        display_name = name.replace("_", " ").title()
        text_width = font_metrics.horizontalAdvance(display_name)

        padding = 10 * scale
        rect_width = text_width + (padding * 2)
        rect_height = font_metrics.height() + 4

        text_rect = QtCore.QRectF(
            x - rect_width / 2,
            y + radius + 5 * scale,
            rect_width,
            rect_height,
        )

        painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 26, 26, 200)))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(text_rect, 4, 4)

        painter.setPen(QtGui.QColor(224, 224, 224))
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, display_name)


    def draw_binary_neuron(self, painter, x, y, value, label, scale=1.0):
        color = (0, 0, 0) if value else (255, 255, 255)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color))); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        x_scaled, y_scaled, size = int(x * scale), int(y * scale), int(30 * scale)
        painter.drawRect(x_scaled - size//2, y_scaled - size//2, size, size)
        font = painter.font(); font.setPointSize(int(8 * scale)); painter.setFont(font)
        label_width, label_height = int(150 * scale), int(20 * scale)
        painter.drawText(x_scaled - label_width//2, y_scaled + int(30 * scale), label_width, label_height, QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, x, y, value, label, scale=1.0):
        color = QtGui.QColor(150, 255, 150); radius = 20 * scale
        painter.setBrush(QtGui.QBrush(color)); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.drawEllipse(int(x - radius), int(y - radius), int(radius*2), int(radius*2))
        self._draw_neuron_label(painter, x, y, label, scale)

    def draw_triangular_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a triangular neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (255, 255, 150)))
        self._draw_polygon_neuron(painter, x, y, 3, radius, color, label, scale, alpha=alpha)

    def show_diagnostic_report(self):
        if hasattr(self, 'brain_widget'): self.brain_widget.show_diagnostic_report()
        else: print("Error: Brain widget not initialized")

    def _draw_polygon_neuron(self, painter, x, y, sides, radius, color, label, scale,
                            rotation=0, alpha=255):
        painter.save()
        painter.translate(x, y)
        painter.rotate(rotation)

        alpha = max(0, min(255, alpha))            # ← clamp
        colored = QtGui.QColor(color)
        colored.setAlpha(alpha)

        pen_color = QtGui.QColor(0, 0, 0)
        pen_color.setAlpha(alpha)

        painter.setBrush(QtGui.QBrush(colored))
        painter.setPen(QtGui.QPen(pen_color))

        polygon = QtGui.QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QtCore.QPointF(radius * math.cos(angle),
                                        radius * math.sin(angle)))
        painter.drawPolygon(polygon)
        painter.restore()
        self._draw_neuron_label(painter, x, y, label, radius, scale, alpha)

    def _draw_neuron_label(self, painter, x, y, label, radius, scale, alpha=255):
        """Draw neuron label below the neuron"""
        alpha = max(0, min(255, alpha))              # ← clamp alpha
        label_color = QtGui.QColor(0, 0, 0)
        label_color.setAlpha(alpha)
        painter.setPen(label_color)
        font = painter.font()
        font.setPointSize(int(8 * scale))
        painter.setFont(font)
        label_y = y + radius + 15 * scale

        # Calculate the width needed for the text
        font_metrics = painter.fontMetrics()
        text_width = font_metrics.horizontalAdvance(label)
        padding = 10 * scale
        rect_width = text_width + 2 * padding

        # Center the text rectangle horizontally around the neuron center (x)
        painter.drawText(
            int(x - rect_width / 2),
            int(label_y),
            int(rect_width),
            int(20 * scale),
            QtCore.Qt.AlignCenter,
            label
        )

    def draw_neurogenesis_highlights(self, painter, scale):
        if (self.neurogenesis_highlight['neuron'] and time.time() - self.neurogenesis_highlight['start_time'] < self.neurogenesis_highlight['duration']):
            pos = self.neuron_positions.get(self.neurogenesis_highlight['neuron'])
            if pos:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), int(3 * scale))); painter.setBrush(QtCore.Qt.NoBrush); radius = int(40 * scale)
                x, y, width, height = int(pos[0] - radius), int(pos[1] - radius), int(radius * 2), int(radius * 2)
                painter.drawEllipse(x, y, width, height)

    def draw_square_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a square neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, radius, color, label, scale, rotation=45, alpha=alpha)

    def draw_diamond_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a diamond-shaped neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, radius, color, label, scale, rotation=0, alpha=alpha)

    def toggle_links(self, state):
        """
        Public slot connected to the checkbox.
        Instead of flipping a boolean immediately we only *request* the
        new target opacity; the timer will do the actual fade with
        per-link random delays and speeds for maximum chaos.
        """
        want_visible = (state == QtCore.Qt.Checked)
        now = time.time()
        
        for key in self.weights.keys():
            self._link_targets[key] = 1.0 if want_visible else 0.0
            
            # Random delay per link (0-800ms)
            self._link_start_times[key] = now + random.uniform(0.0, 0.8)
            
            # Random speed per link for individual character
            self._link_fade_speeds[key] = random.uniform(2.0, 4.5)
            
            # Initialize opacity if not already set
            if key not in self._link_opacities:
                self._link_opacities[key] = 0.0 if want_visible else 1.0

        # Kick the timer (safe to call multiple times)
        if not self._link_fade_timer.isActive():
            self._link_fade_timer.start()

    def toggle_weights(self, state):
        self.show_weights = state == QtCore.Qt.Checked
        self.update()

    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return

        logical_pos = self._get_logical_coords(event.pos())
        neuron = self.get_neuron_at_pos(event.pos())
        
        if not neuron:
            self.dragged_neuron = None
            self.dragging = False
            super().mousePressEvent(event)
            return

        # Allow dragging any neuron
        self.dragged_neuron = neuron
        self.dragging = True
        self.drag_start_pos = event.pos()
        
        # Debug info
        is_neuro = self.is_neurogenesis_neuron(neuron)
        neuron_type = "Neurogenesis" if is_neuro else "Core"
        
        # Debug: Check if neuron is in functional_neurons
        if hasattr(self, 'enhanced_neurogenesis') and neuron in self.enhanced_neurogenesis.functional_neurons:
            print(f"   Functional neuron details: {self.enhanced_neurogenesis.functional_neurons[neuron]}")
        
        self.update()
        super().mousePressEvent(event)

    def handle_neuron_clicked(self, neuron_name):
        print(f"")

    def show_diagnostic_report(self):
        dialog = DiagnosticReportDialog(self, self.parent())
        dialog.exec_()

    def mouseMoveEvent(self, event):
        """Handle mouse movement for tooltips, hover tracking, and dragging"""
        if hasattr(self, 'tooltip_manager'):
            self.tooltip_manager.show_tooltip_for_position(event)

        # Track hover state for neurons (if hover effects enabled)
        if self.anim_hover_enabled:
            neuron = self.get_neuron_at_pos(event.pos())
            was_hovered = self.hovered_neuron is not None
            
            if neuron != self.hovered_neuron:
                self.hovered_neuron = neuron
                self.hover_animation_time = time.time()
                self.hover_value_opacity = 0.0  # Reset fade-in
                self.hover_value_display_active = neuron is not None
                self.update()  # Trigger repaint

        # Dragging logic...
        if self.dragging and self.dragged_neuron:
            if self.is_neurogenesis_neuron(self.dragged_neuron):
                logical_pos = self._get_logical_coords(event.pos())
                self.neuron_positions[self.dragged_neuron] = (logical_pos.x(), logical_pos.y())
                self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Clear hover state when mouse leaves widget."""
        if self.hovered_neuron is not None:
            self.hovered_neuron = None
            self.hover_value_display_active = False
            self.hover_value_opacity = 0.0
            self.update()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
        Handle double-click on a neuron to open the Neuron Laboratory instead of the Inspector.
        """
        if event.button() == QtCore.Qt.LeftButton:
            neuron_name = self.get_neuron_at_pos(event.pos())
            
            if neuron_name:
                print(f"Double-clicked on neuron: {neuron_name}")
                
                # Close the old Inspector if it's currently open (compatibility cleanup)
                if hasattr(self, '_inspector') and self._inspector and self._inspector.isVisible():
                    self._inspector.close()
                    self._inspector = None # Clear the old reference

                # Open or show the Neuron Laboratory
                if self._laboratory is None:
                    self._laboratory = NeuronLaboratory(self, parent=self.window() or self.parent()) 
                
                self._laboratory.show()
                self._laboratory.raise_() # Bring the window to the front

                # CALL A NEW METHOD: Pass the neuron name for selection
                if hasattr(self._laboratory, 'select_neuron_by_name'):
                    self._laboratory.select_neuron_by_name(neuron_name)
                
                self.update() # Redraw the brain visualization
                event.accept()
                return
            
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            is_click = False
            if self.dragged_neuron and self.drag_start_pos:
                distance = (event.pos() - self.drag_start_pos).manhattanLength()
                if distance < QtWidgets.QApplication.startDragDistance():
                    is_click = True
            if is_click:
                self.neuronClicked.emit(self.dragged_neuron)
            self.dragging = False
            self.dragged_neuron = None
            self.drag_start_pos = None
            self.update()
            # Only apply repulsion to neurogenesis neurons
            #if hasattr(self, 'enhanced_neurogenesis'):
            #    self.apply_repulsion_force()
        super().mouseReleaseEvent(event)

    def draw_strength_multiplier(self, painter, scale):
        """
        Draw strength multipliers on neurons that have been strengthened.
        Displays as "2.5x" above strengthened neurons with a badge.
        """
        if not hasattr(self, 'enhanced_neurogenesis'):
            return
        
        current_time = time.time()
        
        # Save painter state to avoid interfering with other drawings
        painter.save()
        
        for name, neuron in self.enhanced_neurogenesis.functional_neurons.items():
            # Verify attribute exists and neuron is strengthened
            if not hasattr(neuron, 'strength_multiplier'):
                continue
                
            if neuron.strength_multiplier <= 1.0 or name not in self.neuron_positions:
                continue
            
            pos = self.neuron_positions[name]
            x, y = pos
            
            # Position ABOVE the neuron (in logical coordinates)
            label_y = y - 45  # Don't scale Y offset - already in logical space
            
            # Format multiplier text
            multiplier_text = f"{neuron.strength_multiplier:.1f}x"  # FIX: typo here
            
            # Create font with proper scaling
            font = QtGui.QFont()
            font.setPointSize(int(9 * scale))
            font.setBold(True)
            painter.setFont(font)
            
            # Draw background circle/badge
            font_metrics = painter.fontMetrics()
            text_width = font_metrics.horizontalAdvance(multiplier_text)
            badge_radius = max(12 * scale, (text_width / 2) + 5 * scale)
            
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 215, 0, 220)))
            painter.setPen(QtGui.QPen(QtGui.QColor(139, 105, 20), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(x, label_y), badge_radius, badge_radius)
            
            # Draw text
            painter.setPen(QtGui.QColor(0, 0, 0))
            painter.drawText(
                int(x - text_width / 2),
                int(label_y - font_metrics.height() / 2),
                int(text_width),
                int(font_metrics.height()),
                QtCore.Qt.AlignCenter,
                multiplier_text
            )
            
            # Optional: Add star indicator
            star_radius = 8 * scale
            star_x = x + 20 * scale
            star_y = y - 20 * scale
            
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 215, 0, 200)))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 165, 0), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(star_x, star_y), star_radius, star_radius)
        
        painter.restore()


    def _is_click_on_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return (abs(scaled_x - point.x()) <= 25 * scale and abs(scaled_y - point.y()) <= 25 * scale)

    def is_point_inside_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return ((scaled_x - 25 * scale) <= point.x() <= (scaled_x + 25 * scale) and (scaled_y - 25 * scale) <= point.y() <= (scaled_y + 25 * scale))

    def reset_positions(self):
        self.neuron_positions = self.original_neuron_positions.copy()
        self.update()
        
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
    
    def get_tutorial_glow_opacity(self):
        """Get current glow opacity (for Qt property animation)"""
        return self._tutorial_glow_opacity
    
    def set_tutorial_glow_opacity(self, value):
        """Set glow opacity and trigger repaint (for Qt property animation)"""
        self._tutorial_glow_opacity = value
        self.update()
    
    # Qt property for animation
    tutorial_glow_opacity = QtCore.pyqtProperty(float, get_tutorial_glow_opacity, set_tutorial_glow_opacity)

import time

class PerformanceProfiler:
    """Lightweight profiler for identifying slow code paths."""
    
    def __init__(self):
        self.timings = {}
        self.call_counts = {}
    
    def start(self, name):
        if name not in self.timings:
            self.timings[name] = []
            self.call_counts[name] = 0
        self._current_start = time.perf_counter()
        self._current_name = name
    
    def stop(self):
        elapsed = (time.perf_counter() - self._current_start) * 1000
        self.timings[self._current_name].append(elapsed)
        self.call_counts[self._current_name] += 1
        # Keep only last 100 samples
        if len(self.timings[self._current_name]) > 100:
            self.timings[self._current_name].pop(0)
    
    def report(self):
        """Print performance report."""
        print("\n" + "="*60)
        print("PERFORMANCE REPORT")
        print("="*60)
        for name, times in sorted(self.timings.items()):
            if times:
                avg = sum(times) / len(times)
                max_t = max(times)
                calls = self.call_counts[name]
                print(f"{name:30} avg={avg:6.2f}ms  max={max_t:6.2f}ms  calls={calls}")
        print("="*60 + "\n")

# =============================================================================
# NETWORK RENDERING MIXIN (Add to brain_widget.py)
# =============================================================================

class NetworkRenderingMixin:
    """
    Mixin providing static network rendering methods extracted from BrainWidget.
    Used by both BrainWidget and save viewer's NetworkCanvas for consistent visuals.
    """
    
    @staticmethod
    def draw_connections(self, painter, scale):
        """Draw connections with extended 2-second weight-change animations.
        Links are forced INVISIBLE while core neurons are still being revealed."""
        if not self.show_links:
            return

        # ===== PERFORMANCE FIX: Skip if widget is hidden =====
        if not self.isVisible():
            return

        # ===== PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE:
            _conn_start = time.perf_counter()

        # absolutely no connections until every core neuron is completely revealed (tutorial mode guard).
        if self.is_tutorial_mode and len(self.visible_neurons) < len(self.original_neurons):
            return

        current_time = time.time()
        connections_drawn = 0
        connections_skipped = 0

        for key, weight in self.weights.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            source, target = key

            # skip tutorial-only connections when not in tutorial
            tutorial_mode = getattr(self.parent(), 'tutorial_active', False)
            is_tutorial_conn = (source.startswith('tutorial_neuron_') or
                                target.startswith('tutorial_neuron_'))
            if is_tutorial_conn and not tutorial_mode:
                continue

            # skip if either neuron is still revealing (tutorial safety)
            if self.is_tutorial_mode and (
                    not self.is_neuron_revealed(source) or
                    not self.is_neuron_revealed(target)):
                connections_skipped += 1
                continue

            if (source not in self.neuron_positions or
                target not in self.neuron_positions or
                source in self.excluded_neurons or
                target in self.excluded_neurons):
                continue

            # skip connections involving non-visible core neurons (tutorial)
            if self.is_tutorial_mode:
                if source in self.original_neurons and source not in self.visible_neurons:
                    connections_skipped += 1
                    continue
                if target in self.original_neurons and target not in self.visible_neurons:
                    connections_skipped += 1
                    continue

            start = self.neuron_positions[source]
            end   = self.neuron_positions[target]
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point   = QtCore.QPointF(float(end[0]),   float(end[1]))

            # special styling:  Stress ↔ Anxiety  (uses animation style params)
            is_stress_to_anxiety = (
                (source.lower().startswith('stress') and target.lower() == 'anxiety') or
                (target.lower().startswith('stress') and source.lower() == 'anxiety'))
            if is_stress_to_anxiety:
                pen = QtGui.QPen(QtGui.QColor(*self.anim_stress_colour))
                pen.setWidth(int(self.anim_stress_width))
                if self.anim_stress_dashed:
                    pen.setStyle(QtCore.Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(start_point, end_point)
                continue   # skip default drawing for this pair

            # ===== EMPHASIZED FOOD CONNECTIONS =====
            is_food_connection = (
                (source == 'can_see_food' and target in ['hunger', 'happiness']) or
                (target == 'can_see_food' and source in ['hunger', 'happiness'])
            )
            if is_food_connection:
                # Bright cyan, thick, solid line for visual emphasis
                pen = QtGui.QPen(QtGui.QColor(0, 200, 255))  # Distinctive cyan color
                pen.setWidth(int(max(3, self.anim_line_base_width * 3)))  # 3x thicker
                pen.setStyle(QtCore.Qt.SolidLine)
                pen.setCapStyle(QtCore.Qt.RoundCap)
                painter.setPen(pen)
                painter.drawLine(start_point, end_point)
                continue  # Skip default rendering to keep emphasis clean

            # default appearance (uses animation style params)
            anim_weight = weight
            base_width  = self.anim_line_base_width * scale
            line_width  = base_width
            pen_style   = QtCore.Qt.SolidLine
            animating   = False
            pulse_progress = 0.0

            # check for active weight-change animations (2-second window)
            for anim in self.weight_animations:
                if anim['pair'] == key:
                    elapsed = current_time - anim['start_time']
                    if elapsed < anim['duration']:
                        progress = elapsed / anim['duration']
                        anim_weight = anim['start_weight'] + progress * (
                            anim['end_weight'] - anim['start_weight'])

                        # growing / shrinking line width
                        if progress < 0.5:
                            line_width = base_width + (6.0 * scale * progress * 2)
                        else:
                            line_width = base_width + (6.0 * scale * (1 - progress) * 2)

                        pulse_progress = progress * anim['pulse_speed']
                        animating = True
                        break

            # colour & alpha
            if animating:
                r, g, b = anim['color']
                alpha = int(255 * (1 - pulse_progress ** 2))
                color = QtGui.QColor(r, g, b, alpha)
            else:
                base_alpha = int(self._link_opacities.get(key, 0.0) * 255)
                
                # ===== VIBRANT STYLE: Apply ambient pulse =====
                if self.anim_ambient_pulse_enabled and base_alpha > 0:
                    pulse_state = self._get_or_create_ambient_pulse(key)
                    phase = pulse_state['phase']
                    
                    # Sinusoidal oscillation (0 to 1 range)
                    pulse_factor = (math.sin(phase) + 1.0) / 2.0
                    
                    # Interpolate width
                    w_min, w_max = self.anim_ambient_pulse_width_range
                    width_mult = w_min + pulse_factor * (w_max - w_min)
                    line_width = base_width * width_mult
                    
                    # Interpolate alpha
                    a_min, a_max = self.anim_ambient_pulse_alpha_range
                    pulse_alpha = int(a_min + pulse_factor * (a_max - a_min))
                    # Combine with base opacity
                    final_alpha = int((base_alpha / 255.0) * pulse_alpha)
                    
                    if weight > 0:
                        color = QtGui.QColor(self.anim_line_col_pos[0], 
                                        self.anim_line_col_pos[1], 
                                        self.anim_line_col_pos[2], final_alpha)
                    else:
                        color = QtGui.QColor(self.anim_line_col_neg[0], 
                                        self.anim_line_col_neg[1], 
                                        self.anim_line_col_neg[2], final_alpha)
                else:
                    # Standard coloring (classic style or opacity 0)
                    color = (QtGui.QColor(0, int(255 * abs(weight)), 0, base_alpha) if weight > 0 else
                            QtGui.QColor(int(255 * abs(weight)), 0, 0, base_alpha))

            # line style
            if is_tutorial_conn and tutorial_mode:
                color = QtGui.QColor(255, 255, 0, 180)
                line_width = 3
                pen_style = QtCore.Qt.DashLine
            else:
                pen_style = (QtCore.Qt.DashLine if weight < 0 else
                            QtCore.Qt.SolidLine)
                if abs(anim_weight) < 0.1:
                    pen_style = QtCore.Qt.DotLine

            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start_point, end_point)

            # pulse circle travelling along the wire (uses animation style params)
            if self.anim_pulse_enabled and animating and pulse_progress < 1.0:
                pulse_pos = pulse_progress
                pulse_x = start_point.x() + pulse_pos * (end_point.x() - start_point.x())
                pulse_y = start_point.y() + pulse_pos * (end_point.y() - start_point.y())
                pulse_size = self.anim_pulse_diameter * scale * (1 - pulse_progress ** 2)

                painter.setBrush(QtGui.QBrush(QtGui.QColor(*self.anim_pulse_colour, self.anim_pulse_alpha)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(pulse_x, pulse_y),
                                    pulse_size, pulse_size)

            # glow around the line (uses animation style params)
            if self.anim_glow_enabled and animating and progress < self.anim_glow_fade_threshold:
                glow_progress = progress / self.anim_glow_fade_threshold
                glow_width = line_width + 4 * scale * (1 - glow_progress)
                glow_color = QtGui.QColor(*self.anim_glow_colour, self.anim_glow_alpha)
                painter.setPen(QtGui.QPen(glow_color, glow_width, pen_style))
                painter.drawLine(start_point, end_point)
            
            # ===== SUBTLE STYLE: Draw communication glow packets =====
            if self.anim_comm_glow_enabled:
                self._draw_comm_glows_for_connection(
                    painter, scale, key, start_point, end_point
                )

            # weight text (optional)
            if self.show_weights and abs(weight) > 0.1:
                midpoint = QtCore.QPointF((start_point.x() + end_point.x()) / 2,
                                        (start_point.y() + end_point.y()) / 2)
                text_area_width  = 80.0 * scale
                text_area_height = 22.0 * scale
                font = painter.font()
                font.setPointSize(max(8, int(8 * scale)))
                painter.setFont(font)
                rect = QtCore.QRectF(midpoint.x() - text_area_width / 2,
                                    midpoint.y() - text_area_height / 2,
                                    text_area_width, text_area_height)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawRect(rect)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))
                painter.drawText(rect, QtCore.Qt.AlignCenter, f"{weight:.2f}")

            connections_drawn += 1

        # debug guard: warn only when something looks wrong
        if connections_drawn == 0 and len(self.weights) > 0:
            print(f"🔴 NO CONNECTIONS DRAWN! tutorial_mode={self.is_tutorial_mode}, "
                f"visible_neurons={len(self.visible_neurons)}, original_neurons={len(self.original_neurons)}, "
                f"total_weights={len(self.weights)}, skipped={connections_skipped}")
        
        # ===== END PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE:
            _conn_elapsed = (time.perf_counter() - _conn_start) * 1000
            perf_tracker.record("draw_connections", _conn_elapsed)
    
    @staticmethod
    def draw_neurons_static(
        painter, neuron_positions, neuron_states,
        visible_neurons=None, excluded_neurons=None,
        scale=1.0, base_font_size=8):
        """
        Static neuron drawing – now correctly handles binary neurons even when
        no tamagotchi_logic reference is available (e.g. during save load).
        """
        BINARY_NEURONS = {
            "can_see_food", "is_eating", "is_sleeping",
            "is_sick", "is_fleeing", "pursuing_food", "is_startled"
        }

        if visible_neurons is None:
            visible_neurons = set(neuron_positions.keys())
        if excluded_neurons is None:
            excluded_neurons = set()

        label_font = QtGui.QFont("Arial", int(base_font_size))
        label_font.setBold(True)
        painter.setFont(label_font)
        font_metrics = painter.fontMetrics()

        for name, pos in neuron_positions.items():
            if name in excluded_neurons or name not in visible_neurons:
                continue

            raw_value = neuron_states.get(name, 0)

            # Binary neuron handling (including can_see_food)
            if name in BINARY_NEURONS:
                value = 100.0 if float(raw_value) > 50 else 0.0
                is_active = value > 50
                color = QtGui.QColor(0, 255, 0) if is_active else QtGui.QColor(255, 0, 0)
            else:
                # Continuous neurons – heat colour map
                value = float(raw_value) if isinstance(raw_value, (int, float, bool)) else 50.0
                value = max(0, min(100, value))
                normalized = value / 100.0
                if normalized > 0.7:
                    color = QtGui.QColor(76, 175, 80)
                elif normalized > 0.4:
                    color = QtGui.QColor(255, 193, 7)
                else:
                    color = QtGui.QColor(244, 67, 54)

            x = pos[0] * scale
            y = pos[1] * scale
            radius = 20 * scale

            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)

            # Label
            display_name = name.replace("_", " ").title()
            text_width = font_metrics.horizontalAdvance(display_name)
            padding = 10 * scale
            rect_width = text_width + padding * 2
            rect_height = font_metrics.height() + 4

            text_rect = QtCore.QRectF(
                x - rect_width / 2,
                y + radius + 5 * scale,
                rect_width,
                rect_height,
            )

            painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 26, 26, 200)))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(text_rect, 4, 4)

            painter.setPen(QtGui.QColor(224, 224, 224))
            painter.drawText(text_rect, QtCore.Qt.AlignCenter, display_name)

    
    @staticmethod
    def draw_layers_static(painter, layers, scale=1.0):
        """Draw layer background rectangles if layer structure exists"""
        if not layers:
            return
            
        for layer in layers:
            y_pos = layer.get('y_position', 0)
            name = layer.get('name', 'Layer')
            layer_type = layer.get('layer_type', 'hidden')
            
            # Logical dimensions (match brain_widget's coordinate system)
            rect_height = 120
            rect_top = (y_pos - rect_height / 2)
            rect_left = -200  # Extend beyond visible area
            rect_width = 2000
            
            # Determine layer color based on type
            if layer_type == 'input':
                color = QtGui.QColor(220, 255, 220, 30)
                border_color = QtGui.QColor(180, 220, 180, 60)
            elif layer_type == 'output':
                color = QtGui.QColor(255, 220, 220, 30)
                border_color = QtGui.QColor(220, 180, 180, 60)
            else:  # hidden
                color = QtGui.QColor(230, 230, 255, 40)
                border_color = QtGui.QColor(200, 200, 240, 60)
            
            # Draw rectangle
            rect = QtCore.QRectF(rect_left, rect_top, rect_width, rect_height)
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(border_color, 1, QtCore.Qt.DashLine))
            painter.drawRect(rect)
            
            # Draw label
            font = QtGui.QFont("Arial", int(10 * scale))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(150, 150, 170))
            painter.drawText(QtCore.QPointF(20, rect_top + 20), name)