from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt

class DebugWindow(QtWidgets.QWidget):
    def __init__(self, tamagotchi_logic, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        self.tamagotchi_logic = tamagotchi_logic
        self.setWindowTitle("Debug Information")
        self.setGeometry(100, 100, 600, 500)
        
        self.setup_ui()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_debug_info)
        self.timer.start(1000)  # Update every second

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        
        # Tab widget for different debug sections
        self.tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Squid Status Tab
        self.squid_tab = QtWidgets.QWidget()
        self.setup_squid_tab()
        self.tab_widget.addTab(self.squid_tab, "Squid Status")
        
        # Environment Tab
        self.env_tab = QtWidgets.QWidget()
        self.setup_env_tab()
        self.tab_widget.addTab(self.env_tab, "Environment")
        
        # Brain Tab
        self.brain_tab = QtWidgets.QWidget()
        self.setup_brain_tab()
        self.tab_widget.addTab(self.brain_tab, "Brain State")
        
        # Controls
        self.controls_group = QtWidgets.QGroupBox("Debug Controls")
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.freeze_btn = QtWidgets.QPushButton("Freeze Simulation")
        self.freeze_btn.setCheckable(True)
        self.freeze_btn.toggled.connect(self.toggle_freeze)
        
        self.reset_btn = QtWidgets.QPushButton("Reset Position")
        self.reset_btn.clicked.connect(self.reset_squid_position)
        
        controls_layout.addWidget(self.freeze_btn)
        controls_layout.addWidget(self.reset_btn)
        self.controls_group.setLayout(controls_layout)
        layout.addWidget(self.controls_group)

    def setup_squid_tab(self):
        layout = QtWidgets.QFormLayout(self.squid_tab)
        
        # Basic Info
        self.pos_label = QtWidgets.QLabel()
        self.direction_label = QtWidgets.QLabel()
        self.status_label = QtWidgets.QLabel()
        self.personality_label = QtWidgets.QLabel()
        
        # Needs
        self.hunger_label = QtWidgets.QLabel()
        self.happiness_label = QtWidgets.QLabel()
        self.cleanliness_label = QtWidgets.QLabel()
        self.sleepiness_label = QtWidgets.QLabel()
        self.health_label = QtWidgets.QLabel()
        
        # Mental States
        self.satisfaction_label = QtWidgets.QLabel()
        self.anxiety_label = QtWidgets.QLabel()
        self.curiosity_label = QtWidgets.QLabel()
        
        layout.addRow("Position:", self.pos_label)
        layout.addRow("Direction:", self.direction_label)
        layout.addRow("Status:", self.status_label)
        layout.addRow("Personality:", self.personality_label)
        layout.addRow(QtWidgets.QLabel("<hr>"))
        layout.addRow("Hunger:", self.hunger_label)
        layout.addRow("Happiness:", self.happiness_label)
        layout.addRow("Cleanliness:", self.cleanliness_label)
        layout.addRow("Sleepiness:", self.sleepiness_label)
        layout.addRow("Health:", self.health_label)
        layout.addRow(QtWidgets.QLabel("<hr>"))
        layout.addRow("Satisfaction:", self.satisfaction_label)
        layout.addRow("Anxiety:", self.anxiety_label)
        layout.addRow("Curiosity:", self.curiosity_label)

    def setup_env_tab(self):
        layout = QtWidgets.QFormLayout(self.env_tab)
        
        self.food_count_label = QtWidgets.QLabel()
        self.poop_count_label = QtWidgets.QLabel()
        self.decoration_count_label = QtWidgets.QLabel()
        self.speed_label = QtWidgets.QLabel()
        self.points_label = QtWidgets.QLabel()
        
        layout.addRow("Food Items:", self.food_count_label)
        layout.addRow("Poop Items:", self.poop_count_label)
        layout.addRow("Decorations:", self.decoration_count_label)
        layout.addRow("Simulation Speed:", self.speed_label)
        layout.addRow("Points:", self.points_label)

    def setup_brain_tab(self):
        layout = QtWidgets.QFormLayout(self.brain_tab)
        
        self.neurogenesis_label = QtWidgets.QLabel()
        self.thought_label = QtWidgets.QLabel()
        self.memory_count_label = QtWidgets.QLabel()
        
        layout.addRow("Neurogenesis Triggers:", self.neurogenesis_label)
        layout.addRow("Current Thought:", self.thought_label)
        layout.addRow("Memory Count:", self.memory_count_label)

    def update_debug_info(self):
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return
            
        squid = self.tamagotchi_logic.squid
        
        # Squid Status Tab
        self.pos_label.setText(f"({squid.squid_x}, {squid.squid_y})")
        self.direction_label.setText(squid.squid_direction)
        self.status_label.setText(squid.status)
        self.personality_label.setText(squid.personality.value)
        
        self.hunger_label.setText(f"{squid.hunger:.1f}")
        self.happiness_label.setText(f"{squid.happiness:.1f}")
        self.cleanliness_label.setText(f"{squid.cleanliness:.1f}")
        self.sleepiness_label.setText(f"{squid.sleepiness:.1f}")
        self.health_label.setText(f"{squid.health:.1f}")
        
        self.satisfaction_label.setText(f"{squid.satisfaction:.1f}")
        self.anxiety_label.setText(f"{squid.anxiety:.1f}")
        self.curiosity_label.setText(f"{squid.curiosity:.1f}")
        
        # Environment Tab
        self.food_count_label.setText(str(len(self.tamagotchi_logic.food_items)))
        self.poop_count_label.setText(str(len(self.tamagotchi_logic.poop_items)))
        self.decoration_count_label.setText(str(len([i for i in self.tamagotchi_logic.user_interface.scene.items() 
                                                    if isinstance(i, ResizablePixmapItem)])))
        self.speed_label.setText(f"{self.tamagotchi_logic.simulation_speed}x")
        self.points_label.setText(str(self.tamagotchi_logic.points))
        
        # Brain Tab
        if hasattr(self.tamagotchi_logic, 'neurogenesis_triggers'):
            triggers = self.tamagotchi_logic.neurogenesis_triggers
            self.neurogenesis_label.setText(
                f"Novelty: {triggers['novel_objects']:.1f} | "
                f"Stress: {triggers['high_stress_cycles']:.1f} | "
                f"Rewards: {triggers['positive_outcomes']:.1f}"
            )
        
        if hasattr(self.tamagotchi_logic, 'brain_window') and self.tamagotchi_logic.brain_window:
            thoughts = self.tamagotchi_logic.brain_window.thoughts_text.toPlainText()
            if thoughts:
                last_thought = thoughts.split('\n')[-2] if len(thoughts.split('\n')) > 1 else "No recent thoughts"
                self.thought_label.setText(last_thought[:100] + "..." if len(last_thought) > 100 else last_thought)
            
            if hasattr(squid, 'memory_manager'):
                st_mem = len(squid.memory_manager.get_all_short_term_memories())
                lt_mem = len(squid.memory_manager.get_all_long_term_memories())
                self.memory_count_label.setText(f"Short-term: {st_mem} | Long-term: {lt_mem}")

    def toggle_freeze(self, frozen):
        if frozen:
            self.tamagotchi_logic.set_simulation_speed(0)
            self.freeze_btn.setText("Unfreeze Simulation")
        else:
            self.tamagotchi_logic.set_simulation_speed(1)
            self.freeze_btn.setText("Freeze Simulation")

    def reset_squid_position(self):
        if self.tamagotchi_logic and self.tamagotchi_logic.squid:
            self.tamagotchi_logic.squid.squid_x = self.tamagotchi_logic.squid.center_x
            self.tamagotchi_logic.squid.squid_y = self.tamagotchi_logic.squid.center_y
            self.tamagotchi_logic.squid.squid_item.setPos(
                self.tamagotchi_logic.squid.squid_x, 
                self.tamagotchi_logic.squid.squid_y
            )

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()