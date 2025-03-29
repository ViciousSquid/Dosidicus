import math
import random
from PyQt5 import QtCore, QtWidgets, QtGui

class RockInteractionManager:
    def __init__(self, squid, logic, scene, message_callback):
        """
        Initialize rock interaction system
        
        Args:
            squid: Reference to Squid instance
            logic: Reference to TamagotchiLogic
            scene: QGraphicsScene reference
            message_callback: Function to display messages
        """
        self.squid = squid
        self.logic = logic
        self.scene = scene
        self.show_message = message_callback

        # Rock interaction state
        self.target_rock = None
        self.rock_test_phase = 0  # 0=approach, 1=carry, 2=throw
        self.rock_carry_time = 0
        
        # Initialize timers
        self.rock_test_timer = QtCore.QTimer()
        self.throw_animation_timer = QtCore.QTimer()
        
        # Connect timers
        self.rock_test_timer.timeout.connect(self.update_rock_test)  # Fixed: was connected to start_rock_test
        self.throw_animation_timer.timeout.connect(self.update_throw_animation)
        
        # Initialize throw velocity variables
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0

    # Core rock interaction methods
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
        """Visually attach rock to squid"""
        rock.setParentItem(self.squid.squid_item)
        rock.setPos(20, -10)  # Relative to squid
        rock.is_being_carried = True
        self.squid.is_carrying_rock = True
        self.squid.carried_rock = rock
        rock.setZValue(self.squid.squid_item.zValue() + 1)

    # Test control methods
    def start_rock_test(self, rock=None):
        """Start test with guaranteed clean state"""
        self.cleanup()  # Critical - reset everything first
        
        if rock is None:
            rocks = [item for item in self.scene.items() 
                    if self.is_valid_rock(item) and item.isVisible()]
            if not rocks:
                self.show_message("No available rocks!")
                return
            rock = min(rocks, key=lambda r: math.hypot(
                r.sceneBoundingRect().center().x() - self.squid.squid_x,
                r.sceneBoundingRect().center().y() - self.squid.squid_y
            ))
        
        self.target_rock = rock
        self.rock_test_phase = 0
        self.rock_test_timer.start(100)

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
        """Initiates a rock throw"""
        if not hasattr(self.squid, 'carried_rock') or not self.squid.carried_rock:
            return False
        
        rock = self.squid.carried_rock
        rock.setParentItem(None)
        
        # Calculate throw vectors
        throw_power = 15
        angle = math.radians(30 if direction == "right" else 150)
        self.throw_velocity_x = throw_power * math.cos(angle)
        self.throw_velocity_y = -throw_power * math.sin(angle)
        
        # Set initial position
        rock.setPos(
            self.squid.squid_x + (self.squid.squid_width/2),
            self.squid.squid_y - 20
        )
        
        # Make rock visible
        rock.setVisible(True)
        
        # Start animation
        self.throw_animation_timer.start(50)  # 50ms updates
        return True

    def update_rock_test(self):
        """Handle the rock test sequence (approach, carry, throw)"""
        if not self.target_rock:
            self.cleanup()
            return
        
        rock = self.target_rock
        rock_center = rock.sceneBoundingRect().center()
        squid_center = self.squid.squid_item.sceneBoundingRect().center()
        distance = math.hypot(rock_center.x()-squid_center.x(),
                             rock_center.y()-squid_center.y())

        if self.rock_test_phase == 0:  # Approach
            if distance < 50:
                if self.squid.pick_up_rock(rock):
                    self.rock_test_phase = 1
                    self.rock_carry_time = 30
                else:
                    self.cleanup()
            else:
                self.squid.move_toward_position(rock_center)
                
        elif self.rock_test_phase == 1:  # Carry
            self.rock_carry_time -= 1
            if self.rock_carry_time <= 0:
                self.throw_rock("right" if random.random() < 0.5 else "left")
                self.rock_test_phase = 2

    def update_throw_animation(self):
        """Handles the physics update for thrown rocks"""
        if not hasattr(self.squid, 'carried_rock') or not self.squid.carried_rock:
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
            return
        
        rock = self.squid.carried_rock
        new_x = rock.x() + self.throw_velocity_x
        new_y = rock.y() + self.throw_velocity_y
        
        # Apply gravity
        self.throw_velocity_y += 0.5
        
        # Boundary checks
        scene_rect = self.scene.sceneRect()
        rock_rect = rock.boundingRect()
        
        # Left/right boundaries
        if new_x < scene_rect.left():
            new_x = scene_rect.left()
            self.throw_velocity_x *= -0.7  # Bounce with energy loss
        elif new_x > scene_rect.right() - rock_rect.width():
            new_x = scene_rect.right() - rock_rect.width()
            self.throw_velocity_x *= -0.7
        
        # Top/bottom boundaries
        if new_y < scene_rect.top():
            new_y = scene_rect.top()
            self.throw_velocity_y *= -0.7
        elif new_y > scene_rect.bottom() - rock_rect.height():
            new_y = scene_rect.bottom() - rock_rect.height()
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
        
        rock.setPos(new_x, new_y)

    # Cleanup methods
    def cleanup(self):
        """Minimal cleanup since rock gets thrown to new position"""
        # Stop timers
        self.rock_test_timer.stop()
        self.throw_animation_timer.stop()
        
        # Reset state variables
        self.target_rock = None
        self.rock_test_phase = 0
        self.rock_carry_time = 0
        
        # Only reset squid's carrying state if still carrying
        if hasattr(self.squid, 'is_carrying_rock') and self.squid.is_carrying_rock:
            self.squid.is_carrying_rock = False
            self.squid.carried_rock = None

    def setup_timers(self, interval=100):
        """Configure timer intervals"""
        self.rock_test_timer.setInterval(interval)
        self.throw_animation_timer.setInterval(50)

    def cleanup_after_throw(self):
        """Cleans up after a throw is complete"""
        if hasattr(self.squid, 'carried_rock') and self.squid.carried_rock:
            self.squid.carried_rock = None
        if hasattr(self.squid, 'is_carrying_rock'):
            self.squid.is_carrying_rock = False
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0