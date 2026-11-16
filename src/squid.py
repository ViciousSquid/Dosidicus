import logging

_LOG = logging.getLogger(__name__)

import random
import uuid
import time
import math
from typing import List, Optional, Tuple
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_about_tab import SQUID_NAMES
from .mental_states import MentalStateManager
from .memory_manager import MemoryManager
from .personality import Personality
from .squid_statistics import SquidStatistics
from .lifecycle import Lifecycle
from .vision_worker import (
    VisionWorker, 
    VisionResult, 
    SceneObject
)
from .squid_vision import SquidVisionMixin
from .squid_sprites import SquidSpriteMixin
from .squid_movement import SquidMovementMixin
from .squid_objects import SquidObjectsMixin


class Squid(
        SquidVisionMixin,
        SquidSpriteMixin,
        SquidMovementMixin,
        SquidObjectsMixin,
):

    def __init__(self, user_interface, tamagotchi_logic=None, personality=None, neuro_cooldown=None):
        self.ui = user_interface
        self.tamagotchi_logic = tamagotchi_logic
        self.memory_manager = MemoryManager()
        self.push_animation = None
        self.startled_icon = None
        self.startled_icon_offset = QtCore.QPointF(0, -100)
        self.ng_icon = None
        self.ng_icon_offset = QtCore.QPointF(0, -100)
        self.tint_color = None
        self.lineage = None        # parents and inherited synapses, for a hatchling
        self.name = random.choice(SQUID_NAMES)
        self.statistics = SquidStatistics(self)
        # Whether this squid has reproduced, is starving for it, or has died.
        # Every squid is born living; see src/lifecycle.py.
        self._lifecycle = Lifecycle()

        # Set neurogenesis cooldown (default to 180 seconds if not specified)
        self.neuro_cooldown = neuro_cooldown if neuro_cooldown is not None else 180

        # Rock interaction system
        self.carrying_rock = False
        self.current_rock = None  # Currently held rock
        self.rock_being_thrown = None  # Rock in mid-flight

        # Hoarding preferences
        self.hoard_corner = {
            Personality.GREEDY: (50, 50),          # Top-left
            Personality.STUBBORN: (self.ui.window_width-100, 50)  # Top-right
        }

        # Rock physics properties
        self.rock_velocity_x = 0
        self.rock_velocity_y = 0
        self.rock_throw_power = 10  # Base throw strength
        self.rock_throw_cooldown = 0

        # Startle transition tracking
        self.startled_transition = False
        self.startled_transition_frames = 0

        # Multiplayer-specific
        self.can_move = True           # Whether the squid can move (disable when away)
        self.is_transitioning = False  # Whether the squid is currently in transit

        # Rock Interactions
        self.rock_interaction_timer = QtCore.QTimer()
        self.rock_interaction_timer.timeout.connect(self.check_rock_interaction)
        self.rock_interaction_timer.start(1000)  # Check every second
        self.rock_hold_start_time = 0
        self.rock_hold_duration = 0
        self.rock_decision_made = False
        self.rock_animation_timer = QtCore.QTimer()
        self.rock_animation_timer.timeout.connect(self.update_rock_throw)

        self.load_images()
        self.load_poop_images()
        self.initialize_attributes()

        self.mental_state_manager = MentalStateManager(self, self.ui.scene)

        self.squid_item = QtWidgets.QGraphicsPixmapItem(self.current_image())
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.squid_item.setAcceptHoverEvents(True)  # Enable hover events
        self.squid_item.mousePressEvent = self.handle_squid_click  # Add click handler
        self.ui.scene.addItem(self.squid_item)
        self.anxiety_cooldown_timer = None
        self.ui.window.resizeEvent = self.handle_window_resize

        self.view_cone_item = None
        self.base_speed = 90  # Normal movement speed
        self.current_speed = self.base_speed

        # Neural drive: the brain's channel into movement. Output bindings set
        # this via set_neural_drive(); move_squid() consults it before falling
        # back to its own food/random logic. Without it, movement outputs like
        # seek_food and approach_rock wrote fields that move_squid overwrote on
        # the very next tick, so they could never affect behaviour.
        self.neural_drive = None
        self.is_fleeing = False
        self.view_cone_visible = False
        self.poop_timer = None
        self.animation_speed = 1
        self.base_move_interval = 1000  # 1 second
        self.health = 100
        self.is_sick = False
        self.sick_icon_item = None
        self.sick_icon_offset = QtCore.QPointF(0, -100)  # Offset the sick icon above the squid

        self.status = "roaming"  # Initialize status

        self.view_cone_angle = math.pi / 2.5  # Squid has a view cone of 80 degrees
        self.current_view_angle = random.uniform(0, 2 * math.pi)
        self.view_cone_change_interval = 2000  # milliseconds
        self.last_view_cone_change = 0
        self.pursuing_food = False
        self.target_food = None

        # View cone periodic scanning
        self.view_cone_timer = QtCore.QTimer()
        self.view_cone_timer.timeout.connect(self.update_view_direction)
        self.view_cone_timer.start(1000)  # Every 1 second

        # Goal neurons
        self.satisfaction = 50
        self.anxiety = 0
        self.curiosity = 50

         # ===== VISION WORKER SETUP =====
        # Background thread for vision calculations
        self._vision_worker = VisionWorker()
        self._vision_worker.food_visibility_changed.connect(self._on_food_visibility_changed)
        self._vision_worker.visibility_update.connect(self._on_visibility_update)
        self._vision_worker.start()
        
        # Cached vision results
        self._cached_vision: Optional[VisionResult] = None
        self._cached_visible_food: List[Tuple[float, float]] = []
        self._cached_can_see_food: bool = False
        self._cached_can_see_plant: bool = False
        
        # Vision update timer - updates worker with squid state
        self._vision_update_timer = QtCore.QTimer()
        self._vision_update_timer.timeout.connect(self._update_vision_worker)
        self._vision_update_timer.start(50)  # 20 Hz updates
        
        # Scene object cache for vision worker
        self._scene_objects_dirty = True
        self._cached_scene_objects: List[SceneObject] = []
        

        if personality is None:
            self.personality = random.choice(list(Personality))
        else:
            self.personality = personality
            
        self.uuid = uuid.uuid4()

    @property
    def lifecycle(self) -> Lifecycle:
        """Created on first use too, for a squid built without __init__."""
        lifecycle = self.__dict__.get('_lifecycle')
        if lifecycle is None:
            lifecycle = self._lifecycle = Lifecycle()
        return lifecycle

    @lifecycle.setter
    def lifecycle(self, value: Lifecycle):
        self._lifecycle = value

    @property
    def carrying_rock(self):
        return hasattr(self, 'is_carrying_rock') and self.is_carrying_rock
    
    @carrying_rock.setter
    def carrying_rock(self, value):
        self.is_carrying_rock = value
    
    @property
    def carrying_poop(self):
        """Mirrors carrying_rock. PoopInteractionManager sets is_carrying_poop
        and reads carrying_poop, but the property was never defined - so its
        hasattr() guards always failed and check_poop_hold_time()/drop_poop()
        could never run. DecisionEngine also reads it directly.
        """
        return getattr(self, 'is_carrying_poop', False)

    @carrying_poop.setter
    def carrying_poop(self, value):
        self.is_carrying_poop = value

    @property 
    def current_rock(self):
        return getattr(self, 'carried_rock', None)
    
    @current_rock.setter
    def current_rock(self, value):
        self.carried_rock = value

    @property
    def hunger(self):
        return self._hunger

    @hunger.setter
    def hunger(self, value):
        old_value = getattr(self, '_hunger', 50)
        self._hunger = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._hunger and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_hunger_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._hunger
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="hunger",
                    old_value=old_value,
                    new_value=self._hunger
                )

    @property
    def happiness(self):
        return self._happiness

    @happiness.setter
    def happiness(self, value):
        old_value = getattr(self, '_happiness', 100)
        self._happiness = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._happiness and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_happiness_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._happiness
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="happiness",
                    old_value=old_value,
                    new_value=self._happiness
                )

    @property
    def cleanliness(self):
        return self._cleanliness

    @cleanliness.setter
    def cleanliness(self, value):
        old_value = getattr(self, '_cleanliness', 100)
        self._cleanliness = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._cleanliness and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_cleanliness_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._cleanliness
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="cleanliness",
                    old_value=old_value,
                    new_value=self._cleanliness
                )

    @property
    def sleepiness(self):
        return self._sleepiness

    @sleepiness.setter
    def sleepiness(self, value):
        old_value = getattr(self, '_sleepiness', 30)
        self._sleepiness = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._sleepiness and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_sleepiness_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._sleepiness
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="sleepiness",
                    old_value=old_value,
                    new_value=self._sleepiness
                )

    @property
    def satisfaction(self):
        return self._satisfaction

    @satisfaction.setter
    def satisfaction(self, value):
        old_value = getattr(self, '_satisfaction', 50)
        self._satisfaction = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._satisfaction and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_satisfaction_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._satisfaction
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="satisfaction",
                    old_value=old_value,
                    new_value=self._satisfaction
                )

    @property
    def anxiety(self):
        return self._anxiety

    @anxiety.setter
    def anxiety(self, value):
        old_value = getattr(self, '_anxiety', 10)
        self._anxiety = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._anxiety and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_anxiety_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._anxiety
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="anxiety",
                    old_value=old_value,
                    new_value=self._anxiety
                )

    @property
    def curiosity(self):
        return self._curiosity

    @curiosity.setter
    def curiosity(self, value):
        old_value = getattr(self, '_curiosity', 50)
        self._curiosity = max(0, min(100, value))
        
        # Trigger hook if value changed and tamagotchi_logic exists
        if old_value != self._curiosity and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_curiosity_change", 
                    squid=self, 
                    old_value=old_value, 
                    new_value=self._curiosity
                )
                
                # General state change hook
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_squid_state_change",
                    squid=self,
                    attribute="curiosity",
                    old_value=old_value,
                    new_value=self._curiosity
                )

    def initialize_attributes(self):
        self.base_squid_speed = 90  # pixels per update at 1x speed
        self.base_vertical_speed = self.base_squid_speed // 2
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        self.squid_x = self.center_x
        self.squid_y = self.center_y
        self.squid_direction = "left"
        self.current_frame = 0
        self.update_preferred_vertical_range()

        self.hunger = 25
        self.sleepiness = 30
        self.happiness = 100
        self.cleanliness = 100
        self.is_sleeping = False

        self.health = 100
        self.is_sick = False

    def update_preferred_vertical_range(self):
        self.preferred_vertical_range = (self.ui.window_height // 4, self.ui.window_height // 4 * 3)

    def handle_window_resize(self, event):
        self.ui.window_width = event.size().width()
        self.ui.window_height = event.size().height()
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        self.update_preferred_vertical_range()
        self.squid_x = max(50, min(self.squid_x, self.ui.window_width - 50 - self.squid_width))
        self.squid_y = max(50, min(self.squid_y, self.ui.window_height - 120 - self.squid_height))
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()
        self.update_head_icon_positions()

    def update_needs(self):
        # This method was moved to TamagotchiLogic 26/07/2024
        pass

    def make_decision(self):
        """Delegate to the decision engine for emergent behavior"""
        if not hasattr(self, '_decision_engine'):
            from .decision_engine import DecisionEngine
            self._decision_engine = DecisionEngine(self)
        
        return self._decision_engine.make_decision()
    
    def handle_squid_click(self, event):
        """Handle mouse click on the squid"""
        if self.is_sleeping:
            self.startle_awake()
        event.accept()

    def startle_awake(self):
        """Startle the squid awake with an anxiety spike"""
        if not self.is_sleeping:
            return

        # Wake up the squid
        self.is_sleeping = False
        if hasattr(self.tamagotchi_logic, 'track_startle'):
            self.tamagotchi_logic.track_startle()

        # self.sleepiness = 0  # Waking up this way doesn't remove all tiredness
        self.happiness = max(0, self.happiness - 25)  # Increased happiness decrease
        self.anxiety = min(100, self.anxiety + 60)    # Increased anxiety spike
        self.statistics_window.award(-100)

        # Visual feedback
        self.show_startled_icon()  # Show the startled icon
        self.tamagotchi_logic.show_message("Squid was rudely startled awake!")
        self.status = "startled"

        # Instead of immediately changing direction, set a transitional state
        self.startled_transition = True
        self.startled_transition_frames = 5  # Show startled animation for 5 frames

        if random.random() < 0.25:
            self.tamagotchi_logic.create_ink_cloud()          # spawns the cloud
            self.current_speed = self.base_speed * 2          # double speed
            self.status = "fleeing from ink cloud"

            # create the requested memory
            self.memory_manager.add_short_term_memory(
                'behaviour', 'ink_cloud', 'Ink Cloud!'
            )

            # return to normal speed after 5 s
            QtCore.QTimer.singleShot(5000, self.end_ink_flee)

        # Start timers
        self.anxiety_cooldown_timer = QtCore.QTimer()
        self.anxiety_cooldown_timer.timeout.connect(self.reduce_startle_anxiety)
        self.anxiety_cooldown_timer.start(5000)  # Reduce anxiety after 5 seconds

        # Hide startled icon after 2 seconds
        QtCore.QTimer.singleShot(2000, self.hide_startled_icon)

        # End transition after a short delay (about half a second)
        QtCore.QTimer.singleShot(500, self.end_startled_transition)

    def end_ink_flee(self):
        """Called 5 s after an ink-cloud flee starts."""
        self.current_speed = self.base_speed
        # fall back to a sensible status
        if self.anxiety > 60:
            self.status = "nervous"
        else:
            self.status = "roaming"

    def end_startled_transition(self):
        """End the startled transition and set a natural direction"""
        self.startled_transition = False
        # Choose a random direction that makes sense for waking up
        self.squid_direction = random.choice(["left", "right"])
        self.update_squid_image()

    def reduce_startle_anxiety(self):
        """Gradually reduce the startle anxiety"""
        self.anxiety = max(20, self.anxiety - 15)  # Reduce anxiety but don't go below a higher baseline

        if self.anxiety <= 35:  # When back to near-normal levels
            if hasattr(self, 'anxiety_cooldown_timer'):
                self.anxiety_cooldown_timer.stop()
            self.tamagotchi_logic.show_message("Squid has calmed down... mostly.")
    
    def _get_squid_color(self):
        """Generate a persistent color for this squid"""
        if not hasattr(self, '_squid_color'):
            # Create stable color generation based on node_id
            import hashlib
            
            # Try multiple fallback methods for generating a unique source
            try:
                # First try network node
                if hasattr(self.tamagotchi_logic, 'network_node') and self.tamagotchi_logic.network_node:
                    node_id_source = self.tamagotchi_logic.network_node.node_id
                # Next try direct node_id attribute
                elif hasattr(self.tamagotchi_logic, 'node_id'):
                    node_id_source = self.tamagotchi_logic.node_id
                # Final fallback is current timestamp
                else:
                    node_id_source = str(time.time())
            except Exception:
                # Ultimate fallback
                node_id_source = str(time.time())
            
            # Generate color from hash
            hash_val = hashlib.md5(node_id_source.encode()).hexdigest()
            
            r = int(hash_val[:2], 16)
            g = int(hash_val[2:4], 16)
            b = int(hash_val[4:6], 16)
            
            # Ensure minimum brightness
            self._squid_color = (
                max(r, 100), 
                max(g, 100), 
                max(b, 100)
            )
        
        return self._squid_color
    
    def determine_startle_reason(self, current_state):
        """Determine why the squid is startled based on environment"""
        # Check for sudden environmental changes
        if self.tamagotchi_logic.environment_changed_recently():
            return "environment changed too quickly"
            
        # Check for novel objects
        if current_state.get('has_novelty_neurons', False):
            visible_objects = []
            if self.get_visible_food():
                visible_objects.append("new food")
            if self.is_near_decorations('poop'):
                visible_objects.append("poop")
            if self.is_near_decorations('plant'):
                visible_objects.append("plant")
            if visible_objects:
                return f"new object sighted ({'/'.join(visible_objects)})"
        
        # Check for emotional state
        if current_state['anxiety'] > 80 and current_state['happiness'] < 30:
            return "emotional overwhelm"
        
        # Check for sudden movement
        if abs(self.rock_velocity_x) > 5 or abs(self.rock_velocity_y) > 5:
            return "fast moving object detected"
            
        # Default reason if none specific found
        return "unknown cause"
    
    def is_near_decorations(self, category):
        """Check if decorations of specified category are nearby"""
        decorations = self.tamagotchi_logic.get_nearby_decorations(
            self.squid_x, self.squid_y)
        return any(getattr(d, 'category', None) == category 
                for d in decorations)

    def load_state(self, state):
        self.hunger = state['hunger']
        self.sleepiness = state['sleepiness']
        self.happiness = state['happiness']
        self.cleanliness = state['cleanliness']
        self.health = state['health']
        self.is_sick = state['is_sick']
        self.squid_x = state['squid_x']
        self.squid_y = state['squid_y']
        self.satisfaction = state['satisfaction']
        self.anxiety = state['anxiety']
        self.curiosity = state['curiosity']
        self.personality = Personality(state['personality'])
        
        # Load the UUID if it exists in the saved state
        if 'uuid' in state:
            self.uuid = uuid.UUID(state['uuid'])  # Convert string back to UUID object
        else:
            # For backward compatibility with old saves
            self.uuid = uuid.uuid4()

        # Restore statistics if saved
        if 'statistics' in state and hasattr(self, 'statistics'):
            stats_data = state['statistics']
            for key, value in stats_data.items():
                if hasattr(self.statistics, key):
                    setattr(self.statistics, key, value)

        # Load the squid's name if it exists in the saved state
        self.name = state.get('name', 'Squid')
        if 'tint_color' in state and state['tint_color']:
            self.tint_color = QtGui.QColor(*state['tint_color'])
        else:
            self.tint_color = None
        # Whose egg it came from, and what it inherited (None: a fresh egg).
        lineage = state.get('lineage')
        self.lineage = lineage if isinstance(lineage, dict) else None
        if self.lineage:
            self.inherited_from = [str(p) for p in (self.lineage.get('parents') or [])][:2]

        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_squid_image()

    def record_startle_reason(self, reason):
        """Record why the squid was startled for memory and display"""
        self.memory_manager.add_short_term_memory('mental_state', 'startled', 
            f"Startled because: {reason}")
        self.tamagotchi_logic.show_message(f"Squid startled! ({reason})")

    def explore_environment(self):
        if random.random() < 0.3:
            self.change_direction()
        self.move_squid()

    def is_mature(self) -> bool:
        """Grown up: old enough, and having learned from its own life.

        The one thing a squid has to be before it can breed. Judged by
        src/life_journey.is_mature on what is true of this squid now - its
        age, the consequences it has worked out, the actions it has learned.
        """
        from .life_journey import gather_facts, is_mature
        return is_mature(gather_facts(getattr(self, 'tamagotchi_logic', None),
                                      squid=self))

    def retire(self):
        """Stop everything this squid runs on its own, before it is replaced.

        A squid owns several timers and a vision thread. When a new squid
        takes over the tank, the old one's timers would otherwise keep firing
        against a body that is no longer in the scene.
        """
        for name in ('rock_interaction_timer', 'rock_animation_timer',
                     'view_cone_timer', 'anxiety_cooldown_timer', 'poop_timer'):
            timer = getattr(self, name, None)
            if timer is not None:
                try:
                    timer.stop()
                except RuntimeError:
                    pass
        self.cleanup_vision_worker()

    def is_debug_mode(self):
        return self.tamagotchi_logic.debug_mode
    

    def go_to_sleep(self):
        if not self.is_sleeping:
            self.is_sleeping = True
            self.squid_direction = "down"
            self.status = "sleeping"
            self.anxiety = max(0, self.anxiety - (1.5 * self.tamagotchi_logic.simulation_speed)) # Anxiety reduction test
            
            # Trigger hook if tamagotchi_logic exists
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                    self.tamagotchi_logic.plugin_manager.trigger_hook(
                        "on_sleep", 
                        squid=self
                    )
            
            # Clear all short-term memories when the squid goes to sleep
            self.memory_manager.clear_short_term_memory()

            self.tamagotchi_logic.show_message("Squid is sleeping...")

    def wake_up(self):
        self.is_sleeping = False
        self.sleepiness = 0
        self.happiness = min(100, self.happiness + 20)
        self.status = "roaming"
        self.squid_direction = "left"
        self.update_squid_image()
        self.tamagotchi_logic.show_message("Squid woke up!")

    def distance_to(self, x, y):
        return math.sqrt((self.squid_x - x)**2 + (self.squid_y - y)**2)

    def is_near_plant(self):
        if self.tamagotchi_logic is None:
            return False

        nearby_decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
        return any(decoration.category == 'plant' for decoration in nearby_decorations)

    def get_center(self):
        """Return the center position of the squid"""
        return (self.squid_x + self.squid_width/2, 
                self.squid_y + self.squid_height/2)
    