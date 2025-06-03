# /plugins/auto_care/main.py

import os
import random
import time

# Import necessary modules from the main application
try:
    from src.tamagotchi_logic import TamagotchiLogic
    from src.squid import Squid, Personality # Added Personality
    from src.ui import ResizablePixmapItem # To check item types if needed, though not directly used here
except ImportError:
    TamagotchiLogic = None
    Squid = None
    Personality = None
    ResizablePixmapItem = None

# Attempt to import PyQt5 modules for UI message and icons.
try:
    from PyQt5.QtWidgets import QGraphicsTextItem, QGraphicsPixmapItem
    from PyQt5.QtGui import QColor, QFont, QPixmap
    from PyQt5.QtCore import QPointF
    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False
    QGraphicsTextItem = None
    QGraphicsPixmapItem = None
    QColor = None
    QFont = None
    QPixmap = None
    QPointF = None

# ANSI escape codes for console coloring text
ANSI_YELLOW = "\x1b[33m"
ANSI_GREY = "\x1b[90m"
ANSI_RESET = "\x1b[0m"

# --- Plugin Metadata ---
PLUGIN_NAME = "Auto-Care"
PLUGIN_VERSION = "1.1.0" # Updated version for new features
PLUGIN_AUTHOR = "Rufus Pearce"
PLUGIN_DESCRIPTION = "Automatically feeds, cleans the squid, provides tips, and visual cues."

# --- Plugin Configuration ---
AUTO_FEED_THRESHOLD = 50
HUNGER_CHECK_INTERVAL_TICKS = 10 # Roughly 10 seconds if 1 tick/sec
TICKS_PER_SECOND_ASSUMPTION = 1 # This might need to align with actual game loop speed
POOP_CHECK_INTERVAL_SECONDS = 120
POOP_CHECK_INTERVAL_TICKS = POOP_CHECK_INTERVAL_SECONDS * TICKS_PER_SECOND_ASSUMPTION

CARE_TIP_INTERVAL_TICKS = 120 * TICKS_PER_SECOND_ASSUMPTION

# Icon Configuration
ICON_SIZE = 128
ICON_PADDING = 0
FEED_ICON_PATH = os.path.join("images", "icons", "feed.png")
CLEAN_ICON_PATH = os.path.join("images", "icons", "clean.png")


