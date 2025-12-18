"""
Brain Designer Window - Main application window for designing custom neural networks.

This module provides a visual editor for creating and editing squid brain configurations
including neurons, connections, layers, sensors, and output bindings.
"""

import sys
import random
import math
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QStatusBar,
    QAction, QToolBar, QLabel, QComboBox, QPushButton, QMessageBox, QFileDialog,
    QDialog, QInputDialog, QFrame, QSizePolicy, QToolButton, QMenu, QSplitter,
    QFormLayout, QSpinBox, QDoubleSpinBox, QDialogButtonBox, QLineEdit,
    QColorDialog, QGroupBox, QApplication, QCheckBox
)
from PyQt5.QtGui import (
    QKeySequence, QIcon, QFont, QFontMetrics, QPainter, QColor, QPalette,
    QTextDocument, QAbstractTextDocumentLayout
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QRectF, QSizeF, pyqtSignal, QPointF

from designer_logging import get_logger, log_exceptions, safe_call, OperationLogger
from designer_core import BrainDesign, DesignerNeuron, DesignerLayer, DesignerConnection
from designer_canvas import BrainCanvas
from designer_constants import NeuronType, DEFAULT_COLORS

# Import brain state bridge for game communication
try:
    from brain_state_bridge import (
        is_game_running,
        import_brain_state_for_designer,
        convert_to_brain_design,
        export_design_to_game
    )
    _HAS_BRAIN_BRIDGE = True
except ImportError:
    _HAS_BRAIN_BRIDGE = False
    print("[BrainDesigner] Warning: brain_state_bridge not found, live import disabled")

from designer_panels import (
    LayersPanel, SensorsPanel, NeuronPropertiesPanel, ConnectionsTable, AddNeuronDialog
)
from designer_templates import TemplateManager
from designer_dialogs import SparseNetworkDialog, ActivationEditorDialog
from designer_network_generator import SparseNetworkGenerator

# Import the new outputs panel
try:
    from designer_outputs_panel import NeuronOutputsPanel
    _HAS_OUTPUTS_PANEL = True
except ImportError:
    _HAS_OUTPUTS_PANEL = False
    print("[BrainDesigner] Warning: designer_outputs_panel not found, outputs tab disabled")


class ScrollingTicker(QWidget):
    """A widget that smoothly scrolls rich text (HTML) horizontally."""
    
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.text = text
        self.offset = 0
        
        # Prepare text document for HTML rendering
        self.doc = QTextDocument()
        self.doc.setDefaultFont(self.font())
        self.doc.setHtml(self.text)
        self.doc.setTextWidth(-1)  # No wrap
        
        # Calculate dimensions
        self.text_width = self.doc.idealWidth()
        self.text_height = self.doc.size().height()
        
        # Separator
        self.sep_doc = QTextDocument()
        self.sep_doc.setDefaultFont(self.font())
        self.sep_doc.setHtml("<span style='color:gray'>   •   </span>")
        self.sep_doc.setTextWidth(-1)
        self.sep_width = self.sep_doc.idealWidth()
        
        # Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll_text)
        self.timer.setInterval(30)
        
        # Style
        self.setStyleSheet("background-color: transparent;")
        self.setFixedHeight(30)
    
    def showEvent(self, event):
        """Start timer when widget becomes visible."""
        super().showEvent(event)
        if not self.timer.isActive():
            self.timer.start()
    
    def hideEvent(self, event):
        """Stop timer when widget becomes hidden."""
        super().hideEvent(event)
        self.timer.stop()
    
    def scroll_text(self):
        """Update scroll offset and trigger repaint."""
        self.offset -= 1
        if self.offset <= -(self.text_width + self.sep_width):
            self.offset = 0
        self.update()
    
    def paintEvent(self, event):
        """Paint the scrolling text."""
        painter = QPainter(self)
        if not painter.isActive():
            return
        
        painter.setRenderHint(QPainter.Antialiasing)
        y_pos = (self.height() - self.text_height) / 2
        
        current_x = self.offset
        while current_x < self.width():
            painter.save()
            painter.translate(current_x, y_pos)
            self.doc.drawContents(painter, QRectF(0, 0, self.text_width, self.text_height))
            painter.restore()
            
            current_x += self.text_width
            
            painter.save()
            painter.translate(current_x, y_pos)
            self.sep_doc.drawContents(painter, QRectF(0, 0, self.sep_width, self.text_height))
            painter.restore()
            
            current_x += self.sep_width


class BrainDesignerWindow(QMainWindow):
    """Main window for the Brain Designer application."""

    exitRequested = pyqtSignal()

    def __init__(self, parent=None, embedded_mode=False):
        super().__init__(parent)
        self.logger = get_logger("brain_designer.window")
        self.embedded_mode = embedded_mode
        
        # Layer management for feedforward networks
        self.network_layers = {}  # name -> {'neurons': [...], 'color': QColor}
        self.layer_counter = 0

        try:
            self.design = BrainDesign()
            self.design.add_missing_required_neurons()

            self.setWindowTitle("Brain Designer - Dosidicus-2")
            self.setMinimumSize(1280, 900)

            self.setup_ui()
            self.setup_menus()
            self.setup_toolbar()

            if not self.embedded_mode:
                self._imported_from_game = False
                if not self._try_import_from_game():
                    self.generate_initial_network()
                
                if self._imported_from_game:
                    self._show_import_notification()

            self.refresh_all()
            self.update_status()
            
            # Collapse the right panel by default after UI is set up
            QTimer.singleShot(100, self._collapse_right_panel_on_start)

        except Exception as e:
            self.logger.critical(f"Failed to initialize window: {e}", exc_info=True)
            raise

    def _collapse_right_panel_on_start(self):
        """Collapse the right panel on startup."""
        if not self.sidebar_collapsed:
            self.toggle_right_panel()

    def setup_ui(self):
        """Setup the main UI layout."""
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # === LEFT/CENTER: CANVAS AREA ===
        canvas_wrapper = QWidget()
        canvas_wrapper.setMinimumWidth(500)
        
        canvas_container = QVBoxLayout(canvas_wrapper)
        canvas_container.setContentsMargins(0, 0, 0, 0)
        canvas_container.setSpacing(5)

        canvas_container.addWidget(self.create_canvas_toolbar())

        self.canvas = BrainCanvas(self.design)
        self.canvas.neuronSelected.connect(self.on_neuron_selected)
        self.canvas.connectionCreated.connect(self.on_connection_created)
        self.canvas.connectionSelected.connect(self.on_connection_selected)
        self.canvas.weightChanged.connect(self.on_weight_changed)
        self.canvas.connectionDeleted.connect(self.on_connection_deleted)

        canvas_container.addWidget(self.canvas)
        canvas_container.addWidget(self.create_help_bar())

        self.splitter.addWidget(canvas_wrapper)

        # === RIGHT PANEL (Tabbed Panels) ===
        self.right_panel = QTabWidget()
        self.right_panel.setTabPosition(QTabWidget.West)
        self.right_panel.setMinimumWidth(32)  # Allow it to shrink to just the tab bar
        
        # Apply style for blue selected tab
        self.right_panel.setStyleSheet("""
            QTabBar::tab:selected {
                background: #2196F3;
                color: white;
                font-weight: bold;
            }
        """)
        
        # Connect tab click to auto-expand logic
        self.right_panel.tabBarClicked.connect(self.on_tab_bar_clicked)

        self.layers_panel = LayersPanel(self.design)
        self.layers_panel.layersChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.layers_panel, "Layers")

        self.sensors_panel = SensorsPanel(self.design)
        self.sensors_panel.sensorsChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.sensors_panel, "Sensors")

        self.props_panel = NeuronPropertiesPanel(self.design)
        self.props_panel.neuronChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.props_panel, "Properties")

        self.connections_table = ConnectionsTable(self.design)
        self.right_panel.addTab(self.connections_table, "Connections")

        if _HAS_OUTPUTS_PANEL:
            self.outputs_panel = NeuronOutputsPanel(self.design)
            self.outputs_panel.outputsChanged.connect(self.on_design_changed)
            self.right_panel.addTab(self.outputs_panel, "Outputs")
        else:
            self.outputs_panel = None

        self.splitter.addWidget(self.right_panel)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes([850, 400])
        
        # Start collapsed
        self.sidebar_collapsed = False
        self.last_sidebar_width = 400

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        if self.embedded_mode:
            self.return_btn = QPushButton("Switch to Game")
            self.return_btn.setStyleSheet("""
                QPushButton {
                    background-color: #673AB7;
                    color: white;
                    font-weight: bold;
                    padding: 2px 15px;
                    margin-right: 5px;
                    border-radius: 3px;
                }
            """)
            self.return_btn.clicked.connect(self.exitRequested.emit)
            self.status_bar.addPermanentWidget(self.return_btn)

    def on_tab_bar_clicked(self, index):
        """Triggered when a tab is clicked. Expands the sidebar if it was collapsed."""
        if self.sidebar_collapsed:
            self.toggle_right_panel()

    def toggle_right_panel(self):
        """Toggle the visibility of the right property/layer panel, leaving tabs visible."""
        sizes = self.splitter.sizes()
        
        # Calculate the approximate width of the vertical tab bar
        tab_bar_width = self.right_panel.tabBar().sizeHint().width() + 4
        
        if not self.sidebar_collapsed:
            # COLLAPSE: Shrink to just the tab bar width
            self.last_sidebar_width = sizes[1] if sizes[1] > tab_bar_width else 400
            self.splitter.setSizes([sum(sizes) - tab_bar_width, tab_bar_width])
            self.toggle_btn.setText("◀")
            self.sidebar_collapsed = True
        else:
            # RESTORE: Return to previous width
            width = self.last_sidebar_width
            self.splitter.setSizes([sum(sizes) - width, width])
            self.toggle_btn.setText("▶")
            self.sidebar_collapsed = False

    def create_canvas_toolbar(self) -> QFrame:
        """Create the toolbar with the requested button order."""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.StyledPanel)
        toolbar.setMaximumHeight(45)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # 1. Tiny Generator (Dice) - NOW FIRST
        self.dice_btn = QPushButton("🎲")
        self.dice_btn.setToolTip("Instant chaotic shuffle")
        self.dice_btn.setFixedWidth(35)
        self.dice_btn.setStyleSheet("""
            QPushButton { background-color: #FF9800; color: white; font-size: 16px; padding: 4px; border-radius: 4px; }
            QPushButton:hover { background-color: #F57C00; }
        """)
        self.dice_btn.clicked.connect(self.instant_random_generate)
        layout.addWidget(self.dice_btn)

        # 2. Main Generate Button
        generate_btn = QPushButton("🎲 Generate")
        generate_btn.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px; }
            QPushButton:hover { background-color: #1976D2; }
        """)
        generate_btn.clicked.connect(self.show_sparse_network_dialog)
        layout.addWidget(generate_btn)

        # 3. Add Neuron
        add_neuron_btn = QPushButton("➕ Neuron")
        add_neuron_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; }
            QPushButton:hover { background-color: #43A047; }
        """)
        add_neuron_btn.clicked.connect(self.show_add_neuron_dialog)
        layout.addWidget(add_neuron_btn)

        # 4. Export
        export_btn = QPushButton("📤 EXPORT")
        export_btn.setStyleSheet("""
            QPushButton { background-color: #FF5722; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; }
            QPushButton:hover { background-color: #E64A19; }
        """)
        export_btn.clicked.connect(self.export_design)
        layout.addWidget(export_btn)

        # 5. Clear Connections
        clear_btn = QPushButton("🗑 Clear")
        clear_btn.setStyleSheet("color: #d32f2f; font-weight: bold;")
        clear_btn.clicked.connect(self.clear_all_connections)
        layout.addWidget(clear_btn)
        
        # 6. Quick Gen Menu (Tiny dropdown) - NOW LAST in group
        quick_gen_btn = QToolButton()
        quick_gen_btn.setText("▼")
        quick_gen_btn.setPopupMode(QToolButton.InstantPopup)
        quick_menu = QMenu(quick_gen_btn)
        generator = SparseNetworkGenerator()
        for key, info in generator.get_preset_styles().items():
            action = quick_menu.addAction(f"{info['name']}")
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.quick_generate(k))
        quick_gen_btn.setMenu(quick_menu)
        layout.addWidget(quick_gen_btn)

        self._sync_btn_container = QFrame()
        self._sync_btn_layout = QHBoxLayout(self._sync_btn_container)
        self._sync_btn_layout.setContentsMargins(0, 0, 0, 0)
        self._sync_btn_container.hide()
        layout.addWidget(self._sync_btn_container)

        layout.addStretch()

        # 7. Sidebar Hide Toggle - Far Right
        self.toggle_btn = QPushButton("▶")
        self.toggle_btn.setToolTip("Toggle Right Panel (Ctrl+B)")
        self.toggle_btn.setShortcut("Ctrl+B")
        self.toggle_btn.setFixedWidth(35)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background-color: #e0e0e0; }
        """)
        self.toggle_btn.clicked.connect(self.toggle_right_panel)
        layout.addWidget(self.toggle_btn)

        return toolbar

    def create_help_bar(self) -> QFrame:
        """Create the help bar below the canvas with scrolling ticker."""
        help_bar = QFrame()
        help_bar.setFrameStyle(QFrame.StyledPanel)
        help_bar.setMaximumHeight(30)
        layout = QHBoxLayout(help_bar)
        layout.setContentsMargins(0, 0, 0, 0)

        self.help_ticker = ScrollingTicker(
            "<span style='color:#333'>💡 <b> Left-Drag</b> from neuron to create connection </span>"
            "<span style='color:#333'><b> Ctrl+Drag</b> neuron to move it </span>"
            "<span style='color:#333'><b> Right-Drag</b> to pan canvas </span>"
            "<span style='color:#333'><b> Scroll Wheel</b> to zoom (or adjust weight on connection) </span>"
            "<span style='color:#333'><b> Double-Click</b> connection to edit weight </span>"
            "<span style='color:#333'><b> Click</b> neuron/connection to select </span>"
            "<span style='color:#333'><b> Del</b> to delete selected </span>"
            "<span style='color:#333'><b> Space</b> to reverse connection direction </span>"
            "<span style='color:#333'><b> +/-</b> keys to adjust weight (Shift for larger steps) </span>"
            "<span style='color:#333'><b> Page Up/Down</b> to adjust weight (large steps) </span>"
            "<span style='color:#333'><b> Shift+N</b> to add neuron </span>"
            "<span style='color:#333'><b> Ctrl+S</b> to save </span>"
            "<span style='color:#333'><b> Ctrl+O</b> to open </span>"
            "<span style='color:#333'><b> Ctrl+E</b> to export </span>"
            "<span style='color:#333'><b> Ctrl+N</b> for new design </span>"
            "<span style='color:#333'><b> Ctrl+G</b> to generate network </span>"
            "<span style='color:#333'>🎲 <b>Dice button</b> for instant chaotic shuffle & generation </span>"
            "<span style='color:#333'><b>Outputs tab</b> to bind neurons to squid behaviors </span>"
        )
        layout.addWidget(self.help_ticker)

        return help_bar

    def setup_menus(self):
        """Setup the menu bar."""
        menu = self.menuBar()

        file_menu = menu.addMenu("File")
        
        if self.embedded_mode:
            return_action = QAction("Save & Return to Game", self)
            return_action.setShortcut("Ctrl+Return")
            return_action.triggered.connect(self.exitRequested.emit)
            file_menu.addAction(return_action)
            file_menu.addSeparator()

        new_action = QAction("New Design", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_design)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        export_action = QAction("Export for Dosidicus...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_design)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        open_action = QAction("Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_design)
        file_menu.addAction(open_action)

        edit_menu = menu.addMenu("Edit")

        generate_action = QAction("Generate Network...", self)
        generate_action.setShortcut("Ctrl+G")
        generate_action.triggered.connect(self.show_sparse_network_dialog)
        edit_menu.addAction(generate_action)

        edit_menu.addSeparator()

        auto_fix = QAction("Auto-Fix Connectivity", self)
        auto_fix.triggered.connect(self.run_auto_fix)
        edit_menu.addAction(auto_fix)

        edit_menu.addSeparator()

        clear_conn_action = QAction("Clear All", self)
        clear_conn_action.triggered.connect(self.clear_all_connections)
        edit_menu.addAction(clear_conn_action)
        
        if _HAS_OUTPUTS_PANEL:
            clear_outputs_action = QAction("Clear all Bindings", self)
            clear_outputs_action.triggered.connect(self.clear_all_outputs)
            edit_menu.addAction(clear_outputs_action)

        # === NEW: Network Menu ===
        network_menu = menu.addMenu("Network")
        
        add_layer_action = QAction("Add Hidden Layer...", self)
        add_layer_action.setToolTip("Add a layer of neurons at once")
        add_layer_action.triggered.connect(self.show_add_layer_dialog)
        network_menu.addAction(add_layer_action)
        
        connect_layers_action = QAction("Connect Layers...", self)
        connect_layers_action.setToolTip("Connect neurons between two layers")
        connect_layers_action.triggered.connect(self.show_connect_layers_dialog)
        network_menu.addAction(connect_layers_action)
        
        network_menu.addSeparator()
        
        feedforward_action = QAction("Create Feedforward Network...", self)
        feedforward_action.setToolTip("Create a complete feedforward neural network")
        feedforward_action.triggered.connect(self.show_feedforward_dialog)
        network_menu.addAction(feedforward_action)
        
        network_menu.addSeparator()
        
        auto_layout_action = QAction("Auto-Layout Network", self)
        auto_layout_action.setToolTip("Arrange neurons automatically using force-directed layout")
        auto_layout_action.triggered.connect(self.auto_layout_network)
        network_menu.addAction(auto_layout_action)
        
        decluster_action = QAction("Decluster Neurons", self)
        decluster_action.setToolTip("Push apart neurons that are too close together")
        decluster_action.triggered.connect(lambda: self.decluster_neurons(120))
        network_menu.addAction(decluster_action)

        tpl_menu = menu.addMenu("Templates")
        for key, info in TemplateManager.get_templates().items():
            a = QAction(info['name'], self)
            a.setData(key)
            a.triggered.connect(self.load_template)
            tpl_menu.addAction(a)

        gen_menu = menu.addMenu("Generate")

        gen_dialog_action = QAction("🎲 Generate...", self)
        gen_dialog_action.setShortcut("Ctrl+G")
        gen_dialog_action.triggered.connect(self.show_sparse_network_dialog)
        gen_menu.addAction(gen_dialog_action)

        gen_menu.addSeparator()

        generator = SparseNetworkGenerator()
        for key, info in generator.get_preset_styles().items():
            action = QAction(f"{info['name']}", self)
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.quick_generate(k))
            gen_menu.addAction(action)

    def setup_toolbar(self):
        """Setup the main toolbar."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction("📂 Open", self.open_design)
        toolbar.addAction("💾 Save", self.save_design)

        toolbar.addSeparator()
        toolbar.addAction("📋 Templates", self.show_template_menu)

    # ========== NEW: Network Menu Methods ==========
    
    def show_add_layer_dialog(self):
        """Show dialog to add a layer of hidden neurons."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Hidden Layer")
        dialog.setMinimumWidth(350)
        layout = QFormLayout(dialog)
        
        # Prefix for neuron names
        prefix_edit = QLineEdit(f"hidden{self.layer_counter}_")
        prefix_edit.setToolTip("Prefix for neuron names in this layer")
        layout.addRow("Name Prefix:", prefix_edit)
        
        # Number of neurons
        count_spin = QSpinBox()
        count_spin.setRange(1, 50)
        count_spin.setValue(4)
        count_spin.setToolTip("Number of neurons to create")
        layout.addRow("Neuron Count:", count_spin)
        
        # X position
        x_spin = QSpinBox()
        x_spin.setRange(-2000, 2000)
        x_spin.setValue(300 + self.layer_counter * 200)
        x_spin.setToolTip("X position of the layer")
        layout.addRow("X Position:", x_spin)
        
        # Y position (center)
        y_spin = QSpinBox()
        y_spin.setRange(-2000, 2000)
        y_spin.setValue(200)
        y_spin.setToolTip("Y position (center of layer)")
        layout.addRow("Y Position:", y_spin)
        
        # Vertical spacing
        spacing_spin = QSpinBox()
        spacing_spin.setRange(30, 200)
        spacing_spin.setValue(80)
        spacing_spin.setToolTip("Vertical spacing between neurons")
        layout.addRow("Spacing:", spacing_spin)
        
        # Color picker
        color_list = [150, 150, 220]
        color_btn = QPushButton()
        color_btn.setStyleSheet(f"background-color: rgb({color_list[0]},{color_list[1]},{color_list[2]});")
        color_btn.setText(f"#{color_list[0]:02x}{color_list[1]:02x}{color_list[2]:02x}")
        
        def pick_color():
            color = QColorDialog.getColor(QColor(*color_list), dialog, "Select Layer Color")
            if color.isValid():
                color_list[0] = color.red()
                color_list[1] = color.green()
                color_list[2] = color.blue()
                color_btn.setStyleSheet(f"background-color: {color.name()};")
                color_btn.setText(color.name())
        
        color_btn.clicked.connect(pick_color)
        layout.addRow("Color:", color_btn)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            prefix = prefix_edit.text()
            count = count_spin.value()
            x = x_spin.value()
            y_center = y_spin.value()
            spacing = spacing_spin.value()
            color = tuple(color_list)
            
            # Calculate starting y position to center the layer
            total_height = (count - 1) * spacing
            y_start = y_center - total_height / 2
            
            layer_name = f"layer{self.layer_counter}"
            layer_neurons = []
            
            for i in range(count):
                # Generate unique name
                base_name = f"{prefix}{i}"
                actual_name = base_name
                idx = 0
                while actual_name in self.design.neurons:
                    actual_name = f"{base_name}_{idx}"
                    idx += 1
                
                y_pos = y_start + i * spacing
                
                neuron = DesignerNeuron(
                    name=actual_name,
                    neuron_type=NeuronType.HIDDEN,
                    position=(x, y_pos),
                    color=color,
                    shape='circle'
                )
                self.design.add_neuron(neuron)
                layer_neurons.append(actual_name)
            
            # Track the layer for connecting later
            self.network_layers[layer_name] = {
                'neurons': layer_neurons,
                'color': QColor(*color).name()
            }
            self.layer_counter += 1
            
            self.on_design_changed()
            self.status_bar.showMessage(f"Added layer '{layer_name}' with {count} neurons", 3000)

    def show_connect_layers_dialog(self):
        """Show dialog to connect two layers."""
        if len(self.network_layers) < 2:
            QMessageBox.warning(
                self, "Connect Layers", 
                "Need at least 2 layers to connect.\n\nUse 'Network > Add Hidden Layer' to create layers first."
            )
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Connect Layers")
        dialog.setMinimumWidth(350)
        layout = QFormLayout(dialog)
        
        layer_names = list(self.network_layers.keys())
        
        # Source layer
        source_combo = QComboBox()
        source_combo.addItems(layer_names)
        layout.addRow("Source Layer:", source_combo)
        
        # Target layer
        target_combo = QComboBox()
        target_combo.addItems(layer_names)
        if len(layer_names) >= 2:
            target_combo.setCurrentIndex(1)
        layout.addRow("Target Layer:", target_combo)
        
        # Connection type
        type_combo = QComboBox()
        type_combo.addItems(["Fully Connected", "One-to-One (Matching Size)"])
        type_combo.setToolTip("Fully Connected: Every source neuron connects to every target\nOne-to-One: Each source connects to corresponding target")
        layout.addRow("Connection Type:", type_combo)
        
        # Weight range
        min_weight = QDoubleSpinBox()
        min_weight.setRange(-1.0, 1.0)
        min_weight.setValue(-0.5)
        min_weight.setSingleStep(0.1)
        min_weight.setDecimals(2)
        layout.addRow("Min Weight:", min_weight)
        
        max_weight = QDoubleSpinBox()
        max_weight.setRange(-1.0, 1.0)
        max_weight.setValue(0.5)
        max_weight.setSingleStep(0.1)
        max_weight.setDecimals(2)
        layout.addRow("Max Weight:", max_weight)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            source_name = source_combo.currentText()
            target_name = target_combo.currentText()
            
            if source_name == target_name:
                QMessageBox.warning(self, "Error", "Source and target layers must be different.")
                return
            
            source_neurons = self.network_layers[source_name]['neurons']
            target_neurons = self.network_layers[target_name]['neurons']
            conn_type = type_combo.currentText()
            w_min = min_weight.value()
            w_max = max_weight.value()
            
            added = 0
            
            if conn_type == "Fully Connected":
                for src in source_neurons:
                    for tgt in target_neurons:
                        if src in self.design.neurons and tgt in self.design.neurons:
                            weight = random.uniform(w_min, w_max)
                            self.design.add_connection(src, tgt, weight)
                            added += 1
            else:  # One-to-One
                if len(source_neurons) != len(target_neurons):
                    QMessageBox.warning(
                        self, "Size Mismatch",
                        f"One-to-One requires matching layer sizes.\n"
                        f"Source has {len(source_neurons)}, target has {len(target_neurons)}."
                    )
                    return
                for src, tgt in zip(source_neurons, target_neurons):
                    if src in self.design.neurons and tgt in self.design.neurons:
                        weight = random.uniform(w_min, w_max)
                        self.design.add_connection(src, tgt, weight)
                        added += 1
            
            self.on_design_changed()
            self.status_bar.showMessage(f"Added {added} connections from {source_name} to {target_name}", 3000)

    def show_feedforward_dialog(self):
        """Show dialog to create a complete feedforward network using core neurons."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Create Feedforward Network")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        
        # Info section
        info = QLabel(
            "<b>Feedforward Network</b><br><br>"
            "<b>Input neurons (always included):</b><br>"
            "hunger, happiness, cleanliness, sleepiness<br><br>"
            "<b>Output neurons (always included):</b><br>"
            "satisfaction, anxiety, curiosity<br><br>"
            "The network flows from top (inputs) to bottom (outputs)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("background-color: #E3F2FD; padding: 10px; border-radius: 6px;")
        layout.addWidget(info)
        
        # Optional sensors group
        sensors_group = QGroupBox("Optional Input Sensors")
        sensors_layout = QVBoxLayout(sensors_group)
        
        self._ff_sensor_checks = {}
        optional_sensors = ['can_see_food', 'is_fleeing', 'plant_proximity']
        for sensor in optional_sensors:
            cb = QCheckBox(sensor.replace('_', ' ').title())
            cb.setProperty('sensor_name', sensor)
            # Check if already in design
            if sensor in self.design.neurons:
                cb.setChecked(True)
            self._ff_sensor_checks[sensor] = cb
            sensors_layout.addWidget(cb)
        
        layout.addWidget(sensors_group)
        
        # Hidden layers group
        hidden_group = QGroupBox("Hidden Layers")
        hidden_layout = QFormLayout(hidden_group)
        
        hidden_edit = QLineEdit("4")
        hidden_edit.setPlaceholderText("e.g., 4 or 4,3 for multiple layers")
        hidden_edit.setToolTip(
            "Enter neuron counts for hidden layers.\n"
            "Examples:\n"
            "  4 = one hidden layer with 4 neurons\n"
            "  4,3 = two hidden layers (4 then 3 neurons)\n"
            "  Leave empty for no hidden layers"
        )
        hidden_layout.addRow("Layer sizes:", hidden_edit)
        
        layout.addWidget(hidden_group)
        
        # Clear option
        clear_check = QCheckBox("Remove existing non-core neurons")
        clear_check.setChecked(True)
        clear_check.setToolTip("Remove custom and sensor neurons before creating the network")
        layout.addWidget(clear_check)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec_() == QDialog.Accepted:
            # Parse hidden layers
            hidden_text = hidden_edit.text().strip()
            hidden_sizes = []
            if hidden_text:
                try:
                    hidden_sizes = [int(s.strip()) for s in hidden_text.split(',') 
                                    if s.strip().isdigit() and int(s.strip()) > 0]
                except ValueError:
                    pass
            
            # Get selected sensors
            selected_sensors = [sensor for sensor, cb in self._ff_sensor_checks.items() 
                               if cb.isChecked()]
            
            # Clear non-core if requested
            if clear_check.isChecked():
                from designer_network_generator import SparseNetworkGenerator
                generator = SparseNetworkGenerator()
                generator.remove_non_core_neurons(self.design)
                self.design.connections.clear()
                self.network_layers.clear()
                self.layer_counter = 0
            
            # Create the network
            self._create_feedforward_network(hidden_sizes, selected_sensors)

    def _create_feedforward_network(self, hidden_layer_sizes, optional_sensors):
        """
        Create a feedforward network using core neurons as inputs/outputs.
        
        Layout: TOP to BOTTOM
          - Input layer (top): hunger, happiness, cleanliness, sleepiness + optional sensors
          - Hidden layers (middle): user-defined sizes
          - Output layer (bottom): satisfaction, anxiety, curiosity
        """
        # Core input neurons (always used)
        core_inputs = ['hunger', 'happiness', 'cleanliness', 'sleepiness']
        
        # Core output neurons (always used)
        core_outputs = ['satisfaction', 'anxiety', 'curiosity']
        
        # Add optional sensors to inputs
        input_neurons = core_inputs.copy()
        for sensor in optional_sensors:
            if sensor not in self.design.neurons:
                self.design.add_sensor(sensor, create_default_connections=False)
            if sensor not in input_neurons:
                input_neurons.append(sensor)
        
        # Ensure all core neurons exist
        self.design.add_missing_required_neurons()
        
        # ====================================================================
        # LAYOUT PARAMETERS - Adjust these to change network appearance
        # ====================================================================
        x_center = 400              # Horizontal center of the network
        y_start = 50                # Input layer Y position (top)
        y_spacing = 150             # Vertical spacing between layers
        neuron_spacing = 180        # Horizontal spacing between neurons (increase if crowded)
        
        all_layer_neurons = []
        current_y = y_start
        
        # === INPUT LAYER (TOP) ===
        # Position input neurons horizontally centered
        total_width = (len(input_neurons) - 1) * neuron_spacing
        x_start = x_center - total_width / 2
        
        for i, name in enumerate(input_neurons):
            x_pos = x_start + i * neuron_spacing
            if name in self.design.neurons:
                self.design.neurons[name].position = (x_pos, current_y)
        
        all_layer_neurons.append(input_neurons)
        self.network_layers['ff_input'] = {
            'neurons': input_neurons.copy(),
            'color': '#96DC96'  # Greenish
        }
        
        current_y += y_spacing
        
        # === HIDDEN LAYERS (MIDDLE) ===
        for layer_idx, size in enumerate(hidden_layer_sizes):
            layer_name = f"ff_hidden{layer_idx}"
            layer_neurons = []
            
            total_width = (size - 1) * neuron_spacing
            x_start = x_center - total_width / 2
            
            # Color for hidden layers (bluish, varying shades)
            hue_offset = (layer_idx * 20) % 60
            color = (150 - hue_offset, 150 - hue_offset, 220)
            
            for i in range(size):
                neuron_name = f"hidden{layer_idx}_{i}"
                x_pos = x_start + i * neuron_spacing
                
                # Make sure name is unique
                while neuron_name in self.design.neurons:
                    neuron_name = f"hidden{layer_idx}_{i}_{random.randint(0, 999)}"
                
                neuron = DesignerNeuron(
                    name=neuron_name,
                    neuron_type=NeuronType.HIDDEN,
                    position=(x_pos, current_y),
                    color=color,
                    shape='circle'
                )
                self.design.add_neuron(neuron)
                layer_neurons.append(neuron_name)
            
            all_layer_neurons.append(layer_neurons)
            self.network_layers[layer_name] = {
                'neurons': layer_neurons,
                'color': QColor(*color).name()
            }
            
            current_y += y_spacing
        
        # === OUTPUT LAYER (BOTTOM) ===
        total_width = (len(core_outputs) - 1) * neuron_spacing
        x_start = x_center - total_width / 2
        
        for i, name in enumerate(core_outputs):
            x_pos = x_start + i * neuron_spacing
            if name in self.design.neurons:
                self.design.neurons[name].position = (x_pos, current_y)
        
        all_layer_neurons.append(core_outputs)
        self.network_layers['ff_output'] = {
            'neurons': core_outputs.copy(),
            'color': '#DC9696'  # Reddish
        }
        
        # === CREATE CONNECTIONS (fully connected between adjacent layers) ===
        for layer_i in range(len(all_layer_neurons) - 1):
            source_layer = all_layer_neurons[layer_i]
            target_layer = all_layer_neurons[layer_i + 1]
            
            for src in source_layer:
                for tgt in target_layer:
                    if src in self.design.neurons and tgt in self.design.neurons:
                        weight = random.uniform(-0.5, 0.5)
                        self.design.add_connection(src, tgt, weight)
        
        self.layer_counter = len(hidden_layer_sizes) + 2
        self.on_design_changed()
        
        if self.canvas:
            self.canvas.center_on_neurons()
        
        # Calculate stats
        total_neurons = len(input_neurons) + sum(hidden_layer_sizes) + len(core_outputs)
        layer_sizes = [len(input_neurons)] + hidden_layer_sizes + [len(core_outputs)]
        total_connections = sum(layer_sizes[i] * layer_sizes[i+1] for i in range(len(layer_sizes)-1))
        
        self.status_bar.showMessage(
            f"Created feedforward network: {layer_sizes} ({total_neurons} neurons, {total_connections} connections)", 
            5000
        )

    def decluster_neurons(self, min_distance: float = 120):
        """
        Push apart any neurons that are too close together.
        
        Args:
            min_distance: Minimum distance between neuron centers (default 120px)
        """
        if len(self.design.neurons) < 2:
            return
        
        neurons = list(self.design.neurons.values())
        iterations = 10  # Multiple passes to resolve chain reactions
        
        for _ in range(iterations):
            moved = False
            for i, n1 in enumerate(neurons):
                if n1.position is None:
                    continue
                x1, y1 = n1.position
                
                for n2 in neurons[i+1:]:
                    if n2.position is None:
                        continue
                    x2, y2 = n2.position
                    
                    # Calculate distance
                    dx = x2 - x1
                    dy = y2 - y1
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    if dist < min_distance and dist > 0:
                        # Push apart
                        overlap = min_distance - dist
                        push = overlap / 2 + 5  # Extra 5px buffer
                        
                        # Normalize direction
                        nx = dx / dist
                        ny = dy / dist
                        
                        # Move both neurons away from each other
                        n1.position = (x1 - nx * push, y1 - ny * push)
                        n2.position = (x2 + nx * push, y2 + ny * push)
                        moved = True
                    elif dist == 0:
                        # Identical positions - move randomly
                        n2.position = (x2 + random.uniform(50, 100), y2 + random.uniform(-30, 30))
                        moved = True
            
            if not moved:
                break
        
        self.on_design_changed()

    def auto_layout_network(self):
        """Apply force-directed layout to arrange neurons automatically."""
        if len(self.design.neurons) < 2:
            self.status_bar.showMessage("Need at least 2 neurons to layout.", 3000)
            return
        
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.status_bar.showMessage("Applying auto-layout...")
        QApplication.processEvents()
        
        try:
            # Get canvas bounds
            if self.canvas and self.canvas.viewport():
                view_rect = self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect()
                center_x = view_rect.center().x()
                center_y = view_rect.center().y()
                width = max(600, view_rect.width() * 0.8)
                height = max(400, view_rect.height() * 0.8)
            else:
                center_x, center_y = 300, 250
                width, height = 600, 400
            
            # Force-directed layout parameters
            iterations = 80
            area = width * height
            k = math.sqrt(area / max(1, len(self.design.neurons)))  # Optimal distance
            temp = width / 8  # Initial temperature
            cooling = 0.95
            
            # Get current positions
            pos = {}
            for name, neuron in self.design.neurons.items():
                pos[name] = QPointF(neuron.position[0], neuron.position[1])
            
            names = list(self.design.neurons.keys())
            
            for iteration in range(iterations):
                # Calculate displacement for each neuron
                disp = {n: QPointF(0, 0) for n in names}
                
                # Repulsive forces between all pairs
                for i, n1 in enumerate(names):
                    for n2 in names[i+1:]:
                        delta = pos[n1] - pos[n2]
                        dist = math.hypot(delta.x(), delta.y()) or 0.01
                        force = (k * k) / dist
                        normalized = QPointF(delta.x() / dist, delta.y() / dist)
                        disp[n1] += normalized * force
                        disp[n2] -= normalized * force
                
                # Attractive forces along connections
                for conn in self.design.connections:
                    if conn.source in pos and conn.target in pos:
                        delta = pos[conn.target] - pos[conn.source]
                        dist = math.hypot(delta.x(), delta.y()) or 0.01
                        force = (dist * dist) / k
                        normalized = QPointF(delta.x() / dist, delta.y() / dist)
                        disp[conn.source] += normalized * force
                        disp[conn.target] -= normalized * force
                
                # Apply displacements with temperature limiting
                for n in names:
                    d = disp[n]
                    d_mag = math.hypot(d.x(), d.y()) or 0.01
                    # Limit displacement by temperature
                    limited = min(d_mag, temp)
                    new_pos = pos[n] + QPointF(d.x() / d_mag, d.y() / d_mag) * limited
                    
                    # Keep within bounds
                    new_pos.setX(max(center_x - width/2, min(center_x + width/2, new_pos.x())))
                    new_pos.setY(max(center_y - height/2, min(center_y + height/2, new_pos.y())))
                    pos[n] = new_pos
                
                temp *= cooling
                
                # Update display periodically
                if iteration % 15 == 0:
                    for name, p in pos.items():
                        self.design.neurons[name].position = (p.x(), p.y())
                    self.canvas.rebuild()
                    QApplication.processEvents()
            
            # Final position update
            for name, p in pos.items():
                self.design.neurons[name].position = (p.x(), p.y())
            
            self.on_design_changed()
            self.status_bar.showMessage("Auto-layout applied.", 3000)
            
        except Exception as e:
            self.logger.error(f"Auto-layout failed: {e}")
            self.status_bar.showMessage(f"Layout failed: {e}", 5000)
        finally:
            QApplication.restoreOverrideCursor()

    # ========== END Network Menu Methods ==========

    def push_to_game(self):
        """Export current design directly to the running game via the bridge."""
        if not _HAS_BRAIN_BRIDGE:
            return

        if not is_game_running():
            QMessageBox.warning(self, "Game Not Found", "Dosidicus does not appear to be running.")
            return

        try:
            if self.outputs_panel:
                self.design.output_bindings = self.outputs_panel.export_bindings()

            data = self.design.to_dosidicus_format()
            
            if export_design_to_game(data):
                self.status_bar.showMessage("Design pushed to bridge!", 5000)
                QMessageBox.information(self, "Push Successful", "Brain design has been sent to the game.")
            else:
                QMessageBox.warning(self, "Export Failed", "Could not write bridge file.")
                
        except Exception as e:
            self.logger.error(f"Push to game failed: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to push design:\n{e}")

    def load_from_brain_widget_state(self, state):
        """Load design from a brain widget state dictionary."""
        try:
            imported_design = None
            try:
                from brain_state_bridge import convert_to_brain_design
                imported_design = convert_to_brain_design(state)
            except ImportError:
                pass
            
            if imported_design is None:
                from designer_core import BrainDesign
                imported_design = BrainDesign.from_dosidicus_format(state)
            
            if imported_design is None:
                return False
            
            self.design = imported_design
            self.refresh_all()
            
            if hasattr(self, 'canvas'):
                self.canvas.center_on_neurons()
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading from state: {e}", exc_info=True)
            return False

    def get_current_design_state(self):
        """Get the current design as a state dictionary compatible with BrainWidget."""
        try:
            if self.outputs_panel:
                self.design.output_bindings = self.outputs_panel.export_bindings()
            return self.design.to_dosidicus_format()
        except Exception as e:
            self.logger.error(f"Error exporting state: {e}", exc_info=True)
            return None

    def refresh_all(self):
        """Refresh all panels with current design."""
        self.canvas.design = self.design
        self.props_panel.design = self.design
        self.layers_panel.design = self.design
        self.sensors_panel.design = self.design
        self.connections_table.design = self.design
        
        if self.outputs_panel:
            self.outputs_panel.design = self.design
            self.outputs_panel.load_bindings(self.design.output_bindings)
        
        self.on_design_changed()

    def update_status(self):
        """Update the status bar."""
        stats = self.design.get_stats()
        status_parts = [
            f"Neurons: {stats['total_neurons']}",
            f"Connections: {stats['connections']}",
            f"Required: {'✓' if stats['has_all_required'] else '✗'}"
        ]
        
        if self.outputs_panel:
            binding_count = len(self.outputs_panel.bindings)
            if binding_count > 0:
                status_parts.append(f"Outputs: {binding_count}")
        
        self.status_bar.showMessage(" | ".join(status_parts))

    def generate_initial_network(self):
        """Generate a random network on startup."""
        try:
            generator = SparseNetworkGenerator()
            density = 0.5 if random.random() < 0.5 else 1.0
            include_feedback = random.random() < 0.5

            generator.generate_for_design(
                self.design,
                clear_existing=True,
                density=density,
                include_feedback=include_feedback,
                silent=True
            )
        except Exception as e:
            self.logger.warning(f"Could not generate initial network: {e}")

    def _try_import_from_game(self) -> bool:
        """Attempt to import brain state from a running game instance."""
        if not _HAS_BRAIN_BRIDGE:
            return False
        
        try:
            if not is_game_running():
                return False
            
            live_state = import_brain_state_for_designer()
            if live_state is None:
                return False
            
            imported_design = convert_to_brain_design(live_state)
            if imported_design is None:
                return False
            
            self.design = imported_design
            if hasattr(self, 'canvas'):
                self.canvas.design = self.design
            
            self._imported_from_game = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing from game: {e}", exc_info=True)
            return False

    def _show_import_notification(self):
        """Show notification that brain was imported from running game."""
        self._show_sync_button()
        
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Live Brain Import")
        msg.setText("🧠 Active brain imported from running game")
        msg.setInformativeText("Changes made here will NOT affect the running game.")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.show()
        QTimer.singleShot(5000, msg.close)
        
        self.setWindowTitle("Brain Designer - Dosidicus-2 [Imported from Game]")
        self.status_bar.showMessage("✨ Active brain imported from running game", 10000)

    def _show_sync_button(self):
        """Show the sync button when game connection is established."""
        if not _HAS_BRAIN_BRIDGE:
            return
        
        while self._sync_btn_layout.count():
            item = self._sync_btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        self._sync_btn_layout.addWidget(divider)
        
        sync_btn = QPushButton("🔄 Sync from Game")
        sync_btn.setStyleSheet("""
            QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 6px 12px; border-radius: 4px; }
        """)
        sync_btn.clicked.connect(self.sync_from_running_game)
        self._sync_btn_layout.addWidget(sync_btn)
        self._sync_btn_container.show()

    def sync_from_running_game(self):
        """Manually sync brain state from running game."""
        if not is_game_running():
            QMessageBox.information(self, "Game Not Running", "The Dosidicus game is no longer running.")
            self._sync_btn_container.hide()
            self.setWindowTitle("Brain Designer - Dosidicus-2")
            return
        
        reply = QMessageBox.question(self, "Sync from Game", "Replace current design with state from game?", 
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes and self._try_import_from_game():
            self.refresh_all()
            self.status_bar.showMessage("✨ Synced with game brain.", 5000)

    def show_sparse_network_dialog(self):
        """Show the sparse network generation dialog."""
        dialog = SparseNetworkDialog(self.design, self)
        if dialog.exec_() == QDialog.Accepted:
            self.on_design_changed()

    def quick_generate(self, style_key):
        """Quickly generate a network using a preset style."""
        try:
            generator = SparseNetworkGenerator()
            presets = generator.get_preset_styles()
            if style_key not in presets:
                return
            
            preset = presets[style_key]
            bounds = (-450, -250, 650, 500)
            if hasattr(self, 'canvas') and self.canvas.viewport():
                try:
                    brect = self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect()
                    bounds = (brect.left(), brect.top(), brect.right(), brect.bottom())
                except: pass

            count, _ = generator.generate_for_design(
                self.design, clear_existing=True,
                density=preset.get('density', 1.0),
                include_feedback=preset.get('include_feedback', False),
                bounds=bounds
            )
            self.on_design_changed()
            self.status_bar.showMessage(f"Generated {count} connections.", 3000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Generation failed: {e}")

    def instant_random_generate(self):
        """Instantly generate a random network, shuffling positions."""
        try:
            generator = SparseNetworkGenerator()
            bounds = (-450, -250, 650, 500)
            if hasattr(self, 'canvas') and self.canvas.viewport():
                try:
                    brect = self.canvas.mapToScene(self.canvas.viewport().rect()).boundingRect()
                    bounds = (brect.left(), brect.top(), brect.right(), brect.bottom())
                except: pass
            
            count, _ = generator.generate_for_design(
                self.design, clear_existing=True,
                density=random.uniform(0.7, 1.4),
                include_feedback=random.random() > 0.3,
                position_variance=random.uniform(0.6, 1.0),
                bounds=bounds
            )
            
            self.on_design_changed()
            if self.canvas:
                self.canvas.center_on_neurons()
            self.status_bar.showMessage(f"🎲 Chaos! Made {count} connections.", 3000)
        except Exception as e:
            self.logger.error(f"Error in chaotic generate: {e}")

    def clear_all_connections(self):
        """Clear all connections from the design."""
        reply = QMessageBox.question(self, "Clear Connections", "Remove all connections?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.design.connections.clear()
            self.on_design_changed()

    def clear_all_outputs(self):
        """Clear all output bindings."""
        if not self.outputs_panel: return
        reply = QMessageBox.question(self, "Clear Bindings", "Remove all output bindings?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.outputs_panel.bindings.clear()
            self.outputs_panel.refresh()
            self.design.output_bindings = []
            self.on_design_changed()

    def on_design_changed(self):
        """Called when the design is modified."""
        try:
            self.canvas.rebuild()
            self.connections_table.refresh()
            self.sensors_panel.refresh()
            self.layers_panel.refresh()
            if self.outputs_panel:
                self.outputs_panel.refresh()
            self.update_status()
        except Exception as e:
            self.logger.error(f"Error updating view: {e}")

    def on_neuron_selected(self, name):
        """Called when a neuron is selected on the canvas."""
        self.props_panel.set_neuron(name)
        if name:
            self.right_panel.setCurrentWidget(self.props_panel)

    def show_add_neuron_dialog(self, x=None, y=None):
        """Show dialog to add a new neuron."""
        dlg = AddNeuronDialog(self.design, (x, y) if x is not None else None, self)
        if dlg.exec_() == QDialog.Accepted:
            self.on_design_changed()

    def on_connection_created(self, source, target):
        """Called when a new connection is created."""
        weight, ok = QInputDialog.getDouble(self, "Weight", f"{source} → {target}:", 0.5, -1.0, 1.0, 2)
        if ok:
            conn = self.design.get_connection(source, target)
            if conn: conn.weight = weight
            self.on_design_changed()
        else:
            self.design.remove_connection(source, target)
            self.on_design_changed()

    def on_connection_selected(self, source, target):
        """Called when a connection is selected."""
        conn = self.design.get_connection(source, target)
        if conn:
            self.status_bar.showMessage(f"Selected: {source} → {target} ({conn.weight:+.3f})")

    def on_weight_changed(self, source, target, new_weight):
        """Called when a connection weight is changed."""
        self.connections_table.refresh()

    def on_connection_deleted(self, source, target):
        """Called when a connection is deleted."""
        self.on_design_changed()

    def new_design(self):
        """Create a new design."""
        if QMessageBox.question(self, "New", "Start new design?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.design = BrainDesign()
            self.design.add_missing_required_neurons()
            self.network_layers.clear()
            self.layer_counter = 0
            self.refresh_all()

    def run_auto_fix(self):
        """Run auto-fix connectivity."""
        count, actions = self.design.auto_fix_connectivity()
        if count > 0:
            # Full refresh to ensure connections are displayed
            self.refresh_all()
            QMessageBox.information(self, "Auto-Fix", f"Created {count} connections.")
        else:
            QMessageBox.information(self, "Auto-Fix", "No issues found.")

    def save_design(self):
        """Save design to file."""
        if self.outputs_panel:
            self.design.output_bindings = self.outputs_panel.export_bindings()
        path, _ = QFileDialog.getSaveFileName(self, "Save", "brain.json", "JSON (*.json)")
        if path:
            success, msg = self.design.save(path)
            if success: QMessageBox.information(self, "Saved", msg)
            else: QMessageBox.warning(self, "Error", msg)

    def export_design(self):
        """Export in Dosidicus format."""
        if self.outputs_panel:
            self.design.output_bindings = self.outputs_panel.export_bindings()
        path, _ = QFileDialog.getSaveFileName(self, "Export", "dosidicus_brain.json", "JSON (*.json)")
        if path:
            success, msg = self.design.export_dosidicus(path)
            if success: QMessageBox.information(self, "Exported", msg)
            else: QMessageBox.warning(self, "Error", msg)

    def open_design(self):
        """Open a design file."""
        path, _ = QFileDialog.getOpenFileName(self, "Open", "", "JSON (*.json)")
        if path:
            self.design = BrainDesign.load(path)
            if self.outputs_panel:
                self.outputs_panel.load_bindings(self.design.output_bindings)
            self.refresh_all()

    def show_template_menu(self):
        """Show load template dialog."""
        templates = TemplateManager.get_templates()
        items = [f"{info['name']}" for info in templates.values()]
        item, ok = QInputDialog.getItem(self, "Template", "Select Template:", items, 0, False)
        if ok and item:
            key = list(templates.keys())[items.index(item)]
            if QMessageBox.question(self, "Load", "Replace design?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                self.design = TemplateManager.create_template(key)
                self.refresh_all()

    def load_template(self):
        """Load template from menu."""
        key = self.sender().data()
        if QMessageBox.question(self, "Load", "Replace design?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.design = TemplateManager.create_template(key)
            self.refresh_all()

    def check_status(self):
        """Validate design."""
        stats = self.design.get_stats()
        _, issues, _ = self.design.validate(auto_fix=False)
        msg = f"Neurons: {stats['total_neurons']}\nConnections: {stats['connections']}\n"
        if issues: msg += "\nIssues:\n" + "\n".join(issues)
        else: msg += "\nStatus: OK"
        QMessageBox.information(self, "Status", msg)


def main():
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = BrainDesignerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
