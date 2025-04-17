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
from .brain_tool import SquidBrainWindow
from .statistics_window import StatisticsWindow
from .plugin_manager_dialog import PluginManagerDialog

class DecorationItem(QtWidgets.QLabel):
    def __init__(self, pixmap, filename):
        super().__init__()
        self.setPixmap(pixmap.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.filename = filename
        self.setFixedSize(128, 128)
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


class ResizablePixmapItem(QtWidgets.QGraphicsPixmapItem, QObject):
    def __init__(self, pixmap=None, filename=None, category=None, parent=None):
        QtWidgets.QGraphicsPixmapItem.__init__(self, parent)
        QObject.__init__(self)

        self._is_pause_message = None
        self.original_pixmap = pixmap

        if pixmap:
            scaled_pixmap = pixmap.scaled(128, 128, 
                                    QtCore.Qt.KeepAspectRatio, 
                                    QtCore.Qt.SmoothTransformation)
            self.setPixmap(scaled_pixmap)
        
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable |
                    QtWidgets.QGraphicsItem.ItemIsSelectable |
                    QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)

        self.resize_handle = None
        self.filename = filename
        
        self.stat_multipliers = {'happiness': 1}
        self.category = category if category else 'generic'  # Use provided category or default to 'generic'

        if filename:
            multipliers, detected_category = self.get_decoration_info()
            if multipliers:
                self.stat_multipliers = multipliers
            if 'rock' in filename.lower():
                self.category = 'rock'
            elif 'poop' in filename.lower():
                self.category = 'poop'
            else:
                self.category = detected_category if detected_category else self.category

        self.can_be_picked_up = filename and ('rock' in filename.lower() or 'poop' in filename.lower())
        self.is_being_carried = False
        self.original_scale = 1.0

    def boundingRect(self):
        return super().boundingRect().adjusted(0, 0, 20, 20)



    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 255), 2))
            painter.drawRect(self.boundingRect())
            
            # Draw resize handle at bottom right
            handle_pos = self.boundingRect().bottomRight() - QtCore.QPointF(20, 20)
            handle_rect = QtCore.QRectF(handle_pos, QtCore.QSizeF(20, 20))
            painter.fillRect(handle_rect, QtGui.QColor(0, 0, 255))


    def mousePressEvent(self, event):
        # Check if resize handle is clicked
        pos = event.pos()
        handle_rect = QtCore.QRectF(
            self.boundingRect().bottomRight() - QtCore.QPointF(20, 20), 
            QtCore.QSizeF(20, 20)
        )
        
        if handle_rect.contains(pos):
            # Resize mode
            self.resize_handle = pos
            event.accept()
        else:
            # Normal move mode
            self.resize_handle = None
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_handle is not None and self.original_pixmap:
            # Calculate new size based on mouse movement
            start_pos = self.resize_handle
            current_pos = event.pos()
            
            # Calculate width and height
            width = abs(current_pos.x() - start_pos.x())
            height = abs(current_pos.y() - start_pos.y())
            
            # Maintain aspect ratio
            aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()
            
            if width / height > aspect_ratio:
                width = height * aspect_ratio
            else:
                height = width / aspect_ratio
            
            # Scale pixmap
            scaled_pixmap = self.original_pixmap.scaled(
                int(width), int(height), 
                QtCore.Qt.KeepAspectRatio, 
                QtCore.Qt.SmoothTransformation
            )
            
            # Set the scaled pixmap
            self.setPixmap(scaled_pixmap)
            
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # Reset resize handle
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
    def __init__(self, window, debug_mode=False):
        self.window = window
        self.tamagotchi_logic = None
        self.debug_mode = debug_mode 
        
        # Initialize window properties first
        self.window.setMinimumSize(1280, 900)
        self.window_width = 1280
        self.window_height = 900
        self.window.setWindowTitle("Dosidicus")
        self.window.resize(self.window_width, self.window_height)

        # Create scene and view before any UI elements
        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.window.setCentralWidget(self.view)

        # Now setup UI elements that depend on the scene
        self.setup_ui_elements()
        
        # Setup menu bar and other components
        self.setup_menu_bar()
        self.neuron_inspector = None
        self.squid_brain_window = None

        # Add debug text item to the scene
        self.debug_text = QtWidgets.QGraphicsTextItem("Debug")
        self.debug_text.setDefaultTextColor(QtGui.QColor("#a9a9a9"))
        font = QtGui.QFont()
        font.setPointSize(20)
        self.debug_text.setFont(font)
        self.debug_text.setRotation(-90)
        self.debug_text.setPos(75, 75)
        self.debug_text.setZValue(100)
        self.debug_text.setVisible(self.debug_mode)
        self.scene.addItem(self.debug_text)

        # Initialize decoration window
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
        
        # Initialize status bar if available
        try:
            from status_bar_component import StatusBarComponent
            self.status_bar = StatusBarComponent(self.window)
        except ImportError:
            print("Status bar component not available, skipping")

        # Optimize animations
        self.optimize_animations()

    def optimize_animations(self):
        self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)  # Better for moving items
        self.view.setCacheMode(QtWidgets.QGraphicsView.CacheBackground)

    def set_tamagotchi_logic(self, logic):
        self.tamagotchi_logic = logic
        if hasattr(logic, 'debug_mode'):
            # Sync the debug mode with the logic
            self.debug_mode = logic.debug_mode
            self.debug_action.setChecked(self.debug_mode)
            self.debug_text.setVisible(self.debug_mode)
        
        # Create multiplayer menu here too
        self.create_multiplayer_menu()


    def setup_plugin_menu(self, plugin_manager):
        #print("DEBUG: Setting up plugin menu")
        
        # Create plugins menu if it doesn't exist
        if not hasattr(self, 'plugins_menu'):
            self.plugins_menu = self.menu_bar.addMenu('Plugins')
        
        # Clear existing actions to prevent duplicates
        self.plugins_menu.clear()
        
        # Add plugin manager action
        self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
        self.plugin_manager_action.triggered.connect(
            lambda: self.show_plugin_manager(plugin_manager)
        )
        self.plugins_menu.addAction(self.plugin_manager_action)
        
        # Add separator
        self.plugins_menu.addSeparator()
        
        # Create or find Multiplayer menu
        multiplayer_menu = None
        multiplayer_loaded = False
        
        # Check if plugin manager exists
        if plugin_manager:
            # Check if multiplayer plugin is loaded
            multiplayer_loaded = 'multiplayer' in plugin_manager.plugins
            
            # Print all loaded plugins for debugging
            #print(f"DEBUG: Loaded plugins: {plugin_manager.get_loaded_plugins()}")
        
        # Look for existing Multiplayer menu
        for action in self.menu_bar.actions():
            if action.text() == '&Multiplayer':
                multiplayer_menu = action.menu()
                break
        
        # Create Multiplayer menu if it doesn't exist and plugin is loaded
        if multiplayer_loaded and not multiplayer_menu:
            #print("Creating Multiplayer menu")
            multiplayer_menu = self.menu_bar.addMenu('&Multiplayer')
        # Remove menu if plugin isn't loaded but menu exists
        elif not multiplayer_loaded and multiplayer_menu:
            #print("Removing Multiplayer menu - plugin not loaded")
            self.menu_bar.removeAction(multiplayer_menu.menuAction())
            multiplayer_menu = None
        
        # Skip further setup if multiplayer isn't loaded or menu doesn't exist
        if not multiplayer_loaded or not multiplayer_menu:
            print("Skipping multiplayer menu setup - plugin not loaded or menu doesn't exist")
            return
        
        # Clear existing menu items
        multiplayer_menu.clear()
        
        # Get multiplayer plugin instance
        multiplayer_plugin_instance = None
        if plugin_manager and 'multiplayer' in plugin_manager.plugins:
            multiplayer_plugin_instance = plugin_manager.plugins['multiplayer'].get('instance')
        
        # Check if plugin is enabled - this is where we check the current status
        multiplayer_enabled = 'multiplayer' in plugin_manager.get_enabled_plugins()
        
        # Add toggle action for enabling/disabling
        toggle_action = QtWidgets.QAction("Enable Multiplayer", self.window)
        toggle_action.setCheckable(True)
        toggle_action.setChecked(multiplayer_enabled)  # Set based on actual enabled state
        toggle_action.triggered.connect(
            lambda checked: self.toggle_plugin('multiplayer', checked)
        )
        multiplayer_menu.addAction(toggle_action)
        
        # Add separator
        multiplayer_menu.addSeparator()
        
        # Add additional menu items if plugin is enabled
        if multiplayer_enabled and multiplayer_plugin_instance and hasattr(multiplayer_plugin_instance, 'register_menu_actions'):
            try:
                # Call the method to register additional actions
                multiplayer_plugin_instance.register_menu_actions(self, multiplayer_menu)
            except Exception as e:
                print(f"Error registering menu actions for multiplayer: {e}")
        
        print("        ")

    def create_multiplayer_menu(self):
        """Create multiplayer menu only if the plugin is loaded and enabled"""
        # This function is now handled in setup_plugin_menu
        # Kept for backward compatibility
        if hasattr(self.tamagotchi_logic, 'plugin_manager'):
            self.setup_plugin_menu(self.tamagotchi_logic.plugin_manager)
        else:
            print("WARNING: create_multiplayer_menu called but no plugin_manager available")

    def apply_plugin_menu_registrations(self, plugin_manager):
        """Apply menu registrations from plugins"""
        if not hasattr(plugin_manager, 'get_menu_registrations'):
            print("Plugin manager doesn't support menu registrations")
            return
        
        # Get all menu registrations
        registrations = plugin_manager.get_menu_registrations()
        
        # Process each plugin's registrations
        for plugin_name, actions in registrations.items():
            # Skip if plugin is not enabled
            if plugin_name not in plugin_manager.get_enabled_plugins():
                continue
            
            # Group actions by menu name
            menus = {}
            for action in actions:
                menu_name = action['menu_name']
                if menu_name not in menus:
                    menus[menu_name] = []
                menus[menu_name].append(action)
            
            # Create or find each menu and add actions
            for menu_name, menu_actions in menus.items():
                # Check if menu already exists
                menu = None
                for action in self.menu_bar.actions():
                    if action.text() == menu_name:
                        menu = action.menu()
                        break
                
                # Create menu if it doesn't exist
                if not menu:
                    menu = QtWidgets.QMenu(menu_name, self.window)
                    self.menu_bar.addMenu(menu)
                
                # Add actions to menu
                for action_data in menu_actions:
                    action = QtWidgets.QAction(action_data['action_name'], 
                                            action_data.get('parent', self.window))
                    callback = action_data['callback']
                    if callback:
                        action.triggered.connect(callback)
                    menu.addAction(action)
        
        print("Applied all plugin menu registrations")

    def toggle_plugin(self, plugin_name, enable):
        """Toggle a plugin on/off"""
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'plugin_manager'):
            pm = self.tamagotchi_logic.plugin_manager
            if enable:
                # Try to enable plugin - if it has a specific enable method, use that
                if plugin_name in pm.plugins and 'instance' in pm.plugins[plugin_name]:
                    plugin_instance = pm.plugins[plugin_name]['instance']
                    
                    # Make sure plugin has the plugin manager reference
                    if plugin_instance and not hasattr(plugin_instance, 'plugin_manager') or plugin_instance.plugin_manager is None:
                        plugin_instance.plugin_manager = pm
                        print(f"Assigned plugin manager to {plugin_name} plugin")
                    
                    # Also make sure it has tamagotchi_logic reference if we have it
                    if plugin_instance and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                        plugin_instance.tamagotchi_logic = self.tamagotchi_logic
                        print(f"Assigned tamagotchi_logic to {plugin_name} plugin")
                    
                    if plugin_instance and hasattr(plugin_instance, 'enable'):
                        print(f"Calling custom enable method for {plugin_name}")
                        success = plugin_instance.enable()
                        if success:
                            pm.enable_plugin(plugin_name)
                    else:
                        success = pm.enable_plugin(plugin_name)
                    
                    # Show multiplayer menu if appropriate
                    if success and plugin_name.lower() == 'multiplayer':
                        self.setup_plugin_menu(pm)
                else:
                    pm.enable_plugin(plugin_name)
            else:
                pm.disable_plugin(plugin_name)
                
                # Hide multiplayer menu if appropriate
                if plugin_name.lower() == 'multiplayer':
                    self.setup_plugin_menu(pm)
                
            # Refresh the plugin menu
            self.setup_plugin_menu(pm)

    def show_plugin_manager(self, plugin_manager):
        """Show the plugin manager dialog"""
        dialog = PluginManagerDialog(plugin_manager, self.window)
        dialog.exec_()
        # Refresh the plugin menu after changes
        self.setup_plugin_menu(plugin_manager)

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
        self.feeding_message.setPos(0, self.window_height - 75)
        self.feeding_message.setTextWidth(self.window_width)
        self.feeding_message.setHtml('<div style="text-align: center;">Squid requires feeding</div>')
        self.feeding_message.setOpacity(0)
        self.scene.addItem(self.feeding_message)

        # Create points labels
        self.points_label = QtWidgets.QGraphicsTextItem("Points:")
        self.points_label.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        self.points_label.setFont(QtGui.QFont("Arial", 12))
        self.points_label.setPos(self.window_width - 255, 10)
        self.points_label.setZValue(2)
        self.scene.addItem(self.points_label)

        self.points_value_label = QtWidgets.QGraphicsTextItem("0")
        self.points_value_label.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        self.points_value_label.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        self.points_value_label.setPos(self.window_width - 95, 10)
        self.points_value_label.setZValue(2)
        self.scene.addItem(self.points_value_label)

        # Check if tamagotchi_logic exists before accessing debug_mode
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.debug_text.setVisible(getattr(self.tamagotchi_logic, 'debug_mode', False))

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

    def show_pause_message(self, is_paused):
        # Remove existing pause items
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                self.scene.removeItem(item)

        # Get current window dimensions
        win_width = self.window_width
        win_height = self.window_height

        if is_paused:
            # Background rectangle 200 pixels wider than the window, 250 pixels tall
            background = QtWidgets.QGraphicsRectItem(
                -200,  # Start 200 pixels left of the window
                (win_height - 250) / 2,  # Vertically center the 250-pixel tall rectangle
                win_width + 400,  # Total width is window width + 400 (200 on each side)
                250  # Fixed height of 250 pixels
            )
            background.setBrush(QtGui.QColor(0, 0, 0, 180))
            background.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            background.setZValue(1000)
            # Store the original rectangle dimensions to prevent resizing
            background.original_rect = background.rect()
            setattr(background, '_is_pause_message', True)
            self.scene.addItem(background)

            # Main pause text
            pause_text = self.scene.addText("p a u s e d", QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
            pause_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            pause_text.setZValue(1002)
            setattr(pause_text, '_is_pause_message', True)
            
            # Center text using view coordinates
            text_rect = pause_text.boundingRect()
            pause_text_x = (win_width - text_rect.width()) / 2
            pause_text_y = (win_height - text_rect.height()) / 2 - 30
            pause_text.setPos(pause_text_x, pause_text_y)

            # Subtext
            sub_text = self.scene.addText("Use 'Speed' menu to unpause", QtGui.QFont("Arial", 14))
            sub_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
            sub_text.setZValue(1002)
            setattr(sub_text, '_is_pause_message', True)
            
            sub_rect = sub_text.boundingRect()
            sub_text_x = (win_width - sub_rect.width()) / 2
            sub_text_y = pause_text_y + text_rect.height() + 10
            sub_text.setPos(sub_text_x, sub_text_y)

            # Create a timer to keep redrawing the pause message
            self.pause_redraw_timer = QtCore.QTimer()
            self.pause_redraw_timer.timeout.connect(self._redraw_pause_message)
            self.pause_redraw_timer.start(500)  # Redraw every 500ms

        else:
            # Stop the redraw timer if it exists
            if hasattr(self, 'pause_redraw_timer'):
                self.pause_redraw_timer.stop()

    def _redraw_pause_message(self):
        # Check if we're still paused
        if not hasattr(self, 'tamagotchi_logic') or self.tamagotchi_logic.simulation_speed != 0:
            if hasattr(self, 'pause_redraw_timer'):
                self.pause_redraw_timer.stop()
            return

        # Remove existing pause items
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                # Restore original rectangle for background if it exists
                if isinstance(item, QtWidgets.QGraphicsRectItem) and hasattr(item, 'original_rect'):
                    item.setRect(item.original_rect)
                else:
                    self.scene.removeItem(item)

        # Get current window dimensions
        win_width = self.window_width
        win_height = self.window_height

        # Recreate the existing pause items
        # Background rectangle 200 pixels wider than the window, 250 pixels tall
        background = QtWidgets.QGraphicsRectItem(
            -200,  # Start 200 pixels left of the window
            (win_height - 250) / 2,  # Vertically center the 250-pixel tall rectangle
            win_width + 400,  # Total width is window width + 400 (200 on each side)
            250  # Fixed height of 250 pixels
        )
        background.setBrush(QtGui.QColor(0, 0, 0, 180))
        background.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        background.setZValue(1000)
        # Store the original rectangle dimensions to prevent resizing
        background.original_rect = background.rect()
        setattr(background, '_is_pause_message', True)
        self.scene.addItem(background)

        # Main pause text
        pause_text = self.scene.addText("p a u s e d", QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
        pause_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        pause_text.setZValue(1002)
        setattr(pause_text, '_is_pause_message', True)
        
        # Center text using view coordinates
        text_rect = pause_text.boundingRect()
        pause_text_x = (win_width - text_rect.width()) / 2
        pause_text_y = (win_height - text_rect.height()) / 2 - 30
        pause_text.setPos(pause_text_x, pause_text_y)

        # Subtext
        sub_text = self.scene.addText("Use 'Speed' menu to unpause", QtGui.QFont("Arial", 14))
        sub_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
        sub_text.setZValue(1002)
        setattr(sub_text, '_is_pause_message', True)
        
        sub_rect = sub_text.boundingRect()
        sub_text_x = (win_width - sub_rect.width()) / 2
        sub_text_y = pause_text_y + text_rect.height() + 10
        sub_text.setPos(sub_text_x, sub_text_y)

        # Ensure redraw
        self.scene.update()
        self.view.viewport().update()

    def show_pause_message(self, is_paused):
        # Remove existing pause items
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                self.scene.removeItem(item)

        # Get current window dimensions
        win_width = self.window_width
        win_height = self.window_height

        if is_paused:
            # Background rectangle 200 pixels wider than the window, 300 pixels tall
            background = QtWidgets.QGraphicsRectItem(
                -200,  # Start 200 pixels left of the window
                (win_height - 250) / 2,  # Vertically center the 300-pixel tall rectangle
                win_width + 400,  # Total width is window width + 400 (200 on each side)
                250  # Fixed height of 250 pixels
            )
            background.setBrush(QtGui.QColor(0, 0, 0, 180))
            background.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            background.setZValue(1000)
            # Store the original rectangle dimensions to prevent resizing
            background.original_rect = background.rect()
            setattr(background, '_is_pause_message', True)
            self.scene.addItem(background)

            # Main pause text
            pause_text = self.scene.addText("p a u s e d", QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
            pause_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            pause_text.setZValue(1002)
            setattr(pause_text, '_is_pause_message', True)
            
            # Center text using view coordinates
            text_rect = pause_text.boundingRect()
            pause_text_x = (win_width - text_rect.width()) / 2
            pause_text_y = (win_height - text_rect.height()) / 2 - 30
            pause_text.setPos(pause_text_x, pause_text_y)

            # Subtext
            sub_text = self.scene.addText("Use 'Speed' menu to unpause", QtGui.QFont("Arial", 14))
            sub_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
            sub_text.setZValue(1002)
            setattr(sub_text, '_is_pause_message', True)
            
            sub_rect = sub_text.boundingRect()
            sub_text_x = (win_width - sub_rect.width()) / 2
            sub_text_y = pause_text_y + text_rect.height() + 10
            sub_text.setPos(sub_text_x, sub_text_y)

            # Create a timer to keep redrawing the pause message
            self.pause_redraw_timer = QtCore.QTimer()
            self.pause_redraw_timer.timeout.connect(self._redraw_pause_message)
            self.pause_redraw_timer.start(500)  # Redraw every 500ms

        else:
            # Stop the redraw timer if it exists
            if hasattr(self, 'pause_redraw_timer'):
                self.pause_redraw_timer.stop()

    def handle_window_resize(self, event):
        self.window_width = event.size().width()
        self.window_height = event.size().height()
        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
        self.cleanliness_overlay.setRect(50, 50, self.window_width - 100, self.window_height - 100)

        self.feeding_message.setPos(0, self.window_height - 75)
        self.feeding_message.setTextWidth(self.window_width)

        self.points_label.setPos(self.window_width - 265, 10)
        self.points_value_label.setPos(self.window_width - 95, 10)
        
        # Update debug text position
        self.debug_text.setPos(self.window_width - 60, self.window_height - 60)

    def show_message(self, message):
        # Call hook if available
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                # Get modified message from plugins
                results = self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_message_display", 
                    ui=self,
                    original_message=message
                )
                
                # Check if any plugin modified the message
                for result in results:
                    if isinstance(result, str) and result:
                        message = result
                        break
        
        # Continue with original behavior
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
                
                # Create the item - don't set flags here since they're set in __init__
                item = ResizablePixmapItem(pixmap, file_path)
                
                # Handle scaling
                if filename.lower().startswith(('rock01', 'rock02')):
                    # For rocks, set a fixed size
                    item.setPixmap(pixmap.scaled(
                        100, 100, 
                        QtCore.Qt.KeepAspectRatio, 
                        QtCore.Qt.SmoothTransformation
                    ))
                elif not filename.startswith('st_'):
                    # For other decorations, random scale
                    scale_factor = random.uniform(0.75, 2)
                    item.setScale(scale_factor)

                # Set position and add to scene
                pos = self.view.mapToScene(event.pos())
                item.setPos(pos)
                self.scene.addItem(item)
                
                # Bring to front to ensure it's clickable
                item.setZValue(1)
                
                # Update scene to ensure item is visible/interactive
                self.scene.update()
                
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
        self.rock_test_action = QtWidgets.QAction('Rock test (native)', self.window)
        self.rock_test_action.setEnabled(False)  # Disabled by default
        if hasattr(self.tamagotchi_logic, 'test_rock_interaction'):
            self.rock_test_action.triggered.connect(self.tamagotchi_logic.test_rock_interaction)
        #debug_menu.addAction(self.rock_test_action)

        # Neurogenesis Action
        self.neurogenesis_action = QtWidgets.QAction('Trigger Neurogenesis', self.window)
        self.neurogenesis_action.setEnabled(False)  # Disabled by default
        if hasattr(self.tamagotchi_logic, 'trigger_neurogenesis'):
            self.neurogenesis_action.triggered.connect(self.trigger_neurogenesis)
        #debug_menu.addAction(self.neurogenesis_action)

        # Add to debug menu
        self.rock_test_action = QtWidgets.QAction('Rock test (forced)', self.window)
        self.rock_test_action.triggered.connect(self.trigger_rock_test)
        #debug_menu.addAction(self.rock_test_action)
        
        # Add Plugins Menu
        self.plugins_menu = self.menu_bar.addMenu('Plugins')
        
        # This menu will be populated later when the plugin manager is available

    def set_simulation_speed(self, speed):
        """Set the simulation speed (0 = paused, 1 = normal, 2 = fast, 3 = very fast)"""
        #print(f"DEBUG: set_simulation_speed called with speed={speed}")  # Debug print
        
        if hasattr(self, 'tamagotchi_logic'):
            # Show/hide pause message
            #print(f"DEBUG: Showing pause message: {speed == 0}")  # Additional debug print
            self.show_pause_message(speed == 0)
            
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
        # Get current debug mode state from logic if available
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            current_debug = self.tamagotchi_logic.debug_mode
        else:
            current_debug = self.debug_mode
        
        # Toggle the state
        new_debug_mode = not current_debug
        
        # Update all components
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic.debug_mode = new_debug_mode
            if hasattr(self.tamagotchi_logic, 'statistics_window'):
                self.tamagotchi_logic.statistics_window.set_debug_mode(new_debug_mode)
        
        # Update UI state
        self.debug_mode = new_debug_mode
        self.debug_action.setChecked(new_debug_mode)
        self.debug_text.setVisible(new_debug_mode)
        
        # Force update the debug text visibility
        if hasattr(self, 'debug_text'):
            self.debug_text.setVisible(new_debug_mode)
            self.scene.update()
        
        # Sync with brain window if it exists
        if hasattr(self, 'squid_brain_window'):
            self.squid_brain_window.debug_mode = new_debug_mode
            if hasattr(self.squid_brain_window, 'brain_widget'):
                self.squid_brain_window.brain_widget.debug_mode = new_debug_mode
        
        print(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")
        self.show_message(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")

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