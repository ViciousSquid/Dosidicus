# UI Stuff

import os
import json
import math
import time
import random
import base64
import uuid
import traceback
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QObject, pyqtProperty
from PyQt5.QtWidgets import QGraphicsPixmapItem
from .brain_tool import SquidBrainWindow
from .statistics_window import StatisticsWindow
from .brain_tool import NeuronInspector as EnhancedNeuronInspector
from .plugin_manager_dialog import PluginManagerDialog
from .tutorial import TutorialManager
from .vision import VisionWindow
from .task_manager import TaskManagerWindow
from .laboratory import NeurogenesisDebugDialog
from .preferences import PreferencesWindow
from .localisation import Localization

class ActionButton(QtWidgets.QPushButton):
    """Custom button with hover and press color states"""
    def __init__(self, text, hover_color, pressed_color, font_size=16, parent=None):
        super().__init__(text, parent)
        self.hover_color = hover_color
        self.pressed_color = pressed_color
        self.font_size = font_size
        self.is_pressed = False
        self.is_hovered = False
        self.update_style()
    
    def update_style(self):
        """Update button style based on current state"""
        if self.is_pressed:
            bg_color = self.pressed_color
            text_color = "white"
        elif self.is_hovered:
            bg_color = self.hover_color
            text_color = "black"
        else:
            bg_color = "white"
            text_color = "black"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: {text_color};
                border: 2px solid black;
                font-weight: bold;
                font-size: {self.font_size}px;
            }}
        """)
    
    def enterEvent(self, event):
        self.is_hovered = True
        self.update_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.is_hovered = False
        self.update_style()
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_pressed = True
            self.update_style()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.is_pressed = False
            self.update_style()
        super().mouseReleaseEvent(event)


class DecorationItem(QtWidgets.QLabel):
    def __init__(self, pixmap, filename):
        super().__init__()
        from .display_scaling import DisplayScaling
        item_size = DisplayScaling.scale(128)
        self.setPixmap(pixmap.scaled(item_size, item_size, 
                                     QtCore.Qt.KeepAspectRatio, 
                                     QtCore.Qt.SmoothTransformation))
        self.filename = filename
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

    def boundingRect(self):
        return super().boundingRect()

    def wheelEvent(self, event):
        if self.filename and ('rock01' in self.filename.lower() or 'rock02' in self.filename.lower()):
            return super().wheelEvent(event)
        if self.isSelected() and self.original_pixmap:
            from .display_scaling import DisplayScaling
            delta = event.angleDelta().y() / 120
            scale_factor = 1.1 if delta > 0 else 0.9
            current_width = self.pixmap().width()
            current_height = self.pixmap().height()
            min_size = DisplayScaling.scale(64)
            new_width = max(min_size, int(current_width * scale_factor))
            new_height = max(min_size, int(current_height * scale_factor))
            scaled_pixmap = self.original_pixmap.scaled(
                new_width, new_height,
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            event.accept()
        else:
            super().wheelEvent(event)

    def paint(self, painter, option, widget):
        option_copy = QtWidgets.QStyleOptionGraphicsItem(option)
        option_copy.state &= ~QtWidgets.QStyle.State_Selected
        super().paint(painter, option_copy, widget)
        
        if self.isSelected():
            pixmap = self.pixmap()
            if pixmap:
                painter.save()
                painter.setPen(QtGui.QPen(QtGui.QColor(30, 144, 255), 2))
                rect = QtCore.QRectF(0, 0, pixmap.width(), pixmap.height())
                painter.drawRect(rect)
                painter.restore()

    def mousePressEvent(self, event):
        pos = event.pos()
        self.last_mouse_pos = pos
        self.resize_mode = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        current_pos = event.pos()
        if self.resize_mode and self.original_pixmap and self.last_mouse_pos:
            delta_x = current_pos.x() - self.last_mouse_pos.x()
            delta_y = current_pos.y() - self.last_mouse_pos.y()
            current_width = self.pixmap().width()
            current_height = self.pixmap().height()
            new_width = max(30, current_width + delta_x)
            new_height = max(30, current_height + delta_y)
            scaled_pixmap = self.original_pixmap.scaled(
                int(new_width), int(new_height),
                QtCore.Qt.KeepAspectRatio,
                QtCore.Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
            self.last_mouse_pos = current_pos
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
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
        loc = Localization.instance()
        self.setWindowTitle(f"{loc.get('decorations')} (D)")
        
        from .display_scaling import DisplayScaling
        self.setFixedWidth(DisplayScaling.scale(800))
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
                scaled_pixmap = pixmap.scaled(item_size, item_size, 
                                        QtCore.Qt.KeepAspectRatio, 
                                        QtCore.Qt.SmoothTransformation)
                item = DecorationItem(scaled_pixmap, full_path)
                self.grid_layout.addWidget(item, row, col)
                col += 1
                if col >= items_per_row:
                    col = 0
                    row += 1
        self.setFixedHeight(min((row + 1) * (item_size + DisplayScaling.scale(20)) + DisplayScaling.scale(40), DisplayScaling.scale(650)))

class Ui:
    def __init__(self, window, debug_mode=False):
        self.window = window
        self.awarded_decorations = set()
        self.tamagotchi_logic = None
        self.debug_mode = debug_mode
        self.setup_neurogenesis_debug_shortcut()
        self.setup_decorations_shortcut()
        
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        from .display_scaling import DisplayScaling
        DisplayScaling.initialize(screen_size.width(), screen_size.height())
        
        if screen_size.width() <= 1920:
            base_width = 1440
            base_height = 960
        else:
            base_width = 1344
            base_height = 936

        self.window.setMinimumSize(DisplayScaling.scale(base_width), DisplayScaling.scale(base_height))
        self.window_width = DisplayScaling.scale(base_width)
        self.window_height = DisplayScaling.scale(base_height)
        self.window.setWindowTitle("Dosidicus")
        self.window.resize(self.window_width, self.window_height)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.tutorial_manager = TutorialManager(self, window)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.view.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.window.setCentralWidget(self.view)

        self.setup_ui_elements()
        self.setup_menu_bar()
        self.enhanced_neuron_inspector_instance = None
        self.squid_brain_window = None

        loc = Localization.instance()
        self.debug_text = QtWidgets.QGraphicsTextItem(loc.get('debug'))
        self.debug_text.setDefaultTextColor(QtGui.QColor("#a9a9a9"))
        font = QtGui.QFont()
        font.setPointSize(DisplayScaling.scale(20))
        self.debug_text.setFont(font)
        self.debug_text.setRotation(-90)
        self.debug_text.setPos(DisplayScaling.scale(75), DisplayScaling.scale(75))
        self.debug_text.setZValue(999)
        self.debug_text.setVisible(self.debug_mode)
        self.scene.addItem(self.debug_text)

        self.decoration_window = DecorationWindow(self.window)
        self.decoration_window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.Tool)
        self.decoration_window.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
        self.statistics_window = None

        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = self.dragEnterEvent
        self.view.dragMoveEvent = self.dragMoveEvent
        self.view.dropEvent = self.dropEvent
        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.view.keyPressEvent = self.keyPressEvent
        
        try:
            from status_bar_component import StatusBarComponent
            self.status_bar = StatusBarComponent(self.window)
        except ImportError:
            print("Status bar component not available, skipping")
        self.optimize_animations()

    def setup_neurogenesis_debug_shortcut(self):
        self.neurogenesis_debug_shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.ALT + QtCore.Qt.Key_N), 
            self.window
        )
        self.neurogenesis_debug_shortcut.activated.connect(self.show_neurogenesis_debug)

    def show_neurogenesis_debug(self):
        if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
            print("Brain window not initialized")
            return
        if not hasattr(self, '_neurogenesis_debug_dialog'):
            self._neurogenesis_debug_dialog = NeurogenesisDebugDialog(
                self.squid_brain_window.brain_widget, 
                self.window
            )
        self._neurogenesis_debug_dialog.update_debug_info()
        self._neurogenesis_debug_dialog.show()
        self._neurogenesis_debug_dialog.raise_()

    def setup_decorations_shortcut(self):
        self.decorations_shortcut = QtWidgets.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key_D), 
            self.window
        )
        self.decorations_shortcut.activated.connect(self.show_decorations_window)

    def show_decorations_window(self):
        self.decoration_window.show()
        self.decoration_window.activateWindow()
        self.decoration_window.raise_()

    def optimize_animations(self):
        self.scene.setItemIndexMethod(QtWidgets.QGraphicsScene.NoIndex)
        self.view.setCacheMode(QtWidgets.QGraphicsView.CacheBackground)

    def set_tamagotchi_logic(self, logic):
        self.tamagotchi_logic = logic
        if hasattr(logic, 'debug_mode'):
            self.debug_mode = logic.debug_mode
            self.debug_action.setChecked(self.debug_mode)
            self.debug_text.setVisible(self.debug_mode)
        if hasattr(self, 'neurogenesis_action'):
            self.neurogenesis_action.triggered.connect(self.trigger_neurogenesis)
        self.create_multiplayer_menu()

    def show_tutorial_overlay(self):
        self.tutorial_manager.start_tutorial()

    def remove_tutorial_overlay(self):
        self.tutorial_manager.advance_to_next_step()

    def show_second_tutorial_banner(self):
        win_width = self.window_width
        win_height = self.window_height
        banner_height = 100
        banner = QtWidgets.QGraphicsRectItem(0, win_height - banner_height, win_width, banner_height)
        banner.setBrush(QtGui.QColor(25, 25, 112, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(135, 206, 250, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.scene.addItem(banner)
        title_text = QtWidgets.QGraphicsTextItem("🧠 NEURAL NETWORK")
        title_text.setDefaultTextColor(QtGui.QColor(135, 206, 250))
        title_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        title_text.setPos(20, win_height - banner_height + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.scene.addItem(title_text)
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
        dismiss_proxy = self.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, win_height - banner_height + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_timer = QtCore.QTimer()
        self.tutorial_timer.timeout.connect(self.close_tutorial_completely)
        self.tutorial_timer.setSingleShot(True)
        self.tutorial_timer.start(12000)

    def close_tutorial_completely(self):
        if hasattr(self, 'tutorial_timer') and self.tutorial_timer.isActive():
            self.tutorial_timer.stop()
        for item in self.scene.items():
            if hasattr(item, '_is_tutorial_element'):
                self.scene.removeItem(item)
        self.scene.update()

    def open_brain_designer(self):
        self.set_simulation_speed(0)
        self.show_message("Simulation paused for Brain Designer")
        import multiprocessing
        try:
            from .brain_designer_launcher import launch_brain_designer_process
        except ImportError as e:
            QtWidgets.QMessageBox.critical(
                self.window,
                "Missing Launcher",
                "Cannot find brain_designer_launcher.py!\n\n"
                "Make sure the file exists in the 'src' folder."
            )
            print(f"Import error: {e}")
            return
        if hasattr(self, '_brain_designer_process') and \
           getattr(self._brain_designer_process, 'is_alive', lambda: False)():
            QtWidgets.QMessageBox.information(
                self.window,
                "Already Running",
                "Brain Designer is already open!"
            )
            return
        try:
            debug_mode = getattr(self, 'debug_mode', False)
            self._brain_designer_process = multiprocessing.Process(
                target=launch_brain_designer_process,
                args=(debug_mode,),
                daemon=False
            )
            self._brain_designer_process.start()
            print(f"Brain Designer launched (PID: {self._brain_designer_process.pid})"
                  f"{' [debug mode]' if debug_mode else ''}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self.window,
                "Launch Failed",
                f"Could not start Brain Designer:\n\n{e}"
            )

    def setup_plugin_menu(self, plugin_manager_instance):
        loc = Localization.instance()
        if not hasattr(self, 'plugins_menu'):
            self.plugins_menu = self.menu_bar.addMenu(loc.get('plugins'))
        if not hasattr(self, 'plugin_manager_action') or not self.plugin_manager_action:
            self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
            self.plugins_menu.addAction(self.plugin_manager_action)
            self.plugins_menu.addSeparator()
        if plugin_manager_instance:
             self.apply_plugin_menu_registrations(plugin_manager_instance)

    def create_multiplayer_menu(self):
        if hasattr(self.tamagotchi_logic, 'plugin_manager'):
            self.setup_plugin_menu(self.tamagotchi_logic.plugin_manager)
        else:
            print("WARNING: create_multiplayer_menu called but plugin_manager is not available")

    def apply_plugin_menu_registrations(self, plugin_manager):
        loc = Localization.instance()
        if not hasattr(self, 'plugins_menu') or not self.plugins_menu:
            self.plugins_menu = self.menu_bar.addMenu(loc.get('plugins'))
            self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
            self.plugins_menu.addAction(self.plugin_manager_action)
            self.plugins_menu.addSeparator()
        elif not hasattr(self, 'plugin_manager_action') or \
             not self.plugin_manager_action or \
             self.plugin_manager_action not in self.plugins_menu.actions():
            self.plugin_manager_action = QtWidgets.QAction('Plugin Manager', self.window)
            try:
                self.plugin_manager_action.triggered.disconnect()
            except TypeError:
                pass
            all_actions = self.plugins_menu.actions()
            if all_actions and all_actions[0].isSeparator():
                self.plugins_menu.insertAction(all_actions[0], self.plugin_manager_action)
            elif all_actions:
                self.plugins_menu.insertAction(all_actions[0], self.plugin_manager_action)
            else:
                self.plugins_menu.addAction(self.plugin_manager_action)
            current_actions = self.plugins_menu.actions()
            pm_action_index = current_actions.index(self.plugin_manager_action) if self.plugin_manager_action in current_actions else -1
            if pm_action_index != -1:
                if pm_action_index + 1 >= len(current_actions) or not current_actions[pm_action_index + 1].isSeparator():
                    sep = QtWidgets.QAction(self.window)
                    sep.setSeparator(True)
                    self.plugins_menu.insertAction(current_actions[pm_action_index + 1] if pm_action_index + 1 < len(current_actions) else None, sep)
        try:
            self.plugin_manager_action.triggered.disconnect()
        except TypeError:
            pass
        if plugin_manager:
            self.plugin_manager_action.triggered.connect(
                lambda: self.show_plugin_manager(plugin_manager)
            )
            self.plugin_manager_action.setEnabled(True)
            self.plugin_manager_action.setToolTip("Open the plugin manager.")
        else:
            self.plugin_manager_action.setEnabled(False)
            self.plugin_manager_action.setToolTip("Plugin manager is not available.")
        
        actions_to_remove = []
        separator_after_pm_action_found = False
        pm_action_ref = self.plugin_manager_action
        if pm_action_ref and pm_action_ref in self.plugins_menu.actions():
            pm_action_index = self.plugins_menu.actions().index(pm_action_ref)
            if pm_action_index + 1 < len(self.plugins_menu.actions()):
                next_action = self.plugins_menu.actions()[pm_action_index + 1]
                if next_action.isSeparator():
                    separator_after_pm_action_found = True
                    for i in range(pm_action_index + 2, len(self.plugins_menu.actions())):
                        actions_to_remove.append(self.plugins_menu.actions()[i])
        if not separator_after_pm_action_found:
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
        if plugin_manager and hasattr(plugin_manager, 'plugins'):
            enabled_plugin_keys = plugin_manager.get_enabled_plugins()
            for plugin_name_key, plugin_data_dict in plugin_manager.plugins.items():
                if plugin_name_key not in enabled_plugin_keys:
                    continue
                plugin_instance = plugin_data_dict.get('instance')
                original_name = plugin_data_dict.get('original_name', plugin_name_key.capitalize())
                if plugin_instance and hasattr(plugin_instance, 'register_menu_actions'):
                    plugin_submenu = self.plugins_menu.addMenu(original_name)
                    try:
                        plugin_instance.register_menu_actions(self.window, plugin_submenu)
                    except Exception as e:
                        print(f"Error calling register_menu_actions for {original_name}: {e}")
        print("Applied all plugin menu registrations")

    def toggle_plugin(self, plugin_name, enable_flag):
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'plugin_manager'):
            plugin_mgr = self.tamagotchi_logic.plugin_manager
            if plugin_name not in plugin_mgr.plugins:
                print(f"WARNING:UI: Attempted to toggle plugin '{plugin_name}', but it's not loaded/found in plugin_mgr.plugins.")
                return
            success = False
            if enable_flag:
                print(f"INFO:UI: Requesting PluginManager to enable plugin '{plugin_name}'.")
                success = plugin_mgr.enable_plugin(plugin_name)
                if success:
                    print(f"INFO:UI: PluginManager reported success enabling '{plugin_name}'.")
                else:
                    print(f"WARNING:UI: PluginManager reported failure enabling '{plugin_name}'.")
            else:
                print(f"INFO:UI: Requesting PluginManager to disable plugin '{plugin_name}'.")
                success = plugin_mgr.disable_plugin(plugin_name)
                if success:
                    print(f"INFO:UI: PluginManager reported success disabling '{plugin_name}'.")
                else:
                    print(f"WARNING:UI: PluginManager reported failure disabling '{plugin_name}'.")
            if hasattr(self, 'setup_plugin_menu') and callable(self.setup_plugin_menu):
                self.setup_plugin_menu(plugin_mgr)
            else:
                print("WARNING:UI: setup_plugin_menu method not found, cannot refresh UI after toggle.")
        else:
            print("WARNING:UI: Cannot toggle plugin - TamagotchiLogic or PluginManager not available.")

    def show_plugin_manager(self, plugin_manager):
        dialog = PluginManagerDialog(plugin_manager, self.window)
        dialog.exec_()
        self.setup_plugin_menu(plugin_manager)

    def setup_ui_elements(self):
        loc = Localization.instance()
        self.rect_item = self.scene.addRect(50, 50, self.window_width - 100, self.window_height - 100,
                                        QtGui.QPen(QtGui.QColor(0, 0, 0)), QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.cleanliness_overlay = self.scene.addRect(50, 50, self.window_width - 100, self.window_height - 100,
                                                    QtGui.QPen(QtCore.Qt.NoPen), QtGui.QBrush(QtGui.QColor(139, 69, 19, 0)))
        
        self.dirty_text_items = []
        self.dirty_text_target_count = 0

        self.feeding_message = QtWidgets.QGraphicsTextItem(loc.get("feed_msg"))
        self.feeding_message.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        self.feeding_message.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self.feeding_message.setPos(0, self.window_height - 75)
        self.feeding_message.setTextWidth(self.window_width)
        self.feeding_message.setHtml(f'<div style="text-align: center;">{loc.get("feed_msg")}</div>')
        self.feeding_message.setOpacity(0)
        self.scene.addItem(self.feeding_message)

        self.points_label = QtWidgets.QGraphicsTextItem(loc.get("points") + ":")
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

        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setSceneRect(0, 0, self.window_width, self.window_height)
        self.original_view_wheel_event = self.view.wheelEvent
        self.view.wheelEvent = self.custom_wheel_event

        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.debug_text.setVisible(getattr(self.tamagotchi_logic, 'debug_mode', False))
        
        self.create_action_buttons()

    def custom_wheel_event(self, event):
        selected_items = self.scene.selectedItems()
        resizable_selected = [item for item in selected_items if 
                            isinstance(item, ResizablePixmapItem)]
        if resizable_selected:
            for item in resizable_selected:
                try:
                    item.wheelEvent(event)
                except Exception as e:
                    print(f"Error in wheel event handling: {e}")
        event.accept()

    def create_action_buttons(self):
        from .display_scaling import DisplayScaling
        try:
            from .config_manager import ConfigManager
            config = ConfigManager()
            display_config = config.get_display_config()
            button_width = display_config['button_width']
            button_height = display_config['button_height']
            button_spacing = display_config['button_spacing']
            button_font_size = display_config['button_font_size']
        except Exception as e:
            print(f"Warning: Could not load display config, using defaults: {e}")
            button_width = 140
            button_height = 50
            button_spacing = 20
            button_font_size = 16
        
        button_width = DisplayScaling.scale(button_width)
        button_height = DisplayScaling.scale(button_height)
        button_spacing = DisplayScaling.scale(button_spacing)
        button_font_size = DisplayScaling.font_size(button_font_size)
        
        total_width = (button_width * 3) + (button_spacing * 2)
        start_x = (self.window_width - total_width) / 2
        y_pos = DisplayScaling.scale(15)
        
        loc = Localization.instance()
        button_configs = [
            (loc.get("feed_btn"), "#C8E6C9", "#4CAF50", "feed_action"),
            (loc.get("clean_btn"), "#B3E5FC", "#2196F3", "clean_action"),
            (loc.get("medicine_btn"), "#FFCDD2", "#F44336", "medicine_action")
        ]
        
        self.action_buttons = []
        for i, (text, hover_color, pressed_color, action_name) in enumerate(button_configs):
            x_pos = start_x + (i * (button_width + button_spacing))
            button = ActionButton(text, hover_color, pressed_color, button_font_size)
            button.setFixedSize(button_width, button_height)
            button.action_name = action_name
            proxy = self.scene.addWidget(button)
            proxy.setPos(x_pos, y_pos)
            proxy.setZValue(10000)
            self.action_buttons.append((button, proxy))
        
    def connect_action_buttons(self):
        if not hasattr(self, 'action_buttons'):
            return
        for button, proxy in self.action_buttons:
            if hasattr(button, 'action_name'):
                action = getattr(self, button.action_name, None)
                if action:
                    button.clicked.connect(action.trigger)

    def update_dirty_text(self, cleanliness):
        if cleanliness >= 25:
            if self.dirty_text_items:
                self.clear_dirty_text()
            return
        tank_left = 50
        tank_right = self.window_width - 50
        tank_top = 50
        tank_bottom = self.window_height - 50
        tank_width = tank_right - tank_left
        tank_height = tank_bottom - tank_top
        font_size = 8
        word_width = font_size * 9
        word_height = font_size + 14
        cols = max(1, int(tank_width / word_width))
        rows = max(1, int(tank_height / word_height))
        max_words = cols * rows
        progress = (25.0 - float(cleanliness)) / 25.0
        target_count = int(progress * max_words)
        self.dirty_text_target_count = target_count
        current_count = len(self.dirty_text_items)
        if current_count < target_count:
            words_to_add = target_count - current_count
            for _ in range(words_to_add):
                word_index = len(self.dirty_text_items)
                row_from_bottom = word_index // cols
                col = word_index % cols
                x = tank_left + (col * word_width) + random.randint(-2, 2)
                y = tank_bottom - ((row_from_bottom + 1) * word_height) + random.randint(-1, 1)
                if y < tank_top:
                    break
                loc = Localization.instance()
                dirty_text = QtWidgets.QGraphicsTextItem(loc.get("dirty"))
                dirty_text.setDefaultTextColor(QtGui.QColor(101, 67, 33))
                font = QtGui.QFont("Arial", font_size, QtGui.QFont.Bold)
                dirty_text.setFont(font)
                dirty_text.setPos(x, y)
                dirty_text.setZValue(1000)
                dirty_text.setData(0, "dirty_text")
                self.scene.addItem(dirty_text)
                self.dirty_text_items.append(dirty_text)
            self.scene.update()
        elif current_count > target_count:
            words_to_remove = current_count - target_count
            for _ in range(words_to_remove):
                if self.dirty_text_items:
                    item = self.dirty_text_items.pop()
                    self.scene.removeItem(item)
            self.scene.update()
    
    def clear_dirty_text(self):
        for item in self.dirty_text_items:
            self.scene.removeItem(item)
        self.dirty_text_items.clear()
        self.dirty_text_target_count = 0
        self.scene.update()

    def check_neurogenesis(self, state):
        current_time = time.time()
        
        if state.get('_debug_forced_neurogenesis', False):
            new_name = f"debug_neuron_{int(current_time)}"
            if self.neuron_positions:
                center_x = sum(pos[0] for pos in self.neuron_positions.values()) / len(self.neuron_positions)
                center_y = sum(pos[1] for pos in self.neuron_positions.values()) / len(self.neuron_positions)
            else:
                center_x, center_y = 600, 300
            self.neuron_positions[new_name] = (
                center_x + random.randint(-100, 100),
                center_y + random.randint(-100, 100)
            )
            self.state[new_name] = 80
            self.state_colors[new_name] = (150, 200, 255)
            for existing in self.neuron_positions:
                if existing != new_name:
                    self.weights[(new_name, existing)] = random.uniform(-0.8, 0.8)
                    self.weights[(existing, new_name)] = random.uniform(-0.8, 0.8)
            if 'new_neurons' not in self.neurogenesis_data:
                self.neurogenesis_data['new_neurons'] = []
            self.neurogenesis_data['new_neurons'].append(new_name)
            self.neurogenesis_data['last_neuron_time'] = current_time
            print(f"DEBUG: Created neuron '{new_name}' at {self.neuron_positions[new_name]}")
            print(f"New connections: {[(k,v) for k,v in self.weights.items() if new_name in k]}")
            self.update()
            return True

        if current_time - self.neurogenesis_data.get('last_neuron_time', 0) > self.neurogenesis_config['cooldown']:
            created = False
            if state.get('novelty_exposure', 0) > self.neurogenesis_config['novelty_threshold']:
                self._create_neuron_internal('novelty', state)
                created = True
            if state.get('sustained_stress', 0) > self.neurogenesis_config['stress_threshold']:
                self._create_neuron_internal('stress', state)
                created = True
            if state.get('recent_rewards', 0) > self.neurogenesis_config['reward_threshold']:
                self._create_neuron_internal('reward', state)
                created = True
            return created
        return False
    
    def _create_neuron(self, neuron_type, trigger_data):
        base_name = {
            'novelty': 'novel',
            'stress': 'defense', 
            'reward': 'reward'
        }[neuron_type]
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        active_neurons = sorted(
            [(k, v) for k, v in self.state.items() if isinstance(v, (int, float))],
            key=lambda x: x[1],
            reverse=True
        )
        if active_neurons:
            base_x, base_y = self.neuron_positions[active_neurons[0][0]]
        else:
            base_x, base_y = 600, 300
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )
        self.state[new_name] = 50
        self.state_colors[new_name] = {
            'novelty': (255, 255, 150),
            'stress': (255, 150, 150),
            'reward': (150, 255, 150)
        }[neuron_type]
        default_weights = {
            'novelty': {'curiosity': 0.6, 'anxiety': -0.4},
            'stress': {'anxiety': -0.7, 'happiness': 0.3},
            'reward': {'satisfaction': 0.8, 'happiness': 0.5}
        }
        for target, weight in default_weights[neuron_type].items():
            self.weights[(new_name, target)] = weight
            self.weights[(target, new_name)] = weight * 0.5
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        return new_name
    
    def trigger_neurogenesis(self):
        try:
            if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
                print("Brain window not found")
                self.show_message("Brain window not initialized")
                return
            brain = self.squid_brain_window.brain_widget
            import time
            import random
            prev_neurons = set(brain.neuron_positions.keys())
            new_name = f"forced_{int(time.time())}"
            if brain.neuron_positions:
                x_values = [pos[0] for pos in brain.neuron_positions.values()]
                y_values = [pos[1] for pos in brain.neuron_positions.values()]
                center_x = sum(x_values) / len(x_values)
                center_y = sum(y_values) / len(y_values)
            else:
                center_x, center_y = 600, 300
            pos_x = center_x + random.randint(-100, 100)
            pos_y = center_y + random.randint(-100, 100)
            print(f"Creating neuron {new_name} at ({pos_x}, {pos_y})")
            brain.neuron_positions[new_name] = (pos_x, pos_y)
            brain.state[new_name] = 75
            if hasattr(brain, 'state_colors'):
                brain.state_colors[new_name] = (150, 200, 255)
            for existing in list(prev_neurons):
                if existing in getattr(brain, 'excluded_neurons', []):
                    continue
                weight = random.uniform(-0.3, 0.3)
                brain.weights[(new_name, existing)] = weight
                brain.weights[(existing, new_name)] = weight * 0.8
            if hasattr(brain, 'neurogenesis_data'):
                if 'new_neurons' not in brain.neurogenesis_data:
                    brain.neurogenesis_data['new_neurons'] = []
                brain.neurogenesis_data['new_neurons'].append(new_name)
                brain.neurogenesis_data['last_neuron_time'] = time.time()
            if hasattr(brain, 'neurogenesis_highlight'):
                brain.neurogenesis_highlight = {
                    'neuron': new_name,
                    'start_time': time.time(),
                    'duration': 5.0
                }
            brain.update()
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
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                self.scene.removeItem(item)
        win_width = self.window_width
        win_height = self.window_height
        from .display_scaling import DisplayScaling
        loc = Localization.instance()

        if is_paused:
            background = QtWidgets.QGraphicsRectItem(
                -DisplayScaling.scale(200),
                (win_height - DisplayScaling.scale(250)) / 2,
                win_width + DisplayScaling.scale(400),
                DisplayScaling.scale(250)
            )
            background.setBrush(QtGui.QColor(0, 0, 0, 180))
            background.setPen(QtGui.QPen(QtCore.Qt.NoPen))
            background.setZValue(1000)
            background.original_rect = background.rect()
            setattr(background, '_is_pause_message', True)
            self.scene.addItem(background)

            pause_font = QtGui.QFont("Arial", DisplayScaling.font_size(24), QtGui.QFont.Bold)
            pause_text = self.scene.addText(loc.get("paused_msg"), pause_font)
            pause_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            pause_text.setZValue(1002)
            setattr(pause_text, '_is_pause_message', True)
            
            text_rect = pause_text.boundingRect()
            pause_text_x = (win_width - text_rect.width()) / 2
            pause_text_y = (win_height - text_rect.height()) / 2 - DisplayScaling.scale(30)
            pause_text.setPos(pause_text_x, pause_text_y)

            sub_font = QtGui.QFont("Arial", DisplayScaling.font_size(14))
            sub_text = self.scene.addText(loc.get("paused_sub"), sub_font)
            sub_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
            sub_text.setZValue(1002)
            setattr(sub_text, '_is_pause_message', True)
            
            sub_rect = sub_text.boundingRect()
            sub_text_x = (win_width - sub_rect.width()) / 2
            sub_text_y = pause_text_y + text_rect.height() + 10
            sub_text.setPos(sub_text_x, sub_text_y)
        
            self.pause_redraw_timer = QtCore.QTimer()
            self.pause_redraw_timer.timeout.connect(self._redraw_pause_message)
            self.pause_redraw_timer.start(500)
        else:
            if hasattr(self, 'pause_redraw_timer'):
                self.pause_redraw_timer.stop()

    def _remove_all_pause_elements(self):
        if hasattr(self, 'pause_redraw_timer') and self.pause_redraw_timer:
            self.pause_redraw_timer.stop()
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                self.scene.removeItem(item)

    def _redraw_pause_message(self):
        if not hasattr(self, 'tamagotchi_logic') or self.tamagotchi_logic.simulation_speed != 0:
            if hasattr(self, 'pause_redraw_timer'):
                self.pause_redraw_timer.stop()
            return
        for item in self.scene.items():
            if hasattr(item, '_is_pause_message'):
                if isinstance(item, QtWidgets.QGraphicsRectItem) and hasattr(item, 'original_rect'):
                    item.setRect(item.original_rect)
                else:
                    self.scene.removeItem(item)
        win_width = self.window_width
        win_height = self.window_height
        loc = Localization.instance()

        background = QtWidgets.QGraphicsRectItem(
            -200,
            (win_height - 250) / 2,
            win_width + 400,
            250
        )
        background.setBrush(QtGui.QColor(0, 0, 0, 180))
        background.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        background.setZValue(1000)
        background.original_rect = background.rect()
        setattr(background, '_is_pause_message', True)
        self.scene.addItem(background)

        pause_text = self.scene.addText(loc.get("paused_msg"), QtGui.QFont("Arial", 24, QtGui.QFont.Bold))
        pause_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        pause_text.setZValue(1002)
        setattr(pause_text, '_is_pause_message', True)
        text_rect = pause_text.boundingRect()
        pause_text_x = (win_width - text_rect.width()) / 2
        pause_text_y = (win_height - text_rect.height()) / 2 - 30
        pause_text.setPos(pause_text_x, pause_text_y)

        sub_text = self.scene.addText(loc.get("paused_sub"), QtGui.QFont("Arial", 14))
        sub_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
        sub_text.setZValue(1002)
        setattr(sub_text, '_is_pause_message', True)
        sub_rect = sub_text.boundingRect()
        sub_text_x = (win_width - sub_rect.width()) / 2
        sub_text_y = pause_text_y + text_rect.height() + 10
        sub_text.setPos(sub_text_x, sub_text_y)
        self.scene.update()
        self.view.viewport().update()

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
        self.debug_text.setPos(self.window_width - 60, self.window_height - 60)
        if hasattr(self, 'current_message_item') and self.current_message_item in self.scene.items():
            text_height = self.current_message_item.boundingRect().height()
            message_y = self.window_height - text_height - 20
            self.current_message_item.setPos(0, message_y)
            self.current_message_item.setTextWidth(self.window_width)
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
            squid = self.tamagotchi_logic.squid
            squid.ui.window_width = self.window_width
            squid.ui.window_height = self.window_height
            squid.center_x = self.window_width // 2
            squid.center_y = self.window_height // 2
            if hasattr(squid, 'update_preferred_vertical_range'):
                squid.update_preferred_vertical_range()
            squid.squid_x = max(50, min(squid.squid_x, self.window_width - 50 - squid.squid_width))
            squid.squid_y = max(50, min(squid.squid_y, self.window_height - 120 - squid.squid_height))
            squid.squid_item.setPos(squid.squid_x, squid.squid_y)
            if hasattr(squid, 'update_view_cone'):
                squid.update_view_cone()
            if hasattr(squid, 'startled_icon') and squid.startled_icon is not None:
                squid.update_startled_icon_position()
            if hasattr(squid, 'sick_icon_item') and squid.sick_icon_item is not None:
                squid.update_sick_icon_position()

    def show_message(self, message):
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                results = self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_message_display", 
                    ui=self,
                    original_message=message
                )
                for result in results:
                    if isinstance(result, str) and result:
                        message = result
                        break
        try:
            for item in self.scene.items():
                try:
                    if hasattr(item, '_is_message_item'):
                        self.scene.removeItem(item)
                except Exception:
                    continue
        except Exception:
            pass

        message_item = QtWidgets.QGraphicsTextItem(message)
        message_item.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        from .display_scaling import DisplayScaling
        font = QtGui.QFont("Verdana", DisplayScaling.font_size(12), QtGui.QFont.Bold)
        message_item.setFont(font)
        message_item.setTextWidth(self.window_width)
        text_height = message_item.boundingRect().height()
        message_y = self.window_height - text_height - 40
        
        message_item.setPos(0, message_y)
        message_item.setHtml(f'<div style="text-align: center; background-color: #000000; padding: 0px;">{message}</div>')
        message_item.setZValue(999)
        message_item.setOpacity(1)
        try:
            setattr(message_item, '_is_message_item', True)
        except TypeError:
            pass
        self.scene.addItem(message_item)
        self.current_message_item = message_item
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
        scene_rect = self.scene.sceneRect()
        new_x = max(scene_rect.left(), min(new_x, scene_rect.right() - decoration.boundingRect().width()))
        animation = QtCore.QVariantAnimation()
        animation.setStartValue(current_pos)
        animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
        animation.setDuration(300)
        animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        animation.valueChanged.connect(decoration.setPos)
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
                item = ResizablePixmapItem(pixmap, file_path)
                item.original_pixmap = pixmap
                if not ('rock01' in file_path.lower() or 'rock02' in file_path.lower()):
                    from .display_scaling import DisplayScaling
                    target_max_size = DisplayScaling.scale(192)
                    orig_width = pixmap.width()
                    orig_height = pixmap.height()
                    max_dimension = max(orig_width, orig_height)
                    if max_dimension > target_max_size:
                        scale_factor = target_max_size / max_dimension
                        scaled_pixmap = pixmap.scaled(
                            int(orig_width * scale_factor),
                            int(orig_height * scale_factor),
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation
                        )
                        item.setPixmap(scaled_pixmap)
                pos = self.view.mapToScene(event.pos())
                item.setPos(pos)
                self.scene.addItem(item)
                self.scene.clearSelection()
                item.setSelected(True)
                unique_id = str(uuid.uuid4())
                item._decoration_id = unique_id
                if unique_id not in self.awarded_decorations:
                    self.awarded_decorations.add(unique_id)
                    if (hasattr(self, 'tamagotchi_logic') and
                        self.tamagotchi_logic is not None and
                        hasattr(self.tamagotchi_logic, 'statistics_window') and
                        self.tamagotchi_logic.statistics_window):
                            self.tamagotchi_logic.statistics_window.award(10)
                event.accept()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            self.delete_selected_items()
        elif event.key() == QtCore.Qt.Key_N and event.modifiers() & QtCore.Qt.ShiftModifier:
            self.direct_create_neuron()

    def show_preferences(self):
        """Show the preferences window"""
        if not hasattr(self, '_preferences_window') or not self._preferences_window:
            self._preferences_window = PreferencesWindow(self.window)
        self._preferences_window.show()
        self._preferences_window.raise_()
        self._preferences_window.activateWindow()

    def direct_create_neuron(self):
        try:
            if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
                print("ERROR: Brain window not initialized")
                return
            brain = self.squid_brain_window.brain_widget
            import time
            import random
            new_name = f"forced_{int(time.time())}"
            if brain.neuron_positions:
                x_values = [pos[0] for pos in brain.neuron_positions.values()]
                y_values = [pos[1] for pos in brain.neuron_positions.values()]
                center_x = sum(x_values) / len(x_values)
                center_y = sum(y_values) / len(y_values)
            else:
                center_x, center_y = 600, 300
            pos_x = center_x + random.randint(-100, 100)
            pos_y = center_y + random.randint(-100, 100)
            print(f"Creating neuron {new_name} at ({pos_x}, {pos_y})")
            brain.neuron_positions[new_name] = (pos_x, pos_y)
            brain.state[new_name] = 75
            if hasattr(brain, 'state_colors'):
                brain.state_colors[new_name] = (150, 200, 255)
            excluded = getattr(brain, 'excluded_neurons', [])
            for existing in list(brain.neuron_positions.keys()):
                if existing != new_name and existing not in excluded:
                    weight = random.uniform(-0.3, 0.3)
                    brain.weights[(new_name, existing)] = weight
                    brain.weights[(existing, new_name)] = weight * 0.8
            if hasattr(brain, 'neurogenesis_data'):
                if 'new_neurons' not in brain.neurogenesis_data:
                    brain.neurogenesis_data['new_neurons'] = []
                brain.neurogenesis_data['new_neurons'].append(new_name)
                brain.neurogenesis_data['last_neuron_time'] = time.time()
            if hasattr(brain, 'neurogenesis_highlight'):
                brain.neurogenesis_highlight = {
                    'neuron': new_name,
                    'start_time': time.time(),
                    'duration': 5.0
                }
            brain.update()
            print(f"Successfully created neuron: {new_name}")
        except Exception as e:
            import traceback
            print(f"NEUROGENESIS FAILURE:\n{traceback.format_exc()}")

    def delete_selected_items(self):
        for item in self.scene.selectedItems():
            if isinstance(item, ResizablePixmapItem):
                is_poop = (hasattr(item, 'category') and item.category == 'poop') or \
                          (hasattr(item, 'filename') and item.filename and 'poop' in item.filename.lower())
                if is_poop:
                    if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and \
                       hasattr(self.tamagotchi_logic, 'statistics_window') and self.tamagotchi_logic.statistics_window:
                        self.tamagotchi_logic.statistics_window.award(5)
                    self.show_floating_score(item, "+5")
                if hasattr(item, '_decoration_id'):
                    self.awarded_decorations.discard(item._decoration_id)
                self.scene.removeItem(item)
        self.scene.update()

    def show_floating_score(self, item, text, color=QtGui.QColor(50, 205, 50)):
        item_rect = item.sceneBoundingRect()
        center_x = item_rect.center().x()
        top_y = item_rect.top() - 30
        score_text = QtWidgets.QGraphicsTextItem(text)
        score_text.setDefaultTextColor(color)
        from .display_scaling import DisplayScaling
        font = QtGui.QFont("Arial", DisplayScaling.font_size(16), QtGui.QFont.Bold)
        score_text.setFont(font)
        text_width = score_text.boundingRect().width()
        score_text.setPos(center_x - text_width / 2, top_y)
        score_text.setZValue(1000)
        self.scene.addItem(score_text)
        start_pos = score_text.pos()
        end_pos = QtCore.QPointF(start_pos.x(), start_pos.y() - 40)
        pos_animation = QtCore.QVariantAnimation()
        pos_animation.setStartValue(start_pos)
        pos_animation.setEndValue(end_pos)
        pos_animation.setDuration(1000)
        pos_animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        pos_animation.valueChanged.connect(score_text.setPos)
        opacity_animation = QtCore.QPropertyAnimation(score_text, b"opacity")
        opacity_animation.setStartValue(1.0)
        opacity_animation.setEndValue(0.0)
        opacity_animation.setDuration(1000)
        opacity_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)
        def cleanup():
            try:
                if score_text.scene():
                    self.scene.removeItem(score_text)
            except:
                pass
        opacity_animation.finished.connect(cleanup)
        score_text._pos_animation = pos_animation
        score_text._opacity_animation = opacity_animation
        pos_animation.start()
        opacity_animation.start()

    def setup_menu_bar(self):
        loc = Localization.instance()
        self.menu_bar = self.window.menuBar()

        file_menu = self.menu_bar.addMenu(loc.get("file"))
        self.new_game_action = QtWidgets.QAction(loc.get("new_game"), self.window)
        self.load_action = QtWidgets.QAction(loc.get("load_game"), self.window)
        self.save_action = QtWidgets.QAction(loc.get("save_game"), self.window)
        file_menu.addAction(self.new_game_action)
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.save_action)

        view_menu = self.menu_bar.addMenu(loc.get("view"))
        self.brain_designer_action = QtWidgets.QAction(loc.get("brain_designer"), self.window)
        self.brain_designer_action.setIcon(self.window.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView))
        self.brain_designer_action.triggered.connect(self.open_brain_designer)
        self.brain_designer_action.setShortcut("Ctrl+Shift+B")
        self.brain_designer_action.setToolTip("Open the visual neural network designer")
        view_menu.addAction(self.brain_designer_action)
        view_menu.addSeparator()

        self.decorations_action = QtWidgets.QAction(loc.get("decorations"), self.window)
        self.decorations_action.setCheckable(True)
        self.decorations_action.triggered.connect(self.toggle_decoration_window)
        view_menu.addAction(self.decorations_action)

        self.stats_window_action = QtWidgets.QAction(loc.get("statistics"), self.window)
        self.stats_window_action.triggered.connect(self.toggle_statistics_window)
        view_menu.addAction(self.stats_window_action)

        self.brain_action = QtWidgets.QAction(loc.get("brain_tool"), self.window)
        self.brain_action.setCheckable(True)
        self.brain_action.triggered.connect(self.toggle_brain_window)
        view_menu.addAction(self.brain_action)

        self.neurogenesis_debug_action = QtWidgets.QAction(loc.get("neuron_lab"), self.window)
        self.neurogenesis_debug_action.triggered.connect(self.show_neurogenesis_debug) 
        view_menu.addAction(self.neurogenesis_debug_action)

        #self.task_mgr_action = QtWidgets.QAction(loc.get("task_manager"), self.window)
        #self.task_mgr_action.triggered.connect(self.show_task_manager)
        #view_menu.addAction(self.task_mgr_action)

        self.preferences_action = QtWidgets.QAction(loc.get("preferences"), self.window)
        self.preferences_action.triggered.connect(self.show_preferences)
        self.preferences_action.setShortcut("Ctrl+P")
        view_menu.addAction(self.preferences_action)

        speed_menu = self.menu_bar.addMenu(loc.get("speed"))
        self.pause_action = QtWidgets.QAction(loc.get("pause"), self.window)
        self.pause_action.setCheckable(True)
        self.pause_action.triggered.connect(lambda: self.set_simulation_speed(0))
        speed_menu.addAction(self.pause_action)
        
        self.normal_speed_action = QtWidgets.QAction(loc.get("normal_speed"), self.window)
        self.normal_speed_action.setCheckable(True)
        self.normal_speed_action.triggered.connect(lambda: self.set_simulation_speed(1))
        speed_menu.addAction(self.normal_speed_action)
        
        self.fast_speed_action = QtWidgets.QAction(loc.get("fast_speed"), self.window)
        self.fast_speed_action.setCheckable(True)
        self.fast_speed_action.triggered.connect(lambda: self.set_simulation_speed(2))
        speed_menu.addAction(self.fast_speed_action)
        
        self.very_fast_speed_action = QtWidgets.QAction(loc.get("very_fast"), self.window)
        self.very_fast_speed_action.setCheckable(True)
        self.very_fast_speed_action.triggered.connect(lambda: self.set_simulation_speed(3))
        speed_menu.addAction(self.very_fast_speed_action)

        self.speed_action_group = QtWidgets.QActionGroup(self.window)
        self.speed_action_group.addAction(self.pause_action)
        self.speed_action_group.addAction(self.normal_speed_action)
        self.speed_action_group.addAction(self.fast_speed_action)
        self.speed_action_group.addAction(self.very_fast_speed_action)

        actions_menu = self.menu_bar.addMenu(loc.get("actions"))
        self.feed_action = QtWidgets.QAction(loc.get("feed"), self.window)
        actions_menu.addAction(self.feed_action)
        self.clean_action = QtWidgets.QAction(loc.get("clean"), self.window)
        actions_menu.addAction(self.clean_action)
        self.medicine_action = QtWidgets.QAction(loc.get("medicine"), self.window)
        actions_menu.addAction(self.medicine_action)

        debug_menu = self.menu_bar.addMenu(loc.get("debug"))
        self.debug_action = QtWidgets.QAction(loc.get("toggle_debug"), self.window)
        self.debug_action.setCheckable(True)
        self.debug_action.triggered.connect(self.toggle_debug_mode)
        debug_menu.addAction(self.debug_action)

        self.view_cone_action = QtWidgets.QAction(loc.get("toggle_cone"), self.window)
        self.view_cone_action.setCheckable(True)
        self.view_cone_action.setShortcut('V')
        if hasattr(self.tamagotchi_logic, 'connect_view_cone_action'):
            self.view_cone_action.triggered.connect(self.tamagotchi_logic.connect_view_cone_action)
        elif hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'toggle_view_cone'):
             self.view_cone_action.triggered.connect(self.tamagotchi_logic.squid.toggle_view_cone)
        debug_menu.addAction(self.view_cone_action)

        self.vision_action = QtWidgets.QAction(loc.get("squid_vision"), self.window)
        self.vision_action.triggered.connect(self.show_vision_window)
        debug_menu.addAction(self.vision_action)

        self.rock_test_action = QtWidgets.QAction('Rock test (forced)', self.window)
        self.rock_test_action.triggered.connect(self.trigger_rock_test)
        
        self.plugins_menu = self.menu_bar.addMenu(loc.get("plugins"))
        self.connect_action_buttons()

    def show_task_manager(self):
        if not hasattr(self, '_task_manager') or not self._task_manager:
            worker = getattr(self.tamagotchi_logic, 'brain_worker', None)
            self._task_manager = TaskManagerWindow(worker, self.window)
        self._task_manager.show()
        self._task_manager.raise_()

    def show_vision_window(self):
        if not hasattr(self, 'vision_window') or self.vision_window is None or not self.vision_window.isVisible():
            if self.tamagotchi_logic:
                self.vision_window = VisionWindow(self.tamagotchi_logic, self.window)
                self.vision_window.show()
            else:
                QtWidgets.QMessageBox.warning(self.window, "Error", "Game logic is not yet initialized.")
        else:
            self.vision_window.raise_()
            self.vision_window.activateWindow()

    def set_simulation_speed(self, speed):
        if hasattr(self, 'tamagotchi_logic'):
            is_paused = (speed == 0)
            self.show_pause_message(is_paused)
            self.tamagotchi_logic.set_simulation_speed(speed)
            self.pause_action.setChecked(speed == 0)
            self.normal_speed_action.setChecked(speed == 1)
            self.fast_speed_action.setChecked(speed == 2)
            self.very_fast_speed_action.setChecked(speed == 3)
            speed_names = ["Paused", "Normal", "Fast", "Very Fast"]
            self.show_message(f"Simulation speed set to {speed_names[speed]}")
        else:
            self.show_message("Game logic not initialized!")

    def toggle_debug_mode(self):
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            current_debug = self.tamagotchi_logic.debug_mode
        else:
            current_debug = self.debug_mode
        new_debug_mode = not current_debug
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic._propagating_debug_mode = True
        self.debug_mode = new_debug_mode
        if hasattr(self, 'debug_action'):
            self.debug_action.setChecked(new_debug_mode)
        if hasattr(self, 'debug_text'):
            self.debug_text.setVisible(new_debug_mode)
            self.scene.update()
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic.debug_mode = new_debug_mode
            if hasattr(self.tamagotchi_logic, 'statistics_window'):
                self.tamagotchi_logic.statistics_window.set_debug_mode(new_debug_mode)
        if hasattr(self, 'squid_brain_window'):
            self.squid_brain_window.debug_mode = new_debug_mode
            if hasattr(self.squid_brain_window, 'brain_widget'):
                self.squid_brain_window.brain_widget.debug_mode = new_debug_mode
                self.squid_brain_window.brain_widget.update()
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
            self.tamagotchi_logic._propagating_debug_mode = False
        print(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")
        try:
            self.show_message(f"Debug mode {'enabled' if new_debug_mode else 'disabled'}")
        except TypeError:
            pass

    def trigger_rock_test(self):
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            self.show_message("Rock interaction system not initialized!")
            return
        rocks = [item for item in self.scene.items() 
                if isinstance(item, ResizablePixmapItem) 
                and self.tamagotchi_logic.rock_interaction.is_valid_rock(item)]
        if not rocks:
            self.show_message("No rocks found in the tank!")
            return
        if not hasattr(self.tamagotchi_logic, 'squid'):
            self.show_message("Squid not initialized!")
            return
        nearest_rock = min(rocks, key=lambda r: 
            math.hypot(
                r.sceneBoundingRect().center().x() - self.tamagotchi_logic.squid.squid_x,
                r.sceneBoundingRect().center().y() - self.tamagotchi_logic.squid.squid_y
            )
        )
        self.tamagotchi_logic.rock_interaction.start_rock_test(nearest_rock)
        self.show_message("Rock test initiated")

    def start_rps_game(self):
        if hasattr(self, 'tamagotchi_logic'):
            self.tamagotchi_logic.start_rps_game()
        else:
            print("TamagotchiLogic not initialized")

    def test_rock_interaction(self):
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
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                current_debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
                if hasattr(self.tamagotchi_logic, 'brain_window') and self.tamagotchi_logic.brain_window:
                    self.squid_brain_window = self.tamagotchi_logic.brain_window
                else: 
                    self.squid_brain_window = SquidBrainWindow(self.tamagotchi_logic, current_debug_mode, show_decorations_callback=self.show_decorations_window)
                    if hasattr(self.tamagotchi_logic, 'set_brain_window'): 
                         self.tamagotchi_logic.set_brain_window(self.squid_brain_window)
            else:
                self.show_message("Brain Tool is not initialized yet.")
                return
        if not self.squid_brain_window.isVisible():
            self.squid_brain_window.show()

        if not hasattr(self.squid_brain_window, 'brain_widget') or not self.squid_brain_window.brain_widget:
            self.show_message("Brain widget component is not ready.")
            return

        if not hasattr(self, 'enhanced_neuron_inspector_instance') or \
           not self.enhanced_neuron_inspector_instance or \
           not self.enhanced_neuron_inspector_instance.isVisible():
            self.enhanced_neuron_inspector_instance = EnhancedNeuronInspector(
                brain_tool_window=self.squid_brain_window,
                brain_widget_ref=self.squid_brain_window.brain_widget
            )
        self.enhanced_neuron_inspector_instance.show()
        self.enhanced_neuron_inspector_instance.raise_()
        self.enhanced_neuron_inspector_instance.activateWindow()
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
                self.tamagotchi_logic.statistics_window = StatisticsWindow(self.tamagotchi_logic.squid, show_decorations_callback=self.show_decorations_window)
            self.statistics_window = self.tamagotchi_logic.statistics_window
        else:
            print("TamagotchiLogic not initialized")

    def toggle_brain_window(self, checked):
        if checked:
            self.squid_brain_window.show()
        else:
            self.squid_brain_window.hide()

    def toggle_designer_mode(self, checked=None):
        if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
            self.show_message("Brain Tool not initialized")
            if hasattr(self, 'designer_mode_action'):
                self.designer_mode_action.setChecked(False)
            return
        if not hasattr(self.squid_brain_window, 'designer_controller') or \
           not self.squid_brain_window.designer_controller:
            self.show_message("Designer mode not available - integration required")
            if hasattr(self, 'designer_mode_action'):
                self.designer_mode_action.setChecked(False)
            return
        if not self.squid_brain_window.isVisible():
            self.squid_brain_window.show()
            if hasattr(self, 'brain_action'):
                self.brain_action.setChecked(True)
        controller = self.squid_brain_window.designer_controller
        controller.toggle_designer_mode()
        is_active = controller.designer_mode_active
        if hasattr(self, 'designer_mode_action'):
            self.designer_mode_action.setChecked(is_active)
        status = "enabled" if is_active else "disabled"
        self.show_message(f"Designer mode {status}")

    def connect_view_cone_action(self, toggle_function):
        self.view_cone_action.triggered.connect(toggle_function)

    def get_decorations_data(self):
        decorations_data = []
        for item in self.scene.items():
            if isinstance(item, ResizablePixmapItem):
                try:
                    pixmap = item.pixmap()
                    buffer = QtCore.QBuffer()
                    buffer.open(QtCore.QIODevice.WriteOnly)
                    pixmap.save(buffer, "PNG")
                    pixmap_data = base64.b64encode(buffer.data()).decode('utf-8')
                    pos = item.pos()
                    pos_tuple = (pos.x(), pos.y())
                    scale = item.scale()
                    filename = getattr(item, 'filename', 'unknown')
                    decoration_dict = {
                        'pixmap_data': pixmap_data,
                        'pos': pos_tuple,
                        'scale': scale,
                        'filename': filename
                    }
                    decorations_data.append(decoration_dict)
                except Exception as e:
                    print(f"Error serializing decoration: {e}")
                    continue
        print(f"Saved {len(decorations_data)} decoration(s)")
        return decorations_data

    def load_decorations_data(self, decorations_data):
        if not decorations_data:
            print("No decorations to load")
            return
        for item in list(self.scene.items()):
            if isinstance(item, ResizablePixmapItem):
                self.scene.removeItem(item)
        if hasattr(self, 'decoration_window'):
            self.decoration_window.decoration_items.clear()
        loaded_count = 0
        for decoration_dict in decorations_data:
            try:
                pixmap_data = decoration_dict['pixmap_data']
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(
                    QtCore.QByteArray(base64.b64decode(pixmap_data.encode('utf-8')))
                )
                filename = decoration_dict.get('filename', 'unknown')
                item = ResizablePixmapItem(pixmap, filename)
                pos_tuple = decoration_dict['pos']
                item.setPos(QtCore.QPointF(pos_tuple[0], pos_tuple[1]))
                scale = decoration_dict.get('scale', 1.0)
                item.setScale(scale)
                self.scene.addItem(item)
                if hasattr(self, 'decoration_window'):
                    self.decoration_window.add_decoration_item(item)
                loaded_count += 1
            except Exception as e:
                print(f"Error loading decoration: {e}")
                import traceback
                traceback.print_exc()
                continue
        print(f"Loaded {loaded_count} decoration(s)")

    def get_pixmap_data(self, item):
        pixmap = item.pixmap()
        buffer = QtCore.QBuffer()
        buffer.open(QtCore.QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        pixmap_data = buffer.data().toBase64().data().decode()
        return pixmap_data

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if hasattr(self.parent(), 'decorations_action'):
            self.parent().decorations_action.setChecked(False)

    def get_rock_items(self):
        return [item for item in self.scene.items() 
                if isinstance(item, ResizablePixmapItem) 
                and getattr(item, 'can_be_picked_up', False)]
    
    def highlight_rock(self, rock, highlight=True):
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(255, 255, 0))
        effect.setStrength(0.7 if highlight else 0.0)
        rock.setGraphicsEffect(effect if highlight else None)

    def reset_all_rock_states(self):
        for rock in self.get_rock_items():
            rock.is_being_carried = False
            self.highlight_rock(rock, False)