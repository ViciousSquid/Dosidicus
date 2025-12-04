# src/brain_statistics_tab.py

from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling
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
            'max_neurons_reached': 0,
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
        """Update the current neuron count in the UI."""
        if hasattr(self, 'stat_labels') and 'current_neurons' in self.stat_labels:
            self.stat_labels['current_neurons'].setText(str(count))

    def track_max_neurons(self, current_count):
        """Track the maximum number of neurons observed."""
        if not hasattr(self, 'max_neurons'):
            self.max_neurons = 0
        self.max_neurons = max(self.max_neurons, current_count)
        if hasattr(self, 'stat_labels') and 'max_neurons_reached' in self.stat_labels:
            self.stat_labels['max_neurons_reached'].setText(str(self.max_neurons))

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

        # Master list of every statistic we want to show
        stat_items = [
            ('squid_age_minutes', 'Squid Age'),
            ('distance_swam', 'Distance Swam (pixels)'),
            ('cheese_eaten', 'Cheese Eaten'),
            ('sushi_eaten', 'Sushi Eaten'),
            ('poops_created', 'Poops Created'),
            ('max_poops_cleaned', 'Max Poops in Tank'),
            ('startles_experienced', 'Times Startled'),
            ('ink_clouds_created', 'Ink Clouds Created'),
            ('times_colour_changed', 'Times Colour Changed'),
            ('rocks_thrown', 'Rocks Thrown'),
            ('plants_interacted', 'Plant Interactions'),
            ('total_sleep_time', 'Total Sleep Time (seconds)'),
            ('sickness_episodes', 'Sickness Episodes'),
            ('novelty_neurons_created', 'Novelty Neurons Created'),
            ('stress_neurons_created', 'Stress Neurons Created'),
            ('reward_neurons_created', 'Reward Neurons Created'),
            ('max_neurons_reached', 'Max Neurons Reached'),
            ('current_neurons', 'Current Neurons'),
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
        
        # Track current and max neurons
        if self.brain_widget and hasattr(self.brain_widget, 'neurons'):
            current_neuron_count = len(self.brain_widget.neurons)
            self.statistics['current_neurons'] = current_neuron_count
            
            # Track maximum neurons ever reached (ignoring pruning)
            if current_neuron_count > self.statistics.get('max_neurons_reached', 0):
                self.statistics['max_neurons_reached'] = current_neuron_count
                
            # Update display labels immediately
            if hasattr(self, 'stat_labels'):
                if 'current_neurons' in self.stat_labels:
                    self.stat_labels['current_neurons'].setText(str(current_neuron_count))
                if 'max_neurons_reached' in self.stat_labels:
                    self.stat_labels['max_neurons_reached'].setText(
                        str(self.statistics['max_neurons_reached'])
                    )

        # ✅ Track sleep time
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
        reply = QtWidgets.QMessageBox.question(
            self, "Reset Statistics", 
            "Are you sure you want to reset all statistics?",
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
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Statistics", "", "Text Files (*.txt)"
        )
        
        if file_name:
            try:
                with open(file_name, 'w') as f:
                    f.write("Squid Statistics Export\n")
                    f.write("=" * 30 + "\n")
                    from datetime import datetime
                    export_time = datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f"Export Time: {export_time}\n\n")
                    
                    f.write("Activity Statistics:\n")
                    f.write(f"Distance Swam: {int(self.statistics['distance_swam'])} pixels\n")
                    f.write(f"Cheese Eaten: {self.statistics['cheese_eaten']}\n")
                    f.write(f"Sushi Eaten: {self.statistics['sushi_eaten']}\n")
                    f.write(f"Poops Created: {self.statistics['poops_created']}\n")
                    f.write(f"Max Poops in Tank: {self.statistics['max_poops_cleaned']}\n")
                    f.write(f"Rocks Thrown: {self.statistics['rocks_thrown']}\n")
                    f.write(f"Plant Interactions: {self.statistics['plants_interacted']}\n")
                    f.write(f"Times Startled: {self.statistics['startles_experienced']}\n")
                    f.write(f"Total Sleep Time: {int(self.statistics['total_sleep_time'])} seconds\n")
                    f.write(f"Sickness Episodes: {self.statistics['sickness_episodes']}\n")
                    f.write(f"Squid Age: {int(self.statistics['squid_age_minutes'])} minutes\n")
                    
                    f.write("\n" + "=" * 30 + "\n")
                    f.write("End of Statistics\n")
                
                QtWidgets.QMessageBox.information(
                    self, "Export Successful", 
                    f"Statistics exported to {file_name}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Export Error", 
                    f"Error exporting statistics: {str(e)}"
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