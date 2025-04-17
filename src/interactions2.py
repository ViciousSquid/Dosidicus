import math
import time
import random
import os
from PyQt5 import QtCore, QtWidgets, QtGui

class PoopInteractionManager:
    def __init__(self, squid, logic, scene, message_callback, config_manager):
        self.squid = squid
        self.logic = logic
        self.scene = scene
        self.show_message = message_callback
        self.config_manager = config_manager
        self.poop_config = config_manager.get_poop_config()

        # Poop interaction state
        self.target_poop = None
        self.poop_test_phase = 0  # 0=approach, 1=carry, 2=throw
        self.poop_carry_time = 0
        self.poop_carry_duration = 0
        
        # Initialize timers
        self.poop_test_timer = QtCore.QTimer()
        self.throw_animation_timer = QtCore.QTimer()
        
        # Connect timers
        self.poop_test_timer.timeout.connect(self.update_poop_test)
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
            
            print("[PoopInteraction] Successfully integrated with multiplayer plugin")
            return True
        
        return False

    def is_valid_poop(self, item):
        """Check if item is a valid poop"""
        if not isinstance(item, QtWidgets.QGraphicsPixmapItem):
            return False
        return (hasattr(item, 'category') and item.category == 'poop') or \
               (hasattr(item, 'filename') and 'poop' in item.filename.lower())

    def can_pick_up_poop(self, poop):
        """Check if squid can pick up this poop"""
        if not self.is_valid_poop(poop):
            return False
        if hasattr(poop, 'is_being_carried') and poop.is_being_carried:
            return False
        return True

    def attach_poop_to_squid(self, poop):
        """Visually attach poop to squid at tentacle position"""
        poop.setParentItem(self.squid.squid_item)
        
        # Set random hold duration between 3-9 seconds
        self.squid.poop_hold_duration = random.uniform(3.0, 9.0)
        self.squid.poop_hold_start_time = time.time()
        self.squid.poop_decision_made = False
        
        offset = -50  # Both vertical and horizontal offset
        
        # Calculate position based on squid direction
        if self.squid.squid_direction == "right":
            # Position poop near right tentacles
            poop.setPos(self.squid.squid_width - 40 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "left":
            # Position poop near left tentacles
            poop.setPos(10 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "up":
            # Position poop near upper tentacles
            poop.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 40 + offset)
        else:  # down/default
            poop.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 20 + offset)
        
        poop.is_being_carried = True
        self.squid.is_carrying_poop = True
        self.squid.carried_poop = poop
        poop.setZValue(self.squid.squid_item.zValue() + 1)
        
        # Scale poop to appropriate size
        poop.setScale(1.0)
        
        return True
    
    def check_poop_hold_time(self):
        """Check if holding time elapsed and make decision"""
        if not hasattr(self.squid, 'carrying_poop') or not self.squid.carrying_poop or not hasattr(self.squid, 'poop_decision_made') or self.squid.poop_decision_made:
            return
        
        current_time = time.time()
        if current_time - self.squid.poop_hold_start_time >= self.squid.poop_hold_duration:
            self.squid.poop_decision_made = True
            self.decide_poop_action()

    def decide_poop_action(self):
        """Randomly decide to throw or drop the poop"""
        if random.random() < 0.7:  # 70% chance to throw
            direction = "right" if random.random() < 0.5 else "left"
            self.throw_poop(direction)
            if self.show_message:
                self.show_message("Squid threw the poop!")
        else:  # 30% chance to drop
            self.drop_poop()
            if self.show_message:
                self.show_message("Squid dropped the poop")

    def drop_poop(self):
        """Gently place the poop below the squid"""
        if not hasattr(self.squid, 'carrying_poop') or not self.squid.carrying_poop or not hasattr(self.squid, 'carried_poop') or not self.squid.carried_poop:
            return
        
        poop = self.squid.carried_poop
        poop.setParentItem(None)
        poop.setPos(
            self.squid.squid_x + self.squid.squid_width//2 - poop.boundingRect().width()//2,
            self.squid.squid_y + self.squid.squid_height + 10
        )
        self.squid.is_carrying_poop = False
        self.squid.carried_poop = None

    def start_poop_test(self, poop=None):
        """Start test with guaranteed clean state and random carry duration"""
        self.cleanup()  # Reset everything first
        
        if poop is None:
            poops = [item for item in self.scene.items() 
                    if self.is_valid_poop(item) and item.isVisible()]
            if not poops:
                if self.show_message:
                    self.show_message("No available poops!")
                return False
            poop = min(poops, key=lambda p: math.hypot(
                p.sceneBoundingRect().center().x() - self.squid.squid_x,
                p.sceneBoundingRect().center().y() - self.squid.squid_y
            ))
        
        self.target_poop = poop
        self.poop_test_phase = 0
        # Use the config values for duration
        self.poop_carry_duration = random.uniform(
            self.poop_config['min_carry_duration'],
            self.poop_config['max_carry_duration']
        )
        self.poop_carry_time = 0  # Reset carry timer
        self.poop_test_timer.start(100)  # 100ms updates
        return True

    def throw_poop(self, direction="right"):
        """Initiates a poop throw with memory formation"""
        # Prevent multiple throws
        if self.throw_animation_timer.isActive():
            return False
            
        if not hasattr(self.squid, 'carried_poop') or not self.squid.carried_poop:
            return False
        
        config = self.poop_config
        poop = self.squid.carried_poop
        
        # Set squid status to throwing poop
        if hasattr(self.squid, 'status'):
            self.squid.status = "throwing_poop"
        
        # Detach from squid and reset parent to scene
        poop.setParentItem(None)
        
        # Calculate throw vectors
        throw_power = 12
        angle = math.radians(30 if direction == "right" else 150)
        self.throw_velocity_x = throw_power * math.cos(angle)
        self.throw_velocity_y = -throw_power * math.sin(angle)  # Negative for upward
        
        # Set position to squid's center in scene coordinates
        squid_rect = self.squid.squid_item.sceneBoundingRect()
        poop_rect = poop.boundingRect()
        poop.setPos(
            squid_rect.center().x() - poop_rect.width()/2,
            squid_rect.center().y() - poop_rect.height()/2
        )
        
        poop.setVisible(True)
        
        # Apply stat changes
        self.squid.happiness = min(100, self.squid.happiness - 5)
        self.squid.satisfaction = min(100, self.squid.satisfaction - 3)
        self.squid.anxiety = min(100, self.squid.anxiety + 10)
        
        # Simplified negative memory
        memory_details = {
            "activity": "poop_throwing",
            "effects": {
                "happiness": -5,
                "satisfaction": -3,
                "anxiety": 10
            },
            "description": "Threw a poop around!",
            "is_positive": False
        }
        
        # Add with moderate importance
        self.squid.memory_manager.add_short_term_memory(
            'play',
            'poop_throwing',
            memory_details,
            importance=5
        )
        
        # Broadcast to network if multiplayer plugin is available
        if hasattr(self, 'multiplayer_plugin') and self.multiplayer_plugin:
            try:
                self.multiplayer_plugin.throw_poop_network(poop, direction)
            except Exception as e:
                print(f"[PoopInteraction] Error broadcasting poop throw: {e}")
        
        self.throw_animation_timer.start(50)
        return True

    def update_poop_test(self):
        """Handle the poop test sequence (approach, carry)"""
        if not self.target_poop:
            self.cleanup()
            return
        
        # Let the Squid class handle the timing and decision making
        if self.poop_test_phase == 0:  # Approach phase
            poop_center = self.target_poop.sceneBoundingRect().center()
            squid_center = self.squid.squid_item.sceneBoundingRect().center()
            distance = math.hypot(poop_center.x()-squid_center.x(),
                                poop_center.y()-squid_center.y())

            if distance < 50:  # Close enough to pick up
                if self.attach_poop_to_squid(self.target_poop):
                    self.poop_test_phase = 1  # Move to carry phase
                else:
                    self.cleanup()
            else:
                self.squid.move_toward_position(poop_center)

    def update_throw_animation(self):
        """Handles the physics update for thrown poops"""
        if not hasattr(self.squid, 'carried_poop') or not self.squid.carried_poop:
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
            return
        
        poop = self.squid.carried_poop
        new_x = poop.x() + self.throw_velocity_x
        new_y = poop.y() + self.throw_velocity_y
        
        # Apply gravity
        self.throw_velocity_y += 0.3
        
        # Boundary checks
        scene_rect = self.scene.sceneRect()
        poop_rect = poop.boundingRect()
        
        # Left/right boundaries with reduced bounce
        if new_x < scene_rect.left():
            new_x = scene_rect.left()
            self.throw_velocity_x *= -0.5
        elif new_x > scene_rect.right() - poop_rect.width():
            new_x = scene_rect.right() - poop_rect.width()
            self.throw_velocity_x *= -0.5
        
        # Top/bottom boundaries
        if new_y < scene_rect.top():
            new_y = scene_rect.top()
            self.throw_velocity_y *= -0.5
        elif new_y > scene_rect.bottom() - poop_rect.height():
            new_y = scene_rect.bottom() - poop_rect.height()
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
            return  # Stop updates when hitting bottom
        
        poop.setPos(new_x, new_y)

    def cleanup(self):
        """Reset all poop interaction state"""
        self.poop_test_timer.stop()
        self.throw_animation_timer.stop()
        
        self.target_poop = None
        self.poop_test_phase = 0
        self.poop_carry_time = 0
        self.poop_carry_duration = 0
        
        if hasattr(self.squid, 'is_carrying_poop') and self.squid.is_carrying_poop:
            self.squid.is_carrying_poop = False
            self.squid.carried_poop = None

    def cleanup_after_throw(self):
        if hasattr(self.squid, 'carried_poop') and self.squid.carried_poop:
            # Make sure to reset all poop-related states
            self.squid.carried_poop.is_being_carried = False
            self.squid.carried_poop = None
        
        # Reset squid states
        self.squid.is_carrying_poop = False
        
        # Reset status to default if it was set to "throwing_poop"
        if hasattr(self.squid, 'status') and self.squid.status == "throwing_poop":
            self.squid.status = "roaming"
        
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0
        self.cleanup()

    def setup_timers(self, interval=100):
        """Configure timer intervals"""
        self.poop_test_timer.setInterval(interval)
        self.throw_animation_timer.setInterval(50)