from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling
from .localisation import Localisation
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
            'current_neurons': 7,
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
        self.pending_distance = 0  # Store distance when tab not visible

        # Connect to neuron creation events for real-time updates
        if self.brain_widget and hasattr(self.brain_widget, 'neuronCreated'):
            self.brain_widget.neuronCreated.connect(self._on_neuron_created_update_stats)

    def showEvent(self, event):
        """Called when tab becomes visible"""
        super().showEvent(event)
        self.is_visible = True
        # Apply any pending distance
        if self.pending_distance > 0:
            self.statistics['distance_swam'] += self.pending_distance
            self.pending_distance = 0
            self.update_display()

    def hideEvent(self, event):
        """Called when tab becomes hidden"""
        super().hideEvent(event)
        self.is_visible = False

    def set_logic(self, logic):
        """Called by main window after TamagotchiLogic (and squid) exist."""
        self.tamagotchi_logic = logic

    def update_current_neurons(self, count):
        """Update the current neuron count in the UI, enforcing only-count-up logic."""
        if hasattr(self, 'stat_labels') and 'current_neurons' in self.stat_labels:
            # Check if new count is higher than stored max
            current_max = self.statistics.get('current_neurons', 0)
            if count > current_max:
                self.statistics['current_neurons'] = count
                self.stat_labels['current_neurons'].setText(str(count))

    def _on_neuron_created_update_stats(self, neuron_name: str):
        """Update current neuron count when a new neuron is created"""
        self.update_statistics()

    def track_distance(self, distance):
        """Track distance swam - only updates if tab is visible"""
        if self.is_visible:
            self.statistics['distance_swam'] += distance
            self.update_display()
        else:
            # Accumulate distance when not visible
            self.pending_distance += distance

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

        # Title with DPI scaling
        title_label = QtWidgets.QLabel("")
        title_font = QtGui.QFont()
        title_font.setPointSize(DisplayScaling.font_size(12))
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50;")
        self.layout.addWidget(title_label)

        # Statistics container
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

        # Master list of every statistic we want to show (using localized strings)
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
            ('current_neurons', "Max neurons"),  # UPDATED LABEL
        ]

        # Ensure the label dictionary exists
        if not hasattr(self, 'stat_labels'):
            self.stat_labels = {}

        # Build / rebuild every row so new keys always appear
        for key, label in stat_items:
            if key not in self.stat_labels:               # row not built yet
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
        """Update tab based on brain state"""
        # This method is called when brain state changes
        # We can use this to track state-dependent statistics
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return
            
        squid = self.tamagotchi_logic.squid
        
        # Track position changes for distance
        current_pos = (squid.squid_x, squid.squid_y)
        if self.statistics['last_position'] is not None:
            last_pos = self.statistics['last_position']
            distance = ((current_pos[0] - last_pos[0])**2 + (current_pos[1] - last_pos[1])**2)**0.5
            self.statistics['distance_swam'] += distance
            
        self.statistics['last_position'] = current_pos
        
        # Track sleep time
        if squid.is_sleeping:
            current_time = time.time()
            time_elapsed = current_time - self.statistics['last_update_time']
            self.statistics['total_sleep_time'] += time_elapsed
            
        self.statistics['last_update_time'] = time.time()
        
        # Update the display
        self.update_display()

    def update_statistics(self):
        """Update statistics from squid state"""
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return

        squid = self.tamagotchi_logic.squid

        # --- FIX: ROBUST NEURON COUNT SYNC ---
        # Ensure we have a valid brain_widget reference
        if not self.brain_widget:
            # Attempt to find it from parent if possible (common in some architectures)
            parent = self.parent()
            if hasattr(parent, 'brain_widget'):
                self.brain_widget = parent.brain_widget

        # Pull count directly from widget if available
        if self.brain_widget and hasattr(self.brain_widget, 'neuron_positions'):
            real_current_count = len(self.brain_widget.neuron_positions)
            stored_count = self.statistics.get('current_neurons', 0)
            
            # If the actual count in the brain is higher than our stats record, update it
            if real_current_count > stored_count:
                self.statistics['current_neurons'] = real_current_count
                
                # Also update the persistent squid statistics object if it exists
                if hasattr(squid, 'statistics') and hasattr(squid.statistics, 'max_neurons_reached'):
                    if real_current_count > squid.statistics.max_neurons_reached:
                         squid.statistics.max_neurons_reached = real_current_count
                         squid.statistics.current_neurons = real_current_count

        # Track sleep time
        if squid.is_sleeping:
            time_elapsed = time.time() - self.statistics['last_update_time']
            self.statistics['total_sleep_time'] += time_elapsed
        self.statistics['last_update_time'] = time.time()

        # Track sickness episodes
        if squid.is_sick and not getattr(self, '_was_sick', False):
            self.statistics['sickness_episodes'] += 1
            self._was_sick = True
        elif not squid.is_sick:
            self._was_sick = False

        # Track startles
        if hasattr(squid, 'tamagotchi_logic') and squid.tamagotchi_logic:
            if hasattr(squid.tamagotchi_logic, 'startle_cooldown'):
                if squid.tamagotchi_logic.startle_cooldown > 0 and not getattr(self, '_was_startled', False):
                    self.statistics['startles_experienced'] += 1
                    self._was_startled = True
                elif squid.tamagotchi_logic.startle_cooldown == 0:
                    self._was_startled = False

        self.update_display()

    def update_display(self):
        """Update the statistics display"""
        for key, label in self.stat_labels.items():
            # Special handling for distance with rollover multiplier
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
        """Increment a specific statistic"""
        if stat_name in self.statistics:
            self.statistics[stat_name] += amount
            self.update_display()
            self.save_statistics()

    def reset_statistics(self):
        """Reset all statistics to zero"""
        loc = Localisation.instance()
        reply = QtWidgets.QMessageBox.question(
            self, loc.get("reset_stats_title"), 
            loc.get("reset_stats_msg"),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            for key in self.statistics:
                if key not in ['last_position', 'last_update_time']:
                    self.statistics[key] = 0
            self.statistics['last_update_time'] = time.time()
            self.update_display()
            self.save_statistics()

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
                    f.write(f"Max Neurons: {self.statistics.get('current_neurons', 7)}\n")
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
        """Save statistics to file"""
        if hasattr(self.tamagotchi_logic, 'save_manager'):
            try:
                self.tamagotchi_logic.save_manager.save_statistics(self.statistics)
            except:
                pass  # Fail silently if save not available

    def load_statistics(self):
        """Load statistics from file"""
        if hasattr(self.tamagotchi_logic, 'save_manager'):
            try:
                loaded_stats = self.tamagotchi_logic.save_manager.load_statistics()
                if loaded_stats:
                    self.statistics.update(loaded_stats)
            except:
                pass  # Use defaults if load fails