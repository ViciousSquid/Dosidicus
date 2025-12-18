from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QListWidget, QListWidgetItem, 
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QCheckBox, QComboBox, QTextEdit, 
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QDialog, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from typing import Optional, Dict

from designer_core import BrainDesign, DesignerNeuron, DesignerLayer
from designer_constants import (
    NeuronType, INPUT_SENSORS, REQUIRED_NEURONS, DEFAULT_SENSOR_CONNECTIONS,
    is_required_neuron, is_input_sensor, is_custom_neuron, 
    validate_custom_neuron_name, normalize_neuron_name,
    DEFAULT_COLORS, CUSTOM_NEURON_COLOR
)

# Optional: Import sensor discovery for plugin sensors
try:
    from designer_sensor_discovery import get_all_available_sensors, is_plugin_sensor
    _HAS_SENSOR_DISCOVERY = True
except ImportError:
    _HAS_SENSOR_DISCOVERY = False
    def get_all_available_sensors():
        return dict(INPUT_SENSORS)
    def is_plugin_sensor(name):
        return False


class AddNeuronDialog(QDialog):
    """
    Dialog for adding new neurons to the brain design.
    
    Supports:
    - Custom neurons with user-defined names
    - Input sensors (built-in and plugin)
    """
    
    def __init__(self, design: BrainDesign, position=None, parent=None):
        super().__init__(parent)
        self.design = design
        self.position = position or (400, 200)
        self.result_neuron = None
        self.result_message = ""
        self.setWindowTitle("Add Neuron")
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # 1. Selection Group - Type Selection Buttons
        type_group = QGroupBox("Select Neuron Type")
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(8)
        
        # Custom Neuron Button (Primary action - more prominent)
        custom_btn = QPushButton("Custom Neuron")
        custom_btn.setToolTip(
            "Create a neuron with a custom name.\n"
            "Custom neurons participate in Hebbian learning\n"
            "and can form connections with other neurons."
        )
        custom_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 6px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        custom_btn.clicked.connect(lambda: self.select_type('custom'))
        type_layout.addWidget(custom_btn)
        
        # Sensor Button
        sensor_btn = QPushButton("Input Sensor")
        sensor_btn.setToolTip(
            "Add a pre-defined input sensor.\n"
            "Sensors receive external input from the game\n"
            "and feed information into the neural network."
        )
        sensor_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        sensor_btn.clicked.connect(lambda: self.select_type('sensor'))
        type_layout.addWidget(sensor_btn)
        
        layout.addWidget(type_group)
        
        # 2. Sensor Selection Group (Hidden by default)
        self.sensor_group = QGroupBox("Select Sensor")
        sensor_layout = QVBoxLayout(self.sensor_group)
        self.sensor_list = QListWidget()
        self.sensor_list.itemDoubleClicked.connect(self.accept_sensor)
        sensor_layout.addWidget(self.sensor_list)
        
        # Add sensor button
        add_sensor_btn = QPushButton("Add Selected Sensor")
        add_sensor_btn.clicked.connect(self.accept_sensor)
        sensor_layout.addWidget(add_sensor_btn)
        
        layout.addWidget(self.sensor_group)
        self.sensor_group.hide()
        
        # 3. Custom Neuron Entry Group (Hidden by default)
        self.custom_group = QGroupBox("Create Custom Neuron")
        custom_layout = QVBoxLayout(self.custom_group)
        custom_layout.setSpacing(10)
        
        # Info label with expanded explanation
        info_label = QLabel(
            "<b>Custom Neurons:</b><br>"
            "• Participate in <b>Hebbian learning</b> (connections strengthen/weaken)<br>"
            "• Can connect to any other neurons<br>"
            "• <b>Neurogenesis</b> can form new connections to them<br><br>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                background-color: #E8F5E9;
                padding: 12px;
                border-radius: 6px;
                color: #2E7D32;
            }
        """)
        custom_layout.addWidget(info_label)
        
        # Name input with validation
        name_form = QFormLayout()
        name_form.setSpacing(8)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., excitement, food_memory, caution")
        self.name_edit.setMinimumHeight(32)
        self.name_edit.textChanged.connect(self._validate_name_live)
        name_form.addRow("Neuron Name:", self.name_edit)
        custom_layout.addLayout(name_form)
        
        # Validation feedback label
        self.validation_label = QLabel("")
        self.validation_label.setWordWrap(True)
        self.validation_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
        custom_layout.addWidget(self.validation_label)
        
        # Preview of normalized name
        self.preview_label = QLabel("")
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #F5F5F5;
                padding: 6px 10px;
                border-radius: 4px;
                font-family: monospace;
            }
        """)
        custom_layout.addWidget(self.preview_label)
        
        # Create button
        self.create_btn = QPushButton("Create Custom Neuron")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.create_btn.clicked.connect(self.accept_custom)
        self.create_btn.setEnabled(False)  # Disabled until valid name
        custom_layout.addWidget(self.create_btn)
        
        layout.addWidget(self.custom_group)
        self.custom_group.hide()
        
        # Cancel button at bottom
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
    
    def select_type(self, t):
        """Handle type selection button clicks."""
        if t == 'sensor':
            self.sensor_group.show()
            self.custom_group.hide()
            self.populate_sensor_list()
        else:
            self.custom_group.show()
            self.sensor_group.hide()
            self.name_edit.setFocus()
            self._validate_name_live()
            
        self.adjustSize()

    def _validate_name_live(self):
        """Live validation of the neuron name as user types."""
        raw_name = self.name_edit.text()
        
        if not raw_name.strip():
            self.validation_label.setText("Enter a name for your custom neuron")
            self.validation_label.setStyleSheet("color: #666; font-size: 11px; padding: 4px;")
            self.preview_label.setText("")
            self.create_btn.setEnabled(False)
            return
        
        # Normalize the name
        normalized = normalize_neuron_name(raw_name)
        
        # Check if already exists
        if normalized in self.design.neurons:
            self.validation_label.setText(f"❌ A neuron named '{normalized}' already exists")
            self.validation_label.setStyleSheet("color: #D32F2F; font-size: 11px; padding: 4px;")
            self.preview_label.setText(f"Name: {normalized}")
            self.create_btn.setEnabled(False)
            return
        
        # Validate the name
        is_valid, message = validate_custom_neuron_name(raw_name)
        
        if is_valid:
            if message:  # Warning message
                self.validation_label.setText(f"⚠️ {message}")
                self.validation_label.setStyleSheet("color: #FF9800; font-size: 11px; padding: 4px;")
            else:
                self.validation_label.setText("✅ Valid neuron name")
                self.validation_label.setStyleSheet("color: #4CAF50; font-size: 11px; padding: 4px;")
            
            self.preview_label.setText(f"Will create: <b>{normalized}</b>")
            self.create_btn.setEnabled(True)
        else:
            self.validation_label.setText(f"❌ {message}")
            self.validation_label.setStyleSheet("color: #D32F2F; font-size: 11px; padding: 4px;")
            self.preview_label.setText(f"Name: {normalized}")
            self.create_btn.setEnabled(False)

    def populate_sensor_list(self):
        """Populate the sensor list with available sensors."""
        self.sensor_list.clear()
        existing = set(self.design.neurons.keys())
        
        # Get all available sensors (built-in + plugin)
        all_sensors = get_all_available_sensors()
        
        # Also ensure can_see_food is included
        if 'can_see_food' not in all_sensors and 'can_see_food' in REQUIRED_NEURONS:
            all_sensors['can_see_food'] = {
                'description': REQUIRED_NEURONS['can_see_food'].get('description', ''),
                'is_binary': True,
                'plugin': None
            }
        
        # Filter to available sensors
        available = {k: v for k, v in all_sensors.items() if k not in existing}
        
        if not available:
            item = QListWidgetItem("All sensors already added")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.sensor_list.addItem(item)
            return

        for name in sorted(available.keys()):
            info = available[name]
            display_name = name.replace('_', ' ').title()
            
            # Add plugin indicator
            if info.get('plugin'):
                display_name = f"🔌 {display_name}"
            
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, name)
            
            # Add tooltip
            tooltip = info.get('description', '')
            if info.get('plugin'):
                tooltip += f"\n[Plugin: {info['plugin']}]"
            if tooltip:
                item.setToolTip(tooltip.strip())
            
            self.sensor_list.addItem(item)

    def accept_sensor(self):
        """Accept the selected sensor."""
        items = self.sensor_list.selectedItems()
        if not items: 
            QMessageBox.warning(self, "No Selection", "Please select a sensor to add.")
            return
            
        name = items[0].data(Qt.UserRole)
        if not name: 
            return 
        
        success, msg = self.design.add_sensor(name)
        if success:
            self.result_message = msg
            self.accept()
        else: 
            QMessageBox.warning(self, "Error", msg)

    def accept_custom(self):
        """Accept the custom neuron creation."""
        raw_name = self.name_edit.text()
        normalized = normalize_neuron_name(raw_name)
        
        if not normalized:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid neuron name.")
            return
            
        if normalized in self.design.neurons:
            QMessageBox.warning(self, "Already Exists", f"A neuron named '{normalized}' already exists.")
            return
        
        # Final validation
        is_valid, message = validate_custom_neuron_name(raw_name)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Name", message)
            return
        
        # Create the custom neuron
        neuron = DesignerNeuron(
            name=normalized, 
            neuron_type=NeuronType.CUSTOM, 
            position=self.position,
            color=CUSTOM_NEURON_COLOR,
            description=f"Custom neuron created by user"
        )
        
        success = self.design.add_neuron(neuron)
        
        if success:
            self.result_message = f"Created custom neuron: {normalized}"
            self.result_neuron = neuron
            self.accept()
        else:
            QMessageBox.warning(self, "Error", f"Failed to create neuron '{normalized}'")


