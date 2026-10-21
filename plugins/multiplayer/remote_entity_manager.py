from PyQt5 import QtCore, QtGui, QtWidgets
import os
import time
import math
from typing import Dict, Any, Optional, List
import logging
import base64

from .identity import SquidIdentity

# Keep one Qt base: combining QGraphicsPixmapItem and QObject gives the
# same wrapper two C++ owners and can crash when a departed visitor is freed.
class AnimatableGraphicsItem(QtWidgets.QGraphicsPixmapItem):
    def __init__(self, pixmap=None, parent=None):
        QtWidgets.QGraphicsPixmapItem.__init__(self, pixmap, parent)
        self._scale = 1.0
    @property
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

        #: Fight clouds on screen, one per pair of squid, keyed by the
        #: other squid's uuid.
        self._fight_clouds = {}
        self._scuffles = {}
        #: Objects flashing dark red because two squid are fighting over them.
        self._contest_flashes = {}
        #: Mating hearts on screen, the same way.
        self._mating_hearts = {}

        self.position_update_timer = QtCore.QTimer()
        self.position_update_timer.timeout.connect(self._update_visuals_once_per_second)
        self.MOVEMENT_INTERVAL_MS = 1000  # Update once per second
        self.MAX_PIXELS_PER_JUMP = 90.0
        self.position_update_timer.start(self.MOVEMENT_INTERVAL_MS)

        #: The resident's swim frame (its Squid.current_frame, 0 or 1), or
        #: None; set by the plugin. A visitor always swims on the other one.
        self.resident_frame = None
        self._last_resident_frame = None
        self.swim_timer = QtCore.QTimer()
        self.swim_timer.timeout.connect(self._swim)
        self.swim_timer.start(self.SWIM_POLL_MS)

    def _get_image_file_name_and_direction(self, payload_direction_key: Optional[str], payload_animation_frame: Any, 
                                          entry_direction_on_this_screen: Optional[str] = None, 
                                          current_image_name_for_fallback_dir: str = "right1.png") -> tuple[str, str]:
        
        base_direction = "right" 
        if payload_direction_key:
            base_direction = payload_direction_key.lower().strip()
        else:
            if self.debug_mode:
                self.logger.warning(f"_get_image_file_name_and_direction: payload_direction_key is missing. Defaulting to '{base_direction}'. Fallback hint: {current_image_name_for_fallback_dir}")
        
        facing_direction = base_direction

        if entry_direction_on_this_screen:
            original_facing_for_log = facing_direction
            if entry_direction_on_this_screen == "left":
                facing_direction = "right"
            elif entry_direction_on_this_screen == "right":
                facing_direction = "left"
            elif entry_direction_on_this_screen == "bottom": # Enters from bottom, should face up
                facing_direction = "up"
            elif entry_direction_on_this_screen == "top":    # Enters from top, should face down
                facing_direction = "down" # Directly use "down" as it's valid since 'down1.png' exists
            
            if self.debug_mode and original_facing_for_log != facing_direction:
                self.logger.debug(f"_get_image_file_name_and_direction: Arrival adjustment. Entry: {entry_direction_on_this_screen}. Original Payload Facing: {original_facing_for_log}. New Visual Facing: {facing_direction}")

        # Valid sprite directions, now including "down" as per your confirmation
        valid_sprite_directions = ["left", "right", "up", "down"] 
        
        if facing_direction not in valid_sprite_directions:
            if self.debug_mode:
                self.logger.warning(f"_get_image_file_name_and_direction: Attempted facing_direction '{facing_direction}' is not in {valid_sprite_directions}. Defaulting to 'right'.")
            facing_direction = "right"

        try:
            frame = int(payload_animation_frame)
            if frame not in [1, 2]: # Assuming animation frames are 1 and 2
                if self.debug_mode and payload_animation_frame not in [1,2]: 
                    self.logger.warning(f"_get_image_file_name_and_direction: Invalid animation frame '{payload_animation_frame}'. Defaulting to 1.")
                frame = 1
        except (ValueError, TypeError):
            if self.debug_mode:
                 self.logger.warning(f"_get_image_file_name_and_direction: Animation frame '{payload_animation_frame}' is not a valid integer. Defaulting to 1.")
            frame = 1
        
        image_file_name = f"{facing_direction}{frame}.png"
        
        if self.debug_mode:
            self.logger.debug(f"_get_image_file_name_and_direction: Args(PayloadDirKey='{payload_direction_key}', EntryDir='{entry_direction_on_this_screen}', AnimFrame='{payload_animation_frame}') -> Result(BaseDir='{base_direction}', FinalFacing='{facing_direction}', Image='{image_file_name}')")
            
        return image_file_name, facing_direction

    def _get_scaled_pixmap(self, image_file_name: str) -> tuple[QtGui.QPixmap, tuple[int, int]]:
        target_width, target_height = self.IMAGE_DIMENSIONS.get(image_file_name, self.DEFAULT_IMAGE_DIMENSION)
        # Drawn at the resident's scale, so a visitor is not bigger than its host
        # on a 1080p screen, nor twice its size on a Retina Mac.
        from src.display_scaling import DisplayScaling
        scale = DisplayScaling.squid_scale()
        target_width, target_height = int(target_width * scale), int(target_height * scale)
        if (target_width, target_height) == self.DEFAULT_IMAGE_DIMENSION and image_file_name not in self.IMAGE_DIMENSIONS:
            if self.debug_mode: self.logger.warning(f"Image file '{image_file_name}' not in IMAGE_DIMENSIONS. Using default: {self.DEFAULT_IMAGE_DIMENSION}")
        
        image_path = os.path.join(self.images_folder_root_path, image_file_name)
        pixmap = QtGui.QPixmap(image_path)
        if pixmap.isNull():
            if self.debug_mode: self.logger.error(f"Image {image_path} not found. Fallback gray pixmap {target_width}x{target_height}.")
            fb_pixmap = QtGui.QPixmap(target_width, target_height); fb_pixmap.fill(QtCore.Qt.gray)
            return fb_pixmap, (target_width, target_height) 
        return pixmap.scaled(target_width, target_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation), (target_width, target_height)

    # ------------------------------------------------------------------
    # Swimming: every squid in the tank animates, never in step
    # ------------------------------------------------------------------
    #: How often the resident's frame is looked at.
    SWIM_POLL_MS = 100
    #: A visitor turns its own frame over when the resident has not for this
    #: long - a still resident does not stop a visitor swimming.
    SWIM_SECONDS = 1.0

    def _resident_swim_frame(self):
        try:
            frame = self.resident_frame() if callable(self.resident_frame) else None
        except Exception:
            return None
        return frame if frame in (0, 1) else None

    @staticmethod
    def _shown_frame(info) -> int:
        """The swim frame (1 or 2) a remote squid is drawn with now."""
        name = str(info.get('current_image_name') or 'right1.png')
        return 2 if name[:-4].endswith('2') else 1

    def _other_frame(self) -> int:
        """The frame a visitor should show: the one the resident is not."""
        resident = self._resident_swim_frame()
        return 1 if resident is None else (2 if resident == 0 else 1)

    def _show_frame(self, info, frame: int) -> None:
        name = str(info.get('current_image_name') or 'right1.png')
        stem = name[:-4].rstrip('12') or 'right'
        new_name = f"{stem}{frame}.png"
        if new_name == name or info.get('visual') is None:
            return
        pixmap, size = self._get_scaled_pixmap(new_name)
        info['visual'].setPixmap(pixmap)
        info['current_image_name'] = new_name
        info['current_display_dimensions'] = size

    def _swim(self):
        """Each visitor uses both swim frames, always the resident's other one.

        When the resident's frame turns over, every visitor's follows it onto
        the opposite frame; when the resident is still, a visitor turns its own
        over each SWIM_SECONDS. Drawing only - nothing about any squid changes.
        """
        resident = self._resident_swim_frame()
        turned = resident is not None and resident != self._last_resident_frame
        self._last_resident_frame = resident
        now = time.monotonic()
        for info in list(self.remote_squids.values()):
            visual = info.get('visual')
            if visual is None or not visual.isVisible():
                continue
            if turned:
                self._show_frame(info, self._other_frame())
                info['swum_at'] = now
            elif now - info.get('swum_at', 0.0) >= self.SWIM_SECONDS:
                self._show_frame(info, 3 - self._shown_frame(info))
                info['swum_at'] = now

    def follow_body(self, node_id, x: float, y: float, facing: Optional[str] = None) -> bool:
        """A visitor's body is in this tank: draw it where the host has it.

        Its home keeps sending object_sync from where its body is frozen at
        home; drawn from that, the visitor stayed by the glass while its body
        - what the host simulates, and what the resident's eyes see - moved.
        """
        info = self.remote_squids.get(node_id)
        if not info or info.get('visual') is None:
            return False
        info['in_tank_body'] = True
        info['network_target_x'], info['network_target_y'] = float(x), float(y)
        if facing in ('left', 'right'):
            name = f"{facing}{self._shown_frame(info)}.png"
            if name != info.get('current_image_name'):
                pixmap, size = self._get_scaled_pixmap(name)
                info['visual'].setPixmap(pixmap)
                info['current_image_name'] = name
                info['current_display_dimensions'] = size
        return True

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

    @staticmethod
    def _label(node_id, payload):
        """The visitor's name, as cleaned by SquidIdentity; its node otherwise."""
        identity = SquidIdentity.from_payload((payload or {}).get('identity'))
        return identity.name if identity else f"Remote ({node_id[-4:]})"

    def _handle_new_squid_arrival(self, node_id, squid_data_payload, entry_x, entry_y, entry_direction_on_this_screen):
        if self.debug_mode:
            self.logger.debug(f"_handle_new_squid_arrival: NodeID='{node_id}', EntryPos=({entry_x:.1f},{entry_y:.1f}), EntryDir='{entry_direction_on_this_screen}'")
            self.logger.debug(f"Payload for new arrival '{node_id}': {squid_data_payload}")

        payload_dir_key = squid_data_payload.get('image_direction_key', 'right')
        # Its swim frame is drawn here, the resident's other one (_swim).
        payload_anim_frame = self._other_frame()
        
        squid_image_name, determined_facing_direction = self._get_image_file_name_and_direction(
            payload_dir_key, 
            payload_anim_frame, 
            entry_direction_on_this_screen=entry_direction_on_this_screen 
        )
        
        scaled_pixmap, (current_w, current_h) = self._get_scaled_pixmap(squid_image_name)
        
        if self.debug_mode:
            self.logger.debug(f"_handle_new_squid_arrival '{node_id}': Image selected='{squid_image_name}', Determined Facing='{determined_facing_direction}', Size=({current_w}x{current_h})")

        remote_visual = AnimatableGraphicsItem(scaled_pixmap)
        remote_visual.setPos(entry_x, entry_y)
        remote_visual.setZValue(5)
        remote_visual.setOpacity(self.remote_opacity)
        remote_visual.setScale(1.0)
        # Another squid, to this tank's resident's eyes: the vision system
        # sees it exactly as it sees food or a rock (vision_worker).
        remote_visual.category = 'squid'
        self.scene.addItem(remote_visual)

        id_text = self.text_pool.acquire()
        if id_text.scene() != self.scene: 
            if id_text.scene(): id_text.scene().removeItem(id_text)
            self.scene.addItem(id_text)
        id_text.setPlainText(self._label(node_id, squid_data_payload))
        id_text.setDefaultTextColor(QtGui.QColor(200,200,200,200))
        id_text.setFont(QtGui.QFont("Arial", 8))
        id_text.setZValue(6) 
        id_text.setVisible(self.show_labels)

        status_text = self.text_pool.acquire()
        if status_text.scene() != self.scene:
            if status_text.scene(): status_text.scene().removeItem(status_text)
            self.scene.addItem(status_text)
        status_text.setPlainText("ENTERING...") 
        status_text.setDefaultTextColor(QtGui.QColor(255,255,0)) 
        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        status_text.setZValue(6)
        status_text.setVisible(self.show_labels)
        
        self._update_dependent_items_position({'id_text': id_text, 'status_text': status_text}, entry_x, entry_y)

        self.remote_squids[node_id] = {
            'visual': remote_visual, 
            'id_text': id_text, 
            'status_text': status_text,
            'view_cone': None, 
            'last_update': time.time(),
            'data': squid_data_payload.copy(), 
            'current_display_dimensions': (current_w, current_h),
            'current_image_name': squid_image_name,
            'was_arrival_text': True, 
            'network_target_x': entry_x, 
            'network_target_y': entry_y
        }
        if self.debug_mode:
            self.logger.info(f"REMOTE_ENTITY_MANAGER: Created NEW remote squid '{node_id}' at ({entry_x:.1f}, {entry_y:.1f}). Image: '{squid_image_name}', Size: {current_w}x{current_h}")

    def _handle_re_arriving_squid(self, node_id, squid_data_payload, remote_squid_info, entry_x, entry_y, entry_direction_on_this_screen):
        if self.debug_mode:
            self.logger.debug(f"_handle_re_arriving_squid: NodeID='{node_id}', EntryPos=({entry_x:.1f},{entry_y:.1f}), EntryDir='{entry_direction_on_this_screen}'")
            self.logger.debug(f"Payload for re-arriving '{node_id}': {squid_data_payload}")

        visual_item = remote_squid_info['visual']
        visual_item.setPos(entry_x, entry_y)
        visual_item.setOpacity(self.remote_opacity) 
        visual_item.setVisible(True)
        visual_item.setScale(1.0) 

        payload_dir_key = squid_data_payload.get('image_direction_key', 'right')
        payload_anim_frame = self._other_frame()
        current_img_name_fallback = remote_squid_info.get('current_image_name', 'right1.png')

        new_squid_image_name, determined_facing_direction = self._get_image_file_name_and_direction(
            payload_dir_key, 
            payload_anim_frame, 
            entry_direction_on_this_screen=entry_direction_on_this_screen,
            current_image_name_for_fallback_dir=current_img_name_fallback
        )
        scaled_pixmap, (current_w, current_h) = self._get_scaled_pixmap(new_squid_image_name)
        visual_item.setPixmap(scaled_pixmap)
        
        if self.debug_mode:
            self.logger.debug(f"_handle_re_arriving_squid '{node_id}': Image selected='{new_squid_image_name}', Determined Facing='{determined_facing_direction}', Size=({current_w}x{current_h})")

        remote_squid_info['current_display_dimensions'] = (current_w, current_h)
        remote_squid_info['current_image_name'] = new_squid_image_name
        remote_squid_info['network_target_x'] = entry_x 
        remote_squid_info['network_target_y'] = entry_y
        
        status_item = remote_squid_info.get('status_text')
        if status_item:
            status_item.setPlainText("ENTERING...")
            status_item.setDefaultTextColor(QtGui.QColor(255,255,0)) 
            status_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
            status_item.setVisible(self.show_labels) 
        
        id_item = remote_squid_info.get('id_text')
        if id_item: 
            id_item.setVisible(self.show_labels)

        self._update_dependent_items_position(remote_squid_info, entry_x, entry_y)
        remote_squid_info['was_arrival_text'] = True 
        
        if self.debug_mode:
            self.logger.info(f"REMOTE_ENTITY_MANAGER: Re-initialized RE-ARRIVING squid '{node_id}' at ({entry_x:.1f}, {entry_y:.1f}). Image: '{new_squid_image_name}', Size: {current_w}x{current_h}")

    def _handle_existing_squid_update(self, node_id, squid_data_payload, remote_squid_info):
        if self.debug_mode:
            log_payload = {
                'x': squid_data_payload.get('x'), 'y': squid_data_payload.get('y'),
                'image_direction_key': squid_data_payload.get('image_direction_key'),
                'current_animation_frame': squid_data_payload.get('current_animation_frame'),
                'status': squid_data_payload.get('status'),
                'view_cone_visible': squid_data_payload.get('view_cone_visible')
            }
            self.logger.debug(f"_handle_existing_squid_update: NodeID='{node_id}'. Payload essentials: {log_payload}")

        network_x = squid_data_payload.get('x')
        network_y = squid_data_payload.get('y')
        if remote_squid_info.get('in_tank_body'):
            # Its body is in this tank (follow_body): where it is and which
            # way it faces are the host's to say, not its frozen home's.
            network_x = network_y = None
            squid_data_payload = {k: v for k, v in squid_data_payload.items()
                                  if k not in ('image_direction_key', 'direction')}
            squid_data_payload['image_direction_key'] = \
                str(remote_squid_info.get('current_image_name', 'right1.png'))[:-5] or 'right'

        if network_x is not None and network_y is not None:
            remote_squid_info['network_target_x'] = network_x
            remote_squid_info['network_target_y'] = network_y
        else:
            if self.debug_mode:
                self.logger.warning(f"_handle_existing_squid_update '{node_id}': Update missing x or y coordinates. Target position not updated.")

        visual_item = remote_squid_info.get('visual')
        if not visual_item:
            if self.debug_mode:
                self.logger.error(f"_handle_existing_squid_update '{node_id}': Visual item not found! Cannot update.")
            return False

        new_status_from_payload = squid_data_payload.get('status', remote_squid_info.get('data',{}).get('status','visiting'))
        status_text_item = remote_squid_info.get('status_text')
        if status_text_item:
            if status_text_item.toPlainText().upper() != new_status_from_payload.upper() or remote_squid_info.get('was_arrival_text', False): # Case-insensitive compare for current text
                status_text_item.setPlainText(new_status_from_payload.upper())
                if remote_squid_info.get('was_arrival_text', False) or "ENTERING" in status_text_item.toPlainText(): 
                    status_text_item.setDefaultTextColor(QtGui.QColor(200,200,200,230)) 
                    status_text_item.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Normal)) 
                    remote_squid_info['was_arrival_text'] = False
            status_text_item.setVisible(self.show_labels)
        
        if 'view_cone_visible' in squid_data_payload: 
            if squid_data_payload['view_cone_visible']:
                self.update_remote_view_cone(node_id, squid_data_payload) 
            elif remote_squid_info.get('view_cone') and remote_squid_info['view_cone'].scene():
                self.scene.removeItem(remote_squid_info['view_cone'])
                remote_squid_info['view_cone'] = None
        
        payload_dir_key = squid_data_payload.get('image_direction_key') 
        # Facing comes from home; the swim frame is drawn here (_swim).
        payload_anim_frame = self._shown_frame(remote_squid_info)
        current_img_name_fallback = remote_squid_info.get('current_image_name', 'right1.png')

        potential_new_image_name, determined_facing_direction = self._get_image_file_name_and_direction(
            payload_dir_key, 
            payload_anim_frame,
            entry_direction_on_this_screen=None, 
            current_image_name_for_fallback_dir=current_img_name_fallback
        )
        
        if potential_new_image_name != remote_squid_info.get('current_image_name'):
            scaled_pixmap, (current_w, current_h) = self._get_scaled_pixmap(potential_new_image_name)
            visual_item.setPixmap(scaled_pixmap) 
            
            remote_squid_info['current_display_dimensions'] = (current_w, current_h)
            remote_squid_info['current_image_name'] = potential_new_image_name
            if self.debug_mode:
                self.logger.debug(f"_handle_existing_squid_update '{node_id}': Image CHANGED to '{potential_new_image_name}', New Facing='{determined_facing_direction}', Size=({current_w}x{current_h})")
        
        return True

    def update_remote_squid(self, node_id, squid_data_payload, is_new_arrival=False):
        if self.debug_mode:
            arrival_status = "NEW ARRIVAL" if is_new_arrival else "EXISTING SQUID UPDATE"
            self.logger.debug(f"update_remote_squid CALLED: NodeID='{node_id}', Status='{arrival_status}'")
            # Avoid logging full payload if too verbose, log key parts or hash if necessary
            # For now, logging essential keys to understand context:
            log_payload_essentials = {
                'x': squid_data_payload.get('x'), 'y': squid_data_payload.get('y'),
                'image_direction_key': squid_data_payload.get('image_direction_key'),
                'status': squid_data_payload.get('status'),
                'node_id_in_payload': squid_data_payload.get('node_id') # verify it matches argument node_id
            }
            self.logger.debug(f"Payload essentials for '{node_id}': {log_payload_essentials}")

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

    def show_notice_icon(self, node_id: str, duration_ms: int = 3000) -> bool:
        """Flash the exclamation icon above a visiting squid.

        The visitor's own body is on this screen, so this is where its "I have
        noticed you" has to be drawn - its real squid is hidden in its own tank
        for the duration of the visit. Same artwork the resident uses, so the
        two squid noticing each other reads as one event.
        """
        info = self.remote_squids.get(node_id)
        if not info or not info.get('visual'):
            return False
        icon = info.get('notice_icon')
        if icon is None:
            pixmap = QtGui.QPixmap(os.path.join("images", "curious.png"))
            if pixmap.isNull():
                return False
            icon = QtWidgets.QGraphicsPixmapItem(pixmap)
            icon.setZValue(500)
            self.scene.addItem(icon)
            info['notice_icon'] = icon
        visual = info['visual']
        icon.setPos(visual.x() + visual.boundingRect().width() / 2
                    - icon.pixmap().width() / 2,
                    visual.y() - 100)
        icon.setVisible(True)
        QtCore.QTimer.singleShot(duration_ms,
                                 lambda: self.hide_notice_icon(node_id))
        return True

    def hide_notice_icon(self, node_id: str) -> None:
        info = self.remote_squids.get(node_id)
        if not info:
            return
        icon = info.pop('notice_icon', None)
        if icon is not None and icon.scene() is self.scene:
            self.scene.removeItem(icon)

    #: The animated cloud drawn over a scuffle, from the game's images folder.
    FIGHT_CLOUD_FILE = "fight_cloud.gif"
    FIGHT_CLOUD_MS = 2500
    #: The beating heart drawn over a pair that has just mated.
    MATING_HEART_FILE = "mating_heart.gif"
    MATING_HEART_MS = 3200

    #: A fight over an object: the object flashes dark red for this long
    #: before the bodies come together, and for this long after the scuffle.
    CONTEST_LEAD_MS = 2000
    CONTEST_AFTER_MS = 2000
    CONTEST_FLASH_MS = 250
    CONTEST_RED = (110, 0, 0)
    #: The scuffle itself: bodies close in (650 ms), then the cloud.
    SCUFFLE_MS = 3150

    def start_fight_sequence(self, key, node_id, resident, actor, on_finished=None,
                             contested=None):
        """Bring both bodies together before playing one cloud over the pair.

        A fight over an object (`contested`, a scene item) opens with a lead-in:
        the object flashes dark red for CONTEST_LEAD_MS before the bodies
        close in, and on until CONTEST_AFTER_MS after the scuffle.
        """
        if key in self._scuffles:
            return True
        info = self.remote_squids.get(node_id)
        if not info or not info.get('visual'):
            return False
        if contested is not None and self.flash_contested(
                contested, self.CONTEST_LEAD_MS + self.SCUFFLE_MS + self.CONTEST_AFTER_MS):
            # Held while the object flashes; the bodies come together after.
            self._scuffles[key] = {'timer': None, 'resident': resident,
                                   'was_moving': getattr(resident, 'can_move', True),
                                   'on_finished': on_finished, 'waiting': True}
            QtCore.QTimer.singleShot(self.CONTEST_LEAD_MS, lambda: self._begin_scuffle(
                key, info, resident, actor, on_finished, after_lead=True))
            return True
        return self._begin_scuffle(key, info, resident, actor, on_finished)

    def _begin_scuffle(self, key, info, resident, actor, on_finished, after_lead=False):
        if after_lead:
            held = self._scuffles.get(key)
            if held is None or not held.get('waiting'):
                return False                 # ended during the lead-in
            del self._scuffles[key]
        visual = info['visual']
        try:
            if visual.scene() is not self.scene:
                return False
        except RuntimeError:
            return False
        initial = (float(resident.squid_x), float(resident.squid_y), float(actor.x), float(actor.y))
        mx, my = (initial[0]+initial[2])/2, (initial[1]+initial[3])/2
        moving = getattr(resident, 'can_move', True)
        resident.can_move = False
        clock = QtCore.QElapsedTimer()
        clock.start()
        timer = QtCore.QTimer()
        entry = {'timer': timer, 'resident': resident, 'was_moving': moving,
                 'on_finished': on_finished}
        self._scuffles[key] = entry

        def tick():
            if key not in self._scuffles:
                return
            elapsed = clock.elapsed()
            if visual.scene() is not self.scene or getattr(getattr(resident, 'lifecycle', None), 'is_dead', False):
                self._end_scuffle(key)
                return
            progress = min(1., elapsed / 650.)
            progress = progress * progress * (3-2*progress)
            resident.squid_x = initial[0] + (mx-20-initial[0])*progress
            resident.squid_y = initial[1] + (my-initial[1])*progress
            actor.x = initial[2] + (mx+20-initial[2])*progress
            actor.y = initial[3] + (my-initial[3])*progress
            resident.squid_item.setPos(resident.squid_x, resident.squid_y)
            visual.setPos(actor.x, actor.y)
            info['network_target_x'], info['network_target_y'] = actor.x, actor.y
            self._update_dependent_items_position(info, actor.x, actor.y)
            if elapsed >= 650 and not entry.get('cloud'):
                entry['cloud'] = True
                cx = mx + visual.boundingRect().width()/2
                cy = my + visual.boundingRect().height()/2
                self.show_fight_cloud(key, cx, cy)
            if elapsed >= 3150:
                self._end_scuffle(key, completed=True)
        timer.timeout.connect(tick)
        timer.start(16)
        tick()
        return True

    def _end_scuffle(self, key, completed=False):
        entry = self._scuffles.pop(key, None)
        if entry:
            if entry.get('timer') is not None:      # None: still in its lead-in
                entry['timer'].stop()
            resident = entry['resident']
            if not getattr(getattr(resident, 'lifecycle', None), 'is_dead', False):
                resident.can_move = entry['was_moving']
        self.hide_fight_cloud(key)
        if entry and completed and entry.get('on_finished'):
            entry['on_finished']()

    def flash_contested(self, item, duration_ms: int) -> bool:
        """The object two squid are fighting over flashes dark red.

        A drawing only: a colourise effect switched on and off every
        CONTEST_FLASH_MS, then put back as it was. An object that already
        shows another kind of effect is left alone; one that leaves the tank
        stops flashing. Flashing an object again extends it.
        """
        try:
            if item is None or item.scene() is not self.scene:
                return False
            existing = item.graphicsEffect()
        except (AttributeError, RuntimeError):
            return False
        key = id(item)
        clock_now = QtCore.QDateTime.currentMSecsSinceEpoch()
        flash = self._contest_flashes.get(key)
        if flash is not None:
            flash['until'] = max(flash['until'], clock_now + int(duration_ms))
            return True
        if existing is not None and not isinstance(existing, QtWidgets.QGraphicsColorizeEffect):
            return False
        if existing is None:
            effect, restore = QtWidgets.QGraphicsColorizeEffect(), None
            item.setGraphicsEffect(effect)
        else:
            effect, restore = existing, (QtGui.QColor(existing.color()), existing.strength())
        effect.setColor(QtGui.QColor(*self.CONTEST_RED))
        effect.setStrength(1.0)
        timer = QtCore.QTimer()
        flash = {'item': item, 'effect': effect, 'restore': restore, 'timer': timer,
                 'until': clock_now + int(duration_ms), 'on': True}
        self._contest_flashes[key] = flash

        def tick():
            try:
                if (item.scene() is not self.scene
                        or QtCore.QDateTime.currentMSecsSinceEpoch() >= flash['until']):
                    self._end_contest_flash(key)
                    return
                flash['on'] = not flash['on']
                effect.setStrength(1.0 if flash['on'] else 0.0)
            except RuntimeError:
                self._end_contest_flash(key)
        timer.timeout.connect(tick)
        timer.start(self.CONTEST_FLASH_MS)
        return True

    def _end_contest_flash(self, key) -> None:
        flash = self._contest_flashes.pop(key, None)
        if flash is None:
            return
        flash['timer'].stop()
        item, effect, restore = flash['item'], flash['effect'], flash['restore']
        try:
            if restore is None:
                if item.graphicsEffect() is effect:
                    item.setGraphicsEffect(None)
            else:
                effect.setColor(restore[0])
                effect.setStrength(restore[1])
        except RuntimeError:
            pass

    def show_fight_cloud(self, key: str, x: float, y: float,
                         duration_ms: int = FIGHT_CLOUD_MS) -> bool:
        """One animated cloud over two squid that are about to scuffle.

        One cloud for the pair, centred between them - not one per squid. A
        cloud already showing for this pair is moved rather than doubled.
        Purely a drawing: it changes nothing about either squid. Returns False
        and draws nothing if the GIF is not installed.
        """
        # The GIF includes distant puffs. Scale its central cloud to obscure
        # the pair, with room for the outer puffs without filling the tank.
        return self._show_overlay(self._fight_clouds, key, self.FIGHT_CLOUD_FILE,
                                  x, y, duration_ms, QtCore.QSize(720, 840))

    def hide_fight_cloud(self, key: str) -> None:
        self._hide_overlay(self._fight_clouds, key)

    def show_mating_heart(self, key: str, x: float, y: float,
                          duration_ms: int = MATING_HEART_MS) -> bool:
        """One beating heart over two squid that have just mated.

        The fight cloud's counterpart: one heart for the pair, centred between
        them, and purely a drawing. Shown at the GIF's own size so its pixels
        stay crisp. Returns False and draws nothing if the GIF is not installed.
        """
        return self._show_overlay(self._mating_hearts, key, self.MATING_HEART_FILE,
                                  x, y, duration_ms)

    def hide_mating_heart(self, key: str) -> None:
        self._hide_overlay(self._mating_hearts, key)

    def _show_overlay(self, overlays, key, filename, x, y, duration_ms,
                      scaled_size=None) -> bool:
        """Play an animated GIF from the images folder over a pair of squid."""
        entry = overlays.get(key)
        if entry is not None:
            entry['x'], entry['y'] = float(x), float(y)
            return True
        path = os.path.join(self.images_folder_root_path, filename)
        if not os.path.exists(path):
            if self.debug_mode:
                self.logger.debug(f"No overlay: {path} is missing")
            return False
        movie = QtGui.QMovie(path)
        if not movie.isValid():
            return False
        if scaled_size is not None:
            movie.setScaledSize(scaled_size)
        item = QtWidgets.QGraphicsPixmapItem()
        item.setZValue(600)
        entry = {'movie': movie, 'item': item, 'x': float(x), 'y': float(y)}

        def show_frame(_frame_number):
            pixmap = movie.currentPixmap()
            item.setPixmap(pixmap)
            item.setPos(entry['x'] - pixmap.width() / 2,
                        entry['y'] - pixmap.height() / 2)

        movie.frameChanged.connect(show_frame)
        self.scene.addItem(item)
        overlays[key] = entry
        movie.start()
        # Hides this overlay only - not a later one shown under the same key.
        QtCore.QTimer.singleShot(duration_ms,
                                 lambda: self._hide_overlay(overlays, key, entry))
        return True

    def _hide_overlay(self, overlays, key, only=None) -> None:
        entry = overlays.get(key)
        if entry is None or (only is not None and entry is not only):
            return
        del overlays[key]
        entry['movie'].stop()
        item = entry['item']
        if item.scene() is self.scene:
            self.scene.removeItem(item)

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
        self.swim_timer.stop()
        for key in list(self._scuffles): self._end_scuffle(key)
        for key in list(self._contest_flashes): self._end_contest_flash(key)
        for key in list(self._fight_clouds.keys()):self.hide_fight_cloud(key)
        for key in list(self._mating_hearts.keys()):self.hide_mating_heart(key)
        for nid in list(self.remote_squids.keys()):self.remove_remote_squid(nid)
        for oid in list(self.remote_objects.keys()):self.remove_remote_object(oid)
        for line_id in list(self.connection_lines.keys()):
            line=self.connection_lines.pop(line_id)
            if line.scene():self.scene.removeItem(line)
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
