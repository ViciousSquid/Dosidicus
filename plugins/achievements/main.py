# File: main.py
# Entry point for the Achievements Plugin
# This file is required by the PluginManager

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

from PyQt5 import QtCore, QtWidgets, QtGui

# Import the local copy of DisplayScaling
from .display_scaling import DisplayScaling as _DS

# Increase the *nominal* sizes by ~1.4× (tweak multiplier to taste)
_FONT_BOOST = 1.4

def _scale_size(pt: int) -> int:
    """Return a bigger base size before DisplayScaling does its job."""
    return int(pt * _FONT_BOOST)

# Monkey-patch the local DisplayScaling.font_size so every caller
# automatically gets the boosted value.
_DS.font_size = lambda pt: max(8, _DS.scale(_scale_size(pt)))
# Re-export the (now patched) class under its original name so UI code can see it
DisplayScaling = _DS


# =============================================================================
# PLUGIN METADATA - Required by PluginManager
# =============================================================================

PLUGIN_NAME = "Achievements"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "ViciousSquid"
PLUGIN_DESCRIPTION = "Track milestones and unlock achievements as your squid grows"
PLUGIN_REQUIRES = []  # No dependencies


# =============================================================================
# ACHIEVEMENT DEFINITIONS
# =============================================================================

class AchievementCategory(Enum):
    FEEDING = "feeding"
    NEUROGENESIS = "neurogenesis"
    SLEEP = "sleep"
    MILESTONES = "milestones"
    EXPLORATION = "exploration"
    SOCIAL = "social"
    SECRET = "secret"


@dataclass
class Achievement:
    id: str
    name: str
    description: str
    icon: str = "🏆"
    category: str = "milestones"
    hidden: bool = False
    points: int = 10
    tier: int = 1
    target_count: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UnlockedAchievement:
    achievement_id: str
    unlocked_at: str
    progress: int = 0
    notified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'UnlockedAchievement':
        return cls(**data)


# Tier colors for UI
TIER_COLORS = {
    1: "#CD7F32",  # Bronze
    2: "#C0C0C0",  # Silver
    3: "#FFD700",  # Gold
    4: "#E5E4E2",  # Platinum
}

