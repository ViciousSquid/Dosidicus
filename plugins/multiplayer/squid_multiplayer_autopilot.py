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
        self.rock_interaction_count = 0
        self.distance_traveled = 0

        self.loot_target_id = None
        self.loot_target_type = None
        self.squid_data['stolen_item_id'] = None
        self.squid_data['stolen_item_type'] = None

        self.move_speed = 5
        self.direction_change_prob = 0.02 
        self.next_decision_time = 0
        self.decision_interval = 0.5  

        self.last_update_time = time.time()

        if self.debug_mode:
            log_x = self.squid_data.get('x', 'N/A') 
            log_y = self.squid_data.get('y', 'N/A')
            print(f"[AutoPilot] Initialized for remote squid {self.squid_data.get('node_id', 'UnknownNode')} at ({log_x}, {log_y})")
            print(f"[AutoPilot] Will consider returning home after {self.max_time_away} seconds. Determined home direction: {self.home_direction}")

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

        if self.time_away > self.max_time_away and self.state not in ["returning", "STEALING_ITEM_AND_EXITING", "RETURNING_HOME_EMPTY_HANDED", "exited"]:
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} time to go home: {self.time_away:.1f}s/{self.max_time_away:.1f}s. Current state: {self.state}")
            if self.state in ["SEARCHING_FOR_LOOT", "MOVING_TO_LOOT_ITEM"]:
                self.state = "RETURNING_HOME_EMPTY_HANDED"
            else: 
                self.state = "returning"

        if self.state == "exploring":
            self.explore()
        elif self.state == "feeding":
            self.seek_food()
        elif self.state == "interacting":
            self.interact_with_object() 
        elif self.state == "returning": 
            self.return_home()
        elif self.state == "SEARCHING_FOR_LOOT":
            self._state_searching_for_loot()
        elif self.state == "MOVING_TO_LOOT_ITEM":
            self._state_moving_to_loot_item()
        elif self.state == "STEALING_ITEM_AND_EXITING":
            self._state_stealing_item_and_exiting()
        elif self.state == "RETURNING_HOME_EMPTY_HANDED":
            self._state_returning_home_empty_handed()
        elif self.state == "exited":
            pass 

        if self.state != "exited" and self.remote_entity_manager:
            self.remote_entity_manager.update_remote_squid(self.squid_data['node_id'], self.squid_data, is_new_arrival=False)

    def explore(self):
        # Low chance to randomly change direction, doesn't prevent other actions this cycle
        if random.random() < self.direction_change_prob: # Default 0.02
            new_direction = random.choice(['left', 'right', 'up', 'down'])
            if self.debug_mode:
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Randomly changed direction to {new_direction}")
            self.squid_data['direction'] = new_direction
        
        # --- START MODIFIED BEHAVIOR PRIORITY ---
        # Priority 1: High chance to decide to search for loot items
        if random.random() < 0.80: # 80% chance to INITIATE a loot search
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Decided to search for loot (80% trigger), -> SEARCHING_FOR_LOOT")
            self.state = "SEARCHING_FOR_LOOT"
            return # State changed, decision made for this cycle

        # Priority 2: High chance to pursue food IF food is detected nearby
        # This check runs if the squid didn't decide to search for loot in this cycle
        food = self.find_nearby_food()
        if food: # Food is present
            if random.random() < 0.80: # 80% chance to go for PRESENT food
                self.target_object = food
                self.state = "feeding"
                if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Spotted food and decided to pursue (80% trigger), -> feeding")
                return # State changed
            elif self.debug_mode: # Decided not to pursue the food this time (20% chance)
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Spotted food but ignored it this cycle (20% chance).")
        
        # Priority 3: Lower chance for simple rock interaction (non-stealing)
        # This runs if no loot search was initiated AND (no food was found OR food was found but ignored)
        elif random.random() < 0.05: # Keep this relatively low
            rock = self.find_nearby_rock() 
            if rock:
                self.target_object = rock
                self.state = "interacting" 
                if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} exploring: Spotted rock for simple interaction (5% trigger), -> interacting")
                return # State changed
        # --- END MODIFIED BEHAVIOR PRIORITY ---

        # Default action if no other state transition occurred: Continue moving in the current direction
        self.move_in_direction(self.squid_data['direction'])

    def _state_searching_for_loot(self):
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} is in SEARCHING_FOR_LOOT")
        lootable_item = self.find_lootable_item()

        if lootable_item:
            self.target_object = lootable_item
            self.loot_target_id = getattr(lootable_item, 'filename', 'unknown_item_id') 
            
            if self.is_rock(lootable_item):
                self.loot_target_type = 'rock'
            elif self.is_decoration(lootable_item): 
                self.loot_target_type = 'decoration'
            else: 
                self.loot_target_type = 'unknown'

            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} found loot: {self.loot_target_type} ({self.loot_target_id}), -> MOVING_TO_LOOT_ITEM")
            self.state = "MOVING_TO_LOOT_ITEM"
        else:
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} found no loot, -> RETURNING_HOME_EMPTY_HANDED")
            self.state = "RETURNING_HOME_EMPTY_HANDED"
            
    def find_lootable_item(self):
        items = self.scene.items()
        lootable_items = []
        for item_qgraphicsobject in items:
            if not item_qgraphicsobject.isVisible():
                continue
            if self.is_rock(item_qgraphicsobject):
                lootable_items.append(item_qgraphicsobject)
                continue
            if self.is_decoration(item_qgraphicsobject): # Assumes is_decoration checks for movable if necessary
                lootable_items.append(item_qgraphicsobject)
        return random.choice(lootable_items) if lootable_items else None

    def _state_moving_to_loot_item(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost loot target, -> SEARCHING_FOR_LOOT")
            self.state = "SEARCHING_FOR_LOOT"
            self.target_object = None; self.loot_target_id = None; self.loot_target_type = None
            return

        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])
        if self.distance_between((self.squid_data['x'], self.squid_data['y']), target_pos) < 50:
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} reached loot {self.loot_target_type}, -> STEALING_ITEM_AND_EXITING")
            self.squid_data['stolen_item_id'] = self.loot_target_id 
            self.squid_data['stolen_item_type'] = self.loot_target_type
            if self.loot_target_type == 'rock': self.squid_data['status'] = "carrying rock"
            elif self.loot_target_type == 'decoration': self.squid_data['status'] = "pushing decoration"
            self.state = "STEALING_ITEM_AND_EXITING"
        
    def _state_stealing_item_and_exiting(self):
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} is STEALING_ITEM_AND_EXITING with {self.squid_data.get('stolen_item_type')}")
        self.move_in_direction(self.home_direction) 
        if self.is_at_boundary(self.home_direction):
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} reached boundary with loot.")
            self.return_home() 
            
    def _state_returning_home_empty_handed(self):
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} is RETURNING_HOME_EMPTY_HANDED")
        self.squid_data['stolen_item_id'] = None 
        self.squid_data['stolen_item_type'] = None
        self.squid_data['status'] = "returning"
        self.return_home() 

    def seek_food(self):
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost food target, -> exploring")
            self.state = "exploring"; self.target_object = None; return
        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])
        if self.distance_between((self.squid_data['x'], self.squid_data['y']), target_pos) < 50:
            self.eat_food(self.target_object) 
            self.target_object = None; self.state = "exploring"
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} ate food. Count: {self.food_eaten_count}")

    def interact_with_object(self): 
        if not self.target_object or not self.is_object_valid(self.target_object):
            if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} lost rock target (for simple interact), -> exploring")
            self.state = "exploring"; self.target_object = None; return
        target_pos = self.get_object_position(self.target_object)
        self.move_toward(target_pos[0], target_pos[1])
        if self.distance_between((self.squid_data['x'], self.squid_data['y']), target_pos) < 50:
            if self.is_rock(self.target_object): 
                self.rock_interaction_count += 1
                if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} interacted with rock. Count: {self.rock_interaction_count}")
                self.squid_data['status'] = "played with rock"
            self.target_object = None
            self.state = "exploring"

    def return_home(self):
        if not self.home_direction:
            self.determine_home_direction() 
            if self.debug_mode: print(f"[AutoPilot] Warning: Squid {self.squid_data.get('node_id')} home_direction determined late: {self.home_direction}")
        current_status = self.squid_data.get('status', 'returning')
        if 'stealing' not in current_status and 'carrying' not in current_status and 'pushing' not in current_status:
            self.squid_data['status'] = "returning home" 
        self.move_in_direction(self.home_direction)
        if self.is_at_boundary(self.home_direction):
            if self.debug_mode:
                summary = self.get_summary() 
                print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} reached home boundary: {self.home_direction}. Summary: {summary}")
            if self.plugin_instance:
                if hasattr(self.plugin_instance, 'handle_remote_squid_return_signal'):
                    self.plugin_instance.handle_remote_squid_return_signal(self.squid_data['node_id'], self)
                elif hasattr(self.plugin_instance, 'complete_remote_squid_return'): 
                     self.plugin_instance.complete_remote_squid_return(self.squid_data['node_id'], self.get_summary(), self.home_direction)
                else: 
                    exit_payload_for_broadcast = self.plugin_instance._get_squid_state_for_exit(self.home_direction, remote_squid_data=self.squid_data.copy())
                    if exit_payload_for_broadcast:
                        self.plugin_instance.network_node.broadcast_message("SQUID_EXIT", exit_payload_for_broadcast)
                if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} signalled exit.")
            self.state = "exited"

    def determine_home_direction(self):
        entry_dir = self.squid_data.get('entry_direction_on_this_screen')
        if entry_dir:
            opposite_map = {'left': 'right', 'right': 'left', 'top': 'down', 'down': 'up', 'center_fallback': random.choice(['left', 'right', 'up', 'down'])}
            self.home_direction = opposite_map.get(entry_dir, random.choice(['left', 'right', 'up', 'down']))
        else: 
            x, y = self.squid_data['x'], self.squid_data['y']
            width, height = self.get_window_width(), self.get_window_height()
            min_dist = min(x, width - x, y, height - y)
            if min_dist == x: self.home_direction = 'left'
            elif min_dist == width - x: self.home_direction = 'right'
            elif min_dist == y: self.home_direction = 'up'
            else: self.home_direction = 'down'
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} (re)determined home dir: {self.home_direction}")

    def move_in_direction(self, direction):
        speed = self.move_speed
        prev_x, prev_y = self.squid_data['x'], self.squid_data['y']
        squid_w = self.squid_data.get('squid_width', 50); squid_h = self.squid_data.get('squid_height', 50)
        if direction == 'left': self.squid_data['x'] = max(0, self.squid_data['x'] - speed)
        elif direction == 'right': self.squid_data['x'] = min(self.get_window_width() - squid_w, self.squid_data['x'] + speed)
        elif direction == 'up': self.squid_data['y'] = max(0, self.squid_data['y'] - speed)
        elif direction == 'down': self.squid_data['y'] = min(self.get_window_height() - squid_h, self.squid_data['y'] + speed)
        self.squid_data['direction'] = direction
        if direction in ['left', 'right']: self.squid_data['image_direction_key'] = direction
        self.distance_traveled += math.sqrt((self.squid_data['x'] - prev_x)**2 + (self.squid_data['y'] - prev_y)**2)

    def move_toward(self, target_x, target_y):
        dx = target_x - self.squid_data['x']; dy = target_y - self.squid_data['y']
        chosen_direction = self.squid_data.get('direction', 'right')
        if abs(dx) > self.move_speed / 2 or abs(dy) > self.move_speed / 2:
            chosen_direction = 'right' if dx > 0 else 'left' if abs(dx) > abs(dy) else 'down' if dy > 0 else 'up'
        self.move_in_direction(chosen_direction)

    def find_nearby_food(self):
        return self._find_nearby_item_by_category_or_filename('food', ['food', 'sushi', 'cheese'], 300)

    def find_nearby_rock(self):
        return self._find_nearby_item_by_category_or_filename('rock', ['rock'], 200)

    def _find_nearby_item_by_category_or_filename(self, category_name, filename_keywords, detection_range):
        items_in_scene = self.get_items_from_scene_by_category_or_filename(category_name, filename_keywords)
        if not items_in_scene: return None
        squid_pos = (self.squid_data['x'], self.squid_data['y'])
        closest_item = None; min_dist = float('inf')
        for item in items_in_scene:
            if not self.is_object_valid(item): continue
            dist = self.distance_between(squid_pos, self.get_object_position(item))
            if dist < min_dist: min_dist = dist; closest_item = item
        return closest_item if closest_item and min_dist < detection_range else None

    def get_items_from_scene_by_category_or_filename(self, category_name, filename_keywords):
        found_items = []
        if not self.scene: return found_items
        for item in self.scene.items():
            try:
                is_category_match = hasattr(item, 'category') and getattr(item, 'category', None) == category_name
                is_filename_match = False
                if hasattr(item, 'filename'):
                    filename = getattr(item, 'filename', '').lower()
                    is_filename_match = any(kw in filename for kw in filename_keywords)
                if item.isVisible() and (is_category_match or (is_filename_match and not is_category_match)): # check category first
                    if item not in found_items: found_items.append(item)
            except Exception as e:
                if self.debug_mode: print(f"[AutoPilot] Error checking item for {category_name}: {e}")
        return found_items
        
    def eat_food(self, food_item):
        if self.debug_mode: print(f"[AutoPilot] Squid {self.squid_data.get('node_id')} 'ate' food item {food_item}")
        self.squid_data['hunger'] = max(0, self.squid_data.get('hunger', 50) - 15)
        self.squid_data['happiness'] = min(100, self.squid_data.get('happiness', 50) + 10)
        self.food_eaten_count += 1 

    def is_rock(self, item):
        if not self.is_object_valid(item): return False
        if hasattr(item, 'category') and getattr(item, 'category', None) == 'rock': return True
        if hasattr(item, 'filename') and 'rock' in getattr(item, 'filename', '').lower(): return True
        return False

    def is_decoration(self, item):
        if not self.is_object_valid(item): return False
        item_category = getattr(item, 'category', None)
        if item_category == 'decoration' or item_category == 'plant': return True
        if hasattr(item, 'filename'): # Fallback check by filename keywords
            fn = getattr(item, 'filename', '').lower()
            if any(dec_kw in fn for dec_kw in ['plant', 'decor', 'toy', 'shell', 'coral', 'gem', 'statue']): return True
        return False

    def is_object_valid(self, obj):
        # Ensure object is not None, has a scene method, is part of the current scene, and is visible
        return obj is not None and hasattr(obj, 'scene') and obj.scene() is self.scene and obj.isVisible()

    def get_object_position(self, obj):
        if obj and hasattr(obj, 'pos'): return (obj.pos().x(), obj.pos().y())
        return (self.squid_data.get('x',0), self.squid_data.get('y',0))

    def distance_between(self, pos1, pos2):
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)

    def get_window_width(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_width'): return self.remote_entity_manager.window_width
        if hasattr(self.scene, 'sceneRect') and self.scene.sceneRect(): return self.scene.sceneRect().width()
        return self.window_width

    def get_window_height(self):
        if self.remote_entity_manager and hasattr(self.remote_entity_manager, 'window_height'): return self.remote_entity_manager.window_height
        if hasattr(self.scene, 'sceneRect') and self.scene.sceneRect(): return self.scene.sceneRect().height()
        return self.window_height

    def is_at_boundary(self, direction):
        x, y = self.squid_data['x'], self.squid_data['y']
        squid_w = self.squid_data.get('squid_width', 50); squid_h = self.squid_data.get('squid_height', 50)
        threshold = 5 
        win_width = self.get_window_width(); win_height = self.get_window_height()
        if direction == 'left': return x <= threshold
        elif direction == 'right': return x + squid_w >= win_width - threshold
        elif direction == 'up': return y <= threshold
        elif direction == 'down': return y + squid_h >= win_height - threshold
        return False

    def get_summary(self):
        summary = {
            'time_away': round(self.time_away, 2),
            'food_eaten': self.food_eaten_count,
            'rock_interactions': self.rock_interaction_count, 
            'distance_traveled': round(self.distance_traveled, 2),
            'final_state': self.state,
            'node_id': self.squid_data.get('node_id', 'UnknownNode'),
            'stolen_item_id': self.squid_data.get('stolen_item_id'),
            'stolen_item_type': self.squid_data.get('stolen_item_type')
        }
        if summary['stolen_item_id'] is None: del summary['stolen_item_id']
        if summary['stolen_item_type'] is None: del summary['stolen_item_type']
        return summary