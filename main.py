import sys
import traceback
from PyQt5 import QtWidgets, QtCore
import random
from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid, Personality
from splash_screen import SplashScreen
from save_manager import SaveManager
from squid_brain_window import SquidBrainWindow
from error_logging import log_error

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_interface = Ui(self, None)
        personality = random.choice(list(Personality))
        self.squid = Squid(self.user_interface, None, personality)
        
        # Create SquidBrainWindow before TamagotchiLogic
        self.brain_window = SquidBrainWindow()
        self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
        
        # Set tamagotchi_logic for the squid and user_interface after it's created
        self.squid.tamagotchi_logic = self.tamagotchi_logic
        self.user_interface.tamagotchi_logic = self.tamagotchi_logic

        self.user_interface.load_action.triggered.connect(self.tamagotchi_logic.load_game)
        self.user_interface.save_action.triggered.connect(lambda: self.tamagotchi_logic.save_game(self.squid, self.tamagotchi_logic))

        # Show the SquidBrainWindow
        self.brain_window.show()
        self.brain_window.update_personality_display(self.squid.personality)

        # Connect the decoration action to toggle the decoration window
        self.user_interface.decorations_action.triggered.connect(self.user_interface.toggle_decoration_window)

        # Initially pause the simulation
        self.tamagotchi_logic.set_simulation_speed(0)

        # Check for existing save data
        save_manager = SaveManager("saves")
        if save_manager.save_exists():
            print("Existing save data found and will be loaded")
            self.tamagotchi_logic.load_game()
            self.start_simulation()
        else:
            print("No save data found: Starting a new simulation.")
            self.show_splash_screen()

        # Set up a timer to update the brain window
        self.brain_update_timer = QtCore.QTimer(self)
        self.brain_update_timer.timeout.connect(self.update_brain_window)
        self.brain_update_timer.start(2000)  # Update every 2000 ms

        # Connect the save_debug_output method to the application's aboutToQuit signal
        QtCore.QCoreApplication.instance().aboutToQuit.connect(self.tamagotchi_logic.save_debug_output)

    def update_brain_window(self):
        # Get the current state from your squid or tamagotchi logic
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

def exception_hook(exctype, value, tb):
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    print(error_msg)  # Print to console
    log_error(f"Uncaught exception:\n{error_msg}")  # Log to file
    QtWidgets.QApplication.quit()  # Terminate the application

def main():
    # Set up global exception handling
    sys.excepthook = exception_hook

    try:
        application = QtWidgets.QApplication(sys.argv)
        
        # Set up event loop exception handling
        def qt_message_handler(mode, context, message):
            if mode == QtCore.QtInfoMsg:
                mode = 'INFO'
            elif mode == QtCore.QtWarningMsg:
                mode = 'WARNING'
            elif mode == QtCore.QtCriticalMsg:
                mode = 'CRITICAL'
            elif mode == QtCore.QtFatalMsg:
                mode = 'FATAL'
            else:
                mode = 'DEBUG'
            print(f'Qt {mode}: {message}')
            log_error(f'Qt {mode}: {message}')

        QtCore.qInstallMessageHandler(qt_message_handler)

        main_window = MainWindow()
        main_window.show()

        # Wrap the exec_ call in a try-except block
        try:
            sys.exit(application.exec_())
        except Exception as e:
            log_error(f"Exception in application.exec_(): {str(e)}")
            raise

    except Exception as e:
        error_message = f"Unhandled exception in main: {str(e)}"
        log_error(error_message)
        raise  # Re-raise the exception after logging

if __name__ == '__main__':
    main()