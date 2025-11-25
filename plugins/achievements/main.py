# File: main.py
# Entry point for the Achievements Plugin
# This file is required by the PluginManager

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
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

# Import achievement definitions from separate file
from .achievements_data import (
    Achievement,
    UnlockedAchievement,
    AchievementCategory,
    ACHIEVEMENT_DEFINITIONS,
    TIER_COLORS,
    get_achievement,
)


# =============================================================================
# PLUGIN METADATA - Required by PluginManager
# =============================================================================

PLUGIN_NAME = "Achievements"
PLUGIN_VERSION = "2.0.0"
PLUGIN_AUTHOR = "ViciousSquid"
PLUGIN_DESCRIPTION = "Track milestones and unlock achievements as your squid grows"
PLUGIN_REQUIRES = []  # No dependencies


# =============================================================================
# UI COMPONENTS
# =============================================================================

class AchievementNotification(QtWidgets.QWidget):
    """Toast notification for achievement unlocks - LARGER VERSION with description"""

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
        
        # LARGER toast to fit description - increased height significantly
        self.setFixedSize(DisplayScaling.scale(520), DisplayScaling.scale(160))

        container = QtWidgets.QFrame(self)
        container.setFixedSize(DisplayScaling.scale(490), DisplayScaling.scale(145))
        container.move(DisplayScaling.scale(15), DisplayScaling.scale(7))

        # Simple dark rectangle background
        tier_color = TIER_COLORS.get(self.achievement.tier, "#CD7F32")
        container.setStyleSheet("""
            QFrame {
                background: rgb(30, 30, 35);
                border: none;
                border-radius: 8px;
            }
        """)

        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(
            DisplayScaling.scale(16),
            DisplayScaling.scale(12),
            DisplayScaling.scale(16),
            DisplayScaling.scale(12)
        )
        layout.setSpacing(DisplayScaling.scale(14))

        # Icon - larger
        icon_label = QtWidgets.QLabel(self.achievement.icon)
        icon_label.setStyleSheet(f"""
            font-size: {DisplayScaling.font_size(52)}px; 
            background: transparent; 
            color: white;
        """)
        icon_label.setFixedWidth(DisplayScaling.scale(80))
        icon_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(icon_label)

        # Text section
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setSpacing(DisplayScaling.scale(4))

        # Header "Achievement Unlocked!"
        header = QtWidgets.QLabel("Achievement Unlocked!")
        header.setStyleSheet(f"""
            color: {tier_color}; 
            font-size: {DisplayScaling.font_size(14)}px; 
            font-weight: bold; 
            background: transparent;
        """)
        text_layout.addWidget(header)

        # Achievement name
        name_label = QtWidgets.QLabel(self.achievement.name)
        name_label.setStyleSheet(f"""
            color: white; 
            font-size: {DisplayScaling.font_size(22)}px; 
            font-weight: bold; 
            background: transparent;
        """)
        text_layout.addWidget(name_label)

        # Achievement DESCRIPTION - the key addition!
        desc_label = QtWidgets.QLabel(self.achievement.description)
        desc_label.setStyleSheet(f"""
            color: #cccccc; 
            font-size: {DisplayScaling.font_size(13)}px; 
            background: transparent;
        """)
        desc_label.setWordWrap(True)
        desc_label.setMaximumWidth(DisplayScaling.scale(320))
        text_layout.addWidget(desc_label)

        # Points earned
        points_label = QtWidgets.QLabel(f"+{self.achievement.points} points")
        points_label.setStyleSheet(f"""
            color: {tier_color}; 
            font-size: {DisplayScaling.font_size(12)}px; 
            font-weight: bold;
            background: transparent;
        """)
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

    def show_notification(self, duration_ms=4000):
        self.show()
        self.fade_in.start()
        self.display_timer.start(duration_ms)


