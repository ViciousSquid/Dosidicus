"""What the squid can see: its view cone, the vision worker that fills it,
and noticing food, plants and other squid.
"""
import logging
import random
import time
import math
from PyQt5 import QtCore, QtGui, QtWidgets
from .vision_worker import (
    VisionResult, 
    SceneObject,
    create_squid_vision_state
)

_LOG = logging.getLogger(__name__)


class SquidVisionMixin:
    """Part of Squid (see squid.py); not used on its own."""

    def _on_food_visibility_changed(self, can_see: bool, food_positions: list):
        """Handle food visibility change from vision worker"""
        old_can_see = self._cached_can_see_food
        self._cached_can_see_food = can_see
        self._cached_visible_food = food_positions
        
        # React to visibility change
        if can_see and not old_can_see:
            # Food just became visible
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                if hasattr(self.tamagotchi_logic, 'brain_window'):
                    self.tamagotchi_logic.brain_window.add_thought("I see food!")
        
        elif not can_see and old_can_see:
            # Food just became invisible
            self.pursuing_food = False
            self.target_food = None

    def _update_scene_objects(self):
        """Update the cached scene objects for vision worker"""
        if not self.tamagotchi_logic:
            return
        
        try:
            objects = []
            
            # Add food items
            for item in self.tamagotchi_logic.food_items:
                try:
                    pos = item.pos()
                    rect = item.boundingRect()
                    objects.append(SceneObject(
                        x=pos.x(),
                        y=pos.y(),
                        width=rect.width(),
                        height=rect.height(),
                        category='food',
                        is_sushi=getattr(item, 'is_sushi', False)
                    ))
                except:
                    _LOG.debug('Ignored exception', exc_info=True)
            
            # Add decorations from scene
            if hasattr(self.ui, 'scene'):
                for item in self.ui.scene.items():
                    # Check if it's a decoration item
                    if hasattr(item, 'category') and item.category in ('plant', 'rock', 'poop'):
                        try:
                            pos = item.pos()
                            rect = item.boundingRect()
                            objects.append(SceneObject(
                                x=pos.x(),
                                y=pos.y(),
                                width=rect.width(),
                                height=rect.height(),
                                category=item.category
                            ))
                        except:
                            _LOG.debug('Ignored exception', exc_info=True)
            
            # Send to vision worker
            self._vision_worker.update_scene_objects(objects)
            self._cached_scene_objects = objects
            self._scene_objects_dirty = False
            
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Error updating scene objects: {e}")

    def mark_scene_objects_dirty(self):
        """Call when objects are added/removed from scene"""
        self._scene_objects_dirty = True

    def _update_vision_worker(self):
        """Periodically update vision worker with current state"""
        if not hasattr(self, '_vision_worker') or not self._vision_worker:
            return
        
        # Update squid state
        try:
            squid_state = create_squid_vision_state(self)
            self._vision_worker.update_squid_state(squid_state)
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Error updating squid vision state: {e}")
        
        # FIX: Always update scene objects if food exists (because food moves constantly!)
        # The dirty flag is only set when items are added/removed, but we need 
        # fresh coordinates for sinking food items every cycle.
        has_food = self.tamagotchi_logic and getattr(self.tamagotchi_logic, 'food_items', False)
        
        if self._scene_objects_dirty or has_food:
            self._update_scene_objects()

    def _on_visibility_update(self, result: VisionResult):
        """Handle full visibility update from vision worker"""
        # Discard stale updates if scene has changed since this calculation started
        if getattr(self, '_scene_objects_dirty', False):
            return

        self._cached_vision = result
        self._cached_visible_food = result.visible_food
        self._cached_can_see_food = result.can_see_food
        self._cached_can_see_plant = result.can_see_plant

    def update_view_direction(self):
        """
        Called every 1 second by a QTimer.
        Makes the squid actively scan its environment by changing gaze direction.
        Includes smart hunger-based food bias + instant brain refresh.
        """
        # Don't interrupt important states
        if (getattr(self, 'is_sleeping', False) or 
            getattr(self, 'is_fleeing', False) or 
            getattr(self, 'pursuing_food', False)):
            return

        if not hasattr(self, 'tamagotchi_logic') or not self.tamagotchi_logic:
            return

        old_angle = self.current_view_angle

        # === Something that has just appeared holds the gaze (notice) ===
        attending = self._look_at_noticed()

        # === Normal scanning: random direction ===
        if not attending:
            self.current_view_angle = random.uniform(0, 2 * math.pi)

        # === Hunger override: high chance to look toward nearest food ===
        if not attending and self.hunger > 65 and self.tamagotchi_logic.food_items:
            nearest_food = min(
                self.tamagotchi_logic.food_items,
                key=lambda f: self.distance_to(f.pos().x(), f.pos().y()),
                default=None
            )
            if nearest_food:
                fx = nearest_food.pos().x() + nearest_food.boundingRect().width() / 2
                fy = nearest_food.pos().y() + nearest_food.boundingRect().height() / 2
                sx = self.squid_x + self.squid_width / 2
                sy = self.squid_y + self.squid_height / 2

                target_angle = math.atan2(fy - sy, fx - sx)

                # The hungrier, the more likely to snap gaze directly at food
                hunger_factor = (self.hunger - 65) / 35.0  # 0.0 -> 1.0 as hunger goes 65->100
                if random.random() < hunger_factor:
                    self.current_view_angle = target_angle
                    
                    # FIX: Force immediate vision sync when locked on
                    # This bridges the gap between "looking" (angle set) and "seeing" (worker detection)
                    # ensuring the squid immediately pursues what it just decided to look at.
                    self._force_sync_vision_until = time.time() + 0.5 
                    
                else:
                    # Look near the food (curious glancing)
                    self.current_view_angle = target_angle + random.uniform(-0.8, 0.8)

        # === Force immediate brain update so 'can_see_food' neuron reacts instantly ===
        if old_angle != self.current_view_angle:
            # Option 1: Direct brain hook refresh (most reliable)
            if hasattr(self.tamagotchi_logic, 'brain_hooks'):
                # This recalculates all input neurons including can_see_food
                QtCore.QTimer.singleShot(10, lambda: self.tamagotchi_logic.apply_input_neurons_to_brain())

            # Option 2: Trigger full brain tick (fallback, also works)
            if hasattr(self.tamagotchi_logic, 'update_squid_brain'):
                QtCore.QTimer.singleShot(20, self.tamagotchi_logic.update_squid_brain)

            # Optional: Visual feedback in VisionWindow
            if hasattr(self.tamagotchi_logic, 'vision_window') and self.tamagotchi_logic.vision_window:
                self.tamagotchi_logic.vision_window.update_view()

    def get_visible_objects(self, object_list):
        """
        Finds objects from a given list that are within the squid's vision cone.
        This is a generic helper method.
        """
        visible_objects = []
        for item in object_list:
            # FIX: Use the center of the item instead of the top-left position.
            # This ensures detection works if the cone touches the object body
            # but misses the specific (0,0) origin point.
            if hasattr(item, 'sceneBoundingRect'):
                center = item.sceneBoundingRect().center()
                check_x, check_y = center.x(), center.y()
            else:
                # Fallback for items not fully initialized in scene
                check_x, check_y = item.pos().x(), item.pos().y()

            if self.is_in_vision_cone(check_x, check_y):
                visible_objects.append(item)
        return visible_objects

    def get_visible_food(self):
        """
        Returns the positions of visible food items.
        Includes a circuit breaker to prevent 'ghost' food detection.
        """
        # 1. Circuit Breaker: If the logic system says there is no food, 
        # we absolutely cannot see any, regardless of what the vision cache says.
        # This fixes the "stuck at top" bug where the worker thread returns old data.
        if self.tamagotchi_logic and not self.tamagotchi_logic.food_items:
            return []

        # 2. Force sync check if recently ate (handling worker latency)
        # This ensures we don't act on stale worker data immediately after eating
        if time.time() < getattr(self, '_force_sync_vision_until', 0):
            return self._get_visible_food_sync()

        # 3. If scene is dirty (items recently added/removed), the cache is invalid.
        # Fall back to synchronous check which uses the authoritative list.
        if getattr(self, '_scene_objects_dirty', False):
            return self._get_visible_food_sync()

        # 4. Use cached result if available and valid
        if hasattr(self, '_cached_visible_food') and self._cached_visible_food is not None:
            return self._cached_visible_food
        
        # 5. Fallback to synchronous calculation
        return self._get_visible_food_sync()

    def _get_visible_food_sync(self):
        """Synchronous fallback for get_visible_food"""
        if self.tamagotchi_logic is None:
            return []
        
        all_visible_food_items = self.get_visible_objects(self.tamagotchi_logic.food_items)
        
        if not all_visible_food_items:
            return []
        
        # Sort visible food to prioritize sushi
        sushi_items = [item for item in all_visible_food_items if getattr(item, 'is_sushi', False)]
        other_food_items = [item for item in all_visible_food_items if not getattr(item, 'is_sushi', False)]
        
        sorted_positions = [(food.pos().x(), food.pos().y()) for food in sushi_items]
        sorted_positions.extend([(food.pos().x(), food.pos().y()) for food in other_food_items])
        
        return sorted_positions

    def can_see_food(self) -> bool:
        """
        Quick check if food is visible.
        Uses cached result from vision worker.
        """
        if hasattr(self, '_cached_can_see_food'):
            return self._cached_can_see_food
        return len(self.get_visible_food()) > 0

    def can_see_plant(self) -> bool:
        """Is a plant in the view cone right now? (Cached from the vision worker.)

        The squid has no other way of knowing about a plant. There is no
        distance reading: a plant behind it does not exist as far as its
        brain is concerned until it turns round.
        """
        if getattr(self, '_cached_vision', None) is not None:
            return bool(self._cached_can_see_plant)
        return self.nearest_visible_plant() is not None

    def nearest_visible_plant(self):
        """The nearest plant IN THE VIEW CONE, as a scene item, or None.

        What the squid swims to when it wants shelter. It used to be handed
        the nearest plant in the tank wherever that was, which made "go to the
        plant" something the game did for it rather than something it could
        only do about a plant it had actually seen.
        """
        scene = getattr(getattr(self, 'ui', None), 'scene', None)
        if scene is None:
            return None
        best, best_distance = None, float('inf')
        for item in scene.items():
            if getattr(item, 'category', None) != 'plant':
                continue
            centre = item.sceneBoundingRect().center()
            if not self.is_in_vision_cone(centre.x(), centre.y()):
                continue
            distance = self.distance_to(centre.x(), centre.y())
            if distance < best_distance:
                best, best_distance = item, distance
        return best

    def get_visible_plants(self):
        """
        Finds plant decorations that are within the squid's vision cone.
        Uses cached result from vision worker when available.
        """
        if hasattr(self, '_cached_vision') and self._cached_vision:
            return self._cached_vision.visible_plants
        
        # Fallback to synchronous calculation
        if self.tamagotchi_logic is None:
            return []
        
        all_plants = []
        for item in self.tamagotchi_logic.user_interface.scene.items():
            if hasattr(item, 'category') and item.category == 'plant':
                all_plants.append(item)
        
        return self.get_visible_objects(all_plants)

    def is_in_vision_cone(self, x, y):
        """
        Check if a point (x,y) is inside the squid's vision cone
        
        Args:
            x (float): X coordinate to check
            y (float): Y coordinate to check
            
        Returns:
            bool: True if the point is in vision cone, False otherwise
        """
        # Get squid center position
        squid_center_x = self.squid_x + self.squid_width // 2
        squid_center_y = self.squid_y + self.squid_height // 2
        
        # Calculate vector to target
        dx = x - squid_center_x
        dy = y - squid_center_y
        
        # Calculate distance
        distance = math.sqrt(dx**2 + dy**2)
        
        # Define vision cone length
        cone_length = max(self.ui.window_width, self.ui.window_height)
        
        # If target is beyond detection range, return false
        if distance > cone_length:
            return False
        
        # Calculate angle to target point
        angle_to_target = math.atan2(dy, dx)
        
        # Get current view angle (use current_view_angle if available, otherwise derive from direction)
        if hasattr(self, 'current_view_angle'):
            current_angle = self.current_view_angle
        else:
            direction_map = {
                'right': 0,
                'up': math.pi * 1.5,
                'left': math.pi,
                'down': math.pi * 0.5
            }
            current_angle = direction_map.get(self.squid_direction, 0)
        
        # Get cone angle (half of the total view cone angle)
        if hasattr(self, 'view_cone_angle'):
            cone_angle = self.view_cone_angle / 2
        else:
            cone_angle = math.pi / 5  # Default 36-degree half-angle
        
        # Calculate angle difference (accounting for wrap-around)
        angle_diff = abs(angle_to_target - current_angle)
        while angle_diff > math.pi:
            angle_diff = 2 * math.pi - angle_diff
        
        # Check if the target is within the cone angle
        return angle_diff <= cone_angle

    def change_view_cone_direction(self):
        if self._look_at_noticed():
            return
        self.current_view_angle = random.uniform(0, 2 * math.pi)

    #: How long something that has just appeared holds the squid's gaze.
    NOTICE_SECONDS = 4.0

    _noticed = None          # the scene item holding the gaze, if any

    _noticed_until = 0.0

    def notice(self, item, seconds=NOTICE_SECONDS):
        """Something has just appeared: swing the view cone onto it, and hold it there.

        The orienting response - a visitor arriving in the tank is the
        multiplayer case. The cone follows the item for ``seconds``; then
        scanning resumes. Whether the squid then sees it is still vision's
        call (vision_worker), from where the cone points. Asleep, it notices
        nothing. Returns whether it looked.
        """
        if getattr(self, 'is_sleeping', False) or item is None:
            return False
        self._noticed = item
        self._noticed_until = time.time() + seconds
        return self._look_at_noticed()

    def _look_at_noticed(self):
        """Point the view cone at what holds the gaze, where it is now.

        False once the hold is over or the thing has gone from the tank.
        """
        item = self._noticed
        if item is None:
            return False
        try:
            gone = (time.time() >= self._noticed_until or item.scene() is None
                    or not item.isVisible())
            centre = item.sceneBoundingRect().center()
        except RuntimeError:  # its Qt object has been deleted
            gone = True
        if gone:
            self._noticed = None
            return False
        self.current_view_angle = math.atan2(
            centre.y() - (self.squid_y + self.squid_height / 2),
            centre.x() - (self.squid_x + self.squid_width / 2))
        self.update_view_cone()
        return True

    def cleanup_vision_worker(self):
        """Clean up vision worker - call before squid destruction"""
        if hasattr(self, '_vision_update_timer') and self._vision_update_timer:
            self._vision_update_timer.stop()
        
        if hasattr(self, '_vision_worker') and self._vision_worker:
            self._vision_worker.stop()
            self._vision_worker.wait(1000)
            self._vision_worker = None

    def process_squid_detection(self, peer_id, is_visible=True):
        """Another squid has come into view, or gone out of it.

        What this NO LONGER does is reach into the squid's drives and add 15
        curiosity and 10 anxiety. That was a rule outside the network deciding
        how meeting a squid feels, which is exactly the shape of thing the
        decision engine stopped doing in v5: it made the reaction the same for
        every squid and put it somewhere no experience could ever change it.

        What happens instead is that the arrival is reported to the senses.
        Novelty goes through external_stimulus, which is the channel every
        other new thing in the tank already uses, and a genuinely startling
        arrival fires the startle reflex - a pathway with synapses on it, which
        personality already tilts and learning can still move. Whether the
        squid is curious or frightened is then something its own network works
        out, and two squid can answer differently.

        Args:
            peer_id (str): persistent identity of the detected squid
            is_visible (bool): Whether the squid is currently visible
        """
        # Only react if the squid is not sleeping
        if self.is_sleeping:
            return

        peer_id = str(peer_id)
        if not hasattr(self, '_seen_squids'):
            self._seen_squids = set()

        if is_visible:
            first_sight = peer_id not in self._seen_squids
            if not first_sight:
                return
            self._seen_squids.add(peer_id)

            # A squid appearing is a new object in the world. Reported through
            # the sense that already means that, rather than as a stat edit.
            logic = getattr(self, 'tamagotchi_logic', None)
            hooks = getattr(logic, 'brain_hooks', None)
            if hooks is not None and hasattr(hooks, 'on_object_spawned'):
                hooks.on_object_spawned('squid')

            # Show that it has noticed. Purely a display, and separate from
            # the real curious state - see show_noticed_squid_icon.
            self.show_noticed_squid_icon()

            # A reflex, not a rule: is_startled drives act_flee through an
            # ordinary synapse that INNATE_PERSONALITY_BIAS has already tilted,
            # so a timid squid and a stubborn one respond differently to the
            # same arrival without anything here knowing that they should.
            if random.random() < 0.3:  # 30% chance
                if logic is not None and hasattr(logic, 'startle_squid'):
                    logic.startle_squid(source="detected_squid")
        else:
            self._seen_squids.discard(peer_id)

    #: How long the "I have noticed another squid" icon stays up.
    NOTICED_SQUID_ICON_MS = 3000

    def show_noticed_squid_icon(self):
        """Flash the exclamation icon on first sight of another squid.

        This shares the curious icon's ARTWORK and nothing else. It is its own
        mental state, so turning it on and off cannot disturb the real curious
        state - a squid that happens to be genuinely curious when a visitor
        arrives keeps being curious for exactly as long as it would have.

        Shown once per individual per first sighting: process_squid_detection
        only reaches here on the first sight of a given peer, and the squid
        forgets a peer when it loses track of it, so a visitor that comes back
        later is noticed again.
        """
        manager = getattr(self, 'mental_state_manager', None)
        if manager is None or not hasattr(manager, 'set_state'):
            return
        try:
            manager.set_state("noticed_squid", True)
            QtCore.QTimer.singleShot(self.NOTICED_SQUID_ICON_MS,
                                     self.hide_noticed_squid_icon)
        except Exception as exc:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Squid] could not show the noticed-squid icon: {exc}")

    def hide_noticed_squid_icon(self):
        manager = getattr(self, 'mental_state_manager', None)
        if manager is None or not hasattr(manager, 'set_state'):
            return
        try:
            manager.set_state("noticed_squid", False)
        except Exception:
            _LOG.debug('Ignored exception', exc_info=True)

    def toggle_view_cone(self):
        self.view_cone_visible = not self.view_cone_visible
        if self.view_cone_visible:
            self.update_view_cone()
        else:
            self.remove_view_cone()

    def update_view_cone(self):
        if self.view_cone_visible:
            if self.view_cone_item is None:
                self.view_cone_item = QtWidgets.QGraphicsPolygonItem()
                self.view_cone_item.setPen(QtGui.QPen(QtCore.Qt.yellow))
                self.view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 0, 50)))
                self.ui.scene.addItem(self.view_cone_item)

            squid_center_x = self.squid_x + self.squid_width // 2
            squid_center_y = self.squid_y + self.squid_height // 2

            if self.pursuing_food and self.target_food:
                dx = self.target_food[0] - squid_center_x
                dy = self.target_food[1] - squid_center_y
                self.current_view_angle = math.atan2(dy, dx)

            cone_length = max(self.ui.window_width, self.ui.window_height)

            cone_points = [
                QtCore.QPointF(squid_center_x, squid_center_y),
                QtCore.QPointF(squid_center_x + math.cos(self.current_view_angle - self.view_cone_angle/2) * cone_length,
                               squid_center_y + math.sin(self.current_view_angle - self.view_cone_angle/2) * cone_length),
                QtCore.QPointF(squid_center_x + math.cos(self.current_view_angle + self.view_cone_angle/2) * cone_length,
                               squid_center_y + math.sin(self.current_view_angle + self.view_cone_angle/2) * cone_length)
            ]

            cone_polygon = QtGui.QPolygonF(cone_points)
            self.view_cone_item.setPolygon(cone_polygon)
        else:
            self.remove_view_cone()

    def remove_view_cone(self):
        if self.view_cone_item is not None:
            self.ui.scene.removeItem(self.view_cone_item)
            self.view_cone_item = None
