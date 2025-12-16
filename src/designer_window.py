# designer_window.py
"""
Brain Designer Window - Main application window for designing custom neural networks.

This module provides a visual editor for creating and editing squid brain configurations
including neurons, connections, layers, sensors, and output bindings.
"""

import sys
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QTabWidget, QStatusBar,
    QAction, QToolBar, QLabel, QComboBox, QPushButton, QMessageBox, QFileDialog,
    QDialog, QInputDialog, QFrame, QSizePolicy, QToolButton, QMenu, QSplitter
)
from PyQt5.QtGui import (
    QKeySequence, QIcon, QFont, QFontMetrics, QPainter, QColor, QPalette,
    QTextDocument, QAbstractTextDocumentLayout
)
# [FIX] Added QRectF to imports
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QRectF, QSizeF

from designer_logging import get_logger, log_exceptions, safe_call, OperationLogger
from designer_core import BrainDesign
from designer_canvas import BrainCanvas

# Import brain state bridge for game communication
try:
    from brain_state_bridge import (
        is_game_running,
        import_brain_state_for_designer,
        convert_to_brain_design
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
        self.text_height = self.doc.size().height()  # FIX: Call method with ()
        
        # Separator
        self.sep_doc = QTextDocument()
        self.sep_doc.setDefaultFont(self.font())
        self.sep_doc.setHtml("<span style='color:gray'>   •   </span>")
        self.sep_doc.setTextWidth(-1)
        self.sep_width = self.sep_doc.idealWidth()
        
        # Timer - don't start it yet
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scroll_text)
        self.timer.setInterval(30)  # ~33fps
        
        # Style
        self.setStyleSheet("background-color: transparent;")
        self.setFixedHeight(30)
    
    def showEvent(self, event):
        """Start timer when widget becomes visible."""
        super().showEvent(event)
        # Start timer on first show (prevents premature updates)
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
        """Paint the scrolling text with proper painter lifecycle."""
        painter = QPainter(self)
        
        # Ensure painter is valid before proceeding
        if not painter.isActive():
            return
        
        # Removed the try...finally block - Qt handles painter lifecycle automatically
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Center vertically
        y_pos = (self.height() - self.text_height) / 2
        
        # Draw copies of the text until we fill the width
        current_x = self.offset
        while current_x < self.width():
            # Draw Main Text
            painter.save()
            painter.translate(current_x, y_pos)
            self.doc.drawContents(painter, QRectF(0, 0, self.text_width, self.text_height))
            painter.restore()
            
            current_x += self.text_width
            
            # Draw Separator
            painter.save()
            painter.translate(current_x, y_pos)
            self.sep_doc.drawContents(painter, QRectF(0, 0, self.sep_width, self.text_height))
            painter.restore()
            
            current_x += self.sep_width
        
        # REMOVED: No need for finally block or manual painter.end()


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

            # Check if game is running and import its brain state
            # Otherwise generate a random network
            with OperationLogger("Initializing brain network", self.logger):
                self._imported_from_game = False
                if not self._try_import_from_game():
                    # No game running, generate random network
                    self.generate_initial_network()

            # Force UI refresh
            self.refresh_all()
            
            # Show import notification if applicable
            if self._imported_from_game:
                self._show_import_notification()

            self.update_status()
            self.logger.info("BrainDesignerWindow initialized successfully")

        except Exception as e:
            self.logger.critical(f"Failed to initialize window: {e}", exc_info=True)
            raise

    # ==========================================================================
    # INITIALIZATION AND SETUP
    # ==========================================================================

    def setup_ui(self):
        """Setup the main UI layout."""
        # Main splitter layout
        self.splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(self.splitter)

        # === LEFT/CENTER: CANVAS AREA ===
        canvas_wrapper = QWidget()
        canvas_wrapper.setMinimumWidth(500)
        
        canvas_container = QVBoxLayout(canvas_wrapper)
        canvas_container.setContentsMargins(0, 0, 0, 0)
        canvas_container.setSpacing(5)

        # Canvas toolbar
        canvas_toolbar = self.create_canvas_toolbar()
        canvas_container.addWidget(canvas_toolbar)

        # Main canvas
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

        # === RIGHT PANEL (Tabbed Panels) ===
        self.right_panel = QTabWidget()
        self.right_panel.setTabPosition(QTabWidget.West)  # Vertical tabs on the left edge
        self.right_panel.setMinimumWidth(350)

        # 1. Layers Panel
        self.layers_panel = LayersPanel(self.design)
        self.layers_panel.layersChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.layers_panel, "Layers")

        # 2. Sensors Panel (Input neurons)
        self.sensors_panel = SensorsPanel(self.design)
        self.sensors_panel.sensorsChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.sensors_panel, "Sensors")

        # 3. Properties Panel
        self.props_panel = NeuronPropertiesPanel(self.design)
        self.props_panel.neuronChanged.connect(self.on_design_changed)
        self.right_panel.addTab(self.props_panel, "Properties")

        # 4. Connections Table
        self.connections_table = ConnectionsTable(self.design)
        self.right_panel.addTab(self.connections_table, "Connections")

        # 5. Outputs Panel (Actuator neurons) - NEW!
        if _HAS_OUTPUTS_PANEL:
            self.outputs_panel = NeuronOutputsPanel(self.design)
            self.outputs_panel.outputsChanged.connect(self.on_design_changed)
            self.right_panel.addTab(self.outputs_panel, "Outputs")
        else:
            self.outputs_panel = None

        self.splitter.addWidget(self.right_panel)
        
        # Set Sensors as the default tab (index 1)
        self.right_panel.setCurrentIndex(1)

        # Set initial splitter sizes (approx 70% canvas, 30% sidebar)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        
        self.splitter.setSizes([850, 400])

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
        
        # Quick dice button - instant random generation
        dice_btn = QPushButton("🎲")
        dice_btn.setToolTip("Instantly generate a random network (no dialog)")
        dice_btn.setFixedWidth(40)
        dice_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 18px;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        dice_btn.clicked.connect(self.instant_random_generate)
        layout.addWidget(dice_btn)

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

        # Placeholder for sync button - will be added later if game is detected
        self._sync_btn_container = QFrame()
        self._sync_btn_layout = QHBoxLayout(self._sync_btn_container)
        self._sync_btn_layout.setContentsMargins(0, 0, 0, 0)
        self._sync_btn_container.hide()  # Hidden by default
        layout.addWidget(self._sync_btn_container)

        layout.addStretch()

        # Clear connections button
        clear_btn = QPushButton("🗑 Clear Connections")
        clear_btn.setToolTip("Remove all connections (keeps neurons)")
        clear_btn.setStyleSheet("color: #d32f2f;")
        clear_btn.clicked.connect(self.clear_all_connections)
        layout.addWidget(clear_btn)

        return toolbar

    def create_help_bar(self) -> QFrame:
        """Create the help bar below the canvas with scrolling ticker."""
        help_bar = QFrame()
        help_bar.setFrameStyle(QFrame.StyledPanel)
        help_bar.setMaximumHeight(30)
        layout = QHBoxLayout(help_bar)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create scrolling ticker with comprehensive shortcuts
        self.help_ticker = ScrollingTicker(
            "<span style='color:#333'>💡 <b>Left-Drag</b> from neuron to create connection</span>"
            "<span style='color:#333'><b>Ctrl+Drag</b> neuron to move it</span>"
            "<span style='color:#333'><b>Right-Drag</b> to pan canvas</span>"
            "<span style='color:#333'><b>Scroll Wheel</b> to zoom (or adjust weight on connection)</span>"
            "<span style='color:#333'><b>Double-Click</b> connection to edit weight</span>"
            "<span style='color:#333'><b>Click</b> neuron/connection to select</span>"
            "<span style='color:#333'><b>Del</b> to delete selected</span>"
            "<span style='color:#333'><b>Space</b> to reverse connection direction</span>"
            "<span style='color:#333'><b>+/-</b> keys to adjust weight (Shift for larger steps)</span>"
            "<span style='color:#333'><b>Page Up/Down</b> to adjust weight (large steps)</span>"
            "<span style='color:#333'><b>Shift+N</b> to add neuron</span>"
            "<span style='color:#333'><b>Ctrl+S</b> to save</span>"
            "<span style='color:#333'><b>Ctrl+O</b> to open</span>"
            "<span style='color:#333'><b>Ctrl+E</b> to export</span>"
            "<span style='color:#333'><b>Ctrl+N</b> for new design</span>"
            "<span style='color:#333'><b>Ctrl+G</b> to generate network</span>"
            "<span style='color:#333'>🎲 <b>Dice button</b> for instant random generation</span>"
            "<span style='color:#333'><b>Outputs tab</b> to bind neurons to squid behaviors</span>"
        )
        layout.addWidget(self.help_ticker)

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
        
        # Clear outputs action
        if _HAS_OUTPUTS_PANEL:
            clear_outputs_action = QAction("Clear All Output Bindings", self)
            clear_outputs_action.triggered.connect(self.clear_all_outputs)
            edit_menu.addAction(clear_outputs_action)

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

        # Template dropdown
        toolbar.addAction("📋 Templates", self.show_template_menu)

    # ==========================================================================
    # REFRESH AND STATUS
    # ==========================================================================

    def refresh_all(self):
        """Refresh all panels with current design."""
        self.canvas.design = self.design
        self.props_panel.design = self.design
        self.layers_panel.design = self.design
        self.sensors_panel.design = self.design
        self.connections_table.design = self.design
        
        # Refresh outputs panel and load bindings from design
        if self.outputs_panel:
            self.outputs_panel.design = self.design
            self.outputs_panel.load_bindings(self.design.output_bindings)
        
        self.on_design_changed()

    def update_status(self):
        """Update the status bar."""
        stats = self.design.get_stats()
        
        # Build status message
        status_parts = [
            f"Neurons: {stats['total_neurons']}",
            f"Connections: {stats['connections']}",
            f"Required: {'✓' if stats['has_all_required'] else '✗'}"
        ]
        
        # Add output bindings count if available
        if self.outputs_panel:
            binding_count = len(self.outputs_panel.bindings)
            if binding_count > 0:
                status_parts.append(f"Outputs: {binding_count}")
        
        self.status_bar.showMessage(" | ".join(status_parts))

    # ==========================================================================
    # NETWORK GENERATION AND CLEARING
    # ==========================================================================

    def generate_initial_network(self):
        """Generate a random network on startup without user interaction."""
        import random
        try:
            generator = SparseNetworkGenerator()
            
            # 50% chance of minimalist configuration (sparse, no feedback)
            # This creates a variety of startup experiences for the user
            if random.random() < 0.5:
                density = 0.5
                include_feedback = False
                mode = "minimalist"
            else:
                density = 1.0
                include_feedback = True
                mode = "balanced"

            count, _ = generator.generate_for_design(
                self.design,
                clear_existing=True,
                density=density,
                include_feedback=include_feedback,
                silent=True
            )
            self.logger.debug(f"Generated initial network ({mode}) with {count} connections")
        except Exception as e:
            self.logger.warning(f"Could not generate initial network: {e}")

    def _try_import_from_game(self) -> bool:
        """
        Attempt to import brain state from a running game instance.
        
        Returns:
            True if import was successful, False otherwise
        """
        if not _HAS_BRAIN_BRIDGE:
            return False
        
        try:
            # Check if game is running
            if not is_game_running():
                self.logger.debug("No running game detected, will generate random network")
                return False
            
            self.logger.info("Detected running game, attempting to import brain state...")
            
            # Import the brain state
            live_state = import_brain_state_for_designer()
            if live_state is None:
                self.logger.warning("Could not import brain state from game")
                return False
            
            # Convert to BrainDesign
            imported_design = convert_to_brain_design(live_state)
            if imported_design is None:
                self.logger.warning("Could not convert imported state to BrainDesign")
                return False
            
            # Replace current design with imported one
            self.design = imported_design
            
            # Update canvas reference
            if hasattr(self, 'canvas'):
                self.canvas.design = self.design
            
            self._imported_from_game = True
            self.logger.info(
                f"Successfully imported brain from game: "
                f"{len(self.design.neurons)} neurons, "
                f"{len(self.design.connections)} connections"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Error importing from game: {e}", exc_info=True)
            return False

    def _show_import_notification(self):
        """Show notification that brain was imported from running game."""
        from PyQt5.QtWidgets import QMessageBox
        from PyQt5.QtCore import QTimer
        
        # Show the sync button now that we know game is running
        self._show_sync_button()
        
        # Create a non-modal notification
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Live Brain Import")
        msg.setText("🧠 Active brain imported from running game")
        msg.setInformativeText(
            f"The designer is now showing the exact neural network "
            f"from your running Dosidicus game.\n\n"
            f"• {len(self.design.neurons)} neurons\n"
            f"• {len(self.design.connections)} connections\n\n"
            f"Changes made here will NOT affect the running game."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        
        # Show and auto-close after 5 seconds
        msg.show()
        QTimer.singleShot(5000, msg.close)
        
        # Update window title to indicate imported state
        self.setWindowTitle("Brain Designer - Dosidicus-2 [Imported from Game]")
        
        # Update status bar
        self.status_bar.showMessage(
            "✨ Active brain imported from running game", 10000
        )

    def _show_sync_button(self):
        """Show the sync button when game connection is established."""
        if not _HAS_BRAIN_BRIDGE:
            return
        
        # Clear any existing content
        while self._sync_btn_layout.count():
            item = self._sync_btn_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        self._sync_btn_layout.addWidget(divider)
        
        # Add sync button
        sync_btn = QPushButton("🔄 Sync from Game")
        sync_btn.setToolTip("Refresh brain state from running Dosidicus game")
        sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        sync_btn.clicked.connect(self.sync_from_running_game)
        self._sync_btn_layout.addWidget(sync_btn)
        
        # Show the container
        self._sync_btn_container.show()

    def sync_from_running_game(self):
        """
        Manually sync brain state from running game.
        Called when user clicks the Sync from Game button.
        """
        # Check if game is still running
        if not is_game_running():
            QMessageBox.information(
                self, "Game Not Running",
                "The Dosidicus game is no longer running.\n\n"
                "Start the game again to sync."
            )
            # Hide the sync button since game is gone
            self._sync_btn_container.hide()
            self.setWindowTitle("Brain Designer - Dosidicus-2")
            return
        
        # Confirm before replacing current design
        reply = QMessageBox.question(
            self, "Sync from Game",
            "Replace current design with the latest brain state from the game?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Try to import
        if self._try_import_from_game():
            self.refresh_all()
            self.status_bar.showMessage(
                f"✨ Synced: {len(self.design.neurons)} neurons, "
                f"{len(self.design.connections)} connections", 5000
            )
        else:
            QMessageBox.warning(
                self, "Sync Failed",
                "Could not import brain state from game."
            )

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
            count, connections = generator.generate_for_design(
                self.design,
                clear_existing=True,
                density=preset.get('density', 1.0),
                include_feedback=preset.get('include_feedback', False),
                position_variance=preset.get('position_variance', 0.2),
                sensor_probability=preset.get('sensor_probability', 0.0)
            )
            
            self.on_design_changed()
            self.status_bar.showMessage(
                f"Generated {count} connections using '{preset['name']}' preset", 3000
            )
        except Exception as e:
            self.logger.error(f"Error in quick_generate: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Generation failed: {e}")

    def instant_random_generate(self):
        """Instantly generate a random network without any dialog."""
        import random
        
        try:
            generator = SparseNetworkGenerator()
            presets = generator.get_preset_styles()
            
            # Pick a random preset
            style_key = random.choice(list(presets.keys()))
            preset = presets[style_key]
            
            # Randomize some parameters
            density = random.uniform(0.5, 1.5)
            excitatory_ratio = random.uniform(0.5, 0.85)
            
            count, _ = generator.generate_for_design(
                self.design,
                clear_existing=True,
                density=density,
                include_feedback=random.random() > 0.3,
            )
            
            self.on_design_changed()
            self.status_bar.showMessage(
                f"🎲 Generated {count} random connections (style: {preset['name']})", 3000
            )
        except Exception as e:
            self.logger.error(f"Error in instant_random_generate: {e}", exc_info=True)

    def clear_all_connections(self):
        """Clear all connections from the design."""
        reply = QMessageBox.question(
            self, "Clear Connections",
            f"Remove all {len(self.design.connections)} connections?\n\n"
            "Neurons will be kept.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            count = len(self.design.connections)
            self.design.connections.clear()
            self.on_design_changed()
            self.status_bar.showMessage(f"Cleared {count} connections", 3000)

    def clear_all_outputs(self):
        """Clear all output bindings from the design."""
        if not self.outputs_panel:
            return
        
        if not self.outputs_panel.bindings:
            QMessageBox.information(self, "Clear Outputs", "No output bindings to clear.")
            return
        
        reply = QMessageBox.question(
            self, "Clear Output Bindings",
            f"Remove all {len(self.outputs_panel.bindings)} output bindings?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            count = len(self.outputs_panel.bindings)
            self.outputs_panel.bindings.clear()
            self.outputs_panel.refresh()
            self.design.output_bindings = []
            self.on_design_changed()
            self.status_bar.showMessage(f"Cleared {count} output bindings", 3000)

    # ==========================================================================
    # EVENT HANDLERS / CALLBACKS
    # ==========================================================================

    def on_design_changed(self):
        """Called when the design is modified."""
        try:
            self.canvas.rebuild()
            self.connections_table.refresh()
            self.sensors_panel.refresh()
            self.layers_panel.refresh()
            
            # Refresh outputs panel
            if self.outputs_panel:
                self.outputs_panel.refresh()
            
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

    # ==========================================================================
    # FILE AND UTILITY OPERATIONS
    # ==========================================================================

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
            # [FIX] Force immediate repaint so changes are visible behind the message box
            if self.canvas:
                self.canvas.viewport().repaint()
            
            QMessageBox.information(
                self, "Auto-Fix",
                f"Created {count} connections:\n\n" + "\n".join(actions[:10])
            )
        else:
            QMessageBox.information(self, "Auto-Fix", "No issues found.")

    def save_design(self):
        """Save the design to file."""
        try:
            # Sync output bindings from panel to design BEFORE saving
            if self.outputs_panel:
                self.design.output_bindings = self.outputs_panel.export_bindings()
            
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Design", "brain.json", "JSON (*.json)"
            )
            if path:
                self.logger.info(f"Saving design to: {path}")
                success, msg = self.design.save(path)
                if success:
                    self.logger.info(f"Design saved successfully: {msg}")
                    
                    # Add output binding info to message
                    if self.outputs_panel and self.outputs_panel.bindings:
                        msg += f"\n({len(self.outputs_panel.bindings)} output bindings included)"
                    
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
            # Sync output bindings from panel to design BEFORE exporting
            if self.outputs_panel:
                self.design.output_bindings = self.outputs_panel.export_bindings()
            
            path, _ = QFileDialog.getSaveFileName(
                self, "Export", "dosidicus_brain.json", "JSON (*.json)"
            )
            if path:
                self.logger.info(f"Exporting design to: {path}")
                success, msg = self.design.export_dosidicus(path)
                if success:
                    self.logger.info(f"Design exported successfully")
                    
                    # Add output binding info to message
                    if self.outputs_panel and self.outputs_panel.bindings:
                        msg += f"\n({len(self.outputs_panel.bindings)} output bindings included)"
                    
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
                self.logger.info(
                    f"Design loaded: {len(self.design.neurons)} neurons, "
                    f"{len(self.design.connections)} connections"
                )
                
                # Load output bindings into the panel
                if self.outputs_panel:
                    self.outputs_panel.load_bindings(self.design.output_bindings)
                    if self.design.output_bindings:
                        self.logger.info(f"Loaded {len(self.design.output_bindings)} output bindings")
                
                self.refresh_all()
        except Exception as e:
            self.logger.error(f"Error opening design: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Could not load design:\n\n{e}")

    def show_template_menu(self):
        """Show templates as a popup."""
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
        
        # Add output binding info
        if self.outputs_panel:
            binding_count = len(self.outputs_panel.bindings)
            enabled_count = sum(1 for b in self.outputs_panel.bindings if b.enabled)
            msg += f"Output Bindings: {binding_count} ({enabled_count} enabled)\n"
            
            # Validate bindings
            binding_warnings = self.outputs_panel.validate_bindings()
            if binding_warnings:
                issues.extend(binding_warnings)

        if issues:
            msg += "\n⚠️ ISSUES:\n" + "\n".join(f"  • {i}" for i in issues)
        else:
            msg += "\n✅ Status: OK"

        QMessageBox.information(self, "Design Status", msg)


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for the Brain Designer application."""
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("Brain Designer (Beta)")
    app.setOrganizationName("Dosidicus")
    
    window = BrainDesignerWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()