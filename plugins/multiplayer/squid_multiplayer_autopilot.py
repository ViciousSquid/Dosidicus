import random
import math
import sys
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

        # Store node_id for convenience and consistent use
        self.node_id = self.squid_data.get('node_id', 'UnknownRemoteNode')
        self.short_node_id = self.node_id[-4:] # For concise console logs if needed

        # Unique log file per remote squid instance
        self.log_file_name = f"autopilot_decisions_remote_{self.node_id}.txt"

        # Clear/initialize the log file for this session
        if self.debug_mode:
            try:
                with open(self.log_file_name, 'w', encoding='utf-8') as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Log for remote squid {self.node_id} (controller instance) started.\n")
            except Exception as e:
                print(f"[AutoPilotSetup] Error clearing/creating log file {self.log_file_name}: {e}")

        self.entry_time = squid_data.get('entry_time', time.time())
        self.entry_position = squid_data.get('entry_position', None) # Tuple (x,y) if provided
        self.window_width = squid_data.get('window_width', 1280) # Provided by host context
        self.window_height = squid_data.get('window_height', 900) # Provided by host context

        entry_dir_on_this_screen = squid_data.get('entry_direction_on_this_screen')
        if entry_dir_on_this_screen:
            opposite_map = {
                'left': 'right', 'right': 'left',
                'up': 'down', 'down': 'up',
                'top': 'down', 'bottom': 'up', # Aliases for clarity
                'center_fallback': random.choice(['left', 'right', 'up', 'down']) # Should not happen if entry_dir valid
            }
            self.home_direction = opposite_map.get(entry_dir_on_this_screen.lower(), random.choice(['left', 'right', 'up', 'down']))
        else:
            # Fallback if entry_direction_on_this_screen is not provided in squid_data
            # This will be called again in return_home if still None, using current position.
            self.home_direction = squid_data.get('home_direction') # Use if provided directly
            if not self.home_direction:
                 # If still None, defer final determination to when return_home is called.
                 # For __init__, it's okay if it's None here, as determine_home_direction() will be called.
                 self._log_decision(f"__init__: home_direction not determined yet (entry_direction_on_this_screen missing). Will determine later.")


        self.state = "exploring"
        self.squid_data['status'] = "exploring" # Autopilot sets its own status

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
        
        self.move_speed = 4.5 
        self.direction_change_prob = 0.15 
        self.next_decision_time = 0 
        self.decision_interval = 0.5 # Time between major decision evaluations in seconds

        self.last_update_time = time.time()

        # Initial console print for immediate feedback (uses short_node_id)
        print(f"[AutoPilot __init__ {self.short_node_id}] Initialized. State: {self.state}, Status: {self.squid_data['status']}")
        print(f"[AutoPilot __init__ {self.short_node_id}] Max Time: {self.max_time_away}s. Max Carry: {self.max_rocks_to_steal}. Home Dir: {self.home_direction if self.home_direction else 'TBD'}")
        
        # Initial log to the dedicated file
        self._log_decision(f"Controller Initialized. Start State: {self.state}, Start Status: {self.squid_data['status']}, Max Time: {self.max_time_away:.1f}s, Max Carry: {self.max_rocks_to_steal}, Home Dir: {self.home_direction if self.home_direction else 'To be determined'}, Speed: {self.move_speed}, DirChangeProb: {self.direction_change_prob}")

    def _log_decision(self, decision_text: str):
        if not self.debug_mode:
            return
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        log_entry = f"[{timestamp}] [SquidID: {self.node_id}] {decision_text}\n"
        
        try:
            with open(self.log_file_name, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[AutoPilotDecisionFileError] Could not write to {self.log_file_name} for SquidID {self.node_id}: {e}")
            print(f"[AutoPilotDecisionFallbackLog] {log_entry.strip()}")

    def _capture_item_properties(self, game_item_object) -> dict | None:
        if not game_item_object or not self.is_object_valid(game_item_object):
            self._log_decision(f"CaptureItemAttempt: FAILED - Target item is invalid or None ('{getattr(game_item_object, 'filename', game_item_object)}').")
            return None

        item_pos = self.get_object_position(game_item_object)
        item_filename = getattr(game_item_object, 'filename', 'unknown_item.png')
        item_category = getattr(game_item_object, 'category', 'unknown')
        item_scale = game_item_object.scale() if hasattr(game_item_object, 'scale') else 1.0
        item_z_value = game_item_object.zValue() if hasattr(game_item_object, 'zValue') else 0.0
        # item_rotation = game_item_object.rotation() if hasattr(game_item_object, 'rotation') else 0.0


        properties = {
            'original_filename': item_filename,
            'original_category': item_category,
            'original_x': item_pos[0], 
            'original_y': item_pos[1],
            'scale': item_scale,
            'zValue': item_z_value,
            # 'rotation': item_rotation,
        }
        base_name = os.path.basename(item_filename) if isinstance(item_filename, str) else "unknown_item_name"
        self._log_decision(f"CaptureItemSuccess: Captured properties for '{base_name}': Scale {properties['scale']:.2f}, Category '{properties['original_category']}'.")
        return properties

    def update(self, delta_time=None):

        current_time_autopilot = time.time() 
        
        if delta_time is None:
            delta_time = current_time_autopilot - self.last_update_time
        self.last_update_time = current_time_autopilot

        # Ensure delta_time is non-negative and reasonable
        delta_time = max(0, delta_time)
        if delta_time > 1.0: # Cap delta_time to prevent huge jumps if there was a long pause
            self._log_decision(f"Warning: Large delta_time detected: {delta_time:.2f}s. Capping to 1.0s for this update.")
            delta_time = 1.0

        self.time_away += delta_time

        self._log_decision(f"Update Cycle Begin. State='{self.state}', Status='{self.squid_data.get('status', 'N/A')}', TimeAway={self.time_away:.1f}/{self.max_time_away:.1f}s, NextDecisionAt={self.next_decision_time:.3f}, DeltaT={delta_time:.3f}")

        if current_time_autopilot < self.next_decision_time:
            self.move_in_direction(self.squid_data['direction'])
            if self.remote_entity_manager:
                self.remote_entity_manager.update_remote_squid(self.node_id, self.squid_data, is_new_arrival=False)
            self._log_decision(f"Update Cycle: Holding decision. Moving {self.squid_data['direction']}. Pos: ({self.squid_data['x']:.1f}, {self.squid_data['y']:.1f})")
            return

        self._log_decision(f"Update Cycle: Making new decision. Old state: '{self.state}', Old status: '{self.squid_data.get('status', 'N/A')}'")
        self.next_decision_time = current_time_autopilot + self.decision_interval
        
        if self.time_away > self.max_time_away and self.state != "returning" and self.state != "exited":
            old_state_before_timeout = self.state
            self.state = "returning"
            self.squid_data['status'] = "returning home (timeout)"
            self._log_decision(f"Update Cycle: Max time away ({self.max_time_away:.1f}s) EXCEEDED. Forcing state change: {old_state_before_timeout} -> {self.state}.")

        # State machine
        if self.state == "exploring":
            self.explore()
        elif self.state == "feeding":
            self.seek_food()
        elif self.state == "interacting":
            self.interact_with_object()
        elif self.state == "returning":
            self.return_home()
        elif self.state == "exited":
            self._log_decision("Update Cycle: State is 'exited'. No further action.")
            return 

        # After state logic, update visuals if not exited
        if self.remote_entity_manager and self.state != "exited":
            self.remote_entity_manager.update_remote_squid(self.node_id, self.squid_data, is_new_arrival=False)
        self._log_decision(f"Update Cycle End. New State='{self.state}', New Status='{self.squid_data.get('status', 'N/A')}'")


    def explore(self):
        self._log_decision(f"Explore State: Current direction: {self.squid_data.get('direction')}. Time away: {self.time_away:.1f}s.")
        
        if self.squid_data.get('status') != "exploring": # Ensure status matches state
            self.squid_data['status'] = "exploring"
            self._log_decision(f"Explore: (Status corrected to 'exploring')")

        # This check is now also in update(), but keeping it here as a safeguard for explore's logic
        if self.time_away > self.max_time_away:
            old_state = self.state
            self.state = "returning"
            self.squid_data['status'] = "returning home (explore timeout)"
            self._log_decision(f"Explore: Max time away ({self.max_time_away:.1f}s) reached. State change: {old_state} -> {self.state}.")
            return

        if random.random() < self.direction_change_prob:
            old_direction = self.squid_data.get('direction', 'N/A')
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            if new_direction == old_direction: # Try to pick a different one
                choices = list(set(['left', 'right', 'up', 'down']) - {old_direction})
                new_direction = random.choice(choices) if choices else new_direction
            self.squid_data['direction'] = new_direction
            self._log_decision(f"Explore: Random direction change {old_direction} -> {new_direction} (Prob: {self.direction_change_prob:.2f}).")
        else:
            self._log_decision(f"Explore: No random direction change (Prob: {self.direction_change_prob:.2f}). Sticking to {self.squid_data.get('direction')}.")
        
        self.move_in_direction(self.squid_data.get('direction', 'right')) # Move first

        food_check_prob = 0.20 
        steal_check_prob = 0.30 

        if random.random() < food_check_prob:
            food = self.find_nearby_food() # This logs internally now
            if food:
                self.target_object = food
                old_state = self.state
                self.state = "feeding"
                self.squid_data['status'] = "heading to food"
                target_name = os.path.basename(getattr(self.target_object, 'filename', 'UnknownFood'))
                self._log_decision(f"Explore: Spotted food '{target_name}'. State change: {old_state} -> {self.state}.")
                return 
            # else: find_nearby_food logs if nothing found
        
        if self.state == "exploring" and random.random() < steal_check_prob: 
            if len(self.carried_items_data) < self.max_rocks_to_steal:
                stealable_item = self.find_nearby_stealable_item() # This logs internally now
                if stealable_item:
                    self.target_object = stealable_item
                    old_state = self.state
                    self.state = "interacting"
                    self.squid_data['status'] = "checking item"
                    item_type = getattr(self.target_object, 'category', 'item')
                    item_name = os.path.basename(getattr(self.target_object, 'filename', f'Unknown{item_type.capitalize()}'))
                    self._log_decision(f"Explore: Spotted stealable {item_type} '{item_name}'. State change: {old_state} -> {self.state}.")
                    return
            else: # Log if wanted to steal but couldn't due to carry limit
                if len(self.carried_items_data) >= self.max_rocks_to_steal:
                    self._log_decision(f"Explore: Considered stealing item, but already carrying max ({len(self.carried_items_data)}/{self.max_rocks_to_steal}).")
        
        if self.state == "exploring": # If no other action taken
             self._log_decision(f"Explore: No new targets. Continuing exploration in direction {self.squid_data.get('direction')}.")


    def seek_food(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            old_target_name = os.path.basename(getattr(self.target_object, 'filename', 'previous food target'))
            old_state = self.state
            self.state = "exploring"
            self.squid_data['status'] = "exploring"
            self._log_decision(f"SeekFood: Lost or invalid food target '{old_target_name}'. State change: {old_state} -> {self.state}.")
            self.target_object = None
            return

        if self.squid_data.get('status') != "heading to food":
            self.squid_data['status'] = "heading to food"
            self._log_decision(f"SeekFood: (Status corrected to 'heading to food')")
            
        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)
        food_name = os.path.basename(getattr(self.target_object, 'filename', 'UnknownFood'))

        self._log_decision(f"SeekFood: Moving towards '{food_name}' at ({target_pos[0]:.1f}, {target_pos[1]:.1f}). Distance: {distance:.1f}.")

        if distance < 50: 
            self.eat_food(self.target_object) # This method already logs "Action: Eating food"
            self.food_eaten_count += 1
            old_state = self.state
            self.state = "exploring" 
            self.squid_data['status'] = "exploring" # Reset status after eating
            self._log_decision(f"SeekFood: Successfully ate food '{food_name}'. Food count: {self.food_eaten_count}. State change: {old_state} -> {self.state}.")
            self.target_object = None


    def interact_with_object(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            old_target_name = os.path.basename(getattr(self.target_object, 'filename', 'previous item target'))
            old_state = self.state
            self.state = "exploring"
            self.squid_data['status'] = "exploring"
            self._log_decision(f"Interact: Lost or invalid item target '{old_target_name}'. State change: {old_state} -> {self.state}.")
            self.target_object = None
            self.stealing_phase = False
            return

        current_status = self.squid_data.get('status', '')
        if current_status != "checking item" and not self.stealing_phase: # Only set if not already in a carrying/stealing related status
            self.squid_data['status'] = "checking item"
            self._log_decision(f"Interact: (Status set to 'checking item')")

        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)
        item_name_for_log = os.path.basename(getattr(self.target_object, 'filename', 'UnknownItem'))
        self._log_decision(f"Interact: Moving towards '{item_name_for_log}' at ({target_pos[0]:.1f}, {target_pos[1]:.1f}). Distance: {distance:.1f}.")

        if distance < 50: 
            self.rock_interaction_count += 1
            attempt_steal_chance = 0.4

            if (self.is_stealable_target(self.target_object) and
                len(self.carried_items_data) < self.max_rocks_to_steal and
                random.random() < attempt_steal_chance):

                item_data_to_carry = self._capture_item_properties(self.target_object)
                if item_data_to_carry:
                    self.carried_items_data.append(item_data_to_carry)
                    self.rocks_stolen = len(self.carried_items_data) 
                    self.squid_data['carrying_rock'] = True 
                    self.stealing_phase = True 

                    item_type_stolen = item_data_to_carry.get('original_category', 'item')
                    item_name_stolen = os.path.basename(item_data_to_carry.get('original_filename', f'UnknownItem'))
                    
                    self.squid_data['status'] = f"carrying {item_type_stolen.lower()}"
                    self._log_decision(f"Interact: SUCCEEDED steal of {item_type_stolen} '{item_name_stolen}'. Status: {self.squid_data['status']}. Carrying {self.rocks_stolen}/{self.max_rocks_to_steal}.")
                    
                    if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'hide_item_temporarily'):
                        self.remote_entity_manager.hide_item_temporarily(self.target_object)

                    if self.rocks_stolen >= self.max_rocks_to_steal:
                        old_state = self.state
                        self.state = "returning"
                        self.squid_data['status'] = "returning home" # Set status for returning
                        self._log_decision(f"Interact: Met carrying quota ({self.rocks_stolen}/{self.max_rocks_to_steal}). State change: {old_state} -> {self.state}.")
                        self.target_object = None 
                        self.stealing_phase = False # Done with stealing for now
                        return 
                else:
                    self._log_decision(f"Interact: Attempted steal but FAILED to capture properties for target '{item_name_for_log}'.")
            else: 
                reason = ""
                if not self.is_stealable_target(self.target_object): reason = "target not stealable type"
                elif len(self.carried_items_data) >= self.max_rocks_to_steal: reason = "carrying quota met"
                else: reason = f"failed {attempt_steal_chance*100:.0f}% steal chance"
                self._log_decision(f"Interact: Interacted with '{item_name_for_log}'. Did not steal (Reason: {reason}). Total interactions: {self.rock_interaction_count}.")
            
            old_state = self.state 
            self.target_object = None
            self.state = "exploring"
            self.squid_data['status'] = "exploring" # Reset status
            self.stealing_phase = False # Reset stealing phase
            self._log_decision(f"Interact: Interaction logic complete for '{item_name_for_log}'. State change: {old_state} -> {self.state}.")


    def return_home(self):
        if self.squid_data.get('status') != "returning home" and not self.squid_data.get('status', '').startswith("returning home"): # Check variants
            self.squid_data['status'] = "returning home"
            self._log_decision(f"ReturnHome: (Status set to 'returning home')")

        if not self.home_direction: # Should have been set by __init__ or explore timeout
            self.determine_home_direction() # Recalculate if somehow lost
            self._log_decision(f"ReturnHome: home_direction was None, re-determined: {self.home_direction}.")

        self.move_in_direction(self.home_direction) # This method now logs boundary hits and turns
        self._log_decision(f"ReturnHome: Moving towards {self.home_direction}. Position: ({self.squid_data['x']:.1f}, {self.squid_data['y']:.1f}).")

        if self.is_at_boundary(self.home_direction):
            summary = self.get_summary() 
            self._log_decision(f"ReturnHome: Reached home boundary ({self.home_direction}). Exiting. Summary: Ate {summary['food_eaten']}, Interacted {summary['rock_interactions']}, Stole {summary['rocks_stolen']} items.")
            
            if self.plugin_instance and hasattr(self.plugin_instance, 'handle_remote_squid_return'):
                self.plugin_instance.handle_remote_squid_return(self.node_id, self) 
            else:
                self._log_decision(f"ReturnHome: CRITICAL - plugin_instance or handle_remote_squid_return method missing for {self.node_id}.")

            self.state = "exited" 
            self.squid_data['status'] = "exited" # Final status for this controller instance
            self._log_decision(f"ReturnHome: State set to 'exited'.")


    def move_in_direction(self, direction):
        speed = self.move_speed
        prev_x, prev_y = self.squid_data['x'], self.squid_data['y']
        
        squid_width = self.squid_data.get('squid_width', 50)
        squid_height = self.squid_data.get('squid_height', 50)
        win_width = self.get_window_width()
        win_height = self.get_window_height()

        new_x, new_y = self.squid_data['x'], self.squid_data['y']
        original_direction = str(direction) # Keep a copy for logging
        current_effective_direction = str(direction) # What direction it will actually end up going

        if current_effective_direction == 'left': new_x -= speed
        elif current_effective_direction == 'right': new_x += speed
        elif current_effective_direction == 'up': new_y -= speed
        elif current_effective_direction == 'down': new_y += speed
        
        boundary_hit_log_message = ""

        # Horizontal boundary check
        if new_x <= 0:
            new_x = 0
            current_effective_direction = 'right'
            boundary_hit_log_message = f"Hit left boundary (was going {original_direction}), turning right."
        elif new_x + squid_width >= win_width:
            new_x = win_width - squid_width
            current_effective_direction = 'left'
            boundary_hit_log_message = f"Hit right boundary (was going {original_direction}), turning left."
        
        # Vertical boundary check (can override horizontal turn if cornered)
        if new_y <= 0:
            new_y = 0
            # If it also hit a side, the horizontal turn takes precedence for the new 'direction'
            # but we still log the vertical hit.
            if not boundary_hit_log_message: current_effective_direction = 'down' # Only change if not already turning from side
            boundary_hit_log_message += (" " if boundary_hit_log_message else "") + f"Hit top boundary (was going {original_direction}), ensuring not moving further up."
        elif new_y + squid_height >= win_height:
            new_y = win_height - squid_height
            if not boundary_hit_log_message: current_effective_direction = 'up'
            boundary_hit_log_message += (" " if boundary_hit_log_message else "") + f"Hit bottom boundary (was going {original_direction}), ensuring not moving further down."

        if boundary_hit_log_message and boundary_hit_log_message != "No boundary hit.": # Log if a boundary was actually hit
             self._log_decision(f"Move: {boundary_hit_log_message} New effective direction: {current_effective_direction}. Pos: ({new_x:.1f},{new_y:.1f})")

        self.squid_data['x'] = new_x
        self.squid_data['y'] = new_y
        self.squid_data['direction'] = current_effective_direction 
        
        if current_effective_direction in ['left', 'right', 'up', 'down']:
            self.squid_data['image_direction_key'] = current_effective_direction
        
        moved_dist = math.sqrt((self.squid_data['x'] - prev_x)**2 + (self.squid_data['y'] - prev_y)**2)
        self.distance_traveled += moved_dist

    def move_toward(self, target_x, target_y):
        current_x = self.squid_data['x'] + self.squid_data.get('squid_width', 50) / 2
        current_y = self.squid_data['y'] + self.squid_data.get('squid_height', 50) / 2
        
        dx, dy = target_x - current_x, target_y - current_y
        chosen_direction = self.squid_data.get('direction', 'right')

        if abs(dx) > self.move_speed / 2 or abs(dy) > self.move_speed / 2: 
            if abs(dx) > abs(dy) * 1.2: # Prioritize horizontal if significantly greater
                chosen_direction = 'right' if dx > 0 else 'left'
            elif abs(dy) > abs(dx) * 1.2: # Prioritize vertical if significantly greater
                chosen_direction = 'down' if dy > 0 else 'up'
            else: # Diagonal-ish: pick dominant or maintain current if aligned
                if abs(dx) > abs(dy):
                    chosen_direction = 'right' if dx > 0 else 'left'
                else:
                    chosen_direction = 'down' if dy > 0 else 'up'
        
        if chosen_direction != self.squid_data.get('direction'):
            self._log_decision(f"MoveToward: Target ({target_x:.0f},{target_y:.0f}), Current ({current_x:.0f},{current_y:.0f}). Direction changed to {chosen_direction}.")
        
        self.move_in_direction(chosen_direction)

    def find_nearby_food(self):
        self._log_decision(f"FIND_NEARBY_FOOD: Entered method for {self.node_id}.")
        food_items = self.get_food_items_from_scene() 
        if not food_items:
            self._log_decision(f"FIND_NEARBY_FOOD: No food items returned by get_food_items_from_scene for {self.node_id}.")
            return None
        
        self._log_decision(f"FIND_NEARBY_FOOD: Found {len(food_items)} potential food items for {self.node_id}.")
        
        squid_pos = (self.squid_data['x'] + self.squid_data.get('squid_width',0)/2, 
                     self.squid_data['y'] + self.squid_data.get('squid_height',0)/2)
        closest_food, min_dist = None, float('inf')

        for i, food in enumerate(food_items):
            self._log_decision(f"FIND_NEARBY_FOOD: Processing item {i} for {self.node_id}. Type of self: {type(self)}")
            self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - Type of food: {type(food)}, Filename: {getattr(food, 'filename', 'N/A')}")
            
            food_center_pos = None # Initialize
            try:
                self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - Attempting INLINED get_object_center_position logic for food item...")
                
                # --- Start of inlined get_object_center_position logic ---
                if food and self.is_object_valid(food): # self.is_object_valid uses 'self' from find_nearby_food context
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - Food item IS valid for inlined logic.")
                    
                    item_rect_local = food.boundingRect() 
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - food.boundingRect() = {item_rect_local}")
                    
                    item_pos_scene = food.pos()
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - food.pos() = {item_pos_scene}")
                    
                    # --- Break down the calculation for center_x ---
                    pos_x_val = None
                    rect_center_obj = None
                    rect_center_x_val = None

                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - About to call item_pos_scene.x()")
                    pos_x_val = item_pos_scene.x()
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - item_pos_scene.x() result: {pos_x_val}")

                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - About to call item_rect_local.center()")
                    rect_center_obj = item_rect_local.center()
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - item_rect_local.center() result: {rect_center_obj}")

                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - About to call rect_center_obj.x()")
                    rect_center_x_val = rect_center_obj.x()
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - rect_center_obj.x() result: {rect_center_x_val}")
                    
                    center_x = pos_x_val + rect_center_x_val
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - center_x calculated: {center_x}")
                    # --- End breakdown for center_x ---
                    
                    # --- Break down the calculation for center_y (similarly) ---
                    pos_y_val = None
                    # rect_center_obj is already available if center_x calculation passed and rect_center_obj is not None
                    rect_center_y_val = None

                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - About to call item_pos_scene.y(). item_pos_scene type: {type(item_pos_scene)}, value: {item_pos_scene}")
                    try:
                        pos_y_val = item_pos_scene.y() 
                        self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - item_pos_scene.y() result: {pos_y_val}")
                    except Exception as e_y_call: # More specific catch for the .y() call
                        self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - *** EXCEPTION SPECIFICALLY during item_pos_scene.y() call: {type(e_y_call).__name__}: {e_y_call} ***")
                        if hasattr(item_pos_scene, 'isNull'): # Check if it's a QPointF that might be null
                             self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - item_pos_scene.isNull(): {item_pos_scene.isNull()}")
                        raise 

                    # rect_center_obj was already fetched for center_x
                    if rect_center_obj is not None: 
                        self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - About to call rect_center_obj.y()")
                        rect_center_y_val = rect_center_obj.y()
                        self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - rect_center_obj.y() result: {rect_center_y_val}")
                    else:
                        self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - rect_center_obj was None, cannot get .y()")
                        raise ValueError("rect_center_obj became None before y calculation for inlined logic")

                    # Ensure values are not None before addition if they could be
                    if pos_y_val is None or rect_center_y_val is None:
                        self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - pos_y_val or rect_center_y_val is None. Cannot calculate center_y.")
                        raise ValueError("Cannot calculate center_y due to None component for inlined logic")

                    center_y = pos_y_val + rect_center_y_val
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - center_y calculated: {center_y}")
                    # --- End breakdown for center_y ---
                    
                    food_center_pos = (center_x, center_y)
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - INLINED logic SUCCEEDED. Result: {food_center_pos}")
                else:
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - Food item NOT valid for inlined logic (obj was None or self.is_object_valid(food) was False).")

            except Exception as e_inline: 
                self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - *** Outer Exception during INLINED logic: {type(e_inline).__name__}: {e_inline} ***")
                import sys 
                exc_type, exc_obj, exc_tb = sys.exc_info()
                if exc_tb:
                    fname = exc_tb.tb_frame.f_code.co_filename
                    self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - Outer Exception was at {fname}:{exc_tb.tb_lineno}")
                raise 
            
            if food_center_pos is None:
                self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - food_center_pos is None after inlined logic. Skipping.")
                continue

            dist = self.distance_between(squid_pos, food_center_pos)
            self._log_decision(f"FIND_NEARBY_FOOD: Item {i} - Distance to food: {dist:.1f}")
            if dist < min_dist: 
                min_dist = dist
                closest_food = food
        
        detection_radius = 300 
        chosen_food = closest_food if closest_food and min_dist < detection_radius else None
        
        if chosen_food:
            self._log_decision(f"FindFood: Target acquired for {self.node_id}: {os.path.basename(getattr(chosen_food, 'filename', 'N/A'))} at distance {min_dist:.1f}.")
        elif food_items: 
            min_dist_str = f"{min_dist:.1f}" if min_dist != float('inf') else "N/A" 
            self._log_decision(f"FindFood: Food items detected for {self.node_id} ({len(food_items)}), but none close/suitable (min_dist: {min_dist_str}, detection_radius: {detection_radius}).")
        else: 
            self._log_decision(f"FindFood: No food items found in scene for {self.node_id}.")
            
        return chosen_food

    def find_nearby_stealable_item(self):
        items = self.get_stealable_items_from_scene() # This now logs periodically
        if not items: return None

        squid_pos = (self.squid_data['x'] + self.squid_data.get('squid_width',0)/2, 
                     self.squid_data['y'] + self.squid_data.get('squid_height',0)/2)
        closest_item, min_dist = None, float('inf')

        for item_obj in items:
            # is_object_valid should have been called by get_stealable_items_from_scene implicitly
            item_center_pos = self.get_object_center_position(item_obj)
            if item_center_pos is None: continue
            
            dist = self.distance_between(squid_pos, item_center_pos)
            if dist < min_dist: 
                min_dist = dist
                closest_item = item_obj
        
        detection_radius = 200
        chosen_item = closest_item if closest_item and min_dist < detection_radius else None
        if chosen_item:
            self._log_decision(f"FindStealable: Target acquired: {os.path.basename(getattr(chosen_item, 'filename', 'N/A'))} at distance {min_dist:.1f}.")
        elif items:
            min_dist_str = f"{min_dist:.1f}" if min_dist != float('inf') else "N/A"
            self._log_decision(f"FindStealable: Stealable items detected ({len(items)}), but none close/suitable (min_dist: {min_dist_str}, detection_radius: {detection_radius}).")
        return chosen_item

    def get_food_items_from_scene(self):
        food_items = []
        if not self.scene: 
            if self.debug_mode: self._log_decision("get_food_items: Scene not available.")
            return food_items
        
        items_checked_count = 0
        scene_items_list = list(self.scene.items()) 

        for item in scene_items_list:
            items_checked_count += 1
            try:
                if not self.is_object_valid(item): # Use the enhanced is_object_valid
                    continue

                is_food = False
                item_category = str(getattr(item, 'category', '')).lower()
                item_filename = str(getattr(item, 'filename', '')).lower()

                if item_category == 'food':
                    is_food = True
                elif any(ft_keyword in item_filename for ft_keyword in ['food', 'sushi', 'cheese']):
                    is_food = True
                
                if is_food:
                     food_items.append(item)
            except Exception as e:
                if self.debug_mode: self._log_decision(f"get_food_items: Error checking item - {type(item)}: {e}")
        
        if self.debug_mode and (random.random() < 0.05 or not food_items): 
             log_food_names = [os.path.basename(getattr(f, 'filename', 'N/A')) for f in food_items]
             self._log_decision(f"get_food_items: Checked {items_checked_count} scene items. Found {len(food_items)} food: [{', '.join(log_food_names)}].")
        return food_items

    def get_stealable_items_from_scene(self):
        stealable_items = []
        if not self.scene: 
            if self.debug_mode: self._log_decision("get_stealable_items: Scene not available.")
            return stealable_items
            
        items_checked_count = 0
        scene_items_list = list(self.scene.items())

        for item_obj in scene_items_list:
            items_checked_count +=1
            try:
                if not self.is_object_valid(item_obj): # Use the enhanced is_object_valid
                    continue
                
                # Crucially, do not attempt to steal items that are already clones from other remote players
                # This check is now also part of is_stealable_target, but good to have consistency
                if getattr(item_obj, 'is_remote_clone', False):
                    continue

                item_category = str(getattr(item_obj, 'category', '')).lower()
                item_filename = str(getattr(item_obj, 'filename', '')).lower()
                
                is_rock = item_category == 'rock' or ('rock' in item_filename)
                is_urchin = item_category == 'urchin' or ('urchin' in item_filename)

                if (is_rock or is_urchin):
                    stealable_items.append(item_obj)
            except Exception as e:
                if self.debug_mode: self._log_decision(f"get_stealable_items: Error checking item - {type(item_obj)}: {e}")
        
        if self.debug_mode and (random.random() < 0.05 or not stealable_items):
            log_item_names = [os.path.basename(getattr(s, 'filename', 'N/A')) for s in stealable_items]
            self._log_decision(f"get_stealable_items: Checked {items_checked_count} scene items. Found {len(stealable_items)} stealable: [{', '.join(log_item_names)}].")
        return stealable_items

    def is_in_vision_range(self, item): 
        if not item or not self.is_object_valid(item): return False
        squid_center_pos = (self.squid_data['x'] + self.squid_data.get('squid_width',0)/2, 
                           self.squid_data['y'] + self.squid_data.get('squid_height',0)/2)
        obj_center_pos = self.get_object_center_position(item)
        if obj_center_pos is None: return False
        return self.distance_between(squid_center_pos, obj_center_pos) < 800 # Generic large range

    def animate_movement(self, squid_data, remote_visual): 
        if self.debug_mode: self._log_decision(f"Animate_movement called (currently advisory). Pos: ({squid_data.get('x',0):.1f}, {squid_data.get('y',0):.1f}) Dir: {squid_data.get('direction')}")

    def eat_food(self, food_item): 
        food_name = os.path.basename(getattr(food_item, 'filename', 'UnknownFood'))
        self._log_decision(f"Action: Eating food '{food_name}'. Current hunger: {self.squid_data.get('hunger', 50):.1f}.")
        
        self.squid_data['hunger'] = max(0, self.squid_data.get('hunger', 50) - 25) # More significant hunger reduction
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 15)
        
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'remove_item_from_scene'):
            self.remote_entity_manager.remove_item_from_scene(food_item)
            self._log_decision(f"Signaled RemoteEntityManager to remove eaten food '{food_name}'. New hunger: {self.squid_data['hunger']:.1f}")
        else:
            self._log_decision(f"EatFood: Could not signal for removal of food '{food_name}'.")

    def interact_with_rock(self, rock_item): # Legacy, use interact_with_object
        item_name = os.path.basename(getattr(rock_item, 'filename', 'UnknownItem'))
        self._log_decision(f"Action: Legacy interact_with_rock called for '{item_name}'.")
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 5)

    def is_stealable_target(self, item_obj): 
        if not self.is_object_valid(item_obj): return False
        if getattr(item_obj, 'is_remote_clone', False): # Should not steal clones
            self._log_decision(f"is_stealable_target: Item '{getattr(item_obj, 'filename', 'N/A')}' is a remote clone. Cannot steal.")
            return False

        item_category = str(getattr(item_obj, 'category', '')).lower()
        item_filename = str(getattr(item_obj, 'filename', '')).lower()
        
        is_rock = item_category == 'rock' or ('rock' in item_filename)
        is_urchin = item_category == 'urchin' or ('urchin' in item_filename) # Example of another stealable
        
        # Add more conditions for stealable items if needed
        # e.g. is_plant = item_category == 'plant' or ('plant' in item_filename)
        
        can_steal = is_rock or is_urchin # or is_plant etc.
        if can_steal and self.debug_mode:
            self._log_decision(f"is_stealable_target: Item '{item_filename}' (cat: {item_category}) IS stealable.")
        elif not can_steal and self.debug_mode:
            self._log_decision(f"is_stealable_target: Item '{item_filename}' (cat: {item_category}) is NOT stealable.")
        return can_steal


    def is_object_valid(self, obj):
        if obj is None:
            if self.debug_mode: self._log_decision("is_object_valid: FAILED - Object is None.")
            return False
        
        has_scene_attr = hasattr(obj, 'scene')
        obj_scene_instance = obj.scene() if has_scene_attr and callable(obj.scene) else None
        
        is_in_correct_scene = obj_scene_instance is self.scene
        
        is_visible_attr = hasattr(obj, 'isVisible')
        is_currently_visible = obj.isVisible() if is_visible_attr and callable(obj.isVisible) else True 
        
        valid = is_in_correct_scene and is_currently_visible

        if not valid and self.debug_mode: # Log only if invalid and debugging
            filename_info = getattr(obj, 'filename', str(type(obj)))
            reasons = []
            if not is_in_correct_scene:
                reasons.append(f"Scene mismatch/None (ItemSceneID: {id(obj_scene_instance) if obj_scene_instance else 'None'}, AutopilotSceneID: {id(self.scene) if self.scene else 'None'})")
            if not is_currently_visible:
                reasons.append("Not visible")
            self._log_decision(f"is_object_valid: Item '{filename_info}' FAILED validation. Reasons: {'; '.join(reasons) if reasons else 'Unknown'}")
            
        return valid

    def get_object_position(self, obj): # Gets top-left
        if obj and hasattr(obj, 'pos') and callable(obj.pos):
            pos_qpointf = obj.pos()
            return (pos_qpointf.x(), pos_qpointf.y())
        if self.debug_mode: self._log_decision(f"Warning: get_object_position failed for object: {getattr(obj, 'filename', type(obj))}")
        return (self.squid_data.get('x',0), self.squid_data.get('y',0)) # Fallback

    def get_object_center_position(self, obj):
        if obj and self.is_object_valid(obj): # Ensure it's valid before getting rect
            try:
                # QGraphicsPixmapItem.boundingRect() is in item's local coordinates.
                # We need its sceneBoundingRect for global center, or combine pos() with boundingRect().center()
                item_rect_local = obj.boundingRect() # Local bounds
                item_pos_scene = obj.pos() # Top-left in scene
                center_x = item_pos_scene.x() + item_rect_local.center().x()
                center_y = item_pos_scene.y() + item_rect_local.center().y()
                return (center_x, center_y)
            except Exception as e:
                if self.debug_mode: self._log_decision(f"Error getting center for {getattr(obj, 'filename', type(obj))}: {e}")
        return None


    def distance_between(self, pos1, pos2):
        try:
            return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
        except TypeError: # If pos1 or pos2 is None or not subscriptable
            self._log_decision(f"Error in distance_between: Invalid input. Pos1: {pos1}, Pos2: {pos2}")
            return float('inf')

    def get_window_width(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_width'):
            return self.remote_entity_manager.window_width
        elif self.scene and hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().width()
        return self.window_width # Fallback to initial value

    def get_window_height(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_height'):
            return self.remote_entity_manager.window_height
        elif self.scene and hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().height()
        return self.window_height # Fallback to initial value

    def is_at_boundary(self, direction_moving_towards: str):
        x, y = self.squid_data['x'], self.squid_data['y']
        squid_w = self.squid_data.get('squid_width', 50)
        squid_h = self.squid_data.get('squid_height', 50)
        # Threshold for being "at" the boundary to trigger exit
        # Should be small enough that it's definitely at edge, but not so small it overshoots.
        boundary_exit_threshold = self.move_speed * 1.5 # Approx 1.5 move steps from edge

        win_width = self.get_window_width()
        win_height = self.get_window_height()

        if direction_moving_towards == 'left': return x <= boundary_exit_threshold
        elif direction_moving_towards == 'right': return x + squid_w >= win_width - boundary_exit_threshold
        elif direction_moving_towards == 'up': return y <= boundary_exit_threshold
        elif direction_moving_towards == 'down': return y + squid_h >= win_height - boundary_exit_threshold
        return False

    def determine_home_direction(self):
        # This method determines the "exit" direction from the current client's perspective
        # to get "home" (back to its original instance).
        entry_dir_on_this_screen = self.squid_data.get('entry_direction_on_this_screen')
        opposite_map = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up', 'top': 'down', 'bottom': 'up'}
        
        if entry_dir_on_this_screen and entry_dir_on_this_screen.lower() in opposite_map:
            self.home_direction = opposite_map[entry_dir_on_this_screen.lower()]
            self._log_decision(f"DetermineHomeDir: Determined home direction '{self.home_direction}' as opposite of entry_direction '{entry_dir_on_this_screen}'.")
        else:
            # Fallback: if entry direction was unclear, choose the closest edge as the exit.
            # This is less ideal as it might not be the true "opposite" of how it entered.
            x, y = self.squid_data.get('x', self.get_window_width()/2), self.squid_data.get('y', self.get_window_height()/2)
            width, height = self.get_window_width(), self.get_window_height()
            
            distances_to_edge = {
                'left': x,
                'right': width - (x + self.squid_data.get('squid_width', 50)),
                'up': y,
                'down': height - (y + self.squid_data.get('squid_height', 50))
            }
            # Choose the edge it is currently closest to as its "home" direction.
            self.home_direction = min(distances_to_edge, key=distances_to_edge.get)
            self._log_decision(f"DetermineHomeDir: Fallback - entry_direction unclear. Closest edge chosen as home_direction: '{self.home_direction}'. Distances: {distances_to_edge}")

    def get_summary(self):
        actual_items_carried_count = len(self.carried_items_data)
        if self.rocks_stolen != actual_items_carried_count: # Ensure consistency
            self._log_decision(f"Summary: Correcting 'rocks_stolen' from {self.rocks_stolen} to actual carried count {actual_items_carried_count}.")
            self.rocks_stolen = actual_items_carried_count

        summary_data = {
            'time_away': round(self.time_away, 2),
            'food_eaten': self.food_eaten_count,
            'rock_interactions': self.rock_interaction_count, # Total interactions with stealable types
            'rocks_stolen': self.rocks_stolen, # Count of items successfully "stolen" and data captured
            'carried_items_details': list(self.carried_items_data), # Ensure it's a list copy
            'distance_traveled': round(self.distance_traveled, 2),
            'final_state_on_this_client': self.state, 
            'node_id': self.node_id # ID of the squid this controller is for
        }
        self._log_decision(f"GetSummary: Generating summary - Food: {summary_data['food_eaten']}, Interactions: {summary_data['rock_interactions']}, Stolen: {summary_data['rocks_stolen']}, Items: {len(summary_data['carried_items_details'])}")
        return summary_data