# All achievement definitions
ACHIEVEMENT_DEFINITIONS: Dict[str, Achievement] = {
    # --- Feeding ---
    "first_feeding": Achievement(
        id="first_feeding", name="First Bite",
        description="Feed the squid for the first time",
        icon="🍽️", category="feeding", points=10, tier=1,
    ),
    "fed_10_times": Achievement(
        id="fed_10_times", name="Regular Meals",
        description="Feed the squid 10 times",
        icon="🥄", category="feeding", points=15, tier=1, target_count=10,
    ),
    "fed_50_times": Achievement(
        id="fed_50_times", name="Dedicated Caretaker",
        description="Feed the squid 50 times",
        icon="🍴", category="feeding", points=25, tier=2, target_count=50,
    ),
    "fed_100_times": Achievement(
        id="fed_100_times", name="Master Chef",
        description="Feed the squid 100 times",
        icon="👨‍🍳", category="feeding", points=50, tier=3, target_count=100,
    ),
    "fed_500_times": Achievement(
        id="fed_500_times", name="Culinary Legend",
        description="Feed the squid 500 times",
        icon="🌟", category="feeding", points=100, tier=4, target_count=500, hidden=True,
    ),
    # --- Neurogenesis ---
    "first_neuron": Achievement(
        id="first_neuron", name="Brain Spark",
        description="Create the first neurogenesis neuron",
        icon="🧠", category="neurogenesis", points=20, tier=1,
    ),
    "neurons_10": Achievement(
        id="neurons_10", name="Neural Network",
        description="Create 10 neurons through neurogenesis",
        icon="🔮", category="neurogenesis", points=30, tier=2, target_count=10,
    ),
    "neurons_50": Achievement(
        id="neurons_50", name="Expanding Mind",
        description="Create 50 neurons through neurogenesis",
        icon="💫", category="neurogenesis", points=50, tier=3, target_count=50,
    ),
    "first_neuron_levelup": Achievement(
        id="first_neuron_levelup", name="Strengthened Synapse",
        description="Level up a neuron for the first time",
        icon="⚡", category="neurogenesis", points=15, tier=1,
    ),
    "neuron_max_level": Achievement(
        id="neuron_max_level", name="Peak Performance",
        description="Level a neuron to maximum strength",
        icon="🌠", category="neurogenesis", points=40, tier=3,
    ),
    # --- Sleep ---
    "first_sleep": Achievement(
        id="first_sleep", name="Sweet Dreams",
        description="The squid wakes from its first sleep",
        icon="😴", category="sleep", points=10, tier=1,
    ),
    "slept_10_times": Achievement(
        id="slept_10_times", name="Well Rested",
        description="The squid has slept 10 times",
        icon="🛏️", category="sleep", points=20, tier=2, target_count=10,
    ),
    "dream_state": Achievement(
        id="dream_state", name="Deep Dreamer",
        description="Squid entered REM sleep",
        icon="💭", category="sleep", points=25, tier=2, hidden=True,
    ),
    # --- Milestones ---
    "age_1_hour": Achievement(
        id="age_1_hour", name="One Hour Old",
        description="Squid reached 1 hour old",
        icon="⏰", category="milestones", points=15, tier=1,
    ),
    "age_10_hours": Achievement(
        id="age_10_hours", name="Growing Up",
        description="Squid reached 10 hours old",
        icon="📅", category="milestones", points=30, tier=2,
    ),
    "age_24_hours": Achievement(
        id="age_24_hours", name="One Day Wonder",
        description="Squid survived for 24 hours",
        icon="🎂", category="milestones", points=50, tier=3,
    ),
    "age_1_week": Achievement(
        id="age_1_week", name="Week Veteran",
        description="Squid has lived for one week",
        icon="🏅", category="milestones", points=100, tier=4, hidden=True,
    ),
    "happiness_100": Achievement(
        id="happiness_100", name="Pure Bliss",
        description="Reach 100% happiness",
        icon="😄", category="milestones", points=20, tier=2,
    ),
    "all_stats_high": Achievement(
        id="all_stats_high", name="Perfect Balance",
        description="All stats above 80% simultaneously",
        icon="⚖️", category="milestones", points=40, tier=3,
    ),
    # --- Exploration ---
    "first_poop_throw": Achievement(
        id="first_poop_throw", name="Mischief Maker",
        description="Squid threw a poop for the first time",
        icon="💩", category="exploration", points=10, tier=1,
    ),
    # --- Secret ---
    "night_owl": Achievement(
        id="night_owl", name="Night Owl",
        description="Play between midnight and 4 AM",
        icon="🦉", category="secret", points=15, tier=2, hidden=True,
    ),
}


# =============================================================================
# UI COMPONENTS
# =============================================================================

