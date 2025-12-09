import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QStatusBar,
    QAction, QToolBar, QLabel, QComboBox, QPushButton, QMessageBox, QFileDialog,
    QDialog, QInputDialog, QFrame, QSizePolicy, QToolButton, QMenu, QSplitter
)
from PyQt5.QtGui import QKeySequence, QIcon, QFont
from PyQt5.QtCore import Qt

from designer_logging import get_logger, log_exceptions, safe_call, OperationLogger
from designer_core import BrainDesign
from designer_canvas import BrainCanvas
from designer_panels import (
    LayersPanel, SensorsPanel, NeuronPropertiesPanel, ConnectionsTable, AddNeuronDialog
)
from designer_templates import TemplateManager
from designer_dialogs import SparseNetworkDialog, ActivationEditorDialog
from designer_network_generator import SparseNetworkGenerator


class BrainDesignerWindow(QMainWindow):
    """Main window for the Brain Designer application."""

    def __init__(self):
        super().__init__()
        self.logger = get_logger("brain_designer.window")
        self.logger.info("Initializing BrainDesignerWindow")

        try:
            self.design = BrainDesign()
            self.design.add_missing_required_neurons()

            self.setWindowTitle("Brain Designer - Dosidicus-2")
            self.setMinimumSize(1280, 900)

            with OperationLogger("Setting up UI", self.logger):
                self.setup_ui()

            with OperationLogger("Setting up menus", self.logger):
                self.setup_menus()

            with OperationLogger("Setting up toolbar", self.logger):
                self.setup_toolbar()

            # Generate a random network on startup so the user sees immediate activity
            with OperationLogger("Generating initial network", self.logger):
                self.generate_initial_network()

            self.update_status()
            self.logger.info("BrainDesignerWindow initialized successfully")

        except Exception as e:
            self.logger.critical(f"Failed to initialize window: {e}", exc_info=True)
            raise

    # --- INITIALIZATION AND SETUP ---

    def setup_ui(self):
        """Setup the main UI layout."""
        # Main splitter layout
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # === LEFT/CENTER: CANVAS AREA ===
        canvas_wrapper = QWidget()
        # [FIX] Set a minimum width for the canvas area to prevent toolbar crushing
        canvas_wrapper.setMinimumWidth(500)
        
        canvas_container = QVBoxLayout(canvas_wrapper)
        canvas_container.setContentsMargins(0, 0, 0, 0)
        canvas_container.setSpacing(5)

        # Canvas toolbar
        canvas_toolbar = self.create_canvas_toolbar()
        canvas_container.addWidget(canvas_toolbar)

        self.canvas = BrainCanvas(self.design)
        self.canvas.neuronSelected.connect(self.on_neuron_selected)
        self.canvas.connectionCreated.connect(self.on_connection_created)
        self.canvas.connectionSelected.connect(self.on_connection_selected)
        self.canvas.weightChanged.connect(self.on_weight_changed)
        self.canvas.connectionDeleted.connect(self.on_connection_deleted)

        canvas_container.addWidget(self.canvas)

        # Canvas help bar
        help_bar = self.create_help_bar()
        canvas_container.addWidget(help_bar)

        self.splitter.addWidget(canvas_wrapper)

        # === RIGHT PANEL (Merged Tabs) ===
        self.right_panel = QTabWidget()
        self.right_panel.setTabPosition(QTabWidget.West)  # Vertical tabs on the left edge
        
        # [FIX] Critical: Set minimum width to accommodate vertical tabs + content
        # This prevents the "wacky" snapping/jittering when resizing
        self.right_panel.setMinimumWidth(350) 

        # 1. Layers
        self.layers_panel = LayersPanel(self.design)
        self.layers_panel.layersChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.layers_panel, "Layers")

        # 2. Sensors
        self.sensors_panel = SensorsPanel(self.design)
        self.sensors_panel.sensorsChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.sensors_panel, "Sensors")

        # 3. Properties
        self.props_panel = NeuronPropertiesPanel(self.design)
        self.props_panel.neuronChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.props_panel, "Properties")

        # 4. Connections
        self.connections_table = ConnectionsTable(self.design)
        self.right_panel.addTab(self.connections_table, "Connections")

        self.splitter.addWidget(self.right_panel)

        # Set initial splitter sizes (approx 70% canvas, 30% sidebar)
        self.splitter.setCollapsible(0, False)
        # [FIX] Disable collapsing for right panel too, to prevent it from snapping to 0
        self.splitter.setCollapsible(1, False) 
        
        self.splitter.setStretchFactor(0, 1) # Simply let them share space
        self.splitter.setStretchFactor(1, 0)
        
        self.splitter.setSizes([850, 400])  # Initial pixel widths

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def create_canvas_toolbar(self) -> QFrame:
        """Create the toolbar above the canvas."""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.StyledPanel)
        toolbar.setMaximumHeight(45)
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)

        # Generate button (prominent)
        generate_btn = QPushButton("🎲 Generate Sparse Network")
        generate_btn.setToolTip("Generate random connections between core neurons")
        generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        generate_btn.clicked.connect(self.show_sparse_network_dialog)
        layout.addWidget(generate_btn)

        # Quick generate menu
        quick_gen_btn = QToolButton()
        quick_gen_btn.setText("▼")
        quick_gen_btn.setPopupMode(QToolButton.InstantPopup)
        quick_menu = QMenu(quick_gen_btn)

        generator = SparseNetworkGenerator()
        for key, info in generator.get_preset_styles().items():
            action = quick_menu.addAction(f"{info['name']} - {info['description']}")
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.quick_generate(k))

        quick_gen_btn.setMenu(quick_menu)
        layout.addWidget(quick_gen_btn)

        layout.addSpacing(20)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        layout.addWidget(divider)

        layout.addSpacing(10)

        # + Neuron button (colorful, prominent)
        add_neuron_btn = QPushButton("➕ Neuron")
        add_neuron_btn.setToolTip("Add a new neuron (Shift+N)")
        add_neuron_btn.setShortcut("Shift+N")
        add_neuron_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
        """)
        add_neuron_btn.clicked.connect(self.show_add_neuron_dialog)
        layout.addWidget(add_neuron_btn)

        layout.addSpacing(10)

        # Auto-fix button
        fix_btn = QPushButton("🔧 Auto-Fix")
        fix_btn.setToolTip("Automatically fix orphan neurons and connectivity issues")
        fix_btn.clicked.connect(self.run_auto_fix)
        layout.addWidget(fix_btn)

        # Validate button
        validate_btn = QPushButton("✓ Validate")
        validate_btn.setToolTip("Check design for issues")
        validate_btn.clicked.connect(self.check_status)
        layout.addWidget(validate_btn)

        layout.addStretch()

        # Clear connections button
        clear_btn = QPushButton("🗑 Clear Connections")
        clear_btn.setToolTip("Remove all connections (keeps neurons)")
        clear_btn.setStyleSheet("color: #d32f2f;")
        clear_btn.clicked.connect(self.clear_all_connections)
        layout.addWidget(clear_btn)

        return toolbar

    def create_help_bar(self) -> QFrame:
        """Create the help bar below the canvas."""
        help_bar = QFrame()
        help_bar.setFrameStyle(QFrame.StyledPanel)
        help_bar.setMaximumHeight(30)
        layout = QHBoxLayout(help_bar)
        layout.setContentsMargins(10, 2, 10, 2)

        help_text = QLabel(
            "💡 <b>Drag</b> from neuron to wire  •  "
            "<b>Scroll</b> on connection to adjust weight  •  "
            "<b>Double-click</b> connection to edit  •  "
            "<b>Del</b> to delete  •  "
            "<b>Space</b> to reverse direction  •  "
            "<b>Shift+N</b> to add neuron"
        )
        help_text.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(help_text)

        layout.addStretch()

        return help_bar

    def setup_menus(self):
        """Setup the menu bar."""
        menu = self.menuBar()

        # File menu
        file_menu = menu.addMenu("File")

        new_action = QAction("New Design", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_design)
        file_menu.addAction(new_action)

        file_menu.addSeparator()

        save_action = QAction("Save...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_design)
        file_menu.addAction(save_action)

        export_action = QAction("Export for Dosidicus...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.export_design)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        open_action = QAction("Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_design)
        file_menu.addAction(open_action)

        # Edit menu
        edit_menu = menu.addMenu("Edit")

        generate_action = QAction("Generate Sparse Network...", self)
        generate_action.setShortcut("Ctrl+G")
        generate_action.triggered.connect(self.show_sparse_network_dialog)
        edit_menu.addAction(generate_action)

        edit_menu.addSeparator()

        auto_fix = QAction("Auto-Fix Connectivity", self)
        auto_fix.triggered.connect(self.run_auto_fix)
        edit_menu.addAction(auto_fix)

        validate_action = QAction("Validate Design", self)
        validate_action.triggered.connect(self.check_status)
        edit_menu.addAction(validate_action)

        edit_menu.addSeparator()

        clear_conn_action = QAction("Clear All Connections", self)
        clear_conn_action.triggered.connect(self.clear_all_connections)
        edit_menu.addAction(clear_conn_action)

        # Templates menu
        tpl_menu = menu.addMenu("Templates")
        for key, info in TemplateManager.get_templates().items():
            a = QAction(info['name'], self)
            a.setData(key)
            a.triggered.connect(self.load_template)
            tpl_menu.addAction(a)

        # Network generation presets
        gen_menu = menu.addMenu("Generate")

        gen_dialog_action = QAction("🎲 Generate Sparse Network...", self)
        gen_dialog_action.setShortcut("Ctrl+G")
        gen_dialog_action.triggered.connect(self.show_sparse_network_dialog)
        gen_menu.addAction(gen_dialog_action)

        gen_menu.addSeparator()

        generator = SparseNetworkGenerator()
        for key, info in generator.get_preset_styles().items():
            action = QAction(f"{info['name']}", self)
            action.setToolTip(info['description'])
            action.setData(key)
            action.triggered.connect(lambda checked, k=key: self.quick_generate(k))
            gen_menu.addAction(action)

    def setup_toolbar(self):
        """Setup the main toolbar."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # File actions
        toolbar.addAction("📂 Open", self.open_design)
        toolbar.addAction("💾 Save", self.save_design)

        toolbar.addSeparator()

        # Template dropdown would go here
        toolbar.addAction("📋 Templates", self.show_template_menu)

    def refresh_all(self):
        """Refresh all panels with current design."""
        self.canvas.design = self.design
        self.props_panel.design = self.design
        self.layers_panel.design = self.design
        self.sensors_panel.design = self.design
        self.connections_table.design = self.design
        self.on_design_changed()

    def update_status(self):
        """Update the status bar."""
        stats = self.design.get_stats()
        self.status_bar.showMessage(
            f"Neurons: {stats['total_neurons']} | "
            f"Connections: {stats['connections']} | "
            f"Required: {'✓' if stats['has_all_required'] else '✗'}"
        )

    # --- NETWORK GENERATION AND CLEARING ---

    def generate_initial_network(self):
        """Generate a random network on startup without user interaction."""
        try:
            generator = SparseNetworkGenerator()
            # Use 'balanced' style logic by default, but silent
            count, _ = generator.generate_for_design(
                self.design,
                clear_existing=True,
                density=1.0,
                include_feedback=True,
                silent=True
            )
            self.logger.info(f"Startup: Generated random network with {count} connections")
            # Force UI update
            self.on_design_changed()
        except Exception as e:
            self.logger.warning(f"Failed to generate initial network: {e}")

    def show_sparse_network_dialog(self):
        """Show the sparse network generation dialog."""
        try:
            self.logger.debug("Opening sparse network dialog")
            dialog = SparseNetworkDialog(self.design, self)
            if dialog.exec_() == QDialog.Accepted:
                self.on_design_changed()
                summary = dialog.get_result_summary()
                self.logger.info(f"Sparse network generated: {summary}")
                self.status_bar.showMessage(f"✨ {summary}", 5000)
                QMessageBox.information(
                    self, "Generation Complete",
                    f"{summary}\n\nThe network has been applied to your design."
                )
        except Exception as e:
            self.logger.error(f"Error in sparse network dialog: {e}", exc_info=True)
            QMessageBox.warning(
                self, "Error",
                f"Failed to generate network:\n\n{e}"
            )

    def quick_generate(self, preset_key: str):
        """Quickly generate with a preset without showing dialog."""
        try:
            reply = QMessageBox.question(
                self, "Quick Generate",
                f"Generate a sparse network with '{preset_key}' preset?\n\n"
                "This will clear existing connections.",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            self.logger.info(f"Quick generating with preset: {preset_key}")

            generator = SparseNetworkGenerator()
            presets = generator.get_preset_styles()

            if preset_key not in presets:
                self.logger.warning(f"Unknown preset: {preset_key}")
                return

            preset = presets[preset_key]
            count, _ = generator.generate_for_design(
                self.design,
                clear_existing=True,
                density=preset['density'],
                include_feedback=preset.get('include_feedback', True)
            )

            self.logger.info(f"Generated {count} connections with preset {preset_key}")
            self.on_design_changed()
            self.status_bar.showMessage(f"✨ Generated {count} connections ({preset_key})", 5000)

        except Exception as e:
            self.logger.error(f"Error in quick_generate: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to generate network:\n\n{e}")

    def clear_all_connections(self):
        """Clear all connections from the design."""
        if not self.design.connections:
            QMessageBox.information(self, "Clear", "No connections to clear.")
            return

        reply = QMessageBox.question(
            self, "Clear Connections",
            f"Remove all {len(self.design.connections)} connections?\n\n"
            "Neurons will be preserved.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            count = len(self.design.connections)
            self.design.connections.clear()
            self.on_design_changed()
            self.status_bar.showMessage(f"Cleared {count} connections", 3000)

    # --- EVENT HANDLERS / CALLBACKS ---

    def on_design_changed(self):
        """Called when the design is modified."""
        try:
            self.canvas.rebuild()
            self.connections_table.refresh()
            self.sensors_panel.refresh()
            self.layers_panel.refresh()
            self.update_status()
        except Exception as e:
            self.logger.error(f"Error updating design view: {e}", exc_info=True)

    def on_neuron_selected(self, name):
        """Called when a neuron is selected on the canvas."""
        self.props_panel.set_neuron(name)
        # Switch to properties tab if a neuron is selected
        if name:
            self.right_panel.setCurrentWidget(self.props_panel)

    def show_add_neuron_dialog(self, x=None, y=None):
        """Show dialog to add a new neuron."""
        pos = (x, y) if x is not None else None
        dlg = AddNeuronDialog(self.design, pos, self)
        if dlg.exec_() == QDialog.Accepted:
            self.on_design_changed()

    def on_connection_created(self, source, target):
        """Called when a new connection is created via drag."""
        weight, ok = QInputDialog.getDouble(
            self, "Connection Weight",
            f"Set weight for {source} → {target}:",
            0.5, -1.0, 1.0, 2
        )
        if ok:
            conn = self.design.get_connection(source, target)
            if conn:
                conn.weight = weight
            self.on_design_changed()
        else:
            # Cancel: remove the connection
            self.design.remove_connection(source, target)
            self.on_design_changed()

    def on_connection_selected(self, source, target):
        """Called when a connection is selected."""
        conn = self.design.get_connection(source, target)
        if conn:
            self.status_bar.showMessage(
                f"Selected: {source} → {target} (weight: {conn.weight:+.3f})"
            )
            # Optional: Switch to connection table?
            # self.right_panel.setCurrentWidget(self.connections_table)

    def on_weight_changed(self, source, target, new_weight):
        """Called when a connection weight is changed."""
        self.connections_table.refresh()
        self.status_bar.showMessage(
            f"Weight updated: {source} → {target} = {new_weight:+.3f}", 2000
        )

    def on_connection_deleted(self, source, target):
        """Called when a connection is deleted."""
        self.on_design_changed()
        self.status_bar.showMessage(f"Deleted connection: {source} → {target}", 2000)

    # --- FILE AND UTILITY OPERATIONS ---

    def new_design(self):
        """Create a new empty design."""
        reply = QMessageBox.question(
            self, "New Design",
            "Start a new design? Unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.design = BrainDesign()
            self.design.add_missing_required_neurons()
            self.refresh_all()

    def run_auto_fix(self):
        """Run auto-fix on the design."""
        count, actions = self.design.auto_fix_connectivity()
        if count > 0:
            self.on_design_changed()
            QMessageBox.information(
                self, "Auto-Fix",
                f"Created {count} connections:\n\n" + "\n".join(actions[:10])
            )
        else:
            QMessageBox.information(self, "Auto-Fix", "No issues found.")

    def save_design(self):
        """Save the design to file."""
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Design", "brain.json", "JSON (*.json)"
            )
            if path:
                self.logger.info(f"Saving design to: {path}")
                success, msg = self.design.save(path)
                if success:
                    self.logger.info(f"Design saved successfully: {msg}")
                    QMessageBox.information(self, "Saved", msg)
                else:
                    self.logger.warning(f"Save failed: {msg}")
                    QMessageBox.warning(self, "Error", msg)
        except Exception as e:
            self.logger.error(f"Error saving design: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to save design:\n\n{e}")

    def export_design(self):
        """Export in Dosidicus format."""
        try:
            path, _ = QFileDialog.getSaveFileName(
                self, "Export", "dosidicus_brain.json", "JSON (*.json)"
            )
            if path:
                self.logger.info(f"Exporting design to: {path}")
                success, msg = self.design.export_dosidicus(path)
                if success:
                    self.logger.info(f"Design exported successfully")
                    QMessageBox.information(self, "Exported", msg)
                else:
                    self.logger.warning(f"Export failed: {msg}")
                    QMessageBox.warning(self, "Error", msg)
        except Exception as e:
            self.logger.error(f"Error exporting design: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to export design:\n\n{e}")

    def open_design(self):
        """Open a design file."""
        try:
            path, _ = QFileDialog.getOpenFileName(
                self, "Open Design", "", "JSON (*.json)"
            )
            if path:
                self.logger.info(f"Opening design from: {path}")
                self.design = BrainDesign.load(path)
                self.logger.info(f"Design loaded: {len(self.design.neurons)} neurons, {len(self.design.connections)} connections")
                self.refresh_all()
        except Exception as e:
            self.logger.error(f"Error opening design: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Could not load design:\n\n{e}")

    def show_template_menu(self):
        """Show templates as a popup."""
        # Simple dialog listing templates
        templates = TemplateManager.get_templates()
        items = [f"{info['name']} - {info['description']}" for info in templates.values()]
        keys = list(templates.keys())

        item, ok = QInputDialog.getItem(
            self, "Load Template", "Select a template:", items, 0, False
        )
        if ok and item:
            idx = items.index(item)
            key = keys[idx]
            if QMessageBox.question(
                self, "Load Template", "Replace current design?",
                QMessageBox.Yes | QMessageBox.No
            ) == QMessageBox.Yes:
                self.design = TemplateManager.create_template(key)
                self.refresh_all()

    def load_template(self):
        """Load a template from menu action."""
        key = self.sender().data()
        if QMessageBox.question(
            self, "Load Template", "Replace current design?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            self.design = TemplateManager.create_template(key)
            self.refresh_all()

    def check_status(self):
        """Validate and show design status."""
        self.on_design_changed()
        stats = self.design.get_stats()
        _, issues, _ = self.design.validate(auto_fix=False)

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