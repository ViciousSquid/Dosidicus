
from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import time
import json
import math
from .statistics_window import StatisticsWindow
from .save_manager import SaveManager
from .rps_game import RPSGame
from .squid import Personality, Squid
from .ui import ResizablePixmapItem
from .brain_tool import SquidBrainWindow
from .learning import HebbianLearning
from .interactions import RockInteractionManager
from .interactions2 import PoopInteractionManager
from .config_manager import ConfigManager
from .plugin_manager import PluginManager

class TamagotchiLogic:
    def __init__(self, user_interface, squid, brain_window):
        self.config_manager = ConfigManager()
        self._propagating_debug_mode = False
        self.user_interface = user_interface
        self.mental_states_enabled = True
        self.squid = squid
        self.brain_window = brain_window
        
        # Initialize rock interaction manager with config
        self.rock_interaction = RockInteractionManager(
            squid=self.squid,
            logic=self,
            scene=self.user_interface.scene,
            message_callback=self.show_message,
            config_manager=self.config_manager  # Add this line
        )
        self.user_interface = user_interface
        self.squid = squid
        self.brain_window = brain_window
        self.window_resize_cooldown = 0
        self.window_resize_cooldown_max = 30  # 30 updates before another resize can startle
        self.has_been_resized = False
        self.was_big = False
        self.debug_mode = False
        self.last_window_size = (1280, 900)  # Default size

        # Initialize plugin manager
        self.plugin_manager = PluginManager()
        self.plugin_manager.load_all_plugins()

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
        self.food_width = 64
        self.food_height = 64
        self.poop_items = []
        self.max_poop = 3
        self.points = 0

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

        # Initialize save manager
        self.save_manager = SaveManager()
        self.load_game()

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
        self.statistics_window.show()

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

        ################################
        #### MENTAL STATE COOLDOWNS ####
        ################################

        self.startle_cooldown = 0
        self.startle_cooldown_max = 30 
        self.mental_states_enabled = True 
        self.curious_cooldown = 0
        self.curious_cooldown_max = 20
        self.curious_interaction_cooldown = 1
        self.curious_interaction_cooldown_max = 5
        self.startle_cooldown = 1000
        self.plant_calming_effect_counter = 0

    

    def set_squid(self, squid):
        self.squid = squid

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
        if self.squid and self.squid.status in ["eating cheese", "eating sushi"]:
            # Choose default status based on personality
            if self.squid.personality == Personality.TIMID:
                self.squid.status = "cautiously exploring"
            elif self.squid.personality == Personality.ADVENTUROUS:
                self.squid.status = "boldly exploring"
            else:
                self.squid.status = "roaming"



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
            
            # Get brain network state if available
            if hasattr(self, 'squid_brain_window') and self.squid_brain_window:
                brain_state = self.squid_brain_window.brain_widget.state
            else:
                brain_state = {}
            
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

    def get_active_memories(self):
        # Get raw memory objects instead of display strings
        memories = self.squid.memory_manager.get_all_short_term_memories(raw=True)[:3]
        return [f"{m['category']}: {m['value']}" for m in memories]

    def get_available_actions(self):
        return ["search_for_food", "explore", "sleep", "move_randomly", "interact_object"]

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


    def update_decoration_learning(self, effects):
        if not effects:
            return

        # Get the current state of the squid
        current_state = {
            "hunger": self.squid.hunger,
            "happiness": self.squid.happiness,
            "cleanliness": self.squid.cleanliness,
            "sleepiness": self.squid.sleepiness,
            "satisfaction": self.squid.satisfaction,
            "anxiety": self.squid.anxiety,
            "curiosity": self.squid.curiosity
        }

        # Update the brain based on the decoration effects
        for stat, boost in effects.items():
            if stat in current_state:
                # Increase the connection strength between the affected stat and satisfaction
                self.brain_window.brain_widget.strengthen_connection(stat, 'satisfaction', boost * 0.01)
                
                # If the boost is significant, also strengthen connection with happiness
                if boost > 5:
                    self.brain_window.brain_widget.strengthen_connection(stat, 'happiness', boost * 0.005)

        # Update the squid's memory
        decoration_memory = {
            "category": "decorations",
            "effects": effects,
            "timestamp": time.time()
        }
        self.squid.memory_manager.add_short_term_memory('decorations', str(time.time()), decoration_memory)

        # If this is a significant effect, consider transferring to long-term memory
        if any(boost > 10 for boost in effects.values()):
            self.squid.memory_manager.transfer_to_long_term_memory('decorations', str(time.time()))


    def _log_thought(self, thought):
        self.thought_log.append(thought)
        print(f"Squid thought: {thought}")

    def check_for_decoration_attraction(self):
        squid_x = self.squid.squid_x
        squid_y = self.squid.squid_y
        
        active_decorations = self.get_nearby_decorations(squid_x, squid_y)
        
        if active_decorations:
            self.apply_decoration_effects(active_decorations)
            
            # NEW: Check for plant contact and update status
            is_hiding = False
            for decoration in active_decorations:
                if hasattr(decoration, 'category') and decoration.category == 'plant':
                    if decoration.collidesWithItem(self.squid.squid_item):
                        self.squid.status = "hiding behind plant"
                        is_hiding = True
                        break  # Squid can only hide behind one plant at a time
            
            if not is_hiding and self.squid.status == "hiding behind plant":
                self.squid.status = "roaming" # Or another default status
                
            # Move decorations
            for decoration in active_decorations:
                decoration_pos = decoration.pos()
                if decoration_pos.x() < squid_x:
                    self.move_decoration(decoration, 5)  # Move right
                else:
                    self.move_decoration(decoration, -5)  # Move left

    def get_nearby_decorations(self, x, y, radius=100):
        nearby_decorations = []
        for item in self.user_interface.scene.items():
            if isinstance(item, ResizablePixmapItem):
                item_center = item.sceneBoundingRect().center()
                distance = ((item_center.x() - x) ** 2 + (item_center.y() - y) ** 2) ** 0.5
                if distance <= radius:
                    nearby_decorations.append(item)
        return nearby_decorations
    
    def investigate_object(self):
        if self.detected_object_position:
            self.move_towards(self.detected_object_position[0], self.detected_object_position[1])
            
            # Add thoughts
            self.brain_window.add_thought("Investigating unknown object")
            
            if self.distance_to(self.detected_object_position[0], self.detected_object_position[1]) < 20:
                object_item = self.tamagotchi_logic.get_item_at_position(self.detected_object_position[0], self.detected_object_position[1])
                if object_item:
                    if isinstance(object_item, Food):
                        self.brain_window.add_thought("Unknown object appears to be food")
                        self.eat() 
                        self.brain_window.add_thought("Ate the food!")
                    elif isinstance(object_item, Decoration):
                        self.brain_window.add_thought("Unknown object appears to be a decoration")
                        self.interact_with_decoration(object_item)

                self.object_visible = False
                self.detected_object_position = None
    
    def check_collision_with_cheese(self, cheese_item):
        if self.squid.personality == Personality.STUBBORN:
            return False  # Stubborn squids never collide with cheese
        
        squid_rect = self.squid.boundingRect().translated(self.squid.squid_x, self.squid.squid_y)
        cheese_rect = cheese_item.boundingRect().translated(cheese_item.pos())
        
        return squid_rect.intersects(cheese_rect)
    
    def move_decoration(self, decoration, dx):
        current_pos = decoration.pos()
        new_x = current_pos.x() + dx
        
        # Ensure the decoration stays within the scene boundaries
        scene_rect = self.user_interface.scene.sceneRect()
        new_x = max(scene_rect.left(), min(new_x, self.user_interface.window_width - decoration.boundingRect().width()))
        
        # Use QVariantAnimation because QGraphicsPixmapItem does not inherit from QObject.
        # This animation will interpolate the position value for us.
        animation = QtCore.QVariantAnimation()
        animation.setStartValue(current_pos)
        animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
        animation.setDuration(300)  # 300 ms duration
        animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        
        # Connect the animation's valueChanged signal to the item's setPos method
        animation.valueChanged.connect(decoration.setPos)
        
        # Store the animation object to prevent it from being garbage collected
        decoration._animation = animation
        
        # Start the animation and have it delete itself when finished
        animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def apply_decoration_effects(self, active_decorations):
        """Apply effects from nearby decorations"""
        if not active_decorations:
            return

        effects = {}
        strongest_effect = 0
        strongest_decoration = None

        for decoration in active_decorations:
            if not hasattr(decoration, 'filename') or decoration.filename is None:
                continue
            if not hasattr(decoration, 'stat_modifiers') or not decoration.stat_modifiers:
                continue

            # Find the decoration with the strongest effect (absolute value)
            max_modifier = max(abs(val) for val in decoration.stat_modifiers.values())
            if max_modifier > strongest_effect:
                strongest_effect = max_modifier
                strongest_decoration = decoration

        if strongest_decoration:
            # Apply stat modifiers additively
            for stat, modifier in strongest_decoration.stat_modifiers.items():
                if hasattr(self.squid, stat):
                    current_value = getattr(self.squid, stat)
                    new_value = current_value + modifier
                    # Clamp the value between 0 and 100
                    new_value = max(0, min(100, new_value))
                    setattr(self.squid, stat, new_value)
                    effects[stat] = modifier

            # Apply category-specific effects
            if strongest_decoration.category == 'plant':
                old_cleanliness = self.squid.cleanliness
                self.squid.cleanliness = min(self.squid.cleanliness + 5, 100)
                effects['cleanliness'] = effects.get('cleanliness', 0) + (self.squid.cleanliness - old_cleanliness)
            elif strongest_decoration.category == 'rock':
                old_satisfaction = self.squid.satisfaction
                self.squid.satisfaction = min(self.squid.satisfaction + 5, 100)
                effects['satisfaction'] = effects.get('satisfaction', 0) + (self.squid.satisfaction - old_satisfaction)

        if strongest_decoration and hasattr(strongest_decoration, 'filename') and strongest_decoration.filename is not None:
            self.squid.memory_manager.add_short_term_memory('decorations', strongest_decoration.filename, effects)
        else:
            if effects:
                self.squid.memory_manager.add_short_term_memory('decorations', 'nearby_decorations', effects)

        if effects:
            self.update_decoration_learning(effects)

    def check_decoration_startle(self, active_decorations):
        if not self.mental_states_enabled:
            return

        if self.startle_cooldown > 0:
            return

        # Very low chance of being startled by decorations
        decoration_startle_chance = 0.001 * len(active_decorations)  # 0.1% chance per decoration

        # Increase chance if anxiety is high
        if self.squid.anxiety > 70:
            decoration_startle_chance *= (self.squid.anxiety / 50)

        if random.random() < decoration_startle_chance:
            self.startle_squid()
            self.show_message("Squid was startled by a decoration!")
            self.brain_window.add_thought("Startled by a decoration!")

    def show_decoration_message(self, decoration):
        category = decoration.category
        messages = {
            'plant': [
                "Squid seems fascinated by the plants!",
                "Your squid is enjoying the greenery.",
                "The plant decoration is making your squid happy."
            ],
            'rock': [
                "Your squid is exploring the rocky terrain.",
                "Squid seems intrigued by the rock formation.",
                "The rock decoration provides a nice hiding spot for your squid."
            ]
        }

        if category in messages:
            message = random.choice(messages[category])
        else:
            message = "Squid is interacting with the decoration."

        self.user_interface.show_message(message)

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
        if hasattr(self, 'rock_interaction'):
            self.rock_interaction.setup_timers(interval=100)
            self.rock_interaction.rock_test_timer.timeout.connect(
                self.rock_interaction.update_rock_test
            )
            self.rock_interaction.throw_animation_timer.timeout.connect(
                self.rock_interaction.update_throw_animation
            )

        # Set up poop interaction
        if hasattr(self, 'poop_interaction'):
            self.poop_interaction.setup_timers(interval=100)
        
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
        else:
            interval = max(10, self.base_interval // self.simulation_speed)  # Ensure minimum interval
            self.simulation_timer.start(interval)

    def check_for_startle(self):
        if not self.mental_states_enabled:
            return

        # Only check for new startle if not currently startled and initial startle allowed
        if self.squid.is_fleeing or not self.initial_startle_allowed:
            return

        if self.startle_cooldown > 0:
            self.startle_cooldown -= 1
            return

        # Base chance of being startled
        startle_chance = 0.002  # low base chance

        # Increase chance if anxiety is high
        if self.squid.anxiety > 70:
            startle_chance *= (self.squid.anxiety / 50)  # Up to 2x more likely when anxiety is >70

        # Check for startle
        if random.random() < startle_chance:
            self.startle_squid()

    def startle_squid(self, source="unknown"):
        if not self.mental_states_enabled:
            return

        # Add protection against startling during initialization
        if not getattr(self, 'initial_startle_allowed', False):
            return

        try:
            # Ensure speed attributes exist
            if not hasattr(self.squid, 'base_speed'):
                self.squid.base_speed = 90
            if not hasattr(self.squid, 'current_speed'):
                self.squid.current_speed = self.squid.base_speed

            # Set startled state
            self.squid.mental_state_manager.set_state("startled", True)
            self.startle_cooldown = self.startle_cooldown_max

            # Change status to more descriptive startled state
            previous_status = getattr(self.squid, 'status', "roaming")

            if source == "first_resize":
                self.squid.status = "startled by environment change"
            elif source == "incoming_rock":
                self.squid.status = "startled by rock"
            elif source == "detected_squid":
                self.squid.status = "startled by other squid"
            elif source == "targeted_by_rock":
                self.squid.status = "fleeing"
            elif source in ["environment", "decoration"]:
                self.squid.status = "startled"
            else:
                # Check for personality-specific startle reactions
                if self.squid.personality == Personality.TIMID:
                    self.squid.status = "hiding"
                else:
                    self.squid.status = "startled"

            self.squid.is_fleeing = True
            self.squid.current_speed = 180  # 2x speed boost

            # Random direction
            self.squid.direction = random.choice(['up', 'down', 'left', 'right'])

            # --- START OF RESILIENCE MODIFICATIONS ---

            # 1. Get the number of stress neurons from the brain
            stress_neuron_count = 0
            if self.brain_window and hasattr(self.brain_window, 'brain_widget'):
                # Assuming you added get_stress_neuron_count() to BrainWidget
                stress_neuron_count = self.brain_window.brain_widget.get_stress_neuron_count()

            # 2. Calculate resilience with diminishing returns (using natural logarithm)
            # The +1 ensures that we don't take log(0) and that the first neuron provides a benefit.
            resilience_factor = math.log(stress_neuron_count + 1)
            
            # 3. Define base anxiety increase and apply resilience
            if source == "first_resize":
                base_anxiety_increase = 5
                message = "The squid noticed its environment changing!"
                base_ink_chance = 0.6
            else:
                base_anxiety_increase = 15 # Slightly increased base for other startles
                message = "The squid was startled!"
                base_ink_chance = 0.6
            
            # Dampen the anxiety increase by the resilience factor
            # The 'max(0, ...)' ensures anxiety never decreases from a startle
            anxiety_increase = max(0, base_anxiety_increase - (resilience_factor * 5)) # Each point of resilience factor negates 5 points of anxiety

            # Apply anxiety, clamped at 100
            self.squid.anxiety = min(100, self.squid.anxiety + anxiety_increase)
            
            # Add a thought that shows the resilience in action
            if stress_neuron_count > 0:
                self.brain_window.add_thought(f"Startled, but felt {resilience_factor:.1f}x more resilient. Anxiety increased by only {anxiety_increase:.1f}.")

            # --- END OF RESILIENCE MODIFICATIONS ---

            # First startle detection
            is_first_startle = not hasattr(self, '_has_startled_before')
            if is_first_startle:
                self._has_startled_before = True

            # Increase ink chance based on anxiety
            ink_chance = base_ink_chance
            if self.squid.anxiety > 60:
                ink_chance = 0.9 # Increase to 90% if anxiety > 60

            # Ink cloud - Modified logic
            produce_ink = is_first_startle or random.random() < ink_chance

            # Create memory
            memory_value = (f"Startled! Status changed from {previous_status} to {self.squid.status}, "
                        f"Speed {self.squid.current_speed}px, Direction {self.squid.direction}")
            self.squid.memory_manager.add_short_term_memory(
                'behavior',
                'startle_response',
                memory_value
            )

            self.show_message(message)
            
            # Ink cloud
            if produce_ink:
                self.create_ink_cloud()
            
            # End flee after 3 seconds
            QtCore.QTimer.singleShot(self.startle_cooldown_max * 100, lambda: self.end_fleeing(previous_status))
            
        except Exception as e:
            print(f"Error during startle: {str(e)}")
            self.show_message("The squid panicked!")


    def end_fleeing(self, previous_status="roaming"):
        """Reset speed and status after fleeing ends"""
        if hasattr(self, 'squid') and self.squid:
            self.squid.is_fleeing = False
            self.squid.current_speed = self.squid.base_speed
            
            # Set more descriptive status based on anxiety level
            if self.squid.anxiety > 80:
                self.squid.status = "extremely anxious"
            elif self.squid.anxiety > 60:
                self.squid.status = "anxious" 
            elif self.squid.anxiety > 40:
                self.squid.status = "nervous"
            elif self.squid.anxiety > 20:
                self.squid.status = "recovering from startle"
            else:
                # Use a more specific status based on personality
                if self.squid.personality == Personality.TIMID:
                    self.squid.status = "cautiously exploring"
                elif self.squid.personality == Personality.ADVENTUROUS:
                    self.squid.status = "boldly exploring"
                else:
                    self.squid.status = previous_status
                
            self.squid.mental_state_manager.set_state("startled", False)  # Explicitly clear startled state
            
            if self.debug_mode:
                print(f"Fleeing ended - status returned to {self.squid.status}")
            
            self.squid.memory_manager.add_short_term_memory(
                'behavior',
                'calm_after_startle',
                f"Returned to {self.squid.status} status after fleeing"
            )


    def create_ink_cloud(self):
        """Create an ink cloud with guaranteed fade-out after 10 seconds"""
        ink_cloud_pixmap = QtGui.QPixmap(os.path.join("images", "inkcloud.png"))
        ink_cloud_item = QtWidgets.QGraphicsPixmapItem(ink_cloud_pixmap)
        
        # Set the center of the ink cloud to match the center of the squid
        squid_center_x = self.squid_x + self.squid_width // 2
        squid_center_y = self.squid_y + self.squid_height // 2
        ink_cloud_item.setPos(
            squid_center_x - ink_cloud_pixmap.width() // 2, 
            squid_center_y - ink_cloud_pixmap.height() // 2
        )
        
        self.ui.scene.addItem(ink_cloud_item)
        
        # Create a QGraphicsOpacityEffect without a parent
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        opacity_effect.setOpacity(1.0)  # Start fully visible
        ink_cloud_item.setGraphicsEffect(opacity_effect)

        # Create a QPropertyAnimation for the opacity effect
        fade_out_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        fade_out_animation.setDuration(10000)  # 10 seconds duration
        fade_out_animation.setStartValue(1.0)
        fade_out_animation.setEndValue(0.0)
        fade_out_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        # Connect the finished signal to remove the item
        fade_out_animation.finished.connect(lambda: self.remove_ink_cloud(ink_cloud_item))

        # Start the animation
        fade_out_animation.start()
        
        # Backup timer to force remove after 10 seconds in case animation fails
        QtCore.QTimer.singleShot(10000, lambda: self.force_remove_ink_cloud(ink_cloud_item))

    def force_remove_ink_cloud(self, ink_cloud_item):
        """Force remove the ink cloud if it still exists after timeout"""
        if ink_cloud_item in self.ui.scene.items():
            self.ui.scene.removeItem(ink_cloud_item)

    def remove_ink_cloud(self, ink_cloud_item):
        """Remove the ink cloud from the scene"""
        if ink_cloud_item in self.ui.scene.items():
            self.ui.scene.removeItem(ink_cloud_item)
        if ink_cloud_item.graphicsEffect():
            ink_cloud_item.graphicsEffect().deleteLater()
        ink_cloud_item.setGraphicsEffect(None)

    def remove_ink_cloud_safety(self):
        """Safety method to ensure ink cloud is removed"""
        if hasattr(self, '_current_ink_cloud') and self._current_ink_cloud:
            if self._current_ink_cloud in self.user_interface.scene.items():
                self.user_interface.scene.removeItem(self._current_ink_cloud)
            self._current_ink_cloud = None
            
        if hasattr(self, '_ink_cloud_timer') and self._ink_cloud_timer:
            self._ink_cloud_timer.stop()

    def end_startle(self):
        if self.mental_states_enabled:
            self.squid.mental_state_manager.set_state("startled", False)
            # Add thoughts
            self.brain_window.add_thought("No longer startled")

    def update_simulation(self):
        # Trigger pre-update hook
        self.plugin_manager.trigger_hook("pre_update", 
                                        tamagotchi_logic=self, 
                                        squid=self.squid)
        # 1. Handle existing simulation updates
        self.move_objects()
        self.animate_poops()
        self.update_statistics()

        # Add poop interaction check
        self.check_poop_interaction()
        
        if self.squid:
            # 2. Core squid updates
            self.squid.move_squid()
            self.check_for_decoration_attraction()
            self.check_for_sickness()
            
            # 3. Mental state updates
            if self.mental_states_enabled:
                self.check_for_startle()
                self.check_for_curiosity()
            
            # 4. Neurogenesis tracking
            self.track_neurogenesis_triggers()
            
            # 5. Memory management
            self.squid.memory_manager.periodic_memory_management()
            
            # 6. Prepare brain state with neurogenesis data
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
                "pursuing_food": self.squid.pursuing_food,
                "direction": self.squid.squid_direction,
                "position": (self.squid.squid_x, self.squid.squid_y),
                
                # Neurogenesis-specific additions
                "novelty_exposure": self.neurogenesis_triggers['novel_objects'],
                "sustained_stress": self.neurogenesis_triggers['high_stress_cycles'] / 10.0,
                "recent_rewards": self.neurogenesis_triggers['positive_outcomes'],
                "personality": self.squid.personality.value
            }
            
            # 7. Update brain (will trigger neurogenesis checks)
            self.brain_window.update_brain(brain_state)
            
            # 8. Reset frame-specific flags
            self.new_object_encountered = False
            self.recent_positive_outcome = False

        # 9. Handle RPS game state if active
        if hasattr(self, 'rps_game') and self.rps_game.game_window:
            self.rps_game.update_state()
            # Trigger post-update hook at the end
        self.plugin_manager.trigger_hook("post_update", 
                                        tamagotchi_logic=self, 
                                        squid=self.squid)

    def check_for_sickness(self):
        # Existing sickness logic
        if (self.cleanliness_threshold_time >= 10 * self.simulation_speed and self.cleanliness_threshold_time <= 60 * self.simulation_speed) or \
        (self.hunger_threshold_time >= 10 * self.simulation_speed and self.hunger_threshold_time <= 50 * self.simulation_speed):
            if random.random() < 0.8:
                self.squid.mental_state_manager.set_state("sick", True)
                
                # Set more descriptive sick status
                if self.squid.health < 30:
                    self.squid.status = "suffering"
                elif self.squid.health < 50:
                    self.squid.status = "feeling ill"
                else:
                    self.squid.status = "feeling sick"
                    
                self.show_message("Squid is feeling sick!")
        else:
            if self.squid.mental_state_manager.is_state_active("sick") and self.squid.health > 80:
                self.squid.status = "recuperating"
            self.squid.mental_state_manager.set_state("sick", False)
    
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

    def track_neurogenesis_triggers(self):
        """Update counters for neurogenesis triggers"""
        # Novelty tracking
        if self.new_object_encountered:
            self.neurogenesis_triggers['novel_objects'] = min(
                self.neurogenesis_triggers['novel_objects'] + 1,
                10  # Max cap
            )
            # Add thought about novelty
            self.add_thought("Encountered something new!")
        else:
            # Gradual decay when no novelty
            self.neurogenesis_triggers['novel_objects'] *= 0.95
        
        # Stress tracking
        if self.squid.anxiety > 70:
            self.neurogenesis_triggers['high_stress_cycles'] += 1
            # Add thought about stress if threshold crossed
            if self.neurogenesis_triggers['high_stress_cycles'] > 5:
                self.add_thought("Feeling stressed for a while...")
        else:
            self.neurogenesis_triggers['high_stress_cycles'] = max(
                0,
                self.neurogenesis_triggers['high_stress_cycles'] - 0.5
            )
        
        # Reward tracking (positive outcomes like eating, playing)
        if self.recent_positive_outcome:
            self.neurogenesis_triggers['positive_outcomes'] = min(
                self.neurogenesis_triggers['positive_outcomes'] + 1,
                5  # Max cap
            )
            # Add thought about positive experience
            if random.random() < 0.3:  # 30% chance to comment
                self.add_thought("That was enjoyable!")
        else:
            # Gradual decay when no rewards
            self.neurogenesis_triggers['positive_outcomes'] = max(
                0,
                self.neurogenesis_triggers['positive_outcomes'] - 0.2
            )
        
        # Debug output if in debug mode
        if self.debug_mode:
            print(f"Neurogenesis triggers: {self.neurogenesis_triggers}")

    def make_squid_curious(self):
        self.squid.mental_state_manager.set_state("curious", True)
        self.curious_cooldown = self.curious_cooldown_max
        
        # Use the new add_thought method
        self.add_thought("Experiencing extreme curiosity")
        
        # Increase curiosity
        self.squid.curiosity = min(100, self.squid.curiosity + 20)
        
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

        # Check if the squid should enter the curious state
        if self.squid.curiosity > 80 and self.mental_states_enabled:
            self.check_for_curiosity()

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

    def start_rps_game(self):
        self.rps_game = RPSGame(self)
        self.rps_game.start_game()

    def give_medicine(self):
        
        # Get plugin results
        results = self.plugin_manager.trigger_hook("on_medicine", 
                                                tamagotchi_logic=self, 
                                                squid=self.squid)
        
        # Check if any plugin returned False to prevent default behavior
        if False in results:
            return
        
        if (self.squid is not None and 
            (self.squid.is_sick or 
            self.squid.mental_state_manager.is_state_active('sick'))):
            
            print("Debug: Applying medicine effects")
            self.squid.is_sick = False
            self.squid.mental_state_manager.set_state("sick", False)
            
            self.squid.happiness = max(0, self.squid.happiness - 30)
            self.squid.sleepiness = min(100, self.squid.sleepiness + 50)
            
            self.show_message("Medicine given. Squid didn't like that!")
            
            # Add thoughts and set status
            if hasattr(self.brain_window, 'add_thought'):
                self.brain_window.add_thought("I am grumpy and anxious because I was forced to take medicine")
            
            self.squid.status = "taking medicine"
            
            # Hide the sick icon immediately
            self.squid.hide_sick_icon()

            # Put Squid to sleep
            QtCore.QTimer.singleShot(5000, lambda: self.delayed_sleep_after_medicine())

            # Display the needle image
            self.display_needle_image()
        else:
            self.show_message("Squid is not sick. Medicine not needed.")

    def delayed_sleep_after_medicine(self):
        """Put squid to sleep after a delay from taking medicine"""
        if self.squid:
            self.squid.go_to_sleep()
            self.squid.status = "recovering"

    def display_needle_image(self):
        needle_pixmap = QtGui.QPixmap(os.path.join("images", "needle.jpg"))
        self.needle_item = QtWidgets.QGraphicsPixmapItem(needle_pixmap)
        self.needle_item.setPos(self.user_interface.window_width // 2 - needle_pixmap.width() // 2,
                                self.user_interface.window_height // 2 - needle_pixmap.height() // 2)
        self.needle_item.setZValue(10)  # Ensure the needle image is displayed on top of everything
        self.user_interface.scene.addItem(self.needle_item)

        # Create a QGraphicsOpacityEffect
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        self.needle_item.setGraphicsEffect(opacity_effect)

        # Create a QPropertyAnimation for the opacity effect
        self.needle_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        self.needle_animation.setDuration(1000)  # 1 second duration
        self.needle_animation.setStartValue(1.0)
        self.needle_animation.setEndValue(0.0)
        self.needle_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        # Connect the finished signal to remove the item
        self.needle_animation.finished.connect(self.remove_needle_image)

        # Start the animation
        self.needle_animation.start()

    def remove_needle_image(self):
        if self.needle_item is not None:
            self.user_interface.scene.removeItem(self.needle_item)
            self.needle_item = None

    def move_foods(self):
        for food_item in self.food_items[:]:
            if getattr(food_item, 'is_sushi', False):
                self.move_sushi(food_item)
            else:
                self.move_cheese(food_item)

    def get_food_item_at(self, x, y):
        for food_item in self.food_items:
            if food_item.pos().x() == x and food_item.pos().y() == y:
                return food_item
        return None

    def move_cheese(self, cheese_item):
        cheese_x = cheese_item.pos().x()
        cheese_y = cheese_item.pos().y() + (self.base_food_speed * self.simulation_speed)

        if cheese_y > self.user_interface.window_height - 120 - self.food_height:
            cheese_y = self.user_interface.window_height - 120 - self.food_height

        cheese_item.setPos(cheese_x, cheese_y)

        # Directly check collision without redundant checks
        if self.squid and cheese_item.collidesWithItem(self.squid.squid_item):
            self.squid.eat(cheese_item)
            
            # Reset status after a short delay
            QtCore.QTimer.singleShot(2000, self.reset_squid_status)

    def move_sushi(self, sushi_item):
        sushi_x = sushi_item.pos().x()
        sushi_y = sushi_item.pos().y() + (self.base_food_speed * self.simulation_speed)

        if sushi_y > self.user_interface.window_height - 120 - self.food_height:
            sushi_y = self.user_interface.window_height - 120 - self.food_height

        sushi_item.setPos(sushi_x, sushi_y)

        if self.squid is not None and sushi_item.collidesWithItem(self.squid.squid_item):
            self.squid.eat(sushi_item)  # Pass the sushi_item as an argument
            self.remove_food(sushi_item)

    def is_sushi(self, food_item):
        return getattr(food_item, 'is_sushi', False)     

    def remove_food(self, food_item):
        if food_item in self.food_items:
            self.user_interface.scene.removeItem(food_item)
            self.food_items.remove(food_item)

    def move_poops(self):
        for poop_item in self.poop_items[:]:
            poop_x = poop_item.pos().x()
            poop_y = poop_item.pos().y() + (self.base_food_speed * self.simulation_speed)

            if poop_y > self.user_interface.window_height - 120 - self.squid.poop_height:
                poop_y = self.user_interface.window_height - 120 - self.squid.poop_height

            poop_item.setPos(poop_x, poop_y)

    def update_statistics(self):
        self.statistics_window.update_statistics()
        self.update_cleanliness_overlay()

        if self.squid is not None:
            # Update squid needs
            if not self.squid.is_sleeping:
                self.squid.hunger = min(100, self.squid.hunger + (0.1 * self.simulation_speed))
                self.squid.sleepiness = min(100, self.squid.sleepiness + (0.1 * self.simulation_speed))
                self.squid.happiness = max(0, self.squid.happiness - (0.1 * self.simulation_speed))
                self.squid.cleanliness = max(0, self.squid.cleanliness - (0.1 * self.simulation_speed))

                # Update new neurons
                self.update_satisfaction()
                self.update_anxiety()
                self.update_curiosity()

                # --- NEWLY ADDED ---
                # Check for special status effects on anxiety reduction.
                if self.squid.status == "hiding behind plant":
                    # Hiding among plants actively reduces anxiety over time.
                    # This makes it a tangible calming behavior for the squid.
                    previous_anxiety = self.squid.anxiety
                    self.squid.anxiety = max(0, self.squid.anxiety - (0.5 * self.simulation_speed))
                    
                    if self.squid.anxiety < previous_anxiety:
                        # Form a memory of the calming effect
                        memory_value = "Being near plants is calming (Anxiety reduction)"
                        self.squid.memory_manager.add_short_term_memory(
                            'environment', 
                            'plant_calming_effect', 
                            memory_value,
                            importance=1.5  # Higher importance
                        )

                        # Increment counter and check for long-term memory transfer
                        self.plant_calming_effect_counter += 1
                        if self.plant_calming_effect_counter >= 5:
                            self.squid.memory_manager.transfer_to_long_term_memory(
                                'environment', 
                                'plant_calming_effect'
                            )
                            self.plant_calming_effect_counter = 0 # Reset counter

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

                # Check if squid becomes sick (80% chance)
                if (self.cleanliness_threshold_time >= 10 * self.simulation_speed and self.cleanliness_threshold_time <= 60 * self.simulation_speed) or \
                (self.hunger_threshold_time >= 10 * self.simulation_speed and self.hunger_threshold_time <= 50 * self.simulation_speed):
                    if random.random() < 0.8:
                        self.squid.mental_state_manager.set_state("sick", True)
                else:
                    self.squid.mental_state_manager.set_state("sick", False)

                # New logic for health decrease based on happiness and cleanliness
                if self.squid.happiness < 20 and self.squid.cleanliness < 20:
                    health_decrease = 0.2 * self.simulation_speed  # Rapid decrease
                else:
                    health_decrease = 0.1 * self.simulation_speed  # Normal decrease when sick

                # Store previous health for change detection
                previous_health = self.squid.health

                if self.squid.is_sick:
                    self.squid.health = max(0, self.squid.health - health_decrease)
                    self.squid.show_sick_icon()
                    if self.squid.health == 0:
                        self.game_over()
                else:
                    self.squid.health = min(100, self.squid.health + (0.1 * self.simulation_speed))
                    self.squid.hide_sick_icon()
                
                # Track health history
                if not hasattr(self, '_health_history'):
                    self._health_history = []
                
                # Add current health data point with timestamp
                # Only record if health actually changed or if we haven't recorded in a while
                if (previous_health != self.squid.health or 
                    not self._health_history or 
                    time.time() - self._health_history[-1][0] > 60):  # Record at least every 60 seconds
                    self._health_history.append((time.time(), self.squid.health))
                    
                    # Limit history size to prevent memory issues
                    if len(self._health_history) > 1000:
                        self._health_history = self._health_history[-1000:]

                # Check if squid should go to sleep
                if self.squid.sleepiness >= 100:
                    self.squid.go_to_sleep()
                    self.show_message("Squid is very tired and went to sleep!")
                    # Add thoughts
                    self.brain_window.add_thought("I am exhausted and going to sleep")
            else:
                self.squid.sleepiness = max(0, self.squid.sleepiness - (0.5 * self.simulation_speed))
                if self.squid.sleepiness == 0:
                    self.squid.wake_up()

            # Update points based on squid's status
            if not self.squid.is_sick and self.squid.happiness >= 80 and self.squid.cleanliness >= 80:
                self.points += 1
            elif self.squid.is_sick or self.squid.hunger >= 80 or self.squid.happiness <= 20:
                self.points = max(0, self.points - 1)

            self.user_interface.update_points(self.points)

    def handle_window_resize(self, event):
        new_width = event.size().width()
        new_height = event.size().height()
        
        # Get current dimensions from user interface
        current_width = self.user_interface.window_width
        current_height = self.user_interface.window_height
        
        # Calculate size change
        width_change = new_width - current_width
        height_change = new_height - current_height
        
        # Update window dimensions in UI
        self.user_interface.window_width = new_width
        self.user_interface.window_height = new_height
        
        # Update UI elements through user interface
        self.user_interface.handle_window_resize(event)
        
        # Notify logic about resize with size change info
        self.handle_window_resize_event(
            width_change, 
            height_change,
            (new_width, new_height)
        )

    def allow_initial_startle(self):
        """Allow the squid to be startled after the initial delay."""
        self.initial_startle_allowed = True
        self.is_first_instance = False  # Reset the flag after the first instance
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
            self.startle_squid(source="major_resize")
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

    def feed_squid(self):
        # Get plugin results
        results = self.plugin_manager.trigger_hook("on_feed", 
                                                tamagotchi_logic=self, 
                                                squid=self.squid)
        
        # Check if any plugin returned False to prevent default behavior
        if False in results:
            return
        
        # Continue with original behavior
        if len(self.food_items) >= self.max_food:
            return
        
        # Only create one food item
        is_sushi = random.random() < 0.5
        self.spawn_food(is_sushi=is_sushi)

    def spawn_food(self, is_sushi=False):
        if len(self.food_items) >= self.max_food:
            return
        
        # Create only one food item
        if is_sushi:
            food_pixmap = QtGui.QPixmap(os.path.join("images", "sushi.png"))
            food_item = QtWidgets.QGraphicsPixmapItem(food_pixmap)
            food_item.is_sushi = True
        else:
            food_pixmap = QtGui.QPixmap(os.path.join("images", "cheese.png"))
            food_item = QtWidgets.QGraphicsPixmapItem(food_pixmap)
            food_item.is_sushi = False

        food_x = random.randint(50, self.user_interface.window_width - 50 - self.food_width)
        food_item.setPos(food_x, 50)
        
        # Add to scene and tracking list
        self.user_interface.scene.addItem(food_item)
        self.food_items.append(food_item)  # Single addition

    def clean_environment(self):
        current_time = time.time()
        if current_time - self.last_clean_time < self.clean_cooldown:
            remaining_cooldown = int(self.clean_cooldown - (current_time - self.last_clean_time))
            self.show_message(f"Cleaning is on cooldown. Please wait {remaining_cooldown} seconds.")
            return

        # Get plugin results
        results = self.plugin_manager.trigger_hook("on_clean",
                                                tamagotchi_logic=self,
                                                squid=self.squid)

        # Check if any plugin returned False to prevent default behavior
        if False in results:
            return

        self.last_clean_time = current_time

        # Create a cleaning line that extends beyond the window vertically
        self.cleaning_line = QtWidgets.QGraphicsLineItem(self.user_interface.window_width, -500,
                                                        self.user_interface.window_width, self.user_interface.window_height + 500)
        self.cleaning_line.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 15))  # Thick black line
        self.user_interface.scene.addItem(self.cleaning_line)

        # Show a message that cleaning has started
        self.show_message("Cleaning in progress...")

        # Set up animation parameters
        self.cleaning_progress = 0
        self.movement_rate = 200  # Movement rate in pixels per second
        self.cleaning_timer = QtCore.QTimer()
        self.cleaning_timer.timeout.connect(self.update_cleaning)
        self.cleaning_timer.start(500)  # Update every 1000 ms (1 second)

    def update_cleaning(self):
        self.cleaning_progress += self.movement_rate  # Increment progress by movement rate each second
        if self.cleaning_progress >= self.user_interface.window_width:
            self.cleaning_timer.stop()
            self.finish_cleaning()
            return

        new_x = self.user_interface.window_width - self.cleaning_progress
        self.cleaning_line.setLine(new_x, -500, new_x, self.user_interface.window_height + 500)

        # Remove poops and food that the line has passed
        for poop_item in self.poop_items[:]:
            if poop_item.pos().x() > new_x:
                self.user_interface.scene.removeItem(poop_item)
                self.poop_items.remove(poop_item)

        for food_item in self.food_items[:]:
            if food_item.pos().x() > new_x:
                self.remove_food(food_item)

        # Force an update of the scene
        self.user_interface.scene.update()



    def finish_cleaning(self):
        # Remove the cleaning line
        self.user_interface.scene.removeItem(self.cleaning_line)

        # Update squid stats if Squid object is available
        if self.squid is not None:
            self.squid.cleanliness = 100
            self.squid.happiness = min(100, self.squid.happiness + 20)

        # Show a message
        self.show_message("Environment cleaned! Squid is happier!")
        # Add thoughts
        self.brain_window.add_thought("I am pleased that the tank was cleaned")

        # Force an update of the scene
        self.user_interface.scene.update()

    def show_message(self, message):
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
            message_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            message_item.setPos(0, self.user_interface.window_height - 75)  # Position the message higher
            message_item.setTextWidth(self.user_interface.window_width)
            message_item.setHtml(f'<div style="text-align: center; background-color: #000000; padding: 5px;">{message}</div>')
            message_item.setZValue(10)  # Ensure the message is on top
            message_item.setOpacity(1)

            # Add the new message item to the scene
            scene.addItem(message_item)

            # Fade out the message after 8 seconds
            fade_out_animation = QtCore.QPropertyAnimation(message_item, b"opacity")
            fade_out_animation.setDuration(8000)
            fade_out_animation.setStartValue(1.0)
            fade_out_animation.setEndValue(0.0)
            fade_out_animation.finished.connect(lambda: scene.removeItem(message_item))
            fade_out_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

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

    def update_cleanliness_overlay(self):
        if self.squid is not None:
            cleanliness = self.squid.cleanliness
            if cleanliness < 15:
                opacity = 200
            elif cleanliness < 50:
                opacity = 100
            else:
                opacity = 0
            self.user_interface.cleanliness_overlay.setBrush(QtGui.QBrush(QtGui.QColor(139, 69, 19, opacity)))
    
    def spawn_sushi(self):
        if len(self.food_items) < self.max_food:
            sushi_pixmap = QtGui.QPixmap(os.path.join("images", "sushi.png"))
            sushi_pixmap = sushi_pixmap.scaled(self.food_width, self.food_height)

            sushi_item = QtWidgets.QGraphicsPixmapItem(sushi_pixmap)

            sushi_x = random.randint(50, self.user_interface.window_width - 50 - self.food_width)
            sushi_y = 50  # Start at the top of the screen
            sushi_item.setPos(sushi_x, sushi_y)

            self.user_interface.scene.addItem(sushi_item)
            sushi_item = QtWidgets.QGraphicsPixmapItem(sushi_pixmap)
            sushi_item.is_sushi = True
            self.food_items.append(sushi_item)

    def spawn_poop(self, x, y):
        if len(self.poop_items) < self.max_poop and self.squid is not None:
            poop_item = ResizablePixmapItem(self.squid.poop_images[0], category='poop')
            poop_item.setPos(x - self.squid.poop_width // 2, y)
            self.user_interface.scene.addItem(poop_item)
            self.poop_items.append(poop_item)

    def animate_poops(self):
        if self.squid is not None:
            for poop_item in self.poop_items:
                current_frame = self.poop_items.index(poop_item) % 2
                poop_item.setPixmap(self.squid.poop_images[current_frame])

    def game_over(self):
        game_over_dialog = QtWidgets.QMessageBox()
        game_over_dialog.setIcon(QtWidgets.QMessageBox.Critical)
        game_over_dialog.setText("Game Over")
        game_over_dialog.setInformativeText("Your squid has died due to poor health.")
        game_over_dialog.setWindowTitle("Game Over")
        game_over_dialog.exec_()
        self.user_interface.window.close()

        # Add any additional game over logic or cleanup here
        print("Game Over - Squid died due to poor health")

        # Save the game state before resetting
        self.save_game()

        # Reset the game state
        self.reset_game()

    def reset_game(self):
        # Reset squid attributes
        self.squid.hunger = 25
        self.squid.sleepiness = 30
        self.squid.happiness = 100
        self.squid.cleanliness = 100
        self.squid.is_sleeping = False
        self.squid.health = 100
        self.squid.is_sick = False

        # Reset new neurons
        self.squid.satisfaction = 50
        self.squid.anxiety = 10
        self.squid.curiosity = 70

        # Reset game variables
        self.cleanliness_threshold_time = 0
        self.hunger_threshold_time = 0
        self.last_clean_time = 0

        # Clear food and poop items
        for food_item in self.food_items:
            self.user_interface.scene.removeItem(food_item)
        self.food_items.clear()

        for poop_item in self.poop_items:
            self.user_interface.scene.removeItem(poop_item)
        self.poop_items.clear()

        # Reset squid position
        self.squid.squid_x = self.squid.center_x
        self.squid.squid_y = self.squid.center_y
        self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)

        # Show a message
        self.show_message("Game reset. Take better care of your squid!")

        # Force an update of the scene
        self.user_interface.scene.update()

        # Save the game state after resetting
        self.save_game()

    def load_game(self):
        save_data = self.save_manager.load_game()
        
        if save_data is not None:
            game_state = save_data['game_state']
            squid_data = game_state['squid']
            self.squid.load_state(squid_data)

            # Load brain state
            self.brain_window.set_brain_state(save_data['brain_state'])

            # Load memories - first try from save_data
            if 'ShortTerm' in save_data and save_data['ShortTerm']:
                self.squid.memory_manager.short_term_memory = save_data['ShortTerm']
            if 'LongTerm' in save_data and save_data['LongTerm']:
                self.squid.memory_manager.long_term_memory = save_data['LongTerm']

            # If empty or not in save_data, try loading from extracted files
            if not self.squid.memory_manager.short_term_memory:
                self.squid.memory_manager.short_term_memory = self.squid.memory_manager.load_memory(
                    self.squid.memory_manager.short_term_file) or []
            if not self.squid.memory_manager.long_term_memory:
                self.squid.memory_manager.long_term_memory = self.squid.memory_manager.load_memory(
                    self.squid.memory_manager.long_term_file) or []

            # Make sure they are lists
            if not isinstance(self.squid.memory_manager.short_term_memory, list):
                self.squid.memory_manager.short_term_memory = []
            if not isinstance(self.squid.memory_manager.long_term_memory, list):
                self.squid.memory_manager.long_term_memory = []

            # Save loaded memories to disk to ensure consistency
            self.squid.memory_manager.save_memory(self.squid.memory_manager.short_term_memory, 
                                                self.squid.memory_manager.short_term_file)
            self.squid.memory_manager.save_memory(self.squid.memory_manager.long_term_memory, 
                                                self.squid.memory_manager.long_term_file)

            print(f"\033[33;1m >>Loaded personality: {self.squid.personality.value}\033[0m")

            # Load decoration data - ensure this runs for both manual loads and autosaves
            decorations_data = game_state.get('decorations', [])
            if decorations_data:
                print(f"Loading {len(decorations_data)} decorations")
                # Clear existing decorations first to avoid duplicates
                for item in list(self.user_interface.scene.items()):
                    if hasattr(item, 'category') and item.category in ['rock', 'plant', 'decoration']:
                        self.user_interface.scene.removeItem(item)
                # Now load the decorations
                self.user_interface.load_decorations_data(decorations_data)
            else:
                print("No decorations found in save data")

            # Load TamagotchiLogic data
            tamagotchi_logic_data = game_state['tamagotchi_logic']
            self.cleanliness_threshold_time = tamagotchi_logic_data['cleanliness_threshold_time']
            self.hunger_threshold_time = tamagotchi_logic_data['hunger_threshold_time']
            self.last_clean_time = tamagotchi_logic_data['last_clean_time']
            self.points = tamagotchi_logic_data['points']
            
            # Load plugin data if it exists
            if 'plugin_data' in save_data:
                plugin_data = save_data['plugin_data']
                self.plugin_manager.trigger_hook("on_load_game", 
                                                tamagotchi_logic=self,
                                                squid=self.squid,
                                                plugin_data=plugin_data)

            # Refresh memory tab if it exists
            if hasattr(self.brain_window, 'memory_tab'):
                QtCore.QTimer.singleShot(1000, self.brain_window.memory_tab.update_memory_display)

            # Ensure the brain window is shown after loading
            if self.brain_window:
                self.brain_window.show()
                self.brain_window.raise_()  # Brings the window to the front

            print("Game loaded successfully")
            self.set_simulation_speed(1)  # Set simulation speed to 1x after loading
        else:
            print("No save data found")

    def update_score(self):
        if self.squid is not None:
            if not self.squid.is_sick and self.squid.happiness >= 80 and self.squid.cleanliness >= 80:
                self.points += 1
            elif self.squid.is_sick or self.squid.hunger >= 80 or self.squid.happiness <= 20:
                self.points -= 1

            self.user_interface.update_points(self.points)


    def update_squid_brain(self):
        if self.squid and self.brain_window.isVisible():
            is_startled_state = False
            # Check if mental_state_manager exists and the "startled" state is active
            if hasattr(self.squid, 'mental_state_manager') and self.squid.mental_state_manager:
                is_startled_state = self.squid.mental_state_manager.is_state_active('startled')
            # Fallback: Check squid status if mental_state_manager is not present or doesn't have the state
            elif hasattr(self.squid, 'status') and self.squid.status:
                 is_startled_state = ("startled" in self.squid.status.lower())


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
                "is_startled": is_startled_state,  # Updated logic for is_startled
                "direction": self.squid.squid_direction,
                "position": (self.squid.squid_x, self.squid.squid_y),
                "personality": self.squid.personality.value
            }

            self.brain_window.update_brain(brain_state)

    def save_game(self, squid, tamagotchi_logic, is_autosave=False):
        try:
            # Trigger save game hook to allow plugins to add data
            plugin_data = {}
            hook_results = self.plugin_manager.trigger_hook("on_save_game", 
                                                        tamagotchi_logic=self,
                                                        squid=self.squid)
            
            # Collect plugin data from results
            for result in hook_results:
                if isinstance(result, dict):
                    for plugin_name, data in result.items():
                        plugin_data[plugin_name] = data
            
            brain_state = self.brain_window.get_brain_state()
            print("Debug: Brain State")
            # print(json.dumps(brain_state, indent=2))
            
            save_data = {
                'game_state': {
                    'squid': {
                        'hunger': squid.hunger,
                        'sleepiness': squid.sleepiness,
                        'happiness': squid.happiness,
                        'cleanliness': squid.cleanliness,
                        'health': squid.health,
                        'is_sick': squid.is_sick,
                        'squid_x': squid.squid_x,
                        'squid_y': squid.squid_y,
                        'satisfaction': squid.satisfaction,
                        'anxiety': squid.anxiety,
                        'curiosity': squid.curiosity,
                        'personality': squid.personality.value
                    },
                    'tamagotchi_logic': {
                        'cleanliness_threshold_time': self.cleanliness_threshold_time,
                        'hunger_threshold_time': self.hunger_threshold_time,
                        'last_clean_time': self.last_clean_time,
                        'points': self.points
                    },
                    'decorations': [
                        {
                            'pixmap_data': self.user_interface.get_pixmap_data(item),
                            'pos': [item.pos().x(), item.pos().y()],
                            'scale': item.scale(),
                            'filename': item.filename
                        }
                        for item in self.user_interface.scene.items()
                        if isinstance(item, ResizablePixmapItem)
                    ]
                },
                'brain_state': brain_state,
                'ShortTerm': squid.memory_manager.short_term_memory,
                'LongTerm': squid.memory_manager.long_term_memory,
                'plugin_data': plugin_data
            }

            #print("Debug: Short Term Memory")
            #print(json.dumps(save_data['ShortTerm'], indent=2))
            #print("Debug: Long Term Memory")
            #print(json.dumps(save_data['LongTerm'], indent=2))

            filepath = self.save_manager.save_game(save_data, is_autosave)
            print(f"Game {'autosaved' if is_autosave else 'saved'} successfully to {filepath}")
        except Exception as e:
            print(f"Error during save: {str(e)}")
            import traceback
            traceback.print_exc()

    def start_autosave(self):
        self.autosave_timer.start(300000)  # 300000 ms = 5 minutes

    def autosave(self):
        print("Autosaving...")
        self.save_game(self.squid, self, is_autosave=True)

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
                direction = "left" if random.random() < 0.5 else "right"
                if self.squid.throw_rock(direction):
                    self.squid.status = "roaming"
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
        from .interactions2 import PoopInteractionManager
        
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
        
        if not hasattr(self.squid, 'current_poop_target'):
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
