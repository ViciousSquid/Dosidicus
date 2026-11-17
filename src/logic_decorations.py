"""What the decorations in the tank do to the squid: attraction, the effects
of being near them, startles, and what it learns from them.
"""
from PyQt5 import QtCore
import random
import time
from .ui import ResizablePixmapItem


class DecorationLogicMixin:
    """Part of TamagotchiLogic (see tamagotchi_logic.py); not used on its own."""

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
        """
        Get decorations near a position.
        
        PERFORMANCE FIX: Uses cached decoration list to avoid
        iterating through all scene items every frame.
        """
        current_time = time.time()
        
        # Rebuild cache if stale (every 300ms or on first call)
        if (current_time - self._decoration_cache_time > self._decoration_cache_interval
            or not self._decoration_cache):
            self._decoration_cache = []
            for item in self.user_interface.scene.items():
                if isinstance(item, ResizablePixmapItem):
                    # Cache both the item and its center point
                    center = item.sceneBoundingRect().center()
                    self._decoration_cache.append((item, center.x(), center.y()))
            self._decoration_cache_time = current_time
        
        # Filter from cache using squared distance (avoids expensive sqrt)
        nearby_decorations = []
        radius_sq = radius * radius
        for item, cx, cy in self._decoration_cache:
            dist_sq = (cx - x) ** 2 + (cy - y) ** 2
            if dist_sq <= radius_sq:
                nearby_decorations.append(item)
        
        return nearby_decorations

    def invalidate_decoration_cache(self):
        """
        Call this when decorations are added/removed to force cache rebuild.
        """
        self._decoration_cache_time = 0

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

    def _get_cached_decorations(self):
        """Get decorations with caching to avoid scanning scene every tick."""
        current_time = time.time()
        if current_time - self._decoration_cache_time > self._decoration_cache_interval:
            self._decoration_cache = []
            for item in self.user_interface.scene.items():
                if isinstance(item, ResizablePixmapItem) and hasattr(item, 'category'):
                    # Cache both the item and its center point
                    center = item.sceneBoundingRect().center()
                    self._decoration_cache.append((item, center.x(), center.y()))
            self._decoration_cache_time = current_time
        return self._decoration_cache

    def _check_decorations_message(self):
        """Check if we should show the decorations window reminder message"""
        current_time = time.time()
        
        # Only check if we haven't shown the max times and enough time has passed
        if (self.decorations_message_count < self.decorations_message_max and 
            current_time >= self.next_decorations_message_check):
            
            # Show the message
            self.show_message("Press D to open the Decorations window")
            self.decorations_message_count += 1
            self.last_decorations_message_time = current_time
            
            # Schedule next check for 2-5 minutes from now
            self.next_decorations_message_check = current_time + random.randint(
                self.decorations_message_cooldown, 
                self.decorations_message_check_interval
            )
