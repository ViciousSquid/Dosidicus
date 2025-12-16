"""
Neuron Output Binding System

This module enables custom neurons in the brain designer to trigger game behaviors
when they fire. It creates a bidirectional system:

INPUT (Sensors):  Game Events → Hooks → Neuron Activation
OUTPUT (Actuators): Neuron Fires → Threshold Check → Hooks → Game Behavior
"""

import time
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
            hook_params=data.get('hook_params', {}),
        )
    
    def should_fire(self, current_activation: float, current_time: float) -> bool:
        """Check if this binding should fire given current activation."""
        if not self.enabled:
            return False
        
        # Check cooldown
        if current_time - self.last_fire_time < self.cooldown:
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
        
        return should_fire


# =============================================================================
# FLOATING LOG WINDOW
# =============================================================================

if HAS_QT:
    class NeuronLogWindow(QtWidgets.QWidget):
        """A floating console window for neuron output logs."""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Neuron Monitor")
            
            # Window Flags: Tool (small title bar), Stay on Top, Frameless (optional, keeping frame for moveability)
            self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
            self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
            
            self.resize(600, 200)
            
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
    
    # Custom/plugin hooks
    'neuron_output_custom': {
        'description': 'Custom behavior (plugin-defined)',
        'category': 'custom',
        'default_threshold': 50.0,
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
        """Register all standard output hooks and subscribe to available handlers."""
        if not hasattr(self.logic, 'plugin_manager'):
            self._log("⚠️ Cannot register handlers: plugin_manager not available")
            return
        
        pm = self.logic.plugin_manager
        
        # Whitelist this monitor as an enabled 'plugin'
        if hasattr(pm, 'enabled_plugins'):
            pm.enabled_plugins.add('neuronoutputmonitor')
            
        self._log(f"📡 Plugin manager found, registering {len(STANDARD_OUTPUT_HOOKS)} hooks...")
        
        # Register hooks
        for hook_name in STANDARD_OUTPUT_HOOKS.keys():
            pm.register_hook(hook_name)
            
        # Subscribe handlers
        import inspect
        subscribed_count = 0
        for method_name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if method_name.startswith('_handle_'):
                base_name = method_name[8:]  # Remove '_handle_' prefix
                hook_name = f"neuron_output_{base_name}"
                
                if hook_name in STANDARD_OUTPUT_HOOKS:
                    success = pm.subscribe_to_hook(hook_name, 'NeuronOutputMonitor', method)
                    if success:
                        subscribed_count += 1
        
        self._log(f"📊 Ready. Total subscriptions: {subscribed_count}")
        
        # Redundant safety pass
        for method_name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if method_name.startswith('_handle_'):
                base_name = method_name[8:]
                hook_name = f"neuron_output_{base_name}"
                if hook_name in STANDARD_OUTPUT_HOOKS:
                    pm.subscribe_to_hook(hook_name, 'NeuronOutputMonitor', method)
    
    # =========================================================================
    # BINDING MANAGEMENT
    # =========================================================================

    def monitor(self, neuron_activations: Dict[str, float], current_time: Optional[float] = None):
        """Main method called every frame with all current neuron activations."""
        if not self.enabled:
            return
            
        # Self-Healing Whitelist
        if hasattr(self.logic, 'plugin_manager'):
            pm = self.logic.plugin_manager
            if hasattr(pm, 'enabled_plugins') and 'neuronoutputmonitor' not in pm.enabled_plugins:
                pm.enabled_plugins.add('neuronoutputmonitor')
        
        current_time = current_time or time.time()
        
        for binding in self.bindings:
            activation = neuron_activations.get(binding.neuron_name, 0.0)
            
            # Check for firing BEFORE updating last_activation
            if binding.should_fire(activation, current_time):
                self._fire_binding(binding, activation, current_time)
            
            # Update last activation for edge detection
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
        """Load output bindings from brain configuration data."""
        self.clear_bindings()
        
        output_bindings = brain_data.get('output_bindings', [])
        for binding_data in output_bindings:
            try:
                binding = NeuronOutputBinding.from_dict(binding_data)
                self.add_binding(binding)
            except Exception as e:
                self._log(f"Error loading binding: {e}")
    
    def export_bindings(self) -> List[dict]:
        """Export all bindings as serializable dicts."""
        return [b.to_dict() for b in self.bindings]
    
    # =========================================================================
    # RUNTIME PROCESSING
    # =========================================================================
    
    def process_outputs(self):
        """
        Process all output bindings.
        Call this each simulation tick after the neural network has been updated.
        """
        if not self.enabled or not self.bindings:
            return
        
        if not hasattr(self.logic, 'brain_window') or not self.logic.brain_window:
            return
        
        brain_widget = self.logic.brain_window.brain_widget
        current_time = time.time()
        
        for binding in self.bindings:
            # Get current activation for this neuron
            activation = self._get_neuron_activation(brain_widget, binding.neuron_name)
            
            # If we can't find the activation, we can't trigger
            if activation is None:
                continue
            
            # Check if should fire
            if binding.should_fire(activation, current_time):
                self._fire_binding(binding, activation, current_time)
            
            # Update last activation for next check
            binding.last_activation = activation
    
    def _get_neuron_activation(self, brain_widget, neuron_name: str) -> Optional[float]:
        """
        Get the current activation value of a neuron.
        Checks multiple sources to ensure compatibility with different brain versions.
        """
        # 1. Check 'neuron_activations' (often used for sensor overrides/inputs)
        if hasattr(brain_widget, 'neuron_activations') and brain_widget.neuron_activations:
            val = brain_widget.neuron_activations.get(neuron_name)
            if val is not None:
                return float(val)

        # 2. Check 'state' (main storage for neuron values in Dosidicus/Custom brains)
        if hasattr(brain_widget, 'state') and brain_widget.state:
            val = brain_widget.state.get(neuron_name)
            if val is not None:
                return float(val)

        # 3. Fallback: check config state
        if hasattr(brain_widget, 'config'):
            try:
                state = brain_widget.config.get_neurogenesis_config().get('state', {})
                val = state.get(neuron_name)
                if val is not None:
                    return float(val)
            except:
                pass
        
        return None
    
    def _fire_binding(self, binding: NeuronOutputBinding, activation: float, current_time: float):
        """Fire a binding's output hook."""
        binding.last_fire_time = current_time
        
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
        if squid and not getattr(squid, 'is_fleeing', False):
            squid.is_fleeing = True
            squid.current_speed = squid.base_speed * 2
            if hasattr(squid, 'mental_state_manager'):
                squid.mental_state_manager.activate_state('fleeing')
    
    def _handle_seek_food(self, neuron_name, activation, squid, tamagotchi_logic, **kwargs):
        if squid and tamagotchi_logic:
            visible_food = squid.get_visible_food() if hasattr(squid, 'get_visible_food') else []
            if visible_food:
                squid.pursuing_food = True
                squid.target_food = visible_food[0]
    
    def _handle_seek_plant(self, neuron_name, activation, squid, tamagotchi_logic, **kwargs):
        if not squid or not tamagotchi_logic: return
        
        nearest_plant = None
        min_dist = float('inf')
        
        for item in tamagotchi_logic.user_interface.scene.items():
            if hasattr(item, 'category') and item.category == 'plant':
                plant_pos = item.sceneBoundingRect().center()
                dist = ((plant_pos.x() - squid.squid_x)**2 + (plant_pos.y() - squid.squid_y)**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    nearest_plant = item
        
        if nearest_plant:
            squid.status = "seeking_plant"
            target_pos = nearest_plant.sceneBoundingRect().center()
            squid.move_toward_position(target_pos)
    
    def _handle_ink_cloud(self, neuron_name, activation, squid, **kwargs):
        if squid and hasattr(squid, 'release_ink'):
            squid.release_ink()
        elif squid and hasattr(squid, 'mental_state_manager'):
            squid.mental_state_manager.activate_state('inking')

    def _handle_change_color(self, neuron_name, activation, squid, **kwargs):
        """
        Handle color change when neuron fires.
        Checks for specific 'red', 'green', 'blue' parameters in kwargs.
        """
        if squid and hasattr(squid, 'apply_tint'):
            from PyQt5.QtGui import QColor
            import random

            try:
                r = int(kwargs.get('red', -1))
                g = int(kwargs.get('green', -1))
                b = int(kwargs.get('blue', -1))
                
                if r >= 0 and g >= 0 and b >= 0:
                    color = QColor(r, g, b)
                    squid.apply_tint(color)
                    self._log(f"Tint: {r},{g},{b}")
                    return
            except (ValueError, TypeError):
                pass
            
            # Fallback only if params missing or invalid
            colors = [
                (255, 100, 100), (100, 255, 100), (100, 100, 255),
                (255, 255, 100), (255, 100, 255), (100, 255, 255)
            ]
            rgb = random.choice(colors)
            squid.apply_tint(QColor(*rgb))
            self._log(f"RandTint: {rgb}")
    
    def _handle_startle(self, neuron_name, activation, squid, **kwargs):
        if squid and hasattr(squid, 'mental_state_manager'):
            squid.mental_state_manager.activate_state('startled')
    
    def _handle_calm(self, neuron_name, activation, squid, **kwargs):
        if squid:
            squid.anxiety = max(0, squid.anxiety - 10)
            squid.is_fleeing = False
            if hasattr(squid, 'mental_state_manager'):
                squid.mental_state_manager.deactivate_state('startled')
                squid.mental_state_manager.deactivate_state('fleeing')
    
    def _handle_sleep(self, neuron_name, activation, squid, **kwargs):
        if squid and not getattr(squid, 'is_sleeping', False):
            squid.is_sleeping = True
            squid.status = "sleeping"
    
    def _handle_wake(self, neuron_name, activation, squid, **kwargs):
        if squid and getattr(squid, 'is_sleeping', False):
            squid.is_sleeping = False
            squid.status = "roaming"
    
    def _handle_boost_happiness(self, neuron_name, activation, squid, **kwargs):
        if squid:
            boost = (activation / 100.0) * 5
            squid.happiness = min(100, squid.happiness + boost)
    
    def _handle_reduce_anxiety(self, neuron_name, activation, squid, **kwargs):
        if squid:
            reduction = ((100 - activation) / 100.0) * 5
            squid.anxiety = max(0, squid.anxiety - reduction)
    
    def _handle_wander(self, neuron_name, activation, squid, **kwargs):
        if squid and hasattr(squid, 'wander'):
            squid.wander()
        elif squid:
            squid.status = "roaming"
    
    def _handle_approach_rock(self, neuron_name, activation, squid, tamagotchi_logic, **kwargs):
        if not squid or not tamagotchi_logic: return
        
        decorations = tamagotchi_logic.get_nearby_decorations(squid.squid_x, squid.squid_y, 300)
        rocks = [d for d in decorations if hasattr(d, 'category') and d.category == 'rock']
        
        if rocks:
            nearest = min(rocks, key=lambda r: 
                ((r.sceneBoundingRect().center().x() - squid.squid_x)**2 + 
                 (r.sceneBoundingRect().center().y() - squid.squid_y)**2))
            squid.status = "approaching_rock"
            squid.current_rock_target = nearest
    
    def _handle_throw_rock(self, neuron_name, activation, squid, **kwargs):
        if squid and getattr(squid, 'carrying_rock', False):
            import random
            direction = random.choice(['left', 'right'])
            squid.throw_rock(direction)
    
    def _handle_pick_up_rock(self, neuron_name, activation, squid, tamagotchi_logic, **kwargs):
        if not squid or getattr(squid, 'carrying_rock', False): return
        
        if tamagotchi_logic:
            decorations = tamagotchi_logic.get_nearby_decorations(squid.squid_x, squid.squid_y, 50)
            rocks = [d for d in decorations if hasattr(d, 'category') and d.category == 'rock']
            if rocks:
                squid.pick_up_rock(rocks[0])
    
    def _handle_eat(self, neuron_name, activation, squid, **kwargs):
        if squid and hasattr(squid, 'target_food') and squid.target_food:
            squid.is_eating = True
    
    def _handle_boost_curiosity(self, neuron_name, activation, squid, **kwargs):
        if squid:
            boost = (activation / 100.0) * 5
            squid.curiosity = min(100, squid.curiosity + boost)


def get_available_output_hooks() -> Dict[str, dict]:
    return dict(STANDARD_OUTPUT_HOOKS)


def get_output_hooks_by_category() -> Dict[str, Dict[str, dict]]:
    by_category = {}
    for hook_name, info in STANDARD_OUTPUT_HOOKS.items():
        cat = info.get('category', 'other')
        if cat not in by_category:
            by_category[cat] = {}
        by_category[cat][hook_name] = info
    return by_category