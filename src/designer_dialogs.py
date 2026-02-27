"""
Sparse Network Generation Dialog

Provides UI for generating random sparse networks with various presets.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QComboBox, QDoubleSpinBox, QCheckBox, QTextEdit, QFrame, QProgressBar,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

from designer_network_generator import SparseNetworkGenerator


class SparseNetworkDialog(QDialog):
    """Dialog for generating sparse neural networks."""
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.generator = SparseNetworkGenerator()
        self.result_connections = []
        self.result_actions = []
        
        self.setWindowTitle("🎲 Generate Sparse Network")
        self.setMinimumWidth(500)
        self.setMinimumHeight(550)
        
        self.setup_ui()
        self.load_preset('balanced')
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Generate Random Neural Connections")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        desc = QLabel(
            "Creates biologically-inspired connections between the 8 required neurons.\n"
            "Each generation is unique due to random noise."
        )
        desc.setStyleSheet("color: #666; font-size: 10pt;")
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        layout.addSpacing(10)
        
        # Preset selection
        preset_group = QGroupBox("Style Preset")
        preset_layout = QHBoxLayout(preset_group)
        
        self.preset_combo = QComboBox()
        presets = self.generator.get_preset_styles()
        for key, info in presets.items():
            self.preset_combo.addItem(info['name'], key)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_changed)
        preset_layout.addWidget(self.preset_combo)
        
        self.preset_desc = QLabel()
        self.preset_desc.setStyleSheet("color: #888; font-style: italic;")
        preset_layout.addWidget(self.preset_desc, stretch=1)
        
        layout.addWidget(preset_group)
        
        # Advanced options
        advanced_group = QGroupBox("Fine Tuning")
        advanced_layout = QVBoxLayout(advanced_group)
        
        # Density & Noise
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Density:"))
        self.density_spin = QDoubleSpinBox()
        self.density_spin.setRange(0.2, 2.0)
        self.density_spin.setSingleStep(0.1)
        self.density_spin.setDecimals(1)
        self.density_spin.setValue(1.0)
        self.density_spin.setToolTip("Lower = fewer connections, Higher = more connections")
        row1.addWidget(self.density_spin)
        
        row1.addSpacing(20)
        
        row1.addWidget(QLabel("Weight Noise:"))
        self.noise_spin = QDoubleSpinBox()
        self.noise_spin.setRange(0.1, 3.0)
        self.noise_spin.setSingleStep(0.1)
        self.noise_spin.setDecimals(1)
        self.noise_spin.setValue(1.0)
        self.noise_spin.setToolTip("How much randomness in connection weights")
        row1.addWidget(self.noise_spin)
        advanced_layout.addLayout(row1)

        # Variance & Sensors (NEW)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Pos Variance:"))
        self.variance_spin = QDoubleSpinBox()
        self.variance_spin.setRange(0.0, 1.0)
        self.variance_spin.setSingleStep(0.1)
        self.variance_spin.setDecimals(2)
        self.variance_spin.setValue(0.0)
        self.variance_spin.setToolTip("Jitter neuron positions (0.0 = fixed, 0.5 = chaotic)")
        row2.addWidget(self.variance_spin)
        
        row2.addSpacing(20)
        
        row2.addWidget(QLabel("Sensor Prob:"))
        self.sensor_prob_spin = QDoubleSpinBox()
        self.sensor_prob_spin.setRange(0.0, 1.0)
        self.sensor_prob_spin.setSingleStep(0.1)
        self.sensor_prob_spin.setDecimals(2)
        self.sensor_prob_spin.setValue(0.0)
        self.sensor_prob_spin.setToolTip("Probability of adding random extra sensors")
        row2.addWidget(self.sensor_prob_spin)
        advanced_layout.addLayout(row2)
        
        # Options row
        options_row = QHBoxLayout()
        
        self.feedback_check = QCheckBox("Include feedback loops")
        self.feedback_check.setChecked(True)
        self.feedback_check.setToolTip("Allow bidirectional connections where biologically plausible")
        options_row.addWidget(self.feedback_check)
        
        self.clear_check = QCheckBox("Clear existing connections")
        self.clear_check.setChecked(True)
        self.clear_check.setToolTip("Remove all existing connections before generating")
        options_row.addWidget(self.clear_check)
        
        options_row.addStretch()
        advanced_layout.addLayout(options_row)
        
        layout.addWidget(advanced_group)
        
        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(150)
        self.preview_text.setStyleSheet("""
            QTextEdit {
                font-family: monospace;
                font-size: 9pt;
                background-color: #f5f5f5;
            }
        """)
        preview_layout.addWidget(self.preview_text)
        
        preview_btn_row = QHBoxLayout()
        self.preview_btn = QPushButton("🔄 Preview Generation")
        self.preview_btn.clicked.connect(self.generate_preview)
        preview_btn_row.addWidget(self.preview_btn)
        preview_btn_row.addStretch()
        
        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #666;")
        preview_btn_row.addWidget(self.count_label)
        
        preview_layout.addLayout(preview_btn_row)
        layout.addWidget(preview_group)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        btn_layout.addStretch()
        
        self.apply_btn = QPushButton("✨ Generate && Apply")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.apply_btn.clicked.connect(self.apply_generation)
        btn_layout.addWidget(self.apply_btn)
        
        layout.addLayout(btn_layout)
        
        # Initial preview
        QTimer.singleShot(100, self.generate_preview)
    
    def on_preset_changed(self, index):
        key = self.preset_combo.currentData()
        self.load_preset(key)
    
    def load_preset(self, key):
        presets = self.generator.get_preset_styles()
        if key not in presets:
            return
        
        preset = presets[key]
        self.preset_desc.setText(preset['description'])
        
        # Block signals during update
        self.density_spin.blockSignals(True)
        self.noise_spin.blockSignals(True)
        self.variance_spin.blockSignals(True)
        self.sensor_prob_spin.blockSignals(True)
        self.feedback_check.blockSignals(True)
        
        self.density_spin.setValue(preset['density'])
        self.noise_spin.setValue(preset.get('weight_noise', 1.0))
        self.variance_spin.setValue(preset.get('position_variance', 0.0))
        self.sensor_prob_spin.setValue(preset.get('sensor_probability', 0.0))
        self.feedback_check.setChecked(preset.get('include_feedback', True))
        
        self.density_spin.blockSignals(False)
        self.noise_spin.blockSignals(False)
        self.variance_spin.blockSignals(False)
        self.sensor_prob_spin.blockSignals(False)
        self.feedback_check.blockSignals(False)
        
        self.generate_preview()
    
    def generate_preview(self):
        """Generate a preview without applying."""
        # Create fresh generator (no seed for variety)
        gen = SparseNetworkGenerator()
        
        # Pass the weight_noise parameter
        connections = gen.generate_connections(
            density=self.density_spin.value(),
            include_feedback_loops=self.feedback_check.isChecked(),
            weight_noise=self.noise_spin.value()
        )
        
        self.result_connections = connections
        
        # Format preview
        lines = []
        excitatory = 0
        inhibitory = 0
        
        for source, target, weight in connections:
            sign = "+" if weight > 0 else ""
            arrow = "→" if weight > 0 else "⊣"
            lines.append(f"  {source:15} {arrow} {target:15} ({sign}{weight:.3f})")
            if weight > 0:
                excitatory += 1
            else:
                inhibitory += 1
        
        # Add note about sensors/variance if active
        if self.sensor_prob_spin.value() > 0:
            lines.insert(0, f"NOTE: Will attempt to add random sensors (Prob: {self.sensor_prob_spin.value()})")
        if self.variance_spin.value() > 0:
            lines.insert(0, f"NOTE: Will randomly perturb positions (Var: {self.variance_spin.value()})")
        
        if lines:
            self.preview_text.setPlainText("\n".join(lines))
        else:
            self.preview_text.setPlainText("No connections would be created with these settings.")
        
        # Update count
        total = len(connections)
        self.count_label.setText(
            f"{total} connections ({excitatory} excitatory, {inhibitory} inhibitory)"
        )
    
    def apply_generation(self):
        """Apply the generated network to the design."""
        gen = SparseNetworkGenerator()
        
        # Now passing all new arguments to fix the TypeError
        count, actions = gen.generate_for_design(
            self.design,
            clear_existing=self.clear_check.isChecked(),
            density=self.density_spin.value(),
            include_feedback=self.feedback_check.isChecked(),
            weight_noise=self.noise_spin.value(),
            position_variance=self.variance_spin.value(),
            sensor_probability=self.sensor_prob_spin.value()
        )
        
        self.result_actions = actions
        self.accept()
    
    def get_result_summary(self) -> str:
        """Get a summary of what was generated."""
        return f"Created {len(self.result_connections)} connections"


class ActivationEditorDialog(QDialog):
    """Dialog for viewing and editing neuron activation values."""
    
    def __init__(self, neuron_name: str, current_activation: float, 
                 is_binary: bool = False, parent=None):
        super().__init__(parent)
        self.neuron_name = neuron_name
        self.is_binary = is_binary
        self.result_value = current_activation
        
        self.setWindowTitle(f"Activation: {neuron_name}")
        self.setMinimumWidth(300)
        
        self.setup_ui(current_activation)
    
    def setup_ui(self, current_value):
        layout = QVBoxLayout(self)
        
        # Header
        name_label = QLabel(self.neuron_name.replace('_', ' ').title())
        name_label.setFont(QFont("Arial", 11, QFont.Bold))
        name_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(name_label)
        
        if self.is_binary:
            # Binary neuron: on/off toggle
            info = QLabel("Binary neuron (On/Off)")
            info.setStyleSheet("color: #666;")
            info.setAlignment(Qt.AlignCenter)
            layout.addWidget(info)
            
            btn_row = QHBoxLayout()
            
            self.off_btn = QPushButton("OFF (0)")
            self.off_btn.setCheckable(True)
            self.off_btn.setChecked(current_value < 50)
            self.off_btn.clicked.connect(lambda: self.set_binary(False))
            btn_row.addWidget(self.off_btn)
            
            self.on_btn = QPushButton("ON (100)")
            self.on_btn.setCheckable(True)
            self.on_btn.setChecked(current_value >= 50)
            self.on_btn.clicked.connect(lambda: self.set_binary(True))
            btn_row.addWidget(self.on_btn)
            
            layout.addLayout(btn_row)
            
        else:
            # Continuous neuron: spinner
            info = QLabel("Activation (0-100)")
            info.setStyleSheet("color: #666;")
            info.setAlignment(Qt.AlignCenter)
            layout.addWidget(info)
            
            spin_row = QHBoxLayout()
            spin_row.addStretch()
            
            self.value_spin = QDoubleSpinBox()
            self.value_spin.setRange(0, 100)
            self.value_spin.setSingleStep(5)
            self.value_spin.setDecimals(1)
            self.value_spin.setValue(current_value)
            self.value_spin.setMinimumWidth(100)
            spin_row.addWidget(self.value_spin)
            
            spin_row.addStretch()
            layout.addLayout(spin_row)
            
            # Quick buttons
            quick_row = QHBoxLayout()
            for val, label in [(0, "Min"), (25, "Low"), (50, "Mid"), (75, "High"), (100, "Max")]:
                btn = QPushButton(label)
                btn.setMaximumWidth(50)
                btn.clicked.connect(lambda checked, v=val: self.value_spin.setValue(v))
                quick_row.addWidget(btn)
            layout.addLayout(quick_row)
        
        layout.addSpacing(15)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        btn_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_value)
        ok_btn.setDefault(True)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def set_binary(self, is_on: bool):
        self.off_btn.setChecked(not is_on)
        self.on_btn.setChecked(is_on)
        self.result_value = 100.0 if is_on else 0.0
    
    def accept_value(self):
        if self.is_binary:
            self.result_value = 100.0 if self.on_btn.isChecked() else 0.0
        else:
            self.result_value = self.value_spin.value()
        self.accept()
    
    def get_value(self) -> float:
        return self.result_value