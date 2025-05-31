# plugins/multiplayer/remote_entity_manager.py

from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List, Union, Tuple
import logging
import base64
import json # For pretty printing in logs

class AnimatableGraphicsItem(QtCore.QObject, QtWidgets.QGraphicsPixmapItem):
    """Graphics item that can be animated with QPropertyAnimation"""
    
    def __init__(self, pixmap=None, parent=None):
        QtCore.QObject.__init__(self)
        QtWidgets.QGraphicsPixmapItem.__init__(self, pixmap, parent)
        self._scale = 1.0
        
    @QtCore.pyqtProperty(float)
    def scale_factor(self):
        return self._scale
        
    @scale_factor.setter
    def scale_factor(self, value):
        self._scale = value
        self.setScale(value)

class ObjectPool:
    """Pool for reusing graphical objects to reduce allocation overhead"""
    
    def __init__(self, factory_func, initial_size=10):
        self.factory = factory_func
        self.available = []
        self.in_use = set()
        for _ in range(initial_size):
            self.available.append(self.factory())
    
    def acquire(self):
        if self.available:
            obj = self.available.pop()
        else:
            obj = self.factory()
        self.in_use.add(obj)
        return obj
    
    def release(self, obj):
        if obj in self.in_use:
            self.in_use.remove(obj)
            self.available.append(obj)
        # Optional: Reset object state here if needed
        if isinstance(obj, QtWidgets.QGraphicsTextItem):
            obj.setPlainText("") # Clear text
            obj.setDefaultTextColor(QtGui.QColor("black")) # Reset color
            obj.setFont(QtGui.QFont()) # Reset font
            obj.setScale(1.0) # Reset scale
            if obj.scene(): # Remove from scene if pooled
                obj.scene().removeItem(obj)

    def clear(self):
        all_items = self.available + list(self.in_use)
        for item in all_items:
            if isinstance(item, QtWidgets.QGraphicsItem) and item.scene():
                item.scene().removeItem(item)
        self.available.clear()
        self.in_use.clear()

