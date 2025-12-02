# brain_personality_tab.py
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .personality import Personality

class PersonalityTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
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
        self.base_font_size = DisplayScaling.font_size(10)  # Reduced from 14
        self.header_font_size = DisplayScaling.font_size(12)  # Reduced from 18
        
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
        self.personality_type_label = QtWidgets.QLabel("Squid Personality: ")
        font = QtGui.QFont()
        font.setPointSize(self.header_font_size)
        font.setBold(True)
        self.personality_type_label.setFont(font)
        self.tab_layout.addWidget(self.personality_type_label)

        # Personality modifier label - larger
        self.personality_modifier_label = QtWidgets.QLabel("Personality Modifier: ")
        mod_font = QtGui.QFont()
        mod_font.setPointSize(self.base_font_size)
        mod_font.setBold(True)
        self.personality_modifier_label.setFont(mod_font)
        self.tab_layout.addWidget(self.personality_modifier_label)

        # Separator
        self.tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))
        self.tab_layout.addSpacing(20)  # Add space between sections

        # Description section
        description_label = QtWidgets.QLabel("Description:")
        description_label.setFont(font)  # Use the same large font for all section headers
        self.tab_layout.addWidget(description_label)

        self.personality_description = QtWidgets.QTextEdit()
        self.personality_description.setReadOnly(True)
        text_font = QtGui.QFont()
        text_font.setPointSize(self.base_font_size)
        self.personality_description.setFont(text_font)
        self.tab_layout.addWidget(self.personality_description)
        self.tab_layout.addSpacing(20)  # Add space between sections

        # Personality modifiers
        self.modifiers_label = QtWidgets.QLabel("Personality Modifiers:")
        self.modifiers_label.setFont(font)
        self.tab_layout.addWidget(self.modifiers_label)

        self.modifiers_text = QtWidgets.QTextEdit()
        self.modifiers_text.setReadOnly(True)
        self.modifiers_text.setFont(text_font)
        self.tab_layout.addWidget(self.modifiers_text)
        self.tab_layout.addSpacing(20)  # Add space between sections

        # Care tips
        self.care_tips_label = QtWidgets.QLabel("Care Tips:")
        self.care_tips_label.setFont(font)
        self.tab_layout.addWidget(self.care_tips_label)

        self.care_tips = QtWidgets.QTextEdit()
        self.care_tips.setReadOnly(True)
        self.care_tips.setFont(text_font)
        self.tab_layout.addWidget(self.care_tips)
        self.tab_layout.addSpacing(20)  # Add space between sections

        # Note about personality generation
        note_label = QtWidgets.QLabel("Note: Personality is randomly generated at the start of a new game")
        note_font = QtGui.QFont()
        note_font.setPointSize(self.base_font_size)
        note_font.setItalic(True)
        note_label.setFont(note_font)
        self.tab_layout.addWidget(note_label)
        
        # Set fixed heights for text boxes to make them more compact
        for text_box in [self.personality_description, self.modifiers_text, self.care_tips]:
            text_box.setMinimumHeight(150)  # Ensure enough space for content
            text_box.setMaximumHeight(200)  # Limit maximum height

    def update_from_brain_state(self, state):
        """Update personality info when brain state changes"""
        if 'personality' in state:
            self.update_personality_display(state['personality'])
            
    def update_personality_display(self, personality):
        """Update all personality display elements"""
        # Convert enum to string if needed
        personality_str = getattr(personality, 'value', str(personality))
        
        # Set personality type label
        self.personality_type_label.setText(f"Squid Personality: {personality_str.capitalize()}")
        
        # Set personality modifier label
        self.personality_modifier_label.setText(f"Personality Modifier: {self.get_personality_modifier(personality)}")
        
        # Set description text
        self.personality_description.setPlainText(self.get_personality_description(personality))
        
        # Set modifiers text
        self.modifiers_text.setPlainText(self.get_personality_modifiers(personality))
        
        # Set care tips text
        self.care_tips.setPlainText(self.get_care_tips(personality))
        
    def get_personality_description(self, personality):
        descriptions = {
            Personality.TIMID: "Your squid is Timid. It tends to be more easily startled and anxious, especially in new situations. It may prefer quiet, calm environments and might be less likely to explore on its own. However, it can form strong bonds when it feels safe and secure.",
            Personality.ADVENTUROUS: "Your squid is Adventurous. It loves to explore and try new things. It's often the first to investigate new objects or areas in its environment. This squid thrives on novelty and might get bored more easily in unchanging surroundings.",
            Personality.LAZY: "Your squid is Lazy. It prefers a relaxed lifestyle and may be less active than other squids. It might need extra encouragement to engage in activities but can be quite content just lounging around. This squid is great at conserving energy!",
            Personality.ENERGETIC: "Your squid is Energetic. It's always on the move, full of life and vigor. This squid needs plenty of stimulation and activities to keep it happy. It might get restless if not given enough opportunity to burn off its excess energy.",
            Personality.INTROVERT: "Your squid is an Introvert. It enjoys solitude and might prefer quieter, less crowded spaces. While it can interact with others, it may need time alone to 'recharge'. This squid might be more observant and thoughtful in its actions.",
            Personality.GREEDY: "Your squid is Greedy. It has a strong focus on food and resources. This squid might be more motivated by treats and rewards than others. While it can be more demanding, it also tends to be resourceful and good at finding hidden treats!",
            Personality.STUBBORN: "Your squid is Stubborn. It has a strong will and definite preferences. This squid might be more resistant to change and could take longer to adapt to new routines. However, its determination can also make it persistent in solving problems."
        }
        # Handle string or enum input
        if isinstance(personality, str):
            try:
                return descriptions.get(Personality(personality), "Unknown personality type")
            except ValueError:
                return "Unknown personality type"
        return descriptions.get(personality, "Unknown personality type")

    def get_personality_modifier(self, personality):
        modifiers = {
            Personality.TIMID: "Higher chance of becoming anxious",
            Personality.ADVENTUROUS: "Increased curiosity and exploration",
            Personality.LAZY: "Slower movement and energy consumption",
            Personality.ENERGETIC: "Faster movement and higher activity levels",
            Personality.INTROVERT: "Prefers solitude and quiet environments",
            Personality.GREEDY: "More focused on food and resources",
            Personality.STUBBORN: "Only eats favorite food (sushi), may refuse to sleep"
        }
        # Handle string or enum input
        if isinstance(personality, str):
            try:
                return modifiers.get(Personality(personality), "No specific modifier")
            except ValueError:
                return "No specific modifier"
        return modifiers.get(personality, "No specific modifier")
    
    def get_care_tips(self, personality):
        tips = {
            Personality.TIMID: (
                "- Place plants in the environment to reduce anxiety\n"
                "- Keep the environment clean and calm\n"
                "- Approach slowly and avoid sudden movements\n"
                "- Maintain a consistent routine\n"
                "- Avoid frequent window resizing which may startle them"
            ),
            Personality.ADVENTUROUS: (
                "- Regularly introduce new objects or decorations\n"
                "- Provide diverse food options\n"
                "- Encourage exploration with strategic food placement\n"
                "- Allow for lots of exploration space\n"
                "- Enable their natural curiosity with interesting items"
            ),
            Personality.LAZY: (
                "- Place food closer to the squid's resting spots\n"
                "- Clean the environment more frequently\n"
                "- Use enticing food to encourage movement\n"
                "- Don't expect much activity - they prefer relaxation\n"
                "- Ensure their favorite resting spots are clean and comfortable"
            ),
            Personality.ENERGETIC: (
                "- Provide a large, open space for movement\n"
                "- Offer frequent feeding opportunities\n"
                "- Introduce interactive elements or games\n"
                "- Keep environment stimulating with varied decorations\n"
                "- They need more food due to higher energy consumption"
            ),
            Personality.INTROVERT: (
                "- Create quiet, secluded areas with decorations\n"
                "- Avoid overcrowding the environment\n"
                "- Respect the squid's need for alone time\n"
                "- Create sheltered spaces using plants\n"
                "- Approach gently and give space when needed"
            ),
            Personality.GREEDY: (
                "- Offer a variety of food types, including sushi\n"
                "- Use food as a reward for desired behaviors\n"
                "- Be cautious not to overfeed\n"
                "- Will get more anxious when hungry compared to other types\n"
                "- Provide opportunities to collect and arrange items"
            ),
            Personality.STUBBORN: (
                "- Always have sushi available as it's their favorite food\n"
                "- Be patient when introducing changes\n"
                "- Use positive reinforcement for desired behaviors\n"
                "- This squid may refuse non-sushi foods when hungry\n"
                "- May resist sleep even when tired - create calm environments"
            )
        }
        
        # Handle string or enum input
        if isinstance(personality, str):
            try:
                return tips.get(Personality(personality), "No specific care tips available for this personality.")
            except ValueError:
                return "No specific care tips available for this personality."
        return tips.get(personality, "No specific care tips available for this personality.")

    def get_personality_modifiers(self, personality):
        modifiers = {
            Personality.TIMID: "- Anxiety increases 50% faster\n- Curiosity increases 50% slower\n- Anxiety decreases by 50% when near plants",
            Personality.ADVENTUROUS: "- Curiosity increases 50% faster",
            Personality.LAZY: "- Moves slower\n- Energy consumption is lower",
            Personality.ENERGETIC: "- Moves faster\n- Energy consumption is higher",
            Personality.INTROVERT: "- Prefers quieter, less crowded spaces\n- May need more time alone to 'recharge'",
            Personality.GREEDY: "- Gets 50% more anxious when hungry\n- Satisfaction increases more when eating",
            Personality.STUBBORN: "- Prefers favorite food (sushi)\n- May refuse to sleep even when tired"
        }
        # Handle string or enum input
        if isinstance(personality, str):
            try:
                return modifiers.get(Personality(personality), "No specific modifiers available for this personality.")
            except ValueError:
                return "No specific modifiers available for this personality."
        return modifiers.get(personality, "No specific modifiers available for this personality.")