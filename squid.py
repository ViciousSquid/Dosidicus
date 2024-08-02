import os
import random
import traceback
from enum import Enum
import math
from PyQt5 import QtCore, QtGui, QtWidgets
from mental_states import MentalStateManager
from error_logging import log_debug, log_error

class Personality(Enum):
    TIMID = "timid"
    ADVENTUROUS = "adventurous"
    LAZY = "lazy"
    ENERGETIC = "energetic"
    INTROVERT = "introvert"
    GREEDY = "greedy"
    STUBBORN = "stubborn"

class Squid:
    def __init__(self, user_interface, tamagotchi_logic, personality=None):
        self.ui = user_interface
        self.tamagotchi_logic = tamagotchi_logic

        self.rps_image = QtGui.QPixmap(os.path.join("images", "squid_rps_frame.png"))

        self.load_images()
        self.load_poop_images()
        self.initialize_attributes()

        self.current_frame_index = 0
        self.animation_speed = 1
        self.pursuing_food = False
        self.target_food = None
        self.view_cone_visible = False
        self.view_cone_item = None
        self.current_view_angle = random.uniform(0, 2 * math.pi)
        self.view_cone_angle = math.pi / 2.5
        self.view_cone_change_interval = 2000  # milliseconds
        self.last_view_cone_change = QtCore.QTime.currentTime().msecsSinceStartOfDay()

        self.sick_icon_item = None
        self.sick_icon_offset = QtCore.QPointF(0, -100)

        self.holding_item = None
        self.throw_cooldown = 0
        self.throw_cooldown_max = 30  # seconds

        self.poop_timer = None

        # Initialize base speeds
        self.original_base_speed = 90  # or whatever your default speed is
        self.original_vertical_speed = 45  # or half of the base speed
        self.base_squid_speed = self.original_base_speed
        self.base_vertical_speed = self.original_vertical_speed

        self.mental_state_manager = MentalStateManager(self, self.ui.scene)

        self.squid_item = QtWidgets.QGraphicsPixmapItem(self.current_frame())
        self.ui.scene.addItem(self.squid_item)

        if personality is None:
            self.personality = random.choice(list(Personality))
        else:
            self.personality = personality

    def toggle_view_cone(self):
        self.view_cone_visible = not self.view_cone_visible
        if self.view_cone_visible:
            self.update_view_cone()
        else:
            self.remove_view_cone()

    def current_frame(self):
        if self.holding_item:
            return self.rps_image
        if self.is_sleeping:
            return self.images[f"sleep{(self.current_frame_index) % 2 + 1}"]
        if self.squid_direction == "left":
            return self.images[f"left{(self.current_frame_index) % 2 + 1}"]
        elif self.squid_direction == "right":
            return self.images[f"right{(self.current_frame_index) % 2 + 1}"]
        elif self.squid_direction == "up":
            return self.images[f"up{(self.current_frame_index) % 2 + 1}"]
        return self.images["left1"]

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
        self.current_frame_index = 0
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

    def update(self):
        # Update position
        self.move_squid()

        # Update needs
        if not self.is_sleeping:
            self.hunger = min(100, self.hunger + (0.1 * self.tamagotchi_logic.simulation_speed))
            self.sleepiness = min(100, self.sleepiness + (0.1 * self.tamagotchi_logic.simulation_speed))
            self.happiness = max(0, self.happiness - (0.1 * self.tamagotchi_logic.simulation_speed))
            self.cleanliness = max(0, self.cleanliness - (0.1 * self.tamagotchi_logic.simulation_speed))

        # Make decisions based on current state
        self.make_decision()

        # Update health
        if self.is_sick:
            self.health = max(0, self.health - (0.1 * self.tamagotchi_logic.simulation_speed))
        else:
            self.health = min(100, self.health + (0.05 * self.tamagotchi_logic.simulation_speed))

        # Check if squid should go to sleep
        if self.sleepiness >= 100 and not self.is_sleeping:
            self.go_to_sleep()
        elif self.sleepiness <= 0 and self.is_sleeping:
            self.wake_up()

        # Update mental state icons
        self.mental_state_manager.update_positions()

        # Throwing-related updates
        if self.throw_cooldown > 0:
            self.throw_cooldown -= 1

        self.decide_throw()

    def change_view_cone_direction(self):
        # Change the view cone direction randomly
        self.current_view_angle = random.uniform(0, 2 * math.pi)
        self.last_view_cone_change = QtCore.QTime.currentTime().msecsSinceStartOfDay()

        # Update the view cone visually
        if self.view_cone_visible:
            self.update_view_cone()

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
        if self.is_sick:
            self.stay_at_bottom()
            self.status = "sick and lethargic"
        elif self.anxiety > 70:
            self.status = "anxious"
            self.move_erratically()
        elif self.curiosity > 50 and random.random() < 0.5:
            self.status = "exploring"
            self.explore_environment()
        elif self.hunger > 30 or self.satisfaction < 30:
            self.status = "searching for food"
            self.search_for_food()
        elif self.sleepiness > 70:
            self.status = "tired"
            self.go_to_sleep()
        elif self.personality == Personality.INTROVERT:
            if self.happiness > 70:
                self.status = "content in solitude"
                self.move_slowly()
            else:
                self.status = "seeking alone time"
                self.explore_environment()

        elif self.personality == Personality.GREEDY:
            if self.hunger > 50 and self.anxiety > 60:
                self.status = "anxious and hungry"
                self.search_for_food()
            elif self.curiosity > 50:
                self.status = "curiously seeking food"
                self.explore_environment()
            else:
                self.status = "content for now"
                self.move_randomly()

        elif self.personality == Personality.TIMID:
            if self.anxiety > 50 and not self.is_near_plant():
                self.status = "anxiously seeking plants"
                self.move_towards_plant()
            elif self.curiosity < 30:
                self.status = "timidly exploring"
                self.explore_environment()
            else:
                self.status = "content amongst plants"
                self.move_slowly()

        elif self.personality == Personality.STUBBORN:
            if self.hunger > 40 and self.target_food is None:
                self.status = "searching for favorite food"
                self.search_for_favorite_food()
            elif self.sleepiness > 80 and random.random() < 0.5:
                self.status = "refusing to sleep"
                self.move_randomly()
            else:
                self.status = "being stubborn"
                self.move_slowly()

        else:
            # Default behavior if no specific conditions are met
            self.status = "roaming"
            self.move_randomly()

        # Update the squid's brain window with the current status
        if hasattr(self.tamagotchi_logic, 'squid_brain_window'):
            self.tamagotchi_logic.squid_brain_window.print_to_console(f"Squid status: {self.status}")

    def change_to_rps_image(self):
        self.rps_image = QtGui.QPixmap(os.path.join("images", "squid_rps_frame.png"))
        self.squid_item.setPixmap(self.rps_image)

    def restore_normal_image(self):
        self.squid_item.setPixmap(self.current_frame())

    def pick_up_item(self, item):
        log_debug(f"Attempting to pick up item: {item}")
        if not self.holding_item and item.is_throwable and not item.is_picked_up:
            self.holding_item = item
            item.is_picked_up = True  # Set the attribute when picked up
            item.setPos(self.squid_x, self.squid_y - item.boundingRect().height())
            log_debug(f"Item picked up: {self.holding_item}")
            self.squid_item.setPixmap(self.rps_image)
        else:
            log_debug(f"Failed to pick up item. Holding item: {self.holding_item}, Is throwable: {item.is_throwable}, Is picked up: {item.is_picked_up}")

    def pick_up_rock_debug(self):
        log_error("Entering pick_up_rock_debug method")
        try:
            if self.debug_mode and self.squid:
                log_error("Creating rock pixmap")
                rock_pixmap = QtGui.QPixmap("images/rock_small.png")
                log_error(f"Rock pixmap created: {rock_pixmap is not None}")

                log_error("Creating ResizablePixmapItem")
                rock_item = ResizablePixmapItem(rock_pixmap, "rock_small.png")
                log_error(f"ResizablePixmapItem created: {rock_item is not None}")

                rock_item.setScale(0.5)
                rock_item.is_throwable = True

                log_error(f"Squid position: ({self.squid.squid_x}, {self.squid.squid_y})")
                rock_item.setPos(self.squid.squid_x + self.squid.squid_width, self.squid.squid_y)
                log_error("Rock positioned")

                log_error("Adding rock to scene")
                self.user_interface.scene.addItem(rock_item)
                log_error("Rock added to scene")

                log_error("Squid picking up rock")
                self.squid.pick_up_item(rock_item)
                log_error(f"Squid picked up the rock: {self.squid.holding_item is not None}")

                if self.squid.holding_item:
                    log_error("Squid is now holding the rock and changed to RPS image")
                    self.set_simulation_speed(0)  # Pause the simulation
                    self.user_interface.show_message("Simulation paused. Squid is holding the rock.")
                else:
                    log_error("Squid failed to pick up the rock")
            else:
                log_error("Debug mode is off or squid doesn't exist")
        except Exception as e:
            error_message = f"Error in pick_up_rock_debug: {str(e)}"
            log_error(error_message)
            log_error(traceback.format_exc())

    def throw_item(self):
        log_debug(f"Attempting to throw item. Holding item: {self.holding_item}, Throw cooldown: {self.throw_cooldown}")

        if self.holding_item and self.throw_cooldown == 0:
            try:
                throw_distance = self.calculate_throw_distance()
                log_debug(f"Throw distance calculated: {throw_distance}")

                target_x, target_y = self.calculate_target_coordinates(throw_distance)
                log_debug(f"Target coordinates: ({target_x}, {target_y})")

                self.animate_throw(self.holding_item, target_x, target_y)
                log_debug("Animate throw called")

                self.holding_item.is_picked_up = False
                self.holding_item = None
                self.throw_cooldown = self.throw_cooldown_max
                self.squid_item.setPixmap(self.current_frame())
                self.restore_normal_image()  # Restore normal image after throwing
                log_debug("Throw completed")
            except Exception as e:
                log_error(f"Error in throw_item: {str(e)}")
                log_error(traceback.format_exc())
        else:
            log_debug("Not holding item or cooldown is not 0")

    def interact_with_decoration(self, decoration):
        log_debug(f"Squid is interacting with decoration: {decoration.filename}")
        
        # Different interactions based on decoration type
        if decoration.category == 'rock':
            if not self.holding_item and decoration.is_throwable:
                self.pick_up_item(decoration)
                self.tamagotchi_logic.show_message("Squid picked up a rock!")
            else:
                self.tamagotchi_logic.show_message("Squid bumped into a rock!")
        elif decoration.category == 'plant':
            self.tamagotchi_logic.show_message("Squid is playing with a plant!")
            self.happiness = min(100, self.happiness + 5)
        else:
            self.tamagotchi_logic.show_message(f"Squid is curious about the {decoration.category}!")
        
        # Increase curiosity slightly for any interaction
        self.curiosity = min(100, self.curiosity + 2)

    def calculate_target_coordinates(self, throw_distance):
        """Calculate the target coordinates based on the squid's direction and throw distance."""
        if self.squid_direction == "left":
            target_x = self.squid_x - throw_distance
        elif self.squid_direction == "right":
            target_x = self.squid_x + throw_distance
        else:
            target_x = self.squid_x

        if self.squid_direction == "up":
            target_y = self.squid_y - throw_distance
        elif self.squid_direction == "down":
            target_y = self.squid_y + throw_distance
        else:
            target_y = self.squid_y

        return target_x, target_y

    def calculate_throw_distance(self):
        base_distance = 100  # pixels
        strength_factor = random.uniform(0.8, 1.2)
        weight_factor = 1
        if self.holding_item:
            if hasattr(self.holding_item, 'weight'):
                weight = max(self.holding_item.weight, 0.1)  # Ensure minimum weight of 0.1
            else:
                # If weight is not available, estimate based on size
                size = max(self.holding_item.boundingRect().width(), self.holding_item.boundingRect().height())
                weight = max(size / 50, 0.1)  # Rough estimate with minimum weight of 0.1
            weight_factor = 1 / weight
        return base_distance * strength_factor * weight_factor

    def animate_throw(self, item, target_x, target_y):
        log_debug("Entering animate_throw")
        try:
            # Set the starting position to the squid's position
            start_pos = QtCore.QPointF(self.squid_x, self.squid_y)
            end_pos = QtCore.QPointF(target_x, target_y)

            # Move the item to the starting position
            item.setPos(start_pos)

            self.throw_animation = QtCore.QVariantAnimation()
            self.throw_animation.setStartValue(start_pos)
            self.throw_animation.setEndValue(end_pos)
            self.throw_animation.setDuration(1000)  # 1 second
            self.throw_animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)

            def update_pos(pos):
                item.setPos(pos)

            self.throw_animation.valueChanged.connect(update_pos)
            self.throw_animation.finished.connect(lambda: self.throw_animation_finished(item))
            self.throw_animation.start()
            log_debug("Animation started")
        except Exception as e:
            log_error(f"Error in animate_throw: {str(e)}")
            log_error(traceback.format_exc())

    def decide_throw(self):
        if self.holding_item and self.throw_cooldown == 0:
            throw_chance = 0
            if self.curiosity > 70:
                throw_chance += 0.3
            if self.happiness > 80:
                throw_chance += 0.2
            if self.satisfaction < 30:
                throw_chance += 0.2

            if random.random() < throw_chance:
                self.throw_item()
                self.tamagotchi_logic.show_message("Squid threw an item!")

    def throw_animation_finished(self, item):
        # This method is called when the throw animation is finished
        # You can add any additional logic here, such as removing the item from the scene
        pass

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

    def move_erratically(self):
        directions = ["left", "right", "up", "down"]
        self.squid_direction = random.choice(directions)
        self.move_squid()

    def move_slowly(self):
        self.base_squid_speed = self.base_squid_speed // 2
        self.base_vertical_speed = self.base_vertical_speed // 2
        self.move_squid()

    def explore_environment(self):
        # Increase curiosity slightly during exploration
        self.curiosity = min(100, self.curiosity + 5)

        # Chance to change direction
        if random.random() < 0.3:
            self.change_direction()

        # Chance to interact with nearby decorations
        nearby_decorations = self.tamagotchi_logic.user_interface.get_nearby_decorations(self.squid_x, self.squid_y)
        if nearby_decorations and random.random() < 0.2:
            self.interact_with_decoration(random.choice(nearby_decorations))

        # Chance to change view cone
        if random.random() < 0.2:
            self.change_view_cone_direction()

        # Adjust movement speed based on curiosity
        speed_factor = 1 + (self.curiosity / 100)
        self.base_squid_speed = self.original_base_speed * speed_factor
        self.base_vertical_speed = self.original_vertical_speed * speed_factor

        # Move the squid
        self.move_randomly()

        # Chance to pick up a small object if not already holding one
        if not self.holding_item and random.random() < 0.1:
            self.try_pick_up_object()

        # Update status
        self.status = "exploring curiously"

    def try_pick_up_object(self):
        if self.holding_item:
            return  # Squid is already holding an item

        nearby_objects = self.tamagotchi_logic.get_nearby_throwable_items(self.squid_x, self.squid_y)
        if nearby_objects:
            object_to_pick = random.choice(nearby_objects)
            self.pick_up_item(object_to_pick)

            # Use the boundingRect to determine the size
            object_size = object_to_pick.boundingRect().width()
            size_description = "small" if object_size < 50 else "medium" if object_size < 100 else "large"

            self.tamagotchi_logic.show_message(f"Squid curiously picked up a {size_description} {object_to_pick.category}")

    def get_nearby_throwable_items(self, x, y, radius=100):
        nearby_items = []
        for item in self.user_interface.scene.items():
            if isinstance(item, ResizablePixmapItem) and item.is_throwable and not item.is_picked_up:
                item_center = item.sceneBoundingRect().center()
                distance = math.sqrt((x - item_center.x())**2 + (y - item_center.y())**2)
                if distance <= radius:
                    nearby_items.append(item)
        return nearby_items

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
            self.current_frame_index = (self.current_frame_index + 1) % 2  # Use 'current_frame_index' instead of 'frame_index'
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

        # Apply boundary limits
        boundary_bottom = self.ui.window_height - 120 - self.squid_height
        if self.tamagotchi_logic.debug_mode:
            boundary_bottom -= 50  # Reduce bottom boundary by 50 pixels in debug mode

        if squid_x_new < 50:
            squid_x_new = 50
            self.change_direction()
        elif squid_x_new > self.ui.window_width - 50 - self.squid_width:
            squid_x_new = self.ui.window_width - 50 - self.squid_width
            self.change_direction()

        if squid_y_new < 50:
            squid_y_new = 50
            self.change_direction()
        elif squid_y_new > boundary_bottom:
            squid_y_new = boundary_bottom
            self.change_direction()

        self.squid_x = squid_x_new
        self.squid_y = squid_y_new

        if self.squid_direction in ["left", "right", "up", "down"]:
            self.squid_item.setPixmap(self.current_frame())

        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()
        self.update_sick_icon_position()

        # Update position of held item if squid is holding one
        if self.holding_item:
            self.holding_item.setPos(self.squid_x, self.squid_y - self.holding_item.boundingRect().height())

    def move_towards(self, target_x, target_y):
        dx = target_x - self.squid_x
        dy = target_y - self.squid_y
        distance = math.sqrt(dx**2 + dy**2)

        if distance > 0:
            # Normalize the direction vector
            dx /= distance
            dy /= distance

            # Move the squid
            self.squid_x += dx * self.base_squid_speed * self.animation_speed
            self.squid_y += dy * self.base_vertical_speed * self.animation_speed

            # Update the squid's direction based on movement
            if abs(dx) > abs(dy):
                self.squid_direction = "right" if dx > 0 else "left"
            else:
                self.squid_direction = "down" if dy > 0 else "up"

        # Update the squid's position
        self.squid_item.setPos(self.squid_x, self.squid_y)

        # Update the squid's image based on the new direction
        self.update_squid_image()

    def eat(self):
        if not self.is_sick:
            for food_item in self.tamagotchi_logic.food_items:
                if self.squid_item.collidesWithItem(food_item):
                    if self.personality == Personality.STUBBORN:
                        if not getattr(food_item, 'is_sushi', False):
                            if self.hunger > 80:  # Extremely hungry
                                self.eat_begrudgingly(food_item)
                            else:
                                self.investigate_food(food_item)
                            return
                    elif self.personality == Personality.GREEDY:
                        self.eat_greedily(food_item)
                        return

                    self.consume_food(food_item)
                    break

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
        self.squid_item.setPixmap(self.current_frame())

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
        if self.is_sleeping:
            self.squid_item.setPixmap(self.images[f"sleep{(self.current_frame_index + 1) % 2}"])
        elif self.squid_direction == "left":
            self.squid_item.setPixmap(self.images[f"left{(self.current_frame_index + 1) % 2}"])
        elif self.squid_direction == "right":
            self.squid_item.setPixmap(self.images[f"right{(self.current_frame_index + 1) % 2}"])
        elif self.squid_direction == "up":
            self.squid_item.setPixmap(self.images[f"up{(self.current_frame_index + 1) % 2}"])
        else:
            self.squid_item.setPixmap(self.images["left1"])

        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.current_frame_index = (self.current_frame_index + 1) % 2

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
        # This method should be implemented to check if the squid is near a plant decoration
        # For now, we'll return False as a placeholder
        return False
