# designer_tools_window.py
"""
Floating Designer Tools Window for Brain Tool Designer Mode

This window provides all the designer tools and panels in a floating window
that can be used alongside the main brain_tool visualization.
"""

import json
import random
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QToolBar,
    QPushButton, QLabel, QComboBox, QMessageBox, QFileDialog, QAction,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFormLayout, QFrame, QSplitter,
    QStatusBar, QToolButton, QMenu, QInputDialog, QScrollArea, QListWidget,
    QListWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QLineEdit, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QIcon

# Import designer core structures - try relative then absolute
try:
    from .designer_core import BrainDesign, DesignerNeuron, DesignerConnection, DesignerLayer
    from .designer_constants import (
        NeuronType, INPUT_SENSORS, REQUIRED_NEURONS, CORE_NEURONS,
        is_required_neuron, is_input_sensor, is_core_neuron, is_binary_neuron,
        get_default_connections_for_sensor, DEFAULT_COLORS
    )
    from .designer_network_generator import SparseNetworkGenerator
    from .designer_dialogs import SparseNetworkDialog
except ImportError:
    from designer_core import BrainDesign, DesignerNeuron, DesignerConnection, DesignerLayer
    from designer_constants import (
        NeuronType, INPUT_SENSORS, REQUIRED_NEURONS, CORE_NEURONS,
        is_required_neuron, is_input_sensor, is_core_neuron, is_binary_neuron,
        get_default_connections_for_sensor, DEFAULT_COLORS
    )
    from designer_network_generator import SparseNetworkGenerator
    from designer_dialogs import SparseNetworkDialog

# Optional imports
try:
    try:
        from .designer_sensor_discovery import get_all_available_sensors, is_plugin_sensor
    except ImportError:
        from designer_sensor_discovery import get_all_available_sensors, is_plugin_sensor
    _HAS_SENSOR_DISCOVERY = True
except ImportError:
    _HAS_SENSOR_DISCOVERY = False
    def get_all_available_sensors():
        return dict(INPUT_SENSORS)
    def is_plugin_sensor(name):
        return False

try:
    try:
        from .designer_outputs_panel import NeuronOutputsPanel
    except ImportError:
        from designer_outputs_panel import NeuronOutputsPanel
    _HAS_OUTPUTS_PANEL = True
except ImportError:
    _HAS_OUTPUTS_PANEL = False


class QuickAddNeuronDialog(QDialog):
    """Simplified dialog for adding neurons in designer mode."""
    
    def __init__(self, design, position=None, parent=None):
        super().__init__(parent)
        self.design = design
        self.position = position or (400, 200)
        self.result_name = None
        
        self.setWindowTitle("Add Neuron")
        self.setMinimumWidth(350)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab for type selection
        tabs = QTabWidget()
        
        # === Sensor Tab ===
        sensor_widget = QWidget()
        sensor_layout = QVBoxLayout(sensor_widget)
        
        self.sensor_list = QListWidget()
        self._populate_sensors()
        self.sensor_list.itemDoubleClicked.connect(self.accept_sensor)
        sensor_layout.addWidget(self.sensor_list)
        
        add_sensor_btn = QPushButton("Add Selected Sensor")
        add_sensor_btn.clicked.connect(self.accept_sensor)
        sensor_layout.addWidget(add_sensor_btn)
        
        tabs.addTab(sensor_widget, "📡 Sensors")
        
        # === Custom Tab ===
        custom_widget = QWidget()
        custom_layout = QVBoxLayout(custom_widget)
        
        info = QLabel("<i>Create a custom neuron. Name it to match a plugin ID "
                      "to connect with game behaviors.</i>")
        info.setWordWrap(True)
        info.setStyleSheet("color: #666;")
        custom_layout.addWidget(info)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. turbo_mode")
        self.name_edit.returnPressed.connect(self.accept_custom)
        name_layout.addWidget(self.name_edit)
        custom_layout.addLayout(name_layout)
        
        add_custom_btn = QPushButton("✨ Create Custom Neuron")
        add_custom_btn.clicked.connect(self.accept_custom)
        custom_layout.addWidget(add_custom_btn)
        
        custom_layout.addStretch()
        tabs.addTab(custom_widget, "✨ Custom")
        
        layout.addWidget(tabs)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
    
    def _populate_sensors(self):
        self.sensor_list.clear()
        existing = set(self.design.neurons.keys())
        
        all_sensors = get_all_available_sensors()
        
        # Also ensure can_see_food is included
        if 'can_see_food' not in all_sensors:
            all_sensors['can_see_food'] = {
                'description': 'Detects food in vision cone',
                'is_binary': True,
                'plugin': None
            }
        
        available = {k: v for k, v in all_sensors.items() if k not in existing}
        
        if not available:
            self.sensor_list.addItem("All sensors already added")
            return
        
        for name in sorted(available.keys()):
            info = available[name]
            display_name = name.replace('_', ' ').title()
            
            if info.get('plugin'):
                display_name = f"🔌 {display_name}"
            
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, name)
            
            tooltip = info.get('description', '')
            if info.get('plugin'):
                tooltip += f"\n[Plugin: {info['plugin']}]"
            if tooltip:
                item.setToolTip(tooltip.strip())
            
            self.sensor_list.addItem(item)
    
    def accept_sensor(self):
        items = self.sensor_list.selectedItems()
        if not items:
            return
        name = items[0].data(Qt.UserRole)
        if not name:
            return
        
        success, msg = self.design.add_sensor(name)
        if success:
            self.result_name = name
            self.accept()
        else:
            QMessageBox.warning(self, "Error", msg)
    
    def accept_custom(self):
        name = self.name_edit.text().strip().lower().replace(' ', '_')
        if not name:
            return
        if name in self.design.neurons:
            QMessageBox.warning(self, "Error", f"Neuron '{name}' already exists")
            return
        
        neuron = DesignerNeuron(
            name=name,
            neuron_type=NeuronType.HIDDEN,
            position=self.position
        )
        self.design.add_neuron(neuron)
        self.result_name = name
        self.accept()


