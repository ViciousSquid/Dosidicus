# /plugins/auto_care/main.py

# Import necessary modules from the main application
try:
    from src.tamagotchi_logic import TamagotchiLogic
    from src.squid import Squid
except ImportError:
    TamagotchiLogic = None
    Squid = None

# Attempt to import PyQt5 modules for UI message.
try:
    from PyQt5.QtWidgets import QGraphicsTextItem
    from PyQt5.QtGui import QColor, QFont
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False
    QGraphicsTextItem = None 
    QColor = None
    QFont = None

# ANSI escape codes for console coloring text
ANSI_YELLOW = "\x1b[33m"
ANSI_GREY = "\x1b[90m"
ANSI_RESET = "\x1b[0m"

# --- Plugin Metadata ---
PLUGIN_NAME = "Auto-Care"
PLUGIN_VERSION = "1.0.0" # Updated version for default load behavior change
PLUGIN_AUTHOR = "Rufus Pearce"
PLUGIN_DESCRIPTION = "Automatically feeds and cleans the squid"

# --- Plugin Configuration ---
AUTO_FEED_THRESHOLD = 40
HUNGER_CHECK_INTERVAL_TICKS = 10
TICKS_PER_SECOND_ASSUMPTION = 1
POOP_CHECK_INTERVAL_SECONDS = 120
POOP_CHECK_INTERVAL_TICKS = POOP_CHECK_INTERVAL_SECONDS * TICKS_PER_SECOND_ASSUMPTION

