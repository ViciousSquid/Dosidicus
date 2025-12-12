"""
squid_vision_integration.py - Integration code for VisionWorker

This file contains the code to integrate VisionWorker into squid.py.
Apply these changes to your existing squid.py file.

INTEGRATION STEPS:
1. Add imports
2. Initialize vision worker in Squid.__init__
3. Connect signals to handlers
4. Replace synchronous vision methods with cached results
5. Add periodic state updates to vision worker
"""

# =============================================================================
# STEP 1: ADD IMPORTS (at top of squid.py)
# =============================================================================

IMPORT_CODE = '''
from .vision_worker import (
    VisionWorker, 
    VisionResult, 
    SquidVisionState,
    SceneObject,
    extract_scene_objects,
    create_squid_vision_state
)
'''


# =============================================================================
# STEP 2: ADD TO __init__ (after other initialization)
# =============================================================================

INIT_CODE = '''
        # ===== VISION WORKER SETUP =====
        # Background thread for vision calculations
        self._vision_worker = VisionWorker(self)
        self._vision_worker.food_visibility_changed.connect(self._on_food_visibility_changed)
        self._vision_worker.plant_proximity_changed.connect(self._on_plant_proximity_changed)
        self._vision_worker.visibility_update.connect(self._on_visibility_update)
        self._vision_worker.start()
        
        # Cached vision results
        self._cached_vision: Optional[VisionResult] = None
        self._cached_visible_food: List[Tuple[float, float]] = []
        self._cached_can_see_food: bool = False
        self._cached_plant_proximity: float = 0.0
        
        # Vision update timer - updates worker with squid state
        self._vision_update_timer = QtCore.QTimer()
        self._vision_update_timer.timeout.connect(self._update_vision_worker)
        self._vision_update_timer.start(50)  # 20 Hz updates
        
        # Scene object cache for vision worker
        self._scene_objects_dirty = True
        self._cached_scene_objects: List[SceneObject] = []
'''


# =============================================================================
# STEP 3: ADD SIGNAL HANDLERS
# =============================================================================

SIGNAL_HANDLERS = '''
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
    
    def _on_plant_proximity_changed(self, proximity: float, plant_positions: list):
        """Handle plant proximity change from vision worker"""
        self._cached_plant_proximity = proximity
        
        # Could trigger calming effects when near plants
        if proximity > 50 and hasattr(self, 'tamagotchi_logic'):
            # Near a plant - slight anxiety reduction
            if hasattr(self.tamagotchi_logic, 'plant_calming_effect_counter'):
                self.tamagotchi_logic.plant_calming_effect_counter += 1
    
    def _on_visibility_update(self, result: VisionResult):
        """Handle full visibility update from vision worker"""
        self._cached_vision = result
        self._cached_visible_food = result.visible_food
        self._cached_can_see_food = result.can_see_food
        self._cached_plant_proximity = result.plant_proximity_value
'''


# =============================================================================
# STEP 4: ADD VISION WORKER UPDATE METHOD
# =============================================================================

VISION_UPDATE_METHOD = '''
    def _update_vision_worker(self):
        """Periodically update vision worker with current state"""
        if not hasattr(self, '_vision_worker') or not self._vision_worker:
            return
        
        # Update squid state
        try:
            squid_state = create_squid_vision_state(self)
            self._vision_worker.update_squid_state(squid_state)
        except Exception as e:
            print(f"Error updating squid vision state: {e}")
        
        # Update scene objects if dirty
        if self._scene_objects_dirty:
            self._update_scene_objects()
    
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
                    pass
            
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
                            pass
            
            # Send to vision worker
            self._vision_worker.update_scene_objects(objects)
            self._cached_scene_objects = objects
            self._scene_objects_dirty = False
            
        except Exception as e:
            print(f"Error updating scene objects: {e}")
    
    def mark_scene_objects_dirty(self):
        """Call when objects are added/removed from scene"""
        self._scene_objects_dirty = True
'''


# =============================================================================
# STEP 5: REPLACE VISION METHODS WITH CACHED VERSIONS
# =============================================================================

CACHED_VISION_METHODS = '''
    def get_visible_food(self):
        """
        Returns the positions of visible food items, prioritized by type (sushi first).
        
        Now uses cached results from vision worker for better performance.
        Falls back to synchronous calculation if worker not available.
        """
        # Use cached result if available and recent
        if hasattr(self, '_cached_visible_food') and self._cached_visible_food is not None:
            return self._cached_visible_food
        
        # Fallback to synchronous calculation
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
    
    def get_plant_proximity(self) -> float:
        """
        Get the current plant proximity value (0-100).
        Uses cached result from vision worker.
        """
        if hasattr(self, '_cached_plant_proximity'):
            return self._cached_plant_proximity
        return 0.0
    
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
'''


# =============================================================================
# STEP 6: ADD CLEANUP
# =============================================================================

CLEANUP_CODE = '''
    def cleanup_vision_worker(self):
        """Clean up vision worker - call before squid destruction"""
        if hasattr(self, '_vision_update_timer') and self._vision_update_timer:
            self._vision_update_timer.stop()
        
        if hasattr(self, '_vision_worker') and self._vision_worker:
            self._vision_worker.stop()
            self._vision_worker.wait(1000)
            self._vision_worker = None
'''


# =============================================================================
# STEP 7: HOOK INTO SCENE CHANGES
# =============================================================================

SCENE_CHANGE_HOOKS = '''
# In tamagotchi_logic.py, add calls to mark_scene_objects_dirty():

# In spawn_food():
    self.squid.mark_scene_objects_dirty()

# In remove_food() or when food is eaten:
    self.squid.mark_scene_objects_dirty()

# In add_decoration() or when decorations change:
    self.squid.mark_scene_objects_dirty()

# Example modification to spawn_food:
def spawn_food(self, food_type='pellet'):
    # ... existing spawn code ...
    
    # Notify vision worker of scene change
    if hasattr(self, 'squid') and hasattr(self.squid, 'mark_scene_objects_dirty'):
        self.squid.mark_scene_objects_dirty()
'''


# =============================================================================
# COMPLETE INTEGRATION EXAMPLE
# =============================================================================

def print_integration_guide():
    """Print the integration guide to console"""
    print("=" * 70)
    print("SQUID VISION WORKER INTEGRATION GUIDE")
    print("=" * 70)
    print()
    print("1. Copy vision_worker.py to your src/ directory")
    print()
    print("2. Add import at top of squid.py:")
    print(IMPORT_CODE)
    print()
    print("3. Add to Squid.__init__ (after other initialization):")
    print(INIT_CODE)
    print()
    print("4. Add signal handler methods to Squid class:")
    print(SIGNAL_HANDLERS)
    print()
    print("5. Add vision worker update method:")
    print(VISION_UPDATE_METHOD)
    print()
    print("6. Replace/add cached vision methods:")
    print("   (See CACHED_VISION_METHODS in this file)")
    print()
    print("7. Add cleanup method")
    print()
    print("8. Hook into scene changes in tamagotchi_logic.py")
    print()
    print("=" * 70)
    print()
    print("BENEFITS:")
    print("- Vision calculations run in background thread")
    print("- Main thread no longer blocked by vision cone math")
    print("- Cached results provide instant access")
    print("- Signals allow reactive behavior changes")
    print()


if __name__ == '__main__':
    print_integration_guide()
