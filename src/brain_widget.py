import logging

_LOG = logging.getLogger(__name__)

import time
import math
import random

# This is the biggest, messiest and most shameful of all the files in this project
# I express my condolences to future devs  that curse the mighty brain_widget on late nights as I do

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QImage
from datetime import datetime

from .brain_render_worker import BrainRenderWorker, create_render_state_from_widget
from .neural_provenance import RecordedSynapses
from .propagation import ExternallyDriven
from .compute_backend import get_backend
from .neurogenesis import EnhancedNeurogenesis
from .brain_tooltips import EnhancedBrainTooltips
from .brain_constants import (
    NEURON_RADIUS, BINARY_NEURONS, is_network_driven, normalise_activation,
)
from .learning import LearningConfig
from .localisation import Localisation
from typing import Optional

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
            export_brain_state,  # noqa: F401
            set_game_running,
            update_brain_state_from_widget
        )
        _HAS_BRAIN_BRIDGE = True
    except ImportError:
        _HAS_BRAIN_BRIDGE = False
        print("[BrainWidget] Warning: brain_state_bridge not found, designer sync disabled")

from .animation_styles import (
    AnimationStyle, get_animation_style, DEFAULT_ANIMATION_STYLE
)

from .brain_widget_painting import BrainPaintingMixin, NetworkRenderingMixin  # noqa: F401
from .brain_widget_animation import BrainAnimationMixin
from .brain_widget_view import BrainViewMixin

