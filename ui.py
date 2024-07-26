import os
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from squid_brain_window import SquidBrainWindow

class DecorationItem(QtWidgets.QLabel):
    def __init__(self, pixmap, filename):
        super().__init__()
        self.setPixmap(pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        self.filename = filename
        self.setFixedSize(110, 110)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setToolTip(filename)

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
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.resize_handle = None
        self.original_pixmap = pixmap
        self.filename = filename
        self.stat_multipliers, self.category = self.get_decoration_info()

    def get_decoration_info(self):
        try:
            with open('decoration_stats.json', 'r') as f:
                stats = json.load(f)
            info = stats.get(self.filename, {})
            return {k: v for k, v in info.items() if k != 'category'}, info.get('category', 'rock')
        except FileNotFoundError:
            print("decoration_stats.json not found. Using empty stats.")
            return {}, 'rock'
        except json.JSONDecodeError:
            print("Error decoding decoration_stats.json. Using empty stats.")
            return {}, 'rock'

    def boundingRect(self):
        return super().boundingRect().adjusted(0, 0, 20, 20)  # Increased the size of the resize handle

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 255), 2))
            painter.drawRect(self.boundingRect())

            handle_pos = self.boundingRect().bottomRight() - QtCore.QPointF(20, 20)  # Increased the size of the resize handle
            handle_rect = QtCore.QRectF(handle_pos, QtCore.QSizeF(20, 20))  # Increased the size of the resize handle
            painter.fillRect(handle_rect, QtGui.QColor(0, 0, 255))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            if QtCore.QRectF(self.boundingRect().bottomRight() - QtCore.QPointF(20, 20),  # Increased the size of the resize handle
                             QtCore.QSizeF(20, 20)).contains(pos):  # Increased the size of the resize handle
                self.resize_handle = self.mapToScene(pos)
            else:
                self.resize_handle = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resize_handle is not None:
            new_pos = self.mapToScene(event.pos())
            width = max(new_pos.x() - self.pos().x(), 20)
            height = max(new_pos.y() - self.pos().y(), 20)
            self.setPixmap(self.original_pixmap.scaled(int(width), int(height), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.resize_handle = None
        super().mouseReleaseEvent(event)

class DecorationWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Decorations")
        self.setFixedWidth(400)

        layout = QtWidgets.QVBoxLayout(self)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        layout.addWidget(scroll_area)

        content_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(content_widget)
        scroll_area.setWidget(content_widget)

        self.load_decorations()

    def load_decorations(self):
        decoration_path = "images/decoration"
        items_per_row = 3
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
        self.setFixedHeight(min((row + 1) * 120 + 40, 600))  # 120 pixels per row, max height of 600

class Ui:
    def __init__(self, window):
        self.window = window
        self.window.setWindowTitle("Dosidicus")

        self.window_width = 1280
        self.window_height = 820

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

        # Remove the decoration button
        # self.decoration_button = QtWidgets.QPushButton("Decorations")
        # self.decoration_button.clicked.connect(self.toggle_decoration_window)
        # self.decoration_button_proxy = self.scene.addWidget(self.decoration_button)
        # self.decoration_button_proxy.setPos(self.window_width - 170, self.window_height - 100)
        # self.decoration_button_proxy.setZValue(1)

        # Create decoration window
        self.decoration_window = DecorationWindow()

        # Enable drag and drop for the main window
        self.view.setAcceptDrops(True)
        self.view.dragEnterEvent = self.dragEnterEvent
        self.view.dragMoveEvent = self.dragMoveEvent
        self.view.dropEvent = self.dropEvent

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
        self.feeding_message.setFont(QtGui.QFont("Arial", 14, QtGui.QFont.Bold))
        self.feeding_message.setPos(0, self.window_height - 30)
        self.feeding_message.setTextWidth(self.window_width)
        self.feeding_message.setHtml('<div style="text-align: center;">Squid requires feeding</div>')
        self.feeding_message.setOpacity(0)
        self.scene.addItem(self.feeding_message)

        # Create points labels
        self.points_label = QtWidgets.QGraphicsTextItem("Points:")
        self.points_label.setDefaultTextColor(QtGui.QColor(0, 0, 0))  # Set font color to black
        self.points_label.setFont(QtGui.QFont("Arial", 12))
        self.points_label.setPos(self.window_width - 255, 10)  # Move the label to the left by 15 pixels
        self.points_label.setZValue(2)  # Increase Z-value to ensure it's on top
        self.scene.addItem(self.points_label)

        self.points_value_label = QtWidgets.QGraphicsTextItem("0")
        self.points_value_label.setDefaultTextColor(QtGui.QColor(0, 0, 0))  # Set font color to black
        self.points_value_label.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        self.points_value_label.setPos(self.window_width - 95, 10)
        self.points_value_label.setZValue(2)  # Increase Z-value to ensure it's on top
        self.scene.addItem(self.points_value_label)

    def toggle_decoration_window(self):
        if self.decoration_window.isVisible():
            self.decoration_window.hide()
        else:
            self.decoration_window.show()

    def handle_window_resize(self, event):
        self.window_width = event.size().width()
        self.window_height = event.size().height()
        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
        self.cleanliness_overlay.setRect(50, 50, self.window_width - 100, self.window_height - 100)

        self.feeding_message.setPos(0, self.window_height - 30)
        self.feeding_message.setTextWidth(self.window_width)

        self.points_label.setPos(self.window_width - 265, 10)  # Move the label to the left by 15 pixels
        self.points_value_label.setPos(self.window_width - 95, 10)

        # Update decoration button position
        # self.decoration_button_proxy.setPos(self.window_width - 170, self.window_height - 100)  # Move up and left by 50 pixels

    def show_message(self, message):
        self.feeding_message.setHtml(f'<div style="text-align: center;">{message}</div>')
        self.feeding_message.setOpacity(1)

        fade_out = QtCore.QVariantAnimation()
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setDuration(3000)
        fade_out.valueChanged.connect(lambda value: self.feeding_message.setOpacity(value))
        fade_out.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def update_points(self, points):
        self.points_value_label.setPlainText(str(points))

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
            pixmap = QtGui.QPixmap(url.toLocalFile())
            if not pixmap.isNull():
                item = ResizablePixmapItem(pixmap, url.toLocalFile())
                pos = self.view.mapToScene(event.pos())
                item.setPos(pos)
                self.scene.addItem(item)
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete:
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if isinstance(item, ResizablePixmapItem):
                    self.scene.removeItem(item)

    def setup_menu_bar(self):
        self.menu_bar = self.window.menuBar()

        file_menu = self.menu_bar.addMenu('File')
        self.load_action = QtWidgets.QAction('Load', self.window)
        self.save_action = QtWidgets.QAction('Save', self.window)
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.save_action)

        actions_menu = self.menu_bar.addMenu('Actions')

        self.feed_action = QtWidgets.QAction('Feed', self.window)
        actions_menu.addAction(self.feed_action)

        self.clean_action = QtWidgets.QAction('Clean', self.window)
        actions_menu.addAction(self.clean_action)

        self.medicine_action = QtWidgets.QAction('Medicine', self.window)
        actions_menu.addAction(self.medicine_action)

        decorations_menu = self.menu_bar.addMenu('Decorations')

        self.decoration_action = QtWidgets.QAction('Toggle Decoration Window', self.window)
        self.decoration_action.triggered.connect(self.toggle_decoration_window)
        decorations_menu.addAction(self.decoration_action)

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

        # help_menu = self.menu_bar.addMenu('Help')

        # about_action = QtWidgets.QAction('About', self.window)
       #  about_action.triggered.connect(self.show_about_dialog)
        # help_menu.addAction(about_action)

    def toggle_brain_window(self, checked):
        if checked:
            self.squid_brain_window.show()
        else:
            self.squid_brain_window.hide()

    def show_about_dialog(self):
        about_message = ("<h2>Dosidicus Electronicae</h2>"
                         "<p>Research project</p>"
                         "<p>Version 1.0.32</p>"
                         "<p>https://github.com/ViciousSquid/Dosidicus")
        QtWidgets.QMessageBox.about(self.window, "About", about_message)

    def connect_view_cone_action(self, toggle_function):
        self.view_cone_action.triggered.connect(toggle_function)

    def get_decorations_data(self):
        decorations_data = []
        for item in self.scene.items():
            if isinstance(item, ResizablePixmapItem):
                decorations_data.append({
                    'pixmap': item.pixmap(),
                    'pos': item.pos(),
                    'scale': item.scale()
                })
        return decorations_data

    def load_decorations_data(self, decorations_data):
        for decoration_data in decorations_data:
            pixmap = decoration_data['pixmap']
            pos = decoration_data['pos']
            scale = decoration_data['scale']
            item = ResizablePixmapItem(pixmap)
            item.setPos(pos)
            item.setScale(scale)
            self.scene.addItem(item)
