import random
import math
import time
import os
from PyQt5 import QtCore, QtGui, QtWidgets

class RemoteSquidController:
    """Controls behavior of squids away from their home instance"""
    
    def __init__(self, squid_data, scene, debug_mode=False):
        self.squid_data = squid_data.copy()  # Make a copy to avoid reference issues
        self.scene = scene                   # The graphics scene for object detection
        self.debug_mode = debug_mode         # Debug flag for verbose logging
        
        # Extract more data from squid_data if available
        self.entry_time = squid_data.get('entry_time', time.time())
        self.entry_position = squid_data.get('entry_position', None)
        self.window_width = squid_data.get('window_width', 1280)  # Default fallback
        self.window_height = squid_data.get('window_height', 900)  # Default fallback
        
        # Initialize home direction from squid data or determine later
        self.home_direction = squid_data.get('home_direction', None)
        
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
            print(f"[AutoPilot] Initialized for squid at ({squid_data['x']}, {squid_data['y']})")
            print(f"[AutoPilot] Will return home after {self.max_time_away} seconds")
            if self.home_direction:
                print(f"[AutoPilot] Home direction: {self.home_direction}")
    
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
            return
            
        self.next_decision_time = current_time + self.decision_interval
        
        # Check if should return home
        if self.time_away > self.max_time_away and self.state != "returning":
            if self.debug_mode:
                print(f"[AutoPilot] Time to go home: {self.time_away:.1f}s/{self.max_time_away:.1f}s")
            self.state = "returning"
            self.determine_home_direction()
        
        # State machine for squid behavior
        if self.state == "exploring":
            self.explore()
        elif self.state == "feeding":
            self.seek_food()
        elif self.state == "interacting":
            self.interact_with_object()
        elif self.state == "returning":
            self.return_home()
    
    def explore(self):
        """Random exploration behavior"""
        # Chance to change direction
        if random.random() < self.direction_change_prob:
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            if self.debug_mode:
                print(f"[AutoPilot] Exploring: Changed direction to {new_direction}")
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
                    print(f"[AutoPilot] Spotted food, switching to feeding state")
        
        # Chance to spot and interact with rocks
        elif random.random() < 0.05:
            rock = self.find_nearby_rock()
            if rock:
                self.target_object = rock
                self.state = "interacting"
                if self.debug_mode:
                    print(f"[AutoPilot] Spotted rock, switching to interacting state")
    
    def seek_food(self):
        """Move toward and try to eat food"""
        if not self.target_object or not self.is_object_valid(self.target_object):
            # Lost target, go back to exploring
            if self.debug_mode:
                print(f"[AutoPilot] Lost food target, returning to exploring")
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
                print(f"[AutoPilot] Ate food, food count: {self.food_eaten_count}")
    
    def interact_with_object(self):
        """Interact with rocks or other objects, with a chance to steal them"""
        if not self.target_object or not self.is_object_valid(self.target_object):
            # Lost target, go back to exploring
            if self.debug_mode:
                print(f"[AutoPilot] Lost rock target, returning to exploring")
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
            is_remotely_owned = getattr(self.target_object, 'is_remote', False)
            is_local_rock = not is_remotely_owned
            
            # Regular interaction
            self.rock_interaction_count += 1
            
            # Try to steal if this is a rock and we haven't reached our limit
            if (self.is_rock(self.target_object) and 
                is_local_rock and 
                self.rocks_stolen < self.max_rocks_to_steal and
                random.random() < 0.4):  # 40% chance to try stealing
                
                # Set carrying state
                self.squid_data['carrying_rock'] = True
                self.stealing_phase = True
                
                # Hide the original rock
                self.target_object.setVisible(False)
                
                # Increment counter
                self.rocks_stolen += 1
                
                if self.debug_mode:
                    print(f"[AutoPilot] Stole a rock! Total stolen: {self.rocks_stolen}")
                
                # Set status to indicate stealing
                self.squid_data['status'] = "stealing rock"
                
                # If we've met our quota, start heading home
                if self.rocks_stolen >= self.max_rocks_to_steal:
                    self.state = "returning"
                    self.determine_home_direction()
                    if self.debug_mode:
                        print(f"[AutoPilot] Met stealing quota, heading home")
                    return
            
            # Move on after interacting
            self.target_object = None
            self.state = "exploring"
    
    def return_home(self):
        """Begin returning to home instance"""
        if not self.home_direction:
            self.determine_home_direction()
        
        if self.debug_mode and random.random() < 0.05:  # Occasional status update
            print(f"[AutoPilot] Returning home via {self.home_direction}, " +
                f"position: ({self.squid_data['x']:.1f}, {self.squid_data['y']:.1f})")
        
        # Calculate target position at the boundary
        target_x, target_y = self.squid_data['x'], self.squid_data['y']
        
        if self.home_direction == 'left':
            target_x = 0
        elif self.home_direction == 'right':
            target_x = self.get_window_width()
        elif self.home_direction == 'up':
            target_y = 0
        elif self.home_direction == 'down':
            target_y = self.get_window_height()
        
        # Calculate ideal direction vector
        dx = target_x - self.squid_data['x']
        dy = target_y - self.squid_data['y']
        
        # Add some randomness to prevent straight-line movement
        if random.random() < 0.1:
            dx += random.uniform(-10, 10)
            dy += random.uniform(-10, 10)
        
        # Determine primary direction based on vector components
        if abs(dx) > abs(dy):
            # Move horizontally
            if dx > 0:
                self.squid_data['direction'] = 'right'
                self.squid_data['x'] = min(self.get_window_width(), 
                                        self.squid_data['x'] + self.move_speed)
            else:
                self.squid_data['direction'] = 'left'
                self.squid_data['x'] = max(0, self.squid_data['x'] - self.move_speed)
        else:
            # Move vertically
            if dy > 0:
                self.squid_data['direction'] = 'down'
                self.squid_data['y'] = min(self.get_window_height(), 
                                        self.squid_data['y'] + self.move_speed)
            else:
                self.squid_data['direction'] = 'up'
                self.squid_data['y'] = max(0, self.squid_data['y'] - self.move_speed)
        
        # Track distance
        self.distance_traveled += self.move_speed
        
        # Check if we've reached the boundary
        if self.is_at_boundary(self.home_direction):
            if self.debug_mode:
                print(f"[AutoPilot] Reached home boundary: {self.home_direction}")
                print(f"[AutoPilot] Summary: ate {self.food_eaten_count} food, " +
                    f"interacted with {self.rock_interaction_count} rocks, " +
                    f"traveled {self.distance_traveled:.1f} pixels")
            # The squid crossing logic will take over from here
    
    def determine_home_direction(self):
        """Determine which direction to head to return home"""
        # This implementation defaults to returning the way the squid came in
        # For more advanced implementations, could keep track of origin direction
        entry_dir = self.squid_data.get('entry_direction', None)
        
        if entry_dir:
            # Return through the opposite direction
            opposite_map = {
                'left': 'right',
                'right': 'left',
                'up': 'down',
                'down': 'up'
            }
            self.home_direction = opposite_map.get(entry_dir, 'left')
        else:
            # Default based on position on screen if entry direction unknown
            x, y = self.squid_data['x'], self.squid_data['y']
            width, height = self.get_window_width(), self.get_window_height()
            
            # Determine closest edge
            left_dist = x
            right_dist = width - x
            top_dist = y
            bottom_dist = height - y
            
            min_dist = min(left_dist, right_dist, top_dist, bottom_dist)
            
            if min_dist == left_dist:
                self.home_direction = 'left'
            elif min_dist == right_dist:
                self.home_direction = 'right'
            elif min_dist == top_dist:
                self.home_direction = 'up'
            else:
                self.home_direction = 'down'
        
        if self.debug_mode:
            print(f"[AutoPilot] Determined home direction: {self.home_direction}")
    
    def move_in_direction(self, direction):
        """Move the squid in a given direction"""
        speed = self.move_speed
        
        if direction == 'left':
            self.squid_data['x'] = max(10, self.squid_data['x'] - speed)
        elif direction == 'right':
            self.squid_data['x'] = min(self.get_window_width() - 60, 
                                      self.squid_data['x'] + speed)
        elif direction == 'up':
            self.squid_data['y'] = max(10, self.squid_data['y'] - speed)
        elif direction == 'down':
            self.squid_data['y'] = min(self.get_window_height() - 60, 
                                      self.squid_data['y'] + speed)
        
        # Track distance traveled
        self.distance_traveled += speed
    
    def move_toward(self, target_x, target_y):
        """Move toward a specific position"""
        current_x, current_y = self.squid_data['x'], self.squid_data['y']
        dx = target_x - current_x
        dy = target_y - current_y
        
        # Determine direction based on larger component
        if abs(dx) > abs(dy):
            if dx > 0:
                self.squid_data['direction'] = 'right'
                self.move_in_direction('right')
            else:
                self.squid_data['direction'] = 'left'
                self.move_in_direction('left')
        else:
            if dy > 0:
                self.squid_data['direction'] = 'down'
                self.move_in_direction('down')
            else:
                self.squid_data['direction'] = 'up'
                self.move_in_direction('up')
    
    def find_nearby_food(self):
        """Find nearby food in the scene"""
        # This is a placeholder - actual implementation would search scene objects
        # Depending on the integration, this method would need to be customized
        food_items = self.get_food_items_from_scene()
        if not food_items:
            return None
        
        # Find the closest food item
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_food = min(food_items, 
                          key=lambda f: self.distance_between(
                              squid_pos, 
                              self.get_object_position(f)
                          ))
        
        # Only return if within detection range
        if self.distance_between(squid_pos, self.get_object_position(closest_food)) < 300:
            return closest_food
        return None
    
    def find_nearby_rock(self):
        """Find nearby rocks in the scene"""
        # Similar to find_nearby_food but for rocks
        rock_items = self.get_rock_items_from_scene()
        if not rock_items:
            return None
        
        # Find the closest rock item
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_rock = min(rock_items, 
                          key=lambda r: self.distance_between(
                              squid_pos, 
                              self.get_object_position(r)
                          ))
        
        # Only return if within detection range
        if self.distance_between(squid_pos, self.get_object_position(closest_rock)) < 200:
            return closest_rock
        return None
    
    def get_food_items_from_scene(self):
        """Get all food items from the scene"""
        food_items = []
        
        # In a real implementation, you would iterate through scene items and check types/categories
        for item in self.scene.items():
            try:
                # Check if item has filename attribute
                if hasattr(item, 'filename'):
                    filename = getattr(item, 'filename', '').lower()
                    if any(food_type in filename for food_type in ['food', 'sushi', 'cheese']):
                        food_items.append(item)
                        if self.debug_mode:
                            print(f"Found food item: {filename}")
                
                # Also check category attribute
                if hasattr(item, 'category') and getattr(item, 'category', None) == 'food':
                    if item not in food_items:
                        food_items.append(item)
                        if self.debug_mode:
                            print(f"Found food by category")
            except Exception as e:
                if self.debug_mode:
                    print(f"Error checking item for food: {e}")
        
        if self.debug_mode:
            print(f"Found {len(food_items)} food items in scene")
        return food_items

    def get_rock_items_from_scene(self):
        """Get all rock items from the scene"""
        rock_items = []
        
        # In a real implementation, you would iterate through scene items and check types/categories
        for item in self.scene.items():
            try:
                # Check if item has category attribute
                if hasattr(item, 'category') and getattr(item, 'category', None) == 'rock':
                    rock_items.append(item)
                    if self.debug_mode:
                        print(f"Found rock by category")
                
                # Also check filename for 'rock'
                elif hasattr(item, 'filename'):
                    filename = getattr(item, 'filename', '').lower()
                    if 'rock' in filename:
                        if item not in rock_items:
                            rock_items.append(item)
                            if self.debug_mode:
                                print(f"Found rock by filename: {filename}")
            except Exception as e:
                if self.debug_mode:
                    print(f"Error checking item for rock: {e}")
        
        if self.debug_mode:
            print(f"Found {len(rock_items)} rock items in scene")
        return rock_items
    
    def is_in_vision_range(self, item):
        """Check if an item is in the squid's vision range"""
        if not item:
            return False
            
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        obj_pos = self.get_object_position(item)
        
        # Calculate distance and angle to object
        distance = self.distance_between(squid_pos, obj_pos)
        
        # Vision range is 800 pixels
        return distance < 800
    
    def get_rock_items_from_scene(self):
        """Get all rock items from the scene"""
        # This is a placeholder that should be implemented based on actual scene structure
        rock_items = []
        
        # In a real implementation, you would iterate through scene items and check types/categories
        for item in self.scene.items():
            if hasattr(item, 'category') and getattr(item, 'category', None) == 'rock':
                rock_items.append(item)
            elif hasattr(item, 'filename') and 'rock' in getattr(item, 'filename', '').lower():
                rock_items.append(item)
        
        return rock_items
    
    def animate_movement(self, squid_data, remote_visual):
        """Add movement animation to make the squid look more natural"""
        # Create frame alternation for swimming animation
        current_direction = squid_data.get('direction', 'right')
        current_frame = getattr(self, '_animation_frame', 0)
        self._animation_frame = (current_frame + 1) % 2  # Toggle between 0 and 1
        
        # Load the appropriate squid image based on direction and frame
        frame_num = self._animation_frame + 1  # Convert to 1-based index for filenames
        squid_image = f"{current_direction}{frame_num}.png"
        image_path = os.path.join("images", squid_image)
        
        if os.path.exists(image_path):
            try:
                pixmap = QtGui.QPixmap(image_path)
                remote_visual.setPixmap(pixmap)
            except Exception as e:
                if self.debug_mode:
                    print(f"Failed to load animation frame: {e}")
    
    def eat_food(self, food_item):
        """Simulate eating food"""
        # Remove food from scene
        if food_item in self.scene.items():
            self.scene.removeItem(food_item)
        
        # Update squid state
        self.squid_data['hunger'] = max(0, self.squid_data.get('hunger', 50) - 15)
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 10)
        
        # Update food eaten count
        self.food_eaten_count += 1
    
    def interact_with_rock(self, rock_item):
        """Simulate interacting with a rock"""
        # Update interaction count
        self.rock_interaction_count += 1
        
        # Update squid happiness
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 5)
    
    def is_rock(self, item):
        """Determine if an item is a rock"""
        if hasattr(item, 'category') and getattr(item, 'category', None) == 'rock':
            return True
        if hasattr(item, 'filename') and 'rock' in getattr(item, 'filename', '').lower():
            return True
        return False
    
    def is_object_valid(self, obj):
        """Check if an object is still valid (exists in scene)"""
        return obj in self.scene.items()
    
    def get_object_position(self, obj):
        """Get the position of an object"""
        if hasattr(obj, 'pos'):
            pos = obj.pos()
            return (pos.x(), pos.y())
        return (0, 0)
    
    def distance_between(self, pos1, pos2):
        """Calculate distance between two positions"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def get_window_width(self):
        """Get window width"""
        # Try multiple ways to get window width
        if hasattr(self, 'window_width'):
            return self.window_width
        elif hasattr(self.scene, 'width'):
            return self.scene.width()
        elif hasattr(self.scene, 'sceneRect'):
            return self.scene.sceneRect().width()
        return 1280  # Default fallback 
    
    def get_window_height(self):
        """Get window height"""
        # Try multiple ways to get window height
        if hasattr(self, 'window_height'):
            return self.window_height
        elif hasattr(self.scene, 'height'):
            return self.scene.height()
        elif hasattr(self.scene, 'sceneRect'):
            return self.scene.sceneRect().height()
        return 900  # Default fallback
    
    def is_at_boundary(self, direction):
        """Check if squid is at specified boundary"""
        x, y = self.squid_data['x'], self.squid_data['y']
        boundary_threshold = 20  # Increased threshold for more reliable detection
        
        if direction == 'left':
            return x <= boundary_threshold
        elif direction == 'right':
            return x >= self.get_window_width() - boundary_threshold
        elif direction == 'up':
            return y <= boundary_threshold
        elif direction == 'down':
            return y >= self.get_window_height() - boundary_threshold
        
        return False
    
    def get_summary(self):
        """Get a summary of the squid's activities while away, including rock stealing"""
        summary = {
            'time_away': self.time_away,
            'food_eaten': self.food_eaten_count,
            'rock_interactions': self.rock_interaction_count,
            'rocks_stolen': self.rocks_stolen,
            'distance_traveled': self.distance_traveled,
            'final_state': self.state
        }
        return summary