class BrainWidget(
        RecordedSynapses,
        ExternallyDriven,
        BrainPaintingMixin,
        BrainAnimationMixin,
        BrainViewMixin,
        QtWidgets.QWidget,
):
    
    neuronClicked = QtCore.pyqtSignal(str)
    animationStyleChanged = QtCore.pyqtSignal(str)  # Emitted when style changes
    neuronCreated = QtCore.pyqtSignal(str)  # Emitted when neurogenesis creates a new neuron

    def __init__(self, config=None, debug_mode=False, tamagotchi_logic=None,
                 animation_style: str = None):
        self.resolution_scale = 1.0  # Default resolution scale
        self.config = config if config else LearningConfig()
        self._laboratory = None
        self._last_lang = Localisation.instance().current_language

        # ===== ANIMATION STYLE INITIALIZATION =====
        # No style named: take the one saved in config.ini, and DEFAULT_
        # ANIMATION_STYLE if there is none. The style the player picks in the
        # Network tab has always been written to the config, but nothing ever
        # read it back - the widget was constructed with a hardcoded 'vibrant'
        # every time - so the setting silently reverted on every launch.
        if animation_style is None:
            getter = getattr(self.config, 'get_animation_style', None)
            animation_style = getter() if callable(getter) else DEFAULT_ANIMATION_STYLE
        try:
            self._animation_style: AnimationStyle = get_animation_style(animation_style)
        except KeyError:
            animation_style = DEFAULT_ANIMATION_STYLE
            self._animation_style = get_animation_style(animation_style)
        self._animation_style_name = animation_style
        self.layers = []

        # State update batching
        self._pending_state_update = False
        self.state_update_queue = []
        
        # Caches for neuron data
        self.neurons = {}
        self.state_colors = {}
        
        # Hover tracking
        self.hovered_neuron = None
        self.hovered_connection = None
        self.hover_value_display_active = False
        self.hover_value_opacity = 0.0
        self.hover_value_animation_time = 0.0
        self.hover_animation_time = 0
        # SquidBrainWindow hands us a ConfigManager (it discards the
        # LearningConfig main.py passes it), and a ConfigManager carries no
        # hebbian/neurogenesis section. This used to be patched with hardcoded
        # literals, which silently overrode config.ini for every learning
        # parameter in the game - the tuning in the file had no effect at all.
        # Populate from the real LearningConfig instead, which reads the file.
        if not hasattr(self.config, 'hebbian') or not hasattr(self.config, 'neurogenesis'):
            _loaded = LearningConfig()
            if not hasattr(self.config, 'hebbian'):
                self.config.hebbian = _loaded.hebbian
            if not hasattr(self.config, 'neurogenesis'):
                self.config.neurogenesis = _loaded.neurogenesis
        super().__init__() #

        # Get neuron label font size from config (single source of truth)
        display_config = self.config.get_display_config()
        self.neuron_label_font_size = display_config['neuron_label_font_size']

        # How big a neuron is drawn, in logical canvas units. config.ini has
        # carried a [Display] neuron_radius the whole time and every renderer
        # ignored it in favour of a hardcoded 20, so the setting did nothing.
        self.neuron_radius = float(
            display_config.get('neuron_radius') or NEURON_RADIUS)

        # Tutorial glow effect properties
        self.tutorial_glow_active = False
        self.tutorial_glow_timer = None
        self.tutorial_glow_animation = None
        self._tutorial_glow_opacity = 0.0
        self._link_fade_speeds = {}        # (src,dst) → fade speed per link
        self._link_start_times = {}        # (src,dst) → when this link should start

        self.excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping']

        # Neurons written from outside the forward pass. Sensors are already
        # kept out of it by is_network_driven(); this is the set the brain adds
        # to at runtime, currently the action representations neurogenesis
        # grows when the squid turns out to be unable to tell two of its own
        # actions apart.
        self.action_representations = {}
        self.externally_driven = set()
        
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

        # Provenance first: everything below writes to it, so it has to exist
        # before anything can change a weight or grow a neuron. This is the
        # brain's own record of why it is the way it is, and it is what the
        # inspection tools read - they never reconstruct it.
        from .neural_provenance import CausalLedger
        self.ledger = CausalLedger(self)

        # What this network currently cannot do. Diagnosis for neurogenesis
        # and, through the Knowledge tab, an explanation for the player.
        from .capability import CapabilityMonitor
        self.capability = CapabilityMonitor(self)

        # Action -> consequence -> outcome -> learning, with temporal credit
        # assignment over the STDP eligibility traces.
        from .causal_learning import ActionOutcomeLedger
        self.causal_learning = ActionOutcomeLedger(self)

        # How it learns what is worth doing: now and then an unwired action
        # neuron fires by itself, and a cue -> action synapse forms only when
        # the action turned out differently with the cue than without it.
        from .action_discovery import ActionDiscovery, DEFAULT_RATE
        self.action_discovery = ActionDiscovery(
            self, rate=float(getattr(self.config, 'hebbian', {}).get(
                'motor_exploration_rate', DEFAULT_RATE)),
            seed=int(time.time() * 1000) % (2 ** 31))

        # Structural plasticity. One engine, capability-driven.
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

        # Plasticity: Hebbian (covariance, signed) + STDP over an eligibility
        # trace. Owned by the widget so the Designer, the Learning tab and the
        # save file all see one implementation.
        from .plasticity import PlasticityEngine, PlasticityConfig
        self.plasticity = PlasticityEngine(
            PlasticityConfig.from_learning_config(self.config))

        # Sleep-time consolidation. Waking experience proposes small changes;
        # sleep replays the day's strongest co-activations into durable
        # structure and prunes what never amounted to anything.
        from .consolidation import ConsolidationManager
        self.consolidation = ConsolidationManager(self)

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

        # Neuron position configuration. brain_constants.newborn_neurons() is
        # the single definition of what a squid hatches with: the eight
        # required neurons, the sensors its innate reflexes read, and the
        # action neurons that are the motor end of every behaviour.
        from .brain_constants import newborn_neurons, ACTION_NEURONS
        self.original_neuron_positions = newborn_neurons()
        self.neuron_positions = self.original_neuron_positions.copy()

        # Every neuron the squid was BORN with - the eight, the innate sensors
        # and the motor bank - as a set, for asking "was this grown?".
        # self.original_neurons below holds the same names as an ORDERED list,
        # because the birth animation needs an order and this does not.
        # Several renderers used to ask "was this grown?" against a hardcoded
        # list of the eight, so the motor bank and the innate sensors were
        # captioned as if the squid had grown them in its first second of life.
        self.innate_neurons = frozenset(self.original_neuron_positions)

        # Action neurons are network-driven like any other: propagation writes
        # them, and the decision engine reads them to see what the squid wants
        # to do. They start at rest, not at the 50 baseline a core stat uses -
        # a newborn should want nothing until something drives it.
        from .brain_constants import action_resting_level
        for action_name in ACTION_NEURONS:
            self.state.setdefault(action_name, action_resting_level(action_name))
        for sensor_name in self.original_neuron_positions:
            self.state.setdefault(sensor_name, 0.0)

        # Randomize positions if configured ---
        neuron_props = self.config.neurogenesis.get('neuron_properties', {})
        if neuron_props.get('randomize_start_positions', False):
            self._randomize_all_positions()

        # The instincts a squid is born with are hatched in one place:
        # initialize_weights(), from brain_constants.INNATE_CONNECTIONS.

        # Track which neurons are visible (for animated reveal on new game)
        self.visible_neurons = set()
        # Every neuron the squid hatches with, in the order the birth
        # animation reveals them: the CORE row, then ACTIONS, then SENSES.
        #
        # This was the eight required neurons alone, and that is why a newly
        # hatched brain had an empty ACTIONS row. A neuron that is never
        # revealed is never added to visible_neurons, and a neuron that is not
        # in visible_neurons is never drawn - so the motor bank, which the
        # squid is every bit as born with as its hunger, simply was not there.
        from .brain_constants import birth_sequence
        self.original_neurons = list(birth_sequence())
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
            self._brain_export_timer.timeout.connect(self.export_brain_state_for_designer)
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
        # self.connections is a derived property over self.weights (see below).
        self.initialize_weights()  # Populate weights
        
        self.show_links = True #
        self.frozen_weights = None #
        self.history = [] #
        self.training_data = [] #
        self.learning_rate = 0.1 #

        # --- Compute backend (NumPy default, optional ONNX for NPU support) ---
        self.compute_backend = get_backend()
        self.associations = self.compute_backend.zeros(
            (len(self.neuron_positions), len(self.neuron_positions))
        ) #
        self.capture_training_data_enabled = False #
        self.dragging = False #
        self.dragged_neuron = None #
        self.drag_start_pos = None #
        self.tooltip_manager = EnhancedBrainTooltips(self)
        self.setMouseTracking(True)
        # Zoom and pan of the network view (see _view_transform). Wheel or
        # pinch zooms about the cursor, dragging empty space pans,
        # double-clicking empty space puts the whole network back in view.
        self.view_zoom = 1.0
        self.view_pan = (0.0, 0.0)
        self._pan_last = None
        self.show_weights = False

        _link_fade_speed = 3.0   # opacity units per second (tweak for faster/slower)

         # ===== OFFSCREEN RENDERING SETUP =====
        # Initialize render worker for background rendering
        self._render_worker = BrainRenderWorker(self)
        self._render_worker.render_complete.connect(self._on_render_complete)
        self._render_worker.start()
        
        # Cached rendered image
        self._cached_render: Optional[QImage] = None
        self._render_dirty = True
        
        # Render throttling
        self._last_render_request = 0.0
        self._render_interval = 1.0 / 10.0  # 10 FPS target
        
        # State change tracking for smart re-rendering
        self._last_state_hash = None
        
        # Timer for periodic render requests (catches animation updates)
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._request_render_if_dirty)
        self._render_timer.start(int(1000 / self.IDLE_RENDER_FPS))

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
                _LOG.debug('Ignored exception', exc_info=True)  # Ignore if signals weren't connected
        
        # Connect new signals
        self.brain_worker.neurogenesis_result.connect(self._on_neurogenesis_complete)
        self.brain_worker.hebbian_result.connect(self._on_hebbian_complete)
        self.brain_worker.state_update_result.connect(self._on_state_update_complete)
        self.brain_worker.error_occurred.connect(self._on_worker_error)
        
        print("🧵 BrainWidget received external BrainWorker")

    # =========================================================================
    # BRAIN STATE BRIDGE METHODS (for designer synchronization)
    # =========================================================================
    def showEvent(self, event):
        """Ensure render is requested when widget becomes visible."""
        super().showEvent(event)
        self.mark_render_dirty()
        # Reset render throttle to force immediate update
        self._last_render_request = 0
        self._request_render()
    
    def export_brain_state_for_designer(self):
        """
        Export current brain state to shared file for designer import.
        Public method - can be called by NetworkTab before launching designer.
        """
        if not _HAS_BRAIN_BRIDGE:
            return
        
        try:
            # Ensure the game lock exists
            set_game_running(True)
            
            # Export the actual data
            update_brain_state_from_widget(self)
        except Exception as e:
            # Silent failure - don't spam console
            _LOG.debug('Ignored exception', exc_info=True)
    
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
                _LOG.debug('Ignored exception', exc_info=True)
    
    def closeEvent(self, event):
        """Handle widget close - stop workers and clear the designer bridge.

        A second closeEvent used to be defined further down this class (a paste
        of SquidBrainWindow.closeEvent) which shadowed this one, so the bridge
        lock file was never removed and a standalone Designer kept believing a
        game was running for 60s after exit.
        """
        self.stop_worker()
        self.cleanup_brain_bridge()
        self._cleanup_render_worker()
        super().closeEvent(event)
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

    
    def _request_render_if_dirty(self):
        """Called by timer to request render if state has changed"""
        if self._render_dirty or self._has_active_animations():
            self._request_render()

    def _request_render(self):
        """Request a new render from the worker thread"""
        current_time = time.time()
        
        # Throttle requests
        if current_time - self._last_render_request < self._render_interval:
            return
        
        self._last_render_request = current_time
        
        # Create state snapshot and send to worker
        try:
            state = create_render_state_from_widget(self)
            self._render_worker.request_render(state)
            self._render_dirty = False
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Error creating render state: {e}")

    def _on_render_complete(self, image: QImage, render_time: float):
        """Called when render worker completes a frame"""
        self._cached_render = image
        # Trigger a lightweight repaint to show the new image
        self.update()

    def mark_render_dirty(self):
        """Call this when state changes that require re-render"""
        self._render_dirty = True

    def _cleanup_render_worker(self):
        """Clean up the render worker - call on widget destruction"""
        if hasattr(self, '_render_worker') and self._render_worker:
            self._render_worker.stop()
            self._render_worker.wait(1000)  # Wait up to 1 second
            self._render_worker = None
        
        if hasattr(self, '_render_timer') and self._render_timer:
            self._render_timer.stop()

    def is_binary_neuron(self, neuron_name: str) -> bool:
        """Return True if neuron represents a binary (on/off) state.

        Delegates to brain_constants.BINARY_NEURONS - the single definition.
        """
        return neuron_name in BINARY_NEURONS

    # =========================================================================
    # DERIVED VIEWS - these used to be independently-maintained copies that
    # drifted out of sync with their source (weights / the output monitor).
    # =========================================================================
    @property
    def connections(self):
        """The edge list. Derived from self.weights, which is the source of truth."""
        return list(self.weights.keys())

    @connections.setter
    def connections(self, value):
        # Legacy call sites assign a rebuilt list; the value is ignored because
        # weights already carries it. Kept so those call sites remain valid.
        return

    @property
    def output_bindings(self):
        """Read-through view of the live NeuronOutputMonitor's bindings.

        Previously this was a second copy of the binding list, so after a load
        the Network-tab overlay showed bindings the monitor no longer had.
        """
        monitor = self._get_output_monitor()
        if monitor is not None:
            return monitor.export_bindings()
        return list(getattr(self, '_detached_output_bindings', []))

    @output_bindings.setter
    def output_bindings(self, value):
        monitor = self._get_output_monitor()
        if monitor is not None:
            monitor.load_bindings_from_brain({'output_bindings': value or []})
        else:
            # No game attached (standalone designer / tests): hold them here
            # until a monitor appears.
            self._detached_output_bindings = list(value or [])

    def _get_output_monitor(self):
        logic = getattr(self, 'tamagotchi_logic', None)
        return getattr(logic, 'neuron_output_monitor', None) if logic else None
    
    def find_orphan_neurons(self):
        """Find neurons with no connections in the weights dictionary.

        An UNLEARNED ACTION is not an orphan. act_play, act_shelter and
        act_rest are deliberately born with nothing driving them - that is what
        "the squid has to learn this" is made of - so reporting them as
        orphans made the brain grow a rescue connector for each one within the
        first few seconds of life, wiring up by accident exactly the actions
        the squid was supposed to have to earn. A disconnected action neuron is
        a capability the squid does not have yet, not a defect in its wiring.
        """
        from .brain_constants import LEARNED_ACTIONS

        orphans = []

        # Define neurons that should be checked even if they are in excluded_neurons
        explicitly_allowed = {'can_see_food', 'can_see_plant', 'is_fleeing'}
        never_orphans = set(LEARNED_ACTIONS)

        for neuron in self.neuron_positions.keys():
            # Skip if the neuron is excluded, unless it's in our allowed list
            if neuron in self.excluded_neurons and neuron not in explicitly_allowed:
                continue
            if neuron in never_orphans:
                continue
            
            # Check for any connection (incoming or outgoing)
            has_connection = any(src == neuron or dst == neuron 
                                for (src, dst) in self.weights.keys())
            
            if not has_connection:
                orphans.append(neuron)
                
        return orphans

    
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
            
        # [NEW] Pre-generate distinct colors for this batch to ensure uniqueness
        from PyQt5.QtGui import QColor
        
        new_connections_created = []  # Track newly formed connections
        
        # Apply the weight updates (main thread only). Every one goes through
        # apply_weight_change, so the correlation, the sample count and the
        # spike-timing contribution that produced it end up in the ledger and
        # the Learning tab reads the real reason instead of guessing from a
        # before/after diff of its own cached copy.
        for i, (pair_str, update_data) in enumerate(weight_updates.items()):
            # Convert string key back to tuple if needed
            if isinstance(pair_str, str):
                pair = tuple(pair_str.split(','))
            else:
                pair = tuple(pair_str)

            is_new_connection = update_data.get('is_new_connection', False)
            old_weight = update_data['old_weight']
            new_weight = update_data['new_weight']

            mechanism = 'stdp' if abs(update_data.get('stdp_delta', 0.0) or 0.0) > \
                abs(update_data.get('hebbian_delta', 0.0) or 0.0) else 'hebbian'

            changed = self.apply_weight_change(
                pair, value=new_weight, mechanism=mechanism,
                detail={'correlation': update_data.get('mean_covariance'),
                        'samples': update_data.get('samples'),
                        'hebbian_delta': update_data.get('hebbian_delta'),
                        'stdp_delta': update_data.get('stdp_delta'),
                        'stdp_direction': update_data.get('stdp_direction'),
                        'window_samples': result.get('window_samples')},
                create=True, animate=False)

            if changed:
                if is_new_connection:
                    new_connections_created.append(pair)

                # Unique vibrant colour per pair so a batch is readable.
                hue = (random.random() + (i * 0.618033988749895)) % 1.0
                unique_color = QColor.fromHslF(hue, 0.95, 0.6).toRgb()
                color_tuple = (unique_color.red(), unique_color.green(), unique_color.blue())
                unique_duration = random.uniform(0.8, 2.0)

                n1, n2 = pair
                self.add_weight_animation(
                    n1, n2, old_weight, new_weight,
                    custom_color=color_tuple,
                    custom_duration=unique_duration
                )
                
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
                    # Mark new connections with a ✨
                    marker = " ✨" if pair in new_connections_created else ""
                    colored.append(f"{color}{a} ↔ {b}{marker}{RESET}")
            if colored:
                print("     Hebbian learning chosen pairs: " + "  ".join(colored))
        
        # Log new connections formed
        if new_connections_created:
            print(f"     🔗 New connections formed: {len(new_connections_created)}")
            # Sync connections list from weights after creating new connections
            self.sync_connections_from_weights()
            
        self.update()
        

    def _on_state_update_complete(self, result: dict):
        """Handle state-update results from the worker thread (main thread)."""
        self._pending_state_update = False

        if result.get('health_check'):
            return

        processed_state = result.get('processed_state', {})
        
        # [CRITICAL FIX] Filter out INPUT SENSORS so the worker cannot overwrite them.
        # The worker operates on slightly old data. For sensors, the Main Thread 
        # (Environment) is the single source of truth.
        INPUT_SENSORS = {
            "can_see_food", "is_eating", "is_sleeping", "is_sick",
            "pursuing_food", "is_fleeing", "is_startled", "external_stimulus",
            "can_see_plant"
        }
        
        # Remove sensors from the update packet before applying it
        for sensor in INPUT_SENSORS:
            if sensor in processed_state:
                del processed_state[sensor]

        # Now it is safe to update. Only hidden/output neurons will be affected.
        self.state.update(processed_state)

        # Update communication events for glow effects
        comm_events = result.get('communication_events', {})
        self.communication_events.update(comm_events)

        # Optional decay pre-application (Tamagotchi logic)
        decay_updates = result.get('decay_updates', {})
        if decay_updates and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'brain_hooks'):
                for neuron, decayed_val in decay_updates.items():
                    if neuron in self.state:
                        # [CRITICAL FIX] Don't let decay logic touch sensors
                        if neuron not in INPUT_SENSORS:
                            self.state[neuron] = decayed_val

        # [NEW] Run Enhanced Neurogenesis logic (Stress reduction, etc.)
        if hasattr(self, 'enhanced_neurogenesis'):
            self.enhanced_neurogenesis.update_neuron_activations(self.state)

        self.update() # Repaint

        # Queue next update if any
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
            # Get connector neurons for Hebbian learning exclusion
            connector_neurons = {name for name, fn in self.enhanced_neurogenesis.functional_neurons.items()
                            if fn.neuron_type == 'connector'}
            
            # Get new neurons for learning rate boost
            new_neurons = set()
            if hasattr(self, 'new_neurons'):
                new_neurons = set(self.new_neurons.keys()) if isinstance(self.new_neurons, dict) else set(self.new_neurons)
            
            self.brain_worker.update_cache(
                self.state,
                self.weights,
                self.neuron_positions,
                self.config,
                excluded_neurons=self.excluded_neurons,
                connector_neurons=connector_neurons,  # Pass connector neurons separately
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

        
    #: Normal render rate. Ten frames a second is plenty for a brain whose
    #: state changes on a game tick.
    IDLE_RENDER_FPS = 10

    #: Rate while neurons are hatching. A 0.45s expand-and-settle rendered at
    #: ten frames a second is four frames, which reads as a stutter rather than
    #: as a pulse; the burst lasts only as long as the birth sequence does.
    REVEAL_RENDER_FPS = 40

    def _set_render_fps(self, fps: int):
        """Retune the offscreen render timer."""
        timer = getattr(self, '_render_timer', None)
        if timer is not None:
            timer.setInterval(max(1, int(1000 / max(1, fps))))

    def _update_network_metrics(self):
        """Update the network tab metrics display"""
        try:
            # Try to get the parent window (SquidBrainWindow)
            parent = self.parent()
            if parent and hasattr(parent, 'network_tab'):
                parent.network_tab.update_metrics_display()
        except Exception as e:
            _LOG.debug('Ignored exception', exc_info=True)  # Silently fail if we can't update - not critical
    
    def is_neurogenesis_neuron(self, neuron_name: str) -> bool:
        """
        Check if a neuron was created through neurogenesis (and can be dragged).
        TO BE REMOVED IN FUTURE VERSION - depreceted
        """
        
        if not neuron_name:
            return False
        
        # Core neurons that should NOT be draggable
        if neuron_name in self.original_neurons:
            return True # HACK make it True anyway
        
        # ANY neuron not in original_neurons is draggable (including circular ones)
        return True

    def _periodic_neurogenesis_check(self):
        """Periodic check for neurogenesis triggers and orphans."""
        if not hasattr(self, 'check_neurogenesis_triggers'):
            return
            
        # Skip if a check is already pending
        if self._pending_neurogenesis_check:
            return
        
        # Prioritise Orphan Rescue ---
        if hasattr(self, 'enhanced_neurogenesis') and hasattr(self.enhanced_neurogenesis, 'rescue_orphan'):
            orphans = self.find_orphan_neurons()
            if orphans:
                orphan = orphans[0]
                print(f"🚑 Orphan detected: {orphan}. Creating connector neuron...")
                
                # ADD ERROR HANDLING
                try:
                    self.enhanced_neurogenesis.rescue_orphan(orphan)
                    self.update()
                    return  # Skip normal neurogenesis this tick
                except Exception as e:
                    print(f"⚠️ Failed to rescue orphan {orphan}: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Re-diagnose what the network cannot do, then act on it. Both run on
        # the main thread, where the state they read is authoritative: the
        # worker only ever had a stale copy, and its own divergent set of
        # thresholds, which is why there used to be two answers to "should this
        # brain grow?".
        monitor = getattr(self, 'capability', None)
        if monitor is not None:
            try:
                monitor.evaluate()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"⚠️ Capability evaluation failed: {e}")

        state_with_context = self.state.copy()
        self._pending_neurogenesis_check = True
        try:
            self.check_neurogenesis_triggers(state_with_context)
        except Exception as e:
            print(f"⚠️ Error in neurogenesis check: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._pending_neurogenesis_check = False

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

    def get_neuron_value(self, value):
        """
        Convert a neuron value to a numerical format for Hebbian learning.

        Args:
            value: The value of the neuron, which can be int, float, bool, or str.

        Returns:
            float: The numerical value of the neuron.
        """
        # bool must be checked before int/float: bool is a subclass of int, so
        # an ordinary (int, float) test would catch True/False first and return
        # 1.0/0.0 instead of the intended 100.0/0.0.
        if isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, (int, float)):
            return float(value)
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
                 # If it's in the list and < 5 mins, assume new.
                 pass
        return False


    def update_connection(self, neuron1, neuron2, value1, value2):
        """Retired: a third Hebbian rule that nothing called.

        It used delta = lr * a1 * a2, which can never be negative, so no amount
        of experience could produce an inhibitory synapse through it - and an
        avoidance behaviour IS an inhibitory synapse. The project's plasticity
        rule lives in src/plasticity.py and is committed by
        perform_hebbian_learning().

        Kept as a delegation so an external caller gets the real rule instead
        of a divergent one, and so the change is recorded like any other.
        """
        product = (self._as_activation(value1) / 100.0) * (self._as_activation(value2) / 100.0)
        self.apply_weight_change(
            (neuron1, neuron2), delta=self.learning_rate * product,
            mechanism='hebbian',
            detail={'note': 'direct co-activation update',
                    'correlation': round(product, 4), 'samples': 1},
            create=True, directed=False)

    @staticmethod
    def _as_activation(value) -> float:
        if isinstance(value, bool):
            return 100.0 if value else 0.0
        if isinstance(value, (int, float)):
            return float(value)
        return 0.0

    # =========================================================================
    # THE SINGLE SYNAPTIC WRITE PATH
    #
    # apply_weight_change / remove_weight come from RecordedSynapses, which the
    # headless trainer and every test double share. Only the drawing is ours:
    # everything about what a weight change IS lives in one place, so it cannot
    # be true here and subtly different there.
    # =========================================================================
    def _on_weight_changed(self, edge, old, new, animate):
        src, dst = edge
        now = time.time()
        self.weight_change_events[src] = now
        self.weight_change_events[dst] = now
        self.communication_events[src] = now
        self.communication_events[dst] = now
        if (src, dst) not in self.recently_updated_neuron_pairs and \
                (dst, src) not in self.recently_updated_neuron_pairs:
            self.recently_updated_neuron_pairs.append((src, dst))
        if animate:
            self.add_weight_animation(src, dst, old, new)
        self.mark_render_dirty()

    def _on_weight_removed(self, edge, old):
        self.mark_render_dirty()

    def is_connector_neuron(self, neuron_name: str) -> bool:
        """
        Check if a neuron is a connector neuron.
        Checks multiple sources to ensure robustness across save/load states.
        """
        if not neuron_name:
            return False
        from .brain_constants import is_social_neuron
        if is_social_neuron(neuron_name):
            return False          # a hexagon too, but a social neuron, not a relay

        # 1. Check visual shape (Primary persistence mechanism)
        if self.neuron_shapes.get(neuron_name) == 'hexagon':
            return True
            
        # 2. Check naming convention
        if neuron_name.startswith('connector_'):
            return True
            
        # 3. Check enhanced neurogenesis registry (Runtime logic)
        if hasattr(self, 'enhanced_neurogenesis') and self.enhanced_neurogenesis:
            fn = self.enhanced_neurogenesis.functional_neurons.get(neuron_name)
            if fn and fn.neuron_type == 'connector':
                return True
                
        return False

    def get_neuron_degree(self, neuron_name: str) -> int:
        """Count the number of active connections for a specific neuron."""
        count = 0
        for (u, v) in self.weights.keys():
            if u == neuron_name or v == neuron_name:
                count += 1
        return count

    def prune_weak_connections(self, threshold=0.05, min_age_sec=600):
        """Removes connections with absolute weight below threshold, ignoring connectors."""
        if not self.pruning_enabled:
            return 0

        to_delete = []

        for pair, weight in list(self.weights.items()):
            if not (isinstance(pair, tuple) and len(pair) == 2):
                continue

            neuron1, neuron2 = pair

            # IMMUNITY: Never prune connections attached to connector neurons
            if self.is_connector_neuron(neuron1) or self.is_connector_neuron(neuron2):
                continue

            # IMMUNITY: New neurons
            if self.is_new_neuron(neuron1, min_age_sec) or self.is_new_neuron(neuron2, min_age_sec):
                continue

            if abs(weight) < threshold:
                to_delete.append(pair)

        for pair in to_delete:
            self.remove_weight(
                pair, mechanism='prune',
                reason=f"weight stayed below {threshold} and neither end was new")

        if len(to_delete) > 0:
            print(f"\x1b[33mPruned {len(to_delete)} weak connections.\x1b[0m")
            self.mark_render_dirty()
            self.update()
        
        return len(to_delete)


    def perform_hebbian_learning(self):
        """Commit one plasticity cycle.

        The cycle runs through PlasticityEngine, which has been accumulating
        co-activation every tick. It runs on the main thread because that is
        where the state it reads is authoritative, and because the work is
        O(pairs) - trivially cheap next to rendering.

        The previous implementation existed twice (a threaded copy in
        BrainWorker and an unreachable synchronous copy here) and both sampled
        the network once per 30s cycle, which could not see the brief events
        that carry what actually happened to the squid.
        """
        squid = getattr(getattr(self, 'tamagotchi_logic', None), 'squid', None)
        if squid is not None and getattr(squid, 'is_sleeping', False):
            # Waking plasticity pauses during sleep; consolidation runs instead.
            return None

        engine = getattr(self, 'plasticity', None)
        if engine is None:
            return None

        connectors = self._connector_neuron_names()

        new_neurons = set()
        raw_new = getattr(self, 'new_neurons', None)
        if isinstance(raw_new, dict):
            new_neurons = set(raw_new.keys())
        elif raw_new:
            new_neurons = set(raw_new)

        result = engine.commit(
            weights=self.weights,
            neuron_names=list(self.neuron_positions.keys()),
            excluded=self.excluded_neurons,
            connectors=connectors,
            new_neurons=new_neurons,
            externally_driven=self.externally_driven,
            fixed_inputs=(self.enhanced_neurogenesis.defined_by_inputs()
                          if hasattr(getattr(self, 'enhanced_neurogenesis', None),
                                     'defined_by_inputs') else ()),
        )
        self._on_hebbian_complete(result)
        return result

    def _connector_neuron_names(self):
        neuro = getattr(self, 'enhanced_neurogenesis', None)
        if neuro is None:
            return set()
        return {name for name, fn in neuro.functional_neurons.items()
                if getattr(fn, 'neuron_type', '') == 'connector'}

    def compute_neural_modulation(self, gain: float = 0.30):
        from .propagation import compute_neural_modulation
        return compute_neural_modulation(self.state, self.weights, gain,
                                         getattr(self, 'ledger', None))

    def observe_for_learning(self):
        """Feed one tick of evidence to every learning mechanism.

        Called from propagate_activations, i.e. once per simulation tick, so a
        one-second event still contributes instead of being invisible to a
        30-second snapshot. All three consumers see the same tick of the same
        authoritative state:

          * plasticity  - what fired together, and in what order
          * capability  - what the network is failing to represent or regulate
          * causal      - whether an action's consequence window has closed
        """
        monitor = getattr(self, 'capability', None)
        if monitor is not None:
            try:
                monitor.observe(self.state)
            except Exception:
                _LOG.debug('Ignored exception', exc_info=True)

        causal = getattr(self, 'causal_learning', None)
        if causal is not None:
            try:
                causal.on_tick(self.state)
            except Exception:
                _LOG.debug('Ignored exception', exc_info=True)

        engine = getattr(self, 'plasticity', None)
        if engine is None:
            return 0
        candidates = engine.eligible_neurons(
            self.neuron_positions.keys(),
            self.excluded_neurons,
            self._connector_neuron_names())
        return engine.observe(self.state, candidates)



    def get_recently_updated_neurons(self):
        """Return the list of neuron pairs updated in the last learning cycle"""
        return self.recently_updated_neuron_pairs


    def resizeEvent(self, event):
        """Handle window resize events (the squid's startle is disabled).

        The network is drawn scaled to whatever size the widget is given
        (brain_render_worker); there is no minimum. One used to be forced here
        - 1280x900 whatever room the window had - so in a smaller Brain Tool
        the network was drawn too big and cut off at the right and bottom.
        """
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


    def save_brain_state(self):
        return {
            'weights': self.weights,
            'neuron_positions': self.neuron_positions,
            'neuron_states': self.state,
            'layer_structure': self.layers,
            'neuron_shapes': dict(self.neuron_shapes),
            'state_colors': dict(self.state_colors),
        }

    def load_brain_state(self, state):
        """Load the brain state from a saved state dictionary"""
        self.weights = state['weights']
        self.neuron_positions = state['neuron_positions']
        self.state = state.get('neuron_states', {})
        self.layers = state.get('layer_structure', [])
        
        # Sync connections list from loaded weights
        self.sync_connections_from_weights()

        # ADD THESE THREE LINES
        self.neuron_shapes = state.get('neuron_shapes', {})  # Load shapes
        self.state_colors = state.get('state_colors', {})    # Load colors
        print(f"📦 Loaded {len(self.neuron_shapes)} neuron shapes")  # Debug print

        # A save written before the layout became rows carries the old
        # scattered positions for neurons the squid was born with. Snap those
        # back onto their rows: the rows are structure, not the player's
        # arrangement, and a loaded squid should look like a newborn that has
        # been alive a while rather than like the layout this replaced.
        for neuron, pos in self.original_neuron_positions.items():
            if neuron in self.neuron_positions:
                self.neuron_positions[neuron] = pos
        # And its grown neurons onto the growth rows - its social network on
        # the social band - as they are after every birth.
        self.relayout_grown_neurons()

        # Ensure all neurons in neuron_positions exist in state
        for neuron in self.neuron_positions:
            if neuron not in self.state:
                self.state[neuron] = 50

        # Explicitly update excluded neurons if they exist in positions
        for neuron in self.excluded_neurons:
            if neuron in self.neuron_positions and neuron not in self.state:
                self.state[neuron] = False

        # Ensure visible_neurons is complete
        if not self.is_tutorial_mode:
            self.visible_neurons = set(self.original_neurons)
            for neuron in self.neuron_positions:
                if neuron not in self.excluded_neurons and neuron not in self.original_neurons:
                    self.visible_neurons.add(neuron)
            print(f"📊 Loaded {len(self.neuron_positions)} neurons, {len(self.visible_neurons)} visible")
        
        # Mark render dirty and trigger update
        self.mark_render_dirty()
        self.update()




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
    
    def initialize_connections(self):
        """Return list of connection tuples derived from self.weights.
        This ensures self.connections stays synced with self.weights as source of truth."""
        return list(self.weights.keys())
    
    def sync_connections_from_weights(self):
        """Sync self.connections list from self.weights (single source of truth).
        Call this after any modification to self.weights."""
        pass  # connections is now derived from weights; nothing to sync.

    def initialize_weights(self):
        """Give a newborn squid the instincts of its species.

        The innate table lives in brain_constants.INNATE_CONNECTIONS and the
        headless trainer hatches from the same one, so a brain trained without
        the GUI starts from the same place the squid does.

        This used to be 40% random connections at random weights in [-1, +1],
        assigned straight into the weights dict. Three things were wrong with
        that: two squids of the same species were born with different
        instincts, so "the same squid, raised differently" was not a comparison
        anyone could make; the trainer disagreed with the game about what a
        newborn is; and none of those synapses could ever say where it came
        from, because they never went through the recorded write path. Some
        rolls of the dice also left a drive with no connections at all, and the
        brain then grew a connector to rescue a defect it was born with.
        """
        from .brain_constants import (INNATE_CONNECTIONS, INNATE_ACTION_WIRING,
                                       LEARNED_ACTIONS,
                                       action_competition_wiring)
        innate = (tuple(INNATE_CONNECTIONS) + tuple(INNATE_ACTION_WIRING)
                  + action_competition_wiring())
        for source, target, weight in innate:
            if source not in self.neuron_positions or target not in self.neuron_positions:
                continue
            self.apply_weight_change(
                (source, target), value=float(weight), mechanism='innate',
                detail={'note': "this squid was born with it"},
                create=True, animate=False)
        self.sync_connections_from_weights()
        if LEARNED_ACTIONS:
            print(f"🥚 Born knowing how to move, eat and flee. "
                  f"Must learn: {', '.join(a[4:] for a in LEARNED_ACTIONS)}")

    def reset_to_newborn(self):
        """Return this widget to the brain a squid hatches with.

        For a new squid taking over the tank. Resetting only the activations
        (create_initial_state) left every learned weight, every grown neuron
        and the whole cognitive history in place, so a "new" squid silently
        inherited the previous one's mind. Each subsystem is reset through its
        own reset method; the innate synapses are then laid down by the same
        initialize_weights() a freshly built widget uses, so they are recorded
        in the reset ledger as innate.
        """
        from .brain_constants import ACTION_NEURONS, action_resting_level

        from .brain_constants import newborn_neurons
        self._brain_document = {}
        self.original_neuron_positions = dict(newborn_neurons())
        self.original_neurons = list(self.original_neuron_positions)
        self.innate_neurons = frozenset(self.original_neurons)
        self.ledger.reset()
        self.capability.reset()
        self.causal_learning.reset()
        self.action_discovery.reset()
        self.plasticity.reset()
        self.consolidation.from_dict({})
        self.consolidation.clear_buffer()
        self.enhanced_neurogenesis.reset_state()
        self.experience_buffer = self.enhanced_neurogenesis.experience_buffer
        self.neurogenesis_data = {
            'new_neurons': [],
            'last_neuron_time': time.time(),
            'new_neurons_details': {},
        }
        self.action_representations = {}
        self.externally_driven = set()
        self.percepts = {}
        self.neuron_shapes = {}
        self.layers = []
        self._personality_bias_applied = False

        self.neuron_positions = self.original_neuron_positions.copy()
        self.state = self.create_initial_state()
        for action_name in ACTION_NEURONS:
            self.state.setdefault(action_name, action_resting_level(action_name))
        for sensor_name in self.original_neuron_positions:
            self.state.setdefault(sensor_name, 0.0)
        self.communication_events = {name: 0 for name in self.neuron_positions}
        self.visible_neurons = set()

        self.weights = {}
        self.initialize_weights()
        self.associations = self.compute_backend.zeros(
            (len(self.neuron_positions), len(self.neuron_positions)))
        self.mark_render_dirty()
        self.update()

    def apply_personality_bias(self, personality):
        """Tilt this squid's innate reflexes toward its personality.

        Personality used to be a multiplier table the decision engine applied
        to finished behaviour weights, which put it outside the network
        entirely: nothing the squid experienced could ever change it, and it
        appeared nowhere in the brain the player was looking at. Here it is a
        one-off adjustment to the innate synapses themselves, recorded like any
        other weight change, so a timid squid is visibly one with a stronger
        startle reflex - and ordinary learning can wear that down.

        Applied once per squid; calling it again is a no-op.
        """
        from .brain_constants import INNATE_PERSONALITY_BIAS

        if getattr(self, '_personality_bias_applied', False):
            return
        value = getattr(personality, 'value', personality)
        if not isinstance(value, str):
            return
        bias = INNATE_PERSONALITY_BIAS.get(value.lower())
        if not bias:
            return

        self._personality_bias_applied = True
        for source, target, multiplier in bias:
            key = (source, target)
            if key not in self.weights:
                continue
            new_value = max(-1.0, min(1.0, float(self.weights[key]) * float(multiplier)))
            self.apply_weight_change(
                key, value=new_value, mechanism='innate',
                detail={'note': f"born {value} - {'stronger' if multiplier > 1 else 'weaker'} "
                                f"than the species baseline"},
                create=False, animate=False)
        self.sync_connections_from_weights()
        print(f"🧬 Innate reflexes tilted for a {value} squid")

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
                _LOG.warning('Handled exception', exc_info=True)
                print(f"\x1b[31mNeurogenesis logging failed: {str(e)}\x1b[0m")

    # In brain_widget.py

    def update_state(self, new_state=None):
        """
        Update neuron activations.

        With `new_state`: the caller is the world (sensors + squid stats) and is
        the source of truth for the keys it supplies.
        Without: run one forward-propagation tick over the network-driven
        neurons. This is the project's single propagation entry point.
        """
        if new_state is not None:
            for k, v in (new_state.items() if isinstance(new_state, dict) else []):
                # normalise_activation is the one place bools/binaries are
                # coerced, so a value no longer depends on whether the neuron
                # happens to be present in neuron_positions.
                self.state[k] = normalise_activation(k, v)

            if hasattr(self, 'brain_worker') and self.brain_worker:
                self._update_worker_cache()

            self.mark_render_dirty()
            self.update()
            return

        self.propagate_activations()

    # =========================================================================
    # FORWARD PROPAGATION - the single authoritative implementation
    # =========================================================================
    def propagate_activations(self, smoothing: float = None):
        """
        Compute one timestep of activation for every network-driven neuron.

        The rule itself lives in src/propagation.py, which is the project's
        single implementation of it - the headless trainer steps a network with
        exactly the same function, so a brain trained there behaves identically
        when the squid runs it.

        Contract
        --------
        * Reads   : self.state (activations), self.weights (synapses)
        * Writes  : self.state, for network-driven neurons only
        * Never   : touches a PURE_INPUT (sensor) or CORE_STAT neuron - those
                    are owned by the world and the squid model respectively.

        Returns the dict of neurons it changed (useful for tests and logging).
        """
        from .propagation import propagate

        if smoothing is None:
            smoothing = getattr(self, 'propagation_smoothing', 0.5)

        # Neurons the world writes go first, so everything downstream - the
        # learning mechanisms below and the transfer function after them - sees
        # one consistent tick.
        self.drive_external_neurons(smoothing)

        # Which neurons may we compute? Anything in the network that is not
        # owned by the world. neuron_positions is the network's membership list.
        targets = [n for n in self.neuron_positions
                   if is_network_driven(n) and n not in self.excluded_neurons
                   and n not in self.externally_driven]
        if not targets:
            # Still gather evidence. A brain with nothing to compute must go on
            # learning: this used to sit after an early return, so a squid whose
            # network was all sensors and drives could never learn at all.
            self.observe_for_learning()
            return {}

        functional = getattr(getattr(self, 'enhanced_neurogenesis', None),
                             'functional_neurons', {}) or {}
        strengths = {name: getattr(fn, 'strength_multiplier', 1.0)
                     for name, fn in functional.items()}
        resting = {name: fn.resting_level for name, fn in functional.items()
                   if getattr(fn, 'resting_level', None) is not None}

        noise = {}
        if isinstance(self.neurons, dict):
            for name in targets:
                props = self.neurons.get(name)
                if isinstance(props, dict) and props.get('noise'):
                    noise[name] = props['noise']

        growth = getattr(self, 'enhanced_neurogenesis', None)
        thresholds = (growth.combination_thresholds()
                      if hasattr(growth, 'combination_thresholds') else None)
        changed = propagate(self.state, self.weights, targets,
                            strengths=strengths, noise=noise, smoothing=smoothing,
                            resting=resting, thresholds=thresholds)

        # Evidence is gathered AFTER the forward pass, so every mechanism sees
        # this tick's sensors alongside the activations those sensors actually
        # produced. Observing first paired each tick's world with the PREVIOUS
        # tick's network, which inverted the very thing the capability monitor
        # measures: a detector wired +0.9 from can_see_food was recorded at its
        # no-food value on exactly the ticks food was visible, and the monitor
        # concluded it was a detector for the ABSENCE of food.
        self.observe_for_learning()

        if changed:
            self.mark_render_dirty()
            if hasattr(self, 'brain_worker') and self.brain_worker:
                self._update_worker_cache()

        return changed

    def _fast_apply_external_state(self, new_state):
        """Quickly apply externally provided state (plugin updates, etc.)"""
        for k, v in new_state.items():
            if k in self.neuron_positions:
                if self.is_binary_neuron(k):
                    self.state[k] = 100.0 if (v if isinstance(v, bool) else float(v) > 50) else 0.0
                else:
                    self.state[k] = float(v) if isinstance(v, (int, float)) else v
        
        # >>> ADDED: Mark render dirty <<<
        self.mark_render_dirty()

    def provide_outcome_feedback(self, outcome_value: float, reason: str = ""):
        """Tell the brain how that turned out.

        outcome_value: 1.0 = very positive, 0.0 = neutral, -1.0 = very negative

        Two things follow. Grown neurons that were recently active have their
        utility score updated, which is what keeps pruning honest. And the
        value is delivered as a reward signal along the spike-timing
        eligibility traces, so the synapses that were causally active in the
        seconds before the outcome are the ones that change.
        """
        current_time = time.time()

        engine = getattr(self, 'enhanced_neurogenesis', None)
        if engine is not None:
            for name, func_neuron in engine.functional_neurons.items():
                # Was this neuron recently active?
                if hasattr(func_neuron, 'last_activated') and current_time - func_neuron.last_activated < 30:
                    if hasattr(func_neuron, 'update_utility_score'):
                        func_neuron.update_utility_score(outcome_value)

        self.deliver_reward(outcome_value, reason)

    def deliver_reward(self, signal: float, reason: str = "") -> int:
        """Broadcast an outcome back along the STDP eligibility traces.

        The third factor in a three-factor learning rule. Spike timing says
        which synapses were causally ordered; the trace says how recently; this
        says whether it was worth repeating. Returns the number of synapses
        that changed.

        This used to live in the STDP plugin, which monkey-patched the worker
        and wrote brain_widget.weights directly, so a caretaker's reward only
        reached the brain when a plugin happened to be enabled - and left no
        record when it did.
        """
        engine = getattr(self, 'plasticity', None)
        stdp = getattr(engine, 'stdp', None) if engine is not None else None
        if stdp is None or not signal:
            return 0
        try:
            deltas = stdp.apply_reward_modulation(
                float(signal), rate=engine.config.learning_rate)
        except Exception:
            return 0

        applied = 0
        note = reason or ("something good happened" if signal > 0
                          else "something bad happened")
        for edge, delta in (deltas or {}).items():
            if not delta:
                continue
            delta = max(-0.08, min(0.08, float(delta)))
            if self.apply_weight_change(
                    edge, delta=delta, mechanism='causal_reward',
                    detail={'reward_signal': round(float(signal), 3),
                            'note': f"{note}, and this synapse was firing in the "
                                    f"right order just before it"},
                    create=False, directed=False):
                applied += 1
        if applied:
            print(f"⚡ Reward {signal:+.2f} ({note}) reached {applied} synapse(s)")
        return applied


    
    
    def check_neurogenesis_triggers(self, state):
        """Consider growing new structure.

        Kept under its historical name because it is the project's structural
        growth entry point, but the question it asks has changed completely.
        It no longer looks for an event that crossed a threshold; it asks the
        capability monitor what this network persistently cannot represent,
        regulate or express, and grows a neuron only when the answer is
        something ordinary learning has already failed to fix.
        """
        if not state.get('neurogenesis_active', True):
            return False

        engine = getattr(self, 'enhanced_neurogenesis', None)
        if engine is None:
            return False

        deficit = None
        if hasattr(engine, 'find_deficit'):
            deficit = engine.find_deficit(state)
            if deficit is None:
                return False

        # The experience context is the birth record's snapshot of the squid's
        # life at the moment it grew - it is *context*, not the reason.
        recent_actions = state.get('recent_actions', [])
        environment = {
            'food_count': state.get('food_count', 0),
            'poop_count': state.get('poop_count', 0),
            'has_rock': state.get('carrying_rock', False),
            'is_eating': state.get('is_eating', False),
            'new_object_encountered': state.get('new_object_encountered', False),
            'recent_positive_outcome': state.get('recent_positive_outcome', False),
        }
        context = engine.capture_experience_context(
            trigger_type=(deficit.suggested_type if deficit is not None else 'novelty'),
            brain_state=self.state,
            recent_actions=recent_actions,
            environment=environment)

        buffer = getattr(self, 'experience_buffer', None)
        if buffer is not None and hasattr(buffer, 'add_experience'):
            try:
                buffer.add_experience(context)
            except Exception:
                _LOG.debug('Ignored exception', exc_info=True)

        # Pass the diagnosis through rather than letting the engine re-run it:
        # a second reading of a state that has moved on could disagree with the
        # first, and then the birth record would name a different deficit from
        # the one that actually justified the growth.
        if not engine.should_create_neuron(context, deficit=deficit):
            return False

        neuron_name = engine.create_functional_neuron(context, deficit=deficit)
        if neuron_name and self.pruning_enabled:
            current_count = len(self.neuron_positions) - len(self.excluded_neurons)
            max_neurons = self.neurogenesis_config.get('max_neurons', 32)
            if current_count > max_neurons * 0.85:
                engine.intelligent_pruning()
        return neuron_name is not None

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
        """Remove weakly connected or inactive neurons, skipping connectors."""
        min_neurons = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        if current_count <= min_neurons:
            return False

        candidates = []
        for neuron in list(self.neuron_positions.keys()):
            # Basic exclusions
            if neuron in self.original_neuron_positions or neuron in self.excluded_neurons:
                continue
            
            # IMMUNITY: Connector neurons are structural and cannot be pruned
            if self.is_connector_neuron(neuron):
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
            if neuron_to_remove in self.neuron_positions:
                del self.neuron_positions[neuron_to_remove]
            if neuron_to_remove in self.state:
                del self.state[neuron_to_remove]
            if neuron_to_remove in self.neuron_shapes:
                del self.neuron_shapes[neuron_to_remove]
            if neuron_to_remove in self.state_colors:
                del self.state_colors[neuron_to_remove]
            self.forget_action_representation(neuron_to_remove)
                
            for conn in list(self.weights.keys()):
                if isinstance(conn, tuple) and (conn[0] == neuron_to_remove or conn[1] == neuron_to_remove):
                    self.remove_weight(
                        conn, mechanism='prune',
                        reason=f"{neuron_to_remove} was pruned for weak connections "
                               f"and inactivity, so its synapses went with it")
                    
            if neuron_to_remove in self.neurogenesis_data.get('new_neurons', []):
                self.neurogenesis_data['new_neurons'].remove(neuron_to_remove)
                
            reason = "weak connections/activity"
            self.log_neurogenesis_event(neuron_to_remove, "pruned", reason)
            
            self.mark_render_dirty()
            self.update()
            return True
        return False

    def apply_repulsion_force(self, iterations=15, strength=0.6, threshold=120.0):
        """Applies repulsion force and enforces boundary constraints from config."""
        
        from .brain_constants import layout_bounds

        neuron_props = self.config.neurogenesis.get('neuron_properties', {})
        force_bounds = neuron_props.get('force_bounds', True)
        centering_force = neuron_props.get('centering_force', 0.02)

        # Bounds and centre both come from the DEFAULT neuron layout rather than
        # from the 1024x768 logical canvas. Pulling toward the canvas centre
        # while allowing the full canvas let the network drift into a clump
        # well below the area the Brain Tool shows at its opening size.
        min_x, min_y, max_x, max_y = layout_bounds(self.original_neuron_positions)
        center_x, center_y = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0

        neuron_list = [name for name in self.neuron_positions.keys() if name not in self.excluded_neurons]

        for _ in range(iterations):
            displacements = {name: [0.0, 0.0] for name in neuron_list}

            # 1. Repulsion between neurons
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

            # 2. Apply movements + Centering Force + Boundary Constraints
            damping = 0.5
            moved = False
            
            for name in neuron_list:
                # Skip core neurons IF you want them fixed, but requirement says randomise start
                # so we allow them to move, but maybe less? For now, move all.
                
                pos = self.neuron_positions[name]
                disp = displacements[name]
                
                # Apply Centering Force (pull towards middle)
                if centering_force > 0:
                    dir_to_center_x = center_x - pos[0]
                    dir_to_center_y = center_y - pos[1]
                    disp[0] += dir_to_center_x * centering_force
                    disp[1] += dir_to_center_y * centering_force

                if abs(disp[0]) > 0.1 or abs(disp[1]) > 0.1:
                    new_x = pos[0] + disp[0] * damping
                    new_y = pos[1] + disp[1] * damping
                    
                    # Force Bounds
                    if force_bounds:
                        new_x = max(min_x, min(max_x, new_x))
                        new_y = max(min_y, min(max_y, new_y))
                        
                    self.neuron_positions[name] = (new_x, new_y)
                    moved = True

            if not moved:
                break
        if moved:
           self.update()


    def update_weights(self):

        if self.frozen_weights is not None:
            return

        # Iterate over a copy of the actual weight keys ---
        for conn in list(self.weights.keys()):
            # Check if the connection still exists (it might be pruned concurrently)
            if conn in self.weights:
                # Clamp the weight to stay within [-1, 1]
                self.weights[conn] = max(-1, min(1, self.weights[conn]))

    def freeze_weights(self):
        self.frozen_weights = self.weights.copy()

    def unfreeze_weights(self):
        self.frozen_weights = None

    def strengthen_connection(self, neuron1, neuron2, amount, mechanism='reflex',
                              reason=""):
        """Strengthen a connection, respecting connector limits for new links.

        Used by the innate reflexes (eating, cleaning, being startled) that
        wire experience directly rather than waiting for a learning cycle. It
        goes through the same recorded write path as everything else.
        """
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)

        exists = pair in self.weights or reverse_pair in self.weights

        # --- CONNECTOR LIMIT CHECK ---
        if not exists:
            if self.is_connector_neuron(neuron1) and self.get_neuron_degree(neuron1) >= 3:
                return
            if self.is_connector_neuron(neuron2) and self.get_neuron_degree(neuron2) >= 3:
                return

        self.apply_weight_change(
            pair, delta=amount, mechanism=mechanism,
            detail={'note': reason or 'an innate response to what just happened'},
            create=True, directed=False)
        self.update()

    def capture_training_data(self, state):
        training_sample = [state[neuron] for neuron in self.neuron_positions.keys()]
        self.training_data.append(training_sample)
        print("Captured training data:", training_sample)

    def train_hebbian(self):
        print("Starting Hebbian training...")
        for sample in self.training_data:
            self.associations = self.compute_backend.hebbian(
                self.associations, sample, self.learning_rate
            )
        self.training_data = []

    def get_association_strength(self, neuron1, neuron2):
        idx1 = list(self.neuron_positions.keys()).index(neuron1)
        idx2 = list(self.neuron_positions.keys()).index(neuron2)
        return self.compute_backend.get_value(self.associations, idx1, idx2)
    
    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

    def show_diagnostic_report(self):
        from .brain_dialogs import DiagnosticReportDialog
        dialog = DiagnosticReportDialog(self, self.parent())
        dialog.exec_()

    def reset_positions(self):
        self.neuron_positions = self.original_neuron_positions.copy()
        
        # Check config for randomization preference
        neuron_props = self.config.neurogenesis.get('neuron_properties', {})
        if neuron_props.get('randomize_start_positions', False):
            self._randomize_all_positions()
            
        self.update()

    def _randomize_all_positions(self):
        """Randomize positions of GROWN neurons within the growth zone.

        Neurons the squid was born with are never moved. They are laid out in
        labelled rows - CORE, ACTIONS, SENSES - and the rows are the whole
        point: scattering them destroys the one thing in the picture that says
        which neurons are the same kind of thing.
        """
        from .brain_constants import layout_bounds

        # Confined to the growth zone below the rows, not the whole logical
        # canvas - a randomised start that puts neurons where the Brain Tool
        # cannot show them is not a start the player can read.
        min_x, min_y, max_x, max_y = layout_bounds(self.original_neuron_positions)

        moved = 0
        for name in self.neuron_positions:
            if name in self.innate_neurons:
                continue                      # the rows stay where they are
            rx = random.randint(int(min_x), int(max_x))
            ry = random.randint(int(min_y), int(max_y))
            self.neuron_positions[name] = (rx, ry)
            moved += 1

        print(f"🎲 Randomized {moved} grown neuron positions "
              f"({len(self.innate_neurons)} born neurons held in their rows)")
        
    def get_tutorial_glow_opacity(self):
        """Get current glow opacity (for Qt property animation)"""
        return self._tutorial_glow_opacity
    
    def set_tutorial_glow_opacity(self, value):
        """Set glow opacity and trigger repaint (for Qt property animation)"""
        self._tutorial_glow_opacity = value
        self.update()
    
    # Qt property for animation
    tutorial_glow_opacity = QtCore.pyqtProperty(float, get_tutorial_glow_opacity, set_tutorial_glow_opacity)


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
