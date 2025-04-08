import math
import time
import random
import os
from PyQt5 import QtCore, QtWidgets, QtGui

class RockInteractionManager:
    def __init__(self, squid, logic, scene, message_callback, config_manager):
        self.squid = squid
        self.logic = logic
        self.scene = scene
        self.show_message = message_callback
        self.config_manager = config_manager
        self.rock_config = config_manager.get_rock_config()

        # Rock interaction state
        self.target_rock = None
        self.rock_test_phase = 0  # 0=approach, 1=carry, 2=throw
        self.rock_carry_time = 0
        self.rock_carry_duration = 0
        
        # Initialize timers
        self.rock_test_timer = QtCore.QTimer()
        self.throw_animation_timer = QtCore.QTimer()
        
        # Connect timers
        self.rock_test_timer.timeout.connect(self.update_rock_test)
        self.throw_animation_timer.timeout.connect(self.update_throw_animation)
        
        # Initialize throw velocity variables
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0

        # Add multiplayer support
        self.multiplayer_plugin = None
        self.setup_multiplayer_integration()

    def setup_multiplayer_integration(self):
        """Set up hooks for multiplayer integration"""
        if not hasattr(self.logic, 'plugin_manager'):
            return False
            
        # Get multiplayer plugin
        multiplayer_plugin = None
        for plugin_name, plugin_data in self.logic.plugin_manager.plugins.items():
            if plugin_name == "multiplayer_plugin":
                # Get the actual plugin instance
                multiplayer_plugin = plugin_data.get('instance')
                break
        
        if multiplayer_plugin:
            # Store reference
            self.multiplayer_plugin = multiplayer_plugin
            
            print("[RockInteraction] Successfully integrated with multiplayer plugin")
            return True
        
        return False

    def is_valid_rock(self, item):
        """Check if item is a valid rock"""
        if not isinstance(item, QtWidgets.QGraphicsPixmapItem):
            return False
        return (hasattr(item, 'category') and item.category == 'rock') or \
               (hasattr(item, 'filename') and 'rock' in item.filename.lower())

    def can_pick_up_rock(self, rock):
        """Check if squid can pick up this rock"""
        if not self.is_valid_rock(rock):
            return False
        if hasattr(rock, 'is_being_carried') and rock.is_being_carried:
            return False
        return True

    def attach_rock_to_squid(self, rock):
        """Visually attach rock to squid at tentacle position"""
        rock.setParentItem(self.squid.squid_item)
        
        # Set random hold duration between 3-9 seconds
        self.squid.rock_hold_duration = random.uniform(3.0, 9.0)
        self.squid.rock_hold_start_time = time.time()
        self.squid.rock_decision_made = False
        
        offset = -50  # Both vertical and horizontal offset
        
        # Calculate position based on squid direction
        if self.squid.squid_direction == "right":
            # Position rock near right tentacles
            rock.setPos(self.squid.squid_width - 40 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "left":
            # Position rock near left tentacles
            rock.setPos(10 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "up":
            # Position rock near upper tentacles
            rock.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 40 + offset)
        else:  # down/default
            rock.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 20 + offset)
        
        rock.is_being_carried = True
        self.squid.is_carrying_rock = True
        self.squid.carried_rock = rock
        rock.setZValue(self.squid.squid_item.zValue() + 1)
        
        # Scale rock to appropriate size
        rock.setScale(1.0)
        
        # Debug output
        #print(f"Rock positioned at: {rock.pos()} (Offset: {offset})")
        #print(f"Squid direction: {self.squid.squid_direction}")
        
        return True
    
    def check_rock_hold_time(self):
        """Check if holding time elapsed and make decision"""
        if not hasattr(self.squid, 'carrying_rock') or not self.squid.carrying_rock or not hasattr(self.squid, 'rock_decision_made') or self.squid.rock_decision_made:
            return
        
        current_time = time.time()
        if current_time - self.squid.rock_hold_start_time >= self.squid.rock_hold_duration:
            self.squid.rock_decision_made = True
            self.decide_rock_action()

    def decide_rock_action(self):
        """Randomly decide to throw or drop the rock"""
        if random.random() < 0.7:  # 70% chance to throw
            direction = "right" if random.random() < 0.5 else "left"
            self.throw_rock(direction)
            if self.show_message:
                self.show_message("Squid threw the rock!")
        else:  # 30% chance to drop
            self.drop_rock()
            if self.show_message:
                self.show_message("Squid dropped the rock")

    def drop_rock(self):
        """Gently place the rock below the squid"""
        if not hasattr(self.squid, 'carrying_rock') or not self.squid.carrying_rock or not hasattr(self.squid, 'carried_rock') or not self.squid.carried_rock:
            return
        
        rock = self.squid.carried_rock
        rock.setParentItem(None)
        rock.setPos(
            self.squid.squid_x + self.squid.squid_width//2 - rock.boundingRect().width()//2,
            self.squid.squid_y + self.squid.squid_height + 10
        )
        self.squid.is_carrying_rock = False
        self.squid.carried_rock = None

    def start_rock_test(self, rock=None):
        """Start test with guaranteed clean state and random carry duration"""
        self.cleanup()  # Reset everything first
        
        if rock is None:
            rocks = [item for item in self.scene.items() 
                    if self.is_valid_rock(item) and item.isVisible()]
            if not rocks:
                if self.show_message:
                    self.show_message("No available rocks!")
                return False
            rock = min(rocks, key=lambda r: math.hypot(
                r.sceneBoundingRect().center().x() - self.squid.squid_x,
                r.sceneBoundingRect().center().y() - self.squid.squid_y
            ))
        
        self.target_rock = rock
        self.rock_test_phase = 0
        # Use the config values for duration
        self.rock_carry_duration = random.uniform(
            self.rock_config['min_carry_duration'],
            self.rock_config['max_carry_duration']
        )
        self.rock_carry_time = 0  # Reset carry timer
        self.rock_test_timer.start(100)  # 100ms updates
        return True

    def highlight_rock(self, rock):
        """Visual feedback for selected rock"""
        highlight = QtWidgets.QGraphicsOpacityEffect()
        highlight.setOpacity(0.3)  # Initial opacity
        rock.setGraphicsEffect(highlight)
        
        # Animate highlight
        self.animate_highlight(highlight)

    def animate_highlight(self, highlight_effect):
        """Pulse animation for rock highlight"""
        self.highlight_animation = QtCore.QPropertyAnimation(highlight_effect, b"opacity")
        self.highlight_animation.setDuration(1000)
        self.highlight_animation.setStartValue(0.3)
        self.highlight_animation.setEndValue(0.8)
        self.highlight_animation.setLoopCount(3)
        self.highlight_animation.start()

    def throw_rock(self, direction="right"):
        """Initiates a rock throw with positive memory formation"""
        # Prevent multiple throws
        if self.throw_animation_timer.isActive():
            return False
            
        if not hasattr(self.squid, 'carried_rock') or not self.squid.carried_rock:
            return False
        
        config = self.rock_config
        rock = self.squid.carried_rock
        
        # Set squid status to throwing rock
        if hasattr(self.squid, 'status'):
            self.squid.status = "throwing_rock"
        
        # Detach from squid and reset parent to scene
        rock.setParentItem(None)
        
        # Calculate throw vectors
        throw_power = 12  # Increased from 8
        angle = math.radians(30 if direction == "right" else 150)
        self.throw_velocity_x = throw_power * math.cos(angle)
        self.throw_velocity_y = -throw_power * math.sin(angle)  # Negative for upward
        
        # Set position to squid's center in scene coordinates
        squid_rect = self.squid.squid_item.sceneBoundingRect()
        rock_rect = rock.boundingRect()
        rock.setPos(
            squid_rect.center().x() - rock_rect.width()/2,
            squid_rect.center().y() - rock_rect.height()/2
        )
        
        rock.setVisible(True)
        
        # Apply stat changes
        self.squid.happiness = min(100, self.squid.happiness + config['happiness_boost'])
        self.squid.satisfaction = min(100, self.squid.satisfaction + config['satisfaction_boost'])
        self.squid.anxiety = max(0, self.squid.anxiety - config['anxiety_reduction'])
        
        # Simplified positive memory
        memory_details = {
            "activity": "rock_throwing",
            "effects": {
                "happiness": config['happiness_boost'],
                "satisfaction": config['satisfaction_boost'],
                "anxiety": -config['anxiety_reduction']
            },
            "description": "Had fun throwing a rock!",
            "is_positive": True
        }
        
        # Add with high importance (7) and positive formatting
        self.squid.memory_manager.add_short_term_memory(
            'play',
            'rock_throwing',
            memory_details,
            importance=7
        )
        
        # Broadcast to network if multiplayer plugin is available
        if hasattr(self, 'multiplayer_plugin') and self.multiplayer_plugin:
            try:
                self.multiplayer_plugin.throw_rock_network(rock, direction)
            except Exception as e:
                print(f"[RockInteraction] Error broadcasting rock throw: {e}")
        
        self.throw_animation_timer.start(50)
        return True

    def update_rock_test(self):
        """Handle the rock test sequence (approach, carry)"""
        if not self.target_rock:
            self.cleanup()
            return
        
        # Let the Squid class handle the timing and decision making
        if self.rock_test_phase == 0:  # Approach phase
            rock_center = self.target_rock.sceneBoundingRect().center()
            squid_center = self.squid.squid_item.sceneBoundingRect().center()
            distance = math.hypot(rock_center.x()-squid_center.x(),
                                rock_center.y()-squid_center.y())

            if distance < 50:  # Close enough to pick up
                if self.attach_rock_to_squid(self.target_rock):
                    self.rock_test_phase = 1  # Move to carry phase
                else:
                    self.cleanup()
            else:
                self.squid.move_toward_position(rock_center)

    def update_throw_animation(self):
        """Handles the physics update for thrown rocks"""
        if not hasattr(self.squid, 'carried_rock') or not self.squid.carried_rock:
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
            return
        
        rock = self.squid.carried_rock
        new_x = rock.x() + self.throw_velocity_x
        new_y = rock.y() + self.throw_velocity_y
        
        # Apply gravity (reduced from 0.5 to 0.3 for slower descent)
        self.throw_velocity_y += 0.3
        
        # Boundary checks
        scene_rect = self.scene.sceneRect()
        rock_rect = rock.boundingRect()
        
        # Left/right boundaries with reduced bounce
        if new_x < scene_rect.left():
            new_x = scene_rect.left()
            self.throw_velocity_x *= -0.5  # Reduced from -0.7
        elif new_x > scene_rect.right() - rock_rect.width():
            new_x = scene_rect.right() - rock_rect.width()
            self.throw_velocity_x *= -0.5
        
        # Top/bottom boundaries
        if new_y < scene_rect.top():
            new_y = scene_rect.top()
            self.throw_velocity_y *= -0.5  # Reduced bounce
        elif new_y > scene_rect.bottom() - rock_rect.height():
            new_y = scene_rect.bottom() - rock_rect.height()
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
            return  # Stop updates when hitting bottom
        
        rock.setPos(new_x, new_y)

    def cleanup(self):
        """Reset all rock interaction state"""
        self.rock_test_timer.stop()
        self.throw_animation_timer.stop()
        
        self.target_rock = None
        self.rock_test_phase = 0
        self.rock_carry_time = 0
        self.rock_carry_duration = 0
        
        if hasattr(self.squid, 'is_carrying_rock') and self.squid.is_carrying_rock:
            self.squid.is_carrying_rock = False
            self.squid.carried_rock = None

    def cleanup_after_throw(self):
        if hasattr(self.squid, 'carried_rock') and self.squid.carried_rock:
            # Make sure to reset all rock-related states
            self.squid.carried_rock.is_being_carried = False
            self.squid.carried_rock = None
        
        # Reset squid states
        self.squid.is_carrying_rock = False
        
        # Reset status to default if it was set to "throwing_rock"
        if hasattr(self.squid, 'status') and self.squid.status == "throwing_rock":
            self.squid.status = "roaming"
        
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0
        self.cleanup()

    def setup_timers(self, interval=100):
        """Configure timer intervals"""
        self.rock_test_timer.setInterval(interval)
        self.throw_animation_timer.setInterval(50)

    # === MULTIPLAYER EXTENSIONS ===

    def handle_remote_rock_throw(self, source_node_id, rock_data):
        """Handle a rock throw from a remote squid"""
        try:
            # Extract rock data
            rock_filename = rock_data.get('rock_filename')
            direction = rock_data.get('direction')
            initial_pos = rock_data.get('initial_pos')
            
            # Skip if missing required data
            if not all([rock_filename, direction, initial_pos]):
                print(f"Incomplete remote rock throw data: {rock_data}")
                return
            
            # Ensure initial_pos is a dict
            if not isinstance(initial_pos, dict):
                initial_pos = {'x': initial_pos[0], 'y': initial_pos[1]} if isinstance(initial_pos, (list, tuple)) else {}
            
            # Find existing rock or create new one
            rock = self._find_or_create_remote_rock(rock_filename, initial_pos)
            
            if rock:
                # Mark as a remote rock
                rock.is_remote = True
                
                # Simulate the throw
                self._simulate_remote_rock_throw(rock, direction)
                
                # Check if our squid is in the path of the thrown rock
                self._check_rock_collision_path(rock, direction, source_node_id)
                
                # Show message
                if self.show_message:
                    self.show_message(f"Remote squid ({source_node_id[-4:]}) threw a rock {direction}!")
            
        except Exception as e:
            print(f"Error handling remote rock throw: {e}")
            import traceback
            traceback.print_exc()
    
    def _find_or_create_remote_rock(self, filename, pos):
        """Find an existing rock or create a new one for remote throws"""
        # Get position values
        pos_x = pos.get('x', 0)
        pos_y = pos.get('y', 0)
        
        # Look for existing rocks with same filename near position
        for item in self.scene.items():
            if (hasattr(item, 'filename') and item.filename == filename and
                abs(item.pos().x() - pos_x) < 50 and
                abs(item.pos().y() - pos_y) < 50):
                return item
        
        # Create new rock if not found
        try:
            # Check if file exists
            if not os.path.exists(filename):
                # Try to find a default rock
                default_rocks = [
                    "images/decoration/rock01.png",
                    "images/decoration/rock02.png",
                    "images/rock.png"
                ]
                
                # Use first valid file
                for rock_file in default_rocks:
                    if os.path.exists(rock_file):
                        filename = rock_file
                        break
                else:
                    print(f"Could not find a valid rock image file")
                    return None
            
            rock_pixmap = QtGui.QPixmap(filename)
            
            # Create ResizablePixmapItem if available
            ResizablePixmapItem = None
            if hasattr(self.logic, 'user_interface') and hasattr(self.logic.user_interface, 'ResizablePixmapItem'):
                ResizablePixmapItem = self.logic.user_interface.ResizablePixmapItem
            
            if ResizablePixmapItem:
                rock = ResizablePixmapItem(rock_pixmap, filename)
            else:
                rock = QtWidgets.QGraphicsPixmapItem(rock_pixmap)
                rock.filename = filename
            
            rock.setPos(pos_x, pos_y)
            rock.setOpacity(0.7)  # Make it semi-transparent
            rock.can_be_picked_up = True
            self.scene.addItem(rock)
            
            # Mark as remote rock
            rock.is_remote = True
            
            return rock
        except Exception as e:
            print(f"Error creating remote rock: {e}")
            return None
    
    def _simulate_remote_rock_throw(self, rock, direction):
        """Simulate a remote rock throw with simplified physics"""
        # Create timer for animation
        throw_timer = QtCore.QTimer()
        throw_counter = [0]  # Use list for mutable counter
        
        # Initial velocity based on direction
        velocity_x = 12 * (1 if direction == "right" else -1)
        velocity_y = -10  # Initial upward
        
        def update_position():
            nonlocal velocity_x, velocity_y
            
            # Update position
            current_pos = rock.pos()
            new_x = current_pos.x() + velocity_x
            new_y = current_pos.y() + velocity_y
            
            # Apply gravity
            velocity_y += 0.4
            
            # Check boundaries
            scene_rect = self.scene.sceneRect()
            rock_rect = rock.boundingRect()
            
            # Left/right boundaries
            if new_x < scene_rect.left():
                new_x = scene_rect.left()
                velocity_x *= -0.5
            elif new_x > scene_rect.right() - rock_rect.width():
                new_x = scene_rect.right() - rock_rect.width()
                velocity_x *= -0.5
            
            # Top/bottom boundaries
            if new_y < scene_rect.top():
                new_y = scene_rect.top()
                velocity_y *= -0.5
            elif new_y > scene_rect.bottom() - rock_rect.height():
                new_y = scene_rect.bottom() - rock_rect.height()
                throw_timer.stop()
                return
            
            # Update position
            rock.setPos(new_x, new_y)
            
            # Stop after some time
            throw_counter[0] += 1
            if throw_counter[0] > 100:  # Stop after 100 updates
                throw_timer.stop()
        
        # Start animation
        throw_timer.timeout.connect(update_position)
        throw_timer.start(50)  # 50ms intervals
    
    def _check_rock_collision_path(self, rock, direction, source_node_id):
        """Check if our squid is in the path of a thrown rock"""
        # Skip if squid isn't initialized
        if not self.squid:
            return
        
        # Get rock and squid positions
        rock_pos = rock.pos()
        squid_rect = self.squid.squid_item.sceneBoundingRect()
        squid_center = squid_rect.center()
        
        # Calculate relative positions
        dx = squid_center.x() - rock_pos.x()
        dy = squid_center.y() - rock_pos.y()
        distance = math.sqrt(dx*dx + dy*dy)
        
        # Check if squid is in the direction of throw
        in_path = (direction == "right" and dx > 0) or (direction == "left" and dx < 0)
        
        # If squid is close enough and in the throw path, react
        if distance < 200 and in_path:
            if hasattr(self.squid, 'react_to_rock_throw'):
                # Use the specialized reaction method
                self.squid.react_to_rock_throw(source_node_id, True)
            elif hasattr(self.logic, 'startle_squid'):
                # Fallback to generic startle
                self.logic.startle_squid(source="incoming_rock")
                
                # Add memory
                if hasattr(self.squid, 'memory_manager'):
                    self.squid.memory_manager.add_short_term_memory(
                        'observation', 'rock_thrown',
                        f"Startled by rock thrown by remote squid ({source_node_id[-4:]})"
                    )