class AchievementNotification(QtWidgets.QWidget):
    """Toast notification for achievement unlocks"""

    def __init__(self, achievement: Achievement, parent=None):
        super().__init__(parent)
        self.achievement = achievement
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self):
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # 1.4× larger base geometry
        self.setFixedSize(DisplayScaling.scale(448), DisplayScaling.scale(112))

        container = QtWidgets.QFrame(self)
        container.setFixedSize(DisplayScaling.scale(420), DisplayScaling.scale(98))
        container.move(DisplayScaling.scale(14), DisplayScaling.scale(7))

        container.setStyleSheet("""
            QFrame {
                background-color: rgb(25, 25, 25);
                border: none;
                border-radius: 8px;
            }
        """)

        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(DisplayScaling.scale(14),
                                  DisplayScaling.scale(7),
                                  DisplayScaling.scale(14),
                                  DisplayScaling.scale(7))

        icon_label = QtWidgets.QLabel(self.achievement.icon)
        icon_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(45)}px; background: transparent; color: white;")
        icon_label.setFixedWidth(DisplayScaling.scale(70))   # give icon a bit more room
        layout.addWidget(icon_label)

        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(DisplayScaling.scale(3))

        header = QtWidgets.QLabel("Achievement Unlocked!")
        header.setStyleSheet(f"color: white; "
                             f"font-size: {DisplayScaling.font_size(15)}px; "
                             f"font-weight: bold; background: transparent;")
        text_layout.addWidget(header)

        name_label = QtWidgets.QLabel(self.achievement.name)
        name_label.setStyleSheet(f"color: white; "
                                 f"font-size: {DisplayScaling.font_size(20)}px; "
                                 f"font-weight: bold; background: transparent;")
        text_layout.addWidget(name_label)

        points_label = QtWidgets.QLabel(f"+{self.achievement.points} points")
        points_label.setStyleSheet(f"color: #aaa; "
                                   f"font-size: {DisplayScaling.font_size(14)}px; "
                                   f"background: transparent;")
        text_layout.addWidget(points_label)

        layout.addLayout(text_layout)
        layout.addStretch()

    def _setup_animation(self):
        self.opacity_effect = QtWidgets.QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)

        self.fade_in = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_in.setDuration(300)
        self.fade_in.setStartValue(0)
        self.fade_in.setEndValue(1)

        self.fade_out = QtCore.QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_out.setDuration(500)
        self.fade_out.setStartValue(1)
        self.fade_out.setEndValue(0)
        self.fade_out.finished.connect(self.close)

        self.display_timer = QtCore.QTimer(self)
        self.display_timer.setSingleShot(True)
        self.display_timer.timeout.connect(self.fade_out.start)

    def show_notification(self, duration_ms=3500):
        self.show()
        self.fade_in.start()
        self.display_timer.start(duration_ms)


