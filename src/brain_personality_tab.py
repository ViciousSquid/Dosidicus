# brain_personality_tab.py
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .personality import Personality
from .localisation import Localisation

class PersonalityTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.loc = Localisation.instance()
        self.initialize_ui()
        
    def initialize_ui(self):
        from .display_scaling import DisplayScaling
        
        # Create a scrollable area for the tab content
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        # Create content widget
        content_widget = QtWidgets.QWidget()
        self.tab_layout = QtWidgets.QVBoxLayout(content_widget)
        
        # Use properly scaled font sizes
        self.base_font_size = DisplayScaling.font_size(10)
        self.header_font_size = DisplayScaling.font_size(12)
        
        # Add personality section
        self.init_personality_section()
        
        # Set the scroll area's widget
        scroll_area.setWidget(content_widget)
        
        # Add to main layout
        self.layout.addWidget(scroll_area)
        
    def init_personality_section(self):
        # Separator line
        self.tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))
        
        # Personality type label - larger and bolder
        self.personality_type_label = QtWidgets.QLabel(f"{self.loc.get('squid_personality')}: ")
        font = QtGui.QFont()
        font.setPointSize(self.header_font_size)
        font.setBold(True)
        self.personality_type_label.setFont(font)
        self.tab_layout.addWidget(self.personality_type_label)

        # Personality modifier label - larger
        self.personality_modifier_label = QtWidgets.QLabel(f"{self.loc.get('personality_modifier')}: ")
        mod_font = QtGui.QFont()
        mod_font.setPointSize(self.base_font_size)
        mod_font.setBold(True)
        self.personality_modifier_label.setFont(mod_font)
        self.tab_layout.addWidget(self.personality_modifier_label)

        # Separator
        self.tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))
        self.tab_layout.addSpacing(20)

        # Description section
        description_label = QtWidgets.QLabel(self.loc.get("description"))
        description_label.setFont(font)
        self.tab_layout.addWidget(description_label)

        self.personality_description = QtWidgets.QTextEdit()
        self.personality_description.setReadOnly(True)
        text_font = QtGui.QFont()
        text_font.setPointSize(self.base_font_size)
        self.personality_description.setFont(text_font)
        self.tab_layout.addWidget(self.personality_description)
        self.tab_layout.addSpacing(20)

        # Personality modifiers
        self.modifiers_label = QtWidgets.QLabel(self.loc.get("personality_modifiers"))
        self.modifiers_label.setFont(font)
        self.tab_layout.addWidget(self.modifiers_label)

        self.modifiers_text = QtWidgets.QTextEdit()
        self.modifiers_text.setReadOnly(True)
        self.modifiers_text.setFont(text_font)
        self.tab_layout.addWidget(self.modifiers_text)
        self.tab_layout.addSpacing(20)

        # Care tips
        self.care_tips_label = QtWidgets.QLabel(self.loc.get("care_tips_label"))
        self.care_tips_label.setFont(font)
        self.tab_layout.addWidget(self.care_tips_label)

        self.care_tips = QtWidgets.QTextEdit()
        self.care_tips.setReadOnly(True)
        self.care_tips.setFont(text_font)
        self.tab_layout.addWidget(self.care_tips)
        self.tab_layout.addSpacing(20)

        # Note about personality generation
        note_label = QtWidgets.QLabel(self.loc.get("personality_note"))
        note_font = QtGui.QFont()
        note_font.setPointSize(self.base_font_size)
        note_font.setItalic(True)
        note_label.setFont(note_font)
        self.tab_layout.addWidget(note_label)
        
        # Set fixed heights for text boxes to make them more compact
        for text_box in [self.personality_description, self.modifiers_text, self.care_tips]:
            text_box.setMinimumHeight(150)
            text_box.setMaximumHeight(200)

    def update_from_brain_state(self, state):
        """Update personality info when brain state changes"""
        if 'personality' in state:
            self.update_personality_display(state['personality'])
            
    def update_personality_display(self, personality):
        """Update all personality display elements"""
        # Get translated personality name
        personality_name = self.loc.get_personality_name(personality)
        
        # Set personality type label
        self.personality_type_label.setText(f"{self.loc.get('squid_personality')}: {personality_name}")
        
        # Set personality modifier label
        self.personality_modifier_label.setText(f"{self.loc.get('personality_modifier')}: {self.get_personality_modifier(personality)}")
        
        # Set description text
        self.personality_description.setPlainText(self.get_personality_description(personality))
        
        # Set modifiers text
        self.modifiers_text.setPlainText(self.get_personality_modifiers(personality))
        
        # Set care tips text
        self.care_tips.setPlainText(self.get_care_tips(personality))
        
    def get_personality_description(self, personality):
        """Get translated personality description"""
        return self.loc.get_personality_description(personality)

    def get_personality_modifier(self, personality):
        """Get translated personality modifier text"""
        return self.loc.get_personality_modifier_text(personality)
    
    def get_care_tips(self, personality):
        """Get translated care tips"""
        return self.loc.get_care_tips(personality)

    def get_personality_modifiers(self, personality):
        """Get translated detailed personality modifiers"""
        return self.loc.get_personality_modifiers(personality)
