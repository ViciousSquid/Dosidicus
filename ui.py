import os
import json
import math
import random
from PyQt5 import QtCore, QtGui, QtWidgets
from squid_brain_window import SquidBrainWindow
from statistics_window import StatisticsWindow
from error_logging import log_error

class ResizablePixmapItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, pixmap, filename):
        super().__init__(pixmap)
        self.filename = filename
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.resize_handle = None
        self.original_pixmap = pixmap
        self.stat_multipliers, self.category = self.get_decoration_info()
        self.is_rock = self.category == 'rock'
        self.is_sinking = False
        self.sink_speed = 2  # pixels per frame, adjust as needed
        self.is_throwable = self.category == 'rock' and self.boundingRect().width() <= 50  # Only small rocks are throwable
        self.is_picked_up = False  # Add this line

    def calculate_weight(self):
        if self.is_throwable:
            size = max(self.boundingRect().width(), self.boundingRect().height())
            if size <= 30:
                return max(random.uniform(0.1, 0.5), 0.1)  # Small items, minimum weight 0.1
            elif size <= 50:
                return max(random.uniform(0.5, 2), 0.1)  # Medium items, minimum weight 0.1
            else:
                return max(random.uniform(2, 5), 0.1)  # Large items, minimum weight 0.1
        return 0.1  # Non-throwable items have a minimal weight

    def check_if_throwable(self):
        is_throwable = (self.category == 'rock' and
                        max(self.boundingRect().width(), self.boundingRect().height()) <= 50)
        log_error(f"Checking if item is throwable: {is_throwable}")
        return is_throwable

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
            with open('decoration_stats.json', 'r') as f:
                stats = json.load(f)
            info = stats.get(self.filename, {})
            return {k: v for k, v in info.items() if k != 'category'}, info.get('category', 'unknown')
        except FileNotFoundError:
            print("decoration_stats.json not found. Using default stats.")
            return {}, 'unknown'