class SensorsPanel(QWidget):
    """Panel for managing input sensors."""
    sensorsChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.checks = {}
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Input Sensors</b>"))
        header.addStretch()
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setToolTip("Refresh sensor list")
        refresh_btn.setMaximumWidth(30)
        refresh_btn.clicked.connect(self.rebuild_list)
        header.addWidget(refresh_btn)
        
        layout.addLayout(header)
        
        scroll = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        
        self._populate_sensors()
        
        scroll.setWidget(self.scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
    
    def _populate_sensors(self):
        self.checks.clear()
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        all_sensors = get_all_available_sensors()
        
        # Group by category
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
                self.scroll_layout.addWidget(cat_label)
            
            for name in sorted(cat_sensors.keys()):
                info = cat_sensors[name]
                
                display_name = name
                if info.get('plugin'):
                    display_name = f"🔌 {name}"
                
                cb = QCheckBox(display_name)
                cb.setProperty('sensor_name', name)
                cb.stateChanged.connect(self._on_toggled)
                
                tooltip = info.get('description', '')
                if info.get('plugin'):
                    tooltip += f"\n[From plugin: {info['plugin']}]"
                if info.get('is_binary'):
                    tooltip += "\n[Binary: 0 or 100]"
                if tooltip:
                    cb.setToolTip(tooltip.strip())
                
                self.checks[name] = cb
                self.scroll_layout.addWidget(cb)
        
        self.scroll_layout.addStretch()
        self.refresh()
    
    def rebuild_list(self):
        self._populate_sensors()
        self.refresh()
    
    def refresh(self):
        current = set(self.design.get_sensors_in_design())
        for name, cb in self.checks.items():
            cb.blockSignals(True)
            cb.setChecked(name in current)
            cb.blockSignals(False)
    
    def _on_toggled(self, state):
        name = self.sender().property('sensor_name')
        if state:
            self.design.add_sensor(name)
        else:
            self.design.remove_neuron(name)
        self.sensorsChanged.emit()


class NeuronPropertiesPanel(QWidget):
    """Panel for viewing and editing neuron properties."""
    neuronChanged = pyqtSignal(str)
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.current_neuron = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.header_label = QLabel("<b>No neuron selected</b>")
        layout.addWidget(self.header_label)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._on_name_changed)
        form.addRow("Name:", self.name_edit)
        
        self.type_label = QLabel("-")
        form.addRow("Type:", self.type_label)
        
        pos_layout = QHBoxLayout()
        self.x_spin = QDoubleSpinBox()
        self.x_spin.setRange(-1000, 2000)
        self.x_spin.valueChanged.connect(self._on_pos_changed)
        pos_layout.addWidget(QLabel("X:"))
        pos_layout.addWidget(self.x_spin)
        
        self.y_spin = QDoubleSpinBox()
        self.y_spin.setRange(-500, 1000)
        self.y_spin.valueChanged.connect(self._on_pos_changed)
        pos_layout.addWidget(QLabel("Y:"))
        pos_layout.addWidget(self.y_spin)
        form.addRow("Position:", pos_layout)
        
        layout.addLayout(form)
        
        # Connection summary
        self.conn_label = QLabel("Connections: -")
        self.conn_label.setStyleSheet("color: #666;")
        layout.addWidget(self.conn_label)
        
        self.delete_btn = QPushButton("🗑️ Delete Neuron")
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn)
        
        layout.addStretch()
        self.setEnabled(False)
    
    def set_neuron(self, name):
        self.current_neuron = name
        if not name or name not in self.design.neurons:
            self.setEnabled(False)
            self.header_label.setText("<b>No neuron selected</b>")
            return
        
        self.setEnabled(True)
        neuron = self.design.get_neuron(name)
        
        self.header_label.setText(f"<b>{name}</b>")
        
        self.name_edit.blockSignals(True)
        self.x_spin.blockSignals(True)
        self.y_spin.blockSignals(True)
        
        self.name_edit.setText(name)
        self.name_edit.setEnabled(not neuron.is_protected)
        self.type_label.setText(neuron.category.title())
        self.x_spin.setValue(neuron.position[0])
        self.y_spin.setValue(neuron.position[1])
        
        self.name_edit.blockSignals(False)
        self.x_spin.blockSignals(False)
        self.y_spin.blockSignals(False)
        
        # Count connections
        incoming = sum(1 for c in self.design.connections if c.target == name)
        outgoing = sum(1 for c in self.design.connections if c.source == name)
        self.conn_label.setText(f"Connections: {incoming} in, {outgoing} out")
        
        self.delete_btn.setEnabled(not neuron.is_protected)
    
    def _on_name_changed(self):
        if not self.current_neuron:
            return
        new_name = self.name_edit.text().strip()
        if new_name != self.current_neuron:
            success, msg = self.design.rename_neuron(self.current_neuron, new_name)
            if success:
                self.current_neuron = new_name
                self.neuronChanged.emit(new_name)
    
    def _on_pos_changed(self):
        if self.current_neuron:
            neuron = self.design.get_neuron(self.current_neuron)
            if neuron:
                neuron.position = (self.x_spin.value(), self.y_spin.value())
                self.neuronChanged.emit(self.current_neuron)
    
    def _on_delete(self):
        if self.current_neuron:
            success, msg = self.design.remove_neuron(self.current_neuron)
            if success:
                self.current_neuron = None
                self.neuronChanged.emit("")


