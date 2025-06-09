import os
import random
import time
from datetime import datetime
from enum import Enum
import math
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QTimer
from .mental_states import MentalStateManager
from .memory_manager import MemoryManager
from .personality import Personality
from .decision_engine import DecisionEngine
from .image_cache import ImageCache

class Squid:

    def __init__(self, user_interface, tamagotchi_logic=None, personality=None, neuro_cooldown=None):
        self.ui = user_interface
        self.tamagotchi_logic = tamagotchi_logic
        self.memory_manager = MemoryManager()
        self.push_animation = None
        self.startled_icon = None
        self.startled_icon_offset = QtCore.QPointF(0, -100)
        self.tint_color = None

        # Set neurogenesis cooldown (default to 200 seconds if not specified)
        self.neuro_cooldown = neuro_cooldown if neuro_cooldown is not None else 200

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

        # Goal neurons
        self.satisfaction = 50
        self.anxiety = 0
        self.curiosity = 50

        if personality is None:
            self.personality = random.choice(list(Personality))
        else:
            self.personality = personality

    @property
    def carrying_rock(self):
        return hasattr(self, 'is_carrying_rock') and self.is_carrying_rock
    
    @carrying_rock.setter
    def carrying_rock(self, value):
        self.is_carrying_rock = value
    
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

    def apply_tint(self, color):
        """Apply a color tint to the squid's image."""
        self.tint_color = color
        self.update_squid_image()

    def set_animation_speed(self, speed):
        self.animation_speed = speed

    def finish_eating(self):
        """Reset status after eating"""
        if self.status == "eating":
            self.status = "roaming"  # Or another appropriate status
            
        # Make sure the brain is updated
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            self.tamagotchi_logic.update_squid_brain()


    def load_images(self):
        """Load images with cache to reduce memory usage and apply resolution scaling"""
        from .display_scaling import DisplayScaling
        
        # Get current screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        
        # Determine resolution-specific scaling
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            # For 1080p resolution, reduce size by 30%
            image_scale = 0.7
            print("Applying 70% squid size scaling for 1080p resolution")
        else:
            # For higher resolutions, use normal scaling
            image_scale = 1.0
        
        # Load original images from cache
        original_images = {
            "left1": ImageCache.get_pixmap(os.path.join("images", "left1.png")),
            "left2": ImageCache.get_pixmap(os.path.join("images", "left2.png")),
            "right1": ImageCache.get_pixmap(os.path.join("images", "right1.png")),
            "right2": ImageCache.get_pixmap(os.path.join("images", "right2.png")),
            "up1": ImageCache.get_pixmap(os.path.join("images", "up1.png")),
            "up2": ImageCache.get_pixmap(os.path.join("images", "up2.png")),
            "sleep1": ImageCache.get_pixmap(os.path.join("images", "sleep1.png")),
            "sleep2": ImageCache.get_pixmap(os.path.join("images", "sleep2.png")),
        }
        
        # Store original dimensions for reference
        self.original_width = original_images["left1"].width()
        self.original_height = original_images["left1"].height()
        
        # Scale images for current resolution
        self.images = {}
        for name, pixmap in original_images.items():
            # Calculate scaled size
            scaled_width = int(pixmap.width() * image_scale)
            scaled_height = int(pixmap.height() * image_scale)
            
            # Create scaled pixmap
            self.images[name] = pixmap.scaled(
                scaled_width, scaled_height,
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
        
        # Scale startled image
        original_startled = ImageCache.get_pixmap(os.path.join("images", "startled.png"))
        startled_width = int(original_startled.width() * image_scale)
        startled_height = int(original_startled.height() * image_scale)
        self.startled_image = original_startled.scaled(
            startled_width, startled_height,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )
        
        # Update squid dimensions to match scaled size
        self.squid_width = self.images["left1"].width()
        self.squid_height = self.images["left1"].height()
        
        print(f"Squid scaled to {self.squid_width}x{self.squid_height} pixels")

    def show_startled_icon(self):
        """Show the startled icon above the squid's head"""
        if self.startled_icon is None:
            self.startled_icon = QtWidgets.QGraphicsPixmapItem(self.startled_image)
            self.ui.scene.addItem(self.startled_icon)
        self.update_startled_icon_position()

    def hide_startled_icon(self):
        """Remove the startled icon"""
        if self.startled_icon is not None:
            self.ui.scene.removeItem(self.startled_icon)
            self.startled_icon = None

    def update_startled_icon_position(self):
        """Position the startled icon above the squid"""
        if self.startled_icon is not None:
            self.startled_icon.setPos(
                self.squid_x + self.squid_width // 2 - self.startled_icon.pixmap().width() // 2 + self.startled_icon_offset.x(),
                self.squid_y + self.startled_icon_offset.y()
            )

    def load_poop_images(self):
        self.poop_images = [
            QtGui.QPixmap(os.path.join("images", "poop1.png")),
            QtGui.QPixmap(os.path.join("images", "poop2.png"))
        ]
        self.poop_width = self.poop_images[0].width()
        self.poop_height = self.poop_images[0].height()

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
        if self.startled_icon is not None:
            self.update_startled_icon_position()

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
        # self.sleepiness = 0  # Waking up no longer removes all tiredness
        self.happiness = max(0, self.happiness - 25)  # Increased happiness decrease
        self.anxiety = min(100, self.anxiety + 60)    # Increased anxiety spike

        # Visual feedback
        self.show_startled_icon()  # Show the startled icon
        self.tamagotchi_logic.show_message("Squid was rudely startled awake!")
        self.status = "startled"

        # Instead of immediately changing direction, set a transitional state
        self.startled_transition = True
        self.startled_transition_frames = 5  # Show startled animation for 5 frames

        # Start timers
        self.anxiety_cooldown_timer = QtCore.QTimer()
        self.anxiety_cooldown_timer.timeout.connect(self.reduce_startle_anxiety)
        self.anxiety_cooldown_timer.start(5000)  # Reduce anxiety after 5 seconds

        # Hide startled icon after 2 seconds
        QtCore.QTimer.singleShot(2000, self.hide_startled_icon)

        # End transition after a short delay (about half a second)
        QtCore.QTimer.singleShot(500, self.end_startled_transition)

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
    
    def check_boundary_exit(self):
        """
        Comprehensive boundary exit detection with robust network node handling
        """
        try:
            # Check basic prerequisites
            if not hasattr(self, 'tamagotchi_logic') or not self.tamagotchi_logic:
                return False
            
            # Check plugin manager and multiplayer status
            pm = self.tamagotchi_logic.plugin_manager
            multiplayer_enabled = 'multiplayer' in pm.get_enabled_plugins()
            
            if not multiplayer_enabled:
                return False
            
            # Attempt to get network node with multiple fallback strategies
            network_node = None
            
            # Strategy 1: Direct attribute on tamagotchi_logic
            if hasattr(self.tamagotchi_logic, 'network_node'):
                network_node = self.tamagotchi_logic.network_node
            
            # Strategy 2: Find in multiplayer plugin
            if network_node is None:
                try:
                    multiplayer_plugin = pm.plugins.get('multiplayer', {}).get('instance')
                    if multiplayer_plugin and hasattr(multiplayer_plugin, 'network_node'):
                        network_node = multiplayer_plugin.network_node
                        # Attempt to set on tamagotchi_logic for future use
                        self.tamagotchi_logic.network_node = network_node
                except Exception as plugin_error:
                    print(f"Error finding network node in plugin: {plugin_error}")
            
            # If still no network node, abort
            if network_node is None or not network_node.is_connected:
                print("No active network node found for boundary exit")
                return False
            
            # Advanced boundary detection logic
            squid_right = self.squid_x + self.squid_width
            squid_bottom = self.squid_y + self.squid_height
            
            exit_direction = None
            
            print("\n===== BOUNDARY EXIT ANALYSIS =====")
            print(f"Squid Position: ({self.squid_x}, {self.squid_y})")
            print(f"Squid Dimensions: {self.squid_width}x{self.squid_height}")
            print(f"Window Dimensions: {self.ui.window_width}x{self.ui.window_height}")
            
            # Comprehensive boundary checks
            if self.squid_x <= 0:
                exit_direction = 'left'
            elif squid_right >= self.ui.window_width:
                exit_direction = 'right'
            elif self.squid_y <= 0:
                exit_direction = 'up'
            elif squid_bottom >= self.ui.window_height:
                exit_direction = 'down'
            
            if exit_direction:
                print(f"Exit Direction Detected: {exit_direction}")
                
                # Prepare comprehensive exit data
                exit_data = {
                    'node_id': network_node.node_id,
                    'direction': exit_direction,
                    'position': {
                        'x': self.squid_x,
                        'y': self.squid_y
                    },
                    'color': self._get_squid_color(),
                    'squid_width': self.squid_width,
                    'squid_height': self.squid_height,
                    'window_width': self.ui.window_width,
                    'window_height': self.ui.window_height
                }
                
                print("Exit Data Details:")
                for key, value in exit_data.items():
                    print(f"  {key}: {value}")
                
                # Broadcast exit message
                try:
                    network_node.send_message(
                        'squid_exit', 
                        {'payload': exit_data}
                    )
                    print("Exit message successfully broadcast")
                    return True
                except Exception as broadcast_error:
                    print(f"Broadcast error: {broadcast_error}")
                    return False
            
            return False
        
        except Exception as e:
            print(f"Comprehensive boundary exit error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
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
    
    def _notify_boundary_exit(self, direction):
        """
        Enhanced notification of boundary exit with comprehensive logging
        """
        print("\n===== BOUNDARY EXIT NOTIFICATION =====")
        
        try:
            # Get plugin manager
            pm = self.tamagotchi_logic.plugin_manager
            
            # Get multiplayer plugin
            if 'multiplayer' in pm.get_enabled_plugins():
                plugin_instance = pm.plugins['multiplayer'].get('instance')
                
                if plugin_instance and hasattr(plugin_instance, 'network_node'):
                    # Prepare exit data with precise details
                    exit_data = {
                        'node_id': plugin_instance.network_node.node_id if plugin_instance.network_node else 'unknown',
                        'direction': direction,
                        'position': {
                            'x': self.squid_x,
                            'y': self.squid_y
                        },
                        'color': plugin_instance.get_squid_color() if hasattr(plugin_instance, 'get_squid_color') else (150, 150, 255),
                        'squid_width': self.squid_width,
                        'squid_height': self.squid_height,
                        'window_width': self.ui.window_width,
                        'window_height': self.ui.window_height
                    }
                    
                    print("Exit Data:")
                    for key, value in exit_data.items():
                        print(f"  {key}: {value}")
                    
                    # Broadcast exit message
                    plugin_instance.network_node.send_message(
                        'squid_exit', 
                        {'payload': exit_data}
                    )
                    
                    print(f"[MULTIPLAYER] Squid exiting through {direction} boundary")
                    
                    # CHANGE: Completely hide the squid instead of reducing opacity
                    self.squid_item.setVisible(False)
                    
                    # CHANGE: Set flag to indicate squid is away
                    self.is_transitioning = True
                    
                    # CHANGE: Disable movement while away
                    self.can_move = False
                    
                    # CHANGE: Update status
                    self.status = "visiting another tank"
                    
                    # Optional: Show a message about the squid leaving
                    if hasattr(self.tamagotchi_logic, 'show_message'):
                        self.tamagotchi_logic.show_message(f"Your squid left through the {direction} boundary!")
                else:
                    print("[ERROR] No network node or plugin instance available")
            else:
                print("[ERROR] Multiplayer plugin not enabled")
        
        except Exception as e:
            print(f"[CRITICAL] Error in boundary exit notification:")
            import traceback
            traceback.print_exc()
        
        print("===== BOUNDARY EXIT NOTIFICATION END =====\n")
    
    
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

    def search_for_favorite_food(self):
        visible_food = self.get_visible_food()
        if visible_food:
            for food_x, food_y in visible_food:
                if self.is_favorite_food(self.tamagotchi_logic.get_food_item_at(food_x, food_y)):
                    self.move_towards(food_x, food_y)
                    return
            # If no favorite food is found, display a message and move randomly
            self.tamagotchi_logic.show_message("Stubborn squid does not like that type of food!")
            self.move_randomly()
        else:
            self.move_randomly()

    def get_favorite_food(self):
        # Implement logic to find the squid's favorite food
        for food_item in self.tamagotchi_logic.food_items:
            if self.is_favorite_food(food_item):
                return food_item.pos().x(), food_item.pos().y()
        return None

    def is_favorite_food(self, food_item):
        return food_item is not None and getattr(food_item, 'is_sushi', False)

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
        
        # Load the squid's name if it exists in the saved state
        if 'name' in state:
            self.name = state['name']
        
        # --- This block is added to load the color ---
        if 'tint_color' in state and state['tint_color']:
            # Recreate the QColor object from the saved RGBA tuple
            self.tint_color = QtGui.QColor(*state['tint_color'])
        else:
            self.tint_color = None
        
        self.squid_item.setPos(self.squid_x, self.squid_y)
        # We must update the image to apply the loaded tint
        self.update_squid_image()

    def push_decoration(self, decoration, direction):
        """Push a decoration with proper animation handling"""
        try:
            push_distance = 80  # pixels to push
            current_pos = decoration.pos()
            new_x = current_pos.x() + (push_distance * direction)

            # Ensure the decoration stays within scene boundaries
            scene_rect = self.ui.scene.sceneRect()
            new_x = max(scene_rect.left(), 
                    min(new_x, scene_rect.right() - decoration.boundingRect().width()))
            
            # Only create animation if we don't have one running
            if self.push_animation and self.push_animation.state() == QtCore.QAbstractAnimation.Running:
                self.push_animation.stop()

            # Create position animation
            self.push_animation = QtCore.QPropertyAnimation(decoration, b"pos")
            self.push_animation.setDuration(300)
            self.push_animation.setStartValue(current_pos)
            self.push_animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
            self.push_animation.finished.connect(
                lambda: self._on_push_complete(decoration))
            self.push_animation.start()
            
        except Exception as e:
            print(f"Error pushing decoration: {e}")
            # Fallback to immediate movement
            decoration.setPos(new_x, current_pos.y())
            self._on_push_complete(decoration)

    def _on_push_complete(self, decoration):
        """Callback when push animation finishes"""
        self.happiness = min(100, self.happiness + 5)
        self.curiosity = min(100, self.curiosity + 10)
        
        # --- NEWLY ADDED ---
        # Pushing decorations is a comforting action that reduces anxiety.
        self.anxiety = max(0, self.anxiety - 6)
        
        self.status = "pushing decoration"
        self.tamagotchi_logic.show_message("Squid pushed a decoration")

        # Remove animation reference
        self.push_animation = None

    def record_startle_reason(self, reason):
        """Record why the squid was startled for memory and display"""
        self.memory_manager.add_short_term_memory('mental_state', 'startled', 
            f"Startled because: {reason}")
        self.tamagotchi_logic.show_message(f"Squid startled! ({reason})")

    def handle_rock_interaction(self, target_rock=None):
        """Unified rock interaction handler delegates to RockInteractionManager"""
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            return False
            
        return self.tamagotchi_logic.rock_interaction.start_rock_test(target_rock)

    def move_erratically(self):
        directions = ["left", "right", "up", "down"]
        self.squid_direction = random.choice(directions)
        self.move_squid()

    def move_slowly(self):
        self.base_squid_speed = self.base_squid_speed // 2
        self.base_vertical_speed = self.base_vertical_speed // 2
        self.move_squid()

    def explore_environment(self):
        if random.random() < 0.3:
            self.change_direction()
        self.move_squid()

    def search_for_food(self):
        visible_food = self.get_visible_food()
        if visible_food:
            # Only set pursuing_food to True if food is actually visible
            self.pursuing_food = True
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.status = "moving to food"
            self.move_towards(closest_food[0], closest_food[1])
        else:
            # Reset pursuing_food when no food is visible
            self.pursuing_food = False
            self.status = "searching for food"
            self.move_randomly()

    def get_visible_food(self):
        if self.tamagotchi_logic is None:
            return []
        visible_food = []
        for food_item in self.tamagotchi_logic.food_items:
            food_x, food_y = food_item.pos().x(), food_item.pos().y()
            # Only add food if it's in the view cone
            if self.is_in_vision_cone(food_x, food_y):
                if getattr(food_item, 'is_sushi', False):
                    visible_food.insert(0, (food_x, food_y))  # Prioritize sushi
                else:
                    visible_food.append((food_x, food_y))  # Add cheese to the end
        return visible_food

    def is_in_vision_cone(self, x, y):
        """
        Check if a point (x,y) is inside the squid's vision cone
        
        Args:
            x (float): X coordinate to check
            y (float): Y coordinate to check
            
        Returns:
            bool: True if the point is in vision cone, False otherwise
        """
        # Get squid center position
        squid_center_x = self.squid_x + self.squid_width // 2
        squid_center_y = self.squid_y + self.squid_height // 2
        
        # Calculate vector to target
        dx = x - squid_center_x
        dy = y - squid_center_y
        
        # Calculate distance
        distance = math.sqrt(dx**2 + dy**2)
        
        # Define vision cone length
        cone_length = max(self.ui.window_width, self.ui.window_height)
        
        # If target is beyond detection range, return false
        if distance > cone_length:
            return False
        
        # Calculate angle to target point
        angle_to_target = math.atan2(dy, dx)
        
        # Get current view angle (use current_view_angle if available, otherwise derive from direction)
        if hasattr(self, 'current_view_angle'):
            current_angle = self.current_view_angle
        else:
            direction_map = {
                'right': 0,
                'up': math.pi * 1.5,
                'left': math.pi,
                'down': math.pi * 0.5
            }
            current_angle = direction_map.get(self.squid_direction, 0)
        
        # Get cone angle (half of the total view cone angle)
        if hasattr(self, 'view_cone_angle'):
            cone_angle = self.view_cone_angle / 2
        else:
            cone_angle = math.pi / 5  # Default 36-degree half-angle
        
        # Calculate angle difference (accounting for wrap-around)
        angle_diff = abs(angle_to_target - current_angle)
        while angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
        
        # Check if the target is within the cone angle
        return angle_diff <= cone_angle
    
    def change_view_cone_direction(self):
        self.current_view_angle = random.uniform(0, 2 * math.pi)

    def move_squid(self):
        """
        Move the squid with comprehensive debug logging and boundary check
        """
        # Check if movement is allowed
        if not getattr(self, 'can_move', True):
            return
        
        # Check if multiplayer is available and enabled
        if hasattr(self.tamagotchi_logic, 'plugin_manager'):
            pm = self.tamagotchi_logic.plugin_manager
            multiplayer_enabled = 'multiplayer' in pm.get_enabled_plugins()
        else:
            multiplayer_enabled = False
        
        if self.animation_speed == 0:
            #print("Animation speed is 0, no movement")
            return

        if self.is_sleeping:
            #print("Squid is sleeping, limited movement")
            if self.squid_y < self.ui.window_height - 120 - self.squid_height:
                self.squid_y += self.base_vertical_speed * self.animation_speed
                self.squid_item.setPos(self.squid_x, self.squid_y)
            self.current_frame = (self.current_frame + 1) % 2
            self.update_squid_image()
            return

        current_time = QtCore.QTime.currentTime().msecsSinceStartOfDay()

        visible_food = self.get_visible_food()

        if visible_food:
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.pursuing_food = True
            self.target_food = closest_food
            self.move_towards(closest_food[0], closest_food[1])
        elif self.pursuing_food:
            self.pursuing_food = False
            self.target_food = None
            self.move_randomly()
        else:
            if current_time - self.last_view_cone_change > self.view_cone_change_interval:
                self.change_view_cone_direction()
                self.last_view_cone_change = current_time
            self.move_randomly()

        # Calculate new position
        squid_x_new = self.squid_x
        squid_y_new = self.squid_y

        if self.squid_direction == "left":
            squid_x_new -= self.base_squid_speed * self.animation_speed
        elif self.squid_direction == "right":
            squid_x_new += self.base_squid_speed * self.animation_speed
        elif self.squid_direction == "up":
            squid_y_new -= self.base_vertical_speed * self.animation_speed
        elif self.squid_direction == "down":
            squid_y_new += self.base_vertical_speed * self.animation_speed

        # Boundary handling for single-player and multiplayer modes
        if not multiplayer_enabled:
            # Original boundary restrictions for single-player mode
            if squid_x_new < 50:
                squid_x_new = 50
                self.change_direction()
            elif squid_x_new > self.ui.window_width - 50 - self.squid_width:
                squid_x_new = self.ui.window_width - 50 - self.squid_width
                self.change_direction()

            if squid_y_new < 50:
                squid_y_new = 50
                self.change_direction()
            elif squid_y_new > self.ui.window_height - 120 - self.squid_height:
                squid_y_new = self.ui.window_height - 120 - self.squid_height
                self.change_direction()
        else:
            # Extended boundary check for multiplayer
            print("Multiplayer mode: Extended boundary check")
            squid_right = squid_x_new + self.squid_width
            squid_bottom = squid_y_new + self.squid_height

        # Update squid position
        self.squid_x = squid_x_new
        self.squid_y = squid_y_new

        # Update animation frame and image
        if self.squid_direction in ["left", "right", "up", "down"]:
            self.current_frame = (self.current_frame + 1) % 2
            self.squid_item.setPixmap(self.current_image())

        # Set new position and update related elements
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()
        self.update_sick_icon_position()

        # Comprehensive boundary exit check in multiplayer mode
        if multiplayer_enabled:
            #print("Triggering boundary exit check in multiplayer mode")
            exit_result = self.check_boundary_exit()
            #print(f"Boundary Exit Result: {exit_result}")

    def move_towards(self, x, y):
        dx = x - (self.squid_x + self.squid_width // 2)
        dy = y - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

    def move_towards_position(self, target_pos):
        dx = target_pos.x() - (self.squid_x + self.squid_width // 2)
        dy = target_pos.y() - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

        self.move_squid()

    def eat(self, food_item):
        effects = {}

        # Basic effects for all food types
        effects['hunger'] = max(-20, -self.hunger)
        effects['happiness'] = min(10, 100 - self.happiness)

        # Determine food type and effects
        is_sushi = getattr(food_item, 'is_sushi', False)
        food_name = "sushi" if is_sushi else "cheese"
        
        # Satisfaction boost (stronger for sushi)
        effects['satisfaction'] = min(15 if is_sushi else 10, 100 - self.satisfaction)

        # Personality-based reward points
        reward_points = 2  # Default for all food
        if is_sushi and self.personality in [Personality.GREEDY, Personality.STUBBORN]:
            reward_points = 3  # Extra reward for favorite food
            effects['satisfaction'] = min(20, 100 - self.satisfaction)  # Even bigger boost

        # Trigger hook if tamagotchi_logic exists
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_feed", 
                    squid=self,
                    food_item=food_item,
                    food_type=food_name,
                    effects=effects
                )
        
        self.is_eating = True
        self.status = "eating"
        # Apply all stat changes
        for attr, change in effects.items():
            setattr(self, attr, getattr(self, attr) + change)

        # Start a timer to reset the status after 1 second
        QTimer.singleShot(1000, self.finish_eating)

        # Memory system
        formatted_effects = ', '.join(f"{attr.capitalize()} {'+' if val >= 0 else ''}{val:.2f}" 
                            for attr, val in effects.items())
        self.memory_manager.add_short_term_memory('food', food_name, 
            f"Ate {food_name}: {formatted_effects}")

        # Neurogenesis tracking
        if hasattr(self.tamagotchi_logic, 'neurogenesis_triggers'):
            current = self.tamagotchi_logic.neurogenesis_triggers['positive_outcomes']
            self.tamagotchi_logic.neurogenesis_triggers['positive_outcomes'] = min(current + reward_points, 5)

        # Visual/behavioral effects
        self.status = f"Eating {food_name}"
        self.tamagotchi_logic.remove_food(food_item)
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None
        self.is_eating = False

        # Personality reactions (with enhanced messages)
        if self.personality == Personality.GREEDY:
            self.eat_greedily(food_item)
            if is_sushi:
                self.tamagotchi_logic.show_message("Greedy squid devours sushi voraciously!")
        elif self.personality == Personality.STUBBORN:
            if not is_sushi:
                self.react_stubborn_eating()
            else:
                self.tamagotchi_logic.show_message("Stubborn squid happily accepts sushi")

    def eat_greedily(self, food_item):
        self.status = "Eating greedily"
        food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"

        # Reduce hunger more than usual
        self.hunger = max(0, self.hunger - 25)

        # Increase happiness more
        self.happiness = min(100, self.happiness + 15)

        # Increase satisfaction significantly
        self.satisfaction = min(100, self.satisfaction + 20)

        # Slightly increase anxiety (from overeating)
        self.anxiety = min(100, self.anxiety + 5)

        self.tamagotchi_logic.remove_food(food_item)
        #print(f"The greedy squid enthusiastically ate the {food_type}")
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Occasionally show a message
        if random.random() < 0.2:  # 20% chance to show a message
            self.tamagotchi_logic.show_message("Nom nom! Greedy squid devours the food!")

        # Check if there's more food nearby
        if self.check_for_more_food():
            if random.random() < 0.1:  # 10% chance to show this message
                self.tamagotchi_logic.show_message("Greedy squid looks around for more food...")
        else:
            if random.random() < 0.1:  # 10% chance to show this message
                self.tamagotchi_logic.show_message("Greedy squid is satisfied... for now.")

    def react_stubborn_eating(self):
        if self.hunger > 80:  # Extremely hungry
            self.happiness = max(0, self.happiness - 5)
            self.tamagotchi_logic.show_message("Stubborn squid reluctantly eats non-sushi food.")
        else:
            self.tamagotchi_logic.show_message("Stubborn squid ignores non-sushi food.")

    def check_for_more_food(self):
        for food_item in self.tamagotchi_logic.food_items:
            if self.is_food_nearby(food_item):
                return True
        return False

    def is_food_nearby(self, food_item):
        food_x, food_y = food_item.pos().x(), food_item.pos().y()
        squid_center_x = self.squid_x + self.squid_width // 2
        squid_center_y = self.squid_y + self.squid_height // 2
        distance = math.sqrt((squid_center_x - food_x)**2 + (squid_center_y - food_y)**2)
        return distance < 100  # Adjust the distance threshold as needed
    
    def process_squid_detection(self, remote_node_id, is_visible=True):
        """
        Process the detection of another squid in this squid's vision cone
        
        Args:
            remote_node_id (str): ID of the detected squid
            is_visible (bool): Whether the squid is currently visible
        """
        # Only react if the squid is not sleeping
        if self.is_sleeping:
            return
        
        if is_visible:
            # Detected a new squid or is continuing to see it
            
            # Increase curiosity when first detected
            if not hasattr(self, '_seen_squids') or remote_node_id not in self._seen_squids:
                # First time seeing this squid
                self.curiosity = min(100, self.curiosity + 15)
                
                # Small anxiety spike from the surprise
                self.anxiety = min(100, self.anxiety + 10)
                
                # Add memory
                self.memory_manager.add_short_term_memory(
                    'social', 'squid_detection',
                    f"Detected another squid (ID: {remote_node_id[-4:]})"
                )
                
                # Initialize tracking of seen squids if needed
                if not hasattr(self, '_seen_squids'):
                    self._seen_squids = set()
                
                # Add to seen squids
                self._seen_squids.add(remote_node_id)
                
                # Chance to get startled
                if random.random() < 0.3:  # 30% chance
                    # Try to use the startle function if it exists
                    if hasattr(self.tamagotchi_logic, 'startle_squid'):
                        self.tamagotchi_logic.startle_squid(source="detected_squid")
            else:
                # Already seen this squid before, smaller reaction
                self.curiosity = min(100, self.curiosity + 5)
        else:
            # Lost sight of a squid
            # Nothing special happens, just note it
            if hasattr(self, '_seen_squids') and remote_node_id in self._seen_squids:
                self.memory_manager.add_short_term_memory(
                    'social', 'squid_lost',
                    f"Lost sight of squid (ID: {remote_node_id[-4:]})"
                )

    def react_to_rock_throw(self, source_node_id, is_target=False):
        """
        React to a rock being thrown by another squid
        
        Args:
            source_node_id (str): ID of the squid that threw the rock
            is_target (bool): Whether this squid is the apparent target
        """
        # Only react if the squid is not sleeping
        if self.is_sleeping:
            return
        
        # Base reaction - increase anxiety
        self.anxiety = min(100, self.anxiety + 5)
        
        # Add memory
        self.memory_manager.add_short_term_memory(
            'observation', 'rock_throw',
            f"Observed squid {source_node_id[-4:]} throw a rock"
        )
        
        # Strong reaction if targeted
        if is_target:
            # Get startled
            if hasattr(self.tamagotchi_logic, 'startle_squid'):
                self.tamagotchi_logic.startle_squid(source="targeted_by_rock")
            
            # Significantly increase anxiety
            self.anxiety = min(100, self.anxiety + 20)
            
            # Decrease happiness
            self.happiness = max(0, self.happiness - 10)
            
            # Add memory of being targeted
            self.memory_manager.add_short_term_memory(
                'social', 'targeted',
                f"Was targeted by rock from squid {source_node_id[-4:]}"
            )
            
            # Higher chance for this memory to go to long-term
            if random.random() < 0.5:  # 50% chance
                self.memory_manager.transfer_to_long_term_memory(
                    'social', 'targeted'
                )


    def investigate_food(self, food_item):
        self.status = "Investigating food"
        self.tamagotchi_logic.show_message("Stubborn squid investigates the food...")

        # Move towards the food
        food_pos = food_item.pos()
        self.move_towards_position(food_pos)

        # Wait for a moment (might need to implement a delay here)

        self.tamagotchi_logic.show_message("Stubborn squid ignored the food")
        self.status = "I don't like that food"

    def consume_food(self, food_item):
        self.status = "Ate food"
        self.hunger = max(0, self.hunger - 20)
        self.happiness = min(100, self.happiness + 10)
        self.satisfaction = min(100, self.satisfaction + 15)
        self.anxiety = max(0, self.anxiety - 10)
        self.tamagotchi_logic.remove_food(food_item)
        #print("The squid ate the food")
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Occasionally show a message based on personality
        if random.random() < 0.25:  # 25% chance to show a message
            if self.personality == Personality.STUBBORN and getattr(food_item, 'is_sushi', False):
                self.tamagotchi_logic.show_message("Nom nom! Stubborn squid enjoys the sushi!")
            elif self.personality == Personality.GREEDY:
                food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"
                self.tamagotchi_logic.show_message(f"Nom nom! Greedy squid gobbles up the {food_type}!")
            else:
                self.tamagotchi_logic.show_message("Nom nom! Squid enjoys the meal!")

    def start_poop_timer(self):
        poop_delay = random.randint(11000, 30000)
        #print("Poop random timer started")
        self.poop_timer = QtCore.QTimer()
        self.poop_timer.setSingleShot(True)
        self.poop_timer.timeout.connect(self.create_poop)
        self.poop_timer.start(poop_delay)

    def create_poop(self):
        self.tamagotchi_logic.spawn_poop(self.squid_x + self.squid_width // 2, self.squid_y + self.squid_height)
        #print("Poop created at squid location")

    def show_eating_effect(self):
        if not self.is_debug_mode():
            return

        effect_item = QtWidgets.QGraphicsEllipseItem(self.squid_x, self.squid_y, self.squid_width, self.squid_height)
        effect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 100)))
        effect_item.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.ui.scene.addItem(effect_item)

        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        effect_item.setGraphicsEffect(opacity_effect)

        self.eating_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        self.eating_animation.setDuration(1000)
        self.eating_animation.setStartValue(2.5)
        self.eating_animation.setEndValue(0.0)
        self.eating_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        self.eating_animation.finished.connect(lambda: self.ui.scene.removeItem(effect_item))

        self.eating_animation.start()

    def is_debug_mode(self):
        return self.tamagotchi_logic.debug_mode
    

    def change_to_rps_image(self):
        self.rps_image = QtGui.QPixmap(os.path.join("images", "squid_rps_frame.png"))
        self.squid_item.setPixmap(self.rps_image)

    def restore_normal_image(self):
        self.squid_item.setPixmap(self.current_image())

    def should_hoard_decorations(self):
        """Check if this personality type should hoard items"""
        return self.personality in [Personality.GREEDY, Personality.STUBBORN]

    def organize_decorations(self):
        target_corner = (50, 50)  # Top-left corner coordinates
        
        # Get nearby decorations (filter by rocks/plants if needed)
        decorations = [
            d for d in self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y) 
            if getattr(d, 'category', None) in ['rock', 'plant']
        ]
        
        if decorations:
            closest = min(decorations, key=lambda d: self.distance_to(d.pos().x(), d.pos().y()))
            
            # Move toward the decoration
            if self.distance_to(closest.pos().x(), closest.pos().y()) > 50:
                self.move_towards(closest.pos().x(), closest.pos().y())
                return "approaching_decoration"
            
            # Push toward hoard corner
            push_direction = 1 if target_corner[0] > closest.pos().x() else -1
            self.push_decoration(closest, push_direction)
            
            # Personality-specific effects
            self.satisfaction = min(100, self.satisfaction + 10)
            if self.personality == Personality.GREEDY:
                self.tamagotchi_logic.show_message("Greedy squid hoards treasures!")
            
            return "hoarding"
        return "nothing_to_hoard"

    def go_to_sleep(self):
        if not self.is_sleeping:
            self.is_sleeping = True
            self.squid_direction = "down"
            self.status = "sleeping"
            
            # Trigger hook if tamagotchi_logic exists
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                    self.tamagotchi_logic.plugin_manager.trigger_hook(
                        "on_sleep", 
                        squid=self
                    )
            
            self.tamagotchi_logic.show_message("Squid is sleeping...")

    def wake_up(self):
        self.is_sleeping = False
        self.sleepiness = 0
        self.happiness = min(100, self.happiness + 20)
        self.status = "roaming"
        self.squid_direction = "left"
        self.update_squid_image()
        self.tamagotchi_logic.show_message("Squid woke up!")

    def update_squid_image(self):
        self.squid_item.setPixmap(self.current_image())

    def current_image(self):
        """Return the current image of the squid, with tint applied only to white parts."""
        # Base image selection logic (same as before)
        if hasattr(self, 'startled_transition') and self.startled_transition:
            base_image = self.startled_image
        elif hasattr(self, 'status') and self.status == "startled" and not self.is_sleeping:
            direction = "left" if random.random() < 0.5 else "right"
            base_image = self.images[f"{direction}{self.current_frame + 1}"]
        elif self.is_sleeping:
            base_image = self.images[f"sleep{self.current_frame + 1}"]
        elif self.squid_direction == "left":
            base_image = self.images[f"left{self.current_frame + 1}"]
        elif self.squid_direction == "right":
            base_image = self.images[f"right{self.current_frame + 1}"]
        elif self.squid_direction == "up":
            base_image = self.images[f"up{self.current_frame + 1}"]
        else:
            base_image = self.images["left1"]

        # If no tint color is set, return the original image
        if not self.tint_color:
            return base_image

        # --- Corrected Tinting Logic ---

        # Convert the QPixmap to a QImage for pixel-level access
        source_image = base_image.toImage()

        # Create a new QImage to draw our modified squid onto.
        # Using Format_ARGB32 is crucial for handling transparency correctly
        # and preventing the black background issue.
        output_image = QtGui.QImage(source_image.size(), QtGui.QImage.Format_ARGB32)
        output_image.fill(QtCore.Qt.transparent)  # Start with a fully transparent canvas

        white_threshold = 240

        # Iterate over every pixel in the source image
        for y in range(source_image.height()):
            for x in range(source_image.width()):
                # Get the color of the current pixel from the source
                pixel_color = QtGui.QColor(source_image.pixel(x, y))

                # Check if the pixel is 'white enough' and not fully transparent
                if (pixel_color.alpha() > 0 and
                    pixel_color.red() > white_threshold and
                    pixel_color.green() > white_threshold and
                    pixel_color.blue() > white_threshold):
                    
                    # If it's a white pixel, apply the tint color
                    new_color = QtGui.QColor(self.tint_color)
                    # Preserve the original pixel's alpha value to keep smooth edges
                    new_color.setAlpha(pixel_color.alpha())
                    output_image.setPixelColor(x, y, new_color)
                else:
                    # For any other pixel (the outline, or fully transparent areas),
                    # just copy it directly from the source. This ensures the background
                    # remains transparent.
                    output_image.setPixel(x, y, source_image.pixel(x, y))

        # Convert the modified QImage back to a QPixmap and return it
        return QtGui.QPixmap.fromImage(output_image)

    def move_randomly(self):
        if random.random() < 0.20:
            self.change_direction()

    def get_food_position(self):
        if self.tamagotchi_logic.food_items:
            closest_food = min(self.tamagotchi_logic.food_items,
                               key=lambda food: self.distance_to(food.pos().x(), food.pos().y()))
            return closest_food.pos().x(), closest_food.pos().y()
        else:
            return -1, -1

    def distance_to(self, x, y):
        return math.sqrt((self.squid_x - x)**2 + (self.squid_y - y)**2)

    def change_direction(self):
        directions = ["left", "right", "up", "down"]
        new_direction = random.choice(directions)
        while new_direction == self.squid_direction:
            new_direction = random.choice(directions)
        self.squid_direction = new_direction

    def toggle_view_cone(self):
        self.view_cone_visible = not self.view_cone_visible
        if self.view_cone_visible:
            self.update_view_cone()
        else:
            self.remove_view_cone()

    def update_view_cone(self):
        if self.view_cone_visible:
            if self.view_cone_item is None:
                self.view_cone_item = QtWidgets.QGraphicsPolygonItem()
                self.view_cone_item.setPen(QtGui.QPen(QtCore.Qt.yellow))
                self.view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 50)))
                self.ui.scene.addItem(self.view_cone_item)

            squid_center_x = self.squid_x + self.squid_width // 2
            squid_center_y = self.squid_y + self.squid_height // 2

            if self.pursuing_food and self.target_food:
                dx = self.target_food[0] - squid_center_x
                dy = self.target_food[1] - squid_center_y
                self.current_view_angle = math.atan2(dy, dx)

            cone_length = max(self.ui.window_width, self.ui.window_height)

            cone_points = [
                QtCore.QPointF(squid_center_x, squid_center_y),
                QtCore.QPointF(squid_center_x + math.cos(self.current_view_angle - self.view_cone_angle/2) * cone_length,
                               squid_center_y + math.sin(self.current_view_angle - self.view_cone_angle/2) * cone_length),
                QtCore.QPointF(squid_center_x + math.cos(self.current_view_angle + self.view_cone_angle/2) * cone_length,
                               squid_center_y + math.sin(self.current_view_angle + self.view_cone_angle/2) * cone_length)
            ]

            cone_polygon = QtGui.QPolygonF(cone_points)
            self.view_cone_item.setPolygon(cone_polygon)
        else:
            self.remove_view_cone()

    def remove_view_cone(self):
        if self.view_cone_item is not None:
            self.ui.scene.removeItem(self.view_cone_item)
            self.view_cone_item = None

    def show_sick_icon(self):
        if self.sick_icon_item is None:
            sick_icon_pixmap = QtGui.QPixmap(os.path.join("images", "sick.png"))
            self.sick_icon_item = QtWidgets.QGraphicsPixmapItem(sick_icon_pixmap)
            self.ui.scene.addItem(self.sick_icon_item)
        self.update_sick_icon_position()

    def hide_sick_icon(self):
        if self.sick_icon_item is not None:
            self.ui.scene.removeItem(self.sick_icon_item)
            self.sick_icon_item = None

    def update_sick_icon_position(self):
        if self.sick_icon_item is not None:
            self.sick_icon_item.setPos(self.squid_x + self.squid_width // 2 - self.sick_icon_item.pixmap().width() // 2 + self.sick_icon_offset.x(),
                                       self.squid_y + self.sick_icon_offset.y())

    def is_near_plant(self):
        if self.tamagotchi_logic is None:
            return False

        nearby_decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
        return any(decoration.category == 'plant' for decoration in nearby_decorations)

    def move_towards_plant(self):
        if self.tamagotchi_logic is None:
            return

        nearby_decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
        plants = [d for d in nearby_decorations if d.category == 'plant']

        if plants:
            closest_plant = min(plants, key=lambda p: self.distance_to(p.pos().x(), p.pos().y()))
            self.move_towards(closest_plant.pos().x(), closest_plant.pos().y())
        else:
            self.move_randomly()

    def should_organize_decorations(self):
        return (self.curiosity > 70 and
                self.satisfaction < 80 and
                self.personality in [Personality.ADVENTUROUS, Personality.ENERGETIC])

    def organize_decorations(self):
        target_corner = (50, 50)  # Top-left corner
        decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)

        if decorations:
            closest = min(decorations, key=lambda d: self.distance_to(d.pos().x(), d.pos().y()))
            self.move_towards(closest.pos().x(), closest.pos().y())

            if self.distance_to(closest.pos().x(), closest.pos().y()) < 50:
                self.push_decoration(closest, direction=1 if random.random() < 0.5 else -1)
                self.satisfaction = min(100, self.satisfaction + 5)
                return "organizing decorations"
        return "searching for decorations"

    def interact_with_rocks(self):
        rocks = [d for d in self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
                 if d.category == 'rock']
        if rocks:
            self.push_decoration(random.choice(rocks), random.choice([-1, 1]))
            self.satisfaction = min(100, self.satisfaction + 8)
            self.happiness = min(100, self.happiness + 5)
            return "interacting with rocks"
        return "no rocks nearby"

    def can_pick_up_rock(self, rock_item):
        """Check if squid can pick up this rock"""
        rock_rect = rock_item.sceneBoundingRect()
        rock_center = rock_rect.center()
        
        squid_rect = self.squid_item.sceneBoundingRect()
        squid_center = squid_rect.center()
        
        distance = math.sqrt((rock_center.x() - squid_center.x())**2 + 
                            (rock_center.y() - squid_center.y())**2)
        
        can_pick = (not self.carrying_rock and 
                    not self.is_sleeping and
                    distance < 50)
        
        print(f"Can pick up rock check:")
        print(f"- Rock center: ({rock_center.x():.1f}, {rock_center.y():.1f})")
        print(f"- Squid center: ({squid_center.x():.1f}, {squid_center.y():.1f})")
        print(f"- Distance: {distance:.1f}")
        print(f"- Carrying: {self.carrying_rock}")
        print(f"- Sleeping: {self.is_sleeping}")
        print(f"- Result: {can_pick}")
        
        return can_pick

    def pick_up_rock(self, item):
        """Delegate to interaction manager with random carry duration"""
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            return False
        return self.tamagotchi_logic.rock_interaction.attach_rock_to_squid(item)

    def throw_rock(self, direction):
        """Delegate to interaction manager"""
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            return False
        return self.tamagotchi_logic.rock_interaction.throw_rock(direction)


    def update_rock_throw(self):
        if not self.rock_being_thrown or not self.rock_being_thrown.scene():
            self.rock_animation_timer.stop()
            return
        
        rock = self.rock_being_thrown
        current_pos = rock.pos()
        
        # Heavy rock physics - sink quickly with minimal bouncing
        self.rock_velocity_y += 2.0  # Strong gravity for quick sinking
        
        # Calculate new position
        new_x = current_pos.x() + self.rock_velocity_x
        new_y = current_pos.y() + self.rock_velocity_y
        
        # Get scene boundaries
        scene_rect = self.ui.scene.sceneRect()
        rock_rect = rock.boundingRect()
        
        # Stop at reachable depth (200px from bottom)
        max_y = self.ui.window_height - 200 - rock_rect.height()
        if new_y > max_y:
            new_y = max_y
            self.rock_animation_timer.stop()
            self.rock_being_thrown = None
            return
        
        # Minimal horizontal movement when sinking
        if abs(self.rock_velocity_y) > 1.0:  # If sinking fast
            self.rock_velocity_x *= 0.3  # Strong horizontal dampening
        
        # Basic wall collisions
        if new_x < scene_rect.left():
            new_x = scene_rect.left()
            self.rock_velocity_x *= -0.5  # Weak wall bounce
        elif new_x > scene_rect.right() - rock_rect.width():
            new_x = scene_rect.right() - rock_rect.width()
            self.rock_velocity_x *= -0.5
        
        # Update position
        rock.setPos(new_x, new_y)


    def check_rock_interaction(self):
        if not hasattr(self, 'tamagotchi_logic') or self.tamagotchi_logic is None:
            return False
            
        if not hasattr(self.tamagotchi_logic, 'config_manager'):
            return False
            
        config = self.tamagotchi_logic.config_manager.get_rock_config()
        
        decorations = self.tamagotchi_logic.get_nearby_decorations(
            self.squid_x, self.squid_y, 150)
        interactables = [d for d in decorations if d.category in ['rock', 'poop']]

        if (self.carrying_rock 
                and self.rock_throw_cooldown == 0 
                and random.random() < config['throw_prob']):
            direction = random.choice(["left", "right"])
            if self.throw_rock(direction):
                return

        if (not self.carrying_rock 
                and self.rock_throw_cooldown == 0 
                and interactables
                and random.random() < config['pickup_prob']):
            target_item = random.choice(interactables)
            
            if self.pick_up_rock(target_item):
                mem_details = {
                    "item": getattr(target_item, 'filename', f'unknown_{target_item.category}'),
                    "position": (target_item.pos().x(), target_item.pos().y()),
                    "timestamp": datetime.now().isoformat()
                }
                self.memory_manager.add_short_term_memory(
                    'interaction', f'{target_item.category}_pickup', mem_details)
            else:
                print(f"[DEBUG] {target_item.category.capitalize()} pickup failed")

    def check_poop_interaction(self):
        """Periodic poop interaction check similar to rock interaction"""
        if not hasattr(self.tamagotchi_logic, 'poop_interaction'):
            return False
            
        config = self.tamagotchi_logic.config_manager.get_poop_config()
        
        decorations = self.tamagotchi_logic.get_nearby_decorations(
            self.squid_x, self.squid_y, 150)
        interactables = [d for d in decorations if d.category == 'poop']

        # If carrying poop and cooldown is done, potentially throw
        if (self.carrying_poop 
                and self.poop_throw_cooldown == 0 
                and random.random() < config['throw_prob']):
            direction = random.choice(["left", "right"])
            if self.throw_poop(direction):
                return

        # If not carrying poop and cooldown is done, potentially pick up
        if (not self.carrying_poop 
                and self.poop_throw_cooldown == 0 
                and interactables
                and random.random() < config['pickup_prob']):
            target_item = random.choice(interactables)
            
            if self.pick_up_poop(target_item):
                mem_details = {
                    "item": getattr(target_item, 'filename', 'unknown_poop'),
                    "position": (target_item.pos().x(), target_item.pos().y()),
                    "timestamp": datetime.now().isoformat()
                }
                self.memory_manager.add_short_term_memory(
                    'interaction', 'poop_pickup', mem_details)
            else:
                print(f"[DEBUG] Poop pickup failed")

    def get_center(self):
        """Return the center position of the squid"""
        return (self.squid_x + self.squid_width/2, 
                self.squid_y + self.squid_height/2)
    
    def move_toward_position(self, target_pos):
        """Move directly toward a QPointF or (x,y) position with rock interaction support"""
        # Handle both QPointF and tuple/position inputs
        if isinstance(target_pos, QtCore.QPointF):
            target_x, target_y = target_pos.x(), target_pos.y()
        else:
            target_x, target_y = target_pos
        
        # Get precise center positions using scene coordinates
        squid_rect = self.squid_item.sceneBoundingRect()
        squid_center_x = squid_rect.center().x()
        squid_center_y = squid_rect.center().y()
        
        dx = target_x - squid_center_x
        dy = target_y - squid_center_y
        distance = math.hypot(dx, dy)  # More efficient than math.sqrt
        
        if distance > 5:  # Small threshold to prevent micro-movements
            # Normalize and scale by speed (removed temporary 1.5x boost)
            norm = max(distance, 0.1)  # Avoid division by zero
            move_x = (dx/norm) * self.base_squid_speed * self.animation_speed
            move_y = (dy/norm) * self.base_vertical_speed * self.animation_speed
            
            # Update position
            self.squid_x += move_x
            self.squid_y += move_y
            
            # Update direction - more precise handling
            if abs(move_x) > abs(move_y):
                self.squid_direction = "right" if move_x > 0 else "left"
            else:
                self.squid_direction = "down" if move_y > 0 else "up"
            
            # Enforce boundaries
            self.squid_x = max(50, min(self.squid_x, self.ui.window_width - 50 - self.squid_width))
            self.squid_y = max(50, min(self.squid_y, self.ui.window_height - 120 - self.squid_height))
            
            # Update graphics
            self.squid_item.setPos(self.squid_x, self.squid_y)
            self.current_frame = (self.current_frame + 1) % 2
            self.update_squid_image()  # Changed to use method instead of direct pixmap set
        
        return distance