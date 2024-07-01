from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import time

class TamagotchiLogic:
    def __init__(self, user_interface, squid):
        self.user_interface = user_interface
        self.squid = squid

        self.user_interface.button_a.clicked.connect(self.feed_squid)
        self.user_interface.button_b.clicked.connect(self.play_with_squid)
        self.user_interface.button_c.clicked.connect(self.toggle_lights)

        self.user_interface.debug_action.triggered.connect(self.toggle_debug_mode)

        self.user_interface.window.resizeEvent = self.handle_window_resize

        self.lights_on = True
        self.debug_mode = False
        self.debug_window = None

        self.food_item = None
        self.food_speed = 2
        self.food_width = 64
        self.food_height = 64

        self.user_interface.feed_action.triggered.connect(self.spawn_food)
        self.user_interface.clean_action.triggered.connect(self.clean_environment)

        self.poop_items = []
        self.poop_animation_timer = QtCore.QTimer()
        self.poop_animation_timer.timeout.connect(self.animate_poops)
        self.poop_animation_timer.start(1000)  # Change poop frame every second

        self.last_clean_time = 0
        self.clean_cooldown = 60  # 60 seconds cooldown

    def handle_window_resize(self, event):
        self.user_interface.window_width = event.size().width()
        self.user_interface.window_height = event.size().height()
        self.user_interface.scene.setSceneRect(0, 0, self.user_interface.window_width, self.user_interface.window_height)
        self.user_interface.button_strip.setGeometry(0, self.user_interface.window_height - 70, self.user_interface.window_width, 70)

        self.squid.update_preferred_vertical_range()

    def feed_squid(self):
        self.spawn_food()

    def play_with_squid(self):
        self.squid.play()

    def toggle_lights(self):
        self.lights_on = not self.lights_on
        if self.lights_on:
            self.user_interface.rect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
            self.show_message("Lights on!")
        else:
            self.user_interface.rect_item.setBrush(QtGui.QBrush(QtGui.QColor(100, 100, 100)))
            self.show_message("Lights off!")

    def show_message(self, message):
        self.user_interface.show_message(message)

    def toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        if self.debug_mode:
            self.open_debug_window()
        else:
            self.close_debug_window()

    def open_debug_window(self):
        self.debug_window = QtWidgets.QWidget()
        self.debug_window.setWindowTitle("Squid Debug Info")
        self.debug_window.setGeometry(100, 100, 300, 250)  # Increased height to accommodate the new button

        layout = QtWidgets.QVBoxLayout()
        self.debug_labels = {
            "hunger": QtWidgets.QLabel(),
            "sleepiness": QtWidgets.QLabel(),
            "happiness": QtWidgets.QLabel(),
            "cleanliness": QtWidgets.QLabel(),
            "is_sleeping": QtWidgets.QLabel(),
            "direction": QtWidgets.QLabel(),
            "position": QtWidgets.QLabel(),
        }

        for label in self.debug_labels.values():
            layout.addWidget(label)

        # Add the toggle view cone button
        self.toggle_view_cone_button = QtWidgets.QPushButton("Toggle View Cone")
        self.toggle_view_cone_button.clicked.connect(self.squid.toggle_view_cone)
        layout.addWidget(self.toggle_view_cone_button)

        self.debug_window.setLayout(layout)
        self.debug_window.show()

        self.debug_timer = QtCore.QTimer()
        self.debug_timer.timeout.connect(self.update_debug_info)
        self.debug_timer.start(100)

    def close_debug_window(self):
        if self.debug_window:
            self.debug_window.close()
            self.debug_window = None
        if hasattr(self, 'debug_timer'):
            self.debug_timer.stop()

    def update_debug_info(self):
        if not self.debug_window:
            return

        self.debug_labels["hunger"].setText(f"Hunger: {self.squid.hunger}")
        self.debug_labels["sleepiness"].setText(f"Sleepiness: {self.squid.sleepiness}")
        self.debug_labels["happiness"].setText(f"Happiness: {self.squid.happiness}")
        self.debug_labels["cleanliness"].setText(f"Cleanliness: {self.squid.cleanliness}")
        self.debug_labels["is_sleeping"].setText(f"Sleeping: {self.squid.is_sleeping}")
        self.debug_labels["direction"].setText(f"Direction: {self.squid.squid_direction}")
        self.debug_labels["position"].setText(f"Position: ({self.squid.squid_x}, {self.squid.squid_y})")

    def spawn_food(self):
        if not self.food_item:
            food_pixmap = QtGui.QPixmap(os.path.join("images", "food.png"))
            food_pixmap = food_pixmap.scaled(self.food_width, self.food_height)

            self.food_item = QtWidgets.QGraphicsPixmapItem(food_pixmap)

            food_x = random.randint(50, self.user_interface.window_width - 50 - self.food_width)
            food_y = 50  # Start at the top of the screen
            self.food_item.setPos(food_x, food_y)

            self.user_interface.scene.addItem(self.food_item)

            self.food_timer = QtCore.QTimer()
            self.food_timer.timeout.connect(self.move_food)
            self.food_timer.start(50)

    def move_food(self):
        if self.food_item:
            food_x = self.food_item.pos().x()
            food_y = self.food_item.pos().y() + self.food_speed

            if food_y > self.user_interface.window_height - 120 - self.food_height:
                food_y = self.user_interface.window_height - 120 - self.food_height

            self.food_item.setPos(food_x, food_y)

            if self.food_item.collidesWithItem(self.squid.squid_item):
                self.squid.eat()
                self.remove_food()

    def remove_food(self):
        if self.food_item:
            self.user_interface.scene.removeItem(self.food_item)
            self.food_item = None
            if hasattr(self, 'food_timer') and self.food_timer is not None:
                self.food_timer.stop()

    def spawn_poop(self, x, y):
        poop_item = QtWidgets.QGraphicsPixmapItem(self.squid.poop_images[0])
        poop_item.setPos(x - self.squid.poop_width // 2, y)
        self.user_interface.scene.addItem(poop_item)
        self.poop_items.append(poop_item)

        poop_timer = QtCore.QTimer()
        poop_timer.timeout.connect(lambda: self.move_poop(poop_item, poop_timer))
        poop_timer.start(50)

    def move_poop(self, poop_item, poop_timer):
        poop_x = poop_item.pos().x()
        poop_y = poop_item.pos().y() + self.food_speed

        # Check if the poop has reached the bottom of the screen
        if poop_y > self.user_interface.window_height - 120 - self.squid.poop_height:
            poop_y = self.user_interface.window_height - 120 - self.squid.poop_height
            poop_timer.stop()  # Stop the timer if the poop has reached the bottom
        else:
            poop_y += self.food_speed

        poop_item.setPos(poop_x, poop_y)

    def animate_poops(self):
        for poop_item in self.poop_items:
            current_frame = self.poop_items.index(poop_item) % 2
            poop_item.setPixmap(self.squid.poop_images[current_frame])

    def clean_environment(self):
        print("Clean environment method called")  # Debug print
        current_time = time.time()
        if current_time - self.last_clean_time < self.clean_cooldown:
            remaining_cooldown = int(self.clean_cooldown - (current_time - self.last_clean_time))
            print(f"Cleaning on cooldown. {remaining_cooldown} seconds left")  # Debug print
            self.show_message(f"Cleaning is on cooldown. Please wait {remaining_cooldown} seconds.")
            return

        print("Starting cleaning process")  # Debug print
        self.last_clean_time = current_time

        # Create a cleaning line
        self.cleaning_line = QtWidgets.QGraphicsLineItem(self.user_interface.window_width, 0, 
                                                         self.user_interface.window_width, self.user_interface.window_height - 120)
        self.cleaning_line.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 10))  # Thick black line
        self.user_interface.scene.addItem(self.cleaning_line)

        # Show a message that cleaning has started
        self.show_message("Cleaning in progress...")

        # Set up animation parameters
        self.cleaning_progress = 0
        self.cleaning_timer = QtCore.QTimer()
        self.cleaning_timer.timeout.connect(self.update_cleaning)
        self.cleaning_timer.start(30)  # Update every 30 ms

        print("Cleaning animation started")  # Debug print

    def update_cleaning(self):
        self.cleaning_progress += 1
        if self.cleaning_progress >= 100:
            self.cleaning_timer.stop()
            self.finish_cleaning()
            return

        progress = self.cleaning_progress / 100.0
        new_x = self.user_interface.window_width * (1 - progress)
        self.cleaning_line.setLine(new_x, 0, new_x, self.user_interface.window_height - 120)
        
        # Remove poops and food that the line has passed
        for poop_item in self.poop_items[:]:
            if poop_item.pos().x() > new_x:
                self.user_interface.scene.removeItem(poop_item)
                self.poop_items.remove(poop_item)
        
        if self.food_item and self.food_item.pos().x() > new_x:
            self.remove_food()

        # Force an update of the scene
        self.user_interface.scene.update()

    def finish_cleaning(self):
        # Remove the cleaning line
        self.user_interface.scene.removeItem(self.cleaning_line)

        # Update squid stats
        self.squid.cleanliness = 100
        self.squid.happiness = min(100, self.squid.happiness + 20)

        # Show a message
        self.show_message("Environment cleaned! Squid is happier!")

        # Force an update of the scene
        self.user_interface.scene.update()

        # Update debug info if debug mode is on
        if self.debug_mode:
            self.update_debug_info()

        print("Cleaning process completed")  # Debug print