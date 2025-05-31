from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List
import logging
import base64 # Added import for base64

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
        """Initialize the pool
        
        Args:
            factory_func: Function to create new objects
            initial_size: Initial pool size
        """
        self.factory = factory_func
        self.available = []
        self.in_use = set()
        
        # Pre-populate pool
        for _ in range(initial_size):
            self.available.append(self.factory())
    
    def acquire(self):
        """Get an object from the pool or create a new one"""
        if self.available:
            obj = self.available.pop()
        else:
            obj = self.factory()
            
        self.in_use.add(obj)
        return obj
    
    def release(self, obj):
        """Return an object to the pool"""
        if obj in self.in_use:
            self.in_use.remove(obj)
            self.available.append(obj)
    
    def clear(self):
        """Clear all objects"""
        self.available.clear()
        self.in_use.clear()

class RemoteEntityManager:
    def __init__(self, scene, window_width, window_height, debug_mode=False, logger=None):
        self.scene = scene
        self.window_width = window_width
        self.window_height = window_height
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
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        self.remote_squids = {}
        self.remote_objects = {}
        self.connection_lines = {}
        
        self.remote_opacity = 0.7
        self.show_labels = True
        self.show_connections = True

        self.text_pool = ObjectPool(
            lambda: self.scene.addText(""), 
            initial_size=20
        )
    
    def update_settings(self, opacity=None, show_labels=None, show_connections=None):
        if opacity is not None:
            self.remote_opacity = opacity
            for squid_data in self.remote_squids.values():
                if 'visual' in squid_data and squid_data['visual']:
                    squid_data['visual'].setOpacity(opacity)
        
        if show_labels is not None:
            self.show_labels = show_labels
            for squid_data in self.remote_squids.values():
                if 'id_text' in squid_data:
                    squid_data['id_text'].setVisible(show_labels)
                if 'status_text' in squid_data:
                    squid_data['status_text'].setVisible(show_labels)
        
        if show_connections is not None:
            self.show_connections = show_connections
            for line in self.connection_lines.values():
                if line in self.scene.items():
                    line.setVisible(show_connections)
    
    def update_remote_squid(self, node_id, squid_data, is_new_arrival=False):
        if not squid_data or not all(k in squid_data for k in ['x', 'y']):
            if self.debug_mode: self.logger.warning(f"Insufficient data for remote squid {node_id}")
            return False
        
        if node_id in self.remote_squids:
            remote_squid_info = self.remote_squids[node_id] # Renamed for clarity
            remote_squid_info['visual'].setPos(squid_data['x'], squid_data['y'])
            
            if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                self.update_remote_view_cone(node_id, squid_data)
            else:
                if 'view_cone' in remote_squid_info and remote_squid_info['view_cone'] is not None and remote_squid_info['view_cone'] in self.scene.items():
                    self.scene.removeItem(remote_squid_info['view_cone'])
                    remote_squid_info['view_cone'] = None
                    
            if 'status_text' in remote_squid_info:
                status = "ENTERING" if is_new_arrival else squid_data.get('status', 'unknown')
                remote_squid_info['status_text'].setPlainText(f"{status}")
                remote_squid_info['status_text'].setPos(
                    squid_data['x'], 
                    squid_data['y'] - 30
                )
                if is_new_arrival:
                    remote_squid_info['status_text'].setDefaultTextColor(QtGui.QColor(255, 255, 0))
                    remote_squid_info['status_text'].setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        else:
            try:
                direction = squid_data.get('direction', 'right')
                # Ensure image name construction is robust, e.g., always includes an extension if needed
                squid_image_name = f"{direction}1.png" 
                image_path = os.path.join("images", squid_image_name) # Ensure "images" is correct base path
                if not os.path.exists(image_path):
                    if self.debug_mode: self.logger.error(f"Squid image not found: {image_path}. Using fallback.")
                    squid_pixmap = QtGui.QPixmap(60,40) # Placeholder size
                    squid_pixmap.fill(QtCore.Qt.gray)
                else:
                    squid_pixmap = QtGui.QPixmap(image_path)

                remote_visual = QtWidgets.QGraphicsPixmapItem(squid_pixmap)
                remote_visual.setPos(squid_data['x'], squid_data['y'])
                remote_visual.setZValue(5 if is_new_arrival else -1) # Higher Z for new arrivals
                remote_visual.setOpacity(self.remote_opacity)
                
                id_text = self.scene.addText(f"Remote Squid ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                id_text.setPos(squid_data['x'], squid_data['y'] - 45)
                id_text.setScale(0.8)
                id_text.setZValue(5 if is_new_arrival else -1)
                id_text.setVisible(self.show_labels)
                
                status_text = self.scene.addText("ENTERING" if is_new_arrival else squid_data.get('status', 'unknown'))
                if is_new_arrival:
                    status_text.setDefaultTextColor(QtGui.QColor(255, 255, 0)) # Bright color for new arrivals
                    status_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                else:
                    status_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                status_text.setPos(squid_data['x'], squid_data['y'] - 30)
                status_text.setScale(0.7)
                status_text.setZValue(5 if is_new_arrival else -1)
                status_text.setVisible(self.show_labels)
                
                self.scene.addItem(remote_visual)
                # id_text and status_text are already added by self.scene.addText
                
                self.remote_squids[node_id] = {
                    'visual': remote_visual,
                    'id_text': id_text,
                    'status_text': status_text,
                    'view_cone': None,
                    'last_update': time.time(),
                    'data': squid_data # Store the full squid_data
                }
                
                if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                    self.update_remote_view_cone(node_id, squid_data)
                    
                if is_new_arrival:
                    self._create_arrival_animation(remote_visual) 
            
            except Exception as e:
                self.logger.error(f"Error creating remote squid {node_id}: {e}", exc_info=True)
                return False
        
        # Process current_animation_frame if present
        # This section is for DECODING the frame data. Applying it visually would require
        # the remote_squid_info['visual'] to be a more complex object with an animation manager.
        if node_id in self.remote_squids and 'current_animation_frame' in squid_data:
            animation_frame_b64 = squid_data['current_animation_frame']
            if animation_frame_b64: # Check if it's not None or empty
                try:
                    decoded_frame_bytes = base64.b64decode(animation_frame_b64)
                    if self.debug_mode:
                        self.logger.debug(f"Decoded animation frame for {node_id}, bytes length: {len(decoded_frame_bytes)}")
                    
                    # TODO: Apply these bytes to the remote squid's animation.
                    # This currently isn't directly possible as remote_squids[node_id]['visual']
                    # is typically a QGraphicsPixmapItem and doesn't have an 'animation_manager'
                    # or a 'set_current_frame_from_bytes' method.
                    # To enable this, remote_squids would need to store references to objects
                    # (e.g., simplified local Squid instances or specialized remote Squid visual classes)
                    # that can process and display these animation frame bytes.
                    # For example:
                    # if hasattr(remote_squid_info.get('animation_handler'), 'set_current_frame_from_bytes'):
                    #    remote_squid_info['animation_handler'].set_current_frame_from_bytes(decoded_frame_bytes)

                except Exception as e:
                    # Log an error if decoding fails (e.g., not valid Base64)
                    if self.debug_mode:
                        self.logger.error(f"Error decoding base64 animation frame for {node_id}: {e}. Data (first 30 chars): {str(animation_frame_b64)[:30]}...")


        if node_id in self.remote_squids:
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'] = squid_data # Ensure the latest full data is stored
        
        return True
    
    def update_remote_view_cone(self, node_id, squid_data):
        if node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"Node {node_id} not in remote_squids for view cone update.")
            return
        
        remote_squid_info = self.remote_squids[node_id]
        
        # Remove existing view cone if it exists to prevent duplicates
        if 'view_cone' in remote_squid_info and remote_squid_info['view_cone'] is not None and remote_squid_info['view_cone'] in self.scene.items():
            self.scene.removeItem(remote_squid_info['view_cone'])
            remote_squid_info['view_cone'] = None # Important to clear the reference
        
        # Get view cone parameters using .get for safety
        squid_x = squid_data.get('x',0) 
        squid_y = squid_data.get('y',0)
        
        visual_item = remote_squid_info.get('visual')
        if visual_item: # Ensure visual_item exists
            squid_width = visual_item.boundingRect().width()
            squid_height = visual_item.boundingRect().height()
        else: # Fallback if visual somehow not set (should not happen if update_remote_squid ran correctly)
            squid_width = 60 
            squid_height = 40

        squid_center_x = squid_x + squid_width / 2
        squid_center_y = squid_y + squid_height / 2
        
        looking_direction = squid_data.get('looking_direction', 0) # Assuming radians
        view_cone_angle = squid_data.get('view_cone_angle', math.radians(60)) # Assuming radians, default 60 degrees
        
        cone_length = 150 # Fixed length for now, could be dynamic from squid_data
        
        # Define points for the cone polygon
        cone_points = [
            QtCore.QPointF(squid_center_x, squid_center_y), # Apex at squid center
            QtCore.QPointF( # Point 1 of cone base
                squid_center_x + math.cos(looking_direction - view_cone_angle/2) * cone_length,
                squid_center_y + math.sin(looking_direction - view_cone_angle/2) * cone_length
            ),
            QtCore.QPointF( # Point 2 of cone base
                squid_center_x + math.cos(looking_direction + view_cone_angle/2) * cone_length,
                squid_center_y + math.sin(looking_direction + view_cone_angle/2) * cone_length
            )
        ]
        
        cone_polygon = QtGui.QPolygonF(cone_points)
        view_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        
        # Use color from squid_data if available, otherwise default
        color_tuple = squid_data.get('color', (150, 150, 255)) # Default color for view cone
        try:
            q_color = QtGui.QColor(*color_tuple) # Ensure color_tuple is valid (e.g., (R,G,B))
        except TypeError: # Fallback if color_tuple is malformed
            q_color = QtGui.QColor(150,150,255) 
            if self.debug_mode: self.logger.warning(f"Invalid color tuple {color_tuple} for view cone. Using default.")

        view_cone_item.setPen(QtGui.QPen(q_color, 0.5)) # Pen for border
        view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 30))) # Semi-transparent fill
        
        # Place view cone behind the squid visual if visual_item exists
        view_cone_item.setZValue(visual_item.zValue() -1 if visual_item else -2)
        
        self.scene.addItem(view_cone_item)
        remote_squid_info['view_cone'] = view_cone_item # Store reference
    
    def _create_arrival_animation(self, visual_item):
        # Check if visual_item supports 'scale_factor' property (i.e., is AnimatableGraphicsItem)
        is_animatable = hasattr(visual_item, 'scale_factor')

        if is_animatable:
            scale_prop_name = b"scale_factor"
        else:
            # Standard QGraphicsItem has a 'scale' property (qreal).
            # QPropertyAnimation should work with 'scale' on QGraphicsItem.
            scale_prop_name = b"scale"


        scale_animation = QtCore.QPropertyAnimation(visual_item, scale_prop_name)
        scale_animation.setDuration(500) # milliseconds
        scale_animation.setStartValue(1.5) # Start slightly larger
        scale_animation.setEndValue(1.0)   # End at normal scale
        scale_animation.setEasingCurve(QtCore.QEasingCurve.OutBounce) # Nice bouncy effect
        
        # Opacity animation for fade-in effect
        opacity_effect = QtWidgets.QGraphicsOpacityEffect(visual_item) # Apply to visual_item itself
        visual_item.setGraphicsEffect(opacity_effect)
        opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        opacity_animation.setDuration(500) # milliseconds
        opacity_animation.setStartValue(0.5) # Start semi-transparent
        # Respect current opacity if it's already set (e.g. if it was 0 due to being hidden)
        opacity_animation.setEndValue(self.remote_opacity if visual_item.opacity() > 0 else 0) 
        
        # Group animations to run in parallel
        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(scale_animation)
        animation_group.addAnimation(opacity_animation)
        
        # Start animation and delete when finished
        animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
    
    def _reset_remote_squid_style(self, visual_item_or_node_id):
        """Reset visual style of remote squid after entry period or for normal state."""
        node_id = None
        squid_display_data = None

        if isinstance(visual_item_or_node_id, str): # it's a node_id
            node_id = visual_item_or_node_id
            squid_display_data = self.remote_squids.get(node_id)
        elif isinstance(visual_item_or_node_id, QtWidgets.QGraphicsPixmapItem): # it's the visual item
            # Find which node_id this visual_item belongs to
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
        id_text_item = squid_display_data.get('id_text')

        if visual_item:
            visual_item.setZValue(-1) # Default Z order
            visual_item.setOpacity(self.remote_opacity)
            # Remove any special graphics effect like a highlight if one was added for arrival
            # Example check for specific effects; adapt if using others
            if isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsDropShadowEffect) or \
               isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsColorizeEffect) : 
                 visual_item.setGraphicsEffect(None)


        if status_text_item:
            # Only reset if not in a special state like "ENTERING" or "ARRIVING"
            # Assumes squid_display_data['data'] holds the actual data payload from network
            current_status = squid_display_data.get('data',{}).get('status','visiting').upper()
            if current_status not in ["ENTERING", "ARRIVING"]: # Avoid overwriting temporary arrival status
                 status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200)) # Default color
                 status_text_item.setFont(QtGui.QFont("Arial", 10)) # Or your default font
                 status_text_item.setPlainText(squid_display_data.get('data',{}).get('status','visiting'))
            # Ensure ZValue is appropriate relative to the visual item
            status_text_item.setZValue(visual_item.zValue() + 1 if visual_item else 0)


        if id_text_item:
            id_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 180)) # Slightly dimmer/transparent
            id_text_item.setFont(QtGui.QFont("Arial", 8)) # Smaller font
            id_text_item.setZValue(visual_item.zValue() + 1 if visual_item else 0)
    
    def update_connection_lines(self, local_squid_pos_tuple):
        """Update the visual lines connecting to remote squids"""
        if not self.show_connections:
            # If lines are hidden, ensure all existing lines are also hidden or removed
            for node_id, line in list(self.connection_lines.items()): # Iterate over a copy for safe removal
                if line in self.scene.items():
                    self.scene.removeItem(line)
                del self.connection_lines[node_id] # Remove from tracking
            return
        
        if not local_squid_pos_tuple or len(local_squid_pos_tuple) != 2:
            if self.debug_mode: self.logger.warning("Invalid local_squid_pos for connection lines.")
            return

        local_center_x, local_center_y = local_squid_pos_tuple
        
        active_lines_for_nodes = set() # Track nodes that should have lines
        for node_id, squid_data in self.remote_squids.items():
            if 'visual' not in squid_data or not squid_data['visual'].isVisible():
                continue # Skip if no visual or not visible
                
            active_lines_for_nodes.add(node_id)
            remote_visual = squid_data['visual']
            remote_pos = remote_visual.pos()
            # Approximate center based on common squid dimensions if boundingRect is problematic
            remote_center_x = remote_pos.x() + remote_visual.boundingRect().width() / 2
            remote_center_y = remote_pos.y() + remote_visual.boundingRect().height() / 2
            
            # Use color from squid_data if available, otherwise default
            color_tuple = squid_data.get('data', {}).get('color', (100, 100, 255)) # Default line color
            try:
                q_color = QtGui.QColor(*color_tuple)
            except TypeError: # Fallback if color_tuple is malformed
                q_color = QtGui.QColor(100,100,255)


            if node_id in self.connection_lines:
                line = self.connection_lines[node_id]
                if line not in self.scene.items(): # Re-add if removed for some reason
                    self.scene.addItem(line)
                line.setLine(local_center_x, local_center_y, remote_center_x, remote_center_y)
                # Update pen color if it can change dynamically
                line.pen().setColor(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 100)) # Semi-transparent
                line.setVisible(True) # Ensure visible if show_connections is true
            else:
                line = QtWidgets.QGraphicsLineItem(
                    local_center_x, local_center_y, remote_center_x, remote_center_y
                )
                pen = QtGui.QPen(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 100)) # Semi-transparent
                pen.setWidth(1) # Thinner lines
                pen.setStyle(QtCore.Qt.SolidLine) # Solid lines might be clearer than dashed for connections
                line.setPen(pen)
                line.setZValue(-10) # Well behind other items
                line.setVisible(True) # Ensure visible on creation if show_connections is true
                self.scene.addItem(line)
                self.connection_lines[node_id] = line
        
        # Remove lines for squids that are no longer present or active
        for node_id in list(self.connection_lines.keys()): # Iterate over a copy for safe removal
            if node_id not in active_lines_for_nodes:
                line_to_remove = self.connection_lines.pop(node_id)
                if line_to_remove in self.scene.items():
                    self.scene.removeItem(line_to_remove)

    def remove_remote_squid(self, node_id):
        """Remove a remote squid and all its components"""
        if node_id not in self.remote_squids:
            return # Nothing to remove
        
        squid_data_to_remove = self.remote_squids.pop(node_id) # Use pop to get and remove
        
        # Remove visual components from scene
        for key in ['visual', 'view_cone', 'id_text', 'status_text']:
            item = squid_data_to_remove.get(key)
            if item is not None and item in self.scene.items(): # Check if item is still in scene
                self.scene.removeItem(item)
        
        # Remove associated connection line
        if node_id in self.connection_lines:
            line = self.connection_lines.pop(node_id)
            if line in self.scene.items():
                self.scene.removeItem(line)
        if self.debug_mode: self.logger.debug(f"Removed remote squid {node_id}")
    
    def cleanup_stale_entities(self, timeout=20.0): # Increased timeout slightly
        """Remove entities that haven't been updated recently"""
        current_time = time.time()
        
        stale_squids_ids = [
            node_id for node_id, data in self.remote_squids.items()
            if current_time - data.get('last_update', 0) > timeout # Check 'last_update' key
        ]
        for node_id in stale_squids_ids:
            if self.debug_mode: self.logger.info(f"Cleaning up stale squid: {node_id}")
            self.remove_remote_squid(node_id)
        
        # Assuming remote_objects have a similar 'last_update' field if they exist
        stale_objects_ids = [
            obj_id for obj_id, data in self.remote_objects.items()
            if current_time - data.get('last_update', 0) > timeout
        ]
        for obj_id in stale_objects_ids:
            if self.debug_mode: self.logger.info(f"Cleaning up stale object: {obj_id}")
            self.remove_remote_object(obj_id) # remove_remote_object needs to be defined
        
        if stale_squids_ids or stale_objects_ids:
             if self.debug_mode: self.logger.debug(f"Cleanup: Removed {len(stale_squids_ids)} squids, {len(stale_objects_ids)} objects.")
        return len(stale_squids_ids), len(stale_objects_ids)
    
    def remove_remote_object(self, obj_id): # Definition was missing in original snippet, adding basic one
        """Remove a remote object"""
        if obj_id not in self.remote_objects:
            return
        
        obj_data = self.remote_objects.pop(obj_id) # Get and remove
        
        visual_item = obj_data.get('visual')
        if visual_item and visual_item in self.scene.items(): # Check if in scene
            self.scene.removeItem(visual_item)
            
        label_item = obj_data.get('label') # If objects have labels
        if label_item and label_item in self.scene.items(): # Check if in scene
            self.scene.removeItem(label_item)
        if self.debug_mode: self.logger.debug(f"Removed remote object {obj_id}")
    
    def cleanup_all(self):
        """Remove all remote entities managed by this instance."""
        # Remove all squids
        for node_id in list(self.remote_squids.keys()): # Iterate over a copy
            self.remove_remote_squid(node_id)
        self.remote_squids.clear() # Should be empty now, but clear just in case
            
        # Remove all objects
        for obj_id in list(self.remote_objects.keys()): # Iterate over a copy
            self.remove_remote_object(obj_id)
        self.remote_objects.clear() # Should be empty

        # Connection lines are removed by remove_remote_squid, but clear dict
        for node_id in list(self.connection_lines.keys()): 
            line = self.connection_lines.pop(node_id)
            if line in self.scene.items():
                self.scene.removeItem(line)
        self.connection_lines.clear()


        # Clear object pools if they hold QGraphicsItems added to the scene
        if hasattr(self, 'text_pool'):
             # Proper cleanup of a pool of QGraphicsItems would involve
             # removing each item from the scene before clearing the pool's internal lists.
             for item in self.text_pool.available:
                 if item in self.scene.items(): self.scene.removeItem(item)
             for item in self.text_pool.in_use: # Should be empty if all released before cleanup_all
                 if item in self.scene.items(): self.scene.removeItem(item)
             self.text_pool.clear()


        if self.debug_mode: self.logger.info("RemoteEntityManager cleaned up all entities.")