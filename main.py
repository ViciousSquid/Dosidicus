import sys
import time
import json
import os
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
from src.brain_tool import SquidBrainWindow
from src.learning import LearningConfig
from src.plugin_manager import PluginManager

# Define IMAGE_CACHE here
IMAGE_CACHE = {}

os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false;qt.style.*=false'

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
    def __init__(self, specified_personality=None, debug_mode=False, neuro_cooldown=None, clean_start=False, parent=None):
        super().__init__(parent)

        # Initialize configuration
        self.config = LearningConfig()
        if neuro_cooldown is not None:
            self.config.neurogenesis['cooldown'] = neuro_cooldown

        # Add initialization tracking flag
        self._initialization_complete = False

        self.clean_start_mode = clean_start

        # Set up debugging
        self.debug_mode = debug_mode
        if self.debug_mode:
            self.setup_logging()

        # Initialize UI first
        logging.debug("Initializing UI")
        self.user_interface = Ui(self, IMAGE_CACHE, debug_mode=self.debug_mode)

        # Initialize SquidBrainWindow with config
        logging.debug("Initializing SquidBrainWindow")
        self.brain_window = SquidBrainWindow(None, self.debug_mode, self.config)

        # Important: Hide the window but ensure it's created
        self.brain_window.hide()

        # Store the original window reference to prevent garbage collection
        self._brain_window_ref = self.brain_window

        # Explicitly force creation of all tab contents
        QtCore.QTimer.singleShot(100, self.preload_brain_window_tabs)

        # Continue with normal initialization
        self.brain_window.set_tamagotchi_logic(None)  # Placeholder to ensure initialization
        self.user_interface.squid_brain_window = self.brain_window

        # --- MODIFIED: Centralize PluginManager ---
        # Initialize plugin manager ONCE here
        logging.debug("Initializing PluginManager")
        self.plugin_manager = PluginManager()
        print(f"> Plugin manager initialized: {self.plugin_manager}")

        logging.debug("Loading all plugins via central PluginManager")
        self.plugin_manager.discover_plugins()
        # --- END MODIFICATION ---

        self.specified_personality = specified_personality
        self.neuro_cooldown = neuro_cooldown
        self.squid = None

        # Check for existing save data
        self.save_manager = SaveManager("saves")

        # Track whether we want to show tutorial
        self.show_tutorial = False

        # Initialize the game (this will create TamagotchiLogic and pass the plugin_manager)
        logging.debug("Initializing game")
        self.initialize_game() # TamagotchiLogic gets plugin_manager here

        logging.debug("Setting final tamagotchi_logic references on plugin_manager and brain_window")
        if hasattr(self.plugin_manager, 'set_tamagotchi_logic'):
             self.plugin_manager.set_tamagotchi_logic(self.tamagotchi_logic)
        else:
             self.plugin_manager.tamagotchi_logic = self.tamagotchi_logic

        self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)

        if hasattr(self.user_interface, 'status_bar'):
            self.user_interface.status_bar.update_plugins_status(self.plugin_manager)

        # Connect signals
        self.user_interface.new_game_action.triggered.connect(self.start_new_game)
        self.user_interface.load_action.triggered.connect(self.load_game)
        self.user_interface.save_action.triggered.connect(self.save_game)
        self.user_interface.decorations_action.triggered.connect(self.user_interface.toggle_decoration_window)
        if hasattr(self.user_interface, 'statistics_action'): # Ensure statistics_action exists
            self.user_interface.statistics_action.triggered.connect(self.user_interface.toggle_statistics_window)

        self.user_interface.apply_plugin_menu_registrations(self.plugin_manager)

        desktop = QtWidgets.QApplication.desktop()
        screen_rect = desktop.screenGeometry()
        window_rect = self.geometry()
        center_x = screen_rect.center().x()
        window_x = center_x - (window_rect.width() // 2)
        self.move(window_x - 300, self.y())

        if self.debug_mode:
            print(f"DEBUG MODE ENABLED: Console output is being logged to console.txt")

    def preload_brain_window_tabs(self):
        """Force creation of all tab contents to prevent crashes during tutorial"""
        print("Pre-loading brain window tabs...")
        if not hasattr(self, 'brain_window') or not self.brain_window:
            print("Brain window not initialized, cannot preload")
            return

        try:
            if hasattr(self.brain_window, 'tabs'):
                tab_count = self.brain_window.tabs.count()
                if not hasattr(self, '_preloaded_tabs'):
                    self._preloaded_tabs = []

                original_pos = self.brain_window.pos()
                self.brain_window.move(-10000, -10000)
                self.brain_window.show()

                for i in range(tab_count):
                    self.brain_window.tabs.setCurrentIndex(i)
                    tab_widget = self.brain_window.tabs.widget(i)
                    self._preloaded_tabs.append(tab_widget)
                    QtWidgets.QApplication.processEvents()
                    time.sleep(0.1)

                self.brain_window.tabs.setCurrentIndex(0)
                QtWidgets.QApplication.processEvents()

                self.brain_window.hide()
                self.brain_window.move(original_pos)
                print("Brain window tabs pre-loaded successfully")
            else:
                print("Brain window has no tabs property")
        except Exception as e:
            print(f"Error pre-loading brain window tabs: {e}")
            traceback.print_exc()

    def initialize_game(self):
        """Initialize the game based on whether save data exists"""
        if self.save_manager.save_exists() and self.specified_personality is None:
            print("\x1b[32mExisting save data found and will be loaded\x1b[0m")
            self.squid = Squid(self.user_interface, None, None)
            self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window, plugin_manager_instance=self.plugin_manager)

            self.squid.tamagotchi_logic = self.tamagotchi_logic
            self.user_interface.tamagotchi_logic = self.tamagotchi_logic
            if hasattr(self.brain_window, 'set_tamagotchi_logic'):
                self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)
            self.create_squid_from_save_data()
        else:
            print("\x1b[92m--------------  STARTING A NEW SIMULATION --------------\x1b[0m")
            self.create_new_game(self.specified_personality)
            self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window, plugin_manager_instance=self.plugin_manager)

            self.squid.tamagotchi_logic = self.tamagotchi_logic
            self.user_interface.tamagotchi_logic = self.tamagotchi_logic
            if hasattr(self.brain_window, 'set_tamagotchi_logic'):
                self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)

            if not self.save_manager.save_exists() and not self.clean_start_mode: # <--- ADDED condition for clean_start_mode
                QtCore.QTimer.singleShot(500, self.delayed_tutorial_check)
            elif self.clean_start_mode:
                 print("Clean start mode: Skipping tutorial and initial window openings.")

        self._initialization_complete = True

    def delayed_tutorial_check(self):
        QtWidgets.QApplication.processEvents()
        self.check_tutorial_preference()
        if self.show_tutorial:
            pass
        elif not self.clean_start_mode: # <--- ADDED condition for clean_start_mode
            QtCore.QTimer.singleShot(500, self.open_initial_windows)

    def check_tutorial_preference(self):
        if self.save_manager.save_exists() or self.clean_start_mode: # <--- ADDED condition for clean_start_mode
            self.show_tutorial = False
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Startup",
            "Show tutorial?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        self.show_tutorial = (reply == QtWidgets.QMessageBox.Yes)

    def position_and_show_decoration_window(self):
        if hasattr(self.user_interface, 'decoration_window') and self.user_interface.decoration_window:
            screen_geometry = QtWidgets.QApplication.desktop().availableGeometry()
            decoration_window = self.user_interface.decoration_window
            decoration_window.move(
                screen_geometry.right() - decoration_window.width(),
                screen_geometry.bottom() - decoration_window.height() - 100
            )
            decoration_window.show()

    def setup_logging(self):
        root_logger = logging.getLogger()
        if self.debug_mode:
            root_logger.setLevel(logging.DEBUG)

        console_txt_handler_exists = any(isinstance(h, logging.FileHandler) and 'console.txt' in getattr(h, 'baseFilename', '') for h in root_logger.handlers)

        if not console_txt_handler_exists:
            fh = logging.FileHandler('console.txt', mode='w')
            fh.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
            fh.setFormatter(formatter)
            root_logger.addHandler(fh)

        if not isinstance(sys.stdout, TeeStream) and self.debug_mode:
            try:
                console_file_for_tee = open('console.txt', 'w')
                sys.stdout = TeeStream(sys.stdout, console_file_for_tee)
                sys.stderr = TeeStream(sys.stderr, open('console.txt', 'a'))
            except Exception as e:
                print(f"Error setting up TeeStream for console.txt: {e}")

    def create_new_game(self, personality=None):
        if self._initialization_complete and hasattr(self, 'squid') and self.squid is not None:
            print("Skipping duplicate game creation - squid already exists")
            return

        personality = personality or random.choice(list(Personality))
        self.squid = Squid(
            user_interface=self.user_interface,
            tamagotchi_logic=None,
            personality=personality,
            neuro_cooldown=self.neuro_cooldown
        )
        print(f"    \n>> Generated squid personality: {self.squid.personality.value}\n    ")
        if self.neuro_cooldown:
            print(f"\x1b[43m Neurogenesis cooldown:\033[0m {self.neuro_cooldown}")
        self.squid.memory_manager.clear_all_memories()
        if not self.clean_start_mode: # <--- ADDED condition
            self.show_splash_screen()

    def start_new_game(self):
        self.clear_all_scene_objects()
        self._initialization_complete = False
        self.create_new_game(self.specified_personality)
        self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window, plugin_manager_instance=self.plugin_manager)
        self.squid.tamagotchi_logic = self.tamagotchi_logic
        self.user_interface.tamagotchi_logic = self.tamagotchi_logic
        if hasattr(self.brain_window, 'set_tamagotchi_logic'):
            self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)
        if hasattr(self.plugin_manager, 'set_tamagotchi_logic'):
            self.plugin_manager.set_tamagotchi_logic(self.tamagotchi_logic)
        else:
            self.plugin_manager.tamagotchi_logic = self.tamagotchi_logic
        self.brain_window.update_personality_display(self.squid.personality)
        self.tamagotchi_logic.set_simulation_speed(0)
        if not self.clean_start_mode: # <--- ADDED condition
            self.show_splash_screen()
        else: # <--- If clean start, manually start simulation parts
            self.start_simulation()
        self._initialization_complete = True

    def clear_all_scene_objects(self):
        if not hasattr(self, 'user_interface') or not self.user_interface: return
        if not hasattr(self, 'squid') or not self.squid or not hasattr(self.squid, 'squid_item'): return
        try:
            main_squid_item = self.squid.squid_item
            all_items = self.user_interface.scene.items()
            found_count = 0
            for item in all_items:
                if item == main_squid_item: continue
                if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    if (hasattr(item, 'pixmap') and item.pixmap() and
                        main_squid_item.pixmap() and
                        item.pixmap().width() == main_squid_item.pixmap().width() and
                        item.pixmap().height() == main_squid_item.pixmap().height()):
                        print(f"Found potential duplicate squid item - removing")
                        self.user_interface.scene.removeItem(item)
                        found_count += 1
            if found_count > 0:
                print(f"Cleaned up {found_count} duplicate squid items")
                self.user_interface.scene.update()
        except Exception as e:
            print(f"Error during cleanup_duplicate_squids: {str(e)}")

    def create_squid_from_save_data(self):
        save_data = self.save_manager.load_game()
        if save_data and 'game_state' in save_data and 'squid' in save_data['game_state']:
            squid_data = save_data['game_state']['squid']
            self.squid.load_state(squid_data)
            if hasattr(self.user_interface, 'show_pause_message'):
                try:
                    self.user_interface.show_pause_message(True)
                except Exception as e:
                    print(f"Warning: Failed to show pause message: {e}")
            self.tamagotchi_logic.start_autosave()

            # <--- MODIFIED: Check clean_start_mode before opening initial windows --->
            if not self.clean_start_mode:
                QtCore.QTimer.singleShot(1000, self.open_initial_windows)
            self.tamagotchi_logic.set_simulation_speed(0)
        else:
            print("No existing save data found - Starting new simulation")
            self.create_new_game()

    def load_game(self):
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            self.tamagotchi_logic.load_game()
        else:
            print("Cannot load game: TamagotchiLogic not initialized.")

    def save_game(self):
        if self.squid and self.tamagotchi_logic:
            self.tamagotchi_logic.save_game(self.squid, self.tamagotchi_logic)
        else:
            print("Cannot save game: Squid or TamagotchiLogic not initialized.")

    def update_brain_window(self):
        if self.squid and self.brain_window and self.brain_window.isVisible():
            novelty_exp = 0
            sust_stress = 0
            rec_rewards = 0
            if hasattr(self.tamagotchi_logic, 'neurogenesis_triggers'):
                novelty_exp = self.tamagotchi_logic.neurogenesis_triggers.get('novel_objects', 0)
                sust_stress = self.tamagotchi_logic.neurogenesis_triggers.get('high_stress_cycles', 0)
                rec_rewards = self.tamagotchi_logic.neurogenesis_triggers.get('positive_outcomes', 0)
            current_state = {
                "hunger": self.squid.hunger, "happiness": self.squid.happiness,
                "cleanliness": self.squid.cleanliness, "sleepiness": self.squid.sleepiness,
                "satisfaction": self.squid.satisfaction, "anxiety": self.squid.anxiety,
                "curiosity": self.squid.curiosity, "is_sick": self.squid.is_sick,
                "is_sleeping": self.squid.is_sleeping, "pursuing_food": self.squid.pursuing_food,
                "direction": self.squid.squid_direction, "position": (self.squid.squid_x, self.squid.squid_y),
                "personality": self.squid.personality.value, "novelty_exposure": novelty_exp,
                "sustained_stress": sust_stress, "recent_rewards": rec_rewards
            }
            self.brain_window.update_brain(current_state)

    def show_splash_screen(self):
        self.splash = SplashScreen(self)
        self.splash.finished.connect(self.start_simulation)
        self.splash.second_frame.connect(self.show_hatching_notification)
        self.splash.show()
        QtCore.QTimer.singleShot(2000, self.splash.start_animation)

    def start_simulation(self):
        print("  ")
        self.cleanup_duplicate_squids()
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            self.tamagotchi_logic.set_simulation_speed(1)
            self.tamagotchi_logic.start_autosave()
        else:
            print("Error: TamagotchiLogic not initialized before starting simulation.")
            return

        # <--- MODIFIED: Check clean_start_mode and show_tutorial --->
        if self.show_tutorial and not self.clean_start_mode:
            QtCore.QTimer.singleShot(1000, self.user_interface.show_tutorial_overlay)
        elif not self.clean_start_mode: # Only open if not clean start AND not showing tutorial (tutorial handles its own window openings)
            QtCore.QTimer.singleShot(500, self.open_initial_windows)

    def show_tutorial_overlay(self):
        self.cleanup_duplicate_squids()
        if hasattr(self, 'user_interface') and self.user_interface:
            self.user_interface.show_tutorial_overlay()

    def show_hatching_notification(self):
        if hasattr(self, 'user_interface') and self.user_interface:
            self.user_interface.show_message("Squid is hatching!")
        else:
            print("UI not available for hatching notification.")

    def open_initial_windows(self): # <--- MODIFIED
        """Open brain window, decorations window, and statistics window unless in clean_start_mode."""
        if self.clean_start_mode: # <--- ADDED check
            print("Clean start mode: Skipping automatic window opening.")
            return

        if hasattr(self, 'brain_window') and self.brain_window:
            self.brain_window.show()
            if hasattr(self.user_interface, 'brain_action'):
                self.user_interface.brain_action.setChecked(True)

        if hasattr(self.user_interface, 'decoration_window') and self.user_interface.decoration_window:
            self.position_and_show_decoration_window()
            if hasattr(self.user_interface, 'decorations_action'):
                self.user_interface.decorations_action.setChecked(True)

        # Open Statistics Window
        if hasattr(self.user_interface, 'statistics_window') and self.user_interface.statistics_window:
            self.user_interface.statistics_window.show()
            if hasattr(self.user_interface, 'statistics_action'):
                self.user_interface.statistics_action.setChecked(True)

    def cleanup_duplicate_squids(self):
        if not hasattr(self, 'user_interface') or not self.user_interface: return
        if not hasattr(self, 'squid') or not self.squid or not hasattr(self.squid, 'squid_item'): return
        try:
            main_squid_item = self.squid.squid_item
            all_items = self.user_interface.scene.items()
            found_count = 0
            for item in all_items:
                if item == main_squid_item: continue
                if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    if (hasattr(item, 'pixmap') and item.pixmap() and
                        main_squid_item.pixmap() and
                        item.pixmap().width() == main_squid_item.pixmap().width() and
                        item.pixmap().height() == main_squid_item.pixmap().height()):
                        print(f"Found potential duplicate squid item - removing")
                        self.user_interface.scene.removeItem(item)
                        found_count += 1
            if found_count > 0:
                print(f"Cleaned up {found_count} duplicate squid items")
                self.user_interface.scene.update()
        except Exception as e:
            print(f"Error during cleanup_duplicate_squids: {str(e)}")

    def initialize_multiplayer_manually(self):
        print("WARNING: initialize_multiplayer_manually called - this may indicate an issue with plugin loading.")
        if not self.plugin_manager:
            print("ERROR: Central PluginManager not found for manual multiplayer init.")
            return False
        try:
            kwargs_for_mp_enable = {
                 'tamagotchi_logic': self.tamagotchi_logic,
                 'squid': self.squid,
                 'user_interface': self.user_interface,
                 'plugin_manager': self.plugin_manager
            }
            multiplayer_plugin_instance = self.plugin_manager.plugins.get('multiplayer', {}).get('instance')
            if multiplayer_plugin_instance:
                 if hasattr(multiplayer_plugin_instance, 'enable'):
                     multiplayer_plugin_instance.enable(**kwargs_for_mp_enable)
                     print("Attempted to manually enable multiplayer plugin instance.")
                     self.user_interface.apply_plugin_menu_registrations(self.plugin_manager)
                     return True
            print("Could not manually enable multiplayer: instance not found or no enable method.")
            return False
        except Exception as e:
            print(f"Error in manual multiplayer initialization: {e}")
            traceback.print_exc()
            return False

