
import sys
import os
import json
import math
import random
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, QPointF, QRectF, pyqtSignal, QTimer
from PyQt5.QtGui import (QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
                         QLinearGradient, QRadialGradient, QFontMetrics)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QSplitter, QTreeWidget, QTreeWidgetItem,
                             QListWidget, QListWidgetItem, QPushButton, QLabel,
                             QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox,
                             QGroupBox, QFormLayout, QTabWidget, QTextEdit,
                             QFileDialog, QMessageBox, QDialog, QDialogButtonBox,
                             QSlider, QCheckBox, QScrollArea, QFrame, QToolBar,
                             QAction, QMenu, QStatusBar, QDockWidget, QColorDialog,
                             QInputDialog, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QToolButton, QSizePolicy)


# =============================================================================
# CORE NEURONS - MANDATORY FOR COMPATIBILITY
# =============================================================================

# These 7 neurons MUST exist in any brain design for it to work with Dosidicus
# Names (but not positions) must match brain_widget.py exactly.
CORE_NEURONS = {
    "hunger": (127, 81),
    "happiness": (361, 81),
    "cleanliness": (627, 81),
    "sleepiness": (840, 81),
    "satisfaction": (271, 380),
    "anxiety": (491, 389),
    "curiosity": (701, 386),
}

CORE_NEURON_NAMES = set(CORE_NEURONS.keys())


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class NeuronType(Enum):
    INPUT = "input"
    HIDDEN = "hidden"
    OUTPUT = "output"
    STATUS = "status"


@dataclass
class DesignerNeuron:
    """Represents a neuron in the designer."""
    name: str
    neuron_type: NeuronType
    position: Tuple[float, float]
    layer_index: int = 0
    color: Tuple[int, int, int] = (150, 150, 220)
    activation: float = 50.0
    description: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.neuron_type.value,
            'position': list(self.position),
            'layer_index': self.layer_index,
            'color': list(self.color),
            'activation': self.activation,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'DesignerNeuron':
        return cls(
            name=data['name'],
            neuron_type=NeuronType(data.get('type', 'hidden')),
            position=tuple(data.get('position', (0, 0))),
            layer_index=data.get('layer_index', 0),
            color=tuple(data.get('color', (150, 150, 220))),
            activation=data.get('activation', 50.0),
            description=data.get('description', '')
        )


@dataclass
class DesignerConnection:
    """Represents a connection between neurons."""
    source: str
    target: str
    weight: float = 0.1
    
    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'target': self.target,
            'weight': self.weight
        }


@dataclass
class DesignerLayer:
    """Represents a layer in the network."""
    name: str
    layer_type: NeuronType
    y_position: float
    color: Tuple[int, int, int] = (240, 240, 250)
    
    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'type': self.layer_type.value,
            'y_position': self.y_position,
            'color': list(self.color)
        }


