import random
import math
import time
import os
from PyQt5 import QtCore, QtGui, QtWidgets

class RemoteSquidController:
    """Controls behavior of squids away from their home instance"""

    def __init__(self, squid_data, scene, plugin_instance=None, debug_mode=False, remote_entity_manager=None):
        self.squid_data = squid_data.copy() # Ensure it's a copy
        self.scene = scene
        self.plugin_instance = plugin_instance
        self.debug_mode = debug_mode
        self.remote_entity_manager = remote_entity_manager

        self.entry_time = squid_data.get('entry_time', time.time())
        self.entry_position = squid_data.get('entry_position', None)
        self.window_width = squid_data.get('window_width', 1280)
        self.window_height = squid_data.get('window_height', 900)

        entry_dir_on_this_screen = squid_data.get('entry_direction_on_this_screen')
        if entry_dir_on_this_screen:
            opposite_map = {
                'left': 'right', 'right': 'left',
                'top': 'down', 'bottom': 'up',
                'center_fallback': random.choice(['left', 'right', 'up', 'down'])
            }
            self.home_direction = opposite_map.get(entry_dir_on_this_screen)
        else:
            self.home_direction = squid_data.get('home_direction', random.choice(['left', 'right', 'up', 'down']))

        self.state = "exploring"
        # Override initial status from payload, as autopilot determines its own status
        self.squid_data['status'] = "exploring" 

        self.target_object = None
        self.time_away = 0
        self.max_time_away = random.randint(60, 180) # e.g. 1-3 minutes

        self.food_eaten_count = 0
        self.rock_interaction_count = 0 # Counts interactions with any stealable item
        self.distance_traveled = 0
        
        self.rocks_stolen = 0 # Will reflect len(self.carried_items_data)
        self.max_rocks_to_steal = random.randint(1, 3) # Max items the squid will try to carry
        self.stealing_phase = False # True when actively trying to "steal" (interaction part)
        
        self.carried_items_data = [] # Stores detailed data of items being "physically" carried
        
        self.move_speed = 4.5 # Tuned for ~90px/sec if controller updates at 20Hz (50ms interval)
        self.direction_change_prob = 0.9 # Increased for less linear movement
        self.direction_change_probability = 0.9
        self.next_decision_time = 0 # Initialize to 0 so first decision happens immediately
        self.decision_interval = 0.5 # Time between major decision evaluations

        self.last_update_time = time.time()

        if self.debug_mode:
            log_x = self.squid_data.get('x', 'N/A')
            log_y = self.squid_data.get('y', 'N/A')
            # This is a direct print, not using _log_decision, for immediate startup confirmation
            print(f"[AutoPilot __init__ {self.squid_data.get('node_id', 'UnknownNode')[-4:]}] Initialized. State: {self.state}, Status: {self.squid_data['status']}")
            print(f"[AutoPilot __init__ {self.squid_data.get('node_id', 'UnknownNode')[-4:]}] Max Time: {self.max_time_away}s. Max Carry: {self.max_rocks_to_steal}. Home Dir: {self.home_direction}")
        
        # This will attempt to write to autopilot_decisions.txt if debug_mode is True
        self._log_decision(f"Controller Initialized. Start State: {self.state}, Start Status: {self.squid_data['status']}, Max Time: {self.max_time_away:.1f}s, Max Carry: {self.max_rocks_to_steal}, Home Dir: {self.home_direction}, Speed: {self.move_speed}, DirChangeProb: {self.direction_change_prob}")

    def _log_decision(self, decision_text: str):
        if not self.debug_mode:
            return
        
        log_file_name = "autopilot_decisions.txt"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        node_id_str = self.squid_data.get('node_id', 'UnknownNode') # Using full ID in log for clarity
        
        log_entry = f"[{timestamp}] [SquidID: {node_id_str}] {decision_text}\n"
        
        try:
            with open(log_file_name, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            # Fallback to console if file logging fails
            print(f"[AutoPilotDecisionFileError] Could not write to {log_file_name} for SquidID {node_id_str}: {e}")
            print(f"[AutoPilotDecisionFallbackLog] {log_entry.strip()}")

    def _capture_item_properties(self, game_item_object) -> dict | None:
        if not game_item_object or not self.is_object_valid(game_item_object):
            self._log_decision(f"CaptureItemAttempt: FAILED - Target item is invalid or None.")
            return None

        item_pos = self.get_object_position(game_item_object)
        properties = {
            'original_filename': getattr(game_item_object, 'filename', 'unknown_item.png'),
            'original_category': getattr(game_item_object, 'category', 'unknown'),
            'original_x': item_pos[0], # Position in the remote tank when stolen
            'original_y': item_pos[1],
            'scale': game_item_object.scale() if hasattr(game_item_object, 'scale') else 1.0,
            'zValue': game_item_object.zValue() if hasattr(game_item_object, 'zValue') else 0,
            # 'rotation': game_item_object.rotation() if hasattr(game_item_object, 'rotation') else 0.0, 
        }
        base_name = os.path.basename(properties['original_filename']) if isinstance(properties['original_filename'], str) else "unknown"
        self._log_decision(f"CaptureItemSuccess: Captured properties for '{base_name}': Scale {properties['scale']:.2f}, Category '{properties['original_category']}'.")
        return properties


    def update(self, delta_time):
        print(f"!!!!!!!! AUTOPILOT RemoteSquidController.update() ENTERED for {self.squid_data.get('node_id', 'UnknownNode')[-4:]} !!!!!!!!") # [cite: 273, 275, 276, 278, 279, 281, 282, 284, 285, 287, 288, 290, 291, 293, 294, 296, 297, 299, 300, 302, 303, 305, 306, 308, 309, 311, 312, 314, 315, 317, 318, 320, 321, 323, 324, 326, 327, 329, 330, 332, 333, 335, 336, 338, 339, 341, 342, 344, 345, 347, 348, 350, 351, 353, 354, 356, 357, 359, 360, 362, 363, 365, 366, 368, 369, 371, 372, 374, 375, 377, 378, 380, 381, 383, 384, 386, 387, 389, 390, 392, 393, 395, 396, 398, 399, 401, 402, 404, 405, 407, 408, 410, 411, 413, 414, 416, 418, 419, 421, 422, 424, 425, 428, 429, 431, 432, 434, 435, 437, 438, 440, 441, 443, 444, 446, 447, 449, 450, 452, 453, 455, 456, 458, 459, 461, 462, 464, 465, 467, 468, 470, 471, 473, 474, 476, 477, 479, 480, 482, 483, 485, 486, 488, 489, 491, 492, 494, 495, 497, 498, 500, 501, 503, 504, 506, 507, 509, 510, 512, 513, 515, 516, 518, 519, 521, 522, 524, 525, 527, 528, 530, 531, 533, 534, 536, 537]

        # Simple random movement logic
        if random.random() < 0.05: # 5% chance to change direction
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            self.squid_data['direction'] = new_direction
            # self.plugin_instance.logger.debug(f"Autopilot {self.squid_data['node_id'][-4:]} changed direction to {new_direction}")

        # Basic boundary avoidance
        # Assuming self.scene and self.squid_data contain necessary info
        # This is highly simplified
        current_x = self.squid_data.get('x', 0)
        current_y = self.squid_data.get('y', 0)
        # Visuals are handled by RemoteEntityManager now based on self.squid_data
        # No direct self.visual_item.pos()

        speed = 50 * delta_time # Example speed

        if self.squid_data['direction'] == 'left':
            self.squid_data['x'] -= speed
            if self.squid_data['x'] < 0: self.squid_data['direction'] = 'right'
        elif self.squid_data['direction'] == 'right':
            self.squid_data['x'] += speed
            # Assuming scene width is available, e.g., self.scene.width() or passed in config
            if self.squid_data['x'] > self.scene.width() - self.squid_data.get('squid_width', 50): # Rough boundary
                self.squid_data['direction'] = 'left'
        # Add similar for 'up' and 'down'

        # The RemoteEntityManager will use self.squid_data to update the visual
        # No need to call self.remote_entity_manager.update_remote_squid() from here
        # if mp_plugin_logic.update_remote_controllers calls it after this.
        # However, if RemoteSquidController is the SOLE manager of its data and visuals,
        # then it would call:
        # if self.remote_entity_manager:
        # self.remote_entity_manager.update_remote_squid(self.squid_data['node_id'], self.squid_data)

    def explore(self, delta_time):
        self._log_decision(f"Explore: Method entered. Current direction: {self.squid_data.get('direction')}") # <<<< THIS IS THE CRUCIAL LOGGING LINE
        # Ensure status is correct if in this state
        if self.squid_data.get('status') != "exploring":
            self.squid_data['status'] = "exploring"
            self._log_decision(f"Explore: Set status to '{self.squid_data['status']}'.")

        if random.random() < self.direction_change_prob:
            old_direction = self.squid_data.get('direction', 'N/A')
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} exploring: Changed direction to {new_direction}")
            self.squid_data['direction'] = new_direction
            self._log_decision(f"Explore: Random direction change {old_direction} -> {new_direction}.")
        
        self.move_in_direction(self.squid_data['direction'])

        food_check_prob = 0.1 
        steal_check_prob = 0.25 

        if random.random() < food_check_prob:
            food = self.find_nearby_food()
            if food:
                self.target_object = food
                old_state = self.state
                self.state = "feeding"
                self.squid_data['status'] = "heading to food"
                target_name = getattr(self.target_object, 'filename', 'UnknownFood')
                if isinstance(target_name, str): target_name = os.path.basename(target_name)
                self._log_decision(f"Explore: Spotted food '{target_name}'. State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")
            else:
                self._log_decision(f"Explore: Checked for food (prob {food_check_prob*100:.0f}%), none found suitable/nearby.")
        
        elif random.random() < steal_check_prob: 
            if len(self.carried_items_data) < self.max_rocks_to_steal: # Only look if can carry more
                stealable_item = self.find_nearby_stealable_item()
                if stealable_item:
                    self.target_object = stealable_item
                    old_state = self.state
                    self.state = "interacting"
                    self.squid_data['status'] = "checking item"
                    item_type = getattr(self.target_object, 'category', 'item')
                    item_name = getattr(self.target_object, 'filename', f'Unknown{item_type.capitalize()}')
                    if isinstance(item_name, str): item_name = os.path.basename(item_name)
                    self._log_decision(f"Explore: Spotted stealable {item_type} '{item_name}'. State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")
                else:
                    self._log_decision(f"Explore: Checked for stealable items (prob {steal_check_prob*100:.0f}%), none found suitable/nearby.")
            else:
                self._log_decision(f"Explore: Checked for stealable items but already carrying max ({len(self.carried_items_data)}/{self.max_rocks_to_steal}).")
        # else: No specific action decided in this cycle beyond moving, status remains "exploring"

    def seek_food(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} lost food target, returning to exploring")
            old_target_name = getattr(self.target_object, 'filename', 'previous target')
            if isinstance(old_target_name, str): old_target_name = os.path.basename(old_target_name)
            old_state = self.state
            self.state = "exploring"
            self.squid_data['status'] = "exploring"
            self._log_decision(f"SeekFood: Lost target '{old_target_name}'. State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")
            self.target_object = None
            return

        if self.squid_data.get('status') != "heading to food": # Ensure status consistency
            self.squid_data['status'] = "heading to food"
            self._log_decision(f"SeekFood: Set status to '{self.squid_data['status']}'.")
            
        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)

        if distance < 50: 
            food_name = getattr(self.target_object, 'filename', 'UnknownFood')
            if isinstance(food_name, str): food_name = os.path.basename(food_name)
            
            self.eat_food(self.target_object) # Autopilot signals to remove, updates its own stats
            self.food_eaten_count += 1
            
            old_state = self.state
            self.state = "exploring" 
            self.squid_data['status'] = "exploring"
            self._log_decision(f"SeekFood: Ate food '{food_name}'. Food count: {self.food_eaten_count}. State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")
            self.target_object = None
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} ate food, food count: {self.food_eaten_count}")

    def interact_with_object(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} lost stealable item target, returning to exploring")
            old_target_name = getattr(self.target_object, 'filename', 'previous target')
            if isinstance(old_target_name, str): old_target_name = os.path.basename(old_target_name)
            old_state = self.state
            self.state = "exploring"
            self.squid_data['status'] = "exploring"
            self._log_decision(f"Interact: Lost target '{old_target_name}'. State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")
            self.target_object = None
            return

        current_status = self.squid_data.get('status', '')
        if current_status != "checking item" and not current_status.startswith("carrying"):
            self.squid_data['status'] = "checking item"
            self._log_decision(f"Interact: Set status to '{self.squid_data['status']}'.")

        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)

        if distance < 50: 
            is_remotely_owned_clone = getattr(self.target_object, 'is_remote_clone', False) 
            is_local_item_for_stealing = not is_remotely_owned_clone # Only steal original items in the scene

            self.rock_interaction_count += 1
            attempt_steal_chance = 0.4

            if (self.is_stealable_target(self.target_object) and # is_stealable_target already checks for remote clones
                is_local_item_for_stealing and # Redundant if is_stealable_target is robust, but good for clarity
                len(self.carried_items_data) < self.max_rocks_to_steal and
                random.random() < attempt_steal_chance):

                item_data_to_carry = self._capture_item_properties(self.target_object)
                
                if item_data_to_carry:
                    self.carried_items_data.append(item_data_to_carry)
                    self.rocks_stolen = len(self.carried_items_data) 

                    self.squid_data['carrying_rock'] = True # Generic flag, might be useful for visuals
                    self.stealing_phase = True # Internal flag for this action

                    item_type_stolen = item_data_to_carry.get('original_category', 'item')
                    item_name_stolen = os.path.basename(item_data_to_carry.get('original_filename', f'UnknownItem'))
                    
                    self.squid_data['status'] = f"carrying {item_type_stolen.lower()}"
                    self._log_decision(f"Interact: SUCCEEDED steal. Captured data for {item_type_stolen} '{item_name_stolen}'. Status: {self.squid_data['status']}. Carrying {self.rocks_stolen}/{self.max_rocks_to_steal} items.")
                    
                    if self.debug_mode:
                        print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} 'stole' and captured data for {item_type_stolen}! Total carried: {self.rocks_stolen}")

                    if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'hide_item_temporarily'):
                        self.remote_entity_manager.hide_item_temporarily(self.target_object)

                    if self.rocks_stolen >= self.max_rocks_to_steal: # Check if quota met
                        old_state = self.state
                        self.state = "returning"
                        self.squid_data['status'] = "returning home"
                        self._log_decision(f"Interact: Met carrying quota ({self.rocks_stolen}/{self.max_rocks_to_steal}). State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")
                        if self.debug_mode:
                            print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} met carrying quota, heading home")
                        self.target_object = None 
                        return # Exit interact_with_object, next update will call return_home()
                else:
                    self._log_decision(f"Interact: Attempted steal but FAILED to capture properties for target '{getattr(self.target_object, 'filename', 'N/A')}'. Not stolen.")
            else: # Did not steal
                reason = ""
                if not self.is_stealable_target(self.target_object): reason = "target not stealable type"
                elif not is_local_item_for_stealing: reason = "target is remotely owned clone"
                elif len(self.carried_items_data) >= self.max_rocks_to_steal: reason = "carrying quota already met"
                else: reason = f"failed {attempt_steal_chance*100:.0f}% steal chance"
                
                item_type = getattr(self.target_object, 'category', 'item')
                item_name = getattr(self.target_object, 'filename', f'Unknown{item_type.capitalize()}')
                if isinstance(item_name, str): item_name = os.path.basename(item_name)
                self._log_decision(f"Interact: Interacted with {item_type} '{item_name}'. Did not steal/carry (Reason: {reason}). Total interactions: {self.rock_interaction_count}.")
            
            # Fall through to exploring if not returning due to quota
            old_state = self.state # Could be "interacting"
            self.target_object = None
            self.state = "exploring"
            self.squid_data['status'] = "exploring"
            self._log_decision(f"Interact: Interaction logic complete. State change: {old_state} -> {self.state}. Status: {self.squid_data['status']}.")

    def return_home(self):
        if self.squid_data.get('status') != "returning home": # Ensure status is set
            self.squid_data['status'] = "returning home"
            self._log_decision(f"ReturnHome: Set status to '{self.squid_data['status']}'.")

        if not self.home_direction:
            self.determine_home_direction() # Sets self.home_direction
            self._log_decision(f"ReturnHome: Warning - home_direction was not set, fallback determined: {self.home_direction}.")

        if self.debug_mode and random.random() < 0.05:
            print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} returning home via {self.home_direction}, position: ({self.squid_data['x']:.1f}, {self.squid_data['y']:.1f})")

        self.move_in_direction(self.home_direction)

        if self.is_at_boundary(self.home_direction):
            summary = self.get_summary() # Get summary before state changes further
            self._log_decision(f"ReturnHome: Reached home boundary ({self.home_direction}). Exiting. Summary: Ate {summary['food_eaten']}, Interacted {summary['rock_interactions']}, Carried {summary['rocks_stolen']} items.")
            
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} reached home boundary: {self.home_direction}")
                print(f"[AutoPilot] Full Summary: {summary}") 
            
            if self.plugin_instance and hasattr(self.plugin_instance, 'handle_remote_squid_return'):
                # This signals mp_plugin_logic that this controller (for a squid visiting this instance)
                # has completed its journey here and wants to "return" (i.e., be removed and its summary processed).
                self.plugin_instance.handle_remote_squid_return(self.squid_data['node_id'], self) # Pass controller
            else:
                self._log_decision(f"ReturnHome: Error - plugin_instance or handle_remote_squid_return method missing.")

            self.state = "exited" # Mark as exited to stop further autopilot updates FOR THIS INSTANCE
            self.squid_data['status'] = "exited" # Final status for this instance

    def determine_home_direction(self):
        entry_dir = self.squid_data.get('entry_direction_on_this_screen')
        if entry_dir:
            opposite_map = {'left': 'right', 'right': 'left', 'top': 'down', 'down': 'up', 'center_fallback': random.choice(['left', 'right', 'up', 'down'])}
            self.home_direction = opposite_map.get(entry_dir, random.choice(['left', 'right', 'up', 'down']))
        else:
            x, y = self.squid_data['x'], self.squid_data['y']
            width, height = self.get_window_width(), self.get_window_height()
            left_dist, right_dist, top_dist, bottom_dist = x, width - x, y, height - y
            min_dist = min(left_dist, right_dist, top_dist, bottom_dist)
            if min_dist == left_dist: self.home_direction = 'left'
            elif min_dist == right_dist: self.home_direction = 'right'
            elif min_dist == top_dist: self.home_direction = 'up'
            else: self.home_direction = 'down'
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} (re)determined home direction: {self.home_direction}")

    def move_in_direction(self, direction):
        speed = self.move_speed
        prev_x, prev_y = self.squid_data['x'], self.squid_data['y']
        
        squid_width = self.squid_data.get('squid_width', 50)
        squid_height = self.squid_data.get('squid_height', 50)
        win_width = self.get_window_width()
        win_height = self.get_window_height()

        if direction == 'left': self.squid_data['x'] = max(0, self.squid_data['x'] - speed)
        elif direction == 'right': self.squid_data['x'] = min(win_width - squid_width, self.squid_data['x'] + speed)
        elif direction == 'up': self.squid_data['y'] = max(0, self.squid_data['y'] - speed)
        elif direction == 'down': self.squid_data['y'] = min(win_height - squid_height, self.squid_data['y'] + speed)
        
        self.squid_data['direction'] = direction
        if direction in ['left', 'right']: self.squid_data['image_direction_key'] = direction # For visual orientation
        
        moved_dist = math.sqrt((self.squid_data['x'] - prev_x)**2 + (self.squid_data['y'] - prev_y)**2)
        self.distance_traveled += moved_dist

    def move_toward(self, target_x, target_y):
        current_x, current_y = self.squid_data['x'], self.squid_data['y']
        # Consider squid center for more accurate dx, dy if needed, but top-left is fine for general direction
        # current_center_x = self.squid_data['x'] + self.squid_data.get('squid_width', 50) / 2
        # current_center_y = self.squid_data['y'] + self.squid_data.get('squid_height', 50) / 2
        
        dx, dy = target_x - current_x, target_y - current_y # Target relative to squid's top-left
        chosen_direction = self.squid_data.get('direction', 'right') # Default/current direction

        # Only change direction if significantly off-axis or if the primary axis of movement changes
        if abs(dx) > self.move_speed / 2 or abs(dy) > self.move_speed / 2: 
            if abs(dx) > abs(dy): # More horizontal movement needed
                chosen_direction = 'right' if dx > 0 else 'left'
            else: # More vertical movement needed
                chosen_direction = 'down' if dy > 0 else 'up'
        
        self.move_in_direction(chosen_direction)

    def find_nearby_food(self):
        food_items = self.get_food_items_from_scene()
        if not food_items: return None
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_food, min_dist = None, float('inf')
        for food in food_items:
            if not self.is_object_valid(food): continue
            # Ensure we don't target food being carried by this squid itself (if such a state is possible)
            # if getattr(food, 'is_carried_by_autopilot_id', None) == self.squid_data.get('node_id'): continue

            dist = self.distance_between(squid_pos, self.get_object_position(food))
            if dist < min_dist: 
                min_dist = dist
                closest_food = food
        return closest_food if closest_food and min_dist < 300 else None # 300px detection range for food

    def find_nearby_stealable_item(self):
        items = self.get_stealable_items_from_scene() # This already filters out remote clones
        if not items: return None
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_item, min_dist = None, float('inf')
        for item_obj in items:
            if not self.is_object_valid(item_obj): continue
            # is_stealable_target also has checks, but good to be robust.
            # Here, get_stealable_items_from_scene should have already filtered appropriately.

            dist = self.distance_between(squid_pos, self.get_object_position(item_obj))
            if dist < min_dist: 
                min_dist = dist
                closest_item = item_obj
        detection_radius = 200 # Detection range for stealable items
        return closest_item if closest_item and min_dist < detection_radius else None

    def get_food_items_from_scene(self):
        food_items = []
        if not self.scene: return food_items
        for item in self.scene.items():
            try:
                # Skip items that are clones from other remote players or not visible
                if getattr(item, 'is_remote_clone', False) or not item.isVisible():
                    continue

                is_food = False
                if hasattr(item, 'category') and getattr(item, 'category', None) == 'food':
                    is_food = True
                elif hasattr(item, 'filename'): # Fallback to filename check
                    filename_attr = getattr(item, 'filename', '')
                    filename = str(filename_attr).lower() if filename_attr is not None else ''
                    if any(ft in filename for ft in ['food', 'sushi', 'cheese']):
                        is_food = True
                
                if is_food and item not in food_items: # Ensure not already added
                     food_items.append(item)
            except Exception as e:
                if self.debug_mode: self._log_decision(f"Error checking item for food: {e}") # Log error
        return food_items

    def get_stealable_items_from_scene(self):
        stealable_items = []
        if not self.scene: return stealable_items
        for item_obj in self.scene.items():
            try:
                if not item_obj.isVisible() or getattr(item_obj, 'is_remote_clone', False):
                    continue # Skip invisible or already remote clones

                item_category_val = getattr(item_obj, 'category', None)
                item_category = str(item_category_val).lower() if item_category_val is not None else ''
                item_filename_val = getattr(item_obj, 'filename', None)
                item_filename = str(item_filename_val).lower() if item_filename_val is not None else ''
                
                is_rock = item_category == 'rock' or 'rock' in item_filename
                is_urchin = item_category == 'urchin' or 'urchin' in item_filename

                if (is_rock or is_urchin) and item_obj not in stealable_items:
                    stealable_items.append(item_obj)
            except Exception as e:
                if self.debug_mode: self._log_decision(f"Error checking item for stealable: {e}") # Log error
        return stealable_items

    def is_in_vision_range(self, item): # General large vision range, less critical for autopilot's direct targeting
        if not item or not self.is_object_valid(item): return False
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        obj_pos = self.get_object_position(item)
        return self.distance_between(squid_pos, obj_pos) < 800 

    def animate_movement(self, squid_data, remote_visual): # Currently advisory
        if self.debug_mode: self._log_decision(f"Animate_movement called (advisory function).")

    def eat_food(self, food_item): # Called when squid is at food_item
        food_name = os.path.basename(getattr(food_item, 'filename', 'UnknownFood'))
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} attempting to 'eat' {food_name}")
        self._log_decision(f"Action: Eating food '{food_name}'.")
        
        # Update internal stats for summary
        self.squid_data['hunger'] = max(0, self.squid_data.get('hunger', 50) - 15) 
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 10)
        
        # Signal to mp_plugin_logic (via RemoteEntityManager or directly) to handle actual item removal from scene
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'remove_item_from_scene'):
            self.remote_entity_manager.remove_item_from_scene(food_item)
            self._log_decision(f"Signaled RemoteEntityManager to remove food '{food_name}'.")
        elif self.plugin_instance and hasattr(self.plugin_instance, 'request_item_removal'):
            self.plugin_instance.request_item_removal(food_item) # Fallback if no entity manager
            self._log_decision(f"Requested plugin_instance to remove food '{food_name}'.")
        else:
            self._log_decision(f"EatFood: Could not signal for removal of food '{food_name}'. Item may persist visually.")


    def interact_with_rock(self, rock_item): # This method is somewhat legacy now due to generic interact_with_object
        item_name = os.path.basename(getattr(rock_item, 'filename', 'UnknownItem'))
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')[-4:]} 'interacted' with item {item_name}")
        self._log_decision(f"Action: Generic interaction with '{item_name}'.")
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 5)

    def is_stealable_target(self, item_obj): # Determines if an item can be targeted for stealing
        if not self.is_object_valid(item_obj): return False
        
        # Crucially, do not attempt to steal items that are already clones from other remote players
        if getattr(item_obj, 'is_remote_clone', False):
            return False
        # Add any other flags that might indicate an item is not "original" to this scene
        # e.g., if trophies brought by other squids have a special flag like 'is_foreign_trophy'
        # if getattr(item_obj, 'is_foreign_trophy_from_other_player', False): return False

        item_category_val = getattr(item_obj, 'category', None)
        item_category = str(item_category_val).lower() if item_category_val is not None else ''
        item_filename_val = getattr(item_obj, 'filename', None)
        item_filename = str(item_filename_val).lower() if item_filename_val is not None else ''
        
        is_rock = item_category == 'rock' or ('rock' in item_filename)
        is_urchin = item_category == 'urchin' or ('urchin' in item_filename)
        
        return is_rock or is_urchin

    def is_object_valid(self, obj):
        # Check if object is not None, belongs to the current scene, and is visible
        return obj is not None and hasattr(obj, 'scene') and obj.scene() is self.scene and obj.isVisible()

    def get_object_position(self, obj):
        if obj and hasattr(obj, 'pos'): 
            pos_method = getattr(obj, 'pos')
            if callable(pos_method):
                pos = pos_method()
                return (pos.x(), pos.y())
        if self.debug_mode: self._log_decision(f"Warning: get_object_position called with invalid/unsuitable object: {obj}")
        return (self.squid_data.get('x',0), self.squid_data.get('y',0))

    def distance_between(self, pos1, pos2):
        try:
            return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
        except TypeError:
            self._log_decision(f"Error calculating distance between {pos1} and {pos2}. Positions might be invalid.")
            return float('inf') # Return a large distance if positions are bad

    def get_window_width(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_width'):
            return self.remote_entity_manager.window_width
        elif self.scene and hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().width()
        return self.window_width

    def get_window_height(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_height'):
            return self.remote_entity_manager.window_height
        elif self.scene and hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().height()
        return self.window_height

    def is_at_boundary(self, direction):
        x, y = self.squid_data['x'], self.squid_data['y']
        squid_w = self.squid_data.get('squid_width', 50)
        squid_h = self.squid_data.get('squid_height', 50)
        boundary_threshold = 5 

        win_width = self.get_window_width()
        win_height = self.get_window_height()

        if direction == 'left': return x <= boundary_threshold
        elif direction == 'right': return x + squid_w >= win_width - boundary_threshold
        elif direction == 'up': return y <= boundary_threshold
        elif direction == 'down': return y + squid_h >= win_height - boundary_threshold
        return False

    def get_summary(self):
        # Ensure rocks_stolen accurately reflects the count of items in carried_items_data
        actual_items_carried_count = len(self.carried_items_data)
        if self.rocks_stolen != actual_items_carried_count:
            self._log_decision(f"Summary: Discrepancy found! self.rocks_stolen was {self.rocks_stolen}, but len(self.carried_items_data) is {actual_items_carried_count}. Updating to actual count.")
            self.rocks_stolen = actual_items_carried_count

        return {
            'time_away': round(self.time_away, 2),
            'food_eaten': self.food_eaten_count,
            'rock_interactions': self.rock_interaction_count,
            'rocks_stolen': self.rocks_stolen, 
            'carried_items_details': self.carried_items_data, 
            'distance_traveled': round(self.distance_traveled, 2),
            'final_state': self.state, 
            'node_id': self.squid_data.get('node_id', 'UnknownNode')
        }