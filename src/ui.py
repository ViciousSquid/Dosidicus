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
from .brain_tool import NeuronInspector as EnhancedNeuronInspector
from .plugin_manager_dialog import PluginManagerDialog
from .tutorial import TutorialManager

class DecorationItem(QtWidgets.QLabel):
    def __init__(self, pixmap, filename):
        super().__init__()
        from .display_scaling import DisplayScaling
        
        # Use scaled size instead of hardcoded 128
        item_size = DisplayScaling.scale(128)
        
        # Scale pixmap using the scaled size
        self.setPixmap(pixmap.scaled(item_size, item_size, 
                                     QtCore.Qt.KeepAspectRatio, 
                                     QtCore.Qt.SmoothTransformation))
        self.filename = filename
        
        # Set fixed size using the scaled value
        self.setFixedSize(item_size, item_size)
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
    def __init__(self, pixmap=None, filename=None, category=None, parent=None):
        QtWidgets.QGraphicsPixmapItem.__init__(self, parent)

        self.original_pixmap = pixmap
        self.resize_mode = False
        self.last_mouse_pos = None

        if pixmap:
            self.setPixmap(pixmap)

        self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable |
                    QtWidgets.QGraphicsItem.ItemIsSelectable |
                    QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)

        self.filename = filename
        self.stat_multipliers = {'happiness': 1}
        self.category = category if category else 'generic'

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

        # Print initialization info
        print(f"Created item: {filename}, Has original pixmap: {self.original_pixmap is not None}")

    def boundingRect(self):
        # Just use the original bounding rect without extra space for handles
        return super().boundingRect()

    def wheelEvent(self, event):
        # Don't scale rocks
        if self.filename and ('rock01' in self.filename.lower() or 'rock02' in self.filename.lower()):
            return super().wheelEvent(event)
            
        # Only scale if the item is selected and we have the original pixmap
        if self.isSelected() and self.original_pixmap:
            # Import DisplayScaling locally
            from .display_scaling import DisplayScaling
            
            # Get scaling delta from wheel event - use angleDelta() instead of delta()
            delta = event.angleDelta().y() / 120  # Standard wheel step is 120 units
            
            # Calculate scaling factor - increase/decrease by 10% per wheel step
            scale_factor = 1.1 if delta > 0 else 0.9
            
            # Get current size
            current_width = self.pixmap().width()
            current_height = self.pixmap().height()
            
            # Calculate new dimensions with minimum size constraint
            min_size = DisplayScaling.scale(64)  # Minimum size of 64x64 scaled for display
            new_width = max(min_size, int(current_width * scale_factor))
            new_height = max(min_size, int(current_height * scale_factor))
            
            # Scale the pixmap to new size
            scaled_pixmap = self.original_pixmap.scaled(
                new_width, new_height,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            # Update the pixmap
            self.setPixmap(scaled_pixmap)
            
            event.accept()
        else:
            # Forward the event to parent
            super().wheelEvent(event)

    def paint(self, painter, option, widget):
        # Always draw the item itself
        option_copy = QtWidgets.QStyleOptionGraphicsItem(option)
        option_copy.state &= ~QtWidgets.QStyle.State_Selected  # Remove default selection rectangle
        super().paint(painter, option_copy, widget)
        
        if self.isSelected():
            # Draw outline of the actual visible content
            pixmap = self.pixmap()
            if pixmap:
                painter.save()
                
                # Use a blue pen for the outline
                painter.setPen(QtGui.QPen(QtGui.QColor(30, 144, 255), 2))
                
                # Get the exact rect of the pixmap content
                rect = QtCore.QRectF(0, 0, pixmap.width(), pixmap.height())
                
                # Draw outline around the actual pixmap content
                painter.drawRect(rect)
                
                painter.restore()



    def mousePressEvent(self, event):
        # Get mouse position
        pos = event.pos()
        self.last_mouse_pos = pos
        
        # Always handle as a regular click for moving/selecting
        self.resize_mode = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        current_pos = event.pos()
        
        if self.resize_mode and self.original_pixmap and self.last_mouse_pos:
            # Calculate movement delta
            delta_x = current_pos.x() - self.last_mouse_pos.x()
            delta_y = current_pos.y() - self.last_mouse_pos.y()
            
            # Get current size
            current_width = self.pixmap().width()
            current_height = self.pixmap().height()
            
            # Calculate new dimensions (minimum 30x30)
            new_width = max(30, current_width + delta_x)
            new_height = max(30, current_height + delta_y)
            
            # Scale the pixmap to new size
            scaled_pixmap = self.original_pixmap.scaled(
                int(new_width), int(new_height),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            
            # Update the pixmap
            self.setPixmap(scaled_pixmap)
            
            # Update mouse position for next move
            self.last_mouse_pos = current_pos
            event.accept()
        else:
            # Normal drag operation
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # End resize mode
        self.resize_mode = False
        self.last_mouse_pos = None
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
        
        # Scale window size
        from .display_scaling import DisplayScaling
        self.setFixedWidth(DisplayScaling.scale(800))

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
        items_per_row = 4
        row, col = 0, 0
        
        from .display_scaling import DisplayScaling
        item_size = DisplayScaling.scale(128)
        
        for filename in os.listdir(decoration_path):
            if filename.endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(decoration_path, filename)
                pixmap = QtGui.QPixmap(full_path)
                
                # Scale item size
                scaled_pixmap = pixmap.scaled(item_size, item_size, 
                                        QtCore.Qt.KeepAspectRatio, 
                                        QtCore.Qt.SmoothTransformation)
                
                item = DecorationItem(scaled_pixmap, full_path)
                self.grid_layout.addWidget(item, row, col)
                
                col += 1
                if col >= items_per_row:
                    col = 0
                    row += 1
        
        # Scale window height
        self.setFixedHeight(min((row + 1) * (item_size + DisplayScaling.scale(20)) + DisplayScaling.scale(40), DisplayScaling.scale(650)))

class Ui:
    def __init__(self, window, debug_mode=False):
        self.window = window
        self.tamagotchi_logic = None
        self.debug_mode = debug_mode
        self.setup_neurogenesis_debug_shortcut()
        
        # Get screen size and initialize scaling
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        
        from .display_scaling import DisplayScaling
        DisplayScaling.initialize(screen_size.width(), screen_size.height())
        
        # Adjust window size based on resolution
        if screen_size.width() <= 1920:  # For 1920x1080 or lower
            base_width = 1440
            base_height = 960
        else:  # For higher resolutions like 2880x1920
            base_width = 1344  # Slightly larger than 1280 for better proportionality
            base_height = 936

        self.window.setMinimumSize(DisplayScaling.scale(base_width), DisplayScaling.scale(base_height))
        self.window_width = DisplayScaling.scale(base_width)
        self.window_height = DisplayScaling.scale(base_height)
        self.window.setWindowTitle("Dosidicus")
        self.window.resize(self.window_width, self.window_height)

        # Create scene and view
        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.tutorial_manager = TutorialManager(self, window)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.view.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)

        self.window.setCentralWidget(self.view)

        # Setup UI elements
        self.setup_ui_elements()

        # Setup menu bar and other components
        self.setup_menu_bar()
        self.enhanced_neuron_inspector_instance = None
        self.squid_brain_window = None

        # Add debug text item to the scene
        self.debug_text = QtWidgets.QGraphicsTextItem("Debug")
        self.debug_text.setDefaultTextColor(QtGui.QColor("#a9a9a9"))
        font = QtGui.QFont()
        font.setPointSize(DisplayScaling.scale(20))
        self.debug_text.setFont(font)
        self.debug_text.setRotation(-90)
        self.debug_text.setPos(DisplayScaling.scale(75), DisplayScaling.scale(75))
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

    def setup_neurogenesis_debug_shortcut(self):
        # Create a shortcut for neurogenesis debug window
        self.neurogenesis_debug_shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.ALT + QtCore.Qt.Key_N), 
            self.window
        )
        self.neurogenesis_debug_shortcut.activated.connect(self.show_neurogenesis_debug)

    def show_neurogenesis_debug(self):
        # Ensure brain widget exists
        if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
            print("Brain window not initialized")
            return

        # Create or show the debug dialog
        if not hasattr(self, '_neurogenesis_debug_dialog'):
            self._neurogenesis_debug_dialog = NeurogenesisDebugDialog(
                self.squid_brain_window.brain_widget, 
                self.window
            )
        
        self._neurogenesis_debug_dialog.update_debug_info()
        self._neurogenesis_debug_dialog.show()
        self._neurogenesis_debug_dialog.raise_()

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
        
        # Connect neurogenesis action now that tamagotchi_logic is available
        if hasattr(self, 'neurogenesis_action'):
            self.neurogenesis_action.triggered.connect(self.trigger_neurogenesis)
        
        # Create multiplayer menu
        self.create_multiplayer_menu()

    def show_tutorial_overlay(self):
        """Show the tutorial using the tutorial manager"""
        self.tutorial_manager.start_tutorial()

    def remove_tutorial_overlay(self):
        """Clean up tutorial elements and advance to next step"""
        self.tutorial_manager.advance_to_next_step()

    def show_second_tutorial_banner(self):
        """Show the second tutorial banner about the neural network"""
        # Get current window dimensions
        win_width = self.window_width
        win_height = self.window_height
        
        # Create a banner across the bottom of the screen
        banner_height = 100
        banner = QtWidgets.QGraphicsRectItem(0, win_height - banner_height, win_width, banner_height)
        banner.setBrush(QtGui.QColor(25, 25, 112, 230))  # Midnight blue, nearly opaque
        banner.setPen(QtGui.QPen(QtGui.QColor(135, 206, 250, 150), 1))  # Light blue outline
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.scene.addItem(banner)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("🧠 NEURAL NETWORK")
        title_text.setDefaultTextColor(QtGui.QColor(135, 206, 250))  # Light blue
        title_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        title_text.setPos(20, win_height - banner_height + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.scene.addItem(title_text)
        
        # Create body text
        info_text = QtWidgets.QGraphicsTextItem(
            "This is the squid's neural network. His behaviour is driven by his needs (round neurons).\n"
            "The network adapts and learns as the squid interacts with his environment."
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", 11))
        info_text.setPos(20, win_height - banner_height + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.scene.addItem(info_text)
        
        # Add a close button
        dismiss_button = QtWidgets.QPushButton("Got it!")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #1E90FF;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #4169E1;
            }
        """)
        dismiss_button.clicked.connect(self.close_tutorial_completely)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, win_height - banner_height + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        
        # Auto-dismiss after 20 seconds
        self.tutorial_timer = QtCore.QTimer()
        self.tutorial_timer.timeout.connect(self.close_tutorial_completely)
        self.tutorial_timer.setSingleShot(True)
        self.tutorial_timer.start(20000)  # 20 seconds

    def close_tutorial_completely(self):
        """Final cleanup of all tutorial elements"""
        # Stop any timers
        if hasattr(self, 'tutorial_timer') and self.tutorial_timer.isActive():
            self.tutorial_timer.stop()
        
        # Remove all tutorial elements
        for item in self.scene.items():
            if hasattr(item, '_is_tutorial_element'):
                self.scene.removeItem(item)
        
        # Force scene update
        self.scene.update()


    def setup_plugin_menu(self, plugin_manager_instance): #
        # This method is called during initial UI setup (Ui.setup_menu_bar).
        # The plugin_manager_instance might be None at this stage.
        # The apply_plugin_menu_registrations method is now responsible for the full
        # and correct setup of the "Plugin Manager" action and plugin-specific menus
        # once the plugin_manager is fully initialized.
        
        if not hasattr(self, 'plugins_menu'):
            self.plugins_menu = self.menu_bar.addMenu('Plugins')
        
        # Minimal setup here; apply_plugin_menu_registrations will do the heavy lifting.
        # We can ensure the "Plugin Manager" action and separator are provisionally added
        # if the menu is being created for the first time.
        if not hasattr(self, 'plugin_manager_action') or not self.plugin_manager_action:
            self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
            self.plugins_menu.addAction(self.plugin_manager_action)
            self.plugins_menu.addSeparator()

        # The connection and enabling/disabling of plugin_manager_action,
        # and the addition of other plugin menus, are handled by
        # apply_plugin_menu_registrations when plugin_manager is ready.
        if plugin_manager_instance: # This is the main plugin_manager from main.py
             self.apply_plugin_menu_registrations(plugin_manager_instance)

    def create_multiplayer_menu(self):
        """Create multiplayer menu only if the plugin is loaded and enabled"""
        # This function is now handled in setup_plugin_menu
        # Kept for backward compatibility
        if hasattr(self.tamagotchi_logic, 'plugin_manager'):
            self.setup_plugin_menu(self.tamagotchi_logic.plugin_manager)
        else:
            print("WARNING: create_multiplayer_menu called but plugin_manager is not available")

    def apply_plugin_menu_registrations(self, plugin_manager):
        """Apply menu registrations from plugins, ensuring Plugin Manager action is correctly set up."""
        
        # Ensure 'Plugins' menu and 'Plugin Manager' action exist and are correctly configured
        if not hasattr(self, 'plugins_menu') or not self.plugins_menu:
            # This means setup_plugin_menu (called during Ui.__init__) did not create self.plugins_menu
            # or it was cleared. Create/recreate main "Plugins" menu.
            self.plugins_menu = self.menu_bar.addMenu('Plugins')
            
            # Create the "Plugin Manager" action
            self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
            self.plugins_menu.addAction(self.plugin_manager_action)
            self.plugins_menu.addSeparator() # Add separator after Plugin Manager
        elif not hasattr(self, 'plugin_manager_action') or \
             not self.plugin_manager_action or \
             self.plugin_manager_action not in self.plugins_menu.actions():
            # plugins_menu exists, but the plugin_manager_action is missing or not in the menu.
            # This can happen if clear() was called on plugins_menu.
            # Re-create the action and add it to the top.
            self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
            
            # Clear existing connections first (if any, to avoid duplicates)
            try:
                self.plugin_manager_action.triggered.disconnect()
            except TypeError: # No connections to disconnect
                pass

            all_actions = self.plugins_menu.actions()
            if all_actions and all_actions[0].isSeparator():
                # If a separator is somehow first, insert before it
                self.plugins_menu.insertAction(all_actions[0], self.plugin_manager_action)
            elif all_actions:
                # Insert before the first existing action
                self.plugins_menu.insertAction(all_actions[0], self.plugin_manager_action)
            else:
                # Menu is empty, just add it
                self.plugins_menu.addAction(self.plugin_manager_action)

            # Ensure separator exists after Plugin Manager action
            current_actions = self.plugins_menu.actions()
            pm_action_index = current_actions.index(self.plugin_manager_action) if self.plugin_manager_action in current_actions else -1

            if pm_action_index != -1:
                if pm_action_index + 1 >= len(current_actions) or not current_actions[pm_action_index + 1].isSeparator():
                    # Add separator if it's not the next action or if it's the last action
                    sep = QtWidgets.QAction(self.window) # Create a QAction to act as a separator placeholder for insertAction
                    sep.setSeparator(True)
                    self.plugins_menu.insertAction(current_actions[pm_action_index + 1] if pm_action_index + 1 < len(current_actions) else None, sep)


        # (Re)Connect the 'Plugin Manager' action with the provided (and presumably valid) plugin_manager
        # Clear any existing connections from plugin_manager_action first
        try:
            self.plugin_manager_action.triggered.disconnect()
        except TypeError: # No connections to disconnect
            pass

        if plugin_manager:
            self.plugin_manager_action.triggered.connect(
                lambda: self.show_plugin_manager(plugin_manager) # Connects to the correct instance
            )
            self.plugin_manager_action.setEnabled(True)
            self.plugin_manager_action.setToolTip("Open the plugin manager.")
        else:
            # This case should ideally not be hit if called correctly from main.py
            self.plugin_manager_action.setEnabled(False)
            self.plugin_manager_action.setToolTip("Plugin manager is not available.")

        # --- Management of plugin-specific menu items ---
        # Identify the separator that should follow the "Plugin Manager" action.
        # All actions after this separator are considered plugin-specific and will be cleared and re-added.
        
        actions_to_remove = []
        separator_after_pm_action_found = False
        pm_action_ref = self.plugin_manager_action # The action we just configured

        if pm_action_ref and pm_action_ref in self.plugins_menu.actions():
            pm_action_index = self.plugins_menu.actions().index(pm_action_ref)
            
            # Check if the item immediately after pm_action_ref is a separator
            if pm_action_index + 1 < len(self.plugins_menu.actions()):
                next_action = self.plugins_menu.actions()[pm_action_index + 1]
                if next_action.isSeparator():
                    separator_after_pm_action_found = True
                    # Mark all actions after this specific separator for removal
                    for i in range(pm_action_index + 2, len(self.plugins_menu.actions())):
                        actions_to_remove.append(self.plugins_menu.actions()[i])
        
        if not separator_after_pm_action_found:
            # If the specific separator wasn't found (e.g., menu was just created, or structure is unexpected)
            # Fallback: remove all actions except the plugin_manager_action and its potential direct separator
            # This is more aggressive but ensures a clean state.
            temp_actions_to_keep = {pm_action_ref}
            if pm_action_ref and pm_action_ref in self.plugins_menu.actions():
                 pm_idx = self.plugins_menu.actions().index(pm_action_ref)
                 if pm_idx + 1 < len(self.plugins_menu.actions()) and self.plugins_menu.actions()[pm_idx+1].isSeparator():
                     temp_actions_to_keep.add(self.plugins_menu.actions()[pm_idx+1])

            for action in self.plugins_menu.actions():
                if action not in temp_actions_to_keep:
                    actions_to_remove.append(action)


        for action_to_remove in actions_to_remove:
            self.plugins_menu.removeAction(action_to_remove)

        # Logic to add actions from individual (enabled) plugins
        if plugin_manager and hasattr(plugin_manager, 'plugins'):
            enabled_plugin_keys = plugin_manager.get_enabled_plugins() # Get set of enabled plugin keys

            for plugin_name_key, plugin_data_dict in plugin_manager.plugins.items():
                if plugin_name_key not in enabled_plugin_keys: # Only process enabled plugins
                    continue

                plugin_instance = plugin_data_dict.get('instance')
                original_name = plugin_data_dict.get('original_name', plugin_name_key.capitalize())

                if plugin_instance and hasattr(plugin_instance, 'register_menu_actions'):
                    # Create a submenu for this plugin if it has actions
                    # Ensure it's added AFTER the main separator for Plugin Manager
                    plugin_submenu = self.plugins_menu.addMenu(original_name)
                    try:
                        # The plugin's register_menu_actions should now add actions to plugin_submenu
                        # Pass the main window (self.window) and the newly created submenu
                        plugin_instance.register_menu_actions(self.window, plugin_submenu)
                    except Exception as e:
                        print(f"Error calling register_menu_actions for {original_name}: {e}")
                        # traceback.print_exc() # For more detailed debugging if needed

        print("Applied all plugin menu registrations") #

    def toggle_plugin(self, plugin_name, enable_flag): # Renamed 'enable' to 'enable_flag' for clarity
        """Toggle a plugin on/off using the PluginManager."""
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'plugin_manager'):
            plugin_mgr = self.tamagotchi_logic.plugin_manager
            
            # Plugin keys are stored in lowercase by the PluginManager
            # Ensure plugin_name matches this convention if it's coming from elsewhere with different casing.
            # However, since it's likely 'multiplayer' from setup_plugin_menu, it should be fine.
            
            if plugin_name not in plugin_mgr.plugins:
                print(f"WARNING:UI: Attempted to toggle plugin '{plugin_name}', but it's not loaded/found in plugin_mgr.plugins.")
                # Optionally, you might want to refresh the menu here if this state is unexpected
                # self.setup_plugin_menu(plugin_mgr)
                return

            success = False
            if enable_flag:
                print(f"INFO:UI: Requesting PluginManager to enable plugin '{plugin_name}'.")
                success = plugin_mgr.enable_plugin(plugin_name) # Let PluginManager handle setup and enable
                if success:
                    print(f"INFO:UI: PluginManager reported success enabling '{plugin_name}'.")
                else:
                    print(f"WARNING:UI: PluginManager reported failure enabling '{plugin_name}'.")
            else:
                print(f"INFO:UI: Requesting PluginManager to disable plugin '{plugin_name}'.")
                success = plugin_mgr.disable_plugin(plugin_name) # Let PluginManager handle disable
                if success:
                    print(f"INFO:UI: PluginManager reported success disabling '{plugin_name}'.")
                else:
                    print(f"WARNING:UI: PluginManager reported failure disabling '{plugin_name}'.")

            # Refresh the plugin menu to reflect the new state.
            # The setup_plugin_menu method in your ui.py is responsible for rebuilding
            # the necessary menu items, including the toggle for the multiplayer plugin.
            if hasattr(self, 'setup_plugin_menu') and callable(self.setup_plugin_menu):
                self.setup_plugin_menu(plugin_mgr)
            else:
                print("WARNING:UI: setup_plugin_menu method not found, cannot refresh UI after toggle.")
        else:
            print("WARNING:UI: Cannot toggle plugin - TamagotchiLogic or PluginManager not available.")

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

        # Completely disable scrolling in the main view
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        # Make sure the scene fits exactly in the view without scrolling
        self.view.setSceneRect(0, 0, self.window_width, self.window_height)
        
        # Override the wheel event to handle only decoration resizing
        self.original_view_wheel_event = self.view.wheelEvent
        self.view.wheelEvent = self.custom_wheel_event

        # Check if tamagotchi_logic exists before accessing debug_mode
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.debug_text.setVisible(getattr(self.tamagotchi_logic, 'debug_mode', False))

    def custom_wheel_event(self, event):
        # Get selected items
        selected_items = self.scene.selectedItems()
        
        # Find selected ResizablePixmapItems
        resizable_selected = [item for item in selected_items if 
                            isinstance(item, ResizablePixmapItem)]
        
        if resizable_selected:
            # Forward the wheel event to all selected resizable items
            for item in resizable_selected:
                # We need to convert QWheelEvent (PyQt5) to QGraphicsSceneWheelEvent
                # This hack allows us to use the existing wheelEvent method
                # Without requiring a full rewrite
                try:
                    item.wheelEvent(event)
                except Exception as e:
                    print(f"Error in wheel event handling: {e}")
        
        # Always accept the event to prevent the view from scrolling
        event.accept()

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
        """Direct neuron creation bypassing all checks"""
        try:
            # Get brain widget
            if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
                print("Brain window not found")
                self.show_message("Brain window not initialized")
                return
                
            brain = self.squid_brain_window.brain_widget
            
            # Remember existing neurons to verify creation
            import time
            import random
            prev_neurons = set(brain.neuron_positions.keys())
            
            # Generate unique name
            new_name = f"forced_{int(time.time())}"
            
            # Calculate position near center of existing neurons
            if brain.neuron_positions:
                x_values = [pos[0] for pos in brain.neuron_positions.values()]
                y_values = [pos[1] for pos in brain.neuron_positions.values()]
                center_x = sum(x_values) / len(x_values)
                center_y = sum(y_values) / len(y_values)
            else:
                center_x, center_y = 600, 300  # Default center position
            
            # Add randomness
            pos_x = center_x + random.randint(-100, 100)
            pos_y = center_y + random.randint(-100, 100)
            
            # Directly add neuron to brain collections
            print(f"Creating neuron {new_name} at ({pos_x}, {pos_y})")
            brain.neuron_positions[new_name] = (pos_x, pos_y)
            brain.state[new_name] = 75  # High initial activation
            
            # Set neuron color
            if hasattr(brain, 'state_colors'):
                brain.state_colors[new_name] = (150, 200, 255)  # Light blue color
            
            # Create connections to existing neurons
            for existing in list(prev_neurons):
                if existing in getattr(brain, 'excluded_neurons', []):
                    continue  # Skip excluded neurons
                weight = random.uniform(-0.3, 0.3)
                brain.weights[(new_name, existing)] = weight
                brain.weights[(existing, new_name)] = weight * 0.8
            
            # Update tracking data
            if hasattr(brain, 'neurogenesis_data'):
                if 'new_neurons' not in brain.neurogenesis_data:
                    brain.neurogenesis_data['new_neurons'] = []
                brain.neurogenesis_data['new_neurons'].append(new_name)
                brain.neurogenesis_data['last_neuron_time'] = time.time()
            
            # Set highlight for visualization
            if hasattr(brain, 'neurogenesis_highlight'):
                brain.neurogenesis_highlight = {
                    'neuron': new_name,
                    'start_time': time.time(),
                    'duration': 5.0
                }
            
            # Force immediate update
            brain.update()
            
            # Verify creation worked
            new_neurons = set(brain.neuron_positions.keys()) - prev_neurons
            if new_neurons:
                try:
                    self.show_message(f"Created neuron: {new_name}")
                except:
                    pass
                print(f"Successfully created neuron: {new_name}")
            else:
                self.show_message("Neuron creation failed!")
                print("ERROR: Failed to create neuron")

        except Exception as e:
            import traceback
            print(f"NEUROGENESIS FAILURE:\n{traceback.format_exc()}")
            try:
                self.show_message(f"Neurogenesis Error: {str(e)}")
            except:
                pass


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
        
        from .display_scaling import DisplayScaling

        if is_paused:
            # Background rectangle with scaled dimensions
            background = QtWidgets.QGraphicsRectItem(
                -DisplayScaling.scale(200),  # Start 200 pixels left of the window
                (win_height - DisplayScaling.scale(250)) / 2,  # Vertically center
                win_width + DisplayScaling.scale(400),  # Total width with scaling
                DisplayScaling.scale(250)  # Fixed height with scaling
            )
            background.setBrush(QtGui.QColor(0, 0, 0, 180))
            background.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            background.setZValue(1000)
            # Store the original rectangle dimensions
            background.original_rect = background.rect()
            setattr(background, '_is_pause_message', True)
            self.scene.addItem(background)

            # Main pause text with scaled font
            pause_font = QtGui.QFont("Arial", DisplayScaling.font_size(24), QtGui.QFont.Bold)
            pause_text = self.scene.addText("p a u s e d", pause_font)
            pause_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            pause_text.setZValue(1002)
            setattr(pause_text, '_is_pause_message', True)
            
            # Center text using scaled calculations
            text_rect = pause_text.boundingRect()
            pause_text_x = (win_width - text_rect.width()) / 2
            pause_text_y = (win_height - text_rect.height()) / 2 - DisplayScaling.scale(30)
            pause_text.setPos(pause_text_x, pause_text_y)

            # Subtext with scaled font
            sub_font = QtGui.QFont("Arial", DisplayScaling.font_size(14))
            sub_text = self.scene.addText("Use 'Speed' menu to unpause", sub_font)
            sub_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
            sub_text.setZValue(1002)
            setattr(sub_text, '_is_pause_message', True)
        
        sub_rect = sub_text.boundingRect()
        sub_text_x = (win_width - sub_rect.width()) / 2
        sub_text_y = pause_text_y + text_rect.height() + 10
        sub_text.setPos(sub_text_x, sub_text_y)
        
        # Set up redraw timer
        self.pause_redraw_timer = QtCore.QTimer()
        self.pause_redraw_timer.timeout.connect(self._redraw_pause_message)
        self.pause_redraw_timer.start(500)  # Redraw every 500ms

    def _remove_all_pause_elements(self):
        """Helper method to remove all pause-related UI elements"""
        # Stop any pause redraw timer
        if hasattr(self, 'pause_redraw_timer') and self.pause_redraw_timer:
            self.pause_redraw_timer.stop()
        
        # Remove all items marked with _is_pause_message
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                self.scene.removeItem(item)

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
        # Update UI dimensions
        self.window_width = event.size().width()
        self.window_height = event.size().height()
        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        # Update boundary rectangle
        self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
        self.cleanliness_overlay.setRect(50, 50, self.window_width - 100, self.window_height - 100)

        # Update UI elements positions
        self.feeding_message.setPos(0, self.window_height - 75)
        self.feeding_message.setTextWidth(self.window_width)
        self.points_label.setPos(self.window_width - 265, 10)
        self.points_value_label.setPos(self.window_width - 95, 10)
        self.debug_text.setPos(self.window_width - 60, self.window_height - 60)
        
        # Reposition any active message
        if hasattr(self, 'current_message_item') and self.current_message_item in self.scene.items():
            text_height = self.current_message_item.boundingRect().height()
            message_y = self.window_height - text_height - 20
            self.current_message_item.setPos(0, message_y)
            self.current_message_item.setTextWidth(self.window_width)
        
        # CRITICAL FIX: Ensure squid stays within boundary after resize
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
            squid = self.tamagotchi_logic.squid
            
            # Update squid's reference to window dimensions
            squid.ui.window_width = self.window_width
            squid.ui.window_height = self.window_height
            
            # Update squid's center position reference
            squid.center_x = self.window_width // 2
            squid.center_y = self.window_height // 2
            
            # Update vertical range preferences
            if hasattr(squid, 'update_preferred_vertical_range'):
                squid.update_preferred_vertical_range()
            
            # Constrain squid position to stay within boundary
            squid.squid_x = max(50, min(squid.squid_x, self.window_width - 50 - squid.squid_width))
            squid.squid_y = max(50, min(squid.squid_y, self.window_height - 120 - squid.squid_height))
            squid.squid_item.setPos(squid.squid_x, squid.squid_y)
            
            # Update visual elements
            if hasattr(squid, 'update_view_cone'):
                squid.update_view_cone()
            if hasattr(squid, 'startled_icon') and squid.startled_icon is not None:
                squid.update_startled_icon_position()
            if hasattr(squid, 'sick_icon_item') and squid.sick_icon_item is not None:
                squid.update_sick_icon_position()

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
        
        # Remove any existing message items - WRAPPED IN TRY-EXCEPT
        try:
            for item in self.scene.items():
                try:
                    if hasattr(item, '_is_message_item'):
                        self.scene.removeItem(item)
                except Exception:
                    continue
        except Exception:
            pass

        # Create a new QGraphicsTextItem for the message with scaled font
        message_item = QtWidgets.QGraphicsTextItem(message)
        message_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        
        # Scale font size
        from .display_scaling import DisplayScaling
        font = QtGui.QFont("Verdana", DisplayScaling.font_size(12), QtGui.QFont.Bold)
        message_item.setFont(font)
        
        message_item.setTextWidth(self.window_width)
        
        # Calculate position - lock to bottom with some padding
        text_height = message_item.boundingRect().height()
        message_y = self.window_height - text_height - 40  # 40px padding from bottom
        
        message_item.setPos(0, message_y)
        message_item.setHtml(f'<div style="text-align: center; background-color: #000000; padding: 0px;">{message}</div>')
        message_item.setZValue(999)  # Ensure the message is on top
        message_item.setOpacity(1)
        try:
            setattr(message_item, '_is_message_item', True)  # Mark as message item
        except TypeError:
            pass  # Skip if attribute setting fails

        # Add the new message item to the scene
        self.scene.addItem(message_item)

        # Store reference to the current message
        self.current_message_item = message_item

        # Fade out the message after 10 seconds
        self.fade_out_animation = QtCore.QPropertyAnimation(message_item, b"opacity")
        self.fade_out_animation.setDuration(10000)
        self.fade_out_animation.setStartValue(1.0)
        self.fade_out_animation.setEndValue(0.0)
        self.fade_out_animation.finished.connect(lambda: self.scene.removeItem(message_item))
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
        
        # Use QVariantAnimation as QGraphicsItem is not a QObject
        animation = QtCore.QVariantAnimation()
        animation.setStartValue(current_pos)
        animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
        animation.setDuration(300)  # 300 ms duration
        animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        # On each frame of the animation, update the decoration's position
        animation.valueChanged.connect(decoration.setPos)

        # Store animation to prevent garbage collection and start it
        decoration._animation = animation
        animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

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
                
                # Create the item with the original pixmap
                item = ResizablePixmapItem(pixmap, file_path)
                
                # IMPORTANT: Make sure the original is preserved
                item.original_pixmap = pixmap
                
                # Set initial size for non-rock items
                if not ('rock01' in file_path.lower() or 'rock02' in file_path.lower()):
                    from .display_scaling import DisplayScaling
                    
                    # Target initial maximum dimension
                    target_max_size = DisplayScaling.scale(192)  # Adjust this value as needed
                    
                    # Get dimensions
                    orig_width = pixmap.width()
                    orig_height = pixmap.height()
                    
                    # Calculate scaling based on largest dimension
                    max_dimension = max(orig_width, orig_height)
                    if max_dimension > target_max_size:
                        scale_factor = target_max_size / max_dimension
                        
                        # Apply scaling
                        scaled_width = int(orig_width * scale_factor)
                        scaled_height = int(orig_height * scale_factor)
                        
                        # Create scaled pixmap
                        scaled_pixmap = pixmap.scaled(
                            scaled_width, scaled_height,
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation
                        )
                        
                        # Update item pixmap
                        item.setPixmap(scaled_pixmap)
                
                # Set position and add to scene
                pos = self.view.mapToScene(event.pos())
                item.setPos(pos)
                
                # Add to scene and select for immediate access
                self.scene.addItem(item)
                self.scene.clearSelection()
                item.setSelected(True)
                
                event.accept()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_selected_items()
        elif event.key() == QtCore.Qt.Key_N and event.modifiers() & QtCore.Qt.ShiftModifier:  # Shift+N for Neurogenesis
            self.direct_create_neuron()

    def direct_create_neuron(self):
        """Direct neuron creation bypassing all checks and UI methods"""
        try:
            # Get brain widget directly
            if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
                print("ERROR: Brain window not initialized")
                return
                
            brain = self.squid_brain_window.brain_widget
            
            # Generate unique name with timestamp
            import time
            import random
            new_name = f"forced_{int(time.time())}"
            
            # Calculate center of existing neurons
            if brain.neuron_positions:
                x_values = [pos[0] for pos in brain.neuron_positions.values()]
                y_values = [pos[1] for pos in brain.neuron_positions.values()]
                center_x = sum(x_values) / len(x_values)
                center_y = sum(y_values) / len(y_values)
            else:
                center_x, center_y = 600, 300
            
            # Add randomness to position
            pos_x = center_x + random.randint(-100, 100)
            pos_y = center_y + random.randint(-100, 100)
            
            # DIRECTLY ADD THE NEURON - bypassing all methods
            print(f"Creating neuron {new_name} at ({pos_x}, {pos_y})")
            
            # 1. Add to positions
            brain.neuron_positions[new_name] = (pos_x, pos_y)
            
            # 2. Set activation
            brain.state[new_name] = 75
            
            # 3. Set color
            if hasattr(brain, 'state_colors'):
                brain.state_colors[new_name] = (150, 200, 255)
            
            # 4. Create connections
            excluded = getattr(brain, 'excluded_neurons', [])
            for existing in list(brain.neuron_positions.keys()):
                if existing != new_name and existing not in excluded:
                    weight = random.uniform(-0.3, 0.3)
                    brain.weights[(new_name, existing)] = weight
                    brain.weights[(existing, new_name)] = weight * 0.8
            
            # 5. Update tracking
            if hasattr(brain, 'neurogenesis_data'):
                if 'new_neurons' not in brain.neurogenesis_data:
                    brain.neurogenesis_data['new_neurons'] = []
                brain.neurogenesis_data['new_neurons'].append(new_name)
                brain.neurogenesis_data['last_neuron_time'] = time.time()
            
            # 6. Set highlight
            if hasattr(brain, 'neurogenesis_highlight'):
                brain.neurogenesis_highlight = {
                    'neuron': new_name,
                    'start_time': time.time(),
                    'duration': 5.0
                }
            
            # 7. Force update
            brain.update()
            
            print(f"Successfully created neuron: {new_name}")
            
        except Exception as e:
            import traceback
            print(f"NEUROGENESIS FAILURE:\n{traceback.format_exc()}")

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

        self.brain_action = QtWidgets.QAction('Toggle Brain Tool', self.window)
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
        if hasattr(self.tamagotchi_logic, 'connect_view_cone_action'): # This check is good practice
            self.view_cone_action.triggered.connect(self.tamagotchi_logic.connect_view_cone_action)
        elif hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'toggle_view_cone'): # Fallback if connect_view_cone_action is not on logic
             self.view_cone_action.triggered.connect(self.tamagotchi_logic.squid.toggle_view_cone)
        debug_menu.addAction(self.view_cone_action)
        
        # Neurogenesis Debug Window Action
        self.neurogenesis_debug_action = QtWidgets.QAction('Neurogenesis Debug Info', self.window)
        self.neurogenesis_debug_action.triggered.connect(self.show_neurogenesis_debug) 
        debug_menu.addAction(self.neurogenesis_debug_action)

        # Add to debug menu
        self.rock_test_action = QtWidgets.QAction('Rock test (forced)', self.window)
        self.rock_test_action.triggered.connect(self.trigger_rock_test)
        #debug_menu.addAction(self.rock_test_action) # As per your file, this was commented out
        
        # Add Plugins Menu
        self.plugins_menu = self.menu_bar.addMenu('Plugins')
        # This menu will be populated later when the plugin manager is available

    def set_simulation_speed(self, speed):
        """Set the simulation speed (0 = paused, 1 = normal, 2 = fast, 3 = very fast)"""
        if hasattr(self, 'tamagotchi_logic'):
            # Update pause message visibility
            is_paused = (speed == 0)
            self.show_pause_message(is_paused)
            
            # Update game logic
            self.tamagotchi_logic.set_simulation_speed(speed)
            
            # Update menu actions
            self.pause_action.setChecked(speed == 0)
            self.normal_speed_action.setChecked(speed == 1)
            self.fast_speed_action.setChecked(speed == 2)
            self.very_fast_speed_action.setChecked(speed == 3)
            
            speed_names = ["Paused", "Normal", "Fast", "Very Fast"]
            self.show_message(f"Simulation speed set to {speed_names[speed]}")
        else:
            self.show_message("Game logic not initialized!")

    def toggle_debug_mode(self):
        """Toggle debug mode state with improved synchronization"""
        # Get current debug mode state
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            current_debug = self.tamagotchi_logic.debug_mode
        else:
            current_debug = self.debug_mode
        
        # Toggle the state
        new_debug_mode = not current_debug
        
        # Set a flag to prevent circular callbacks
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic._propagating_debug_mode = True
        
        # First, update self
        self.debug_mode = new_debug_mode
        
        # Update UI elements
        if hasattr(self, 'debug_action'):
            self.debug_action.setChecked(new_debug_mode)
        
        if hasattr(self, 'debug_text'):
            self.debug_text.setVisible(new_debug_mode)
            self.scene.update()
        
        # Sync with tamagotchi_logic and its components
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic.debug_mode = new_debug_mode
            
            # Update statistics window if it exists
            if hasattr(self.tamagotchi_logic, 'statistics_window'):
                self.tamagotchi_logic.statistics_window.set_debug_mode(new_debug_mode)
        
        # Sync with brain window and its components
        if hasattr(self, 'squid_brain_window'):
            self.squid_brain_window.debug_mode = new_debug_mode
            
            # Ensure brain_widget gets updated too
            if hasattr(self.squid_brain_window, 'brain_widget'):
                self.squid_brain_window.brain_widget.debug_mode = new_debug_mode
                # Force update to reflect changes
                self.squid_brain_window.brain_widget.update()
        
        # Clear propagation flag
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic._propagating_debug_mode = False
        
        # Print status for confirmation
        print(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")
        
        try:
            self.show_message(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")
        except TypeError:
            print("Note: Show message had TypeError, but debug mode was still set")

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
        # Ensure SquidBrainWindow instance exists and is visible
        if not self.squid_brain_window:
            # Try to create/get it if TamagotchiLogic is available
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                current_debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
                # Assuming SquidBrainWindow is instantiated and stored in tamagotchi_logic
                # or that tamagotchi_logic can provide it.
                # For this example, we'll rely on it being set during initialization or toggle.
                if hasattr(self.tamagotchi_logic, 'brain_window') and self.tamagotchi_logic.brain_window:
                    self.squid_brain_window = self.tamagotchi_logic.brain_window
                else: # Fallback to create if necessary (might need self.tamagotchi_logic to be passed)
                    self.squid_brain_window = SquidBrainWindow(self.tamagotchi_logic, current_debug_mode)
                    if hasattr(self.tamagotchi_logic, 'set_brain_window'): # If your logic sets it
                         self.tamagotchi_logic.set_brain_window(self.squid_brain_window)
            else:
                self.show_message("Brain Tool is not initialized yet.")
                return

        if not self.squid_brain_window.isVisible():
            self.squid_brain_window.show() # Show it if it's hidden

        # Ensure brain_widget exists within squid_brain_window
        if not hasattr(self.squid_brain_window, 'brain_widget') or not self.squid_brain_window.brain_widget:
            self.show_message("Brain widget component is not ready.")
            return

        # Use or create the instance of the enhanced neuron inspector
        if not hasattr(self, 'enhanced_neuron_inspector_instance') or \
           not self.enhanced_neuron_inspector_instance or \
           not self.enhanced_neuron_inspector_instance.isVisible():
            # The EnhancedNeuronInspector from brain_tool.py expects:
            # 1. brain_tool_window (which is self.squid_brain_window, an instance of SquidBrainWindow)
            # 2. brain_widget_ref (which is self.squid_brain_window.brain_widget)
            # Its QDialog parent is set internally to brain_tool_window.
            self.enhanced_neuron_inspector_instance = EnhancedNeuronInspector(
                brain_tool_window=self.squid_brain_window,
                brain_widget_ref=self.squid_brain_window.brain_widget
                # parent=self.window (Optionally, if you want the main QMainWindow as parent)
            )
        
        self.enhanced_neuron_inspector_instance.show()
        self.enhanced_neuron_inspector_instance.raise_()
        self.enhanced_neuron_inspector_instance.activateWindow()
        # Populate/refresh the inspector's neuron list and initial view
        self.enhanced_neuron_inspector_instance.update_neuron_list()
        if self.enhanced_neuron_inspector_instance.neuron_combo.count() > 0:
            self.enhanced_neuron_inspector_instance.update_info()

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


class NeurogenesisDebugDialog(QtWidgets.QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.brain_widget = brain_widget
        
        self.setWindowTitle("Neurogenesis Debug Information (Auto-Refreshes)")
        self.resize(650, 850) # Slightly wider for more details
        
        # Main layout
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Scrollable text area
        self.debug_text = QtWidgets.QTextEdit()
        self.debug_text.setReadOnly(True)
        # Use a monospace font for better table alignment if complex text tables are used
        # self.debug_text.setFont(QtGui.QFont("Monospace", 9)) 
        layout.addWidget(self.debug_text)
        
        # REMOVE Refresh button
        # refresh_button = QtWidgets.QPushButton("Refresh Data")
        # refresh_button.clicked.connect(self.update_debug_info)
        # layout.addWidget(refresh_button)
        
        # ADD QTimer for auto-refresh
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_debug_info)
        # Timer will be started in showEvent

        self.update_debug_info() # Initial update when dialog is created
    

    def update_debug_info(self):
        # Clear existing text
        self.debug_text.clear()
        
        # Simplified HTML styling for QTextEdit
        html_template = """
        <html>
        <head>
            <style type="text/css">
                body { font-family: Arial, sans-serif; font-size: 10pt; /* Standard font size for Qt */ }
                .container { padding: 5px; }
                .section { 
                    background-color: #f0f0f0; 
                    padding: 8px; 
                    margin-bottom: 8px; 
                    border: 1px solid #cccccc;
                }
                .title { 
                    font-weight: bold; 
                    color: #00007f; /* Dark Blue */
                    font-size: 12pt; 
                    margin-bottom: 5px; 
                    border-bottom: 1px solid #aaaaaa; 
                    padding-bottom: 2px;
                }
                .data table { 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin-top: 5px; 
                    font-size: 9pt; 
                }
                .data th, .data td { 
                    border: 1px solid #bbbbbb; 
                    padding: 4px; 
                    text-align: left; 
                    vertical-align: top; 
                }
                .data th { 
                    background-color: #dddddd; 
                    font-weight: bold; 
                    color: #333333;
                }
                /* Alternating row colors might need to be applied via Python if :nth-child is not supported */
                /* For simplicity, removed here. Can add <tr bgcolor="#f9f9f9"> in Python loop. */

                .metric-name { font-weight: bold; color: #333333; }
                .value-current { color: #0055aa; font-weight: bold; }
                .value-threshold { color: #007700; font-weight: bold; }
                .value-progress { font-size: 8pt; color: #444444; }
                .neuron-name { color: #770077; font-weight: bold; } /* Purple */
                .timestamp { font-size: 8pt; color: #444444; }
                .status-ok { color: #007700; } /* Green */
                .status-warning { color: #DD6600; } /* Orange */
                .status-active { color: #aa0000; } /* Red */
                .details-snapshot ul { margin-top: 2px; margin-bottom: 2px; padding-left: 15px; list-style-type: disc; }
                .details-snapshot li { margin-bottom: 1px; }
                .code { font-family: 'Courier New', Courier, monospace; background-color: #eeeeee; padding: 1px 2px; font-size: 8pt;}
            </style>
        </head>
        <body><div class="container">
        """
        
        # --- Data Gathering and HTML Construction (largely the same logic as before) ---
        if hasattr(self.brain_widget, 'neurogenesis_data') and self.brain_widget.neurogenesis_data and \
           hasattr(self.brain_widget, 'neurogenesis_config') and self.brain_widget.neurogenesis_config:
            data = self.brain_widget.neurogenesis_data
            config = self.brain_widget.neurogenesis_config
            
            # Counters and Thresholds Section
            html_template += f"""
            <div class="section">
                <div class="title">&#x1F9E0; Neurogenesis Counters &amp; Thresholds</div>
                <div class="data">
                    <table>
                        <tr><th>Metric</th><th>Current Value</th><th>Config Threshold</th><th>Progress</th></tr>"""
            
            metrics = [
                ('Novelty', data.get('novelty_counter', 0), config.get('novelty_threshold', 3)),
                ('Stress', data.get('stress_counter', 0), config.get('stress_threshold', 0.7)),
                ('Reward', data.get('reward_counter', 0), config.get('reward_threshold', 0.6))
            ]
            
            for name, current_val, threshold_val in metrics:
                progress_percent = (current_val / threshold_val) * 100 if threshold_val > 0 else 0
                progress_percent = min(100, max(0, progress_percent)) # Cap at 0-100
                html_template += f"""
                        <tr>
                            <td class="metric-name">{name} Counter</td>
                            <td><span class="value-current">{current_val:.3f}</span></td>
                            <td><span class="value-threshold">{threshold_val}</span></td>
                            <td><span class="value-progress">{progress_percent:.1f}%</span></td>
                        </tr>"""
            html_template += "</table></div></div>"

            # Status and Limits Section
            last_creation_time = data.get('last_neuron_time', 0)
            time_since_last = time.time() - last_creation_time if last_creation_time > 0 else -1
            cooldown_period = config.get('cooldown', 300)
            cooldown_active = time_since_last >= 0 and time_since_last < cooldown_period
            cooldown_status_class = "status-active" if cooldown_active else "status-ok"
            cooldown_text = f"{time_since_last:.1f}s ago (Cooldown: {'Active' if cooldown_active else 'Inactive'})" if time_since_last >=0 else "N/A"

            pruning_enabled_val = self.brain_widget.pruning_enabled if hasattr(self.brain_widget, 'pruning_enabled') else 'N/A'
            pruning_status_class = "status-ok" if pruning_enabled_val else "status-warning"
            
            current_neurons_val = len(self.brain_widget.neuron_positions) - len(self.brain_widget.excluded_neurons) if hasattr(self.brain_widget, 'neuron_positions') and hasattr(self.brain_widget, 'excluded_neurons') else 'N/A'
            max_neurons_val = config.get('max_neurons', 20)
            
            html_template += f"""
            <div class="section">
                <div class="title">&#x2699;&#xFE0F; Neuron Creation Status &amp; Limits</div>
                <div class="data">
                    <table>
                        <tr><td class="metric-name">Last Neuron Created:</td><td class="timestamp">{time.ctime(last_creation_time) if last_creation_time else 'N/A'}</td></tr>
                        <tr><td class="metric-name">Time Since Last / Cooldown:</td><td class="{cooldown_status_class}">{cooldown_text} / {cooldown_period}s</td></tr>
                        <tr><td class="metric-name">Pruning Enabled:</td><td class="{pruning_status_class}">{pruning_enabled_val}</td></tr>
                        <tr><td class="metric-name">Max Neurons (if pruning):</td><td>{max_neurons_val}</td></tr>
                        <tr><td class="metric-name">Current Eligible Neurons:</td><td>{current_neurons_val}</td></tr>
                        <tr><td class="metric-name">Neurogenesis Neurons Count:</td><td>{len(data.get('new_neurons_details', {}))}</td></tr>
                    </table>
                </div>
            </div>"""
            
            # Detailed Neurogenesis Neuron Info Section
            new_neurons_details = data.get('new_neurons_details', {})
            if new_neurons_details:
                html_template += """
                <div class="section">
                    <div class="title">&#x1F4A1; Details of Neurogenesis Neurons</div>
                    <div class="data"><table>
                        <tr>
                            <th>Neuron Name</th>
                            <th>Created At</th>
                            <th>Trigger Type</th>
                            <th>Trigger Value</th>
                            <th>Associated State Snapshot</th>
                        </tr>"""
                sorted_neuron_details = sorted(new_neurons_details.items(), key=lambda item: item[1].get('created_at', 0), reverse=True)

                for name, details in sorted_neuron_details:
                    created_at_val = details.get('created_at')
                    created_at_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at_val)) if created_at_val else "Unknown"
                    trigger_type = str(details.get('trigger_type', "N/A")).capitalize()
                    trigger_value_raw = details.get('trigger_value_at_creation', "N/A")
                    trigger_value_str = f"{trigger_value_raw:.2f}" if isinstance(trigger_value_raw, float) else str(trigger_value_raw)
                    
                    snapshot = details.get('associated_state_snapshot', {})
                    snapshot_html = "<ul class='details-snapshot'>"
                    if snapshot:
                        for k, v_snap in snapshot.items():
                            if v_snap is not None:
                                snapshot_html += f"<li><span class='metric-name'>{k.capitalize()}:</span> <span class='code'>{v_snap}</span></li>"
                    else:
                        snapshot_html += "<li>N/A</li>"
                    snapshot_html += "</ul>"

                    html_template += f"""
                        <tr>
                            <td><span class="neuron-name">{name}</span></td>
                            <td class="timestamp">{created_at_str}</td>
                            <td>{trigger_type}</td>
                            <td><span class="value-current">{trigger_value_str}</span></td>
                            <td>{snapshot_html}</td>
                        </tr>"""
                html_template += "</table></div></div>"
            else:
                html_template += """
                <div class="section">
                    <div class="title">&#x1F4A1; Details of Neurogenesis Neurons</div>
                    <div class="data"><p>No neurogenesis neurons with details found.</p></div>
                </div>"""
        else:
            html_template += "<div class='section'><div class='title'>Error</div><p class='data status-active'>Neurogenesis data or configuration not available from BrainWidget.</p></div>"
        
        html_template += "</div></body></html>"
        
        self.debug_text.setHtml(html_template)

    def showEvent(self, event):
        """Start the timer when the dialog is shown."""
        if not self.update_timer.isActive():
            self.update_timer.start(1000) # 1 second
        self.update_debug_info() # Refresh immediately on show
        super().showEvent(event)

    def hideEvent(self, event):
        """Stop the timer when the dialog is hidden/closed."""
        self.update_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        """Ensure the timer stops when the dialog is explicitly closed."""
        self.update_timer.stop()
        super().closeEvent(event)