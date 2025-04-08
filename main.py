import sys
import time
import json
import os
os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false'
import traceback
import logging
from PyQt5 import QtWidgets, QtCore
import random
import argparse
from src.ui import Ui
from src.tamagotchi_logic import TamagotchiLogic
from src.squid import Squid, Personality
from src.splash_screen import SplashScreen
from src.save_manager import SaveManager
from src.squid_brain_window import SquidBrainWindow
from src.learning import LearningConfig
from src.plugin_manager import PluginManager

# Enable high-DPI scaling (Qt5)
#QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)

# Set up logging
logging.basicConfig(filename='dosidicus_log.txt', level=logging.ERROR, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

def global_exception_handler(exctype, value, tb):
    """Global exception handler to log unhandled exceptions"""
    error_message = ''.join(traceback.format_exception(exctype, value, tb))
    logging.error("Unhandled exception:\n%s", error_message)
    QtWidgets.QMessageBox.critical(None, "Error", 
                                 "An unexpected error occurred. Please check dosidicus_log.txt for details.")

class TeeStream:
    """Duplicate output to both console and file"""
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
    def __init__(self, specified_personality=None, debug_mode=False, neuro_cooldown=None, parent=None):
        super().__init__(parent)
        
        # Initialize configuration
        self.config = LearningConfig()
        if neuro_cooldown is not None:
            self.config.neurogenesis['cooldown'] = neuro_cooldown
        
        # Set up debugging
        self.debug_mode = debug_mode
        if self.debug_mode:
            self.setup_logging()
        
        # Initialize UI with debug mode
        self.user_interface = Ui(self, debug_mode=self.debug_mode)

        # Initialize plugin manager - do this before other components
        self.plugin_manager = PluginManager()
        print("  ")
        print(f"Plugin manager initialized: {self.plugin_manager}")
        print("  ")
        
        # Create SquidBrainWindow with config
        self.brain_window = SquidBrainWindow(None, self.debug_mode, self.config)
        self.user_interface.squid_brain_window = self.brain_window
        
        self.specified_personality = specified_personality
        self.neuro_cooldown = neuro_cooldown
        self.squid = None
        
        # Check for existing save data
        self.save_manager = SaveManager("saves")
        if self.save_manager.save_exists() and specified_personality is None:
            print("Existing save data found and will be loaded")
            self.squid = Squid(self.user_interface, None, None)
            self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
            
            # Set up connections first
            self.squid.tamagotchi_logic = self.tamagotchi_logic
            self.user_interface.tamagotchi_logic = self.tamagotchi_logic
            self.brain_window.tamagotchi_logic = self.tamagotchi_logic
            
            # Now load from save data
            self.create_squid_from_save_data()
        else:
            print(f"  ")

            print(f"#  ░▒▓███████▓▒░ ░▒▓██████▓▒░ ░▒▓███████▓▒░▒▓█▓▒░▒▓███████▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓███████▓▒░ ")
            print(f"#  ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        ")
            print(f"#  ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░        ")
            print(f"#  ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░  ")
            print(f"#  ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ ")
            print(f"#  ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░ ")
            print(f"#  ░▒▓███████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░░▒▓█▓▒░▒▓███████▓▒░░▒▓█▓▒░░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░  ")
            print(" #                                https://github.com/ViciousSquid/Dosidicus ")
 
            self.create_new_game(self.specified_personality)
            self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
            
            # Connect components
            self.squid.tamagotchi_logic = self.tamagotchi_logic
            self.user_interface.tamagotchi_logic = self.tamagotchi_logic
            self.brain_window.tamagotchi_logic = self.tamagotchi_logic

        # Now that tamagotchi_logic is created, set it in plugin_manager
        self.plugin_manager.tamagotchi_logic = self.tamagotchi_logic
        self.tamagotchi_logic.plugin_manager = self.plugin_manager
        
        # Load and initialize plugins
        #print("Loading all plugins...")
        plugin_results = self.plugin_manager.load_all_plugins()
        #print(f"Plugin loading results: {plugin_results}")
        
        # Update status bar with plugin information
        if hasattr(self.user_interface, 'status_bar'):
            self.user_interface.status_bar.update_plugins_status(self.plugin_manager)
        
        # Connect signals
        self.user_interface.new_game_action.triggered.connect(self.start_new_game)
        self.user_interface.load_action.triggered.connect(self.load_game)
        self.user_interface.save_action.triggered.connect(self.save_game)
        self.user_interface.decorations_action.triggered.connect(self.user_interface.toggle_decoration_window)
        
        # Initialize plugin menu - do this AFTER loading plugins
        self.user_interface.setup_plugin_menu(self.plugin_manager)

        if self.debug_mode:
            print(f"DEBUG MODE ENABLED: Console output is being logged to console.txt")

    def position_and_show_decoration_window(self):
        """Position the decoration window in the bottom right and show it"""
        if hasattr(self.user_interface, 'decoration_window') and self.user_interface.decoration_window:
            # Get screen geometry
            screen_geometry = QtWidgets.QApplication.desktop().availableGeometry()
            
            # Position window in bottom right
            decoration_window = self.user_interface.decoration_window
            decoration_window.move(
                screen_geometry.right() - decoration_window.width(),
                screen_geometry.bottom() - decoration_window.height() - 100
            )
            decoration_window.show()

    def setup_logging(self):
        """Configure logging for debug mode"""
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
            filename='console.txt',
            filemode='w'
        )
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s:%(message)s'))
        logging.getLogger().addHandler(console_handler)

        # Tee output to file
        sys.stdout = TeeStream(sys.stdout, open('console.txt', 'w'))
        sys.stderr = TeeStream(sys.stderr, open('console.txt', 'a'))

    def create_new_game(self, personality=None):
        """Initialize a new game with specified personality"""
        personality = personality or random.choice(list(Personality))
        
        self.squid = Squid(
            user_interface=self.user_interface,
            tamagotchi_logic=None,
            personality=personality,
            neuro_cooldown=self.neuro_cooldown
        )
        
        print(f"    ")
        print(f">> Generated squid personality: {self.squid.personality.value}")
        print(f"    ")
        if self.neuro_cooldown:
            print(f"\033Neurogenesis cooldown:\033[0m {self.neuro_cooldown}")
        
        self.squid.memory_manager.clear_all_memories()
        self.show_splash_screen()

    def start_new_game(self):
        """Handle new game request"""
        self.create_new_game()
        self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
        self.squid.tamagotchi_logic = self.tamagotchi_logic
        self.user_interface.tamagotchi_logic = self.tamagotchi_logic
        self.brain_window.tamagotchi_logic = self.tamagotchi_logic
        self.brain_window.update_personality_display(self.squid.personality)
        self.tamagotchi_logic.set_simulation_speed(0)
        self.show_splash_screen()

    def create_squid_from_save_data(self):
        """Load squid state from save file"""
        save_data = self.save_manager.load_game()
        if save_data and 'game_state' in save_data and 'squid' in save_data['game_state']:
            squid_data = save_data['game_state']['squid']
            personality = Personality(squid_data['personality'])
            self.squid.load_state(squid_data)
            print(f"\033Loaded squid with personality:\033[0m {self.squid.personality.value}")
            
            # Show the pause message first
            if hasattr(self.user_interface, 'show_pause_message'):
                try:
                    self.user_interface.show_pause_message(True)
                except Exception as e:
                    print(f"Warning: Failed to show pause message: {e}")
            
            # Initialize but keep paused
            self.tamagotchi_logic.start_autosave()
            
            # Open windows without changing speed
            QtCore.QTimer.singleShot(1000, self.open_initial_windows)
            
            # Make sure we're actually paused
            self.tamagotchi_logic.set_simulation_speed(0)
        else:
            print("No existing save data found - Starting new simulation")
            self.create_new_game()

    def load_game(self):
        """Delegate to tamagotchi_logic"""
        self.tamagotchi_logic.load_game()

    def save_game(self):
        """Delegate to tamagotchi_logic"""
        if self.squid and self.tamagotchi_logic:
            self.tamagotchi_logic.save_game(self.squid, self.tamagotchi_logic)

    def update_brain_window(self):
        """Update brain visualization with current state"""
        if self.squid and self.brain_window.isVisible():
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
                "personality": self.squid.personality.value,
                "novelty_exposure": self.tamagotchi_logic.neurogenesis_triggers['novel_objects'],
                "sustained_stress": self.tamagotchi_logic.neurogenesis_triggers['high_stress_cycles'],
                "recent_rewards": self.tamagotchi_logic.neurogenesis_triggers['positive_outcomes']
            }
            self.brain_window.update_brain(current_state)

    def show_splash_screen(self):
        """Display splash screen animation"""
        self.splash = SplashScreen(self)
        self.splash.finished.connect(self.start_simulation)
        self.splash.second_frame.connect(self.show_hatching_notification)
        self.splash.show()

    def start_simulation(self):
        """Begin the simulation and automatically open brain and decoration windows"""
        print("  ")
        self.tamagotchi_logic.set_simulation_speed(1)
        self.tamagotchi_logic.start_autosave()

        # Use QTimer to delay opening windows slightly
        QtCore.QTimer.singleShot(500, self.open_initial_windows)

    def show_hatching_notification(self):
        """Display hatching message"""
        self.user_interface.show_message("Squid is hatching!")

    def open_initial_windows(self):
        """Open brain window and decorations window"""
        # Open brain window
        if hasattr(self, 'brain_window'):
            self.brain_window.show()
            self.user_interface.brain_action.setChecked(True)

        # Open decorations window
        if hasattr(self.user_interface, 'decoration_window'):
            self.position_and_show_decoration_window()
            self.user_interface.decorations_action.setChecked(True)

    
    def initialize_multiplayer_manually(self):
        """Manually initialize multiplayer plugin if needed"""
        try:
            # Import the plugin module directly
            import sys
            import os
            plugin_path = os.path.join(os.path.dirname(__file__), 'plugins', 'multiplayer')
            if plugin_path not in sys.path:
                sys.path.insert(0, plugin_path)
                
            import main as multiplayer_main
            
            # Create plugin instance
            multiplayer_plugin = multiplayer_main.MultiplayerPlugin()
            
            # Find it in plugin_manager and add the instance
            for plugin_name, plugin_data in self.plugin_manager.plugins.items():
                if plugin_name.lower() == "multiplayer":
                    plugin_data['instance'] = multiplayer_plugin
                    print(f"Manually added multiplayer plugin instance to {plugin_name}")
                    
                    # Initialize the plugin
                    if hasattr(multiplayer_plugin, 'setup'):
                        multiplayer_plugin.setup(self.plugin_manager)
                    
                    # Register menu actions
                    if hasattr(multiplayer_plugin, 'register_menu_actions'):
                        multiplayer_plugin.register_menu_actions()
                    
                    break
                    
            # Force the UI to refresh plugin menu
            self.user_interface.setup_plugin_menu(self.plugin_manager)
            
            #print("Manual multiplayer initialization complete")
            return True
            
        except Exception as e:
            print(f"Error in manual multiplayer initialization: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main entry point"""
    sys.excepthook = global_exception_handler

    parser = argparse.ArgumentParser(description="Dosidicus digital squid with a neural network")
    parser.add_argument('-p', '--personality', type=str, 
                       choices=[p.value for p in Personality], 
                       help='Specify squid personality')
    parser.add_argument('-d', '--debug', action='store_true', 
                       help='Enable debug mode with console logging')
    parser.add_argument('-nc', '--neurocooldown', type=int, 
                       help='Set neurogenesis cooldown in seconds')
    args = parser.parse_args()

    print(f"Personality: {args.personality}")
    print(f"Debug mode: {args.debug}")
    print(f"Cooldown {args.neurocooldown or 'will be loaded from config'}")

    app = QtWidgets.QApplication(sys.argv)
    
    try:
        personality = Personality(args.personality) if args.personality else None
        main_window = MainWindow(personality, args.debug, args.neurocooldown)
        main_window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("Fatal error in main")
        QtWidgets.QMessageBox.critical(None, "Error", 
                                     f"Critical error: {str(e)}\nSee dosidicus_log.txt for details.")

if __name__ == '__main__':
    main()