class RemoteEntityManager:
    def __init__(self, scene: QtWidgets.QGraphicsScene, window_width: int, window_height: int, tamagotchi_logic: Any = None, debug_mode: bool = False, logger: Optional[logging.Logger] = None):
        self.scene = scene
        self.window_width = window_width
        self.window_height = window_height
        self.tamagotchi_logic = tamagotchi_logic # Store if needed, e.g. for UI access
        self.debug_mode = debug_mode

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__ + ".RemoteEntityManager")
            if not self.logger.hasHandlers(): 
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO) # Default to INFO, override if needed
        if self.debug_mode:
             self.logger.setLevel(logging.DEBUG)
        
        self.remote_squids: Dict[str, Dict[str, Any]] = {}
        self.remote_objects: Dict[str, Dict[str, Any]] = {} # Assuming similar structure if used
        self.connection_lines: Dict[str, QtWidgets.QGraphicsLineItem] = {}
        self._last_calculated_entry_details: Dict[str, Dict[str, Any]] = {}
        
        self.remote_opacity: float = 0.7
        self.show_labels: bool = True
        self.show_connections: bool = True

        self.text_pool = ObjectPool(
            lambda: QtWidgets.QGraphicsTextItem(None), # Parent is None initially
            initial_size=20
        )

    def calculate_entry_position(self, exit_data: dict) -> tuple[float, float, str]:
        """
        Calculates the entry position for a remote squid on the current instance's screen,
        based on how it exited the other instance.
        """
        if self.debug_mode: self.logger.debug(f"REM_DEBUG: calculate_entry_position called with exit_data: {json.dumps(exit_data, default=str)}")
        
        original_exit_direction = exit_data.get('direction')
        original_exit_pos_x = float(exit_data.get('position', {}).get('x', 0))
        original_exit_pos_y = float(exit_data.get('position', {}).get('y', 0))
        
        squid_width = float(exit_data.get('squid_width', 50))
        squid_height = float(exit_data.get('squid_height', 50))

        current_window_width = float(self.window_width)
        current_window_height = float(self.window_height)

        entry_x = 0.0
        entry_y = 0.0
        entry_direction_on_this_screen = "unknown" # Direction squid appears to be coming FROM on this screen

        if original_exit_direction == 'right':
            entry_x = -squid_width * 0.8  # Start mostly off-screen to the left
            entry_y = original_exit_pos_y
            entry_direction_on_this_screen = "left" 
        elif original_exit_direction == 'left':
            entry_x = current_window_width - squid_width * 0.2 # Start mostly off-screen to the right
            entry_y = original_exit_pos_y
            entry_direction_on_this_screen = "right"
        elif original_exit_direction == 'down': # Exited towards increasing Y
            entry_y = -squid_height * 0.8 # Start mostly off-screen at the top
            entry_x = original_exit_pos_x
            entry_direction_on_this_screen = "top"
        elif original_exit_direction == 'up': # Exited towards decreasing Y
            entry_y = current_window_height - squid_height * 0.2 # Start mostly off-screen at the bottom
            entry_x = original_exit_pos_x
            entry_direction_on_this_screen = "bottom"
        else:
            self.logger.warning(f"REM_DEBUG: Unknown original_exit_direction: '{original_exit_direction}'. Placing in center as fallback.")
            entry_x = current_window_width / 2 - squid_width / 2
            entry_y = current_window_height / 2 - squid_height / 2
            entry_direction_on_this_screen = "center_fallback"

        # Clamp entry_y/x to be within screen bounds (respecting squid height/width)
        if original_exit_direction in ['right', 'left']: # Horizontal exit/entry
            entry_y = max(0.0, min(entry_y, current_window_height - squid_height))
        if original_exit_direction in ['up', 'down']: # Vertical exit/entry
            entry_x = max(0.0, min(entry_x, current_window_width - squid_width))
        
        if self.debug_mode:
            self.logger.debug(f"REM_DEBUG: Calculated entry: original_exit_dir='{original_exit_direction}' (from {original_exit_pos_x:.2f},{original_exit_pos_y:.2f})"
                              f" -> entry_pos=({entry_x:.2f}, {entry_y:.2f}) on this screen (size {current_window_width}x{current_window_height}), "
                              f"squid_size=({squid_width},{squid_height}), entry_side_on_this_screen='{entry_direction_on_this_screen}'")
        
        node_id = exit_data.get('node_id')
        if node_id:
            self._last_calculated_entry_details[node_id] = {
                'entry_pos': (entry_x, entry_y),
                'entry_direction': entry_direction_on_this_screen 
            }
        return entry_x, entry_y, entry_direction_on_this_screen

    def get_last_calculated_entry_details(self, node_id: str) -> Optional[Dict[str, Any]]:
        return self._last_calculated_entry_details.get(node_id)

    # In plugins/multiplayer/remote_entity_manager.py
