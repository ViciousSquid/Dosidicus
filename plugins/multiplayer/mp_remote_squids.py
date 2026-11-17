"""Other players' squid as they appear in this tank: arriving, being drawn
and moved, carrying things, and going home again.
"""
import os
import time
import random
import math
from typing import Dict, List, Any
from PyQt5 import QtCore, QtGui, QtWidgets
from .mp_network_node import NetworkNode
from .squid_multiplayer_autopilot import RemoteSquidController # Ensure this for autopilot logic
from .asset_paths import resolve_local_asset, is_inside_assets
from .identity import SquidIdentity
from .consent import (ConsentDecision, REASON_CLOSED,
                      REASON_ACCEPTED)
from .remote_protocol import (
    new_visit_id,
)


class RemoteSquidsMixin:
    """Part of MultiplayerPlugin (see mp_plugin_logic.py); not used on its own."""

    def update_remote_squid_image(self, remote_squid_display_data: Dict, direction: str):
        """Updates the visual image of a remote squid based on its direction."""
        if not self.logger: return False
        visual_item = remote_squid_display_data.get('visual')
        if not visual_item or not isinstance(visual_item, QtWidgets.QGraphicsPixmapItem):
            return False
        try:
            base_image_path = "images"
            squid_image_file = f"{direction.lower()}1.png"
            full_image_path = os.path.join(base_image_path, squid_image_file)
            squid_pixmap = QtGui.QPixmap(full_image_path)
            if squid_pixmap.isNull():
                fallback_path = os.path.join(base_image_path, "right1.png") # Default fallback
                squid_pixmap = QtGui.QPixmap(fallback_path)
                if squid_pixmap.isNull() and self.debug_mode:
                    self.logger.warning(f"Could not load squid image '{full_image_path}' or fallback '{fallback_path}'.")
                    # Create a colored square as an ultimate fallback if even "right1.png" fails
                    squid_pixmap = QtGui.QPixmap(60,40) # Default size
                    squid_color = remote_squid_display_data.get('data',{}).get('color',(128,128,128))
                    squid_pixmap.fill(QtGui.QColor(*squid_color))

            visual_item.setPixmap(squid_pixmap)
            return True
        except Exception as e:
            if self.debug_mode:
                self.logger.error(f"Error updating remote squid image for direction '{direction}': {e}", exc_info=True)
            return False

    def _animate_remote_squid_entry(self, squid_graphics_item, status_text_item, entry_direction_str):
        """MODIFIED: Animates (or rather, just shows) the visual entry of a remote squid."""
        if not self.logger: return
        if not squid_graphics_item: return

        # Directly set opacity to full (or the plugin's setting)
        squid_graphics_item.setOpacity(self.REMOTE_SQUID_OPACITY) # REMOTE_SQUID_OPACITY is 1.0 for testing
        squid_graphics_item.setScale(1.0) # Ensure normal scale

        if squid_graphics_item.graphicsEffect(): # Remove any prior effect
            squid_graphics_item.setGraphicsEffect(None)

        if status_text_item:
            status_text_item.setOpacity(1.0) # Make status text fully visible
            if status_text_item.graphicsEffect(): # Remove any prior effect
                status_text_item.setGraphicsEffect(None)
        
        if self.debug_mode:
            self.logger.debug(f"Static display for remote squid entry: {entry_direction_str}")

    def get_opposite_direction(self, direction_str: str) -> str:
        """Returns the opposite of a given cardinal direction string."""
        opposites = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
        return opposites.get(direction_str.lower(), 'right') # Default if unknown

    def create_entry_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect at the point where a remote squid enters the scene.
           MODIFIED: This effect will be static or very simple for testing."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        # Simplified static indicator (e.g., a small, briefly visible circle or text)
        # For testing, we can even skip this visual flourish if the goal is just to see the squid.
        if self.debug_mode:
            self.logger.debug(f"Skipping dynamic entry effect for static testing at ({center_x},{center_y}).")

        # If you still want a minimal static cue:
        # arrival_text_str = "New Visitor"
        # arrival_text_item = scene.addText(arrival_text_str)
        # arrival_font = QtGui.QFont("Fio UI", 10, QtGui.QFont.Bold)
        # arrival_text_item.setFont(arrival_font)
        # text_metrics = QtGui.QFontMetrics(arrival_font)
        # text_rect = text_metrics.boundingRect(arrival_text_str)
        # arrival_text_item.setDefaultTextColor(QtGui.QColor(255, 215, 0)) # Gold
        # arrival_text_item.setPos(center_x - text_rect.width() / 2, center_y - 60) # Position above entry
        # arrival_text_item.setZValue(100)
        # arrival_text_item.setVisible(True)
        # # Timer to remove it after a short period if desired, or let it persist.
        # QtCore.QTimer.singleShot(3000, lambda: scene.removeItem(arrival_text_item) if arrival_text_item.scene() else None)

    def _setup_controller_immediately(self, node_id: str, squid_initial_data: Dict):
        """Creates and initializes a RemoteSquidController."""
        if not self.logger: return
        try:
            # from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController # Already at top
            pass # Ensure it's imported
        except ImportError:
            if self.debug_mode: self.logger.error("RemoteSquidController module not found. Remote squids will not be autonomous.")
            return

        if node_id in self.remote_squid_controllers:
            if self.debug_mode: self.logger.debug(f"Controller for squid {node_id[-6:]} already exists. Updating its data.")
            # Ensure squid_data includes x,y if updating position via controller
            self.remote_squid_controllers[node_id].squid_data.update(squid_initial_data)
            # Potentially trigger a state re-evaluation in the controller if data changed significantly
            # self.remote_squid_controllers[node_id].evaluate_state() # If such a method exists
            return

        if self.debug_mode: self.logger.info(f"Creating autopilot controller for remote squid {node_id[-6:]}.")
        try:
            controller_instance = RemoteSquidController(
                squid_data=squid_initial_data, # This now contains x,y from entry_details if available
                scene=self.tamagotchi_logic.user_interface.scene,
                plugin_instance=self, # Pass self (MultiplayerPlugin instance)
                debug_mode=self.debug_mode,
                remote_entity_manager=self.entity_manager # Pass the entity manager
            )
            self.remote_squid_controllers[node_id] = controller_instance
            if self.debug_mode: self.logger.info(f"Controller for {node_id[-6:]} created. Initial state: {getattr(controller_instance, 'state', 'N/A')}")
        except Exception as e_create:
            self.logger.error(f"Failed to create RemoteSquidController for {node_id[-6:]}: {e_create}", exc_info=True)
            return
            
        # Ensure the controller update timer is running
        if self.controller_update_timer and not self.controller_update_timer.isActive():
            self.controller_update_timer.start()
            if self.debug_mode: self.logger.debug("Restarted controller update timer.")

    def handle_squid_exit_message(self, node: Any, message: Dict, addr: tuple):
        """
        We just received a 'squid_exit' multicast.
        Draw the giant exit-arrow and then create / update the remote squid visual.
        """
        # ----- basic sanity / logging -----
        node_id_for_print = (getattr(self, 'config_manager', None) and
                            getattr(self.config_manager, 'get_node_id', None) and
                            self.config_manager.get_node_id()) or \
                            (self.network_node and self.network_node.node_id) or "UnknownNode_HandleExit"

        if self.debug_mode:
            print(f"DEBUG_STEP_1: Node {node_id_for_print} - handle_squid_exit_message CALLED. "
                f"Message type: {message.get('type')}")

        if not self.logger:
            print("MPPluginLogic ERRA: Logger not available in handle_squid_exit_message")
            return False

        try:
            self.logger.info(f"MY NODE ID {self.network_node.node_id if self.network_node else 'Unknown'} - "
                            f"Received squid_exit message: {message} from {addr}")

            exit_payload_outer = message.get('payload', {})
            exit_payload_inner = exit_payload_outer.get('payload')  # actual exit_data
            if not exit_payload_inner:
                self.logger.warning("squid_exit message missing nested 'payload' key.")
                return False

            source_node_id = exit_payload_inner.get('node_id')
            if not source_node_id:
                self.logger.warning("squid_exit inner payload missing 'node_id'.")
                return False

            # ignore our own broadcast
            if self.network_node and source_node_id == self.network_node.node_id:
                self.logger.debug(f"Ignoring own squid_exit broadcast for {source_node_id}.")
                return False
            # ...and one addressed to another tank (address_exit). Without
            # 'to' (an older client) any host that hears it may answer.
            addressed_to = exit_payload_inner.get('to')
            if addressed_to and self.network_node and addressed_to != self.network_node.node_id:
                self.logger.debug(f"squid_exit from {source_node_id} is for {addressed_to}.")
                return False

            # ---------- HOST CONSENT ----------
            # Entry used to be unconditional: any squid_exit on the multicast
            # group put a visitor in the tank. The host decides now, and a
            # refusal is where the visit ends - no body is created, so a
            # refused visitor cannot enter.
            visitor_identity = SquidIdentity.from_payload(
                exit_payload_inner.get('identity') or {})
            # Already here, from that same tank: its home did not hear the
            # answer and is asking again. Say yes again - and nothing else.
            # Admitting it a second time gave it a second visit, and its
            # home went on following the first.
            visitor_uuid = getattr(visitor_identity, 'uuid', '') or ''
            if (visitor_uuid and self.host_body is not None
                    and visitor_uuid in self.host_body.visitors
                    and self.visit_node_ids.get(visitor_uuid) == source_node_id):
                if self.network_node:
                    self.network_node.send_message('visit_response', {
                        'accepted': True, 'reason': REASON_ACCEPTED,
                        'peer_uuid': visitor_uuid, 'to': source_node_id})
                return True
            current = len(self.host_body.visitors) if self.host_body else 0
            if self._resident_is_dead():
                # Nobody to visit: the tank is waiting for its egg to hatch.
                decision = ConsentDecision(
                    False, REASON_CLOSED,
                    getattr(visitor_identity, 'uuid', '') or '')
            else:
                decision = self.consent_policy.evaluate(
                    visitor_identity, current_visitors=current)
            if not decision.accepted:
                self.logger.info(
                    f"Refused entry to {visitor_identity or source_node_id}: {decision.reason}")
                if self.network_node:
                    # Addressed to the node too: a refusal for an identity it
                    # could not read has no uuid to address, and was ignored -
                    # the squid kept asking every few seconds.
                    self.network_node.send_message(
                        'visit_response', dict(decision.to_payload(), to=source_node_id))
                return False
            self.peer_identities[source_node_id] = visitor_identity
            if self.network_node:
                self.network_node.send_message(
                    'visit_response', dict(decision.to_payload(), to=source_node_id))

            # ========== NEW: SHOW THE BIG EXIT ARROW ==========
            exit_dir = exit_payload_inner.get('direction', 'right')
            if self.debug_mode:
                self.logger.debug(f"Showing exit arrow for direction: {exit_dir}")
            self._show_exit_arrow(exit_dir)
            # ===================================================

            # create / update the remote squid visual
            if self.entity_manager:
                update_success = self.entity_manager.update_remote_squid(
                    source_node_id, exit_payload_inner, is_new_arrival=True
                )
                if update_success and self.host_body is not None:
                    # A BODY, not a brain. The visitor is given a position in
                    # this tank and nothing that decides what to do with it -
                    # that stays on the visitor's own machine, and arrives as
                    # action intents. Before Stage 1 this built a
                    # RemoteSquidController: a four-state policy running here,
                    # standing in for a brain that was running perfectly well
                    # somewhere else. Nothing stands in for it now.
                    entry_details = self.entity_manager.get_last_calculated_entry_details(source_node_id)
                    entry_x, entry_y = self.calculate_entry_position(exit_dir)
                    if entry_details:
                        entry_x, entry_y = entry_details['entry_pos']

                    visit_id = new_visit_id(
                        str(getattr(self.local_identity, 'uuid', '')),
                        visitor_identity.uuid)
                    actor = self.host_body.admit(visitor_identity, visit_id,
                                                 entry_x, entry_y)
                    self.visit_node_ids[visitor_identity.uuid] = source_node_id
                    # A squid appearing in the tank catches the resident's
                    # eye: its view cone swings onto the newcomer, so it is
                    # seen (or not) through vision like anything else.
                    resident = getattr(self.tamagotchi_logic, 'squid', None)
                    visual = getattr(self.entity_manager, 'remote_squids', {}).get(
                        source_node_id, {}).get('visual')
                    if visual is not None:
                        # Who that drawn squid is, for aiming at it and for a
                        # rock that strikes it (src/interactions.py).
                        visual.squid_name = visitor_identity.name
                        visual.peer_uuid = visitor_identity.uuid
                    if hasattr(resident, 'notice'):
                        resident.notice(visual)
                    # The squid this resident mated with is back. Tell it
                    # again, in case it never heard; it files the mating once.
                    lifecycle = getattr(getattr(self.tamagotchi_logic, 'squid', None),
                                        'lifecycle', None)
                    if (lifecycle is not None and lifecycle.mating_id
                            and lifecycle.mate_uuid == visitor_identity.uuid):
                        self.host_body.announce_mating(actor, lifecycle.mating_id)
                    # First frame straight away, so the visitor's brain has
                    # something to decide from without waiting a cadence.
                    self._send('perception_frame',
                               self.host_body.build_frame(actor).to_payload())
                    self.logger.info(
                        f"Visitor {visitor_identity} admitted as visit {visit_id}")
                else:
                    self.logger.warning(f"Failed to create/update remote squid {source_node_id} in entity_manager.")
            else:
                self.logger.error("Remote entity manager (self.entity_manager) not found!")

            return True

        except Exception as e:
            self.logger.error(f"Error in handle_squid_exit_message: {e}", exc_info=True)
            return False

    def _setup_controller_creation_timer(self):
        """(Fallback) Sets up a QTimer to process pending controller creations."""
        if not self.logger: return
        if self.controller_creation_timer and self.controller_creation_timer.isActive():
            return # Already running
        if not self.controller_creation_timer:
            self.controller_creation_timer = QtCore.QTimer()
            self.controller_creation_timer.timeout.connect(self._process_pending_controller_creations)
        self.controller_creation_timer.start(300) # Check every 300ms
        if self.debug_mode: self.logger.debug("Fallback controller creation timer started.")

    def _process_pending_controller_creations(self):
        """(Fallback) Processes remote squids waiting for controllers."""
        if not self.logger: return
        if not hasattr(self, 'pending_controller_creations') or not self.pending_controller_creations:
            return

        items_to_process = list(self.pending_controller_creations) # Copy for safe iteration
        self.pending_controller_creations.clear() # Clear original list

        for creation_task in items_to_process:
            node_id = creation_task.get('node_id')
            squid_data = creation_task.get('squid_data')
            if not node_id or not squid_data: continue

            if node_id not in self.remote_squid_controllers:
                if self.debug_mode: self.logger.debug(f"Fallback: Creating controller for squid {node_id[-6:]}.")
                self._setup_controller_immediately(node_id, squid_data)
            elif self.debug_mode:
                self.logger.debug(f"Fallback: Controller for {node_id[-6:]} already exists, skipping duplicate creation.")

    def update_remote_controllers(self):
        """Called by a QTimer to update RemoteSquidController instances."""
        if not self.logger:
            return

        # ----  TRACE  ----
        if self.debug_mode:
            print(f"TRACE ++++ MP_PLUGIN_LOGIC: update_remote_controllers METHOD ENTERED. "
                f"Num controllers: {len(self.remote_squid_controllers)} ++++")
            self.logger.info("DEBUG_MPL_UPDATE: At start of update_remote_controllers. "
                            "Current controllers: %s. Dict size: %s",
                            list(self.remote_squid_controllers.keys()),
                            len(self.remote_squid_controllers))
        # -----------------

        if not hasattr(self, 'remote_squid_controllers') or not self.remote_squid_controllers:
            return

        current_time = time.time()
        delta_time = current_time - self.last_controller_update
        if delta_time <= 0.001:
            return
        self.last_controller_update = current_time

        for node_id, controller in list(self.remote_squid_controllers.items()):
            try:
                if self.debug_mode:
                    print(f"++++ MP_PLUGIN_LOGIC: Attempting to call update() for controller {node_id[-4:]} ++++")
                controller.update(delta_time)
            except Exception as e:
                self.logger.error(f"++++ MP_PLUGIN_LOGIC: Error updating controller for {node_id[-6:]}: {e}", exc_info=True)

    def calculate_entry_position(self, entry_side_direction: str) -> tuple:
        """Calculates X,Y coordinates for a squid entering this local screen."""
        if not self.logger: return (100,100) # Default fallback
        if not self.tamagotchi_logic or not self.tamagotchi_logic.user_interface:
            return (100, 100) # Fallback if UI not available
        
        window_w = self.tamagotchi_logic.user_interface.window_width
        window_h = self.tamagotchi_logic.user_interface.window_height
        margin = 70 # How far from the edge it should appear

        if entry_side_direction == 'left':   return (margin, window_h / 2)
        elif entry_side_direction == 'right':return (window_w - margin, window_h / 2)
        elif entry_side_direction == 'up':   return (window_w / 2, margin)
        elif entry_side_direction == 'down': return (window_w / 2, window_h - margin)
        
        return (window_w / 2, window_h / 2) # Default to center if direction unknown

    def apply_remote_experiences(self, local_squid, activity_summary: Dict):
        """Applies summarized experiences from a remote journey to the local squid."""
        if not self.logger: return
        if not local_squid or not activity_summary: return

        food_eaten = activity_summary.get('food_eaten', 0)
        rocks_interacted = activity_summary.get('rock_interactions', 0)
        rocks_brought_back = activity_summary.get('rocks_stolen', 0)
        time_away_seconds = activity_summary.get('time_away', 0)
        time_str = f"{int(time_away_seconds/60)}m {int(time_away_seconds%60)}s"
        
        journey_desc = f"Returned from a {time_str} journey to another tank. "

        if hasattr(local_squid, 'memory_manager'):
            mm = local_squid.memory_manager
            if food_eaten > 0:
                journey_desc += f"Ate {food_eaten} snacks there. "
                local_squid.hunger = max(0, local_squid.hunger - 10 * food_eaten) # Reduce hunger
                mm.add_short_term_memory('travel', 'ate_on_trip', f"Found {food_eaten} yummy treats on my trip!", 5)
            if rocks_interacted > 0:
                journey_desc += f"Played with {rocks_interacted} interesting rocks. "
                local_squid.happiness = min(100, local_squid.happiness + 3 * rocks_interacted) # Increase happiness
                mm.add_short_term_memory('travel', 'played_on_trip', f"Played with {rocks_interacted} cool rocks elsewhere!", 4)
            
            mm.add_short_term_memory('travel', 'completed_journey', journey_desc, importance=7)

            if food_eaten > 1 or rocks_interacted > 3 or rocks_brought_back > 0:
                mm.add_short_term_memory('emotion', 'happy_return', "It's great to be back home after an exciting adventure!", 6)
            else:
                mm.add_short_term_memory('emotion', 'calm_return', "Returned home. It was a quiet trip.", 3)

        if hasattr(local_squid, 'curiosity'): # Reduce curiosity after travel
            local_squid.curiosity = max(0, local_squid.curiosity - 25)

    def create_exit_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect when a local squid exits the screen.
           MODIFIED: This effect will be static or very simple for testing."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        # scene = self.tamagotchi_logic.user_interface.scene # Scene not used if no visual effects

        # Simplified static indicator (e.g., a small, briefly visible circle or text)
        if self.debug_mode:
            self.logger.debug(f"Skipping dynamic exit effect for static testing at ({center_x},{center_y}).")

    def _show_exit_arrow(self, exit_direction: str):
        """
        Draw a big arrow flush with the screen edge the squid just left through.
        exit_direction : 'left' | 'right' | 'up' | 'down'
        """
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'):
            return
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        w, h = ui.window_width, ui.window_height
        colour = QtGui.QColor(255, 200, 0, 200)   # juicy orange
        pen = QtGui.QPen(colour, 16)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        pen.setJoinStyle(QtCore.Qt.RoundJoin)

        # ---------- geometry ----------
        shaft_len = min(w, h) * 0.55          # long shaft
        head_len  = shaft_len * 0.30          # arrow-head
        shaft_wid = 24                        # visual thickness

        if exit_direction == 'left':          # leaving LEFT edge → arrow points LEFT
            shaft = QtCore.QLineF(shaft_len, h/2, 0, h/2)
            head1 = QtCore.QLineF(head_len,  h/2 - head_len*0.6, 0, h/2)
            head2 = QtCore.QLineF(head_len,  h/2 + head_len*0.6, 0, h/2)
        elif exit_direction == 'right':       # leaving RIGHT edge → arrow points RIGHT
            shaft = QtCore.QLineF(w - shaft_len, h/2, w, h/2)
            head1 = QtCore.QLineF(w - head_len,  h/2 - head_len*0.6, w, h/2)
            head2 = QtCore.QLineF(w - head_len,  h/2 + head_len*0.6, w, h/2)
        elif exit_direction == 'up':          # leaving TOP edge → arrow points UP
            shaft = QtCore.QLineF(w/2, shaft_len, w/2, 0)
            head1 = QtCore.QLineF(w/2 - head_len*0.6, head_len, w/2, 0)
            head2 = QtCore.QLineF(w/2 + head_len*0.6, head_len, w/2, 0)
        else:                                 # leaving BOTTOM edge → arrow points DOWN
            shaft = QtCore.QLineF(w/2, h - shaft_len, w/2, h)
            head1 = QtCore.QLineF(w/2 - head_len*0.6, h - head_len, w/2, h)
            head2 = QtCore.QLineF(w/2 + head_len*0.6, h - head_len, w/2, h)

        # ---------- draw ----------
        group = QtWidgets.QGraphicsItemGroup()
        group.setZValue(1000)  # on top of everything
        for line in (shaft, head1, head2):
            group.addToGroup(scene.addLine(line, pen))
        scene.addItem(group)

        # ---------- fade & self-destruct ----------
        def fade():
            opacity = group.opacity()
            if opacity > 0.01:
                group.setOpacity(max(0, opacity - 0.04))
            else:
                scene.removeItem(group)
                fade_timer.stop()
                fade_timer.deleteLater()

        # Parented to the scene: a timer only this closure referred to was
        # garbage-collected, and the arrow stayed up for good.
        fade_timer = QtCore.QTimer(scene)
        fade_timer.timeout.connect(fade)
        fade_timer.start(40)  # ~25 fps → gone in ~2 s

    def handle_squid_return(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles a 'squid_return' message for the player's own squid."""
        if not self.logger: return
        try:
            return_payload = message.get('payload', {})
            returning_node_id = return_payload.get('node_id')

            if not self.network_node or returning_node_id != self.network_node.node_id:
                if self.debug_mode:
                    expected_id = self.network_node.node_id if self.network_node else "N/A"
                    self.logger.debug(f"Squid_return message ignored. Expected node '{expected_id}', got '{returning_node_id}'.")
                return

            local_squid = self.tamagotchi_logic.squid
            if not local_squid or not local_squid.squid_item:
                if self.debug_mode: self.logger.debug("Local squid or its visual item not found for return.")
                return

            activity_summary = return_payload.get('activity_summary', {})
            entry_side = return_payload.get('return_direction', 'left') 
            entry_coords = self.calculate_entry_position(entry_side)

            local_squid.squid_x, local_squid.squid_y = entry_coords[0], entry_coords[1]
            local_squid.squid_item.setPos(local_squid.squid_x, local_squid.squid_y)
            if hasattr(local_squid, 'set_in_tank'):
                local_squid.set_in_tank(True)        # and its head icons with it
            else:
                local_squid.squid_item.setVisible(True)
            local_squid.squid_item.setOpacity(1.0)
            if local_squid.squid_item.graphicsEffect():
                local_squid.squid_item.graphicsEffect().setEnabled(False)
                local_squid.squid_item.setGraphicsEffect(None)

            self.apply_remote_experiences(local_squid, activity_summary)

            # --- MODIFICATION FOR DETAILED ITEM RECREATION ---
            carried_items_details_list = activity_summary.get('carried_items_details', [])
            num_items_brought_back = len(carried_items_details_list) # Or use 'rocks_stolen' if it reliably matches the list length

            if num_items_brought_back > 0:
                self.logger.info(f"Local squid returned carrying {num_items_brought_back} item(s). Details: {carried_items_details_list}")
                # We'll create/modify this method in the next step:
                self.recreate_carried_items_in_tank(local_squid, carried_items_details_list, entry_coords)
                
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    self.tamagotchi_logic.show_message(f"Your squid returned with {num_items_brought_back} item(s) from its adventure!")
            else:
                # ... (existing message for no items stolen) ...
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    journey_time_sec = activity_summary.get('time_away', 0)
                    time_str = f"{int(journey_time_sec/60)}m {int(journey_time_sec%60)}s"
                    self.tamagotchi_logic.show_message(f"Welcome back! Your squid explored for {time_str}.")
            
            local_squid.can_move = True
            if hasattr(local_squid, 'is_transitioning'): local_squid.is_transitioning = False
            local_squid.status = "just returned home"

            if self.debug_mode: self.logger.debug(f"Local squid '{getattr(local_squid,'name','')}' returned to {entry_coords} from {entry_side}. Brought back {num_items_brought_back} items.")

        except Exception as e:
            self.logger.error(f"Handling local squid's return failed: {e}", exc_info=True)

    def recreate_carried_items_in_tank(self, local_squid, carried_items_data_list: List[Dict], entry_position: tuple):
        """
        Recreates items in the local scene based on detailed data brought back by the squid.
        The first item is given to the squid to carry; subsequent items are placed in the tank.
        """
        if not self.logger:
            print("MPPluginLogic ERRA: Logger not available in recreate_carried_items_in_tank")
            return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface') or not carried_items_data_list:
            self.logger.warning("Cannot recreate carried items: TamagotchiLogic, UI, or item data missing.")
            return
        
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        entry_x, entry_y = entry_position

        self.logger.info(f"Recreating {len(carried_items_data_list)} item(s) brought back by squid {local_squid.name if hasattr(local_squid, 'name') else 'N/A'}.")

        item_successfully_given_to_squid_to_carry = False

        for i, item_data in enumerate(carried_items_data_list):
            try:
                original_filename = item_data.get('original_filename')
                original_category = item_data.get('original_category', 'decoration') # Default if not specified
                item_scale = item_data.get('scale', 1.0)
                # Use original_zValue if provided, otherwise default (e.g. for decorations)
                # Add a small positive bias if it's going to be carried to appear above squid if at same base Z
                item_z_value = item_data.get('zValue', 0) 


                if not original_filename:
                    self.logger.warning(f"Skipping item recreation: 'original_filename' missing in item data: {item_data}")
                    continue

                # --- Asset Path Resolution ---
                # original_filename arrives from another machine. It is used
                # ONLY to pick a file out of this installation's own asset
                # directories: resolve_local_asset takes the basename and then
                # verifies the resolved path really is inside those roots, so
                # a name like '../../etc/passwd.png' resolves to nothing.
                # This used to end with the remote value used verbatim as a
                # relative path, which resolved wherever the sender liked.
                item_image_path = resolve_local_asset(original_filename)

                if not item_image_path:
                    self.logger.warning(f"No local asset matches remote item name '{original_filename}'. Falling back to the default rock.")
                    # Fallback to a generic rock image if specific image not found
                    item_image_path = os.path.join("images", "rock.png") # Default fallback
                    if not (os.path.exists(item_image_path)
                            and is_inside_assets(item_image_path)):
                        self.logger.error("Default fallback image 'images/rock.png' also not found. Cannot recreate item.")
                        continue # Skip this item
                    original_category = 'rock' # Override category if using fallback rock

                self.logger.info(f"Attempting to recreate item {i+1}: Path='{item_image_path}', Category='{original_category}', Scale={item_scale:.2f}")

                pixmap = QtGui.QPixmap(item_image_path)
                if pixmap.isNull():
                    self.logger.error(f"Failed to load QPixmap for item image: '{item_image_path}'")
                    continue

                # --- Item Creation ---
                created_item_visual = None
                if hasattr(ui, 'ResizablePixmapItem'):
                    created_item_visual = ui.ResizablePixmapItem(pixmap, item_image_path)
                else:
                    created_item_visual = QtWidgets.QGraphicsPixmapItem(pixmap)
                    setattr(created_item_visual, 'filename', item_image_path)
                
                setattr(created_item_visual, 'category', original_category)
                created_item_visual.setScale(item_scale)
                # ZValue for carried item will be handled by squid logic to be on top
                # ZValue for placed items will use item_z_value
                # setattr(created_item_visual, 'original_zValue', item_z_value) # Store for later placement

                setattr(created_item_visual, 'is_stolen_from_remote', True)
                setattr(created_item_visual, 'is_foreign', True)
                self.apply_foreign_object_tint(created_item_visual)
                
                # Add to scene so it's managed by Qt, positions will be updated
                scene.addItem(created_item_visual)

                if not item_successfully_given_to_squid_to_carry and hasattr(local_squid, 'start_carrying_item'):
                    # The first successfully created item is given to the squid to carry
                    created_item_visual.setZValue(local_squid.squid_item.zValue() + 0.1) # Ensure it's visually above squid slightly
                    local_squid.start_carrying_item(created_item_visual)
                    item_successfully_given_to_squid_to_carry = True
                    self.logger.info(f"Squid '{local_squid.name}' is now carrying '{os.path.basename(item_image_path)}'.")
                else:
                    # Subsequent items, or if squid can't carry, place them in the tank
                    if not hasattr(local_squid, 'start_carrying_item'):
                         self.logger.warning(f"Squid object does not have 'start_carrying_item' method. Placing item '{os.path.basename(item_image_path)}' near entry.")
                    else:
                        self.logger.info(f"Placing additional item '{os.path.basename(item_image_path)}' directly in tank.")

                    created_item_visual.setZValue(item_z_value) # Use its original/default Z for placed items
                    
                    # Scatter these additional items around the entry point
                    angle_offset = random.uniform(-math.pi / 2, math.pi / 2) 
                    # Use 'i' to ensure different angle for each subsequent item
                    angle = (i * (math.pi / max(1, len(carried_items_data_list) -1 ))) + angle_offset 
                    dist_from_entry = random.uniform(80, 150) # Slightly further for placed items
                    
                    item_x = entry_x + dist_from_entry * math.cos(angle)
                    item_y = entry_y + dist_from_entry * math.sin(angle)
                    
                    item_w = pixmap.width() * item_scale
                    item_h = pixmap.height() * item_scale
                    # Basic boundary check
                    item_x = max(item_w/2, min(item_x, ui.window_width - item_w/2))
                    item_y = max(item_h/2, min(item_y, ui.window_height - item_h/2))

                    created_item_visual.setPos(item_x - item_w/2, item_y - item_h/2)
                    created_item_visual.setOpacity(1.0) # Ensure visible

                # Add memory for each successfully recreated item
                if hasattr(local_squid, 'memory_manager'):
                    local_squid.memory_manager.add_short_term_memory(
                        'achievement', f'brought_back_{original_category}',
                        f"Brought back a {os.path.basename(item_image_path)} from an adventure!", importance=6
                    )

            except Exception as e:
                self.logger.error(f"Error processing and recreating a carried item from data '{item_data}': {e}", exc_info=True)

    def _create_arrival_animation(self, graphics_item: QtWidgets.QGraphicsPixmapItem):
        """MODIFIED: Creates a simple fade-in animation (now static) for newly arrived remote items."""
        if not self.logger: return
        if not graphics_item: return
        try:
            # For static testing, just ensure opacity and scale are correct
            target_opacity = self.REMOTE_SQUID_OPACITY # Should be 1.0
            if hasattr(graphics_item, 'is_remote_clone') and getattr(graphics_item, 'is_remote_clone'):
                # Cloned objects might have a slightly different base opacity if desired, but for squid, full.
                pass #  target_opacity *= 0.75 (example if clones were different)
            
            graphics_item.setOpacity(target_opacity)
            graphics_item.setScale(1.0) # Ensure normal scale

            if graphics_item.graphicsEffect(): # Remove any prior opacity effect
                graphics_item.setGraphicsEffect(None)

        except Exception as e:
            if self.debug_mode: self.logger.warning(f"Simple static arrival display error: {e}")
            if graphics_item: graphics_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Fallback

    def _reset_remote_squid_style(self, node_id_or_item):
        """Resets the visual style of a remote squid to default (static, full opacity)."""
        if not self.logger: return
        node_id = None
        squid_display_data = None

        if isinstance(node_id_or_item, str): # If node_id is passed
            node_id = node_id_or_item
            squid_display_data = self.remote_squids.get(node_id)
        elif isinstance(node_id_or_item, QtWidgets.QGraphicsPixmapItem): # If visual item is passed
            for nid, s_data in self.remote_squids.items():
                if s_data.get('visual') == node_id_or_item:
                    node_id = nid
                    squid_display_data = s_data
                    break
        
        if not squid_display_data: return # Squid not found

        visual_item = squid_display_data.get('visual')
        status_text_item = squid_display_data.get('status_text')
        id_text_item = squid_display_data.get('id_text')

        if visual_item:
            visual_item.setZValue(5) # Default Z-order for remote squids
            visual_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Ensure full opacity
            visual_item.setScale(1.0) # Ensure normal scale
            if visual_item.graphicsEffect(): # Remove any effects (like shadow or previous opacity effects)
                visual_item.setGraphicsEffect(None)
        
        # Reset status text style
        if status_text_item:
            current_status_from_data = squid_display_data.get('data', {}).get('status', 'visiting')
            status_text_item.setPlainText(current_status_from_data)
            status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 220)) # Default color
            status_text_item.setFont(QtGui.QFont("Fio UI", 9)) # Default font
            status_text_item.setZValue(6) # Above squid

        # Reset ID text style (usually less dynamic)
        if id_text_item:
            id_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 180))
            id_text_item.setFont(QtGui.QFont("Fio UI", 8))
            id_text_item.setZValue(6)

    def initialize_remote_representation(self):
        """(Fallback) Initializes basic timers for managing remote entity visuals if entity_manager is not used."""
        if not self.logger: return
        if self.entity_manager: # If entity_manager is active, it handles these.
            if self.debug_mode: self.logger.debug("RemoteEntityManager is active, skipping fallback timers.")
            return

        if not self.cleanup_timer_basic:
            self.cleanup_timer_basic = QtCore.QTimer()
            self.cleanup_timer_basic.timeout.connect(self.cleanup_stale_nodes) # Fallback cleanup
            self.cleanup_timer_basic.start(7500) # Check every 7.5s
        
        if not self.connection_timer_basic:
            self.connection_timer_basic = QtCore.QTimer()
            self.connection_timer_basic.timeout.connect(self._network_health_check)
            self.connection_timer_basic.start(1200) # Update lines every 1.2s

        # A heartbeat says a peer is online, not that its squid is here. It
        # used to draw a grey squid in this tank for every peer, every 8
        # seconds, at the position the squid has in its own tank - and the
        # resident sees what is drawn. A squid is in this tank when its
        # owner sends it and this host admits it (handle_squid_exit_message).


    def update_remote_squid(self, remote_node_id: str, squid_data_dict: Dict, is_new_arrival=False, high_visibility=False):
        """Updates or creates the visual representation of a remote squid.
           This method now primarily defers to self.entity_manager if available."""
        if not self.logger: return False

        # Perception first: this is the one place every remote squid position
        # passes through, so it is where the local brain gets told that
        # another squid is there.
        self.perceive_remote_squid(remote_node_id, squid_data_dict)
        
        if self.entity_manager:
            # entity_manager.update_remote_squid will handle all visual creation and updates
            # Pass is_new_arrival along, high_visibility is implicitly handled by static display now
            success = self.entity_manager.update_remote_squid(remote_node_id, squid_data_dict, is_new_arrival)
            if success and is_new_arrival:
                # If entity_manager handled it, log for clarity, autopilot logic is in handle_squid_exit.
                if self.debug_mode: self.logger.debug(f"RemoteEntityManager handled update/creation for {remote_node_id}.")
            elif not success:
                 if self.debug_mode: self.logger.warning(f"RemoteEntityManager failed to update/create {remote_node_id}.")
            return success

        # --- Fallback logic if entity_manager is NOT available (original basic logic) ---
        self.logger.warning("entity_manager NOT found. Using fallback remote squid update logic.")
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False
        if not squid_data_dict or not all(key in squid_data_dict for key in ['x', 'y', 'direction']):
            if self.debug_mode: self.logger.warning(f"Fallback: Insufficient data for remote squid {remote_node_id}.")
            return False
        
        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_squids_lock: # Ensure lock for fallback access too
            existing_squid_display = self.remote_squids.get(remote_node_id)
            if existing_squid_display:
                visual = existing_squid_display.get('visual')
                id_text = existing_squid_display.get('id_text')
                status_text = existing_squid_display.get('status_text')

                if visual:
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    visual.setOpacity(self.REMOTE_SQUID_OPACITY) # Fallback ensure opacity
                    visual.setScale(1.0) # Fallback ensure scale
                    self.update_remote_squid_image(existing_squid_display, squid_data_dict['direction'])
                
                new_status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                if id_text: id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 50) # Adjust as needed
                if status_text:
                    status_text.setPlainText(new_status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 35) # Adjust
                    # Static text styling, no animation-dependent changes
                    status_text.setDefaultTextColor(QtGui.QColor(200,200,200,230))
                    status_text.setFont(QtGui.QFont("Fio UI", 9))
                    if is_new_arrival: # Slight emphasis for new arrivals' status
                        status_text.setDefaultTextColor(QtGui.QColor(255, 223, 0)) # Gold
                        status_text.setFont(QtGui.QFont("Fio UI", 10, QtGui.QFont.Bold))

                existing_squid_display['data'] = squid_data_dict
                existing_squid_display['last_update'] = time.time()
            else: # New squid, fallback creation
                try:
                    initial_direction = squid_data_dict.get('direction', 'right')
                    # Attempt to load image, fallback to placeholder
                    base_image_path = "images"
                    squid_image_file = f"{initial_direction.lower()}1.png"
                    full_image_path = os.path.join(base_image_path, squid_image_file)
                    
                    squid_pixmap = QtGui.QPixmap(full_image_path)
                    if squid_pixmap.isNull():
                        self.logger.warning(f"Fallback: Image {full_image_path} not found. Using color placeholder.")
                        squid_width = squid_data_dict.get('squid_width', 60)
                        squid_height = squid_data_dict.get('squid_height', 40)
                        squid_pixmap = QtGui.QPixmap(int(squid_width), int(squid_height))
                        squid_color_tuple = squid_data_dict.get('color', (100,150,255)) # Default color
                        squid_pixmap.fill(QtGui.QColor(*squid_color_tuple))

                    visual = QtWidgets.QGraphicsPixmapItem(squid_pixmap)
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    visual.setOpacity(self.REMOTE_SQUID_OPACITY) # Full opacity (1.0)
                    visual.setScale(1.0) # Normal scale
                    visual.setZValue(5) # Default Z order
                    scene.addItem(visual)

                    # ID Text
                    display_id_str = f"{remote_node_id[-6:]}" # Show last 6 chars of ID
                    id_text = scene.addText(display_id_str) # Basic text item
                    id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 50) # Position above visual
                    id_text.setFont(QtGui.QFont("Fio UI", 8))
                    id_text.setDefaultTextColor(QtGui.QColor(200,200,200,180)) # Semi-transparent white
                    id_text.setZValue(6) # Above squid visual
                    id_text.setVisible(self.SHOW_REMOTE_LABELS)

                    # Status Text
                    status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                    status_text = scene.addText(status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 35) # Position above visual
                    status_text.setFont(QtGui.QFont("Fio UI", 9))
                    status_text.setDefaultTextColor(QtGui.QColor(200,200,200,230))
                    if is_new_arrival: # Emphasize for new arrivals
                        status_text.setDefaultTextColor(QtGui.QColor(255, 215, 0)) # Gold
                        status_text.setFont(QtGui.QFont("Fio UI", 10, QtGui.QFont.Bold))
                    status_text.setZValue(6) # Above squid visual
                    status_text.setVisible(self.SHOW_REMOTE_LABELS)
                    
                    new_squid_display_data = {
                        'visual': visual, 'id_text': id_text, 'status_text': status_text,
                        'view_cone': None, 'last_update': time.time(), 'data': squid_data_dict
                    }
                    self.remote_squids[remote_node_id] = new_squid_display_data
                    # update_remote_squid_image is implicitly handled by direct pixmap load or placeholder
                    if self.debug_mode: self.logger.debug(f"Fallback: Created static remote squid visual for {remote_node_id}.")

                except Exception as e_create_squid_fb:
                    self.logger.error(f"Fallback: Creating remote squid visual for {remote_node_id} failed: {e_create_squid_fb}", exc_info=True)
                    if remote_node_id in self.remote_squids: del self.remote_squids[remote_node_id] # Cleanup partial creation
                    return False
        return True

    def _create_enhanced_arrival_animation(self, squid_visual_item: QtWidgets.QGraphicsPixmapItem, at_x: float, at_y: float):
        """MODIFIED: Creates a more prominent visual animation (now static) for newly arriving remote squids."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        # scene = self.tamagotchi_logic.user_interface.scene # Scene not used if no visual effects

        if squid_visual_item:
            squid_visual_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Ensure full visibility (1.0)
            squid_visual_item.setScale(1.0) # Ensure normal scale
            if squid_visual_item.graphicsEffect(): # Remove any prior effect
                 squid_visual_item.setGraphicsEffect(None)
        
        if self.debug_mode:
            self.logger.debug(f"Static display for enhanced arrival at ({at_x}, {at_y}).")

    def handle_remote_squid_return(self, remote_node_id: str, controller: Any): # Type hint for controller if available
        """Initiates the process for a remote squid (controlled by autopilot) to return to its home instance."""
        if not self.logger: return
        if self.debug_mode: self.logger.debug(f"Remote squid {remote_node_id[-6:]} is being returned home by its controller.")

        activity_summary_data = controller.get_summary() # Get summary of activities from controller
        home_direction_for_exit = controller.home_direction # Direction it should exit this screen

        # If entity_manager is handling visuals, tell it to start the removal process
        if self.entity_manager and hasattr(self.entity_manager, 'initiate_squid_departure_animation'):
            self.entity_manager.initiate_squid_departure_animation(
                remote_node_id,
                lambda: self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
            )
            if hasattr(self.tamagotchi_logic, 'show_message'):
                 self.tamagotchi_logic.show_message(f"👋 Visitor squid {remote_node_id[-6:]} is heading back home!")
            return

        # Fallback: Basic immediate removal or simple fade if no entity_manager animation
        remote_squid_display_info = self.remote_squids.get(remote_node_id)
        if not remote_squid_display_info or not remote_squid_display_info.get('visual'):
            if self.debug_mode: self.logger.warning(f"Visual for returning remote squid {remote_node_id[-6:]} not found. Completing return directly.")
            self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
            return

        visual_item = remote_squid_display_info['visual']
        status_text = remote_squid_display_info.get('status_text')
        if status_text: # Update status text
            status_text.setPlainText("RETURNING HOME...")
            status_text.setDefaultTextColor(QtGui.QColor(255, 165, 0)) # Orange
            status_text.setFont(QtGui.QFont("Fio UI", 10, QtGui.QFont.Bold))
        
        # For static testing, remove immediately after sending message
        self.logger.info(f"Static removal for remote squid {remote_node_id[-6:]} returning home.")
        self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
        
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"👋 Visitor squid {remote_node_id[-6:]} is heading back home!")

    def complete_remote_squid_return(self, remote_node_id: str, activity_summary: Dict, exit_direction: str):
        """Finalizes the return of a remote squid: sends message and removes local visuals."""
        if not self.logger: return
        try:
            # Send 'squid_return' message to the network so the original instance knows its squid is back
            if self.network_node and self.network_node.is_connected:
                return_message_payload = {
                    'node_id': remote_node_id, # ID of the squid that is returning
                    'activity_summary': activity_summary, # What it did on this instance
                    'return_direction': exit_direction # How it should re-enter its home screen
                }
                self.network_node.send_message('squid_return', return_message_payload)
                if self.debug_mode:
                    rocks = activity_summary.get('rocks_stolen',0)
                    self.logger.info(f"Sent 'squid_return' for {remote_node_id[-6:]} (summary: {rocks} rocks). Exit dir: {exit_direction}")
            
            # Remove the remote squid's visual representation from this instance
            if self.entity_manager:
                self.entity_manager.remove_remote_squid(remote_node_id)
            else: # Fallback
                self.remove_remote_squid(remote_node_id) # This plugin's method for basic removal

            # Remove its controller
            if remote_node_id in self.remote_squid_controllers:
                del self.remote_squid_controllers[remote_node_id]
                if self.debug_mode: self.logger.info(f"Removed controller for returned remote squid {remote_node_id[-6:]}.")
        except Exception as e:
            self.logger.error(f"Completing remote squid return for {remote_node_id[-6:]} failed: {e}", exc_info=True)

    def update_remote_view_cone(self, remote_node_id: str, remote_squid_data: Dict):
        """Updates the visual representation of a remote squid's view cone.
           This is the mp_plugin_logic's own implementation, potentially a fallback if entity_manager is not used
           or if this plugin needs to draw cones for controllers it manages directly."""
        if not self.logger: return
        
        # If entity_manager is present and handles view cones, defer to it.
        if self.entity_manager and hasattr(self.entity_manager, 'update_remote_view_cone'):
            # Ensure entity_manager's update_remote_view_cone is compatible or adapt the call
            # This assumes entity_manager.update_remote_view_cone(node_id, data) signature
            self.entity_manager.update_remote_view_cone(remote_node_id, remote_squid_data)
            return

        # --- Fallback or direct implementation if no entity_manager for this ---
        if not self.SHOW_REMOTE_LABELS: # View cones are often tied to label visibility
            if remote_node_id in self.remote_squids and self.remote_squids[remote_node_id].get('view_cone'):
                self._remove_view_cone_for_squid(remote_node_id) # Helper to remove existing cone
            return

        if remote_node_id not in self.remote_squids or not self.tamagotchi_logic or \
           not hasattr(self.tamagotchi_logic, 'user_interface'):
            return

        scene = self.tamagotchi_logic.user_interface.scene
        squid_display_info = self.remote_squids[remote_node_id] # This plugin's own remote_squids dict
        
        # Remove existing cone if any
        self._remove_view_cone_for_squid(remote_node_id) 
        
        if not remote_squid_data.get('view_cone_visible', False): # If cone should not be visible
            return

        # Get squid's visual item from this plugin's tracking (if fallback)
        visual_item = squid_display_info.get('visual') 
        if not visual_item: 
            if self.debug_mode: self.logger.warning(f"Fallback: No visual item for {remote_node_id} to draw view cone.")
            return

        # Use visual item's current position and size for cone origin
        squid_center_x = visual_item.pos().x() + visual_item.boundingRect().width() / 2
        squid_center_y = visual_item.pos().y() + visual_item.boundingRect().height() / 2
        
        looking_direction_rad = remote_squid_data.get('looking_direction', 0.0) # In radians
        view_cone_angle_rad = remote_squid_data.get('view_cone_angle', math.radians(50)) # Default cone angle
        cone_half_angle = view_cone_angle_rad / 2.0
        cone_length = 150 # Length of the cone

        # Calculate points of the cone triangle
        point1_origin = QtCore.QPointF(squid_center_x, squid_center_y)
        point2_edge1 = QtCore.QPointF(
            squid_center_x + cone_length * math.cos(looking_direction_rad - cone_half_angle),
            squid_center_y + cone_length * math.sin(looking_direction_rad - cone_half_angle)
        )
        point3_edge2 = QtCore.QPointF(
            squid_center_x + cone_length * math.cos(looking_direction_rad + cone_half_angle),
            squid_center_y + cone_length * math.sin(looking_direction_rad + cone_half_angle)
        )
        
        cone_polygon = QtGui.QPolygonF([point1_origin, point2_edge1, point3_edge2])
        new_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        
        squid_color = remote_squid_data.get('color', (150, 150, 255)) # Use squid's color for cone
        try:
            cone_q_color = QtGui.QColor(*squid_color)
        except TypeError:
            cone_q_color = QtGui.QColor(150,150,255) # Fallback color

        new_cone_item.setPen(QtGui.QPen(QtGui.QColor(cone_q_color.red(), cone_q_color.green(), cone_q_color.blue(), 0))) # Transparent border
        new_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(cone_q_color.red(), cone_q_color.green(), cone_q_color.blue(), 25))) # Semi-transparent fill
        new_cone_item.setZValue(visual_item.zValue() - 1) # Draw behind squid
        
        scene.addItem(new_cone_item)
        squid_display_info['view_cone'] = new_cone_item # Store reference

    def _remove_view_cone_for_squid(self, remote_node_id: str):
        """Safely removes a view cone for a specific remote squid (used by fallback logic)."""
        if not self.logger: return
        # This check is for this plugin's remote_squids dictionary
        if remote_node_id in self.remote_squids and self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
            squid_display_info = self.remote_squids[remote_node_id]
            cone_item = squid_display_info.get('view_cone')
            if cone_item and cone_item.scene(): # Check if it has a scene before removing
                self.tamagotchi_logic.user_interface.scene.removeItem(cone_item)
            squid_display_info['view_cone'] = None # Clear reference

    def remove_remote_squid(self, node_id_to_remove: str):
        """Removes visual components of a specific remote squid (used by fallback or direct management)."""
        if not self.logger: return
        if node_id_to_remove not in self.remote_squids: return # Not in this plugin's tracking
        
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        with self.remote_squids_lock: # Thread safety for self.remote_squids
            squid_display_elements = self.remote_squids.pop(node_id_to_remove, None)
        
        if squid_display_elements:
            visual_keys = ['visual', 'view_cone', 'id_text', 'status_text']
            for key in visual_keys:
                item_to_remove = squid_display_elements.get(key)
                if item_to_remove and item_to_remove.scene(): # Check if item has a scene
                    scene.removeItem(item_to_remove)
            
            # Remove associated connection line if managed by this plugin directly
            if node_id_to_remove in self.connection_lines:
                line = self.connection_lines.pop(node_id_to_remove)
                if line.scene(): scene.removeItem(line)
            
            if self.debug_mode: self.logger.debug(f"Fallback: Removed all visuals for remote squid {node_id_to_remove[-6:]}.")

        # Update UI status if network_node is still valid
        if self.network_node: 
            if self.status_widget: self.status_widget.update_peers(self.network_node.known_nodes if self.network_node else {})
            elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(len(self.network_node.known_nodes if self.network_node else {}))
