from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List

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




class RemoteEntityManager:
    def __init__(self, scene, window_width, window_height, debug_mode=False):
        self.scene = scene
        self.window_width = window_width
        self.window_height = window_height
        self.debug_mode = debug_mode
        
        # Storage for remote entities
        self.remote_squids = {}
        self.remote_objects = {}
        self.connection_lines = {}
        
        # Visual settings
        self.remote_opacity = 0.7
        self.show_labels = True
        self.show_connections = True
    
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
                if 'view_cone' in remote_squid and remote_squid['view_cone'] in self.scene.items():
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
                squid_image = f"{direction}1.png"
                squid_pixmap = QtGui.QPixmap(os.path.join("images", squid_image))
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
                    self._create_arrival_animation(remote_visual)
            
            except Exception as e:
                print(f"Error creating remote squid: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Update last seen time
        if node_id in self.remote_squids:
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'] = squid_data
        
        return True
    
    def update_remote_view_cone(self, node_id, squid_data):
        """Update or create the view cone for a remote squid"""
        if node_id not in self.remote_squids:
            return
        
        remote_squid = self.remote_squids[node_id]
        
        # Remove existing view cone if it exists
        if 'view_cone' in remote_squid and remote_squid['view_cone'] in self.scene.items():
            self.scene.removeItem(remote_squid['view_cone'])
        
        # Get view cone parameters
        squid_x = squid_data['x']
        squid_y = squid_data['y']
        squid_width = 60  # Default width
        squid_height = 40  # Default height
        
        squid_center_x = squid_x + squid_width / 2
        squid_center_y = squid_y + squid_height / 2
        
        # Get viewing direction angle - default to 0 (right)
        looking_direction = squid_data.get('looking_direction', 0)
        
        # Set view cone angle
        view_cone_angle = squid_data.get('view_cone_angle', 1.0)
        
        # Calculate cone length
        cone_length = max(self.window_width, self.window_height)
        
        # Create polygon for view cone
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
        
        # Create view cone item
        view_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        
        # Use squid color for the view cone
        color = squid_data.get('color', (150, 150, 255))
        view_cone_item.setPen(QtGui.QPen(QtGui.QColor(*color)))
        view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(*color, 30)))
        
        view_cone_item.setZValue(-2)  # Behind the squid
        
        # Add to scene
        self.scene.addItem(view_cone_item)
        
        # Store in our tracking dict
        remote_squid['view_cone'] = view_cone_item
    
    def _create_arrival_animation(self, visual_item):
        """Create an attention-grabbing animation for newly arrived squids"""
        # Create scale animation
        scale_animation = QtCore.QPropertyAnimation(visual_item, b"scale_factor")
        scale_animation.setDuration(500)
        scale_animation.setStartValue(1.5)  # Start larger
        scale_animation.setEndValue(1.0)  # End at normal size
        scale_animation.setEasingCurve(QtCore.QEasingCurve.OutBounce)
        
        # Create opacity effect animation
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        visual_item.setGraphicsEffect(opacity_effect)
        opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        opacity_animation.setDuration(500)
        opacity_animation.setStartValue(0.5)
        opacity_animation.setEndValue(self.remote_opacity)
        
        # Create animation group
        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(scale_animation)
        animation_group.addAnimation(opacity_animation)
        
        # Start animation
        animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        
        # Reset to normal after a delay
        QtCore.QTimer.singleShot(5000, lambda: self._reset_remote_squid_style(visual_item))
    
    def _reset_remote_squid_style(self, visual_item):
        """Reset visual style of remote squid after entry period"""
        # Find which squid this belongs to
        for node_id, squid_data in self.remote_squids.items():
            if squid_data['visual'] == visual_item:
                # Reset status text
                if 'status_text' in squid_data:
                    squid_data['status_text'].setDefaultTextColor(QtGui.QColor(200, 200, 200))
                    squid_data['status_text'].setFont(QtGui.QFont("Arial", 10))
                    squid_data['status_text'].setPlainText("visiting")
                
                # Reset visual properties
                visual_item.setZValue(-1)
                visual_item.setOpacity(self.remote_opacity)
                
                # Reset ID text
                if 'id_text' in squid_data:
                    squid_data['id_text'].setZValue(-1)
                break
    
    def update_connection_lines(self, local_squid_pos):
        """Update the visual lines connecting to remote squids"""
        if not self.show_connections:
            return
        
        # Get local squid position
        local_pos = local_squid_pos
        
        # Update/create lines for each remote squid
        for node_id, squid_data in self.remote_squids.items():
            # Skip if no visual
            if 'visual' not in squid_data:
                continue
                
            remote_visual = squid_data['visual']
            remote_pos = remote_visual.pos()
            remote_center = (remote_pos.x() + 30, remote_pos.y() + 20)  # Center of ellipse
            
            # Create or update connection line
            if node_id in self.connection_lines:
                line = self.connection_lines[node_id]
                if line in self.scene.items():
                    line.setLine(local_pos[0], local_pos[1], remote_center[0], remote_center[1])
            else:
                # Create new line
                line = QtWidgets.QGraphicsLineItem(
                    local_pos[0], local_pos[1], remote_center[0], remote_center[1]
                )
                
                # Style the line
                color = squid_data.get('data', {}).get('color', (100, 100, 255))
                pen = QtGui.QPen(QtGui.QColor(*color, 100))
                pen.setWidth(2)
                pen.setStyle(QtCore.Qt.DashLine)
                line.setPen(pen)
                
                # Add to scene and store reference
                line.setZValue(-5)  # Below squids
                line.setVisible(self.show_connections)
                self.scene.addItem(line)
                self.connection_lines[node_id] = line
    
    def remove_remote_squid(self, node_id):
        """Remove a remote squid and all its components"""
        if node_id not in self.remote_squids:
            return
        
        squid_data = self.remote_squids[node_id]
        
        # Remove all visual components
        for key in ['visual', 'view_cone', 'id_text', 'status_text']:
            if key in squid_data and squid_data[key] in self.scene.items():
                self.scene.removeItem(squid_data[key])
        
        # Remove connection line
        if node_id in self.connection_lines:
            if self.connection_lines[node_id] in self.scene.items():
                self.scene.removeItem(self.connection_lines[node_id])
            del self.connection_lines[node_id]
        
        # Remove from tracking
        del self.remote_squids[node_id]
    
    def cleanup_stale_entities(self, timeout=10.0):
        """Remove entities that haven't been updated recently"""
        current_time = time.time()
        stale_threshold = timeout
        
        # Find and remove stale squids
        stale_squids = []
        for node_id, squid_data in self.remote_squids.items():
            if current_time - squid_data['last_update'] > stale_threshold:
                stale_squids.append(node_id)
        
        # Remove stale squids
        for node_id in stale_squids:
            self.remove_remote_squid(node_id)
        
        # Find and remove stale objects
        stale_objects = []
        for obj_id, obj_data in self.remote_objects.items():
            if current_time - obj_data['last_update'] > stale_threshold:
                stale_objects.append(obj_id)
        
        # Remove stale objects
        for obj_id in stale_objects:
            self.remove_remote_object(obj_id)
        
        return len(stale_squids), len(stale_objects)
    
    def remove_remote_object(self, obj_id):
        """Remove a remote object"""
        if obj_id not in self.remote_objects:
            return
        
        obj_data = self.remote_objects[obj_id]
        
        # Remove visual
        if 'visual' in obj_data and obj_data['visual'] in self.scene.items():
            self.scene.removeItem(obj_data['visual'])
            
        # Remove label if it exists
        if 'label' in obj_data and obj_data['label'] in self.scene.items():
            self.scene.removeItem(obj_data['label'])
        
        # Remove from tracking
        del self.remote_objects[obj_id]
    
    def cleanup_all(self):
        """Remove all remote entities"""
        # Remove all remote squids
        for node_id in list(self.remote_squids.keys()):
            self.remove_remote_squid(node_id)
            
        # Remove all remote objects
        for obj_id in list(self.remote_objects.keys()):
            self.remove_remote_object(obj_id)