# (within the RemoteEntityManager class)

    def update_remote_squid(self, node_id: str, squid_data_payload: Dict[str, Any], is_new_arrival: bool = False) -> Union[QtWidgets.QGraphicsPixmapItem, bool, None]:
        """
        Creates or updates a remote squid's visual representation and data.
        """
        if self.debug_mode:
            try:
                payload_type_info = squid_data_payload.get('type', 'UnknownType') if isinstance(squid_data_payload, dict) else 'NonDictPayload'
                log_payload = json.dumps(squid_data_payload, indent=2, default=str) 
            except Exception:
                log_payload = str(squid_data_payload)
            self.logger.info(f"REM_DEBUG_ENTRY: update_remote_squid CALLED for node {node_id}. is_new_arrival_arg={is_new_arrival}. Payload type: {payload_type_info}. Payload snapshot: {log_payload[:500]}...")

        if not squid_data_payload or not isinstance(squid_data_payload, dict):
            if self.debug_mode: self.logger.warning(f"REM_DEBUG: update_remote_squid called for {node_id} with invalid or no data payload. Payload: {squid_data_payload}")
            return False

        is_creating_new_squid = (node_id not in self.remote_squids) or is_new_arrival
        
        if self.debug_mode:
            self.logger.info(f"REM_DEBUG_CONDITION: For node {node_id}: (node_id not in self.remote_squids) is {(node_id not in self.remote_squids)}. is_new_arrival_arg is {is_new_arrival}. SO, is_creating_new_squid = {is_creating_new_squid}")
            if node_id in self.remote_squids:
                self.logger.info(f"REM_DEBUG_DETAIL: Node {node_id} IS currently in self.remote_squids. Keys: {list(self.remote_squids.keys())}")
            else:
                self.logger.info(f"REM_DEBUG_DETAIL: Node {node_id} IS NOT currently in self.remote_squids.")

        if is_creating_new_squid:
            # ----- NEW SQUID CREATION -----
            if self.debug_mode: self.logger.info(f"REM_DEBUG: Block for Creating NEW remote squid for node_id: {node_id}. Full incoming payload (exit_data): {json.dumps(squid_data_payload, indent=2, default=str)}")
            
            remote_visual = None 
            id_text = None
            status_text = None
            try:
                entry_x, entry_y, entry_direction_on_this_screen = self.calculate_entry_position(squid_data_payload)
                if self.debug_mode: self.logger.info(f"REM_DEBUG: For new squid {node_id}, calculated entry_pos: ({entry_x:.2f}, {entry_y:.2f}), entry_direction_on_this_screen: '{entry_direction_on_this_screen}'")

                image_facing_direction = "right" 
                if entry_direction_on_this_screen == "left": image_facing_direction = "right"
                elif entry_direction_on_this_screen == "right": image_facing_direction = "left"
                elif entry_direction_on_this_screen == "top": image_facing_direction = "down"
                elif entry_direction_on_this_screen == "bottom": image_facing_direction = "up"
                
                squid_image_name = f"{image_facing_direction}1.png"
                
                # --- REVISED IMAGE PATH LOGIC ---
                # Assumes 'images' folder is directly inside the same directory as this file (plugins/multiplayer/images/)
                current_file_dir = os.path.dirname(os.path.abspath(__file__))
                image_path = os.path.join(current_file_dir, "images", squid_image_name)
                # --- END OF REVISED IMAGE PATH LOGIC ---

                if self.debug_mode: self.logger.info(f"REM_DEBUG: New squid {node_id} - Attempting to load image from path: {image_path}")

                squid_width_from_payload = int(squid_data_payload.get('squid_width', 60))
                squid_height_from_payload = int(squid_data_payload.get('squid_height', 40))

                if not os.path.exists(image_path):
                    if self.debug_mode: self.logger.error(f"REM_DEBUG_ERROR: Squid image NOT FOUND at: {image_path}. Using fallback placeholder for {node_id}.")
                    squid_pixmap = QtGui.QPixmap(squid_width_from_payload, squid_height_from_payload)
                    squid_pixmap.fill(QtCore.Qt.darkRed) 
                else:
                    squid_pixmap = QtGui.QPixmap(image_path)
                    if squid_width_from_payload > 0 and squid_height_from_payload > 0:
                        squid_pixmap = squid_pixmap.scaled(squid_width_from_payload, squid_height_from_payload, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    if self.debug_mode: self.logger.info(f"REM_DEBUG: Squid image {image_path} loaded successfully for {node_id}. Loaded Size: {squid_pixmap.width()}x{squid_pixmap.height()}")

                remote_visual = AnimatableGraphicsItem(squid_pixmap)
                remote_visual.setPos(entry_x, entry_y)
                remote_visual.setZValue(5) 
                remote_visual.setOpacity(0.0) 
                
                if self.debug_mode: self.logger.info(f"REM_DEBUG: New squid {node_id} - Visual item created, initial pos: ({remote_visual.pos().x():.2f}, {remote_visual.pos().y():.2f})")

                id_text = self.text_pool.acquire()
                if id_text.scene() != self.scene:
                    if id_text.scene(): id_text.scene().removeItem(id_text)
                    self.scene.addItem(id_text)
                id_text.setPlainText(f"Remote ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                id_text.setPos(entry_x, entry_y - 45) 
                id_text.setScale(0.8)
                id_text.setZValue(6) 
                id_text.setVisible(self.show_labels)

                status_text = self.text_pool.acquire()
                if status_text.scene() != self.scene:
                    if status_text.scene(): status_text.scene().removeItem(status_text)
                    self.scene.addItem(status_text)
                status_text.setPlainText("ENTERING...") 
                status_text.setDefaultTextColor(QtGui.QColor(255, 255, 0)) 
                status_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                status_text.setPos(entry_x, entry_y - 30) 
                status_text.setScale(0.7)
                status_text.setZValue(6)
                status_text.setVisible(self.show_labels)
                
                self.scene.addItem(remote_visual) 
                if self.debug_mode: self.logger.info(f"REM_DEBUG: New squid {node_id} - Visual item and text items ADDED TO SCENE.")
                
                self.remote_squids[node_id] = {
                    'visual': remote_visual, 'id_text': id_text, 'status_text': status_text,
                    'view_cone': None, 'last_update': time.time(), 'data': squid_data_payload,
                    'was_arrival_text': True
                }
                
                if squid_data_payload.get('view_cone_visible', False):
                    view_cone_data_at_entry = squid_data_payload.copy()
                    view_cone_data_at_entry['x'] = entry_x 
                    view_cone_data_at_entry['y'] = entry_y
                    self.update_remote_view_cone(node_id, view_cone_data_at_entry)
                
                self._create_arrival_animation(remote_visual)
                if self.debug_mode: self.logger.info(f"REM_DEBUG: Successfully created and initialized new remote squid {node_id}.")
                return remote_visual 
            
            except Exception as e:
                self.logger.error(f"REM_DEBUG_ERROR: Critical error during NEW remote squid {node_id} creation: {e}", exc_info=True)
                if remote_visual and remote_visual.scene(): self.scene.removeItem(remote_visual)
                if id_text:
                    if id_text.scene(): self.scene.removeItem(id_text)
                    self.text_pool.release(id_text) 
                if status_text:
                    if status_text.scene(): self.scene.removeItem(status_text)
                    self.text_pool.release(status_text)
                if node_id in self.remote_squids:
                    del self.remote_squids[node_id]
                return False
        
        else: # ----- EXISTING SQUID UPDATE -----
            if node_id not in self.remote_squids:
                if self.debug_mode: self.logger.warning(f"REM_DEBUG: update_remote_squid called for existing node {node_id} but not found in self.remote_squids.")
                return False

            if self.debug_mode: self.logger.info(f"REM_DEBUG: Updating EXISTING remote squid {node_id}. Payload: {json.dumps(squid_data_payload, default=str, indent=2)[:500]}...")

            remote_squid_info = self.remote_squids[node_id]
            visual_item = remote_squid_info.get('visual')

            if not visual_item:
                if self.debug_mode: self.logger.error(f"REM_DEBUG_ERROR: No visual item found for existing remote squid {node_id}. Cannot update.")
                return False

            current_x = squid_data_payload.get('x')
            current_y = squid_data_payload.get('y')

            if current_x is not None and current_y is not None:
                visual_item.setPos(current_x, current_y)
                if remote_squid_info.get('id_text'):
                    remote_squid_info['id_text'].setPos(current_x, current_y - 45)
                if remote_squid_info.get('status_text'):
                    remote_squid_info['status_text'].setPos(current_x, current_y - 30)
            elif self.debug_mode:
                 self.logger.warning(f"REM_DEBUG: Position data (x or y) missing for remote squid UPDATE {node_id}. Payload: {squid_data_payload}")

            if 'status_text' in remote_squid_info and remote_squid_info['status_text']:
                new_status = squid_data_payload.get('status', remote_squid_info.get('data',{}).get('status','visiting'))
                if remote_squid_info['status_text'].toPlainText() != new_status or remote_squid_info.get('was_arrival_text', False):
                    remote_squid_info['status_text'].setPlainText(f"{new_status}")
                    if remote_squid_info.get('was_arrival_text', False) and new_status.upper() != "ENTERING...": 
                        remote_squid_info['status_text'].setDefaultTextColor(QtGui.QColor(200, 200, 200))
                        remote_squid_info['status_text'].setFont(QtGui.QFont("Arial", 10))
                        remote_squid_info['was_arrival_text'] = False

            if squid_data_payload.get('view_cone_visible', False):
                view_cone_payload = squid_data_payload.copy()
                if 'x' not in view_cone_payload and current_x is not None: view_cone_payload['x'] = current_x
                if 'y' not in view_cone_payload and current_y is not None: view_cone_payload['y'] = current_y
                self.update_remote_view_cone(node_id, view_cone_payload)
            elif 'view_cone' in remote_squid_info and remote_squid_info['view_cone'] is not None:
                 if remote_squid_info['view_cone'].scene(): 
                    self.scene.removeItem(remote_squid_info['view_cone'])
                 remote_squid_info['view_cone'] = None
            
            new_image_key = squid_data_payload.get('image_direction_key')
            new_frame_index_str = squid_data_payload.get('current_animation_frame')
            
            if new_image_key: 
                if self.debug_mode:
                    self.logger.debug(f"REM_DEBUG: Animation update for {node_id}: key='{new_image_key}', frame_data='{new_frame_index_str}'. (Visual update logic TBD)")

            remote_squid_info['last_update'] = time.time()
            for key, value in squid_data_payload.items():
                remote_squid_info['data'][key] = value
            return True 
        
        if self.debug_mode: self.logger.error(f"REM_DEBUG_ERROR: update_remote_squid for {node_id} reached end without explicit return in main branches. This is a logic error.")
        return False

    def update_settings(self, opacity=None, show_labels=None, show_connections=None):
        if opacity is not None:
            self.remote_opacity = opacity
            for squid_data in self.remote_squids.values():
                if 'visual' in squid_data and squid_data['visual']:
                    squid_data['visual'].setOpacity(opacity)
        
        if show_labels is not None:
            self.show_labels = show_labels
            for squid_data in self.remote_squids.values():
                if 'id_text' in squid_data and squid_data['id_text']:
                    squid_data['id_text'].setVisible(show_labels)
                if 'status_text' in squid_data and squid_data['status_text']:
                    squid_data['status_text'].setVisible(show_labels)
        
        if show_connections is not None:
            self.show_connections = show_connections
            for line in self.connection_lines.values():
                if line.scene(): # Check if it's in a scene
                    line.setVisible(show_connections)

    def update_remote_view_cone(self, node_id: str, squid_data: Dict[str, Any]):
        if node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"REM_DEBUG: Node {node_id} not in remote_squids for view cone update.")
            return
        
        remote_squid_info = self.remote_squids[node_id]
        visual_item = remote_squid_info.get('visual')
        if not visual_item: 
            if self.debug_mode: self.logger.warning(f"REM_DEBUG: No visual item for {node_id} to draw view cone.")
            return

        if 'view_cone' in remote_squid_info and remote_squid_info['view_cone'] is not None:
            if remote_squid_info['view_cone'].scene():
                self.scene.removeItem(remote_squid_info['view_cone'])
            remote_squid_info['view_cone'] = None
        
        # Use current position from visual_item for cone origin, not potentially stale squid_data['x'/'y']
        # if the cone update is for an existing, moving squid.
        # If it's a new squid, squid_data['x'/'y'] would be the entry_x/y.
        squid_current_pos_x = squid_data.get('x', visual_item.pos().x())
        squid_current_pos_y = squid_data.get('y', visual_item.pos().y())
        
        squid_width = visual_item.boundingRect().width()
        squid_height = visual_item.boundingRect().height()

        squid_center_x = squid_current_pos_x + squid_width / 2
        squid_center_y = squid_current_pos_y + squid_height / 2
        
        looking_direction = float(squid_data.get('looking_direction', 0.0)) # Radians
        view_cone_angle = float(squid_data.get('view_cone_angle', math.radians(60.0))) # Radians
        cone_length = float(squid_data.get('view_cone_length', 150.0))
        
        cone_points = [
            QtCore.QPointF(squid_center_x, squid_center_y),
            QtCore.QPointF(squid_center_x + math.cos(looking_direction - view_cone_angle/2) * cone_length,
                           squid_center_y + math.sin(looking_direction - view_cone_angle/2) * cone_length),
            QtCore.QPointF(squid_center_x + math.cos(looking_direction + view_cone_angle/2) * cone_length,
                           squid_center_y + math.sin(looking_direction + view_cone_angle/2) * cone_length)
        ]
        
        cone_polygon = QtGui.QPolygonF(cone_points)
        view_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        
        color_tuple = squid_data.get('color', (150, 150, 255)) 
        try:
            q_color = QtGui.QColor(*color_tuple) 
        except TypeError: 
            q_color = QtGui.QColor(150,150,255) 
            if self.debug_mode: self.logger.warning(f"REM_DEBUG: Invalid color tuple {color_tuple} for view cone. Using default.")

        view_cone_item.setPen(QtGui.QPen(q_color, 0.5)) 
        view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 30)))
        view_cone_item.setZValue(visual_item.zValue() -1) 
        
        self.scene.addItem(view_cone_item)
        remote_squid_info['view_cone'] = view_cone_item
    
    def _create_arrival_animation(self, visual_item: QtWidgets.QGraphicsPixmapItem):
        if not isinstance(visual_item, AnimatableGraphicsItem) : 
             if self.debug_mode: self.logger.warning("REM_DEBUG: Arrival animation skipped: visual_item is not AnimatableGraphicsItem. Setting opacity directly.")
             visual_item.setOpacity(self.remote_opacity) 
             return

        # --- TEMPORARY TEST ---
        # Force immediate full visibility to rule out animation issues
        print(f"REM_DEBUG_ANIM: Forcing full opacity on {visual_item} before animation start.")
        visual_item.setOpacity(1.0) 
        visual_item.setScale(1.0) # Also ensure normal scale initially
        # --- END TEMPORARY TEST ---

        # Scale animation
        scale_animation = QtCore.QPropertyAnimation(visual_item, b"scale_factor")
        scale_animation.setDuration(700) 
        scale_animation.setStartValue(1.6) 
        scale_animation.setEndValue(1.0)   
        scale_animation.setEasingCurve(QtCore.QEasingCurve.OutElastic) 
        
        opacity_effect = visual_item.graphicsEffect()
        if not isinstance(opacity_effect, QtWidgets.QGraphicsOpacityEffect):
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(visual_item) 
            visual_item.setGraphicsEffect(opacity_effect)
        
        opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        opacity_animation.setDuration(500) 
        opacity_animation.setStartValue(0.0) # Animation still starts from 0
        opacity_animation.setEndValue(self.remote_opacity) 
        
        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(scale_animation)
        animation_group.addAnimation(opacity_animation)
        # To see if the item is there before animation, you might comment out animation_group.start() for a test
        # animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        # print(f"REM_DEBUG_ANIM: Arrival animation started for {visual_item}.") # Optional: Log animation start

    def _reset_remote_squid_style(self, visual_item_or_node_id: Union[str, QtWidgets.QGraphicsPixmapItem]):
        # ... (This method seems okay, ensure it uses self.logger if debug_mode is active) ...
        # For brevity, keeping as is from your provided file.
        node_id = None
        squid_display_data = None

        if isinstance(visual_item_or_node_id, str): 
            node_id = visual_item_or_node_id
            squid_display_data = self.remote_squids.get(node_id)
        elif isinstance(visual_item_or_node_id, QtWidgets.QGraphicsPixmapItem): 
            for nid, s_data in self.remote_squids.items():
                if s_data.get('visual') == visual_item_or_node_id:
                    node_id = nid
                    squid_display_data = s_data
                    break
        
        if not squid_display_data:
            if self.debug_mode: self.logger.debug(f"REM_DEBUG: Could not find squid data for style reset: {visual_item_or_node_id}")
            return

        visual_item = squid_display_data.get('visual')
        status_text_item = squid_display_data.get('status_text')

        if visual_item:
            visual_item.setZValue(-1) 
            visual_item.setOpacity(self.remote_opacity)
            # Only remove graphics effect if it's an opacity effect used for animation,
            # or if you want to clear all effects.
            # if isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsOpacityEffect):
            # visual_item.setGraphicsEffect(None)


        if status_text_item:
            current_status = squid_display_data.get('data',{}).get('status','visiting').upper()
            if squid_display_data.get('was_arrival_text', False) and current_status not in ["ENTERING...", "ARRIVING"]: # Check original case
                 status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200)) 
                 status_text_item.setFont(QtGui.QFont("Arial", 10)) 
                 status_text_item.setPlainText(squid_display_data.get('data',{}).get('status','visiting'))
                 squid_display_data['was_arrival_text'] = False
            if visual_item : status_text_item.setZValue(visual_item.zValue() + 1)


    def update_connection_lines(self, local_squid_pos_tuple: Optional[Tuple[float, float]]):
        # ... (This method seems okay, ensure it uses self.logger if debug_mode is active) ...
        # For brevity, keeping as is from your provided file.
        if not self.show_connections:
            for node_id, line in list(self.connection_lines.items()): 
                if line.scene(): self.scene.removeItem(line) # Check if in scene
                del self.connection_lines[node_id] 
            return
        
        if not local_squid_pos_tuple or len(local_squid_pos_tuple) != 2:
            if self.debug_mode: self.logger.warning("REM_DEBUG: Invalid local_squid_pos for connection lines.")
            return

        local_center_x, local_center_y = local_squid_pos_tuple
        active_lines_for_nodes = set() 

        for node_id, squid_info in self.remote_squids.items(): 
            visual_item = squid_info.get('visual') 
            if not visual_item or not visual_item.isVisible():
                continue 
                
            active_lines_for_nodes.add(node_id)
            remote_pos = visual_item.pos()
            remote_center_x = remote_pos.x() + visual_item.boundingRect().width() / 2
            remote_center_y = remote_pos.y() + visual_item.boundingRect().height() / 2
            
            color_tuple = squid_info.get('data', {}).get('color', (100, 100, 255))
            try:
                q_color = QtGui.QColor(*color_tuple)
            except TypeError: 
                q_color = QtGui.QColor(100,100,255)

            if node_id in self.connection_lines:
                line = self.connection_lines[node_id]
                if not line.scene(): self.scene.addItem(line) # Re-add if removed
                line.setLine(local_center_x, local_center_y, remote_center_x, remote_center_y)
                new_pen = line.pen()
                new_pen.setColor(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 100))
                line.setPen(new_pen)
                line.setVisible(True) 
            else:
                line = QtWidgets.QGraphicsLineItem(local_center_x, local_center_y, remote_center_x, remote_center_y)
                pen = QtGui.QPen(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 100)) 
                pen.setWidth(1) 
                pen.setStyle(QtCore.Qt.SolidLine) 
                line.setPen(pen)
                line.setZValue(-10) 
                line.setVisible(True) 
                self.scene.addItem(line)
                self.connection_lines[node_id] = line
        
        for node_id in list(self.connection_lines.keys()): 
            if node_id not in active_lines_for_nodes:
                line_to_remove = self.connection_lines.pop(node_id)
                if line_to_remove.scene(): # Check if in scene
                    self.scene.removeItem(line_to_remove)

    def remove_remote_squid(self, node_id: str):
        if node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"REM_DEBUG: Attempted to remove non-existent remote squid {node_id}.")
            return 
        
        squid_data_to_remove = self.remote_squids.pop(node_id)
        
        for key in ['visual', 'view_cone', 'id_text', 'status_text']:
            item = squid_data_to_remove.get(key)
            if item is not None:
                if item.scene(): 
                    self.scene.removeItem(item)
                if hasattr(self, 'text_pool') and key in ['id_text', 'status_text']:
                    try:
                        self.text_pool.release(item) 
                    except ValueError: # Item might not be in in_use set if error occurred during creation
                         if self.debug_mode: self.logger.warning(f"REM_DEBUG: Item {key} for {node_id} not in text_pool's 'in_use' set during release.")
                         pass


        if node_id in self.connection_lines:
            line = self.connection_lines.pop(node_id)
            if line.scene():
                self.scene.removeItem(line)
        if self.debug_mode: self.logger.info(f"REM_DEBUG: Removed remote squid {node_id}")
    
    def cleanup_stale_entities(self, timeout: float = 20.0):
        current_time = time.time()
        stale_squids_ids = [
            node_id for node_id, data in self.remote_squids.items()
            if current_time - data.get('last_update', 0) > timeout
        ]
        for node_id in stale_squids_ids:
            if self.debug_mode: self.logger.info(f"REM_DEBUG: Cleaning up stale squid: {node_id}")
            self.remove_remote_squid(node_id)
        
        # Assuming remote_objects have a similar 'last_update' field
        stale_objects_ids = [
            obj_id for obj_id, data in self.remote_objects.items() # Ensure self.remote_objects exists
            if current_time - data.get('last_update', 0) > timeout
        ]
        for obj_id in stale_objects_ids:
            if self.debug_mode: self.logger.info(f"REM_DEBUG: Cleaning up stale object: {obj_id}")
            self.remove_remote_object(obj_id) 
        
        if stale_squids_ids or stale_objects_ids:
             if self.debug_mode: self.logger.debug(f"REM_DEBUG: Cleanup: Removed {len(stale_squids_ids)} squids, {len(stale_objects_ids)} objects.")
        return len(stale_squids_ids), len(stale_objects_ids)
    
    def remove_remote_object(self, obj_id: str): 
        if obj_id not in self.remote_objects:
            return
        obj_data = self.remote_objects.pop(obj_id)
        visual_item = obj_data.get('visual')
        if visual_item and visual_item.scene(): 
            self.scene.removeItem(visual_item)
        label_item = obj_data.get('label') 
        if label_item and label_item.scene(): 
            self.scene.removeItem(label_item)
        if self.debug_mode: self.logger.debug(f"REM_DEBUG: Removed remote object {obj_id}")
    
    def cleanup_all(self):
        for node_id in list(self.remote_squids.keys()): 
            self.remove_remote_squid(node_id)
        self.remote_squids.clear()
            
        for obj_id in list(self.remote_objects.keys()): 
            self.remove_remote_object(obj_id)
        self.remote_objects.clear()

        for node_id in list(self.connection_lines.keys()): 
            line = self.connection_lines.pop(node_id)
            if line.scene():
                self.scene.removeItem(line)
        self.connection_lines.clear()

        if hasattr(self, 'text_pool'):
             self.text_pool.clear() # ObjectPool.clear() now handles removing from scene

        if self.debug_mode: self.logger.info("REM_DEBUG: RemoteEntityManager cleaned up all entities.")

    # Helper method to get remote squid instance, used by mp_plugin_logic
    def get_remote_squid_instance_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Returns the internal data dictionary for a remote squid, which includes its visual item."""
        return self.remote_squids.get(node_id)