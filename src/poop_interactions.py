# POOP INTERACTIONS

import math
import time
import random
import os
import uuid
from PyQt5 import QtCore, QtWidgets, QtGui

class PoopInteractionManager:
    def __init__(self, squid, logic, scene, message_callback, config_manager):
        self.squid = squid
        self.logic = logic
        self.scene = scene
        self.show_message = message_callback
        self.config_manager = config_manager
        self.poop_config = config_manager.get_poop_config()

        # Poop interaction state
        self.target_poop = None
        self.poop_test_phase = 0  # 0=approach, 1=carry, 2=throw
        self.poop_carry_time = 0
        self.poop_carry_duration = 0
        
        # Initialize timers
        self.poop_test_timer = QtCore.QTimer()
        self.throw_animation_timer = QtCore.QTimer()
        
        # Connect timers
        self.poop_test_timer.timeout.connect(self.update_poop_test)
        self.throw_animation_timer.timeout.connect(self.update_throw_animation)
        
        # Initialize throw velocity variables
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0
        # The poop in flight, and its throw (aimed and powered as a rock's:
        # src/throwing.py) - what reaches a squid it strikes is the fact only.
        self.flying_poop = None
        self.current_throw = None

        # Add multiplayer support
        self.multiplayer_plugin = None
        self.setup_multiplayer_integration()

    def setup_multiplayer_integration(self):
        """Set up hooks for multiplayer integration"""
        if not hasattr(self.logic, 'plugin_manager'):
            return False
            
        # Get multiplayer plugin
        multiplayer_plugin = None
        for plugin_name, plugin_data in self.logic.plugin_manager.plugins.items():
            if plugin_name == "multiplayer_plugin":
                # Get the actual plugin instance
                multiplayer_plugin = plugin_data.get('instance')
                break
        
        if multiplayer_plugin:
            # Store reference
            self.multiplayer_plugin = multiplayer_plugin
            
            print("[PoopInteraction] Successfully integrated with multiplayer plugin")
            return True
        
        return False

    def is_valid_poop(self, item):
        """Check if item is a valid poop"""
        if not isinstance(item, QtWidgets.QGraphicsPixmapItem):
            return False
        return (hasattr(item, 'category') and item.category == 'poop') or \
               (hasattr(item, 'filename') and 'poop' in item.filename.lower())

    def can_pick_up_poop(self, poop):
        """Check if squid can pick up this poop"""
        if not self.is_valid_poop(poop):
            return False
        if hasattr(poop, 'is_being_carried') and poop.is_being_carried:
            return False
            
        # Check if poop is in cooldown after being thrown
        if hasattr(poop, 'throw_cooldown_until'):
            if time.time() < poop.throw_cooldown_until:
                return False      
        return True

    def attach_poop_to_squid(self, poop):
        """Visually attach poop to squid at tentacle position"""
        poop.setParentItem(self.squid.squid_item)
        
        # Set random hold duration between 3-9 seconds
        self.squid.poop_hold_duration = random.uniform(3.0, 9.0)
        self.squid.poop_hold_start_time = time.time()
        self.squid.poop_decision_made = False
        
        offset = -50  # Both vertical and horizontal offset
        
        # Calculate position based on squid direction
        if self.squid.squid_direction == "right":
            # Position poop near right tentacles
            poop.setPos(self.squid.squid_width - 40 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "left":
            # Position poop near left tentacles
            poop.setPos(10 + offset, 
                    self.squid.squid_height - 30 + offset)
        elif self.squid.squid_direction == "up":
            # Position poop near upper tentacles
            poop.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 40 + offset)
        else:  # down/default
            poop.setPos(self.squid.squid_width//2 - 15 + offset, 
                    self.squid.squid_height - 20 + offset)
        
        poop.is_being_carried = True
        self.squid.is_carrying_poop = True
        self.squid.carried_poop = poop
        poop.setZValue(self.squid.squid_item.zValue() + 1)
        
        # Scale poop to appropriate size
        poop.setScale(1.0)
        
        return True
    
    def check_poop_hold_time(self):
        """Check if holding time elapsed and make decision"""
        if not hasattr(self.squid, 'carrying_poop') or not self.squid.carrying_poop or not hasattr(self.squid, 'poop_decision_made') or self.squid.poop_decision_made:
            return
        
        current_time = time.time()
        if current_time - self.squid.poop_hold_start_time >= self.squid.poop_hold_duration:
            self.squid.poop_decision_made = True
            self.decide_poop_action()

    def decide_poop_action(self):
        """Throw or drop: its play neuron decides, as for a rock - not dice."""
        from .throwing import throw_or_drop
        if throw_or_drop(self._brain_state()):
            if self.throw_poop() or getattr(self.squid, 'carried_poop', None) is not None:
                return              # thrown, or held while it closes in
        self.drop_poop()
        if self.show_message:
            self.show_message("Squid dropped the poop")

    def _brain_state(self):
        brain = getattr(getattr(self.logic, 'brain_window', None), 'brain_widget', None)
        return dict(getattr(brain, 'state', None) or {})

    def drop_poop(self):
        """Gently place the poop below the squid"""
        if not hasattr(self.squid, 'carrying_poop') or not self.squid.carrying_poop or not hasattr(self.squid, 'carried_poop') or not self.squid.carried_poop:
            return
        
        poop = self.squid.carried_poop
        poop.setParentItem(None)
        poop.setPos(
            self.squid.squid_x + self.squid.squid_width//2 - poop.boundingRect().width()//2,
            self.squid.squid_y + self.squid.squid_height + 10
        )
        self.squid.is_carrying_poop = False
        self.squid.carried_poop = None

    def start_poop_test(self, poop=None):
        """Start test with guaranteed clean state and random carry duration"""
        self.cleanup()  # Reset everything first
        
        if poop is None:
            poops = [item for item in self.scene.items() 
                    if self.is_valid_poop(item) and item.isVisible()]
            if not poops:
                if self.show_message:
                    self.show_message("No available poops!")
                return False
            poop = min(poops, key=lambda p: math.hypot(
                p.sceneBoundingRect().center().x() - self.squid.squid_x,
                p.sceneBoundingRect().center().y() - self.squid.squid_y
            ))
        
        self.target_poop = poop
        self.poop_test_phase = 0
        # Use the config values for duration
        self.poop_carry_duration = random.uniform(
            self.poop_config['min_carry_duration'],
            self.poop_config['max_carry_duration']
        )
        self.poop_carry_time = 0  # Reset carry timer
        self.poop_test_timer.start(100)  # 100ms updates
        return True

    def throw_poop(self, direction=None):
        """Throw the carried poop - aimed and as hard as the squid's network
        throws it, exactly as a rock (src/throwing.py): at the nearest squid
        in its view cone, else along its gaze. A squid it strikes is not
        harmed, but it is splattered (throwing.HIT_EFFECTS). `direction` is
        ignored; it is kept for callers that still pass one."""
        from .interactions import (CLOSE_IN_SECONDS, RockInteractionManager as Rock,
                                   close_in, squids_in_view, tank_bounds)
        from .throwing import plan_throw, describe, out_of_reach, practice_of
        # Prevent multiple throws
        if self.throw_animation_timer.isActive():
            return False
            
        if not hasattr(self.squid, 'carried_poop') or not self.squid.carried_poop:
            return False
        
        poop = self.squid.carried_poop

        rect = self.squid.squid_item.sceneBoundingRect()
        bounds = (tank_bounds(self.scene, poop) if hasattr(poop, 'sceneBoundingRect')
                  else None)
        plan = plan_throw(self._brain_state(), (rect.center().x(), rect.center().y()),
                          float(getattr(self.squid, 'current_view_angle', 0.0)),
                          squids_in_view(self.scene, self.squid),
                          slowest=Rock.THROW_SLOWEST, fastest=Rock.THROW_FASTEST,
                          gravity=Rock.THROW_GRAVITY, drag=Rock.THROW_DRAG, bounds=bounds,
                          practice=practice_of(getattr(self.squid, 'statistics', None)))
        # Beyond this throw: keep it, close in, look again shortly.
        if out_of_reach(plan):
            close_in(self.squid, self.logic, plan)
            self.squid.poop_decision_made = False
            self.squid.poop_hold_start_time = time.time()
            self.squid.poop_hold_duration = CLOSE_IN_SECONDS
            return False
        self.squid._closing_in_on = None

        # Detach from squid and reset parent to scene
        poop.setParentItem(None)
        plan['what'] = 'poop'
        self.current_throw = dict(plan, hit=None, throw_id=uuid.uuid4().hex,
                                  source_uuid=str(getattr(self.squid, 'uuid', '')))
        self.flying_poop = poop
        poop.is_being_carried = False
        self.squid.carried_poop = None
        self.squid.is_carrying_poop = False
        self.throw_velocity_x, self.throw_velocity_y = plan['vx'], plan['vy']
        direction = 'right' if plan['vx'] >= 0 else 'left'

        # Set squid status
        if hasattr(self.squid, 'status'):
            self.squid.status = (f"throwing poop at {plan['target']}" if plan['target']
                                 else "throwing poop")
        if self.show_message:
            self.show_message(describe(plan))
        
        # Set position to squid's center in scene coordinates
        poop_rect = poop.boundingRect()
        poop.setPos(
            rect.center().x() - poop_rect.width()/2,
            min(rect.center().y() - poop_rect.height()/2,
                self.scene.sceneRect().bottom() - 50 - poop_rect.height())
        )
        
        poop.setVisible(True)
        
        # Apply stat changes
        self.squid.happiness = min(100, self.squid.happiness - 5)
        self.squid.satisfaction = min(100, self.squid.satisfaction - 3)
        self.squid.anxiety = min(100, self.squid.anxiety + 10)
        self.logic.statistics_window.award(-75)
        
        # Simplified negative memory
        memory_details = {
            "activity": "poop_throwing",
            "item": getattr(poop, 'filename', '') or '',
            "effects": {
                "happiness": -5,
                "satisfaction": -3,
                "anxiety": 10
            },
            "description": describe(plan),
            "is_positive": False,
            # Where it was aimed, how hard, and what drove it.
            "throw": {"aimed_at": plan['target'], "driven_by": plan['driven_by'],
                      "drive": plan['drive'], "angle": plan['angle'],
                      "speed": plan['speed'], "throw_id": self.current_throw['throw_id']},
        }

        # Deliver the completed throw once to the canonical statistics model.
        if hasattr(self.logic, 'track_poop_thrown'):
            self.logic.track_poop_thrown()
        
        # Add with moderate importance
        self.squid.memory_manager.add_short_term_memory(
            'play',
            'poop_throwing',
            memory_details,
            importance=5
        )
        
        # Broadcast to network if multiplayer plugin is available
        if hasattr(self, 'multiplayer_plugin') and self.multiplayer_plugin:
            try:
                self.multiplayer_plugin.throw_poop_network(poop, direction)
            except Exception as e:
                print(f"[PoopInteraction] Error broadcasting poop throw: {e}")
        
        self.throw_animation_timer.start(50)
        return True

    def update_poop_test(self):
        """Handle the poop test sequence (approach, carry)"""
        if not self.target_poop:
            self.cleanup()
            return
        
        # Let the Squid class handle the timing and decision making
        if self.poop_test_phase == 0:  # Approach phase
            poop_center = self.target_poop.sceneBoundingRect().center()
            squid_center = self.squid.squid_item.sceneBoundingRect().center()
            distance = math.hypot(poop_center.x()-squid_center.x(),
                                poop_center.y()-squid_center.y())

            if distance < 50:  # Close enough to pick up
                if self.attach_poop_to_squid(self.target_poop):
                    self.poop_test_phase = 1  # Move to carry phase
                else:
                    self.cleanup()
            else:
                self.squid.move_toward_position(poop_center)

    def update_throw_animation(self):
        """One step of flight (the rock's physics), then sweep the path for
        the first squid it splatters - once per throw."""
        from .interactions import RockInteractionManager as Rock, first_struck
        from .throwing import flight_step
        poop = self.flying_poop
        if poop is None or poop.scene() is None:
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()
            return
        rect = poop.sceneBoundingRect()
        centre = rect.center()
        start = (centre.x(), centre.y())
        scene = self.scene.sceneRect()
        bounds = (scene.left() + rect.width()/2, scene.right() - rect.width()/2,
                  scene.top() + rect.height()/2, scene.bottom() - 50 - rect.height()/2)
        end, velocity, landed = flight_step(start, (self.throw_velocity_x, self.throw_velocity_y),
                                            bounds, gravity=Rock.THROW_GRAVITY)
        poop.moveBy(end[0] - start[0], end[1] - start[1])
        self.throw_velocity_x, self.throw_velocity_y = velocity
        throw = self.current_throw
        if throw and throw.get('hit') is None:
            resident = getattr(getattr(self.logic, 'squid', None), 'squid_item', None)
            item = first_struck(self.scene, poop, start, end, self.squid.squid_item,
                                resident, Rock.HIT_RADIUS)
            if item is not None:
                throw['hit'] = str(getattr(item, 'peer_uuid', '') or id(item))
                notify = getattr(self.logic, 'on_rock_hit', None)
                if callable(notify):
                    notify(item, dict(throw))
        if landed:
            self.throw_animation_timer.stop()
            self.cleanup_after_throw()

    def cleanup(self):
        """Reset all poop interaction state"""
        self.poop_test_timer.stop()
        self.throw_animation_timer.stop()
        
        self.target_poop = None
        self.poop_test_phase = 0
        self.poop_carry_time = 0
        self.poop_carry_duration = 0
        
        if hasattr(self.squid, 'is_carrying_poop') and self.squid.is_carrying_poop:
            self.squid.is_carrying_poop = False
            self.squid.carried_poop = None

    def cleanup_after_throw(self):
        poop = self.flying_poop or getattr(self.squid, 'carried_poop', None)
        if poop is not None:
            # Set cooldown on the poop so it can't be picked up immediately
            cooldown = self.poop_config.get('cooldown_after_throw', 10.0)
            poop.throw_cooldown_until = time.time() + cooldown
            poop.is_being_carried = False
        self.flying_poop = None
        self.current_throw = None
        self.squid.carried_poop = None
        
        # Reset squid states
        self.squid.is_carrying_poop = False
        
        # Reset status to default if it was set to "throwing_poop"
        if hasattr(self.squid, 'status') and self.squid.status == "throwing_poop":
            self.squid.status = "roaming"
        
        self.throw_velocity_x = 0
        self.throw_velocity_y = 0
        self.cleanup()

    def setup_timers(self, interval=100):
        """Configure timer intervals"""
        self.poop_test_timer.setInterval(interval)
        self.throw_animation_timer.setInterval(50)