class AchievementsWindow(QtWidgets.QDialog):
    """Window displaying all achievements"""

    def __init__(self, plugin: 'AchievementsPlugin', parent=None):
        super().__init__(parent)
        self.plugin = plugin
        self.setWindowTitle(f"🏆 {PLUGIN_NAME}")
        self.setMinimumSize(DisplayScaling.scale(550), DisplayScaling.scale(650))
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
            cat_achievements = [a for a in ACHIEVEMENT_DEFINITIONS.values() if a.category == cat.value]
            if cat_achievements:  # Only add tab if category has achievements
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

        # Timers
        self.age_check_timer: Optional[QtCore.QTimer] = None
        self.stat_check_timer: Optional[QtCore.QTimer] = None
        self.notification_timer: Optional[QtCore.QTimer] = None
        self.notification_queue: List[Achievement] = []
        self.current_notification: Optional[AchievementNotification] = None

        # Tracking for timed achievements
        self.cleanliness_high_since: Optional[float] = None  # For germaphobe
        self.anxiety_low_since: Optional[float] = None  # For zen_master
        self.max_speed_since: Optional[float] = None  # For speed_demon
        self.health_was_critical: bool = False  # For comeback_kid
        self.weekend_saturday: bool = False  # For weekend_warrior
        self.weekend_sunday: bool = False

        self.parent_window: Optional[QtWidgets.QMainWindow] = None
        self.is_setup = False
        self.debug_mode = False
        self._original_methods: Dict[str, Any] = {}

    # ----------------------------------------------------------
    #  Write unlock to text file only
    # ----------------------------------------------------------
    def _log_unlock_to_text_file(self, ach: Achievement) -> None:
        """Append 'ID | long-date | HHMMSS | name' to achievements_log.txt"""
        try:
            log_path = Path(self._get_save_path()).with_name("achievements_log.txt")
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

        # Subscribe to plugin manager hooks
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
            # Original hooks
            ("on_feed", self._hook_on_feed),
            ("on_wake", self._hook_on_wake),
            ("on_sleep", self._hook_on_sleep),
            ("on_neurogenesis", self._hook_on_neurogenesis),
            # New hooks for expanded achievements
            ("on_clean", self._hook_on_clean),
            ("on_medicine", self._hook_on_medicine),
            ("on_rock_pickup", self._hook_on_rock_pickup),
            ("on_rock_throw", self._hook_on_rock_throw),
            ("on_decoration_interaction", self._hook_on_decoration_interaction),
            ("on_ink_cloud", self._hook_on_ink_cloud),
            ("on_startle", self._hook_on_startle),
            ("on_memory_created", self._hook_on_memory_created),
            ("on_memory_to_long_term", self._hook_on_memory_to_long_term),
            ("on_curiosity_change", self._hook_on_curiosity_change),
            ("on_anxiety_change", self._hook_on_anxiety_change),
            ("on_speed_change", self._hook_on_speed_change),
        ]
        
        for hook_name, callback in hook_subscriptions:
            try:
                if hasattr(self.plugin_manager, 'subscribe_to_hook'):
                    result = self.plugin_manager.subscribe_to_hook(hook_name, PLUGIN_NAME, callback)
                    if self.logger:
                        self.logger.debug(f"Subscribed to hook '{hook_name}': {result}")
            except Exception as e:
                if self.logger:
                    self.logger.warning(f"Could not subscribe to hook '{hook_name}': {e}")

    # ----------------------------------------------------------
    # Hook Callbacks
    # ----------------------------------------------------------
    
    def _hook_on_feed(self, **kwargs):
        self.on_squid_fed()

    def _hook_on_wake(self, **kwargs):
        self.on_squid_woke()

    def _hook_on_sleep(self, **kwargs):
        pass  # Sleep achievement triggers on wake

    def _hook_on_neurogenesis(self, **kwargs):
        self.on_neuron_created()

    def _hook_on_clean(self, **kwargs):
        self.on_tank_cleaned()

    def _hook_on_medicine(self, **kwargs):
        self.on_medicine_given()

    def _hook_on_rock_pickup(self, **kwargs):
        self.on_rock_picked_up()

    def _hook_on_rock_throw(self, **kwargs):
        self.on_rock_thrown()

    def _hook_on_decoration_interaction(self, **kwargs):
        decoration = kwargs.get('decoration')
        interaction_type = kwargs.get('type', 'push')
        self.on_decoration_interacted(decoration, interaction_type)

    def _hook_on_ink_cloud(self, **kwargs):
        self.on_ink_cloud_released()

    def _hook_on_startle(self, **kwargs):
        self.on_squid_startled()

    def _hook_on_memory_created(self, **kwargs):
        self.on_memory_formed()

    def _hook_on_memory_to_long_term(self, **kwargs):
        self.on_memory_promoted()

    def _hook_on_curiosity_change(self, **kwargs):
        new_value = kwargs.get('new_value', 0)
        if new_value >= 100:
            self.unlock_achievement("curiosity_100")

    def _hook_on_anxiety_change(self, **kwargs):
        new_value = kwargs.get('new_value', 0)
        if new_value >= 100:
            self.unlock_achievement("nervous_wreck")
        # Track for zen_master
        if new_value < 10:
            if self.anxiety_low_since is None:
                self.anxiety_low_since = time.time()
        else:
            self.anxiety_low_since = None

    def _hook_on_speed_change(self, **kwargs):
        speed = kwargs.get('speed', 1)
        max_speed = kwargs.get('max_speed', 4)
        if speed >= max_speed:
            if self.max_speed_since is None:
                self.max_speed_since = time.time()
        else:
            self.max_speed_since = None

    # ----------------------------------------------------------
    # Event Handlers
    # ----------------------------------------------------------

    def on_squid_fed(self):
        self._increment_stat("times_fed")
        count = self.statistics.get("times_fed", 0)
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
        if count >= 100:
            self.unlock_achievement("neurons_100")
        self._update_progress("neurons_10", count)
        self._update_progress("neurons_50", count)
        self._update_progress("neurons_100", count)

    def on_neuron_leveled(self):
        self._increment_stat("neurons_leveled")
        if self.statistics.get("neurons_leveled", 0) == 1:
            self.unlock_achievement("first_neuron_levelup")

    def on_poop_thrown(self):
        self._increment_stat("poops_thrown")
        if self.statistics.get("poops_thrown", 0) == 1:
            self.unlock_achievement("first_poop_throw")

    def on_tank_cleaned(self):
        self._increment_stat("times_cleaned")
        count = self.statistics.get("times_cleaned", 0)
        if count == 1:
            self.unlock_achievement("first_clean")
        if count >= 25:
            self.unlock_achievement("cleaned_25_times")
        self._update_progress("cleaned_25_times", count)

    def on_medicine_given(self):
        self._increment_stat("times_medicated")
        count = self.statistics.get("times_medicated", 0)
        if count == 1:
            self.unlock_achievement("first_medicine")
        if count >= 10:
            self.unlock_achievement("medicine_10_times")
        self._update_progress("medicine_10_times", count)
        
        # Check for comeback_kid - track if health was critical before medicine
        if self.health_was_critical and self.squid:
            health = getattr(self.squid, 'health', 100)
            if health >= 100:
                self.unlock_achievement("comeback_kid")
                self.health_was_critical = False

    def on_rock_picked_up(self):
        self._increment_stat("rocks_picked")
        count = self.statistics.get("rocks_picked", 0)
        if count == 1:
            self.unlock_achievement("first_rock_pickup")
        if count >= 10:
            self.unlock_achievement("rocks_picked_10")
        if count >= 50:
            self.unlock_achievement("rocks_picked_50")
        self._update_progress("rocks_picked_10", count)
        self._update_progress("rocks_picked_50", count)
        # Also count as object investigated
        self._on_object_investigated()

    def on_rock_thrown(self):
        self._increment_stat("rocks_thrown")
        count = self.statistics.get("rocks_thrown", 0)
        if count == 1:
            self.unlock_achievement("first_rock_throw")
        if count >= 25:
            self.unlock_achievement("rocks_thrown_25")
        if count >= 100:
            self.unlock_achievement("rocks_thrown_100")
        self._update_progress("rocks_thrown_25", count)
        self._update_progress("rocks_thrown_100", count)

    def on_decoration_interacted(self, decoration=None, interaction_type='push'):
        """Handle decoration interactions (push, investigate, etc.)"""
        # Track push interactions
        if interaction_type == 'push':
            self._increment_stat("decorations_pushed")
            count = self.statistics.get("decorations_pushed", 0)
            if count == 1:
                self.unlock_achievement("first_decoration_push")
            if count >= 10:
                self.unlock_achievement("decorations_pushed_10")
            if count >= 50:
                self.unlock_achievement("decorations_pushed_50")
            self._update_progress("decorations_pushed_10", count)
            self._update_progress("decorations_pushed_50", count)
        
        # Track plant-specific interactions
        if decoration and hasattr(decoration, 'category'):
            if decoration.category == 'plant':
                self._increment_stat("plants_interacted")
                count = self.statistics.get("plants_interacted", 0)
                if count == 1:
                    self.unlock_achievement("first_plant_interact")
                if count >= 10:
                    self.unlock_achievement("plants_interacted_10")
                if count >= 50:
                    self.unlock_achievement("plants_interacted_50")
                self._update_progress("plants_interacted_10", count)
                self._update_progress("plants_interacted_50", count)
        
        # Count as object investigated
        self._on_object_investigated()

    def _on_object_investigated(self):
        """Track unique object investigations"""
        self._increment_stat("objects_investigated")
        count = self.statistics.get("objects_investigated", 0)
        if count >= 25:
            self.unlock_achievement("objects_investigated_25")
        if count >= 100:
            self.unlock_achievement("objects_investigated_100")
        self._update_progress("objects_investigated_25", count)
        self._update_progress("objects_investigated_100", count)

    def on_ink_cloud_released(self):
        self._increment_stat("ink_clouds")
        count = self.statistics.get("ink_clouds", 0)
        if count == 1:
            self.unlock_achievement("first_ink_cloud")
        if count >= 20:
            self.unlock_achievement("ink_clouds_20")
        self._update_progress("ink_clouds_20", count)

    def on_squid_startled(self):
        self._increment_stat("times_startled")
        if self.statistics.get("times_startled", 0) == 1:
            self.unlock_achievement("first_startle")

    def on_memory_formed(self):
        self._increment_stat("memories_formed")
        count = self.statistics.get("memories_formed", 0)
        if count == 1:
            self.unlock_achievement("first_memory")
        if count >= 50:
            self.unlock_achievement("memories_50")
        self._update_progress("memories_50", count)

    def on_memory_promoted(self):
        self._increment_stat("memories_promoted")
        if self.statistics.get("memories_promoted", 0) == 1:
            self.unlock_achievement("memory_long_term")

    def on_brain_tool_opened(self):
        """Called when brain visualization is opened"""
        if "brain_surgeon" not in self.unlocked:
            self.unlock_achievement("brain_surgeon")

    # ----------------------------------------------------------
    # Periodic Checks
    # ----------------------------------------------------------

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
        if age_hours >= 168:  # 1 week
            self.unlock_achievement("age_1_week")
        if age_hours >= 720:  # 30 days
            self.unlock_achievement("age_1_month")

        # Time-of-day achievements
        hour = datetime.now().hour
        if 0 <= hour < 4:
            self.unlock_achievement("night_owl")
        if 5 <= hour < 7:
            self.unlock_achievement("early_bird")
        
        # Weekend warrior
        day = datetime.now().weekday()
        if day == 5:  # Saturday
            self.weekend_saturday = True
        elif day == 6:  # Sunday
            self.weekend_sunday = True
        if self.weekend_saturday and self.weekend_sunday:
            self.unlock_achievement("weekend_warrior")

    def _check_stat_achievements(self):
        if not self.squid:
            return
        
        # Happiness
        if hasattr(self.squid, 'happiness') and self.squid.happiness >= 100:
            self.unlock_achievement("happiness_100")

        # All stats high
        stats = ['happiness', 'hunger', 'energy', 'health']
        all_high = all(getattr(self.squid, s, 0) >= 80 for s in stats if hasattr(self.squid, s))
        if all_high:
            self.unlock_achievement("all_stats_high")
        
        # Check health for comeback_kid tracking
        if hasattr(self.squid, 'health'):
            if self.squid.health < 20:
                self.health_was_critical = True
            elif self.squid.health >= 100 and self.health_was_critical:
                self.unlock_achievement("comeback_kid")
                self.health_was_critical = False
        
        # Cleanliness tracking for germaphobe
        if hasattr(self.squid, 'cleanliness'):
            if self.squid.cleanliness >= 90:
                if self.cleanliness_high_since is None:
                    self.cleanliness_high_since = time.time()
                elif time.time() - self.cleanliness_high_since >= 3600:  # 1 hour
                    self.unlock_achievement("germaphobe")
            else:
                self.cleanliness_high_since = None
        
        # Anxiety tracking for zen_master
        if hasattr(self.squid, 'anxiety'):
            if self.squid.anxiety < 10:
                if self.anxiety_low_since is None:
                    self.anxiety_low_since = time.time()
                elif time.time() - self.anxiety_low_since >= 1800:  # 30 minutes
                    self.unlock_achievement("zen_master")
            else:
                self.anxiety_low_since = None
        
        # Speed demon check
        if self.max_speed_since is not None:
            if time.time() - self.max_speed_since >= 600:  # 10 minutes
                self.unlock_achievement("speed_demon")
        
        # Completionist check
        unlocked_count = len(self.unlocked)
        if "completionist" not in self.unlocked and unlocked_count >= 30:
            self.unlock_achievement("completionist")

    # ----------------------------------------------------------
    # Core Methods
    # ----------------------------------------------------------

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
            "cleaned": self.on_tank_cleaned,
            "medicine": self.on_medicine_given,
            "rock_pickup": self.on_rock_picked_up,
            "rock_throw": self.on_rock_thrown,
            "ink_cloud": self.on_ink_cloud_released,
            "startle": self.on_squid_startled,
            "memory_formed": self.on_memory_formed,
            "memory_promoted": self.on_memory_promoted,
            "brain_opened": self.on_brain_tool_opened,
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

    # ----------------------------------------------------------
    # Notifications
    # ----------------------------------------------------------

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
            x = geo.x() + DisplayScaling.scale(20)
            y = geo.y() + DisplayScaling.scale(20)
            self.current_notification.move(x, y)

        self.current_notification.show_notification()

        if self.notification_queue:
            self.notification_timer.start(4500)  # Slightly longer for reading description

    # ----------------------------------------------------------
    # Timers & Hooks Setup
    # ----------------------------------------------------------

    def _setup_timers(self):
        self.age_check_timer = QtCore.QTimer()
        self.age_check_timer.timeout.connect(self._check_age_achievements)

        self.stat_check_timer = QtCore.QTimer()
        self.stat_check_timer.timeout.connect(self._check_stat_achievements)

        self.notification_timer = QtCore.QTimer()
        self.notification_timer.timeout.connect(self._show_next_notification)

    def _install_hooks(self):
        """Hook into game events via method wrapping"""
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
                plugin_self = self
                
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

            # Hook push_decoration on squid
            if hasattr(self.squid, 'push_decoration') and 'push_decoration' not in self._original_methods:
                self._original_methods['push_decoration'] = self.squid.push_decoration
                original_push = self._original_methods['push_decoration']
                plugin_self = self
                
                def hooked_push(decoration, direction):
                    result = original_push(decoration, direction)
                    try:
                        plugin_self.on_decoration_interacted(decoration, 'push')
                    except Exception as e:
                        if plugin_self.logger:
                            plugin_self.logger.error(f"Error in on_decoration_interacted: {e}")
                    return result
                
                self.squid.push_decoration = hooked_push
                hooks_installed.append('push_decoration')

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
            if 'push_decoration' in self._original_methods and self.squid:
                self.squid.push_decoration = self._original_methods['push_decoration']
        except:
            pass
        self._original_methods.clear()

    # ----------------------------------------------------------
    # Enable / Disable / Shutdown
    # ----------------------------------------------------------

    def enable(self) -> bool:
        if self.logger:
            self.logger.info(f"{PLUGIN_NAME} enable() called. is_setup={self.is_setup}")
        
        if not self.age_check_timer:
            self._setup_timers()
        
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid'):
            if self.squid != self.tamagotchi_logic.squid:
                self.squid = self.tamagotchi_logic.squid
                self._install_hooks()
                if self.logger:
                    self.logger.info(f"Re-acquired squid reference and reinstalled hooks")

        if self.age_check_timer and not self.age_check_timer.isActive():
            self.age_check_timer.start(60000)
                
        if self.stat_check_timer and not self.stat_check_timer.isActive():
            self.stat_check_timer.start(5000)

        if self.logger:
            self.logger.info(f"{PLUGIN_NAME} enabled successfully")
        return True

    def disable(self):
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
        self.disable()
        self._uninstall_hooks()

    # ----------------------------------------------------------
    # Persistence
    # ----------------------------------------------------------

    def _get_save_path(self) -> str:
        os.makedirs("saves", exist_ok=True)
        return os.path.join("saves", "achievements.json")

    def get_save_data(self) -> dict:
        return {
            "unlocked": {k: v.to_dict() for k, v in self.unlocked.items()},
            "progress": self.progress,
            "statistics": self.statistics,
            "tracking": {
                "weekend_saturday": self.weekend_saturday,
                "weekend_sunday": self.weekend_sunday,
            }
        }

    def load_save_data(self, data: dict):
        if not data:
            return
        for aid, adata in data.get("unlocked", {}).items():
            self.unlocked[aid] = UnlockedAchievement.from_dict(adata)
        self.progress = data.get("progress", {})
        self.statistics = data.get("statistics", {})
        tracking = data.get("tracking", {})
        self.weekend_saturday = tracking.get("weekend_saturday", False)
        self.weekend_sunday = tracking.get("weekend_sunday", False)

    # ----------------------------------------------------------
    # UI
    # ----------------------------------------------------------

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
    plugin_key = PLUGIN_NAME.lower()

    if plugin_key in plugin_manager.plugins:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.warning(f"{PLUGIN_NAME} is already registered. Skipping re-registration.")
        return True  # Already initialized, no error

    try:
        instance = AchievementsPlugin()

        plugin_manager.plugins[plugin_key] = {
            'name': plugin_key,
            'original_name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'author': PLUGIN_AUTHOR,
            'description': PLUGIN_DESCRIPTION,
            'requires': PLUGIN_REQUIRES,
            'instance': instance,
            'is_setup': False,
        }

        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.info(f"{PLUGIN_NAME} v{PLUGIN_VERSION} initialized")

        return True

    except Exception as e:
        if hasattr(plugin_manager, 'logger'):
            plugin_manager.logger.error(f"Failed to initialize {PLUGIN_NAME}: {e}")
        return False