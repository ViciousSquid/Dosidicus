import sys
from PyQt5 import QtWidgets, QtCore

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid
from splash_screen import SplashScreen
from save_manager import SaveManager
from squid_brain_window import SquidBrainWindow  # Import the SquidBrainWindow

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui(self, None)
        self.squid = Squid(self.ui, None)
        self.tamagotchi_logic = TamagotchiLogic(self.ui, self.squid)
        
        self.squid.tamagotchi_logic = self.tamagotchi_logic
        self.ui.tamagotchi_logic = self.tamagotchi_logic

        self.ui.load_action.triggered.connect(self.tamagotchi_logic.load_game)
        self.ui.save_action.triggered.connect(lambda: self.tamagotchi_logic.save_game(self.squid, self.tamagotchi_logic))

        # Create and show the SquidBrainWindow
        self.brain_window = SquidBrainWindow()
        self.brain_window.show()

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
        }
        self.brain_window.update_brain_state(current_state)

    def show_splash_screen(self):
        self.splash = SplashScreen(self)
        self.splash.finished.connect(self.start_simulation)
        self.splash.show()

    def start_simulation(self):
        print("Starting simulation")
        self.tamagotchi_logic.set_simulation_speed(1)
        self.tamagotchi_logic.start_autosave()

def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()