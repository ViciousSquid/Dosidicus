# UI Stuff

import os
import json
import math
import time
import random
import traceback
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QObject, pyqtProperty
from PyQt5.QtWidgets import QGraphicsPixmapItem
from .squid_brain_window import SquidBrainWindow
from .statistics_window import StatisticsWindow


class DecorationItem(QtWidgets.QLabel):
    def __init__(self, pixmap, filename):
        super().__init__()
        self.setPixmap(pixmap.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.filename = filename
        self.setFixedSize(138, 138)  # Increased to accommodate larger thumbnails
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setToolTip(filename)

        self.decoration_items = []

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            drag = QtGui.QDrag(self)
            mime_data = QtCore.QMimeData()
            mime_data.setUrls([QtCore.QUrl.fromLocalFile(self.filename)])
            drag.setMimeData(mime_data)
            drag.setPixmap(self.pixmap())
            drag.setHotSpot(event.pos() - self.rect().topLeft())
            drag.exec_(QtCore.Qt.CopyAction)

class ResizablePixmapItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, pixmap, filename):
        super().__init__(pixmap)
        self.filename = filename
        self.pixmap_item = QtWidgets.QGraphicsPixmapItem(self)
        self.pixmap_item.setPixmap(pixmap.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.resize_handle = None
        self.original_pixmap = pixmap
        self.filename = filename
        self.stat_multipliers, self.category = self.get_decoration_info()

        if not self.stat_multipliers:
            self.stat_multipliers = {'happiness': 1}

        # Add these rock interaction attributes
        self.can_be_picked_up = 'rock' in filename.lower()  # Auto-detect rocks from filename
        self.is_being_carried = False
        self.original_scale = 1.0  # Store original scale for restoration

    def boundingRect(self):
        return self.pixmap_item.boundingRect().adjusted(0, 0, 20, 20)

    def paint(self, painter, option, widget):
        self.pixmap_item.paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 255), 2))
            painter.drawRect(self.boundingRect())
            handle_pos = self.boundingRect().bottomRight() - QtCore.QPointF(20, 20)
            handle_rect = QtCore.QRectF(handle_pos, QtCore.QSizeF(20, 20))
            painter.fillRect(handle_rect, QtGui.QColor(0, 0, 255))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            if QtCore.QRectF(self.boundingRect().bottomRight() - QtCore.QPointF(20, 20),
                             QtCore.QSizeF(20, 20)).contains(pos):
                self.resize_handle = self.mapToScene(pos)
            else:
                self.resize_handle = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_handle is not None:
            new_pos = self.mapToScene(event.pos())
            width = max(new_pos.x() - self.pos().x(), 20)
            height = max(new_pos.y() - self.pos().y(), 20)
            aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()
            if width / height > aspect_ratio:
                width = height * aspect_ratio
            else:
                height = width / aspect_ratio
            self.pixmap_item.setPixmap(self.original_pixmap.scaled(int(width), int(height), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.resize_handle = None
        super().mouseReleaseEvent(event)

    def get_decoration_info(self):
        try:
            file_path = os.path.join(os.path.dirname(__file__), 'decoration_stats.json')
            with open(file_path, 'r') as f:
                stats = json.load(f)
            info = stats.get(self.filename, {})
            stat_multipliers = {k: v for k, v in info.items() if k != 'category'}
            category = info.get('category', 'plant')
            return stat_multipliers, category
        except FileNotFoundError:
            print(f"decoration_stats.json not found at {file_path}. Using empty stats.")
            return {}, 'plant'
        except json.JSONDecodeError:
            print(f"Error decoding decoration_stats.json at {file_path}. Using empty stats.")
            return {}, 'plant'


class DecorationWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        self.setWindowTitle("Decorations")
        self.setFixedWidth(800)  # Increased width

        # Create a list to store the decoration items
        self.decoration_items = []

        layout = QtWidgets.QVBoxLayout(self)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        layout.addWidget(scroll_area)

        content_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)

        self.load_decorations()

    def add_decoration_item(self, item):
        self.decoration_items.append(item)

    def load_decorations(self):
        decoration_path = "images/decoration"
        items_per_row = 4  # Increased to 4 items per row
        row, col = 0, 0

        for filename in os.listdir(decoration_path):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(decoration_path, filename)
                pixmap = QtGui.QPixmap(full_path)
                item = DecorationItem(pixmap, full_path)
                self.grid_layout.addWidget(item, row, col)

                col += 1
                if col >= items_per_row:
                    col = 0
                    row += 1

        # Set the window height based on the number of rows
        self.setFixedHeight(min((row + 1) * 148 + 40, 650))  # 148 pixels per row (138 + 10 padding), max height of 600

class Ui:
    def __init__(self, window, tamagotchi_logic):
        self.window = window
        self.tamagotchi_logic = tamagotchi_logic
        self.window_width = 1280
        self.window_height = 820

        self.window.setWindowTitle("Dosidicus")

        self.window.resize(self.window_width, self.window_height)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.window.setCentralWidget(self.view)

        self.setup_menu_bar()
        self.neuron_inspector = None
        self.squid_brain_window = None

        self.decoration_window = DecorationWindow(self.window)
        self.decoration_window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.Tool)
        self.decoration_window.setAttribute(QtCore.Qt.WA_QuitOnClose, False)

        self.statistics_window = None

        # Enable drag and drop for the main window
        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = self.dragEnterEvent
        self.view.dragMoveEvent = self.dragMoveEvent
        self.view.dropEvent = self.dropEvent

        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.view.keyPressEvent = self.keyPressEvent
        self.setup_ui_elements()

    def optimize_animations(self):
        self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)  # Better for moving items
        self.view.setCacheMode(QtWidgets.QGraphicsView.CacheBackground)

    def setup_ui_elements(self):
        # Create the rectangle item
        self.rect_item = self.scene.addRect(50, 50, self.window_width - 100, self.window_height - 100,
                                            QtGui.QPen(QtGui.QColor(0, 0, 0)), QtGui.QBrush(QtGui.QColor(255, 255, 255)))

        # Create the cleanliness overlay
        self.cleanliness_overlay = self.scene.addRect(50, 50, self.window_width - 100, self.window_height - 100,
                                                      QtGui.QPen(QtCore.Qt.NoPen), QtGui.QBrush(QtGui.QColor(139, 69, 19, 0)))

        # Create the feeding message
        self.feeding_message = QtWidgets.QGraphicsTextItem("Squid requires feeding")
        self.feeding_message.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        self.feeding_message.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.feeding_message.setPos(0, self.window_height - 75 )
        self.feeding_message.setTextWidth(self.window_width)
        self.feeding_message.setHtml('<div style="text-align: center;">Squid requires feeding</div>')
        self.feeding_message.setOpacity(0)
        self.scene.addItem(self.feeding_message)

        # Create points labels
        self.points_label = QtWidgets.QGraphicsTextItem("Points:")
        self.points_label.setDefaultTextColor(QtGui.QColor(255, 255, 255))  # Set font color to white HACK HACK
        self.points_label.setFont(QtGui.QFont("Arial", 12))
        self.points_label.setPos(self.window_width - 255, 10)  # Move the label to the left by 15 pixels
        self.points_label.setZValue(2)  # Increase Z-value to ensure it's on top
        self.scene.addItem(self.points_label)

        self.points_value_label = QtWidgets.QGraphicsTextItem("0")
        self.points_value_label.setDefaultTextColor(QtGui.QColor(255, 255, 255))  # Set font color to black HACK HACK
        self.points_value_label.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        self.points_value_label.setPos(self.window_width - 95, 10)
        self.points_value_label.setZValue(2)  # Increase Z-value to ensure it's on top
        self.scene.addItem(self.points_value_label)

    def check_neurogenesis(self, state):
        """Handle neuron creation, with special debug mode that bypasses all checks"""
        current_time = time.time()
        
        # DEBUG MODE: Bypass all checks and force creation
        if state.get('_debug_forced_neurogenesis', False):
            # Create unique name with timestamp
            new_name = f"debug_neuron_{int(current_time)}"
            
            # Calculate position near center of existing network
            if self.neuron_positions:
                center_x = sum(pos[0] for pos in self.neuron_positions.values()) / len(self.neuron_positions)
                center_y = sum(pos[1] for pos in self.neuron_positions.values()) / len(self.neuron_positions)
            else:
                center_x, center_y = 600, 300  # Default center position
            
            # Add some randomness to the position
            self.neuron_positions[new_name] = (
                center_x + random.randint(-100, 100),
                center_y + random.randint(-100, 100)
            )
            
            # Initialize with high activation
            self.state[new_name] = 80
            self.state_colors[new_name] = (150, 200, 255)  # Light blue color
            
            # Create connections to all existing neurons
            for existing in self.neuron_positions:
                if existing != new_name:
                    # Create bidirectional connections with random weights
                    self.weights[(new_name, existing)] = random.uniform(-0.8, 0.8)
                    self.weights[(existing, new_name)] = random.uniform(-0.8, 0.8)
            
            # Update neurogenesis tracking
            if 'new_neurons' not in self.neurogenesis_data:
                self.neurogenesis_data['new_neurons'] = []
            self.neurogenesis_data['new_neurons'].append(new_name)
            self.neurogenesis_data['last_neuron_time'] = current_time
            
            # Debug output
            print(f"DEBUG: Created neuron '{new_name}' at {self.neuron_positions[new_name]}")
            print(f"New connections: {[(k,v) for k,v in self.weights.items() if new_name in k]}")
            
            self.update()  # Force redraw
            return True

        # NORMAL OPERATION (only runs if debug flag is False)
        if current_time - self.neurogenesis_data.get('last_neuron_time', 0) > self.neurogenesis_config['cooldown']:
            created = False
            
            # Novelty-based neurogenesis
            if state.get('novelty_exposure', 0) > self.neurogenesis_config['novelty_threshold']:
                self._create_neuron_internal('novelty', state)
                created = True
            
            # Stress-based neurogenesis
            if state.get('sustained_stress', 0) > self.neurogenesis_config['stress_threshold']:
                self._create_neuron_internal('stress', state)
                created = True
            
            # Reward-based neurogenesis
            if state.get('recent_rewards', 0) > self.neurogenesis_config['reward_threshold']:
                self._create_neuron_internal('reward', state)
                created = True
                
            return created
        
        return False
    
    def _create_neuron(self, neuron_type, trigger_data):
        """Internal neuron creation method for normal operation"""
        base_name = {
            'novelty': 'novel',
            'stress': 'defense', 
            'reward': 'reward'
        }[neuron_type]
        
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        
        # Position near most active connected neuron
        active_neurons = sorted(
            [(k, v) for k, v in self.state.items() if isinstance(v, (int, float))],
            key=lambda x: x[1],
            reverse=True
        )
        
        if active_neurons:
            base_x, base_y = self.neuron_positions[active_neurons[0][0]]
        else:
            base_x, base_y = 600, 300  # Default position
        
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )
        
        # Initialize state
        self.state[new_name] = 50  # Neutral activation
        self.state_colors[new_name] = {
            'novelty': (255, 255, 150),
            'stress': (255, 150, 150),
            'reward': (150, 255, 150)
        }[neuron_type]
        
        # Create default connections
        default_weights = {
            'novelty': {'curiosity': 0.6, 'anxiety': -0.4},
            'stress': {'anxiety': -0.7, 'happiness': 0.3},
            'reward': {'satisfaction': 0.8, 'happiness': 0.5}
        }
        
        for target, weight in default_weights[neuron_type].items():
            self.weights[(new_name, target)] = weight
            self.weights[(target, new_name)] = weight * 0.5  # Weaker reciprocal
        
        # Update tracking
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        
        return new_name
    
    def trigger_neurogenesis(self):
        """Guaranteed neuron creation with validation"""
        try:
            if not hasattr(self, 'squid_brain_window'):
                raise ValueError("Brain window not initialized")
                
            # Get current neuron count and names
            brain = self.squid_brain_window.brain_widget
            prev_count = len(brain.neuron_positions)
            prev_neurons = set(brain.neuron_positions.keys())
            
            # Create forced state with debug flag
            forced_state = {
                "_debug_forced_neurogenesis": True,
                "personality": getattr(self.tamagotchi_logic.squid, 'personality', None)
            }
            
            # Force update - call update_state directly to ensure it runs
            brain.update_state(forced_state)
            
            # Verify creation
            new_count = len(brain.neuron_positions)
            new_neurons = set(brain.neuron_positions.keys()) - prev_neurons
            
            if not new_neurons:
                # If no new neurons, try forcing it again with more debug info
                print("First attempt failed, trying again with debug info:")
                print(f"Before state: {brain.state}")
                print(f"Before positions: {brain.neuron_positions}")
                
                # Force create a neuron directly
                new_name = f"forced_{time.time()}"
                brain.neuron_positions[new_name] = (600, 300)
                brain.state[new_name] = 50
                brain.state_colors[new_name] = (255, 150, 150)
                brain.update()
                
                new_neurons = set(brain.neuron_positions.keys()) - prev_neurons
                if not new_neurons:
                    raise RuntimeError(
                        "Neurogenesis completely failed. Check:\n"
                        f"- Previous count: {prev_count}\n"
                        f"- New count: {len(brain.neuron_positions)}\n"
                        f"- State keys: {brain.state.keys()}\n"
                        f"- Position keys: {brain.neuron_positions.keys()}\n"
                        f"- Debug flag was: {forced_state['_debug_forced_neurogenesis']}"
                    )
            
            neuron_name = new_neurons.pop()
            self.show_message(f"Created neuron: {neuron_name}")
            print(f"Successfully created neuron: {neuron_name}")
            print(f"New neuron state: {brain.state[neuron_name]}")
            print(f"New neuron position: {brain.neuron_positions[neuron_name]}")
            
        except Exception as e:
            self.show_message(f"Neurogenesis Error: {str(e)}")
            print(f"NEUROGENESIS FAILURE:\n{traceback.format_exc()}")
            print("CURRENT NETWORK STATE:")
            print(f"State: {self.squid_brain_window.brain_widget.state}")
            print(f"Positions: {self.squid_brain_window.brain_widget.neuron_positions}")
            print(f"Weights: {list(self.squid_brain_window.brain_widget.weights.items())[:5]}...")

    def toggle_decoration_window(self, checked):
        if checked:
            self.decoration_window.show()
            self.decoration_window.activateWindow()
        else:
            self.decoration_window.hide()

    def handle_window_resize(self, event):
        self.window_width = event.size().width()
        self.window_height = event.size().height()
        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
        self.cleanliness_overlay.setRect(50, 50, self.window_width - 100, self.window_height - 100)

        self.feeding_message.setPos(0, self.window_height - 75)
        self.feeding_message.setTextWidth(self.window_width)

        self.points_label.setPos(self.window_width - 265, 10)  # Move the label to the left by 15 pixels
        self.points_value_label.setPos(self.window_width - 95, 10)

    def show_message(self, message):
        # Remove any existing message items
        for item in self.scene.items():
            if isinstance(item, QtWidgets.QGraphicsTextItem):
                self.scene.removeItem(item)

        # Create a new QGraphicsTextItem for the message
        self.message_item = QtWidgets.QGraphicsTextItem(message)
        self.message_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))  # White text
        self.message_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.message_item.setPos(0, self.window_height - 75)  # Position the message higher
        self.message_item.setTextWidth(self.window_width)
        self.message_item.setHtml(f'<div style="text-align: center; background-color: #000000; padding: 5px;">{message}</div>')
        self.message_item.setZValue(10)  # Ensure the message is on top
        self.message_item.setOpacity(1)

        # Add the new message item to the scene
        self.scene.addItem(self.message_item)

        # Fade out the message after 8 seconds
        self.fade_out_animation = QtCore.QPropertyAnimation(self.message_item, b"opacity")
        self.fade_out_animation.setDuration(8000)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(lambda: self.scene.removeItem(self.message_item))
        self.fade_out_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def update_points(self, points):
        self.points_value_label.setPlainText(str(points))

    def get_nearby_decorations(self, x, y, radius=100):
        nearby_decorations = []
        for item in self.scene.items():
            if isinstance(item, ResizablePixmapItem):
                item_center = item.sceneBoundingRect().center()
                distance = ((item_center.x() - x) ** 2 + (item_center.y() - y) ** 2) ** 0.5
                if distance <= radius:
                    nearby_decorations.append(item)
        return nearby_decorations

    def move_decoration(self, decoration, dx):
        current_pos = decoration.pos()
        new_x = current_pos.x() + dx
        
        # Ensure the decoration stays within the scene boundaries
        scene_rect = self.scene.sceneRect()
        new_x = max(scene_rect.left(), min(new_x, scene_rect.right() - decoration.boundingRect().width()))
        
        decoration.setPos(new_x, current_pos.y())

        # Create a small animation to make the movement smoother
        #animation = QtCore.QPropertyAnimation(decoration, b"pos")
        #animation.setDuration(300)  # 300 ms duration
        #animation.setStartValue(current_pos)
        #animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
        #animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        #animation.start()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            file_path = url.toLocalFile()
            pixmap = QtGui.QPixmap(file_path)
            if not pixmap.isNull():
                filename = os.path.basename(file_path)
                item = ResizablePixmapItem(pixmap, file_path)

                # Set fixed size for Rock01 and Rock02
                if filename.lower().startswith(('rock01', 'rock02')):
                    item.pixmap_item.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
                    item.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
                    item.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
                    item.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
                elif filename.startswith('st_'):
                    # Don't scale items starting with 'st_'
                    scale_factor = 1.0
                else:
                    # Generate a random scale factor between 0.5 and 2 for other decorations
                    scale_factor = random.uniform(0.75, 2)
                    item.setScale(scale_factor)

                pos = self.view.mapToScene(event.pos())
                item.setPos(pos)
                self.scene.addItem(item)
                self.decoration_window.add_decoration_item(item)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_selected_items()

    def delete_selected_items(self):
        for item in self.scene.selectedItems():
            if isinstance(item, ResizablePixmapItem):
                self.scene.removeItem(item)
        self.scene.update()

    def setup_menu_bar(self):
        self.menu_bar = self.window.menuBar()

        # File Menu
        file_menu = self.menu_bar.addMenu('File')
        self.new_game_action = QtWidgets.QAction('New Game', self.window)
        self.load_action = QtWidgets.QAction('Load Game', self.window)
        self.save_action = QtWidgets.QAction('Save Game', self.window)
        file_menu.addAction(self.new_game_action)
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.save_action)

        # View Menu
        view_menu = self.menu_bar.addMenu('View')
        self.stats_window_action = QtWidgets.QAction('Statistics', self.window)
        self.stats_window_action.triggered.connect(self.toggle_statistics_window)
        view_menu.addAction(self.stats_window_action)

        self.decorations_action = QtWidgets.QAction('Decorations', self.window)
        self.decorations_action.setCheckable(True)
        self.decorations_action.triggered.connect(self.toggle_decoration_window)
        view_menu.addAction(self.decorations_action)

        self.brain_action = QtWidgets.QAction('Toggle Brain View', self.window)
        self.brain_action.setCheckable(True)
        self.brain_action.triggered.connect(self.toggle_brain_window)
        view_menu.addAction(self.brain_action)

        self.inspector_action = QtWidgets.QAction('Neuron Inspector', self.window)
        self.inspector_action.triggered.connect(self.show_neuron_inspector)
        view_menu.addAction(self.inspector_action)

        # Speed Menu
        speed_menu = self.menu_bar.addMenu('Speed')
        
        self.pause_action = QtWidgets.QAction('Pause', self.window)
        self.pause_action.setCheckable(True)
        self.pause_action.triggered.connect(lambda: self.set_simulation_speed(0))
        speed_menu.addAction(self.pause_action)
        
        self.normal_speed_action = QtWidgets.QAction('Normal Speed', self.window)
        self.normal_speed_action.setCheckable(True)
        self.normal_speed_action.triggered.connect(lambda: self.set_simulation_speed(1))
        speed_menu.addAction(self.normal_speed_action)
        
        self.fast_speed_action = QtWidgets.QAction('Fast Speed', self.window)
        self.fast_speed_action.setCheckable(True)
        self.fast_speed_action.triggered.connect(lambda: self.set_simulation_speed(2))
        speed_menu.addAction(self.fast_speed_action)
        
        self.very_fast_speed_action = QtWidgets.QAction('Very Fast', self.window)
        self.very_fast_speed_action.setCheckable(True)
        self.very_fast_speed_action.triggered.connect(lambda: self.set_simulation_speed(3))
        speed_menu.addAction(self.very_fast_speed_action)

        # Create an action group for the speed menu to make them mutually exclusive
        self.speed_action_group = QtWidgets.QActionGroup(self.window)
        self.speed_action_group.addAction(self.pause_action)
        self.speed_action_group.addAction(self.normal_speed_action)
        self.speed_action_group.addAction(self.fast_speed_action)
        self.speed_action_group.addAction(self.very_fast_speed_action)

        # Actions Menu
        actions_menu = self.menu_bar.addMenu('Actions')
        self.feed_action = QtWidgets.QAction('Feed', self.window)
        actions_menu.addAction(self.feed_action)

        self.clean_action = QtWidgets.QAction('Clean', self.window)
        actions_menu.addAction(self.clean_action)

        self.medicine_action = QtWidgets.QAction('Medicine', self.window)
        actions_menu.addAction(self.medicine_action)

        # Debug Menu
        debug_menu = self.menu_bar.addMenu('Debug')
        
        # Debug Mode Toggle
        self.debug_action = QtWidgets.QAction('Toggle Debug Mode', self.window)
        self.debug_action.setCheckable(True)
        self.debug_action.triggered.connect(self.toggle_debug_mode)
        debug_menu.addAction(self.debug_action)

        # View Cone Toggle
        self.view_cone_action = QtWidgets.QAction('Toggle View Cone', self.window)
        self.view_cone_action.setCheckable(True)
        if hasattr(self.tamagotchi_logic, 'connect_view_cone_action'):
            self.view_cone_action.triggered.connect(self.tamagotchi_logic.connect_view_cone_action)
        debug_menu.addAction(self.view_cone_action)

        # Rock Test Action
        self.rock_test_action = QtWidgets.QAction('Test Rock Interaction', self.window)
        self.rock_test_action.setEnabled(False)  # Disabled by default
        if hasattr(self.tamagotchi_logic, 'test_rock_interaction'):
            self.rock_test_action.triggered.connect(self.tamagotchi_logic.test_rock_interaction)
        debug_menu.addAction(self.rock_test_action)

        # Neurogenesis Action
        self.neurogenesis_action = QtWidgets.QAction('Trigger Neurogenesis', self.window)
        self.neurogenesis_action.setEnabled(False)  # Disabled by default
        if hasattr(self.tamagotchi_logic, 'trigger_neurogenesis'):
            self.neurogenesis_action.triggered.connect(self.trigger_neurogenesis)
        debug_menu.addAction(self.neurogenesis_action)

        # Add to debug menu
        self.rock_test_action = QtWidgets.QAction('+ Rock test', self.window)
        self.rock_test_action.triggered.connect(self.trigger_rock_test)
        debug_menu.addAction(self.rock_test_action)

        # Disabled RPS Game Action (commented out)
        # self.rps_game_action = QtWidgets.QAction('Play Rock, Paper, Scissors', self.window)
        # actions_menu.addAction(self.rps_game_action)
        # self.rps_game_action.triggered.connect(self.start_rps_game)

    def set_simulation_speed(self, speed):
        """Set the simulation speed (0 = paused, 1 = normal, 2 = fast, 3 = very fast)"""
        if hasattr(self, 'tamagotchi_logic'):
            self.tamagotchi_logic.set_simulation_speed(speed)
            
            # Update the menu check states
            self.pause_action.setChecked(speed == 0)
            self.normal_speed_action.setChecked(speed == 1)
            self.fast_speed_action.setChecked(speed == 2)
            self.very_fast_speed_action.setChecked(speed == 3)
            
            speed_names = ["Paused", "Normal", "Fast", "Very Fast"]
            self.show_message(f"Simulation speed set to {speed_names[speed]}")
        else:
            self.show_message("Game logic not initialized!")

    def toggle_debug_mode(self):
        """Toggle debug mode state"""
        if hasattr(self, 'tamagotchi_logic'):
            self.tamagotchi_logic.debug_mode = not self.tamagotchi_logic.debug_mode
            self.debug_action.setChecked(self.tamagotchi_logic.debug_mode)
            
            # Enable/disable debug-specific actions
            if hasattr(self, 'rock_test_action'):
                self.rock_test_action.setEnabled(self.tamagotchi_logic.debug_mode)
            if hasattr(self, 'neurogenesis_action'):
                self.neurogenesis_action.setEnabled(self.tamagotchi_logic.debug_mode)
            
            print(f"Debug mode {'enabled' if self.tamagotchi_logic.debug_mode else 'disabled'}")

    def trigger_rock_test(self):
        """Trigger rock test from UI using the interaction manager"""
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            self.show_message("Rock interaction system not initialized!")
            return
                
        # Find all valid rocks in the scene using the interaction manager's checker
        rocks = [item for item in self.scene.items() 
                if isinstance(item, ResizablePixmapItem) 
                and self.tamagotchi_logic.rock_interaction.is_valid_rock(item)]
        
        if not rocks:
            self.show_message("No rocks found in the tank!")
            return
            
        if not hasattr(self.tamagotchi_logic, 'squid'):
            self.show_message("Squid not initialized!")
            return
            
        # Find nearest rock to squid
        nearest_rock = min(rocks, key=lambda r: 
            math.hypot(
                r.sceneBoundingRect().center().x() - self.tamagotchi_logic.squid.squid_x,
                r.sceneBoundingRect().center().y() - self.tamagotchi_logic.squid.squid_y
            )
        )
        
        # Start the test through the interaction manager
        self.tamagotchi_logic.rock_interaction.start_rock_test(nearest_rock)
        
        # Show status message
        self.show_message("Rock test initiated")

    def start_rps_game(self):
        if hasattr(self, 'tamagotchi_logic'):
            self.tamagotchi_logic.start_rps_game()
        else:
            print("TamagotchiLogic not initialized")

    def test_rock_interaction(self):
        """Trigger rock interaction test from debug menu"""
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if not self.tamagotchi_logic.debug_mode:
                self.show_message("Enable debug mode first!")
                return
                
            print("[DEBUG] Starting rock interaction test from menu...")
            self.tamagotchi_logic.test_rock_interaction()
        else:
            print("TamagotchiLogic not available for rock testing")
            self.show_message("Game logic not initialized!")

    def show_neuron_inspector(self):
        if not self.squid_brain_window:
            self.squid_brain_window = SquidBrainWindow(self.tamagotchi_logic, self.debug_mode)
            
        if not self.neuron_inspector:
            self.neuron_inspector = NeuronInspector(self.squid_brain_window, self.window)
            
        self.neuron_inspector.show()
        self.neuron_inspector.raise_()
        self.neuron_inspector.update_neuron_list()

    def toggle_statistics_window(self):
        if self.statistics_window is None:
            self.create_statistics_window()

        if self.statistics_window is not None:
            if self.statistics_window.isVisible():
                self.statistics_window.hide()
            else:
                self.statistics_window.show()
        else:
            print("Failed to create statistics window")

    def create_statistics_window(self):
        if hasattr(self, 'tamagotchi_logic'):
            if not hasattr(self.tamagotchi_logic, 'statistics_window'):
                self.tamagotchi_logic.statistics_window = StatisticsWindow(self.tamagotchi_logic.squid)
            self.statistics_window = self.tamagotchi_logic.statistics_window
        else:
            print("TamagotchiLogic not initialized")

    def toggle_brain_window(self, checked):
        if checked:
            self.squid_brain_window.show()
        else:
            self.squid_brain_window.hide()

    def connect_view_cone_action(self, toggle_function):
        self.view_cone_action.triggered.connect(toggle_function)

    def get_decorations_data(self):
        decorations_data = []
        for item in self.scene.items():
            if isinstance(item, ResizablePixmapItem):
                pixmap = item.pixmap()
                buffer = QtCore.QBuffer()
                buffer.open(QtCore.QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                pixmap_data = buffer.data().toBase64().data().decode()
                decorations_data.append({
                    'pixmap_data': pixmap_data,
                    'pos': (item.pos().x(), item.pos().y()),  # Convert QPointF to tuple
                    'scale': item.scale()
                })
        return decorations_data

    def load_decorations_data(self, decorations_data):
        for decoration_data in decorations_data:
            pixmap_data = decoration_data['pixmap_data']
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(QtCore.QByteArray.fromBase64(pixmap_data.encode()))
            pos = QtCore.QPointF(decoration_data['pos'][0], decoration_data['pos'][1])
            scale = decoration_data['scale']
            filename = decoration_data['filename']
            item = ResizablePixmapItem(pixmap, filename)
            item.setPos(pos)
            item.setScale(scale)
            self.scene.addItem(item)

    def get_pixmap_data(self, item):
        pixmap = item.pixmap()
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        pixmap_data = buffer.data().toBase64().data().decode()
        return pixmap_data

    def closeEvent(self, event):
        # Instead of closing, just hide the window
        event.ignore()
        self.hide()
        # Uncheck the menu item
        if hasattr(self.parent(), 'decorations_action'):
            self.parent().decorations_action.setChecked(False)

    def get_rock_items(self):
        """Return all rock items in the scene"""
        return [item for item in self.scene.items() 
                if isinstance(item, ResizablePixmapItem) 
                and getattr(item, 'can_be_picked_up', False)]
    
    def highlight_rock(self, rock, highlight=True):
        """Visually highlight a rock"""
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(255, 255, 0))  # Yellow highlight
        effect.setStrength(0.7 if highlight else 0.0)
        rock.setGraphicsEffect(effect if highlight else None)

    def reset_all_rock_states(self):
        """Reset all rocks to default state"""
        for rock in self.get_rock_items():
            rock.is_being_carried = False
            self.highlight_rock(rock, False)

