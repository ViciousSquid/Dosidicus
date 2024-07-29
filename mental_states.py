from PyQt5 import QtCore, QtGui, QtWidgets
import os

class MentalState:
    def __init__(self, name, icon_filename):
        self.name = name
        self.icon_filename = icon_filename
        self.is_active = False
        self.icon_item = None

class MentalStateManager:
    def __init__(self, squid, scene):
        self.squid = squid
        self.scene = scene
        self.icon_offset = QtCore.QPointF(0, -100)  # Offset for all icons above the squid
        self.mental_states_enabled = True  

        self.mental_states = {                                      #   List of possible mental states:
            "sick": MentalState("sick", "sick.png"),                #   SICK
            "thinking": MentalState("thinking", "think.png"),       #   THINKING
            "startled": MentalState("startled", "startled.png"),    #   STARTLED
            "curious": MentalState("curious", "curious.png")        #   CURIOUS
        }

    def set_mental_states_enabled(self, enabled):
        self.mental_states_enabled = enabled
        if not enabled:
            self.clear_optional_states()

    def set_state(self, state_name, is_active):
        if state_name in self.mental_states:
            if state_name == "sick" or self.mental_states_enabled:
                self.mental_states[state_name].is_active = is_active
                self.update_mental_state_icons()

    def update_mental_state_icons(self):
        for state in self.mental_states.values():
            if state.name == "sick" or self.mental_states_enabled:
                self.update_icon_state(state)

    def update_icon_state(self, state):
        if state.is_active:
            if state.icon_item is None:
                icon_pixmap = QtGui.QPixmap(os.path.join("images", state.icon_filename))
                state.icon_item = QtWidgets.QGraphicsPixmapItem(icon_pixmap)
                self.scene.addItem(state.icon_item)
            self.update_icon_position(state.icon_item)
        else:
            if state.icon_item is not None:
                self.scene.removeItem(state.icon_item)
                state.icon_item = None

    def update_icon_position(self, icon_item):
        icon_item.setPos(self.squid.squid_x + self.squid.squid_width // 2 - icon_item.pixmap().width() // 2 + self.icon_offset.x(),
                         self.squid.squid_y + self.icon_offset.y())

    def update_positions(self):
        self.update_mental_state_icons()

    def is_state_active(self, state_name):
        if state_name == "sick" or self.mental_states_enabled:
            return self.mental_states.get(state_name, MentalState(state_name, "")).is_active
        return False

    def clear_optional_states(self):
        for state in self.mental_states.values():
            if state.name != "sick":
                if state.icon_item is not None:
                    self.scene.removeItem(state.icon_item)
                    state.icon_item = None
                state.is_active = False