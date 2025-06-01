# File: remote_entity_manager.py

import os
import math
import time # Keep time import if any timing related logic is added later
from PyQt5 import QtCore, QtGui, QtWidgets
import logging # Added for logger
from typing import Dict, Any # For type hinting

# Attempt to import ResizablePixmapItem from the main application's UI module
try:
    from src.ui import ResizablePixmapItem
except ImportError:
    ResizablePixmapItem = None # Fallback if not found

class RemoteEntityManager:
    """
    Manages the visual representation of remote squids and potentially other entities
    in the local game scene.
    """
    def __init__(self, scene: QtWidgets.QGraphicsScene, window_width: int, window_height: int,
                 debug_mode: bool = False, logger: logging.Logger = None):
        
        self.scene = scene
        self.window_width = window_width
        self.window_height = window_height
        self.debug_mode = debug_mode

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(__name__) 
            if not self.logger.hasHandlers():
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        self.remote_squid_visuals: Dict[str, Dict[str, Any]] = {}
        self.image_load_cache: Dict[str, QtGui.QPixmap] = {}

        self.DEFAULT_OPACITY = 0.75 # Default, can be changed by settings
        self.SHOW_LABELS = True
        self.SHOW_CONNECTION_LINES = True
        
        self.logger.info("RemoteEntityManager initialized.")
        if ResizablePixmapItem is None:
             self.logger.warning("ResizablePixmapItem not imported. Custom item features might be limited.")

    def update_settings(self, remote_opacity=None, show_labels=None, show_connections=None, debug_mode=None):
        if remote_opacity is not None: self.DEFAULT_OPACITY = remote_opacity
        if show_labels is not None: self.SHOW_LABELS = show_labels
        if show_connections is not None: self.SHOW_CONNECTION_LINES = show_connections
        if debug_mode is not None: 
            self.debug_mode = debug_mode
            self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)

        for node_id, visual_components in self.remote_squid_visuals.items():
            if visual_components.get('visual'):
                visual_components['visual'].setOpacity(self.DEFAULT_OPACITY) # Apply new default
            # Apply label visibility to all text items
            for key in ['id_text', 'status_text']:
                if visual_components.get(key):
                    visual_components[key].setVisible(self.SHOW_LABELS)
            # View cone visibility often tied to labels and squid data
            if visual_components.get('view_cone'):
                is_cone_data_visible = visual_components.get('data', {}).get('view_cone_visible', False)
                visual_components['view_cone'].setVisible(self.SHOW_LABELS and is_cone_data_visible)
        
        if self.debug_mode: self.logger.debug(f"Settings updated: Opacity={self.DEFAULT_OPACITY}, Labels={self.SHOW_LABELS}")

    def _get_pixmap(self, image_path: str, item_type_for_fallback: str = "generic") -> QtGui.QPixmap | None:
        """Loads a QPixmap from a path, using a cache. Includes typed fallback."""
        if image_path in self.image_load_cache:
            return self.image_load_cache[image_path]
        
        if not os.path.exists(image_path):
            self.logger.warning(f"Image file not found: {image_path}")
            fallback_path = None
            if item_type_for_fallback == "squid":
                fallback_path = os.path.join("images", "squid.png") # Generic squid
            elif item_type_for_fallback == "rock":
                fallback_path = os.path.join("images", "rock.png") # Generic rock
            # Add more typed fallbacks if needed
            
            if fallback_path and os.path.exists(fallback_path):
                 pixmap = QtGui.QPixmap(fallback_path)
                 if not pixmap.isNull():
                    self.logger.info(f"Using fallback image '{fallback_path}' for missing '{image_path}'.")
                    self.image_load_cache[image_path] = pixmap # Cache fallback against original path
                    return pixmap
            return None

        pixmap = QtGui.QPixmap(image_path)
        if pixmap.isNull():
            self.logger.error(f"Failed to load QPixmap for image: {image_path}")
            return None
        
        self.image_load_cache[image_path] = pixmap
        return pixmap

    def _create_squid_visual_item(self, squid_data: Dict) -> QtWidgets.QGraphicsPixmapItem | None:
        direction = squid_data.get('direction', 'right')
        image_key_suffix = squid_data.get('image_direction_key', direction)
        image_filename = f"{image_key_suffix.lower()}1.png" 
        full_image_path = os.path.join("images", image_filename)

        pixmap = self._get_pixmap(full_image_path, item_type_for_fallback="squid") # Specify type for fallback
        if not pixmap:
            self.logger.warning(f"Pixmap for {full_image_path} is null. Creating color placeholder for squid.")
            width = squid_data.get('squid_width', 60); height = squid_data.get('squid_height', 40)
            color_tuple = squid_data.get('color', (100, 100, 255)); q_color = QtGui.QColor(*color_tuple)
            pixmap = QtGui.QPixmap(int(width), int(height)); pixmap.fill(q_color)
            if pixmap.isNull(): self.logger.error("Failed to create color placeholder pixmap."); return None
        
        visual_item = QtWidgets.QGraphicsPixmapItem(pixmap) # Fallback to standard if ResizablePixmapItem fails or not avail
        if ResizablePixmapItem:
            try:
                visual_item = ResizablePixmapItem(pixmap, filename=full_image_path, category="remote_squid")
            except Exception as e_rpmi:
                self.logger.error(f"Error creating ResizablePixmapItem for squid: {e_rpmi}. Using QGraphicsPixmapItem.", exc_info=True)
                visual_item = QtWidgets.QGraphicsPixmapItem(pixmap) # Ensure fallback

        visual_item.setPos(squid_data['x'], squid_data['y'])
        visual_item.setOpacity(self.DEFAULT_OPACITY)
        visual_item.setZValue(5)
        return visual_item

    def _create_text_item(self, text: str, parent_visual_item: QtWidgets.QGraphicsPixmapItem,
                          offset_y: int, font_size: int, color_tuple: tuple = (200,200,200,200), is_bold: bool = False) -> QtWidgets.QGraphicsTextItem:
        text_item = QtWidgets.QGraphicsTextItem(text)
        font = QtGui.QFont("Arial", font_size); 
        if is_bold: font.setBold(True)
        text_item.setFont(font)
        try: text_item.setDefaultTextColor(QtGui.QColor(*color_tuple))
        except TypeError: text_item.setDefaultTextColor(QtGui.QColor(200,200,200,200))

        parent_rect = parent_visual_item.boundingRect()
        text_rect = text_item.boundingRect() # Get after setting font
        # Center text above the parent item
        pos_x = parent_visual_item.pos().x() + (parent_rect.width() / 2) - (text_rect.width() / 2)
        pos_y = parent_visual_item.pos().y() + offset_y 
        text_item.setPos(pos_x, pos_y)
        
        text_item.setZValue(parent_visual_item.zValue() + 1) 
        text_item.setVisible(self.SHOW_LABELS)
        self.scene.addItem(text_item)
        return text_item

    def _update_carried_item_visual(self, node_id: str, squid_visual_components: Dict, squid_data: Dict):
        """Creates, updates, or removes the visual for an item carried by a remote squid."""
        # This status comes directly from the autopilot
        status = squid_data.get('status', '') 
        # The autopilot also now includes these directly in squid_data when it intends to steal
        carried_item_type = squid_data.get('stolen_item_type') 
        carried_item_filename = squid_data.get('stolen_item_id') # Expects filename

        squid_main_visual = squid_visual_components.get('visual')
        current_carried_visual = squid_visual_components.get('carried_item_visual')

        # Condition to show carried item: status indicates carrying AND type is rock AND filename provided
        is_carrying_rock_status = "carrying rock" in status.lower()
        should_show_carried_rock = (is_carrying_rock_status or carried_item_type == 'rock') and carried_item_filename and squid_main_visual

        if should_show_carried_rock:
            if not current_carried_visual:
                rock_pixmap = self._get_pixmap(carried_item_filename, item_type_for_fallback="rock")
                if rock_pixmap:
                    current_carried_visual = QtWidgets.QGraphicsPixmapItem(rock_pixmap)
                    self.scene.addItem(current_carried_visual)
                    squid_visual_components['carried_item_visual'] = current_carried_visual
                    if self.debug_mode: self.logger.debug(f"Created carried rock visual for {node_id}: {carried_item_filename}")
                else:
                    if self.debug_mode: self.logger.warning(f"Could not load pixmap for carried rock '{carried_item_filename}' for squid {node_id}.")
                    return # Cannot display

            if current_carried_visual: # Ensure it was created or already exists
                squid_pos = squid_main_visual.pos()
                squid_img_dir = squid_data.get('image_direction_key', squid_data.get('direction', 'right'))
                
                # Simplified offset logic (adjust these values as needed for better visual fit)
                offset_x, offset_y = 20, 30 
                if squid_img_dir == 'left': offset_x = - (current_carried_visual.boundingRect().width() * 0.5) - 5
                elif squid_img_dir == 'right': offset_x = squid_main_visual.boundingRect().width() - (current_carried_visual.boundingRect().width() * 0.5) + 5
                
                current_carried_visual.setPos(squid_pos.x() + offset_x, squid_pos.y() + offset_y)
                current_carried_visual.setZValue(squid_main_visual.zValue() - 0.1) # Slightly behind squid
                current_carried_visual.setOpacity(self.DEFAULT_OPACITY * 0.85) # Slightly more transparent
                current_carried_visual.setScale(0.45) # Smaller to look "held"
                current_carried_visual.setVisible(True)
        
        elif current_carried_visual: # Not carrying a rock, or item details missing, remove visual
            if self.debug_mode: self.logger.debug(f"Removing carried item visual for {node_id} as status/type is no longer 'rock' or item ID missing.")
            if current_carried_visual.scene():
                self.scene.removeItem(current_carried_visual)
            squid_visual_components['carried_item_visual'] = None


    def update_remote_squid(self, node_id: str, squid_data: Dict, is_new_arrival: bool = False) -> bool:
        if not all(k in squid_data for k in ['x', 'y', 'direction', 'node_id']):
            self.logger.warning(f"Insufficient base data for remote squid {node_id}. Required: x, y, direction, node_id.")
            return False

        visual_components = self.remote_squid_visuals.get(node_id)

        if not visual_components and is_new_arrival: # Create new visual set for a new arrival
            if self.debug_mode: self.logger.info(f"New remote squid arrival: {node_id}. Creating visuals.")
            squid_main_visual = self._create_squid_visual_item(squid_data)
            if not squid_main_visual:
                self.logger.error(f"Failed to create main visual for new remote squid {node_id}.")
                return False
            
            id_text_str = f"ID: {node_id[-6:]}" # Show last 6 chars
            status_text_str = squid_data.get('status', 'Exploring...')
            
            id_text = self._create_text_item(id_text_str, squid_main_visual, offset_y=-50, font_size=8, color_tuple=(180,180,200,150))
            status_text = self._create_text_item(status_text_str, squid_main_visual, offset_y=-35, font_size=9)
            
            visual_components = {'visual': squid_main_visual, 'id_text': id_text, 'status_text': status_text, 'data': squid_data.copy(), 'view_cone': None, 'carried_item_visual': None}
            self.remote_squid_visuals[node_id] = visual_components
            self._apply_arrival_effect(squid_main_visual) # Apply a simple arrival effect

        elif not visual_components: # Data received for a squid that has no visuals and isn't marked as new arrival
            self.logger.warning(f"Data for non-existent remote squid {node_id} (not new arrival). Ignored or queue for creation.")
            # Potentially, you might want to treat this as a new arrival if it's unexpected.
            # For now, returning False if no visuals and not a new arrival.
            return False
        
        # Update existing visuals
        visual_components['data'].update(squid_data) # Update stored data
        squid_main_visual = visual_components.get('visual')
        id_text = visual_components.get('id_text')
        status_text_item = visual_components.get('status_text')

        if squid_main_visual:
            squid_main_visual.setPos(squid_data['x'], squid_data['y'])
            direction = squid_data.get('direction', 'right')
            image_key_suffix = squid_data.get('image_direction_key', direction)
            image_filename = f"{image_key_suffix.lower()}1.png"
            full_image_path = os.path.join("images", image_filename)
            pixmap = self._get_pixmap(full_image_path, item_type_for_fallback="squid")
            if pixmap:
                squid_main_visual.setPixmap(pixmap)
            elif self.debug_mode:
                self.logger.warning(f"Pixmap update failed for {full_image_path} on squid {node_id}.")
            squid_main_visual.setOpacity(self.DEFAULT_OPACITY) # Apply current opacity setting

        if id_text: # Update ID text position (content rarely changes)
            parent_rect = squid_main_visual.boundingRect() if squid_main_visual else QtCore.QRectF()
            text_rect = id_text.boundingRect()
            pos_x = squid_data['x'] + (parent_rect.width() / 2) - (text_rect.width() / 2)
            id_text.setPos(pos_x, squid_data['y'] - 50)
            id_text.setVisible(self.SHOW_LABELS)

        if status_text_item: # Update status text content and position
            parent_rect = squid_main_visual.boundingRect() if squid_main_visual else QtCore.QRectF()
            status_text_item.setPlainText(squid_data.get('status', '...')) # Update text
            text_rect = status_text_item.boundingRect() # Re-get BR after text change
            pos_x = squid_data['x'] + (parent_rect.width() / 2) - (text_rect.width() / 2)
            status_text_item.setPos(pos_x, squid_data['y'] - 35)
            status_text_item.setVisible(self.SHOW_LABELS)

        self.update_remote_view_cone(node_id, squid_data)
        self._update_carried_item_visual(node_id, visual_components, squid_data) # UPDATE CARRIED ITEM

        return True

    def _apply_arrival_effect(self, visual_item: QtWidgets.QGraphicsPixmapItem):
        """Applies a simple visual effect for new arrivals."""
        if not visual_item: return
        visual_item.setOpacity(0.0) # Start invisible
        visual_item.setScale(0.5)   # Start small

        # Opacity animation
        opacity_anim = QtCore.QPropertyAnimation(visual_item, b"opacity")
        opacity_anim.setDuration(700) # milliseconds
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(self.DEFAULT_OPACITY)
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        
        # Scale animation
        scale_anim = QtCore.QPropertyAnimation(visual_item, b"scale")
        scale_anim.setDuration(700)
        scale_anim.setStartValue(0.5)
        scale_anim.setEndValue(1.0)
        scale_anim.setEasingCurve(QtCore.QEasingCurve.OutBack) # Playful bounce

        # Group animations (optional, but good for parallel execution)
        self.arrival_animation_group = QtCore.QParallelAnimationGroup()
        self.arrival_animation_group.addAnimation(opacity_anim)
        self.arrival_animation_group.addAnimation(scale_anim)
        self.arrival_animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)


    def update_remote_view_cone(self, node_id: str, squid_data: Dict):
        """Updates the view cone visual for a remote squid."""
        if node_id not in self.remote_squid_visuals: return
        
        visual_components = self.remote_squid_visuals[node_id]
        squid_main_visual = visual_components.get('visual')
        existing_cone = visual_components.get('view_cone')

        should_show_cone = self.SHOW_LABELS and squid_data.get('view_cone_visible', False)

        if not should_show_cone:
            if existing_cone and existing_cone.scene():
                self.scene.removeItem(existing_cone)
            visual_components['view_cone'] = None
            return

        if not squid_main_visual: return # Need main visual to base cone on

        # Create or update cone
        looking_direction_rad = squid_data.get('looking_direction', 0.0)
        view_cone_angle_rad = squid_data.get('view_cone_angle', math.radians(50))
        cone_half_angle = view_cone_angle_rad / 2.0
        cone_length = 120 # Visual length of cone

        squid_center_x = squid_main_visual.pos().x() + squid_main_visual.boundingRect().width() / 2
        squid_center_y = squid_main_visual.pos().y() + squid_main_visual.boundingRect().height() / 2
        
        points = [
            QtCore.QPointF(squid_center_x, squid_center_y),
            QtCore.QPointF(squid_center_x + cone_length * math.cos(looking_direction_rad - cone_half_angle),
                           squid_center_y + cone_length * math.sin(looking_direction_rad - cone_half_angle)),
            QtCore.QPointF(squid_center_x + cone_length * math.cos(looking_direction_rad + cone_half_angle),
                           squid_center_y + cone_length * math.sin(looking_direction_rad + cone_half_angle))
        ]
        cone_polygon = QtGui.QPolygonF(points)

        if existing_cone:
            existing_cone.setPolygon(cone_polygon)
        else:
            existing_cone = QtWidgets.QGraphicsPolygonItem(cone_polygon)
            squid_color_tuple = squid_data.get('color', (150,150,255,30)) # Use squid color with low alpha
            try: q_color = QtGui.QColor(*squid_color_tuple)
            except TypeError: q_color = QtGui.QColor(150,150,255,30)
            
            existing_cone.setPen(QtGui.QPen(QtGui.QColor(q_color.red(),q_color.green(),q_color.blue(),0))) # Transparent border
            existing_cone.setBrush(QtGui.QBrush(q_color)) # Semi-transparent fill
            existing_cone.setZValue(squid_main_visual.zValue() - 1) # Behind squid
            self.scene.addItem(existing_cone)
            visual_components['view_cone'] = existing_cone
        
        existing_cone.setVisible(True)


    def remove_remote_squid(self, node_id: str):
        """Removes all visual components associated with a remote squid."""
        if node_id in self.remote_squid_visuals:
            visual_components = self.remote_squid_visuals.pop(node_id)
            items_to_remove = ['visual', 'id_text', 'status_text', 'view_cone', 'carried_item_visual'] # Added carried_item_visual
            for key in items_to_remove:
                item = visual_components.get(key)
                if item and item.scene():
                    self.scene.removeItem(item)
            if self.debug_mode: self.logger.debug(f"Removed all visuals for remote squid {node_id}")
        elif self.debug_mode:
            self.logger.debug(f"Attempted to remove non-existent remote squid: {node_id}")

    def initiate_squid_departure_animation(self, node_id: str, on_finish_callback: callable):
        """Animates a remote squid departing and calls a callback when done."""
        if node_id not in self.remote_squid_visuals:
            self.logger.warning(f"Cannot animate departure for non-existent squid {node_id}")
            if on_finish_callback: QtCore.QTimer.singleShot(0, on_finish_callback) # Call immediately
            return

        visual_components = self.remote_squid_visuals[node_id]
        squid_visual = visual_components.get('visual')
        # Hide text labels and view cone immediately
        for key in ['id_text', 'status_text', 'view_cone', 'carried_item_visual']: # Also hide carried item
            item = visual_components.get(key)
            if item: item.setVisible(False)

        if not squid_visual: # No main visual to animate
            if on_finish_callback: QtCore.QTimer.singleShot(0, on_finish_callback)
            return

        # Opacity animation for departure
        opacity_anim = QtCore.QPropertyAnimation(squid_visual, b"opacity")
        opacity_anim.setDuration(800) # milliseconds
        opacity_anim.setStartValue(squid_visual.opacity()) # Start from current opacity
        opacity_anim.setEndValue(0.0) # Fade to invisible
        opacity_anim.setEasingCurve(QtCore.QEasingCurve.InQuad)
        
        # Scale animation (shrinking)
        scale_anim = QtCore.QPropertyAnimation(squid_visual, b"scale")
        scale_anim.setDuration(800)
        scale_anim.setStartValue(squid_visual.scale()) # Start from current scale
        scale_anim.setEndValue(0.1) # Shrink significantly
        scale_anim.setEasingCurve(QtCore.QEasingCurve.InQuad)

        departure_animation_group = QtCore.QParallelAnimationGroup()
        departure_animation_group.addAnimation(opacity_anim)
        departure_animation_group.addAnimation(scale_anim)
        
        # Connect the group's finished signal to the callback
        departure_animation_group.finished.connect(on_finish_callback)
        departure_animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        if self.debug_mode: self.logger.debug(f"Started departure animation for {node_id}")

    def get_last_calculated_entry_details(self, node_id: str) -> Dict | None:
        """
        Retrieves the last calculated entry details for a node_id.
        This is a placeholder; actual calculation happens in mp_plugin_logic when SQUID_EXIT is processed.
        This manager might store it if it needs to for re-creating visuals without full data.
        """
        # This manager doesn't typically calculate or store this. It's more mp_plugin_logic's role.
        # However, if it were to store it (e.g., from the is_new_arrival data):
        visual_comps = self.remote_squid_visuals.get(node_id)
        if visual_comps and 'entry_details_on_this_screen' in visual_comps:
            return visual_comps['entry_details_on_this_screen']
        #self.logger.warning(f"get_last_calculated_entry_details: No stored entry details for {node_id} in REM.")
        return None # Or retrieve from visual_components['data'] if stored there by update_remote_squid

    def cleanup_all(self):
        """Removes all remote squid visuals and their components from the scene."""
        all_node_ids = list(self.remote_squid_visuals.keys()) # Iterate over a copy of keys
        for node_id in all_node_ids:
            self.remove_remote_squid(node_id) # This now handles all components including carried items
        self.remote_squid_visuals.clear() # Should be empty now
        self.image_load_cache.clear()
        self.logger.info("Cleaned up all remote entity visuals.")