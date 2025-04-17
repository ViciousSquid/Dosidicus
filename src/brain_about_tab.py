# brain_about_tab.py
import random
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab

class AboutTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()

    def initialize_ui(self):
        # Main text content using QTextEdit
        about_text = QtWidgets.QTextEdit()
        about_text.setReadOnly(True)

        # Set font size for QTextEdit
        font = about_text.font()
        font.setPointSize(14)  # Increase the font size here
        about_text.setFont(font)

        # Predefined list of approved squid names
        SQUID_NAMES = [
            "Algernon", "Cuthbert", "Englebert", "D'Artagnan",
            "Gaspard", "Ulysse", "Leopold", "Miroslav",
            "Artemis", "Jacques", "Cecil", "Wilhelm", "Giskard"
        ]

        # Randomly select and permanently set the squid name
        squid_name = random.choice(SQUID_NAMES)

        # Get personality
        personality = "Unknown"
        if hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
            personality = str(self.tamagotchi_logic.squid.personality).split('.')[-1] if hasattr(self.tamagotchi_logic.squid, 'personality') else "Unknown"

            # Set the randomly selected name
            if hasattr(self.tamagotchi_logic.squid, 'name'):
                self.tamagotchi_logic.squid.name = squid_name

        # Remove the badge from the QTextEdit HTML
        about_text.setHtml(f"""
        <h1>Dosidicus electronicae</h1>
        <p><a href="https://github.com/ViciousSquid/Dosidicus">github.com/ViciousSquid/Dosidicus</a></p>
        <p>A Tamagotchi-style digital pet with a simple neural network</p>
        <ul>
            <li>by Rufus Pearce (ViciousSquid)</li><br><br>
        <br>
        <b>Dosidicus version 2.1.0</b> (milestone 5)<br>
        Brain Tool version 2.0nf<br>
        Decision engine version 1.0<br><br>
        <p>This is a research project. Please suggest features.</p><br><br>
        </ul>
        """)

        # Create a custom widget for the badge
        badge_widget = QtWidgets.QWidget()
        badge_layout = QtWidgets.QVBoxLayout(badge_widget)
        badge_layout.setContentsMargins(0, 0, 0, 0)

        # Badge container
        badge_container = QtWidgets.QWidget()
        badge_container.setFixedWidth(300)
        badge_container.setStyleSheet("""
            background-color: white;
            border: 0px solid #FF0000;
            border-radius: 0px;
            padding: 0px;
        """)

        badge_inner_layout = QtWidgets.QVBoxLayout(badge_container)
        badge_inner_layout.setSpacing(2)  # Reduced spacing

        # "HELLO" label
        hello_label = QtWidgets.QLabel("HELLO")
        hello_label.setAlignment(QtCore.Qt.AlignCenter)
        hello_label.setStyleSheet("""
            font-family: Verdana, sans-serif;
            font-size: 42px;  # Increase the font size here
            font-weight: bold;
            color: #FFFFFF;
            background-color: #FF0000;
            padding: 0px;
        """)
        badge_inner_layout.addWidget(hello_label)

        # "my name is..." label with dotted effect
        my_name_label = QtWidgets.QLabel("my name is")
        my_name_label.setAlignment(QtCore.Qt.AlignCenter)
        my_name_label.setStyleSheet("""
            font-family: Verdana, sans-serif;
            font-size: 32px;  # Increase the font size here
            color: #FFFFFF;
            background-color: #FF0000;
            padding: 2px;
        """)
        badge_inner_layout.addWidget(my_name_label)

        # Name label
        name_label = QtWidgets.QLabel(squid_name)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setStyleSheet("""
            font-family: Verdana, sans-serif;
            font-size: 44px;  # Increase the font size here
            font-weight: bold;
            color: #000000;
            background-color: #eff1f0;
            padding: 10px;
        """)
        badge_inner_layout.addWidget(name_label)

        badge_layout.addWidget(badge_container, alignment=QtCore.Qt.AlignHCenter)

        # Add both widgets to the layout
        self.layout.addWidget(about_text)
        self.layout.addWidget(badge_widget)
