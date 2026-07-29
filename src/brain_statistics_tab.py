from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling
from .localisation import Localisation
from .squid_statistics import DEFAULT_NEURON_COUNT
import time

class StatisticsTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()

        # Statistics tracking
        self.statistics = {
            'distance_swam': 0,
            'cheese_eaten': 0,
            'sushi_eaten': 0,
            'poops_created': 0,
            'max_poops_cleaned': 0,
            'startles_experienced': 0,
            'ink_clouds_created': 0,
            'times_colour_changed': 0,
            'rocks_thrown': 0,
            'plants_interacted': 0,
            'total_sleep_time': 0,
            'sickness_episodes': 0,
            'novelty_neurons_created': 0,
            'stress_neurons_created': 0,
            'reward_neurons_created': 0,
            'current_neurons': DEFAULT_NEURON_COUNT,
            'squid_age_minutes': 0,
            'last_position': None,
            'last_update_time': time.time()
        }

        # Load existing statistics if available
        self.load_statistics()

        # Setup update timer
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_statistics)
        self.update_timer.start(1000)  # Update every second

        self.is_visible = False

    def showEvent(self, event):
        """Called when tab becomes visible"""
        super().showEvent(event)
        self.is_visible = True
        self._sync_from_squid_statistics()
        self.update_display()

    def hideEvent(self, event):
        """Called when tab becomes hidden"""
        super().hideEvent(event)
        self.is_visible = False

    def set_logic(self, logic):
        """Called by main window after TamagotchiLogic (and squid) exist."""
        self.tamagotchi_logic = logic
        self._sync_from_squid_statistics()
        self.update_display()

    def _sync_from_squid_statistics(self):
        """Mirror the persistent squid statistics object into the tab state."""
        if not self.tamagotchi_logic or not getattr(self.tamagotchi_logic, 'squid', None):
            return

        squid = self.tamagotchi_logic.squid
        squid_stats = getattr(squid, 'statistics', None)
        if not squid_stats:
            return

        self.statistics['distance_swam'] = getattr(squid_stats, 'distance_swam', self.statistics['distance_swam'])
        self.statistics['cheese_eaten'] = getattr(squid_stats, 'cheese_consumed', self.statistics['cheese_eaten'])
        self.statistics['sushi_eaten'] = getattr(squid_stats, 'sushi_consumed', self.statistics['sushi_eaten'])
        self.statistics['poops_created'] = getattr(squid_stats, 'poops_created', self.statistics['poops_created'])
        self.statistics['max_poops_cleaned'] = getattr(squid_stats, 'max_poops_cleaned', self.statistics['max_poops_cleaned'])
        self.statistics['startles_experienced'] = getattr(squid_stats, 'startles_experienced', self.statistics['startles_experienced'])
        self.statistics['ink_clouds_created'] = getattr(squid_stats, 'ink_clouds_created', self.statistics['ink_clouds_created'])
        self.statistics['times_colour_changed'] = getattr(squid_stats, 'times_colour_changed', self.statistics['times_colour_changed'])
        self.statistics['rocks_thrown'] = getattr(squid_stats, 'total_rocks_thrown', self.statistics['rocks_thrown'])
        self.statistics['plants_interacted'] = getattr(squid_stats, 'plants_interacted', self.statistics['plants_interacted'])
        self.statistics['total_sleep_time'] = getattr(squid_stats, 'time_spent_asleep', self.statistics['total_sleep_time'])
        self.statistics['sickness_episodes'] = getattr(squid_stats, 'sickness_episodes', self.statistics['sickness_episodes'])
        self.statistics['novelty_neurons_created'] = getattr(squid_stats, 'novelty_neurons_created', self.statistics['novelty_neurons_created'])
        self.statistics['stress_neurons_created'] = getattr(squid_stats, 'stress_neurons_created', self.statistics['stress_neurons_created'])
        self.statistics['reward_neurons_created'] = getattr(squid_stats, 'reward_neurons_created', self.statistics['reward_neurons_created'])
        self.statistics['current_neurons'] = getattr(squid_stats, 'max_neurons_reached', self.statistics['current_neurons'])
        self.statistics['squid_age_minutes'] = int(getattr(squid_stats, 'get_total_age_seconds', lambda: 0)() // 60)

    def _increment_squid_stat(self, stat_name, amount=1):
        """Increment the canonical squid statistics attribute for a tab stat key."""
        if not self.tamagotchi_logic or not getattr(self.tamagotchi_logic, 'squid', None):
            return False

        squid_stats = getattr(self.tamagotchi_logic.squid, 'statistics', None)
        if not squid_stats:
            return False

        return squid_stats.increment(stat_name, amount)

    def track_distance(self, distance):
        """Forward a movement event to the canonical model."""
        if self.tamagotchi_logic and getattr(self.tamagotchi_logic, 'squid', None):
            squid_stats = getattr(self.tamagotchi_logic.squid, 'statistics', None)
            if squid_stats:
                squid_stats.add_distance(distance)
                self._sync_from_squid_statistics()
                if self.is_visible:
                    self.update_display()

    def initialize_ui(self):
        """Build the statistics tab interface with DPI scaling"""
        loc = Localisation.instance()
        
        self.layout.setContentsMargins(
            DisplayScaling.scale(15),
            DisplayScaling.scale(15),
            DisplayScaling.scale(15),
            DisplayScaling.scale(15),
        )
        self.layout.setSpacing(DisplayScaling.scale(10))

        title_label = QtWidgets.QLabel("")
        title_font = QtGui.QFont()
        title_font.setPointSize(DisplayScaling.font_size(12))
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")
        self.layout.addWidget(title_label)

        stats_container = QtWidgets.QWidget()
        stats_container.setObjectName("statsContainer")
        stats_container.setStyleSheet(
            """
            #statsContainer {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 10px;
            }
            """
        )
        stats_layout = QtWidgets.QFormLayout(stats_container)
        stats_layout.setSpacing(DisplayScaling.scale(10))

        stat_items = [
            ('squid_age_minutes', loc.get('stat_squid_age')),
            ('distance_swam', loc.get('stat_distance')),
            ('cheese_eaten', loc.get('stat_cheese')),
            ('sushi_eaten', loc.get('stat_sushi')),
            ('poops_created', loc.get('stat_poops')),
            ('max_poops_cleaned', loc.get('stat_max_poops')),
            ('startles_experienced', loc.get('stat_startles')),
            ('ink_clouds_created', loc.get('stat_ink')),
            ('times_colour_changed', loc.get('stat_colour_change')),
            ('rocks_thrown', loc.get('stat_rocks')),
            ('plants_interacted', loc.get('stat_plants')),
            ('total_sleep_time', loc.get('stat_sleep')),
            ('sickness_episodes', loc.get('stat_sickness')),
            ('novelty_neurons_created', loc.get('stat_novelty_neurons')),
            ('stress_neurons_created', loc.get('stat_stress_neurons')),
            ('reward_neurons_created', loc.get('stat_reward_neurons')),
            ('current_neurons', "Max neurons"),
        ]

        if not hasattr(self, 'stat_labels'):
            self.stat_labels = {}

        for key, label in stat_items:
            if key not in self.stat_labels:
                lbl = QtWidgets.QLabel(f"{label}:")
                font = QtGui.QFont()
                font.setPointSize(DisplayScaling.font_size(10))
                lbl.setFont(font)

                val = QtWidgets.QLabel("0")
                val_font = QtGui.QFont()
                val_font.setPointSize(DisplayScaling.font_size(12))
                val_font.setBold(True)
                val.setFont(val_font)
                val.setStyleSheet("color: #495057;")

                self.stat_labels[key] = val
                stats_layout.addRow(lbl, val)

        self.layout.addWidget(stats_container)
        self.layout.addStretch()

    def update_from_brain_state(self, state):
        """Refresh the read-only mirror after a brain-state update."""
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return

        self._sync_from_squid_statistics()
        self.update_display()

    def update_statistics(self):
        """Refresh the UI from the canonical squid statistics model."""
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return

        self._sync_from_squid_statistics()
        self.statistics['last_update_time'] = time.time()
        self.update_display()

    def update_display(self):
        """Update the statistics display"""
        for key, label in self.stat_labels.items():
            if key == 'distance_swam':
                if (self.tamagotchi_logic and 
                    self.tamagotchi_logic.squid and 
                    hasattr(self.tamagotchi_logic.squid, 'statistics')):
                    distance_str = self.tamagotchi_logic.squid.statistics.get_distance_display()
                    label.setText(distance_str)
                else:
                    value = self.statistics.get(key, 0)
                    label.setText(f"{int(value):,}")
            elif key == 'total_sleep_time':
                value = self.statistics.get(key, 0)
                label.setText(f"{int(value)}")
            else:
                value = self.statistics.get(key, 0)
                label.setText(str(int(value)))

    def increment_stat(self, stat_name, amount=1):
        """Forward a discrete event to the canonical model."""
        if not self._increment_squid_stat(stat_name, amount):
            return

        self._sync_from_squid_statistics()
        self.update_display()

    def reset_statistics(self):
        """Reset all statistics to zero"""
        loc = Localisation.instance()
        reply = QtWidgets.QMessageBox.question(
            self, loc.get("reset_stats_title"), 
            loc.get("reset_stats_msg"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            if self.tamagotchi_logic and getattr(self.tamagotchi_logic, 'squid', None):
                squid_stats = getattr(self.tamagotchi_logic.squid, 'statistics', None)
                if squid_stats:
                    squid_stats.reset()
                    self.tamagotchi_logic.refresh_neuron_count()
                    self._sync_from_squid_statistics()
                    self.update_display()

    def export_statistics(self):
        """Export statistics to a file"""
        loc = Localisation.instance()
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, loc.get("export_stats_title"), "", loc.get("export_file_type")
        )

        if file_name:
            try:
                with open(file_name, 'w') as f:
                    f.write(f"{loc.get('export_header')}\n")
                    f.write("=" * 30 + "\n")
                    from datetime import datetime
                    export_time = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"{loc.get('export_time')}: {export_time}\n\n")

                    f.write(f"{loc.get('export_activity_section')}:\n")
                    f.write(f"{loc.get('stat_distance')}: {int(self.statistics['distance_swam'])}\n")
                    f.write(f"{loc.get('stat_cheese')}: {self.statistics['cheese_eaten']}\n")
                    f.write(f"{loc.get('stat_sushi')}: {self.statistics['sushi_eaten']}\n")
                    f.write(f"{loc.get('stat_poops')}: {self.statistics['poops_created']}\n")
                    f.write(f"{loc.get('stat_max_poops')}: {self.statistics['max_poops_cleaned']}\n")
                    f.write(f"{loc.get('stat_rocks')}: {self.statistics['rocks_thrown']}\n")
                    f.write(f"{loc.get('stat_plants')}: {self.statistics['plants_interacted']}\n")
                    f.write(f"{loc.get('stat_startles')}: {self.statistics['startles_experienced']}\n")
                    f.write(f"{loc.get('stat_sleep')}: {int(self.statistics['total_sleep_time'])}\n")
                    f.write(f"{loc.get('stat_sickness')}: {self.statistics['sickness_episodes']}\n")
                    f.write(f"{loc.get('stat_squid_age')}: {int(self.statistics['squid_age_minutes'])}\n")
                    f.write(
                        "Max Neurons: "
                        f"{self.statistics.get('current_neurons', DEFAULT_NEURON_COUNT)}\n"
                    )
                    f.write("\n" + "=" * 30 + "\n")
                    f.write(f"{loc.get('export_end')}\n")

                QtWidgets.QMessageBox.information(
                    self, loc.get("export_success_title"), 
                    loc.get("export_success_msg", file_name=file_name)
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, loc.get("export_error_title"), 
                    loc.get("export_error_msg", error=str(e))
                )

    def save_statistics(self):
        """Compatibility hook; the main save pipeline persists the model."""
        self._sync_from_squid_statistics()

    def load_statistics(self):
        """Compatibility hook; the main load pipeline restores the model."""
        self._sync_from_squid_statistics()