class AchievementsWindow(QtWidgets.QDialog):
    """Window displaying all achievements"""

    def __init__(self, plugin: 'AchievementsPlugin', parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle(f"🏆 {PLUGIN_NAME}")
        self.setMinimumSize(DisplayScaling.scale(500), DisplayScaling.scale(600))
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2c3e50, stop:1 #3498db);
                border-radius: 8px; padding: 10px;
            }
        """)
        header_layout = QtWidgets.QHBoxLayout(header)

        total_points = self.plugin.get_total_points()
        total_unlocked = len(self.plugin.unlocked)
        total_available = len([a for a in ACHIEVEMENT_DEFINITIONS.values() if not a.hidden])

        points_label = QtWidgets.QLabel(f"🏆 {total_points} Points")
        points_label.setStyleSheet(f"color: gold; "
                                   f"font-size: {DisplayScaling.font_size(18)}px; "
                                   f"font-weight: bold;")
        header_layout.addWidget(points_label)
        header_layout.addStretch()

        progress_label = QtWidgets.QLabel(f"📊 {total_unlocked}/{total_available} Unlocked")
        progress_label.setStyleSheet(f"color: white; "
                                     f"font-size: {DisplayScaling.font_size(14)}px;")
        header_layout.addWidget(progress_label)

        layout.addWidget(header)

        # Tabs
        tabs = QtWidgets.QTabWidget()
        tabs.addTab(self._create_list(None), "All")
        for cat in AchievementCategory:
            tabs.addTab(self._create_list(cat.value), cat.value.title())
        layout.addWidget(tabs)

    def _create_list(self, category_filter: Optional[str]) -> QtWidgets.QScrollArea:
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(DisplayScaling.scale(8))

        unlocked_ids = set(self.plugin.unlocked.keys())

        for ach_id, ach in ACHIEVEMENT_DEFINITIONS.items():
            if category_filter and ach.category != category_filter:
                continue
            is_unlocked = ach_id in unlocked_ids
            if ach.hidden and not is_unlocked:
                continue

            card = self._create_card(ach, is_unlocked, self.plugin.progress.get(ach_id, 0))
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _create_card(self, ach: Achievement, unlocked: bool, progress: int) -> QtWidgets.QFrame:
        card = QtWidgets.QFrame()
        border_color = TIER_COLORS.get(ach.tier, "#CD7F32") if unlocked else "#555"
        bg = "rgba(40, 50, 60, 200)" if unlocked else "rgba(30, 30, 35, 180)"
        card.setStyleSheet(f"QFrame {{ background: {bg}; border: 2px solid {border_color}; border-radius: 8px; }}")

        layout = QtWidgets.QHBoxLayout(card)

        icon = QtWidgets.QLabel(ach.icon if unlocked else "🔒")
        icon.setStyleSheet(f"font-size: {DisplayScaling.font_size(28)}px;")
        icon.setFixedWidth(DisplayScaling.scale(50))
        layout.addWidget(icon)

        info = QtWidgets.QVBoxLayout()
        name = QtWidgets.QLabel(ach.name if unlocked or not ach.hidden else "???")
        name.setStyleSheet(f"color: {'white' if unlocked else '#888'}; "
                           f"font-size: {DisplayScaling.font_size(14)}px; "
                           f"font-weight: bold;")
        info.addWidget(name)

        desc = QtWidgets.QLabel(ach.description if unlocked or not ach.hidden else "Hidden achievement")
        desc.setStyleSheet(f"color: {'#aaa' if unlocked else '#666'}; "
                           f"font-size: {DisplayScaling.font_size(11)}px;")
        desc.setWordWrap(True)
        info.addWidget(desc)

        if ach.target_count > 1 and not unlocked:
            pbar = QtWidgets.QProgressBar()
            pbar.setMaximum(ach.target_count)
            pbar.setValue(min(progress, ach.target_count))
            pbar.setFormat(f"{progress}/{ach.target_count}")
            pbar.setFixedHeight(DisplayScaling.scale(16))
            info.addWidget(pbar)

        layout.addLayout(info, 1)

        pts = QtWidgets.QLabel(f"+{ach.points}")
        pts.setStyleSheet(f"color: {TIER_COLORS.get(ach.tier, '#CD7F32')}; "
                          f"font-size: {DisplayScaling.font_size(12)}px; "
                          f"font-weight: bold;")
        layout.addWidget(pts)

        return card


# =============================================================================
# MAIN PLUGIN CLASS
# =============================================================================

class AchievementsPlugin:
    """Main achievements plugin class"""

    def __init__(self):
        self.logger = None
        self.plugin_manager = None
        self.tamagotchi_logic = None
        self.squid = None

        self.unlocked: Dict[str, UnlockedAchievement] = {}
        self.progress: Dict[str, int] = {}
        self.statistics: Dict[str, int] = {}

        self.age_check_timer: Optional[QtCore.QTimer] = None
        self.stat_check_timer: Optional[QtCore.QTimer] = None
        self.notification_timer: Optional[QtCore.QTimer] = None
        self.notification_queue: List[Achievement] = []
        self.current_notification: Optional[AchievementNotification] = None

        self.parent_window: Optional[QtWidgets.QMainWindow] = None
        self.is_setup = False
        self.debug_mode = False
        self._original_methods: Dict[str, Any] = {}

    # ----------------------------------------------------------
    #  Write unlock to text file only
    # ----------------------------------------------------------
    def _log_unlock_to_text_file(self, ach: Achievement) -> None:
        """Append 'ID | long-date | HHMMSS | name' to achievements_log.txt in the same folder as the json save."""
        try:
            log_path = Path(self._get_save_path()).with_name("achievements_log.txt")
            # long form date + HHMMSS
            time_stamp = datetime.now().strftime("%A, %B %d, %Y @ %H%M%S")
            line = f"{ach.id} | {time_stamp} | {ach.name}\n"
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Could not write achievement log: {e}")

    def setup(self, plugin_manager, tamagotchi_logic) -> bool:
        """Called by PluginManager when enabling the plugin"""
        self.plugin_manager = plugin_manager
        self.tamagotchi_logic = tamagotchi_logic

        # Setup logger
        if hasattr(plugin_manager, 'logger'):
            self.logger = plugin_manager.logger.getChild(PLUGIN_NAME)
        else:
            self.logger = logging.getLogger(f"{PLUGIN_NAME}_Plugin")
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s: %(message)s'))
                self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

        self.logger.info(f"Setting up {PLUGIN_NAME}...")

        # Get squid reference
        if tamagotchi_logic and hasattr(tamagotchi_logic, 'squid'):
            self.squid = tamagotchi_logic.squid
            self.logger.info(f"Got squid reference: {self.squid}")

        # Get parent window
        if tamagotchi_logic and hasattr(tamagotchi_logic, 'user_interface'):
            ui = tamagotchi_logic.user_interface
            if hasattr(ui, 'window'):
                self.parent_window = ui.window
            elif isinstance(ui, QtWidgets.QMainWindow):
                self.parent_window = ui

        self.debug_mode = getattr(tamagotchi_logic, 'debug_mode', False)

        # Setup timers
        self._setup_timers()

        # Subscribe to plugin manager hooks (more reliable than method hooking)
        self._subscribe_to_hooks()

        # Also try direct method hooks as backup
        self._install_hooks()

        self.is_setup = True
        self.logger.info(f"{PLUGIN_NAME} setup complete. {len(self.unlocked)} achievements loaded.")
        return True

    def _subscribe_to_hooks(self):
        """Subscribe to plugin manager hooks for event tracking"""
        if not self.plugin_manager:
            if self.logger:
                self.logger.warning("No plugin_manager, cannot subscribe to hooks")
            return
        
        hook_subscriptions = [
            ("on_feed", self._hook_on_feed),
            ("on_wake", self._hook_on_wake),
            ("on_sleep", self._hook_on_sleep),
            ("on_neurogenesis", self._hook_on_neurogenesis),
        ]
        
        for hook_name, callback in hook_subscriptions:
            try:
                if hasattr(self.plugin_manager, 'subscribe_to_hook'):
                    result = self.plugin_manager.subscribe_to_hook(hook_name, PLUGIN_NAME, callback)
                    if self.logger:
                        self.logger.info(f"Subscribed to hook '{hook_name}': {result}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not subscribe to hook '{hook_name}': {e}")

    def _hook_on_feed(self, **kwargs):
        """Called via plugin manager hook when squid is fed"""
        if self.logger:
            self.logger.info(f"Hook on_feed triggered! kwargs={kwargs}")
        self.on_squid_fed()

    def _hook_on_wake(self, **kwargs):
        """Called via plugin manager hook when squid wakes"""
        if self.logger:
            self.logger.info(f"Hook on_wake triggered!")
        self.on_squid_woke()

    def _hook_on_sleep(self, **kwargs):
        """Called via plugin manager hook when squid sleeps"""
        if self.logger:
            self.logger.info(f"Hook on_sleep triggered!")
        # Sleep achievement triggers on wake, not on sleep start

    def _hook_on_neurogenesis(self, **kwargs):
        """Called via plugin manager hook when neurogenesis occurs"""
        if self.logger:
            self.logger.info(f"Hook on_neurogenesis triggered!")
        self.on_neuron_created()

    def enable(self) -> bool:
        """Called when plugin is enabled"""
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME} enable() called. is_setup={self.is_setup}")
        
        # If not setup yet, that's okay - setup() will be called by plugin manager first
        # Just make sure timers are created
        if not self.age_check_timer:
            self._setup_timers()
        
        # Re-acquire squid reference in case it changed
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid'):
            if self.squid != self.tamagotchi_logic.squid:
                self.squid = self.tamagotchi_logic.squid
                self._install_hooks()  # Reinstall hooks on new squid
                if self.logger:
                    self.logger.info(f"Re-acquired squid reference and reinstalled hooks")

        # Start timers
        if self.age_check_timer and not self.age_check_timer.isActive():
            self.age_check_timer.start(60000)
            if self.logger:
                self.logger.info("Age check timer started")
                
        if self.stat_check_timer and not self.stat_check_timer.isActive():
            self.stat_check_timer.start(5000)
            if self.logger:
                self.logger.info("Stat check timer started")

        if self.logger:
            self.logger.info(f"{PLUGIN_NAME} enabled successfully")
        return True

    def disable(self):
        """Called when plugin is disabled"""
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME} disable() called")
            
        if self.age_check_timer:
            self.age_check_timer.stop()
        if self.stat_check_timer:
            self.stat_check_timer.stop()
        if self.notification_timer:
            self.notification_timer.stop()
        
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME} disabled")

    def shutdown(self):
        """Called on plugin unload"""
        self.disable()
        self._uninstall_hooks()

    def _setup_timers(self):
        self.age_check_timer = QtCore.QTimer()
        self.age_check_timer.timeout.connect(self._check_age_achievements)

        self.stat_check_timer = QtCore.QTimer()
        self.stat_check_timer.timeout.connect(self._check_stat_achievements)

        self.notification_timer = QtCore.QTimer()
        self.notification_timer.timeout.connect(self._show_next_notification)

    def _install_hooks(self):
        """Hook into game events"""
        if self.logger:
            self.logger.info(f"Installing hooks... squid={self.squid is not None}")
        
        if not self.squid:
            if self.logger:
                self.logger.warning("Cannot install hooks: squid is None")
            return

        hooks_installed = []
        
        try:
            # Hook squid.eat
            if hasattr(self.squid, 'eat') and 'eat' not in self._original_methods:
                self._original_methods['eat'] = self.squid.eat
                original_eat = self._original_methods['eat']
                plugin_self = self  # Capture reference
                
                def hooked_eat(*args, **kwargs):
                    result = original_eat(*args, **kwargs)
                    try:
                        plugin_self.on_squid_fed()
                    except Exception as e:
                        if plugin_self.logger:
                            plugin_self.logger.error(f"Error in on_squid_fed: {e}")
                    return result
                
                self.squid.eat = hooked_eat
                hooks_installed.append('eat')

            # Hook squid.wake_up
            if hasattr(self.squid, 'wake_up') and 'wake_up' not in self._original_methods:
                self._original_methods['wake_up'] = self.squid.wake_up
                original_wake = self._original_methods['wake_up']
                plugin_self = self
                
                def hooked_wake(*args, **kwargs):
                    result = original_wake(*args, **kwargs)
                    try:
                        plugin_self.on_squid_woke()
                    except Exception as e:
                        if plugin_self.logger:
                            plugin_self.logger.error(f"Error in on_squid_woke: {e}")
                    return result
                
                self.squid.wake_up = hooked_wake
                hooks_installed.append('wake_up')

            # Hook neurogenesis
            if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'neurogenesis_system'):
                ng = self.tamagotchi_logic.neurogenesis_system
                if ng and hasattr(ng, 'create_neuron') and 'create_neuron' not in self._original_methods:
                    self._original_methods['create_neuron'] = ng.create_neuron
                    original_create = self._original_methods['create_neuron']
                    plugin_self = self
                    
                    def hooked_create(*args, **kwargs):
                        result = original_create(*args, **kwargs)
                        if result:
                            try:
                                plugin_self.on_neuron_created()
                            except Exception as e:
                                if plugin_self.logger:
                                    plugin_self.logger.error(f"Error in on_neuron_created: {e}")
                        return result
                    
                    ng.create_neuron = hooked_create
                    hooks_installed.append('create_neuron')

            # Hook poop throwing
            if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'poop_manager'):
                pm = self.tamagotchi_logic.poop_manager
                if pm and hasattr(pm, 'throw_poop') and 'throw_poop' not in self._original_methods:
                    self._original_methods['throw_poop'] = pm.throw_poop
                    original_throw = self._original_methods['throw_poop']
                    plugin_self = self
                    
                    def hooked_throw(*args, **kwargs):
                        result = original_throw(*args, **kwargs)
                        if result:
                            try:
                                plugin_self.on_poop_thrown()
                            except Exception as e:
                                if plugin_self.logger:
                                    plugin_self.logger.error(f"Error in on_poop_thrown: {e}")
                        return result
                    
                    pm.throw_poop = hooked_throw
                    hooks_installed.append('throw_poop')

            if self.logger:
                self.logger.info(f"Hooks installed: {hooks_installed}")

        except Exception as e:
            if self.logger:
                self.logger.error(f"Error installing hooks: {e}", exc_info=True)

    def _uninstall_hooks(self):
        try:
            if 'eat' in self._original_methods and self.squid:
                self.squid.eat = self._original_methods['eat']
            if 'wake_up' in self._original_methods and self.squid:
                self.squid.wake_up = self._original_methods['wake_up']
        except:
            pass
        self._original_methods.clear()

    # --- Event Handlers ---

    def on_squid_fed(self):
        if self.logger:
            self.logger.info("")
        self._increment_stat("times_fed")
        count = self.statistics.get("times_fed", 0)
        if self.logger:
            self.logger.info(f"")
        if count == 1:
            self.unlock_achievement("first_feeding")
        if count >= 10:
            self.unlock_achievement("fed_10_times")
        if count >= 50:
            self.unlock_achievement("fed_50_times")
        if count >= 100:
            self.unlock_achievement("fed_100_times")
        if count >= 500:
            self.unlock_achievement("fed_500_times")
        for aid in ["fed_10_times", "fed_50_times", "fed_100_times", "fed_500_times"]:
            self._update_progress(aid, count)

    def on_squid_woke(self):
        self._increment_stat("times_slept")
        count = self.statistics.get("times_slept", 0)
        if count == 1:
            self.unlock_achievement("first_sleep")
        if count >= 10:
            self.unlock_achievement("slept_10_times")
        self._update_progress("slept_10_times", count)

    def on_neuron_created(self):
        self._increment_stat("neurons_created")
        count = self.statistics.get("neurons_created", 0)
        if count == 1:
            self.unlock_achievement("first_neuron")
        if count >= 10:
            self.unlock_achievement("neurons_10")
        if count >= 50:
            self.unlock_achievement("neurons_50")
        self._update_progress("neurons_10", count)
        self._update_progress("neurons_50", count)

    def on_neuron_leveled(self):
        self._increment_stat("neurons_leveled")
        if self.statistics.get("neurons_leveled", 0) == 1:
            self.unlock_achievement("first_neuron_levelup")

    def on_poop_thrown(self):
        self._increment_stat("poops_thrown")
        if self.statistics.get("poops_thrown", 0) == 1:
            self.unlock_achievement("first_poop_throw")

    def _check_age_achievements(self):
        if not self.squid:
            return
        age_hours = 0
        if hasattr(self.squid, 'birth_time'):
            age_hours = (time.time() - self.squid.birth_time) / 3600
        elif hasattr(self.squid, 'age_hours'):
            age_hours = self.squid.age_hours

        if age_hours >= 1:
            self.unlock_achievement("age_1_hour")
        if age_hours >= 10:
            self.unlock_achievement("age_10_hours")
        if age_hours >= 24:
            self.unlock_achievement("age_24_hours")
        if age_hours >= 168:
            self.unlock_achievement("age_1_week")

        if 0 <= datetime.now().hour < 4:
            self.unlock_achievement("night_owl")

    def _check_stat_achievements(self):
        if not self.squid:
            return
        if hasattr(self.squid, 'happiness') and self.squid.happiness >= 100:
            self.unlock_achievement("happiness_100")

        stats = ['happiness', 'hunger', 'energy', 'health']
        all_high = all(getattr(self.squid, s, 0) >= 80 for s in stats if hasattr(self.squid, s))
        if all_high:
            self.unlock_achievement("all_stats_high")

    # --- Core Methods ---

    def unlock_achievement(self, achievement_id: str, silent: bool = False) -> bool:
        if achievement_id in self.unlocked:
            return False
        if achievement_id not in ACHIEVEMENT_DEFINITIONS:
            return False

        ach = ACHIEVEMENT_DEFINITIONS[achievement_id]
        if ach.target_count > 1 and self.progress.get(achievement_id, 0) < ach.target_count:
            return False

        self.unlocked[achievement_id] = UnlockedAchievement(
            achievement_id=achievement_id,
            unlocked_at=datetime.now().isoformat(),
            progress=ach.target_count,
            notified=silent
        )

        if self.logger:
            self.logger.info(f"🏆 Unlocked: {ach.name}")

        # Log to text file
        self._log_unlock_to_text_file(ach)

        if not silent:
            self._queue_notification(ach)

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"🏆")

        return True

    def manually_trigger(self, event_name: str):
        handlers = {
            "fed": self.on_squid_fed,
            "woke": self.on_squid_woke,
            "neuron_created": self.on_neuron_created,
            "neuron_leveled": self.on_neuron_leveled,
            "poop_thrown": self.on_poop_thrown,
            "neuron_max_level": lambda: self.unlock_achievement("neuron_max_level"),
            "dream_state": lambda: self.unlock_achievement("dream_state"),
        }
        if event_name in handlers:
            handlers[event_name]()
        else:
            self.unlock_achievement(event_name)

    def get_total_points(self) -> int:
        return sum(
            ACHIEVEMENT_DEFINITIONS[a.achievement_id].points
            for a in self.unlocked.values()
            if a.achievement_id in ACHIEVEMENT_DEFINITIONS
        )

    def _increment_stat(self, name: str, amount: int = 1):
        self.statistics[name] = self.statistics.get(name, 0) + amount

    def _update_progress(self, achievement_id: str, value: int):
        self.progress[achievement_id] = value

    # --- Notifications ---

    def _queue_notification(self, achievement: Achievement):
        self.notification_queue.append(achievement)
        if not self.notification_timer.isActive():
            self._show_next_notification()

    def _show_next_notification(self):
        if self.current_notification:
            self.current_notification.close()
            self.current_notification = None

        if not self.notification_queue:
            self.notification_timer.stop()
            return

        ach = self.notification_queue.pop(0)
        self.current_notification = AchievementNotification(ach, self.parent_window)

        if self.parent_window:
            geo = self.parent_window.geometry()
            # pin top-left corner with a small inset
            x = geo.x() + DisplayScaling.scale(20)
            y = geo.y() + DisplayScaling.scale(20)
            self.current_notification.move(x, y)

        self.current_notification.show_notification()

        if self.notification_queue:
            self.notification_timer.start(4000)

    # --- Persistence ---

    def _get_save_path(self) -> str:
        # We only use this to determine the directory for the text log
        os.makedirs("saves", exist_ok=True)
        return os.path.join("saves", "achievements.json")

    def get_save_data(self) -> dict:
        return {
            "unlocked": {k: v.to_dict() for k, v in self.unlocked.items()},
            "progress": self.progress,
            "statistics": self.statistics,
        }

    def load_save_data(self, data: dict):
        if not data:
            return
        for aid, adata in data.get("unlocked", {}).items():
            self.unlocked[aid] = UnlockedAchievement.from_dict(adata)
        self.progress = data.get("progress", {})
        self.statistics = data.get("statistics", {})

    # --- UI ---

    def show_achievements_window(self):
        window = AchievementsWindow(self, self.parent_window)
        window.exec_()

    def register_menu_actions(self, main_window: QtWidgets.QMainWindow, menu: QtWidgets.QMenu):
        action = QtWidgets.QAction(f"🏆 {PLUGIN_NAME}...", main_window)
        action.triggered.connect(self.show_achievements_window)
        menu.addAction(action)


# =============================================================================
# INITIALIZE FUNCTION - Required by PluginManager
# =============================================================================

def initialize(plugin_manager) -> bool:
    """
    Called by PluginManager to initialize this plugin.
    Must register the plugin instance with the plugin manager.
    """
    try:
        # Create plugin instance
        instance = AchievementsPlugin()

        # Register with plugin manager (REQUIRED!)
        plugin_manager.plugins[PLUGIN_NAME.lower()] = {
            'name': PLUGIN_NAME.lower(),
            'original_name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'author': PLUGIN_AUTHOR,
            'description': PLUGIN_DESCRIPTION,
            'requires': PLUGIN_REQUIRES,
            'instance': instance,
            'is_setup': False,
        }

        # Log success
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.info(f"{PLUGIN_NAME} v{PLUGIN_VERSION} initialized")

        return True

    except Exception as e:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.error(f"Failed to initialize {PLUGIN_NAME}: {e}")
        return False