def main():
    sys.excepthook = global_exception_handler

    parser = argparse.ArgumentParser(description="Dosidicus digital squid with a neural network")
    parser.add_argument('-p', '--personality', type=str,
                       choices=[p.value for p in Personality],
                       help='Specify squid personality')
    parser.add_argument('-d', '--debug', action='store_true',
                       help='Enable debug mode with console logging')
    parser.add_argument('-nc', '--neurocooldown', type=int,
                       help='Set neurogenesis cooldown in seconds')
    parser.add_argument('-c', '--clean', action='store_true',
                       help='Start with only the main window, no auto-opened tools.')
    args = parser.parse_args()

    print(f"Personality: {args.personality}")
    print(f"Debug mode: {args.debug}")
    print(f"Neuro Cooldown: {args.neurocooldown or 'will be loaded from config'}")
    print(f"Clean Start: {args.clean}")

    app = QtWidgets.QApplication(sys.argv)

    try:
        personality_enum_val = Personality(args.personality) if args.personality else None
        main_window = MainWindow(
            specified_personality=personality_enum_val,
            debug_mode=args.debug,
            neuro_cooldown=args.neurocooldown,
            clean_start=args.clean # <--- PASS new argument
        )
        main_window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("Fatal error in main")
        QtWidgets.QMessageBox.critical(None, "Error",
                                     f"Critical error: {str(e)}\nSee dosidicus_log.txt for details.")

if __name__ == '__main__':
    main()
