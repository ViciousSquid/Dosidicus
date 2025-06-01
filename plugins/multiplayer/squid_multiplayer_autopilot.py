import random
import math
import time
import os
from PyQt5 import QtCore, QtGui, QtWidgets

class RemoteSquidController:
    """Controls behavior of squids away from their home instance"""

    def __init__(self, squid_data, scene, plugin_instance=None, debug_mode=False, remote_entity_manager=None):
        self.squid_data = squid_data.copy()
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
        self.target_object = None
        self.time_away = 0
        self.max_time_away = random.randint(60, 180)

        self.food_eaten_count = 0
        self.rock_interaction_count = 0 # Interpreted as "stealable item interaction count"
        self.distance_traveled = 0

        self.rocks_stolen = 0 # Interpreted as "stealable items stolen count"
        self.max_rocks_to_steal = random.randint(1, 3)
        self.stealing_phase = False

        self.move_speed = 4.5
        self.direction_change_prob = 0.15
        self.next_decision_time = 0
        self.decision_interval = 0.5

        self.last_update_time = time.time()

        if self.debug_mode:
            log_x = self.squid_data.get('x', 'N/A')
            log_y = self.squid_data.get('y', 'N/A')
            print(f"[AutoPilot] Initialized for remote squid {self.squid_data.get('node_id', 'UnknownNode')} at ({log_x}, {log_y})")
            print(f"[AutoPilot] Will consider returning home after {self.max_time_away} seconds. Determined home direction: {self.home_direction}")

        self._log_decision(f"Initialized. State: {self.state}, Max Time: {self.max_time_away:.1f}s, Max Steal: {self.max_rocks_to_steal}, Home Dir: {self.home_direction}, Speed: {self.move_speed}, DirChangeProb: {self.direction_change_prob}")

    def _log_decision(self, decision_text: str):
        if not self.debug_mode:
            return
        
        log_file_name = "autopilot_decisions.txt"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        node_id_str = self.squid_data.get('node_id', 'UnknownNode')
        
        log_entry = f"[{timestamp}] [SquidID: {node_id_str}] {decision_text}\n"
        
        try:
            with open(log_file_name, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"[AutoPilotDecisionFileError] Could not write to {log_file_name}: {e}")
            print(f"[AutoPilotDecisionFallbackLog] {log_entry.strip()}")

    def update(self, delta_time=None):
        current_time = time.time()
        if delta_time is None:
            delta_time = current_time - self.last_update_time
        self.last_update_time = current_time

        self.time_away += delta_time

        if current_time < self.next_decision_time:
            self.move_in_direction(self.squid_data['direction'])
            if self.remote_entity_manager:
                self.remote_entity_manager.update_remote_squid(self.squid_data['node_id'], self.squid_data, is_new_arrival=False)
            return

        self.next_decision_time = current_time + self.decision_interval

        if self.time_away > self.max_time_away and self.state != "returning":
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} time to go home: {self.time_away:.1f}s/{self.max_time_away:.1f}s")
            old_state = self.state
            self.state = "returning"
            self._log_decision(f"State change: {old_state} -> returning. Reason: Max time away ({self.time_away:.1f}s / {self.max_time_away:.1f}s).")

        if self.state == "exploring":
            self.explore()
        elif self.state == "feeding":
            self.seek_food()
        elif self.state == "interacting":
            self.interact_with_object()
        elif self.state == "returning":
            self.return_home()

        if self.remote_entity_manager:
            self.remote_entity_manager.update_remote_squid(self.squid_data['node_id'], self.squid_data, is_new_arrival=False)

    def explore(self):
        if random.random() < self.direction_change_prob:
            old_direction = self.squid_data.get('direction', 'N/A')
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Changed direction to {new_direction}")
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
                target_name = getattr(self.target_object, 'filename', 'UnknownFood')
                if isinstance(target_name, str): target_name = os.path.basename(target_name)
                self._log_decision(f"Explore: Spotted food '{target_name}'. State change: {old_state} -> feeding.")
            else:
                self._log_decision(f"Explore: Checked for food (prob {food_check_prob*100}%), none found suitable/nearby.")
        
        elif random.random() < steal_check_prob: 
            stealable_item = self.find_nearby_stealable_item()
            if stealable_item:
                self.target_object = stealable_item
                old_state = self.state
                self.state = "interacting"
                item_type = getattr(self.target_object, 'category', 'item')
                item_name = getattr(self.target_object, 'filename', f'Unknown{item_type.capitalize()}')
                if isinstance(item_name, str): item_name = os.path.basename(item_name)
                self._log_decision(f"Explore: Spotted stealable {item_type} '{item_name}'. State change: {old_state} -> interacting.")
            else:
                self._log_decision(f"Explore: Checked for stealable items (prob {steal_check_prob*100}%), none found suitable/nearby.")

    def seek_food(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost food target, returning to exploring")
            old_target_name = getattr(self.target_object, 'filename', 'previous target')
            if isinstance(old_target_name, str): old_target_name = os.path.basename(old_target_name)
            old_state = self.state
            self.state = "exploring"
            self._log_decision(f"SeekFood: Lost target '{old_target_name}'. State change: {old_state} -> exploring.")
            self.target_object = None
            return

        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)

        if distance < 50: 
            food_name = getattr(self.target_object, 'filename', 'UnknownFood')
            if isinstance(food_name, str): food_name = os.path.basename(food_name)
            self.eat_food(self.target_object) 
            self.food_eaten_count += 1
            old_state = self.state
            self.state = "exploring"
            self._log_decision(f"SeekFood: Ate food '{food_name}'. Food count: {self.food_eaten_count}. State change: {old_state} -> exploring.")
            self.target_object = None
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} ate food, food count: {self.food_eaten_count}")

    def interact_with_object(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost stealable item target, returning to exploring")
            old_target_name = getattr(self.target_object, 'filename', 'previous target')
            if isinstance(old_target_name, str): old_target_name = os.path.basename(old_target_name)
            old_state = self.state
            self.state = "exploring"
            self._log_decision(f"Interact: Lost target '{old_target_name}'. State change: {old_state} -> exploring.")
            self.target_object = None
            return

        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])

        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        distance = self.distance_between(squid_pos, target_pos)

        if distance < 50: 
            is_remotely_owned = getattr(self.target_object, 'is_remote', False) or \
                                getattr(self.target_object, 'is_remote_clone', False) 
            is_local_item_for_stealing = not is_remotely_owned

            self.rock_interaction_count += 1 
            attempt_steal_chance = 0.4

            if (self.is_stealable_target(self.target_object) and
                is_local_item_for_stealing and
                self.rocks_stolen < self.max_rocks_to_steal and
                random.random() < attempt_steal_chance):

                self.squid_data['carrying_rock'] = True 
                self.stealing_phase = True 
                self.rocks_stolen += 1

                item_type_stolen = getattr(self.target_object, 'category', 'item')
                item_name_stolen = getattr(self.target_object, 'filename', f'Unknown{item_type_stolen.capitalize()}')
                if isinstance(item_name_stolen, str): item_name_stolen = os.path.basename(item_name_stolen)
                
                self._log_decision(f"Interact: Attempted steal (chance {attempt_steal_chance*100}%) and SUCCEEDED. Stole {item_type_stolen} '{item_name_stolen}'. Total stolen: {self.rocks_stolen}.")
                
                if self.debug_mode:
                    print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'stole' a {item_type_stolen}! Total stolen: {self.rocks_stolen}")
                self.squid_data['status'] = f"stealing {item_type_stolen.lower()}"

                if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'hide_item_temporarily'):
                    self.remote_entity_manager.hide_item_temporarily(self.target_object)

                if self.rocks_stolen >= self.max_rocks_to_steal:
                    old_state = self.state
                    self.state = "returning"
                    self._log_decision(f"Interact: Met stealing quota ({self.rocks_stolen}/{self.max_rocks_to_steal}). State change: {old_state} -> returning.")
                    if self.debug_mode:
                        print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} met stealing quota, heading home")
                    self.target_object = None
                    return 
            else:
                reason = ""
                if not self.is_stealable_target(self.target_object): reason = "target not stealable type"
                elif not is_local_item_for_stealing: reason = "target is remotely owned/clone"
                elif self.rocks_stolen >= self.max_rocks_to_steal: reason = "stealing quota already met"
                else: reason = f"failed {attempt_steal_chance*100}% steal chance"
                
                item_type = getattr(self.target_object, 'category', 'item')
                item_name = getattr(self.target_object, 'filename', f'Unknown{item_type.capitalize()}')
                if isinstance(item_name, str): item_name = os.path.basename(item_name)
                self._log_decision(f"Interact: Interacted with {item_type} '{item_name}'. Did not steal (Reason: {reason}). Total interactions: {self.rock_interaction_count}.")
            
            old_state = self.state
            self.target_object = None
            self.state = "exploring"
            self._log_decision(f"Interact: Interaction with object complete. State change: {old_state} -> exploring.")

    def return_home(self):
        if not self.home_direction:
            self.determine_home_direction()
            self._log_decision(f"ReturnHome: Warning - home_direction was not set, fallback determined: {self.home_direction}.")

        if self.debug_mode and random.random() < 0.05:
            print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} returning home via {self.home_direction}, position: ({self.squid_data['x']:.1f}, {self.squid_data['y']:.1f})")

        self.move_in_direction(self.home_direction)

        if self.is_at_boundary(self.home_direction):
            summary = self.get_summary()
            self._log_decision(f"ReturnHome: Reached home boundary ({self.home_direction}). Exiting. Summary: Ate {summary['food_eaten']}, Interacted {summary['rock_interactions']}, Stole {summary['rocks_stolen']}.")
            
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} reached home boundary: {self.home_direction}")
                print(f"[AutoPilot] Summary: ate {summary['food_eaten']} food, interacted with {summary['rock_interactions']} items, stole {summary['rocks_stolen']} items, traveled {summary['distance_traveled']:.1f} pixels")
            
            if self.plugin_instance and hasattr(self.plugin_instance, 'handle_remote_squid_return'):
                self.plugin_instance.handle_remote_squid_return(self.squid_data['node_id'], self)
            else:
                self._log_decision(f"ReturnHome: Error - plugin_instance does not have handle_remote_squid_return method.")

            self.state = "exited"

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
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} (re)determined home direction: {self.home_direction}")

    def move_in_direction(self, direction):
        speed = self.move_speed
        prev_x, prev_y = self.squid_data['x'], self.squid_data['y']
        if direction == 'left': self.squid_data['x'] = max(0, self.squid_data['x'] - speed)
        elif direction == 'right': self.squid_data['x'] = min(self.get_window_width() - self.squid_data.get('squid_width', 50), self.squid_data['x'] + speed)
        elif direction == 'up': self.squid_data['y'] = max(0, self.squid_data['y'] - speed)
        elif direction == 'down': self.squid_data['y'] = min(self.get_window_height() - self.squid_data.get('squid_height', 50), self.squid_data['y'] + speed)
        self.squid_data['direction'] = direction
        if direction in ['left', 'right']: self.squid_data['image_direction_key'] = direction
        moved_dist = math.sqrt((self.squid_data['x'] - prev_x)**2 + (self.squid_data['y'] - prev_y)**2)
        self.distance_traveled += moved_dist

    def move_toward(self, target_x, target_y):
        current_x, current_y = self.squid_data['x'], self.squid_data['y']
        dx, dy = target_x - current_x, target_y - current_y
        chosen_direction = self.squid_data.get('direction', 'right')
        if abs(dx) > self.move_speed / 2 or abs(dy) > self.move_speed / 2:
            chosen_direction = 'right' if dx > 0 else 'left' if abs(dx) > abs(dy) else 'down' if dy > 0 else 'up'
        self.move_in_direction(chosen_direction)

    def find_nearby_food(self):
        food_items = self.get_food_items_from_scene()
        if not food_items: return None
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_food, min_dist = None, float('inf')
        for food in food_items:
            if not self.is_object_valid(food): continue
            dist = self.distance_between(squid_pos, self.get_object_position(food))
            if dist < min_dist: min_dist, closest_food = dist, food
        return closest_food if closest_food and min_dist < 300 else None

    def find_nearby_stealable_item(self):
        items = self.get_stealable_items_from_scene()
        if not items: return None
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_item, min_dist = None, float('inf')
        for item_obj in items:
            if not self.is_object_valid(item_obj): continue
            dist = self.distance_between(squid_pos, self.get_object_position(item_obj))
            if dist < min_dist: min_dist, closest_item = dist, item_obj
        detection_radius = 200
        return closest_item if closest_item and min_dist < detection_radius else None

    def get_food_items_from_scene(self):
        food_items = []
        if not self.scene: return food_items
        for item in self.scene.items():
            try:
                if hasattr(item, 'category') and getattr(item, 'category', None) == 'food':
                    if item.isVisible(): food_items.append(item)
                    continue
                if hasattr(item, 'filename'):
                    filename = getattr(item, 'filename', '').lower()
                    if any(ft in filename for ft in ['food', 'sushi', 'cheese']):
                        if item.isVisible() and item not in food_items: food_items.append(item)
            except Exception as e:
                if self.debug_mode: print(f"[AutoPilot] Error checking item for food: {e}")
        return food_items

    def get_stealable_items_from_scene(self):
        stealable_items = []
        if not self.scene: return stealable_items
        for item_obj in self.scene.items():
            try:
                item_category_val = getattr(item_obj, 'category', None)
                item_category = str(item_category_val).lower() if item_category_val is not None else ''
                item_filename_val = getattr(item_obj, 'filename', None)
                item_filename = str(item_filename_val).lower() if item_filename_val is not None else ''
                is_rock = item_category == 'rock' or 'rock' in item_filename
                is_urchin = item_category == 'urchin' or 'urchin' in item_filename
                if is_rock or is_urchin:
                    if item_obj.isVisible() and item_obj not in stealable_items:
                        stealable_items.append(item_obj)
            except Exception as e:
                if self.debug_mode: print(f"[AutoPilot] Error checking item for stealable (rock/urchin): {e}")
        return stealable_items

    def is_in_vision_range(self, item):
        if not item or not self.is_object_valid(item): return False
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        obj_pos = self.get_object_position(item)
        return self.distance_between(squid_pos, obj_pos) < 800

    def animate_movement(self, squid_data, remote_visual):
        if self.debug_mode: print(f"[AutoPilot] Animate_movement called (currently advisory, visual update by RemoteEntityManager)")

    def eat_food(self, food_item):
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'ate' food item {food_item}")
        self.squid_data['hunger'] = max(0, self.squid_data.get('hunger', 50) - 15)
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 10)

    def interact_with_rock(self, rock_item):
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'interacted' with item {rock_item}")
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 5)

    def is_stealable_target(self, item_obj):
        if not self.is_object_valid(item_obj): return False
        item_category_val = getattr(item_obj, 'category', None)
        item_category = str(item_category_val).lower() if item_category_val is not None else ''
        item_filename_val = getattr(item_obj, 'filename', None)
        item_filename = str(item_filename_val).lower() if item_filename_val is not None else ''
        is_rock = item_category == 'rock' or ('rock' in item_filename)
        is_urchin = item_category == 'urchin' or ('urchin' in item_filename)
        return is_rock or is_urchin

    def is_object_valid(self, obj):
        return obj is not None and hasattr(obj, 'scene') and obj.scene() is self.scene and obj.isVisible()

    def get_object_position(self, obj):
        if obj and hasattr(obj, 'pos'):
            pos = obj.pos()
            return (pos.x(), pos.y())
        return (self.squid_data.get('x', 0), self.squid_data.get('y', 0))

    def distance_between(self, pos1, pos2):
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def get_window_width(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_width'):
            return self.remote_entity_manager.window_width
        elif hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().width()
        return self.window_width

    def get_window_height(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_height'):
            return self.remote_entity_manager.window_height
        elif hasattr(self.scene, 'sceneRect') and self.scene.sceneRect():
            return self.scene.sceneRect().height()
        return self.window_height

    def is_at_boundary(self, direction):
        x, y = self.squid_data['x'], self.squid_data['y']
        squid_w = self.squid_data.get('squid_width', 50)
        squid_h = self.squid_data.get('squid_height', 50)
        boundary_threshold = 5
        win_width, win_height = self.get_window_width(), self.get_window_height()
        if direction == 'left': return x <= boundary_threshold
        elif direction == 'right': return x + squid_w >= win_width - boundary_threshold
        elif direction == 'up': return y <= boundary_threshold
        elif direction == 'down': return y + squid_h >= win_height - boundary_threshold
        return False

    def get_summary(self):
        return {
            'time_away': round(self.time_away, 2),
            'food_eaten': self.food_eaten_count,
            'rock_interactions': self.rock_interaction_count,
            'rocks_stolen': self.rocks_stolen,
            'distance_traveled': round(self.distance_traveled, 2),
            'final_state': self.state,
            'node_id': self.squid_data.get('node_id', 'UnknownNode')
        }