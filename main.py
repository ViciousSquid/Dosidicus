# Main Entry point

import sys
import os
from PyQt5 import QtWidgets, QtCore
import random
from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid, Personality
from splash_screen import SplashScreen
from save_manager import SaveManager
from squid_brain_window import SquidBrainWindow
import argparse
import logging

class TeeStream:
    def __init__(self, original_stream, file_stream):
        self.original_stream = original_stream
        self.file_stream = file_stream

    def write(self, data):
        self.original_stream.write(data)
        self.file_stream.write(data)
        self.file_stream.flush()

    def flush(self):
        self.original_stream.flush()
        self.file_stream.flush()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, specified_personality=None, debug_mode=False, parent=None):
        super().__init__(parent)
        
        # Set up debugging first
        self.debug_mode = debug_mode
        if self.debug_mode:
            self.setup_logging()
        
        self.user_interface = Ui(self, None)
        
        self.specified_personality = specified_personality
        self.squid = None  # We'll create the squid after deciding on the personality
        
        # Create SquidBrainWindow before TamagotchiLogic
        self.brain_window = SquidBrainWindow()
        
        # Redirect console output to brain window
        sys.stdout = self.brain_window.console
        sys.stderr = self.brain_window.console
        
        # Check for existing save data
        self.save_manager = SaveManager("saves")
        if self.save_manager.save_exists() and specified_personality is None:
            print("Existing save data found and will be loaded")
            self.load_game()
        else:
            print(f"Starting a new simulation with {self.specified_personality.value if self.specified_personality else 'random'} squid.")
            self.create_new_game()

        self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
        
        # Set tamagotchi_logic for the squid and user_interface after it's created
        self.squid.tamagotchi_logic = self.tamagotchi_logic
        self.user_interface.tamagotchi_logic = self.tamagotchi_logic

        self.user_interface.load_action.triggered.connect(self.load_game)
        self.user_interface.save_action.triggered.connect(self.save_game)

        # Show the SquidBrainWindow
        self.brain_window.show()
        self.brain_window.update_personality_display(self.squid.personality)

        # Connect the decoration action to toggle the decoration window
        self.user_interface.decorations_action.triggered.connect(self.user_interface.toggle_decoration_window)

        # Initially pause the simulation
        self.tamagotchi_logic.set_simulation_speed(0)

        # Set up a timer to update the brain window
        self.brain_update_timer = QtCore.QTimer(self)
        self.brain_update_timer.timeout.connect(self.update_brain_window)
        self.brain_update_timer.start(2000)  # Update every 2000 ms

        if self.debug_mode:
            print("Debug mode is enabled. Console output will be saved to console.txt")

    def setup_logging(self):
        # Set up file logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
            filename='console.txt',
            filemode='w'
        )

        # Create a stream handler for the console output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s'))

        # Get the root logger and add the console handler
        root_logger = logging.getLogger()
        root_logger.addHandler(console_handler)

        # Create a TeeStream to capture both console and file output
        tee_stdout = TeeStream(sys.stdout, open('console.txt', 'w'))
        tee_stderr = TeeStream(sys.stderr, open('console.txt', 'a'))

        # Replace sys.stdout and sys.stderr with the TeeStream
        sys.stdout = tee_stdout
        sys.stderr = tee_stderr

    def create_new_game(self):
        if self.specified_personality is None:
            personality = random.choice(list(Personality))
        else:
            personality = self.specified_personality
        
        self.squid = Squid(self.user_interface, None, personality)
        print(f"Created new squid with personality: {self.squid.personality.value}")
        self.show_splash_screen()

    def load_game(self):
        save_data = self.save_manager.load_game()
        if save_data is not None:
            squid_data = save_data['squid']
            personality = Personality(squid_data['personality'])
            self.squid = Squid(self.user_interface, None, personality)
            self.squid.load_state(squid_data)
            print(f"Loaded squid with personality: {self.squid.personality.value}")
            self.start_simulation()
        else:
            print("No save data found. Starting a new game.")
            self.create_new_game()

    def save_game(self):
        if self.squid and self.tamagotchi_logic:
            self.tamagotchi_logic.save_game(self.squid, self.tamagotchi_logic)

    def update_brain_window(self):
        if self.squid:
            current_state = {
                "hunger": self.squid.hunger,
                "happiness": self.squid.happiness,
                "cleanliness": self.squid.cleanliness,
                "sleepiness": self.squid.sleepiness,
                "satisfaction": self.squid.satisfaction,
                "anxiety": self.squid.anxiety,
                "curiosity": self.squid.curiosity,
                "is_sick": self.squid.is_sick,
                "is_sleeping": self.squid.is_sleeping,
                "pursuing_food": self.squid.pursuing_food,
                "direction": self.squid.squid_direction,
                "position": (self.squid.squid_x, self.squid.squid_y),
                "personality": self.squid.personality.value
            }
            self.brain_window.update_brain(current_state)

    def show_splash_screen(self):
        self.splash = SplashScreen(self)
        self.splash.finished.connect(self.start_simulation)
        self.splash.second_frame.connect(self.show_hatching_notification)
        self.splash.show()

    def start_simulation(self):
        print("Starting simulation")
        self.tamagotchi_logic.set_simulation_speed(1)
        self.tamagotchi_logic.start_autosave()

    def show_hatching_notification(self):
        self.user_interface.show_message("Squid is hatching!")
        # The message will automatically fade out after 8 seconds as per the show_message implementation

def main():
    parser = argparse.ArgumentParser(description="Start the squid game with a specific personality and optional debug mode.")
    parser.add_argument('-personality', type=str, choices=[p.value for p in Personality], 
                        help='Specify the squid personality')
    parser.add_argument('-debug', action='store_true', help='Enable debug mode and log console output to console.txt')
    args = parser.parse_args()

    application = QtWidgets.QApplication(sys.argv)
    
    if args.personality:
        personality = Personality(args.personality)
    else:
        personality = None
    
    main_window = MainWindow(personality, args.debug)
    main_window.show()
    sys.exit(application.exec_())

if __name__ == '__main__':
    main()