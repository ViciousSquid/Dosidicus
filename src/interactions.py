
# ROCK INTERACTIONS

import math
import time
import random
import uuid
from PyQt5 import QtCore, QtWidgets, QtGui

def squids_in_view(scene, squid):
    """(name, x, y) of every other squid in `squid`'s view cone - what a
    thrown rock or poop can be aimed at (src/throwing.py)."""
    from .vision_cone import VIEW_CONE_ANGLE, in_view_cone
    rect = squid.squid_item.sceneBoundingRect()
    cx, cy = rect.center().x(), rect.center().y()
    reach = math.hypot(scene.width(), scene.height())
    angle = float(getattr(squid, 'current_view_angle', 0.0))
    seen = []
    for item in scene.items():
        if (item is squid.squid_item or getattr(item, 'category', None) != 'squid'
                or not item.isVisible()):
            continue
        centre = item.sceneBoundingRect().center()
        if in_view_cone(cx, cy, angle, VIEW_CONE_ANGLE, reach, centre.x(), centre.y()):
            seen.append((getattr(item, 'squid_name', 'another squid'),
                         centre.x(), centre.y()))
    return seen


def first_struck(scene, projectile, start, end, thrower_item, resident_item, hit_radius):
    """The first squid a projectile's path from start to end passes through,
    or None. Swept (throwing.swept_hit), so a fast throw cannot tunnel."""
    from .throwing import swept_hit
    contacts = []
    size = max(projectile.sceneBoundingRect().width(), projectile.sceneBoundingRect().height())
    for item in scene.items():
        if (item is thrower_item
                or (item is not resident_item and getattr(item, 'category', None) != 'squid')
                or not item.isVisible()):
            continue
        body = item.sceneBoundingRect()
        other = body.center()
        radius = max(hit_radius, body.width()/2, body.height()/2) + size / 2
        t = swept_hit(start, end, (other.x(), other.y()), radius)
        if t is not None:
            contacts.append((t, item))
    return min(contacts, key=lambda c: c[0])[1] if contacts else None


