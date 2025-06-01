import random
import math
import time
import os
from PyQt5 import QtCore, QtGui, QtWidgets

class RemoteSquidController:
    """Controls behavior of squids away from their home instance"""

    def __init__(self, squid_data, scene, plugin_instance=None, debug_mode=False, remote_entity_manager=None): # MODIFIED
        self.squid_data = squid_data.copy()  # Make a copy to avoid reference issues
        self.scene = scene                   # The graphics scene for object detection
        self.plugin_instance = plugin_instance  # ADDED: Store the plugin instance
        self.debug_mode = debug_mode         # Debug flag for verbose logging
        self.remote_entity_manager = remote_entity_manager  # ADDED: Store the entity manager

        # Extract more data from squid_data if available
        self.entry_time = squid_data.get('entry_time', time.time())
        self.entry_position = squid_data.get('entry_position', None) # This should be the calculated entry on *this* screen
        self.window_width = squid_data.get('window_width', 1280)  # Default fallback
        self.window_height = squid_data.get('window_height', 900)  # Default fallback

        # Initialize home direction from squid data or determine later
        # home_direction is crucial for the "returning" state.
        # It should be the direction the squid needs to go to exit THIS screen and return to its origin.
        # mp_plugin_logic.py's handle_squid_exit_message calculates entry_direction_on_this_screen.
        # The opposite of that is the direction to go home.
        entry_dir_on_this_screen = squid_data.get('entry_direction_on_this_screen') # This key is passed in initial_autopilot_data
        if entry_dir_on_this_screen:
            opposite_map = {
                'left': 'right', 'right': 'left',
                'top': 'down', 'bottom': 'up',
                'center_fallback': random.choice(['left', 'right', 'up', 'down']) # Fallback for center entry
            }
            self.home_direction = opposite_map.get(entry_dir_on_this_screen)
        else:
            # Fallback if entry_direction_on_this_screen is not in squid_data for some reason
            self.home_direction = squid_data.get('home_direction', random.choice(['left', 'right', 'up', 'down']))


        # Behavior state - start with exploring after entry
        self.state = "exploring"  # exploring, feeding, interacting, returning
        self.target_object = None # Current target object (food, rock)
        self.time_away = 0        # Time spent in foreign instance

        # Calculate random time before returning home (1-3 minutes)
        self.max_time_away = random.randint(60, 180)

        # Activity tracking
        self.food_eaten_count = 0
        self.rock_interaction_count = 0
        self.distance_traveled = 0

        # Add rock stealing behavior
        self.rocks_stolen = 0
        self.max_rocks_to_steal = random.randint(1, 3)  # Limit how many rocks to steal
        self.stealing_phase = False

        # Movement parameters
        self.move_speed = 5
        self.direction_change_prob = 0.02  # Lower for more natural movement
        self.next_decision_time = 0
        self.decision_interval = 0.5  # Faster decisions for more responsive behavior

        # Initialize timestamp
        self.last_update_time = time.time()

        if self.debug_mode:
            # Corrected access to x and y which are top-level in squid_data for the controller's initial state
            log_x = self.squid_data.get('x', 'N/A') # Initial position when autopilot is created
            log_y = self.squid_data.get('y', 'N/A')
            print(f"[AutoPilot] Initialized for remote squid {self.squid_data.get('node_id', 'UnknownNode')} at ({log_x}, {log_y})")
            print(f"[AutoPilot] Will consider returning home after {self.max_time_away} seconds. Determined home direction: {self.home_direction}")

    def update(self, delta_time=None):
        """Update remote squid behavior"""
        # Calculate time delta if not provided
        current_time = time.time()
        if delta_time is None:
            delta_time = current_time - self.last_update_time
        self.last_update_time = current_time

        # Update time away
        self.time_away += delta_time

        # Only make decisions at certain intervals
        if current_time < self.next_decision_time:
            # Still move in current direction between decisions
            self.move_in_direction(self.squid_data['direction'])
            # Also update the visual representation via entity_manager
            if self.remote_entity_manager:
                self.remote_entity_manager.update_remote_squid(self.squid_data['node_id'], self.squid_data, is_new_arrival=False)
            return

        self.next_decision_time = current_time + self.decision_interval

        # Check if should return home
        if self.time_away > self.max_time_away and self.state != "returning":
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} time to go home: {self.time_away:.1f}s/{self.max_time_away:.1f}s")
            self.state = "returning"
            # self.determine_home_direction() # Home direction is now set at init

        # State machine for squid behavior
        if self.state == "exploring":
            self.explore()
        elif self.state == "feeding":
            self.seek_food()
        elif self.state == "interacting":
            self.interact_with_object()
        elif self.state == "returning":
            self.return_home()

        # After behavior update, ensure the remote_entity_manager updates the visual
        if self.remote_entity_manager:
            self.remote_entity_manager.update_remote_squid(self.squid_data['node_id'], self.squid_data, is_new_arrival=False)


    def explore(self):
        """Random exploration behavior"""
        # Chance to change direction
        if random.random() < self.direction_change_prob:
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Changed direction to {new_direction}")
            self.squid_data['direction'] = new_direction

        # Move in current direction
        self.move_in_direction(self.squid_data['direction'])

        # Chance to spot and pursue food
        if random.random() < 0.1:
            food = self.find_nearby_food()
            if food:
                self.target_object = food
                self.state = "feeding"
                if self.debug_mode:
                    print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} spotted food, switching to feeding state")

        # Chance to spot and interact with rocks
        elif random.random() < 0.05:
            rock = self.find_nearby_rock()
            if rock:
                self.target_object = rock
                self.state = "interacting"
                if self.debug_mode:
                    print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} spotted rock, switching to interacting state")

    def seek_food(self):
        """Move toward and try to eat food"""
        if not self.target_object or not self.is_object_valid(self.target_object):
            # Lost target, go back to exploring
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost food target, returning to exploring")
            self.state = "exploring"
            self.target_object = None
            return

        # Move toward food
        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        # Check if close enough to eat
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)

        if distance < 50:  # Close enough to eat
            self.eat_food(self.target_object)
            self.food_eaten_count += 1
            self.target_object = None
            self.state = "exploring"

            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} ate food, food count: {self.food_eaten_count}")

    def interact_with_object(self):
        """Interact with rocks or other objects, with a chance to steal them"""
        if not self.target_object or not self.is_object_valid(self.target_object):
            # Lost target, go back to exploring
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost rock target, returning to exploring")
            self.state = "exploring"
            self.target_object = None
            return

        # Move toward object
        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        # Check if close enough to interact
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)

        if distance < 50:  # Close enough to interact
            is_remotely_owned = getattr(self.target_object, 'is_remote', False) # Assuming target object might have this attribute
            is_local_rock = not is_remotely_owned # Simplification: if not remote, it's local

            # Regular interaction
            self.rock_interaction_count += 1

            # Try to steal if this is a rock and we haven't reached our limit
            if (self.is_rock(self.target_object) and
                is_local_rock and
                self.rocks_stolen < self.max_rocks_to_steal and
                random.random() < 0.4):  # 40% chance to try stealing

                # Set carrying state
                self.squid_data['carrying_rock'] = True # This state should be part of the squid_data payload
                self.stealing_phase = True

                # Hide the original rock (Visual only, actual object removal/state change should be handled by main logic via plugin_instance if needed)
                # self.target_object.setVisible(False) # Autopilot shouldn't directly manipulate scene items it doesn't own

                # Increment counter
                self.rocks_stolen += 1

                if self.debug_mode:
                    print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'stole' a rock! Total stolen: {self.rocks_stolen}")

                # Set status to indicate stealing (this will be sent in updates)
                self.squid_data['status'] = "stealing rock"

                # If we've met our quota, start heading home
                if self.rocks_stolen >= self.max_rocks_to_steal:
                    self.state = "returning"
                    # self.determine_home_direction() # Home direction set at init
                    if self.debug_mode:
                        print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} met stealing quota, heading home")
                    return # Skip to next update cycle for return_home logic

            # Move on after interacting
            self.target_object = None
            self.state = "exploring"

    def return_home(self):
        """Begin returning to home instance"""
        if not self.home_direction:
            # This case should ideally not be hit if home_direction is set correctly at init
            # self.determine_home_direction() # Fallback, though better if direction is known from entry
            if self.debug_mode:
                print(f"[AutoPilot] Warning: Squid {self.squid_data.get('node_id')} home_direction was not set, attempting to determine.")
            entry_dir_on_this_screen = self.squid_data.get('entry_direction_on_this_screen')
            if entry_dir_on_this_screen:
                opposite_map = {'left': 'right', 'right': 'left', 'top': 'down', 'bottom': 'up'}
                self.home_direction = opposite_map.get(entry_dir_on_this_screen, random.choice(['left', 'right', 'up', 'down']))
            else:
                self.home_direction = random.choice(['left', 'right', 'up', 'down']) # Last resort
            if self.debug_mode: print(f"[AutoPilot] Fallback home_direction set to: {self.home_direction}")


        if self.debug_mode and random.random() < 0.05:  # Occasional status update
            print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} returning home via {self.home_direction}, " +
                f"position: ({self.squid_data['x']:.1f}, {self.squid_data['y']:.1f})")

        # Move towards the determined home_direction boundary
        self.move_in_direction(self.home_direction)
        # The actual 'direction' for animation is set within move_in_direction.
        # The 'home_direction' is the target boundary.

        # Track distance
        self.distance_traveled += self.move_speed

        # Check if we've reached the boundary
        if self.is_at_boundary(self.home_direction):
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} reached home boundary: {self.home_direction}")
                print(f"[AutoPilot] Summary: ate {self.food_eaten_count} food, " +
                    f"interacted with {self.rock_interaction_count} rocks, " +
                    f"stole {self.rocks_stolen} rocks, " +
                    f"traveled {self.distance_traveled:.1f} pixels")
            # Notify plugin_instance that this squid wants to exit
            if self.plugin_instance:
                exit_payload = self.plugin_instance._get_squid_state_for_exit(self.home_direction, remote_squid_data=self.squid_data)
                if exit_payload: # Make sure _get_squid_state_for_exit can handle remote_squid_data or adapt
                    self.plugin_instance.network_node.broadcast_message("SQUID_EXIT", exit_payload)
                    # Autopilot should probably stop or be removed after signaling exit.
                    # For now, it might continue trying to exit if not removed by mp_plugin_logic.
                    if self.debug_mode: print(f"[Autopilot] Squid {self.squid_data.get('node_id')} signalled exit.")
            self.state = "exited" # Mark as exited to stop further autopilot updates

    def determine_home_direction(self):
        """Determine which direction to head to return home
        NOTE: This method is kept for reference but home_direction is now primarily set during __init__.
        """
        entry_dir = self.squid_data.get('entry_direction_on_this_screen') # Using the key from mp_plugin_logic

        if entry_dir:
            opposite_map = {
                'left': 'right',
                'right': 'left',
                'top': 'down',
                'down': 'up',
                'center_fallback': random.choice(['left', 'right', 'up', 'down'])
            }
            self.home_direction = opposite_map.get(entry_dir, random.choice(['left', 'right', 'up', 'down']))
        else:
            # Fallback: Default based on position on screen if entry direction unknown
            x, y = self.squid_data['x'], self.squid_data['y']
            width, height = self.get_window_width(), self.get_window_height()

            left_dist = x
            right_dist = width - x
            top_dist = y
            bottom_dist = height - y

            min_dist = min(left_dist, right_dist, top_dist, bottom_dist)

            if min_dist == left_dist: self.home_direction = 'left'
            elif min_dist == right_dist: self.home_direction = 'right'
            elif min_dist == top_dist: self.home_direction = 'up'
            else: self.home_direction = 'down'

        if self.debug_mode:
            print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} (re)determined home direction: {self.home_direction}")


    def move_in_direction(self, direction):
        """Move the squid in a given direction and update its 'direction' key for animation/state."""
        speed = self.move_speed
        prev_x, prev_y = self.squid_data['x'], self.squid_data['y']

        # Update position
        if direction == 'left':
            self.squid_data['x'] = max(0, self.squid_data['x'] - speed) # Use 0 as absolute boundary
        elif direction == 'right':
            self.squid_data['x'] = min(self.get_window_width() - self.squid_data.get('squid_width', 50),
                                      self.squid_data['x'] + speed) # Consider squid width
        elif direction == 'up':
            self.squid_data['y'] = max(0, self.squid_data['y'] - speed) # Use 0 as absolute boundary
        elif direction == 'down':
            self.squid_data['y'] = min(self.get_window_height() - self.squid_data.get('squid_height', 50),
                                      self.squid_data['y'] + speed) # Consider squid height

        # Set the 'direction' key which might be used for image facing direction
        self.squid_data['direction'] = direction
        # Also update image_direction_key if movement is horizontal, for consistency with local squid
        if direction == 'left' or direction == 'right':
            self.squid_data['image_direction_key'] = direction
        # If moving vertically, image_direction_key retains its last horizontal value (consistent with Squid.py)

        # Track distance traveled
        moved_dist = math.sqrt((self.squid_data['x'] - prev_x)**2 + (self.squid_data['y'] - prev_y)**2)
        self.distance_traveled += moved_dist


    def move_toward(self, target_x, target_y):
        """Move toward a specific position, setting the appropriate direction."""
        current_x, current_y = self.squid_data['x'], self.squid_data['y']
        dx = target_x - current_x
        dy = target_y - current_y

        chosen_direction = self.squid_data.get('direction', 'right') # Default if no clear path

        if abs(dx) > self.move_speed / 2 or abs(dy) > self.move_speed / 2: # Only change direction if sufficiently off
            if abs(dx) > abs(dy):
                chosen_direction = 'right' if dx > 0 else 'left'
            else:
                chosen_direction = 'down' if dy > 0 else 'up'
        
        self.move_in_direction(chosen_direction)


    def find_nearby_food(self):
        """Find nearby food in the scene"""
        food_items = self.get_food_items_from_scene()
        if not food_items:
            return None

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_food = None
        min_dist = float('inf')

        for food in food_items:
            if not self.is_object_valid(food): continue # Skip invalid items
            dist = self.distance_between(squid_pos, self.get_object_position(food))
            if dist < min_dist:
                min_dist = dist
                closest_food = food
        
        if closest_food and min_dist < 300: # Detection range
            return closest_food
        return None

    def find_nearby_rock(self):
        """Find nearby rocks in the scene"""
        rock_items = self.get_rock_items_from_scene()
        if not rock_items:
            return None

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_rock = None
        min_dist = float('inf')

        for rock in rock_items:
            if not self.is_object_valid(rock): continue
            # Avoid targeting remotely owned rocks for stealing, but can interact
            # is_remotely_owned = getattr(rock, 'is_remote', False) # Check if it's a representation of another remote object
            # if is_remotely_owned: continue

            dist = self.distance_between(squid_pos, self.get_object_position(rock))
            if dist < min_dist:
                min_dist = dist
                closest_rock = rock

        if closest_rock and min_dist < 200: # Detection range
            return closest_rock
        return None

    def get_food_items_from_scene(self):
        """Get all food items from the scene"""
        food_items = []
        if not self.scene: return food_items

        for item in self.scene.items():
            try:
                # Check category attribute first
                if hasattr(item, 'category') and getattr(item, 'category', None) == 'food':
                    if item.isVisible(): food_items.append(item) # Only visible items
                    continue # Already added if food by category

                # Then check filename if not added by category
                if hasattr(item, 'filename'):
                    filename = getattr(item, 'filename', '').lower()
                    if any(food_type in filename for food_type in ['food', 'sushi', 'cheese']): # Example food types
                         if item.isVisible() and item not in food_items: food_items.append(item)

            except Exception as e:
                if self.debug_mode:
                    print(f"[AutoPilot] Error checking item for food: {e}")
        return food_items

    def get_rock_items_from_scene(self):
        """Get all rock items from the scene"""
        rock_items = []
        if not self.scene: return rock_items

        for item in self.scene.items():
            try:
                if hasattr(item, 'category') and getattr(item, 'category', None) == 'rock':
                    if item.isVisible(): rock_items.append(item)
                    continue
                elif hasattr(item, 'filename') and 'rock' in getattr(item, 'filename', '').lower():
                     if item.isVisible() and item not in rock_items: rock_items.append(item)
            except Exception as e:
                if self.debug_mode:
                    print(f"[AutoPilot] Error checking item for rock: {e}")
        return rock_items

    def is_in_vision_range(self, item): # This method seems duplicated by find_nearby_X logic's range check
        """Check if an item is in the squid's vision range"""
        if not item or not self.is_object_valid(item):
            return False

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        obj_pos = self.get_object_position(item)
        distance = self.distance_between(squid_pos, obj_pos)
        return distance < 800 # General vision range

    # Removed duplicated get_rock_items_from_scene method. The one above is more complete.

    def animate_movement(self, squid_data, remote_visual): # This method is not directly called by update()
        """DEPRECATED or needs integration: Add movement animation to make the squid look more natural.
        The current autopilot updates squid_data, and RemoteEntityManager handles visuals.
        This method would need to be part of RemoteEntityManager or called by it.
        """
        # This logic should ideally be in RemoteEntityManager if it's about visual updates
        current_direction = squid_data.get('image_direction_key', 'right') # Use image_direction_key
        current_frame = getattr(self, '_animation_frame', 0) # Autopilot shouldn't manage visual item's frames directly
        self._animation_frame = (current_frame + 1) % 2
        frame_num = self._animation_frame + 1
        squid_image_name = f"{current_direction.lower()}{frame_num}.png"

        # Path resolution should also be in RemoteEntityManager
        # image_path = os.path.join("images", squid_image_name)
        # if os.path.exists(image_path):
        #     try:
        #         pixmap = QtGui.QPixmap(image_path)
        #         remote_visual.setPixmap(pixmap) # remote_visual is not an attribute of autopilot
        #     except Exception as e:
        #         if self.debug_mode:
        #             print(f"Failed to load animation frame: {e}")
        if self.debug_mode:
            print(f"[AutoPilot] Animate_movement called (currently advisory, visual update by RemoteEntityManager)")


    def eat_food(self, food_item):
        """Simulate eating food"""
        # Autopilot should not directly modify the scene.
        # It should signal the plugin_instance or some other manager to handle object removal.
        # For now, we'll assume the object disappears or becomes invalid for targeting.
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'ate' food item {food_item}")

        # Update squid state (this data is sent back on exit)
        self.squid_data['hunger'] = max(0, self.squid_data.get('hunger', 50) - 15)
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 10)
        self.food_eaten_count += 1
        # In a more complex system, this action might be reported back to the home instance.

    def interact_with_rock(self, rock_item): # This was part of interact_with_object, keeping for potential direct call
        """Simulate interacting with a rock"""
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'interacted' with rock {rock_item}")
        self.rock_interaction_count += 1
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 5)


    def is_rock(self, item):
        """Determine if an item is a rock"""
        if not self.is_object_valid(item): return False
        if hasattr(item, 'category') and getattr(item, 'category', None) == 'rock':
            return True
        if hasattr(item, 'filename') and 'rock' in getattr(item, 'filename', '').lower():
            return True
        return False

    def is_object_valid(self, obj):
        """Check if an object is still valid (exists in scene and is visible)"""
        return obj is not None and obj in self.scene.items() and obj.isVisible()


    def get_object_position(self, obj):
        """Get the position of an object"""
        if obj and hasattr(obj, 'pos'): # Check obj is not None
            pos = obj.pos()
            return (pos.x(), pos.y())
        return (self.squid_data.get('x',0), self.squid_data.get('y',0)) # Fallback to current squid pos if obj is invalid

    def distance_between(self, pos1, pos2):
        """Calculate distance between two positions"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def get_window_width(self):
        """Get window width"""
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_width'):
            return self.remote_entity_manager.window_width
        elif hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().width()
        return self.window_width # Fallback to initial squid_data

    def get_window_height(self):
        """Get window height"""
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_height'):
            return self.remote_entity_manager.window_height
        elif hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().height()
        return self.window_height # Fallback to initial squid_data

    def is_at_boundary(self, direction):
        """Check if squid is at specified boundary"""
        x, y = self.squid_data['x'], self.squid_data['y']
        squid_w = self.squid_data.get('squid_width', 50)
        squid_h = self.squid_data.get('squid_height', 50)
        boundary_threshold = 5 # Small threshold, actual exit is when it's off-screen

        win_width = self.get_window_width()
        win_height = self.get_window_height()

        if direction == 'left':
            return x <= boundary_threshold
        elif direction == 'right':
            return x + squid_w >= win_width - boundary_threshold
        elif direction == 'up':
            return y <= boundary_threshold
        elif direction == 'down':
            return y + squid_h >= win_height - boundary_threshold

        return False

    def get_summary(self):
        """Get a summary of the squid's activities while away, including rock stealing"""
        summary = {
            'time_away': round(self.time_away, 2),
            'food_eaten': self.food_eaten_count,
            'rock_interactions': self.rock_interaction_count,
            'rocks_stolen': self.rocks_stolen,
            'distance_traveled': round(self.distance_traveled, 2),
            'final_state': self.state,
            'node_id': self.squid_data.get('node_id', 'UnknownNode')
        }
        return summary