import random
import os
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .localisation import Localisation

# Predefined list of approved squid names
SQUID_NAMES = [
    "Algernon", "Cuthbert", "Englebert", "D'Artagnan",
    "Gaspard", "Ulysses", "Leopold", "Miroslav",
    "Artemis", "Jacques", "Cecil", "Wilhelm", "Giskard"
]

class AboutTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        # Initialize localisation
        self.loc = Localisation.instance()
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()

    def update_from_brain_state(self, state):
        """Update tab based on brain state - handle personality updates"""
        if not hasattr(self, 'personality_label'):
            return

        # Check for personality in state
        if 'personality' in state:
            # Get the raw personality string (e.g., "timid")
            raw_personality = str(state['personality']).lower()
            
            # Get the localized display name (e.g., "Timido")
            display_personality = self.loc.get_personality_name(raw_personality)

            # Only update if the personality has actually changed
            current_text = self.personality_label.text()
            # We construct the prefix to check against
            prefix = f"{self.loc.get('squid_personality')}: "
            current_personality_display = current_text.replace(prefix, "").strip()

            if display_personality != current_personality_display:
                # Update the label with localized text
                self.personality_label.setText(f"{prefix}{display_personality}")

                # Enable care tips button if we now have a personality
                if hasattr(self, 'care_tips_button'):
                    # Check against "Unknown" or localized equivalent if needed
                    is_valid = raw_personality != "unknown"
                    self.care_tips_button.setEnabled(is_valid)
                    
                    # Update button callback to use current personality
                    try:
                        self.care_tips_button.clicked.disconnect()
                    except TypeError:
                        pass
                    # Pass the RAW personality to show_care_tips so it can look up the key correctly
                    self.care_tips_button.clicked.connect(lambda: self.show_care_tips(raw_personality))

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
        
        # Determine the squid name and personality - more robust approach
        squid_name = random.choice(SQUID_NAMES)
        raw_personality = "unknown"
        display_personality = "Unknown"
        
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
                squid = self.tamagotchi_logic.squid
                
                # Get personality if available
                if hasattr(squid, 'personality'):
                    raw_personality = str(squid.personality).split('.')[-1].lower()
                    display_personality = self.loc.get_personality_name(raw_personality)
                    # print(f"  Found personality: {raw_personality} ({display_personality})")
                
                # Handle name (existing or assign new)
                if hasattr(squid, 'name'):
                    if squid.name:
                        squid_name = squid.name
                    else:
                        squid.name = squid_name
                else:
                    # Initialize name attribute
                    squid.name = squid_name
        
        # Build About text with version info and LOCALIZED strings
        about_html = f"""
            <h1>{self.loc.get('dosidicus_title')}</h1>
            <p>
                <img src="images/string.png"
                    width="128" height="128"
                    style="float: right; margin: 10px;">
                <p> <a href="https://github.com/ViciousSquid/Dosidicus">github.com/ViciousSquid/Dosidicus</a><br>
                {self.loc.get('dosidicus_desc')} </p> <br>
                <div style="text-align: right;"><b>{self.loc.get('string_acronym')}</b>
                <br><br></div><ul>{self.loc.get('created_by')} Rufus Pearce (ViciousSquid)<br>
                <b>{self.loc.get('version_dosidicus')} {version_info['dosidicus']}</b><br>
                {self.loc.get('version_brain_tool')} {version_info['brain_tool']}<br>
                {self.loc.get('version_decision')} {version_info['decision_engine']}<br>
                {self.loc.get('version_neuro')} {version_info['neurogenesis']}<br>
                <p>{self.loc.get('research_project')}</p><br><br>
                </ul>
                        """
        about_text.setHtml(about_html)
        
        # Create a custom widget for the badge
        badge_widget = QtWidgets.QWidget()
        badge_layout = QtWidgets.QVBoxLayout(badge_widget)
        badge_layout.setContentsMargins(0, 0, 0, 0)
        badge_layout.setSpacing(0)
        
        # Badge container
        badge_container = QtWidgets.QWidget()
        badge_container.setFixedWidth(DisplayScaling.scale(300))
        badge_container.setStyleSheet("""
            background-color: white;
            border: 4px solid #FF0000;
            border-radius: 5px;
        """)
        
        badge_inner_layout = QtWidgets.QVBoxLayout(badge_container)
        badge_inner_layout.setContentsMargins(0, 0, 0, 0)
        badge_inner_layout.setSpacing(0)
        
        # "HELLO" label
        hello_label = QtWidgets.QLabel(self.loc.get("hello"))
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
        my_name_label = QtWidgets.QLabel(self.loc.get("my_name_is"))
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
        self.name_label.setToolTip(self.loc.get("change_name")) 
        self.name_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        badge_inner_layout.addWidget(self.name_label)
        
        badge_layout.addWidget(badge_container, alignment=QtCore.Qt.AlignHCenter)
        
        # Add personality information below the badge
        personality_container = QtWidgets.QWidget()
        personality_layout = QtWidgets.QVBoxLayout(personality_container)
        personality_layout.setContentsMargins(DisplayScaling.scale(10), DisplayScaling.scale(20), DisplayScaling.scale(10), DisplayScaling.scale(10))
        
        # Personality label - store reference for updates
        # Using "squid_personality" key
        self.personality_label = QtWidgets.QLabel(f"{self.loc.get('squid_personality')}: {display_personality}")
        self.personality_label.setAlignment(QtCore.Qt.AlignCenter)
        self.personality_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(22)}px;")
        personality_layout.addWidget(self.personality_label)
        
       # Button container
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, DisplayScaling.scale(10), 0, 0)

        # Add stretchable space to the left
        button_layout.addStretch()

        # Add Certificate button
        certificate_button = QtWidgets.QPushButton(self.loc.get("view_certificate"))
        certificate_button.clicked.connect(self.show_certificate)
        certificate_button.setStyleSheet(f"font-size: {DisplayScaling.font_size(18)}px; padding: {DisplayScaling.scale(12)}px;")
        # button_layout.addWidget(certificate_button) 

        # Add color picker button
        color_button = QtWidgets.QPushButton(self.loc.get("change_colour")) 
        color_button.clicked.connect(self.open_color_picker)
        color_button.setStyleSheet(f"font-size: {DisplayScaling.font_size(18)}px; padding: {DisplayScaling.scale(12)}px; background-color: #FFC0CB;") 
        button_layout.addWidget(color_button)

        # Add stretchable space to the right
        button_layout.addStretch()

        # Add button container to personality layout
        personality_layout.addWidget(button_container)

        # Add all widgets to the main layout
        self.layout.addWidget(about_text)
        self.layout.addWidget(badge_widget)
        self.layout.addWidget(personality_container)
        
        print(f"AboutTab initialization complete - Personality: {display_personality}")

    def open_color_picker(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            if self.tamagotchi_logic and self.tamagotchi_logic.squid:
                self.tamagotchi_logic.squid.apply_tint(color)
                if hasattr(self.tamagotchi_logic, 'brain_window') and \
                hasattr(self.tamagotchi_logic.brain_window, 'statistics_tab'):
                    self.tamagotchi_logic.brain_window.statistics_tab.increment_stat('times_colour_changed')

    def edit_name(self):
        """Allow user to edit squid name on double-click"""
        if not hasattr(self, 'name_label'):
            return

        current_name = self.name_label.text()
        new_name, ok = QtWidgets.QInputDialog.getText(
            self, 
            self.loc.get("change_name"), 
            self.loc.get("enter_new_name"),
            QtWidgets.QLineEdit.Normal, 
            current_name
        )
        if ok and new_name:
            self.name_label.setText(new_name)
            # Update the squid's name
            if hasattr(self.tamagotchi_logic, 'squid') and self.tamagotchi_logic.squid:
                self.tamagotchi_logic.squid.name = new_name

    def show_certificate(self):
        """Show the squid certificate window"""
        try:
            from .certificate import SquidCertificateWindow

            if not hasattr(self, 'certificate_window') or self.certificate_window is None:
                self.certificate_window = SquidCertificateWindow(self, self.tamagotchi_logic)
            else:
                self.certificate_window.update_certificate()

            self.certificate_window.show()
            self.certificate_window.raise_()
        except Exception as e:
            print(f"Error showing certificate: {e}")
            import traceback
            traceback.print_exc()

    def show_care_tips(self, personality_type_raw):
        """Show care tips for the specific personality type"""
        # Ensure we are working with the raw string key (e.g., 'timid')
        personality_type_raw = str(personality_type_raw).lower()
        
        # Get localized name and tips
        localized_name = self.loc.get_personality_name(personality_type_raw)
        tips = self.get_care_tips(personality_type_raw)

        # Create a dialog to display the tips
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f"{self.loc.get('care_tips')}: {localized_name}")
        dialog.setMinimumSize(600, 800)

        layout = QtWidgets.QVBoxLayout(dialog)

        # Add a title
        # Uses format string "Care Tips for {personality} Squids"
        title_text = self.loc.get("care_tips_for", personality=localized_name)
        title = QtWidgets.QLabel(title_text)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)

        # Add the tips content
        tips_text = QtWidgets.QTextEdit()
        tips_text.setReadOnly(True)

        font = tips_text.font()
        font.setPointSize(12)
        tips_text.setFont(font)

        tips_text.setPlainText(tips)
        tips_text.setStyleSheet("line-height: 1.6;")
        layout.addWidget(tips_text)

        # Add a close button
        close_button = QtWidgets.QPushButton(self.loc.get("close"))
        close_button.clicked.connect(dialog.close)
        close_button.setFixedWidth(150)
        close_button.setStyleSheet("font-size: 18px; padding: 8px;")
        layout.addWidget(close_button, alignment=QtCore.Qt.AlignRight)

        dialog.exec_()

    def get_care_tips(self, personality_type):
        """Return care tips for a specific personality type using Localisation"""
        # This now delegates entirely to the Localisation class which handles languages
        return self.loc.get_care_tips(personality_type)

    def get_version_info(self):
        """Read version information from the version file"""
        version_info = {
            "dosidicus": "Dosidicus-2 2.6.1.0 b1218",
            "brain_tool": "STRINg 3",
            "decision_engine": "4.0",
            "neurogenesis": "ver3_unified"
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