"""What the squid does with things: eating food, and pushing, carrying and
throwing rocks, poop and decorations.
"""
import logging
import random
import time
from datetime import datetime
import math
from PyQt5 import QtCore
from PyQt5.QtCore import QTimer
from .personality import Personality

_LOG = logging.getLogger(__name__)


class SquidObjectsMixin:
    """Part of Squid (see squid.py); not used on its own."""

    def finish_eating(self):
        """Reset status after eating"""
        # Check if status contains "eating" (handles "eating cheese", "eating sushi", "eating greedily", etc.)
        if "eating" in self.status.lower():
            # Reset to personality-appropriate default status
            if self.personality == Personality.TIMID:
                self.status = "cautiously exploring"
            elif self.personality == Personality.ADVENTUROUS:
                self.status = "boldly exploring"
            else:
                self.status = "roaming"
        
        # Always clear the is_eating flag
        self.is_eating = False
            
        # Make sure the brain is updated
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            self.tamagotchi_logic.update_squid_brain()

    def search_for_favorite_food(self):
        visible_food = self.get_visible_food()
        if visible_food:
            for food_x, food_y in visible_food:
                if self.is_favorite_food(self.tamagotchi_logic.get_food_item_at(food_x, food_y)):
                    self.move_towards(food_x, food_y)
                    return
            # If no favorite food is found, display a message and move randomly
            self.tamagotchi_logic.show_message("Stubborn squid does not like that type of food!")
            self.move_randomly()
        else:
            self.move_randomly()

    def get_favorite_food(self):
        # Implement logic to find the squid's favorite food
        for food_item in self.tamagotchi_logic.food_items:
            if self.is_favorite_food(food_item):
                return food_item.pos().x(), food_item.pos().y()
        return None

    def is_favorite_food(self, food_item):
        return food_item is not None and getattr(food_item, 'is_sushi', False)

    def push_decoration(self, decoration, direction):
        """Push a decoration with proper animation handling"""
        try:
            push_distance = 80
            current_pos = decoration.pos()
            new_x = current_pos.x() + (push_distance * direction)

            scene_rect = self.ui.scene.sceneRect()
            new_x = max(scene_rect.left(), min(new_x, scene_rect.right() - decoration.boundingRect().width()))

            if self.push_animation and self.push_animation.state() == QtCore.QAbstractAnimation.Running:
                self.push_animation.stop()

            self.push_animation = QtCore.QVariantAnimation()
            self.push_animation.setDuration(300)
            self.push_animation.setStartValue(current_pos)
            self.push_animation.setEndValue(QtCore.QPointF(new_x, current_pos.y()))
            self.push_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)

            self.push_animation.valueChanged.connect(decoration.setPos)
            self.push_animation.finished.connect(lambda: self._on_push_complete(decoration))
            self.push_animation.start()

        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Tried to push decoration but failed: {e}")
            decoration.setPos(new_x, current_pos.y())
            self._on_push_complete(decoration)

    def _on_push_complete(self, decoration):
        """Called when the push animation finishes."""
        self.happiness = min(100, self.happiness + 5)
        self.curiosity = min(100, self.curiosity + 10)
        self.anxiety = max(0, self.anxiety - 6)

        # --- Plant-specific tracking & reward ---
        if hasattr(decoration, 'category') and decoration.category == 'plant':
            # Count this interaction
            self.memory_manager.add_short_term_memory(
                'interaction', 'plant_contact',
                {'plant_key': decoration.filename, 'effect': 'calming'},
                importance=2.0
            )
            # Tell the logic layer to track it
            if hasattr(self.tamagotchi_logic, 'track_plant_interaction'):
                self.tamagotchi_logic.track_plant_interaction()

            # Mark as favourite after 3 touches
            key = decoration.filename
            self.memory_manager.plant_interaction_count[key] = self.memory_manager.plant_interaction_count.get(key, 0) + 1
            if self.memory_manager.plant_interaction_count[key] >= 3:
                self.memory_manager.add_long_term_memory('favourite_plant', key, {
                    'reason': 'Repeated calming contact',
                    'anxiety_reduction': True
                })

        # --- Reward for RL ---
        if hasattr(self.tamagotchi_logic, 'recent_positive_outcome'):
            self.tamagotchi_logic.recent_positive_outcome = True

        self.status = "pushing decoration"
        # The animation can finish after the game it belonged to has gone
        # (and this runs inside a Qt slot, where an exception aborts the game).
        if self.tamagotchi_logic is not None:
            self.tamagotchi_logic.show_message("Squid pushed a decoration")

        # Clean up animation reference
        self.push_animation = None

    def handle_rock_interaction(self, target_rock=None):
        """Unified rock interaction handler delegates to RockInteractionManager"""
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            return False
            
        return self.tamagotchi_logic.rock_interaction.start_rock_test(target_rock)

    def search_for_food(self):
        visible_food = self.get_visible_food()
        if visible_food:
            # Only set pursuing_food to True if food is actually visible
            self.pursuing_food = True
            closest_food = min(visible_food, key=lambda f: self.distance_to(f[0], f[1]))
            self.status = "moving to food"
            self.move_towards(closest_food[0], closest_food[1])
        else:
            # Reset pursuing_food when no food is visible
            self.pursuing_food = False
            self.status = "searching for food"
            self.move_randomly()

    def throw_poop(self, direction="right"):
        """Delegate to PoopInteractionManager, mirroring throw_rock.

        DecisionEngine calls s.throw_poop(); the method lives on the manager,
        not on Squid, so that branch raised AttributeError too.
        """
        manager = getattr(self.tamagotchi_logic, 'poop_interaction', None)
        if manager is None or not hasattr(manager, 'throw_poop'):
            return False
        return manager.throw_poop(direction)

    def eat(self, food_item):
        """Eat a food item. Returns True if it was eaten.

        A squid that has reproduced does not eat. The food stays where it is
        and the squid's own hunger keeps rising by the ordinary rule - the
        refusal is a fact about its body, not a decision taken for its brain,
        which may well go on wanting the food.
        """
        if not self.lifecycle.can_eat:
            return False

        # FIX: Force synchronous vision for a short time to prevent "ghost" food
        # This prevents the vision worker from reporting the just-eaten food as visible
        # before it has processed the scene update.
        self._force_sync_vision_until = time.time() + 0.5

        effects = {}

        # Basic effects for all food types
        effects['hunger'] = max(-20, -self.hunger)
        effects['happiness'] = min(10, 100 - self.happiness)

        # Determine food type and effects
        is_sushi = getattr(food_item, 'is_sushi', False)
        food_name = "sushi" if is_sushi else "cheese"
        
        # Satisfaction boost (stronger for sushi)
        effects['satisfaction'] = min(15 if is_sushi else 10, 100 - self.satisfaction)

        # Personality-based reward points
        reward_points = 2  # Default for all food
        if is_sushi and self.personality in [Personality.GREEDY, Personality.STUBBORN]:
            reward_points = 3  # Extra reward for favorite food
            effects['satisfaction'] = min(20, 100 - self.satisfaction)  # Even bigger boost

        # Trigger hook if tamagotchi_logic exists
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            if hasattr(self.tamagotchi_logic, 'plugin_manager'):
                self.tamagotchi_logic.plugin_manager.trigger_hook(
                    "on_feed", 
                    squid=self,
                    food_item=food_item,
                    food_type=food_name,
                    effects=effects
                )
        
        # Set eating state BEFORE applying effects
        self.is_eating = True
        self.status = f"eating {food_name}"  # Use lowercase for consistency
        self.statistics_window.award(75)
        
        # Apply all stat changes
        for attr, change in effects.items():
            setattr(self, attr, getattr(self, attr) + change)

        # Start a timer to reset the status after 1 second
        QTimer.singleShot(1000, self.finish_eating)

        # Innate reflex: eating is an unconditioned positive. The squid does
        # not have to accumulate statistics to discover that food helps - a
        # real animal is born knowing. Personality colours how hard it lands,
        # and the change is recorded in the ledger like any other.
        reflex = getattr(self, 'hebbian_learning', None)
        if reflex is not None:
            try:
                reflex.learn_from_eating()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Reflex] learn_from_eating failed: {type(e).__name__}: {e}")

        # Memory system
        formatted_effects = ', '.join(f"{attr.capitalize()} {'+' if val >= 0 else ''}{val:.2f}" 
                            for attr, val in effects.items())
        self.memory_manager.add_short_term_memory('food', food_name, 
            f"Ate {food_name}: {formatted_effects}")

        # Neurogenesis tracking
        if hasattr(self.tamagotchi_logic, 'neurogenesis_triggers'):
            triggers = self.tamagotchi_logic.neurogenesis_triggers
            current = triggers['positive_outcomes']
            triggers['positive_outcomes'] = min(current + reward_points, 5)

            # Food writes this trigger outside track_neurogenesis_triggers().
            # Preserve its live maximum before the same simulation tick can
            # decay the value.
            statistics = getattr(self, 'statistics', None)
            if statistics:
                statistics.observe_neurogenesis_peaks(
                    statistics.peak_novelty,
                    statistics.peak_stress,
                    triggers['positive_outcomes'],
                )

        # Visual/behavioral effects
        self.tamagotchi_logic.remove_food(food_item)

        # --- FIX Clear vision cache immediately ---
        # This prevents the squid from "seeing" the ghost of the food it just ate
        # and getting stuck in 'pursuing_food' mode at the top of the screen.
        self._cached_visible_food = []
        self._cached_can_see_food = False
        # --- FIX END ---

        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Add tracking (added in 2.4.4)
        if hasattr(self.tamagotchi_logic, 'track_food_consumed'):
            self.tamagotchi_logic.track_food_consumed(food_item)

        # Personality reactions (with enhanced messages)
        if self.personality == Personality.GREEDY:
            self.eat_greedily(food_item)
            if is_sushi:
                self.tamagotchi_logic.show_message("Greedy squid devours sushi voraciously!")
        elif self.personality == Personality.STUBBORN:
            if not is_sushi:
                self.react_stubborn_eating()
            else:
                self.tamagotchi_logic.show_message("Stubborn squid happily accepts sushi")
        return True

    def eat_greedily(self, food_item):
        # Update status to show greedy eating (lowercase for consistency)
        self.status = "eating greedily"
        food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"

        # Reduce hunger more than usual
        self.hunger = max(0, self.hunger - 25)

        # Increase happiness more
        self.happiness = min(100, self.happiness + 15)

        # Increase satisfaction significantly
        self.satisfaction = min(100, self.satisfaction + 20)

        # Slightly increase anxiety (from overeating)
        self.anxiety = min(100, self.anxiety + 5)

        # Note: Food is already removed in eat() method, don't remove again
        # self.tamagotchi_logic.remove_food(food_item)  # REMOVED - already done
        #print(f"The greedy squid enthusiastically ate the {food_type}")
        
        # These are already called in eat() method, but safe to call again
        self.show_eating_effect()
        # Poop timer already started in eat(), don't restart
        # self.start_poop_timer()  # Already called
        
        # These should already be set in eat(), but ensure they're cleared
        self.pursuing_food = False
        self.target_food = None

        # Occasionally show a message
        if random.random() < 0.2:  # 20% chance to show a message
            self.tamagotchi_logic.show_message("Nom nom! Greedy squid devours the food!")

        # Check if there's more food nearby
        if self.check_for_more_food():
            if random.random() < 0.1:  # 10% chance to show this message
                self.tamagotchi_logic.show_message("Greedy squid looks around for more food...")
        else:
            if random.random() < 0.1:  # 10% chance to show this message
                self.tamagotchi_logic.show_message("Greedy squid is satisfied... for now.")

    def react_stubborn_eating(self):
        if self.hunger > 80:  # Extremely hungry
            self.happiness = max(0, self.happiness - 5)
            self.tamagotchi_logic.show_message("Stubborn squid reluctantly eats non-sushi food.")
        else:
            self.tamagotchi_logic.show_message("Stubborn squid ignores non-sushi food.")

    def check_for_more_food(self):
        for food_item in self.tamagotchi_logic.food_items:
            if self.is_food_nearby(food_item):
                return True
        return False

    def is_food_nearby(self, food_item):
        food_x, food_y = food_item.pos().x(), food_item.pos().y()
        squid_center_x = self.squid_x + self.squid_width // 2
        squid_center_y = self.squid_y + self.squid_height // 2
        distance = math.sqrt((squid_center_x - food_x)**2 + (squid_center_y - food_y)**2)
        return distance < 100  # Adjust the distance threshold as needed

    def react_to_rock_throw(self, source_node_id, is_target=False):
        """
        React to a rock being thrown by another squid
        
        Args:
            source_node_id (str): ID of the squid that threw the rock
            is_target (bool): Whether this squid is the apparent target
        """
        # Only react if the squid is not sleeping
        if self.is_sleeping:
            return
        
        # Base reaction - increase anxiety
        self.anxiety = min(100, self.anxiety + 5)
        
        # Add memory
        self.memory_manager.add_short_term_memory(
            'observation', 'rock_throw',
            f"Observed squid {source_node_id[-4:]} throw a rock"
        )
        
        # Strong reaction if targeted
        if is_target:
            # Get startled
            if hasattr(self.tamagotchi_logic, 'startle_squid'):
                self.tamagotchi_logic.startle_squid(source="targeted_by_rock")
            
            # Significantly increase anxiety
            self.anxiety = min(100, self.anxiety + 20)
            
            # Decrease happiness
            self.happiness = max(0, self.happiness - 10)
            
            # Add memory of being targeted
            self.memory_manager.add_short_term_memory(
                'social', 'targeted',
                f"Was targeted by rock from squid {source_node_id[-4:]}"
            )
            
            # Higher chance for this memory to go to long-term
            if random.random() < 0.5:  # 50% chance
                self.memory_manager.transfer_to_long_term_memory(
                    'social', 'targeted'
                )

    def investigate_food(self, food_item):
        self.status = "Investigating food"
        self.tamagotchi_logic.show_message("Stubborn squid investigates the food...")

        # Move towards the food
        food_pos = food_item.pos()
        self.move_towards_position(food_pos)

        # Wait for a moment (might need to implement a delay here)

        self.tamagotchi_logic.show_message("Stubborn squid ignored the food")
        self.status = "I don't like that food"

    def consume_food(self, food_item):
        if not self.lifecycle.can_eat:
            return
        self.status = "Ate food"
        self.hunger = max(0, self.hunger - 20)
        self.happiness = min(100, self.happiness + 10)
        self.satisfaction = min(100, self.satisfaction + 15)
        self.anxiety = max(0, self.anxiety - 10)
        self.tamagotchi_logic.remove_food(food_item)
        #print("The squid ate the food")
        self.show_eating_effect()
        self.start_poop_timer()
        self.pursuing_food = False
        self.target_food = None

        # Occasionally show a message based on personality
        if random.random() < 0.25:  # 25% chance to show a message
            if self.personality == Personality.STUBBORN and getattr(food_item, 'is_sushi', False):
                self.tamagotchi_logic.show_message("Nom nom! Stubborn squid enjoys the sushi!")
            elif self.personality == Personality.GREEDY:
                food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"
                self.tamagotchi_logic.show_message(f"Nom nom! Greedy squid gobbles up the {food_type}!")
            else:
                self.tamagotchi_logic.show_message("Nom nom! Squid enjoys the meal!")

    def start_poop_timer(self):
        poop_delay = random.randint(11000, 30000)
        #print("Poop random timer started")
        self.poop_timer = QtCore.QTimer()
        self.poop_timer.setSingleShot(True)
        self.poop_timer.timeout.connect(self.create_poop)
        self.poop_timer.start(poop_delay)

    def create_poop(self):
        created = self.tamagotchi_logic.spawn_poop(
            self.squid_x + self.squid_width // 2,
            self.squid_y + self.squid_height,
        )
        # Add tracking
        if created and hasattr(self.tamagotchi_logic, 'track_poop_created'):
            self.tamagotchi_logic.track_poop_created()
        return created

    def should_hoard_decorations(self):
        """Check if this personality type should hoard items"""
        return self.personality in [Personality.GREEDY, Personality.STUBBORN]

    def get_food_position(self):
        if self.tamagotchi_logic.food_items:
            closest_food = min(self.tamagotchi_logic.food_items,
                               key=lambda food: self.distance_to(food.pos().x(), food.pos().y()))
            return closest_food.pos().x(), closest_food.pos().y()
        else:
            return -1, -1

    def should_organize_decorations(self):
        return (self.curiosity > 70 and
                self.satisfaction < 80 and
                self.personality in [Personality.ADVENTUROUS, Personality.ENERGETIC])

    def organize_decorations(self):
        target_corner = (50, 50)  # Top-left corner
        decorations = self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)

        if decorations:
            closest = min(decorations, key=lambda d: self.distance_to(d.pos().x(), d.pos().y()))
            self.move_towards(closest.pos().x(), closest.pos().y())

            if self.distance_to(closest.pos().x(), closest.pos().y()) < 50:
                self.push_decoration(closest, direction=1 if random.random() < 0.5 else -1)
                self.satisfaction = min(100, self.satisfaction + 5)
                return "organizing decorations"
        return "searching for decorations"

    def interact_with_rocks(self):
        rocks = [d for d in self.tamagotchi_logic.get_nearby_decorations(self.squid_x, self.squid_y)
                 if d.category == 'rock']
        if rocks:
            self.push_decoration(random.choice(rocks), random.choice([-1, 1]))
            self.satisfaction = min(100, self.satisfaction + 8)
            self.happiness = min(100, self.happiness + 5)
            return "interacting with rocks"
        return "no rocks nearby"

    def can_pick_up_rock(self, rock_item):
        """Check if squid can pick up this rock"""
        rock_rect = rock_item.sceneBoundingRect()
        rock_center = rock_rect.center()
        
        squid_rect = self.squid_item.sceneBoundingRect()
        squid_center = squid_rect.center()
        
        distance = math.sqrt((rock_center.x() - squid_center.x())**2 + 
                            (rock_center.y() - squid_center.y())**2)
        
        can_pick = (not self.carrying_rock and 
                    not self.is_sleeping and
                    distance < 50)
        
        print("Can pick up rock check:")
        print(f"- Rock center: ({rock_center.x():.1f}, {rock_center.y():.1f})")
        print(f"- Squid center: ({squid_center.x():.1f}, {squid_center.y():.1f})")
        print(f"- Distance: {distance:.1f}")
        print(f"- Carrying: {self.carrying_rock}")
        print(f"- Sleeping: {self.is_sleeping}")
        print(f"- Result: {can_pick}")
        
        return can_pick

    def pick_up_rock(self, item):
        """Delegate to interaction manager with random carry duration"""
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            return False
        return self.tamagotchi_logic.rock_interaction.attach_rock_to_squid(item)

    def throw_rock(self, direction=None, *, cause=None):
        """
        Delegate to interaction manager BUT capture result for RL reward.
        Returns:  bool  True = rock landed (success), False = fell out of bounds / no effect
        """
        if not hasattr(self.tamagotchi_logic, 'rock_interaction'):
            return False

        # --- Call the existing manager ---
        success = self.tamagotchi_logic.rock_interaction.throw_rock(direction, cause=cause)

        # --- Compute RL reward ---
        reward = 0.0
        if success:
            reward += 5.0                       # base success
            reward += self.happiness * 0.05     # happier squid → bigger reward
            reward += self.satisfaction * 0.05
            # memory boost
            rock_mem = self.memory_manager.get_short_term_memory('interaction', 'rock_throw')
            if rock_mem and isinstance(rock_mem, dict) and rock_mem.get('is_positive'):
                reward += 2.0
        else:
            return False   # no physical action: no invented learning outcome

        # --- Push reward into RL ---
        if hasattr(self.tamagotchi_logic, 'give_rl_reward'):
            self.tamagotchi_logic.give_rl_reward(reward)

        # --- Flag for neurogenesis / stats ---
        if hasattr(self.tamagotchi_logic, 'recent_positive_outcome'):
            self.tamagotchi_logic.recent_positive_outcome = success

        return success

    def update_rock_throw(self):
        if not self.rock_being_thrown or not self.rock_being_thrown.scene():
            self.rock_animation_timer.stop()
            return
        
        rock = self.rock_being_thrown
        current_pos = rock.pos()
        
        # Heavy rock physics - sink quickly with minimal bouncing
        self.rock_velocity_y += 2.0  # Strong gravity for quick sinking
        
        # Calculate new position
        new_x = current_pos.x() + self.rock_velocity_x
        new_y = current_pos.y() + self.rock_velocity_y
        
        # Get scene boundaries
        scene_rect = self.ui.scene.sceneRect()
        rock_rect = rock.boundingRect()
        
        # Stop at reachable depth (200px from bottom)
        max_y = self.ui.window_height - 200 - rock_rect.height()
        if new_y > max_y:
            new_y = max_y
            self.rock_animation_timer.stop()
            self.rock_being_thrown = None
            return
        
        # Minimal horizontal movement when sinking
        if abs(self.rock_velocity_y) > 1.0:  # If sinking fast
            self.rock_velocity_x *= 0.3  # Strong horizontal dampening
        
        # Basic wall collisions
        if new_x < scene_rect.left():
            new_x = scene_rect.left()
            self.rock_velocity_x *= -0.5  # Weak wall bounce
        elif new_x > scene_rect.right() - rock_rect.width():
            new_x = scene_rect.right() - rock_rect.width()
            self.rock_velocity_x *= -0.5
        
        # Update position
        rock.setPos(new_x, new_y)

    def check_rock_interaction(self):
        if not hasattr(self, 'tamagotchi_logic') or self.tamagotchi_logic is None:
            return False
            
        if not hasattr(self.tamagotchi_logic, 'config_manager'):
            return False
            
        config = self.tamagotchi_logic.config_manager.get_rock_config()
        
        decorations = self.tamagotchi_logic.get_nearby_decorations(
            self.squid_x, self.squid_y, 150)
        interactables = [d for d in decorations if d.category == 'rock']

        # Whether to throw, and whether to pick one up, is the squid's play
        # neuron's - not a roll of the dice (src/throwing.py).
        from .throwing import throw_or_drop
        brain = getattr(getattr(self.tamagotchi_logic, 'brain_window', None),
                        'brain_widget', None)
        playing = throw_or_drop(dict(getattr(brain, 'state', None) or {}))
        if (self.carrying_rock
                and self.rock_throw_cooldown == 0
                and not self.rock_decision_made):
            self.tamagotchi_logic.rock_interaction.check_rock_hold_time()
            return

        if (not self.carrying_rock
                and self.rock_throw_cooldown == 0
                and interactables
                and playing):
            target_item = min(interactables, key=lambda r: math.hypot(
                r.sceneBoundingRect().center().x() - self.squid_x,
                r.sceneBoundingRect().center().y() - self.squid_y))
            
            if self.pick_up_rock(target_item):
                mem_details = {
                    "item": getattr(target_item, 'filename', f'unknown_{target_item.category}'),
                    "position": (target_item.pos().x(), target_item.pos().y()),
                    "timestamp": datetime.now().isoformat()
                }
                self.memory_manager.add_short_term_memory(
                    'interaction', f'{target_item.category}_pickup', mem_details)
            else:
                print(f"[DEBUG] {target_item.category.capitalize()} pickup failed")

    def check_poop_interaction(self):
        """Periodic poop interaction check similar to rock interaction"""
        if not hasattr(self.tamagotchi_logic, 'poop_interaction'):
            return False
            
        config = self.tamagotchi_logic.config_manager.get_poop_config()
        
        decorations = self.tamagotchi_logic.get_nearby_decorations(
            self.squid_x, self.squid_y, 150)
        interactables = [d for d in decorations if d.category == 'poop']

        # If carrying poop and cooldown is done, potentially throw
        if (self.carrying_poop 
                and self.poop_throw_cooldown == 0 
                and random.random() < config['throw_prob']):
            direction = random.choice(["left", "right"])
            if self.throw_poop(direction):
                return

        # If not carrying poop and cooldown is done, potentially pick up
        if (not self.carrying_poop 
                and self.poop_throw_cooldown == 0 
                and interactables
                and random.random() < config['pickup_prob']):
            target_item = random.choice(interactables)
            
            if self.pick_up_poop(target_item):
                mem_details = {
                    "item": getattr(target_item, 'filename', 'unknown_poop'),
                    "position": (target_item.pos().x(), target_item.pos().y()),
                    "timestamp": datetime.now().isoformat()
                }
                self.memory_manager.add_short_term_memory(
                    'interaction', 'poop_pickup', mem_details)
            else:
                print("[DEBUG] Poop pickup failed")
