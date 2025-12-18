# designer_outputs_panel.py
"""
Brain Designer panel for configuring neuron output bindings.

This panel allows users to:
1. Bind neurons to output hooks (actuators)
2. Configure trigger thresholds and modes
3. Manage cooldowns and parameters (including color selection)

When the squid runs this brain, neurons that exceed their threshold
will trigger the bound behaviors (flee, seek food, ink, etc.)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QPushButton, QLabel, QComboBox, QDoubleSpinBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QDialogButtonBox, QScrollArea, QFrame, QMessageBox, QSpinBox,
    QColorDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor

from brain_neuron_outputs import (
    NeuronOutputBinding, OutputTriggerMode, 
    STANDARD_OUTPUT_HOOKS, get_output_hooks_by_category
)


class OutputBindingDialog(QDialog):
    """Dialog for creating or editing a neuron output binding."""
    
    def __init__(self, design, existing_binding=None, parent=None):
        super().__init__(parent)
        self.design = design
        self.existing_binding = existing_binding
        self.result_binding = None
        
        # Store dynamic parameters here
        self.current_params = {}
        if existing_binding and existing_binding.hook_params:
            self.current_params = existing_binding.hook_params.copy()
        
        self.setWindowTitle("Configure Output Binding" if existing_binding else "Add Output Binding")
        self.setMinimumWidth(450)
        self.setup_ui()
        
        if existing_binding:
            self._populate_from_binding(existing_binding)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. Selection Group
        type_group = QGroupBox("Select Neuron Type")
        type_layout = QFormLayout(type_group)
        
        self.neuron_combo = QComboBox()
        self._populate_neurons()
        type_layout.addRow("Neuron:", self.neuron_combo)
        
        # Show current activation hint
        self.activation_label = QLabel("Current: --")
        self.activation_label.setStyleSheet("color: #888;")
        type_layout.addRow("", self.activation_label)
        
        layout.addWidget(type_group)
        
        # 2. Output hook selection
        hook_group = QGroupBox("Output Behavior")
        hook_layout = QFormLayout(hook_group)
        
        self.hook_combo = QComboBox()
        self._populate_hooks()
        self.hook_combo.currentTextChanged.connect(self._on_hook_changed)
        hook_layout.addRow("Trigger:", self.hook_combo)
        
        self.hook_description = QLabel("")
        self.hook_description.setWordWrap(True)
        self.hook_description.setStyleSheet("color: #666; font-style: italic;")
        hook_layout.addRow("", self.hook_description)
        
        layout.addWidget(hook_group)

        # === Dynamic Parameters Area ===
        self.params_group = QGroupBox("Behavior Parameters")
        self.params_layout = QVBoxLayout(self.params_group)
        
        # Color Picker UI (Hidden by default)
        self.color_widget = QWidget()
        color_layout = QHBoxLayout(self.color_widget)
        color_layout.setContentsMargins(0,0,0,0)
        
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(30, 30)
        self.color_preview.setStyleSheet("background-color: #CCCCCC; border: 1px solid #888;")
        
        self.pick_color_btn = QPushButton("Pick Colour...")
        self.pick_color_btn.clicked.connect(self._pick_color)
        
        self.reset_color_btn = QPushButton("Reset (Random)")
        self.reset_color_btn.clicked.connect(self._reset_color)
        
        color_layout.addWidget(QLabel("Tint Colour:"))
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.pick_color_btn)
        color_layout.addWidget(self.reset_color_btn)
        color_layout.addStretch()
        
        self.params_layout.addWidget(self.color_widget)
        self.color_widget.hide() # Hide initially
        
        layout.addWidget(self.params_group)
        self.params_group.hide() # Hide group initially
        
        # Trigger configuration
        trigger_group = QGroupBox("Trigger Settings")
        trigger_layout = QFormLayout(trigger_group)
        
        # Threshold
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0, 100)
        self.threshold_spin.setValue(70)
        self.threshold_spin.setSuffix(" %")
        self.threshold_spin.setToolTip("Activation level required to trigger the output")
        trigger_layout.addRow("Threshold:", self.threshold_spin)
        
        # Trigger mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Rising Edge (cross threshold going up)", OutputTriggerMode.THRESHOLD_RISING.value)
        self.mode_combo.addItem("Falling Edge (cross threshold going down)", OutputTriggerMode.THRESHOLD_FALLING.value)
        self.mode_combo.addItem("While Above (continuous while > threshold)", OutputTriggerMode.THRESHOLD_ABOVE.value)
        self.mode_combo.addItem("While Below (continuous while < threshold)", OutputTriggerMode.THRESHOLD_BELOW.value)
        self.mode_combo.addItem("On Change (any significant change)", OutputTriggerMode.ON_CHANGE.value)
        trigger_layout.addRow("Mode:", self.mode_combo)
        
        # Cooldown
        self.cooldown_spin = QDoubleSpinBox()
        self.cooldown_spin.setRange(0.1, 60)
        self.cooldown_spin.setValue(1.0)
        self.cooldown_spin.setSuffix(" sec")
        self.cooldown_spin.setToolTip("Minimum time between triggers")
        trigger_layout.addRow("Cooldown:", self.cooldown_spin)
        
        # Enabled
        self.enabled_check = QCheckBox("Enabled")
        self.enabled_check.setChecked(True)
        trigger_layout.addRow("", self.enabled_check)
        
        layout.addWidget(trigger_group)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Initialize hook description
        self._on_hook_changed()
    
    def _populate_neurons(self):
        """Populate neuron combo with available neurons."""
        self.neuron_combo.clear()
        
        # Get all non-core neurons (outputs typically come from processing neurons)
        for name, neuron in sorted(self.design.neurons.items()):
            if not neuron.is_core:
                display = name
                
                # Add icons for special types
                if neuron.is_sensor:
                    display = f"📡 {name}"
                elif name.startswith('connector_'):
                    display = f"🔗 {name}"
                elif name.startswith('novelty_'):
                    display = f"✨ {name}"
                elif name.startswith('stress_'):
                    display = f"🔥 {name}"
                elif name.startswith('reward_'):
                    display = f"💎 {name}"
                    
                self.neuron_combo.addItem(display, name)
        
        # Also add core neurons (they might want anxiety to trigger flee, etc.)
        self.neuron_combo.insertSeparator(self.neuron_combo.count())
        for name, neuron in sorted(self.design.neurons.items()):
            if neuron.is_core:
                self.neuron_combo.addItem(f"⚡ {name}", name)
    
    def _populate_hooks(self):
        """Populate hook combo with available output hooks."""
        self.hook_combo.clear()
        
        by_category = get_output_hooks_by_category()
        
        for category in sorted(by_category.keys()):
            hooks = by_category[category]
            
            # Add category header
            self.hook_combo.addItem(f"── {category.title()} ──", None)
            
            # Make header non-selectable
            idx = self.hook_combo.count() - 1
            self.hook_combo.model().item(idx).setEnabled(False)
            
            for hook_name, info in sorted(hooks.items()):
                display_name = hook_name.replace('neuron_output_', '').replace('_', ' ').title()
                self.hook_combo.addItem(f"  {display_name}", hook_name)
    
    def _on_hook_changed(self):
        """Update description and param UI when hook selection changes."""
        hook_name = self.hook_combo.currentData()
        self._update_param_ui(hook_name)

        if hook_name and hook_name in STANDARD_OUTPUT_HOOKS:
            info = STANDARD_OUTPUT_HOOKS[hook_name]
            self.hook_description.setText(info.get('description', ''))
            
            # Update default threshold
            default_thresh = info.get('default_threshold', 70)
            if not self.existing_binding:  # Only auto-set for new bindings
                self.threshold_spin.setValue(default_thresh)
        else:
            self.hook_description.setText("")
    
    def _update_param_ui(self, hook_name):
        """Show specific UI elements based on the selected hook."""
        self.params_group.hide()
        self.color_widget.hide()
        
        if hook_name == 'neuron_output_change_color':
            self.params_group.show()
            self.color_widget.show()
            self._update_color_preview()

    def _update_color_preview(self):
        """Update the color preview box based on current params."""
        if 'red' in self.current_params:
            r = self.current_params.get('red', 255)
            g = self.current_params.get('green', 255)
            b = self.current_params.get('blue', 255)
            self.color_preview.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #000;")
            self.color_preview.setText("")
        else:
            self.color_preview.setStyleSheet("background-color: #EEE; border: 1px dashed #888;")
            self.color_preview.setText("?")

    def _pick_color(self):
        """Open color picker dialog."""
        initial = QColor(255, 255, 255)
        if 'red' in self.current_params:
            initial = QColor(
                self.current_params['red'], 
                self.current_params['green'], 
                self.current_params['blue']
            )
            
        color = QColorDialog.getColor(initial, self, "Select Output Tint")
        
        if color.isValid():
            self.current_params['red'] = color.red()
            self.current_params['green'] = color.green()
            self.current_params['blue'] = color.blue()
            self._update_color_preview()

    def _reset_color(self):
        """Clear color params to revert to random."""
        self.current_params.pop('red', None)
        self.current_params.pop('green', None)
        self.current_params.pop('blue', None)
        self._update_color_preview()

    def _populate_from_binding(self, binding: NeuronOutputBinding):
        """Fill dialog fields from existing binding."""
        # Find and select neuron
        for i in range(self.neuron_combo.count()):
            if self.neuron_combo.itemData(i) == binding.neuron_name:
                self.neuron_combo.setCurrentIndex(i)
                break
        
        # Find and select hook
        for i in range(self.hook_combo.count()):
            if self.hook_combo.itemData(i) == binding.output_hook:
                self.hook_combo.setCurrentIndex(i)
                break
        
        self.threshold_spin.setValue(binding.threshold)
        self.cooldown_spin.setValue(binding.cooldown)
        self.enabled_check.setChecked(binding.enabled)
        
        # Find and select mode
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == binding.trigger_mode.value:
                self.mode_combo.setCurrentIndex(i)
                break
        
        # Load params
        self.current_params = binding.hook_params.copy() if binding.hook_params else {}
        self._on_hook_changed()

    def accept(self):
        """Validate and create binding."""
        neuron_name = self.neuron_combo.currentData()
        hook_name = self.hook_combo.currentData()
        
        if not neuron_name:
            QMessageBox.warning(self, "Error", "Please select a neuron")
            return
        
        if not hook_name:
            QMessageBox.warning(self, "Error", "Please select an output behavior")
            return
        
        mode_value = self.mode_combo.currentData()
        trigger_mode = OutputTriggerMode(mode_value)
        
        self.result_binding = NeuronOutputBinding(
            neuron_name=neuron_name,
            output_hook=hook_name,
            threshold=self.threshold_spin.value(),
            trigger_mode=trigger_mode,
            cooldown=self.cooldown_spin.value(),
            enabled=self.enabled_check.isChecked(),
            hook_params=self.current_params # Save collected params
        )
        
        super().accept()


class NeuronOutputsPanel(QWidget):
    """
    Panel for managing neuron output bindings in the brain designer.
    
    Shows a table of all output bindings and allows adding/editing/removing them.
    """
    
    outputsChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        
        # Store bindings locally (will be exported with brain)
        self.bindings: list = []
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header with description
        header = QLabel(
            "<b>Output Bindings</b><br>"
            "<small>Connect neurons to squid behaviors. When a neuron's activation "
            "exceeds the threshold, it triggers the bound action.</small>"
        )
        header.setWordWrap(True)
        layout.addWidget(header)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        add_btn = QPushButton("➕ Add Binding")
        add_btn.clicked.connect(self.add_binding)
        toolbar.addWidget(add_btn)
        
        remove_btn = QPushButton("🗑️ Remove")
        remove_btn.clicked.connect(self.remove_binding)
        toolbar.addWidget(remove_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Bindings table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Neuron", "→ Behavior", "Threshold", "Mode", "Enabled"
        ])
        
        # [CHANGED] Enable interactive column resizing and set default widths
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 150)  # Neuron
        self.table.setColumnWidth(1, 200)  # Behavior (wider to show color)
        self.table.setColumnWidth(2, 100)  # Threshold
        self.table.setColumnWidth(3, 150)  # Mode
        self.table.setColumnWidth(4, 80)   # Enabled
        
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.doubleClicked.connect(self.edit_binding)
        layout.addWidget(self.table)
        
        # Quick info
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #888;")
        layout.addWidget(self.info_label)
        
        self.refresh()
    
    def refresh(self):
        """Refresh the bindings table."""
        self.table.setRowCount(len(self.bindings))
        
        for row, binding in enumerate(self.bindings):
            # Neuron name
            neuron_item = QTableWidgetItem(binding.neuron_name)
            if binding.neuron_name not in self.design.neurons:
                neuron_item.setForeground(QColor(255, 100, 100))  # Red if missing
                neuron_item.setToolTip("⚠️ Neuron not found in design")
            self.table.setItem(row, 0, neuron_item)
            
            # Output hook (formatted nicely)
            hook_display = binding.output_hook.replace('neuron_output_', '').replace('_', ' ').title()
            
            # [CHANGED] For color bindings, show color as cell background instead of RGB text
            hook_item = QTableWidgetItem(hook_display)
            if binding.output_hook in STANDARD_OUTPUT_HOOKS:
                hook_item.setToolTip(STANDARD_OUTPUT_HOOKS[binding.output_hook].get('description', ''))
            
            # If this is a color binding, set the background color
            if binding.hook_params and 'red' in binding.hook_params:
                r = binding.hook_params.get('red', 255)
                g = binding.hook_params.get('green', 255)
                b = binding.hook_params.get('blue', 255)
                color = QColor(r, g, b)
                hook_item.setBackground(color)
                
                # Adjust text color for contrast
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                if brightness < 128:
                    hook_item.setForeground(QColor(255, 255, 255))
                else:
                    hook_item.setForeground(QColor(0, 0, 0))
            
            self.table.setItem(row, 1, hook_item)
            
            # Threshold
            thresh_item = QTableWidgetItem(f"{binding.threshold:.0f}%")
            self.table.setItem(row, 2, thresh_item)
            
            # Mode
            mode_display = binding.trigger_mode.value.replace('_', ' ').title()
            mode_item = QTableWidgetItem(mode_display)
            self.table.setItem(row, 3, mode_item)
            
            # Enabled
            enabled_item = QTableWidgetItem("✓" if binding.enabled else "✗")
            enabled_item.setTextAlignment(Qt.AlignCenter)
            if not binding.enabled:
                enabled_item.setForeground(QColor(150, 150, 150))
            self.table.setItem(row, 4, enabled_item)
        
        # Update info
        enabled_count = sum(1 for b in self.bindings if b.enabled)
        self.info_label.setText(f"{len(self.bindings)} binding(s), {enabled_count} enabled")
    
    def add_binding(self):
        """Show dialog to add a new binding."""
        dialog = OutputBindingDialog(self.design, parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.result_binding:
            # Duplicate check REMOVED to allow multiple bindings for same neuron/hook
            # (e.g. one for Rising threshold, one for Falling)
            
            self.bindings.append(dialog.result_binding)
            self.refresh()
            self.outputsChanged.emit()
    
    def edit_binding(self):
        """Edit the selected binding."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.bindings):
            return
        
        binding = self.bindings[row]
        dialog = OutputBindingDialog(self.design, existing_binding=binding, parent=self)
        
        if dialog.exec_() == QDialog.Accepted and dialog.result_binding:
            self.bindings[row] = dialog.result_binding
            self.refresh()
            self.outputsChanged.emit()
    
    def remove_binding(self):
        """Remove the selected binding."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self.bindings):
            return
        
        binding = self.bindings[row]
        reply = QMessageBox.question(
            self, "Remove Binding",
            f"Remove binding: {binding.neuron_name} → {binding.output_hook}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.bindings.pop(row)
            self.refresh()
            self.outputsChanged.emit()
    
    def load_bindings(self, bindings_data: list):
        """Load bindings from saved data."""
        self.bindings.clear()
        for data in bindings_data:
            try:
                binding = NeuronOutputBinding.from_dict(data)
                self.bindings.append(binding)
            except Exception as e:
                print(f"[OutputsPanel] Error loading binding: {e}")
        self.refresh()
    
    def export_bindings(self) -> list:
        """Export bindings for saving."""
        return [b.to_dict() for b in self.bindings]
    
    def validate_bindings(self) -> list:
        """
        Validate bindings against current design.
        
        Returns list of warning messages.
        """
        warnings = []
        for binding in self.bindings:
            if binding.neuron_name not in self.design.neurons:
                warnings.append(f"Binding references missing neuron: {binding.neuron_name}")
        return warnings