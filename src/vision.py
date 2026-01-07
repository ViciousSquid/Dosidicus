from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .localisation import loc

class VisionWindow(QtWidgets.QDialog):
    def __init__(self, tamagotchi_logic, parent=None):
        super().__init__(parent)
        self.tamagotchi_logic = tamagotchi_logic
        self.setWindowTitle(loc("vision_window_title"))
        self.setMinimumSize(400, 300)

        # Store original view cone state and enable it for the dialog
        self.original_view_cone_state = self.tamagotchi_logic.squid.view_cone_visible
        if not self.original_view_cone_state:
            self.tamagotchi_logic.squid.toggle_view_cone()

        self.initialize_ui()

        # Timer to refresh the view
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_view)
        self.update_timer.start(1000) # Update every second

    def initialize_ui(self):
        """Initializes the UI for the Vision window."""
        layout = QtWidgets.QVBoxLayout(self) # Set layout on the dialog itself
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Title
        title_layout = QtWidgets.QHBoxLayout()
        title_icon = QtWidgets.QLabel("👁️")
        title_icon.setStyleSheet("font-size: 28px;")
        
        # Reuse existing key "visible_objects"
        title_label = QtWidgets.QLabel(loc("visible_objects"))
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #343a40;")
        title_layout.addWidget(title_icon)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        # List widget to display visible objects
        self.visible_objects_list = QtWidgets.QListWidget()
        self.visible_objects_list.setStyleSheet("""
            QListWidget {
                background-color: #303030;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px;
                font-size: 24px;
                color: white;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:hover {
                background-color: #f1f3f5;
            }
        """)
        layout.addWidget(self.visible_objects_list)

        # Create a horizontal layout for the buttons
        button_layout = QtWidgets.QHBoxLayout()

        # Add the new "Toggle View Cone" button
        # Reuse existing key "toggle_cone" from Debug menu
        self.toggle_cone_button = QtWidgets.QPushButton(loc("toggle_cone"))
        self.toggle_cone_button.clicked.connect(self.toggle_view_cone)
        button_layout.addWidget(self.toggle_cone_button)

        # Add a stretch to push the close button to the right
        button_layout.addStretch()

        # Add the close button
        # Reuse existing key "close"
        self.close_button = QtWidgets.QPushButton(loc("close"))
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)

        # Add the button layout to the main layout
        layout.addLayout(button_layout)

    def toggle_view_cone(self):
        """Toggles the visibility of the squid's view cone."""
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid'):
            self.tamagotchi_logic.squid.toggle_view_cone()

    def closeEvent(self, event):
        """Override the close event to restore the view cone's original state."""
        if self.tamagotchi_logic.squid.view_cone_visible != self.original_view_cone_state:
            self.tamagotchi_logic.squid.toggle_view_cone()
        super().closeEvent(event)

    def update_view(self):
        """The method to update the content, formerly update_from_brain_state."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid'):
            self.visible_objects_list.clear()
            self.visible_objects_list.addItem(loc("vis_logic_unavailable"))
            return

        squid = self.tamagotchi_logic.squid
        
        # Gather all world objects to check for visibility
        all_objects = []
        if hasattr(self.tamagotchi_logic, 'food_items'):
            all_objects.extend(self.tamagotchi_logic.food_items)
        if hasattr(self.tamagotchi_logic, 'poop_items'):
            all_objects.extend(self.tamagotchi_logic.poop_items)
        if hasattr(self.tamagotchi_logic, 'user_interface') and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
             all_decorations = [item for item in self.tamagotchi_logic.user_interface.scene.items() if hasattr(item, 'category')]
             all_objects.extend(all_decorations)

        # Use the squid's own vision method to get what it can see
        visible_objects = squid.get_visible_objects(all_objects)

        self.visible_objects_list.clear()

        if not visible_objects:
            self.visible_objects_list.addItem(loc("vis_nothing_in_view"))
        else:
            for obj in visible_objects:
                # Reuse existing "unknown" key
                obj_name = loc("unknown")
                
                # Determine object name based on its attributes
                if hasattr(obj, 'category') and obj.category:
                    # Attempt to translate category (e.g. 'rock', 'plant') using existing keys
                    obj_name = loc(obj.category, default=obj.category.capitalize())
                elif hasattr(obj, 'is_sushi'):
                    # Use existing "sushi" and "food" keys (Cheese is default food)
                    obj_name = loc("sushi") if obj.is_sushi else loc("food")
                
                distance = squid.distance_to(obj.pos().x(), obj.pos().y())
                
                dist_label = loc("vis_distance")
                list_item_text = f"{obj_name} ({dist_label}: {distance:.0f})"
                self.visible_objects_list.addItem(list_item_text)