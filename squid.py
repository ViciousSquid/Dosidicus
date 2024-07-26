# A cute squid with a view cone that he uses to locate food
# by Rufus Pearce (ViciousSquid)  |  July 2024  |  MIT License
# https://github.com/ViciousSquid/Dosidicus

import os
import random
import math
from PyQt5 import QtCore, QtGui, QtWidgets

class Squid:
    def __init__(self, ui, tamagotchi_logic):
        self.ui = ui
        self.tamagotchi_logic = tamagotchi_logic

        self.load_images()
        self.load_poop_images()
        self.initialize_attributes()

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

    def make_decision(self):        # Make decisions and report about them
        if self.is_sick:
            self.stay_at_bottom()
            self.status = "sick and lethargic"
        elif self.hunger > 30:      # Search for food if this hungry
            self.status = "searching for food"
            self.search_for_food()
        elif self.sleepiness > 70:  # try to go to sleep if this tired
            self.status = "tired"
            self.go_to_sleep()
        else:
            self.status = "roaming" # Default status
            self.move_randomly()

    def search_for_food(self):  # Search for food within the view cone and move towards it
        visible_food = self.get_visible_food()
        if visible_food:
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.status = "moving to food"
            self.move_towards(closest_food[0], closest_food[1])
        else:
            self.status = "searching for food"
            self.move_randomly()

    def get_visible_food(self):
        visible_food = []
        for food_item in self.tamagotchi_logic.food_items:
            food_x, food_y = food_item.pos().x(), food_item.pos().y()
            if self.is_in_vision_cone(food_x, food_y):
                visible_food.append((food_x, food_y))
        return visible_food

    def is_in_vision_cone(self, x, y):
        dx = x - (self.squid_x + self.squid_width // 2)
        dy = y - (self.squid_y + self.squid_height // 2)
        distance = math.sqrt(dx**2 + dy**2)

        # Define vision cone parameters
        cone_length = max(self.ui.window_width, self.ui.window_height)
        cone_angle = math.pi / 2.5  # 80 degrees, as in the original code

        if distance > cone_length:
            return False

        angle_to_food = math.atan2(dy, dx)
        direction_angle = self.get_direction_angle()
        angle_diff = abs(angle_to_food - direction_angle)

        return angle_diff <= cone_angle / 2 or angle_diff >= 2 * math.pi - cone_angle / 2

    def move_towards(self, x, y):
        dx = x - (self.squid_x + self.squid_width // 2)
        dy = y - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

    def get_direction_angle(self):
        if self.squid_direction == "right":
            return 0
        elif self.squid_direction == "up":
            return math.pi / 2
        elif self.squid_direction == "left":
            return math.pi
        elif self.squid_direction == "down":
            return 3 * math.pi / 2
        else:
            return 0

    def move_randomly(self):
        if random.random() < 0.20:  # 20% chance to change direction
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

    def eat(self):
        if not self.is_sick:
            for food_item in self.tamagotchi_logic.food_items:
                if self.squid_item.collidesWithItem(food_item):
                    self.status = "Ate some cheese"
                    self.hunger = max(0, self.hunger - 20)
                    self.happiness = min(100, self.happiness + 10)
                    self.tamagotchi_logic.remove_food(food_item)
                    print("The squid ate the food")
                    self.show_eating_effect()
                    self.start_poop_timer()
                    break

    def start_poop_timer(self):
        poop_delay = random.randint(11000, 30000)  # 11 to 30 seconds until poop is created (to simulate digestion)
        print("Poop timer started")
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
        effect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 100)))  # Yellow, semi-transparent
        effect_item.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.ui.scene.addItem(effect_item)

        # Create a QGraphicsOpacityEffect
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        effect_item.setGraphicsEffect(opacity_effect)

        # Create a QPropertyAnimation for the opacity effect
        self.eating_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        self.eating_animation.setDuration(5000)  # 5 seconds duration
        self.eating_animation.setStartValue(1.0)
        self.eating_animation.setEndValue(0.0)
        self.eating_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        # Connect the finished signal to remove the item
        self.eating_animation.finished.connect(lambda: self.ui.scene.removeItem(effect_item))

        # Start the animation
        self.eating_animation.start()

    def is_debug_mode(self):
        return self.tamagotchi_logic.debug_mode

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
        self.squid_direction = "left"  # Set a default direction when waking up
        self.update_squid_image()  # Update the squid's image to reflect the new state
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
        return self.images["left1"]  # Default to left-facing image if direction is unknown

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

        squid_x_new = self.squid_x
        squid_y_new = self.squid_y

        if self.squid_direction == "left":
            squid_x_new -= self.base_squid_speed * self.animation_speed
        elif self.squid_direction == "right":
            squid_x_new += self.base_squid_speed * self.animation_speed
        elif self.squid_direction == "up":
            squid_y_new -= self.base_vertical_speed * self.animation_speed
        else:  # Treat any other direction as downward movement
            squid_y_new += self.base_vertical_speed * self.animation_speed

        # Check if the squid hits the screen edge
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

        if self.squid_direction in ["left", "right", "up"]:
            self.current_frame = (self.current_frame + 1) % 2
            self.update_squid_image()

        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()
        self.update_sick_icon_position()

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

            direction_angle = self.get_direction_angle()
            cone_angle = math.pi / 2.5  # angle of the view cone   2.5 = 80 degrees
            cone_length = max(self.ui.window_width, self.ui.window_height)

            squid_center_x = self.squid_x + self.squid_width // 2
            squid_center_y = self.squid_y + self.squid_height // 2

            cone_points = [
                QtCore.QPointF(squid_center_x, squid_center_y),
                QtCore.QPointF(squid_center_x + math.cos(direction_angle - cone_angle/2) * cone_length,
                               squid_center_y + math.sin(direction_angle - cone_angle/2) * cone_length),
                QtCore.QPointF(squid_center_x + math.cos(direction_angle + cone_angle/2) * cone_length,
                               squid_center_y + math.sin(direction_angle + cone_angle/2) * cone_length)
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
