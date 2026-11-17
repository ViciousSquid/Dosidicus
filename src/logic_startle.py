"""Being startled: the fright, the flight, and the ink cloud left behind.
"""
import logging
from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
import math
from .squid import Personality

_LOG = logging.getLogger(__name__)


class StartleAndInkMixin:
    """Part of TamagotchiLogic (see tamagotchi_logic.py); not used on its own."""

    def check_for_startle(self):
        if not self.mental_states_enabled:
            return

        # Only check for new startle if not currently startled and initial startle allowed
        if self.squid.is_fleeing or not self.initial_startle_allowed:
            return

        if self.startle_cooldown > 0:
            self.startle_cooldown -= 1
            return

        # Base chance of being startled
        startle_chance = 0.002  # low base chance

        # Increase chance if anxiety is high
        if self.squid.anxiety > 70:
            startle_chance *= (self.squid.anxiety / 50)  # Up to 2x more likely when anxiety is >70

        # Check for startle
        if random.random() < startle_chance:
            self.startle_squid()

    def startle_squid(self, source="unknown"):
        if not self.mental_states_enabled and source != 'rock_hit':
            return

        if not getattr(self, 'initial_startle_allowed', False) and source != 'rock_hit':
            return

        try:
            # --- existing speed init -------------------------------------------------
            if not hasattr(self.squid, 'base_speed'):
                self.squid.base_speed = 90
            if not hasattr(self.squid, 'current_speed'):
                self.squid.current_speed = self.squid.base_speed

            # Being startled is an aversive outcome: whatever was firing in the
            # right order just beforehand gets weakened, which is how a squid
            # comes to avoid the thing that startled it.
            bw = getattr(self.brain_window, 'brain_widget', None)
            if bw is not None and hasattr(bw, 'provide_outcome_feedback'):
                bw.provide_outcome_feedback(-0.3, f"it was startled by {source}")

            # --- existing startled state / status block ------------------------------
            self.squid.mental_state_manager.set_state("startled", True)
            self.startle_cooldown = self.startle_cooldown_max
            previous_status = getattr(self.squid, 'status', "roaming")

            if source == "first_resize":
                self.squid.status = "startled by environment change"
            elif source == "incoming_rock":
                self.squid.status = "startled by rock"
            elif source == "detected_squid":
                self.squid.status = "startled by other squid"
            elif source == "targeted_by_rock":
                self.squid.status = "fleeing"
            elif source in ["environment", "decoration"]:
                self.squid.status = "startled"
            else:
                if self.squid.personality == Personality.TIMID:
                    self.squid.status = "hiding"
                else:
                    self.squid.status = "startled"

            self.squid.is_fleeing = True
            self.statistics_window.award(-50)
            self.squid.current_speed = 180
            # squid_direction is what move_squid reads; assigning .direction
            # merely created a new attribute nothing consulted.
            self.squid.squid_direction = random.choice(['up', 'down', 'left', 'right'])

            # Record the accepted startle once on the model.
            self.track_startle()

            # --- resilience / anxiety / ink logic --------------------------
            stress_neuron_count = 0
            if self.brain_window and hasattr(self.brain_window, 'brain_widget'):
                stress_neuron_count = self.brain_window.brain_widget.get_stress_neuron_count()
            resilience_factor = math.log(stress_neuron_count + 1)

            if source == "first_resize":
                base_anxiety_increase = 5
                message = "The squid noticed its environment changing!"
                base_ink_chance = 0.6
            else:
                base_anxiety_increase = 15
                message = "The squid was startled!"
                base_ink_chance = 0.6

            anxiety_increase = max(0, base_anxiety_increase - (resilience_factor * 5))
            self.squid.anxiety = min(100, self.squid.anxiety + anxiety_increase)

            if stress_neuron_count > 0:
                self.brain_window.add_thought(
                    f"Startled, but felt {resilience_factor:.1f}x more resilient. "
                    f"Anxiety increased by only {anxiety_increase:.1f}."
                )

            # --- existing first-startle / ink / memory / timer ----------------------
            is_first_startle = not hasattr(self, '_has_startled_before')
            if is_first_startle:
                self._has_startled_before = True

            ink_chance = 0.9 if self.squid.anxiety > 60 else base_ink_chance
            produce_ink = is_first_startle or random.random() < ink_chance

            memory_value = (
                f"Startled! Status changed from {previous_status} to {self.squid.status}, "
                f"Speed {self.squid.current_speed}px, Direction {self.squid.squid_direction}"
            )
            self.squid.memory_manager.add_short_term_memory(
                'behavior', 'startle_response', memory_value
            )

            # Fear memory when anxiety is very high
            if self.squid.anxiety >= 80:
                self.squid.memory_manager.add_short_term_memory(
                    'emotion', 'fear',
                    f'Gripped by fear! Anxiety at {int(self.squid.anxiety)}.',
                    importance=6
                )

            self.show_message(message)
            if produce_ink:
                self.create_ink_cloud()

            QtCore.QTimer.singleShot(self.startle_cooldown_max * 100,
                                    lambda: self.end_fleeing(previous_status))

        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Error during startle: {str(e)}")
            self.show_message("The squid panicked!")

    def end_fleeing(self, previous_status="roaming"):
        """Reset speed and status after fleeing ends"""
        if hasattr(self, 'squid') and self.squid:
            self.squid.is_fleeing = False
            self.squid.current_speed = self.squid.base_speed
            
            # Set more descriptive status based on anxiety level
            if self.squid.anxiety > 80:
                self.squid.status = "extremely anxious"
            elif self.squid.anxiety > 60:
                self.squid.status = "anxious" 
            elif self.squid.anxiety > 40:
                self.squid.status = "nervous"
            elif self.squid.anxiety > 20:
                self.squid.status = "recovering from startle"
            else:
                # Use a more specific status based on personality
                if self.squid.personality == Personality.TIMID:
                    self.squid.status = "cautiously exploring"
                elif self.squid.personality == Personality.ADVENTUROUS:
                    self.squid.status = "boldly exploring"
                else:
                    self.squid.status = previous_status
                
            self.squid.mental_state_manager.set_state("startled", False)  # Explicitly clear startled state
            
            if self.debug_mode:
                print(f"Fleeing ended - status returned to {self.squid.status}")
            
            self.squid.memory_manager.add_short_term_memory(
                'behavior',
                'calm_after_startle',
                f"Returned to {self.squid.status} status after fleeing"
            )

    #: How long an ink cloud takes to fade away.
    INK_FADE_MS = 10000

    def create_ink_cloud(self, position=None, *, record=True):
        """Create an ink cloud with guaranteed fade-out after 10 seconds"""
        # Inking is something the squid did, and whatever follows is what it
        # will come to expect of inking - whether or not the ink had anything
        # to do with it (src/causal_learning: beliefs).
        if position is None:
            brain = getattr(getattr(self, 'brain_window', None), 'brain_widget', None)
            discovery = getattr(brain, 'action_discovery', None)
            if discovery is not None:
                try:
                    discovery.acted('inking', brain.state)
                except Exception as e:
                    _LOG.warning('Handled exception', exc_info=True)
                    print(f"[ActionDiscovery] ink not noted: {type(e).__name__}: {e}")
        from .display_scaling import DisplayScaling
        ink_cloud_pixmap = DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "inkcloud.png")))
        ink_cloud_item = QtWidgets.QGraphicsPixmapItem(ink_cloud_pixmap)
        
        # Set the center of the ink cloud to match the center of the squid
        squid = self.squid
        squid_center_x = squid.squid_x + squid.squid_width // 2
        squid_center_y = squid.squid_y + squid.squid_height // 2
        if position is not None:
            squid_center_x, squid_center_y = position
        ink_cloud_item.setPos(
            squid_center_x - ink_cloud_pixmap.width() // 2, 
            squid_center_y - ink_cloud_pixmap.height() // 2
        )
        
        squid.ui.scene.addItem(ink_cloud_item)
        
        # Create a QGraphicsOpacityEffect without a parent
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        opacity_effect.setOpacity(1.0)  # Start fully visible
        ink_cloud_item.setGraphicsEffect(opacity_effect)

        # Parented to the effect it animates: an unparented animation held only
        # by a local is collected the moment this returns, so the cloud never
        # faded - it sat at full opacity until the backup timer below removed
        # it all at once.
        fade_out_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity",
                                                       opacity_effect)
        fade_out_animation.setDuration(self.INK_FADE_MS)
        fade_out_animation.setStartValue(1.0)
        fade_out_animation.setEndValue(0.0)
        fade_out_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)

        # Connect the finished signal to remove the item
        fade_out_animation.finished.connect(lambda: self.remove_ink_cloud(ink_cloud_item))

        # Start the animation and deduct points
        fade_out_animation.start()
        if record:
            self.statistics_window.award(-250)
            self.record_statistic_event('ink_clouds_created')
        
        
        # Backup timer to force remove it, should the animation ever fail.
        QtCore.QTimer.singleShot(self.INK_FADE_MS + 500,
                                 lambda: self.force_remove_ink_cloud(ink_cloud_item))

    def force_remove_ink_cloud(self, ink_cloud_item):
        """Force remove the ink cloud if it still exists after timeout"""
        if ink_cloud_item in self.squid.ui.scene.items():
            self.squid.ui.scene.removeItem(ink_cloud_item)

    def remove_ink_cloud(self, ink_cloud_item):
        """Remove the ink cloud from the scene, once it has faded."""
        scene = self.user_interface.scene
        if ink_cloud_item in scene.items():
            scene.removeItem(ink_cloud_item)
        if ink_cloud_item.graphicsEffect():
            ink_cloud_item.graphicsEffect().deleteLater()
        ink_cloud_item.setGraphicsEffect(None)

    def remove_ink_cloud_safety(self):
        """Safety method to ensure ink cloud is removed"""
        if hasattr(self, '_current_ink_cloud') and self._current_ink_cloud:
            if self._current_ink_cloud in self.user_interface.scene.items():
                self.user_interface.scene.removeItem(self._current_ink_cloud)
            self._current_ink_cloud = None
            
        if hasattr(self, '_ink_cloud_timer') and self._ink_cloud_timer:
            self._ink_cloud_timer.stop()

    def end_startle(self):
        if self.mental_states_enabled:
            self.squid.mental_state_manager.set_state("startled", False)
            # Add thoughts
            self.brain_window.add_thought("No longer startled")

    def allow_initial_startle(self):
        """Allow the squid to be startled after the initial delay."""
        self.initial_startle_allowed = True
        self.is_first_instance = False  # Reset the flag after the first instance
