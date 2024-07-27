# Tamagotchi logic for a digital pet with a neural network
# by Rufus Pearce (ViciousSquid)  |  July 2024  |  MIT License
# https://github.com/ViciousSquid/Dosidicus

from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import time
import math
from statistics_window import StatisticsWindow
from save_manager import SaveManager
from rps_game import RPSGame

class TamagotchiLogic:
    def __init__(self, user_interface, squid):
        self.user_interface = user_interface
        self.squid = squid

        # Connect menu actions
        self.user_interface.feed_action.triggered.connect(self.feed_squid)
        self.user_interface.clean_action.triggered.connect(self.clean_environment)
        self.user_interface.connect_view_cone_action(self.squid.toggle_view_cone)
        self.user_interface.medicine_action.triggered.connect(self.give_medicine)
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

        self.cleanliness_threshold_time = 0
        self.hunger_threshold_time = 0

        self.needle_item = None

        self.save_manager = SaveManager("save_data.json")

        self.points = 0
        self.score_update_timer = QtCore.QTimer()
        self.score_update_timer.timeout.connect(self.update_score)
        self.score_update_timer.start(5000)  # Update score every 5 seconds

        self.brain_update_timer = QtCore.QTimer()
        self.brain_update_timer.timeout.connect(self.update_squid_brain)
        self.brain_update_timer.start(1000)  # Update every second

        self.load_game()

        # Initialize new neurons
        self.squid.satisfaction = 50
        self.squid.anxiety = 50
        self.squid.curiosity = 50

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

    def move_squid_to_bottom_left(self, callback):      # Currently buggy but working
        target_x = 150  # Left edge + margin
        target_y = self.user_interface.window_height - 150 - self.squid.squid_height  # Bottom edge - margin - squid height
        
        def step_movement():
            dx = target_x - self.squid.squid_x
            dy = target_y - self.squid.squid_y
            
            if abs(dx) < 90 and abs(dy) < 90:
                # If close enough, snap to final position and call callback
                self.squid.squid_x = target_x
                self.squid.squid_y = target_y
                self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)
                callback()
            else:
                # Determine direction of movement
                if abs(dx) > abs(dy):
                    # Move horizontally
                    self.squid.squid_x += 90 if dx > 0 else -90
                else:
                    # Move vertically
                    self.squid.squid_y += 90 if dy > 0 else -90
                
                # Update squid position
                self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)
                
                # Schedule next movement in 1 second
                QtCore.QTimer.singleShot(1000, step_movement)
        
        # Start the movement
        step_movement()

    def start_rps_game(self):
        self.rps_game = RPSGame(self)
        self.rps_game.start_game()

    def give_medicine(self):
        if self.squid is not None and self.squid.is_sick:
            self.squid.is_sick = False
            self.squid.happiness = max(0, self.squid.happiness - 30)
            self.squid.sleepiness = min(100, self.squid.sleepiness + 50)
            self.show_message("Medicine given. Squid is no longer sick but feels drowsy.")

            # Hide the sick icon immediately
            self.squid.hide_sick_icon()

            # Put the squid to sleep
            self.squid.go_to_sleep()

            # Display the needle image
            self.display_needle_image()
        else:
            self.show_message("Squid is not sick. Medicine not needed.")

    def start_rps_game(self):       ## Entry point for Rock Paper Scissors game
        rps_game = RPSGame(self)
        rps_game.start_game()

    def display_needle_image(self):
        needle_pixmap = QtGui.QPixmap(os.path.join("images", "needle.jpg"))
        self.needle_item = QtWidgets.QGraphicsPixmapItem(needle_pixmap)
        self.needle_item.setPos(self.user_interface.window_width // 2 - needle_pixmap.width() // 2,
                                self.user_interface.window_height // 2 - needle_pixmap.height() // 2)
        self.needle_item.setZValue(10)  # Ensure the needle image is displayed on top of everything
        self.user_interface.scene.addItem(self.needle_item)

        # Create a QGraphicsOpacityEffect
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        self.needle_item.setGraphicsEffect(opacity_effect)

        # Create a QPropertyAnimation for the opacity effect
        self.needle_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        self.needle_animation.setDuration(1000)  # 1 second duration
        self.needle_animation.setStartValue(1.0)
        self.needle_animation.setEndValue(0.0)
        self.needle_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        # Connect the finished signal to remove the item
        self.needle_animation.finished.connect(self.remove_needle_image)

        # Start the animation
        self.needle_animation.start()

    def remove_needle_image(self):
        if self.needle_item is not None:
            self.user_interface.scene.removeItem(self.needle_item)
            self.needle_item = None

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
                self.squid.cleanliness = max(0, self.squid.cleanliness - (0.1 * self.simulation_speed))

                # Update new neurons
                self.update_satisfaction()
                self.update_anxiety()
                self.update_curiosity()

                # Check if cleanliness has been too low for too long
                if self.squid.cleanliness < 20:
                    self.cleanliness_threshold_time += 1
                else:
                    self.cleanliness_threshold_time = 0

                # Check if hunger has been too high for too long
                if self.squid.hunger > 80:
                    self.hunger_threshold_time += 1
                else:
                    self.hunger_threshold_time = 0

                # Check if squid becomes sick (80% chance)
                if (self.cleanliness_threshold_time >= 10 * self.simulation_speed and self.cleanliness_threshold_time <= 60 * self.simulation_speed) or \
                   (self.hunger_threshold_time >= 10 * self.simulation_speed and self.hunger_threshold_time <= 50 * self.simulation_speed):
                    if random.random() < 0.8:
                        self.squid.is_sick = True
                else:
                    self.squid.is_sick = False

                # New logic for health decrease based on happiness and cleanliness
                if self.squid.happiness < 20 and self.squid.cleanliness < 20:
                    health_decrease = 0.2 * self.simulation_speed  # Rapid decrease
                else:
                    health_decrease = 0.1 * self.simulation_speed  # Normal decrease when sick

                if self.squid.is_sick:
                    self.squid.health = max(0, self.squid.health - health_decrease)
                    self.squid.show_sick_icon()
                    if self.squid.health == 0:
                        self.game_over()
                else:
                    self.squid.health = min(100, self.squid.health + (0.1 * self.simulation_speed))
                    self.squid.hide_sick_icon()

                # Check if squid should go to sleep
                if self.squid.sleepiness >= 100:
                    self.squid.go_to_sleep()
                    self.show_message("Squid is very tired and went to sleep!")
            else:
                self.squid.sleepiness = max(0, self.squid.sleepiness - (0.2 * self.simulation_speed))
                if self.squid.sleepiness == 0:
                    self.squid.wake_up()

            # Update points based on squid's status
            if not self.squid.is_sick and self.squid.happiness >= 80 and self.squid.cleanliness >= 80:
                self.points += 1
            elif self.squid.is_sick or self.squid.hunger >= 80 or self.squid.happiness <= 20:
                self.points = max(0, self.points - 1)

            self.user_interface.update_points(self.points)

    def handle_window_resize(self, event):
        self.user_interface.window_width = event.size().width()
        self.user_interface.window_height = event.size().height()
        self.user_interface.scene.setSceneRect(0, 0, self.user_interface.window_width, self.user_interface.window_height)

        if hasattr(self.user_interface, 'rect_item'):
            self.user_interface.rect_item.setRect(50, 50, self.user_interface.window_width - 100, self.user_interface.window_height - 100)

        if hasattr(self.user_interface, 'cleanliness_overlay'):
            self.user_interface.cleanliness_overlay.setRect(50, 50, self.user_interface.window_width - 100, self.user_interface.window_height - 100)

        if hasattr(self.user_interface, 'feeding_message'):
            self.user_interface.feeding_message.setPos(0, self.user_interface.window_height - 30)
            self.user_interface.feeding_message.setTextWidth(self.user_interface.window_width)

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
        self.statistics_window.set_debug_mode(self.debug_mode)
        print(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")

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

    def game_over(self):
        game_over_dialog = QtWidgets.QMessageBox()
        game_over_dialog.setIcon(QtWidgets.QMessageBox.Critical)
        game_over_dialog.setText("Game Over")
        game_over_dialog.setInformativeText("Your squid has died due to poor health.")
        game_over_dialog.setWindowTitle("Game Over")
        game_over_dialog.exec_()
        self.user_interface.window.close()

        # Add any additional game over logic or cleanup here
        print("Game Over - Squid died due to poor health")

        # Save the game state before resetting
        self.save_game()

        # Reset the game state
        self.reset_game()

    def reset_game(self):
        # Reset squid attributes
        self.squid.hunger = 25
        self.squid.sleepiness = 30
        self.squid.happiness = 100
        self.squid.cleanliness = 100
        self.squid.is_sleeping = False
        self.squid.health = 100
        self.squid.is_sick = False

        # Reset new neurons
        self.squid.satisfaction = 50
        self.squid.anxiety = 50
        self.squid.curiosity = 50

        # Reset game variables
        self.cleanliness_threshold_time = 0
        self.hunger_threshold_time = 0
        self.last_clean_time = 0

        # Clear food and poop items
        for food_item in self.food_items:
            self.user_interface.scene.removeItem(food_item)
        self.food_items.clear()

        for poop_item in self.poop_items:
            self.user_interface.scene.removeItem(poop_item)
        self.poop_items.clear()

        # Reset squid position
        self.squid.squid_x = self.squid.center_x
        self.squid.squid_y = self.squid.center_y
        self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)

        # Show a message
        self.show_message("Game reset. Take better care of your squid!")

        # Force an update of the scene
        self.user_interface.scene.update()

        # Save the game state after resetting
        self.save_game()

    def load_game(self):
        save_data = self.save_manager.load_game()
        if save_data is not None:
            squid_data = save_data["squid"]
            self.squid.hunger = squid_data["hunger"]
            self.squid.sleepiness = squid_data["sleepiness"]
            self.squid.happiness = squid_data["happiness"]
            self.squid.cleanliness = squid_data["cleanliness"]
            self.squid.health = squid_data["health"]
            self.squid.is_sick = squid_data["is_sick"]
            self.squid.squid_x = squid_data["squid_x"]
            self.squid.squid_y = squid_data["squid_y"]
            self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)

            tamagotchi_logic_data = save_data["tamagotchi_logic"]
            self.cleanliness_threshold_time = tamagotchi_logic_data["cleanliness_threshold_time"]
            self.hunger_threshold_time = tamagotchi_logic_data["hunger_threshold_time"]
            self.last_clean_time = tamagotchi_logic_data["last_clean_time"]

            decorations_data = save_data.get('decorations', [])
            self.user_interface.load_decorations_data(decorations_data)

    def update_score(self):
        if self.squid is not None:
            if not self.squid.is_sick and self.squid.happiness >= 80 and self.squid.cleanliness >= 80:
                self.points += 1
            elif self.squid.is_sick or self.squid.hunger >= 80 or self.squid.happiness <= 20:
                self.points -= 1

            self.user_interface.update_points(self.points)

    def update_squid_brain(self):
        brain_state = {}
        if self.squid and self.user_interface.squid_brain_window.isVisible():
            brain_state = {
                "hunger": self.squid.hunger,
                "happiness": self.squid.happiness,
                "cleanliness": self.squid.cleanliness,
                "sleepiness": self.squid.sleepiness,
                "satisfaction": self.squid.satisfaction,
                "anxiety": self.squid.anxiety,
                "curiosity": self.squid.curiosity,
                "is_sick": self.squid.is_sick,
                "is_eating": self.squid.status == "eating",
                "is_sleeping": self.squid.is_sleeping,
                "pursuing_food": self.squid.pursuing_food,
                "direction": self.squid.squid_direction,
                "position": (self.squid.squid_x, self.squid.squid_y)
            }
        self.user_interface.squid_brain_window.update_brain(brain_state)

    def save_game(self):
        squid_data = {
            "hunger": self.squid.hunger,
            "sleepiness": self.squid.sleepiness,
            "happiness": self.squid.happiness,
            "cleanliness": self.squid.cleanliness,
            "health": self.squid.health,
            "is_sick": self.squid.is_sick,
            "squid_x": self.squid.squid_x,
            "squid_y": self.squid.squid_y,
            "satisfaction": self.squid.satisfaction,
            "anxiety": self.squid.anxiety,
            "curiosity": self.squid.curiosity
        }

        tamagotchi_logic_data = {
            "cleanliness_threshold_time": self.cleanliness_threshold_time,
            "hunger_threshold_time": self.hunger_threshold_time,
            "last_clean_time": self.last_clean_time
        }

        decorations_data = self.user_interface.get_decorations_data()

        save_data = {
            'squid': squid_data,
            'tamagotchi_logic': tamagotchi_logic_data,
            'decorations': decorations_data
        }

        self.save_manager.save_game(save_data)

    # New methods to update the new neurons
    def update_satisfaction(self):
        # Update satisfaction based on hunger, happiness, and cleanliness
        hunger_factor = max(0, 1 - self.squid.hunger / 100)
        happiness_factor = self.squid.happiness / 100
        cleanliness_factor = self.squid.cleanliness / 100

        satisfaction_change = (hunger_factor + happiness_factor + cleanliness_factor) / 3
        satisfaction_change = (satisfaction_change - 0.5) * 2  # Scale to range from -1 to 1

        self.squid.satisfaction += satisfaction_change * self.simulation_speed
        self.squid.satisfaction = max(0, min(100, self.squid.satisfaction))

    def update_anxiety(self):
        # Update anxiety based on hunger, cleanliness, and health
        hunger_factor = self.squid.hunger / 100
        cleanliness_factor = 1 - self.squid.cleanliness / 100
        health_factor = 1 - self.squid.health / 100

        anxiety_change = (hunger_factor + cleanliness_factor + health_factor) / 3

        self.squid.anxiety += anxiety_change * self.simulation_speed
        self.squid.anxiety = max(0, min(100, self.squid.anxiety))

    def update_curiosity(self):
        # Update curiosity based on satisfaction and anxiety
        if self.squid.satisfaction > 70 and self.squid.anxiety < 30:
            curiosity_change = 0.2 * self.simulation_speed
        else:
            curiosity_change = -0.1 * self.simulation_speed

        self.squid.curiosity += curiosity_change
        self.squid.curiosity = max(0, min(100, self.squid.curiosity))