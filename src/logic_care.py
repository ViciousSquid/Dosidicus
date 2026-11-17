"""What the caretaker does: feeding, cleaning and medicine - and the food and
poop that move about the tank as a result.
"""
import logging
from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import time
from .squid import Personality
from .ui import ResizablePixmapItem

_LOG = logging.getLogger(__name__)


class CareActionsMixin:
    """Part of TamagotchiLogic (see tamagotchi_logic.py); not used on its own."""

    def check_collision_with_cheese(self, cheese_item):
        if self.squid.personality == Personality.STUBBORN:
            return False  # Stubborn squids never collide with cheese
        
        squid_rect = self.squid.boundingRect().translated(self.squid.squid_x, self.squid.squid_y)
        cheese_rect = cheese_item.boundingRect().translated(cheese_item.pos())
        
        return squid_rect.intersects(cheese_rect)

    def _set_sickness_state(self, is_sick):
        """Keep squid state, mental-state visuals, and transition stats aligned."""
        if self.squid is None:
            return

        is_sick = bool(is_sick)
        self.squid.is_sick = is_sick

        mental_state_manager = getattr(self.squid, 'mental_state_manager', None)
        if mental_state_manager:
            mental_state_manager.set_state("sick", is_sick)

        # Innate reflex: falling ill teaches the squid about filth immediately.
        if is_sick and getattr(self, 'hebbian_learning', None) is not None:
            try:
                self.hebbian_learning.learn_from_sickness()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Reflex] learn_from_sickness failed: {type(e).__name__}: {e}")

        statistics = getattr(self.squid, 'statistics', None)
        if statistics:
            statistics.record_sickness_state(is_sick)

    def give_medicine(self):
        
        # Get plugin results
        bw = getattr(self.brain_window, 'brain_widget', None)
        if bw is not None and hasattr(bw, 'provide_outcome_feedback'):
            bw.provide_outcome_feedback(0.4, "it was given medicine")

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
            self._set_sickness_state(False)
            
            self.squid.happiness = max(0, self.squid.happiness - 30)
            self.squid.sleepiness = min(100, self.squid.sleepiness + 50)
            self.statistics_window.award(-100)
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
        from .display_scaling import DisplayScaling
        needle_pixmap = DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "needle.jpg")))
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
            if self.squid.eat(cheese_item):
                # Reset status after a short delay
                QtCore.QTimer.singleShot(2000, self.reset_squid_status)

    def move_sushi(self, sushi_item):
        sushi_x = sushi_item.pos().x()
        sushi_y = sushi_item.pos().y() + (self.base_food_speed * self.simulation_speed)

        if sushi_y > self.user_interface.window_height - 120 - self.food_height:
            sushi_y = self.user_interface.window_height - 120 - self.food_height

        sushi_item.setPos(sushi_x, sushi_y)

        if self.squid is not None and sushi_item.collidesWithItem(self.squid.squid_item):
            # A squid that does not eat leaves the sushi where it is.
            if self.squid.eat(sushi_item):
                self.remove_food(sushi_item)

                # Reset status after a short delay (matching cheese behavior)
                QtCore.QTimer.singleShot(2000, self.reset_squid_status)

    def is_sushi(self, food_item):
        return getattr(food_item, 'is_sushi', False)     

    def remove_food(self, food_item):
        if food_item in self.food_items:
            self.user_interface.scene.removeItem(food_item)
            self.food_items.remove(food_item)

            # Notify vision worker of scene change
            if hasattr(self.squid, 'mark_scene_objects_dirty'):
                self.squid.mark_scene_objects_dirty()

    def move_poops(self):
        for poop_item in self.poop_items[:]:
            poop_x = poop_item.pos().x()
            poop_y = poop_item.pos().y() + (self.base_food_speed * self.simulation_speed)

            if poop_y > self.user_interface.window_height - 120 - self.squid.poop_height:
                poop_y = self.user_interface.window_height - 120 - self.squid.poop_height

            poop_item.setPos(poop_x, poop_y)

    def feed_squid(self):
        """Modified to track action for neurogenesis"""
        # Track for neurogenesis FIRST
        if hasattr(self.brain_window, 'brain_widget') and \
           hasattr(self.brain_window.brain_widget, 'enhanced_neurogenesis'):
            self.brain_window.brain_widget.enhanced_neurogenesis.track_action('user_feeding')
        
        self.track_action('feeding')  # Keep original tracking
        self.brain_hooks.on_user_interaction('feed')
        
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

        if self.squid.hunger < 50:  # Feeding was successful
            self.brain_window.brain_widget.provide_outcome_feedback(1.0)

    def spawn_food(self, is_sushi=False):
        if len(self.food_items) >= self.max_food:
            return
        
        # Create only one food item
        from .display_scaling import DisplayScaling
        if is_sushi:
            food_pixmap = DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "sushi.png")))
            food_item = QtWidgets.QGraphicsPixmapItem(food_pixmap)
            food_item.is_sushi = True
        else:
            food_pixmap = DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "cheese.png")))
            food_item = QtWidgets.QGraphicsPixmapItem(food_pixmap)
            food_item.is_sushi = False

        food_x = random.randint(50, self.user_interface.window_width - 50 - self.food_width)
        food_item.setPos(food_x, 50)
        
        # Add to scene and tracking list
        self.user_interface.scene.addItem(food_item)
        self.food_items.append(food_item)  # Single addition
        self.brain_hooks.on_object_spawned('food')

        # Notify vision worker of scene change
        if hasattr(self.squid, 'mark_scene_objects_dirty'):
            self.squid.mark_scene_objects_dirty()

    def clean_environment(self):
        # Track for neurogenesis FIRST
        if hasattr(self.brain_window, 'brain_widget') and \
        hasattr(self.brain_window.brain_widget, 'enhanced_neurogenesis'):
            self.brain_window.brain_widget.enhanced_neurogenesis.track_action('user_cleaning')

        self.brain_hooks.on_user_interaction('clean')
        
        self.track_action('cleaning')
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

        items_removed = False

        # Remove poops and food that the line has passed
        for poop_item in self.poop_items[:]:
            if poop_item.scenePos().x() > new_x:
                self.user_interface.scene.removeItem(poop_item)
                self.poop_items.remove(poop_item)
                items_removed = True

        for food_item in self.food_items[:]:
            if food_item.pos().x() > new_x:
                self.remove_food(food_item) # This calls mark_scene_objects_dirty internally
                items_removed = True

        # Force an update of the scene
        self.user_interface.scene.update()

        # Explicitly notify if we removed poop (food handled by remove_food)
        if items_removed and hasattr(self.squid, 'mark_scene_objects_dirty'):
            self.squid.mark_scene_objects_dirty()

    def finish_cleaning(self):
        # 1. remove the cleaning line (existing)
        self.user_interface.scene.removeItem(self.cleaning_line)

        # 2. count poops actually removed & award
        poops_removed = 0
        for poop_item in self.poop_items[:]:
            if not poop_item.scene():   # already erased by the swipe
                poops_removed += 1
        if poops_removed:
            self.statistics_window.award(25 * poops_removed)   # 25 per poop

        # 3. rest unchanged …
        if self.squid:
            self.squid.cleanliness = 100
            self.squid.happiness = min(100, self.squid.happiness + 20)
            self.squid.memory_manager.add_short_term_memory(
                'cleanliness', 'washed_clean',
                'Washed clean! Feeling fresh.',
                importance=3
            )
        
            bw = getattr(self.brain_window, 'brain_widget', None)
            if bw is not None and hasattr(bw, 'provide_outcome_feedback'):
                bw.provide_outcome_feedback(0.3, "the tank was cleaned")

            # Innate reflex: a clean tank is an unconditioned good.
            if getattr(self, 'hebbian_learning', None) is not None:
                try:
                    self.hebbian_learning.learn_from_organization()
                except Exception as e:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"[Reflex] learn_from_organization failed: "
                          f"{type(e).__name__}: {e}")

        # Clear all DIRTY text immediately when cleaned
        self.user_interface.clear_dirty_text()
        
        self.show_message("Environment cleaned! Squid is happier!")
        self.user_interface.scene.update()

    def update_cleanliness_overlay(self):
        if self.squid is not None:
            cleanliness = self.squid.cleanliness
            # Use the new DIRTY text system instead of brown overlay
            self.user_interface.update_dirty_text(cleanliness)
            # Keep the overlay transparent (no more brown color)
            self.user_interface.cleanliness_overlay.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, 0)))

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

            # Notify vision worker of scene change
            if hasattr(self.squid, 'mark_scene_objects_dirty'):
                self.squid.mark_scene_objects_dirty()

    def spawn_poop(self, x, y):
        if len(self.poop_items) < self.max_poop and self.squid is not None:
            poop_item = ResizablePixmapItem(self.squid.poop_images[0], category='poop')
            poop_item.setPos(x - self.squid.poop_width // 2, y)
            self.user_interface.scene.addItem(poop_item)
            self.poop_items.append(poop_item)
            self.brain_hooks.on_object_spawned('poop')

            # Notify vision worker of scene change
            if hasattr(self.squid, 'mark_scene_objects_dirty'):
                self.squid.mark_scene_objects_dirty()
            return True
        return False

    def animate_poops(self):
        if self.squid is not None:
            # enumerate() gives the index directly – avoids an O(n) list.index()
            # lookup per item (previously O(n^2) over all poops each tick).
            for index, poop_item in enumerate(self.poop_items):
                current_frame = index % 2
                poop_item.setPixmap(self.squid.poop_images[current_frame])
