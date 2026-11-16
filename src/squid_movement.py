"""How the squid moves: neural drives steering it, the swimming itself, and
leaving the tank through its edge to visit another.
"""
import logging
import random
import time
import math
from PyQt5 import QtCore

_LOG = logging.getLogger(__name__)


class SquidMovementMixin:
    """Part of Squid (see squid.py); not used on its own."""

    #: Seconds between departure requests while waiting at the side.
    EXIT_RETRY_SECONDS = 3.0

    def is_venturing(self) -> bool:
        """Is its own network taking it out of the tank? (src/venturing.py)"""
        return self.why_not_venturing() is None

    def why_not_venturing(self):
        from .venturing import why_not
        brain = getattr(getattr(getattr(self, 'tamagotchi_logic', None), 'brain_window', None),
                        'brain_widget', None)
        if brain is None:
            return 'it has no brain to decide with'
        lifecycle = getattr(self, 'lifecycle', None)
        return why_not(getattr(brain, 'state', {}) or {}, getattr(brain, 'weights', {}) or {},
                       fleeing=bool(getattr(self, 'is_fleeing', False)),
                       chasing_food=bool(getattr(self, 'pursuing_food', False)),
                       can_visit=bool(getattr(lifecycle, 'can_visit', True)))

    def _exit_identity(self):
        """Who is asking to come in, as the host checks it - with the
        encounter protocol this build speaks. A hard-coded protocol 1 had
        every host refuse the squid (protocol_mismatch), so none could leave."""
        from plugins.multiplayer.identity import SquidIdentity
        identity = SquidIdentity.from_squid(self)
        return identity.to_payload() if identity is not None else {}

    def check_boundary_exit(self):
        """
        Leave through the side the squid has reached - only while its own
        network is taking it out (is_venturing), and through the left or
        right side, never the surface or the sand.
        """
        try:
            # Check basic prerequisites
            if not hasattr(self, 'tamagotchi_logic') or not self.tamagotchi_logic:
                return False
            
            # A parent stays with its egg, and a dead squid goes nowhere.
            if not self.lifecycle.can_visit:
                return False

            if not self.is_venturing():
                return False
            if time.time() - getattr(self, '_last_exit_request', 0.0) < self.EXIT_RETRY_SECONDS:
                return False

            # Check plugin manager and multiplayer status
            pm = self.tamagotchi_logic.plugin_manager
            multiplayer_enabled = 'multiplayer' in pm.get_enabled_plugins()
            
            if not multiplayer_enabled:
                return False
            
            # Attempt to get network node with multiple fallback strategies
            network_node = None
            
            # Strategy 1: Direct attribute on tamagotchi_logic
            if hasattr(self.tamagotchi_logic, 'network_node'):
                network_node = self.tamagotchi_logic.network_node
            
            # Strategy 2: Find in multiplayer plugin
            if network_node is None:
                try:
                    multiplayer_plugin = pm.plugins.get('multiplayer', {}).get('instance')
                    if multiplayer_plugin and hasattr(multiplayer_plugin, 'network_node'):
                        network_node = multiplayer_plugin.network_node
                        # Attempt to set on tamagotchi_logic for future use
                        self.tamagotchi_logic.network_node = network_node
                except Exception as plugin_error:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"Error finding network node in plugin: {plugin_error}")
            
            # If still no network node, abort
            if network_node is None or not network_node.is_connected:
                print("No active network node found for boundary exit")
                return False
            
            # Advanced boundary detection logic
            squid_right = self.squid_x + self.squid_width
            squid_bottom = self.squid_y + self.squid_height
            
            exit_direction = None
            
            if self.squid_x <= 0:
                exit_direction = 'left'
            elif squid_right >= self.ui.window_width:
                exit_direction = 'right'
            
            if exit_direction:
                print(f"Exit Direction Detected: {exit_direction}")
                
                # Prepare comprehensive exit data
                exit_data = {
                    'node_id': network_node.node_id,
                    'direction': exit_direction,
                    'position': {
                        'x': self.squid_x,
                        'y': self.squid_y
                    },
                    'color': self._get_squid_color(),
                    'squid_width': self.squid_width,
                    'squid_height': self.squid_height,
                    'window_width': self.ui.window_width,
                    'window_height': self.ui.window_height,
                    # Who is asking to come in. The host needs this to decide
                    # whether to admit the visitor at all, and to recognise it
                    # if it has been here before.
                    'identity': self._exit_identity(),
                }
                
                print("Exit Data Details:")
                for key, value in exit_data.items():
                    print(f"  {key}: {value}")
                
                # Addressed to the one aquarium it is visiting (the plugin
                # picks the one heard most recently), so only that host answers.
                plugin = (getattr(pm, 'plugins', {}) or {}).get('multiplayer', {}).get('instance')
                if hasattr(plugin, 'address_exit') and not plugin.address_exit(exit_data):
                    return False
                # Broadcast exit message
                try:
                    self._last_exit_request = time.time()
                    network_node.send_message(
                        'squid_exit', 
                        {'payload': exit_data}
                    )
                    print("Exit message successfully broadcast")
                    from .social_knowledge import think
                    think(self.tamagotchi_logic, "Another aquarium is nearby and I want to "
                          f"explore it: I am leaving through the {exit_direction} side.")
                    return True
                except Exception as broadcast_error:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"Broadcast error: {broadcast_error}")
                    return False
            
            return False
        
        except Exception as e:
            print(f"Comprehensive boundary exit error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _notify_boundary_exit(self, direction):
        """
        Enhanced notification of boundary exit with comprehensive logging
        """
        print("\n===== BOUNDARY EXIT NOTIFICATION =====")
        
        try:
            # Get plugin manager
            pm = self.tamagotchi_logic.plugin_manager
            
            # Get multiplayer plugin
            if 'multiplayer' in pm.get_enabled_plugins():
                plugin_instance = pm.plugins['multiplayer'].get('instance')
                
                if plugin_instance and hasattr(plugin_instance, 'network_node'):
                    # Prepare exit data with precise details
                    exit_data = {
                        'node_id': plugin_instance.network_node.node_id if plugin_instance.network_node else 'unknown',
                        'direction': direction,
                        'position': {
                            'x': self.squid_x,
                            'y': self.squid_y
                        },
                        'color': plugin_instance.get_squid_color() if hasattr(plugin_instance, 'get_squid_color') else (150, 150, 255),
                        'squid_width': self.squid_width,
                        'squid_height': self.squid_height,
                        'window_width': self.ui.window_width,
                        'window_height': self.ui.window_height,
                        # See the other exit payload: the host cannot consent
                        # to, or recognise, a visitor it cannot identify.
                        'identity': self._exit_identity(),
                    }
                    
                    print("Exit Data:")
                    for key, value in exit_data.items():
                        print(f"  {key}: {value}")
                    
                    # Broadcast exit message
                    plugin_instance.network_node.send_message(
                        'squid_exit', 
                        {'payload': exit_data}
                    )
                    
                    print(f"[MULTIPLAYER] Squid exiting through {direction} boundary")
                    
                    # Gone from this tank - and its head icons with it.
                    self.set_in_tank(False)
                    
                    # CHANGE: Set flag to indicate squid is away
                    self.is_transitioning = True
                    
                    # CHANGE: Disable movement while away
                    self.can_move = False
                    
                    # CHANGE: Update status
                    self.status = "visiting another tank"
                    
                    # Optional: Show a message about the squid leaving
                    if hasattr(self.tamagotchi_logic, 'show_message'):
                        self.tamagotchi_logic.show_message(f"Your squid left through the {direction} boundary!")
                else:
                    print("[ERROR] No network node or plugin instance available")
            else:
                print("[ERROR] Multiplayer plugin not enabled")
        
        except Exception as e:
            print("[CRITICAL] Error in boundary exit notification:")
            import traceback
            traceback.print_exc()
        
        print("===== BOUNDARY EXIT NOTIFICATION END =====\n")

    def move_erratically(self):
        """Dart about for one tick."""
        self.squid_direction = random.choice(["left", "right", "up", "down"])
        self.current_speed = self.base_speed * 1.5
        self.move_squid()
        self.current_speed = self.base_speed

    def move_slowly(self):
        """Drift for one tick.

        This used to do `base_squid_speed = base_squid_speed // 2` with no
        restore, so the squid's baseline was permanently halved on every call:
        90 -> 45 -> 22 -> 11 -> 5 -> 2 -> 1 -> 0. Seven "lounging" decisions
        left it with a base speed of zero and it could never move again for
        the rest of the session. Speed is now a transient multiplier, which is
        what current_speed is for.
        """
        previous = self.current_speed
        self.current_speed = max(1.0, self.base_speed * 0.4)
        try:
            self.move_squid()
        finally:
            self.current_speed = previous

    # =========================================================================
    # NEURAL DRIVE - the brain's control channel into movement
    #
    # Three tiers arbitrate for the squid's heading each tick:
    #
    #   1. DRIVE_URGE     set by neuron output bindings. An irresistible
    #                     biological urge: it overrides everything, including
    #                     the squid's own reflexes.
    #   2. innate reflex  food in the view cone. Hard-wired, always available,
    #                     and it interrupts deliberation - the squid does not
    #                     need a brain to notice food.
    #   3. DRIVE_DECISION set by DecisionEngine. Ordinary deliberate behaviour,
    #                     and what drives the squid most of the time.
    #
    # ...then random wandering if nothing above applies.
    # =========================================================================
    DRIVE_URGE = 'urge'

    DRIVE_DECISION = 'decision'

    _DRIVE_RANK = {DRIVE_DECISION: 1, DRIVE_URGE: 2}

    def speed_multiplier(self) -> float:
        """current_speed expressed as a factor of base_speed, sanity-bounded.

        A squid with no speed override moves at 1.0x, so the attributes are
        read defensively rather than assumed to exist.
        """
        base = getattr(self, 'base_speed', None)
        current = getattr(self, 'current_speed', None)
        if base is None or current is None:
            return 1.0
        try:
            base = float(base)
            if base == 0:
                return 1.0
            return max(0.25, min(3.0, float(current) / base))
        except (TypeError, ValueError):
            return 1.0

    def set_neural_drive(self, action: str, duration: float = 3.0, target=None,
                         priority: str = None):
        """Give the squid a short-lived movement intent.

        priority is DRIVE_URGE (output bindings) or DRIVE_DECISION
        (DecisionEngine). A decision can never displace an urge that is still
        running - that is what makes an urge irresistible. Drives expire on
        their own so a one-shot firing produces a burst of behaviour rather
        than a state the squid can never leave.

        Returns the active drive, which is the existing one if this call was
        outranked.
        """
        priority = priority or self.DRIVE_DECISION
        current = self.get_neural_drive()
        if current is not None:
            here = self._DRIVE_RANK.get(priority, 1)
            there = self._DRIVE_RANK.get(current.get('priority'), 1)
            if here < there:
                return current  # outranked by an urge still in force

        self.neural_drive = {
            'action': action,
            'expires': time.time() + max(0.1, float(duration)),
            'target': target,
            'priority': priority,
        }
        return self.neural_drive

    def has_urge(self) -> bool:
        """True while an output binding's urge is overriding everything else."""
        drive = self.get_neural_drive()
        return bool(drive) and drive.get('priority') == self.DRIVE_URGE

    def flee_from_center(self):
        """Bolt away from the middle of the tank.

        DecisionEngine calls this; it was never defined, so the whole fleeing
        branch raised AttributeError the moment anything selected it.
        """
        cx = self.ui.window_width / 2.0
        cy = self.ui.window_height / 2.0
        sx = self.squid_x + self.squid_width / 2.0
        sy = self.squid_y + self.squid_height / 2.0
        away = (sx + (sx - cx) * 4.0, sy + (sy - cy) * 4.0)

        self.is_fleeing = True
        self.current_speed = self.base_speed * 2
        return self.set_neural_drive('flee', duration=4.0, target=away,
                                     priority=self.DRIVE_DECISION)

    def get_neural_drive(self):
        """The active drive, or None once it has expired."""
        drive = getattr(self, 'neural_drive', None)
        if not drive:
            return None
        if time.time() >= drive.get('expires', 0):
            self.neural_drive = None
            return None
        return drive

    def clear_neural_drive(self):
        self.neural_drive = None

    def _steer_by_neural_drive(self, drive) -> bool:
        """Point the squid according to `drive`.

        Returns True when the drive has taken control of this tick's heading,
        in which case move_squid skips its own food/random selection. The
        existing position, boundary and animation code then runs unchanged.
        """
        action = drive.get('action')
        target = drive.get('target')

        if action == 'wander':
            if self.is_venturing():
                # Exploring, drawn by another aquarium: out of the nearest side.
                from .venturing import way_out
                _side, (tx, ty) = way_out(self.squid_x, self.squid_y, self.squid_width,
                                          self.squid_height, self.ui.window_width)
                self.status = "venturing out"
                self.squid_direction = ("right" if tx > self.squid_x + self.squid_width / 2.0
                                        else "left")
                return True
            self.move_randomly()
            return True

        if action == 'flee':
            self.is_fleeing = True
            self.current_speed = self.base_speed * 2
            if random.random() < 0.35:
                self.change_direction()
            return True

        target_point = self._resolve_drive_target(action, target)
        if target_point is None:
            return False

        tx, ty = target_point
        cx = self.squid_x + self.squid_width / 2.0
        cy = self.squid_y + self.squid_height / 2.0
        dx, dy = tx - cx, ty - cy

        if abs(dx) < 5 and abs(dy) < 5:
            return True  # arrived; hold position this tick

        if abs(dx) >= abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"
        return True

    def _resolve_drive_target(self, action, target):
        """Turn a drive target into an (x, y) scene point, or None."""
        if target is not None:
            try:
                if hasattr(target, 'sceneBoundingRect'):
                    c = target.sceneBoundingRect().center()
                    return (c.x(), c.y())
                if isinstance(target, QtCore.QPointF):
                    return (target.x(), target.y())
                if isinstance(target, (tuple, list)) and len(target) >= 2:
                    return (float(target[0]), float(target[1]))
            except Exception:
                return None

        if action == 'seek_food':
            visible = self.get_visible_food()
            if visible:
                closest = min(visible, key=lambda f: self.distance_to(f[0], f[1]))
                self.pursuing_food = True
                return (closest[0], closest[1])
        return None

    def move_squid(self):
        """
        Move the squid with comprehensive debug logging and multiplayer boundary check
        """
        # Check if movement is allowed
        if not getattr(self, 'can_move', True):
            return
        
        # Check if multiplayer is available and enabled
        if hasattr(self.tamagotchi_logic, 'plugin_manager'):
            pm = self.tamagotchi_logic.plugin_manager
            multiplayer_enabled = 'multiplayer' in pm.get_enabled_plugins()
        else:
            multiplayer_enabled = False
        
        if self.animation_speed == 0:
            #print("Animation speed is 0, no movement")
            return

        if self.is_sleeping:
            #print("Squid is sleeping, limited movement")
            previous_x, previous_y = self.squid_x, self.squid_y
            if self.squid_y < self.ui.window_height - 120 - self.squid_height:
                self.squid_y += self.base_vertical_speed * self.animation_speed
                self.squid_item.setPos(self.squid_x, self.squid_y)
            self._track_position_delta(previous_x, previous_y)
            self.current_frame = (self.current_frame + 1) % 2
            self.update_squid_image()
            return
        

        current_time = QtCore.QTime.currentTime().msecsSinceStartOfDay()

        # ---- Heading arbitration: urge > innate food reflex > decision ----
        drive = self.get_neural_drive()
        steered = False

        # 1. An urge from an output binding is irresistible.
        if drive is not None and drive.get('priority') == self.DRIVE_URGE:
            steered = self._steer_by_neural_drive(drive)

        visible_food = None if steered else self.get_visible_food()

        if visible_food:
            # 2. Innate reflex: the squid sees food in its view cone and goes
            #    for it. Hard-wired - it needs no brain and it interrupts
            #    whatever the DecisionEngine was deliberating about.
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.pursuing_food = True
            self.target_food = closest_food
            self.move_towards(closest_food[0], closest_food[1])
        elif steered:
            pass  # the urge already chose a heading this tick
        elif drive is not None and self._steer_by_neural_drive(drive):
            pass  # 3. deliberate behaviour from the DecisionEngine
        elif self.pursuing_food:
            self.pursuing_food = False
            self.target_food = None
            self.move_randomly()
        else:
            if current_time - self.last_view_cone_change > self.view_cone_change_interval:
                self.change_view_cone_direction()
                self.last_view_cone_change = current_time
            self.move_randomly()

        # Store previous position for distance calculation
        prev_x, prev_y = self.squid_x, self.squid_y

        # Calculate new position
        squid_x_new = self.squid_x
        squid_y_new = self.squid_y

        # current_speed used to be written in five places and read in none;
        # movement always used base_squid_speed, so "flee at double speed" and
        # the startle speed boost were both invisible. It is now a real factor.
        h_speed = self.base_squid_speed * self.speed_multiplier()
        v_speed = self.base_vertical_speed * self.speed_multiplier()

        if self.squid_direction == "left":
            squid_x_new -= h_speed * self.animation_speed
        elif self.squid_direction == "right":
            squid_x_new += h_speed * self.animation_speed
        elif self.squid_direction == "up":
            squid_y_new -= v_speed * self.animation_speed
        elif self.squid_direction == "down":
            squid_y_new += v_speed * self.animation_speed

        # The tank's edges stop the squid - unless, with multiplayer on, its own
        # network is taking it out (src/venturing.py): then it may reach the
        # side it is heading for, and leaves there (check_boundary_exit).
        venturing = multiplayer_enabled and self.is_venturing()
        if venturing:
            squid_x_new = max(0, min(self.ui.window_width - self.squid_width, squid_x_new))
            squid_y_new = max(50, min(self.ui.window_height - 120 - self.squid_height, squid_y_new))
        else:
            if squid_x_new < 50:
                squid_x_new = 50
                self.change_direction()
            elif squid_x_new > self.ui.window_width - 50 - self.squid_width:
                squid_x_new = self.ui.window_width - 50 - self.squid_width
                self.change_direction()

            if squid_y_new < 50:
                squid_y_new = 50
                self.change_direction()
            elif squid_y_new > self.ui.window_height - 120 - self.squid_height:
                squid_y_new = self.ui.window_height - 120 - self.squid_height
                self.change_direction()

        # Update squid position
        self.squid_x = squid_x_new
        self.squid_y = squid_y_new

        self._track_position_delta(prev_x, prev_y)

        # Update animation frame and image
        if self.squid_direction in ["left", "right", "up", "down"]:
            self.current_frame = (self.current_frame + 1) % 2
            self.squid_item.setPixmap(self.current_image())

        # Set new position and update related elements
        self.squid_item.setPos(self.squid_x, self.squid_y)
        self.update_view_cone()
        self.update_head_icon_positions()

        # Leaving, if it is venturing out and has reached the side.
        if venturing:
            self.check_boundary_exit()

    def move_towards(self, x, y):
        dx = x - (self.squid_x + self.squid_width // 2)
        dy = y - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

    def _track_position_delta(self, previous_x, previous_y):
        """Record the actual distance moved at a coordinate update boundary."""
        distance = math.hypot(
            self.squid_x - previous_x,
            self.squid_y - previous_y,
        )
        track_distance = getattr(
            getattr(self, 'tamagotchi_logic', None),
            'track_distance',
            None,
        )
        if distance > 0 and track_distance:
            track_distance(distance)
        return distance

    def move_towards_position(self, target_pos):
        dx = target_pos.x() - (self.squid_x + self.squid_width // 2)
        dy = target_pos.y() - (self.squid_y + self.squid_height // 2)

        if abs(dx) > abs(dy):
            self.squid_direction = "right" if dx > 0 else "left"
        else:
            self.squid_direction = "down" if dy > 0 else "up"

        self.move_squid()

    def move_randomly(self):
        if random.random() < 0.20:
            self.change_direction()

    def change_direction(self):
        directions = ["left", "right", "up", "down"]
        new_direction = random.choice(directions)
        while new_direction == self.squid_direction:
            new_direction = random.choice(directions)
        self.squid_direction = new_direction

    def move_towards_plant(self):
        if self.tamagotchi_logic is None:
            return

        nearby_decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
        plants = [d for d in nearby_decorations if d.category == 'plant']

        if plants:
            closest_plant = min(plants, key=lambda p: self.distance_to(p.pos().x(), p.pos().y()))
            self.move_towards(closest_plant.pos().x(), closest_plant.pos().y())
        else:
            self.move_randomly()

    def move_toward_position(self, target_pos):
        """Move directly toward a QPointF or (x,y) position with rock interaction support"""
        # Handle both QPointF and tuple/position inputs
        if isinstance(target_pos, QtCore.QPointF):
            target_x, target_y = target_pos.x(), target_pos.y()
        else:
            target_x, target_y = target_pos
        
        # Get precise center positions using scene coordinates
        squid_rect = self.squid_item.sceneBoundingRect()
        squid_center_x = squid_rect.center().x()
        squid_center_y = squid_rect.center().y()
        
        dx = target_x - squid_center_x
        dy = target_y - squid_center_y
        distance = math.hypot(dx, dy)  # More efficient than math.sqrt
        
        if distance > 5:  # Small threshold to prevent micro-movements
            previous_x, previous_y = self.squid_x, self.squid_y

            # Normalize and scale by speed (removed temporary 1.5x boost)
            norm = max(distance, 0.1)  # Avoid division by zero
            move_x = (dx/norm) * self.base_squid_speed * self.animation_speed
            move_y = (dy/norm) * self.base_vertical_speed * self.animation_speed
            
            # Update position
            self.squid_x += move_x
            self.squid_y += move_y
            
            # Update direction - more precise handling
            if abs(move_x) > abs(move_y):
                self.squid_direction = "right" if move_x > 0 else "left"
            else:
                self.squid_direction = "down" if move_y > 0 else "up"
            
            # Enforce boundaries
            self.squid_x = max(50, min(self.squid_x, self.ui.window_width - 50 - self.squid_width))
            self.squid_y = max(50, min(self.squid_y, self.ui.window_height - 120 - self.squid_height))
            
            # Update graphics
            self.squid_item.setPos(self.squid_x, self.squid_y)
            self._track_position_delta(previous_x, previous_y)
            self.current_frame = (self.current_frame + 1) % 2
            self.update_squid_image()  # Changed to use method instead of direct pixmap set
        
        return distance