class AutoCarePlugin:
    """
    AutoCarePlugin class.
    Automates squid care, displays messages, tips, and visual cues.
    """

    def __init__(self):
        """
        Initialize the plugin instance.
        """
        # --- Core Game References ---
        self.tamagotchi_logic = None
        self.squid = None
        self.plugin_manager = None
        self.ui = None # For accessing window_width etc.

        # --- Timers and State Flags ---
        self.poop_check_tick_counter = 0
        self.hunger_check_tick_counter = 0
        self.care_tip_tick_counter = 0

        self.hunger_alert_shown_console = False # For console message, to avoid spam

        # --- UI Elements for this plugin ---
        self.active_indicator_item = None # The "Auto-Care active" text

        self.feed_icon_item = None
        self.clean_icon_item = None
        
        self.care_tips = [
            {"text": "Did you know? Regular feeding keeps your squid's hunger low and happiness up!",
             "condition": lambda squid: squid.hunger > 30},
            {"text": "A clean environment is crucial for your squid's health. Don't let poop pile up!",
             "condition": lambda squid: squid.cleanliness < 70},
            {"text": "Your squid seems a bit down. Playing or interacting might cheer it up!",
             "condition": lambda squid: squid.happiness < 40},
            {"text": "High anxiety can stress your squid. Ensure its needs are met to keep it calm.",
             "condition": lambda squid: hasattr(squid, 'anxiety') and squid.anxiety > 60},
            {"text": "A curious squid is an engaged squid! Try adding new decorations.",
             "condition": lambda squid: hasattr(squid, 'curiosity') and squid.curiosity < 50},
            {"text": f"Timid squids appreciate a calm environment. Sudden changes can startle them.",
             "condition": lambda squid: hasattr(squid, 'personality') and squid.personality == Personality.TIMID},
            {"text": f"Adventurous squids love to explore! Make sure they have interesting things to see.",
             "condition": lambda squid: hasattr(squid, 'personality') and squid.personality == Personality.ADVENTUROUS},
            {"text": "If your squid is sick, medicine can help, but it might also make it grumpy for a bit.",
             "condition": lambda squid: squid.is_sick},
            {"text": "Keeping your squid well-fed, clean, and happy contributes to better overall health!",
             "condition": lambda squid: True}, # Generic tip
            {"text": "Check the Brain Window to see how your actions affect the squid's neural network!",
             "condition": lambda squid: random.random() < 0.2} # Randomly shown
        ]
        self.last_tip_shown_time = 0


    def setup(self, plugin_manager, tamagotchi_logic_instance: TamagotchiLogic):
        self.plugin_manager = plugin_manager
        self.tamagotchi_logic = tamagotchi_logic_instance
        if self.tamagotchi_logic:
            self.squid = getattr(self.tamagotchi_logic, 'squid', None)
            self.ui = getattr(self.tamagotchi_logic, 'user_interface', None)
        else:
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - TamagotchiLogic instance not available during setup.{ANSI_RESET}")
            return

        if not self.squid:
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - Squid instance not available during setup.{ANSI_RESET}")
        if not self.ui:
             print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - User Interface not available during setup.{ANSI_RESET}")

        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Setup in progress. Squid: {'Set' if self.squid else 'Not Set'}, UI: {'Set' if self.ui else 'Not Set'}.{ANSI_RESET}")

        if self.plugin_manager and hasattr(self.plugin_manager, 'subscribe_to_hook'):
            self.plugin_manager.subscribe_to_hook("on_update", PLUGIN_NAME, self.on_game_update)
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Subscribed to 'on_update' hook.{ANSI_RESET}")
        else:
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - PluginManager or subscribe_to_hook method not available. Cannot subscribe to hooks.{ANSI_RESET}")

        # Initialize icons (hidden by default)
        self._ensure_icon_item('feed', FEED_ICON_PATH, hidden=True)
        self._ensure_icon_item('clean', CLEAN_ICON_PATH, hidden=True)
        
        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Setup complete.{ANSI_RESET}")

    def _get_icon_base_x_position(self):
        """Calculates base X for right-aligned icons, considering points display."""
        if self.ui and hasattr(self.ui, 'window_width'):
            # Position icons to the left of the points display area
            # Points label starts at window_width - 255. Let's place icons before that.
            return self.ui.window_width - 255 - ICON_SIZE - ICON_PADDING 
        return 10 # Fallback if UI width not available

    def _ensure_icon_item(self, icon_name, icon_path, hidden=True):
        if not PYQT5_AVAILABLE or not self.ui or not hasattr(self.ui, 'scene') or not self.ui.scene:
            return

        icon_attr_name = f"{icon_name}_icon_item"
        current_item = getattr(self, icon_attr_name, None)

        if current_item and current_item.scene() == self.ui.scene:
            # Item exists and is in the correct scene, just ensure visibility
            current_item.setVisible(not hidden)
            return current_item

        # If item doesn't exist or not in current scene, (re)create it
        if current_item and current_item.scene():
            current_item.scene().removeItem(current_item)
        
        pixmap = QPixmap(icon_path)
        if pixmap.isNull():
            print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Warning - Failed to load icon: {icon_path}{ANSI_RESET}")
            setattr(self, icon_attr_name, None)
            return None

        new_item = QGraphicsPixmapItem(pixmap.scaled(ICON_SIZE, ICON_SIZE, aspectRatioMode=0, transformMode=0)) # aspectRatioMode=0 (Qt.KeepAspectRatio), transformMode=0 (Qt.SmoothTransformation)
        
        base_x = self._get_icon_base_x_position()
        y_pos = 10 # Default Y for the first icon
        
        if icon_name == 'feed':
            y_pos = 10
        elif icon_name == 'clean':
            y_pos = 10 + ICON_SIZE + ICON_PADDING # Stack below feed icon

        new_item.setPos(QPointF(base_x, y_pos))
        new_item.setZValue(190)  # Below plugin active message (200) but above most other things
        new_item.setVisible(not hidden)
        self.ui.scene.addItem(new_item)
        setattr(self, icon_attr_name, new_item)
        return new_item

    def _show_icon(self, icon_name):
        item = self._ensure_icon_item(icon_name, FEED_ICON_PATH if icon_name == 'feed' else CLEAN_ICON_PATH, hidden=False)
        if item:
            item.setVisible(True)

    def _hide_icon(self, icon_name):
        icon_attr_name = f"{icon_name}_icon_item"
        item = getattr(self, icon_attr_name, None)
        if item:
            item.setVisible(False)

    def _display_active_message(self):
        if not PYQT5_AVAILABLE or not self.ui or not hasattr(self.ui, 'scene') or not self.ui.scene:
            return

        if self.active_indicator_item and self.active_indicator_item.scene() == self.ui.scene:
            self.active_indicator_item.setVisible(True) # Just make it visible if it exists
            return

        if self.active_indicator_item and self.active_indicator_item.scene(): # remove if in wrong scene
            self.active_indicator_item.scene().removeItem(self.active_indicator_item)
        
        self.active_indicator_item = QGraphicsTextItem(f"{PLUGIN_NAME} active")
        self.active_indicator_item.setDefaultTextColor(QColor("yellow"))
        self.active_indicator_item.setFont(QFont("Arial", 10)) # Smaller font
        self.active_indicator_item.setPos(10, 10) 
        self.active_indicator_item.setZValue(200)
        self.ui.scene.addItem(self.active_indicator_item)

    def _remove_active_message(self):
        if self.active_indicator_item and self.active_indicator_item.scene():
            self.active_indicator_item.setVisible(False) # Just hide it

    def enable(self):
        if not self.tamagotchi_logic and self.plugin_manager and hasattr(self.plugin_manager, 'tamagotchi_logic_instance'):
            self.setup(self.plugin_manager, self.plugin_manager.tamagotchi_logic_instance)

        self.poop_check_tick_counter = 0
        self.hunger_check_tick_counter = 0
        self.care_tip_tick_counter = 0
        self.last_tip_shown_time = time.time() # Reset tip timer

        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} ENABLED")
        self._display_active_message()
        return True

    def disable(self):
        self._remove_active_message()
        self._hide_icon('feed')
        self._hide_icon('clean')
        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Disabled.{ANSI_RESET}")
        return True

    def _show_care_tip(self):
        if not self.squid or not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'show_message'):
            return

        # Simple weighted random choice, or iterate and pick first valid
        eligible_tips = [tip for tip in self.care_tips if tip["condition"](self.squid)]
        if not eligible_tips:
            # Fallback to a generic tip if no specific condition met
             eligible_tips = [tip for tip in self.care_tips if tip["text"].startswith("Keeping your squid")]


        if eligible_tips:
            chosen_tip = random.choice(eligible_tips)
            self.tamagotchi_logic.show_message(f"Care Tip: {chosen_tip['text']}")
            self.last_tip_shown_time = time.time()
            # Reset counter to ensure interval is met for next tip
            self.care_tip_tick_counter = 0


    def on_game_update(self, tamagotchi_logic: TamagotchiLogic, **kwargs):
        if not self.tamagotchi_logic or not self.squid or not self.ui:
            # Attempt to re-setup if core components are missing (e.g., after a game load/reset)
            if self.plugin_manager and hasattr(self.plugin_manager, 'tamagotchi_logic_instance'):
                 current_logic = self.plugin_manager.tamagotchi_logic_instance
                 if current_logic and (self.tamagotchi_logic != current_logic or not self.squid or not self.ui):
                    print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Core component changed/missing, re-running setup...{ANSI_RESET}")
                    self.setup(self.plugin_manager, current_logic)
                    if not self.tamagotchi_logic or not self.squid or not self.ui: # If still missing, return
                        return
            else: # If no way to get logic instance, return
                return


        # Ensure UI elements are present if plugin is active
        if PYQT5_AVAILABLE and self.ui and hasattr(self.ui, 'scene') and self.ui.scene:
            if not self.active_indicator_item or \
               (hasattr(self.active_indicator_item, 'scene') and self.active_indicator_item.scene() != self.ui.scene):
                self._display_active_message()
            
            # Update icon positions if window width changed significantly
            # This is a basic check; more robust handling might be needed for frequent resizes
            if hasattr(self.ui, '_last_known_width_for_autocare_icons') and \
               abs(self.ui.window_width - self.ui._last_known_width_for_autocare_icons) > 10:
                self._ensure_icon_item('feed', FEED_ICON_PATH, hidden=(not (self.feed_icon_item and self.feed_icon_item.isVisible())))
                self._ensure_icon_item('clean', CLEAN_ICON_PATH, hidden=(not (self.clean_icon_item and self.clean_icon_item.isVisible())))
            self.ui._last_known_width_for_autocare_icons = self.ui.window_width


        # --- Auto Feed Logic ---
        self.hunger_check_tick_counter += 1
        if self.hunger_check_tick_counter >= HUNGER_CHECK_INTERVAL_TICKS:
            self.hunger_check_tick_counter = 0

            if self.squid.hunger > AUTO_FEED_THRESHOLD:
                self._show_icon('feed')
                if not self.hunger_alert_shown_console:
                    # Console message for debugging/logging
                    print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Squid hunger ({self.squid.hunger}%) is above threshold ({AUTO_FEED_THRESHOLD}%). Attempting to feed.{ANSI_RESET}")
                    self.hunger_alert_shown_console = True
                
                # Game message for user
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    self.tamagotchi_logic.show_message(f"{PLUGIN_NAME}: Feeding squid (Hunger: {int(self.squid.hunger)}% / Threshold: {AUTO_FEED_THRESHOLD}%)")
                
                self.tamagotchi_logic.feed_squid()
                # Icon will be hidden below once hunger drops
            else:
                self._hide_icon('feed')
                if self.hunger_alert_shown_console:
                    self.hunger_alert_shown_console = False
        
        # Hide feed icon if hunger drops below threshold for any reason (e.g. manual feed)
        if self.squid.hunger <= AUTO_FEED_THRESHOLD and self.feed_icon_item and self.feed_icon_item.isVisible():
             self._hide_icon('feed')


        # --- Auto Clean Logic ---
        self.poop_check_tick_counter += 1
        if self.poop_check_tick_counter >= POOP_CHECK_INTERVAL_TICKS:
            self.poop_check_tick_counter = 0
            
            # Check if there are poop items using the attribute from tamagotchi_logic
            if hasattr(self.tamagotchi_logic, 'poop_items') and self.tamagotchi_logic.poop_items:
                print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Poop found! Initiating cleaning.{ANSI_RESET}")
                self._show_icon('clean')

                if hasattr(self.tamagotchi_logic, 'show_message'):
                     self.tamagotchi_logic.show_message(f"{PLUGIN_NAME}: Poop detected! Cleaning environment.")
                
                # Call clean_environment from tamagotchi_logic
                self.tamagotchi_logic.clean_environment()
                
                # Hide clean icon after initiating cleaning.
                # A more advanced implementation might wait for cleaning to finish.
                self._hide_icon('clean') 
            else:
                # Ensure clean icon is hidden if no poop was found during this check
                self._hide_icon('clean')

        # --- Care Tips Logic ---
        self.care_tip_tick_counter += 1
        current_time = time.time()
        # Check tick counter and also a time-based cooldown to prevent spam if ticks are very fast
        if self.care_tip_tick_counter >= CARE_TIP_INTERVAL_TICKS and \
           (current_time - self.last_tip_shown_time) > (CARE_TIP_INTERVAL_TICKS / TICKS_PER_SECOND_ASSUMPTION * 0.8): # Ensure roughly the interval has passed in real time too
            self.care_tip_tick_counter = 0 # Reset tick counter
            self._show_care_tip()


# --- Plugin Registration Function ---
def initialize(plugin_manager_instance):
    """
    Initializes the Auto-Care plugin and registers it with the plugin manager.
    """
    try:
        plugin_instance = AutoCarePlugin()
        plugin_key = PLUGIN_NAME.lower().replace(" ", "_").replace("-", "_") # auto_care

        plugin_manager_instance.plugins[plugin_key] = { # type: ignore
            'instance': plugin_instance,
            'name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'author': PLUGIN_AUTHOR,
            'description': PLUGIN_DESCRIPTION,
            'is_setup': False,
            'is_enabled_by_default': False # Default to false, user can enable via manager
        }
        print(f"{ANSI_YELLOW}{PLUGIN_NAME}:{ANSI_RESET}{ANSI_GREY} Plugin registered with key '{plugin_key}'.{ANSI_RESET}")
        return True
    except Exception as e:
        print(f"{ANSI_YELLOW}Error during {PLUGIN_NAME}{ANSI_RESET}{ANSI_GREY} plugin initialization: {e}{ANSI_RESET}")
        import traceback
        print(f"{ANSI_YELLOW}Traceback:{ANSI_RESET}{ANSI_GREY} {traceback.format_exc()}{ANSI_RESET}")
        return False