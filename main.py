import time
import sys
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
    def __init__(self, specified_personality=None, debug_mode=False, neuro_cooldown=None, parent=None):
        super().__init__(parent)
        
        # Initialize configuration
        self.config = LearningConfig()
        if neuro_cooldown is not None:
            self.config.neurogenesis['cooldown'] = neuro_cooldown
        
        # Add initialization tracking flag
        self._initialization_complete = False
        
        # Set up debugging
        self.debug_mode = debug_mode
        if self.debug_mode:
            self.setup_logging()
        
        # Initialize UI first
        logging.debug("Initializing UI")
        self.user_interface = Ui(self, debug_mode=self.debug_mode)

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
        
        # Initialize plugin manager after UI and brain window
        logging.debug("Initializing PluginManager")
        self.plugin_manager = PluginManager()
        print(f"> Plugin manager initialized: {self.plugin_manager}")
        
        self.specified_personality = specified_personality
        self.neuro_cooldown = neuro_cooldown
        self.squid = None
        
        # Check for existing save data
        self.save_manager = SaveManager("saves")
        
        # Track whether we want to show tutorial
        self.show_tutorial = False
        
        # Initialize the game
        logging.debug("Initializing game")
        self.initialize_game()
        
        # Now that tamagotchi_logic is created, set it in plugin_manager and brain_window
        logging.debug("Setting tamagotchi_logic references")
        self.plugin_manager.tamagotchi_logic = self.tamagotchi_logic
        self.tamagotchi_logic.plugin_manager = self.plugin_manager
        self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)
        
        # Load and initialize plugins after core components
        logging.debug("Loading plugins")
        plugin_results = self.plugin_manager.load_all_plugins()
        
        # Update status bar with plugin information
        if hasattr(self.user_interface, 'status_bar'):
            self.user_interface.status_bar.update_plugins_status(self.plugin_manager)
        
        # Connect signals
        self.user_interface.new_game_action.triggered.connect(self.start_new_game)
        self.user_interface.load_action.triggered.connect(self.load_game)
        self.user_interface.save_action.triggered.connect(self.save_game)
        self.user_interface.decorations_action.triggered.connect(self.user_interface.toggle_decoration_window)
        
        # Initialize plugin menu - do this AFTER loading plugins
        self.user_interface.apply_plugin_menu_registrations(self.plugin_manager)
    
        # Position window 300 pixels to the left of default position
        desktop = QtWidgets.QApplication.desktop()
        screen_rect = desktop.screenGeometry()
        window_rect = self.geometry()
        center_x = screen_rect.center().x()
        window_x = center_x - (window_rect.width() // 2)  # Default centered X position
        
        # Move 300 pixels to the left
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
            # Force the window to process events and initialize all tabs
            if hasattr(self.brain_window, 'tabs'):
                # Visit each tab to ensure it's loaded
                tab_count = self.brain_window.tabs.count()
                #print(f"Pre-loading {tab_count} tabs...")
                
                # Initialize tabs array to prevent garbage collection
                if not hasattr(self, '_preloaded_tabs'):
                    self._preloaded_tabs = []
                    
                # Temporarily show the window off-screen to force loading
                original_pos = self.brain_window.pos()
                self.brain_window.move(-10000, -10000)  # Move off-screen
                self.brain_window.show()
                
                # Force each tab to be displayed at least once
                for i in range(tab_count):
                    self.brain_window.tabs.setCurrentIndex(i)
                    tab_name = self.brain_window.tabs.tabText(i)
                    #print(f"Pre-loading tab {i}: {tab_name}")
                    
                    # Get the tab widget and reference it to prevent garbage collection
                    tab_widget = self.brain_window.tabs.widget(i)
                    self._preloaded_tabs.append(tab_widget)
                    
                    # Process events to allow rendering
                    QtWidgets.QApplication.processEvents()
                    
                    # Add a small delay between tab changes
                    time.sleep(0.1)
                
                # Return to first tab
                self.brain_window.tabs.setCurrentIndex(0)
                QtWidgets.QApplication.processEvents()
                
                # Hide window again 
                self.brain_window.hide()
                self.brain_window.move(original_pos)
                
                print("Brain window tabs pre-loaded successfully")
            else:
                print("Brain window has no tabs property")
        except Exception as e:
            print(f"Error pre-loading brain window tabs: {e}")
            import traceback
            traceback.print_exc()

    def initialize_game(self):
        """Initialize the game based on whether save data exists"""
        if self.save_manager.save_exists() and self.specified_personality is None:
            print("\x1b[32mExisting save data found and will be loaded\x1b[0m")
            self.squid = Squid(self.user_interface, None, None)
            self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
            
            # Set up connections
            self.squid.tamagotchi_logic = self.tamagotchi_logic
            self.user_interface.tamagotchi_logic = self.tamagotchi_logic
            self.brain_window.tamagotchi_logic = self.tamagotchi_logic
            if hasattr(self.brain_window, 'set_tamagotchi_logic'):
                self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)
            
            # Now load from save data
            self.create_squid_from_save_data()
        else:
            print("\x1b[92m--------------  STARTING A NEW SIMULATION --------------\x1b[0m")
            
            # Create the game but don't check for tutorial yet
            self.create_new_game(self.specified_personality)
            self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
            
            # Connect components
            self.squid.tamagotchi_logic = self.tamagotchi_logic
            self.user_interface.tamagotchi_logic = self.tamagotchi_logic
            self.brain_window.tamagotchi_logic = self.tamagotchi_logic
            if hasattr(self.brain_window, 'set_tamagotchi_logic'):
                self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)
                
            # Schedule tutorial check for AFTER initialization
            if not self.save_manager.save_exists():
                QtCore.QTimer.singleShot(500, self.delayed_tutorial_check)
        
        # Mark initialization as complete
        self._initialization_complete = True

    def delayed_tutorial_check(self):
        """Check if the user wants to see the tutorial after UI is responsive"""
        # Process pending events to ensure UI is responsive
        QtWidgets.QApplication.processEvents()
        
        # Now check tutorial preference
        self.check_tutorial_preference()
        
        # If tutorial was chosen, schedule it for later
        if self.show_tutorial:
            # We'll show tutorial when the game starts
            pass
        else:
            # Just open windows if no tutorial
            QtCore.QTimer.singleShot(500, self.open_initial_windows)

    def check_tutorial_preference(self):
        """Show a dialog asking if the user wants to see the tutorial"""
        # Don't ask about tutorial if save data exists
        if self.save_manager.save_exists():
            self.show_tutorial = False
            return
            
        # Ask user if they want to see the tutorial
        reply = QtWidgets.QMessageBox.question(
            self, 
            "Startup",
            "Show tutorial?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        
        # Set flag based on user's choice
        self.show_tutorial = (reply == QtWidgets.QMessageBox.Yes)
    
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
        # Skip if already initialized
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
        
        print(f"    ")
        print(f">> Generated squid personality: {self.squid.personality.value}")
        print(f"    ")
        if self.neuro_cooldown:
            print(f"\x1b[43m Neurogenesis cooldown:\033[0m {self.neuro_cooldown}")
        
        self.squid.memory_manager.clear_all_memories()
        self.show_splash_screen()

    def start_new_game(self, personality=None):
        """Starts a new game, either from the menu or after the splash screen."""
        if self.tamagotchi_logic:
            self.tamagotchi_logic.autosave_timer.stop()

        if personality is None:
            personality = self.personality_selection_dialog()
            if personality is None:
                return  # User cancelled

        # Re-initialize the UI and logic for a new game
        self.ui = Ui(self, self.debug_mode)
        self.squid = Squid(self.ui, personality=personality, neuro_cooldown=self.neuro_cooldown)
        self.tamagotchi_logic = TamagotchiLogic(self.ui, self.squid, self.brain_window)

        self.ui.set_tamagotchi_logic(self.tamagotchi_logic)
        self.squid.ui = self.ui  # Ensure squid has the latest UI reference

        self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)

        # The existing method gathers all squid data and updates the entire brain window.
        # This is the correct way to propagate the new squid's state.
        self.tamagotchi_logic.update_squid_brain()

        self.tamagotchi_logic.start_autosave()
        self.show()
        self.brain_window.show()

    def clear_all_scene_objects(self):
        """Clear all objects from the scene for a fresh start"""
        if not hasattr(self, 'user_interface') or not self.user_interface:
            return
            
        # Clear decorations (ResizablePixmapItems)
        decorations = [item for item in self.user_interface.scene.items() 
                    if isinstance(item, QtWidgets.QGraphicsItem)]
        for decoration in decorations:
            if not isinstance(decoration, QtWidgets.QGraphicsTextItem) and not decoration == self.squid.squid_item:
                self.user_interface.scene.removeItem(decoration)
        
        # Clear food items if tamagotchi_logic exists
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'food_items'):
            for food_item in self.tamagotchi_logic.food_items:
                self.user_interface.scene.removeItem(food_item)
            self.tamagotchi_logic.food_items.clear()
        
        # Clear poop items if tamagotchi_logic exists
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'poop_items'):
            for poop_item in self.tamagotchi_logic.poop_items:
                self.user_interface.scene.removeItem(poop_item)
            self.tamagotchi_logic.poop_items.clear()
        
        # Force scene update
        self.user_interface.scene.update()
        
        print("All scene objects cleared for new game")

    def create_squid_from_save_data(self):
        """Load squid state from save file"""
        save_data = self.save_manager.load_game()
        if save_data and 'game_state' in save_data and 'squid' in save_data['game_state']:
            squid_data = save_data['game_state']['squid']
            personality = Personality(squid_data['personality'])
            self.squid.load_state(squid_data)
            
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
        
        # Delay starting the animation until window is fully initialized
        QtCore.QTimer.singleShot(2000, self.splash.start_animation)

    def start_simulation(self):
        """Begin the simulation and automatically open brain and decoration windows"""
        print("  ")
        
        # Clean up any duplicate squids
        self.cleanup_duplicate_squids()
        
        self.tamagotchi_logic.set_simulation_speed(1)
        self.tamagotchi_logic.start_autosave()

        # Show tutorial if enabled
        if self.show_tutorial:
            QtCore.QTimer.singleShot(1000, self.user_interface.show_tutorial_overlay)
        else:
            # Only open windows automatically if NOT showing tutorial
            QtCore.QTimer.singleShot(500, self.open_initial_windows)

    def show_tutorial_overlay(self):
        """Delegate to UI layer and ensure no duplicates remain"""
        # First do one more duplicate cleanup
        self.cleanup_duplicate_squids()
        
        # Then show the tutorial via the UI
        if hasattr(self, 'user_interface') and self.user_interface:
            self.user_interface.show_tutorial_overlay()

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

    def cleanup_duplicate_squids(self):
        """Remove any duplicate squid items from the scene"""
        if not hasattr(self, 'user_interface') or not self.user_interface:
            return
            
        if not hasattr(self, 'squid') or not self.squid:
            return
            
        try:
            # Get the reference to our genuine squid item
            main_squid_item = self.squid.squid_item
            
            # Get all items in the scene
            all_items = self.user_interface.scene.items()
            
            # Track how many items we find and remove
            found_count = 0
            
            # Look for graphics items that could be duplicate squids
            for item in all_items:
                # Skip our genuine squid item
                if item == main_squid_item:
                    continue
                    
                # Only check QGraphicsPixmapItems
                if isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    # Check if it has the same pixmap dimensions as our squid
                    if (hasattr(item, 'pixmap') and item.pixmap() and main_squid_item.pixmap() and
                        item.pixmap().width() == main_squid_item.pixmap().width() and
                        item.pixmap().height() == main_squid_item.pixmap().height()):
                        print(f"Found potential duplicate squid item - removing")
                        self.user_interface.scene.removeItem(item)
                        found_count += 1
            
            if found_count > 0:
                print(f"Cleaned up {found_count} duplicate squid items")
                # Force scene update
                self.user_interface.scene.update()
        
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

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