class NeuronInspector(QtWidgets.QDialog):
    def __init__(self, brain_window, parent=None):
        super().__init__(parent)
        self.brain_window = brain_window
        self.setWindowTitle("Neuron Inspector")
        self.setFixedSize(400, 400)
        
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Neuron selector
        self.neuron_combo = QtWidgets.QComboBox()
        layout.addWidget(self.neuron_combo)
        
        # Info display
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)
        
        # Connection list
        self.connections_list = QtWidgets.QListWidget()
        layout.addWidget(self.connections_list)
        
        # Refresh button
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.update_info)
        layout.addWidget(self.refresh_btn)
        
        self.update_neuron_list()

    def update_neuron_list(self):
        if hasattr(self.brain_window, 'brain_widget'):
            brain = self.brain_window.brain_widget
            self.neuron_combo.clear()
            self.neuron_combo.addItems(sorted(brain.neuron_positions.keys()))
            self.update_info()

    def update_info(self):
        if not hasattr(self.brain_window, 'brain_widget'):
            return
            
        brain = self.brain_window.brain_widget
        neuron = self.neuron_combo.currentText()
        
        if neuron not in brain.neuron_positions:
            return
            
        pos = brain.neuron_positions[neuron]
        activation = brain.state.get(neuron, 0)
        
        info = f"""<b>{neuron}</b>
Position: ({pos[0]:.1f}, {pos[1]:.1f})
Activation: {activation:.1f}
Type: {'Original' if neuron in getattr(brain, 'original_neuron_positions', {}) else 'New'}"""
        
        self.info_text.setHtml(info)
        self.connections_list.clear()
        
        for (src, dst), weight in brain.weights.items():
            if src == neuron or dst == neuron:
                item = QtWidgets.QListWidgetItem(f"{src} → {dst}: {weight:.2f}")
                item.setForeground(QtGui.QColor("green") if weight > 0 else QtGui.QColor("red"))
                self.connections_list.addItem(item)