class ConnectionsTable(QWidget):
    """Table showing all connections."""
    connectionSelected = pyqtSignal(str, str)  # source, target
    connectionChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Source", "Target", "Weight", ""])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 70)
        self.table.setColumnWidth(3, 40)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_selection)
        
        layout.addWidget(self.table)
        
        self.count_label = QLabel("0 connections")
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)
        
        self.refresh()
    
    def refresh(self):
        self.table.setRowCount(len(self.design.connections))
        
        for i, conn in enumerate(self.design.connections):
            self.table.setItem(i, 0, QTableWidgetItem(conn.source))
            self.table.setItem(i, 1, QTableWidgetItem(conn.target))
            
            weight_item = QTableWidgetItem(f"{conn.weight:+.2f}")
            weight_item.setForeground(QColor(50, 200, 50) if conn.weight >= 0 else QColor(200, 50, 50))
            self.table.setItem(i, 2, weight_item)
            
            del_btn = QPushButton("×")
            del_btn.setMaximumWidth(30)
            del_btn.clicked.connect(lambda checked, r=i: self._delete_connection(r))
            self.table.setCellWidget(i, 3, del_btn)
        
        excitatory = sum(1 for c in self.design.connections if c.weight >= 0)
        inhibitory = len(self.design.connections) - excitatory
        self.count_label.setText(f"{len(self.design.connections)} connections "
                                  f"({excitatory} excitatory, {inhibitory} inhibitory)")
    
    def _on_selection(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.design.connections):
            conn = self.design.connections[row]
            self.connectionSelected.emit(conn.source, conn.target)
    
    def _delete_connection(self, row):
        if 0 <= row < len(self.design.connections):
            conn = self.design.connections[row]
            self.design.remove_connection(conn.source, conn.target)
            self.connectionChanged.emit()
            self.refresh()


