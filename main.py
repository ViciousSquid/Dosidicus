#  ENTRY POINT for Dosidicus
# by Rufus Pearce (ViciousSquid)  |  July 2024  |  MIT License
# https://github.com/ViciousSquid/Dosidicus

import sys
from PyQt5 import QtWidgets, QtCore

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid
from splash_screen import SplashScreen
from save_manager import SaveManager

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

        # Initially pause the simulation
        self.tamagotchi_logic.set_simulation_speed(0)

        # Check for existing save data
        save_manager = SaveManager("saves")  # Pass the directory path instead of the file name
        if save_manager.save_exists():
            print("Existing save data found and will be loaded")
            self.tamagotchi_logic.load_game()
            self.start_simulation()
        else:
            print("No save data found: Starting a new simulation.")
            self.show_splash_screen()

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