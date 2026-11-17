"""Keeping tanks in step: the periodic presence broadcast, and what is done
with the ones received (objects, heartbeats, stale nodes).
"""
import os
import time
import math
from typing import Dict, List
from PyQt5 import QtCore, QtGui, QtWidgets
from .mp_network_node import NetworkNode
from .asset_paths import resolve_local_asset
from .identity import SquidIdentity
from .remote_protocol import (
    ROUND_TRIP_INTERVAL,
)


class StateSyncMixin:
    """Part of MultiplayerPlugin (see mp_plugin_logic.py); not used on its own."""

    def cleanup_stale_nodes(self):
        """(Fallback) Removes visuals of remote nodes that haven't sent updates, used if entity_manager is None."""
        if not self.logger: return
        if self.entity_manager: return # entity_manager handles its own cleanup

        if not self.network_node: return
        current_time = time.time()
        stale_threshold_seconds = 45.0 # Example: 45 seconds timeout
        
        nodes_to_remove_ids = []
        # Check known_nodes from NetworkNode
        for node_id, (_, last_seen_time, _) in list(self.network_node.known_nodes.items()):
            if current_time - last_seen_time > stale_threshold_seconds:
                nodes_to_remove_ids.append(node_id)
        
        for node_id_to_remove in nodes_to_remove_ids:
            if self.debug_mode: self.logger.debug(f"Basic Cleanup: Node {node_id_to_remove[-6:]} timed out. Removing.")
            if node_id_to_remove in self.network_node.known_nodes:
                del self.network_node.known_nodes[node_id_to_remove]
            
            # Remove visual representation using this plugin's direct management
            self.remove_remote_squid(node_id_to_remove) # This uses self.remote_squids
            
            if node_id_to_remove in self.remote_squid_controllers: # Also remove controller
                del self.remote_squid_controllers[node_id_to_remove]

        # Update UI status
        if self.network_node: # Check again as it might be cleaned up
            peers_now = self.network_node.known_nodes if self.network_node else {}
            if self.status_widget: self.status_widget.update_peers(peers_now)
            elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(len(peers_now))

    def start_sync_timer(self):
        """Drive the real remote-mind round trip on Qt's owning thread.

        No sync timer was ever constructed, so enable() skipped this path and
        admitted visitors never received another frame or sent an intent.
        Reading bodies/scenes and resolving contacts also belongs on this thread.
        """
        if self.sync_timer is None:
            self.sync_timer = QtCore.QTimer()
            self.sync_timer.setInterval(max(50, int(ROUND_TRIP_INTERVAL * 1000)))
            self.sync_timer.timeout.connect(self.sync_game_state)
        if not self.sync_timer.isActive():
            self.sync_timer.start()

    def sync_game_state(self):
        """Collects and sends current local game state."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid') or \
           not self.network_node or not self.network_node.is_connected:
            return # Prerequisites not met

        try:
            # Encounters are advanced on the same tick the state goes out, so
            # "how long was that squid here" is measured on the same clock the
            # rest of multiplayer runs on.
            try:
                self._perceive_aquariums()
                self.update_encounters()
            except Exception as exc:
                self.logger.error(f"Encounter update failed: {exc}", exc_info=True)

            try:
                self.run_round_trip()
            except Exception as exc:
                self.logger.error(f"Remote-mind round trip failed: {exc}", exc_info=True)

            now = time.time()
            if now - self._last_world_sync < self.SYNC_INTERVAL:
                return
            self._last_world_sync = now
            squid_current_state = self._get_squid_state()
            objects_current_state = self._get_objects_state() # Get state of syncable objects

            sync_payload = {
                'squid': squid_current_state,
                'objects': objects_current_state,
                'node_info': {'id': self.network_node.node_id, 'ip': self.network_node.local_ip}
            }
            self.network_node.send_message('object_sync', sync_payload) # Use 'object_sync' for combined state
            
            # Send heartbeat periodically as well
            time_now = time.time()
            if time_now - self.last_message_times.get('heartbeat_sent', 0) > 8.0: # Every 8 seconds
                heartbeat_payload = {
                    'node_id': self.network_node.node_id, 'status': 'active',
                    'squid_pos': (squid_current_state['x'], squid_current_state['y']) # Include position in heartbeat
                }
                self.network_node.send_message('heartbeat', heartbeat_payload)
                self.last_message_times['heartbeat_sent'] = time_now
        except Exception as e:
            self.logger.error(f"ERROR during sync_game_state: {e}", exc_info=True)

    def _get_squid_state(self) -> Dict:
        """Compiles and returns a dictionary of the local squid's current state."""
        if not self.logger: return {}
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid or not self.network_node:
            return {} # Not enough info to build state

        squid = self.tamagotchi_logic.squid
        view_direction_rad = self.get_actual_view_direction(squid) # Get view cone direction

        # --- Logging for sent direction ---
        if self.debug_mode:
            self.logger.debug(f"Sending squid state: NodeID={self.network_node.node_id}, Direction={squid.squid_direction}, X={squid.squid_x:.1f}, Y={squid.squid_y:.1f}")

        return {
            'x': squid.squid_x, 
            'y': squid.squid_y, 
            'direction': squid.squid_direction,  # General movement/logic direction
            'image_direction_key': squid.squid_direction, # Explicit key for visual rendering direction
            'looking_direction': view_direction_rad, # For view cone
            'view_cone_angle': getattr(squid, 'view_cone_angle_rad', math.radians(60)),
            # No drives: hunger, happiness and the rest are private cognitive
            # state (remote_protocol.FORBIDDEN_KEYS), seen by no other tank.
            'status': getattr(squid, 'status', "idle"), # Current action/status
            'carrying_rock': getattr(squid, 'carrying_rock', False),
            'is_sleeping': getattr(squid, 'is_sleeping', False),
            'color': self.get_squid_color(), # Get consistent color based on node ID
            'node_id': self.network_node.node_id, # Include node_id for identification
            'view_cone_visible': getattr(squid, 'view_cone_visible', False), # Is view cone active
            'squid_width': getattr(squid, 'squid_width', 60), # For rendering remote squid
            'squid_height': getattr(squid, 'squid_height', 40), # For rendering remote squid
            # Who this is, as opposed to which socket it came from. node_id is
            # regenerated every setup; squid.uuid is written into the save file
            # and restored from it, so it is what makes "the same squid again"
            # a question with an answer.
            'identity': self._identity_now(squid),
        }

    def get_actual_view_direction(self, squid_instance) -> float:
        """Determines the squid's current viewing direction in radians."""
        if hasattr(squid_instance, 'current_view_angle_radians'): # If a dynamic view angle exists
            return squid_instance.current_view_angle_radians
        
        # Fallback to movement direction if no specific view angle
        direction_to_radians_map = {
            'right': 0.0, 
            'left': math.pi, 
            'up': 1.5 * math.pi, # -math.pi/2 or 3*math.pi/2
            'down': 0.5 * math.pi  # math.pi/2
        }
        return direction_to_radians_map.get(getattr(squid_instance, 'squid_direction', 'right'), 0.0)

    def _identity_now(self, squid):
        """Who this squid is, as of now - read afresh, so a colour the
        player gives it after going online is the colour others see."""
        identity = SquidIdentity.from_squid(squid) or self.local_identity
        if identity is not None:
            self.local_identity = identity
        return identity.to_payload() if identity else None

    def get_squid_color(self) -> tuple:
        """Generates a persistent color (R,G,B) for the local squid based on its node ID."""
        if not hasattr(self, '_local_squid_color_cache'): # Cache to avoid recalculation
            node_id_str = "default_node" # Fallback
            if self.network_node and self.network_node.node_id:
                node_id_str = self.network_node.node_id
            
            # Simple hash-like function to generate color from node_id
            hash_value = 0
            for char_code in node_id_str.encode('utf-8'): # Use byte values of chars
                hash_value = (hash_value * 37 + char_code) & 0xFFFFFF # Keep it within 24-bit color range
            
            r = (hash_value >> 16) & 0xFF
            g = (hash_value >> 8) & 0xFF
            b = hash_value & 0xFF
            
            # Ensure colors are reasonably bright and distinct
            r = max(80, min(r, 220)) 
            g = max(80, min(g, 220))
            b = max(80, min(b, 220))
            
            self._local_squid_color_cache = (r, g, b)
        return self._local_squid_color_cache

    def _get_objects_state(self) -> List[Dict]:
        """
        Collects and returns a list of syncable game object states.
        MODIFIED: Returns an empty list to prevent general mirroring of local items.
        Items will now only transfer between instances via the explicit "stealing/carrying" mechanic.
        """
        if not self.logger: 
            # This check is good practice, though an empty list is returned anyway.
            print("MPPluginLogic ERRA: Logger not available in _get_objects_state")
            return [] 
        
        # To stop broadcasting general local items like rocks, food, decorations, etc.,
        # simply return an empty list. The 'object_sync' message will still send squid state
        # and any other essential global state, but not these common environmental items.
        if self.debug_mode:
            self.logger.debug("_get_objects_state: Intentionally returning empty list to prevent general item mirroring.")
        
        return []   # Return an empty list (do not sync decoration items)

    def _determine_object_type(self, scene_item: QtWidgets.QGraphicsItem) -> str:
        """Determines a string type for a scene item based on attributes or filename."""
        # Prioritize explicit 'category' or 'object_type' attributes
        if hasattr(scene_item, 'category') and isinstance(getattr(scene_item, 'category'), str):
            return getattr(scene_item, 'category')
        if hasattr(scene_item, 'object_type') and isinstance(getattr(scene_item, 'object_type'), str):
            return getattr(scene_item, 'object_type')

        # Fallback to filename analysis if it's a QGraphicsPixmapItem with a filename
        if isinstance(scene_item, QtWidgets.QGraphicsPixmapItem) and hasattr(scene_item, 'filename'):
            filename_lower = getattr(scene_item, 'filename', '').lower()
            if not filename_lower: return 'unknown_pixmap' # If filename is empty

            if 'rock' in filename_lower: return 'rock'
            if any(food_kw in filename_lower for food_kw in ['food', 'sushi', 'apple', 'cheese', 'berry']): return 'food'
            if 'poop' in filename_lower: return 'poop'
            # Check common decoration paths or keywords
            if os.path.join("images", "decoration") in filename_lower.replace("\\", "/") or \
               any(kw in filename_lower for kw in ['decor', 'plant', 'toy', 'shell', 'coral', 'starfish', 'gem']):
                return 'decoration'
                
        return 'generic_item' # Default if type cannot be determined

    def handle_object_sync(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles incoming 'object_sync' messages from remote peers."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return

        try:
            sync_payload = message.get('payload', {})
            remote_squid_state = sync_payload.get('squid', {}) # Data about the sender's squid
            remote_objects_list = sync_payload.get('objects', []) # List of objects from sender
            source_node_info = sync_payload.get('node_info', {})
            sender_node_id = source_node_info.get('id') or remote_squid_state.get('node_id') # Get sender's ID

            if not sender_node_id:
                if self.debug_mode: self.logger.warning("Received object_sync with no identifiable sender node_id.")
                return
            
            if self.network_node and sender_node_id == self.network_node.node_id: return # Ignore own sync messages

            # Update the visual of the remote squid based on their state
            if remote_squid_state:
                # If entity_manager exists, it will handle the update. Otherwise, basic update.
                if self.entity_manager:
                    self.entity_manager.update_remote_squid(sender_node_id, remote_squid_state, is_new_arrival=False)
                else:
                    self.update_remote_squid(sender_node_id, remote_squid_state, is_new_arrival=False) # Fallback

            # Process remote objects
            if remote_objects_list:
                active_cloned_ids_for_this_sender = set()
                for remote_obj_data in remote_objects_list:
                    if not all(k in remote_obj_data for k in ['id', 'type', 'x', 'y', 'filename']):
                        if self.debug_mode: self.logger.debug(f"Skipping incomplete remote object data from {sender_node_id}: {remote_obj_data.get('id', 'No ID')}")
                        continue
                    
                    original_id_from_sender = remote_obj_data['id']
                    # Create a unique ID for the clone in this instance's scene
                    clone_id = f"clone_{sender_node_id}_{original_id_from_sender}"
                    active_cloned_ids_for_this_sender.add(clone_id)
                    
                    # Process (create or update) the visual clone of the remote object
                    self.process_remote_object(remote_obj_data, sender_node_id, clone_id)
                
                # Cleanup: Remove clones of objects that are no longer in the sender's sync list
                with self.remote_objects_lock: # Ensure thread safety for self.remote_objects
                    ids_to_remove = [
                        obj_id for obj_id, obj_info in self.remote_objects.items()
                        if obj_info.get('source_node') == sender_node_id and obj_id not in active_cloned_ids_for_this_sender
                    ]
                    for obj_id_to_remove in ids_to_remove:
                        self.remove_remote_object(obj_id_to_remove) # Method to remove visual and from dict

            # Tell the local squid it can see another squid. Keyed on the
            # PERSISTENT identity, not the node id: "have I seen this one
            # before" has to survive the sender restarting.
            if self.tamagotchi_logic.squid and remote_squid_state:
                identity = self.peer_identities.get(sender_node_id)
                if identity is not None:
                    self.tamagotchi_logic.squid.process_squid_detection(
                        identity.uuid, is_visible=True)
        except Exception as e:
            if self.debug_mode: self.logger.error(f"Handling object_sync from {addr} failed: {e}", exc_info=True)

    def process_remote_object(self, remote_obj_data: Dict, source_node_id: str, clone_id: str):
        """
        Creates or updates a visual clone of a remote object in the local scene.
        MODIFIED: Selectively ignores common environmental items to prevent general mirroring.
        """
        if not self.logger: 
            print("MPPluginLogic ERRA: Logger not available in process_remote_object") # Basic fallback print
            return 

        # --- NEW: SELECTIVE PROCESSING TO PREVENT MIRRORING OF COMMON LOCAL ITEMS ---
        # The 'type' field in remote_obj_data is set by _determine_object_type 
        # from _get_objects_state on the sender's side.
        item_type_from_remote = remote_obj_data.get('type', 'unknown').lower()
        
        # Define types that should NOT be mirrored through general sync.
        # These items should be local to each tank unless explicitly carried over.
        types_to_ignore_for_mirroring = ['rock', 'urchin', 'food', 'poop', 'decoration'] 

        if item_type_from_remote in types_to_ignore_for_mirroring:
            # If a mirrored clone of this type of item already exists in our scene 
            # (e.g., from before this filtering logic was active, or if the other client is still sending),
            # we should remove it to enforce the non-mirroring rule.
            if clone_id in self.remote_objects: # self.remote_objects tracks visual clones this instance created
                if self.debug_mode:
                    self.logger.debug(f"process_remote_object: Removing existing undesired mirrored clone '{clone_id}' (type: '{item_type_from_remote}') from node {source_node_id}.")
                self.remove_remote_object(clone_id) # This method should handle removal from scene and self.remote_objects
            
            if self.debug_mode:
                self.logger.debug(f"process_remote_object: Ignoring general sync for remote object type '{item_type_from_remote}' (Original ID: {remote_obj_data.get('id', 'N/A')}, Clone ID: {clone_id}) from node {source_node_id}. This item type should only transfer via explicit stealing/carrying.")
            return # Stop further processing for this item, thus preventing its mirroring.
        # --- END NEW SELECTIVE PROCESSING ---

        # Original continuation of the method for item types that ARE allowed to be mirrored,
        # or for other types of shared objects if you have any.
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): 
            self.logger.warning("process_remote_object: TamagotchiLogic or UI not available, cannot process item further.")
            return
        
        scene = self.tamagotchi_logic.user_interface.scene
        
        # The rest of this method is the original logic for creating/updating clones.
        # It will now only apply to items NOT filtered out by the block above.
        # For example, if you had a special shared item type like 'portal' or 'shared_toy'
        # that you *did* want mirrored, its processing would continue here.

        # One definition of "which local file does this remote name mean" -
        # see asset_paths.resolve_local_asset. It takes the basename and then
        # verifies the resolved path is genuinely inside this installation's
        # asset directories, so nothing a peer sends can name a file outside
        # them.
        base_filename = remote_obj_data.get('filename', 'unknown_sync_item.png')
        resolved_filename = resolve_local_asset(base_filename)
        if not resolved_filename:
            if self.debug_mode: self.logger.warning(f"process_remote_object: Image for allowed sync item '{base_filename}' (type: '{item_type_from_remote}') not found in local assets for clone '{clone_id}'. Skipping visual.")
            return

        # Thread safety for self.remote_objects dictionary
        with self.remote_objects_lock: 
            if clone_id in self.remote_objects: # If clone already exists, update it
                existing_clone_info = self.remote_objects[clone_id]
                visual_item = existing_clone_info['visual']
                
                # Update existing visual item's properties
                visual_item.setPos(remote_obj_data['x'], remote_obj_data['y'])
                visual_item.setScale(remote_obj_data.get('scale', 1.0))
                visual_item.setZValue(remote_obj_data.get('zValue', -5)) # Default Z for background items
                visual_item.setVisible(not remote_obj_data.get('is_being_carried', False)) # Hide if carried by remote squid
                
                existing_clone_info['last_update'] = time.time()
                existing_clone_info['data'] = remote_obj_data # Store latest data
                
                # Ensure tint is applied if it's meant to be foreign (clones always are)
                if not getattr(visual_item, 'is_foreign', False): # Should always be true for clones
                     self.apply_foreign_object_tint(visual_item)
                if self.debug_mode:
                    self.logger.debug(f"process_remote_object: Updated mirrored clone '{clone_id}' (type: '{item_type_from_remote}') from {source_node_id}.")

            else: # New clone for an allowed item type, create it
                if remote_obj_data.get('is_being_carried', False): # Don't create visual if it's being carried by the remote squid
                    if self.debug_mode:
                        self.logger.debug(f"process_remote_object: Item '{clone_id}' (type: '{item_type_from_remote}') is being carried remotely. Not creating visual clone yet.")
                    return

                try:
                    pixmap = QtGui.QPixmap(resolved_filename)
                    if pixmap.isNull():
                        if self.debug_mode: self.logger.error(f"process_remote_object: Failed to load QPixmap for allowed remote object '{resolved_filename}'.")
                        return
                    
                    cloned_visual = QtWidgets.QGraphicsPixmapItem(pixmap)
                    cloned_visual.setPos(remote_obj_data['x'], remote_obj_data['y'])
                    cloned_visual.setScale(remote_obj_data.get('scale', 1.0))
                    # Cloned objects are typically less prominent than remote squids themselves
                    cloned_visual.setOpacity(self.REMOTE_SQUID_OPACITY * 0.65) # Example: Slightly more transparent
                    cloned_visual.setZValue(remote_obj_data.get('zValue', -5)) # Default Z for background items
                    
                    setattr(cloned_visual, 'filename', resolved_filename) 
                    setattr(cloned_visual, 'is_remote_clone', True) # Mark as a clone from a remote instance
                    setattr(cloned_visual, 'original_id_from_sender', remote_obj_data['id'])
                    
                    self.apply_foreign_object_tint(cloned_visual) # Apply visual tint
                    scene.addItem(cloned_visual)
                    
                    self.remote_objects[clone_id] = {
                        'visual': cloned_visual, 
                        'type': item_type_from_remote, # Store the determined type
                        'source_node': source_node_id, 
                        'last_update': time.time(), 
                        'data': remote_obj_data # Store all received data
                    }
                    if self.debug_mode:
                        self.logger.debug(f"process_remote_object: Created new mirrored clone '{clone_id}' (type: '{item_type_from_remote}') from {source_node_id}.")
                except Exception as e_create_clone:
                    if self.debug_mode: self.logger.error(f"process_remote_object: Creating visual clone for allowed item '{clone_id}' failed: {e_create_clone}", exc_info=True)

    def handle_heartbeat(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles heartbeat messages from other peers."""
        if not self.logger: return
        if not self.network_node: return # This instance's network node must exist

        sender_node_id = message.get('payload', {}).get('node_id') # Heartbeat payload contains sender's ID
        if not sender_node_id or sender_node_id == self.network_node.node_id: return # Ignore own or invalid heartbeats

        # Update UI (status widget or bar) with known peers
        first_heard = sender_node_id not in self._peers_heard
        self._peers_heard.add(sender_node_id)
        self._peers_last_heard[sender_node_id] = time.time()
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes) # known_nodes is updated by NetworkNode
            if first_heard:
                self.status_widget.add_activity(f"Peer {sender_node_id[-6:]} detected via heartbeat.")
        elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'):
            self.status_bar.update_peers_count(len(self.network_node.known_nodes))

    def remove_remote_object(self, full_clone_id: str):
        """Removes a specific cloned remote object (used by fallback or direct management)."""
        if not self.logger: return
        if full_clone_id not in self.remote_objects: return # Not in this plugin's tracking
        
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        with self.remote_objects_lock: # Thread safety for self.remote_objects
            object_clone_info = self.remote_objects.pop(full_clone_id, None)
        
        if object_clone_info:
            visual_item = object_clone_info.get('visual')
            if visual_item and visual_item.scene(): # Check if item has a scene
                scene.removeItem(visual_item)
            
            if self.debug_mode: self.logger.debug(f"Fallback: Removed remote object clone: {full_clone_id}.")

    def throw_rock_network(self, rock_graphics_item: QtWidgets.QGraphicsPixmapItem, direction_thrown: str):
        """Broadcasts a 'rock_throw' event when the local squid throws a rock."""
        if not self.logger: return
        if not self.network_node or not self.network_node.is_connected or not rock_graphics_item:
            return # Prerequisites not met

        try:
            rock_filename = getattr(rock_graphics_item, 'filename', "default_rock.png") # Get filename
            initial_pos = rock_graphics_item.pos() # Position when thrown
            
            rock_throw_payload = {
                'rock_data': {
                    'filename': rock_filename, 
                    'direction': direction_thrown,
                    'initial_pos_x': initial_pos.x(), 
                    'initial_pos_y': initial_pos.y(),
                    'scale': rock_graphics_item.scale() if hasattr(rock_graphics_item, 'scale') else 1.0,
                }
            }
            self.network_node.send_message('rock_throw', rock_throw_payload) # Send message
            if self.debug_mode:
                self.logger.debug(f"Broadcasted local rock throw: {os.path.basename(rock_filename)} towards {direction_thrown}.")
        except Exception as e_throw:
            if self.debug_mode: self.logger.error(f"Broadcasting rock throw failed: {e_throw}", exc_info=True)

    def handle_squid_move(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles discrete 'squid_move' messages (less frequent than full sync)."""
        if not self.logger: return
        
        payload = message.get('payload', {})
        sender_node_id = payload.get('node_id') # Assume payload contains node_id
        
        if not sender_node_id: 
            sender_node_id = message.get('node_id') # Fallback if NetworkNode added it to top level
            if not sender_node_id:
                if self.debug_mode: self.logger.warning("squid_move message missing sender_node_id.")
                return

        if self.network_node and sender_node_id == self.network_node.node_id: return # Ignore own move messages

        # Defer to entity_manager if available for visual updates
        if self.entity_manager:
            # Ensure payload matches what entity_manager.update_remote_squid expects
            # It needs x, y, direction, and other relevant fields from _get_squid_state
            self.entity_manager.update_remote_squid(sender_node_id, payload, is_new_arrival=False)
        elif sender_node_id in self.remote_squids: # Fallback basic update
            current_display_data = self.remote_squids[sender_node_id]
            visual = current_display_data.get('visual')
            if visual and all(k in payload for k in ['x', 'y', 'direction']):
                visual.setPos(payload['x'], payload['y'])
                self.update_remote_squid_image(current_display_data, payload['direction']) # Update image based on direction
            
            # Update stored data for this squid
            if 'data' in current_display_data:
                current_display_data['data'].update(payload) # Merge new data
                current_display_data['last_update'] = time.time()

    def handle_rock_throw(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles 'rock_throw' messages from remote players, creating a visual effect."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        
        scene = self.tamagotchi_logic.user_interface.scene
        payload_outer = message.get('payload', {}) # Payload from NetworkNode (contains original sender's payload)
        rock_throw_data = payload_outer.get('rock_data', {}) # Actual rock data
        
        # Get sender_node_id (NetworkNode should add this based on sender's address if not in payload)
        sender_node_id = payload_outer.get('node_id') or message.get('node_id') 
        
        if not rock_throw_data or not sender_node_id: 
            if self.debug_mode: self.logger.warning(f"Incomplete rock_throw message: data={rock_throw_data}, sender={sender_node_id}")
            return
        
        if self.network_node and sender_node_id == self.network_node.node_id: return # Ignore own rock throws

        if self.debug_mode: self.logger.debug(f"Received rock_throw from {sender_node_id[-6:]}, data: {rock_throw_data}")

        # Create visual for the thrown rock
        rock_filename = rock_throw_data.get('filename', os.path.join("images","rock.png")) # Default rock image
        try:
            pixmap = QtGui.QPixmap(rock_filename)
            if pixmap.isNull(): # Fallback if specified image fails
                pixmap = QtGui.QPixmap(os.path.join("images","rock.png")) 
            
            thrown_rock_item = QtWidgets.QGraphicsPixmapItem(pixmap)
            initial_x = rock_throw_data.get('initial_pos_x', scene.width()/2) # Default to center
            initial_y = rock_throw_data.get('initial_pos_y', scene.height()/2)
            thrown_rock_item.setPos(initial_x, initial_y)
            thrown_rock_item.setScale(rock_throw_data.get('scale', 0.8)) # Use scale from payload
            thrown_rock_item.setZValue(20) # High Z-value to be visible
            
            self.apply_foreign_object_tint(thrown_rock_item) # Mark as from remote
            scene.addItem(thrown_rock_item)
            
            # Static display for testing - no animation
            # The rock will just appear and then be removed if it goes off-screen or by other logic.
            # For a simple effect, you could make it disappear after a short time.
            if self.debug_mode: self.logger.debug(f"Static remote rock '{os.path.basename(rock_filename)}' displayed from {sender_node_id[-6:]}.")
            QtCore.QTimer.singleShot(1500, lambda item=thrown_rock_item: item.scene().removeItem(item) if item.scene() else None)


        except Exception as e_rock_throw_vis:
            if self.debug_mode: self.logger.error(f"Error visualizing remote rock throw: {e_rock_throw_vis}", exc_info=True)

    def handle_state_update(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles generic 'state_update' messages. Could be used for various game events."""
        if not self.logger: return
        
        payload = message.get('payload', {})
        # Sender ID might be in top-level message from NetworkNode or within payload
        sender_node_id = message.get('node_id') or payload.get('node_id') 

        if self.debug_mode: self.logger.debug(f"Received generic 'state_update' from {sender_node_id[-6:] if sender_node_id else 'Unknown'}. Payload: {payload}")