class LayersPanel(QWidget):
    """Panel for managing layers."""
    layersChanged = pyqtSignal()
    
    def __init__(self, design, parent=None):
        super().__init__(parent)
        self.design = design
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("+ Add Layer")
        add_btn.clicked.connect(self.add_layer)
        btn_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("- Remove")
        remove_btn.clicked.connect(self.remove_layer)
        btn_layout.addWidget(remove_btn)
        
        layout.addLayout(btn_layout)
        self.refresh()
    
    def refresh(self):
        self.list_widget.clear()
        for layer in self.design.layers:
            self.list_widget.addItem(f"{layer.name} ({layer.layer_type.name})")
    
    def add_layer(self):
        name, ok = QInputDialog.getText(self, "New Layer", "Layer name:")
        if ok and name:
            self.design.add_layer(DesignerLayer(name, NeuronType.HIDDEN, 200))
            self.refresh()
            self.layersChanged.emit()
    
    def remove_layer(self):
        row = self.list_widget.currentRow()
        if row >= 0 and row < len(self.design.layers):
            self.design.layers.pop(row)
            self.refresh()
            self.layersChanged.emit()


class DesignerToolsWindow(QMainWindow):
    """
    Floating tools window for Brain Designer mode.
    
    Contains all the designer panels in a compact, dockable window.
    """
    
    # Signals
    designChanged = pyqtSignal()
    neuronSelected = pyqtSignal(str)
    connectionSelected = pyqtSignal(str, str)
    requestRefresh = pyqtSignal()
    
    def __init__(self, brain_widget=None, parent=None):
        super().__init__(parent)
        self.brain_widget = brain_widget
        
        # Create design object that mirrors brain_widget state
        self.design = BrainDesign()
        
        self.setWindowTitle("🧠 Designer Tools")
        self.setMinimumWidth(320)
        self.setMinimumHeight(500)
        
        # Make it a tool window that stays on top of parent
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        
        self.setup_ui()
        self.setup_toolbar()
        
        # Sync from brain_widget if available
        if brain_widget:
            self.sync_from_brain_widget()
    
    def setup_ui(self):
        """Setup the main UI layout."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # Tab widget for panels
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        
        # Sensors panel
        self.sensors_panel = SensorsPanel(self.design)
        self.sensors_panel.sensorsChanged.connect(self._on_design_changed)
        self.tabs.addTab(self.sensors_panel, "📡 Sensors")
        
        # Properties panel
        self.props_panel = NeuronPropertiesPanel(self.design)
        self.props_panel.neuronChanged.connect(self._on_design_changed)
        self.tabs.addTab(self.props_panel, "⚙️ Properties")
        
        # Connections panel
        self.connections_panel = ConnectionsTable(self.design)
        self.connections_panel.connectionChanged.connect(self._on_design_changed)
        self.connections_panel.connectionSelected.connect(
            lambda s, t: self.connectionSelected.emit(s, t)
        )
        self.tabs.addTab(self.connections_panel, "🔗 Connections")
        
        # Layers panel
        self.layers_panel = LayersPanel(self.design)
        self.layers_panel.layersChanged.connect(self._on_design_changed)
        self.tabs.addTab(self.layers_panel, "📊 Layers")
        
        # Outputs panel (if available)
        if _HAS_OUTPUTS_PANEL:
            self.outputs_panel = NeuronOutputsPanel(self.design)
            self.outputs_panel.outputsChanged.connect(self._on_design_changed)
            self.tabs.addTab(self.outputs_panel, "⚡ Outputs")
        else:
            self.outputs_panel = None
        
        layout.addWidget(self.tabs)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status()
    
    def setup_toolbar(self):
        """Setup the toolbar with common actions."""
        toolbar = QToolBar("Designer Tools")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Generate network button
        generate_btn = QToolButton()
        generate_btn.setText("🎲")
        generate_btn.setToolTip("Generate sparse network")
        generate_btn.setPopupMode(QToolButton.MenuButtonPopup)
        
        gen_menu = QMenu(generate_btn)
        gen_menu.addAction("🎲 Random Network", self.generate_random_network)
        gen_menu.addAction("⚖️ Balanced", lambda: self.quick_generate('balanced'))
        gen_menu.addAction("🔬 Minimal", lambda: self.quick_generate('sparse'))
        gen_menu.addAction("🕸️ Dense", lambda: self.quick_generate('dense'))
        gen_menu.addAction("🌀 Chaotic", lambda: self.quick_generate('chaotic'))
        generate_btn.setMenu(gen_menu)
        generate_btn.clicked.connect(self.generate_random_network)
        toolbar.addWidget(generate_btn)
        
        # Add neuron button
        add_neuron_btn = QPushButton("➕ Neuron")
        add_neuron_btn.setToolTip("Add a new neuron")
        add_neuron_btn.clicked.connect(self.show_add_neuron_dialog)
        toolbar.addWidget(add_neuron_btn)
        
        toolbar.addSeparator()
        
        # Auto-fix button
        fix_btn = QPushButton("🔧")
        fix_btn.setToolTip("Auto-fix connectivity issues")
        fix_btn.clicked.connect(self.run_auto_fix)
        toolbar.addWidget(fix_btn)
        
        # Validate button
        validate_btn = QPushButton("✓")
        validate_btn.setToolTip("Validate design")
        validate_btn.clicked.connect(self.check_status)
        toolbar.addWidget(validate_btn)
        
        toolbar.addSeparator()
        
        # Save/Load buttons
        save_btn = QPushButton("💾")
        save_btn.setToolTip("Save design to file")
        save_btn.clicked.connect(self.save_design)
        toolbar.addWidget(save_btn)
        
        load_btn = QPushButton("📂")
        load_btn.setToolTip("Load design from file")
        load_btn.clicked.connect(self.load_design)
        toolbar.addWidget(load_btn)
        
        # Apply to brain button
        apply_btn = QPushButton("▶ Apply")
        apply_btn.setToolTip("Apply design to brain widget")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        apply_btn.clicked.connect(self.apply_to_brain_widget)
        toolbar.addWidget(apply_btn)
    
    def sync_from_brain_widget(self):
        """Import current state from brain_widget into design."""
        if not self.brain_widget:
            return
        
        self.design = BrainDesign()
        
        # Import neurons
        for name, pos in self.brain_widget.neuron_positions.items():
            if is_core_neuron(name):
                ntype = NeuronType.CORE
            elif is_input_sensor(name) or name == 'can_see_food':
                ntype = NeuronType.SENSOR
            else:
                ntype = NeuronType.HIDDEN
            
            neuron = DesignerNeuron(
                name=name,
                neuron_type=ntype,
                position=pos,
                is_binary=is_binary_neuron(name)
            )
            self.design.add_neuron(neuron)
        
        # Import connections
        for (src, tgt), weight in self.brain_widget.weights.items():
            self.design.connections.append(DesignerConnection(src, tgt, weight))
        
        # Import layers if available
        if hasattr(self.brain_widget, 'layers'):
            for layer_data in self.brain_widget.layers:
                self.design.layers.append(DesignerLayer.from_dict(layer_data))
        
        # Update all panels
        self._update_panels()
        self.update_status()
    
    def apply_to_brain_widget(self):
        """Apply design changes back to brain_widget."""
        if not self.brain_widget:
            QMessageBox.warning(self, "No Brain", "No brain widget connected")
            return
        
        # Validate first
        is_valid, issues, _ = self.design.validate(auto_fix=False)
        if not is_valid:
            reply = QMessageBox.question(
                self, "Validation Issues",
                f"Design has issues:\n\n" + "\n".join(issues[:5]) +
                "\n\nApply anyway?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        # Update neuron positions
        self.brain_widget.neuron_positions = {
            n.name: n.position for n in self.design.neurons.values()
        }
        
        # Update weights
        self.brain_widget.weights = {
            (c.source, c.target): c.weight for c in self.design.connections
        }
        
        # Update visible neurons
        self.brain_widget.visible_neurons = set(self.design.neurons.keys())
        
        # Update state for new neurons
        for name in self.design.neurons.keys():
            if name not in self.brain_widget.state:
                neuron = self.design.neurons[name]
                if neuron.is_binary:
                    self.brain_widget.state[name] = False
                elif neuron.is_core:
                    self.brain_widget.state[name] = 50.0
                else:
                    self.brain_widget.state[name] = 0.0
        
        # Update layers
        self.brain_widget.layers = [l.to_dict() for l in self.design.layers]
        
        # Mark render dirty and refresh
        self.brain_widget.mark_render_dirty()
        self.brain_widget.update()
        
        self.status_bar.showMessage("Applied to brain widget!", 3000)
        self.requestRefresh.emit()
    
    def _update_panels(self):
        """Update all panels with current design."""
        # Update sensors panel design reference
        self.sensors_panel.design = self.design
        self.sensors_panel.refresh()
        
        # Update properties panel design reference
        self.props_panel.design = self.design
        self.props_panel.set_neuron(None)
        
        # Update connections panel
        self.connections_panel.design = self.design
        self.connections_panel.refresh()
        
        # Update layers panel
        self.layers_panel.design = self.design
        self.layers_panel.refresh()
        
        # Update outputs panel
        if self.outputs_panel:
            self.outputs_panel.design = self.design
            self.outputs_panel.refresh()
    
    def _on_design_changed(self, *args):
        """Handle design changes."""
        self.update_status()
        self.designChanged.emit()
    
    def update_status(self):
        """Update status bar with design stats."""
        stats = self.design.get_stats()
        self.status_bar.showMessage(
            f"Neurons: {stats['total_neurons']} | "
            f"Connections: {stats['connections']} | "
            f"Layers: {stats['layers']}"
        )
    
    def select_neuron(self, name):
        """Select a neuron in the properties panel."""
        self.props_panel.set_neuron(name)
        self.tabs.setCurrentWidget(self.props_panel)
        self.neuronSelected.emit(name)
    
    def show_add_neuron_dialog(self):
        """Show dialog to add a neuron."""
        dialog = QuickAddNeuronDialog(self.design, parent=self)
        if dialog.exec_() == QDialog.Accepted and dialog.result_name:
            self._on_design_changed()
            self._update_panels()
            self.select_neuron(dialog.result_name)
    
    def generate_random_network(self):
        """Show the sparse network generation dialog."""
        dialog = SparseNetworkDialog(self.design, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            self._on_design_changed()
            self._update_panels()
    
    def quick_generate(self, preset):
        """Quick generate with a preset."""
        generator = SparseNetworkGenerator()
        presets = generator.get_preset_styles()
        
        if preset not in presets:
            return
        
        info = presets[preset]
        
        # Ensure required neurons exist
        self.design.add_missing_required_neurons()
        
        # Clear existing connections
        self.design.connections.clear()
        
        # Generate
        connections = generator.generate_connections(
            density=info['density'],
            include_feedback_loops=info.get('include_feedback', True),
            weight_noise=info.get('weight_noise', 1.0)
        )
        
        for src, tgt, weight in connections:
            if src in self.design.neurons and tgt in self.design.neurons:
                self.design.add_connection(src, tgt, weight)
        
        self._on_design_changed()
        self._update_panels()
        self.status_bar.showMessage(f"Generated {len(connections)} connections ({preset})", 3000)
    
    def run_auto_fix(self):
        """Run auto-fix on the design."""
        count, actions = self.design.auto_fix_connectivity()
        if count > 0:
            self._on_design_changed()
            self._update_panels()
            QMessageBox.information(
                self, "Auto-Fix",
                f"Fixed {count} issues:\n\n" + "\n".join(actions[:10])
            )
        else:
            QMessageBox.information(self, "Auto-Fix", "No issues found.")
    
    def check_status(self):
        """Show design validation status."""
        is_valid, issues, _ = self.design.validate(auto_fix=False)
        stats = self.design.get_stats()
        
        msg = (
            f"Neurons: {stats['total_neurons']}\n"
            f"  • Required: {stats['required_neurons']}\n"
            f"  • Sensors: {stats['sensor_neurons']}\n"
            f"  • Custom: {stats['custom_neurons']}\n\n"
            f"Connections: {stats['connections']}\n"
            f"Layers: {stats['layers']}\n"
        )
        
        if issues:
            msg += "\n⚠️ ISSUES:\n" + "\n".join(f"  • {i}" for i in issues)
        else:
            msg += "\n✅ Status: OK"
        
        QMessageBox.information(self, "Design Status", msg)
    
    def save_design(self):
        """Save design to file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Design", "brain_design.json", "JSON (*.json)"
        )
        if path:
            success, msg = self.design.save(path)
            if success:
                QMessageBox.information(self, "Saved", msg)
            else:
                QMessageBox.warning(self, "Error", msg)
    
    def load_design(self):
        """Load design from file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Design", "", "JSON (*.json)"
        )
        if path:
            try:
                self.design = BrainDesign.load(path)
                self._update_panels()
                self._on_design_changed()
                QMessageBox.information(
                    self, "Loaded",
                    f"Loaded {len(self.design.neurons)} neurons, "
                    f"{len(self.design.connections)} connections"
                )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load: {e}")
    
    def closeEvent(self, event):
        """Handle close - just hide instead of destroy."""
        self.hide()
        event.ignore()
