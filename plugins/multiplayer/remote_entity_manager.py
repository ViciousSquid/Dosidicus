from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List # Ensure List is imported if used for type hinting
import logging
import base64

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
    
    def clear(self):
        # Proper cleanup for QGraphicsItems in a pool would involve
        # ensuring they are removed from the scene if they were added.
        # This basic clear just empties lists.
        for item in self.available:
            if isinstance(item, QtWidgets.QGraphicsItem) and item.scene():
                item.scene().removeItem(item)
        for item in self.in_use:
            if isinstance(item, QtWidgets.QGraphicsItem) and item.scene():
                item.scene().removeItem(item)
        self.available.clear()
        self.in_use.clear()

class RemoteEntityManager:
    def __init__(self, scene, window_width, window_height, debug_mode=False, logger=None): # Added tamagotchi_logic
        self.scene = scene
        self.window_width = window_width # Current instance's window width
        self.window_height = window_height # Current instance's window height
        self.debug_mode = debug_mode
        # self.tamagotchi_logic = tamagotchi_logic # Store if needed for other things

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__ + ".RemoteEntityManager")
            if not self.logger.hasHandlers(): 
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        self.remote_squids = {}
        self.remote_objects = {}
        self.connection_lines = {}
        self._last_calculated_entry_details = {} # To store entry details for autopilot
        
        self.remote_opacity = 1.0 # Changed from 0.7 for full visibility
        self.show_labels = True
        self.show_connections = True

        # Assuming a simple text factory for the pool
        self.text_pool = ObjectPool(
            lambda: QtWidgets.QGraphicsTextItem(""), # Use QGraphicsTextItem for better control
            initial_size=20
        )
        # Ensure pooled text items are not parented or added to scene by factory
        # They will be added/removed explicitly when acquired/released.

    def calculate_entry_position(self, exit_data: dict) -> tuple[float, float, str]:
        """
        Calculates the entry position for a remote squid on the current instance's screen,
        based on how it exited the other instance.

        Args:
            exit_data: The payload from the 'squid_exit' message.
                       Contains 'direction' (of exit), 'position' (x,y of exit),
                       'squid_width', 'squid_height'.

        Returns:
            A tuple (entry_x, entry_y, entry_direction_on_this_screen).
        """
        original_exit_direction = exit_data.get('direction')
        original_exit_pos_x = exit_data.get('position', {}).get('x', 0)
        original_exit_pos_y = exit_data.get('position', {}).get('y', 0)
        
        squid_width = exit_data.get('squid_width', 50)
        squid_height = exit_data.get('squid_height', 50)

        # Use current instance's window dimensions stored during __init__
        current_window_width = self.window_width
        current_window_height = self.window_height

        entry_x = 0.0
        entry_y = 0.0
        entry_direction_on_this_screen = "unknown"

        if original_exit_direction == 'right':
            entry_x = -squid_width * 0.8  # Start mostly off-screen to the left
            entry_y = original_exit_pos_y
            entry_direction_on_this_screen = "left" # It's entering from this screen's left
        elif original_exit_direction == 'left':
            entry_x = current_window_width - squid_width * 0.2 # Start mostly off-screen to the right
            entry_y = original_exit_pos_y
            entry_direction_on_this_screen = "right"
        elif original_exit_direction == 'down':
            entry_y = -squid_height * 0.8 # Start mostly off-screen at the top
            entry_x = original_exit_pos_x
            entry_direction_on_this_screen = "top"
        elif original_exit_direction == 'up':
            entry_y = current_window_height - squid_height * 0.2 # Start mostly off-screen at the bottom
            entry_x = original_exit_pos_x
            entry_direction_on_this_screen = "bottom"
        else:
            self.logger.warning(f"Unknown original_exit_direction: {original_exit_direction}. Placing in center.")
            entry_x = current_window_width / 2 - squid_width / 2
            entry_y = current_window_height / 2 - squid_height / 2
            entry_direction_on_this_screen = "center_fallback"

        # Clamp entry_y to be within screen bounds (respecting squid height)
        # Useful if original_exit_pos_y is from a screen of different height
        if original_exit_direction in ['right', 'left']: # Horizontal exit/entry
            entry_y = max(0, min(entry_y, current_window_height - squid_height))
        
        # Clamp entry_x similarly for vertical exits/entries
        if original_exit_direction in ['up', 'down']: # Vertical exit/entry
            entry_x = max(0, min(entry_x, current_window_width - squid_width))
        
        if self.debug_mode:
            self.logger.debug(f"Calculated entry: original_exit_dir={original_exit_direction} (from {original_exit_pos_x},{original_exit_pos_y})"
                              f" -> entry_pos=({entry_x:.2f}, {entry_y:.2f}) on this screen (size {current_window_width}x{current_window_height}), "
                              f"squid_size=({squid_width},{squid_height}), entry_side='{entry_direction_on_this_screen}'")
        
        # Store for potential use by autopilot's initial movement
        node_id = exit_data.get('node_id')
        if node_id:
            self._last_calculated_entry_details[node_id] = {
                'entry_pos': (entry_x, entry_y),
                'entry_direction': entry_direction_on_this_screen 
            }
        return entry_x, entry_y, entry_direction_on_this_screen

    def get_last_calculated_entry_details(self, node_id: str) -> dict | None:
        return self._last_calculated_entry_details.get(node_id)

    def update_settings(self, opacity=None, show_labels=None, show_connections=None):
        if opacity is not None:
            # For testing static image, we'll force opacity to 1.0 if not specified otherwise
            self.remote_opacity = opacity 
        # Ensure all squids adhere to the new static full opacity if opacity is not being set by this call
        # Or, if it IS being set, ensure they adopt it.
        current_target_opacity = opacity if opacity is not None else self.remote_opacity # self.remote_opacity is 1.0 now

        for squid_data in self.remote_squids.values():
            if 'visual' in squid_data and squid_data['visual']:
                squid_data['visual'].setOpacity(current_target_opacity) # Use the determined opacity
        
        if show_labels is not None:
            self.show_labels = show_labels
            for squid_data in self.remote_squids.values():
                if 'id_text' in squid_data and squid_data['id_text']: # check not None
                    squid_data['id_text'].setVisible(show_labels)
                if 'status_text' in squid_data and squid_data['status_text']: # check not None
                    squid_data['status_text'].setVisible(show_labels)
        
        if show_connections is not None:
            self.show_connections = show_connections
            for line in self.connection_lines.values():
                if line in self.scene.items(): # Check if still in scene
                    line.setVisible(show_connections)
    
    def update_remote_squid(self, node_id, squid_data_payload, is_new_arrival=False): # squid_data_payload is the exit_data or update_data
        if not squid_data_payload:
            if self.debug_mode: self.logger.warning(f"No data provided for remote squid {node_id}")
            return False

        current_x = squid_data_payload.get('x')
        current_y = squid_data_payload.get('y')

        if current_x is None or current_y is None: # For updates, x and y must be present
             if not (is_new_arrival or node_id not in self.remote_squids): # if it's not a new arrival, x,y are mandatory
                if self.debug_mode: self.logger.warning(f"Insufficient position data for remote squid update {node_id}")
                return False

        if node_id in self.remote_squids: # Existing squid: Update position and other attributes
            remote_squid_info = self.remote_squids[node_id]
            visual_item = remote_squid_info['visual']
            visual_item.setPos(current_x, current_y) # Update with current x, y from payload
            visual_item.setOpacity(self.remote_opacity) # Ensure full opacity
            
            new_status = squid_data_payload.get('status', remote_squid_info.get('data',{}).get('status','visiting'))
            if 'status_text' in remote_squid_info and remote_squid_info['status_text']:
                remote_squid_info['status_text'].setPlainText(f"{new_status}")
                remote_squid_info['status_text'].setPos(current_x, current_y - 30) 
                if remote_squid_info.get('was_arrival_text', False):
                    remote_squid_info['status_text'].setDefaultTextColor(QtGui.QColor(200, 200, 200))
                    remote_squid_info['status_text'].setFont(QtGui.QFont("Arial", 10)) 
                    remote_squid_info['was_arrival_text'] = False


            if 'view_cone_visible' in squid_data_payload and squid_data_payload['view_cone_visible']:
                self.update_remote_view_cone(node_id, squid_data_payload)
            elif 'view_cone' in remote_squid_info and remote_squid_info['view_cone'] is not None:
                 if remote_squid_info['view_cone'] in self.scene.items(): 
                    self.scene.removeItem(remote_squid_info['view_cone'])
                 remote_squid_info['view_cone'] = None
            
            if 'id_text' in remote_squid_info and remote_squid_info['id_text']:
                remote_squid_info['id_text'].setPos(current_x, current_y - 45) 

        else: # New squid: Create it using calculated entry position
            try:
                entry_x, entry_y, entry_direction = self.calculate_entry_position(squid_data_payload)
                is_new_arrival = True 

                squid_image_direction = squid_data_payload.get('direction', 'right') 
                image_facing_direction = squid_image_direction
                if entry_direction == "left": image_facing_direction = "right"
                elif entry_direction == "right": image_facing_direction = "left"
                elif entry_direction == "top": image_facing_direction = "down"
                elif entry_direction == "bottom": image_facing_direction = "up"


                squid_image_name = f"{image_facing_direction}1.png" 
                image_path = os.path.join("images", squid_image_name)
                
                if not os.path.exists(image_path):
                    if self.debug_mode: self.logger.error(f"Squid image not found: {image_path}. Using fallback.")
                    squid_pixmap = QtGui.QPixmap(int(squid_data_payload.get('squid_width', 60)), int(squid_data_payload.get('squid_height', 40)))
                    squid_pixmap.fill(QtCore.Qt.gray)
                else:
                    squid_pixmap = QtGui.QPixmap(image_path)
                    squid_width = squid_data_payload.get('squid_width')
                    squid_height = squid_data_payload.get('squid_height')
                    if squid_width and squid_height:
                        squid_pixmap = squid_pixmap.scaled(int(squid_width), int(squid_height), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

                remote_visual = AnimatableGraphicsItem(squid_pixmap) # Still use Animatable for scale property if needed elsewhere
                remote_visual.setPos(entry_x, entry_y) 
                remote_visual.setZValue(5) 
                remote_visual.setOpacity(self.remote_opacity) # MODIFIED: Set to full opacity (or self.remote_opacity which is 1.0)
                remote_visual.setScale(1.0) # Ensure scale is normal
                
                id_text = self.text_pool.acquire()
                if id_text.scene() != self.scene : 
                    if id_text.scene(): id_text.scene().removeItem(id_text) 
                    self.scene.addItem(id_text)
                id_text.setPlainText(f"Remote ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                id_text.setPos(entry_x, entry_y - 45) 
                id_text.setScale(0.8)
                id_text.setZValue(6) 
                id_text.setVisible(self.show_labels)
                
                status_text = self.text_pool.acquire()
                if status_text.scene() != self.scene :
                    if status_text.scene(): status_text.scene().removeItem(status_text)
                    self.scene.addItem(status_text)

                status_text.setPlainText("ENTERING") # Or "VISIBLE"
                status_text.setDefaultTextColor(QtGui.QColor(255, 255, 0)) 
                status_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                status_text.setPos(entry_x, entry_y - 30) 
                status_text.setScale(0.7)
                status_text.setZValue(6)
                status_text.setVisible(self.show_labels)
                
                self.scene.addItem(remote_visual)
                
                self.remote_squids[node_id] = {
                    'visual': remote_visual,
                    'id_text': id_text,
                    'status_text': status_text,
                    'view_cone': None,
                    'last_update': time.time(),
                    'data': squid_data_payload, 
                    'was_arrival_text': True 
                }
                
                if 'view_cone_visible' in squid_data_payload and squid_data_payload['view_cone_visible']:
                    view_cone_data_at_entry = squid_data_payload.copy()
                    view_cone_data_at_entry['x'] = entry_x
                    view_cone_data_at_entry['y'] = entry_y
                    self.update_remote_view_cone(node_id, view_cone_data_at_entry)
                    
                # MODIFIED: Comment out arrival animation call
                # if is_new_arrival: 
                #     self._create_arrival_animation(remote_visual) 
            
            except Exception as e:
                self.logger.error(f"Error creating remote squid {node_id}: {e}", exc_info=True)
                if node_id in self.remote_squids:
                    items_to_check = ['visual', 'id_text', 'status_text']
                    for key_item_name in items_to_check:
                        item_to_remove = self.remote_squids[node_id].get(key_item_name)
                        if item_to_remove and item_to_remove.scene():
                            item_to_remove.scene().removeItem(item_to_remove)
                            if hasattr(self, 'text_pool') and key_item_name in ['id_text', 'status_text']:
                                self.text_pool.release(item_to_remove) 
                    del self.remote_squids[node_id]
                return False
        
        # MODIFIED: Comment out animation frame processing
        # Common update logic for both new and existing squids
        # if node_id in self.remote_squids:
        #     # Animation frame processing (ensure it uses the latest squid_data_payload)
        #     if 'current_animation_frame' in squid_data_payload:
        #         animation_frame_b64 = squid_data_payload['current_animation_frame']
        #         if animation_frame_b64:
        #             try:
        #                 # This part remains a TODO for actual visual update of animation frames
        #                 decoded_frame_bytes = base64.b64decode(animation_frame_b64)
        #                 # self.logger.debug(f"Decoded animation frame for {node_id}, len: {len(decoded_frame_bytes)}")
        #                 # Visual application of frame would go here if 'visual' item supports it
        #                 current_visual = self.remote_squids[node_id]['visual']
        #                 # Example: if hasattr(current_visual, 'set_pixmap_from_bytes'): current_visual.set_pixmap_from_bytes(decoded_frame_bytes)
        #                 # Or if you have a list of pixmaps:
        #                 # frame_index = squid_data_payload.get('frame_index', 0) # assuming frame_index is sent
        #                 # direction_key = squid_data_payload.get('image_direction_key', 'left') # assuming direction is sent
        #                 # if hasattr(self, 'image_cache') and direction_key in self.image_cache:
        #                 #    current_visual.setPixmap(self.image_cache[direction_key][frame_index % len(self.image_cache[direction_key])])
        #
        #             except Exception as e:
        #                 if self.debug_mode:
        #                     self.logger.error(f"Error decoding/applying animation frame for {node_id}: {e}. Data: {str(animation_frame_b64)[:30]}")
            
        if node_id in self.remote_squids: # Ensure this runs if the above animation block is commented
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'].update(squid_data_payload) 
        
        return True

    def update_remote_view_cone(self, node_id, squid_data): # squid_data here has x,y of the squid's current position
        if node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"Node {node_id} not in remote_squids for view cone update.")
            return
        
        remote_squid_info = self.remote_squids[node_id]
        visual_item = remote_squid_info.get('visual')
        if not visual_item: 
            if self.debug_mode: self.logger.warning(f"No visual item for {node_id} to draw view cone.")
            return

        if 'view_cone' in remote_squid_info and remote_squid_info['view_cone'] is not None:
            if remote_squid_info['view_cone'] in self.scene.items():
                self.scene.removeItem(remote_squid_info['view_cone'])
            remote_squid_info['view_cone'] = None
        
        squid_current_pos_x = visual_item.pos().x() 
        squid_current_pos_y = visual_item.pos().y()
        
        squid_width = visual_item.boundingRect().width()
        squid_height = visual_item.boundingRect().height()

        squid_center_x = squid_current_pos_x + squid_width / 2
        squid_center_y = squid_current_pos_y + squid_height / 2
        
        looking_direction = squid_data.get('looking_direction', 0) 
        view_cone_angle = squid_data.get('view_cone_angle', math.radians(60))
        cone_length = squid_data.get('view_cone_length', 150) 
        
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
            if self.debug_mode: self.logger.warning(f"Invalid color tuple {color_tuple} for view cone. Using default.")

        view_cone_item.setPen(QtGui.QPen(q_color, 0.5)) 
        view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 30)))
        view_cone_item.setZValue(visual_item.zValue() -1) 
        
        self.scene.addItem(view_cone_item)
        remote_squid_info['view_cone'] = view_cone_item
    
    def _create_arrival_animation(self, visual_item):
        # MODIFIED: Simplify to just make visible and set scale, no animation
        if not isinstance(visual_item, AnimatableGraphicsItem) : # Though AnimatableGraphicsItem might not be strictly needed now
             self.logger.warning("Arrival animation skipped: visual_item is not AnimatableGraphicsItem.")
             visual_item.setOpacity(self.remote_opacity) # Ensure it's visible
             visual_item.setScale(1.0) # Ensure normal scale
             return

        visual_item.setOpacity(self.remote_opacity) # Make fully visible
        visual_item.setScale(1.0) # Set scale to normal

        # Remove any existing graphics effect if it was for opacity animation
        if visual_item.graphicsEffect() and isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsOpacityEffect):
            visual_item.setGraphicsEffect(None)


        # The original animation code is now effectively bypassed:
        # scale_animation = QtCore.QPropertyAnimation(visual_item, b"scale_factor") 
        # scale_animation.setDuration(500)
        # scale_animation.setStartValue(1.5) 
        # scale_animation.setEndValue(1.0)   
        # scale_animation.setEasingCurve(QtCore.QEasingCurve.OutBounce) 
        # 
        # opacity_effect = QtWidgets.QGraphicsOpacityEffect(visual_item.parentItem()) 
        # visual_item.setGraphicsEffect(opacity_effect) 
        # opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity") 
        # opacity_animation.setDuration(500) 
        # opacity_animation.setStartValue(0.0) 
        # opacity_animation.setEndValue(self.remote_opacity) 
        # 
        # animation_group = QtCore.QParallelAnimationGroup()
        # animation_group.addAnimation(scale_animation)
        # animation_group.addAnimation(opacity_animation)
        # animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
    
    def _reset_remote_squid_style(self, visual_item_or_node_id):
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
            if self.debug_mode: self.logger.debug(f"Could not find squid data for reset: {visual_item_or_node_id}")
            return

        visual_item = squid_display_data.get('visual')
        status_text_item = squid_display_data.get('status_text')

        if visual_item:
            visual_item.setZValue(5) # Original ZValue for squids
            visual_item.setOpacity(self.remote_opacity) # Ensure full visibility based on setting
            visual_item.setScale(1.0) # Ensure normal scale
            # Remove graphics effect if it was set for animation
            if visual_item.graphicsEffect() is not None:
                 visual_item.setGraphicsEffect(None)


        if status_text_item:
            current_status = squid_display_data.get('data',{}).get('status','visiting').upper()
            if squid_display_data.get('was_arrival_text', False) and current_status not in ["ENTERING", "ARRIVING"]:
                 status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200)) 
                 status_text_item.setFont(QtGui.QFont("Arial", 10)) 
                 status_text_item.setPlainText(squid_display_data.get('data',{}).get('status','visiting'))
                 squid_display_data['was_arrival_text'] = False 
            status_text_item.setZValue(visual_item.zValue() + 1 if visual_item else 6) # Above squid

    def update_connection_lines(self, local_squid_pos_tuple):
        if not self.show_connections:
            for node_id, line in list(self.connection_lines.items()): 
                if line in self.scene.items(): self.scene.removeItem(line)
                del self.connection_lines[node_id] 
            return
        
        if not local_squid_pos_tuple or len(local_squid_pos_tuple) != 2:
            if self.debug_mode: self.logger.warning("Invalid local_squid_pos for connection lines.")
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
                if line not in self.scene.items(): self.scene.addItem(line)
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
                if line_to_remove in self.scene.items():
                    self.scene.removeItem(line_to_remove)

    def remove_remote_squid(self, node_id):
        if node_id not in self.remote_squids:
            return 
        
        squid_data_to_remove = self.remote_squids.pop(node_id)
        
        for key in ['visual', 'view_cone', 'id_text', 'status_text']:
            item = squid_data_to_remove.get(key)
            if item is not None:
                if item.scene() and item in item.scene().items():  # Check scene before removing
                    item.scene().removeItem(item)
                if hasattr(self, 'text_pool') and key in ['id_text', 'status_text']:
                    self.text_pool.release(item) 

        if node_id in self.connection_lines:
            line = self.connection_lines.pop(node_id)
            if line.scene() and line in line.scene().items(): # Check scene
                line.scene().removeItem(line)
        if self.debug_mode: self.logger.debug(f"Removed remote squid {node_id}")
    
    def cleanup_stale_entities(self, timeout=20.0):
        current_time = time.time()
        stale_squids_ids = [
            node_id for node_id, data in self.remote_squids.items()
            if current_time - data.get('last_update', 0) > timeout
        ]
        for node_id in stale_squids_ids:
            if self.debug_mode: self.logger.info(f"Cleaning up stale squid: {node_id}")
            self.remove_remote_squid(node_id)
        
        stale_objects_ids = [
            obj_id for obj_id, data in self.remote_objects.items()
            if current_time - data.get('last_update', 0) > timeout
        ]
        for obj_id in stale_objects_ids:
            if self.debug_mode: self.logger.info(f"Cleaning up stale object: {obj_id}")
            self.remove_remote_object(obj_id)
        
        if stale_squids_ids or stale_objects_ids:
             if self.debug_mode: self.logger.debug(f"Cleanup: Removed {len(stale_squids_ids)} squids, {len(stale_objects_ids)} objects.")
        return len(stale_squids_ids), len(stale_objects_ids)
    
    def remove_remote_object(self, obj_id):
        if obj_id not in self.remote_objects:
            return
        obj_data = self.remote_objects.pop(obj_id)
        visual_item = obj_data.get('visual')
        if visual_item and visual_item.scene() and visual_item in visual_item.scene().items(): 
            visual_item.scene().removeItem(visual_item)
        label_item = obj_data.get('label') 
        if label_item and label_item.scene() and label_item in label_item.scene().items(): 
            label_item.scene().removeItem(label_item)
        if self.debug_mode: self.logger.debug(f"Removed remote object {obj_id}")
    
    def cleanup_all(self):
        for node_id in list(self.remote_squids.keys()): 
            self.remove_remote_squid(node_id)
        self.remote_squids.clear()
            
        for obj_id in list(self.remote_objects.keys()): 
            self.remove_remote_object(obj_id)
        self.remote_objects.clear()

        for node_id in list(self.connection_lines.keys()): 
            line = self.connection_lines.pop(node_id)
            if line.scene() and line in line.scene().items():
                line.scene().removeItem(line)
        self.connection_lines.clear()

        if hasattr(self, 'text_pool'):
             all_pooled_items = self.text_pool.available + list(self.text_pool.in_use)
             for item in all_pooled_items:
                 if item.scene(): 
                     item.scene().removeItem(item)
             self.text_pool.clear() 
        if self.debug_mode: self.logger.info("RemoteEntityManager cleaned up all entities.")