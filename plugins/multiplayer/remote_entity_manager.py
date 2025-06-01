from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List
import logging
import base64

# AnimatableGraphicsItem class
class AnimatableGraphicsItem(QtWidgets.QGraphicsPixmapItem, QtCore.QObject):
    def __init__(self, pixmap=None, parent=None):
        QtWidgets.QGraphicsPixmapItem.__init__(self, pixmap, parent)
        QtCore.QObject.__init__(self)
        self._scale = 1.0
    @QtCore.pyqtProperty(float)
    def scale_factor(self): return self._scale
    @scale_factor.setter
    def scale_factor(self, value):
        self._scale = value
        self.setScale(value)

# ObjectPool class
class ObjectPool:
    def __init__(self, factory_func, initial_size=10):
        self.factory = factory_func
        self.available = []
        self.in_use = set()
        for _ in range(initial_size): self.available.append(self.factory())
    def acquire(self):
        obj = self.available.pop() if self.available else self.factory()
        self.in_use.add(obj)
        return obj
    def release(self, obj):
        if obj in self.in_use:
            self.in_use.remove(obj)
            self.available.append(obj)
    def clear(self):
        for item_list in [self.available, self.in_use]:
            for item in list(item_list): # Iterate copy if modifying list
                if isinstance(item, QtWidgets.QGraphicsItem) and item.scene(): 
                    item.scene().removeItem(item)
                if item_list is self.in_use and item in self.in_use: # If clearing in_use, ensure removed
                     self.in_use.remove(item)
        self.available.clear()
        # self.in_use should be cleared by loop above if items are released,
        # but direct clear if items are not released back to pool by external logic.
        self.in_use.clear()