class NeuronPropertiesPanel(QWidget):
    """Panel for viewing and editing neuron properties."""
    
    neuronChanged = pyqtSignal(str)
    
    def __init__(self, design: BrainDesign, parent=None):
        super().__init__(parent)
        self.design = design
        self.current_neuron = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.header_label = QLabel("No neuron selected")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.header_label)
        
        # Category indicator
        self.category_label = QLabel("")
        self.category_label.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(self.category_label)
        
        form = QFormLayout()
        form.setSpacing(8)
        
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.on_name_changed)
        form.addRow("Name:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["CORE", "SENSOR", "INPUT", "OUTPUT", "HIDDEN", "CONNECTOR", "CUSTOM"])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        form.addRow("Type:", self.type_combo)
        
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-1000, 2000)
        self.x_spin.valueChanged.connect(self.on_pos_changed)
        form.addRow("X:", self.x_spin)
        
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-500, 1000)
        self.y_spin.valueChanged.connect(self.on_pos_changed)
        form.addRow("Y:", self.y_spin)
        
        layout.addLayout(form)
        
        # Info section for custom neurons
        self.custom_info = QLabel("")
        self.custom_info.setWordWrap(True)
        self.custom_info.setStyleSheet("""
            QLabel {
                background-color: #E8F5E9;
                padding: 8px;
                border-radius: 4px;
                color: #2E7D32;
                margin-top: 8px;
            }
        """)
        self.custom_info.hide()
        layout.addWidget(self.custom_info)
        
        self.delete_btn = QPushButton("Delete Neuron")
        self.delete_btn.setStyleSheet("color: #D32F2F;")
        self.delete_btn.clicked.connect(self.on_delete)
        layout.addWidget(self.delete_btn)
        
        layout.addStretch()
        self.setEnabled(False)

    def set_neuron(self, name):
        """Set the currently displayed neuron."""
        self.current_neuron = name
        if not name:
            self.setEnabled(False)
            self.header_label.setText("No Selection")
            self.category_label.setText("")
            self.custom_info.hide()
            return
        
        self.setEnabled(True)
        neuron = self.design.get_neuron(name)
        if not neuron:
            self.setEnabled(False)
            return
            
        self.header_label.setText(name.replace('_', ' ').title())
        
        # Show category
        category = neuron.category
        category_colors = {
            'core': '#1565C0',
            'required': '#2E7D32',
            'sensor': '#00838F',
            'custom': '#7B1FA2',
            'connector': '#455A64',
            'stress': '#C62828',
            'novelty': '#F57F17',
            'reward': '#2E7D32',
        }
        color = category_colors.get(category, '#666')
        self.category_label.setText(f"<span style='color:{color}'>● {category.upper()}</span>")
        
        # Block signals during update
        self.name_edit.blockSignals(True)
        self.type_combo.blockSignals(True)
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        
        self.name_edit.setText(name)
        self.name_edit.setEnabled(not neuron.is_protected)
        self.type_combo.setCurrentText(neuron.neuron_type.name)
        self.type_combo.setEnabled(not neuron.is_protected and not neuron.is_sensor)
        self.x_spin.setValue(neuron.position[0])
        self.y_spin.setValue(neuron.position[1])
        self.delete_btn.setEnabled(not neuron.is_protected)
        
        # Show info for custom neurons
        if is_custom_neuron(name):
            self.custom_info.setText(
                "🟣 <b>Custom Neuron</b><br>"
                "• Participates in Hebbian learning<br>"
                "• Can form new connections via neurogenesis"
            )
            self.custom_info.show()
        else:
            self.custom_info.hide()
        
        self.name_edit.blockSignals(False)
        self.type_combo.blockSignals(False)
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
    
    def on_name_changed(self):
        """Handle neuron name change."""
        if not self.current_neuron: 
            return
        new_name = normalize_neuron_name(self.name_edit.text())
        if new_name != self.current_neuron:
            # Validate the new name
            is_valid, message = validate_custom_neuron_name(new_name)
            if not is_valid:
                QMessageBox.warning(self, "Invalid Name", message)
                self.name_edit.setText(self.current_neuron)
                return
                
            success, msg = self.design.rename_neuron(self.current_neuron, new_name)
            if success:
                self.current_neuron = new_name
                self.neuronChanged.emit(new_name)
            else:
                QMessageBox.warning(self, "Rename Failed", msg)
                self.name_edit.setText(self.current_neuron)

    def on_type_changed(self, t):
        """Handle neuron type change."""
        if self.current_neuron:
            try:
                self.design.get_neuron(self.current_neuron).neuron_type = NeuronType[t]
                self.neuronChanged.emit(self.current_neuron)
            except KeyError:
                pass

    def on_pos_changed(self):
        """Handle position change."""
        if self.current_neuron:
            neuron = self.design.get_neuron(self.current_neuron)
            if neuron:
                neuron.position = (self.x_spin.value(), self.y_spin.value())
                self.neuronChanged.emit(self.current_neuron)

    def on_delete(self):
        """Handle neuron deletion."""
        if not self.current_neuron:
            return
            
        reply = QMessageBox.question(
            self, "Delete Neuron",
            f"Delete neuron '{self.current_neuron}'?\n\nThis will also remove all connections to/from this neuron.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, msg = self.design.remove_neuron(self.current_neuron)
            if success:
                self.current_neuron = None
                self.neuronChanged.emit("")
            else:
                QMessageBox.warning(self, "Delete Failed", msg)


class LayersPanel(QWidget):
    """Panel for managing layers."""
    
    layersChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.setup_ui()
    
    def setup_ui(self):
        l = QVBoxLayout(self)
        self.list = QListWidget()
        l.addWidget(self.list)
        
        # Button row
        btn_row = QHBoxLayout()
        
        add_btn = QPushButton("Add Layer")
        add_btn.clicked.connect(self.add_layer)
        btn_row.addWidget(add_btn)
        
        delete_btn = QPushButton("Delete Layer")
        delete_btn.clicked.connect(self.delete_layer)
        btn_row.addWidget(delete_btn)
        
        l.addLayout(btn_row)
        self.refresh()
        
    def refresh(self):
        self.list.clear()
        for layer in self.design.layers:
            self.list.addItem(f"{layer.name} ({layer.layer_type.name})")

    def add_layer(self):
        name, ok = QInputDialog.getText(self, "New Layer", "Name:")
        if ok and name:
            self.design.add_layer(DesignerLayer(name, NeuronType.HIDDEN, 200))
            self.refresh()
            self.layersChanged.emit()

    def delete_layer(self):
        """Delete the selected layer."""
        row = self.list.currentRow()
        if row < 0 or row >= len(self.design.layers):
            QMessageBox.warning(self, "No Selection", "Please select a layer to delete.")
            return
        
        layer = self.design.layers[row]
        reply = QMessageBox.question(
            self, "Delete Layer",
            f"Delete layer '{layer.name}'?\n\n"
            "Note: This removes the layer metadata only.\n"
            "Neurons in this layer will not be removed.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.design.remove_layer(row)
            self.refresh()
            self.layersChanged.emit()


class SensorsPanel(QWidget):
    """
    Panel showing available input sensors.
    
    Supports both built-in sensors from INPUT_SENSORS and
    custom sensors registered by plugins via the PluginManager.
    """
    sensorsChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self._scroll_widget = None
        self._scroll_layout = None
        self.setup_ui()
    
    def setup_ui(self):
        l = QVBoxLayout(self)
        
        # Header with refresh button
        header = QHBoxLayout()
        header.addWidget(QLabel("Input Sensors:"))
        header.addStretch()
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh sensor list")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(self.rebuild_sensor_list)
        header.addWidget(refresh_btn)
        l.addLayout(header)
        
        # Scrollable sensor list
        scroll = QScrollArea()
        self._scroll_widget = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_widget)
        self.checks = {}
        
        self._populate_sensors()
        
        scroll.setWidget(self._scroll_widget)
        scroll.setWidgetResizable(True)
        l.addWidget(scroll)
        self.refresh()
    
    def _populate_sensors(self):
        """Populate the sensor checkboxes."""
        self.checks.clear()
        while self._scroll_layout.count():
            item = self._scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        all_sensors = get_all_available_sensors()
        
        categories = {}
        for name, info in all_sensors.items():
            cat = info.get('category', 'other')
            if cat not in categories:
                categories[cat] = {}
            categories[cat][name] = info
        
        for cat_name in sorted(categories.keys()):
            cat_sensors = categories[cat_name]
            
            if len(categories) > 1:
                cat_label = QLabel(f"── {cat_name.title()} ──")
                cat_label.setStyleSheet("color: #888; font-size: 10px;")
                self._scroll_layout.addWidget(cat_label)
            
            for name in sorted(cat_sensors.keys()):
                info = cat_sensors[name]
                
                display_name = name
                if info.get('plugin'):
                    display_name = f"🔌 {name}"
                
                cb = QCheckBox(display_name)
                cb.setProperty('n', name)
                cb.stateChanged.connect(self.toggled)
                
                tooltip = info.get('description', '')
                if info.get('plugin'):
                    tooltip += f"\n[From plugin: {info['plugin']}]"
                if info.get('is_binary'):
                    tooltip += "\n[Binary: 0 or 100]"
                if tooltip:
                    cb.setToolTip(tooltip.strip())
                
                self.checks[name] = cb
                self._scroll_layout.addWidget(cb)
        
        self._scroll_layout.addStretch()
    
    def rebuild_sensor_list(self):
        """Rebuild the sensor list."""
        self._populate_sensors()
        self.refresh()
        
    def refresh(self):
        """Update checkbox states."""
        current = set(self.design.get_sensors_in_design())
        for name, cb in self.checks.items():
            cb.blockSignals(True)
            cb.setChecked(name in current)
            cb.blockSignals(False)

    def toggled(self, state):
        name = self.sender().property('n')
        if state: 
            self.design.add_sensor(name)
        else: 
            self.design.remove_neuron(name)
        self.sensorsChanged.emit()


class ConnectionsTable(QWidget):
    """Table showing all connections."""
    
    connectionChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        l = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Source", "Target", "Weight"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        l.addWidget(self.table)
        self.refresh()
        
    def refresh(self):
        self.table.setRowCount(len(self.design.connections))
        for i, c in enumerate(self.design.connections):
            self.table.setItem(i, 0, QTableWidgetItem(c.source))
            self.table.setItem(i, 1, QTableWidgetItem(c.target))
            weight_item = QTableWidgetItem(f"{c.weight:+.3f}")
            # Color code weights
            if c.weight > 0:
                weight_item.setForeground(QColor(46, 125, 50))  # Green
            elif c.weight < 0:
                weight_item.setForeground(QColor(198, 40, 40))  # Red
            self.table.setItem(i, 2, weight_item)
