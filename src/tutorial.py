# tutorial.py
from PyQt5 import QtCore, QtGui, QtWidgets
import logging

class TutorialManager:
    """Manages tutorial overlays and sequences for the Dosidicus application"""
    
    def __init__(self, ui_reference, main_window):
        self.ui = ui_reference
        self.main_window = main_window
        self.tutorial_elements = []
        self.tutorial_timer = None
        self.current_step = 0
        logging.debug("TutorialManager initialized with ui_reference and main_window")
    
    def get_tutorial_font_sizes(self, base_title_size=12, base_body_size=11):
        """Determine font sizes for tutorial text, increasing by 2 for ~1920x1080 resolution"""
        from .display_scaling import DisplayScaling
        screen_width = QtWidgets.QApplication.primaryScreen().size().width()
        
        # Check if resolution is around 1920x1080 (within 1800-2000 pixels width)
        if 1800 <= screen_width <= 2000:
            title_font_size = DisplayScaling.font_size(base_title_size + 2)  # Increased by 2 instead of 1
            body_font_size = DisplayScaling.font_size(base_body_size + 2)    # Increased by 2 instead of 1
        else:
            title_font_size = DisplayScaling.font_size(base_title_size)
            body_font_size = DisplayScaling.font_size(base_body_size)
        
        return title_font_size, body_font_size
    
    def start_tutorial(self):
        logging.debug("Starting tutorial sequence")
        self.current_step = 0
        self.show_first_tutorial()
    
    def show_first_tutorial(self):
        """Show the initial tutorial about basic squid care"""
        # Clear any existing tutorial elements
        self.clear_tutorial_elements()
        
        # Get current window dimensions from UI
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        # Create a banner across the bottom of the screen
        banner_height = 100
        
        # POSITION ADJUSTMENT: Move banner up by 40px from bottom
        # TODO: Fine-tune this offset value as needed
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(0, 0, 0, 230))  # Nearly opaque black
        banner.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 150), 1))
        banner.setZValue(2000)  # Extremely high Z-value to ensure it's on top
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        # Get scaled font sizes
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("⚠️")
        title_text.setDefaultTextColor(QtGui.QColor(255, 215, 0))  # Gold color
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Create body text
        info_text = QtWidgets.QGraphicsTextItem(
            "A squid has hatched and you must look after him!\n"
            "• Feed him when he's hungry\n"
            "• Clean his tank when it gets dirty\n"
            "• Watch his behavior to learn about his personality"
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)  # Leave room for button
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        # Add a dismiss button
        dismiss_button = QtWidgets.QPushButton("Got it!")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        dismiss_button.clicked.connect(self.advance_to_next_step)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)  # Higher than other elements
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        # Set auto-dismiss timer
        self.start_auto_dismiss_timer(15000)  # 15 seconds
    
    def show_second_tutorial(self):
        logging.debug("Showing second tutorial (NEURAL NETWORK)")
        try:
            # Verify scene is ready
            if not self.ui.scene:
                logging.error("UI scene not initialized")
                self.end_tutorial()
                return

            self.clear_tutorial_elements()
            win_width = self.ui.window_width
            win_height = self.ui.window_height
            banner_height = 100
            banner_y_offset = 40
            banner_y = win_height - banner_height - banner_y_offset

            banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
            banner.setBrush(QtGui.QColor(25, 25, 112, 230))
            banner.setPen(QtGui.QPen(QtGui.QColor(135, 206, 250, 150), 1))
            banner.setZValue(2000)
            setattr(banner, '_is_tutorial_element', True)
            self.ui.scene.addItem(banner)
            self.tutorial_elements.append(banner)

            from .display_scaling import DisplayScaling
            screen_width = QtWidgets.QApplication.primaryScreen().size().width()
            if screen_width <= 1920:
                title_base_size = 14
                body_base_size = 13
            else:
                title_base_size = 12
                body_base_size = 11
            title_font_size, body_font_size = self.get_tutorial_font_sizes(title_base_size, body_base_size)

            title_text = QtWidgets.QGraphicsTextItem("🧠")
            title_text.setDefaultTextColor(QtGui.QColor(135, 206, 250))
            title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
            title_text.setPos(20, banner_y + 10)
            title_text.setZValue(2001)
            setattr(title_text, '_is_tutorial_element', True)
            self.ui.scene.addItem(title_text)
            self.tutorial_elements.append(title_text)

            info_text = QtWidgets.QGraphicsTextItem(
                "This is the squid's neural network. His behaviour is driven by his needs (round neurons).\n"
                "The network adapts and learns as the squid interacts with his environment."
            )
            info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            info_text.setFont(QtGui.QFont("Arial", body_font_size))
            info_text.setPos(20, banner_y + 35)
            info_text.setTextWidth(win_width - 150)
            info_text.setZValue(2001)
            setattr(info_text, '_is_tutorial_element', True)
            self.ui.scene.addItem(info_text)
            self.tutorial_elements.append(info_text)

            dismiss_button = QtWidgets.QPushButton("Next")
            dismiss_button.setStyleSheet(DisplayScaling.scale_css("""
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
            """))
            dismiss_button.clicked.connect(self.advance_to_next_step)

            dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
            dismiss_proxy.setPos(win_width - 120, banner_y + 35)
            dismiss_proxy.setZValue(2002)
            setattr(dismiss_proxy, '_is_tutorial_element', True)
            self.tutorial_elements.append(dismiss_proxy)

            self.start_auto_dismiss_timer(15000)
        except Exception as e:
            logging.error(f"Error in show_second_tutorial: {str(e)}")
            self.end_tutorial()
    
    def show_neurogenesis_tutorial(self):
        """Show the third tutorial about neurogenesis"""
        # Clear previous tutorial elements
        self.clear_tutorial_elements()
        
        # Get current window dimensions
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        # Create banner (positioned higher as specified)
        banner_height = 100
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(70, 25, 110, 230))  # Purple-ish, nearly opaque
        banner.setPen(QtGui.QPen(QtGui.QColor(200, 150, 255, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        # Get scaled font sizes
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("🔄")
        title_text.setDefaultTextColor(QtGui.QColor(200, 150, 255))  # Light purple
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Create body text - STEP 3 content
        info_text = QtWidgets.QGraphicsTextItem(
            "The squid can generate new neurons in response to extreme environmental stimulus.\n"
            "These new neurons help the squid adapt to challenging situations."
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        # Add a continue button
        dismiss_button = QtWidgets.QPushButton("Next")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #8A2BE2;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #9932CC;
            }
        """)
        dismiss_button.clicked.connect(self.advance_to_next_step)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        # Set auto-dismiss timer
        self.start_auto_dismiss_timer(15000)
    
    def show_learning_tutorial(self):
        """Show the fourth tutorial about hebbian learning"""
        # Switch to the learning tab first
        if hasattr(self.ui, 'squid_brain_window') and self.ui.squid_brain_window:
            if hasattr(self.ui.squid_brain_window, 'tabs'):
                # Find the learning tab index
                learning_tab_index = -1
                for i in range(self.ui.squid_brain_window.tabs.count()):
                    if self.ui.squid_brain_window.tabs.tabText(i) == "Learning":
                        learning_tab_index = i
                        break
                
                if learning_tab_index >= 0:
                    self.ui.squid_brain_window.tabs.setCurrentIndex(learning_tab_index)
        
        # Clear previous tutorial elements
        self.clear_tutorial_elements()
        
        # Get current window dimensions
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        # Create banner (positioned higher as specified)
        banner_height = 100
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(0, 100, 0, 230))  # Green, nearly opaque
        banner.setPen(QtGui.QPen(QtGui.QColor(144, 238, 144, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        # Get scaled font sizes
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("🧬")
        title_text.setDefaultTextColor(QtGui.QColor(144, 238, 144))  # Light green
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Create body text for STEP 4
        info_text = QtWidgets.QGraphicsTextItem(
            "When a pair of neurons fire at the same time, their connection strengthens. "
            "This allows the squid to learn associations between different stimuli and responses."
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        # Add a continue button
        dismiss_button = QtWidgets.QPushButton("Next")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #228B22;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #32CD32;
            }
        """)
        dismiss_button.clicked.connect(self.advance_to_next_step)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        # Set auto-dismiss timer
        self.start_auto_dismiss_timer(15000)
    
    def show_decisions_tutorial(self):
        """Show the fifth tutorial about decision making"""
        # Switch to the decisions tab first
        if hasattr(self.ui, 'squid_brain_window') and self.ui.squid_brain_window:
            if hasattr(self.ui.squid_brain_window, 'tabs'):
                # Find the decisions tab index
                decisions_tab_index = -1
                for i in range(self.ui.squid_brain_window.tabs.count()):
                    if self.ui.squid_brain_window.tabs.tabText(i) == "Decisions":
                        decisions_tab_index = i
                        break
                
                if decisions_tab_index >= 0:
                    self.ui.squid_brain_window.tabs.setCurrentIndex(decisions_tab_index)
        
        # Clear previous tutorial elements
        self.clear_tutorial_elements()
        
        # Get current window dimensions
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        # Create banner (positioned higher as specified)
        banner_height = 100
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(139, 69, 19, 230))  # Brown, nearly opaque
        banner.setPen(QtGui.QPen(QtGui.QColor(222, 184, 135, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        # Get scaled font sizes
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("🤔")
        title_text.setDefaultTextColor(QtGui.QColor(222, 184, 135))  # Tan
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Create body text for STEP 5
        info_text = QtWidgets.QGraphicsTextItem(
            "The neural network makes decisions based on current needs and past memories.\n"
            "Each decision affects the squid's state and shapes future behavior."
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        # Add a continue button
        dismiss_button = QtWidgets.QPushButton("Next")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #8B4513;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """)
        dismiss_button.clicked.connect(self.advance_to_next_step)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        # Set auto-dismiss timer
        self.start_auto_dismiss_timer(15000)
    
    def show_decorations_tutorial(self):
        """Show the sixth tutorial about decorations"""
        # Position and show the decorations window in the bottom right
        if hasattr(self.ui, 'decoration_window') and self.ui.decoration_window:
            # Call the method to position and show the decoration window
            self.main_window.position_and_show_decoration_window()
            if hasattr(self.ui, 'decorations_action'):
                self.ui.decorations_action.setChecked(True)
        
        # Switch to memory tab in brain window
        if hasattr(self.ui, 'squid_brain_window') and self.ui.squid_brain_window:
            if hasattr(self.ui.squid_brain_window, 'tabs'):
                # Find the memory tab index
                memory_tab_index = -1
                for i in range(self.ui.squid_brain_window.tabs.count()):
                    if self.ui.squid_brain_window.tabs.tabText(i) == "Memory":
                        memory_tab_index = i
                        break
                
                if memory_tab_index >= 0:
                    self.ui.squid_brain_window.tabs.setCurrentIndex(memory_tab_index)
        
        # Clear previous tutorial elements
        self.clear_tutorial_elements()
        
        # Get current window dimensions
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        # Create banner (positioned higher as specified)
        banner_height = 100
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(70, 130, 180, 230))  # Steel blue, nearly opaque
        banner.setPen(QtGui.QPen(QtGui.QColor(173, 216, 230, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        # Get scaled font sizes
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("🌿 ")
        title_text.setDefaultTextColor(QtGui.QColor(173, 216, 230))  # Light blue
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Create body text for STEP 6
        info_text = QtWidgets.QGraphicsTextItem(
            "Drag and drop decorations into the environment and see how squid reacts to different things.\n"
            "Each decoration affects the squid's mental state in unique ways."
            "Click and use the mouse wheel to resize"
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        # Add a continue button
        dismiss_button = QtWidgets.QPushButton("Next")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #4682B4;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5F9EA0;
            }
        """)
        dismiss_button.clicked.connect(self.advance_to_next_step)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        # Set auto-dismiss timer
        self.start_auto_dismiss_timer(15000)
    
    def show_final_tutorial(self):
        """Show the final tutorial step with concluding message"""
        # Clear previous tutorial elements
        self.clear_tutorial_elements()
        
        # Get current window dimensions
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        # Create banner (positioned higher as specified)
        banner_height = 100
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(75, 0, 130, 230))  # Indigo, nearly opaque
        banner.setPen(QtGui.QPen(QtGui.QColor(147, 112, 219, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        # Get scaled font sizes
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        # Create title with icon
        title_text = QtWidgets.QGraphicsTextItem("✨")
        title_text.setDefaultTextColor(QtGui.QColor(147, 112, 219))  # Medium purple
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Create body text for STEP 7
        info_text = QtWidgets.QGraphicsTextItem(
            "Keep satisfaction high and anxiety low.\n"
            "Your squid will develop unique traits and behaviors based on how you raise him."
        )
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        # Add a finish button
        dismiss_button = QtWidgets.QPushButton("Finish")
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #9370DB;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #8A2BE2;
            }
        """)
        dismiss_button.clicked.connect(self.end_tutorial)
        
        # Create a proxy widget for the button
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        # Set auto-dismiss timer
        self.start_auto_dismiss_timer(15000)
    
    def advance_to_next_step(self):
        logging.debug(f"Advancing to tutorial step {self.current_step + 1}")
        self.cancel_auto_dismiss_timer()
        self.clear_tutorial_elements()
        self.current_step += 1

        if self.current_step == 1:
            # Check if brain window is initialized
            if not hasattr(self.ui, 'squid_brain_window') or not self.ui.squid_brain_window:
                logging.error("squid_brain_window not initialized or None")
                self.end_tutorial()  # Skip tutorial to avoid crash
                return

            # Verify brain window components
            try:
                if not hasattr(self.ui.squid_brain_window, 'brain_widget') or not self.ui.squid_brain_window.brain_widget:
                    logging.error("squid_brain_window.brain_widget not initialized")
                    self.end_tutorial()
                    return

                # Show brain window
                logging.debug("Showing squid_brain_window")
                self.ui.squid_brain_window.show()
                if hasattr(self.ui, 'brain_action'):
                    self.ui.brain_action.setChecked(True)

                # Increase delay to 1000ms to ensure window is fully initialized
                QtCore.QTimer.singleShot(1000, self.show_second_tutorial)
            except Exception as e:
                logging.error(f"Error showing brain window: {str(e)}")
                self.end_tutorial()
                return

        elif self.current_step == 2:
            QtCore.QTimer.singleShot(300, self.show_neurogenesis_tutorial)
        elif self.current_step == 3:
            QtCore.QTimer.singleShot(300, self.show_learning_tutorial)
        elif self.current_step == 4:
            QtCore.QTimer.singleShot(300, self.show_decisions_tutorial)
        elif self.current_step == 5:
            QtCore.QTimer.singleShot(300, self.show_decorations_tutorial)
        elif self.current_step == 6:
            QtCore.QTimer.singleShot(300, self.show_final_tutorial)
        else:
            self.end_tutorial()
    
    def end_tutorial(self):
        """End the tutorial sequence and clean up"""
        self.cancel_auto_dismiss_timer()
        self.clear_tutorial_elements()
        self.current_step = 0
    
    def start_auto_dismiss_timer(self, ms_duration):
        """Start a timer to automatically dismiss the current tutorial step"""
        # Cancel any existing timer
        self.cancel_auto_dismiss_timer()
        
        # Create new timer
        self.tutorial_timer = QtCore.QTimer()
        self.tutorial_timer.timeout.connect(self.advance_to_next_step)
        self.tutorial_timer.setSingleShot(True)
        self.tutorial_timer.start(ms_duration)
    
    def cancel_auto_dismiss_timer(self):
        """Cancel the auto-dismiss timer if active"""
        if self.tutorial_timer and self.tutorial_timer.isActive():
            self.tutorial_timer.stop()
            self.tutorial_timer = None
    
    def clear_tutorial_elements(self):
        """Remove all tutorial elements from the scene"""
        # Remove any existing tutorial elements from the scene
        for item in self.tutorial_elements:
            if item in self.ui.scene.items():
                self.ui.scene.removeItem(item)
        
        # Clear the list
        self.tutorial_elements = []
        
        # Force scene update
        self.ui.scene.update()