class AutoCarePlugin:
    """
    AutoCarePlugin class.
    Automates squid care and displays an active message on the UI.
    """

    def __init__(self):
        """
        Initialize the plugin instance.
        This method is called by the PluginManager when the plugin is first loaded (typically during
        the plugin's `initialize()` function).
        It should set up the initial state of the plugin's instance variables.
        """
        # --- Core Game References ---
        self.tamagotchi_logic = None
        self.squid = None
        self.plugin_manager = None

        # --- Timers and State Flags ---
        self.poop_check_tick_counter = 0
        self.active_indicator_item = None
        self.active_message_item = None
        
        self.hunger_alert_shown = False
        self.hunger_check_tick_counter = 0
        # self.HUNGER_CHECK_INTERVAL_TICKS = 5 # This is a class/global constant


    def setup(self, plugin_manager, tamagotchi_logic_instance: TamagotchiLogic):
        self.plugin_manager = plugin_manager
        self.tamagotchi_logic = tamagotchi_logic_instance
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid'):
            self.squid = self.tamagotchi_logic.squid
        else:
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - TamagotchiLogic or Squid instance not available during setup.{ANSI_RESET}")

        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Setup in progress. Squid instance: {'Set' if self.squid else 'Not Set'}.{ANSI_RESET}")

        if self.plugin_manager and hasattr(self.plugin_manager, 'subscribe_to_hook'):
            self.plugin_manager.subscribe_to_hook("on_update", PLUGIN_NAME, self.on_game_update)
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Subscribed to 'on_update' hook.{ANSI_RESET}")
        else:
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - PluginManager or subscribe_to_hook method not available. Cannot subscribe to hooks.{ANSI_RESET}")
        
        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Setup complete.{ANSI_RESET}")

    def _display_active_message(self):
        """Helper method to create and display the 'Auto-Care active' indicator."""
        if not PYQT5_AVAILABLE:
            return

        if self.tamagotchi_logic and \
           hasattr(self.tamagotchi_logic, 'user_interface') and self.tamagotchi_logic.user_interface and \
           hasattr(self.tamagotchi_logic.user_interface, 'scene') and self.tamagotchi_logic.user_interface.scene:
            
            # Using self.active_indicator_item consistently
            if self.active_indicator_item and self.active_indicator_item.scene():
                self.active_indicator_item.scene().removeItem(self.active_indicator_item)
            self.active_indicator_item = None 

            if QGraphicsTextItem is None: 
                 print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} QGraphicsTextItem not loaded, cannot display UI indicator.{ANSI_RESET}")
                 return

            self.active_indicator_item = QGraphicsTextItem(f"{PLUGIN_NAME} active") 
            
            if QColor: 
                self.active_indicator_item.setDefaultTextColor(QColor("yellow")) 
            
            self.active_indicator_item.setPos(10, 10)
            self.active_indicator_item.setZValue(200) 
            
            self.tamagotchi_logic.user_interface.scene.addItem(self.active_indicator_item)
        else:
            if PYQT5_AVAILABLE:
                print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} UI components not ready, cannot display UI active message yet.{ANSI_RESET}")

    def _remove_active_message(self):
        """Helper method to remove the 'Auto-Care active' indicator."""
        if not PYQT5_AVAILABLE:
            return

        # Using self.active_indicator_item consistently
        if self.active_indicator_item:
            if self.active_indicator_item.scene():
                self.active_indicator_item.scene().removeItem(self.active_indicator_item)
            self.active_indicator_item = None

    def enable(self):
        """
        Called when the plugin is enabled.
        """
        if not self.tamagotchi_logic and self.plugin_manager:
            if hasattr(self.plugin_manager, 'tamagotchi_logic_instance'):
                 self.setup(self.plugin_manager, self.plugin_manager.tamagotchi_logic_instance)

        self.poop_check_tick_counter = 0
        self.hunger_check_tick_counter = 0
        # Ensure HUNGER_CHECK_INTERVAL_TICKS and POOP_CHECK_INTERVAL_TICKS are defined (e.g. globally or as class attributes)
        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} ENABLED")
        
        # Corrected call to match the likely defined method name
        self._display_active_message() 
        
        return True

    def disable(self):
        """
        Called when the plugin is disabled.
        """
        # Corrected call to match the likely defined method name
        self._remove_active_message() 
        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Disabled.{ANSI_RESET}")
        return True

    def on_game_update(self, tamagotchi_logic: TamagotchiLogic, **kwargs):
        """
        Called every game update tick.
        """
        if PYQT5_AVAILABLE and self.tamagotchi_logic and \
           hasattr(self.tamagotchi_logic, 'user_interface') and self.tamagotchi_logic.user_interface and \
           hasattr(self.tamagotchi_logic.user_interface, 'scene') and self.tamagotchi_logic.user_interface.scene:
            # Using self.active_indicator_item consistently
            if not self.active_indicator_item or \
               (hasattr(self.active_indicator_item, 'scene') and self.active_indicator_item.scene() != self.tamagotchi_logic.user_interface.scene):
                # Corrected call to match the likely defined method name
                self._display_active_message() 
        
        if not self.squid or not self.tamagotchi_logic:
            return

        self.hunger_check_tick_counter += 1
        if self.hunger_check_tick_counter >= HUNGER_CHECK_INTERVAL_TICKS: # Ensure HUNGER_CHECK_INTERVAL_TICKS is defined
            self.hunger_check_tick_counter = 0 

            if self.squid.hunger > AUTO_FEED_THRESHOLD: 
                if not self.hunger_alert_shown: 
                    print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Squid hunger is above threshold ({AUTO_FEED_THRESHOLD}). Attempting to feed.{ANSI_RESET}")
                    self.hunger_alert_shown = True
                self.tamagotchi_logic.feed_squid() 
            else:
                if self.hunger_alert_shown: 
                    self.hunger_alert_shown = False
        
        self.poop_check_tick_counter += 1
        if self.poop_check_tick_counter >= POOP_CHECK_INTERVAL_TICKS: # Ensure POOP_CHECK_INTERVAL_TICKS is defined
            self.poop_check_tick_counter = 0 
            # Ensure POOP_CHECK_INTERVAL_SECONDS is defined for the print message
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Checking for poop every {POOP_CHECK_INTERVAL_SECONDS}s ({POOP_CHECK_INTERVAL_TICKS} ticks)...{ANSI_RESET}")
            if self.tamagotchi_logic.poop_items:
                 print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Poop found! Initiating cleaning.{ANSI_RESET}")
            
            self.tamagotchi_logic.clean_environment()

# --- Plugin Registration Function ---
def initialize(plugin_manager_instance):
    """
    Initializes the Auto-Care plugin and registers it with the plugin manager.
    """
    try:
        plugin_instance = AutoCarePlugin()
        plugin_key = PLUGIN_NAME.lower().replace(" ", "_")

        plugin_manager_instance.plugins[plugin_key] = { # type: ignore
            'instance': plugin_instance,
            'name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'author': PLUGIN_AUTHOR,
            'description': PLUGIN_DESCRIPTION,
            'is_setup': False, 
            'is_enabled_by_default': False
        }
        return True
    except Exception as e:
        print(f"{ANSI_YELLOW}Error during {PLUGIN_NAME}{ANSI_RESET}{ANSI_GREY} plugin initialization: {e}{ANSI_RESET}")
        import traceback
        print(f"{ANSI_YELLOW}Traceback:{ANSI_RESET}{ANSI_GREY} {traceback.format_exc()}{ANSI_RESET}")
        return False