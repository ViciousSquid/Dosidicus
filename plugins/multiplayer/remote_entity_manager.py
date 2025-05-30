from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List
import logging # Added import for logging

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
    def __init__(self, scene, window_width, window_height, debug_mode=False, logger=None): # MODIFIED: Added logger parameter
        self.scene = scene
        self.window_width = window_width
        self.window_height = window_height
        self.debug_mode = debug_mode

        # MODIFIED: Use provided logger or create a default one
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__ + ".RemoteEntityManager")
            if not self.logger.hasHandlers(): # Basic configuration for default logger
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        # Storage for remote entities
        self.remote_squids = {}
        self.remote_objects = {}
        self.connection_lines = {}
        
        # Visual settings
        self.remote_opacity = 0.7
        self.show_labels = True
        self.show_connections = True

        # text_pool initialization (retained from previous fix)
        self.text_pool = ObjectPool(
            lambda: self.scene.addText(""), 
            initial_size=20
        )
    
    def update_settings(self, opacity=None, show_labels=None, show_connections=None):
        """Update visual settings"""
        if opacity is not None:
            self.remote_opacity = opacity
            # Update existing squids
            for squid_data in self.remote_squids.values():
                if 'visual' in squid_data and squid_data['visual']:
                    squid_data['visual'].setOpacity(opacity)
        
        if show_labels is not None:
            self.show_labels = show_labels
            # Update visibility of labels
            for squid_data in self.remote_squids.values():
                if 'id_text' in squid_data:
                    squid_data['id_text'].setVisible(show_labels)
                if 'status_text' in squid_data:
                    squid_data['status_text'].setVisible(show_labels)
        
        if show_connections is not None:
            self.show_connections = show_connections
            # Update visibility of connection lines
            for line in self.connection_lines.values():
                if line in self.scene.items():
                    line.setVisible(show_connections)
    
    def update_remote_squid(self, node_id, squid_data, is_new_arrival=False):
        """Update or create a remote squid visualization"""
        if not squid_data or not all(k in squid_data for k in ['x', 'y']):
            # Use self.logger for logging
            if self.debug_mode: self.logger.warning(f"Insufficient data for remote squid {node_id}")
            return False
        
        # Check if we already have this remote squid
        if node_id in self.remote_squids:
            # Update existing squid
            remote_squid = self.remote_squids[node_id]
            remote_squid['visual'].setPos(squid_data['x'], squid_data['y'])
            
            # Update view cone if needed
            if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                self.update_remote_view_cone(node_id, squid_data)
            else:
                # Hide view cone if it exists
                if 'view_cone' in remote_squid and remote_squid['view_cone'] is not None and remote_squid['view_cone'] in self.scene.items():
                    self.scene.removeItem(remote_squid['view_cone'])
                    remote_squid['view_cone'] = None
                    
            
            # Update status text
            if 'status_text' in remote_squid:
                status = "ENTERING" if is_new_arrival else squid_data.get('status', 'unknown')
                remote_squid['status_text'].setPlainText(f"{status}")
                remote_squid['status_text'].setPos(
                    squid_data['x'], 
                    squid_data['y'] - 30
                )
                
                # Make text more visible for entering squids
                if is_new_arrival:
                    remote_squid['status_text'].setDefaultTextColor(QtGui.QColor(255, 255, 0))
                    remote_squid['status_text'].setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        else:
            # Create new remote squid representation
            try:
                # Load the appropriate squid image based on direction
                direction = squid_data.get('direction', 'right')
                squid_image = f"{direction}1.png" # Ensure this path logic is robust
                image_path = os.path.join("images", squid_image)
                if not os.path.exists(image_path):
                    # Fallback image or log error
                    if self.debug_mode: self.logger.error(f"Squid image not found: {image_path}. Using fallback.")
                    # Example: use a default pixmap or a placeholder
                    squid_pixmap = QtGui.QPixmap(60,40) # Placeholder size
                    squid_pixmap.fill(QtCore.Qt.gray)
                else:
                    squid_pixmap = QtGui.QPixmap(image_path)

                # Check if visual_item should be AnimatableGraphicsItem for animations
                # For now, using QGraphicsPixmapItem as per original structure in this part of file
                remote_visual = QtWidgets.QGraphicsPixmapItem(squid_pixmap)
                remote_visual.setPos(squid_data['x'], squid_data['y'])
                remote_visual.setZValue(5 if is_new_arrival else -1)
                remote_visual.setOpacity(self.remote_opacity)
                
                # Add ID text
                id_text = self.scene.addText(f"Remote Squid ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                id_text.setPos(squid_data['x'], squid_data['y'] - 45)
                id_text.setScale(0.8)
                id_text.setZValue(5 if is_new_arrival else -1)
                id_text.setVisible(self.show_labels)
                
                # Add status text with emphasis on "ENTERING"
                status_text = self.scene.addText("ENTERING" if is_new_arrival else squid_data.get('status', 'unknown'))
                if is_new_arrival:
                    status_text.setDefaultTextColor(QtGui.QColor(255, 255, 0))
                    status_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                else:
                    status_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                status_text.setPos(squid_data['x'], squid_data['y'] - 30)
                status_text.setScale(0.7)
                status_text.setZValue(5 if is_new_arrival else -1)
                status_text.setVisible(self.show_labels)
                
                # Add to scene
                self.scene.addItem(remote_visual)
                # id_text is already added by self.scene.addText
                # status_text is already added by self.scene.addText
                
                # Store in tracking dict
                self.remote_squids[node_id] = {
                    'visual': remote_visual,
                    'id_text': id_text,
                    'status_text': status_text,
                    'view_cone': None,
                    'last_update': time.time(),
                    'data': squid_data
                }
                
                # Add view cone if needed
                if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                    self.update_remote_view_cone(node_id, squid_data)
                    
                # Create arrival animation for new squids
                if is_new_arrival:
                    # Ensure remote_visual is compatible with _create_arrival_animation
                    # If _create_arrival_animation expects AnimatableGraphicsItem, instantiate remote_visual accordingly
                    self._create_arrival_animation(remote_visual) # Pass the QGraphicsPixmapItem
            
            except Exception as e:
                self.logger.error(f"Error creating remote squid {node_id}: {e}", exc_info=True)
                return False
        
        # Update last seen time
        if node_id in self.remote_squids:
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'] = squid_data # Ensure data is updated
        
        return True
    
    def update_remote_view_cone(self, node_id, squid_data):
        """Update or create the view cone for a remote squid"""
        if node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"Node {node_id} not in remote_squids for view cone update.")
            return
        
        remote_squid = self.remote_squids[node_id]
        
        # Remove existing view cone if it exists
        if 'view_cone' in remote_squid and remote_squid['view_cone'] is not None and remote_squid['view_cone'] in self.scene.items():
            self.scene.removeItem(remote_squid['view_cone'])
            remote_squid['view_cone'] = None # Ensure it's cleared
        
        # Get view cone parameters
        squid_x = squid_data.get('x',0) # Use .get for safety
        squid_y = squid_data.get('y',0)
        
        # Assuming squid visual exists if we are here and node_id is in remote_squids
        visual_item = remote_squid.get('visual')
        if visual_item:
            squid_width = visual_item.boundingRect().width()
            squid_height = visual_item.boundingRect().height()
        else: # Fallback if visual somehow not set
            squid_width = 60 
            squid_height = 40

        squid_center_x = squid_x + squid_width / 2
        squid_center_y = squid_y + squid_height / 2
        
        looking_direction = squid_data.get('looking_direction', 0) # Radians
        view_cone_angle = squid_data.get('view_cone_angle', math.radians(60)) # Radians
        
        cone_length = 150 # Fixed length for now, could be dynamic
        
        cone_points = [
            QtCore.QPointF(squid_center_x, squid_center_y),
            QtCore.QPointF(
                squid_center_x + math.cos(looking_direction - view_cone_angle/2) * cone_length,
                squid_center_y + math.sin(looking_direction - view_cone_angle/2) * cone_length
            ),
            QtCore.QPointF(
                squid_center_x + math.cos(looking_direction + view_cone_angle/2) * cone_length,
                squid_center_y + math.sin(looking_direction + view_cone_angle/2) * cone_length
            )
        ]
        
        cone_polygon = QtGui.QPolygonF(cone_points)
        view_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        
        color_tuple = squid_data.get('color', (150, 150, 255))
        try:
            q_color = QtGui.QColor(*color_tuple) # Ensure color_tuple is valid
        except TypeError:
            q_color = QtGui.QColor(150,150,255) # Fallback color
            if self.debug_mode: self.logger.warning(f"Invalid color tuple {color_tuple} for view cone. Using default.")

        view_cone_item.setPen(QtGui.QPen(q_color, 0.5)) # Pen for border
        view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 30))) # Semi-transparent fill
        
        view_cone_item.setZValue(visual_item.zValue() -1 if visual_item else -2)
        
        self.scene.addItem(view_cone_item)
        remote_squid['view_cone'] = view_cone_item
    
    def _create_arrival_animation(self, visual_item):
        """Create an attention-grabbing animation for newly arrived squids"""
        # Check if visual_item supports 'scale_factor' property (i.e., is AnimatableGraphicsItem)
        # If visual_item is just a QGraphicsPixmapItem, QPropertyAnimation on "scale_factor" won't work directly.
        # For simplicity, if it's not an AnimatableGraphicsItem, we can animate 'scale' property.
        
        is_animatable = hasattr(visual_item, 'scale_factor')

        if is_animatable:
            scale_prop_name = b"scale_factor"
        else:
            # Standard QGraphicsItem has a 'scale' property (qreal) but it's not a pyqtProperty by default for QPropertyAnimation
            # We might need to use a different approach or ensure visual_item is AnimatableGraphicsItem.
            # For now, let's try to animate 'scale' directly, it might work if Qt's meta-object system picks it up.
            scale_prop_name = b"scale"


        scale_animation = QtCore.QPropertyAnimation(visual_item, scale_prop_name)
        scale_animation.setDuration(500)
        scale_animation.setStartValue(1.5)
        scale_animation.setEndValue(1.0)
        scale_animation.setEasingCurve(QtCore.QEasingCurve.OutBounce)
        
        opacity_effect = QtWidgets.QGraphicsOpacityEffect(visual_item) # Apply to visual_item itself
        visual_item.setGraphicsEffect(opacity_effect)
        opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        opacity_animation.setDuration(500)
        opacity_animation.setStartValue(0.5)
        opacity_animation.setEndValue(self.remote_opacity if visual_item.opacity() > 0 else 0) # Respect current opacity
        
        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(scale_animation)
        animation_group.addAnimation(opacity_animation)
        
        animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        
        # Removed the singleShot for _reset_remote_squid_style as it might conflict with ongoing status updates
        # Style resets are better handled based on state changes or timeouts elsewhere.
    
    def _reset_remote_squid_style(self, visual_item_or_node_id):
        """Reset visual style of remote squid after entry period or for normal state."""
        node_id = None
        squid_display_data = None

        if isinstance(visual_item_or_node_id, str): # it's a node_id
            node_id = visual_item_or_node_id
            squid_display_data = self.remote_squids.get(node_id)
        elif isinstance(visual_item_or_node_id, QtWidgets.QGraphicsPixmapItem): # it's the visual item
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
            if isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsDropShadowEffect) or \
               isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsColorizeEffect) : # Example effects
                 visual_item.setGraphicsEffect(None)


        if status_text_item:
            # Only reset if not in a special state like "ENTERING" or "ARRIVING"
            current_status = squid_display_data.get('data',{}).get('status','visiting').upper()
            if current_status not in ["ENTERING", "ARRIVING"]:
                 status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                 status_text_item.setFont(QtGui.QFont("Arial", 10)) # Or your default font
                 status_text_item.setPlainText(squid_display_data.get('data',{}).get('status','visiting'))
            status_text_item.setZValue(visual_item.zValue() + 1 if visual_item else 0)


        if id_text_item:
            id_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 180)) # Slightly dimmer
            id_text_item.setFont(QtGui.QFont("Arial", 8)) # Smaller font
            id_text_item.setZValue(visual_item.zValue() + 1 if visual_item else 0)
    
    def update_connection_lines(self, local_squid_pos_tuple):
        """Update the visual lines connecting to remote squids"""
        if not self.show_connections:
            # If lines are hidden, ensure all existing lines are also hidden or removed
            for node_id, line in list(self.connection_lines.items()): # Iterate over a copy for safe removal
                if line in self.scene.items():
                    self.scene.removeItem(line)
                del self.connection_lines[node_id]
            return
        
        if not local_squid_pos_tuple or len(local_squid_pos_tuple) != 2:
            if self.debug_mode: self.logger.warning("Invalid local_squid_pos for connection lines.")
            return

        local_center_x, local_center_y = local_squid_pos_tuple
        
        active_lines_for_nodes = set()
        for node_id, squid_data in self.remote_squids.items():
            if 'visual' not in squid_data or not squid_data['visual'].isVisible():
                continue # Skip if no visual or not visible
                
            active_lines_for_nodes.add(node_id)
            remote_visual = squid_data['visual']
            remote_pos = remote_visual.pos()
            # Approximate center based on common squid dimensions if boundingRect is problematic
            remote_center_x = remote_pos.x() + remote_visual.boundingRect().width() / 2
            remote_center_y = remote_pos.y() + remote_visual.boundingRect().height() / 2
            
            color_tuple = squid_data.get('data', {}).get('color', (100, 100, 255))
            try:
                q_color = QtGui.QColor(*color_tuple)
            except TypeError:
                q_color = QtGui.QColor(100,100,255)


            if node_id in self.connection_lines:
                line = self.connection_lines[node_id]
                if line not in self.scene.items(): # Re-add if removed for some reason
                    self.scene.addItem(line)
                line.setLine(local_center_x, local_center_y, remote_center_x, remote_center_y)
                line.pen().setColor(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 100))
                line.setVisible(True) # Ensure visible
            else:
                line = QtWidgets.QGraphicsLineItem(
                    local_center_x, local_center_y, remote_center_x, remote_center_y
                )
                pen = QtGui.QPen(QtGui.QColor(q_color.red(), q_color.green(), q_color.blue(), 100))
                pen.setWidth(1) # Thinner lines
                pen.setStyle(QtCore.Qt.SolidLine) # Solid lines might be clearer
                line.setPen(pen)
                line.setZValue(-10) # Well behind other items
                line.setVisible(True)
                self.scene.addItem(line)
                self.connection_lines[node_id] = line
        
        # Remove lines for squids that are no longer present
        for node_id in list(self.connection_lines.keys()):
            if node_id not in active_lines_for_nodes:
                line_to_remove = self.connection_lines.pop(node_id)
                if line_to_remove in self.scene.items():
                    self.scene.removeItem(line_to_remove)

    def remove_remote_squid(self, node_id):
        """Remove a remote squid and all its components"""
        if node_id not in self.remote_squids:
            return
        
        squid_data = self.remote_squids.pop(node_id) # Use pop to get and remove
        
        for key in ['visual', 'view_cone', 'id_text', 'status_text']:
            item = squid_data.get(key)
            if item is not None and item in self.scene.items():
                self.scene.removeItem(item)
        
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
            if current_time - data.get('last_update', 0) > timeout
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
        
        obj_data = self.remote_objects.pop(obj_id)
        
        visual_item = obj_data.get('visual')
        if visual_item and visual_item in self.scene.items():
            self.scene.removeItem(visual_item)
            
        label_item = obj_data.get('label') # If objects have labels
        if label_item and label_item in self.scene.items():
            self.scene.removeItem(label_item)
        if self.debug_mode: self.logger.debug(f"Removed remote object {obj_id}")
    
    def cleanup_all(self):
        """Remove all remote entities managed by this instance."""
        for node_id in list(self.remote_squids.keys()):
            self.remove_remote_squid(node_id)
        self.remote_squids.clear()
            
        for obj_id in list(self.remote_objects.keys()):
            self.remove_remote_object(obj_id)
        self.remote_objects.clear()

        for node_id in list(self.connection_lines.keys()): # Also clear connection lines dict
            line = self.connection_lines.pop(node_id)
            if line in self.scene.items():
                self.scene.removeItem(line)
        self.connection_lines.clear()

        # Clear object pools if they hold QGraphicsItems added to the scene
        # This requires objects in pool to be removed from scene when pool is cleared/reset
        # For simplicity, if objects are re-added to scene on acquire, this is okay.
        # If objects remain in scene and pool just tracks them, more complex cleanup is needed.
        # Assuming objects from pool are managed (added/removed from scene) upon acquire/release.
        if hasattr(self, 'text_pool'):
             # Proper cleanup of a pool of QGraphicsItems would involve
             # removing each item from the scene before clearing the pool's internal lists.
             # For items managed by ObjectPool (added to scene by factory, visible when in use)
             for item in self.text_pool.available:
                 if item in self.scene.items(): self.scene.removeItem(item)
             for item in self.text_pool.in_use: # Should be empty if all released before cleanup_all
                 if item in self.scene.items(): self.scene.removeItem(item)
             self.text_pool.clear()


        if self.debug_mode: self.logger.info("RemoteEntityManager cleaned up all entities.")