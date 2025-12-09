"""
Canvas implementation for Brain Designer.
Handles visual representation and interaction.
"""

import math
import json
import os
from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, 
    QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QStyle, QToolTip,
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton,
    QCheckBox, QMessageBox
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics, QPainterPath, 
    QRadialGradient, QTransform, QCursor, QPainterPathStroker, QPolygonF
)

from designer_core import BrainDesign
from designer_constants import (
    NeuronType, CORE_NEURON_RING_COLOR, INPUT_SENSOR_RING_COLOR, 
    CUSTOM_NEURON_RING_COLOR, PROTECTED_RING_WIDTH, NORMAL_RING_WIDTH, 
    DEFAULT_LAYER_HEIGHT
)


class SmartConnectionItem(QGraphicsItem):
    """Visual representation of a neural connection with animated pulse."""
    
    def __init__(self, source_pos, target_pos, weight=0.5, source_name="", target_name="", parent=None):
        super().__init__(parent)
        self.source_pos = source_pos
        self.target_pos = target_pos
        self.weight = weight
        self.source_name = source_name
        self.target_name = target_name
        
        # Visual states
        self.is_selected = False
        
        # Pulse animation
        self.pulse_phase = 0.0
        self.pulse_speed = 0.02 + (hash(str(source_pos)) % 100) * 0.0001 
        
        # Hover events disabled
        self.setAcceptHoverEvents(False)
        self.setZValue(-5) 
        self.hit_thickness = 25 

    def boundingRect(self):
        extra = 30
        return QRectF(self.source_pos, self.target_pos).normalized().adjusted(-extra, -extra, extra, extra)

    def shape(self):
        path = QPainterPath()
        path.moveTo(self.source_pos)
        path.lineTo(self.target_pos)
        stroker = QPainterPathStroker()
        stroker.setWidth(self.hit_thickness) 
        return stroker.createStroke(path)
    
    def advance_pulse(self):
        self.pulse_phase += self.pulse_speed
        if self.pulse_phase > 1.0: 
            self.pulse_phase = 0.0
        self.update()

    def paint(self, painter, option, widget):
        abs_weight = abs(self.weight)
        # Thickness based on weight: 2px at 0, up to 22px at |1.0|
        base_thickness = 2.0 + (abs_weight * 20.0)
        
        # Color based on excitatory/inhibitory
        if self.weight >= 0:
            color = QColor(50, 205, 50)  # Green for excitatory
            pen_style = Qt.SolidLine
            is_inhibitory = False
        else:
            color = QColor(220, 20, 60)  # Red for inhibitory
            pen_style = Qt.DashLine 
            is_inhibitory = True

        # Selection glow (yellow)
        if self.is_selected:
            painter.setPen(QPen(QColor(255, 255, 0, 180), base_thickness + 10, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(self.source_pos, self.target_pos)
        
        painter.setPen(QPen(color, base_thickness, pen_style, Qt.RoundCap))
        painter.setRenderHint(QPainter.Antialiasing)

        line = QLineF(self.source_pos, self.target_pos)
        if line.length() == 0: 
            return
        
        angle = math.atan2(line.dy(), line.dx())
        offset_start, offset_end = 25, 32
        
        start_p = QPointF(self.source_pos.x() + offset_start * math.cos(angle),
                          self.source_pos.y() + offset_start * math.sin(angle))
        end_p = QPointF(self.target_pos.x() - offset_end * math.cos(angle),
                        self.target_pos.y() - offset_end * math.sin(angle))

        painter.drawLine(start_p, end_p)

        # Draw arrowhead or inhibitory bar
        painter.setBrush(QBrush(color))
        if is_inhibitory:
            # Flat bar for inhibitory
            bar_len = 8 + base_thickness
            dx, dy = bar_len * math.sin(angle), bar_len * math.cos(angle)
            painter.setPen(QPen(color, max(3, base_thickness / 2)))
            painter.drawLine(QPointF(end_p.x() - dx, end_p.y() + dy), 
                           QPointF(end_p.x() + dx, end_p.y() - dy))
        else:
            # Arrowhead for excitatory
            arrow_size = 12 + base_thickness
            p1 = end_p - QPointF(math.cos(angle + 0.5) * arrow_size, math.sin(angle + 0.5) * arrow_size)
            p2 = end_p - QPointF(math.cos(angle - 0.5) * arrow_size, math.sin(angle - 0.5) * arrow_size)
            painter.setPen(Qt.NoPen)
            painter.drawPolygon(QPolygonF([end_p, p1, p2]))

        # Animated pulse orb
        pulse_curr = start_p + (end_p - start_p) * self.pulse_phase
        orb_size = max(8, base_thickness * 0.8)
        grad = QRadialGradient(pulse_curr, orb_size)
        grad.setColorAt(0, QColor(255, 255, 255, 255))
        grad.setColorAt(0.5, color.lighter(150))
        grad.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(pulse_curr, orb_size, orb_size)

        # Weight label ONLY on selection
        if self.is_selected:
            mid = (start_p + end_p) / 2
            weight_str = f"{self.weight:+.2f}"
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            fm = QFontMetrics(painter.font())
            tw = fm.horizontalAdvance(weight_str)
            th = fm.height()
            rect = QRectF(mid.x() - tw/2 - 6, mid.y() - th/2 - 2, tw + 12, th + 4)
            
            # Background
            bg_color = QColor(255, 255, 0, 220)
            painter.setBrush(bg_color)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 4, 4)
            
            # Text
            painter.setPen(Qt.black)
            painter.drawText(rect, Qt.AlignCenter, weight_str)


class NeuronItem(QGraphicsEllipseItem):
    """Neuron body."""
    
    def __init__(self, x, y, radius, name, parent=None):
        super().__init__(x - radius, y - radius, radius * 2, radius * 2, parent)
        self.name = name
        self.center = QPointF(x, y)
        self.radius = radius
        # Hover states removed to prevent crashes
        self.is_selected = False
        self.setAcceptHoverEvents(False)
        self.setData(0, ('neuron', name))
        self.setZValue(2)

    def event(self, event):
        # If the item has been removed from the scene, ignore all events
        if self.scene() is None:
            return False
        return super().event(event)


class DesignerConfig:
    """Manages designer preferences stored in a JSON config file."""
    
    def __init__(self, config_path=None):
        if config_path is None:
            # Store in user's home directory
            config_dir = os.path.expanduser("~/.dosidicus")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "designer_config.json")
        
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        """Load config from file, or return defaults if file doesn't exist."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        
        # Default config
        return {
            'confirm_connection_delete': True
        }
    
    def save(self):
        """Save current config to file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")
    
    def get(self, key, default=None):
        """Get a config value."""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Set a config value and save."""
        self.config[key] = value
        self.save()


class ConfirmDeleteDialog(QDialog):
    """Confirmation dialog with 'Don't ask again' checkbox."""
    
    def __init__(self, source, target, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Connection")
        self.dont_ask_again = False
        
        layout = QVBoxLayout()
        
        # Message
        msg = QLabel(f"Are you sure you want to delete the connection:\n{source} → {target}?")
        msg.setWordWrap(True)
        layout.addWidget(msg)
        
        # Don't ask again checkbox
        self.checkbox = QCheckBox("Don't ask again")
        layout.addWidget(self.checkbox)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.yes_button = QPushButton("Yes, Delete")
        self.yes_button.clicked.connect(self.accept)
        
        self.no_button = QPushButton("Cancel")
        self.no_button.clicked.connect(self.reject)
        
        button_layout.addWidget(self.no_button)
        button_layout.addWidget(self.yes_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Make Yes button the default
        self.yes_button.setDefault(True)
        self.yes_button.setFocus()
    
    def accept(self):
        """Override to capture checkbox state."""
        self.dont_ask_again = self.checkbox.isChecked()
        super().accept()


class ConnectionWeightDialog(QDialog):
    """Dialog for editing connection weight with delete button."""
    
    def __init__(self, source, target, current_weight, config, parent=None):
        super().__init__(parent)
        self.source = source
        self.target = target
        self.config = config
        self.delete_requested = False
        
        self.setWindowTitle("Edit Connection")
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Connection info
        info_label = QLabel(f"Connection: {source} → {target}")
        info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(info_label)
        
        # Weight editor
        weight_layout = QHBoxLayout()
        weight_layout.addWidget(QLabel("Weight:"))
        
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(-1.0, 1.0)
        self.weight_spin.setSingleStep(0.05)
        self.weight_spin.setDecimals(3)
        self.weight_spin.setValue(current_weight)
        self.weight_spin.setMinimumWidth(100)
        weight_layout.addWidget(self.weight_spin)
        
        layout.addLayout(weight_layout)
        
        # Info text
        info_text = QLabel("Positive = Excitatory (green), Negative = Inhibitory (red)")
        info_text.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_text)
        
        layout.addSpacing(10)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.delete_button = QPushButton("Delete Connection")
        self.delete_button.setStyleSheet("background-color: #d32f2f; color: white;")
        self.delete_button.clicked.connect(self.on_delete_clicked)
        button_layout.addWidget(self.delete_button)
        
        button_layout.addStretch()
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setDefault(True)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        # Focus on weight spinner
        self.weight_spin.setFocus()
        self.weight_spin.selectAll()
    
    def on_delete_clicked(self):
        """Handle delete button click with optional confirmation."""
        should_confirm = self.config.get('confirm_connection_delete', True)
        
        if should_confirm:
            # Show confirmation dialog
            confirm_dlg = ConfirmDeleteDialog(self.source, self.target, self)
            result = confirm_dlg.exec_()
            
            if result == QDialog.Accepted:
                # Update config if user checked "don't ask again"
                if confirm_dlg.dont_ask_again:
                    self.config.set('confirm_connection_delete', False)
                
                self.delete_requested = True
                self.reject()  # Close the weight dialog
            # If cancelled, do nothing - stay in weight dialog
        else:
            # No confirmation needed
            self.delete_requested = True
            self.reject()
    
    def get_weight(self):
        """Get the edited weight value."""
        return self.weight_spin.value()



class BrainCanvas(QGraphicsView):
    """Main canvas for visualizing and editing brain designs."""
    
    # Signals
    neuronSelected = pyqtSignal(str) 
    neuronMoved = pyqtSignal(str, float, float)
    connectionCreated = pyqtSignal(str, str)
    connectionSelected = pyqtSignal(str, str)
    connectionDeleted = pyqtSignal(str, str)  # source, target
    canvasClicked = pyqtSignal(float, float)
    weightChanged = pyqtSignal(str, str, float)  # source, target, new_weight
    connectionReversed = pyqtSignal(str, str)    # old_source, old_target
    
    NEURON_RADIUS = 25
    WEIGHT_STEP = 0.05
    WEIGHT_STEP_LARGE = 0.25
    
    # Grid settings
    GRID_SIZE_MINOR = 25       # Small grid spacing
    GRID_SIZE_MAJOR = 100      # Large grid spacing (every 4th line)
    GRID_COLOR_MINOR = QColor(220, 220, 230, 100)  # Subtle minor grid
    GRID_COLOR_MAJOR = QColor(200, 200, 215, 150)  # Slightly more visible major grid
    
    def __init__(self, design: BrainDesign, parent=None):
        super().__init__(parent)
        self.design = design
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Config for preferences
        self.config = DesignerConfig()
        
        # Selection state
        self.selected_neuron = None
        self.selected_connection_key = None  # (source, target) tuple
        
        # Interaction state
        self.pan_active = False
        self.pan_start_pos = QPointF()
        self.drag_line = None
        self.drag_source_id = None
        self.drag_start_pos = None
        self.zoom_level = 1.0
        
        # Item tracking
        self.neuron_items = {}      # name -> NeuronItem
        self.connection_items = {}  # (source, target) -> SmartConnectionItem
        
        # Setup
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setMouseTracking(True)
        # Background is now drawn in drawBackground() for infinite grid support
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)  # Ensures grid redraws on scroll
        self.scene.setSceneRect(-500, -200, 1500, 800)
        self.setFocusPolicy(Qt.StrongFocus)  # Ensure we get key events
        
        self.rebuild()
        
        # Animation timer
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_network)
        self.anim_timer.start(33)

    def drawBackground(self, painter, rect):
        """Draw an infinite grid that scales with zoom."""
        # Fill background first
        painter.fillRect(rect, QColor(245, 245, 250))
        
        # Get the visible rectangle with some padding
        left = int(rect.left()) - (int(rect.left()) % self.GRID_SIZE_MINOR) - self.GRID_SIZE_MINOR
        top = int(rect.top()) - (int(rect.top()) % self.GRID_SIZE_MINOR) - self.GRID_SIZE_MINOR
        right = int(rect.right()) + self.GRID_SIZE_MINOR
        bottom = int(rect.bottom()) + self.GRID_SIZE_MINOR
        
        painter.setRenderHint(QPainter.Antialiasing, False)  # Crisp grid lines
        
        # Draw minor grid lines
        painter.setPen(QPen(self.GRID_COLOR_MINOR, 1))
        
        # Vertical lines
        x = left
        while x <= right:
            # Skip major grid lines (we'll draw them separately)
            if x % self.GRID_SIZE_MAJOR != 0:
                painter.drawLine(x, top, x, bottom)
            x += self.GRID_SIZE_MINOR
        
        # Horizontal lines
        y = top
        while y <= bottom:
            if y % self.GRID_SIZE_MAJOR != 0:
                painter.drawLine(left, y, right, y)
            y += self.GRID_SIZE_MINOR
        
        # Draw major grid lines (thicker)
        painter.setPen(QPen(self.GRID_COLOR_MAJOR, 1.5))
        
        # Vertical major lines
        major_left = left - (left % self.GRID_SIZE_MAJOR)
        x = major_left
        while x <= right:
            painter.drawLine(x, top, x, bottom)
            x += self.GRID_SIZE_MAJOR
        
        # Horizontal major lines
        major_top = top - (top % self.GRID_SIZE_MAJOR)
        y = major_top
        while y <= bottom:
            painter.drawLine(left, y, right, y)
            y += self.GRID_SIZE_MAJOR
        
        # Draw origin axes (optional - slightly more prominent)
        if left <= 0 <= right:
            painter.setPen(QPen(QColor(180, 180, 200, 180), 2))
            painter.drawLine(0, top, 0, bottom)
        if top <= 0 <= bottom:
            painter.setPen(QPen(QColor(180, 180, 200, 180), 2))
            painter.drawLine(left, 0, right, 0)

    def animate_network(self):
        """Advance pulse animations on all connections."""
        for item in self.connection_items.values():
            item.advance_pulse()

    def rebuild(self):
        """Rebuild the entire visual scene from the design."""
        # [FIX] Do NOT call setEnabled(False) here.
        # Disabling the widget clears focus, preventing key events (like Space) from working
        # immediately after a selection rebuild.
        
        self.scene.blockSignals(True)  # Prevent signal emissions during rebuild
        self.scene.clear()
        self.neuron_items.clear()
        self.connection_items.clear()
        self.draw_layers()
        self.draw_connections()
        self.draw_neurons()
        self.center_on_neurons()
        self.scene.blockSignals(False)
        
    def draw_layers(self):
        """Draw layer backgrounds."""
        for layer in self.design.layers:
            y_pos = layer.y_position
            rect_height = DEFAULT_LAYER_HEIGHT
            rect_top = y_pos - rect_height / 2
            
            lt = layer.layer_type.name.lower()
            if lt == 'input': 
                fill, border = (180, 235, 180, 100), (120, 180, 120, 150)
            elif lt == 'output': 
                fill, border = (235, 180, 180, 100), (180, 120, 120, 150)
            else: 
                fill, border = (200, 200, 235, 100), (160, 160, 200, 150)

            rect = QGraphicsRectItem(-400, rect_top, 1300, rect_height)
            rect.setBrush(QBrush(QColor(*fill)))
            rect.setPen(QPen(QColor(*border), 2, Qt.DashLine))
            rect.setZValue(-10)
            self.scene.addItem(rect)

            label = QGraphicsTextItem(layer.name)
            label.setDefaultTextColor(QColor(*border[:3]))
            label.setFont(QFont("Arial", 11, QFont.Bold))
            label.setPos(-380, rect_top + 5)
            label.setZValue(-9)
            self.scene.addItem(label)

    def draw_connections(self):
        """Draw all connections."""
        for conn in self.design.connections:
            src_neuron = self.design.get_neuron(conn.source)
            tgt_neuron = self.design.get_neuron(conn.target)
            if not src_neuron or not tgt_neuron:
                continue
                
            src_pos = QPointF(*src_neuron.position)
            tgt_pos = QPointF(*tgt_neuron.position)
            
            item = SmartConnectionItem(
                src_pos, tgt_pos, conn.weight,
                conn.source, conn.target
            )
            item.setData(0, conn)  # Store connection reference
            
            # Restore selection state
            if self.selected_connection_key == (conn.source, conn.target):
                item.is_selected = True
            
            self.scene.addItem(item)
            self.connection_items[(conn.source, conn.target)] = item

    def draw_neurons(self):
        """Draw all neurons with proper styling."""
        for name, neuron in self.design.neurons.items():
            x, y = neuron.position
            
            # Determine ring color based on neuron type
            if neuron.is_core:
                ring_color = QColor(*CORE_NEURON_RING_COLOR)
                ring_width = PROTECTED_RING_WIDTH
            elif neuron.is_required:
                ring_color = QColor(*INPUT_SENSOR_RING_COLOR)
                ring_width = PROTECTED_RING_WIDTH
            elif neuron.is_sensor:
                ring_color = QColor(*INPUT_SENSOR_RING_COLOR)
                ring_width = NORMAL_RING_WIDTH
            else:
                ring_color = QColor(*CUSTOM_NEURON_RING_COLOR)
                ring_width = NORMAL_RING_WIDTH
            
            # Override for selection
            if name == self.selected_neuron:
                ring_color = QColor(255, 255, 255)
                ring_width = 4
            
            # Outer ring
            outer = QGraphicsEllipseItem(
                x - self.NEURON_RADIUS - 3, 
                y - self.NEURON_RADIUS - 3, 
                (self.NEURON_RADIUS + 3) * 2, 
                (self.NEURON_RADIUS + 3) * 2
            )
            outer.setPen(QPen(ring_color, ring_width))
            outer.setZValue(1)
            outer.setData(0, ('ring', name))
            self.scene.addItem(outer)
            
            # Neuron body (interactive)
            body = NeuronItem(x, y, self.NEURON_RADIUS, name)
            body.setBrush(QBrush(QColor(*neuron.color)))
            body.setPen(QPen(QColor(50, 50, 50), 2))
            body.is_selected = (name == self.selected_neuron)
            self.scene.addItem(body)
            self.neuron_items[name] = body
            
            # Label
            display = name.replace('_', ' ').title()
            if neuron.is_core: 
                display = f"🟡 {display}"
            elif name == 'can_see_food': 
                display = f"👁 {display}"
            elif neuron.is_sensor: 
                display = f"📡 {display}"
            
            label = QGraphicsTextItem(display)
            label.setDefaultTextColor(QColor(40, 40, 50))
            label.setFont(QFont("Arial", 9, QFont.Bold))
            label.setPos(x - label.boundingRect().width() / 2, y + self.NEURON_RADIUS + 5)
            label.setZValue(3)
            self.scene.addItem(label)

    def center_on_neurons(self):
        """Adjust scene rect to fit all neurons."""
        if not self.design.neurons or self.pan_active: 
            return
        positions = [n.position for n in self.design.neurons.values()]
        if not positions:
            return
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        self.scene.setSceneRect(QRectF(
            min(xs) - 100, min(ys) - 100, 
            max(xs) - min(xs) + 200, max(ys) - min(ys) + 200
        ))

    def get_neuron_at(self, pos):
        """Find neuron at scene position."""
        for name, neuron in self.design.neurons.items():
            if math.hypot(pos.x() - neuron.position[0], pos.y() - neuron.position[1]) <= self.NEURON_RADIUS + 5:
                return name
        return None
    
    def get_connection_at(self, pos):
        """Find connection at scene position."""
        items = self.scene.items(pos)
        for item in items:
            if isinstance(item, SmartConnectionItem):
                return item
        return None

    # =========================================================================
    # MOUSE EVENTS
    # =========================================================================

    def mousePressEvent(self, event):
        # Ensure canvas gets keyboard focus for shortcuts
        self.setFocus()
        
        scene_pos = self.mapToScene(event.pos())
        
        # Right-click: Pan
        if event.button() == Qt.RightButton:
            self.pan_active = True
            self.pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        # Left-click
        if event.button() == Qt.LeftButton:
            # Check for neuron click
            clicked_neuron = self.get_neuron_at(scene_pos)
            if clicked_neuron:
                self.select_neuron(clicked_neuron)
                
                # Start connection drag if not an output neuron
                n_obj = self.design.get_neuron(clicked_neuron)
                if n_obj.neuron_type != NeuronType.OUTPUT:
                    self.start_connection_drag(clicked_neuron, scene_pos)
                event.accept()
                return

            # Check for connection click
            conn_item = self.get_connection_at(scene_pos)
            if conn_item:
                conn_data = conn_item.data(0)
                self.select_connection(conn_data.source, conn_data.target)
                event.accept()
                return
            
            # Click on empty space - just clear selection
            self.clear_selection()
            
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to edit connection weight."""
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            
            # Check if double-clicking on a connection
            conn_item = self.get_connection_at(scene_pos)
            if conn_item:
                conn_data = conn_item.data(0)
                self.open_weight_dialog(conn_data.source, conn_data.target)
                event.accept()
                return
        
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        # Panning
        if self.pan_active:
            delta = event.pos() - self.pan_start_pos
            self.pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        
        # Connection dragging
        if self.drag_line:
            scene_pos = self.mapToScene(event.pos())
            target_id = self.get_neuron_at(scene_pos)
            
            if target_id and target_id != self.drag_source_id:
                end = QPointF(*self.design.get_neuron(target_id).position)
                valid = self.is_valid_connection(self.drag_source_id, target_id)
                color = QColor(50, 205, 50) if valid else QColor(220, 20, 60)
                style = Qt.SolidLine if valid else Qt.DashLine
            else:
                end = scene_pos
                color = QColor(255, 215, 0)
                style = Qt.DashLine
            
            self.drag_line.setLine(QLineF(self.drag_start_pos, end))
            self.drag_line.setPen(QPen(color, 3, style))
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # End pan
        if event.button() == Qt.RightButton:
            self.pan_active = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        
        # End connection drag
        if self.drag_line:
            scene_pos = self.mapToScene(event.pos())
            target_id = self.get_neuron_at(scene_pos)
            
            self.scene.removeItem(self.drag_line)
            self.drag_line = None
            
            if target_id and target_id != self.drag_source_id:
                if self.is_valid_connection(self.drag_source_id, target_id):
                    self.design.add_connection(self.drag_source_id, target_id, 0.5)
                    self.connectionCreated.emit(self.drag_source_id, target_id)
                    self.select_connection(self.drag_source_id, target_id)
                    self.rebuild()
                else:
                    QToolTip.showText(QCursor.pos(), "Invalid connection", self)
            
            self.drag_source_id = None
            event.accept()
            return
            
        super().mouseReleaseEvent(event)

    # =========================================================================
    # KEY EVENTS
    # =========================================================================

    def keyPressEvent(self, event):
        # Delete selected connection
        if event.key() == Qt.Key_Delete:
            if self.selected_connection_key:
                self.design.remove_connection(*self.selected_connection_key)
                self.selected_connection_key = None
                self.rebuild()
                event.accept()
                return
        
        # SPACE: Reverse selected connection direction
        if event.key() == Qt.Key_Space:
            if self.selected_connection_key:
                self.reverse_selected_connection()
                event.accept()
                return
        
        # Weight adjustment with +/- keys
        if event.key() in [Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus, Qt.Key_Underscore]:
            self.adjust_connection_weight_by_key(event)
            event.accept()
            return
        
        # Page Up/Down for weight adjustment
        if event.key() in [Qt.Key_PageUp, Qt.Key_PageDown]:
            self.adjust_connection_weight_page(event)
            event.accept()
            return
        
        super().keyPressEvent(event)

    # =========================================================================
    # WHEEL EVENT (Weight adjustment)
    # =========================================================================

    def wheelEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        
        # Check if mouse is over a connection
        conn_item = self.get_connection_at(scene_pos)
        
        # Or if a connection is selected
        if conn_item or self.selected_connection_key:
            # Prefer hovered, fall back to selected
            if conn_item:
                conn = conn_item.data(0)
            else:
                conn = self.design.get_connection(*self.selected_connection_key)
            
            if conn:
                delta = event.angleDelta().y()
                step = self.WEIGHT_STEP_LARGE if event.modifiers() & Qt.ShiftModifier else self.WEIGHT_STEP
                change = step if delta > 0 else -step
                
                new_weight = max(-1.0, min(1.0, conn.weight + change))
                # Snap to zero
                if abs(new_weight) < 0.03:
                    new_weight = 0.0
                conn.weight = new_weight
                
                self.rebuild()
                self.weightChanged.emit(conn.source, conn.target, new_weight)
                QToolTip.showText(QCursor.pos(), f"Weight: {new_weight:+.2f}", self)
                event.accept()
                return
        
        # Zoom if not on connection
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_level = max(0.2, min(3.0, self.zoom_level * factor))
        self.setTransform(QTransform().scale(self.zoom_level, self.zoom_level))
        event.accept()

    # =========================================================================
    # SELECTION HELPERS
    # =========================================================================

    def select_neuron(self, name):
        """Select a neuron and deselect everything else."""
        self.selected_neuron = name
        self.selected_connection_key = None
        self.neuronSelected.emit(name)
        self.rebuild()
    
    def select_connection(self, source, target):
        """Select a connection and deselect everything else."""
        self.selected_connection_key = (source, target)
        self.selected_neuron = None
        self.connectionSelected.emit(source, target)
        self.rebuild()
    
    def clear_selection(self):
        """Clear all selection."""
        self.selected_neuron = None
        self.selected_connection_key = None
        self.rebuild()

    def start_connection_drag(self, neuron_name, scene_pos):
        """Start dragging a new connection from a neuron."""
        n_obj = self.design.get_neuron(neuron_name)
        self.drag_source_id = neuron_name
        self.drag_start_pos = QPointF(*n_obj.position)
        
        self.drag_line = QGraphicsLineItem(QLineF(self.drag_start_pos, scene_pos))
        self.drag_line.setPen(QPen(QColor(255, 215, 0), 3, Qt.DashLine))
        self.drag_line.setZValue(10)
        self.scene.addItem(self.drag_line)

    # =========================================================================
    # CONNECTION OPERATIONS
    # =========================================================================

    def is_valid_connection(self, src_name, tgt_name):
        """Check if a connection would be valid."""
        src = self.design.get_neuron(src_name)
        tgt = self.design.get_neuron(tgt_name)
        
        if not src or not tgt:
            return False
        
        # Can't connect TO input/sensor neurons
        if tgt.neuron_type in [NeuronType.INPUT, NeuronType.SENSOR]:
            return False
        
        # Can't connect FROM output neurons
        if src.neuron_type == NeuronType.OUTPUT:
            return False
        
        # Can't duplicate existing connection
        if self.design.get_connection(src_name, tgt_name):
            return False
        
        return True

    def reverse_selected_connection(self):
        """Reverse the direction of the selected connection."""
        if not self.selected_connection_key:
            QToolTip.showText(QCursor.pos(), "No connection selected", self)
            return
        
        source, target = self.selected_connection_key
        conn = self.design.get_connection(source, target)
        if not conn:
            QToolTip.showText(QCursor.pos(), "Connection not found", self)
            return
        
        # Get neuron info for better error messages
        src_neuron = self.design.get_neuron(source)
        tgt_neuron = self.design.get_neuron(target)
        
        # Check if reverse already exists
        if self.design.get_connection(target, source):
            QToolTip.showText(QCursor.pos(), "Reverse connection already exists", self)
            return
        
        # [FIX] Logic was swapped. 
        # We are proposing a NEW connection: target -> source
        # So 'target' acts as the NEW SOURCE, and 'source' acts as the NEW TARGET.
        
        # Rule 1: New Target (old source) cannot be a Sensor/Input
        if src_neuron and src_neuron.neuron_type in [NeuronType.SENSOR, NeuronType.INPUT]:
            QToolTip.showText(QCursor.pos(), f"Cannot connect TO sensor/input '{source}'", self)
            return
        
        # Rule 2: New Source (old target) cannot be an Output
        if tgt_neuron and tgt_neuron.neuron_type == NeuronType.OUTPUT:
            QToolTip.showText(QCursor.pos(), f"Cannot connect FROM output '{target}'", self)
            return
        
        # Perform the reversal
        weight = conn.weight
        self.design.remove_connection(source, target)
        self.design.add_connection(target, source, weight)
        
        # Update selection to the new connection
        self.selected_connection_key = (target, source)
        self.connectionReversed.emit(source, target)
        self.rebuild()
        
        QToolTip.showText(QCursor.pos(), f"Reversed: {target} → {source}", self)

    def open_weight_dialog(self, source, target):
        """Open dialog to edit connection weight with delete option."""
        conn = self.design.get_connection(source, target)
        if not conn:
            return
        
        # Open the dialog
        dialog = ConnectionWeightDialog(source, target, conn.weight, self.config, self)
        result = dialog.exec_()
        
        # Handle delete request
        if dialog.delete_requested:
            # Delete the connection
            self.design.remove_connection(source, target)
            self.selected_connection_key = None
            self.connectionDeleted.emit(source, target)
            self.rebuild()
            return
        
        # Handle weight change (if OK was pressed)
        if result == QDialog.Accepted:
            new_weight = dialog.get_weight()
            if new_weight != conn.weight:
                conn.weight = new_weight
                self.weightChanged.emit(source, target, new_weight)
                self.rebuild()

    def adjust_connection_weight_by_key(self, event):
        """Adjust weight using +/- keys."""
        # Find target connection (click position or selected)
        pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
        conn_item = self.get_connection_at(pos)
        
        if conn_item:
            conn = conn_item.data(0)
        elif self.selected_connection_key:
            conn = self.design.get_connection(*self.selected_connection_key)
        else:
            return
        
        if not conn:
            return
        
        step = self.WEIGHT_STEP_LARGE if event.modifiers() & Qt.ShiftModifier else self.WEIGHT_STEP
        if event.key() in [Qt.Key_Minus, Qt.Key_Underscore]:
            step = -step
        
        conn.weight = max(-1.0, min(1.0, conn.weight + step))
        self.rebuild()
        self.weightChanged.emit(conn.source, conn.target, conn.weight)
        QToolTip.showText(QCursor.pos(), f"Weight: {conn.weight:+.2f}", self)

    def adjust_connection_weight_page(self, event):
        """Adjust weight using Page Up/Down (larger steps)."""
        # Find target connection
        pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
        conn_item = self.get_connection_at(pos)
        
        if conn_item:
            conn = conn_item.data(0)
        elif self.selected_connection_key:
            conn = self.design.get_connection(*self.selected_connection_key)
        else:
            return
        
        if not conn:
            return
        
        # Page keys use larger step
        step = self.WEIGHT_STEP_LARGE
        if event.key() == Qt.Key_PageDown:
            step = -step
        
        conn.weight = max(-1.0, min(1.0, conn.weight + step))
        self.rebuild()
        self.weightChanged.emit(conn.source, conn.target, conn.weight)
        QToolTip.showText(QCursor.pos(), f"Weight: {conn.weight:+.2f}", self)