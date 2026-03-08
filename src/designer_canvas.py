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

from .designer_core import BrainDesign
from .designer_constants import (
    NeuronType, CORE_NEURON_RING_COLOR, INPUT_SENSOR_RING_COLOR, 
    CUSTOM_NEURON_RING_COLOR, PROTECTED_RING_WIDTH, NORMAL_RING_WIDTH, 
    DEFAULT_LAYER_HEIGHT
)


class SmartConnectionItem(QGraphicsItem):
    """Visual representation of a neural connection with organic growth animation."""
    
    def __init__(self, source_pos, target_pos, weight=0.5, source_name="", target_name="", parent=None):
        super().__init__(parent)
        self.source_pos = source_pos
        self.target_pos = target_pos
        self.weight = weight
        self.source_name = source_name
        self.target_name = target_name
        
        # Visual states
        self.is_selected = False
        self.is_hovered = False
        self.is_dying = False  # If True, connection is retreating/fading out
        
        # Organic Animation States
        self.growth = 0.0      # 0.0 = at source, 1.0 = full connection
        self.opacity = 0.0     # 0.0 = invisible, 1.0 = fully visible
        
        # Randomized "Personality" for this vine
        self.growth_speed = 0.02 + (hash(str(source_pos) + str(target_pos)) % 50) * 0.0006
        self.growth = -0.1 # Start slightly delayed
        
        # Pulse animation (standard)
        self.pulse_phase = 0.0
        
        self.setAcceptHoverEvents(True)
        self.setZValue(-5) 
        self.hit_thickness = 25 

    def boundingRect(self):
        extra = 30
        # protect against null-length line
        if self.source_pos == self.target_pos:
            return QRectF(self.source_pos.x() - extra, self.source_pos.y() - extra,
                        2 * extra, 2 * extra)
        return QRectF(self.source_pos, self.target_pos).normalized() \
            .adjusted(-extra, -extra, extra, extra)

    def shape(self):
        """Custom hit area for connection lines."""
        path = QPainterPath()
        path.moveTo(self.source_pos)
        path.lineTo(self.target_pos)
        
        # Create a stroker to widen the hit area
        stroker = QPainterPathStroker()
        stroker.setWidth(self.hit_thickness)
        stroker.setCapStyle(Qt.RoundCap)
        return stroker.createStroke(path)
    
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def advance_animation(self):
        """Calculates one frame of growth/retreat logic."""
        
        # 1. Handle Dying (Retreating)
        if self.is_dying:
            self.growth -= self.growth_speed * 1.5
            self.opacity -= 0.05
            if self.opacity < 0: self.opacity = 0
            return self.opacity <= 0

        # 2. Handle Living (Growing)
        if self.growth < 1.0:
            self.growth += self.growth_speed
        if self.growth > 1.0: self.growth = 1.0
        
        # Fade in
        if self.growth > 0 and self.opacity < 1.0:
            self.opacity += 0.05
            if self.opacity > 1.0: self.opacity = 1.0
            
        # 3. Pulse Logic
        if self.growth > 0.8:
            current_speed = 0.02 + (abs(self.weight) * 0.06)
            self.pulse_phase += current_speed
            if self.pulse_phase > 1.0: self.pulse_phase = 0.0

        self.update()
        return False # Still alive

    def paint(self, painter, option, widget):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw hover glow (subtle blue when hovered but not selected)
        if self.is_hovered and not self.is_selected:
            pen_width = 12
            glow_color = QColor(100, 200, 255, 100)
            painter.setPen(QPen(glow_color, pen_width, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(self.source_pos, self.target_pos)

        # Draw the actual connection line
        # Determine color based on weight (Green=Excitatory, Red=Inhibitory)
        base_color = QColor(50, 205, 50) if self.weight >= 0 else QColor(220, 50, 50)
        
        # Adjust alpha by opacity (growth animation)
        base_color.setAlpha(int(255 * self.opacity))
        
        # Determine thickness (magnitude of weight)
        thickness = 2 + abs(self.weight) * 6
        
        # Pulse effect for thickness
        pulse = math.sin(self.pulse_phase * math.pi * 2) * 0.5 + 0.5
        thickness += pulse * 1.5

        # Draw selection highlight (yellow glow when selected)
        if self.is_selected:
            painter.setPen(QPen(QColor(255, 215, 0), thickness + 4, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(self.source_pos, self.target_pos)

        painter.setPen(QPen(base_color, thickness, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(self.source_pos, self.target_pos)
        
        painter.restore()


class ConnectorNeuronItem(QGraphicsItem):
    """
    Connector Neuron: Black hexagon with a white 'c' inside.
    Matches brain_widget.py's draw_hexagon_neuron style.
    """
    
    def __init__(self, x, y, radius, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.radius = radius
        self.is_selected = False
        self.is_hovered = False
        self.neuron_type = NeuronType.CONNECTOR
        
        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setData(0, ('neuron', name))
        self.setZValue(2)
    
    def boundingRect(self):
        extra = 15
        return QRectF(-self.radius - extra, -self.radius - extra,
                      (self.radius + extra) * 2, (self.radius + extra) * 2)
    
    def shape(self):
        """Custom hitbox for Hexagon."""
        path = QPainterPath()
        sides = 6
        polygon = QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QPointF(self.radius * math.cos(angle), 
                                   self.radius * math.sin(angle)))
        path.addPolygon(polygon)
        path.closeSubpath()
        return path
    
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def paint(self, painter, option, widget):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw hover glow
        if self.is_hovered and not self.is_selected:
            grad = QRadialGradient(0, 0, self.radius + 12)
            grad.setColorAt(0.5, QColor(100, 200, 255, 100))
            grad.setColorAt(1.0, QColor(100, 200, 255, 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(0, 0), self.radius + 12, self.radius + 12)
        
        # Draw selection ring
        if self.is_selected:
            painter.setPen(QPen(QColor(255, 255, 255), 4))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(0, 0), self.radius + 5, self.radius + 5)
        
        # Draw BLACK hexagon body
        sides = 6
        polygon = QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QPointF(self.radius * math.cos(angle), 
                                   self.radius * math.sin(angle)))
        
        painter.setBrush(QBrush(QColor(0, 0, 0)))  # BLACK fill
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        painter.drawPolygon(polygon)
        
        # Draw WHITE 'c' inside
        font = QFont("Arial", int(self.radius * 0.7))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255))  # WHITE text
        
        rect = QRectF(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        painter.drawText(rect, Qt.AlignCenter, "c")
        
        painter.restore()


class NeuronItem(QGraphicsEllipseItem):
    """
    Neuron body. 
    Acts as the Parent item for the Ring and Label.
    """
    
    def __init__(self, x, y, radius, name, neuron_type=None, parent=None):
        # Define geometry centered at (0,0) locally
        super().__init__(-radius, -radius, radius * 2, radius * 2, parent)
        self.name = name
        self.radius = radius
        self.is_selected = False
        self.is_hovered = False
        self.neuron_type = neuron_type
        # Set absolute position in the scene
        self.setPos(x, y)
        
        self.setAcceptHoverEvents(True)
        self.setData(0, ('neuron', name))
        self.setZValue(2)

    def event(self, event):
        if self.scene() is None:
            return False
        return super().event(event)
    
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)
    
    def paint(self, painter, option, widget):
        # Draw hover glow
        if self.is_hovered and not self.is_selected:
            painter.setRenderHint(QPainter.Antialiasing)
            # Glow is drawn relative to local center (0,0)
            grad = QRadialGradient(0, 0, self.radius + 12)
            grad.setColorAt(0.5, QColor(100, 200, 255, 100))
            grad.setColorAt(1.0, QColor(100, 200, 255, 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(-self.radius - 12, -self.radius - 12, (self.radius + 12)*2, (self.radius + 12)*2)
        
        super().paint(painter, option, widget)


class DesignerConfig:
    """Manages designer preferences."""
    def __init__(self, config_path=None):
        if config_path is None:
            config_dir = os.path.expanduser("~/.dosidicus")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "designer_config.json")
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except: pass
        return {'confirm_connection_delete': True}
    
    def save(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except: pass
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save()


class ConfirmDeleteDialog(QDialog):
    """Confirmation dialog."""
    def __init__(self, source, target, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Connection")
        self.dont_ask_again = False
        layout = QVBoxLayout()
        msg = QLabel(f"Are you sure you want to delete the connection:\n{source} → {target}?")
        msg.setWordWrap(True)
        layout.addWidget(msg)
        self.checkbox = QCheckBox("Don't ask again")
        layout.addWidget(self.checkbox)
        button_layout = QHBoxLayout()
        self.yes_button = QPushButton("Yes, Delete")
        self.yes_button.clicked.connect(self.accept)
        self.no_button = QPushButton("Cancel")
        self.no_button.clicked.connect(self.reject)
        button_layout.addWidget(self.no_button)
        button_layout.addWidget(self.yes_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.yes_button.setDefault(True)
    
    def accept(self):
        self.dont_ask_again = self.checkbox.isChecked()
        super().accept()


class ConnectionWeightDialog(QDialog):
    """Dialog for editing connection weight."""
    def __init__(self, source, target, current_weight, config, parent=None):
        super().__init__(parent)
        self.source = source
        self.target = target
        self.config = config
        self.delete_requested = False
        self.setWindowTitle("Edit Connection")
        self.setModal(True)
        layout = QVBoxLayout()
        info_label = QLabel(f"Connection: {source} → {target}")
        info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(info_label)
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
        info_text = QLabel("Positive = Excitatory (green), Negative = Inhibitory (red)")
        info_text.setStyleSheet("color: gray; font-size: 9pt;")
        layout.addWidget(info_text)
        layout.addSpacing(10)
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
        self.weight_spin.setFocus()
        self.weight_spin.selectAll()
    
    def on_delete_clicked(self):
        should_confirm = self.config.get('confirm_connection_delete', True)
        if should_confirm:
            confirm_dlg = ConfirmDeleteDialog(self.source, self.target, self)
            result = confirm_dlg.exec_()
            if result == QDialog.Accepted:
                if confirm_dlg.dont_ask_again:
                    self.config.set('confirm_connection_delete', False)
                self.delete_requested = True
                self.reject()
        else:
            self.delete_requested = True
            self.reject()
    
    def get_weight(self):
        return self.weight_spin.value()


class BrainCanvas(QGraphicsView):
    """Main canvas for visualizing and editing brain designs."""
    
    # Signals
    neuronSelected = pyqtSignal(str) 
    neuronMoved = pyqtSignal(str, float, float)
    connectionCreated = pyqtSignal(str, str)
    connectionSelected = pyqtSignal(str, str)
    connectionDeleted = pyqtSignal(str, str)
    canvasClicked = pyqtSignal(float, float)
    weightChanged = pyqtSignal(str, str, float)
    connectionReversed = pyqtSignal(str, str)
    
    NEURON_RADIUS = 25
    WEIGHT_STEP = 0.05
    WEIGHT_STEP_LARGE = 0.25
    
    GRID_SIZE_MINOR = 25
    GRID_SIZE_MAJOR = 100
    GRID_COLOR_MINOR = QColor(220, 220, 230, 100)
    GRID_COLOR_MAJOR = QColor(200, 200, 215, 150)
    
    def __init__(self, design: BrainDesign, parent=None):
        super().__init__(parent)
        self.design = design
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.config = DesignerConfig()
        
        self.selected_neuron = None
        self.selected_connection_key = None
        
        self.pan_active = False
        self.pan_start_pos = QPointF()
        self.drag_line = None
        self.drag_source_id = None
        self.drag_start_pos = None
        self.zoom_level = 1.0
        
        self.dragging_neuron = None
        self.neuron_drag_start_pos = None
        
        self.neuron_items = {}
        self.connection_items = {}
        
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setMouseTracking(True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.scene.setSceneRect(-500, -200, 1500, 800)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.rebuild()
        
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_network)
        self.anim_timer.start(33)

    def drawBackground(self, painter, rect):
        painter.fillRect(rect, QColor(245, 245, 250))
        left = int(rect.left()) - (int(rect.left()) % self.GRID_SIZE_MINOR) - self.GRID_SIZE_MINOR
        top = int(rect.top()) - (int(rect.top()) % self.GRID_SIZE_MINOR) - self.GRID_SIZE_MINOR
        right = int(rect.right()) + self.GRID_SIZE_MINOR
        bottom = int(rect.bottom()) + self.GRID_SIZE_MINOR
        
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(self.GRID_COLOR_MINOR, 1))
        
        x = left
        while x <= right:
            if x % self.GRID_SIZE_MAJOR != 0:
                painter.drawLine(x, top, x, bottom)
            x += self.GRID_SIZE_MINOR
        
        y = top
        while y <= bottom:
            if y % self.GRID_SIZE_MAJOR != 0:
                painter.drawLine(left, y, right, y)
            y += self.GRID_SIZE_MINOR
        
        painter.setPen(QPen(self.GRID_COLOR_MAJOR, 1.5))
        major_left = left - (left % self.GRID_SIZE_MAJOR)
        x = major_left
        while x <= right:
            painter.drawLine(x, top, x, bottom)
            x += self.GRID_SIZE_MAJOR
        
        major_top = top - (top % self.GRID_SIZE_MAJOR)
        y = major_top
        while y <= bottom:
            painter.drawLine(left, y, right, y)
            y += self.GRID_SIZE_MAJOR
        
        if left <= 0 <= right:
            painter.setPen(QPen(QColor(180, 180, 200, 180), 2))
            painter.drawLine(0, top, 0, bottom)
        if top <= 0 <= bottom:
            painter.setPen(QPen(QColor(180, 180, 200, 180), 2))
            painter.drawLine(left, 0, right, 0)

    def animate_network(self):
        for item in self.connection_items.values():
            item.advance_animation()
        if hasattr(self, 'dying_connections'):
            for i in range(len(self.dying_connections) - 1, -1, -1):
                item = self.dying_connections[i]
                is_dead = item.advance_animation()
                if is_dead:
                    self.scene.removeItem(item)
                    self.dying_connections.pop(i)

    def rebuild(self):
        """Synchronizes the visual scene with the design data."""
        self.scene.blockSignals(True)
        
        # 1. Update Layers
        for item in self.scene.items():
            if not isinstance(item, (NeuronItem, ConnectorNeuronItem, SmartConnectionItem)) and item.zValue() < 0:
                if isinstance(item, (QGraphicsRectItem, QGraphicsTextItem)): 
                     if item.zValue() < -5: self.scene.removeItem(item)
        self.draw_layers()

        # 2. Update Neurons
        existing_neurons = set(self.neuron_items.keys())
        design_neurons = set(self.design.neurons.keys())
        
        for name in existing_neurons - design_neurons:
            self.scene.removeItem(self.neuron_items[name])
            del self.neuron_items[name]
            
        for name in design_neurons:
            neuron = self.design.neurons[name]
            if neuron.position is None: continue
            
            x, y = neuron.position
            
            if name in self.neuron_items:
                # Update existing position
                self.neuron_items[name].setPos(x, y) 
            else:
                self.draw_single_neuron(name, neuron)

        # 3. Connection Update
        existing_keys = set(self.connection_items.keys())
        design_keys = set()
        for conn in self.design.connections:
            design_keys.add((conn.source, conn.target))
        
        for key in existing_keys - design_keys:
            item = self.connection_items[key]
            item.is_dying = True
            del self.connection_items[key]
            if not hasattr(self, 'dying_connections'):
                self.dying_connections = []
            self.dying_connections.append(item)

        for conn in self.design.connections:
            key = (conn.source, conn.target)
            src_neuron = self.design.get_neuron(conn.source)
            tgt_neuron = self.design.get_neuron(conn.target)
            
            if not (src_neuron and tgt_neuron and src_neuron.position and tgt_neuron.position):
                continue

            src_pos = QPointF(*src_neuron.position)
            tgt_pos = QPointF(*tgt_neuron.position)

            if key not in existing_keys:
                item = SmartConnectionItem(src_pos, tgt_pos, conn.weight, conn.source, conn.target)
                item.setData(0, conn)
                if self.selected_connection_key == key: item.is_selected = True
                self.scene.addItem(item)
                self.connection_items[key] = item
            else:
                item = self.connection_items[key]
                item.is_dying = False 
                
                # Check for weight change to ensure visual thickness updates
                if item.weight != conn.weight:
                    item.weight = conn.weight
                    item.update()
                
                if self.selected_connection_key == key: item.is_selected = True
                else: item.is_selected = False
                
                if src_pos != item.source_pos or tgt_pos != item.target_pos:
                    item.prepareGeometryChange()
                    item.source_pos = src_pos
                    item.target_pos = tgt_pos
                    item.update()

        self.center_on_neurons()
        self.scene.blockSignals(False)
        
    def draw_layers(self):
        for layer in self.design.layers:
            y_pos = layer.y_position
            rect_height = DEFAULT_LAYER_HEIGHT
            rect_top = y_pos - rect_height / 2
            
            lt = layer.layer_type.name.lower()
            if lt == 'input': fill, border = (180, 235, 180, 100), (120, 180, 120, 150)
            elif lt == 'output': fill, border = (235, 180, 180, 100), (180, 120, 120, 150)
            else: fill, border = (200, 200, 235, 100), (160, 160, 200, 150)

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

    def draw_single_neuron(self, name, neuron):
        """Draw a single neuron item (Body) and attach its children (Ring, Label)."""
        if neuron.position is None: return

        try:
            x, y = neuron.position
        except (TypeError, ValueError): return

        # Determine Shape
        shape = getattr(neuron, 'shape', 'circle')

        # --- CASE 1: CONNECTOR (Hexagon) ---
        is_connector = (neuron.neuron_type == NeuronType.CONNECTOR or 
                        name.startswith('connector_') or
                        shape == 'hexagon')
        
        if is_connector:
            # Use the special ConnectorNeuronItem (black hexagon with 'c')
            body = ConnectorNeuronItem(x, y, self.NEURON_RADIUS, name)
            body.is_selected = (name == self.selected_neuron)
            self.scene.addItem(body)
            self.neuron_items[name] = body
            
            # Create Label (Child of Body) - simplified for connectors
            display = name.replace('_', ' ').title()
            label = QGraphicsTextItem(display)
            label.setDefaultTextColor(QColor(40, 40, 50))
            label.setFont(QFont("Arial", 8, QFont.Bold))
            
            # Center text horizontally relative to body center (0,0)
            w = label.boundingRect().width()
            label.setPos(-w / 2, self.NEURON_RADIUS + 5)
            label.setZValue(3)
            label.setParentItem(body)
            return

        # --- CASE 2: POLYGONS (Diamond, Square, Triangle) ---
        if shape in ['diamond', 'square', 'triangle']:
            sides = 4
            rotation = 0
            if shape == 'diamond':
                sides = 4
                rotation = 0
            elif shape == 'square':
                sides = 4
                rotation = 45
            elif shape == 'triangle':
                sides = 3
                rotation = 0
            
            # Create Polygon Body
            body = PolygonNeuronItem(x, y, self.NEURON_RADIUS, name, 
                                     sides=sides, rotation=rotation, 
                                     color=neuron.color)
            body.is_selected = (name == self.selected_neuron)
            self.scene.addItem(body)
            self.neuron_items[name] = body

            # Create Label (Child of Body)
            display = name.replace('_', ' ').title()
            label = QGraphicsTextItem(display)
            label.setDefaultTextColor(QColor(40, 40, 50))
            label.setFont(QFont("Arial", 9, QFont.Bold))
            
            w = label.boundingRect().width()
            label.setPos(-w / 2, self.NEURON_RADIUS + 5)
            label.setZValue(3)
            label.setParentItem(body)
            return

        # --- CASE 3: CIRCLE (Default) ---
        # 1. Create Neuron Body (The Parent Item) - standard ellipse
        body = NeuronItem(x, y, self.NEURON_RADIUS, name, neuron.neuron_type)
        body.setBrush(QBrush(QColor(*neuron.color)))
        body.setPen(QPen(QColor(50, 50, 50), 2))
        body.is_selected = (name == self.selected_neuron)
        
        self.scene.addItem(body)
        self.neuron_items[name] = body

        # 2. Determine Ring Style (Only for circles)
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

        if name == self.selected_neuron:
            ring_color = QColor(255, 255, 255)
            ring_width = 4

        # 3. Create Ring (Child of Body)
        r_outer = self.NEURON_RADIUS + 3
        outer = QGraphicsEllipseItem(-r_outer, -r_outer, r_outer * 2, r_outer * 2)
        outer.setPen(QPen(ring_color, ring_width))
        outer.setZValue(1) 
        outer.setData(0, ('ring', name))
        outer.setParentItem(body)
        outer.setFlag(QGraphicsItem.ItemStacksBehindParent)

        # 4. Create Label (Child of Body)
        display = name.replace('_', ' ').title()
        # Add icons for specific types
        if neuron.is_core: display = f"🟡 {display}"
        elif name == 'can_see_food': display = f"👁 {display}"
        elif neuron.is_sensor: display = f"📡 {display}"
        
        label = QGraphicsTextItem(display)
        label.setDefaultTextColor(QColor(40, 40, 50))
        label.setFont(QFont("Arial", 9, QFont.Bold))
        
        # Center text horizontally relative to body center (0,0)
        w = label.boundingRect().width()
        label.setPos(-w / 2, self.NEURON_RADIUS + 5)
        label.setZValue(3)
        label.setParentItem(body)


    def draw_neurons(self):
        for name, neuron in self.design.neurons.items():
            self.draw_single_neuron(name, neuron)

    def center_on_neurons(self):
        if not self.design.neurons or self.pan_active: return
        valid_positions = []
        for n in self.design.neurons.values():
            if n.position is not None:
                try:
                    x, y = n.position
                    if x is not None and y is not None:
                        valid_positions.append((x, y))
                except: continue
        
        if not valid_positions: return
        xs = [p[0] for p in valid_positions]
        ys = [p[1] for p in valid_positions]
        self.scene.setSceneRect(QRectF(
            min(xs) - 100, min(ys) - 100, 
            max(xs) - min(xs) + 200, max(ys) - min(ys) + 200
        ))

    def get_neuron_at(self, pos):
        for name, neuron in self.design.neurons.items():
            if neuron.position is None: continue
            x, y = neuron.position
            if math.hypot(pos.x() - x, pos.y() - y) <= self.NEURON_RADIUS + 5:
                return name
        return None
    
    def get_connection_at(self, pos):
        items = self.scene.items(pos)
        for item in items:
            if isinstance(item, SmartConnectionItem):
                return item
        return None

    # MOUSE EVENTS
    def mousePressEvent(self, event):
        self.setFocus()
        scene_pos = self.mapToScene(event.pos())
        
        if event.button() == Qt.RightButton or event.button() == Qt.MiddleButton:
            self.pan_active = True
            self.pan_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            clicked_neuron = self.get_neuron_at(scene_pos)
            if clicked_neuron:
                self.select_neuron(clicked_neuron)
                if event.modifiers() & Qt.ControlModifier:
                    self.dragging_neuron = clicked_neuron
                    self.neuron_drag_start_pos = scene_pos
                    event.accept()
                    return
                
                n_obj = self.design.get_neuron(clicked_neuron)
                if n_obj.neuron_type != NeuronType.OUTPUT:
                    self.start_connection_drag(clicked_neuron, scene_pos)
                event.accept()
                return

            conn_item = self.get_connection_at(scene_pos)
            if conn_item:
                conn_data = conn_item.data(0)
                self.select_connection(conn_data.source, conn_data.target)
                event.accept()
                return
            
            self.clear_selection()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            conn_item = self.get_connection_at(scene_pos)
            if conn_item:
                conn_data = conn_item.data(0)
                self.open_weight_dialog(conn_data.source, conn_data.target)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        
        if self.pan_active:
            delta = event.pos() - self.pan_start_pos
            self.pan_start_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        
        if self.dragging_neuron:
            delta = scene_pos - self.neuron_drag_start_pos
            neuron = self.design.get_neuron(self.dragging_neuron)
            if neuron:
                old_pos = neuron.position
                new_pos = (old_pos[0] + delta.x(), old_pos[1] + delta.y())
                neuron.position = new_pos
                self.neuron_drag_start_pos = scene_pos
                self.rebuild()
            event.accept()
            return
        
        if self.drag_line:
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
        if event.button() == Qt.RightButton or event.button() == Qt.MiddleButton:
            self.pan_active = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        
        if self.dragging_neuron:
            self.dragging_neuron = None
            self.neuron_drag_start_pos = None
            event.accept()
            return
        
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

    # KEY EVENTS
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            if self.selected_connection_key:
                self.design.remove_connection(*self.selected_connection_key)
                self.selected_connection_key = None
                self.rebuild()
                event.accept()
                return
        if event.key() == Qt.Key_Space:
            if self.selected_connection_key:
                self.reverse_selected_connection()
                event.accept()
                return
        if event.key() in [Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus, Qt.Key_Underscore]:
            self.adjust_connection_weight_by_key(event)
            event.accept()
            return
        if event.key() in [Qt.Key_PageUp, Qt.Key_PageDown]:
            self.adjust_connection_weight_page(event)
            event.accept()
            return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """
        Mouse wheel behavior:
        - If a connection is SELECTED (clicked), scroll changes its weight
        - Otherwise, scroll zooms the canvas
        """
        # Only adjust weight if a connection is explicitly selected (clicked)
        if self.selected_connection_key:
            conn = self.design.get_connection(*self.selected_connection_key)
            if conn:
                delta = event.angleDelta().y()
                step = self.WEIGHT_STEP_LARGE if event.modifiers() & Qt.ShiftModifier else self.WEIGHT_STEP
                change = step if delta > 0 else -step
                new_weight = max(-1.0, min(1.0, conn.weight + change))
                if abs(new_weight) < 0.03: new_weight = 0.0
                conn.weight = new_weight
                self.rebuild()
                self.weightChanged.emit(conn.source, conn.target, new_weight)
                QToolTip.showText(QCursor.pos(), f"Weight: {new_weight:+.2f}", self)
                event.accept()
                return
        
        # Default: zoom canvas
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom_level = max(0.2, min(3.0, self.zoom_level * factor))
        self.setTransform(QTransform().scale(self.zoom_level, self.zoom_level))
        event.accept()

    # SELECTION HELPERS
    def select_neuron(self, name):
        self.selected_neuron = name
        self.selected_connection_key = None
        self.neuronSelected.emit(name)
        self.rebuild()
    
    def select_connection(self, source, target):
        self.selected_connection_key = (source, target)
        self.selected_neuron = None
        self.connectionSelected.emit(source, target)
        self.rebuild()
    
    def clear_selection(self):
        self.selected_neuron = None
        self.selected_connection_key = None
        self.rebuild()

    def start_connection_drag(self, neuron_name, scene_pos):
        n_obj = self.design.get_neuron(neuron_name)
        self.drag_source_id = neuron_name
        self.drag_start_pos = QPointF(*n_obj.position)
        self.drag_line = QGraphicsLineItem(QLineF(self.drag_start_pos, scene_pos))
        self.drag_line.setPen(QPen(QColor(255, 215, 0), 3, Qt.DashLine))
        self.drag_line.setZValue(10)
        self.scene.addItem(self.drag_line)

    def is_valid_connection(self, src_name, tgt_name):
        src = self.design.get_neuron(src_name)
        tgt = self.design.get_neuron(tgt_name)
        if not src or not tgt: return False
        if tgt.neuron_type in [NeuronType.INPUT, NeuronType.SENSOR]: return False
        if src.neuron_type == NeuronType.OUTPUT: return False
        if self.design.get_connection(src_name, tgt_name): return False
        return True

    def reverse_selected_connection(self):
        if not self.selected_connection_key: return
        source, target = self.selected_connection_key
        conn = self.design.get_connection(source, target)
        if not conn: return
        src_neuron = self.design.get_neuron(source)
        tgt_neuron = self.design.get_neuron(target)
        if self.design.get_connection(target, source): return
        if src_neuron and src_neuron.neuron_type in [NeuronType.SENSOR, NeuronType.INPUT]: return
        if tgt_neuron and tgt_neuron.neuron_type == NeuronType.OUTPUT: return
        weight = conn.weight
        self.design.remove_connection(source, target)
        self.design.add_connection(target, source, weight)
        self.selected_connection_key = (target, source)
        self.connectionReversed.emit(source, target)
        self.rebuild()

    def open_weight_dialog(self, source, target):
        conn = self.design.get_connection(source, target)
        if not conn: return
        dialog = ConnectionWeightDialog(source, target, conn.weight, self.config, self)
        result = dialog.exec_()
        if dialog.delete_requested:
            self.design.remove_connection(source, target)
            self.selected_connection_key = None
            self.connectionDeleted.emit(source, target)
            self.rebuild()
            return
        if result == QDialog.Accepted:
            new_weight = dialog.get_weight()
            if new_weight != conn.weight:
                conn.weight = new_weight
                self.weightChanged.emit(source, target, new_weight)
                self.rebuild()

    def adjust_connection_weight_by_key(self, event):
        pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
        conn_item = self.get_connection_at(pos)
        if conn_item: conn = conn_item.data(0)
        elif self.selected_connection_key: conn = self.design.get_connection(*self.selected_connection_key)
        else: return
        if not conn: return
        step = self.WEIGHT_STEP_LARGE if event.modifiers() & Qt.ShiftModifier else self.WEIGHT_STEP
        if event.key() in [Qt.Key_Minus, Qt.Key_Underscore]: step = -step
        conn.weight = max(-1.0, min(1.0, conn.weight + step))
        self.rebuild()
        self.weightChanged.emit(conn.source, conn.target, conn.weight)
        QToolTip.showText(QCursor.pos(), f"Weight: {conn.weight:+.2f}", self)

    def adjust_connection_weight_page(self, event):
        pos = self.mapToScene(self.mapFromGlobal(QCursor.pos()))
        conn_item = self.get_connection_at(pos)
        if conn_item: conn = conn_item.data(0)
        elif self.selected_connection_key: conn = self.design.get_connection(*self.selected_connection_key)
        else: return
        if not conn: return
        step = self.WEIGHT_STEP_LARGE
        if event.key() == Qt.Key_PageDown: step = -step
        conn.weight = max(-1.0, min(1.0, conn.weight + step))
        self.rebuild()
        self.weightChanged.emit(conn.source, conn.target, conn.weight)
        QToolTip.showText(QCursor.pos(), f"Weight: {conn.weight:+.2f}", self)


class PolygonNeuronItem(QGraphicsItem):
    """
    Polygonal Neuron Body (Diamond, Square, Triangle).
    Acts as Parent item for Label (Ring is usually not used for these shapes in Designer).
    """
    
    def __init__(self, x, y, radius, name, sides=4, rotation=0, color=(150, 150, 220), parent=None):
        super().__init__(parent)
        self.name = name
        self.radius = radius
        self.sides = sides
        self.rotation_deg = rotation
        self.color = color
        self.is_selected = False
        self.is_hovered = False
        
        self.setPos(x, y)
        self.setAcceptHoverEvents(True)
        self.setData(0, ('neuron', name))
        self.setZValue(2)
        
    def boundingRect(self):
        extra = 5
        return QRectF(-self.radius - extra, -self.radius - extra,
                      (self.radius + extra) * 2, (self.radius + extra) * 2)
    
    def shape(self):
        path = QPainterPath()
        polygon = QPolygonF()
        angle_step = 360.0 / self.sides
        # Apply rotation offset
        offset_rad = math.radians(self.rotation_deg - 90)
        
        for i in range(self.sides):
            angle = math.radians(i * angle_step) + offset_rad
            polygon.append(QPointF(self.radius * math.cos(angle), 
                                   self.radius * math.sin(angle)))
        path.addPolygon(polygon)
        path.closeSubpath()
        return path

    def paint(self, painter, option, widget):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw hover glow
        if self.is_hovered and not self.is_selected:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(100, 200, 255, 150), 6))
            # Re-calculate polygon for glow path
            path = self.shape()
            painter.drawPath(path)

        # Draw Selection Highlight
        if self.is_selected:
            painter.setPen(QPen(QColor(255, 255, 255), 4))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(self.shape())

        # Draw Polygon Body
        painter.setBrush(QBrush(QColor(*self.color)))
        painter.setPen(QPen(QColor(50, 50, 50), 2))
        
        polygon = QPolygonF()
        angle_step = 360.0 / self.sides
        offset_rad = math.radians(self.rotation_deg - 90)
        
        for i in range(self.sides):
            angle = math.radians(i * angle_step) + offset_rad
            polygon.append(QPointF(self.radius * math.cos(angle), 
                                   self.radius * math.sin(angle)))
        
        painter.drawPolygon(polygon)
        painter.restore()
        
    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)