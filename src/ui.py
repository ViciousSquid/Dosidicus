# UI Stuff

import os
import json
import math
import random
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
        scaled_pixmap = pixmap.scaled(128, 128, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        super().__init__(scaled_pixmap)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.resize_handle = None
        self.original_pixmap = pixmap
        self.filename = filename
        self.stat_multipliers, self.category = self.get_decoration_info()
        
        # Ensure stat_multipliers is never empty
        if not self.stat_multipliers:
            self.stat_multipliers = {'happiness': 1}

    def boundingRect(self):
        return super().boundingRect().adjusted(0, 0, 20, 20)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
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
            self.setPixmap(self.original_pixmap.scaled(int(width), int(height), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.resize_handle = None
        super().mouseReleaseEvent(event)

    def get_decoration_info(self):
        try:
            # Construct the path to decoration_stats.json
            file_path = os.path.join(os.path.dirname(__file__), 'decoration_stats.json')
            
            # Open and read the JSON file
            with open(file_path, 'r') as f:
                stats = json.load(f)
            
            # Get the info for this decoration
            info = stats.get(self.filename, {})
            
            # Extract stat multipliers and category
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
        self.setFixedWidth(550)  # Increased width

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
        items_per_row = 3  # Increased to 4 items per row
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

        # Initialize SquidBrainWindow
        self.squid_brain_window = None

        # Create decoration window
        self.decoration_window = DecorationWindow(self.window)
        self.decoration_window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.Tool)
        self.decoration_window.setAttribute(QtCore.Qt.WA_QuitOnClose, False)

        # Initialize statistics window
        self.statistics_window = None

        # Enable drag and drop for the main window
        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = self.dragEnterEvent
        self.view.dragMoveEvent = self.dragMoveEvent
        self.view.dropEvent = self.dropEvent

        # Add this line to enable key events for the view
        self.view.setFocusPolicy(QtCore.Qt.StrongFocus)

        # Connect the key press event
        self.view.keyPressEvent = self.keyPressEvent

        # Setup other UI elements
        self.setup_ui_elements()

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
                
                # Don't scale rocks or anything eginning with st_
                if filename.startswith(('rock01', 'rock02', 'st_')):
                    scale_factor = 1.0
                else:
                    # Generate a random scale factor between 0.5 and 2 for other decorations
                    scale_factor = random.uniform(0.5, 2)
                
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

        file_menu = self.menu_bar.addMenu('File')
        self.new_game_action = QtWidgets.QAction('New Game', self.window)
        self.load_action = QtWidgets.QAction('Load Game', self.window)
        self.save_action = QtWidgets.QAction('Save Game', self.window)
        file_menu.addAction(self.new_game_action)
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.save_action)

        view_menu = self.menu_bar.addMenu('View')
        self.stats_window_action = QtWidgets.QAction('Statistics', self.window)
        self.stats_window_action.triggered.connect(self.toggle_statistics_window)
        view_menu.addAction(self.stats_window_action)

        self.decorations_action = QtWidgets.QAction('Decorations', self.window)
        self.decorations_action.setCheckable(True)
        self.decorations_action.triggered.connect(self.toggle_decoration_window)
        view_menu.addAction(self.decorations_action)

        actions_menu = self.menu_bar.addMenu('Actions')

        debug_menu = self.menu_bar.addMenu('Debug')

        self.brain_action = QtWidgets.QAction('Toggle Brain View', self.window)
        self.brain_action.setCheckable(True)
        self.brain_action.triggered.connect(self.toggle_brain_window)
        debug_menu.addAction(self.brain_action)

        self.debug_action = QtWidgets.QAction('Toggle Debug Mode', self.window)
        self.debug_action.setCheckable(True)
        debug_menu.addAction(self.debug_action)

        self.view_cone_action = QtWidgets.QAction('Toggle View Cone', self.window)
        self.view_cone_action.setCheckable(True)
        debug_menu.addAction(self.view_cone_action)

        self.feed_action = QtWidgets.QAction('Feed', self.window)
        actions_menu.addAction(self.feed_action)

        self.clean_action = QtWidgets.QAction('Clean', self.window)
        actions_menu.addAction(self.clean_action)

        self.medicine_action = QtWidgets.QAction('Medicine', self.window)
        actions_menu.addAction(self.medicine_action)

        #self.rps_game_action = QtWidgets.QAction('Play Rock, Paper, Scissors', self.window)
        #actions_menu.addAction(self.rps_game_action)
        #self.rps_game_action.triggered.connect(self.start_rps_game)

    def start_rps_game(self):
        if hasattr(self, 'tamagotchi_logic'):
            self.tamagotchi_logic.start_rps_game()
        else:
            print("TamagotchiLogic not initialized")

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
