"""
Neuron Output Binding System

This module enables custom neurons in the brain designer to trigger game behaviors
when they fire. It creates a bidirectional system:

INPUT (Sensors):  Game Events → Hooks → Neuron Activation
OUTPUT (Actuators): Neuron Fires → Threshold Check → Hooks → Game Behavior
"""

import time
import random
from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

# Try importing PyQt5 for the floating console
try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    HAS_QT = True
except ImportError:
    HAS_QT = False

# ANSI Colors for Console Output (Fallback)
ANSI_ORANGE = "\033[38;5;208m"
ANSI_RESET = "\033[0m"

class OutputTriggerMode(Enum):
    """How the output should be triggered."""
    THRESHOLD_RISING = "rising"      # Fire when crossing threshold upward
    THRESHOLD_FALLING = "falling"    # Fire when crossing threshold downward  
    THRESHOLD_ABOVE = "above"        # Fire continuously while above threshold
    THRESHOLD_BELOW = "below"        # Fire continuously while below threshold
    ON_CHANGE = "change"             # Fire on any significant change


@dataclass
class NeuronOutputBinding:
    """
    Binds a neuron to an output hook.
    
    When the neuron's activation meets the trigger conditions,
    the bound hook is fired with the activation value.
    """
    neuron_name: str
    output_hook: str
    threshold: float = 70.0
    trigger_mode: OutputTriggerMode = OutputTriggerMode.THRESHOLD_RISING
    cooldown: float = 1.0  # Seconds between firings
    enabled: bool = True

    # Chance the behaviour actually happens once the neuron has crossed its
    # threshold. 1.0 is a reflex that always fires; the ink cloud is 0.35,
    # which is what makes a startled squid SOMETIMES ink instead of always.
    # Keeping the chance on the binding makes it a visible, tunable property
    # of the reflex rather than a random.random() buried in a behaviour rule.
    probability: float = 1.0
    
    # Optional parameters passed to the hook
    hook_params: Dict[str, Any] = field(default_factory=dict)
    
    # Runtime state (not saved)
    last_fire_time: float = 0.0
    last_activation: float = 0.0
    
    def to_dict(self) -> dict:
        """Serialize for saving."""
        return {
            'neuron_name': self.neuron_name,
            'output_hook': self.output_hook,
            'threshold': self.threshold,
            'trigger_mode': self.trigger_mode.value,
            'cooldown': self.cooldown,
            'enabled': self.enabled,
            'probability': self.probability,
            'hook_params': self.hook_params,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NeuronOutputBinding':
        """Deserialize from saved data."""
        trigger_mode = OutputTriggerMode(data.get('trigger_mode', 'rising'))
        return cls(
            neuron_name=data['neuron_name'],
            output_hook=data['output_hook'],
            threshold=data.get('threshold', 70.0),
            trigger_mode=trigger_mode,
            cooldown=data.get('cooldown', 1.0),
            enabled=data.get('enabled', True),
            probability=float(data.get('probability', 1.0)),
            hook_params=data.get('hook_params', {}),
        )
    
    def should_fire(self, current_activation: float, current_time: float) -> bool:
        """Check if this binding should fire given current activation.

        NOTE: the cooldown is checked *after* the edge test, and the caller only
        advances last_activation once the edge has been evaluated. Checking the
        cooldown first (as this did) meant a rising-edge crossing that landed
        inside the cooldown window was swallowed instead of deferred, and the
        binding then never fired at all until the signal fell and rose again.
        """
        if not self.enabled:
            return False

        should_fire = False
        
        if self.trigger_mode == OutputTriggerMode.THRESHOLD_RISING:
            # Fire when crossing threshold upward
            should_fire = (
                self.last_activation < self.threshold and 
                current_activation >= self.threshold
            )
        
        elif self.trigger_mode == OutputTriggerMode.THRESHOLD_FALLING:
            # Fire when crossing threshold downward
            should_fire = (
                self.last_activation >= self.threshold and 
                current_activation < self.threshold
            )
        
        elif self.trigger_mode == OutputTriggerMode.THRESHOLD_ABOVE:
            # Fire continuously while above threshold
            should_fire = current_activation >= self.threshold
        
        elif self.trigger_mode == OutputTriggerMode.THRESHOLD_BELOW:
            # Fire continuously while below threshold
            should_fire = current_activation < self.threshold
        
        elif self.trigger_mode == OutputTriggerMode.ON_CHANGE:
            # Fire on significant change (>10% difference)
            should_fire = abs(current_activation - self.last_activation) > 10.0

        if not should_fire:
            return False

        # Edge established - now respect the cooldown. An edge suppressed here
        # is retried on the next evaluation because the caller holds
        # last_activation back until the binding is actually allowed to fire.
        if current_time - self.last_fire_time < self.cooldown:
            return False

        return True

    def is_edge_pending(self, current_activation: float) -> bool:
        """True when an edge exists but the cooldown is suppressing it."""
        if not self.enabled:
            return False
        if self.trigger_mode == OutputTriggerMode.THRESHOLD_RISING:
            return self.last_activation < self.threshold <= current_activation
        if self.trigger_mode == OutputTriggerMode.THRESHOLD_FALLING:
            return current_activation < self.threshold <= self.last_activation
        if self.trigger_mode == OutputTriggerMode.ON_CHANGE:
            return abs(current_activation - self.last_activation) > 10.0
        return False


# =============================================================================
# FLOATING LOG WINDOW
# =============================================================================

if HAS_QT:
    class NeuronLogWindow(QtWidgets.QWidget):
        """A floating console window for neuron output logs."""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Neuron Monitor")
            
            # Window Flags: Tool (small title bar), Stay on Top
            self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
            self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
            
            self.resize(800, 200)
            
            # Styling: Dark background, Orange text (Consolas/Monospace)
            self.setStyleSheet("""
                QWidget {
                    background-color: #121212;
                    color: #ffb74d;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 10pt;
                }
                QPlainTextEdit {
                    border: 1px solid #333;
                    selection-background-color: #333;
                }
            """)
            
            # Layout
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(2, 2, 2, 2)
            
            # Text Area
            self.text_area = QtWidgets.QPlainTextEdit()
            self.text_area.setReadOnly(True)
            self.text_area.setMaximumBlockCount(1000) # Limit history
            layout.addWidget(self.text_area)
            
            # Initial positioning
            self._position_at_bottom_center()
            
        def _position_at_bottom_center(self):
            """Move window to bottom center of primary screen."""
            if not QtWidgets.QApplication.instance():
                return
                
            screen = QtWidgets.QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                # Center X
                x = geo.x() + (geo.width() - self.width()) // 2
                # Bottom Y (with some padding)
                y = geo.y() + geo.height() - self.height() - 50
                self.move(x, y)

        def log(self, message: str):
            """Append a message to the log."""
            timestamp = time.strftime("%H:%M:%S")
            self.text_area.appendPlainText(f"[{timestamp}] {message}")
            
            # Auto-scroll to bottom
            bar = self.text_area.verticalScrollBar()
            bar.setValue(bar.maximum())
else:
    class NeuronLogWindow:
        """Dummy class if PyQt is not available."""
        def log(self, msg): print(msg)
        def show(self): pass


# =============================================================================
# PREDEFINED OUTPUT HOOKS
# =============================================================================

STANDARD_OUTPUT_HOOKS = {
    # Movement behaviors
    'neuron_output_flee': {
        'description': 'Trigger fleeing behavior',
        'category': 'movement',
        'default_threshold': 80.0,
    },
    'neuron_output_seek_food': {
        'description': 'Drive food-seeking behavior',
        'category': 'movement',
        'default_threshold': 60.0,
    },
    'neuron_output_seek_plant': {
        'description': 'Move toward nearest plant',
        'category': 'movement',
        'default_threshold': 50.0,
    },
    'neuron_output_approach_rock': {
        'description': 'Approach nearest rock',
        'category': 'movement',
        'default_threshold': 50.0,
    },
    'neuron_output_wander': {
        'description': 'Random exploration movement',
        'category': 'movement',
        'default_threshold': 40.0,
    },
    
    # Action behaviors
    'neuron_output_throw_rock': {
        'description': 'Throw held rock',
        'category': 'action',
        'default_threshold': 70.0,
    },
    'neuron_output_pick_up_rock': {
        'description': 'Pick up nearby rock',
        'category': 'action',
        'default_threshold': 60.0,
    },
    'neuron_output_ink_cloud': {
        'description': 'Release defensive ink cloud',
        'category': 'action',
        'default_threshold': 85.0,
    },
    'neuron_output_eat': {
        'description': 'Eat nearby food',
        'category': 'action',
        'default_threshold': 50.0,
    },
    
    # State changes
    'neuron_output_sleep': {
        'description': 'Initiate sleep',
        'category': 'state',
        'default_threshold': 90.0,
    },
    'neuron_output_wake': {
        'description': 'Wake from sleep',
        'category': 'state',
        'default_threshold': 30.0,
    },
    'neuron_output_startle': {
        'description': 'Trigger startle response',
        'category': 'state',
        'default_threshold': 75.0,
    },
    'neuron_output_calm': {
        'description': 'Reduce anxiety/calm down',
        'category': 'state',
        'default_threshold': 20.0,
    },
    
    # Stat modifications
    'neuron_output_boost_happiness': {
        'description': 'Increase happiness',
        'category': 'stats',
        'default_threshold': 70.0,
    },
    'neuron_output_boost_curiosity': {
        'description': 'Increase curiosity',
        'category': 'stats',
        'default_threshold': 60.0,
    },
    'neuron_output_reduce_anxiety': {
        'description': 'Decrease anxiety',
        'category': 'stats',
        'default_threshold': 30.0,
    },

     # Colour change
    'neuron_output_change_color': {
        'description': 'Change the squid body color when triggered. Can specify specific color parameters.',
        'category': 'action',
        'default_threshold': 60.0,
        'has_params': True,
    },
    
    # Custom/plugin hooks. NOTE: no built-in handler by design - this hook only
    # does anything when a plugin subscribes to it. It is therefore hidden from
    # the Brain Designer unless a subscriber exists, so the user cannot build a
    # binding that is guaranteed to be inert.
    'neuron_output_custom': {
        'description': 'Custom behavior (plugin-defined)',
        'category': 'custom',
        'default_threshold': 50.0,
        'requires_plugin': True,
    },
}


class NeuronOutputMonitor:
    """
    Monitors neuron activations and triggers output hooks when thresholds are met.
    
    This is the runtime component that connects the neural network to game behaviors.
    """
    
    def __init__(self, tamagotchi_logic):
        self.logic = tamagotchi_logic
        self.bindings: List[NeuronOutputBinding] = []
        self.enabled = True
        
        # Statistics
        self.total_fires = 0
        self.fires_by_hook: Dict[str, int] = {}
        
        # Log Window
        self.log_window = None
        
        # Register default hook handlers
        self._register_default_handlers()

        # Every squid is born with its actions connected to its body.
        self.install_innate_bindings()

    def install_innate_bindings(self):
        """Connect each action neuron to the actuator that carries it out.

        This is the squid's BODY, not its knowledge: it can always physically
        ink, or swim at a rock. What decides whether it ever does is whether
        anything in the network drives the neuron hard enough to cross the
        threshold - and for everything except moving, eating and fleeing,
        nothing does until the squid learns it. See INNATE_ACTION_WIRING.

        Bindings the player or a custom brain already defined for a neuron are
        left alone, so this can never overwrite a deliberate choice.
        """
        from .brain_constants import innate_bindings

        installed = 0
        for neuron, hook, threshold, cooldown, probability in innate_bindings():
            if any(b.neuron_name == neuron for b in self.bindings):
                continue
            self.bindings.append(NeuronOutputBinding(
                neuron_name=neuron,
                output_hook=hook,
                threshold=float(threshold),
                trigger_mode=OutputTriggerMode.THRESHOLD_RISING,
                cooldown=float(cooldown),
                probability=float(probability),
            ))
            installed += 1
        if installed:
            self._log(f"Innate reflexes wired to the body: {installed} bindings.")
    
    def _ensure_log_window(self):
        """Create the log window if it doesn't exist and Qt is available."""
        if self.log_window is None and HAS_QT:
            # Only create if QApplication exists
            if QtWidgets.QApplication.instance():
                self.log_window = NeuronLogWindow()

    def _log(self, message: str):
        """Helper to print logs to floating window (or console fallback)."""
        if HAS_QT and QtWidgets.QApplication.instance():
            self._ensure_log_window()
            if self.log_window:
                self.log_window.log(message)
        else:
            # Fallback for headless or non-Qt environments
            print(f"{ANSI_ORANGE}[NeuronOutputMonitor]{ANSI_RESET} {message}")

    def _register_default_handlers(self):
        """Register the standard output hooks and subscribe our handlers once."""
        if not hasattr(self.logic, 'plugin_manager'):
            self._log("Cannot register handlers: plugin_manager not available")
            return

        pm = self.logic.plugin_manager

        # The monitor is part of the engine, not a plugin. PluginManager keeps
        # it in core_subscribers so enabled_plugins.clear() cannot silence it.
        # (It used to add itself to enabled_plugins, which TamagotchiLogic and
        # load_all_plugins then cleared - disabling every binding at startup.)
        if hasattr(pm, 'core_subscribers'):
            pm.core_subscribers.add('neuronoutputmonitor')

        for hook_name in STANDARD_OUTPUT_HOOKS.keys():
            pm.register_hook(hook_name)

        import inspect
        subscribed = 0
        for method_name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if not method_name.startswith('_handle_'):
                continue
            hook_name = f"neuron_output_{method_name[8:]}"
            if hook_name not in STANDARD_OUTPUT_HOOKS:
                continue
            # Subscribe exactly once. A "redundant safety pass" used to repeat
            # this loop, so every handler ran twice and every stat-modifying
            # output applied double its documented magnitude.
            already = any(h.get('plugin') == 'NeuronOutputMonitor'
                          for h in pm.hooks.get(hook_name, []))
            if already:
                continue
            if pm.subscribe_to_hook(hook_name, 'NeuronOutputMonitor', method):
                subscribed += 1

        self._log(f"Ready. {subscribed} output handlers subscribed.")

    # =========================================================================
    # BINDING MANAGEMENT
    # =========================================================================

    def monitor(self, neuron_activations: Dict[str, float], current_time: Optional[float] = None):
        """Evaluate all bindings against an explicit activation snapshot."""
        self._evaluate(neuron_activations, current_time)

    def _evaluate(self, activations: Dict[str, float], current_time: Optional[float] = None):
        """The single binding-evaluation loop used by every entry point."""
        if not self.enabled or not self.bindings:
            return

        current_time = current_time or time.time()

        for binding in self.bindings:
            raw = activations.get(binding.neuron_name)
            if raw is None:
                continue
            try:
                activation = float(raw)
            except (TypeError, ValueError):
                activation = 100.0 if raw else 0.0

            if binding.should_fire(activation, current_time):
                self._fire_binding(binding, activation, current_time)
                binding.last_activation = activation
            elif binding.is_edge_pending(activation):
                # Hold last_activation back so the edge survives the cooldown
                # and fires on a later evaluation instead of being lost.
                continue
            else:
                binding.last_activation = activation

    def add_binding(self, binding: NeuronOutputBinding) -> bool:
        """Add a new output binding."""
        self.bindings.append(binding)
        self._log(f"Added binding: {binding.neuron_name} → {binding.output_hook}")
        return True
    
    def remove_binding(self, neuron_name: str, output_hook: str) -> bool:
        """Remove bindings matching neuron and hook name."""
        initial_len = len(self.bindings)
        self.bindings = [
            b for b in self.bindings 
            if not (b.neuron_name == neuron_name and b.output_hook == output_hook)
        ]
        return len(self.bindings) < initial_len
    
    def get_bindings_for_neuron(self, neuron_name: str) -> List[NeuronOutputBinding]:
        """Get all output bindings for a specific neuron."""
        return [b for b in self.bindings if b.neuron_name == neuron_name]
    
    def clear_bindings(self):
        """Remove all bindings."""
        self.bindings.clear()
    
    def load_bindings_from_brain(self, brain_data: dict):
        """Load output bindings from brain configuration data.

        If the payload carries no 'output_bindings' key at all the current
        bindings are left alone. This used to clear unconditionally, so loading
        a save (whose brain_state never contained the key) silently destroyed
        every binding the player had made.
        """
        if 'output_bindings' not in (brain_data or {}):
            return

        self.clear_bindings()

        output_bindings = brain_data.get('output_bindings') or []
        for binding_data in output_bindings:
            try:
                binding = NeuronOutputBinding.from_dict(binding_data)
                self.add_binding(binding)
            except Exception as e:
                self._log(f"Error loading binding: {e}")

        # Re-attach any innate reflex the loaded payload did not carry. A save
        # written before action neurons existed has none of them, and a squid
        # restored from it would have a brain that wants to flee and no body
        # able to do it.
        self.install_innate_bindings()
    
    def export_bindings(self) -> List[dict]:
        """Export all bindings as serializable dicts."""
        return [b.to_dict() for b in self.bindings]
    
    # =========================================================================
    # RUNTIME PROCESSING
    # =========================================================================
    
    def process_outputs(self):
        """
        Evaluate every binding against the live brain state.
        Called once per simulation tick, after propagation.
        """
        if not self.enabled or not self.bindings:
            return

        brain_window = getattr(self.logic, 'brain_window', None)
        brain_widget = getattr(brain_window, 'brain_widget', None) if brain_window else None
        if brain_widget is None:
            return

        activations = {}
        for binding in self.bindings:
            if binding.neuron_name in activations:
                continue
            val = self._get_neuron_activation(brain_widget, binding.neuron_name)
            if val is not None:
                activations[binding.neuron_name] = val

        self._evaluate(activations)

    def _get_neuron_activation(self, brain_widget, neuron_name: str) -> Optional[float]:
        """Current activation of a neuron, or None if it has no value.

        brain_widget.state is the project's single activation store. (A former
        first branch read brain_widget.neuron_activations, an attribute that
        does not exist on BrainWidget, and a former third branch read a
        'state' key that get_neurogenesis_config() never provides.)
        """
        state = getattr(brain_widget, 'state', None)
        if not state:
            return None
        val = state.get(neuron_name)
        if val is None:
            return None
        if isinstance(val, bool):
            return 100.0 if val else 0.0
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def _fire_binding(self, binding: NeuronOutputBinding, activation: float, current_time: float):
        """Fire a binding's output hook."""
        binding.last_fire_time = current_time

        # A reflex with a probability below 1.0 only happens some of the time.
        # The cooldown is still consumed on a failed roll, so "a chance of
        # inking when startled" does not become "keep rolling every tick until
        # it inks", which is the same as always inking, just later.
        if binding.probability < 1.0 and random.random() > binding.probability:
            if getattr(self.logic, 'debug_mode', False):
                self._log(f"declined: {binding.neuron_name} → {binding.output_hook} "
                          f"(p={binding.probability:.2f})")
            return
        
        # Update statistics
        self.total_fires += 1
        self.fires_by_hook[binding.output_hook] = self.fires_by_hook.get(binding.output_hook, 0) + 1
        
        # Trigger the hook
        if hasattr(self.logic, 'plugin_manager'):
            self.logic.plugin_manager.trigger_hook(
                binding.output_hook,
                neuron_name=binding.neuron_name,
                activation=activation,
                threshold=binding.threshold,
                squid=self.logic.squid,
                tamagotchi_logic=self.logic,
                **binding.hook_params
            )
        
        # Debug output
        if hasattr(self.logic, 'debug_mode') and self.logic.debug_mode:
            self._log(f"FIRED: {binding.neuron_name} → {binding.output_hook} ({activation:.0f})")
    
    # =========================================================================
    # DEFAULT HOOK HANDLERS
    # =========================================================================
    
    def _handle_flee(self, neuron_name, activation, squid, **kwargs):
        """Panic response: flee state + double speed + evasive heading."""
        if not squid:
            return
        squid.is_fleeing = True
        squid.current_speed = squid.base_speed * 2
        squid.status = "fleeing"
        if hasattr(squid, 'set_neural_drive'):
            squid.set_neural_drive('flee', duration=4.0, priority=squid.DRIVE_URGE)
        # MentalStateManager exposes set_state(name, bool); activate_state()
        # never existed and raised AttributeError here on every firing.
        msm = getattr(squid, 'mental_state_manager', None)
        if msm:
            msm.set_state('startled', True)

    def _handle_seek_food(self, neuron_name, activation, squid, tamagotchi_logic=None, **kwargs):
        """Drive the squid toward visible food for a few seconds."""
        if not squid:
            return
        visible_food = squid.get_visible_food() if hasattr(squid, 'get_visible_food') else []
        if not visible_food:
            return
        closest = min(visible_food, key=lambda f: squid.distance_to(f[0], f[1]))
        squid.pursuing_food = True
        squid.target_food = closest
        squid.status = "seeking food"
        if hasattr(squid, 'set_neural_drive'):
            squid.set_neural_drive('seek_food', duration=4.0,
                                   target=(closest[0], closest[1]),
                                   priority=squid.DRIVE_URGE)

    def _handle_seek_plant(self, neuron_name, activation, squid, tamagotchi_logic=None, **kwargs):
        """Drive the squid toward the nearest plant decoration."""
        if not squid or not tamagotchi_logic:
            return

        nearest_plant, min_dist = None, float('inf')
        for item in tamagotchi_logic.user_interface.scene.items():
            if getattr(item, 'category', None) != 'plant':
                continue
            c = item.sceneBoundingRect().center()
            d = ((c.x() - squid.squid_x) ** 2 + (c.y() - squid.squid_y) ** 2) ** 0.5
            if d < min_dist:
                min_dist, nearest_plant = d, item

        if nearest_plant is None:
            return
        squid.status = "seeking_plant"
        if hasattr(squid, 'set_neural_drive'):
            squid.set_neural_drive('seek_plant', duration=5.0, target=nearest_plant,
                                   priority=squid.DRIVE_URGE)
        else:
            squid.move_toward_position(nearest_plant.sceneBoundingRect().center())

    def _handle_ink_cloud(self, neuron_name, activation, squid, tamagotchi_logic=None, **kwargs):
        """Release a real ink cloud into the scene."""
        logic = tamagotchi_logic or self.logic
        # squid.release_ink() does not exist anywhere in the project; the real
        # actuator is TamagotchiLogic.create_ink_cloud(), used by startle_awake.
        if logic and hasattr(logic, 'create_ink_cloud'):
            logic.create_ink_cloud()
            if squid:
                squid.status = "inking"

    def _handle_change_color(self, neuron_name, activation, squid, **kwargs):
        """Tint the squid, using explicit r/g/b params when the binding has them."""
        if not squid or not hasattr(squid, 'apply_tint'):
            return
        from PyQt5.QtGui import QColor
        import random as _random
        try:
            r, g, b = int(kwargs.get('red', -1)), int(kwargs.get('green', -1)), int(kwargs.get('blue', -1))
            if r >= 0 and g >= 0 and b >= 0:
                squid.apply_tint(QColor(r, g, b))
                return
        except (ValueError, TypeError):
            pass
        squid.apply_tint(QColor(*_random.choice([
            (255, 100, 100), (100, 255, 100), (100, 100, 255),
            (255, 255, 100), (255, 100, 255), (100, 255, 255)])))

    def _handle_startle(self, neuron_name, activation, squid, **kwargs):
        if not squid:
            return
        squid.status = "startled"
        msm = getattr(squid, 'mental_state_manager', None)
        if msm:
            msm.set_state('startled', True)

    def _handle_calm(self, neuron_name, activation, squid, **kwargs):
        if not squid:
            return
        squid.anxiety = max(0, squid.anxiety - 10)
        squid.is_fleeing = False
        squid.current_speed = squid.base_speed
        if hasattr(squid, 'clear_neural_drive'):
            squid.clear_neural_drive()
        msm = getattr(squid, 'mental_state_manager', None)
        if msm:
            msm.set_state('startled', False)

    def _handle_sleep(self, neuron_name, activation, squid, **kwargs):
        """Go to sleep the way the rest of the game does.

        Setting the two attributes by hand skipped everything else
        go_to_sleep() does - the sink animation, the anxiety relief, the
        on_sleep hook, the short-term memory clear - so a squid put to sleep
        by its own brain went to sleep differently from one put to sleep by
        anything else.
        """
        if not squid or getattr(squid, 'is_sleeping', False):
            return
        if hasattr(squid, 'go_to_sleep'):
            squid.go_to_sleep()
        else:
            squid.is_sleeping = True
            squid.status = "sleeping"

    def _handle_wake(self, neuron_name, activation, squid, **kwargs):
        if squid and getattr(squid, 'is_sleeping', False):
            squid.is_sleeping = False
            squid.status = "roaming"

    def _handle_boost_happiness(self, neuron_name, activation, squid, **kwargs):
        if squid:
            squid.happiness = min(100, squid.happiness + (activation / 100.0) * 5)

    def _handle_boost_curiosity(self, neuron_name, activation, squid, **kwargs):
        if squid:
            squid.curiosity = min(100, squid.curiosity + (activation / 100.0) * 5)

    def _handle_reduce_anxiety(self, neuron_name, activation, squid, **kwargs):
        """Stronger firing means MORE relief.

        The old formula was ((100 - activation) / 100) * 5, so a neuron firing
        at full strength reduced anxiety by exactly zero - the inverse of the
        hook's own description, and the opposite of its two sibling handlers.
        """
        if squid:
            squid.anxiety = max(0, squid.anxiety - (activation / 100.0) * 5)

    def _handle_wander(self, neuron_name, activation, squid, **kwargs):
        """Explore. squid.wander() does not exist; move_randomly() does."""
        if not squid:
            return
        squid.status = "roaming"
        if hasattr(squid, 'set_neural_drive'):
            squid.set_neural_drive('wander', duration=3.0, priority=squid.DRIVE_URGE)
        elif hasattr(squid, 'move_randomly'):
            squid.move_randomly()

    def _handle_approach_rock(self, neuron_name, activation, squid, tamagotchi_logic=None, **kwargs):
        """Swim at an object. Sometimes another squid had a claim to it.

        One action, two situations. When the object the squid is going for is
        nearer another squid than to itself, taking it is a contest, and the
        tank changes in a way both squid can perceive. The squid did not
        decide to contest anything and has no capability for it: it decided to
        go and get that object, and the situation supplied the rest.
        """
        if not squid or not tamagotchi_logic:
            return
        rocks = self._nearby_rocks(squid, tamagotchi_logic, 300)
        if not rocks:
            return

        contested, rival = self._contested_item(squid, tamagotchi_logic, rocks)
        target = contested if contested is not None else min(
            rocks, key=lambda r: self._dist_to_squid(r, squid))

        # Reported distinctly so the causal ledger has two actions to tell
        # apart. Whether the squid's network CAN tell them apart is the open
        # question; naming them is what lets the capability monitor ask it.
        squid.status = "contesting" if contested is not None else "approaching_rock"
        squid.current_rock_target = target
        if hasattr(squid, 'set_neural_drive'):
            squid.set_neural_drive('approach_rock', duration=6.0, target=target,
                                   priority=squid.DRIVE_URGE)

        if contested is None:
            return
        taken = False
        if (self._dist_to_squid(contested, squid) <= 120
                and not getattr(squid, 'carrying_rock', False)
                and hasattr(squid, 'pick_up_rock')):
            taken = bool(squid.pick_up_rock(contested))
        view = getattr(tamagotchi_logic, 'conspecific_view', None)
        if view is not None and hasattr(view, 'note_contest'):
            view.note_contest(rival, contested, taken=taken, squid=squid)

    def _handle_throw_rock(self, neuron_name, activation, squid, **kwargs):
        if squid and getattr(squid, 'carrying_rock', False):
            import random as _random
            squid.throw_rock(_random.choice(['left', 'right']))

    def _handle_pick_up_rock(self, neuron_name, activation, squid, tamagotchi_logic=None, **kwargs):
        if not squid or getattr(squid, 'carrying_rock', False):
            return
        logic = tamagotchi_logic or self.logic
        if not logic:
            return
        # Measured from the squid's CENTRE. The old code passed squid_x/squid_y
        # (the top-left corner) with a 50px radius against decoration centres,
        # which for a ~120px-wide squid was effectively unreachable.
        rocks = self._nearby_rocks(squid, logic, 120)
        if rocks:
            nearest = min(rocks, key=lambda r: self._dist_to_squid(r, squid))
            squid.pick_up_rock(nearest)

    def _handle_eat(self, neuron_name, activation, squid, tamagotchi_logic=None, **kwargs):
        """Actually consume nearby food.

        This used to set squid.is_eating = True, which is an OUTPUT flag of the
        real eating routine, not an input to it: no food was consumed and
        hunger never moved.
        """
        logic = tamagotchi_logic or self.logic
        if not squid or not logic:
            return
        food_items = list(getattr(logic, 'food_items', []) or [])
        if not food_items:
            return
        cx = squid.squid_x + squid.squid_width / 2.0
        cy = squid.squid_y + squid.squid_height / 2.0

        def _d(item):
            c = item.sceneBoundingRect().center()
            return ((c.x() - cx) ** 2 + (c.y() - cy) ** 2) ** 0.5

        nearest = min(food_items, key=_d)
        if _d(nearest) <= 120 and hasattr(squid, 'eat'):
            squid.eat(nearest)
        elif hasattr(squid, 'set_neural_drive'):
            c = nearest.sceneBoundingRect().center()
            squid.pursuing_food = True
            squid.set_neural_drive('seek_food', duration=4.0, target=(c.x(), c.y()),
                                   priority=squid.DRIVE_URGE)

    @staticmethod
    def _contested_item(squid, logic, candidates):
        """The nearest of `candidates` that is closer to another squid than to us.

        This is what makes an approach a CONTEST, and note where the fact
        lives: in the tank, not in the squid. A squid does not need a
        dedicated contest capability any more than it needs a dedicated
        capability for picking up a rock that happens to be blue. It swims at
        an object; whether another squid had a claim to that object is a
        property of the situation it swam into.

        Whether the squid can tell the two situations apart - whether anything
        in its brain fires differently for a contested rock than a free one -
        is exactly the question the capability monitor exists to ask, and it
        can only ask it if both are reachable by the same action.
        """
        view = getattr(logic, 'conspecific_view', None)
        rival = view.nearest() if view is not None else None
        if rival is None or not candidates:
            return None, None
        rx, ry = rival.x, rival.y
        contested = []
        for item in candidates:
            centre = item.sceneBoundingRect().center()
            to_rival = ((centre.x() - rx) ** 2 + (centre.y() - ry) ** 2) ** 0.5
            to_self = NeuronOutputMonitor._dist_to_squid(item, squid)
            if to_rival < to_self:
                contested.append((to_self, item))
        if not contested:
            return None, rival
        return min(contested, key=lambda pair: pair[0])[1], rival

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def _dist_to_squid(item, squid) -> float:
        c = item.sceneBoundingRect().center()
        cx = squid.squid_x + squid.squid_width / 2.0
        cy = squid.squid_y + squid.squid_height / 2.0
        return ((c.x() - cx) ** 2 + (c.y() - cy) ** 2) ** 0.5

    @staticmethod
    def _nearby_rocks(squid, logic, radius):
        if not hasattr(logic, 'get_nearby_decorations'):
            return []
        cx = squid.squid_x + squid.squid_width / 2.0
        cy = squid.squid_y + squid.squid_height / 2.0
        decorations = logic.get_nearby_decorations(cx, cy, radius)
        return [d for d in decorations if getattr(d, 'category', None) == 'rock']

def hook_has_handler(hook_name: str, plugin_manager=None) -> bool:
    """True if firing this hook would actually reach a handler.

    Hooks flagged requires_plugin have no built-in handler, so they are only
    live when a plugin has subscribed.
    """
    info = STANDARD_OUTPUT_HOOKS.get(hook_name, {})
    if not info.get('requires_plugin'):
        return True

    if plugin_manager is None:
        plugin_manager = _find_plugin_manager()
    if plugin_manager is None:
        return False
    return bool(getattr(plugin_manager, 'hooks', {}).get(hook_name))


def _find_plugin_manager():
    """Best-effort lookup of the live PluginManager singleton."""
    try:
        from .plugin_manager import PluginManager
    except ImportError:
        try:
            from plugin_manager import PluginManager  # standalone designer
        except ImportError:
            return None
    pm = PluginManager._instance
    return pm if pm is not None and getattr(pm, '_initialized', False) else None


def get_available_output_hooks(plugin_manager=None, include_unhandled: bool = False) -> Dict[str, dict]:
    """Output hooks the user may bind to.

    By default only hooks that can actually do something are returned.
    """
    return {
        name: info for name, info in STANDARD_OUTPUT_HOOKS.items()
        if include_unhandled or hook_has_handler(name, plugin_manager)
    }


def get_output_hooks_by_category(plugin_manager=None,
                                 include_unhandled: bool = False) -> Dict[str, Dict[str, dict]]:
    by_category: Dict[str, Dict[str, dict]] = {}
    for hook_name, info in get_available_output_hooks(plugin_manager, include_unhandled).items():
        by_category.setdefault(info.get('category', 'other'), {})[hook_name] = info
    return by_category