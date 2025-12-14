# preferences.py
import os
import sys
import glob
from PyQt5 import QtWidgets, QtCore, QtGui
from .config_manager import ConfigManager
from .localisation import Localization
from .display_scaling import DisplayScaling
import zipfile

# Define the path to the ZIP file - must match localisation.py
ZIP_FILENAME = "languages.zip"

class PreferencesWindow(QtWidgets.QDialog):
    """Floating preferences window for Dosidicus configuration"""
    
    # NOTE: The LANGUAGE_MAP is now only used for displaying the name in the preferences window
    # if the localisation system failed to provide a name.
    LANGUAGE_MAP = {
        'en': 'English',
        'es': 'Spanish (Español)',
        'fr': 'French (Français)',
        # Add any other widely expected languages here for display purposes
        'de': 'German (Deutsch)',
        'pl': 'Polish (Polski)',
        'uk': 'Ukrainian (Українська)',
        'zh': 'Chinese (中文)',
        'ja': 'Japanese (日本語)',
        'pt': 'Portuguese (Português)',
        'cy': 'Welsh (Cymraeg)',
        'ga': 'Irish (Gaeilge)',
        'gen_z': 'Gen Z Slang',
    }

    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        
        # Ensure scaling is initialized based on the screen this window is on
        screen = QtWidgets.QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        # Re-initialize scaling to ensure context is correct for this window creation
        DisplayScaling.initialize(screen_geometry.width(), screen_geometry.height())
        
        self.setWindowTitle("Preferences")
        self.setModal(False)
        
        # Scale the initial window size
        w = DisplayScaling.scale(900)
        h = DisplayScaling.scale(800)
        self.resize(w, h)
        
        # Center on screen
        x = (screen_geometry.width() - self.width()) // 2
        y = (screen_geometry.height() - self.height()) // 2
        self.move(x, y)
        
        # Load config manager (use same instance if available)
        self.config_manager = ConfigManager()
        
        # Track if changes were made
        self.changes_made = False
        self.original_values = {}
        
        # Apply styles first (no dependencies)
        self._apply_styles()
        
        # Initialize UI components
        self.init_ui()
        
        # Load config values into UI
        self.load_current_config()
        
    def _apply_styles(self):
        """Apply global stylesheet with scaling logic"""
        
        # SIGNIFICANTLY INCREASED BASE SIZES
        base_font = DisplayScaling.font_size(18)    
        header_font = DisplayScaling.font_size(22)  
        small_font = DisplayScaling.font_size(14)   
        
        # Keep Language Huge
        large_font = DisplayScaling.font_size(32)   
        
        # INCREASED SUBTITLE SIZE
        subtitle_font = DisplayScaling.font_size(24) 
        
        padding_std = DisplayScaling.scale(12)      
        padding_lrg = DisplayScaling.scale(20)
        radius = DisplayScaling.scale(8)
        border_width = max(1, DisplayScaling.scale(2))
        
        # =====================================================================
        # DEVELOPER: ADJUST THE VALUE BELOW TO CHANGE TOP TAB WIDTH
        # =====================================================================
        tab_min_width = DisplayScaling.scale(150)
        
        css = f"""
            QWidget {{
                font-size: {base_font}px;
                color: #2c3e50;
            }}
            
            /* Headers and Labels */
            QLabel {{
                font-size: {base_font}px;
            }}
            
            /* Group Boxes */
            QGroupBox {{
                font-weight: bold;
                font-size: {header_font}px;
                border: {border_width}px solid #bdc3c7;
                border-radius: {radius}px;
                margin-top: {DisplayScaling.scale(30)}px;
                padding-top: {DisplayScaling.scale(15)}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {DisplayScaling.scale(15)}px;
                padding: 0 {DisplayScaling.scale(8)}px;
                color: #34495e;
            }}
            
            /* Tabs */
            QTabWidget::pane {{
                border: {border_width}px solid #bdc3c7;
                background: #fdfdfd;
                border-radius: {radius}px;
            }}
            QTabBar::tab {{
                background: #ecf0f1;
                color: #2c3e50;
                font-size: {base_font}px;
                padding: {padding_std}px {padding_lrg}px;
                border-top-left-radius: {radius}px;
                border-top-right-radius: {radius}px;
                margin-right: {DisplayScaling.scale(4)}px;
                font-weight: bold;
                min-width: {tab_min_width}px; /* WIDER TABS APPLIED HERE */
                alignment: center;
            }}
            QTabBar::tab:selected {{
                background: #003366; /* Dark Blue */
                color: white;        /* White Text */
            }}
            QTabBar::tab:hover:!selected {{
                background: #bdc3c7;
            }}

            /* Inputs and Buttons */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                padding: {DisplayScaling.scale(8)}px;
                border: {border_width}px solid #bdc3c7;
                border-radius: {DisplayScaling.scale(6)}px;
                background: white;
                min-height: {DisplayScaling.scale(40)}px;
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: #ecf0f1;
                border: {border_width}px solid #bdc3c7;
                border-radius: {radius}px;
                padding: {padding_std}px {padding_lrg}px;
                min-height: {DisplayScaling.scale(45)}px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #dfe6e9;
            }}
            QPushButton:pressed {{
                background-color: #b2bec3;
            }}
            
            /* The Save Button */
            QPushButton#SaveButton {{
                background-color: #27ae60;
                color: white;
                font-size: {header_font}px;
            }}
            QPushButton#SaveButton:disabled {{
                background-color: #95a5a6;
            }}
            
            /* ESPECIALLY LARGE LANGUAGE SELECTION */
            QComboBox#LanguageCombo {{
                font-size: {large_font}px;
                height: {DisplayScaling.scale(80)}px;
                padding: {DisplayScaling.scale(15)}px;
                font-weight: bold;
                background-color: #e8f6f3;
                border: {DisplayScaling.scale(3)}px solid #1abc9c;
                border-radius: {radius}px;
            }}
            QComboBox#LanguageCombo QAbstractItemView {{
                font-size: {large_font}px;
                selection-background-color: #1abc9c;
            }}
            
            /* The Label showing 'en - English' */
            QLabel#LanguageNameLabel {{
                font-size: {subtitle_font}px; /* LARGER FONT */
                color: #34495e;
                font-weight: bold;
                padding-left: {DisplayScaling.scale(5)}px;
                margin-top: {DisplayScaling.scale(10)}px;
            }}
            
            /* Specific helper for description text */
            QLabel#DescriptionLabel {{
                font-size: {small_font}px;
                color: #7f8c8d;
                font-style: italic;
            }}
        """
        self.setStyleSheet(css)

    def _get_available_languages(self):
        """
        Returns a sorted list of language DISPLAY STRINGS (code - name format)
        by asking the localisation system for available languages.
        """
        languages = []
        
        # Get available language codes from localisation
        try:
            lang_codes = Localization.instance().get_available_languages()
            
            # Build display strings with native names
            for code in lang_codes:
                name = Localization.instance().get_language_name(code)
                languages.append(f"{code} - {name}")
                
        except Exception as e:
            print(f"[Preferences] Error getting languages from localisation: {e}")
            
            # Emergency fallback to hardcoded map
            for code, name in self.LANGUAGE_MAP.items():
                languages.append(f"{code} - {name}")
        
        # Sort alphabetically by code, but put 'gen_z' last
        if any(item.startswith('gen_z -') for item in languages):
            languages = [item for item in languages if not item.startswith('gen_z -')]
            sorted_items = sorted(languages)
            gen_z_name = Localization.instance().get_language_name('gen_z', fallback=True)
            sorted_items.append(f"gen_z - {gen_z_name}")
            return sorted_items
        
        return sorted(languages)

    def init_ui(self):
        """Initialize the UI components"""
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(DisplayScaling.scale(20))
        layout.setContentsMargins(
            DisplayScaling.scale(25), 
            DisplayScaling.scale(25), 
            DisplayScaling.scale(25), 
            DisplayScaling.scale(25)
        )
        
        # Create tab widget
        self.tab_widget = QtWidgets.QTabWidget()
        
        # General tab
        self.general_tab = self._create_general_tab()
        self.tab_widget.addTab(self.general_tab, "General")
        
        # Rock Interactions tab
        self.rock_tab = self._create_rock_tab()
        self.tab_widget.addTab(self.rock_tab, "Rock Interactions")
        
        # Neurogenesis tab
        self.neurogenesis_tab = self._create_neurogenesis_tab()
        self.tab_widget.addTab(self.neurogenesis_tab, "Neurogenesis")
        
        # Display tab
        self.display_tab = self._create_display_tab()
        self.tab_widget.addTab(self.display_tab, "Display")
        
        layout.addWidget(self.tab_widget)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(DisplayScaling.scale(15))
        button_layout.addStretch()
        
        self.save_button = QtWidgets.QPushButton("Save & Restart")
        self.save_button.setObjectName("SaveButton") # ID for styling
        self.save_button.clicked.connect(self.save_and_restart)
        self.save_button.setEnabled(False)
        
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def _create_general_tab(self):
        """Create General settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout() 
        layout.setSpacing(DisplayScaling.scale(25))
        layout.setContentsMargins(DisplayScaling.scale(40), DisplayScaling.scale(40), DisplayScaling.scale(40), DisplayScaling.scale(40))
        
        # Language Label
        lang_label = QtWidgets.QLabel("Interface Language:")
        layout.addWidget(lang_label)
        
        # Language dropdown - Styled via CSS #LanguageCombo
        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.setObjectName("LanguageCombo") 
        
        # POPULATE USING NEW SCANNING METHOD (.py files)
        available_langs = self._get_available_languages()
        self.language_combo.addItems(available_langs)
        
        # Connect change signal
        self.language_combo.currentTextChanged.connect(self._on_change)
        
        layout.addWidget(self.language_combo)
        
        # Add description
        desc_label = QtWidgets.QLabel("Requires restart to take effect")
        desc_label.setObjectName("DescriptionLabel") # Styled specifically smaller
        layout.addWidget(desc_label)
        
        layout.addStretch() 
        widget.setLayout(layout)
        return widget

    def _create_rock_tab(self):
        """Create Rock Interactions settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(DisplayScaling.scale(20))
        layout.setContentsMargins(DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25))
        
        # Probabilities (0-1)
        self.rock_pickup_prob = QtWidgets.QDoubleSpinBox()
        self.rock_pickup_prob.setRange(0.0, 1.0)
        self.rock_pickup_prob.setSingleStep(0.1)
        self.rock_pickup_prob.setDecimals(2)
        self.rock_pickup_prob.valueChanged.connect(self._on_change)
        layout.addRow("Pickup Probability:", self.rock_pickup_prob)
        
        self.rock_throw_prob = QtWidgets.QDoubleSpinBox()
        self.rock_throw_prob.setRange(0.0, 1.0)
        self.rock_throw_prob.setSingleStep(0.1)
        self.rock_throw_prob.setDecimals(2)
        self.rock_throw_prob.valueChanged.connect(self._on_change)
        layout.addRow("Throw Probability:", self.rock_throw_prob)
        
        # Durations
        self.rock_min_carry = QtWidgets.QDoubleSpinBox()
        self.rock_min_carry.setRange(0.5, 30.0)
        self.rock_min_carry.setSingleStep(0.5)
        self.rock_min_carry.setSuffix(" sec")
        self.rock_min_carry.valueChanged.connect(self._on_change)
        layout.addRow("Min Carry Duration:", self.rock_min_carry)
        
        self.rock_max_carry = QtWidgets.QDoubleSpinBox()
        self.rock_max_carry.setRange(1.0, 60.0)
        self.rock_max_carry.setSingleStep(0.5)
        self.rock_max_carry.setSuffix(" sec")
        self.rock_max_carry.valueChanged.connect(self._on_change)
        layout.addRow("Max Carry Duration:", self.rock_max_carry)
        
        self.rock_cooldown = QtWidgets.QDoubleSpinBox()
        self.rock_cooldown.setRange(0.0, 60.0)
        self.rock_cooldown.setSingleStep(1.0)
        self.rock_cooldown.setSuffix(" sec")
        self.rock_cooldown.valueChanged.connect(self._on_change)
        layout.addRow("Cooldown After Throw:", self.rock_cooldown)
        
        # Stat effects
        self.rock_happiness_boost = QtWidgets.QSpinBox()
        self.rock_happiness_boost.setRange(0, 100)
        self.rock_happiness_boost.valueChanged.connect(self._on_change)
        layout.addRow("Happiness Boost:", self.rock_happiness_boost)
        
        self.rock_satisfaction_boost = QtWidgets.QSpinBox()
        self.rock_satisfaction_boost.setRange(0, 100)
        self.rock_satisfaction_boost.valueChanged.connect(self._on_change)
        layout.addRow("Satisfaction Boost:", self.rock_satisfaction_boost)
        
        self.rock_anxiety_reduction = QtWidgets.QSpinBox()
        self.rock_anxiety_reduction.setRange(0, 100)
        self.rock_anxiety_reduction.valueChanged.connect(self._on_change)
        layout.addRow("Anxiety Reduction:", self.rock_anxiety_reduction)
        
        # Memory
        self.rock_memory_decay = QtWidgets.QDoubleSpinBox()
        self.rock_memory_decay.setRange(0.0, 1.0)
        self.rock_memory_decay.setSingleStep(0.05)
        self.rock_memory_decay.valueChanged.connect(self._on_change)
        layout.addRow("Memory Decay Rate:", self.rock_memory_decay)
        
        self.rock_max_memories = QtWidgets.QSpinBox()
        self.rock_max_memories.setRange(1, 20)
        self.rock_max_memories.valueChanged.connect(self._on_change)
        layout.addRow("Max Rock Memories:", self.rock_max_memories)
        
        widget.setLayout(layout)
        return widget
    
    def _create_neurogenesis_tab(self):
        """Create Neurogenesis settings tab with sub-tabs"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.setSpacing(DisplayScaling.scale(20))
        layout.setContentsMargins(DisplayScaling.scale(20), DisplayScaling.scale(20), DisplayScaling.scale(20), DisplayScaling.scale(20))
        
        # Enable checkbox
        self.neurogenesis_enabled = QtWidgets.QCheckBox("Enable Neurogenesis")
        self.neurogenesis_enabled.stateChanged.connect(self._on_change)
        layout.addWidget(self.neurogenesis_enabled)
        
        # Showmanship checkbox
        self.showmanship_enabled = QtWidgets.QCheckBox("Enable Showmanship (Dramatic neuron creation)")
        self.showmanship_enabled.stateChanged.connect(self._on_change)
        layout.addWidget(self.showmanship_enabled)
        
        # Sub-tabs
        sub_tabs = QtWidgets.QTabWidget()
        
        # General sub-tab
        general_subtab = self._create_neurogenesis_general()
        sub_tabs.addTab(general_subtab, "General")
        
        # Triggers sub-tab
        triggers_subtab = self._create_neurogenesis_triggers()
        sub_tabs.addTab(triggers_subtab, "Triggers")
        
        # Appearance sub-tab
        appearance_subtab = self._create_neurogenesis_appearance()
        sub_tabs.addTab(appearance_subtab, "Appearance")
        
        layout.addWidget(sub_tabs)
        widget.setLayout(layout)
        return widget
    
    def _create_neurogenesis_general(self):
        """Create Neurogenesis General sub-tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(DisplayScaling.scale(20))
        layout.setContentsMargins(DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25))
        
        # Cooldowns
        self.neuro_cooldown = QtWidgets.QDoubleSpinBox()
        self.neuro_cooldown.setRange(30.0, 600.0)
        self.neuro_cooldown.setSingleStep(30.0)
        self.neuro_cooldown.setSuffix(" sec")
        self.neuro_cooldown.valueChanged.connect(self._on_change)
        layout.addRow("Global Cooldown:", self.neuro_cooldown)
        
        self.neuro_per_type_cooldown = QtWidgets.QDoubleSpinBox()
        self.neuro_per_type_cooldown.setRange(10.0, 120.0)
        self.neuro_per_type_cooldown.setSingleStep(10.0)
        self.neuro_per_type_cooldown.setSuffix(" sec")
        self.neuro_per_type_cooldown.valueChanged.connect(self._on_change)
        layout.addRow("Per-Type Cooldown:", self.neuro_per_type_cooldown)
        
        # Max neurons
        self.neuro_max_neurons = QtWidgets.QSpinBox()
        self.neuro_max_neurons.setRange(10, 100)
        self.neuro_max_neurons.valueChanged.connect(self._on_change)
        layout.addRow("Max Neurons:", self.neuro_max_neurons)
        
        # Initial neuron count
        self.neuro_initial_count = QtWidgets.QSpinBox()
        self.neuro_initial_count.setRange(5, 20)
        self.neuro_initial_count.valueChanged.connect(self._on_change)
        layout.addRow("Initial Neuron Count:", self.neuro_initial_count)

        # --- Positioning & Physics Group ---
        pos_group = QtWidgets.QGroupBox("Positioning & Physics")
        pos_layout = QtWidgets.QFormLayout()
        pos_layout.setSpacing(DisplayScaling.scale(15))
        
        self.random_start_pos = QtWidgets.QCheckBox("Randomize Start Positions")
        self.random_start_pos.stateChanged.connect(self._on_change)
        pos_layout.addRow(self.random_start_pos)
        
        self.force_bounds = QtWidgets.QCheckBox("Enforce Canvas Bounds")
        self.force_bounds.stateChanged.connect(self._on_change)
        pos_layout.addRow(self.force_bounds)
        
        self.canvas_padding = QtWidgets.QSpinBox()
        self.canvas_padding.setRange(0, 300)
        self.canvas_padding.setSingleStep(10)
        self.canvas_padding.setSuffix(" px")
        self.canvas_padding.valueChanged.connect(self._on_change)
        pos_layout.addRow("Canvas Padding:", self.canvas_padding)
        
        self.centering_force = QtWidgets.QDoubleSpinBox()
        self.centering_force.setRange(0.0, 0.5)
        self.centering_force.setSingleStep(0.01)
        self.centering_force.setDecimals(3)
        self.centering_force.valueChanged.connect(self._on_change)
        pos_layout.addRow("Centering Force:", self.centering_force)
        
        pos_group.setLayout(pos_layout)
        layout.addRow(pos_group)
        
        widget.setLayout(layout)
        return widget
    
    def _create_neurogenesis_triggers(self):
        """Create Neurogenesis Triggers sub-tab"""
        widget = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setSpacing(DisplayScaling.scale(20))
        
        # Scroll area for smaller screens if needed
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setSpacing(DisplayScaling.scale(25))
        
        # Novelty trigger
        novelty_group = QtWidgets.QGroupBox("Novelty Trigger")
        novelty_layout = QtWidgets.QFormLayout()
        novelty_layout.setSpacing(DisplayScaling.scale(15))
        
        self.novelty_enabled = QtWidgets.QCheckBox("Enabled")
        self.novelty_enabled.stateChanged.connect(self._on_change)
        novelty_layout.addRow(self.novelty_enabled)
        
        self.novelty_threshold = QtWidgets.QDoubleSpinBox()
        self.novelty_threshold.setRange(0.5, 10.0)
        self.novelty_threshold.setSingleStep(0.5)
        self.novelty_threshold.valueChanged.connect(self._on_change)
        novelty_layout.addRow("Threshold:", self.novelty_threshold)
        
        self.novelty_decay = QtWidgets.QDoubleSpinBox()
        self.novelty_decay.setRange(0.0, 1.0)
        self.novelty_decay.setSingleStep(0.05)
        self.novelty_decay.valueChanged.connect(self._on_change)
        novelty_layout.addRow("Decay Rate:", self.novelty_decay)
        
        novelty_group.setLayout(novelty_layout)
        content_layout.addWidget(novelty_group)
        
        # Stress trigger
        stress_group = QtWidgets.QGroupBox("Stress Trigger")
        stress_layout = QtWidgets.QFormLayout()
        stress_layout.setSpacing(DisplayScaling.scale(15))
        
        self.stress_enabled = QtWidgets.QCheckBox("Enabled")
        self.stress_enabled.stateChanged.connect(self._on_change)
        stress_layout.addRow(self.stress_enabled)
        
        self.stress_threshold = QtWidgets.QDoubleSpinBox()
        self.stress_threshold.setRange(0.5, 10.0)
        self.stress_threshold.setSingleStep(0.5)
        self.stress_threshold.valueChanged.connect(self._on_change)
        stress_layout.addRow("Threshold:", self.stress_threshold)
        
        self.stress_decay = QtWidgets.QDoubleSpinBox()
        self.stress_decay.setRange(0.0, 1.0)
        self.stress_decay.setSingleStep(0.05)
        self.stress_decay.valueChanged.connect(self._on_change)
        stress_layout.addRow("Decay Rate:", self.stress_decay)
        
        stress_group.setLayout(stress_layout)
        content_layout.addWidget(stress_group)
        
        # Reward trigger
        reward_group = QtWidgets.QGroupBox("Reward Trigger")
        reward_layout = QtWidgets.QFormLayout()
        reward_layout.setSpacing(DisplayScaling.scale(15))
        
        self.reward_enabled = QtWidgets.QCheckBox("Enabled")
        self.reward_enabled.stateChanged.connect(self._on_change)
        reward_layout.addRow(self.reward_enabled)
        
        self.reward_threshold = QtWidgets.QDoubleSpinBox()
        self.reward_threshold.setRange(0.5, 10.0)
        self.reward_threshold.setSingleStep(0.5)
        self.reward_threshold.valueChanged.connect(self._on_change)
        reward_layout.addRow("Threshold:", self.reward_threshold)
        
        self.reward_decay = QtWidgets.QDoubleSpinBox()
        self.reward_decay.setRange(0.0, 1.0)
        self.reward_decay.setSingleStep(0.05)
        self.reward_decay.valueChanged.connect(self._on_change)
        reward_layout.addRow("Decay Rate:", self.reward_decay)
        
        reward_group.setLayout(reward_layout)
        content_layout.addWidget(reward_group)
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
        widget.setLayout(main_layout)
        return widget
    
    def _create_neurogenesis_appearance(self):
        """Create Neurogenesis Appearance sub-tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(DisplayScaling.scale(20))
        layout.setContentsMargins(DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25))
        
        # Colors for each type
        self.novelty_color = self._create_color_button()
        self.novelty_color.clicked.connect(self._on_change)
        layout.addRow("Novelty Color:", self.novelty_color)
        
        self.stress_color = self._create_color_button()
        self.stress_color.clicked.connect(self._on_change)
        layout.addRow("Stress Color:", self.stress_color)
        
        self.reward_color = self._create_color_button()
        self.reward_color.clicked.connect(self._on_change)
        layout.addRow("Reward Color:", self.reward_color)
        
        # Visual effects
        self.highlight_duration = QtWidgets.QDoubleSpinBox()
        self.highlight_duration.setRange(1.0, 20.0)
        self.highlight_duration.setSingleStep(0.5)
        self.highlight_duration.setSuffix(" sec")
        self.highlight_duration.valueChanged.connect(self._on_change)
        layout.addRow("Highlight Duration:", self.highlight_duration)
        
        self.pulse_effect = QtWidgets.QCheckBox("Enable Pulse Effect")
        self.pulse_effect.stateChanged.connect(self._on_change)
        layout.addRow(self.pulse_effect)
        
        widget.setLayout(layout)
        return widget
    
    def _create_color_button(self):
        """Create a color picker button"""
        button = QtWidgets.QPushButton()
        # Scale the color button size
        size = DisplayScaling.scale(40) # Larger color buttons
        button.setFixedSize(size * 2, size)
        button.setStyleSheet("background-color: white; border: 1px solid gray;")
        button.clicked.connect(self._pick_color)
        return button
    
    def _pick_color(self):
        """Open color picker dialog"""
        button = self.sender()
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")
            self._on_change()
    
    def _create_display_tab(self):
        """Create Display settings tab"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(DisplayScaling.scale(20))
        layout.setContentsMargins(DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25), DisplayScaling.scale(25))
        
        # Neuron settings
        self.neuron_radius = QtWidgets.QSpinBox()
        self.neuron_radius.setRange(10, 50)
        self.neuron_radius.valueChanged.connect(self._on_change)
        layout.addRow("Neuron Radius:", self.neuron_radius)
        
        self.neuron_font_size = QtWidgets.QSpinBox()
        self.neuron_font_size.setRange(6, 20)
        self.neuron_font_size.valueChanged.connect(self._on_change)
        layout.addRow("Neuron Label Size:", self.neuron_font_size)
        
        # Connection settings
        self.connection_width = QtWidgets.QDoubleSpinBox()
        self.connection_width.setRange(0.5, 5.0)
        self.connection_width.setSingleStep(0.1)
        self.connection_width.valueChanged.connect(self._on_change)
        layout.addRow("Line Width:", self.connection_width)
        
        # Button settings
        self.button_font_size = QtWidgets.QSpinBox()
        self.button_font_size.setRange(10, 24)
        self.button_font_size.valueChanged.connect(self._on_change)
        layout.addRow("Button Font Size:", self.button_font_size)
        
        self.button_width = QtWidgets.QSpinBox()
        self.button_width.setRange(80, 200)
        self.button_width.valueChanged.connect(self._on_change)
        layout.addRow("Button Width:", self.button_width)
        
        self.button_height = QtWidgets.QSpinBox()
        self.button_height.setRange(30, 80)
        self.button_height.valueChanged.connect(self._on_change)
        layout.addRow("Button Height:", self.button_height)
        
        self.button_spacing = QtWidgets.QSpinBox()
        self.button_spacing.setRange(10, 50)
        self.button_spacing.valueChanged.connect(self._on_change)
        layout.addRow("Button Spacing:", self.button_spacing)
        
        widget.setLayout(layout)
        return widget
    
    def _on_change(self):
        """Mark that changes have been made"""
        self.changes_made = True
        self.save_button.setEnabled(True)
    
    def load_current_config(self):
        """Load current config values into UI"""
        # General
        current_lang = self.config_manager.get_language()
        
        # Find and set the matching language display string
        for i in range(self.language_combo.count()):
            item_text = self.language_combo.itemText(i)
            if item_text.startswith(f"{current_lang} -"):
                self.language_combo.setCurrentIndex(i)
                break
        
        # Rock config
        rock_config = self.config_manager.get_rock_config()
        self.rock_pickup_prob.setValue(rock_config['pickup_prob'])
        self.rock_throw_prob.setValue(rock_config['throw_prob'])
        self.rock_min_carry.setValue(rock_config['min_carry_duration'])
        self.rock_max_carry.setValue(rock_config['max_carry_duration'])
        self.rock_cooldown.setValue(rock_config['cooldown_after_throw'])
        self.rock_happiness_boost.setValue(rock_config['happiness_boost'])
        self.rock_satisfaction_boost.setValue(rock_config['satisfaction_boost'])
        self.rock_anxiety_reduction.setValue(rock_config['anxiety_reduction'])
        self.rock_memory_decay.setValue(rock_config['memory_decay_rate'])
        self.rock_max_memories.setValue(rock_config['max_rock_memories'])
        
        # Neurogenesis config
        neuro_config = self.config_manager.get_neurogenesis_config()
        self.neurogenesis_enabled.setChecked(neuro_config['general']['enabled'])
        self.showmanship_enabled.setChecked(neuro_config['general']['showmanship'])
        self.neuro_cooldown.setValue(neuro_config['general']['cooldown'])
        self.neuro_per_type_cooldown.setValue(neuro_config['general']['per_type_cooldown'])
        self.neuro_max_neurons.setValue(neuro_config['general']['max_neurons'])
        self.neuro_initial_count.setValue(neuro_config['general']['initial_neuron_count'])
        
        # Load Positioning & Physics (Directly from raw config for new properties)
        raw_config = self.config_manager.config
        sec_props = 'Neurogenesis.NeuronProperties'
        
        self.random_start_pos.setChecked(raw_config.getboolean(sec_props, 'randomize_start_positions', fallback=True))
        self.force_bounds.setChecked(raw_config.getboolean(sec_props, 'force_bounds', fallback=True))
        self.canvas_padding.setValue(raw_config.getint(sec_props, 'canvas_padding', fallback=60))
        self.centering_force.setValue(raw_config.getfloat(sec_props, 'centering_force', fallback=0.02))

        # Triggers
        self.novelty_enabled.setChecked(neuro_config['triggers']['novelty']['enabled'])
        self.novelty_threshold.setValue(neuro_config['triggers']['novelty']['threshold'])
        self.novelty_decay.setValue(neuro_config['triggers']['novelty']['decay_rate'])
        
        self.stress_enabled.setChecked(neuro_config['triggers']['stress']['enabled'])
        self.stress_threshold.setValue(neuro_config['triggers']['stress']['threshold'])
        self.stress_decay.setValue(neuro_config['triggers']['stress']['decay_rate'])
        
        self.reward_enabled.setChecked(neuro_config['triggers']['reward']['enabled'])
        self.reward_threshold.setValue(neuro_config['triggers']['reward']['threshold'])
        self.reward_decay.setValue(neuro_config['triggers']['reward']['decay_rate'])
        
        # Appearance
        self._set_color_button(self.novelty_color, neuro_config['appearance']['colors']['novelty'])
        self._set_color_button(self.stress_color, neuro_config['appearance']['colors']['stress'])
        self._set_color_button(self.reward_color, neuro_config['appearance']['colors']['reward'])
        self.highlight_duration.setValue(neuro_config['visual_effects']['highlight_duration'])
        self.pulse_effect.setChecked(neuro_config['visual_effects']['pulse_effect'])
        
        # Display
        display_config = self.config_manager.get_display_config()
        self.neuron_radius.setValue(display_config['neuron_radius'])
        self.neuron_font_size.setValue(display_config['neuron_label_font_size'])
        self.connection_width.setValue(display_config['connection_line_width'])
        self.button_font_size.setValue(display_config['button_font_size'])
        self.button_width.setValue(display_config['button_width'])
        self.button_height.setValue(display_config['button_height'])
        self.button_spacing.setValue(display_config['button_spacing'])
        
        # Reset changes flag
        self.changes_made = False
    
    def _set_color_button(self, button, rgb_list):
        """Set color button background from RGB list"""
        color = QtGui.QColor(*rgb_list)
        button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")
    
    def save_and_restart(self):
        """Save configuration and prompt for restart"""
        # Save all settings
        self._save_all_settings()
        
        # Show restart prompt
        reply = QtWidgets.QMessageBox.question(
            self,
            "Restart Required",
            "Configuration saved successfully!\n\nA restart is required for changes to take effect.\n\nWould you like to restart the application now?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self._restart_application()
        else:
            self.close()
    
    def _save_all_settings(self):
        """Save all settings to config.ini"""
        # General
        if not self.config_manager.config.has_section('General'):
            self.config_manager.config.add_section('General')
        
        # EXTRACT language code from display string
        selected_lang_display = self.language_combo.currentText()
        language_code = selected_lang_display.split(' - ')[0]
        self.config_manager.config.set('General', 'language', language_code)
        
        # Rock Interactions
        if not self.config_manager.config.has_section('RockInteractions'):
            self.config_manager.config.add_section('RockInteractions')
        self.config_manager.config.set('RockInteractions', 'pickup_probability', str(self.rock_pickup_prob.value()))
        self.config_manager.config.set('RockInteractions', 'throw_probability', str(self.rock_throw_prob.value()))
        self.config_manager.config.set('RockInteractions', 'min_carry_duration', str(self.rock_min_carry.value()))
        self.config_manager.config.set('RockInteractions', 'max_carry_duration', str(self.rock_max_carry.value()))
        self.config_manager.config.set('RockInteractions', 'cooldown_after_throw', str(self.rock_cooldown.value()))
        self.config_manager.config.set('RockInteractions', 'happiness_boost', str(self.rock_happiness_boost.value()))
        self.config_manager.config.set('RockInteractions', 'satisfaction_boost', str(self.rock_satisfaction_boost.value()))
        self.config_manager.config.set('RockInteractions', 'anxiety_reduction', str(self.rock_anxiety_reduction.value()))
        self.config_manager.config.set('RockInteractions', 'memory_decay_rate', str(self.rock_memory_decay.value()))
        self.config_manager.config.set('RockInteractions', 'max_rock_memories', str(self.rock_max_memories.value()))
        
        # Neurogenesis
        if not self.config_manager.config.has_section('Neurogenesis'):
            self.config_manager.config.add_section('Neurogenesis')
        self.config_manager.config.set('Neurogenesis', 'enabled', str(self.neurogenesis_enabled.isChecked()))
        self.config_manager.config.set('Neurogenesis', 'showmanship', str(self.showmanship_enabled.isChecked()))
        self.config_manager.config.set('Neurogenesis', 'cooldown', str(self.neuro_cooldown.value()))
        self.config_manager.config.set('Neurogenesis', 'per_type_cooldown', str(self.neuro_per_type_cooldown.value()))
        self.config_manager.config.set('Neurogenesis', 'max_neurons', str(self.neuro_max_neurons.value()))
        self.config_manager.config.set('Neurogenesis', 'initial_neuron_count', str(self.neuro_initial_count.value()))
        
        # Neurogenesis.NeuronProperties (Positioning)
        if not self.config_manager.config.has_section('Neurogenesis.NeuronProperties'):
            self.config_manager.config.add_section('Neurogenesis.NeuronProperties')
            
        self.config_manager.config.set('Neurogenesis.NeuronProperties', 'randomize_start_positions', str(self.random_start_pos.isChecked()))
        self.config_manager.config.set('Neurogenesis.NeuronProperties', 'force_bounds', str(self.force_bounds.isChecked()))
        self.config_manager.config.set('Neurogenesis.NeuronProperties', 'canvas_padding', str(self.canvas_padding.value()))
        self.config_manager.config.set('Neurogenesis.NeuronProperties', 'centering_force', str(self.centering_force.value()))

        # Triggers
        if not self.config_manager.config.has_section('Neurogenesis.Novelty'):
            self.config_manager.config.add_section('Neurogenesis.Novelty')
        self.config_manager.config.set('Neurogenesis.Novelty', 'enabled', str(self.novelty_enabled.isChecked()))
        self.config_manager.config.set('Neurogenesis.Novelty', 'threshold', str(self.novelty_threshold.value()))
        self.config_manager.config.set('Neurogenesis.Novelty', 'decay_rate', str(self.novelty_decay.value()))
        
        if not self.config_manager.config.has_section('Neurogenesis.Stress'):
            self.config_manager.config.add_section('Neurogenesis.Stress')
        self.config_manager.config.set('Neurogenesis.Stress', 'enabled', str(self.stress_enabled.isChecked()))
        self.config_manager.config.set('Neurogenesis.Stress', 'threshold', str(self.stress_threshold.value()))
        self.config_manager.config.set('Neurogenesis.Stress', 'decay_rate', str(self.stress_decay.value()))
        
        if not self.config_manager.config.has_section('Neurogenesis.Reward'):
            self.config_manager.config.add_section('Neurogenesis.Reward')
        self.config_manager.config.set('Neurogenesis.Reward', 'enabled', str(self.reward_enabled.isChecked()))
        self.config_manager.config.set('Neurogenesis.Reward', 'threshold', str(self.reward_threshold.value()))
        self.config_manager.config.set('Neurogenesis.Reward', 'decay_rate', str(self.reward_decay.value()))
        
        # Appearance
        if not self.config_manager.config.has_section('Neurogenesis.Appearance'):
            self.config_manager.config.add_section('Neurogenesis.Appearance')
        self.config_manager.config.set('Neurogenesis.Appearance', 'novelty_color', self._get_color_from_button(self.novelty_color))
        self.config_manager.config.set('Neurogenesis.Appearance', 'stress_color', self._get_color_from_button(self.stress_color))
        self.config_manager.config.set('Neurogenesis.Appearance', 'reward_color', self._get_color_from_button(self.reward_color))
        
        # Visual Effects
        if not self.config_manager.config.has_section('Neurogenesis.VisualEffects'):
            self.config_manager.config.add_section('Neurogenesis.VisualEffects')
        self.config_manager.config.set('Neurogenesis.VisualEffects', 'highlight_duration', str(self.highlight_duration.value()))
        self.config_manager.config.set('Neurogenesis.VisualEffects', 'pulse_effect', str(self.pulse_effect.isChecked()))
        
        # Display
        if not self.config_manager.config.has_section('Display'):
            self.config_manager.config.add_section('Display')
        self.config_manager.config.set('Display', 'neuron_radius', str(self.neuron_radius.value()))
        self.config_manager.config.set('Display', 'neuron_label_font_size', str(self.neuron_font_size.value()))
        self.config_manager.config.set('Display', 'connection_line_width', str(self.connection_width.value()))
        self.config_manager.config.set('Display', 'button_font_size', str(self.button_font_size.value()))
        self.config_manager.config.set('Display', 'button_width', str(self.button_width.value()))
        self.config_manager.config.set('Display', 'button_height', str(self.button_height.value()))
        self.config_manager.config.set('Display', 'button_spacing', str(self.button_spacing.value()))
        
        # Write to file
        self.config_manager._save_config()
    
    def _get_color_from_button(self, button):
        """Extract RGB values from button stylesheet"""
        style = button.styleSheet()
        # Parse background-color from stylesheet
        import re
        match = re.search(r'background-color:\s*#?([0-9a-fA-F]{6})', style)
        if match:
            hex_color = match.group(1)
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r},{g},{b}"
        return "255,255,255"
    
    def _restart_application(self):
        """Restart the application"""
        # Close current window
        if hasattr(self, 'parent') and self.parent():
            self.parent().close()
        
        # Restart process
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            QtCore.QProcess.startDetached(sys.executable, [])
        else:
            # Running from source
            QtCore.QProcess.startDetached(sys.executable, sys.argv)
        
        # Exit current process
        QtWidgets.QApplication.quit()