class RemoteEntityManager:
    def __init__(self, scene, window_width, window_height, debug_mode=False, logger=None):
        self.scene = scene
        self.window_width = window_width
        self.window_height = window_height
        self.debug_mode = debug_mode

        self.IMAGE_DIMENSIONS = {
            "left1.png": (253, 147), "left2.png": (253, 147),
            "right1.png": (253, 147), "right2.png": (253, 147),
            "up1.png": (177, 238), "up2.png": (177, 238),
        }
        self.DEFAULT_IMAGE_DIMENSION = (253, 147) 

        if logger: self.logger = logger
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
        self._last_calculated_entry_details = {}
        self.remote_opacity = 1.0
        self.show_labels = True
        self.show_connections = True
        self.text_pool = ObjectPool(lambda: QtWidgets.QGraphicsTextItem(""), initial_size=20)
        
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.join(self.script_dir, '..', '..')
        self.images_folder_root_path = os.path.join(self.project_root, 'images')

        self.position_update_timer = QtCore.QTimer()
        self.position_update_timer.timeout.connect(self._update_visuals_once_per_second)
        self.MOVEMENT_INTERVAL_MS = 1000  # Update once per second
        self.MAX_PIXELS_PER_JUMP = 90.0
        self.position_update_timer.start(self.MOVEMENT_INTERVAL_MS)

    def _get_image_file_name_and_direction(self, payload_direction_key: Optional[str], payload_animation_frame: Any, 
                                          entry_direction_on_this_screen: Optional[str] = None, 
                                          current_image_name_for_fallback_dir: str = "right1.png") -> tuple[str, str]:
        intended_facing = "right" # Default
        if payload_direction_key:
            intended_facing = payload_direction_key.lower().strip()
        elif current_image_name_for_fallback_dir:
            # Try to derive from current image if payload key is missing
            # e.g. "left1.png" -> "left"
            name_part = current_image_name_for_fallback_dir.split('.')[0]
            if name_part.endswith("1") or name_part.endswith("2"):
                derived_dir = name_part[:-1]
                if derived_dir in ["left", "right", "up"]: # Valid known directions
                    intended_facing = derived_dir

        facing_direction = intended_facing # Start with this

        if entry_direction_on_this_screen: # Arrival logic modifies facing based on entry side
            if entry_direction_on_this_screen == "left": facing_direction = "right"
            elif entry_direction_on_this_screen == "right": facing_direction = "left"
            elif entry_direction_on_this_screen == "bottom": facing_direction = "up"
            elif entry_direction_on_this_screen == "top": 
                facing_direction = intended_facing if intended_facing in ["left", "right"] else "right"
        
        if facing_direction == "down": # Map "down" to a horizontal direction
            if self.debug_mode: self.logger.debug(f"Mapping 'down' direction. Original payload key: {payload_direction_key}")
            # Prefer left if current image (hint) was left, otherwise default to right
            facing_direction = "left" if current_image_name_for_fallback_dir.startswith("left") else "right"
        
        try:
            frame = int(payload_animation_frame)
            if frame not in [1, 2]: frame = 1
        except (ValueError, TypeError): frame = 1
        
        image_file_name = f"{facing_direction}{frame}.png"
        return image_file_name, facing_direction

    def _get_scaled_pixmap(self, image_file_name: str) -> tuple[QtGui.QPixmap, tuple[int, int]]:
        target_width, target_height = self.IMAGE_DIMENSIONS.get(image_file_name, self.DEFAULT_IMAGE_DIMENSION)
        if (target_width, target_height) == self.DEFAULT_IMAGE_DIMENSION and image_file_name not in self.IMAGE_DIMENSIONS:
            if self.debug_mode: self.logger.warning(f"Image file '{image_file_name}' not in IMAGE_DIMENSIONS. Using default: {self.DEFAULT_IMAGE_DIMENSION}")
        
        image_path = os.path.join(self.images_folder_root_path, image_file_name)
        pixmap = QtGui.QPixmap(image_path)
        if pixmap.isNull():
            if self.debug_mode: self.logger.error(f"Image {image_path} not found. Fallback gray pixmap {target_width}x{target_height}.")
            fb_pixmap = QtGui.QPixmap(target_width, target_height); fb_pixmap.fill(QtCore.Qt.gray)
            return fb_pixmap, (target_width, target_height) 
        return pixmap.scaled(target_width, target_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation), (target_width, target_height)

    def _update_dependent_items_position(self, remote_squid_info, new_visual_x, new_visual_y):
        if remote_squid_info.get('status_text'):
            remote_squid_info['status_text'].setPos(new_visual_x, new_visual_y - 30)
        if remote_squid_info.get('id_text'):
            remote_squid_info['id_text'].setPos(new_visual_x, new_visual_y - 45)

    def _update_visuals_once_per_second(self):
        for node_id, remote_squid_info in list(self.remote_squids.items()):
            visual_item = remote_squid_info.get('visual')
            if not visual_item: continue

            target_x = remote_squid_info.get('network_target_x')
            target_y = remote_squid_info.get('network_target_y')
            if target_x is None or target_y is None: continue

            current_pos = visual_item.pos()
            target_pos = QtCore.QPointF(target_x, target_y)
            if current_pos == target_pos: continue

            vector_to_target = target_pos - current_pos
            distance_to_target = math.sqrt(vector_to_target.x()**2 + vector_to_target.y()**2)
            new_pos: QtCore.QPointF

            if distance_to_target <= self.MAX_PIXELS_PER_JUMP:
                new_pos = target_pos
            else:
                normalized_x = vector_to_target.x() / distance_to_target
                normalized_y = vector_to_target.y() / distance_to_target
                new_pos = QtCore.QPointF(
                    current_pos.x() + normalized_x * self.MAX_PIXELS_PER_JUMP,
                    current_pos.y() + normalized_y * self.MAX_PIXELS_PER_JUMP
                )
            
            visual_item.setPos(new_pos)
            self._update_dependent_items_position(remote_squid_info, new_pos.x(), new_pos.y())
            # No debug log here by default to avoid spam, enable if needed

    def _handle_new_squid_arrival(self, node_id, squid_data_payload, entry_x, entry_y, entry_direction_on_this_screen):
        payload_dir_key = squid_data_payload.get('image_direction_key', 'right')
        payload_anim_frame = squid_data_payload.get('current_animation_frame', 1)
        squid_image_name, _ = self._get_image_file_name_and_direction(payload_dir_key, payload_anim_frame, entry_direction_on_this_screen)
        scaled_pixmap, (current_w, current_h) = self._get_scaled_pixmap(squid_image_name)
        
        remote_visual = AnimatableGraphicsItem(scaled_pixmap)
        remote_visual.setPos(entry_x, entry_y)
        remote_visual.setZValue(5); remote_visual.setOpacity(self.remote_opacity); remote_visual.setScale(1.0)
        self.scene.addItem(remote_visual)

        id_text = self.text_pool.acquire()
        if id_text.scene() != self.scene:
            if id_text.scene(): id_text.scene().removeItem(id_text)
            self.scene.addItem(id_text)
        id_text.setPlainText(f"Remote ({node_id[-4:]})"); id_text.setDefaultTextColor(QtGui.QColor(200,200,200,200))
        id_text.setFont(QtGui.QFont("Arial", 8)); id_text.setZValue(6); id_text.setVisible(self.show_labels)

        status_text = self.text_pool.acquire()
        if status_text.scene() != self.scene:
            if status_text.scene(): status_text.scene().removeItem(status_text)
            self.scene.addItem(status_text)
        status_text.setPlainText("ENTERING..."); status_text.setDefaultTextColor(QtGui.QColor(255,255,0))
        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold)); status_text.setZValue(6); status_text.setVisible(self.show_labels)
        
        self._update_dependent_items_position({'id_text': id_text, 'status_text': status_text}, entry_x, entry_y)

        self.remote_squids[node_id] = {
            'visual': remote_visual, 'id_text': id_text, 'status_text': status_text,
            'view_cone': None, 'last_update': time.time(),
            'data': squid_data_payload.copy(),
            'current_display_dimensions': (current_w, current_h),
            'current_image_name': squid_image_name,
            'was_arrival_text': True,
            'network_target_x': entry_x, 
            'network_target_y': entry_y
        }
        self.logger.info(f"REMOTE_ENTITY_MANAGER: Created new remote squid {node_id} at ({entry_x:.1f}, {entry_y:.1f}). Image: {squid_image_name}, Size: {current_w}x{current_h}")

    def _handle_re_arriving_squid(self, node_id, squid_data_payload, remote_squid_info, entry_x, entry_y, entry_direction_on_this_screen):
        visual_item = remote_squid_info['visual']
        visual_item.setPos(entry_x, entry_y)
        visual_item.setOpacity(self.remote_opacity); visual_item.setVisible(True); visual_item.setScale(1.0)

        payload_dir_key = squid_data_payload.get('image_direction_key', 'right')
        payload_anim_frame = squid_data_payload.get('current_animation_frame', 1)
        new_squid_image_name, _ = self._get_image_file_name_and_direction(
            payload_dir_key, payload_anim_frame, entry_direction_on_this_screen,
            remote_squid_info.get('current_image_name', 'right1.png')
        )
        scaled_pixmap, (current_w, current_h) = self._get_scaled_pixmap(new_squid_image_name)
        visual_item.setPixmap(scaled_pixmap)
        
        remote_squid_info['current_display_dimensions'] = (current_w, current_h)
        remote_squid_info['current_image_name'] = new_squid_image_name
        remote_squid_info['network_target_x'] = entry_x 
        remote_squid_info['network_target_y'] = entry_y
        
        if 'status_text' in remote_squid_info and remote_squid_info['status_text']:
            remote_squid_info['status_text'].setPlainText("ENTERING...")
            remote_squid_info['status_text'].setDefaultTextColor(QtGui.QColor(255,255,0))
            remote_squid_info['status_text'].setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        self._update_dependent_items_position(remote_squid_info, entry_x, entry_y)
        remote_squid_info['was_arrival_text'] = True
        
        self.logger.info(f"REMOTE_ENTITY_MANAGER: Re-initialized re-arriving squid {node_id} at ({entry_x:.1f}, {entry_y:.1f}). Image: {new_squid_image_name}, Size: {current_w}x{current_h}")

    def _handle_existing_squid_update(self, node_id, squid_data_payload, remote_squid_info):
        network_x = squid_data_payload.get('x')
        network_y = squid_data_payload.get('y')

        if network_x is not None and network_y is not None:
            remote_squid_info['network_target_x'] = network_x
            remote_squid_info['network_target_y'] = network_y
        else:
            if self.debug_mode: self.logger.debug(f"Existing squid update for {node_id} missing x or y. Target not updated.")

        visual_item = remote_squid_info['visual'] 

        new_status = squid_data_payload.get('status', remote_squid_info.get('data',{}).get('status','visiting'))
        if 'status_text' in remote_squid_info and remote_squid_info['status_text']:
            remote_squid_info['status_text'].setPlainText(f"{new_status}")
            if remote_squid_info.get('was_arrival_text', False):
                remote_squid_info['status_text'].setDefaultTextColor(QtGui.QColor(200,200,200,230))
                remote_squid_info['status_text'].setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Normal))
                remote_squid_info['was_arrival_text'] = False
        
        if 'view_cone_visible' in squid_data_payload:
            if squid_data_payload['view_cone_visible']:
                self.update_remote_view_cone(node_id, squid_data_payload)
            elif remote_squid_info.get('view_cone') and remote_squid_info['view_cone'].scene():
                self.scene.removeItem(remote_squid_info['view_cone']); remote_squid_info['view_cone'] = None
        
        payload_dir_key = squid_data_payload.get('image_direction_key')
        payload_anim_frame = squid_data_payload.get('current_animation_frame', 1)
        potential_new_image_name, _ = self._get_image_file_name_and_direction(
            payload_dir_key, payload_anim_frame, None,
            remote_squid_info.get('current_image_name', 'right1.png')
        )
        
        if potential_new_image_name != remote_squid_info.get('current_image_name'):
            scaled_pixmap, (current_w, current_h) = self._get_scaled_pixmap(potential_new_image_name)
            visual_item.setPixmap(scaled_pixmap); visual_item.setScale(1.0) 
            remote_squid_info['current_display_dimensions'] = (current_w, current_h)
            remote_squid_info['current_image_name'] = potential_new_image_name
            if self.debug_mode: self.logger.debug(f"Updated image for {node_id} to {potential_new_image_name}, Size: {current_w}x{current_h}")
        return True

    def update_remote_squid(self, node_id, squid_data_payload, is_new_arrival=False):
        if not squid_data_payload:
            if self.debug_mode: self.logger.warning(f"No data for remote squid {node_id}")
            return False
        try:
            if is_new_arrival:
                entry_x, entry_y, entry_dir = self.calculate_entry_position(squid_data_payload)
                if node_id in self.remote_squids:
                    self._handle_re_arriving_squid(node_id, squid_data_payload, self.remote_squids[node_id], entry_x, entry_y, entry_dir)
                else:
                    self._handle_new_squid_arrival(node_id, squid_data_payload, entry_x, entry_y, entry_dir)
                if node_id in self.remote_squids:
                    self._create_arrival_animation(self.remote_squids[node_id]['visual'])
                    if squid_data_payload.get('view_cone_visible', False):
                        self.update_remote_view_cone(node_id, squid_data_payload)
            elif node_id in self.remote_squids:
                 self._handle_existing_squid_update(node_id, squid_data_payload, self.remote_squids[node_id])
            else: 
                if self.debug_mode: self.logger.warning(f"Update for unknown {node_id} (not new arrival). Ignoring.")
                return False

            if node_id in self.remote_squids:
                self.remote_squids[node_id]['data'].update(squid_data_payload)
                self.remote_squids[node_id]['last_update'] = time.time()
                return True
            elif is_new_arrival and node_id not in self.remote_squids: # Should have been added
                if self.debug_mode: self.logger.error(f"New arrival {node_id} not added to remote_squids.")
                return False
            return False 

        except Exception as e:
            self.logger.error(f"Error update_remote_squid for {node_id}: {e}", exc_info=True)
            if node_id in self.remote_squids and self.remote_squids[node_id].get('visual') and \
               not self.remote_squids[node_id]['visual'].scene():
                 self.logger.info(f"Cleanup partially processed squid {node_id} after error.")
                 self.remove_remote_squid(node_id)
            return False

    def calculate_entry_position(self, exit_data: dict) -> tuple[float, float, str]:
        original_exit_direction = exit_data.get('direction')
        original_exit_pos_x = exit_data.get('position', {}).get('x', 0)
        original_exit_pos_y = exit_data.get('position', {}).get('y', 0)
        squid_width_payload = int(exit_data.get('squid_width', 50))
        squid_height_payload = int(exit_data.get('squid_height', 50))
        current_window_width = self.window_width; current_window_height = self.window_height
        entry_x, entry_y = 0.0, 0.0; entry_direction_on_this_screen = "unknown"
        if original_exit_direction == 'right':
            entry_x = -squid_width_payload*0.8; entry_y = original_exit_pos_y; entry_direction_on_this_screen = "left"
        elif original_exit_direction == 'left':
            entry_x = current_window_width - squid_width_payload*0.2; entry_y = original_exit_pos_y; entry_direction_on_this_screen = "right"
        elif original_exit_direction == 'down':
            entry_y = -squid_height_payload*0.8; entry_x = original_exit_pos_x; entry_direction_on_this_screen = "top"
        elif original_exit_direction == 'up':
            entry_y = current_window_height - squid_height_payload*0.2; entry_x = original_exit_pos_x; entry_direction_on_this_screen = "bottom"
        else:
            entry_x = current_window_width/2 - squid_width_payload/2; entry_y = current_window_height/2 - squid_height_payload/2; entry_direction_on_this_screen = "center_fallback"
        if original_exit_direction in ['right','left']: entry_y = max(0, min(entry_y, current_window_height - squid_height_payload))
        if original_exit_direction in ['up','down']: entry_x = max(0, min(entry_x, current_window_width - squid_width_payload))
        node_id = exit_data.get('node_id')
        if node_id: self._last_calculated_entry_details[node_id] = {'entry_pos': (entry_x, entry_y), 'entry_direction': entry_direction_on_this_screen}
        return entry_x, entry_y, entry_direction_on_this_screen

    def get_last_calculated_entry_details(self, node_id: str) -> dict | None: return self._last_calculated_entry_details.get(node_id)
    def update_settings(self, opacity=None, show_labels=None, show_connections=None):
        if opacity is not None: self.remote_opacity = opacity
        current_target_opacity = self.remote_opacity
        for squid_data in self.remote_squids.values():
            if squid_data.get('visual'): squid_data['visual'].setOpacity(current_target_opacity)
        if show_labels is not None:
            self.show_labels = show_labels
            for squid_data in self.remote_squids.values():
                if squid_data.get('id_text'): squid_data['id_text'].setVisible(show_labels)
                if squid_data.get('status_text'): squid_data['status_text'].setVisible(show_labels)
        if show_connections is not None:
            self.show_connections = show_connections
            for line in self.connection_lines.values(): # Values, not items() for direct line objects
                if line.scene(): line.setVisible(show_connections)

    def update_remote_view_cone(self, node_id, squid_data):
        if node_id not in self.remote_squids: return
        remote_squid_info = self.remote_squids[node_id]; visual_item = remote_squid_info.get('visual')
        if not visual_item: return
        if remote_squid_info.get('view_cone') and remote_squid_info['view_cone'].scene(): self.scene.removeItem(remote_squid_info['view_cone'])
        remote_squid_info['view_cone'] = None
        if not squid_data.get('view_cone_visible', False): return
        squid_visual_pos = visual_item.pos() # Uses current visual position
        display_dims = remote_squid_info.get('current_display_dimensions')
        if not display_dims: pixmap = visual_item.pixmap(); display_dims = (pixmap.width(), pixmap.height()) if not pixmap.isNull() else self.DEFAULT_IMAGE_DIMENSION
        current_w, current_h = display_dims; item_scale = visual_item.scale()
        squid_center_x = squid_visual_pos.x()+(current_w/2*item_scale); squid_center_y = squid_visual_pos.y()+(current_h/2*item_scale)
        looking_direction_rad=squid_data.get('looking_direction',0.0); view_cone_angle_rad=squid_data.get('view_cone_angle',math.radians(50))
        cone_length=squid_data.get('view_cone_length',150); cone_half_angle=view_cone_angle_rad/2.0
        p1=QtCore.QPointF(squid_center_x,squid_center_y)
        p2=QtCore.QPointF(squid_center_x+cone_length*math.cos(looking_direction_rad-cone_half_angle),squid_center_y+cone_length*math.sin(looking_direction_rad-cone_half_angle))
        p3=QtCore.QPointF(squid_center_x+cone_length*math.cos(looking_direction_rad+cone_half_angle),squid_center_y+cone_length*math.sin(looking_direction_rad+cone_half_angle))
        cone_poly=QtGui.QPolygonF([p1,p2,p3]); cone_item=QtWidgets.QGraphicsPolygonItem(cone_poly)
        color_tuple=squid_data.get('color',(150,150,255)); q_color=QtGui.QColor(*color_tuple) if isinstance(color_tuple,tuple) else QtGui.QColor(150,150,255)
        cone_item.setPen(QtGui.QPen(QtGui.QColor(q_color.red(),q_color.green(),q_color.blue(),0)))
        cone_item.setBrush(QtGui.QBrush(QtGui.QColor(q_color.red(),q_color.green(),q_color.blue(),25)))
        cone_item.setZValue(visual_item.zValue()-1); self.scene.addItem(cone_item); remote_squid_info['view_cone']=cone_item

    def _create_arrival_animation(self, visual_item):
        if hasattr(visual_item, 'setOpacity'): visual_item.setOpacity(self.remote_opacity)
        if hasattr(visual_item, 'setScale'): visual_item.setScale(1.0)
    def _reset_remote_squid_style(self, visual_item_or_node_id): # Full method
        node_id=None; squid_display_data=None
        if isinstance(visual_item_or_node_id,str): node_id=visual_item_or_node_id; squid_display_data=self.remote_squids.get(node_id)
        elif isinstance(visual_item_or_node_id,QtWidgets.QGraphicsPixmapItem):
            for nid,s_data in self.remote_squids.items():
                if s_data.get('visual')==visual_item_or_node_id: node_id=nid; squid_display_data=s_data; break
        if not squid_display_data: return
        visual_item=squid_display_data.get('visual'); status_text_item=squid_display_data.get('status_text')
        if visual_item: visual_item.setZValue(5); visual_item.setOpacity(self.remote_opacity); visual_item.setScale(1.0); visual_item.setGraphicsEffect(None)
        if status_text_item:
            current_status=squid_display_data.get('data',{}).get('status','visiting').upper()
            if squid_display_data.get('was_arrival_text',False) and current_status not in ["ENTERING...","ARRIVING...",squid_display_data.get('data',{}).get('status','visiting').upper()]:
                status_text_item.setDefaultTextColor(QtGui.QColor(200,200,200,230)); status_text_item.setFont(QtGui.QFont("Arial",10,QtGui.QFont.Normal))
                status_text_item.setPlainText(squid_display_data.get('data',{}).get('status','visiting')); squid_display_data['was_arrival_text']=False
            status_text_item.setZValue(visual_item.zValue()+1 if visual_item else 6)

    def remove_remote_squid(self, node_id): # Full method
        if node_id not in self.remote_squids: return
        squid_data=self.remote_squids.pop(node_id)
        for key in ['visual','view_cone','id_text','status_text']:
            item=squid_data.get(key)
            if item and item.scene():item.scene().removeItem(item)
            if key in ['id_text','status_text'] and hasattr(self,'text_pool') and item in self.text_pool.in_use:self.text_pool.release(item)
        if node_id in self.connection_lines:
            line=self.connection_lines.pop(node_id)
            if line.scene():line.scene().removeItem(line)
        if self.debug_mode:self.logger.info(f"Removed remote squid {node_id}.")
    def cleanup_stale_entities(self, timeout=20.0): # Full method
        now=time.time()
        stale_squids=[nid for nid,data in self.remote_squids.items() if now-data.get('last_update',0)>timeout]
        for nid in stale_squids:self.remove_remote_squid(nid)
        stale_objs=[oid for oid,data in self.remote_objects.items() if now-data.get('last_update',0)>timeout]
        for oid in stale_objs:self.remove_remote_object(oid)
        if stale_squids or stale_objs and self.debug_mode:self.logger.debug(f"Stale cleanup: Removed {len(stale_squids)} squids, {len(stale_objs)} objects.")
        return len(stale_squids),len(stale_objs)

    def remove_remote_object(self, obj_id): # Full method
        if obj_id not in self.remote_objects:return
        obj_data=self.remote_objects.pop(obj_id)
        visual=obj_data.get('visual')
        if visual and visual.scene():visual.scene().removeItem(visual)
        if self.debug_mode:self.logger.debug(f"Removed remote object {obj_id}")
    def cleanup_all(self): # Full method
        for nid in list(self.remote_squids.keys()):self.remove_remote_squid(nid)
        for oid in list(self.remote_objects.keys()):self.remove_remote_object(oid)
        for line_id in list(self.connection_lines.keys()):
            line=self.connection_lines.pop(line_id)
            if line.scene():self.scene().removeItem(line)
        if hasattr(self,'text_pool'):self.text_pool.clear()
        if self.debug_mode:self.logger.info("RemoteEntityManager: All entities cleaned up.")

    def update_connection_lines(self, local_squid_pos_tuple): # Full method
        if not self.show_connections:
            for node_id,line in list(self.connection_lines.items()):
                if line.scene():self.scene.removeItem(line); del self.connection_lines[node_id]
            return
        if not local_squid_pos_tuple or len(local_squid_pos_tuple)!=2:return
        lx,ly=local_squid_pos_tuple; active_nodes=set()
        for node_id,squid_info in self.remote_squids.items():
            visual=squid_info.get('visual')
            if not visual or not visual.isVisible() or not visual.scene():continue
            active_nodes.add(node_id); r_pos=visual.pos()
            dims=squid_info.get('current_display_dimensions')
            if not dims:pixmap=visual.pixmap();dims=(pixmap.width(),pixmap.height()) if not pixmap.isNull() else self.DEFAULT_IMAGE_DIMENSION
            w,h=dims; scale=visual.scale()
            rx=r_pos.x()+(w/2*scale); ry=r_pos.y()+(h/2*scale)
            color_tuple=squid_info.get('data',{}).get('color',(100,100,255)); q_color=QtGui.QColor(*color_tuple) if isinstance(color_tuple,tuple) else QtGui.QColor(100,100,255)
            if node_id in self.connection_lines:
                line=self.connection_lines[node_id]
                if not line.scene():self.scene.addItem(line)
                line.setLine(lx,ly,rx,ry);pen=line.pen();pen.setColor(QtGui.QColor(q_color.red(),q_color.green(),q_color.blue(),100));line.setPen(pen);line.setVisible(True)
            else:
                line=QtWidgets.QGraphicsLineItem(lx,ly,rx,ry)
                pen=QtGui.QPen(QtGui.QColor(q_color.red(),q_color.green(),q_color.blue(),100));pen.setWidth(1);pen.setStyle(QtCore.Qt.SolidLine)
                line.setPen(pen);line.setZValue(-10);line.setVisible(True);self.scene.addItem(line);self.connection_lines[node_id]=line
        for node_id in list(self.connection_lines.keys()):
            if node_id not in active_nodes:
                if self.connection_lines[node_id].scene():self.scene.removeItem(self.connection_lines[node_id]);del self.connection_lines[node_id]