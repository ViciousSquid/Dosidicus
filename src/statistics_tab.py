from PyQt5 import QtWidgets, QtCore

class StatisticsTab(QtWidgets.QWidget):
    def __init__(self, tamagotchi_logic, parent=None):
        super().__init__(parent)
        self.tamagotchi_logic = tamagotchi_logic
        self.init_ui()

    def set_tamagotchi_logic(self, tamagotchi_logic):
        """Update the reference to the main logic controller."""
        self.tamagotchi_logic = tamagotchi_logic

    def init_ui(self):
        layout = QtWidgets.QFormLayout(self)
        self.stats_labels = {
            # General
            "Squid Age": QtWidgets.QLabel("N/A"),
            "Distance Swam": QtWidgets.QLabel("N/A"),
            "Time Asleep": QtWidgets.QLabel("N/A"),
            # Consumption
            "Sushi Consumed": QtWidgets.QLabel("N/A"),
            "Cheese Consumed": QtWidgets.QLabel("N/A"),
            # Mental State Peaks
            "Highest Anxiety": QtWidgets.QLabel("N/A"),
            "Lowest Happiness": QtWidgets.QLabel("N/A"),
            # Interactions
            "Rocks Thrown": QtWidgets.QLabel("N/A"),
            "Environment Interactions": QtWidgets.QLabel("N/A"),
            "Other Squids Encountered": QtWidgets.QLabel("N/A"),
            # Memory
            "Total Memories": QtWidgets.QLabel("N/A"),
            # --- MODIFIED & NEW NEUROGENESIS STATS ---
            "Peak Novelty Trigger": QtWidgets.QLabel("N/A"),
            "Peak Stress Trigger": QtWidgets.QLabel("N/A"),
            "Peak Reward Trigger": QtWidgets.QLabel("N/A"),
        }

        for label_text, label_widget in self.stats_labels.items():
            layout.addRow(QtWidgets.QLabel(f"<b>{label_text}:</b>"), label_widget)

        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_stats)
        self.update_timer.start(1000)

    def start_updates(self):
        """Start the timer to periodically update stats."""
        if not self.update_timer.isActive():
            self.update_timer.start(2000)

    def stop_updates(self):
        """Stop the timer to prevent stats from updating."""
        self.update_timer.stop()

    def update_stats(self):
        if self.tamagotchi_logic and self.tamagotchi_logic.squid and hasattr(self.tamagotchi_logic.squid, 'stats'):
            stats = self.tamagotchi_logic.squid.stats
            self.stats_labels["Squid Age"].setText(stats.get_squid_age())
            self.stats_labels["Distance Swam"].setText(str(stats.distance_swam))
            self.stats_labels["Sushi Consumed"].setText(str(stats.sushi_consumed))
            self.stats_labels["Cheese Consumed"].setText(str(stats.cheese_consumed))
            self.stats_labels["Time Asleep"].setText(stats.get_sleep_time())
            self.stats_labels["Total Memories"].setText(str(len(self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()) + len(self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories())))
            self.stats_labels["Highest Anxiety"].setText(f"{stats.highest_anxiety:.2f}")
            self.stats_labels["Lowest Happiness"].setText(f"{stats.lowest_happiness:.2f}")
            self.stats_labels["Rocks Thrown"].setText(str(stats.total_rocks_thrown))
            self.stats_labels["Environment Interactions"].setText(str(stats.total_env_interactions))
            # --- Get new peak values from stats object and round them ---
            self.stats_labels["Peak Novelty Trigger"].setText(str(round(stats.peak_novelty)))
            self.stats_labels["Peak Stress Trigger"].setText(str(round(stats.peak_stress)))
            self.stats_labels["Peak Reward Trigger"].setText(str(round(stats.peak_reward)))