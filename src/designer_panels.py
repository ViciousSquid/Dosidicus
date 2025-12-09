from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout, QListWidget, QListWidgetItem, 
    QPushButton, QLabel, QLineEdit, QDoubleSpinBox, QCheckBox, QComboBox, QTextEdit, 
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QDialog, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal
from typing import Optional, Dict

from designer_core import BrainDesign, DesignerNeuron, DesignerLayer
from designer_constants import (
    NeuronType, INPUT_SENSORS, REQUIRED_NEURONS, DEFAULT_SENSOR_CONNECTIONS,
    is_required_neuron, is_input_sensor
)

class AddNeuronDialog(QDialog):
    def __init__(self, design: BrainDesign, position=None, parent=None):
        super().__init__(parent)
        self.design = design
        self.position = position or (400, 200)
        self.result_neuron = None
        self.result_message = ""
        self.setWindowTitle("Add Neuron")
        self.setMinimumWidth(400)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        type_group = QGroupBox("What type of neuron?")
        type_layout = QVBoxLayout(type_group)
        
        custom_btn = QPushButton("🔧 Custom Neuron")
        custom_btn.clicked.connect(lambda: self.select_type('custom'))
        type_layout.addWidget(custom_btn)
        
        sensor_btn = QPushButton("📡 Input Sensor")
        sensor_btn.clicked.connect(lambda: self.select_type('sensor'))
        type_layout.addWidget(sensor_btn)
        layout.addWidget(type_group)
        
        self.sensor_group = QGroupBox("Select Sensor")
        sensor_layout = QVBoxLayout(self.sensor_group)
        self.sensor_list = QListWidget()
        self.sensor_list.itemDoubleClicked.connect(self.accept_sensor)
        sensor_layout.addWidget(self.sensor_list)
        layout.addWidget(self.sensor_group)
        self.sensor_group.hide()
        
        self.custom_group = QGroupBox("Custom Neuron")
        custom_layout = QFormLayout(self.custom_group)
        self.name_edit = QLineEdit()
        custom_layout.addRow("Name:", self.name_edit)
        add_custom_btn = QPushButton("Create")
        add_custom_btn.clicked.connect(self.accept_custom)
        custom_layout.addRow(add_custom_btn)
        layout.addWidget(self.custom_group)
        self.custom_group.hide()
    
    def select_type(self, t):
        if t == 'sensor':
            self.sensor_group.show()
            self.custom_group.hide()
            self.populate_sensor_list()
        else:
            self.custom_group.show()
            self.sensor_group.hide()
            self.name_edit.setFocus()

    def populate_sensor_list(self):
        self.sensor_list.clear()
        existing = set(self.design.neurons.keys())
        all_sensors = dict(INPUT_SENSORS)
        if 'can_see_food' not in existing: all_sensors['can_see_food'] = REQUIRED_NEURONS['can_see_food']
        available = {k: v for k, v in all_sensors.items() if k not in existing}
        
        if not available:
            self.sensor_list.addItem("All sensors added")
            return

        for name in sorted(available.keys()):
            item = QListWidgetItem(name.replace('_', ' ').title())
            item.setData(Qt.UserRole, name)
            self.sensor_list.addItem(item)

    def accept_sensor(self):
        items = self.sensor_list.selectedItems()
        if not items: return
        name = items[0].data(Qt.UserRole)
        if not name: return 
        
        success, msg = self.design.add_sensor(name)
        if success:
            self.result_message = msg
            self.accept()
        else: QMessageBox.warning(self, "Error", msg)

    def accept_custom(self):
        name = self.name_edit.text().strip().lower().replace(' ', '_')
        if not name: return
        if name in self.design.neurons:
            QMessageBox.warning(self, "Error", "Exists")
            return
        self.design.add_neuron(DesignerNeuron(name=name, neuron_type=NeuronType.HIDDEN, position=self.position))
        self.result_message = f"Created {name}"
        self.accept()

class NeuronPropertiesPanel(QWidget):
    neuronChanged = pyqtSignal(str)
    def __init__(self, design: BrainDesign, parent=None):
        super().__init__(parent)
        self.design = design
        self.current_neuron = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.header_label = QLabel("No neuron selected")
        layout.addWidget(self.header_label)
        
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.on_name_changed)
        form.addRow("Name:", self.name_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems(["CORE", "SENSOR", "INPUT", "OUTPUT", "HIDDEN"])
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
        
        self.delete_btn = QPushButton("Delete Neuron")
        self.delete_btn.clicked.connect(self.on_delete)
        layout.addWidget(self.delete_btn)
        layout.addStretch()
        self.setEnabled(False)

    def set_neuron(self, name):
        self.current_neuron = name
        if not name:
            self.setEnabled(False)
            self.header_label.setText("No Selection")
            return
        
        self.setEnabled(True)
        neuron = self.design.get_neuron(name)
        self.header_label.setText(name)
        
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
        
        self.name_edit.blockSignals(False)
        self.type_combo.blockSignals(False)
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
    
    def on_name_changed(self):
        if not self.current_neuron: return
        new_name = self.name_edit.text().strip()
        if new_name != self.current_neuron:
            if self.design.rename_neuron(self.current_neuron, new_name)[0]:
                self.current_neuron = new_name
                self.neuronChanged.emit(new_name)

    def on_type_changed(self, t):
        if self.current_neuron:
             self.design.get_neuron(self.current_neuron).neuron_type = NeuronType[t]
             self.neuronChanged.emit(self.current_neuron)

    def on_pos_changed(self):
        if self.current_neuron:
            self.design.get_neuron(self.current_neuron).position = (self.x_spin.value(), self.y_spin.value())
            self.neuronChanged.emit(self.current_neuron)

    def on_delete(self):
        if self.design.remove_neuron(self.current_neuron)[0]:
            self.current_neuron = None
            self.neuronChanged.emit("")

class LayersPanel(QWidget):
    layersChanged = pyqtSignal()
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.setup_ui()
    
    def setup_ui(self):
        l = QVBoxLayout(self)
        self.list = QListWidget()
        l.addWidget(self.list)
        btn = QPushButton("Add Layer")
        btn.clicked.connect(self.add_layer)
        l.addWidget(btn)
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

class SensorsPanel(QWidget):
    sensorsChanged = pyqtSignal()
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.setup_ui()
    
    def setup_ui(self):
        l = QVBoxLayout(self)
        scroll = QScrollArea()
        w = QWidget()
        sl = QVBoxLayout(w)
        self.checks = {}
        for name in sorted(INPUT_SENSORS.keys()):
            cb = QCheckBox(name)
            cb.setProperty('n', name)
            cb.stateChanged.connect(self.toggled)
            self.checks[name] = cb
            sl.addWidget(cb)
        scroll.setWidget(w)
        scroll.setWidgetResizable(True)
        l.addWidget(scroll)
        self.refresh()
        
    def refresh(self):
        current = set(self.design.get_sensors_in_design())
        for name, cb in self.checks.items():
            cb.blockSignals(True)
            cb.setChecked(name in current)
            cb.blockSignals(False)

    def toggled(self, state):
        name = self.sender().property('n')
        if state: self.design.add_sensor(name)
        else: self.design.remove_neuron(name)
        self.sensorsChanged.emit()

class ConnectionsTable(QWidget):
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
            self.table.setItem(i, 2, QTableWidgetItem(str(c.weight)))