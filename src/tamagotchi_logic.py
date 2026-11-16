import logging

_LOG = logging.getLogger(__name__)

from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import time
import math
from .statistics_window import StatisticsWindow
from .save_manager import SaveManager
from .squid import Personality
from .ui import ResizablePixmapItem
from .learning import HebbianLearning
from .interactions import RockInteractionManager
from .poop_interactions import PoopInteractionManager
from .config_manager import ConfigManager
from .plugin_manager import PluginManager
from .brain_neuron_hooks import BrainNeuronHooks
from .brain_neuron_outputs import NeuronOutputMonitor
from .vision_worker import VisionWorker, create_squid_vision_state, extract_scene_objects
from .image_cache import ImageCache


# Performance tracking for Task Manager
try:
    from .task_manager import perf_tracker
    _PERF_TRACKING_AVAILABLE = True
except ImportError:
    _PERF_TRACKING_AVAILABLE = False

#: Health regained per tick of sleep by a squid that is fed and well, and the
#: hunger above which a sleeping squid is too hungry to mend.
HEAL_PER_TICK = 0.05
HEAL_BELOW_HUNGER = 70.0



def heal_in_sleep(squid, speed: float = 1.0) -> float:
    """Mend a sleeping squid a little, if it is fed and well. Returns how much.

    A parent, which no longer eats, does not mend: that is what it is to be
    one.
    """
    if not getattr(squid, 'is_sleeping', False) or getattr(squid, 'is_sick', False):
        return 0.0
    if not getattr(getattr(squid, 'lifecycle', None), 'can_eat', True):
        return 0.0
    health = float(getattr(squid, 'health', 100.0) or 0.0)
    if health >= 100.0 or float(getattr(squid, 'hunger', 0.0) or 0.0) >= HEAL_BELOW_HUNGER:
        return 0.0
    mended = min(100.0, health + HEAL_PER_TICK * float(speed)) - health
    squid.health = health + mended
    return mended


#: How much calmer a squid gets, each tick, while it is hiding in a plant.
PLANT_CALM_PER_TICK = 2.5
from .logic_statistics import StatisticsTrackingMixin
from .logic_decorations import DecorationLogicMixin
from .logic_startle import StartleAndInkMixin
from .logic_lifecycle import LifecycleLogicMixin
from .logic_persistence import SaveLoadMixin
from .logic_care import CareActionsMixin

