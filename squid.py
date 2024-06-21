import os
import random
from PyQt5 import QtCore, QtGui, QtWidgets
from brain import Brain

class Squid:
    def __init__(self, ui, tamagotchi_logic):
        self.ui = ui
        self.tamagotchi_logic = tamagotchi_logic
        self.brain = Brain()

        self.load_images()
        self.initialize_attributes()
        self.setup_timers()

        self.squid_item = QtWidgets.QGraphicsPixmapItem(self.current_image())
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.ui.scene.addItem(self.squid_item)

        self.ui.window.resizeEvent = self.handle_window_resize

    def load_images(self):
        self.images = {
            "left1": QtGui.QPixmap(os.path.join("images", "left1.png")),
            "left2": QtGui.QPixmap(os.path.join("images", "left2.png")),
            "right1": QtGui.QPixmap(os.path.join("images", "right1.png")),
            "right2": QtGui.QPixmap(os.path.join("images", "right2.png")),
        }
        self.squid_width = self.images["left1"].width()
        self.squid_height = self.images["left1"].height()

    def initialize_attributes(self):
        self.squid_speed = int(self.squid_width * 0.8)
        self.vertical_speed = self.squid_speed // 2
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        self.squid_x = self.center_x
        self.squid_y = self.center_y
        self.squid_direction = random.choice(["left", "right", "up", "down"])
        self.current_frame = 0
        self.update_preferred_vertical_range()

        self.hunger = 0
        self.sleepiness = 0
        self.happiness = 100
        self.is_sleeping = False
        self.color = QtGui.QColor(0, 255, 0)  # Start with green (happy)
        self.target_color = QtGui.QColor(0, 255, 0)

    def setup_timers(self):
        self.move_timer = QtCore.QTimer()
        self.move_timer.timeout.connect(self.move_squid)
        self.move_timer.start(1000)

        self.need_timer = QtCore.QTimer()
        self.need_timer.timeout.connect(self.update_needs)
        self.need_timer.start(5000)

        self.color_transition_timer = QtCore.QTimer()
        self.color_transition_timer.timeout.connect(self.transition_color)

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

    def update_needs(self):
        if not self.is_sleeping:
            self.hunger += 1
            self.sleepiness += 1
            self.happiness = max(0, self.happiness - 1)
        else:
            self.sleepiness = max(0, self.sleepiness - 2)
            if self.sleepiness == 0:
                self.wake_up()

        self.update_color()
        self.make_decision()

    def update_color(self):
        if not self.tamagotchi_logic.debug_mode:
            return

        # Calculate color based on happiness (0-100)
        # 0 (unhappy) = red (255, 0, 0)
        # 50 (neutral) = yellow (255, 255, 0)
        # 100 (happy) = green (0, 255, 0)
        if self.happiness <= 50:
            red = 255
            green = int((self.happiness / 50) * 255)
        else:
            red = int(((100 - self.happiness) / 50) * 255)
            green = 255

        self.target_color = QtGui.QColor(red, green, 0)

        if self.color != self.target_color:
            self.start_color_transition()

    def start_color_transition(self):
        self.color_transition_timer.start(50)  # Update every 50ms

    def transition_color(self):
        if self.color == self.target_color:
            self.color_transition_timer.stop()
            return

        r = self.color.red() + (self.target_color.red() - self.color.red()) // 10
        g = self.color.green() + (self.target_color.green() - self.color.green()) // 10
        b = self.color.blue() + (self.target_color.blue() - self.color.blue()) // 10

        self.color = QtGui.QColor(r, g, b)
        self.update_squid_image()

    def update_squid_image(self):
        for key in self.images:
            colored_image = self.images[key].copy()
            painter = QtGui.QPainter(colored_image)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
            painter.fillRect(colored_image.rect(), self.color)
            painter.end()
            self.images[key] = colored_image

        self.squid_item.setPixmap(self.current_image())

    def make_decision(self):
        inputs = {
            "hunger": self.hunger / 100,
            "sleepiness": self.sleepiness / 100,
            "happiness": self.happiness / 100
        }
        outputs = self.brain.think(inputs)

        action = max(outputs, key=outputs.get)
        if action == "eat" and outputs["eat"] > 0.5:
            self.find_food()
        elif action == "sleep" and outputs["sleep"] > 0.5:
            self.go_to_sleep()
        elif action == "play" and outputs["play"] > 0.5:
            self.play()

    def find_food(self):
        self.squid_direction = "left" if self.squid_x > self.center_x else "right"
        if abs(self.squid_x - self.center_x) < self.squid_speed:
            self.eat()

    def eat(self):
        prev_hunger = self.hunger
        self.hunger = max(0, self.hunger - 20)
        self.happiness = min(100, self.happiness + 10)
        self.tamagotchi_logic.show_message("Squid is eating!")
        reward = (prev_hunger - self.hunger) / 100  # Positive reward for reducing hunger
        self.brain.update_connections(reward)

    def go_to_sleep(self):
        if not self.is_sleeping:
            self.is_sleeping = True
            self.squid_direction = "none"
            self.tamagotchi_logic.show_message("Squid is sleeping...")
            reward = 0.1  # Small positive reward for going to sleep when tired
            self.brain.update_connections(reward)

    def wake_up(self):
        self.is_sleeping = False
        self.sleepiness = 0
        self.happiness = min(100, self.happiness + 20)
        self.tamagotchi_logic.show_message("Squid woke up!")

    def play(self):
        prev_happiness = self.happiness
        self.happiness = min(100, self.happiness + 10)
        self.tamagotchi_logic.show_message("Squid is playing!")
        reward = (self.happiness - prev_happiness) / 100  # Positive reward for increasing happiness
        self.brain.update_connections(reward)

    def move_squid(self):
        if self.is_sleeping:
            return

        squid_x_new = self.squid_x
        squid_y_new = self.squid_y

        if self.squid_direction == "left":
            squid_x_new -= self.squid_speed
        elif self.squid_direction == "right":
            squid_x_new += self.squid_speed
        elif self.squid_direction == "up":
            squid_y_new -= self.vertical_speed
        elif self.squid_direction == "down":
            squid_y_new += self.vertical_speed

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

        if self.squid_direction in ["left", "right"]:
            self.current_frame = (self.current_frame + 1) % 2
            self.squid_item.setPixmap(self.current_image())
        else:
            self.squid_item.setPixmap(self.current_image())

        self.squid_item.setPos(self.squid_x, self.squid_y)

        if random.random() < 0.15:
            self.change_direction()

    def change_direction(self):
        left_prob = 0.25 + 0.25 * (self.squid_x - self.center_x) / self.center_x
        right_prob = 0.25 + 0.25 * (self.center_x - self.squid_x) / self.center_x
        up_prob = 0.25 + 0.25 * (self.squid_y - self.center_y) / self.center_y
        down_prob = 0.25 + 0.25 * (self.center_y - self.squid_y) / self.center_y

        total = left_prob + right_prob + up_prob + down_prob
        left_prob /= total
        right_prob /= total
        up_prob /= total
        down_prob /= total

        rand = random.random()
        if rand < left_prob:
            new_direction = "left"
        elif rand < left_prob + right_prob:
            new_direction = "right"
        elif rand < left_prob + right_prob + up_prob:
            new_direction = "up"
        else:
            new_direction = "down"

        self.squid_direction = new_direction

    def current_image(self):
        if self.is_sleeping:
            return self.images["left1"]  # Use left1 as sleeping image
        if self.squid_direction in ["left", "right"]:
            return self.images[f"{self.squid_direction}{self.current_frame + 1}"]
        return self.images["left1"]