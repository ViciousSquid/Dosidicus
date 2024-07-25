from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import time
from statistics_window import StatisticsWindow

class TamagotchiLogic:
    def __init__(self, user_interface, squid):
        self.user_interface = user_interface
        self.squid = squid

        # Connect menu actions
        self.user_interface.feed_action.triggered.connect(self.feed_squid)
        self.user_interface.clean_action.triggered.connect(self.clean_environment)
        self.user_interface.connect_view_cone_action(self.squid.toggle_view_cone)

        self.user_interface.debug_action.triggered.connect(self.toggle_debug_mode)

        self.user_interface.window.resizeEvent = self.handle_window_resize

        self.lights_on = True
        self.debug_mode = False
        self.statistics_window = StatisticsWindow(squid)
        self.statistics_window.show()

        self.food_items = []
        self.max_food = 3
        self.base_food_speed = 90  # pixels per update at 1x speed
        self.food_width = 64
        self.food_height = 64

        self.poop_items = []
        self.max_poop = 3

        self.last_clean_time = 0
        self.clean_cooldown = 60  # 60 seconds cooldown

        self.simulation_speed = 1
        self.setup_speed_menu()

        self.base_interval = 1000  # 1000 milliseconds (1 second)
        self.setup_timers()

    def setup_speed_menu(self):
        speed_menu = self.user_interface.menu_bar.addMenu('Speed')

        speed_actions = {
            "Pause": 0,
            "1x": 1,
            "2x": 2,
            "4x": 4
        }

        for label, speed in speed_actions.items():
            action = QtWidgets.QAction(label, self.user_interface.window)
            action.triggered.connect(lambda checked, s=speed: self.set_simulation_speed(s))
            speed_menu.addAction(action)

    def set_simulation_speed(self, speed):
        self.simulation_speed = speed
        self.update_timers()
        if self.squid:
            self.squid.set_animation_speed(speed)
        print(f"Simulation speed set to {speed}x")

    def setup_timers(self):
        self.simulation_timer = QtCore.QTimer()
        self.simulation_timer.timeout.connect(self.update_simulation)
        self.update_timers()

    def update_timers(self):
        if self.simulation_speed == 0:
            self.simulation_timer.stop()
        else:
            interval = self.base_interval // self.simulation_speed
            self.simulation_timer.start(interval)

    def update_simulation(self):
        self.move_objects()
        self.animate_poops()
        self.update_statistics()
        if self.squid:
            self.squid.move_squid()

    def move_objects(self):
        self.move_foods()
        self.move_poops()

    def move_foods(self):
        for food_item in self.food_items[:]:
            food_x = food_item.pos().x()
            food_y = food_item.pos().y() + (self.base_food_speed * self.simulation_speed)

            if food_y > self.user_interface.window_height - 120 - self.food_height:
                food_y = self.user_interface.window_height - 120 - self.food_height

            food_item.setPos(food_x, food_y)

            if self.squid is not None and food_item.collidesWithItem(self.squid.squid_item):
                self.squid.eat()
                self.remove_food(food_item)

    def remove_food(self, food_item):
        if food_item in self.food_items:
            self.user_interface.scene.removeItem(food_item)
            self.food_items.remove(food_item)

    def move_poops(self):
        for poop_item in self.poop_items[:]:
            poop_x = poop_item.pos().x()
            poop_y = poop_item.pos().y() + (self.base_food_speed * self.simulation_speed)

            if poop_y > self.user_interface.window_height - 120 - self.squid.poop_height:
                poop_y = self.user_interface.window_height - 120 - self.squid.poop_height

            poop_item.setPos(poop_x, poop_y)

    def update_statistics(self):
        self.statistics_window.update_statistics()
        self.update_cleanliness_overlay()

        if self.squid is not None:
            # Update squid needs
            if not self.squid.is_sleeping:
                self.squid.hunger = min(100, self.squid.hunger + (0.1 * self.simulation_speed))
                self.squid.sleepiness = min(100, self.squid.sleepiness + (0.1 * self.simulation_speed))
                self.squid.happiness = max(0, self.squid.happiness - (0.1 * self.simulation_speed))

                # Check if squid should go to sleep
                if self.squid.sleepiness >= 100:
                    self.squid.go_to_sleep()
                    self.show_message("Squid is very tired and went to sleep!")
            else:
                self.squid.sleepiness = max(0, self.squid.sleepiness - (0.2 * self.simulation_speed))
                if self.squid.sleepiness == 0:
                    self.squid.wake_up()

    def handle_window_resize(self, event):
        self.user_interface.window_width = event.size().width()
        self.user_interface.window_height = event.size().height()
        self.user_interface.scene.setSceneRect(0, 0, self.user_interface.window_width, self.user_interface.window_height)

        if hasattr(self.user_interface, 'rect_item'):
            self.user_interface.rect_item.setRect(50, 50, self.user_interface.window_width - 100, self.user_interface.window_height - 100)

        if hasattr(self.user_interface, 'cleanliness_overlay'):
            self.user_interface.cleanliness_overlay.setRect(50, 50, self.user_interface.window_width - 100, self.user_interface.window_height - 100)

        if hasattr(self.user_interface, 'feeding_message'):
            self.user_interface.feeding_message.setGeometry(0, self.user_interface.window_height - 30, self.user_interface.window_width, 30)

        if self.squid:
            self.squid.update_preferred_vertical_range()

    def feed_squid(self):
        self.spawn_food()

    def clean_environment(self):
        current_time = time.time()
        if current_time - self.last_clean_time < self.clean_cooldown:
            remaining_cooldown = int(self.clean_cooldown - (current_time - self.last_clean_time))
            self.show_message(f"Cleaning is on cooldown. Please wait {remaining_cooldown} seconds.")
            return

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

        for food_item in self.food_items[:]:
            if food_item.pos().x() > new_x:
                self.remove_food(food_item)

        # Force an update of the scene
        self.user_interface.scene.update()

    def finish_cleaning(self):
        # Remove the cleaning line
        self.user_interface.scene.removeItem(self.cleaning_line)

        # Update squid stats if the squid object is available
        if self.squid is not None:
            self.squid.cleanliness = 100
            self.squid.happiness = min(100, self.squid.happiness + 20)

        # Show a message
        self.show_message("Environment cleaned! Squid is happier!")

        # Force an update of the scene
        self.user_interface.scene.update()

    def show_message(self, message):
        self.user_interface.show_message(message)

    def toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        if self.debug_mode:
            for input_field in self.statistics_window.statistic_inputs.values():
                input_field.setReadOnly(False)  # Enable editing
            self.statistics_window.apply_button.setEnabled(True)  # Enable the apply button
        else:
            for input_field in self.statistics_window.statistic_inputs.values():
                input_field.setReadOnly(True)  # Disable editing
            self.statistics_window.apply_button.setEnabled(False)  # Disable the apply button

    def update_cleanliness_overlay(self):
        if self.squid is not None:
            cleanliness = self.squid.cleanliness
            if cleanliness < 15:
                opacity = 200
            elif cleanliness < 50:
                opacity = 100
            else:
                opacity = 0
            self.user_interface.cleanliness_overlay.setBrush(QtGui.QBrush(QtGui.QColor(139, 69, 19, opacity)))

    def spawn_food(self):
        if len(self.food_items) < self.max_food:
            food_pixmap = QtGui.QPixmap(os.path.join("images", "food.png"))
            food_pixmap = food_pixmap.scaled(self.food_width, self.food_height)

            food_item = QtWidgets.QGraphicsPixmapItem(food_pixmap)

            food_x = random.randint(50, self.user_interface.window_width - 50 - self.food_width)
            food_y = 50  # Start at the top of the screen
            food_item.setPos(food_x, food_y)

            self.user_interface.scene.addItem(food_item)
            self.food_items.append(food_item)

    def spawn_poop(self, x, y):
        if len(self.poop_items) < self.max_poop and self.squid is not None:
            poop_item = QtWidgets.QGraphicsPixmapItem(self.squid.poop_images[0])
            poop_item.setPos(x - self.squid.poop_width // 2, y)
            self.user_interface.scene.addItem(poop_item)
            self.poop_items.append(poop_item)

    def animate_poops(self):
        if self.squid is not None:
            for poop_item in self.poop_items:
                current_frame = self.poop_items.index(poop_item) % 2
                poop_item.setPixmap(self.squid.poop_images[current_frame])