class TamagotchiLogic(
        StatisticsTrackingMixin,
        DecorationLogicMixin,
        StartleAndInkMixin,
        LifecycleLogicMixin,
        SaveLoadMixin,
        CareActionsMixin,
):

    def __init__(self, user_interface, squid, brain_window):
        self.config_manager = ConfigManager()
        self._propagating_debug_mode = False
        self.user_interface = user_interface
        self.mental_states_enabled = True
        self.squid = squid
        self.brain_window = brain_window
        self.brain_hooks = BrainNeuronHooks(self)

        # Innate reflexes. Not a second learning rule - every change it makes
        # goes through the brain's one recorded write path (see learning.py).
        # It was previously never instantiated, so get_recent_learning() could
        # only ever report "No learning data available".
        self.hebbian_learning = HebbianLearning(squid, brain_window)
        if squid is not None:
            squid.hebbian_learning = self.hebbian_learning

        # Initialize Vision Worker
        self.vision_worker = VisionWorker()
        self.vision_worker.visibility_update.connect(self.handle_vision_update)
        self.vision_worker.start()
        self.latest_vision_result = None
        
        # Initialize rock interaction manager with config
        self.rock_interaction = RockInteractionManager(
            squid=self.squid,
            logic=self,
            scene=self.user_interface.scene,
            message_callback=self.show_message,
            config_manager=self.config_manager
        )

        self.last_save_hash = None
        self.save_count = 0

        # Reproduction, parental starvation and the egg. The state itself is
        # the squid's (squid.lifecycle); this is the tank's side of it.
        self.lifecycle_config = self.config_manager.get_lifecycle_config()
        self.egg_item = None
        
        self.window_resize_cooldown = 0
        self.window_resize_cooldown_max = 20  # 20 updates before another resize can startle
        self.has_been_resized = False
        self.was_big = False
        self.debug_mode = False
        self.last_window_size = (1280, 900)  # Default size

        # Age tracking
        self.squid_birth_time = time.time()
        self.age_update_timer = QtCore.QTimer()
        self.age_update_timer.timeout.connect(self.update_squid_age)
        self.age_update_timer.start(60000)  # 1 minute

        # Decorations message system
        self.decorations_message_count = 0
        self.decorations_message_max = 3
        self.last_decorations_message_time = 0
        self.decorations_message_cooldown = 120  # 2 minutes in seconds
        self.decorations_message_check_interval = 300  # 5 minutes in seconds
        self.next_decorations_message_check = time.time() + random.randint(120, 300)  # 2-5 minutes from now

        
        self.mental_states_enabled = True 
        self.curious_cooldown = 0
        self.curious_cooldown_max = 20
        self.curious_interaction_cooldown = 1
        self.curious_interaction_cooldown_max = 5
        self.startle_cooldown = 1000
        self.startle_cooldown_max = 20 
        self.plant_calming_effect_counter = 0
        self.sleep_frame = 0

        # Add action tracking - new in 2.4.5.0
        self.recent_actions = []

        # Initialize save manager FIRST (before plugins)
        self.save_manager = SaveManager()
        
        # Initialize plugin manager
        self.plugin_manager = PluginManager()
        self.plugin_manager.set_tamagotchi_logic(self)

        # Initialize Monitor so handlers can register
        self.neuron_output_monitor = NeuronOutputMonitor(self)

        # Register all built-in sensors with the plugin manager
        # This makes them discoverable via plugin_manager.get_all_neuron_handler_info()
        self.plugin_manager.register_all_sensors(self)

        # Store save data that will be loaded later (needed for achievements)
        self._pending_save_data = None
    
        # Load save data FIRST (but don't apply it yet)
        save_data = self.save_manager.load_game()
        if save_data:
            self._pending_save_data = save_data
            print("✓ Save data loaded and cached for plugin initialization")

        # --- BLACKLIST MULTIPLAYER PLUGIN FROM AUTO-LOADING ---
        blacklisted = {"multiplayer"}
        discovered = self.plugin_manager.discover_plugins()
        for name in list(discovered.keys()):
            if name.lower() in blacklisted:
                del discovered[name]
                print(f"[PluginManager] Blacklisted '{name}' from auto-loading.")

        # Manually populate plugins dict to skip blacklisted ones
        self.plugin_manager.plugins.clear()
        self.plugin_manager.enabled_plugins.clear()

        for name, data in discovered.items():
            success = self.plugin_manager.load_plugin(name)
            if success and name != "multiplayer":
                self.plugin_manager.enabled_plugins.add(name)

        # Setup each loaded plugin (multiplayer is not in self.plugin_manager.plugins)
        for plugin_name, plugin_data in self.plugin_manager.plugins.items():
            instance = plugin_data.get('instance')
            if instance and hasattr(instance, 'setup') and not plugin_data.get('is_setup', False):
                try:
                    instance.setup(self.plugin_manager, self)
                    plugin_data['is_setup'] = True
                    print(f"✓ Setup plugin: {plugin_name}")
                except Exception as e:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"Error setting up plugin {plugin_name}: {e}")

        # Update status bar with plugin information
        self.update_status_bar()
                    
        # Trigger startup hook
        self.plugin_manager.trigger_hook("on_startup",
                                        tamagotchi_logic=self,
                                        squid=self.squid,
                                        user_interface=self.user_interface)

        # Initialize core attributes first
        self.simulation_speed = 1  # Default to 1x speed
        self.base_interval = 1000  # 1000ms = 1 second base interval
        self.base_food_speed = 90  # pixels per update at 1x speed

        # Initialize game objects BEFORE load_game()
        self.food_items = []
        self.max_food = 3
        from .display_scaling import DisplayScaling
        self.food_width = DisplayScaling.points(64)
        self.food_height = DisplayScaling.points(64)
        self.poop_items = []
        self.max_poop = 3
        self.points = 0

        # Caches scene items to avoid iterating the entire scene every tick
        self._decoration_cache = []
        self._decoration_cache_time = 0
        self._decoration_cache_interval = 0.3  # Rebuild cache every 300ms max

        # Flag to indicate the first instance of the application start
        self.is_first_instance = True

        # Initialize a timer for the initial delay if it's the first instance
        if self.is_first_instance:
            self.initial_delay_timer = QtCore.QTimer()
            self.initial_delay_timer.setSingleShot(True)
            self.initial_delay_timer.timeout.connect(self.allow_initial_startle)
            self.initial_delay_timer.start(60000)  # 60000 ms = 1 minute
            self.initial_startle_allowed = False

        # Initialize neurogenesis triggers with all required keys
        self.neurogenesis_triggers = {
            'novel_objects': 0,
            'high_stress_cycles': 0,
            'positive_outcomes': 0
        }
        self.new_object_encountered = False
        self.recent_positive_outcome = False

        # Setup timers with required arguments
        self.setup_timers()

        # Initialize thought system
        if hasattr(self.brain_window, 'add_thought'):
            self.add_thought = self.brain_window.add_thought
        else:
            self.thought_log = []
            self.add_thought = self._log_thought

        # Connect menu actions
        self.user_interface.feed_action.triggered.connect(self.feed_squid)
        self.user_interface.clean_action.triggered.connect(self.clean_environment)
        self.user_interface.connect_view_cone_action(self.squid.toggle_view_cone)
        self.user_interface.medicine_action.triggered.connect(self.give_medicine)
        self.user_interface.debug_action.triggered.connect(self.toggle_debug_mode)

        # Window setup
        self.user_interface.window.resizeEvent = self.handle_window_resize

        # Initialize state tracking
        self.last_clean_time = 0
        self.clean_cooldown = 60
        self.cleanliness_threshold_time = 0
        self.hunger_threshold_time = 0
        self.needle_item = None
        self.lights_on = True

        # Initialize statistics window
        self.statistics_window = StatisticsWindow(squid)
        squid.statistics_window = self.statistics_window
        self.statistics_window.show()
        
        # NOW load the game after statistics_window exists AND plugins are initialized
        self.load_game()

        # Setup additional timers
        self.score_update_timer = QtCore.QTimer()
        self.score_update_timer.timeout.connect(self.update_score)
        self.score_update_timer.start(5000)

        self.brain_update_timer = QtCore.QTimer()
        self.brain_update_timer.timeout.connect(self.update_squid_brain)
        self.brain_update_timer.start(1000)

        self.autosave_timer = QtCore.QTimer()
        self.autosave_timer.timeout.connect(self.autosave)

        # Initialize goal neurons
        self.squid.satisfaction = 50
        self.squid.anxiety = 10
        self.squid.curiosity = 55

        # Connect neurogenesis signal to show icon and store long-term memory
        if hasattr(self.brain_window, 'brain_widget'):
            self.brain_window.brain_widget.neuronCreated.connect(self._on_neurogenesis_icon_and_memory)
            self.refresh_neuron_count()

    def handle_vision_update(self, result):
        """Cache the latest vision result and push to brain immediately."""
        self.latest_vision_result = result
        # [FIX] Push to brain now. Waiting for the 1-second timer causes lag/flicker.
        self.apply_input_neurons_to_brain()

    def _on_neurogenesis_icon_and_memory(self, neuron_name: str):
        """Called when a new neuron is created via neurogenesis.
        Shows images/ng.png above the squid's head for 4 seconds
        and records a long-term memory of the event.
        """
        brain_widget = getattr(self.brain_window, 'brain_widget', None)
        neuron_type = None
        current_count = None

        if brain_widget:
            current_count = self._live_neuron_count()
            neurogenesis = getattr(brain_widget, 'enhanced_neurogenesis', None)
            functional_neurons = getattr(neurogenesis, 'functional_neurons', {})
            functional_neuron = functional_neurons.get(neuron_name)
            neuron_type = getattr(functional_neuron, 'neuron_type', None)

            if neuron_type is None:
                details = getattr(brain_widget, 'neurogenesis_data', {}).get(
                    'new_neurons_details', {}
                ).get(neuron_name, {})
                neuron_type = details.get('trigger_type')

        self.track_neuron_creation(neuron_type, current_count)

        # The creation signal is emitted before optional pruning. Re-observe
        # the settled live count on the next event-loop turn without reducing
        # the lifetime maximum recorded at birth.
        QtCore.QTimer.singleShot(0, self.refresh_neuron_count)

        # Show the ng icon above the squid's head for 4 seconds
        if hasattr(self.squid, 'show_neurogenesis_icon'):
            self.squid.show_neurogenesis_icon()
            QtCore.QTimer.singleShot(4000, self.squid.hide_neurogenesis_icon)

        # Store a long-term memory
        if hasattr(self.squid, 'memory_manager'):
            self.squid.memory_manager.add_long_term_memory(
                'neurogenesis',
                f'neurogenesis_{time.time():.0f}',
                {
                    'description': 'GREW A NEW NEURON VIA NEUROGENESIS!',
                    'neuron_name': neuron_name,
                    'timestamp': time.time(),
                    'icon': 'images/ng.png'
                }
            )

    def _initialize_plugins(self):
        """Initialize all plugins before loading game data"""
        # --- BLACKLIST MULTIPLAYER PLUGIN FROM AUTO-LOADING ---
        blacklisted = {"multiplayer"}  # lowercase plugin key
        discovered = self.plugin_manager.discover_plugins()
        
        for name in list(discovered.keys()):
            if name.lower() in blacklisted:
                del discovered[name]
                print(f"[PluginManager] Blacklisted '{name}' from auto-loading.")

        # Clear existing plugins
        self.plugin_manager.plugins.clear()
        self.plugin_manager.enabled_plugins.clear()

        # Load all discovered plugins (except multiplayer)
        for name, data in discovered.items():
            success = self.plugin_manager.load_plugin(name)
            if success and name != "multiplayer":
                self.plugin_manager.enabled_plugins.add(name)

        # Setup each loaded plugin
        for plugin_name, plugin_data in self.plugin_manager.plugins.items():
            instance = plugin_data.get('instance')
            if instance and hasattr(instance, 'setup') and not plugin_data.get('is_setup', False):
                try:
                    instance.setup(self.plugin_manager, self)
                    plugin_data['is_setup'] = True
                    print(f"✓ Setup plugin: {plugin_name}")
                except Exception as e:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"Error setting up plugin {plugin_name}: {e}")

        # Update status bar with plugin information
        self.update_status_bar()
                    
        # Trigger startup hook
        self.plugin_manager.trigger_hook("on_startup", 
                                        tamagotchi_logic=self,
                                        squid=self.squid,
                                        user_interface=self.user_interface)
        

    def update_squid_age(self):
        """Refresh the age projection from the persistent model clock."""
        self._refresh_statistics_tab()

    def set_squid(self, squid):
        self.squid = squid
        # The brain is built before the squid exists, so this is the first
        # moment its personality is known - and personality is innate, so it
        # belongs in the newborn's synapses rather than in a rule applied to
        # its decisions later. See BrainWidget.apply_personality_bias.
        bw = getattr(getattr(self, 'brain_window', None), 'brain_widget', None)
        personality = getattr(squid, 'personality', None)
        if bw is not None and personality is not None:
            try:
                bw.apply_personality_bias(personality)
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Personality] could not tilt innate reflexes: {e}")

    def set_brain_window(self, brain_window):
        self.brain_window = brain_window

    def set_mental_states_enabled(self, enabled):
        self.mental_states_enabled = enabled
        self.squid.mental_state_manager.set_mental_states_enabled(enabled)

    def get_health_history(self, limit=100):
        """
        Returns historical health data for the squid.
        
        Args:
            limit (int): Maximum number of data points to return (default: 100)
            
        Returns:
            list: A list of (timestamp, health_value) tuples, newest first
        """
        # Initialize health history if it doesn't exist
        if not hasattr(self, '_health_history'):
            self._health_history = []
        
        # Return a copy of the history, limited to the requested number of points
        return self._health_history[-limit:]

    

    def reset_squid_status(self):
        """Reset squid status to default state after temporary actions"""
        if self.squid and "eating" in self.squid.status.lower():
            # Choose default status based on personality
            if self.squid.personality == Personality.TIMID:
                self.squid.status = "cautiously exploring"
            elif self.squid.personality == Personality.ADVENTUROUS:
                self.squid.status = "boldly exploring"
            else:
                self.squid.status = "roaming"
            
            # Ensure is_eating flag is also cleared
            self.squid.is_eating = False



    def get_decision_data(self):
        """Package decision-making information for visualization based on DecisionEngine"""
        # Default empty data structure
        decision_data = {
            'timestamp': time.strftime("%H:%M:%S"),
            'inputs': {},
            'active_memories': [],
            'possible_actions': [],
            'final_decision': "unknown",
            'confidence': 0.0,
            'processing_time': 0,
            'personality_influence': getattr(self.squid, 'personality', 'unknown'),
            'weights': {},
            'adjusted_weights': {},
            'randomness': {}
        }
        
        if not hasattr(self, 'squid') or not self.squid:
            return decision_data
            
        try:
            # Get current state for inputs
            decision_data['inputs'] = {
                "hunger": self.squid.hunger,
                "happiness": self.squid.happiness,
                "cleanliness": self.squid.cleanliness,
                "sleepiness": self.squid.sleepiness,
                "satisfaction": self.squid.satisfaction,
                "anxiety": self.squid.anxiety,
                "curiosity": self.squid.curiosity,
                "is_sick": self.squid.is_sick,
                "is_sleeping": self.squid.is_sleeping,
                "has_food_visible": bool(self.squid.get_visible_food()),
                "carrying_rock": getattr(self.squid, 'carrying_rock', False),
            }
            
            # Capture decision engine logic before making the decision
            decision_data['final_decision'] = self.squid.status
            
            # Get active memories
            if hasattr(self.squid, 'memory_manager'):
                active_memories = self.squid.memory_manager.get_active_memories_data(3)
                decision_data['active_memories'] = [
                    f"{mem.get('category', 'memory')}: {str(mem.get('formatted_value', ''))[:50]}"
                    for mem in active_memories
                ]
            
            # Simulate processing time (would be cool to measure actual time)
            decision_data['processing_time'] = random.randint(20, 100)
            
            # Confidence of the decision (higher for more extreme weight differences)
            # Here we're estimating based on the squid's state and randomizing a bit
            base_confidence = 0.5
            # Adjust confidence based on state extremes
            for key, value in decision_data['inputs'].items():
                if isinstance(value, (int, float)) and value > 80:
                    base_confidence += 0.1  # More confident with extreme values
                elif isinstance(value, (int, float)) and value < 20:
                    base_confidence += 0.1
            # Cap and add randomness
            base_confidence = min(0.9, base_confidence)
            decision_data['confidence'] = base_confidence + random.uniform(-0.1, 0.1)
            
            # Get brain network state. This used to read self.squid_brain_window,
            # an attribute that lives on Ui and never on TamagotchiLogic, so the
            # dict was always empty and every weight below fell through to its
            # hard-coded default of 50.
            brain_state = {}
            if getattr(self, 'brain_window', None) is not None:
                brain_state = getattr(self.brain_window, 'brain_widget', None)
                brain_state = dict(brain_state.state) if brain_state is not None else {}
            
            # Calculate decision weights (replicating the logic from DecisionEngine)
            weights = {
                "exploring": brain_state.get("curiosity", 50) * 0.8 * (1 - (brain_state.get("anxiety", 50) / 100)),
                "eating": brain_state.get("hunger", 50) * 1.2 if self.squid.get_visible_food() else 0,
                "approaching_rock": brain_state.get("curiosity", 50) * 0.7 if not getattr(self.squid, 'carrying_rock', False) else 0,
                "throwing_rock": brain_state.get("satisfaction", 50) * 0.7 if getattr(self.squid, 'carrying_rock', False) else 0,
                "avoiding_threat": brain_state.get("anxiety", 50) * 0.9,
                "organizing": brain_state.get("satisfaction", 50) * 0.5
            }
            
            decision_data['weights'] = weights
            
            # Apply personality modifiers (replicating logic from DecisionEngine)
            adjusted_weights = weights.copy()
            
            # Personality modifiers from the DecisionEngine
            if self.squid.personality.value == "timid":
                adjusted_weights["avoiding_threat"] *= 1.5
                adjusted_weights["approaching_rock"] *= 0.7
            elif self.squid.personality.value == "adventurous":
                adjusted_weights["exploring"] *= 1.3
                adjusted_weights["approaching_rock"] *= 1.2
            elif self.squid.personality.value == "greedy":
                adjusted_weights["eating"] *= 1.5
                
            decision_data['adjusted_weights'] = adjusted_weights
            
            # Generate random factors for each action
            randomness = {}
            for action in weights.keys():
                randomness[action] = random.uniform(0.85, 1.15)
            
            decision_data['randomness'] = randomness
            
            # Possible actions
            decision_data['possible_actions'] = [
                action for action, weight in adjusted_weights.items()
                if weight > 0
            ]
        except Exception as e:
            print(f"Error generating decision data: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return decision_data
    
    def give_rl_reward(self, reward):
        """
        Feed a scalar reward into the DecisionEngine's Q-learning update.
        Call this immediately after the action finishes.
        """
        de = getattr(self.squid, '_decision_engine', None) if hasattr(self, 'squid') else None
        # DecisionEngine v4 carries no Q-table; this only runs if a future
        # engine provides one. It used to read `decision_engine` (no underscore),
        # an attribute that never exists, so it was unreachable either way.
        if de is not None and hasattr(de, 'ql') and hasattr(de, 'get_state_index'):
            if getattr(de, 'last_state', None) is not None and getattr(de, 'last_action', None) is not None:
                # Build next state from current squid state
                next_state = de.get_state_index({
                    "hunger": self.squid.hunger,
                    "happiness": self.squid.happiness,
                    "anxiety": self.squid.anxiety,
                    "curiosity": self.squid.curiosity
                })
                # Update Q-table
                de.ql.update(de.last_state, de.last_action, reward, next_state)

    def get_recent_learning(self):
        """Get last 3 significant weight changes"""
        if hasattr(self.squid, 'hebbian_learning') and self.squid.hebbian_learning:
            try:
                learning_data = self.squid.hebbian_learning.get_learning_data()
                return [f"{n1}-{n2}: {delta:.2f}" for _,n1,n2,delta in learning_data[-3:]]
            except AttributeError:
                return ["Learning system initializing"]
        return ["No learning data available"]
    

    def get_current_state(self):
        """Get current sensory inputs and status"""
        return {
            'hunger': self.squid.hunger,
            'happiness': self.squid.happiness,
            'cleanliness': self.squid.cleanliness,
            'sleepiness': self.squid.sleepiness,
            'satisfaction': self.squid.satisfaction,
            'anxiety': self.squid.anxiety,
            'curiosity': self.squid.curiosity,
            'is_sick': self.squid.is_sick,
            'near_food': len(self.squid.get_visible_food()) > 0,
            'near_poop': len(self.poop_items) > 0
        }

    def get_active_memories(self):
        memories = self.squid.memory_manager.get_active_memories_data(3)
        return [f"{m['category']}: {m['formatted_value']}" for m in memories]

    def get_available_actions(self):
        """List of currently available actions"""
        actions = ["explore", "sleep", "move_randomly"]
        if self.squid.hunger > 50:
            actions.append("search_for_food")
        if self.squid.curiosity > 60:
            actions.append("investigate_object")
        return actions

    def update_from_brain(self, brain_state):   # Communication between brain tool and Squid
        if self.squid is not None:
            for key, value in brain_state.items():
                if hasattr(self.squid, key):
                    setattr(self.squid, key, value)

            # Handle special cases
            if brain_state['sleepiness'] >= 100 and not self.squid.is_sleeping:
                self.squid.go_to_sleep()
            elif brain_state['sleepiness'] < 50 and self.squid.is_sleeping:
                self.squid.wake_up()

            if brain_state['direction'] != self.squid.squid_direction:
                self.squid.squid_direction = brain_state['direction']
                self.squid.move_squid()

        self.update_statistics()
        self.user_interface.scene.update()


    def _log_thought(self, thought):
        self.thought_log.append(thought)
        print(f"Squid thought: {thought}")

    def setup_speed_menu(self):
        speed_menu = self.user_interface.menu_bar.addMenu('Speed')

        speed_actions = {
            "Pause": 0,
            "1x": 1,
            "2x": 2,
            "4x": 4
        }

        for label, speed in speed_actions.items():
            action = QtWidgets.QAction(label, self.user_interface.window)
            action.triggered.connect(lambda checked, s=speed: self.set_simulation_speed(s))
            speed_menu.addAction(action)

    

    def set_simulation_speed(self, speed):
        """Set the simulation speed and notify plugins of the change"""
        # Store current speed before changing (default to 1 if not set)
        previous_speed = getattr(self, 'simulation_speed', 1)
        
        # Apply new speed
        self.simulation_speed = speed
        self.update_timers()
        
        # Clear any pause messages if unpausing
        if previous_speed == 0 and speed > 0:
            # Remove any existing message items
            if hasattr(self, 'user_interface') and hasattr(self.user_interface, 'scene'):
                for item in self.user_interface.scene.items():
                    if isinstance(item, QtWidgets.QGraphicsTextItem):
                        self.user_interface.scene.removeItem(item)
        
        # Update dependent systems
        if hasattr(self, 'squid'):
            self.squid.set_animation_speed(speed)
        
        if hasattr(self, 'brain_window'):
            self.brain_window.set_pause_state(speed == 0)

        # Safety check before plugin hook
        if not hasattr(self, 'plugin_manager'):
            self.plugin_manager = PluginManager()  # Ensure plugin manager exists
            
        # Call plugin hook with both speeds
        self.plugin_manager.trigger_hook(
            "on_speed_change",
            tamagotchi_logic=self,
            old_speed=previous_speed,  # Now properly defined
            new_speed=speed
        )
        
        print(f"\033[38;5;208;1m >> Simulation speed: {speed}x\033[0m")


    def setup_timers(self, scene=None, message_callback=None):
        """Setup all timers including rock interaction timers"""
        # Initialize core timers
        self.simulation_timer = QtCore.QTimer()
        self.simulation_timer.timeout.connect(self.update_simulation)
        
        # Set default simulation speed
        if not hasattr(self, 'simulation_speed'):
            self.simulation_speed = 1
        
        # Configure initial timer intervals
        self.update_timers()
        
        # Score update timer
        self.score_update_timer = QtCore.QTimer()
        self.score_update_timer.timeout.connect(self.update_score)
        self.score_update_timer.start(5000)  # 5 seconds
        
        # Brain update timer
        self.brain_update_timer = QtCore.QTimer()
        self.brain_update_timer.timeout.connect(self.update_squid_brain)
        self.brain_update_timer.start(1000)  # 1 second
        
        # Autosave timer
        self.autosave_timer = QtCore.QTimer()
        self.autosave_timer.timeout.connect(self.autosave)
        
        # Configure rock interaction timers
        # ===== PERFORMANCE FIX: Increased interval from 100ms to 200ms =====
        if hasattr(self, 'rock_interaction'):
            self.rock_interaction.setup_timers(interval=200)

        # Set up poop interaction
        # ===== PERFORMANCE FIX: Increased interval from 100ms to 200ms =====
        if hasattr(self, 'poop_interaction'):
            self.poop_interaction.setup_timers(interval=200)
        
        # Start the simulation timer
        self.simulation_timer.start()

    def update_timers(self):
        """Update timer intervals based on current simulation speed"""
        if not hasattr(self, 'base_interval'):
            self.base_interval = 1000  # Ensure base_interval exists
            
        if not hasattr(self, 'simulation_speed'):
            self.simulation_speed = 1
            
        if self.simulation_speed == 0:
            self.simulation_timer.stop()
            # Also stop brain-related timers when paused
            if hasattr(self, 'brain_window') and self.brain_window:
                if hasattr(self.brain_window, 'hebbian_timer'):
                    self.brain_window.hebbian_timer.stop()
                if hasattr(self.brain_window, 'countdown_timer'):
                    self.brain_window.countdown_timer.stop()
        else:
            interval = max(10, self.base_interval // self.simulation_speed)  # Ensure minimum interval
            self.simulation_timer.start(interval)
            
            # Update hebbian learning timer if it exists
            if hasattr(self, 'brain_window') and self.brain_window:
                if hasattr(self.brain_window, 'hebbian_timer'):
                    # Get the base learning interval from config
                    base_learning_interval = self.brain_window.config.hebbian.get('learning_interval', 30000)
                    # Scale the interval inversely with simulation speed
                    new_learning_interval = max(1000, int(base_learning_interval / self.simulation_speed))
                    self.brain_window.hebbian_timer.setInterval(new_learning_interval)
                    
                    # Update the countdown timer's initial value
                    if hasattr(self.brain_window, 'hebbian_countdown_seconds'):
                        self.brain_window.hebbian_countdown_seconds = int(new_learning_interval / 1000)
                    
                    # Restart countdown timer if it was stopped
                    if hasattr(self.brain_window, 'countdown_timer'):
                        if not self.brain_window.countdown_timer.isActive():
                            self.brain_window.countdown_timer.start(1000)
                
                # Update neurogenesis cooldown if the system exists
                if hasattr(self.brain_window, 'brain_widget') and hasattr(self.brain_window.brain_widget, 'enhanced_neurogenesis'):
                    # The neurogenesis system uses time-based cooldowns, so we need to adjust how time passes
                    # This is handled by the base cooldown time in the config
                    neuro_system = self.brain_window.brain_widget.enhanced_neurogenesis
                    if hasattr(neuro_system, 'config'):
                        # Store the base cooldown if not already stored
                        if not hasattr(neuro_system, 'base_cooldown'):
                            neuro_system.base_cooldown = neuro_system.config.neurogenesis.get('cooldown', 120)
                        # Scale cooldown inversely with simulation speed
                        neuro_system.config.neurogenesis['cooldown'] = max(10, int(neuro_system.base_cooldown / self.simulation_speed))


    def stop(self):
        """Stop all timers and clean up resources"""
        brain_widget = getattr(
            getattr(self, 'brain_window', None),
            'brain_widget',
            None,
        )
        neuron_created = getattr(brain_widget, 'neuronCreated', None)
        if neuron_created:
            try:
                neuron_created.disconnect(
                    self._on_neurogenesis_icon_and_memory
                )
            except (TypeError, RuntimeError):
                pass

        # Stop Vision Worker
        if hasattr(self, 'vision_worker') and self.vision_worker:
            self.vision_worker.stop()
            self.vision_worker.wait()

        # Stop main timers
        if hasattr(self, 'simulation_timer') and self.simulation_timer:
            self.simulation_timer.stop()
        
        if hasattr(self, 'score_update_timer') and self.score_update_timer:
            self.score_update_timer.stop()
        
        if hasattr(self, 'brain_update_timer') and self.brain_update_timer:
            self.brain_update_timer.stop()
        
        if hasattr(self, 'autosave_timer') and self.autosave_timer:
            self.autosave_timer.stop()
        
        if hasattr(self, 'age_update_timer') and self.age_update_timer:
            self.age_update_timer.stop()
        
        if hasattr(self, 'initial_delay_timer') and self.initial_delay_timer:
            self.initial_delay_timer.stop()
        
        # Stop rock interaction timers
        if hasattr(self, 'rock_interaction') and self.rock_interaction:
            if hasattr(self.rock_interaction, 'rock_test_timer') and self.rock_interaction.rock_test_timer:
                self.rock_interaction.rock_test_timer.stop()
            if hasattr(self.rock_interaction, 'throw_animation_timer') and self.rock_interaction.throw_animation_timer:
                self.rock_interaction.throw_animation_timer.stop()
            for flight in getattr(self.rock_interaction, '_visitor_flights', []):
                flight.throw_animation_timer.stop()
        
        # Stop poop interaction timers
        if hasattr(self, 'poop_interaction') and self.poop_interaction:
            if hasattr(self.poop_interaction, 'poop_timer') and self.poop_interaction.poop_timer:
                self.poop_interaction.poop_timer.stop()
        
        # Stop brain window timers
        if hasattr(self, 'brain_window') and self.brain_window:
            if hasattr(self.brain_window, 'hebbian_timer') and self.brain_window.hebbian_timer:
                self.brain_window.hebbian_timer.stop()
            if hasattr(self.brain_window, 'countdown_timer') and self.brain_window.countdown_timer:
                self.brain_window.countdown_timer.stop()

            ######################################### UPDATE_SIMULATION METHOD BELOW


    def update_simulation(self):
        """
        Main simulation update loop.
        """
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _sim_start = time.perf_counter()
            perf_tracker.increment("simulation_ticks")
        
        # 1. Pre-update hook
        self.plugin_manager.trigger_hook("pre_update", tamagotchi_logic=self, squid=self.squid)
        
        # 2. Paused?
        if self.simulation_speed == 0:
            return

        # Record continuous model statistics once per simulation callback.
        # Sleep duration is elapsed wall-clock time, matching the former
        # time.time()-based statistic. The timer already fires more often at
        # higher simulation speeds, so multiplying by simulation_speed would
        # overcount the time the squid was actually asleep.
        squid_statistics = getattr(self.squid, 'statistics', None)
        if squid_statistics:
            elapsed_seconds = self._statistics_elapsed_seconds()
            squid_statistics.update(elapsed_seconds=elapsed_seconds)
        
        # Check for decorations message
        self._check_decorations_message()
        
        # 3. World updates
        self.move_objects()
        self.animate_poops()
        self.update_statistics()
        self.check_poop_interaction()
        
        # Vision Worker
        if self.squid and hasattr(self, 'vision_worker') and self.vision_worker.isRunning():
            vision_state = create_squid_vision_state(self.squid)
            self.vision_worker.update_squid_state(vision_state)
            # _get_cached_decorations() returns (item, center_x, center_y)
            # tuples; extract_scene_objects() expects the graphics items
            # themselves. Unwrap them here – previously the tuples raised inside
            # extract_scene_objects and were silently swallowed, so decorations
            # (plants/rocks) never reached the vision worker.
            decorations = [entry[0] for entry in self._get_cached_decorations()]
            scene_objects = extract_scene_objects(self.user_interface.scene, self.food_items, decorations)
            self.vision_worker.update_scene_objects(scene_objects)
            # Other squid drawn in the tank, for how close one is (closeness is
            # felt whichever way the squid looks; seeing one is the cone's).
            self.squid_objects = [o for o in scene_objects if o.category == 'squid']

        if self.squid:
            # === FORCE SLEEP WHEN SLEEPINESS == 100 ===
            if self.squid.sleepiness >= 100.0:
                if not getattr(self.squid, 'is_sleeping', False):
                    self.squid.is_sleeping = True
                    self.squid.status = "sleeping"
                    if hasattr(self.squid, 'current_action'):
                        self.squid.current_action = "sleep"
                    self.user_interface.show_message("💤 The squid is completely exhausted and fell asleep!")
                    print("💤 FORCED SLEEP: sleepiness hit 100%")
                    self.sleep_frame = 0

            # === SLEEP ANIMATION (swaps between sleep1.png and sleep2.png) ===
            if getattr(self.squid, 'is_sleeping', False):
                self.sleep_frame = (self.sleep_frame + 1) % 2
                
                try:
                    # Reuse the shared image cache instead of decoding the PNG
                    # from disk on every tick while the squid sleeps.
                    if self.sleep_frame == 0:
                        pix = ImageCache.get_pixmap(os.path.join("images", "sleep1.png"))
                    else:
                        pix = ImageCache.get_pixmap(os.path.join("images", "sleep2.png"))

                    if not pix.isNull() and hasattr(self.squid, 'squid_item'):
                        self.squid.squid_item.setPixmap(pix)
                except Exception as e:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"Sleep animation error: {e}")

                # Sleep physiology is driven by elapsed simulation time.
                # update_simulation() normally runs once per second at 1x speed.
                elapsed_seconds = self.simulation_timer.interval() / 1000.0

                recovery_rate = 28.0 * elapsed_seconds
                self.squid.sleepiness = max(0.0, self.squid.sleepiness - recovery_rate)

                # Small restorative effects while sleeping.
                self.squid.happiness = min(
                    100.0,
                    self.squid.happiness + 0.45 * elapsed_seconds
                )
                self.squid.satisfaction = min(
                    100.0,
                    self.squid.satisfaction + 0.30 * elapsed_seconds
                )

                # Auto-wake when sufficiently rested (from original)
                if self.squid.sleepiness <= 25.0:
                    self.squid.is_sleeping = False
                    self.squid.status = "roaming"
                    self.user_interface.show_message("😴 The squid woke up feeling refreshed!")
                    self.sleep_frame = 0

            # A stubborn squid holding off sleep (personality.resists_sleep,
            # decided where sleep is - DecisionEngine) pays a little for it.
            elif getattr(self.squid, '_resisting_sleep', False):
                self.squid.happiness = max(15.0, self.squid.happiness - 1.8)

            # Normal behavior only when NOT sleeping
            if not getattr(self.squid, 'is_sleeping', False):
                self.run_decision_engine()
                self.squid.move_squid()
                self.check_for_decoration_attraction()

                if self.mental_states_enabled:
                    self.check_for_startle()
                    self.check_for_curiosity()

            # Rest of the original code (neurogenesis, brain state, etc.)
            self.track_neurogenesis_triggers()
            
            if self.squid.is_sleeping:
                self.squid.memory_manager.review_and_transfer_memories()
            else:
                self.squid.memory_manager.periodic_memory_management()
            
            # brain_state building
            is_startled_state = False
            if hasattr(self.squid, 'mental_state_manager') and self.squid.mental_state_manager:
                is_startled_state = self.squid.mental_state_manager.is_state_active('startled')
            elif hasattr(self.squid, 'status'):
                is_startled_state = "startled" in str(self.squid.status).lower()
            
            brain_state = {
                "hunger": self.squid.hunger,
                "happiness": self.squid.happiness,
                "cleanliness": self.squid.cleanliness,
                "sleepiness": self.squid.sleepiness,
                "satisfaction": self.squid.satisfaction,
                "anxiety": self.squid.anxiety,
                "curiosity": self.squid.curiosity,
                "is_sick": self.squid.is_sick,
                "is_sleeping": self.squid.is_sleeping,
                "is_eating": getattr(self.squid, 'is_eating', False) or (self.squid.status == "eating"),
                "pursuing_food": self.squid.pursuing_food,
                "is_fleeing": getattr(self.squid, 'is_fleeing', False),
                "is_startled": is_startled_state,
                "direction": self.squid.squid_direction,
                "position": (self.squid.squid_x, self.squid.squid_y),
                "personality": self.squid.personality.value if isinstance(self.squid.personality, Personality) else str(self.squid.personality),
                "status": self.squid.status,
                "novelty_exposure": self.neurogenesis_triggers['novel_objects'],
                "sustained_stress": self.neurogenesis_triggers['high_stress_cycles'] / 10.0,
                "recent_rewards": self.neurogenesis_triggers['positive_outcomes'],
                'recent_actions': self.recent_actions[-10:],
                'food_count': len(self.food_items),
                'poop_count': len(self.poop_items),
            }
            
            if hasattr(self, 'brain_hooks'):
                input_values = self.brain_hooks.get_input_neuron_values()
                brain_state.update(input_values)
            
            self.brain_window.update_brain(brain_state)
            
            if (hasattr(self.brain_window, 'brain_widget') and 
                hasattr(self.brain_window.brain_widget, 'enhanced_neurogenesis')):
                neuro = self.brain_window.brain_widget.enhanced_neurogenesis
                current_status = getattr(self.squid, 'status', 'roaming')
                action_to_track = self._normalize_action_name(current_status)
                neuro.track_action(action_to_track)
                neuro.track_state_change(brain_state)

                # Open a causal episode for what the squid has decided to do.
                # The consequence of the action is measured over the next few
                # seconds and compared against how the drives drift when it is
                # NOT doing that - which is what makes the conclusion causal
                # rather than merely correlational.
                causal = getattr(self.brain_window.brain_widget, 'causal_learning', None)
                if causal is not None:
                    try:
                        if not self._note_learned_action(self.brain_window.brain_widget):
                            causal.on_action(action_to_track,
                                             self.brain_window.brain_widget.state)
                    except Exception as e:
                        _LOG.warning('Handled exception', exc_info=True)
                        print(f"[CausalLearning] could not open episode: {e}")
                
                environment = {
                    'food_count': len(self.food_items),
                    'poop_count': len(self.poop_items),
                    'is_sick': self.squid.is_sick,
                    'is_eating': brain_state.get('is_eating', False),
                    'has_rock': len(getattr(self, 'rock_items', [])) > 0,
                    'new_object_encountered': self.new_object_encountered,
                    'recent_positive_outcome': self.recent_positive_outcome
                }
                neuro.check_and_capture_experience(brain_state, environment)
            
            # ============================================================
            # THE COGNITIVE LOOP, in order:
            #   1. sensors + squid stats were written into brain state above
            #   2. propagate activation along the synapses
            #   3. let neurogenesis apply its stress/anxiety feedback
            #   4. evaluate output bindings -> squid behaviour
            # ============================================================
            bw = getattr(self.brain_window, 'brain_widget', None)
            if bw is not None:
                if hasattr(bw, 'propagate_activations'):
                    bw.propagate_activations()
                # Settle what its earlier actions led to and, now and then,
                # let an unwired action neuron fire by itself. The spike is
                # in the network before the output bindings and the decision
                # engine read it, so whether the squid acts on it is decided
                # the way everything it does is decided.
                self._notice_journey()
                discovery = getattr(bw, 'action_discovery', None)
                if discovery is not None:
                    try:
                        discovery.tick(bw.state,
                                       asleep=getattr(self.squid, 'is_sleeping', False)
                                       or getattr(self.squid, 'is_transitioning', False))
                    except Exception as e:
                        _LOG.warning('Handled exception', exc_info=True)
                        print(f"[ActionDiscovery] tick failed: {type(e).__name__}: {e}")
                neuro = getattr(bw, 'enhanced_neurogenesis', None)
                if neuro is not None and hasattr(neuro, 'update_neuron_activations'):
                    neuro.update_neuron_activations(bw.state)

                # Learned associations modulate the squid's physiology. This
                # is what makes a synapse between two core stats mean
                # something, and it is the channel through which a squid's
                # history shows up in how it reacts.
                self.apply_neural_modulation(bw)

                # Sleep consolidation: samples while awake, replays and prunes
                # while asleep. Core, not a plugin.
                consolidation = getattr(bw, 'consolidation', None)
                if consolidation is not None:
                    consolidation.on_tick(
                        getattr(self.squid, 'is_sleeping', False), bw.state)

            if not getattr(self.squid, 'is_sleeping', False):
                if hasattr(self, 'neuron_output_monitor'):
                    self.neuron_output_monitor.process_outputs()
                # Drives set by movement outputs need their consumer ticked.
                self.update_rock_interaction()

            self.new_object_encountered = False
            self.recent_positive_outcome = False
            
            if self.squid.hunger <= 1 or self.squid.hunger >= 99:
                self.statistics_window.update_score()
        
        # 15. Decay environmental stimulus trackers
        if hasattr(self, 'brain_hooks'):
            self.brain_hooks.update_decay()
        
        # 16. Post-update hook
        self.plugin_manager.trigger_hook("post_update", tamagotchi_logic=self, squid=self.squid)
        
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _sim_elapsed = (time.perf_counter() - _sim_start) * 1000
            perf_tracker.record("simulation_tick", _sim_elapsed)

    def apply_neural_modulation(self, brain_widget=None):
        """Apply the brain's learned influence to the squid's statistics.

        Deliberately gentle: the natural drift of a core stat is around 0.3
        per tick, and a maximal synapse from a saturated source contributes
        0.15, so learning colours the squid's physiology over minutes without
        ever seizing control of it.
        """
        bw = brain_widget or getattr(self.brain_window, 'brain_widget', None)
        squid = getattr(self, 'squid', None)
        if bw is None or squid is None:
            return {}
        if not hasattr(bw, 'compute_neural_modulation'):
            return {}

        deltas = bw.compute_neural_modulation()
        applied = {}
        for stat, delta in deltas.items():
            if not hasattr(squid, stat) or abs(delta) < 1e-9:
                continue
            try:
                current = float(getattr(squid, stat))
            except (TypeError, ValueError):
                continue
            setattr(squid, stat, max(0.0, min(100.0, current + delta)))
            applied[stat] = delta
        self.last_neural_modulation = applied
        return applied

    def run_decision_engine(self):
        """Let the DecisionEngine choose the squid's next deliberate behaviour.

        Called once per tick, immediately before move_squid so the drive it
        installs is acted on in the same tick rather than being overwritten.

        It is skipped while any drive is still running, which does two things:
        an output binding's urge is genuinely irresistible (the engine cannot
        argue with it), and an ordinary decision gets to run to completion
        instead of the squid re-deciding every tick and dithering on the spot.
        """
        squid = getattr(self, 'squid', None)
        if squid is None or getattr(squid, 'is_sleeping', False):
            return None
        if not hasattr(squid, 'make_decision'):
            return None
        if squid.get_neural_drive() is not None:
            return None

        try:
            decision = squid.make_decision()
            # Surface the engine's choice on the model. make_decision returns a
            # descriptive string ("boldly exploring", "seeking comfort in
            # plant") but never assigned it, so the status bar, the memory log
            # and _normalize_action_name never saw what the squid decided.
            if decision and not getattr(squid, 'is_eating', False):
                squid.status = decision

            # Note what it chose, so the ledger can say how a learned synapse
            # actually showed up in behaviour rather than only asserting that
            # it must have.
            bw = getattr(self.brain_window, 'brain_widget', None)
            ledger = getattr(bw, 'ledger', None)
            if ledger is not None and decision:
                engine = getattr(squid, '_decision_engine', None)
                data = engine.get_decision_data() if engine is not None else {}
                ledger.record_decision(decision, (data or {}).get('adjusted_weights'))
            return decision
        except Exception as e:
            # Never let a decision failure stop the simulation, but never
            # swallow it either - a silent engine is how it stayed broken.
            print(f"[DecisionEngine] decision failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _squid_proximity(self) -> float:
        """How near the nearest other squid in the tank is, 0-100."""
        from .vision_cone import proximity
        others = getattr(self, 'squid_objects', None) or []
        if not others or self.squid is None:
            return 0.0
        cx = self.squid.squid_x + self.squid.squid_width / 2
        cy = self.squid.squid_y + self.squid.squid_height / 2
        return proximity(min(math.hypot(o.x + o.width / 2 - cx, o.y + o.height / 2 - cy)
                             for o in others))

    def apply_input_neurons_to_brain(self):
        """
        Apply real-time sensor values to the brain's input neurons.
        Without this, can_see_food, external_stimulus, etc. will NEVER update.
        """
        if not self.brain_window or not self.brain_window.brain_widget:
            return

        brain_widget = self.brain_window.brain_widget

        # Another squid in view, and how close one is, are percepts, not sense
        # organs: they reach the network only through the sensors neurogenesis
        # grows the first time they matter (brain_constants.SOCIAL_SENSORS).
        # While the squid is away visiting, the host's frame reports them
        # instead (plugins/multiplayer/visitor_mind.py).
        if hasattr(brain_widget, 'perceive') and \
                not getattr(self.squid, 'is_transitioning', False):
            seen = getattr(self.latest_vision_result, 'can_see_squid', False)
            brain_widget.perceive('squid_in_view', 100.0 if seen else 0.0)
            # A plant in the view cone, likewise: a percept that reaches the
            # network only through the can_see_plant sense the squid grows the
            # first time it sees one. Nothing reports a plant it is not
            # looking at.
            plant = getattr(self.latest_vision_result, 'can_see_plant', False)
            brain_widget.perceive('plant_in_view', 100.0 if plant else 0.0)
            brain_widget.perceive('squid_proximity', self._squid_proximity())

        # Get fresh input neuron values (this calls calculate_can_see_food(), etc.)
        input_values = self.brain_hooks.get_input_neuron_values()

        # Override specific neurons with VisionWorker results if available
        # This prioritizes the async worker result over the synchronous check
        if self.latest_vision_result:
            # Overwrite the hook's calculation with the worker's result
            input_values['can_see_food'] = 100.0 if self.latest_vision_result.can_see_food else 0.0

        if not input_values:
            return

        # Directly inject into the brain state
        # This overrides any propagation — input neurons are driven by the world, not the network
        for neuron_name, activation in input_values.items():
            # 1. Update visual/display state (what the user sees)
            if neuron_name in brain_widget.state:
                brain_widget.state[neuron_name] = activation
            
            # 2. CRITICAL FIX: Ensure internal neuron dict is also updated.
            # If we don't do this, the local simulation logic might use an old value.
            if hasattr(brain_widget, 'neurons') and neuron_name in brain_widget.neurons:
                brain_widget.neurons[neuron_name]['activation'] = activation

            # Optional: also update any cached activations if used in older logic/plugins
            if hasattr(brain_widget, 'neuron_activations') and neuron_name in brain_widget.neuron_activations:
                brain_widget.neuron_activations[neuron_name] = activation

        # CRITICAL ADDITION: Push these new values to the worker thread immediately.
        # Without this, the background worker has "stale" data (e.g., can_see_food=0) 
        # while the UI shows 100. This ensures Hebbian learning uses the correct values.
        if hasattr(brain_widget, '_update_worker_cache'):
            brain_widget._update_worker_cache()

        # Force a repaint to show immediate change
        brain_widget.update()

    def update_squid_brain(self):
        if not self.squid or not self.brain_window.isVisible():
            return

        # Robust startled detection
        is_startled_state = False
        if hasattr(self.squid, 'mental_state_manager') and self.squid.mental_state_manager:
            is_startled_state = self.squid.mental_state_manager.is_state_active('startled')
        elif hasattr(self.squid, 'status') and isinstance(self.squid.status, str):
            is_startled_state = "startled" in self.squid.status.lower()

        brain_state = {
            "hunger": self.squid.hunger,
            "happiness": self.squid.happiness,
            "cleanliness": self.squid.cleanliness,
            "sleepiness": self.squid.sleepiness,
            "anxiety": self.squid.anxiety,
            "curiosity": self.squid.curiosity,
            "satisfaction": self.squid.satisfaction,
            "is_sick": self.squid.is_sick,
            "is_eating": self.squid.is_eating if hasattr(self.squid, 'is_eating') else (self.squid.status == "eating"),
            "is_sleeping": self.squid.is_sleeping,
            "pursuing_food": self.squid.pursuing_food,
            "is_fleeing": getattr(self.squid, 'is_fleeing', False),
            "is_startled": is_startled_state,
            "direction": self.squid.squid_direction,
            "position": (self.squid.squid_x, self.squid.squid_y),
            "personality": self.squid.personality.value if isinstance(self.squid.personality, Personality) else str(self.squid.personality),
            "status": self.squid.status,
            'recent_actions': self.recent_actions[-10:],
            'food_count': len(self.food_items),
            'poop_count': len(self.poop_items),
        }

        # === DYNAMIC PERCEPTION ===
        if hasattr(self, 'brain_hooks'):
            input_values = self.brain_hooks.get_input_neuron_values()
            
            # Override with VisionWorker results
            if self.latest_vision_result:
                input_values['can_see_food'] = 100.0 if self.latest_vision_result.can_see_food else 0.0
            
            brain_state.update(input_values)

            # --- Force-sync inputs to bw.neurons to prevent Sync Loop overwrite
            if hasattr(self.brain_window, 'brain_widget'):
                bw = self.brain_window.brain_widget
                if hasattr(bw, 'neurons') and bw.neurons:
                    for k, v in input_values.items():
                        if k in bw.neurons:
                            # Update the internal simulation prop directly
                            bw.neurons[k]['activation'] = v

            # Decay temporal sensors so they don't stick forever
            self.brain_hooks.update_decay()

        # Allow plugins to inject or modify brain state
        self.plugin_manager.trigger_hook(
            "on_brain_state_update",
            brain_state=brain_state,
            squid=self.squid,
            logic=self
        )

        # Final push to brain visualizer
        self.brain_window.update_brain(brain_state)

        # Output bindings are evaluated exactly once per tick, from
        # update_simulation(). Doing it here as well made every "while above"
        # binding fire twice per second and decayed temporal sensors at a rate
        # that depended on whether the brain window happened to be open.


    def check_for_curiosity(self):
        if self.curious_cooldown > 0:
            self.curious_cooldown -= 1
            return

        # Base chance of becoming curious
        curious_chance = 0.02  # 2% base chance

        # Increase chance if satisfaction is high and anxiety is low
        if self.squid.satisfaction > 70 and self.squid.anxiety < 30:
            curious_chance *= 2  # Double the chance

        # Check for curiosity
        if random.random() < curious_chance:
            self.make_squid_curious()

    def _notice_journey(self) -> None:
        """Tell the player when the squid reaches a new stage of its life.

        Read every few seconds from what is true of the squid (life_journey);
        nothing is awarded here, only noticed. Whatever it had already
        reached when the game started is not announced again.
        """
        self._journey_ticks = getattr(self, '_journey_ticks', 0) + 1
        if self._journey_ticks % 10:
            return
        try:
            from .life_journey import JourneyTracker, gather_facts
            tracker = getattr(self, '_journey', None)
            if tracker is None:
                tracker = self._journey = JourneyTracker()
            for milestone in tracker.update(gather_facts(self)):
                self.show_message(f"✨ {milestone.title}")
                manager = getattr(self, 'plugin_manager', None)
                if manager is not None:
                    manager.trigger_hook('on_journey_milestone', key=milestone.key,
                                         title=milestone.title, squid=self.squid)
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Journey] could not be read: {type(e).__name__}: {e}")

    def _note_learned_action(self, bw) -> bool:
        """If the squid has just started one of its LEARNED actions - going to
        a plant, playing, lying down to rest - open that action's outcome
        window under the action neuron's own name and file it as a trial.

        True when it did, in which case the caller must not also open an
        episode from the status string: the same activity under two names is
        two episodes sharing the credit for one outcome.
        """
        from .action_discovery import behaviour_under_way
        from .brain_constants import ACTION_THRESHOLDS
        discovery = getattr(bw, 'action_discovery', None)
        squid = self.squid
        if discovery is None or squid is None:
            return False
        asleep = bool(getattr(squid, 'is_sleeping', False))
        fell_asleep = asleep and not getattr(self, '_was_asleep_last_tick', False)
        self._was_asleep_last_tick = asleep
        rest = float(bw.state.get('act_rest', 0.0) or 0.0)
        chose_rest = (rest >= ACTION_THRESHOLDS['act_rest']
                      or getattr(discovery, 'urge', None) == 'act_rest')
        drive = squid.get_neural_drive() if hasattr(squid, 'get_neural_drive') else None
        behaviour = behaviour_under_way(
            (drive or {}).get('action'), fell_asleep, chose_rest)
        if behaviour is None:
            if asleep and discovery.brain.causal_learning.current_action == 'sleeping':
                return True      # still the rest it chose; one bout, one episode
            return False
        discovery.acted(behaviour, bw.state)
        return True

    def _normalize_action_name(self, status_string):
        """
        Convert verbose status strings into trackable action categories.
        This prevents explosion of unique but semantically similar actions.
        """
        if not status_string:
            return 'idle'
            
        status_lower = status_string.lower()
        
        # Food-related behaviors
        if 'eating' in status_lower:
            return 'eating'
        elif 'eyeing food' in status_lower or 'approaching food' in status_lower:
            return 'pursuing_food'
        elif 'moving toward food' in status_lower:
            return 'pursuing_food'
        
        # Rock interactions
        elif 'rock' in status_lower:
            if 'throwing' in status_lower or 'thrown' in status_lower:
                return 'throwing_rock'
            elif 'approaching' in status_lower or 'eyeing' in status_lower:
                return 'investigating_rock'
            elif 'carrying' in status_lower:
                return 'carrying_rock'
        
        # Poop interactions
        elif 'poop' in status_lower:
            if 'throwing' in status_lower:
                return 'throwing_poop'
            elif 'approaching' in status_lower:
                return 'investigating_poop'
        
        # Plant interactions
        elif 'plant' in status_lower:
            # Going to a plant and staying in it is ONE action - the one the
            # act_shelter neuron stands for - and has to be one episode, or
            # the relief of hiding is credited to a different action from the
            # one that got the squid there.
            if ('hiding' in status_lower or 'comfort' in status_lower
                    or 'approaching' in status_lower or 'seeking' in status_lower):
                return 'approaching_plant'
            elif 'noticing' in status_lower:
                return 'noticing_plant'
        
        # Emotional/mental states
        elif 'startled' in status_lower or 'fleeing' in status_lower:
            return 'fleeing'
        elif 'anxious' in status_lower or 'nervous' in status_lower:
            return 'anxious'
        elif 'sleeping' in status_lower or 'drowsy' in status_lower or 'feeling drowsy' in status_lower:
            return 'sleeping'
        elif 'sick' in status_lower or 'ill' in status_lower or 'suffering' in status_lower:
            return 'sick'
        elif 'distressed' in status_lower:
            return 'distressed'
        
        # Encounters with another squid. These have to be nameable actions or
        # causal_learning sees 'idle' (a _NON_ACTION) and drops the episode,
        # so nothing an encounter causes could ever be attributed to it.
        elif 'contesting' in status_lower:
            return 'contesting'

        # Exploration behaviors
        elif 'exploring' in status_lower:
            return 'exploring'
        elif 'roaming' in status_lower or 'wandering' in status_lower or 'patrolling' in status_lower:
            return 'roaming'
        elif 'zooming' in status_lower or 'buzzing' in status_lower:
            return 'energetic_movement'
        elif 'resting' in status_lower or 'lounging' in status_lower:
            return 'resting'
        elif 'watching' in status_lower:
            return 'watching'
        elif 'seeking adventure' in status_lower:
            return 'seeking_adventure'
        elif 'searching' in status_lower or 'scouting' in status_lower:
            return 'searching'
        
        # Default fallback
        else:
            return 'idle'

    def make_squid_curious(self):
        self.squid.mental_state_manager.set_state("curious", True)
        self.curious_cooldown = self.curious_cooldown_max
        
        # Use the new add_thought method
        self.add_thought("Experiencing extreme curiosity")
        
        # Increase curiosity
        self.squid.curiosity = min(100, self.squid.curiosity + 20)

        # Memory
        self.squid.memory_manager.add_short_term_memory(
            'emotion', 'intense_curiosity',
            'Overwhelmed by intense curiosity!',
            importance=4
        )
        
        # Innate reflex: curiosity is intrinsically rewarding.
        if getattr(self, 'hebbian_learning', None) is not None:
            try:
                self.hebbian_learning.learn_from_curiosity()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Reflex] learn_from_curiosity failed: {type(e).__name__}: {e}")

        # Schedule the end of the curious state
        QtCore.QTimer.singleShot(5000, self.end_curious)  # End curious after 5 seconds

        # Start curious interactions
        self.curious_interaction_timer = QtCore.QTimer()
        self.curious_interaction_timer.timeout.connect(self.curious_interaction)
        self.curious_interaction_timer.start(1000)  # Check for interactions every second

    def end_curious(self):
        if self.mental_states_enabled:
            self.squid.mental_state_manager.set_state("curious", False)
        if hasattr(self, 'curious_interaction_timer'):
            self.curious_interaction_timer.stop()

    def curious_interaction(self):
        if self.curious_interaction_cooldown > 0:
            self.curious_interaction_cooldown -= 1
            return

        if random.random() < 0.6:  # Increased chance to 60% for more frequent interactions
            decorations = self.user_interface.get_nearby_decorations(self.squid.squid_x, self.squid.squid_y)
            if decorations:
                decoration = random.choice(decorations)
                if random.random() < 0.75:  # 75% chance to push decorations
                    direction = random.choice([-1, 1])  # -1 for left, 1 for right
                    self.squid.push_decoration(decoration, direction)
                else:
                    self.brain_window.add_thought("I am curious about a decoration item...")
                
                self.curious_interaction_cooldown = self.curious_interaction_cooldown_max

    def move_objects(self):
        self.move_foods()
        self.move_poops()

    def move_squid_to_bottom_left(self, callback):      # Force the squid to move to bottom left (buggy)
        target_x = 150  # Left edge + margin
        target_y = self.user_interface.window_height - 150 - self.squid.squid_height  # Bottom edge - margin - squid height

        # Disable Squid's ability to move in any other direction - doesn't work 100% - he puts up a fight sometimes!!
        self.squid.can_move = False

        def step_movement():
            dx = target_x - self.squid.squid_x
            dy = target_y - self.squid.squid_y

            if abs(dx) < 100 and abs(dy) < 100:
                # If close enough, snap to final position and call callback
                self.squid.squid_x = target_x
                self.squid.squid_y = target_y
                self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)
                self.squid.can_move = True  # Re-enable Squid's movement
                callback()
            else:
                # Determine direction of movement
                if abs(dx) > abs(dy):
                    # Move horizontally
                    self.squid.squid_x += 90 if dx > 0 else -90
                else:
                    # Move vertically
                    self.squid.squid_y += 90 if dy > 0 else -90

                # Update squid position
                self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)

                # Schedule next movement in 1000 ms
                QtCore.QTimer.singleShot(900, step_movement)

        # Start the movement
        step_movement()

    def update_statistics(self):
        if self.squid is None:
            return

        # ------- GUARD ---------------------------------------------------------
        if hasattr(self, 'statistics_window') and self.statistics_window is not None:
            self.statistics_window.update_statistics()
        # -----------------------------------------------------------------------

        self.update_cleanliness_overlay()

        # A dead squid has no metabolism. Its egg is about to take over.
        lifecycle = getattr(self.squid, 'lifecycle', None)
        if lifecycle is not None and lifecycle.is_dead:
            return

        if self.squid is not None:
            # A squid whose body has no health left - rocks and fights take it
            # and nothing gives it back - dies of its injuries, asleep or
            # awake, as on Android (src/lifecycle.py).
            if lifecycle is not None and lifecycle.injure(self.squid):
                self.on_squid_died()
                return

            # Update squid needs
            if not self.squid.is_sleeping:
                self.squid.hunger      = min(100, self.squid.hunger      + (0.1 * self.simulation_speed))
                self.squid.sleepiness  = min(100, self.squid.sleepiness  + (0.12 * self.simulation_speed))
                self.squid.happiness   = max(0,   self.squid.happiness   - (0.1 * self.simulation_speed))
                self.squid.cleanliness = max(0,   self.squid.cleanliness - (0.1 * self.simulation_speed))

                # Update new neurons
                self.update_satisfaction()
                self.update_anxiety()
                self.update_curiosity()

                # Check for special status effects on anxiety reduction.
                if self.squid.status == "hiding behind plant":
                    previous_anxiety = self.squid.anxiety
                    # Hiding in a plant is how a squid's anxiety comes down:
                    # there are no neurons that lower it by themselves any
                    # more. Strong enough to be felt within the few seconds an
                    # action's consequence is watched for, or the squid could
                    # hide a hundred times and never be able to tell it helped.
                    self.squid.anxiety = max(0, self.squid.anxiety - (PLANT_CALM_PER_TICK * self.simulation_speed))
                    if self.squid.anxiety < previous_anxiety:
                        memory_value = "Being near plants is calming (Anxiety reduction)"
                        self.squid.memory_manager.add_short_term_memory(
                            'environment',
                            'plant_calming_effect',
                            memory_value,
                            importance=1.5
                        )
                        self.plant_calming_effect_counter += 1
                        if self.plant_calming_effect_counter >= 5:
                            self.squid.memory_manager.transfer_to_long_term_memory(
                                'environment',
                                'plant_calming_effect'
                            )
                            self.plant_calming_effect_counter = 0

                # Check if cleanliness has been too low for too long
                if self.squid.cleanliness < 20:
                    self.cleanliness_threshold_time += 1
                else:
                    self.cleanliness_threshold_time = 0

                # Check if hunger has been too high for too long
                if self.squid.hunger > 80:
                    self.hunger_threshold_time += 1
                else:
                    self.hunger_threshold_time = 0

                # Check if squid becomes sick (80 % chance)
                if ((self.cleanliness_threshold_time >= 10 * self.simulation_speed and
                    self.cleanliness_threshold_time <= 60 * self.simulation_speed) or
                    (self.hunger_threshold_time >= 10 * self.simulation_speed and
                    self.hunger_threshold_time <= 50 * self.simulation_speed)):
                    if random.random() < 0.8:
                        self._set_sickness_state(True)
                # Sickness persists until medicine or an explicit game reset.

                # Wounds heal in sleep, in a squid that is fed and not ill.
                # Health used only ever to go down, so every fight and every
                # thrown rock was permanent damage: thirteen lost fights killed
                # a squid whatever happened in between, which makes a squid
                # that meets others often a squid that dies soon. What a fight
                # leaves for good is what it should leave - the memory of it,
                # the experience, and the mark on its aggression - not a body
                # that can never recover.
                heal_in_sleep(self.squid, self.simulation_speed)

                # New logic for health decrease based on happiness and cleanliness
                if self.squid.happiness < 20 and self.squid.cleanliness < 20:
                    health_decrease = 0.2 * self.simulation_speed  # Rapid decrease
                else:
                    health_decrease = 0.1 * self.simulation_speed 

                # Only a parent, which no longer eats, actually loses this
                # health - and only once it is starving. Every other squid's
                # health is untouched here, exactly as before. Any squid can
                # also die of neglect or of a sickness left untreated, counted
                # in the same play-time as the needs above.
                if lifecycle is not None:
                    seconds = float(self.simulation_speed)
                    setting = self._lifecycle_setting
                    if (lifecycle.starve(self.squid, health_decrease,
                                         setting('starvation_hunger'))
                            or lifecycle.sicken(self.squid, seconds,
                                                setting('sickness_seconds'))
                            or lifecycle.neglect(self.squid, seconds,
                                                 setting('neglect_hunger'),
                                                 setting('neglect_seconds'))):
                        self.on_squid_died()

    def handle_window_resize(self, event):
        new_width = event.size().width()
        new_height = event.size().height()
        
        # Get current dimensions from user interface
        current_width = self.user_interface.window_width
        current_height = self.user_interface.window_height
        
        # Calculate size change
        width_change = new_width - current_width
        height_change = new_height - current_height
        
        # Create new_size tuple for brain hooks
        new_size = (new_width, new_height)  # ADD THIS LINE
        
        # Update window dimensions in UI
        self.user_interface.window_width = new_width
        self.user_interface.window_height = new_height
        
        # Update UI elements through user interface
        self.user_interface.handle_window_resize(event)
        
        # Notify logic about resize with size change info
        self.brain_hooks.on_window_resize(width_change, height_change, new_size)
        self.handle_window_resize_event(
            width_change, 
            height_change,
            new_size
        )

        #print("Initial startle protection period ended")
    
    def handle_window_resize_event(self, width_change, height_change, new_size):
        """Handle window resize events with specific effects"""
        # First resize startles the squid (only once and after the initial delay)
        if not self.has_been_resized and self.initial_startle_allowed:
            self.startle_squid(source="first_resize")
            self.has_been_resized = True
            self.add_thought("positive: My environment got bigger!")
            self.last_window_size = new_size
            return

        # Only startle for MAJOR size changes (increased threshold)
        if (abs(width_change) > 200 or abs(height_change) > 200) and random.random() < 0.3:  # Added randomness
            # self.startle_squid(source="major_resize") # STARTLE WHEN WINDOW IS RESIZED
            return

        # Check if window got bigger
        if new_size[0] > self.last_window_size[0] or new_size[1] > self.last_window_size[1]:
            # Positive effect for enlargement
            self.squid.happiness = min(100, self.squid.happiness + 5)
            self.squid.satisfaction = min(100, self.squid.satisfaction + 3)
            self.was_big = True

            memory_msg = "My environment got bigger!"
            self.squid.memory_manager.add_short_term_memory(
                'environment',
                'window_enlarged',
                memory_msg
            )
            self.add_thought("More space to swim!")

        # Check if window got smaller after being big
        elif self.was_big and (new_size[0] < self.last_window_size[0] or new_size[1] < self.last_window_size[1]):
            # Negative effect for reduction
            self.squid.happiness = max(0, self.squid.happiness - 5)
            self.squid.anxiety = min(100, self.squid.anxiety + 5)

            memory_msg = "negative: decreased happiness and increased anxiety from less space"
            self.squid.memory_manager.add_short_term_memory(
                'environment',
                'window_reduced',
                memory_msg
            )
            self.add_thought("The space is shrinking...")

        # Update last known size
        self.last_window_size = new_size

    def show_message(self, message):
        display = getattr(getattr(self, 'user_interface', None), 'show_message', None)
        if callable(display):
            # The UI removes only its own message, preserving name badges and
            # multiplayer labels. The old path deleted every text item.
            return display(message)
        # Call hook if available
        if hasattr(self, 'plugin_manager'):
            # Get modified message from plugins
            results = self.plugin_manager.trigger_hook(
                "on_message_display", 
                tamagotchi_logic=self,
                original_message=message
            )
            
            # Check if any plugin modified the message
            for result in results:
                if isinstance(result, str) and result:
                    message = result
                    break
        
        # Use the user_interface's scene instead of self.scene
        if hasattr(self, 'user_interface') and hasattr(self.user_interface, 'scene'):
            scene = self.user_interface.scene
            # Remove any existing message items
            for item in scene.items():
                if isinstance(item, QtWidgets.QGraphicsTextItem):
                    scene.removeItem(item)

            # Create a new QGraphicsTextItem for the message
            message_item = QtWidgets.QGraphicsTextItem(message)
            message_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))  # White text
            message_item.setFont(QtGui.QFont("Fio UI", 10, QtGui.QFont.Bold))
            message_item.setPos(0, self.user_interface.window_height - 75)  # Position the message higher
            message_item.setTextWidth(self.user_interface.window_width)
            message_item.setHtml(f'<div style="text-align: center; background-color: #000000; padding: 5px;">{message}</div>')
            message_item.setZValue(10)  # Ensure the message is on top
            message_item.setOpacity(1)

            # Add the new message item to the scene
            scene.addItem(message_item)

            # Fade out the message after 8 seconds
            # Parented to the message, or Python collects it on return and the
            # message neither fades nor goes away.
            fade_out_animation = QtCore.QPropertyAnimation(message_item, b"opacity",
                                                           message_item)
            fade_out_animation.setDuration(8000)
            fade_out_animation.setStartValue(1.0)
            fade_out_animation.setEndValue(0.0)
            fade_out_animation.finished.connect(lambda: scene.removeItem(message_item))
            fade_out_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def show_thought(self, text):
        """Display a squid 'thought' in yellow."""
        self.user_interface.show_message(f'<span style="color:#FFEB3B;">{text}</span>')


    def update_score(self):
        if self.squid is not None:
            if not self.squid.is_sick and self.squid.happiness >= 80 and self.squid.cleanliness >= 80:
                self.points += 1
            elif self.squid.is_sick or self.squid.hunger >= 80 or self.squid.happiness <= 20:
                self.points -= 1

            self.user_interface.update_points(self.points)

    def toggle_debug_mode(self):
        """Toggle debug mode across all components without circular references"""
        # Set the new state directly (don't toggle twice)
        new_debug_mode = not self.debug_mode
        self.debug_mode = new_debug_mode
        
        # Propagate to statistics window
        if hasattr(self, 'statistics_window') and self.statistics_window:
            self.statistics_window.set_debug_mode(new_debug_mode)
        
        # Propagate to brain window, WITHOUT triggering a callback
        if hasattr(self, 'brain_window') and self.brain_window:
            # Set a flag to indicate we're in the middle of propagating
            self._propagating_debug_mode = True
            
            # Set brain window's debug mode
            self.brain_window.set_debug_mode(new_debug_mode)
            
            # Set brain widget's debug mode directly 
            if hasattr(self.brain_window, 'brain_widget'):
                self.brain_window.brain_widget.debug_mode = new_debug_mode
            
            # Clear the propagation flag
            self._propagating_debug_mode = False
        
        # User interface components
        if hasattr(self, 'user_interface'):
            if hasattr(self.user_interface, 'debug_mode'):
                self.user_interface.debug_mode = new_debug_mode
        
        print(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")

    # New methods to update the new neurons
    def update_satisfaction(self):
        # Update satisfaction based on hunger, happiness, and cleanliness
        hunger_factor = max(0, 1 - self.squid.hunger / 100)
        happiness_factor = self.squid.happiness / 100
        cleanliness_factor = self.squid.cleanliness / 100

        satisfaction_change = (hunger_factor + happiness_factor + cleanliness_factor) / 3
        satisfaction_change = (satisfaction_change - 0.5) * 2  # Scale to range from -1 to 1

        self.squid.satisfaction += satisfaction_change * self.simulation_speed
        self.squid.satisfaction = max(0, min(100, self.squid.satisfaction))

    def update_anxiety(self):
        # Update anxiety based on hunger, cleanliness, and health
        hunger_factor = self.squid.hunger / 100
        cleanliness_factor = 1 - self.squid.cleanliness / 100
        health_factor = 1 - self.squid.health / 100

        if self.squid.personality == Personality.GREEDY:
            hunger_factor *= 1.5  # Greedy squids get more anxious when hungry

        anxiety_change = (hunger_factor + cleanliness_factor + health_factor) / 3

        if self.squid.personality == Personality.TIMID and self.squid.is_near_plant():
            anxiety_change *= 0.5  # Timid squids are less anxious near plants

        self.squid.anxiety += anxiety_change * self.simulation_speed
        self.squid.anxiety = max(0, min(100, self.squid.anxiety))

    def update_curiosity(self):
        # Update curiosity based on satisfaction and anxiety
        if self.squid.satisfaction > 70 and self.squid.anxiety < 30:
            curiosity_change = 0.2 * self.simulation_speed
        else:
            curiosity_change = -0.1 * self.simulation_speed

        # Adjust curiosity change based on personality
        if self.squid.personality == Personality.TIMID:
            curiosity_change *= 0.5  # Timid squids are less curious
        elif self.squid.personality == Personality.ADVENTUROUS:
            curiosity_change *= 1.5  # Adventurous squids are more curious

        self.squid.curiosity += curiosity_change
        self.squid.curiosity = max(0, min(100, self.squid.curiosity))


    def trigger_rock_test(self):
        """Trigger rock test from UI using the interaction manager"""
        if not hasattr(self, 'rock_interaction'):
            self.show_message("Rock interaction system not initialized!")
            return
                
        # Find all valid rocks in the scene using the interaction manager's checker
        rocks = [item for item in self.user_interface.scene.items() 
                if isinstance(item, ResizablePixmapItem) 
                and self.rock_interaction.is_valid_rock(item)]
        
        if not rocks:
            self.show_message("No rocks found in the tank!")
            return
            
        if not hasattr(self, 'squid'):
            self.show_message("Squid not initialized!")
            return
            
        # Find nearest rock to squid
        nearest_rock = min(rocks, key=lambda r: 
            math.hypot(
                r.sceneBoundingRect().center().x() - self.squid.squid_x,
                r.sceneBoundingRect().center().y() - self.squid.squid_y
            )
        )
        
        # Highlight the rock (visual feedback)
        self.highlight_rock(nearest_rock)
        
        # Start the test through the interaction manager
        self.rock_interaction.start_rock_test(nearest_rock)
        
        # Show status message
        self.show_message("Rock test initiated")

    def is_valid_rock(self, item):
        """Check if an item is a valid rock decoration"""
        if not isinstance(item, ResizablePixmapItem):
            return False
        # Check if it's a rock based on filename or category
        if hasattr(item, 'category') and item.category == 'rock':
            return True
        if hasattr(item, 'filename') and 'rock' in item.filename.lower():
            return True
        return False

    def update_rock_interaction(self):
        """Unified method used for both test and autonomous interactions"""
        if not hasattr(self.squid, 'current_rock_target') or not self.squid.current_rock_target:
            return
        
        rock = self.squid.current_rock_target
        rock_rect = rock.sceneBoundingRect()
        squid_rect = self.squid.squid_item.sceneBoundingRect()
        
        # Calculate precise distance between edges
        dx = rock_rect.center().x() - squid_rect.center().x()
        dy = rock_rect.center().y() - squid_rect.center().y()
        distance = math.hypot(dx, dy)
        
        if self.squid.status == "approaching_rock":
            if distance < 40:  # Close enough to pick up
                if self.squid.pick_up_rock(rock):
                    self.squid.status = "carrying_rock"
                    self.squid.rock_carry_timer = random.randint(30, 50)  # 3-5 seconds
                else:
                    self.squid.current_rock_target = None
            else:
                # Move toward rock at normal speed
                self.squid.move_toward_position(rock_rect.center())
        
        elif self.squid.status == "carrying_rock":
            self.squid.rock_carry_timer -= 1
            if self.squid.rock_carry_timer <= 0:
                self.rock_interaction.decide_rock_action()
                self.squid.current_rock_target = None

    def update_rock_test(self):
        """Delegate to interaction manager"""
        if hasattr(self, 'rock_interaction'):
            self.rock_interaction.update_rock_test()

    def update_status_bar(self):
            """Update the status bar with the current plugin state"""
            if hasattr(self.user_interface, 'status_bar'):
                self.user_interface.status_bar.update_plugins_status(self.plugin_manager)
                
                # Check for multiplayer plugin specifically
                if 'MultiplayerPlugin' in self.plugin_manager.enabled_plugins:
                    # Try to get the plugin instance
                    for plugin_name, plugin_data in self.plugin_manager.plugins.items():
                        if plugin_name == 'MultiplayerPlugin' and 'instance' in plugin_data:
                            plugin = plugin_data['instance']
                            
                            # Update network status if plugin has a network node
                            if hasattr(plugin, 'network_node') and plugin.network_node:
                                self.user_interface.status_bar.update_network_status(
                                    plugin.network_node.is_connected,
                                    plugin.network_node.node_id
                                )
                            
                            # Update peers count
                            if hasattr(plugin, 'network_node') and plugin.network_node:
                                peers_count = len(plugin.network_node.known_nodes)
                                self.user_interface.status_bar.update_peers_count(peers_count)

    def setup_poop_interaction(self):
        """Initialize poop interaction manager"""
        
        # Check if config manager has poop config
        if not hasattr(self.config_manager, 'get_poop_config'):
            # Create a default poop config if not available
            def get_poop_config():
                return {
                    'min_carry_duration': 3.0,
                    'max_carry_duration': 9.0,
                    'pickup_prob': 0.2,
                    'throw_prob': 0.3,
                    # Optional additional config parameters
                    'happiness_penalty': 5,
                    'anxiety_increase': 10
                }
            self.config_manager.get_poop_config = get_poop_config
        
        # Initialize poop interaction
        self.poop_interaction = PoopInteractionManager(
            squid=self.squid,
            logic=self,
            scene=self.user_interface.scene,
            message_callback=self.show_message,
            config_manager=self.config_manager
        )

    def check_poop_interaction(self):
        """Unified method for poop interaction checks"""
        if not hasattr(self, 'poop_interaction'):
            self.setup_poop_interaction()
        
        if not getattr(self.squid, 'current_poop_target', None):
            return
        
        poop = self.squid.current_poop_target
        poop_rect = poop.sceneBoundingRect()
        squid_rect = self.squid.squid_item.sceneBoundingRect()
        
        # Calculate precise distance between edges
        dx = poop_rect.center().x() - squid_rect.center().x()
        dy = poop_rect.center().y() - squid_rect.center().y()
        distance = math.hypot(dx, dy)
        
        if self.squid.status == "approaching_poop":
            if distance < 40:  # Close enough to pick up
                if self.squid.pick_up_poop(poop):
                    self.squid.status = "carrying_poop"
                    self.squid.poop_carry_timer = random.randint(30, 50)  # 3-5 seconds
                else:
                    self.squid.current_poop_target = None
            else:
                # Move toward poop at normal speed
                self.squid.move_toward_position(poop_rect.center())
        
        elif self.squid.status == "carrying_poop":
            self.squid.poop_carry_timer -= 1
            if self.squid.poop_carry_timer <= 0:
                direction = "left" if random.random() < 0.5 else "right"
                if self.squid.throw_poop(direction):
                    self.squid.status = "roaming"
                    self.squid.current_poop_target = None