class ThrowableItem(ResizablePixmapItem):
    def __init__(self, pixmap, filename, size):
        super().__init__(pixmap, filename)
        self.size = size  # 'small', 'medium', or 'large'
        self.weight = self.calculate_weight()
        self.sink_speed = self.calculate_sink_speed()
        self.is_picked_up = False

    def advance(self, phase):
        if not phase or not self.is_rock or not self.is_sinking:
            return

        new_pos = self.pos() + QtCore.QPointF(0, self.sink_speed)
        scene_bottom = self.scene().sceneRect().bottom()
        if new_pos.y() + self.boundingRect().height() > scene_bottom:
            new_pos.setY(scene_bottom - self.boundingRect().height())
            self.is_sinking = False
        self.setPos(new_pos)

    def start_sinking(self):
        if self.is_rock:
            self.is_sinking = True

    def calculate_weight(self):
        if self.size == 'small':
            return random.uniform(0.1, 0.5)
        elif self.size == 'medium':
            return random.uniform(0.5, 2)
        else:  # large
            return random.uniform(2, 5)

    def calculate_sink_speed(self):
        # Adjust the sinking speed based on the weight
        if self.weight <= 0.5:
            return 1  # Slow sinking speed for light items
        elif self.weight <= 2:
            return 2  # Medium sinking speed for medium items
        else:
            return 5  # Fast sinking speed for heavy items

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
        self.squid_brain_window = SquidBrainWindow()

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

        self.debug_mode = False
        self.throw_rock_button = None

        # Setup other UI elements
        self.setup_ui_elements()
        self.setup_scene_elements()

        # Set up the scene update timer
        self.scene_update_timer = QtCore.QTimer()
        self.scene_update_timer.timeout.connect(self.update_scene)
        self.scene_update_timer.start(50)  # Update every 50ms

        # Setup throwable items
        self.setup_throwable_items()

        # Add small rocks randomly at the bottom of the screen
        self.add_random_small_rocks()

    def setup_ui_elements(self):
        # Add UI elements that don't depend on the scene
        pass

    def setup_scene_elements(self):
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

    def setup_throwable_items(self):
        # Load throwable item images
        self.throwable_item_images = {
            'small': QtGui.QPixmap("images/rock_small.png"),
            'medium': QtGui.QPixmap("images/rock_medium.png"),
            'large': QtGui.QPixmap("images/rock_large.png")
        }

    def create_throwable_item(self, size, x, y):
        item = ThrowableItem(self.throwable_item_images[size], f"rock_{size}.png", size)
        item.setPos(x, y)
        self.scene.addItem(item)
        return item

    def update_rectangle_size(self):
        if self.debug_mode:
            self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 150)
            self.create_throw_rock_button()
            self.create_pick_up_rock_button()
        else:
            self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
            self.remove_throw_rock_button()
            self.remove_pick_up_rock_button()

    def create_throw_rock_button(self):
        if self.throw_rock_button is None:
            self.throw_rock_button = QtWidgets.QPushButton("Throw Rock", self.window)
            self.throw_rock_button.setGeometry(50, self.window_height - 90, 100, 30)
            self.throw_rock_button.clicked.connect(self.tamagotchi_logic.throw_rock_debug)
        self.throw_rock_button.show()

    def remove_throw_rock_button(self):
        if self.throw_rock_button is not None:
            self.throw_rock_button.hide()

    def create_pick_up_rock_button(self):
        if not hasattr(self, 'pick_up_rock_button'):
            self.pick_up_rock_button = QtWidgets.QPushButton("Pick Up Rock", self.window)
            self.pick_up_rock_button.setGeometry(160, self.window_height - 90, 100, 30)
            self.pick_up_rock_button.clicked.connect(self.tamagotchi_logic.pick_up_rock_debug)
            self.pick_up_rock_button.show()

    def remove_pick_up_rock_button(self):
        if hasattr(self, 'pick_up_rock_button'):
            self.pick_up_rock_button.deleteLater()
            delattr(self, 'pick_up_rock_button')

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

        self.update_rectangle_size()
        if self.throw_rock_button:
            self.throw_rock_button.setGeometry(50, self.window_height - 90, 100, 30)
        if hasattr(self, 'pick_up_rock_button'):
            self.pick_up_rock_button.setGeometry(160, self.window_height - 90, 100, 30)

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
        # Keep the functionality but remove the display
        pass

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
                item = None

                # Check if the item is a rock and determine its size
                if 'rock' in filename.lower():
                    size = 'small' if 'small' in filename.lower() else 'medium' if 'medium' in filename.lower() else 'large'
                    item = ThrowableItem(pixmap, filename, size)
                else:
                    item = ResizablePixmapItem(pixmap, filename)

                # Generate a random scale factor between 0.5 and 2
                scale_factor = random.uniform(0.5, 2)
                item.setScale(scale_factor)

                pos = self.view.mapToScene(event.pos())
                item.setPos(pos)
                self.scene.addItem(item)

                # Start sinking if the item is a ThrowableItem
                if isinstance(item, ThrowableItem):
                    item.start_sinking()

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
        self.load_action = QtWidgets.QAction('Load', self.window)
        self.save_action = QtWidgets.QAction('Save', self.window)
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

        self.rps_game_action = QtWidgets.QAction('Play Rock, Paper, Scissors', self.window)
        actions_menu.addAction(self.rps_game_action)
        self.rps_game_action.triggered.connect(self.start_rps_game)

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

    def set_debug_mode(self, enabled):
        self.debug_mode = enabled
        self.update_rectangle_size()

    def update_rectangle_size(self):
        if self.debug_mode:
            self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 150)
            self.create_throw_rock_button()
            self.create_pick_up_rock_button()
        else:
            self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
            self.remove_throw_rock_button()
            self.remove_pick_up_rock_button()

    def create_throw_rock_button(self):
        if self.throw_rock_button is None:
            self.throw_rock_button = QtWidgets.QPushButton("Throw Rock", self.window)
            self.throw_rock_button.setGeometry(50, self.window_height - 90, 100, 30)
            self.throw_rock_button.clicked.connect(self.tamagotchi_logic.throw_rock_debug)
        self.throw_rock_button.show()

    def remove_throw_rock_button(self):
        if self.throw_rock_button is not None:
            self.throw_rock_button.hide()

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

    def update_scene(self):
        self.ensure_rocks_sink_to_bottom()
        self.scene.update()

    def add_random_small_rocks(self):
        num_rocks = random.randint(2, 3)  # Add between 2 and 3 small rocks
        for _ in range(num_rocks):
            x = random.randint(50, self.window_width - 50)
            y = self.window_height - random.randint(25, 50)  # Ensure rocks are within 25 pixels of the bottom
            rock_item = self.create_throwable_item('small', x, y)
            rock_item.setScale(random.uniform(0.3, 0.5))  # Scale the size randomly between 30% and 50%
            rock_item.setRotation(random.uniform(0, 360))  # Rotate the rock randomly
            rock_item.start_sinking()

    def ensure_rocks_sink_to_bottom(self):
        for item in self.scene.items():
            if isinstance(item, ThrowableItem) and item.is_sinking:
                new_pos = item.pos() + QtCore.QPointF(0, item.sink_speed)
                scene_bottom = self.scene.sceneRect().bottom()
                if new_pos.y() + item.boundingRect().height() > scene_bottom:
                    new_pos.setY(scene_bottom - item.boundingRect().height())
                    item.is_sinking = False
                item.setPos(new_pos)
