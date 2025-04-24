import random
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab

class AboutTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()

    def update_from_brain_state(self, state):
        """Update tab based on brain state - handle personality updates"""
        if not hasattr(self, 'personality_label'):
            return

        # Check for personality in state
        if 'personality' in state:
            new_personality = str(state['personality']).lower().capitalize()

            # Only update if the personality has actually changed
            current_text = self.personality_label.text()
            current_personality = current_text.replace("Personality: ", "").strip()

            if new_personality != current_personality:
                #print(f"AboutTab: Updated personality from '{current_personality}' to '{new_personality}'")
                self.personality_label.setText(f"Personality: {new_personality}")

                # Enable care tips button if we now have a personality
                if hasattr(self, 'care_tips_button'):
                    self.care_tips_button.setEnabled(new_personality != "Unknown")
                    # Update button callback to use current personality
                    try:
                        self.care_tips_button.clicked.disconnect()
                    except TypeError:
                        # It's okay if there wasn't a connection
                        pass
                    self.care_tips_button.clicked.connect(lambda: self.show_care_tips(new_personality))

        # Check for squid object updates
        if hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
            squid = self.tamagotchi_logic.squid

            # Update name if it exists
            if hasattr(squid, 'name') and hasattr(self, 'name_label'):
                current_name = self.name_label.text()
                if squid.name != current_name:
                    self.name_label.setText(squid.name)

    def initialize_ui(self):
        # Get version info first
        version_info = self.get_version_info()
        
        from .display_scaling import DisplayScaling
        
        # Main text content using QTextEdit
        about_text = QtWidgets.QTextEdit()
        about_text.setReadOnly(True)
        
        # Set scaled font size for QTextEdit
        font = about_text.font()
        font.setPointSize(DisplayScaling.font_size(10))
        about_text.setFont(font)
        
        # Predefined list of approved squid names
        SQUID_NAMES = [
            "Algernon", "Cuthbert", "Englebert", "D'Artagnan",
            "Gaspard", "Ulysses", "Leopold", "Miroslav",
            "Artemis", "Jacques", "Cecil", "Wilhelm", "Giskard"
        ]
        
        # Determine the squid name and personality - more robust approach
        squid_name = random.choice(SQUID_NAMES)
        personality = "Unknown"
        
        # Debug log
        #print("AboutTab initialize_ui:")
        #print(f"  tamagotchi_logic exists: {hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None}")
        
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
                squid = self.tamagotchi_logic.squid
                
                # Get personality if available
                if hasattr(squid, 'personality'):
                    personality = str(squid.personality).split('.')[-1]
                    personality = personality.lower().capitalize()
                    print(f"  Found personality: {personality}")
                else:
                    print("  Squid has no personality attribute")
                
                # Handle name (existing or assign new)
                if hasattr(squid, 'name'):
                    if squid.name:
                        squid_name = squid.name
                        print(f"  Using existing name: {squid_name}")
                    else:
                        squid.name = squid_name
                        print(f"  Assigned new name: {squid_name}")
                else:
                    # Initialize name attribute
                    squid.name = squid_name
                    print(f"  Created new name attribute: {squid_name}")
        
        # Build About text with version info
        about_text.setHtml(f"""
        <h1>Dosidicus electronicae</h1>
        <p><a href="https://github.com/ViciousSquid/Dosidicus">github.com/ViciousSquid/Dosidicus</a></p>
        <p>A Tamagotchi-style digital pet with a simple neural network</p>
        <ul>
            <li>by Rufus Pearce (ViciousSquid)</li><br><br>
        <br>
        <b>Dosidicus version: {version_info['dosidicus']}</b><br>
        Brain Tool version: {version_info['brain_tool']}<br>
        Decision engine version: {version_info['decision_engine']}<br><br>
        <p>This is a research project. Please suggest features.</p><br><br>
        </ul>
        """)
        
        # Create a custom widget for the badge
        badge_widget = QtWidgets.QWidget()
        badge_layout = QtWidgets.QVBoxLayout(badge_widget)
        badge_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        badge_layout.setSpacing(0)  # No spacing
        
        # Badge container
        badge_container = QtWidgets.QWidget()
        badge_container.setFixedWidth(DisplayScaling.scale(300))
        badge_container.setStyleSheet("""
            background-color: white;
            border: 4px solid #FF0000;
            border-radius: 5px;
        """)
        
        badge_inner_layout = QtWidgets.QVBoxLayout(badge_container)
        badge_inner_layout.setContentsMargins(0, 0, 0, 0)  # No margins
        badge_inner_layout.setSpacing(0)  # No spacing
        
        # "HELLO" label
        hello_label = QtWidgets.QLabel("HELLO")
        hello_label.setAlignment(QtCore.Qt.AlignCenter)
        hello_label.setStyleSheet(f"""
            font-family: Arial, sans-serif;
            font-size: {DisplayScaling.font_size(38)}px;
            font-weight: bold;
            color: #FFFFFF;
            background-color: #FF0000;
        """)
        badge_inner_layout.addWidget(hello_label)
        
        # "my name is..." label
        my_name_label = QtWidgets.QLabel("my name is")
        my_name_label.setAlignment(QtCore.Qt.AlignCenter)
        my_name_label.setStyleSheet(f"""
            font-family: Arial, sans-serif;
            font-size: {DisplayScaling.font_size(20)}px;
            color: #FFFFFF;
            background-color: #FF0000;
        """)
        badge_inner_layout.addWidget(my_name_label)
        
        # Name label - editable on double-click
        self.name_label = QtWidgets.QLabel(squid_name)
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setStyleSheet(f"""
            font-family: Arial, sans-serif;
            font-size: {DisplayScaling.font_size(38)}px;
            font-weight: bold;
            color: #000000;
            background-color: white;
        """)
        self.name_label.mouseDoubleClickEvent = lambda event: self.edit_name()
        self.name_label.setToolTip("Double-click to change name")
        self.name_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        badge_inner_layout.addWidget(self.name_label)
        
        badge_layout.addWidget(badge_container, alignment=QtCore.Qt.AlignHCenter)
        
        # Add personality information below the badge
        personality_container = QtWidgets.QWidget()
        personality_layout = QtWidgets.QVBoxLayout(personality_container)
        personality_layout.setContentsMargins(DisplayScaling.scale(10), DisplayScaling.scale(20), DisplayScaling.scale(10), DisplayScaling.scale(10))
        
        # Personality label - store reference for updates
        self.personality_label = QtWidgets.QLabel(f"Personality: {personality}")
        self.personality_label.setAlignment(QtCore.Qt.AlignCenter)
        self.personality_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(22)}px;")
        personality_layout.addWidget(self.personality_label)
        
        # Button container
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, DisplayScaling.scale(10), 0, 0)

        # Add Certificate button (removed care tips button)
        certificate_button = QtWidgets.QPushButton("View Squid Certificate")
        certificate_button.clicked.connect(self.show_certificate)
        certificate_button.setStyleSheet(f"font-size: {DisplayScaling.font_size(18)}px; padding: {DisplayScaling.scale(12)}px;")
        button_layout.addWidget(certificate_button)

        # Add button container to personality layout
        personality_layout.addWidget(button_container)
        
        # Add all widgets to the main layout
        self.layout.addWidget(about_text)
        self.layout.addWidget(badge_widget)
        self.layout.addWidget(personality_container)
        
        print(f"AboutTab initialization complete - Personality: {personality}")

    def edit_name(self):
        """Allow user to edit squid name on double-click"""
        if not hasattr(self, 'name_label'):
            return

        current_name = self.name_label.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, "Change Name", "Enter new name for your squid:",
            QtWidgets.QLineEdit.Normal, current_name
        )
        if ok and new_name:
            self.name_label.setText(new_name)
            # Update the squid's name
            if hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
                self.tamagotchi_logic.squid.name = new_name

    def show_certificate(self):
        """Show the squid certificate window"""
        try:
            # Import here to avoid circular imports
            from .certificate import SquidCertificateWindow

            if not hasattr(self, 'certificate_window') or self.certificate_window is None:
                self.certificate_window = SquidCertificateWindow(self, self.tamagotchi_logic)
            else:
                # Update the certificate with current data
                self.certificate_window.update_certificate()

            self.certificate_window.show()
            self.certificate_window.raise_()
        except Exception as e:
            print(f"Error showing certificate: {e}")
            import traceback
            traceback.print_exc()

    def show_care_tips(self, personality_type):
        """Show care tips for the specific personality type"""
        tips = self.get_care_tips(personality_type.lower())

        # Create a dialog to display the tips
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"Care Tips: {personality_type}")
        dialog.setMinimumSize(600, 800)  # Increased size

        layout = QtWidgets.QVBoxLayout(dialog)

        # Add a title
        title = QtWidgets.QLabel(f"Care Tips for {personality_type} Squids")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)

        # Add the tips content
        tips_text = QtWidgets.QTextEdit()
        tips_text.setReadOnly(True)

        # Set a larger font for the tips text
        font = tips_text.font()
        font.setPointSize(12)
        tips_text.setFont(font)

        tips_text.setPlainText(tips)
        tips_text.setStyleSheet("line-height: 1.6;")  # Increased line spacing
        layout.addWidget(tips_text)

        # Add a close button
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        close_button.setFixedWidth(150)  # Wider button
        close_button.setStyleSheet("font-size: 18px; padding: 8px;")  # Larger text and padding
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)

        dialog.exec_()

    def get_care_tips(self, personality_type):
        """Return care tips for a specific personality type"""
        tips = {
            "timid": (
                "Timid Squid Care Tips:\n\n"
                "- Place plants in the environment to reduce anxiety\n"
                "- Keep the environment clean and calm\n"
                "- Approach slowly and avoid sudden movements\n"
                "- Maintain a consistent routine\n"
                "- Avoid frequent window resizing which may startle them"
            ),
            "adventurous": (
                "Adventurous Squid Care Tips:\n\n"
                "- Regularly introduce new objects or decorations\n"
                "- Provide diverse food options\n"
                "- Allow for lots of exploration space\n"
                "- Encourage physical activity\n"
                "- Enable their natural curiosity with interesting items"
            ),
            "lazy": (
                "Lazy Squid Care Tips:\n\n"
                "- Place food closer to the squid's resting spots\n"
                "- Clean the environment more frequently as they move less\n"
                "- Use enticing food to encourage movement\n"
                "- Don't expect much activity - they prefer relaxation\n"
                "- Ensure their favorite resting spots are clean and comfortable"
            ),
            "energetic": (
                "Energetic Squid Care Tips:\n\n"
                "- Provide a large, open space for movement\n"
                "- Offer frequent feeding opportunities\n"
                "- Introduce interactive elements or games\n"
                "- Keep environment stimulating with varied decorations\n"
                "- They need more food due to higher energy consumption"
            ),
            "introvert": (
                "Introvert Squid Care Tips:\n\n"
                "- Create quiet, secluded areas with decorations\n"
                "- Avoid overcrowding the environment with objects\n"
                "- Respect the squid's need for alone time\n"
                "- Create sheltered spaces using plants\n"
                "- Approach gently and give space when needed"
            ),
            "greedy": (
                "Greedy Squid Care Tips:\n\n"
                "- Offer a variety of food types, including sushi\n"
                "- Use food as a reward for desired behaviors\n"
                "- Be cautious not to overfeed\n"
                "- Will get more anxious when hungry compared to other types\n"
                "- Provide opportunities to collect and arrange items"
            ),
            "stubborn": (
                "Stubborn Squid Care Tips:\n\n"
                "- Always have sushi available as it's their favorite food\n"
                "- Be patient when introducing changes\n"
                "- Use positive reinforcement for desired behaviors\n"
                "- This squid may refuse non-sushi foods when hungry\n"
                "- May resist sleep even when tired - create calm environments"
            )
        }

        # Return tips for the specific personality, or a default message
        return tips.get(personality_type.lower(),
                        f"No specific care tips available for {personality_type} squids.")

    def get_version_info(self):
        """Read version information from the version file"""
        version_info = {
            "dosidicus": "2.1.0",  # Default versions if file not found
            "brain_tool": "2.0nf",
            "decision_engine": "2.1"
        }

        try:
            # Look for version file in the project root
            version_file = os.path.join(os.path.dirname(__file__), '..', 'version')
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    for line in f:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key in version_info:
                                version_info[key] = value
        except Exception as e:
            print(f"Error reading version file: {e}")

        return version_info