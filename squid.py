import os
import random
from PyQt5 import QtCore, QtGui, QtWidgets

class Squid:
    def __init__(self, ui, tamagotchi_logic):
        self.ui = ui
        self.tamagotchi_logic = tamagotchi_logic

        self.left1_image = QtGui.QPixmap(os.path.join("images", "left1.png"))
        self.left2_image = QtGui.QPixmap(os.path.join("images", "left2.png"))
        self.right1_image = QtGui.QPixmap(os.path.join("images", "right1.png"))
        self.right2_image = QtGui.QPixmap(os.path.join("images", "right2.png"))

        self.squid_width = self.left1_image.width()
        self.squid_height = self.left1_image.height()
        self.squid_speed = int(self.squid_width * 0.8)  # Decreased by 20%
        self.vertical_speed = self.squid_speed // 2  # 50% of horizontal speed
        
        # Initialize center coordinates
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        
        self.squid_x = self.center_x
        self.squid_y = self.center_y
        self.squid_direction = random.choice(["left", "right", "up", "down"])

        self.animation_frames = {
            "left": [self.left1_image, self.left2_image],
            "right": [self.right1_image, self.right2_image]
        }
        self.current_frame = 0

        self.update_preferred_vertical_range()

        self.squid_item = QtWidgets.QGraphicsPixmapItem(self.animation_frames.get(self.squid_direction, [self.left1_image])[0])
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.ui.scene.addItem(self.squid_item)

        # Connect the window resize event to our handler
        self.ui.window.resizeEvent = self.handle_window_resize

        self.move_squid()

    def update_preferred_vertical_range(self):
        self.preferred_vertical_range = (self.ui.window_height // 4, self.ui.window_height // 4 * 3)

    def handle_window_resize(self, event):
        # Update window dimensions
        self.ui.window_width = event.size().width()
        self.ui.window_height = event.size().height()
        
        # Recalculate center coordinates
        self.center_x = self.ui.window_width // 2
        self.center_y = self.ui.window_height // 2
        
        # Update scene rect and button strip position
        self.ui.scene.setSceneRect(0, 0, self.ui.window_width, self.ui.window_height)
        self.ui.button_strip.setGeometry(0, self.ui.window_height - 70, self.ui.window_width, 70)
        
        # Update squid's vertical range
        self.update_preferred_vertical_range()
        
        # Ensure squid is within new boundaries
        self.squid_x = max(50, min(self.squid_x, self.ui.window_width - 50 - self.squid_width))
        self.squid_y = max(50, min(self.squid_y, self.ui.window_height - 120 - self.squid_height))
        self.squid_item.setPos(self.squid_x, self.squid_y)

    def move_squid(self):
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

        # Boundary checks
        if squid_x_new < 50:
            squid_x_new = 50
            self.change_direction()
        elif squid_x_new > self.ui.window_width - 50 - self.squid_width:
            squid_x_new = self.ui.window_width - 50 - self.squid_width
            self.change_direction()

        if squid_y_new < 50:
            squid_y_new = 50
            self.change_direction()
        elif squid_y_new > self.ui.window_height - 120 - self.squid_height:  # Adjusted for button strip
            squid_y_new = self.ui.window_height - 120 - self.squid_height
            self.change_direction()

        self.squid_x = squid_x_new
        self.squid_y = squid_y_new

        # Update animation frame
        if self.squid_direction in ["left", "right"]:
            self.current_frame = (self.current_frame + 1) % len(self.animation_frames[self.squid_direction])
            self.squid_item.setPixmap(self.animation_frames[self.squid_direction][self.current_frame])
        else:
            self.squid_item.setPixmap(self.animation_frames["left" if self.squid_direction == "up" else "right"][0])

        self.squid_item.setPos(self.squid_x, self.squid_y)

        # Randomly change direction occasionally, with center attraction
        if random.random() < 0.15:  # 15% chance to change direction each move
            self.change_direction()

        QtCore.QTimer.singleShot(1000, self.move_squid)

    def change_direction(self):
        # Calculate probabilities based on distance from center
        left_prob = 0.25 + 0.25 * (self.squid_x - self.center_x) / self.center_x
        right_prob = 0.25 + 0.25 * (self.center_x - self.squid_x) / self.center_x
        up_prob = 0.25 + 0.25 * (self.squid_y - self.center_y) / self.center_y
        down_prob = 0.25 + 0.25 * (self.center_y - self.squid_y) / self.center_y

        # Normalize probabilities
        total = left_prob + right_prob + up_prob + down_prob
        left_prob /= total
        right_prob /= total
        up_prob /= total
        down_prob /= total

        # Choose new direction based on probabilities
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