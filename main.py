# Dosidicus - a digital pet with a neural network
# main.py Entrypoint 

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
from src.brain_worker import BrainWorker

os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.*=false;qt.style.*=false'
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    filename='logs/dosidicus_log.txt',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

class TimedMessageBox(QtWidgets.QDialog):
    """A message box that auto-closes after a timeout with a default choice"""
    def __init__(self, parent, title, message, timeout_seconds=5):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.timeout_seconds = timeout_seconds
        self.remaining_seconds = timeout_seconds
        self.result_value = QtWidgets.QMessageBox.No  # Default to No
        
        # Setup UI
        layout = QtWidgets.QVBoxLayout()
        
        self.message_label = QtWidgets.QLabel(message)
        layout.addWidget(self.message_label)
        
        self.timer_label = QtWidgets.QLabel(f"(Auto-declining in {self.remaining_seconds}s)")
        self.timer_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.timer_label)
        
        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Yes | QtWidgets.QDialogButtonBox.No
        )
        button_box.accepted.connect(self.accept_yes)
        button_box.rejected.connect(self.reject_no)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
        
        # Setup timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)  # Update every second


        
    def update_countdown(self):
        """Update the countdown and auto-close when time runs out"""
        self.remaining_seconds -= 1
        self.timer_label.setText(f"(Auto-declining in {self.remaining_seconds}s)")
        
        if self.remaining_seconds <= 0:
            self.timer.stop()
            self.reject_no()  # Auto-close with No
    
    def accept_yes(self):
        """User clicked Yes"""
        self.timer.stop()
        self.result_value = QtWidgets.QMessageBox.Yes
        self.accept()
    
    def reject_no(self):
        """User clicked No or timeout occurred"""
        self.timer.stop()
        self.result_value = QtWidgets.QMessageBox.No
        self.reject()
    
    def get_result(self):
        """Get the result after dialog closes"""
        return self.result_value

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, specified_personality=None, debug_mode=False, neuro_cooldown=None):
        super().__init__()
        
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

        # ===== PERFORMANCE FIX: Single BrainWorker managed by brain_tool =====
        # Don't create another worker here - SquidBrainWindow creates and shares it
        # Access via self.brain_window.brain_worker if needed
        self.brain_worker = None
        print("ℹ️ BrainWorker managed by SquidBrainWindow")
        
        # Initialize the game
        logging.debug("Initializing game")
        self.initialize_game()
        
        # Now that tamagotchi_logic is created, set it in plugin_manager and brain_window
        logging.debug("Setting tamagotchi_logic references")
        self.plugin_manager.tamagotchi_logic = self.tamagotchi_logic
        self.tamagotchi_logic.plugin_manager = self.plugin_manager
        self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)

        # New in 2.4.5.0 : Create a unique personality starter neuron
        squid = self.tamagotchi_logic.squid
        brain_widget = self.brain_window.brain_widget
        if (squid and squid.personality and
            brain_widget and hasattr(brain_widget, 'enhanced_neurogenesis')):

            if not squid._has_personality_starter_neuron():
                neuron = brain_widget.enhanced_neurogenesis.create_personality_starter_neuron(
                    squid.personality.value,
                    brain_widget.state
                )
                if neuron:
                    print(f"🧬 Personality starter neuron created: {neuron}")
        
        # Load and initialize plugins after core components
        logging.debug("Loading plugins")
        plugin_results = self.plugin_manager.load_all_plugins()
        
        # Setup plugins with tamagotchi_logic reference
        for plugin_name, plugin_data in self.plugin_manager.plugins.items():
            instance = plugin_data.get('instance')
            if instance and hasattr(instance, 'setup') and not plugin_data.get('is_setup', False):
                try:
                    instance.setup(self.plugin_manager, self.tamagotchi_logic)
                    plugin_data['is_setup'] = True
                except Exception as e:
                    print(f"Error setting up plugin {plugin_name}: {e}")
        
        # CRITICAL FIX: Re-load achievement data since plugin instances were replaced
        # during load_all_plugins(), discarding any data loaded earlier
        if self.save_manager.save_exists():
            save_data = self.save_manager.load_game()
            if save_data and 'achievements' in save_data:
                self._restore_achievements_data(save_data['achievements'])
        
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
            print("⚠️  Brain window not initialized, cannot preload")
            return
            
        try:
            # Force the window to process events and initialize all tabs
            if hasattr(self.brain_window, 'tabs'):
                # Visit each tab to ensure it's loaded
                tab_count = self.brain_window.tabs.count()
                
                # Initialize tabs array to prevent garbage collection
                if not hasattr(self, '_preloaded_tabs'):
                    self._preloaded_tabs = []
                
                # Remember if window was visible before we started
                was_visible = self.brain_window.isVisible()
                #print(f"📋 Brain window was_visible before preload: {was_visible}")
                    
                # Temporarily show the window off-screen to force loading
                original_pos = self.brain_window.pos()
                self.brain_window.move(-10000, -10000)  # Move off-screen
                self.brain_window.show()
                
                # Force each tab to be displayed at least once
                for i in range(tab_count):
                    self.brain_window.tabs.setCurrentIndex(i)
                    QtWidgets.QApplication.processEvents()
                    
                    # Get and store references to tab widgets
                    widget = self.brain_window.tabs.widget(i)
                    if widget:
                        self._preloaded_tabs.append(widget)
                        #print(f"  ✓ Preloaded tab {i}: {self.brain_window.tabs.tabText(i)}")
                
                # Return to first tab (Network/Brain tab)
                self.brain_window.tabs.setCurrentIndex(0)
                QtWidgets.QApplication.processEvents()
                #print(f"📋 Reset to first tab: {self.brain_window.tabs.tabText(0)}")
                
                # Restore original position
                self.brain_window.move(original_pos)
                
                # Only hide if it wasn't visible before (don't hide if user is viewing it)
                if not was_visible:
                    self.brain_window.hide()
                    print("📋 Brain window hidden after preload (was not visible before)")
                else:
                    print("📋 Brain window kept visible after preload (was visible before)")
                
                print(f"✅ Successfully preloaded {len(self._preloaded_tabs)} tabs")
        except Exception as e:
            print(f"❌ Error preloading tabs: {e}")
            import traceback
            traceback.print_exc()

    def setup_logging(self):
        """Set up console logging to file"""
        if not hasattr(sys, '_original_stdout'):
            sys._original_stdout = sys.stdout
            sys._original_stderr = sys.stderr
            
        console_log = open('console.txt', 'w', encoding='utf-8')
        sys.stdout = TeeStream(sys._original_stdout, console_log)
        sys.stderr = TeeStream(sys._original_stderr, console_log)

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
            self.load_game()

            # Force immediate statistics update to ensure score displays correctly
            if hasattr(self.tamagotchi_logic, 'statistics_window'):
                self.tamagotchi_logic.statistics_window.update_statistics()

            # ------------------------------------------------------------------
            #  NEW: reveal all neurons with the same fast animation used on
            #       first-run, so saved-game startups also get the fade-in effect.
            # ------------------------------------------------------------------
            brain_widget = self.brain_window.brain_widget

            # -- make every neuron visible -------------------------------------
            # core neurons
            for name in brain_widget.original_neurons:
                brain_widget.visible_neurons.add(name)
            # neurogenesis neurons
            if hasattr(brain_widget, 'neurogenesis_data'):
                for name in brain_widget.neurogenesis_data.get('new_neurons_details', {}):
                    brain_widget.visible_neurons.add(name)

            # -- animate them (0.5 s apart) ------------------------------------
            core = brain_widget.original_neurons
            for idx, name in enumerate(core):
                QtCore.QTimer.singleShot(idx * 500, lambda n=name: brain_widget.reveal_neuron(n))

            # -- finally, show window and check menu item ----------------------
            self.brain_window.show()
            self.user_interface.brain_action.setChecked(True)
        else:
            print("\x1b[92m--------------  STARTING A NEW SIMULATION --------------\x1b[0m")
            
            # Create the game immediately
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
            # Just open initial windows if no tutorial
            QtCore.QTimer.singleShot(500, self.open_initial_windows)

    def create_new_game(self, specified_personality=None):
        """Create a new game instance"""
        # Delete any existing save to ensure clean start
        if self.save_manager.save_exists():
            self.save_manager.delete_save()
        
        # Choose personality randomly if not specified
        if specified_personality is None:
            personality = random.choice(list(Personality))
        else:
            personality = specified_personality
        
        # Create new squid with chosen personality
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

    def check_tutorial_preference(self):
        """Show a dialog asking if the user wants to see the tutorial with 5-second timeout"""
        # Don't ask about tutorial if save data exists
        if self.save_manager.save_exists():
            self.show_tutorial = False
            return
            
        # Show timed dialog
        dialog = TimedMessageBox(
            self,
            "Startup",
            "Show tutorial?",
            timeout_seconds=5
        )
        dialog.exec_()
        
        # Set flag based on user's choice (defaults to No if timeout)
        self.show_tutorial = (dialog.get_result() == QtWidgets.QMessageBox.Yes)
    
    def position_and_show_decoration_window(self):
        """Position the decoration window in the bottom right and show it"""
        if hasattr(self.user_interface, 'decoration_window') and self.user_interface.decoration_window:
            # Get screen geometry
            screen_geometry = QtWidgets.QApplication.desktop().availableGeometry()
            
            # Position window in bottom right
            decoration_window = self.user_interface.decoration_window
            decoration_window.move(
                screen_geometry.right() - decoration_window.width() - 20,
                screen_geometry.bottom() - decoration_window.height() - 20
            )
            decoration_window.show()
            self.user_interface.decorations_action.setChecked(True)

    def start_new_game(self):
        """Start a new game, deleting any existing save"""
        # First, ask for confirmation with a timed dialog
        confirm_dialog = TimedMessageBox(
            self,
            "Confirm New Game",
            "Are you sure you want to start a new game? This will delete all current progress and save data.",
            timeout_seconds=10
        )
        confirm_dialog.exec_()
        
        # If user declined or let it timeout, abort
        if confirm_dialog.get_result() != QtWidgets.QMessageBox.Yes:
            print("New game cancelled by user")
            return
        
        print("Starting new game...")
        
        # Ask about tutorial
        tutorial_dialog = TimedMessageBox(
            self,
            "Tutorial",
            "Would you like to see the tutorial?",
            timeout_seconds=5
        )
        tutorial_dialog.exec_()
        self.show_tutorial = (tutorial_dialog.get_result() == QtWidgets.QMessageBox.Yes)
        
        # Stop current simulation if running
        if hasattr(self, 'tamagotchi_logic'):
            self.tamagotchi_logic.stop()
            # Stop autosave timer if it exists
            if hasattr(self.tamagotchi_logic, 'autosave_timer'):
                self.tamagotchi_logic.autosave_timer.stop()
        
        # Delete all save files (both autosave and manual save)
        if self.save_manager.save_exists():
            self.save_manager.delete_save(is_autosave=True)  # Delete autosave
            self.save_manager.delete_save(is_autosave=False)  # Delete manual save
            print("All save files deleted")
        
        # Clear memory files
        memory_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '_memory')
        if os.path.exists(memory_dir):
            import shutil
            shutil.rmtree(memory_dir)
            print("Memory directory cleared")
        
        # Clear all neurons and state from brain window
        if hasattr(self, 'brain_window') and hasattr(self.brain_window, 'brain_widget'):
            brain_widget = self.brain_window.brain_widget
            
            # Clear visible neurons
            brain_widget.visible_neurons = set()
            
            # Clear neurogenesis data
            if hasattr(brain_widget, 'neurogenesis_data'):
                brain_widget.neurogenesis_data = {
                    'new_neurons': [],
                    'new_neurons_details': {},
                    'new_synapses': []
                }
            
            # Clear enhanced neurogenesis tracking
            if hasattr(brain_widget, 'enhanced_neurogenesis'):
                brain_widget.enhanced_neurogenesis.reset_all_state()
            
            # Reset brain widget state
            if hasattr(brain_widget, 'state'):
                brain_widget.state = brain_widget.create_initial_state()
            
            # Clear hebbian learning state
            if hasattr(brain_widget, 'hebbian'):
                brain_widget.hebbian.reset()
            
            print("Brain state cleared")
        
        # Clear all decorations and items from the scene
        if hasattr(self, 'user_interface') and hasattr(self.user_interface, 'scene'):
            # Remove all items except the background (if it exists)
            items_to_remove = []
            background_item = getattr(self.user_interface, 'background', None)
            
            for item in self.user_interface.scene.items():
                # Keep the background (if it exists) and remove everything else
                if background_item is None or item != background_item:
                    items_to_remove.append(item)
            
            for item in items_to_remove:
                self.user_interface.scene.removeItem(item)
            
            # Clear decoration tracking
            if hasattr(self.user_interface, 'awarded_decorations'):
                self.user_interface.awarded_decorations = set()
            
            print("Scene cleared")
        
        # Create new game (creates squid but not tamagotchi_logic)
        self.create_new_game(self.specified_personality)
        
        # Create TamagotchiLogic
        self.tamagotchi_logic = TamagotchiLogic(self.user_interface, self.squid, self.brain_window)
        
        # Update references
        self.squid.tamagotchi_logic = self.tamagotchi_logic
        self.user_interface.tamagotchi_logic = self.tamagotchi_logic
        self.brain_window.tamagotchi_logic = self.tamagotchi_logic
        if hasattr(self.brain_window, 'set_tamagotchi_logic'):
            self.brain_window.set_tamagotchi_logic(self.tamagotchi_logic)
        
        self.plugin_manager.tamagotchi_logic = self.tamagotchi_logic
        self.tamagotchi_logic.plugin_manager = self.plugin_manager
        
        # Create personality starter neuron if needed
        squid = self.tamagotchi_logic.squid
        brain_widget = self.brain_window.brain_widget
        if (squid and squid.personality and
            brain_widget and hasattr(brain_widget, 'enhanced_neurogenesis')):
            if not squid._has_personality_starter_neuron():
                neuron = brain_widget.enhanced_neurogenesis.create_personality_starter_neuron(
                    squid.personality.value,
                    brain_widget.state
                )
                if neuron:
                    print(f"🧬 Personality starter neuron created: {neuron}")
        
        # Reload plugins to ensure they get the new tamagotchi_logic
        self.plugin_manager.reload_all_plugins()
        
        print("New game created successfully!")

    def load_game(self):
        """Load game with selection dialog for multiple saves"""
        if not hasattr(self, 'tamagotchi_logic') or not self.tamagotchi_logic:
            print("⚠️  Cannot load: TamagotchiLogic not initialized")
            return False
        
        success = self.tamagotchi_logic.load_game_with_selection()
        
        if success:
            # Refresh statistics display
            if hasattr(self.tamagotchi_logic, 'statistics_window'):
                self.tamagotchi_logic.statistics_window.update_statistics()
        
        return success

    def save_game(self):
        """Delegate to tamagotchi_logic"""
        if self.squid and self.tamagotchi_logic:
            self.tamagotchi_logic.save_game()

    def _restore_achievements_data(self, achievements_data):
        """Restore achievement data to the achievements plugin after plugin reload.
        
        This is needed because plugin instances get replaced during initialization,
        discarding any previously loaded save data.
        """
        if not achievements_data:
            return
        try:
            if 'achievements' in self.plugin_manager.plugins:
                plugin_info = self.plugin_manager.plugins['achievements']
                instance = plugin_info.get('instance')
                if instance and hasattr(instance, 'load_save_data'):
                    instance.load_save_data(achievements_data)
                    unlocked_count = len(achievements_data.get('unlocked', {}))
                    print(f"✓ Restored {unlocked_count} achievements")
        except Exception as e:
            print(f"[Warning] Could not restore achievements: {e}")

    def closeEvent(self, event):
        """Handle window close event"""
        # Save game before closing
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            self.save_game()
        
        # Stop the tamagotchi logic if it has a stop method
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'stop'):
                self.tamagotchi_logic.stop()
            # Stop the timer if it exists
            elif hasattr(self.tamagotchi_logic, 'timer') and self.tamagotchi_logic.timer:
                self.tamagotchi_logic.timer.stop()
        
        # Close brain window
        if hasattr(self, 'brain_window') and self.brain_window:
            self.brain_window.close()
        
        event.accept()

    def show_splash_screen(self):
        """Display splash screen animation with synchronized neuron reveal"""
        self.splash = SplashScreen(self)
        self.splash.finished.connect(self.start_simulation)
        self.splash.finished.connect(lambda: self.tamagotchi_logic.statistics_window.award(1000))
        self.splash.second_frame.connect(self.show_hatching_notification)

        # NEW: award 1000 points the instant the splash ends
        self.splash.finished.connect(
            lambda: self.tamagotchi_logic.statistics_window.award(1000)
        )

       # After splash ends, wait 3 s then show the normal feeding hint
        self.splash.finished.connect(lambda: QtCore.QTimer.singleShot(3000, self.show_feeding_hint))

        # Check if this is a brand new game (no save exists)
        is_new_game = not self.save_manager.save_exists()
        print(f"🎮 show_splash_screen: is_new_game={is_new_game}, save_exists={self.save_manager.save_exists()}")

        if is_new_game:
            # Ensure brain widget starts empty
            if hasattr(self.brain_window, 'brain_widget') and hasattr(self.brain_window.brain_widget, 'visible_neurons'):
                self.brain_window.brain_widget.visible_neurons = set()
            
            # Show brain window first
            self.brain_window.show()
            self.user_interface.brain_action.setChecked(True)
            
            # Force immediate processing to ensure brain window is painted
            QtWidgets.QApplication.processEvents()
            
            # Give the brain window time to fully render (longer delay)
            QtCore.QTimer.singleShot(1500, lambda: self._start_splash_with_reveals())
        else:
            # For loaded games, show brain window with all neurons visible
            if hasattr(self.brain_window, 'brain_widget') and hasattr(self.brain_window.brain_widget, 'visible_neurons'):
                brain_widget = self.brain_window.brain_widget
                # Add all core neurons to visible set
                for neuron_name in brain_widget.original_neurons:
                    brain_widget.visible_neurons.add(neuron_name)
                
                # Also add any neurogenesis neurons that exist
                if hasattr(brain_widget, 'neurogenesis_data') and 'new_neurons_details' in brain_widget.neurogenesis_data:
                    for neuron_name in brain_widget.neurogenesis_data['new_neurons_details'].keys():
                        brain_widget.visible_neurons.add(neuron_name)
            
            # Show brain window immediately for loaded games
            self.brain_window.show()
            self.user_interface.brain_action.setChecked(True)
            
            # Force immediate processing to ensure brain window is painted
            QtWidgets.QApplication.processEvents()
            
            # Show splash normally (no animated reveals needed for loaded games)
            self.splash.show()
            QtCore.QTimer.singleShot(1000, self.splash.start_animation)


    def show_feeding_hint(self):
        """Use the same strip as every other message."""
        self.user_interface.show_message("Use the Actions menu to feed the squid")
    
    def _start_splash_with_reveals(self):
        """Start splash screen with neuron reveal synchronization (called after brain window is ready)"""
        print("🥚 A squid is hatching...")
        
        # Connect frame changes to neuron reveals
        self.splash.frame_changed.connect(self._reveal_neuron_for_frame)
        
        # Show and start the splash screen animation
        self.splash.show()
        QtCore.QTimer.singleShot(500, self.splash.start_animation)  # Small delay for splash to show

    def _reveal_neuron_for_frame(self, frame_index):
        """Reveal core neurons in sequence with animation frames"""
        if not hasattr(self.brain_window, 'brain_widget'):
            return
            
        brain_widget = self.brain_window.brain_widget
        core_neurons = brain_widget.original_neurons
        
        # Distribution: 1-2 neurons per frame to reveal all 7 core neurons quickly
        reveal_map = {
            0: [0],       # First frame: reveal hunger
            1: [1],       # Second frame: reveal happiness  
            2: [2],       # Third frame: reveal cleanliness
            3: [3],       # Fourth frame: reveal sleepiness
            4: [4],    # Fifth frame: reveal satisfaction & anxiety
            5: [5, 6]        # Sixth frame: reveal curiosity
        }
        
        # Reveal mapped neurons for this frame
        for neuron_idx in reveal_map.get(frame_index, []):
            if neuron_idx < len(core_neurons):
                neuron_name = core_neurons[neuron_idx]
                brain_widget.reveal_neuron(neuron_name)
                #print(f"🧠 Revealed neuron: {neuron_name} (frame {frame_index})")

    def show_hatching_notification(self):
        """Display hatching message"""
        self.user_interface.show_message("Squid is hatching!")

    def start_simulation(self):
        """Begin the simulation - brain window is already visible for new games"""
        self.cleanup_duplicate_squids()
        self.tamagotchi_logic.set_simulation_speed(1)
        self.tamagotchi_logic.start_autosave()

        # Show tutorial if enabled
        if self.show_tutorial:
            QtCore.QTimer.singleShot(1000, self.user_interface.show_tutorial_overlay)
        else:
            # Only open decoration window automatically (brain window already visible for new games)
            QtCore.QTimer.singleShot(500, self.position_and_show_decoration_window)

    def show_tutorial_overlay(self):
        """Delegate to UI layer and ensure no duplicates remain"""
        # First do one more duplicate cleanup
        self.cleanup_duplicate_squids()
        
        # Then show the tutorial via the UI
        if hasattr(self, 'user_interface') and self.user_interface:
            self.user_interface.show_tutorial_overlay()

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