class BrainDesign:
    """Container for the complete brain design."""
    
    def __init__(self):
        self.neurons: Dict[str, DesignerNeuron] = {}
        self.connections: Dict[Tuple[str, str], DesignerConnection] = {}
        self.layers: List[DesignerLayer] = []
        self.excluded_neurons: Set[str] = set()
        self.config = {
            'hebbian': {
                'base_learning_rate': 0.1,
                'learning_interval': 30000,
                'weight_decay': 0.01,
            },
            'neurogenesis': {
                'max_neurons': 50,
                'cooldown': 180,
            }
        }
        self.metadata = {
            'name': 'Untitled Brain',
            'author': '',
            'description': '',
            'version': '1.0'
        }
    
    def add_neuron(self, neuron: DesignerNeuron) -> bool:
        if neuron.name in self.neurons:
            return False
        self.neurons[neuron.name] = neuron
        return True
    
    def remove_neuron(self, name: str) -> Tuple[bool, str]:
        """
        Remove a neuron from the design.
        
        Returns:
            (success: bool, message: str) - False with message if core neuron
        """
        if name not in self.neurons:
            return False, f"Neuron '{name}' not found"
        
        # Prevent deletion of core neurons
        if name in CORE_NEURON_NAMES:
            return False, f"Cannot delete core neuron '{name}' - required for Dosidicus-2 compatibility"
        
        del self.neurons[name]
        # Remove associated connections
        to_remove = [(s, t) for s, t in self.connections.keys() 
                     if s == name or t == name]
        for key in to_remove:
            del self.connections[key]
        self.excluded_neurons.discard(name)
        return True, f"Neuron '{name}' removed"
    
    def is_core_neuron(self, name: str) -> bool:
        """Check if a neuron is a core neuron."""
        return name in CORE_NEURON_NAMES
    
    def get_missing_core_neurons(self) -> List[str]:
        """Return list of core neurons that are missing from the design."""
        return [name for name in CORE_NEURON_NAMES if name not in self.neurons]
    
    def has_all_core_neurons(self) -> bool:
        """Check if all 7 core neurons exist in the design."""
        return all(name in self.neurons for name in CORE_NEURON_NAMES)
    
    def add_missing_core_neurons(self) -> List[str]:
        """
        Add any missing core neurons to the design.
        Returns list of neurons that were added.
        """
        added = []
        for name, position in CORE_NEURONS.items():
            if name not in self.neurons:
                self.neurons[name] = DesignerNeuron(
                    name=name,
                    neuron_type=NeuronType.HIDDEN,
                    position=position,
                    color=(150, 150, 220),
                    description=f"Core neuron - required for Dosidicus-2"
                )
                added.append(name)
        return added
    
    def validate_for_export(self) -> Tuple[bool, List[str]]:
        """Validate that all 7 core neuron names exist (positions are flexible)"""
        issues = []
        
        # Check for missing core neuron NAMES only
        missing = self.get_missing_core_neurons()
        if missing:
            issues.append(f"Missing core neurons: {', '.join(missing)}")
        
        # Optional: friendly warning about neuron count
        total_neurons = len(self.neurons)
        if total_neurons < 10:
            issues.append(f"Warning: Only {total_neurons} neurons - consider adding more for interesting behavior")
        
        return len(issues) == 0, issues
    
    def add_connection(self, source: str, target: str, weight: float = 0.1) -> bool:
        if source not in self.neurons or target not in self.neurons:
            return False
        key = (source, target)
        self.connections[key] = DesignerConnection(source, target, weight)
        return True
    
    def remove_connection(self, source: str, target: str) -> bool:
        key = (source, target)
        if key not in self.connections:
            return False
        del self.connections[key]
        return True
    
    def add_layer(self, layer: DesignerLayer):
        self.layers.append(layer)
        self.layers.sort(key=lambda l: l.y_position)
    
    def to_dict(self) -> Dict:
        return {
            'metadata': self.metadata,
            'neurons': {n.name: n.to_dict() for n in self.neurons.values()},
            'connections': [c.to_dict() for c in self.connections.values()],
            'layers': [l.to_dict() for l in self.layers],
            'excluded_neurons': list(self.excluded_neurons),
            'config': self.config
        }
    
    def to_dosidicus_format(self) -> Dict:
        """Export in format compatible with NetworkAdapter."""
        return {
            'version': '2.0',
            'adapter_type': 'NetworkAdapter',
            'neurons': {
                name: {
                    'type': n.neuron_type.value,
                    'position': list(n.position),
                    'attributes': {
                        'color': list(n.color),
                        'description': n.description
                    }
                }
                for name, n in self.neurons.items()
            },
            'connections': {
                f"{c.source}->{c.target}": c.weight
                for c in self.connections.values()
            },
            'state': {name: n.activation for name, n in self.neurons.items()},
            'config': self.config,
            'layer_structure': [
                {
                    'name': layer.name,
                    'neuron_names': [n.name for n in self.neurons.values() 
                                    if n.layer_index == i],
                    'layer_type': layer.layer_type.value,
                    'y_position': layer.y_position
                }
                for i, layer in enumerate(self.layers)
            ],
            'excluded_neurons': list(self.excluded_neurons),
            'neurogenesis_data': {
                'new_neurons': [],
                'last_neuron_time': 0,
                'new_neurons_details': {}
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'BrainDesign':
        design = cls()
        design.metadata = data.get('metadata', design.metadata)
        design.config = data.get('config', design.config)
        design.excluded_neurons = set(data.get('excluded_neurons', []))
        
        for layer_data in data.get('layers', []):
            design.layers.append(DesignerLayer(
                name=layer_data['name'],
                layer_type=NeuronType(layer_data['type']),
                y_position=layer_data['y_position'],
                color=tuple(layer_data.get('color', (240, 240, 250)))
            ))
        
        for name, n_data in data.get('neurons', {}).items():
            design.neurons[name] = DesignerNeuron.from_dict(n_data)
        
        for c_data in data.get('connections', []):
            key = (c_data['source'], c_data['target'])
            design.connections[key] = DesignerConnection(
                c_data['source'], c_data['target'], c_data['weight']
            )
        
        return design


# =============================================================================
# CANVAS WIDGET - Main visualization and editing area
# =============================================================================

class BrainCanvas(QWidget):
    """Interactive canvas for visualizing and editing the brain design."""
    
    neuronSelected = pyqtSignal(str)  # Emitted when a neuron is selected
    connectionSelected = pyqtSignal(str, str)  # Emitted when connection selected
    designChanged = pyqtSignal()  # Emitted when design is modified
    
    # Visual constants
    NEURON_RADIUS = 30
    LAYER_HEIGHT = 40
    GRID_SIZE = 20
    
    # Colors
    COLORS = {
        NeuronType.INPUT: QColor(150, 220, 150),
        NeuronType.HIDDEN: QColor(150, 150, 220),
        NeuronType.OUTPUT: QColor(220, 150, 150),
        NeuronType.STATUS: QColor(180, 180, 180),
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.design = BrainDesign()
        
        # Interaction state
        self.selected_neuron: Optional[str] = None
        self.hovered_neuron: Optional[str] = None
        self.dragging_neuron: Optional[str] = None
        self.drag_offset = QPointF(0, 0)
        
        # Connection creation state
        self.creating_connection = False
        self.connection_start: Optional[str] = None
        self.connection_end_pos: Optional[QPointF] = None
        
        # View state
        self.pan_offset = QPointF(0, 0)
        self.zoom = 1.0
        self.panning = False
        self.last_pan_pos = QPointF()
        
        # Display options
        self.show_grid = True
        self.show_layers = True
        self.show_weights = True
        self.show_activation = True
        self.snap_to_grid = True
        
        # Animation
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.update)
        self.animation_timer.start(50)
        self.animation_phase = 0
        
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(600, 400)
    
    def set_design(self, design: BrainDesign):
        """Set the brain design to display/edit."""
        self.design = design
        self.selected_neuron = None
        self.update()
    
    def screen_to_world(self, pos: QPointF) -> QPointF:
        """Convert screen coordinates to world coordinates."""
        return (pos - self.pan_offset) / self.zoom
    
    def world_to_screen(self, pos: QPointF) -> QPointF:
        """Convert world coordinates to screen coordinates."""
        return pos * self.zoom + self.pan_offset
    
    def get_neuron_at_pos(self, world_pos: QPointF) -> Optional[str]:
        """Find neuron at given world position."""
        for name, neuron in self.design.neurons.items():
            nx, ny = neuron.position
            dist = math.sqrt((world_pos.x() - nx)**2 + (world_pos.y() - ny)**2)
            if dist <= self.NEURON_RADIUS:
                return name
        return None
    
    def get_connection_at_pos(self, world_pos: QPointF) -> Optional[Tuple[str, str]]:
        """Find connection near given world position."""
        for (source, target), conn in self.design.connections.items():
            if source not in self.design.neurons or target not in self.design.neurons:
                continue
            
            p1 = QPointF(*self.design.neurons[source].position)
            p2 = QPointF(*self.design.neurons[target].position)
            
            # Check distance from point to line segment
            line_vec = p2 - p1
            point_vec = world_pos - p1
            line_len = math.sqrt(line_vec.x()**2 + line_vec.y()**2)
            
            if line_len == 0:
                continue
            
            # Project point onto line
            t = max(0, min(1, (point_vec.x() * line_vec.x() + point_vec.y() * line_vec.y()) / (line_len**2)))
            projection = p1 + t * line_vec
            
            dist = math.sqrt((world_pos.x() - projection.x())**2 + (world_pos.y() - projection.y())**2)
            if dist < 10:
                return (source, target)
        
        return None
    
    def snap_position(self, pos: Tuple[float, float]) -> Tuple[float, float]:
        """Snap position to grid if enabled."""
        if not self.snap_to_grid:
            return pos
        x = round(pos[0] / self.GRID_SIZE) * self.GRID_SIZE
        y = round(pos[1] / self.GRID_SIZE) * self.GRID_SIZE
        return (x, y)
    
    # =========================================================================
    # PAINTING
    # =========================================================================
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Background
        painter.fillRect(self.rect(), QColor(250, 250, 255))
        
        # Apply view transform
        painter.translate(self.pan_offset)
        painter.scale(self.zoom, self.zoom)
        
        # Draw grid
        if self.show_grid:
            self.draw_grid(painter)
        
        # Draw layers
        if self.show_layers:
            self.draw_layers(painter)
        
        # Draw connections
        self.draw_connections(painter)
        
        # Draw connection being created
        if self.creating_connection and self.connection_start and self.connection_end_pos:
            self.draw_pending_connection(painter)
        
        # Draw neurons
        self.draw_neurons(painter)
        
        # Draw selection highlight
        if self.selected_neuron and self.selected_neuron in self.design.neurons:
            self.draw_selection(painter, self.selected_neuron)
        
        painter.end()
    
    def draw_grid(self, painter: QPainter):
        """Draw background grid."""
        painter.setPen(QPen(QColor(230, 230, 240), 1))
        
        # Calculate visible area
        visible_rect = QRectF(
            -self.pan_offset.x() / self.zoom,
            -self.pan_offset.y() / self.zoom,
            self.width() / self.zoom,
            self.height() / self.zoom
        )
        
        start_x = int(visible_rect.left() / self.GRID_SIZE) * self.GRID_SIZE
        start_y = int(visible_rect.top() / self.GRID_SIZE) * self.GRID_SIZE
        
        x = start_x
        while x < visible_rect.right():
            painter.drawLine(int(x), int(visible_rect.top()), 
                           int(x), int(visible_rect.bottom()))
            x += self.GRID_SIZE
        
        y = start_y
        while y < visible_rect.bottom():
            painter.drawLine(int(visible_rect.left()), int(y),
                           int(visible_rect.right()), int(y))
            y += self.GRID_SIZE
    
    def draw_layers(self, painter: QPainter):
        """Draw layer backgrounds."""
        for i, layer in enumerate(self.design.layers):
            # Calculate layer bounds
            y_start = layer.y_position - self.LAYER_HEIGHT
            y_end = layer.y_position + self.LAYER_HEIGHT + 60
            
            # Draw layer background
            color = QColor(*layer.color)
            color.setAlpha(80)
            painter.fillRect(QRectF(0, y_start, self.width() / self.zoom + 200, y_end - y_start), color)
            
            # Draw layer label
            painter.setPen(QPen(QColor(100, 100, 120), 1))
            font = QFont("Arial", 10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QPointF(10, y_start + 20), f"Layer {i}: {layer.name} ({layer.layer_type.value})")
    
    def draw_connections(self, painter: QPainter):
        """Draw all connections between neurons."""
        for (source, target), conn in self.design.connections.items():
            if source not in self.design.neurons or target not in self.design.neurons:
                continue
            
            p1 = QPointF(*self.design.neurons[source].position)
            p2 = QPointF(*self.design.neurons[target].position)
            
            # Color based on weight
            if conn.weight > 0:
                color = QColor(50, 180, 50, 180)
            else:
                color = QColor(220, 50, 50, 180)
            
            # Width based on weight magnitude
            width = max(1, min(6, abs(conn.weight) * 5))
            painter.setPen(QPen(color, width))
            
            # Draw line
            painter.drawLine(p1, p2)
            
            # Draw arrow
            self.draw_arrow(painter, p1, p2, color)
            
            # Draw weight label
            if self.show_weights:
                mid = (p1 + p2) / 2
                painter.setPen(QPen(Qt.black, 1))
                painter.setFont(QFont("Arial", 8))
                painter.drawText(mid + QPointF(5, -5), f"{conn.weight:.2f}")
    
    def draw_arrow(self, painter: QPainter, p1: QPointF, p2: QPointF, color: QColor):
        """Draw an arrowhead pointing to p2."""
        # Calculate direction
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0:
            return
        
        # Normalize
        dx /= length
        dy /= length
        
        # Arrow position (before the neuron circle)
        arrow_pos = p2 - QPointF(dx, dy) * self.NEURON_RADIUS
        
        # Arrow wings
        wing_length = 10
        wing_angle = 0.5
        
        left_wing = arrow_pos - QPointF(
            dx * wing_length - dy * wing_length * wing_angle,
            dy * wing_length + dx * wing_length * wing_angle
        )
        right_wing = arrow_pos - QPointF(
            dx * wing_length + dy * wing_length * wing_angle,
            dy * wing_length - dx * wing_length * wing_angle
        )
        
        # Draw arrow
        path = QPainterPath()
        path.moveTo(arrow_pos)
        path.lineTo(left_wing)
        path.moveTo(arrow_pos)
        path.lineTo(right_wing)
        
        painter.setPen(QPen(color, 2))
        painter.drawPath(path)
    
    def draw_pending_connection(self, painter: QPainter):
        """Draw connection being created."""
        if self.connection_start not in self.design.neurons:
            return
        
        p1 = QPointF(*self.design.neurons[self.connection_start].position)
        p2 = self.screen_to_world(self.connection_end_pos)
        
        painter.setPen(QPen(QColor(100, 100, 255, 150), 2, Qt.DashLine))
        painter.drawLine(p1, p2)
    
    def draw_neurons(self, painter: QPainter):
        """Draw all neurons."""
        for name, neuron in self.design.neurons.items():
            self.draw_neuron(painter, neuron, name == self.hovered_neuron)
    
    def draw_neuron(self, painter: QPainter, neuron: DesignerNeuron, hovered: bool = False):
        """Draw a single neuron."""
        pos = QPointF(*neuron.position)
        radius = self.NEURON_RADIUS
        is_core = self.design.is_core_neuron(neuron.name)
        
        if hovered:
            radius *= 1.1
        
        # Core neuron indicator - golden ring
        if is_core:
            painter.setPen(QPen(QColor(218, 165, 32), 3))  # Golden
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(pos, radius + 5, radius + 5)
        
        # Outer glow for selected/hovered
        if hovered or neuron.name == self.selected_neuron:
            glow_color = QColor(100, 150, 255, 100)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(glow_color))
            painter.drawEllipse(pos, radius + 8, radius + 8)
        
        # Main circle with gradient
        gradient = QRadialGradient(pos, radius)
        base_color = QColor(*neuron.color)
        gradient.setColorAt(0, base_color.lighter(130))
        gradient.setColorAt(1, base_color)
        
        painter.setPen(QPen(base_color.darker(120), 2))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(pos, radius, radius)
        
        # Activation indicator (fill level)
        if self.show_activation:
            activation_height = (neuron.activation / 100.0) * radius * 1.6
            clip_rect = QRectF(pos.x() - radius, pos.y() + radius - activation_height,
                              radius * 2, activation_height)
            
            painter.setClipRect(clip_rect)
            activation_color = QColor(255, 255, 100, 100)
            painter.setBrush(QBrush(activation_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(pos, radius - 2, radius - 2)
            painter.setClipping(False)
        
        # Neuron name
        painter.setPen(QPen(Qt.black, 1))
        font = QFont("Arial", 9)
        font.setBold(True)
        painter.setFont(font)
        
        # Center text - add star for core neurons
        display_name = f"⭐{neuron.name}" if is_core else neuron.name
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(display_name)
        text_pos = pos + QPointF(-text_width/2, radius + 18)
        painter.drawText(text_pos, display_name)
        
        # Type indicator
        type_char = neuron.neuron_type.value[0].upper()
        painter.setFont(QFont("Arial", 8))
        painter.drawText(pos + QPointF(-4, 4), type_char)
        
        # Excluded indicator
        if neuron.name in self.design.excluded_neurons:
            painter.setPen(QPen(QColor(255, 100, 100), 2))
            painter.drawLine(pos + QPointF(-radius, -radius), 
                           pos + QPointF(radius, radius))
    
    def draw_selection(self, painter: QPainter, neuron_name: str):
        """Draw selection highlight around neuron."""
        if neuron_name not in self.design.neurons:
            return
        
        neuron = self.design.neurons[neuron_name]
        pos = QPointF(*neuron.position)
        
        # Animated selection ring
        self.animation_phase = (self.animation_phase + 0.1) % (2 * math.pi)
        
        painter.setPen(QPen(QColor(50, 100, 255), 3, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        
        # Rotate dash pattern
        pen = painter.pen()
        pen.setDashOffset(self.animation_phase * 5)
        painter.setPen(pen)
        
        painter.drawEllipse(pos, self.NEURON_RADIUS + 5, self.NEURON_RADIUS + 5)
    
    # =========================================================================
    # MOUSE HANDLING
    # =========================================================================
    
    def mousePressEvent(self, event):
        world_pos = self.screen_to_world(QPointF(event.pos()))
        
        if event.button() == Qt.LeftButton:
            # Check if clicking on neuron
            neuron_name = self.get_neuron_at_pos(world_pos)
            
            if neuron_name:
                if event.modifiers() & Qt.ShiftModifier:
                    # Start creating connection
                    self.creating_connection = True
                    self.connection_start = neuron_name
                    self.connection_end_pos = QPointF(event.pos())
                else:
                    # Start dragging or select
                    self.selected_neuron = neuron_name
                    self.dragging_neuron = neuron_name
                    neuron = self.design.neurons[neuron_name]
                    self.drag_offset = QPointF(*neuron.position) - world_pos
                    self.neuronSelected.emit(neuron_name)
            else:
                # Click on empty space - deselect
                self.selected_neuron = None
            
            self.update()
        
        elif event.button() == Qt.RightButton:
            # Start panning
            self.panning = True
            self.last_pan_pos = QPointF(event.pos())
        
        elif event.button() == Qt.MiddleButton:
            # Check for connection to select/delete
            conn = self.get_connection_at_pos(world_pos)
            if conn:
                self.connectionSelected.emit(conn[0], conn[1])
    
    def mouseMoveEvent(self, event):
        world_pos = self.screen_to_world(QPointF(event.pos()))
        
        # Update hover state
        self.hovered_neuron = self.get_neuron_at_pos(world_pos)
        
        if self.dragging_neuron:
            # Move neuron
            new_pos = world_pos + self.drag_offset
            snapped = self.snap_position((new_pos.x(), new_pos.y()))
            self.design.neurons[self.dragging_neuron].position = snapped
            self.designChanged.emit()
        
        elif self.creating_connection:
            # Update connection endpoint
            self.connection_end_pos = QPointF(event.pos())
        
        elif self.panning:
            # Pan view
            delta = QPointF(event.pos()) - self.last_pan_pos
            self.pan_offset += delta
            self.last_pan_pos = QPointF(event.pos())
        
        self.update()
    
    def mouseReleaseEvent(self, event):
        world_pos = self.screen_to_world(QPointF(event.pos()))
        
        if event.button() == Qt.LeftButton:
            if self.creating_connection and self.connection_start:
                # Finish connection creation
                target = self.get_neuron_at_pos(world_pos)
                if target and target != self.connection_start:
                    self.design.add_connection(self.connection_start, target, 0.1)
                    self.designChanged.emit()
                
                self.creating_connection = False
                self.connection_start = None
                self.connection_end_pos = None
            
            self.dragging_neuron = None
        
        elif event.button() == Qt.RightButton:
            self.panning = False
        
        self.update()
    
    def mouseDoubleClickEvent(self, event):
        """Double-click to add neuron or edit connection."""
        world_pos = self.screen_to_world(QPointF(event.pos()))
        
        # Check if double-clicking a neuron
        neuron_name = self.get_neuron_at_pos(world_pos)
        if neuron_name:
            self.neuronSelected.emit(neuron_name)
            return
        
        # Check if double-clicking a connection
        conn = self.get_connection_at_pos(world_pos)
        if conn:
            self.connectionSelected.emit(conn[0], conn[1])
            return
        
        # Double-click on empty space - add neuron
        snapped = self.snap_position((world_pos.x(), world_pos.y()))
        self.add_neuron_at_position(snapped)
    
    def wheelEvent(self, event):
        """Zoom with mouse wheel."""
        delta = event.angleDelta().y()
        
        # Zoom factor
        factor = 1.1 if delta > 0 else 0.9
        new_zoom = self.zoom * factor
        
        # Clamp zoom
        new_zoom = max(0.25, min(4.0, new_zoom))
        
        # Zoom toward cursor
        cursor_pos = QPointF(event.pos())
        world_pos = self.screen_to_world(cursor_pos)
        
        self.zoom = new_zoom
        
        # Adjust pan to keep cursor position fixed
        new_screen_pos = self.world_to_screen(world_pos)
        self.pan_offset += cursor_pos - new_screen_pos
        
        self.update()
    
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Delete and self.selected_neuron:
            success, message = self.design.remove_neuron(self.selected_neuron)
            if success:
                self.selected_neuron = None
                self.designChanged.emit()
                self.update()
            else:
                # Show message for protected core neurons
                from PyQt5.QtWidgets import QToolTip
                QToolTip.showText(
                    self.mapToGlobal(self.rect().center()),
                    message,
                    self,
                    self.rect(),
                    2000
                )
        
        elif event.key() == Qt.Key_G:
            self.show_grid = not self.show_grid
            self.update()
        
        elif event.key() == Qt.Key_L:
            self.show_layers = not self.show_layers
            self.update()
        
        elif event.key() == Qt.Key_W:
            self.show_weights = not self.show_weights
            self.update()
        
        elif event.key() == Qt.Key_Home:
            self.pan_offset = QPointF(50, 50)
            self.zoom = 1.0
            self.update()
    
    def add_neuron_at_position(self, position: Tuple[float, float]):
        """Add a new neuron at the given position."""
        # Generate unique name
        base_name = "neuron"
        idx = len(self.design.neurons)
        while f"{base_name}_{idx}" in self.design.neurons:
            idx += 1
        name = f"{base_name}_{idx}"
        
        # Determine layer based on y position
        layer_idx = 0
        for i, layer in enumerate(self.design.layers):
            if position[1] >= layer.y_position - self.LAYER_HEIGHT:
                layer_idx = i
        
        # Determine type from layer
        neuron_type = NeuronType.HIDDEN
        if self.design.layers:
            neuron_type = self.design.layers[layer_idx].layer_type
        
        neuron = DesignerNeuron(
            name=name,
            neuron_type=neuron_type,
            position=position,
            layer_index=layer_idx,
            color=self.COLORS[neuron_type].getRgb()[:3]
        )
        
        self.design.add_neuron(neuron)
        self.selected_neuron = name
        self.neuronSelected.emit(name)
        self.designChanged.emit()
        self.update()


# =============================================================================
# PROPERTY PANELS
# =============================================================================

class NeuronPropertiesPanel(QWidget):
    """Panel for editing selected neuron properties."""
    
    propertiesChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.design: Optional[BrainDesign] = None
        self.current_neuron: Optional[str] = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        self.title_label = QLabel("Neuron Properties")
        self.title_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.title_label)
        
        # Form
        form_layout = QFormLayout()
        
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self.on_name_changed)
        form_layout.addRow("Name:", self.name_edit)
        
        self.type_combo = QComboBox()
        for nt in NeuronType:
            self.type_combo.addItem(nt.value, nt)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        form_layout.addRow("Type:", self.type_combo)
        
        self.layer_spin = QSpinBox()
        self.layer_spin.setRange(0, 10)
        self.layer_spin.valueChanged.connect(self.on_layer_changed)
        form_layout.addRow("Layer:", self.layer_spin)
        
        self.activation_spin = QDoubleSpinBox()
        self.activation_spin.setRange(0, 100)
        self.activation_spin.setValue(50)
        self.activation_spin.valueChanged.connect(self.on_activation_changed)
        form_layout.addRow("Activation:", self.activation_spin)
        
        self.pos_x_spin = QDoubleSpinBox()
        self.pos_x_spin.setRange(-10000, 10000)
        self.pos_x_spin.valueChanged.connect(self.on_position_changed)
        form_layout.addRow("X Position:", self.pos_x_spin)
        
        self.pos_y_spin = QDoubleSpinBox()
        self.pos_y_spin.setRange(-10000, 10000)
        self.pos_y_spin.valueChanged.connect(self.on_position_changed)
        form_layout.addRow("Y Position:", self.pos_y_spin)
        
        self.excluded_check = QCheckBox("Excluded from Learning")
        self.excluded_check.stateChanged.connect(self.on_excluded_changed)
        form_layout.addRow("", self.excluded_check)
        
        layout.addLayout(form_layout)
        
        # Color picker
        color_layout = QHBoxLayout()
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(30, 30)
        self.color_preview.setStyleSheet("background-color: rgb(150, 150, 220); border: 1px solid black;")
        color_layout.addWidget(QLabel("Color:"))
        color_layout.addWidget(self.color_preview)
        
        self.color_btn = QPushButton("Choose...")
        self.color_btn.clicked.connect(self.on_choose_color)
        color_layout.addWidget(self.color_btn)
        color_layout.addStretch()
        layout.addLayout(color_layout)
        
        # Description
        layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.textChanged.connect(self.on_description_changed)
        layout.addWidget(self.description_edit)
        
        # Delete button
        self.delete_btn = QPushButton("Delete Neuron")
        self.delete_btn.setStyleSheet("background-color: #ffcccc;")
        self.delete_btn.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.delete_btn)
        
        layout.addStretch()
        
        self.set_enabled(False)
    
    def set_enabled(self, enabled: bool):
        """Enable/disable all controls."""
        self.name_edit.setEnabled(enabled)
        self.type_combo.setEnabled(enabled)
        self.layer_spin.setEnabled(enabled)
        self.activation_spin.setEnabled(enabled)
        self.pos_x_spin.setEnabled(enabled)
        self.pos_y_spin.setEnabled(enabled)
        self.excluded_check.setEnabled(enabled)
        self.color_btn.setEnabled(enabled)
        self.description_edit.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)
    
    def set_design(self, design: BrainDesign):
        self.design = design
    
    def set_neuron(self, neuron_name: Optional[str]):
        self.current_neuron = neuron_name
        
        if not neuron_name or not self.design or neuron_name not in self.design.neurons:
            self.set_enabled(False)
            self.title_label.setText("Neuron Properties")
            return
        
        self.set_enabled(True)
        neuron = self.design.neurons[neuron_name]
        
        # Check if this is a core neuron
        is_core = self.design.is_core_neuron(neuron_name)
        
        # Update title with core indicator
        if is_core:
            self.title_label.setText(f"Neuron: {neuron_name} ⭐ (Core)")
        else:
            self.title_label.setText(f"Neuron: {neuron_name}")
        
        # Disable delete button for core neurons
        self.delete_btn.setEnabled(not is_core)
        if is_core:
            self.delete_btn.setToolTip("Core neurons cannot be deleted - required for Dosidicus-2")
            self.delete_btn.setStyleSheet("background-color: #dddddd;")
        else:
            self.delete_btn.setToolTip("Delete this neuron")
            self.delete_btn.setStyleSheet("background-color: #ffcccc;")
        
        # Disable name editing for core neurons (names must match exactly)
        self.name_edit.setEnabled(not is_core)
        if is_core:
            self.name_edit.setToolTip("Core neuron names cannot be changed")
        else:
            self.name_edit.setToolTip("")
        
        # Block signals while updating
        self.name_edit.blockSignals(True)
        self.type_combo.blockSignals(True)
        self.layer_spin.blockSignals(True)
        self.activation_spin.blockSignals(True)
        self.pos_x_spin.blockSignals(True)
        self.pos_y_spin.blockSignals(True)
        self.excluded_check.blockSignals(True)
        self.description_edit.blockSignals(True)
        
        self.name_edit.setText(neuron.name)
        self.type_combo.setCurrentIndex(self.type_combo.findData(neuron.neuron_type))
        self.layer_spin.setValue(neuron.layer_index)
        self.activation_spin.setValue(neuron.activation)
        self.pos_x_spin.setValue(neuron.position[0])
        self.pos_y_spin.setValue(neuron.position[1])
        self.excluded_check.setChecked(neuron.name in self.design.excluded_neurons)
        self.description_edit.setPlainText(neuron.description)
        
        # Update color preview
        r, g, b = neuron.color
        self.color_preview.setStyleSheet(f"background-color: rgb({r}, {g}, {b}); border: 1px solid black;")
        
        self.name_edit.blockSignals(False)
        self.type_combo.blockSignals(False)
        self.layer_spin.blockSignals(False)
        self.activation_spin.blockSignals(False)
        self.pos_x_spin.blockSignals(False)
        self.pos_y_spin.blockSignals(False)
        self.excluded_check.blockSignals(False)
        self.description_edit.blockSignals(False)
    
    def on_name_changed(self):
        if not self.current_neuron or not self.design:
            return
        
        new_name = self.name_edit.text().strip()
        if not new_name or new_name == self.current_neuron:
            return
        
        if new_name in self.design.neurons:
            QMessageBox.warning(self, "Error", "A neuron with this name already exists.")
            self.name_edit.setText(self.current_neuron)
            return
        
        # Rename neuron
        neuron = self.design.neurons.pop(self.current_neuron)
        neuron.name = new_name
        self.design.neurons[new_name] = neuron
        
        # Update connections
        for key in list(self.design.connections.keys()):
            conn = self.design.connections[key]
            if conn.source == self.current_neuron:
                conn.source = new_name
            if conn.target == self.current_neuron:
                conn.target = new_name
            
            if key[0] == self.current_neuron or key[1] == self.current_neuron:
                del self.design.connections[key]
                new_key = (conn.source, conn.target)
                self.design.connections[new_key] = conn
        
        # Update excluded
        if self.current_neuron in self.design.excluded_neurons:
            self.design.excluded_neurons.remove(self.current_neuron)
            self.design.excluded_neurons.add(new_name)
        
        self.current_neuron = new_name
        self.title_label.setText(f"Neuron: {new_name}")
        self.propertiesChanged.emit()
    
    def on_type_changed(self):
        if not self.current_neuron or not self.design:
            return
        neuron = self.design.neurons[self.current_neuron]
        neuron.neuron_type = self.type_combo.currentData()
        self.propertiesChanged.emit()
    
    def on_layer_changed(self):
        if not self.current_neuron or not self.design:
            return
        neuron = self.design.neurons[self.current_neuron]
        neuron.layer_index = self.layer_spin.value()
        self.propertiesChanged.emit()
    
    def on_activation_changed(self):
        if not self.current_neuron or not self.design:
            return
        neuron = self.design.neurons[self.current_neuron]
        neuron.activation = self.activation_spin.value()
        self.propertiesChanged.emit()
    
    def on_position_changed(self):
        if not self.current_neuron or not self.design:
            return
        neuron = self.design.neurons[self.current_neuron]
        neuron.position = (self.pos_x_spin.value(), self.pos_y_spin.value())
        self.propertiesChanged.emit()
    
    def on_excluded_changed(self):
        if not self.current_neuron or not self.design:
            return
        if self.excluded_check.isChecked():
            self.design.excluded_neurons.add(self.current_neuron)
        else:
            self.design.excluded_neurons.discard(self.current_neuron)
        self.propertiesChanged.emit()
    
    def on_choose_color(self):
        if not self.current_neuron or not self.design:
            return
        neuron = self.design.neurons[self.current_neuron]
        color = QColorDialog.getColor(QColor(*neuron.color), self)
        if color.isValid():
            neuron.color = (color.red(), color.green(), color.blue())
            self.color_preview.setStyleSheet(
                f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); border: 1px solid black;"
            )
            self.propertiesChanged.emit()
    
    def on_description_changed(self):
        if not self.current_neuron or not self.design:
            return
        neuron = self.design.neurons[self.current_neuron]
        neuron.description = self.description_edit.toPlainText()
    
    def on_delete_clicked(self):
        if not self.current_neuron or not self.design:
            return
        
        # Double-check for core neuron (shouldn't reach here due to disabled button)
        if self.design.is_core_neuron(self.current_neuron):
            QMessageBox.warning(
                self, "Cannot Delete",
                f"'{self.current_neuron}' is a core neuron required for Dosidicus-2 compatibility."
            )
            return
        
        reply = QMessageBox.question(
            self, "Delete Neuron",
            f"Delete neuron '{self.current_neuron}' and all its connections?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            success, message = self.design.remove_neuron(self.current_neuron)
            if success:
                self.current_neuron = None
                self.set_enabled(False)
                self.propertiesChanged.emit()
            else:
                QMessageBox.warning(self, "Cannot Delete", message)


class ConnectionPropertiesPanel(QWidget):
    """Panel for editing connections."""
    
    propertiesChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.design: Optional[BrainDesign] = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Connections"))
        
        # Connection table
        self.conn_table = QTableWidget()
        self.conn_table.setColumnCount(4)
        self.conn_table.setHorizontalHeaderLabels(["Source", "Target", "Weight", ""])
        self.conn_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.conn_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.conn_table.setColumnWidth(3, 60)
        self.conn_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.conn_table)
        
        # Add connection controls
        add_group = QGroupBox("Add Connection")
        add_layout = QFormLayout(add_group)
        
        self.source_combo = QComboBox()
        add_layout.addRow("Source:", self.source_combo)
        
        self.target_combo = QComboBox()
        add_layout.addRow("Target:", self.target_combo)
        
        self.weight_spin = QDoubleSpinBox()
        self.weight_spin.setRange(-1.0, 1.0)
        self.weight_spin.setSingleStep(0.05)
        self.weight_spin.setValue(0.1)
        add_layout.addRow("Weight:", self.weight_spin)
        
        self.add_conn_btn = QPushButton("Add Connection")
        self.add_conn_btn.clicked.connect(self.on_add_connection)
        add_layout.addRow("", self.add_conn_btn)
        
        layout.addWidget(add_group)
        
        # Bulk operations
        bulk_layout = QHBoxLayout()
        
        self.connect_all_btn = QPushButton("Connect All Layers")
        self.connect_all_btn.clicked.connect(self.on_connect_all_layers)
        bulk_layout.addWidget(self.connect_all_btn)
        
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.on_clear_all)
        bulk_layout.addWidget(self.clear_all_btn)
        
        layout.addLayout(bulk_layout)
    
    def set_design(self, design: BrainDesign):
        self.design = design
        self.refresh()
    
    def refresh(self):
        if not self.design:
            return
        
        # Update combo boxes
        self.source_combo.clear()
        self.target_combo.clear()
        for name in sorted(self.design.neurons.keys()):
            self.source_combo.addItem(name)
            self.target_combo.addItem(name)
        
        # Update table
        self.conn_table.setRowCount(len(self.design.connections))
        
        for row, ((source, target), conn) in enumerate(self.design.connections.items()):
            self.conn_table.setItem(row, 0, QTableWidgetItem(source))
            self.conn_table.setItem(row, 1, QTableWidgetItem(target))
            
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(-1.0, 1.0)
            weight_spin.setSingleStep(0.05)
            weight_spin.setValue(conn.weight)
            weight_spin.valueChanged.connect(lambda v, s=source, t=target: self.on_weight_changed(s, t, v))
            self.conn_table.setCellWidget(row, 2, weight_spin)
            
            delete_btn = QPushButton("X")
            delete_btn.setFixedWidth(40)
            delete_btn.clicked.connect(lambda _, s=source, t=target: self.on_delete_connection(s, t))
            self.conn_table.setCellWidget(row, 3, delete_btn)
    
    def on_weight_changed(self, source: str, target: str, value: float):
        if not self.design:
            return
        key = (source, target)
        if key in self.design.connections:
            self.design.connections[key].weight = value
            self.propertiesChanged.emit()
    
    def on_delete_connection(self, source: str, target: str):
        if not self.design:
            return
        self.design.remove_connection(source, target)
        self.refresh()
        self.propertiesChanged.emit()
    
    def on_add_connection(self):
        if not self.design:
            return
        
        source = self.source_combo.currentText()
        target = self.target_combo.currentText()
        weight = self.weight_spin.value()
        
        if source and target and source != target:
            if (source, target) not in self.design.connections:
                self.design.add_connection(source, target, weight)
                self.refresh()
                self.propertiesChanged.emit()
    
    def on_connect_all_layers(self):
        """Create connections between adjacent layers."""
        if not self.design or not self.design.layers:
            return
        
        # Group neurons by layer
        layers = {}
        for name, neuron in self.design.neurons.items():
            if neuron.layer_index not in layers:
                layers[neuron.layer_index] = []
            layers[neuron.layer_index].append(name)
        
        # Connect adjacent layers
        layer_indices = sorted(layers.keys())
        for i in range(len(layer_indices) - 1):
            source_layer = layers[layer_indices[i]]
            target_layer = layers[layer_indices[i + 1]]
            
            for source in source_layer:
                for target in target_layer:
                    if (source, target) not in self.design.connections:
                        weight = random.uniform(-0.3, 0.3)
                        self.design.add_connection(source, target, weight)
        
        self.refresh()
        self.propertiesChanged.emit()
    
    def on_clear_all(self):
        if not self.design:
            return
        
        reply = QMessageBox.question(
            self, "Clear Connections",
            "Delete ALL connections?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.design.connections.clear()
            self.refresh()
            self.propertiesChanged.emit()


# =============================================================================
# LAYER MANAGEMENT
# =============================================================================

class LayerManagerPanel(QWidget):
    """Panel for managing layers."""
    
    layersChanged = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.design: Optional[BrainDesign] = None
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Layers"))
        
        # Layer list
        self.layer_list = QListWidget()
        self.layer_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.layer_list.currentRowChanged.connect(self.on_layer_selected)
        layout.addWidget(self.layer_list)
        
        # Layer controls
        btn_layout = QHBoxLayout()
        
        self.add_layer_btn = QPushButton("+")
        self.add_layer_btn.setFixedWidth(40)
        self.add_layer_btn.clicked.connect(self.on_add_layer)
        btn_layout.addWidget(self.add_layer_btn)
        
        self.remove_layer_btn = QPushButton("-")
        self.remove_layer_btn.setFixedWidth(40)
        self.remove_layer_btn.clicked.connect(self.on_remove_layer)
        btn_layout.addWidget(self.remove_layer_btn)
        
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        
        # Layer properties
        props_group = QGroupBox("Layer Properties")
        props_layout = QFormLayout(props_group)
        
        self.layer_name_edit = QLineEdit()
        self.layer_name_edit.editingFinished.connect(self.on_layer_name_changed)
        props_layout.addRow("Name:", self.layer_name_edit)
        
        self.layer_type_combo = QComboBox()
        for nt in [NeuronType.INPUT, NeuronType.HIDDEN, NeuronType.OUTPUT]:
            self.layer_type_combo.addItem(nt.value, nt)
        self.layer_type_combo.currentIndexChanged.connect(self.on_layer_type_changed)
        props_layout.addRow("Type:", self.layer_type_combo)
        
        self.layer_y_spin = QDoubleSpinBox()
        self.layer_y_spin.setRange(0, 2000)
        self.layer_y_spin.valueChanged.connect(self.on_layer_y_changed)
        props_layout.addRow("Y Position:", self.layer_y_spin)
        
        layout.addWidget(props_group)
        
        # Presets
        preset_group = QGroupBox("Quick Presets")
        preset_layout = QVBoxLayout(preset_group)
        
        self.preset_3layer_btn = QPushButton("3-Layer (I-H-O)")
        self.preset_3layer_btn.clicked.connect(lambda: self.apply_preset(3))
        preset_layout.addWidget(self.preset_3layer_btn)
        
        self.preset_4layer_btn = QPushButton("4-Layer (I-H-H-O)")
        self.preset_4layer_btn.clicked.connect(lambda: self.apply_preset(4))
        preset_layout.addWidget(self.preset_4layer_btn)
        
        self.preset_5layer_btn = QPushButton("5-Layer Deep")
        self.preset_5layer_btn.clicked.connect(lambda: self.apply_preset(5))
        preset_layout.addWidget(self.preset_5layer_btn)
        
        layout.addWidget(preset_group)
    
    def set_design(self, design: BrainDesign):
        self.design = design
        self.refresh()
    
    def refresh(self):
        if not self.design:
            return
        
        self.layer_list.clear()
        for i, layer in enumerate(self.design.layers):
            item = QListWidgetItem(f"{i}: {layer.name} ({layer.layer_type.value})")
            self.layer_list.addItem(item)
    
    def on_layer_selected(self, row: int):
        if not self.design or row < 0 or row >= len(self.design.layers):
            return
        
        layer = self.design.layers[row]
        
        self.layer_name_edit.blockSignals(True)
        self.layer_type_combo.blockSignals(True)
        self.layer_y_spin.blockSignals(True)
        
        self.layer_name_edit.setText(layer.name)
        self.layer_type_combo.setCurrentIndex(self.layer_type_combo.findData(layer.layer_type))
        self.layer_y_spin.setValue(layer.y_position)
        
        self.layer_name_edit.blockSignals(False)
        self.layer_type_combo.blockSignals(False)
        self.layer_y_spin.blockSignals(False)
    
    def on_add_layer(self):
        if not self.design:
            return
        
        # Calculate Y position
        if self.design.layers:
            y = self.design.layers[-1].y_position + 150
        else:
            y = 100
        
        idx = len(self.design.layers)
        layer = DesignerLayer(
            name=f"Layer_{idx}",
            layer_type=NeuronType.HIDDEN,
            y_position=y
        )
        self.design.add_layer(layer)
        self.refresh()
        self.layersChanged.emit()
    
    def on_remove_layer(self):
        if not self.design:
            return
        
        row = self.layer_list.currentRow()
        if row >= 0 and row < len(self.design.layers):
            del self.design.layers[row]
            self.refresh()
            self.layersChanged.emit()
    
    def on_layer_name_changed(self):
        if not self.design:
            return
        row = self.layer_list.currentRow()
        if row >= 0 and row < len(self.design.layers):
            self.design.layers[row].name = self.layer_name_edit.text()
            self.refresh()
            self.layersChanged.emit()
    
    def on_layer_type_changed(self):
        if not self.design:
            return
        row = self.layer_list.currentRow()
        if row >= 0 and row < len(self.design.layers):
            self.design.layers[row].layer_type = self.layer_type_combo.currentData()
            self.refresh()
            self.layersChanged.emit()
    
    def on_layer_y_changed(self):
        if not self.design:
            return
        row = self.layer_list.currentRow()
        if row >= 0 and row < len(self.design.layers):
            self.design.layers[row].y_position = self.layer_y_spin.value()
            self.design.layers.sort(key=lambda l: l.y_position)
            self.refresh()
            self.layersChanged.emit()
    
    def apply_preset(self, num_layers: int):
        if not self.design:
            return
        
        self.design.layers.clear()
        
        y_spacing = 150
        y_start = 80
        
        if num_layers == 3:
            self.design.layers = [
                DesignerLayer("Input", NeuronType.INPUT, y_start),
                DesignerLayer("Hidden", NeuronType.HIDDEN, y_start + y_spacing),
                DesignerLayer("Output", NeuronType.OUTPUT, y_start + y_spacing * 2),
            ]
        elif num_layers == 4:
            self.design.layers = [
                DesignerLayer("Input", NeuronType.INPUT, y_start),
                DesignerLayer("Hidden_1", NeuronType.HIDDEN, y_start + y_spacing),
                DesignerLayer("Hidden_2", NeuronType.HIDDEN, y_start + y_spacing * 2),
                DesignerLayer("Output", NeuronType.OUTPUT, y_start + y_spacing * 3),
            ]
        elif num_layers == 5:
            self.design.layers = [
                DesignerLayer("Input", NeuronType.INPUT, y_start),
                DesignerLayer("Hidden_1", NeuronType.HIDDEN, y_start + y_spacing),
                DesignerLayer("Hidden_2", NeuronType.HIDDEN, y_start + y_spacing * 2),
                DesignerLayer("Hidden_3", NeuronType.HIDDEN, y_start + y_spacing * 3),
                DesignerLayer("Output", NeuronType.OUTPUT, y_start + y_spacing * 4),
            ]
        
        self.refresh()
        self.layersChanged.emit()


# =============================================================================
# TEMPLATE LIBRARY
# =============================================================================

class TemplateLibraryPanel(QWidget):
    """Panel for template selection and management."""
    
    templateSelected = pyqtSignal(str)
    
    TEMPLATES = {
        # ✅ COMPATIBLE TEMPLATES
        'dosidicus_default': {
            'name': '⭐ Dosidicus Default',
            'description': 'Standard flat network - 7 core neurons at original positions',
            'has_core_neurons': True,
        },
        'core_only': {
            'name': '⭐ Core Only', 
            'description': 'Blank slate with just the 7 core neurons - build from scratch',
            'has_core_neurons': True,
        },
        'layered_dosidicus': {
            'name': '⭐ Layered Dosidicus',
            'description': 'Core neurons reorganized into Input→Hidden→Output layers + external stimulus',
            'has_core_neurons': True,
        },
        'sensory_enhanced': {
            'name': '⭐ Sensory Enhanced',
            'description': 'Core + environmental sensors (food proximity, threat detection, etc.)',
            'has_core_neurons': True,
        },
        'cognitive_complex': {
            'name': '⭐ Cognitive Complex', 
            'description': 'Deep 4-layer network with memory & prediction processors',
            'has_core_neurons': True,
        },
    }
    
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Template Library"))
        
        # Template list
        self.template_list = QListWidget()
        self.template_list.setAlternatingRowColors(True)  # Enable alternating colors
        self.template_list.setStyleSheet("""
            QListWidget {
                alternate-background-color: #F5F5F5;
                background-color: white;
            }
            QListWidget::item {
                padding: 5px;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #E0E0E0;
                color: black;
            }
        """)
        
        for key, info in self.TEMPLATES.items():
            item = QListWidgetItem(f"{info['name']}\n  {info['description']}")
            item.setData(Qt.UserRole, key)
            self.template_list.addItem(item)
        layout.addWidget(self.template_list)
        
        # Load button
        self.load_btn = QPushButton("Load Template")
        self.load_btn.clicked.connect(self.on_load_template)
        layout.addWidget(self.load_btn)
        
        # Info
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        self.template_list.currentRowChanged.connect(self.on_selection_changed)
    
    def on_selection_changed(self, row: int):
        item = self.template_list.item(row)
        if item:
            key = item.data(Qt.UserRole)
            info = self.TEMPLATES.get(key, {})
            has_core = info.get('has_core_neurons', False)
            compat_text = "✓ Has all core neurons" if has_core else "⚠️ Missing core neurons - will need to be added"
            self.info_label.setText(
                f"Neurons: {info.get('neurons', '?')}\n"
                f"Layers: {info.get('layers', '?')}\n"
                f"{compat_text}"
            )
            self.info_label.setText(
                f"Neurons: {info.get('neurons', '?')}\n"
                f"Layers: {info.get('layers', '?')}"
            )
    
    def on_load_template(self):
        item = self.template_list.currentItem()
        if item:
            key = item.data(Qt.UserRole)
            self.templateSelected.emit(key)


# =============================================================================
# EXPORT DIALOG
# =============================================================================

class ExportDialog(QDialog):
    """Dialog for exporting the brain design."""
    
    def __init__(self, design: BrainDesign, parent=None):
        super().__init__(parent)
        self.design = design
        self.setWindowTitle("Export Brain Design")
        self.setMinimumSize(600, 500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tabs for different export formats
        tabs = QTabWidget()
        
        # Dosidicus format tab
        dosi_tab = QWidget()
        dosi_layout = QVBoxLayout(dosi_tab)
        
        dosi_layout.addWidget(QLabel(
            "Export in Dosidicus-2 compatible format.\n"
            "This JSON file can be loaded directly using NetworkAdapter.load()"
        ))
        
        self.dosi_preview = QTextEdit()
        self.dosi_preview.setReadOnly(True)
        self.dosi_preview.setFont(QFont("Courier", 9))
        dosi_layout.addWidget(self.dosi_preview)
        
        dosi_btn = QPushButton("Export as Dosidicus JSON...")
        dosi_btn.clicked.connect(self.export_dosidicus)
        dosi_layout.addWidget(dosi_btn)
        
        tabs.addTab(dosi_tab, "Dosidicus Format")
        
        # Designer format tab
        design_tab = QWidget()
        design_layout = QVBoxLayout(design_tab)
        
        design_layout.addWidget(QLabel(
            "Export in Brain Designer format.\n"
            "This format preserves all designer metadata and can be re-opened."
        ))
        
        self.design_preview = QTextEdit()
        self.design_preview.setReadOnly(True)
        self.design_preview.setFont(QFont("Courier", 9))
        design_layout.addWidget(self.design_preview)
        
        design_btn = QPushButton("Export as Designer JSON...")
        design_btn.clicked.connect(self.export_designer)
        design_layout.addWidget(design_btn)
        
        tabs.addTab(design_tab, "Designer Format")
        
        # Python code tab
        code_tab = QWidget()
        code_layout = QVBoxLayout(code_tab)
        
        code_layout.addWidget(QLabel(
            "Generate Python code to create this brain programmatically."
        ))
        
        self.code_preview = QTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Courier", 9))
        code_layout.addWidget(self.code_preview)
        
        code_btn = QPushButton("Copy to Clipboard")
        code_btn.clicked.connect(self.copy_code)
        code_layout.addWidget(code_btn)
        
        tabs.addTab(code_tab, "Python Code")
        
        layout.addWidget(tabs)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        # Generate previews
        self.generate_previews()
    
    def generate_previews(self):
        # Dosidicus format
        dosi_data = self.design.to_dosidicus_format()
        self.dosi_preview.setPlainText(json.dumps(dosi_data, indent=2))
        
        # Designer format
        design_data = self.design.to_dict()
        self.design_preview.setPlainText(json.dumps(design_data, indent=2))
        
        # Python code
        code = self.generate_python_code()
        self.code_preview.setPlainText(code)
    
    def generate_python_code(self) -> str:
        """Generate Python code to create this brain."""
        lines = [
            "from brain_factory import BrainFactory",
            "from network_adapter import NetworkAdapter",
            "from network_protocol import NeuronData, BrainConfig",
            "",
            "def create_custom_brain():",
            '    """Auto-generated brain design."""',
            "",
        ]
        
        # Create layers
        if self.design.layers:
            lines.append("    # Create layered network")
            layers_code = "    brain = BrainFactory.create_layered_network(["
            lines.append(layers_code)
            
            for layer in self.design.layers:
                neurons_in_layer = [n.name for n in self.design.neurons.values() 
                                   if n.layer_index == self.design.layers.index(layer)]
                lines.append(f"        ('{layer.layer_type.value}', {neurons_in_layer}),")
            
            lines.append("    ])")
        else:
            lines.append("    # Create empty network")
            lines.append("    from core import Network")
            lines.append("    brain = NetworkAdapter(Network())")
        
        lines.append("")
        
        # Custom connections
        if self.design.connections:
            lines.append("    # Custom connection weights")
            for (src, tgt), conn in self.design.connections.items():
                lines.append(f"    brain.add_connection('{src}', '{tgt}', {conn.weight:.3f})")
        
        lines.append("")
        
        # Excluded neurons
        if self.design.excluded_neurons:
            lines.append("    # Excluded neurons")
            lines.append(f"    brain._excluded_neurons.update({list(self.design.excluded_neurons)})")
        
        lines.append("")
        lines.append("    return brain")
        lines.append("")
        lines.append("")
        lines.append("if __name__ == '__main__':")
        lines.append("    brain = create_custom_brain()")
        lines.append("    print(f'Created brain with {len(brain.neuron_positions)} neurons')")
        
        return "\n".join(lines)
    
    def export_dosidicus(self):
        # Validate before export
        valid, issues = self.design.validate_for_export()
        
        if not valid:
            # Ask user if they want to add missing core neurons
            missing = self.design.get_missing_core_neurons()
            if missing:
                reply = QMessageBox.question(
                    self, "Missing Core Neurons",
                    f"The following core neurons are missing:\n• {chr(10).join(missing)}\n\n"
                    f"These are required for Dosidicus-2 compatibility.\n\n"
                    f"Would you like to add them automatically?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                
                if reply == QMessageBox.Cancel:
                    return
                elif reply == QMessageBox.Yes:
                    added = self.design.add_missing_core_neurons()
                    QMessageBox.information(
                        self, "Core Neurons Added",
                        f"Added {len(added)} core neuron(s):\n• {chr(10).join(added)}"
                    )
                    # Refresh preview
                    self.generate_previews()
                # If No, continue anyway (user's choice)
        
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Dosidicus Brain",
            f"{self.design.metadata.get('name', 'brain')}_dosidicus.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            data = self.design.to_dosidicus_format()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export Complete", f"Brain exported to:\n{filepath}")
    
    def export_designer(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Designer File",
            f"{self.design.metadata.get('name', 'brain')}_design.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            data = self.design.to_dict()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            QMessageBox.information(self, "Export Complete", f"Design exported to:\n{filepath}")
    
    def copy_code(self):
        QApplication.clipboard().setText(self.code_preview.toPlainText())
        QMessageBox.information(self, "Copied", "Python code copied to clipboard!")


# =============================================================================
# MAIN WINDOW
# =============================================================================

class BrainDesignerWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DOSIDICUS Brain Designer")
        self.setMinimumSize(1280, 800)
        
        self.design = BrainDesign()
        self.current_file: Optional[str] = None
        
        self.setup_ui()
        self.setup_menu()
        self.setup_toolbar()
        self.setup_statusbar()
        
        # Load default template
        self.load_template('layered_dosidicus')
    
    def setup_ui(self):
        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout(central)
        
        # Left panel - Templates and Layers
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_tabs = QTabWidget()
        
        self.template_panel = TemplateLibraryPanel()
        self.template_panel.templateSelected.connect(self.load_template)
        left_tabs.addTab(self.template_panel, "Templates")
        
        self.layer_panel = LayerManagerPanel()
        self.layer_panel.layersChanged.connect(self.on_design_changed)
        left_tabs.addTab(self.layer_panel, "Layers")
        
        left_layout.addWidget(left_tabs)
        left_panel.setMinimumWidth(200)
        
        # Center - Canvas
        self.canvas = BrainCanvas()
        self.canvas.set_design(self.design)
        self.canvas.neuronSelected.connect(self.on_neuron_selected)
        self.canvas.connectionSelected.connect(self.on_connection_selected)
        self.canvas.designChanged.connect(self.on_design_changed)
        
        # Right panel - Properties
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        right_tabs = QTabWidget()
        
        self.neuron_panel = NeuronPropertiesPanel()
        self.neuron_panel.propertiesChanged.connect(self.on_design_changed)
        right_tabs.addTab(self.neuron_panel, "Neuron")
        
        self.connection_panel = ConnectionPropertiesPanel()
        self.connection_panel.propertiesChanged.connect(self.on_design_changed)
        right_tabs.addTab(self.connection_panel, "Connections")
        
        right_layout.addWidget(right_tabs)
        right_panel.setMinimumWidth(250)
        
        # Splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.canvas)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        
        # Make splitter handles more visible and easier to grab
        splitter.setHandleWidth(4)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #cccccc;
            }
            QSplitter::handle:hover {
                background: #999999;
            }
            QSplitter::handle:pressed {
                background: #666666;
            }
        """)
        
        # Set initial sizes (left: 280, center: flexible, right: 320)
        splitter.setSizes([280, 600, 320])
        
        main_layout.addWidget(splitter)
        
        # Initial panel setup
        self.neuron_panel.set_design(self.design)
        self.connection_panel.set_design(self.design)
        self.layer_panel.set_design(self.design)
    
    def setup_menu(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        new_action = QAction("&New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_design)
        file_menu.addAction(new_action)
        
        open_action = QAction("&Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_design)
        file_menu.addAction(open_action)
        
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_design)
        file_menu.addAction(save_action)
        
        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_design_as)
        file_menu.addAction(save_as_action)
        
        file_menu.addSeparator()
        
        export_action = QAction("&Export...", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self.show_export_dialog)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("&Edit")
        
        add_neuron_action = QAction("Add &Neuron", self)
        add_neuron_action.setShortcut("Ctrl+N")
        add_neuron_action.triggered.connect(self.add_neuron_dialog)
        edit_menu.addAction(add_neuron_action)
        
        edit_menu.addSeparator()
        
        add_core_action = QAction("Add &Missing Core Neurons", self)
        add_core_action.setToolTip("Add any missing core neurons required for Dosidicus-2")
        add_core_action.triggered.connect(self.add_missing_core_neurons)
        edit_menu.addAction(add_core_action)
        
        check_core_action = QAction("&Check Core Neuron Status", self)
        check_core_action.triggered.connect(self.check_core_neurons)
        edit_menu.addAction(check_core_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        self.grid_action = QAction("Show &Grid", self)
        self.grid_action.setCheckable(True)
        self.grid_action.setChecked(True)
        self.grid_action.triggered.connect(lambda: setattr(self.canvas, 'show_grid', self.grid_action.isChecked()) or self.canvas.update())
        view_menu.addAction(self.grid_action)
        
        self.layers_action = QAction("Show &Layers", self)
        self.layers_action.setCheckable(True)
        self.layers_action.setChecked(True)
        self.layers_action.triggered.connect(lambda: setattr(self.canvas, 'show_layers', self.layers_action.isChecked()) or self.canvas.update())
        view_menu.addAction(self.layers_action)
        
        self.weights_action = QAction("Show &Weights", self)
        self.weights_action.setCheckable(True)
        self.weights_action.setChecked(True)
        self.weights_action.triggered.connect(lambda: setattr(self.canvas, 'show_weights', self.weights_action.isChecked()) or self.canvas.update())
        view_menu.addAction(self.weights_action)
        
        view_menu.addSeparator()
        
        reset_view_action = QAction("&Reset View", self)
        reset_view_action.setShortcut("Home")
        reset_view_action.triggered.connect(self.reset_view)
        view_menu.addAction(reset_view_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        instructions_action = QAction("&Instructions", self)
        instructions_action.setShortcut("F1")
        instructions_action.triggered.connect(self.show_instructions)
        help_menu.addAction(instructions_action)
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        # Add neuron button
        add_btn = QToolButton()
        add_btn.setText("+ Neuron")
        add_btn.setToolTip("Add a new neuron (double-click canvas)")
        add_btn.clicked.connect(self.add_neuron_dialog)
        toolbar.addWidget(add_btn)
        
        toolbar.addSeparator()
        
        # Template dropdown
        toolbar.addWidget(QLabel("  Template: "))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(150)
        for key, info in TemplateLibraryPanel.TEMPLATES.items():
            self.template_combo.addItem(info['name'], key)
        self.template_combo.currentIndexChanged.connect(
            lambda: self.load_template(self.template_combo.currentData())
        )
        toolbar.addWidget(self.template_combo)
        
        toolbar.addSeparator()
        
        # Snap to grid
        self.snap_check = QCheckBox("Snap to Grid")
        self.snap_check.setChecked(True)
        self.snap_check.toggled.connect(lambda v: setattr(self.canvas, 'snap_to_grid', v))
        toolbar.addWidget(self.snap_check)
        
        toolbar.addSeparator()
        
        # Export button
        export_btn = QToolButton()
        export_btn.setText("Export")
        export_btn.setToolTip("Export brain for Dosidicus-2")
        export_btn.clicked.connect(self.show_export_dialog)
        toolbar.addWidget(export_btn)
    
    def setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.update_statusbar()
    
    def update_statusbar(self):
        neurons = len(self.design.neurons)
        connections = len(self.design.connections)
        layers = len(self.design.layers)
        
        # Core neuron status
        missing_core = self.design.get_missing_core_neurons()
        if missing_core:
            core_status = f"⚠️ Missing {len(missing_core)} core"
        else:
            core_status = "✓ All core neurons"
        
        self.statusbar.showMessage(
            f"Neurons: {neurons} | Connections: {connections} | Layers: {layers} | "
            f"{core_status} | "
            f"Double-click to add neurons | Shift+drag to connect"
        )
    
    # =========================================================================
    # ACTIONS
    # =========================================================================
    
    def new_design(self):
        reply = QMessageBox.question(
            self, "New Design",
            "Create a new design? Unsaved changes will be lost.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.design = BrainDesign()
            self.current_file = None
            self.refresh_all_panels()
    
    def open_design(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open Design",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filepath:
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                self.design = BrainDesign.from_dict(data)
                self.current_file = filepath
                self.refresh_all_panels()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")
    
    def save_design(self):
        if self.current_file:
            self._save_to_file(self.current_file)
        else:
            self.save_design_as()
    
    def save_design_as(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Design",
            f"{self.design.metadata.get('name', 'brain')}_design.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            self._save_to_file(filepath)
            self.current_file = filepath
    
    def _save_to_file(self, filepath: str):
        try:
            with open(filepath, 'w') as f:
                json.dump(self.design.to_dict(), f, indent=2)
            self.statusbar.showMessage(f"Saved to {filepath}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
    
    def show_export_dialog(self):
        dialog = ExportDialog(self.design, self)
        dialog.exec_()
    
    def add_neuron_dialog(self):
        name, ok = QInputDialog.getText(self, "Add Neuron", "Neuron name:")
        if ok and name:
            if name in self.design.neurons:
                QMessageBox.warning(self, "Error", "A neuron with this name already exists.")
                return
            
            # Find center of canvas
            x = self.canvas.width() / 2 / self.canvas.zoom - self.canvas.pan_offset.x() / self.canvas.zoom
            y = self.canvas.height() / 2 / self.canvas.zoom - self.canvas.pan_offset.y() / self.canvas.zoom
            
            neuron = DesignerNeuron(
                name=name,
                neuron_type=NeuronType.HIDDEN,
                position=(x, y)
            )
            self.design.add_neuron(neuron)
            self.on_design_changed()
    
    def reset_view(self):
        self.canvas.pan_offset = QPointF(50, 50)
        self.canvas.zoom = 1.0
        self.canvas.update()
    
    def add_missing_core_neurons(self):
        """Add any missing core neurons to the design."""
        added = self.design.add_missing_core_neurons()
        if added:
            QMessageBox.information(
                self, "Core Neurons Added",
                f"Added {len(added)} missing core neuron(s):\n• " + "\n• ".join(added)
            )
            self.refresh_all_panels()
        else:
            QMessageBox.information(
                self, "All Core Neurons Present",
                "All 7 core neurons are already in the design."
            )
    
    def check_core_neurons(self):
        """Check and display core neuron status."""
        missing = self.design.get_missing_core_neurons()
        present = [n for n in CORE_NEURON_NAMES if n not in missing]
        
        msg = "Core Neuron Status:\n\n"
        msg += "Present:\n"
        for name in present:
            msg += f"  ✓ {name}\n"
        
        if missing:
            msg += "\nMissing:\n"
            for name in missing:
                msg += f"  ✗ {name}\n"
            msg += "\nUse Edit → Add Missing Core Neurons to add them."
        else:
            msg += "\n✓ All core neurons present - design is Dosidicus-2 compatible!"
        
        QMessageBox.information(self, "Core Neuron Check", msg)
    
    def load_template(self, template_key: str):
        info = TemplateLibraryPanel.TEMPLATES.get(template_key, {})
        
        if not info.get('has_core_neurons', False):
            QMessageBox.critical(
                self, "Incompatible Template",
                f"'{info.get('name', 'This template')}' is missing core neurons.\n\n"
                f"Only templates marked with ⭐ are compatible with Dosidicus-2."
            )
            return
        
        # Proceed with loading...
        self.design = BrainDesign()
        
        if template_key == 'dosidicus_default':
            self._create_dosidicus_default()
        elif template_key == 'core_only':
            self._create_core_only()
        elif template_key == 'layered_dosidicus':
            self._create_layered_dosidicus()
        elif template_key == 'sensory_enhanced':
            self._create_sensory_enhanced()
        elif template_key == 'cognitive_complex':
            self._create_cognitive_complex()
        
        self.refresh_all_panels()
    
    def _create_dosidicus_default(self):
        """Create the default flat Dosidicus brain - matches brain_widget.py exactly."""
        self.design.layers = [
            DesignerLayer("Main", NeuronType.HIDDEN, 200)
        ]
        
        # Exact positions from brain_widget.py original_neuron_positions
        neurons = [
            ("hunger", (127, 81)),
            ("happiness", (361, 81)),
            ("cleanliness", (627, 81)),
            ("sleepiness", (840, 81)),
            ("satisfaction", (271, 380)),
            ("anxiety", (491, 389)),
            ("curiosity", (701, 386)),
        ]
        
        for name, pos in neurons:
            self.design.add_neuron(DesignerNeuron(
                name=name,
                neuron_type=NeuronType.HIDDEN,
                position=pos,
                color=(150, 150, 220),
                description=f"Core neuron - required for Dosidicus-2"
            ))
        
        # Add some basic connections
        connections = [
            ("hunger", "satisfaction", -0.5),
            ("hunger", "anxiety", 0.3),
            ("happiness", "satisfaction", 0.6),
            ("cleanliness", "happiness", 0.3),
        ]
        for src, tgt, w in connections:
            self.design.add_connection(src, tgt, w)
    
    def _create_core_only(self):
        """Create minimal brain with just the 7 core neurons and no connections."""
        self.design.metadata['name'] = 'Core Only'
        self.design.metadata['description'] = 'Starting point with 7 core neurons - add your own connections'
        
        self.design.layers = [
            DesignerLayer("Core", NeuronType.HIDDEN, 200)
        ]
        
        # Use the CORE_NEURONS constant to ensure exact match
        for name, pos in CORE_NEURONS.items():
            self.design.add_neuron(DesignerNeuron(
                name=name,
                neuron_type=NeuronType.HIDDEN,
                position=pos,
                color=(150, 150, 220),
                description=f"Core neuron - required for Dosidicus-2"
            ))
        
        # No connections - user will add their own
    
    def _create_layered_dosidicus(self):
        """Core neurons reorganized into Input→Hidden→Output layers"""
        self.design.metadata['name'] = 'Layered Dosidicus'
        
        # First add core neurons (positions will be overridden)
        self._create_core_only()
        
        # Redefine layers with conceptual grouping
        self.design.layers = [
            DesignerLayer("Input", NeuronType.INPUT, 80, (200, 255, 200)),
            DesignerLayer("Hidden", NeuronType.HIDDEN, 250, (200, 200, 255)),
            DesignerLayer("Output", NeuronType.OUTPUT, 420, (255, 200, 200)),
        ]
        
        # Reposition core neurons into functional layers
        # Input layer: raw physiological needs
        self.design.neurons["hunger"].position = (150, 80)
        self.design.neurons["hunger"].neuron_type = NeuronType.INPUT
        self.design.neurons["hunger"].layer_index = 0
        
        self.design.neurons["cleanliness"].position = (350, 80)
        self.design.neurons["cleanliness"].neuron_type = NeuronType.INPUT
        self.design.neurons["cleanliness"].layer_index = 0
        
        self.design.neurons["sleepiness"].position = (550, 80)
        self.design.neurons["sleepiness"].neuron_type = NeuronType.INPUT
        self.design.neurons["sleepiness"].layer_index = 0
        
        # Hidden layer: processing & intermediate states
        self.design.neurons["satisfaction"].position = (250, 250)
        self.design.neurons["satisfaction"].neuron_type = NeuronType.HIDDEN
        self.design.neurons["satisfaction"].layer_index = 1
        
        self.design.neurons["anxiety"].position = (450, 250)
        self.design.neurons["anxiety"].neuron_type = NeuronType.HIDDEN
        self.design.neurons["anxiety"].layer_index = 1
        
        # Output layer: high-level emotions & drives
        self.design.neurons["happiness"].position = (350, 420)
        self.design.neurons["happiness"].neuron_type = NeuronType.OUTPUT
        self.design.neurons["happiness"].layer_index = 2
        
        self.design.neurons["curiosity"].position = (550, 420)
        self.design.neurons["curiosity"].neuron_type = NeuronType.OUTPUT
        self.design.neurons["curiosity"].layer_index = 2
        
        # ADD MEANINGFUL sensory neuron (replaces arbitrary "stimulation")
        self.design.add_neuron(DesignerNeuron(
            name="external_stimulus",  # Clear purpose
            neuron_type=NeuronType.INPUT,
            position=(750, 80),
            layer_index=0,
            color=(180, 240, 180),
            description="Environmental sensory input (light, sound, etc.)"
        ))
        
        # Create meaningful inter-layer connections
        conns = [
            # Input → Hidden
            ("hunger", "anxiety", 0.5),
            ("cleanliness", "satisfaction", 0.4),
            ("sleepiness", "anxiety", 0.3),
            ("external_stimulus", "curiosity", 0.6),
            
            # Hidden → Output
            ("satisfaction", "happiness", 0.7),
            ("anxiety", "happiness", -0.5),
            
            # Cross-layer shortcuts
            ("hunger", "satisfaction", -0.3),
        ]
        
        for src, tgt, w in conns:
            self.design.add_connection(src, tgt, w)

    def _create_sensory_enhanced(self):
        """Core + sensors for richer environmental interaction"""
        self.design.metadata['name'] = 'Sensory Enhanced'
        
        # Start with the layered dosidicus as base
        self._create_layered_dosidicus()
        
        # Add sensory input neurons that feed into the core network
        sensors = [
            ("food_proximity", (800, 80), "Distance to nearest food item"),
            ("threat_level", (900, 80), "Detected danger/predator presence"),
            ("light_intensity", (850, 130), "Environmental light level"),
            ("temperature", (750, 130), "Temperature sensing")
        ]
        
        for name, pos, desc in sensors:
            self.design.add_neuron(DesignerNeuron(
                name=name,
                neuron_type=NeuronType.INPUT,
                position=pos,
                layer_index=0,
                color=(170, 230, 170),
                description=desc
            ))
        
        # Connect sensors to relevant core neurons (add your connection logic)
        sensor_conns = [
            ("food_proximity", "hunger", -0.7),
            ("threat_level", "anxiety", 0.9),
            # ... add rest of connections
        ]
        
        for src, tgt, w in sensor_conns:
            self.design.add_connection(src, tgt, w)

    def _create_cognitive_complex(self):
        """Core + internal processing layers for memory & prediction"""
        self._create_layered_dosidicus()
        
        # Add internal processing neurons in hidden layers
        processors = [
            # Memory layer (between Input and Hidden)
            ("memory_buffer", (650, 180), "Short-term memory storage", 1),
            ("pattern_recognizer", (750, 180), "Recognizes environmental patterns", 1),
            
            # Prediction layer (between Hidden and Output)  
            ("outcome_predictor", (650, 320), "Predicts action consequences", 2),
            ("risk_assessor", (750, 320), "Evaluates action risks", 2),
            
            # Meta-cognitive layer (new top layer)
            ("self_monitor", (450, 500), "Monitors internal state", 3)
        ]
        
        for name, pos, desc, layer_idx in processors:
            self.design.add_neuron(DesignerNeuron(
                name=name,
                neuron_type=NeuronType.HIDDEN if layer_idx < 3 else NeuronType.OUTPUT,
                position=pos,
                layer_index=layer_idx,
                color=(180, 180, 220),
                description=desc
            ))
        
        # Connect processors in a deep, recurrent pattern
        complex_conns = [
            # Input → Memory
            ("external_stimulus", "memory_buffer", 0.5),
            ("food_proximity", "pattern_recognizer", 0.4),
            
            # Memory → Hidden (feeds into core processing)
            ("memory_buffer", "satisfaction", 0.3),
            ("pattern_recognizer", "anxiety", 0.2),
            
            # Hidden → Prediction
            ("satisfaction", "outcome_predictor", 0.6),
            ("anxiety", "risk_assessor", 0.7),
            
            # Prediction → Output (modulates behavior)
            ("outcome_predictor", "curiosity", 0.4),
            ("risk_assessor", "happiness", -0.3),
            
            # Self-monitoring (top-level)
            ("happiness", "self_monitor", 0.5),
            ("self_monitor", "curiosity", 0.2)  # Self-awareness drives exploration
        ]
        
        for src, tgt, w in complex_conns:
            self.design.add_connection(src, tgt, w)
    
    def _create_deep_processor(self):
        """Create a 4-layer deep processor."""
        self.design.metadata['name'] = 'Deep Processor'
        
        self.design.layers = [
            DesignerLayer("Input", NeuronType.INPUT, 60),
            DesignerLayer("Hidden_1", NeuronType.HIDDEN, 180),
            DesignerLayer("Hidden_2", NeuronType.HIDDEN, 300),
            DesignerLayer("Output", NeuronType.OUTPUT, 420),
        ]
        
        # Create neurons
        y_positions = [60, 180, 300, 420]
        layer_configs = [
            [("in_1", 200), ("in_2", 400), ("in_3", 600)],
            [("h1_1", 250), ("h1_2", 450), ("h1_3", 650)],
            [("h2_1", 300), ("h2_2", 500)],
            [("out_1", 350), ("out_2", 550)],
        ]
        
        types = [NeuronType.INPUT, NeuronType.HIDDEN, NeuronType.HIDDEN, NeuronType.OUTPUT]
        colors = [(150, 220, 150), (150, 150, 220), (180, 150, 220), (220, 150, 150)]
        
        for layer_idx, (neurons, y, n_type, color) in enumerate(zip(layer_configs, y_positions, types, colors)):
            for name, x in neurons:
                self.design.add_neuron(DesignerNeuron(
                    name=name, neuron_type=n_type,
                    position=(x, y), layer_index=layer_idx, color=color
                ))
        
        # Connect adjacent layers
        for layer_idx in range(len(layer_configs) - 1):
            for name1, _ in layer_configs[layer_idx]:
                for name2, _ in layer_configs[layer_idx + 1]:
                    self.design.add_connection(name1, name2, random.uniform(-0.3, 0.3))
    
    def _create_emotion_engine(self):
        """Create an emotion-focused brain."""
        self.design.metadata['name'] = 'Emotion Engine'
        
        self.design.layers = [
            DesignerLayer("Stimuli", NeuronType.INPUT, 80),
            DesignerLayer("Appraisal", NeuronType.HIDDEN, 230),
            DesignerLayer("Emotions", NeuronType.OUTPUT, 380),
        ]
        
        # Stimuli
        for i, name in enumerate(["positive_stimulus", "negative_stimulus", "novel_stimulus"]):
            self.design.add_neuron(DesignerNeuron(
                name=name, neuron_type=NeuronType.INPUT,
                position=(200 + i*250, 80), layer_index=0, color=(150, 220, 150)
            ))
        
        # Appraisal
        for i, name in enumerate(["valence", "arousal", "novelty_detector"]):
            self.design.add_neuron(DesignerNeuron(
                name=name, neuron_type=NeuronType.HIDDEN,
                position=(200 + i*250, 230), layer_index=1, color=(150, 150, 220)
            ))
        
        # Emotions
        for i, name in enumerate(["joy", "fear", "curiosity"]):
            self.design.add_neuron(DesignerNeuron(
                name=name, neuron_type=NeuronType.OUTPUT,
                position=(200 + i*250, 380), layer_index=2, color=(220, 150, 150)
            ))
        
        # Connections
        conns = [
            ("positive_stimulus", "valence", 0.8),
            ("negative_stimulus", "valence", -0.8),
            ("negative_stimulus", "arousal", 0.7),
            ("novel_stimulus", "novelty_detector", 0.9),
            ("novel_stimulus", "arousal", 0.4),
            ("valence", "joy", 0.8),
            ("valence", "fear", -0.6),
            ("arousal", "fear", 0.5),
            ("novelty_detector", "curiosity", 0.8),
            ("arousal", "curiosity", 0.3),
        ]
        for src, tgt, w in conns:
            self.design.add_connection(src, tgt, w)
    
    def _create_minimal(self):
        """Create minimal 2-neuron brain."""
        self.design.metadata['name'] = 'Minimal'
        
        self.design.layers = [
            DesignerLayer("Input", NeuronType.INPUT, 100),
            DesignerLayer("Output", NeuronType.OUTPUT, 300),
        ]
        
        self.design.add_neuron(DesignerNeuron(
            name="input", neuron_type=NeuronType.INPUT,
            position=(400, 100), layer_index=0, color=(150, 220, 150)
        ))
        self.design.add_neuron(DesignerNeuron(
            name="output", neuron_type=NeuronType.OUTPUT,
            position=(400, 300), layer_index=1, color=(220, 150, 150)
        ))
        
        self.design.add_connection("input", "output", 0.5)
    
    def refresh_all_panels(self):
        """Refresh all UI panels with current design."""
        self.canvas.set_design(self.design)
        self.neuron_panel.set_design(self.design)
        self.neuron_panel.set_neuron(None)
        self.connection_panel.set_design(self.design)
        self.layer_panel.set_design(self.design)
        self.update_statusbar()
    
    def on_design_changed(self):
        """Called when the design is modified."""
        self.canvas.update()
        self.connection_panel.refresh()
        self.update_statusbar()
    
    def on_neuron_selected(self, neuron_name: str):
        """Called when a neuron is selected."""
        self.neuron_panel.set_neuron(neuron_name)
    
    def on_connection_selected(self, source: str, target: str):
        """Called when a connection is selected."""
        # Could show a dialog to edit the connection
        weight, ok = QInputDialog.getDouble(
            self, "Edit Connection Weight",
            f"Weight for {source} → {target}:",
            self.design.connections.get((source, target), DesignerConnection(source, target)).weight,
            -1.0, 1.0, 3
        )
        
        if ok:
            if (source, target) in self.design.connections:
                self.design.connections[(source, target)].weight = weight
                self.on_design_changed()
    
    def show_instructions(self):
        """Show usage instructions."""
        instructions = """
<h2>Brain Designer Instructions</h2>

<h3>Canvas Controls</h3>
<ul>
<li><b>Double-click</b> on empty space to add a neuron</li>
<li><b>Click</b> on a neuron to select it</li>
<li><b>Drag</b> neurons to reposition them</li>
<li><b>Shift+drag</b> from one neuron to another to create a connection</li>
<li><b>Right-drag</b> to pan the view</li>
<li><b>Scroll wheel</b> to zoom in/out</li>
<li><b>Delete key</b> to remove selected neuron</li>
<li><b>Middle-click</b> on a connection to edit its weight</li>
</ul>

<h3>Keyboard Shortcuts</h3>
<ul>
<li><b>G</b> - Toggle grid display</li>
<li><b>L</b> - Toggle layer backgrounds</li>
<li><b>W</b> - Toggle weight labels</li>
<li><b>Home</b> - Reset view</li>
<li><b>Ctrl+S</b> - Save design</li>
<li><b>Ctrl+E</b> - Export for Dosidicus-2</li>
</ul>

<h3>Workflow</h3>
<ol>
<li>Start with a template or create layers in the Layers tab</li>
<li>Add neurons by double-clicking the canvas</li>
<li>Position neurons within their layers</li>
<li>Create connections using Shift+drag or the Connections tab</li>
<li>Adjust connection weights in the Connections tab</li>
<li>Export using File → Export</li>
</ol>

<h3>Dosidicus-2 Integration</h3>
<p>After exporting, use this code to load your brain:</p>
<pre>
from network_adapter import NetworkAdapter
from brain_integration import BrainIntegrator

# Load your custom brain
brain = NetworkAdapter.load('my_brain_dosidicus.json')

# Inject into BrainWidget
BrainIntegrator.full_integration(brain_widget, brain, brain_worker)
</pre>
        """
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Instructions")
        dialog.setMinimumSize(500, 600)
        
        layout = QVBoxLayout(dialog)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(instructions)
        layout.addWidget(text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec_()
    
    def show_about(self):
        QMessageBox.about(
            self, "About Brain Designer",
            "<h2>Brain Designer</h2>"
            "<p>Version 1.0.0</p>"
            "<p>A visual neural network editor for creating custom brains "
            "compatible with the Dosidicus-2 tamagotchi simulation.</p>"
            "<p>Features:</p>"
            "<ul>"
            "<li>Drag-and-drop neuron placement</li>"
            "<li>Visual connection editing</li>"
            "<li>Layer management</li>"
            "<li>Template library</li>"
            "<li>Direct export to Dosidicus-2 format</li>"
            "</ul>"
        )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Set application-wide font
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    window = BrainDesignerWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()