class RockInteractionManager:
    def __init__(self, squid, logic, scene, message_callback, config_manager):
        self.squid = squid
        self.logic = logic
        self.scene = scene
        self.show_message = message_callback
        self.config_manager = config_manager
        self.rock_config = config_manager.get_rock_config()

        # Rock interaction state
        self.target_rock = None
        self.rock_test_phase = 0  # 0=approach, 1=carry, 2=throw
        self.rock_carry_time = 0
        self.rock_carry_duration = 0
        
        # Initialize timers
        self.rock_test_timer = QtCore.QTimer()
        self.throw_animation_timer = QtCore.QTimer()
        
        # Connect timers
        self.rock_test_timer.timeout.connect(self.update_rock_test)
        self.throw_animation_timer.timeout.connect(self.update_throw_animation)
        
        # Initialize throw velocity variables
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0
        self.flying_rock = None

        # Add multiplayer support
        self.multiplayer_plugin = None
        self.setup_multiplayer_integration()

    def setup_multiplayer_integration(self):
        """Set up hooks for multiplayer integration"""
        if not hasattr(self.logic, 'plugin_manager'):
            return False
            
        # Plugins are discovered after the interaction manager is constructed.
        # Retry lookup when needed, using the manager's canonical key.
        data = self.logic.plugin_manager.plugins.get('multiplayer', {})
        self.multiplayer_plugin = data.get('instance')
        return self.multiplayer_plugin is not None

    def is_valid_rock(self, item):
        """Check if item is a valid rock"""
        if not isinstance(item, QtWidgets.QGraphicsPixmapItem):
            return False
        if getattr(item, 'category', None) == 'headstone':
            return False
        return (hasattr(item, 'category') and item.category == 'rock') or \
               (hasattr(item, 'filename') and 'rock' in item.filename.lower())

    def can_pick_up_rock(self, rock):
        """Check if squid can pick up this rock"""
        if not self.is_valid_rock(rock):
            return False
        if getattr(rock, 'is_projectile', False):
            return False
        if hasattr(rock, 'is_being_carried') and rock.is_being_carried:
            return False
        # Check if rock is in cooldown after being thrown
        if hasattr(rock, 'throw_cooldown_until'):
            if time.time() < rock.throw_cooldown_until:
                return False
        return True

    def attach_rock_to_squid(self, rock):
        """Visually attach rock to squid at tentacle position"""
        if (self.squid.carrying_rock or self.throw_animation_timer.isActive()
                or not self.can_pick_up_rock(rock) or self.squid.is_sleeping):
            return False
        rock.setParentItem(self.squid.squid_item)
        
        # Use config values for hold duration
        config = self.rock_config
        self.squid.rock_hold_duration = random.uniform(
            config['min_carry_duration'],
            config['max_carry_duration']
        )
        self.squid.rock_hold_start_time = time.time()
        self.squid.rock_decision_made = False
        
        offset = -50  # Both vertical and horizontal offset
        
        # Calculate position based on squid direction
        if self.squid.squid_direction == "right":
            # Position rock near right tentacles
            rock.setPos(self.squid.squid_width - 40 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "left":
            # Position rock near left tentacles
            rock.setPos(10 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "up":
            # Position rock near upper tentacles
            rock.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 40 + offset)
        else:  # down/default
            rock.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 20 + offset)
        
        rock.is_being_carried = True
        self.squid.is_carrying_rock = True
        self.squid.carried_rock = rock
        rock.setZValue(self.squid.squid_item.zValue() + 1)
        
        # Scale rock to appropriate size
        rock.setScale(1.0)
        
        # Update squid status
        self.squid.status = "carrying rock"
        
        return True
    
    def check_rock_hold_time(self):
        """Check if holding time elapsed and make decision"""
        if not hasattr(self.squid, 'carrying_rock') or not self.squid.carrying_rock or not hasattr(self.squid, 'rock_decision_made') or self.squid.rock_decision_made:
            return
        
        current_time = time.time()
        if current_time - self.squid.rock_hold_start_time >= self.squid.rock_hold_duration:
            self.squid.rock_decision_made = True
            self.decide_rock_action()

    def decide_rock_action(self):
        """Throw the rock if the squid's play neuron is firing; else put it down."""
        from .throwing import throw_or_drop
        if self.throw_animation_timer.isActive():
            return False
        if throw_or_drop(self._brain_state()):
            return self.squid.throw_rock()
        else:
            self.drop_rock()
            if self.show_message:
                self.show_message("Squid dropped the rock")

    def drop_rock(self):
        """Release possession and settle the rock within the tank."""
        if self.throw_animation_timer.isActive() or not self.squid.carried_rock:
            return False
        rock = self.squid.carried_rock
        centre = rock.sceneBoundingRect().center()
        rock.setParentItem(None)
        rect = rock.sceneBoundingRect()
        bounds = self.scene.sceneRect()
        x = max(bounds.left(), min(bounds.right() - rect.width(), centre.x() - rect.width()/2))
        y = max(bounds.top(), min(bounds.bottom() - rect.height() - 50,
                                self.squid.squid_y + self.squid.squid_height + 10))
        rock.setPos(x, y)
        rock.is_being_carried = False
        rock.throw_cooldown_until = time.time() + self.rock_config.get('cooldown_after_throw', 10.0)
        self.squid.carrying_rock = False
        self.squid.carried_rock = None
        self.squid.rock_decision_made = True
        self._end_carry_sequence()
        self.squid.status = 'roaming'
        return True

    def _end_carry_sequence(self):
        self.rock_test_timer.stop()
        self.target_rock = None
        self.rock_test_phase = 0
        self.rock_carry_time = 0
        self.rock_carry_duration = 0

    def start_rock_test(self, rock=None):
        """Start test with guaranteed clean state and random carry duration"""
        if self.throw_animation_timer.isActive() or self.squid.carrying_rock:
            return False
        self._end_carry_sequence()
        
        if rock is None:
            # Filter rocks that are valid, visible, and not on cooldown
            rocks = [item for item in self.scene.items() 
                    if self.is_valid_rock(item) and item.isVisible() and self.can_pick_up_rock(item)]
            if not rocks:
                if self.show_message:
                    self.show_message("No available rocks!")
                return False
            rock = min(rocks, key=lambda r: math.hypot(
                r.sceneBoundingRect().center().x() - self.squid.squid_x,
                r.sceneBoundingRect().center().y() - self.squid.squid_y
            ))
        elif not self.can_pick_up_rock(rock):
            if self.show_message:
                self.show_message("Rock is on cooldown!")
            return False
        
        self.target_rock = rock
        self.rock_test_phase = 0
        # Use the config values for duration
        self.rock_carry_duration = random.uniform(
            self.rock_config['min_carry_duration'],
            self.rock_config['max_carry_duration']
        )
        self.rock_carry_time = 0  # Reset carry timer
        self.rock_test_timer.start(100)  # 100ms updates
        return True

    def highlight_rock(self, rock):
        """Visual feedback for selected rock"""
        highlight = QtWidgets.QGraphicsOpacityEffect()
        highlight.setOpacity(0.3)  # Initial opacity
        rock.setGraphicsEffect(highlight)
        
        # Animate highlight
        self.animate_highlight(highlight)

    def animate_highlight(self, highlight_effect):
        """Pulse animation for rock highlight"""
        self.highlight_animation = QtCore.QPropertyAnimation(highlight_effect, b"opacity")
        self.highlight_animation.setDuration(1000)
        self.highlight_animation.setStartValue(0.3)
        self.highlight_animation.setEndValue(0.8)
        self.highlight_animation.setLoopCount(3)
        self.highlight_animation.start()

    #: Throw speeds, in pixels per 50 ms animation step, and the rock's gravity.
    THROW_SLOWEST = 6.0
    THROW_FASTEST = 20.0
    THROW_GRAVITY = 0.3
    THROW_DRAG = 0.02               # throwing.flight_step keeps 0.98 of vx a step
    #: A rock passing this close to another squid's centre hits it.
    HIT_RADIUS = 45.0

    def _brain_state(self):
        brain = getattr(getattr(self.logic, 'brain_window', None), 'brain_widget', None)
        return dict(getattr(brain, 'state', None) or {})

    def _squids_in_view(self):
        """(name, x, y) of every other squid in this squid's view cone."""
        return squids_in_view(self.scene, self.squid)

    def throw_rock(self, direction=None, *, cause=None):
        """Throw the carried rock - aimed and as hard as the squid's network throws it.

        Where: at the nearest squid in its view cone, leading for the drop,
        else along its gaze. How hard: from its play neuron, or its
        aggression if that is stronger (src/throwing.py). `direction` is
        ignored; it is kept for callers that still pass one.
        """
        from .throwing import plan_throw, throw_or_drop, describe as describe_throw
        # Prevent multiple throws
        if self.throw_animation_timer.isActive():
            return False
            
        if not hasattr(self.squid, 'carried_rock') or not self.squid.carried_rock:
            return False
        
        state = self._brain_state()
        if cause is None and not throw_or_drop(state):
            return False
        # A user-bound output is already a decision by that neuron. Its
        # activation, rather than an unrelated play level, drives this throw.
        if cause is not None:
            neuron, activation = cause
            state = {'act_play': activation}
        config = self.rock_config
        rock = self.squid.carried_rock
        
        # Detach from squid and reset parent to scene
        rock.setParentItem(None)

        rect = self.squid.squid_item.sceneBoundingRect()
        plan = plan_throw(state, (rect.center().x(), rect.center().y()),
                          float(getattr(self.squid, 'current_view_angle', 0.0)),
                          self._squids_in_view(), slowest=self.THROW_SLOWEST,
                          fastest=self.THROW_FASTEST, gravity=self.THROW_GRAVITY,
                          drag=self.THROW_DRAG)
        if cause is not None:
            plan['driven_by'] = neuron
        self.current_throw = dict(plan, hit=None, throw_id=uuid.uuid4().hex,
                                 source_uuid=str(self.squid.uuid))
        self.flying_rock = rock
        rock.is_projectile = True
        rock.is_being_carried = False
        self.squid.carrying_rock = False
        self.squid.carried_rock = None
        self.squid.rock_decision_made = True
        self._end_carry_sequence()
        self.throw_velocity_x, self.throw_velocity_y = plan['vx'], plan['vy']
        direction = 'right' if plan['vx'] >= 0 else 'left'
        if hasattr(self.squid, 'status'):
            self.squid.status = (f"throwing rock at {plan['target']}" if plan['target']
                                 else "throwing rock")
        if self.show_message:
            self.show_message(describe_throw(plan))
        
        # Set position to squid's center in scene coordinates
        squid_rect = self.squid.squid_item.sceneBoundingRect()
        rock_rect = rock.sceneBoundingRect()
        rock.setPos(
            squid_rect.center().x() - rock_rect.width()/2,
            min(squid_rect.center().y() - rock_rect.height()/2,
                self.scene.sceneRect().bottom() - 50 - rock_rect.height())
        )
        
        rock.setVisible(True)
        
        # Apply stat changes
        self.squid.happiness = min(100, self.squid.happiness + config['happiness_boost'])
        self.squid.satisfaction = min(100, self.squid.satisfaction + config['satisfaction_boost'])
        self.squid.anxiety = max(0, self.squid.anxiety - config['anxiety_reduction'])
        self.logic.statistics_window.award(50)
        
        # Simplified positive memory
        rock_filename = getattr(rock, 'filename', '') or ''
        is_urchin = 'rock03' in rock_filename.lower()
        memory_details = {
            "activity": "urchin_throwing" if is_urchin else "rock_throwing",
            "item": rock_filename,
            "effects": {
                "happiness": config['happiness_boost'],
                "satisfaction": config['satisfaction_boost'],
                "anxiety": -config['anxiety_reduction']
            },
            "description": "Had fun throwing an urchin!" if is_urchin else "Had fun throwing a rock!",
            "is_positive": True,
            # Where it was aimed, how hard, and what drove it.
            "throw": {"aimed_at": plan['target'], "driven_by": plan['driven_by'],
                      "drive": plan['drive'], "angle": plan['angle'],
                      "speed": plan['speed'], "throw_id": self.current_throw['throw_id']},
        }

        # Deliver the completed throw once to the canonical statistics model.
        if hasattr(self.logic, 'track_rock_thrown'):
            self.logic.track_rock_thrown()
        
        # Add with importance (2) and positive formatting
        self.squid.memory_manager.add_short_term_memory(
            'play',
            memory_details["activity"],
            memory_details,
            importance=2
        )
        
        self.throw_animation_timer.start(50)
        return True


    def update_rock_test(self):
        """Handle the rock test sequence (approach, carry)"""
        if not self.target_rock:
            self.cleanup()
            return
        
        if self.rock_test_phase == 0:  # Approach phase
            rock_center = self.target_rock.sceneBoundingRect().center()
            squid_center = self.squid.squid_item.sceneBoundingRect().center()
            distance = math.hypot(rock_center.x()-squid_center.x(),
                                rock_center.y()-squid_center.y())

            if distance < 50:  # Close enough to pick up
                if self.attach_rock_to_squid(self.target_rock):
                    self.rock_test_phase = 1  # Move to carry phase
                else:
                    self.cleanup()
            else:
                self.squid.move_toward_position(rock_center)
                
        elif self.rock_test_phase == 1:  # Carry phase
            # Update the carry time
            self.rock_carry_time += self.rock_test_timer.interval() / 1000.0
            
            # Check if carry duration has elapsed
            if self.rock_carry_time >= self.rock_carry_duration:
                # The squid's network decides: throw, or put it down.
                self.decide_rock_action()
                        
                self._end_carry_sequence()

    def update_throw_animation(self):
        """Move a projectile independently of possession, then sweep its path."""
        from .throwing import flight_step
        rock = self.flying_rock
        if rock is None or rock.scene() is None:
            self.cleanup_after_throw()
            return
        rect = rock.sceneBoundingRect()
        centre = rect.center()
        start = (centre.x(), centre.y())
        scene = self.scene.sceneRect()
        bounds = (scene.left() + rect.width()/2, scene.right() - rect.width()/2,
                  scene.top() + rect.height()/2, scene.bottom() - 50 - rect.height()/2)
        end, velocity, landed = flight_step(start,
            (self.throw_velocity_x, self.throw_velocity_y), bounds)
        rock.moveBy(end[0] - start[0], end[1] - start[1])
        self.throw_velocity_x, self.throw_velocity_y = velocity
        self._check_hit(rock, start, end)
        if landed:
            self.cleanup_after_throw()

    def _check_hit(self, rock, start=None, end=None):
        """First struck body, once per projectile, including its landing step."""
        throw = getattr(self, 'current_throw', None)
        if not throw or throw.get('hit') is not None:
            return
        centre = rock.sceneBoundingRect().center()
        end = end or (centre.x(), centre.y())
        start = start or end
        resident = getattr(getattr(self.logic, 'squid', None), 'squid_item', None)
        item = first_struck(self.scene, rock, start, end, self.squid.squid_item,
                            resident, self.HIT_RADIUS)
        if item is not None:
            throw['hit'] = str(getattr(item, 'peer_uuid', '') or id(item))
            notify = getattr(self.logic, 'on_rock_hit', None)
            if callable(notify):
                notify(item, dict(throw))

    def throw_from_visitor(self, actor, rock, intent, visual):
        """A body executes the remote play command; no visitor brain is built."""
        from types import SimpleNamespace
        from .throwing import plan_throw
        from .vision_cone import FACING_ANGLES, VIEW_CONE_ANGLE, in_view_cone
        angle = FACING_ANGLES.get(actor.facing, 0.)
        centre = visual.sceneBoundingRect().center()
        origin = (centre.x(), centre.y())
        targets = []
        resident = self.squid.squid_item
        for item in self.scene.items():
            if item is visual or not item.isVisible():
                continue
            if item is not resident and getattr(item, 'category', None) != 'squid':
                continue
            c = item.sceneBoundingRect().center()
            if in_view_cone(*origin, angle, VIEW_CONE_ANGLE, math.hypot(self.scene.width(), self.scene.height()), c.x(), c.y()):
                name = self.squid.name if item is resident else getattr(item, 'squid_name', 'Squid')
                targets.append((name, c.x(), c.y()))
        plan = plan_throw({'act_play': intent.activation, 'aggression': intent.aggression},
                          origin, angle, targets, slowest=self.THROW_SLOWEST,
                          fastest=self.THROW_FASTEST, gravity=self.THROW_GRAVITY,
                          drag=self.THROW_DRAG)
        plan.update(throw_id=uuid.uuid4().hex, source_uuid=actor.uuid,
                    source_identity=actor.identity.to_payload(), hit=None)
        flight = object.__new__(RockInteractionManager)
        flight.squid = SimpleNamespace(squid_item=visual, status='throwing rock')
        flight.logic, flight.scene, flight.rock_config = self.logic, self.scene, self.rock_config
        flight.flying_rock, flight.current_throw = rock, plan
        flight.throw_velocity_x, flight.throw_velocity_y = plan['vx'], plan['vy']
        flight.throw_animation_timer = QtCore.QTimer()
        flight.throw_animation_timer.timeout.connect(flight.update_throw_animation)
        rock.setParentItem(None)
        if rock.scene() is None:
            self.scene.addItem(rock)
        rect = rock.sceneBoundingRect()
        floor = self.scene.sceneRect().bottom() - 50 - rect.height()/2
        rock.setPos(origin[0] - rect.width()/2, min(floor, origin[1]) - rect.height()/2)
        rock.is_being_carried = False
        if not hasattr(self, '_visitor_flights'):
            self._visitor_flights = []
        self._visitor_flights[:] = [f for f in self._visitor_flights if f.flying_rock is not None]
        self._visitor_flights.append(flight)
        rock.is_projectile = True
        flight.throw_animation_timer.start(50)
        return plan

    def cleanup(self):
        """Cancel only this manager's interactions, leaving physical rocks free."""
        self._end_carry_sequence()
        for flight in getattr(self, '_visitor_flights', []):
            flight.cleanup_after_throw()
        self._visitor_flights = []
        self.cleanup_after_throw()
        if self.squid.carried_rock is not None:
            self.drop_rock()

    def cleanup_after_throw(self):
        self.throw_animation_timer.stop()
        rock = self.flying_rock
        if rock is not None:
            rock.throw_cooldown_until = time.time() + self.rock_config.get('cooldown_after_throw', 10.0)
            rock.is_being_carried = False
            rock.is_projectile = False
        self.flying_rock = None
        self.current_throw = None
        self.throw_velocity_x = self.throw_velocity_y = 0
        if 'throwing rock' in self.squid.status:
            self.squid.status = 'roaming'


    def setup_timers(self, interval=100):
        """Configure timer intervals"""
        self.rock_test_timer.setInterval(interval)
        self.throw_animation_timer.setInterval(50)
