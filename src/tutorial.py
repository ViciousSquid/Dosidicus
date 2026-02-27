# tutorial.py
from PyQt5 import QtCore, QtGui, QtWidgets
import logging
import random
from .localisation import Localisation

class TutorialManager:
    """Manages tutorial overlays and sequences"""
    
    def __init__(self, ui_reference, main_window):
        self.ui = ui_reference
        self.main_window = main_window
        self.tutorial_elements = []
        self.tutorial_timer = None
        self.current_step = 0
        self.loc = Localisation.instance()
        logging.debug("TutorialManager initialized with ui_reference and main_window")
    
    def get_tutorial_font_sizes(self, base_title_size=12, base_body_size=11):
        """Determine font sizes for tutorial text, increasing by 2 for ~1920x1080 resolution"""
        from .display_scaling import DisplayScaling
        screen_width = QtWidgets.QApplication.primaryScreen().size().width()
        
        if 1800 <= screen_width <= 2000:
            title_font_size = DisplayScaling.font_size(base_title_size + 2)
            body_font_size = DisplayScaling.font_size(base_body_size + 2)
        else:
            title_font_size = DisplayScaling.font_size(base_title_size)
            body_font_size = DisplayScaling.font_size(base_body_size)
        
        return title_font_size, body_font_size
    
    def start_tutorial(self):
        logging.debug("Starting tutorial")
        try:
            if not hasattr(self, 'ui') or not self.ui:
                logging.error("UI reference missing, cannot start tutorial")
                return
                
            if not hasattr(self.ui, 'scene') or not self.ui.scene:
                logging.error("Scene not initialized, cannot start tutorial")
                return
            
            if (hasattr(self.ui, 'squid_brain_window') and 
                self.ui.squid_brain_window and 
                hasattr(self.ui.squid_brain_window, 'brain_widget') and
                self.ui.squid_brain_window.brain_widget):
                self.ui.squid_brain_window.brain_widget.is_tutorial_mode = True
                logging.debug("Tutorial mode enabled in brain widget")
            
            self.current_step = 0
            self.show_first_tutorial()
        except Exception as e:
            logging.error(f"Error starting tutorial: {str(e)}")
            self.end_tutorial()
    
    def show_first_tutorial(self):
        """Show the initial tutorial about basic squid care"""
        self.clear_tutorial_elements()
        
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        banner_height = 170
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset - 100
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(0, 0, 0, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        title_text = QtWidgets.QGraphicsTextItem("⚠️")
        title_text.setDefaultTextColor(QtGui.QColor(255, 215, 0))
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        # Use localised text
        info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step1_text"))
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        dismiss_button = QtWidgets.QPushButton(self.loc.get("got_it"))
        dismiss_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        dismiss_button.clicked.connect(self.advance_to_next_step)
        
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        self.start_auto_dismiss_timer(15000)
    
    def show_second_tutorial(self):
        logging.debug("Showing second tutorial (NEURAL NETWORK)")
        try:
            if not self.ui.scene:
                logging.error("UI scene not initialized")
                self.end_tutorial()
                return

            self.clear_tutorial_elements()
            
            if (hasattr(self.ui, 'squid_brain_window') and 
                self.ui.squid_brain_window and 
                hasattr(self.ui.squid_brain_window, 'brain_widget') and
                self.ui.squid_brain_window.brain_widget):
                self.ui.squid_brain_window.brain_widget.start_tutorial_glow(duration_ms=3000)
                logging.debug("Started tutorial glow on brain widget")
            
            win_width = self.ui.window_width
            win_height = self.ui.window_height
            banner_height = 170
            banner_y_offset = 40
            banner_y = win_height - banner_height - banner_y_offset - 100

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

            info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step2_text"))
            info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
            info_text.setFont(QtGui.QFont("Arial", body_font_size))
            info_text.setPos(20, banner_y + 35)
            info_text.setTextWidth(win_width - 150)
            info_text.setZValue(2001)
            setattr(info_text, '_is_tutorial_element', True)
            self.ui.scene.addItem(info_text)
            self.tutorial_elements.append(info_text)

            dismiss_button = QtWidgets.QPushButton(self.loc.get("next"))
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
        """Show the third tutorial about neurogenesis with example neurons"""
        self.clear_tutorial_elements()
        self.create_tutorial_example_neurons()
        
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        banner_height = 170
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset - 100
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(70, 25, 110, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(200, 150, 255, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        title_text = QtWidgets.QGraphicsTextItem("🔄")
        title_text.setDefaultTextColor(QtGui.QColor(200, 150, 255))
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step3_text"))
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        dismiss_button = QtWidgets.QPushButton(self.loc.get("next"))
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
        
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        self.start_auto_dismiss_timer(15000)
    
    def show_learning_tutorial(self):
        """Show the fourth tutorial about hebbian learning"""
        if (hasattr(self.ui, 'squid_brain_window') and 
            self.ui.squid_brain_window and 
            hasattr(self.ui.squid_brain_window, 'brain_widget')):
            self.ui.squid_brain_window.brain_widget.perform_hebbian_learning()
            logging.debug("Forced Hebbian learning cycle before learning tutorial step")
        
        if hasattr(self.ui, 'squid_brain_window') and self.ui.squid_brain_window:
            if hasattr(self.ui.squid_brain_window, 'tabs'):
                learning_tab_index = -1
                for i in range(self.ui.squid_brain_window.tabs.count()):
                    if self.ui.squid_brain_window.tabs.tabText(i) == "Learning":
                        learning_tab_index = i
                        break
                
                if learning_tab_index >= 0:
                    self.ui.squid_brain_window.tabs.setCurrentIndex(learning_tab_index)
        
        self.clear_tutorial_elements()
        
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        banner_height = 170
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset - 100
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(0, 100, 0, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(144, 238, 144, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        title_text = QtWidgets.QGraphicsTextItem("🧬")
        title_text.setDefaultTextColor(QtGui.QColor(144, 238, 144))
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step4_text"))
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        dismiss_button = QtWidgets.QPushButton(self.loc.get("next"))
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
        
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        self.start_auto_dismiss_timer(15000)
    
    def show_decisions_tutorial(self):
        """Show the fifth tutorial about decision making"""
        if hasattr(self.ui, 'squid_brain_window') and self.ui.squid_brain_window:
            if hasattr(self.ui.squid_brain_window, 'tabs'):
                decisions_tab_index = -1
                for i in range(self.ui.squid_brain_window.tabs.count()):
                    if self.ui.squid_brain_window.tabs.tabText(i) == "Decisions":
                        decisions_tab_index = i
                        break
                
                if decisions_tab_index >= 0:
                    self.ui.squid_brain_window.tabs.setCurrentIndex(decisions_tab_index)
        
        self.clear_tutorial_elements()
        
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        banner_height = 170
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset - 100
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(139, 69, 19, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(222, 184, 135, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        title_text = QtWidgets.QGraphicsTextItem("🤔")
        title_text.setDefaultTextColor(QtGui.QColor(222, 184, 135))
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step5_text"))
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        dismiss_button = QtWidgets.QPushButton(self.loc.get("next"))
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
        
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        self.start_auto_dismiss_timer(15000)
    
    def show_decorations_tutorial(self):
        """Show the sixth tutorial about decorations"""
        if hasattr(self.ui, 'decoration_window') and self.ui.decoration_window:
            self.main_window.position_and_show_decoration_window()
            if hasattr(self.ui, 'decorations_action'):
                self.ui.decorations_action.setChecked(True)
        
        if hasattr(self.ui, 'squid_brain_window') and self.ui.squid_brain_window:
            if hasattr(self.ui.squid_brain_window, 'tabs'):
                memory_tab_index = -1
                for i in range(self.ui.squid_brain_window.tabs.count()):
                    if self.ui.squid_brain_window.tabs.tabText(i) == "Memory":
                        memory_tab_index = i
                        break
                
                if memory_tab_index >= 0:
                    self.ui.squid_brain_window.tabs.setCurrentIndex(memory_tab_index)
        
        self.clear_tutorial_elements()
        
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        banner_height = 170
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset - 100
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(70, 130, 180, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(173, 216, 230, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        title_text = QtWidgets.QGraphicsTextItem("🌿 ")
        title_text.setDefaultTextColor(QtGui.QColor(173, 216, 230))
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step6_text"))
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        dismiss_button = QtWidgets.QPushButton(self.loc.get("next"))
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
        
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        self.start_auto_dismiss_timer(15000)
    
    def show_final_tutorial(self):
        """Show the final tutorial step with concluding message"""
        self.clear_tutorial_elements()
        
        win_width = self.ui.window_width
        win_height = self.ui.window_height
        
        banner_height = 170
        banner_y_offset = 40
        banner_y = win_height - banner_height - banner_y_offset - 100
        
        banner = QtWidgets.QGraphicsRectItem(0, banner_y, win_width, banner_height)
        banner.setBrush(QtGui.QColor(75, 0, 130, 230))
        banner.setPen(QtGui.QPen(QtGui.QColor(147, 112, 219, 150), 1))
        banner.setZValue(2000)
        setattr(banner, '_is_tutorial_element', True)
        self.ui.scene.addItem(banner)
        self.tutorial_elements.append(banner)
        
        title_font_size, body_font_size = self.get_tutorial_font_sizes(12, 11)
        
        title_text = QtWidgets.QGraphicsTextItem("✨")
        title_text.setDefaultTextColor(QtGui.QColor(147, 112, 219))
        title_text.setFont(QtGui.QFont("Arial", title_font_size, QtGui.QFont.Bold))
        title_text.setPos(20, banner_y + 10)
        title_text.setZValue(2001)
        setattr(title_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(title_text)
        self.tutorial_elements.append(title_text)
        
        info_text = QtWidgets.QGraphicsTextItem(self.loc.get("tutorial_step7_text"))
        info_text.setDefaultTextColor(QtGui.QColor(255, 255, 255))
        info_text.setFont(QtGui.QFont("Arial", body_font_size))
        info_text.setPos(20, banner_y + 35)
        info_text.setTextWidth(win_width - 150)
        info_text.setZValue(2001)
        setattr(info_text, '_is_tutorial_element', True)
        self.ui.scene.addItem(info_text)
        self.tutorial_elements.append(info_text)
        
        dismiss_button = QtWidgets.QPushButton(self.loc.get("finish"))
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
        
        dismiss_proxy = self.ui.scene.addWidget(dismiss_button)
        dismiss_proxy.setPos(win_width - 120, banner_y + 35)
        dismiss_proxy.setZValue(2002)
        setattr(dismiss_proxy, '_is_tutorial_element', True)
        self.tutorial_elements.append(dismiss_proxy)
        
        self.start_auto_dismiss_timer(15000)

    def check_brain_window_ready(self):
        if (hasattr(self.ui, 'squid_brain_window') and 
            self.ui.squid_brain_window and 
            hasattr(self.ui.squid_brain_window, 'tabs') and
            self.ui.squid_brain_window.tabs):
            self.show_second_tutorial()
        else:
            QtCore.QTimer.singleShot(500, self.check_brain_window_ready)
    
    def advance_to_next_step(self):
        logging.debug(f"Advancing to tutorial step {self.current_step + 1}")
        self.cancel_auto_dismiss_timer()
        self.clear_tutorial_example_neurons()
        self.clear_tutorial_elements()
        self.current_step += 1

        if self.current_step == 1:
            if not hasattr(self.ui, 'squid_brain_window') or not self.ui.squid_brain_window:
                logging.error("squid_brain_window not initialized or None")
                self.end_tutorial()
                return

            try:
                if not hasattr(self.ui.squid_brain_window, 'brain_widget') or not self.ui.squid_brain_window.brain_widget:
                    logging.error("squid_brain_window.brain_widget not initialized")
                    self.end_tutorial()
                    return

                logging.debug("Showing squid_brain_window")
                self.ui.squid_brain_window.show()
                if hasattr(self.ui, 'brain_action'):
                    self.ui.brain_action.setChecked(True)

                QtCore.QTimer.singleShot(1000, self.check_brain_window_ready)
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
        
        if (hasattr(self.ui, 'squid_brain_window') and 
            self.ui.squid_brain_window and 
            hasattr(self.ui.squid_brain_window, 'brain_widget') and
            self.ui.squid_brain_window.brain_widget):
            self.ui.squid_brain_window.brain_widget.is_tutorial_mode = False
            logging.debug("Tutorial mode disabled in brain widget")
    
    def start_auto_dismiss_timer(self, ms_duration):
        """Start a timer to automatically dismiss the current tutorial step"""
        self.cancel_auto_dismiss_timer()
        
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
        self.clear_tutorial_example_neurons()
        
        for item in self.tutorial_elements[:]:
            if item and item.scene():
                item.scene().removeItem(item)
        
        self.tutorial_elements = []
        self.ui.scene.update()

    def create_tutorial_example_neurons(self):
        """Create 3 temporary example neurons in the brain widget"""
        if not hasattr(self.ui, 'squid_brain_window') or not self.ui.squid_brain_window:
            return
        
        brain_widget = self.ui.squid_brain_window.brain_widget
        
        tutorial_positions = [(300, 200), (500, 350), (700, 250)]
        
        for i, (x, y) in enumerate(tutorial_positions):
            neuron_name = f'tutorial_neuron_{i+1}'
            
            brain_widget.neuron_positions[neuron_name] = (x, y)
            brain_widget.state[neuron_name] = 80
            brain_widget.state_colors[neuron_name] = (255, 255, 0)
            
            existing_neurons = [n for n in brain_widget.neuron_positions.keys() 
                            if not n.startswith('tutorial_')]
            if existing_neurons and len(existing_neurons) >= 2:
                targets = random.sample(existing_neurons, 2)
                for target in targets:
                    weight = random.uniform(0.5, 0.8)
                    brain_widget.weights[(neuron_name, target)] = weight
                    brain_widget.weights[(target, neuron_name)] = weight * 0.5
        
        brain_widget.update()

    def clear_tutorial_example_neurons(self):
        """Remove tutorial example neurons from brain widget"""
        if not hasattr(self.ui, 'squid_brain_window') or not self.ui.squid_brain_window:
            return
        
        if not hasattr(self.ui.squid_brain_window, 'brain_widget') or not self.ui.squid_brain_window.brain_widget:
            return
        
        brain_widget = self.ui.squid_brain_window.brain_widget
        
        tutorial_neurons = [n for n in list(brain_widget.neuron_positions.keys()) if n.startswith('tutorial_')]
        
        for neuron_name in tutorial_neurons:
            if neuron_name in brain_widget.neuron_positions:
                del brain_widget.neuron_positions[neuron_name]
            if neuron_name in brain_widget.state:
                del brain_widget.state[neuron_name]
            if hasattr(brain_widget, 'state_colors') and neuron_name in brain_widget.state_colors:
                del brain_widget.state_colors[neuron_name]
            
            keys_to_remove = [k for k in brain_widget.weights.keys() if neuron_name in k]
            for key in keys_to_remove:
                del brain_widget.weights[key]
        
        brain_widget.update()
