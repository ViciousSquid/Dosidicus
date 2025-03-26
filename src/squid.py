# Dosidicus
# Version 1.0.400       March 2025

import os
import random
from enum import Enum
import math
from PyQt5 import QtCore, QtGui, QtWidgets
from .mental_states import MentalStateManager
from .memory_manager import MemoryManager
from .personality import Personality

class Squid:
    def __init__(self, user_interface, tamagotchi_logic=None, personality=None, neuro_cooldown=None):
        self.ui = user_interface
        self.tamagotchi_logic = tamagotchi_logic
        self.memory_manager = MemoryManager()
        self.push_animation = None
        
        # Set neurogenesis cooldown (default to 60 seconds if not specified)
        self.neuro_cooldown = neuro_cooldown if neuro_cooldown is not None else 120

        self.load_images()
        self.load_poop_images()
        self.initialize_attributes()

        self.mental_state_manager = MentalStateManager(self, self.ui.scene)

        self.squid_item = QtWidgets.QGraphicsPixmapItem(self.current_image())
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.ui.scene.addItem(self.squid_item)

        self.ui.window.resizeEvent = self.handle_window_resize

        self.view_cone_item = None
        self.view_cone_visible = False
        self.poop_timer = None
        self.animation_speed = 1
        self.base_move_interval = 1000  # 1 second
        self.health = 100
        self.is_sick = False
        self.sick_icon_item = None
        self.sick_icon_offset = QtCore.QPointF(0, -100)  # Offset the sick icon above the squid

        self.status = "roaming"  # Initialize status

        self.view_cone_angle = math.pi / 2.5  # Squid has a view cone of 80 degrees
        self.current_view_angle = random.uniform(0, 2 * math.pi)
        self.view_cone_change_interval = 2500  # milliseconds
        self.last_view_cone_change = 0
        self.pursuing_food = False
        self.target_food = None

        self.satisfaction = 50
        self.anxiety = 10
        self.curiosity = 50

        if personality is None:
            self.personality = random.choice(list(Personality))
        else:
            self.personality = personality
        #self.tamagotchi_logic.squid_brain_window.print_to_console(f"Squid created with personality: {self.personality}")

    def set_animation_speed(self, speed):
        self.animation_speed = speed

    def load_images(self):
        self.images = {
            "left1": QtGui.QPixmap(os.path.join("images", "left1.png")),
            "left2": QtGui.QPixmap(os.path.join("images", "left2.png")),
            "right1": QtGui.QPixmap(os.path.join("images", "right1.png")),
            "right2": QtGui.QPixmap(os.path.join("images", "right2.png")),
            "up1": QtGui.QPixmap(os.path.join("images", "up1.png")),
            "up2": QtGui.QPixmap(os.path.join("images", "up2.png")),
            "sleep1": QtGui.QPixmap(os.path.join("images", "sleep1.png")),
            "sleep2": QtGui.QPixmap(os.path.join("images", "sleep2.png")),
        }
        self.squid_width = self.images["left1"].width()
        self.squid_height = self.images["left1"].height()

    def load_poop_images(self):
        self.poop_images = [
            QtGui.QPixmap(os.path.join("images", "poop1.png")),
            QtGui.QPixmap(os.path.join("images", "poop2.png"))
        ]
        self.poop_width = self.poop_images[0].width()
        self.poop_height = self.poop_images[0].height()

    def initialize_attributes(self):
        self.base_squid_speed = 90  # pixels per update at 1x speed
        self.base_vertical_speed = self.base_squid_speed // 2
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        self.squid_x = self.center_x
        self.squid_y = self.center_y
        self.squid_direction = "left"
        self.current_frame = 0
        self.update_preferred_vertical_range()

        self.hunger = 25
        self.sleepiness = 30
        self.happiness = 100
        self.cleanliness = 100
        self.is_sleeping = False

        self.health = 100
        self.is_sick = False

    def update_preferred_vertical_range(self):
        self.preferred_vertical_range = (self.ui.window_height // 4, self.ui.window_height // 4 * 3)

    def handle_window_resize(self, event):
        self.ui.window_width = event.size().width()
        self.ui.window_height = event.size().height()
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        self.update_preferred_vertical_range()
        self.squid_x = max(50, min(self.squid_x, self.ui.window_width - 50 - self.squid_width))
        self.squid_y = max(50, min(self.squid_y, self.ui.window_height - 120 - self.squid_height))
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()

    def update_needs(self):
        # This method was moved to TamagotchiLogic 26/07/2024
        pass

    def make_decision(self):
        # Reset novelty tracking flag at start of each decision cycle
        self.tamagotchi_logic.new_object_encountered = False
        self.tamagotchi_logic.recent_positive_outcome = False

        # Get current state including neurogenesis data
        current_state = {
            "hunger": self.hunger,
            "happiness": self.happiness,
            "cleanliness": self.cleanliness,
            "sleepiness": self.sleepiness,
            "satisfaction": self.satisfaction,
            "anxiety": self.anxiety,
            "curiosity": self.curiosity,
            "is_sick": self.is_sick,
            "is_sleeping": self.is_sleeping,
            "food_visible": bool(self.get_visible_food()),
            "personality": self.personality.value,
            "near_rocks": self.is_near_decorations('rock'),
            "has_novelty_neurons": any(n.startswith('novel') for n in 
                                    self.tamagotchi_logic.brain_window.brain_widget.new_neurons)
        }

        # Check for neurogenesis-triggered behaviors first
        if "defense_0" in self.tamagotchi_logic.brain_window.brain_widget.state:
            if current_state['anxiety'] > 60:
                self.status = "avoiding_threat"
                return self.move_away_from_threat()

        # Personality-specific decision modifiers
        personality_modifiers = {
            Personality.TIMID: self._make_timid_decision,
            Personality.GREEDY: self._make_greedy_decision,
            Personality.STUBBORN: self._make_stubborn_decision
        }
        if self.personality in personality_modifiers:
            decision = personality_modifiers[self.personality](current_state)
            if decision:
                return decision

        # Main decision hierarchy
        if self.should_organize_decorations():
            return "organize_decorations"
        
        if current_state["near_rocks"] and self.curiosity > 60:
            return "interact_with_rocks"

        # Enhanced food decision with neurogenesis consideration
        if current_state["hunger"] > 70 and self.get_visible_food():
            closest_food = min(self.get_visible_food(), 
                            key=lambda f: self.distance_to(f[0], f[1]))
            
            # If we have novelty neurons, be more exploratory
            if current_state["has_novelty_neurons"] and random.random() < 0.3:
                self.tamagotchi_logic.new_object_encountered = True
                return "explore_food_options"
            else:
                self.move_towards(closest_food[0], closest_food[1])
                return "moving_to_food"

        # Sleep decision with neurogenesis modifier
        if current_state["sleepiness"] > 90:
            if "stress_response" in self.tamagotchi_logic.brain_window.brain_widget.new_neurons:
                # Stress neurons make sleep harder
                if random.random() < 0.7:
                    self.go_to_sleep()
                    return "sleeping"
            else:
                self.go_to_sleep()
                return "sleeping"

        # Default behaviors with neurogenesis influence
        if current_state["has_novelty_neurons"] and random.random() < 0.4:
            self.tamagotchi_logic.new_object_encountered = True
            return "exploring_novelty"

        # Fallback to neural network decision
        decision = self.tamagotchi_logic.squid_brain_window.make_decision(current_state)
        
        # Record positive outcomes for neurogenesis
        if decision in ["eating", "playing", "exploring"]:
            self.tamagotchi_logic.recent_positive_outcome = True

        return decision or "exploring_default"

    def search_for_favorite_food(self):
        visible_food = self.get_visible_food()
        if visible_food:
            for food_x, food_y in visible_food:
                if self.is_favorite_food(self.tamagotchi_logic.get_food_item_at(food_x, food_y)):
                    self.move_towards(food_x, food_y)
                    return
            # If no favorite food is found, display a message and move randomly
            self.tamagotchi_logic.show_message("Stubborn squid does not like that type of food!")
            self.move_randomly()
        else:
            self.move_randomly()

    def get_favorite_food(self):
        # Implement logic to find the squid's favorite food
        for food_item in self.tamagotchi_logic.food_items:
            if self.is_favorite_food(food_item):
                return food_item.pos().x(), food_item.pos().y()
        return None

    def is_favorite_food(self, food_item):
        return food_item is not None and getattr(food_item, 'is_sushi', False)

    def load_state(self, state):
        self.hunger = state['hunger']
        self.sleepiness = state['sleepiness']
        self.happiness = state['happiness']
        self.cleanliness = state['cleanliness']
        self.health = state['health']
        self.is_sick = state['is_sick']
        self.squid_x = state['squid_x']
        self.squid_y = state['squid_y']
        self.satisfaction = state['satisfaction']
        self.anxiety = state['anxiety']
        self.curiosity = state['curiosity']
        self.personality = Personality(state['personality'])
        self.squid_item.setPos(self.squid_x, self.squid_y)

    def push_decoration(self, decoration, direction):
        push_distance = 40  # pixels to push
        current_pos = decoration.pos()
        new_x = current_pos.x() + (push_distance * direction)

        # Ensure the decoration stays within scene boundaries
        scene_rect = self.ui.scene.sceneRect()
        new_x = max(scene_rect.left(), min(new_x, scene_rect.right() - decoration.boundingRect().width()))

        # Create animation using modern approach
        self.push_animation = QtCore.QPropertyAnimation(decoration, b"pos")
        self.push_animation.setDuration(300)  # 300ms animation
        self.push_animation.setStartValue(current_pos)
        self.push_animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
        self.push_animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        
        # Connect cleanup callback
        self.push_animation.finished.connect(
            lambda: self._on_push_complete(decoration))
        
        self.push_animation.start()


    def _on_push_complete(self, decoration):
        """Callback when push animation finishes"""
        self.happiness = min(100, self.happiness + 5)
        self.curiosity = min(100, self.curiosity + 10)
        self.status = "pushing decoration"
        self.ui.show_message("Squid pushed a decoration")
        
        # Remove animation reference
        self.push_animation = None

    def move_erratically(self):
        directions = ["left", "right", "up", "down"]
        self.squid_direction = random.choice(directions)
        self.move_squid()

    def move_slowly(self):
        self.base_squid_speed = self.base_squid_speed // 2
        self.base_vertical_speed = self.base_vertical_speed // 2
        self.move_squid()

    def explore_environment(self):
        if random.random() < 0.3:
            self.change_direction()
        self.move_squid()

    def search_for_food(self):
        visible_food = self.get_visible_food()
        if visible_food:
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.status = "moving to food"
            self.move_towards(closest_food[0], closest_food[1])
        else:
            self.status = "searching for food"
            self.move_randomly()

    def get_visible_food(self):
        if self.tamagotchi_logic is None:
            return []
        visible_food = []
        for food_item in self.tamagotchi_logic.food_items:
            food_x, food_y = food_item.pos().x(), food_item.pos().y()
            if self.is_in_vision_cone(food_x, food_y):
                if getattr(food_item, 'is_sushi', False):
                    visible_food.insert(0, (food_x, food_y))  # Prioritize sushi
                else:
                    visible_food.append((food_x, food_y))  # Add cheese to the end of the list
        return visible_food

    def is_in_vision_cone(self, x, y):
        dx = x - (self.squid_x + self.squid_width // 2)
        dy = y - (self.squid_y + self.squid_height // 2)
        distance = math.sqrt(dx**2 + dy**2)

        cone_length = max(self.ui.window_width, self.ui.window_height)

        if distance > cone_length:
            return False

        angle_to_food = math.atan2(dy, dx)
        angle_diff = abs(angle_to_food - self.current_view_angle)

        return angle_diff <= self.view_cone_angle / 2 or angle_diff >= 2 * math.pi - self.view_cone_angle / 2

    def move_squid(self):
        if self.animation_speed == 0:
            return

        if self.is_sleeping:
            if self.squid_y < self.ui.window_height - 120 - self.squid_height:
                self.squid_y += self.base_vertical_speed * self.animation_speed
                self.squid_item.setPos(self.squid_x, self.squid_y)
            self.current_frame = (self.current_frame + 1) % 2
            self.update_squid_image()
            return

        current_time = QtCore.QTime.currentTime().msecsSinceStartOfDay()

        visible_food = self.get_visible_food()

        if visible_food:
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.pursuing_food = True
            self.target_food = closest_food
            self.move_towards(closest_food[0], closest_food[1])
        elif self.pursuing_food:
            self.pursuing_food = False
            self.target_food = None
            self.move_randomly()
        else:
            if current_time - self.last_view_cone_change > self.view_cone_change_interval:
                self.change_view_cone_direction()
                self.last_view_cone_change = current_time
            self.move_randomly()

        squid_x_new = self.squid_x
        squid_y_new = self.squid_y

        if self.squid_direction == "left":
            squid_x_new -= self.base_squid_speed * self.animation_speed
        elif self.squid_direction == "right":
            squid_x_new += self.base_squid_speed * self.animation_speed
        elif self.squid_direction == "up":
            squid_y_new -= self.base_vertical_speed * self.animation_speed
        elif self.squid_direction == "down":
            squid_y_new += self.base_vertical_speed * self.animation_speed

        if squid_x_new < 50:
            squid_x_new = 50
            self.change_direction()
        elif squid_x_new > self.ui.window_width - 50 - self.squid_width:
            squid_x_new = self.ui.window_width - 50 - self.squid_width
            self.change_direction()

        if squid_y_new < 50:
            squid_y_new = 50
            self.change_direction()
        elif squid_y_new > self.ui.window_height - 120 - self.squid_height:
            squid_y_new = self.ui.window_height - 120 - self.squid_height
            self.change_direction()

        self.squid_x = squid_x_new
        self.squid_y = squid_y_new

        if self.squid_direction in ["left", "right", "up", "down"]:
            self.current_frame = (self.current_frame + 1) % 2
            self.squid_item.setPixmap(self.current_image())

        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()
        self.update_sick_icon_position()

    def change_view_cone_direction(self):
        self.current_view_angle = random.uniform(0, 2 * math.pi)

    def move_towards(self, x, y):
        dx = x - (self.squid_x + self.squid_width // 2)
        dy = y - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

    def move_towards_position(self, target_pos):
        dx = target_pos.x() - (self.squid_x + self.squid_width // 2)
        dy = target_pos.y() - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

        self.move_squid()

    def eat(self, food_item):
        effects = {}

        # Basic effects for all food types
        effects['hunger'] = max(-20, -self.hunger)  # Reduce hunger by 20, but not below 0
        effects['happiness'] = min(10, 100 - self.happiness)  # Increase happiness by 10, but not above 100

        # Special effects based on food type
        if getattr(food_item, 'is_sushi', False):
            effects['satisfaction'] = min(15, 100 - self.satisfaction)
            food_name = "sushi"
        else:
            effects['satisfaction'] = min(10, 100 - self.satisfaction)
            food_name = "cheese"

        # Apply effects
        for attr, change in effects.items():
            current_value = getattr(self, attr)
            new_value = current_value + change
            setattr(self, attr, new_value)

        # Format effects for memory
        formatted_effects = ', '.join(f"{attr.capitalize()} {'+' if val >= 0 else ''}{val:.2f}" for attr, val in effects.items())
        memory_value = f"Ate {food_name}: {formatted_effects}"

        # Add memory
        self.memory_manager.add_short_term_memory('food', food_name, memory_value)

        # Additional effects
        self.status = "Ate food"
        self.tamagotchi_logic.remove_food(food_item)
        print(f"The squid ate the {food_name}")
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Personality-specific reactions
        if self.personality == Personality.GREEDY:
            self.eat_greedily(food_item)
        elif self.personality == Personality.STUBBORN and not getattr(food_item, 'is_sushi', False):
            self.react_stubborn_eating()

    def eat_greedily(self, food_item):
        self.status = "Eating greedily"
        food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"

        # Reduce hunger more than usual
        self.hunger = max(0, self.hunger - 25)

        # Increase happiness more
        self.happiness = min(100, self.happiness + 15)

        # Increase satisfaction significantly
        self.satisfaction = min(100, self.satisfaction + 20)

        # Slightly increase anxiety (from overeating)
        self.anxiety = min(100, self.anxiety + 5)

        self.tamagotchi_logic.remove_food(food_item)
        print(f"The greedy squid enthusiastically ate the {food_type}")
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Occasionally show a message
        if random.random() < 0.2:  # 20% chance to show a message
            self.tamagotchi_logic.show_message("Nom nom! Greedy squid devours the food!")

        # Check if there's more food nearby
        if self.check_for_more_food():
            if random.random() < 0.1:  # 10% chance to show this message
                self.tamagotchi_logic.show_message("Greedy squid looks around for more food...")
        else:
            if random.random() < 0.1:  # 10% chance to show this message
                self.tamagotchi_logic.show_message("Greedy squid is satisfied... for now.")

    def react_stubborn_eating(self):
        if self.hunger > 80:  # Extremely hungry
            self.happiness = max(0, self.happiness - 5)
            self.tamagotchi_logic.show_message("Stubborn squid reluctantly eats non-sushi food.")
        else:
            self.tamagotchi_logic.show_message("Stubborn squid ignores non-sushi food.")

    def check_for_more_food(self):
        for food_item in self.tamagotchi_logic.food_items:
            if self.is_food_nearby(food_item):
                return True
        return False

    def is_food_nearby(self, food_item):
        food_x, food_y = food_item.pos().x(), food_item.pos().y()
        squid_center_x = self.squid_x + self.squid_width // 2
        squid_center_y = self.squid_y + self.squid_height // 2
        distance = math.sqrt((squid_center_x - food_x)**2 + (squid_center_y - food_y)**2)
        return distance < 100  # Adjust the distance threshold as needed

    def investigate_food(self, food_item):
        self.status = "Investigating food"
        self.tamagotchi_logic.show_message("Stubborn squid investigates the food...")

        # Move towards the food
        food_pos = food_item.pos()
        self.move_towards_position(food_pos)

        # Wait for a moment (might need to implement a delay here)

        self.tamagotchi_logic.show_message("Stubborn squid ignored the food")
        self.status = "I don't like that food"

    def consume_food(self, food_item):
        self.status = "Ate food"
        self.hunger = max(0, self.hunger - 20)
        self.happiness = min(100, self.happiness + 10)
        self.satisfaction = min(100, self.satisfaction + 15)
        self.anxiety = max(0, self.anxiety - 10)
        self.tamagotchi_logic.remove_food(food_item)
        print("The squid ate the food")
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Occasionally show a message based on personality
        if random.random() < 0.2:  # 20% chance to show a message
            if self.personality == Personality.STUBBORN and getattr(food_item, 'is_sushi', False):
                self.tamagotchi_logic.show_message("Nom nom! Stubborn squid enjoys the sushi!")
            elif self.personality == Personality.GREEDY:
                food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"
                self.tamagotchi_logic.show_message(f"Nom nom! Greedy squid gobbles up the {food_type}!")
            else:
                self.tamagotchi_logic.show_message("Nom nom! Squid enjoys the meal!")

    def start_poop_timer(self):
        poop_delay = random.randint(11000, 30000)
        print("Poop random timer started")
        self.poop_timer = QtCore.QTimer()
        self.poop_timer.setSingleShot(True)
        self.poop_timer.timeout.connect(self.create_poop)
        self.poop_timer.start(poop_delay)

    def create_poop(self):
        self.tamagotchi_logic.spawn_poop(self.squid_x + self.squid_width // 2, self.squid_y + self.squid_height)
        print("Poop created at squid location")

    def show_eating_effect(self):
        if not self.is_debug_mode():
            return

        effect_item = QtWidgets.QGraphicsEllipseItem(self.squid_x, self.squid_y, self.squid_width, self.squid_height)
        effect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 100)))
        effect_item.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.ui.scene.addItem(effect_item)

        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        effect_item.setGraphicsEffect(opacity_effect)

        self.eating_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        self.eating_animation.setDuration(5000)
        self.eating_animation.setStartValue(1.0)
        self.eating_animation.setEndValue(0.0)
        self.eating_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        self.eating_animation.finished.connect(lambda: self.ui.scene.removeItem(effect_item))

        self.eating_animation.start()

    def is_debug_mode(self):
        return self.tamagotchi_logic.debug_mode

    def change_to_rps_image(self):
        self.rps_image = QtGui.QPixmap(os.path.join("images", "squid_rps_frame.png"))
        self.squid_item.setPixmap(self.rps_image)

    def restore_normal_image(self):
        self.squid_item.setPixmap(self.current_image())

    def go_to_sleep(self):
        if not self.is_sleeping:
            self.is_sleeping = True
            self.squid_direction = "down"
            self.status = "sleeping"
            self.tamagotchi_logic.show_message("Squid is sleeping...")

    def wake_up(self):
        self.is_sleeping = False
        self.sleepiness = 0
        self.happiness = min(100, self.happiness + 20)
        self.status = "roaming"
        self.squid_direction = "left"
        self.update_squid_image()
        self.tamagotchi_logic.show_message("Squid woke up!")

    def update_squid_image(self):
        self.squid_item.setPixmap(self.current_image())

    def current_image(self):
        if self.is_sleeping:
            return self.images[f"sleep{self.current_frame + 1}"]
        if self.squid_direction == "left":
            return self.images[f"left{self.current_frame + 1}"]
        elif self.squid_direction == "right":
            return self.images[f"right{self.current_frame + 1}"]
        elif self.squid_direction == "up":
            return self.images[f"up{self.current_frame + 1}"]
        return self.images["left1"]

    def move_randomly(self):
        if random.random() < 0.20:
            self.change_direction()

    def get_food_position(self):
        if self.tamagotchi_logic.food_items:
            closest_food = min(self.tamagotchi_logic.food_items,
                               key=lambda food: self.distance_to(food.pos().x(), food.pos().y()))
            return closest_food.pos().x(), closest_food.pos().y()
        else:
            return -1, -1

    def distance_to(self, x, y):
        return math.sqrt((self.squid_x - x)**2 + (self.squid_y - y)**2)

    def change_direction(self):
        directions = ["left", "right", "up", "down"]
        new_direction = random.choice(directions)
        while new_direction == self.squid_direction:
            new_direction = random.choice(directions)
        self.squid_direction = new_direction

    def toggle_view_cone(self):
        self.view_cone_visible = not self.view_cone_visible
        if self.view_cone_visible:
            self.update_view_cone()
        else:
            self.remove_view_cone()

    def update_view_cone(self):
        if self.view_cone_visible:
            if self.view_cone_item is None:
                self.view_cone_item = QtWidgets.QGraphicsPolygonItem()
                self.view_cone_item.setPen(QtGui.QPen(QtCore.Qt.yellow))
                self.view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 50)))
                self.ui.scene.addItem(self.view_cone_item)

            squid_center_x = self.squid_x + self.squid_width // 2
            squid_center_y = self.squid_y + self.squid_height // 2

            if self.pursuing_food and self.target_food:
                dx = self.target_food[0] - squid_center_x
                dy = self.target_food[1] - squid_center_y
                self.current_view_angle = math.atan2(dy, dx)

            cone_length = max(self.ui.window_width, self.ui.window_height)

            cone_points = [
                QtCore.QPointF(squid_center_x, squid_center_y),
                QtCore.QPointF(squid_center_x + math.cos(self.current_view_angle - self.view_cone_angle/2) * cone_length,
                               squid_center_y + math.sin(self.current_view_angle - self.view_cone_angle/2) * cone_length),
                QtCore.QPointF(squid_center_x + math.cos(self.current_view_angle + self.view_cone_angle/2) * cone_length,
                               squid_center_y + math.sin(self.current_view_angle + self.view_cone_angle/2) * cone_length)
            ]

            cone_polygon = QtGui.QPolygonF(cone_points)
            self.view_cone_item.setPolygon(cone_polygon)
        else:
            self.remove_view_cone()

    def remove_view_cone(self):
        if self.view_cone_item is not None:
            self.ui.scene.removeItem(self.view_cone_item)
            self.view_cone_item = None

    def show_sick_icon(self):
        if self.sick_icon_item is None:
            sick_icon_pixmap = QtGui.QPixmap(os.path.join("images", "sick.png"))
            self.sick_icon_item = QtWidgets.QGraphicsPixmapItem(sick_icon_pixmap)
            self.ui.scene.addItem(self.sick_icon_item)
        self.update_sick_icon_position()

    def hide_sick_icon(self):
        if self.sick_icon_item is not None:
            self.ui.scene.removeItem(self.sick_icon_item)
            self.sick_icon_item = None

    def update_sick_icon_position(self):
        if self.sick_icon_item is not None:
            self.sick_icon_item.setPos(self.squid_x + self.squid_width // 2 - self.sick_icon_item.pixmap().width() // 2 + self.sick_icon_offset.x(),
                                       self.squid_y + self.sick_icon_offset.y())

    def is_near_plant(self):
        if self.tamagotchi_logic is None:
            return False

        nearby_decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
        return any(decoration.category == 'plant' for decoration in nearby_decorations)

    def move_towards_plant(self):
        if self.tamagotchi_logic is None:
            return

        nearby_decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
        plants = [d for d in nearby_decorations if d.category == 'plant']

        if plants:
            closest_plant = min(plants, key=lambda p: self.distance_to(p.pos().x(), p.pos().y()))
            self.move_towards(closest_plant.pos().x(), closest_plant.pos().y())
        else:
            self.move_randomly()

    def should_organize_decorations(self):
        return (self.curiosity > 70 and
                self.satisfaction < 80 and
                self.personality in [Personality.ADVENTUROUS, Personality.ENERGETIC])

    def organize_decorations(self):
        target_corner = (50, 50)  # Top-left corner
        decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)

        if decorations:
            closest = min(decorations, key=lambda d: self.distance_to(d.pos().x(), d.pos().y()))
            self.move_towards(closest.pos().x(), closest.pos().y())

            if self.distance_to(closest.pos().x(), closest.pos().y()) < 50:
                self.push_decoration(closest, direction=1 if random.random() < 0.5 else -1)
                self.satisfaction = min(100, self.satisfaction + 5)
                return "organizing decorations"
        return "searching for decorations"

    def interact_with_rocks(self):
        rocks = [d for d in self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
                 if d.category == 'rock']
        if rocks:
            self.push_decoration(random.choice(rocks), random.choice([-1, 1]))
            self.satisfaction = min(100, self.satisfaction + 8)
            self.happiness = min(100, self.happiness + 5)
            return "interacting with rocks"
        return "no rocks nearby"
