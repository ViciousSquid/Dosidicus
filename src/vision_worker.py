"""
vision_worker.py - Background thread for squid vision calculations

Handles vision cone calculations, food detection, and object visibility
in a separate thread to prevent blocking the main UI.

The worker maintains a cache of visible objects and emits signals when
visibility changes, allowing the squid to react without polling.

Usage:
    1. Create VisionWorker with scene reference
    2. Connect to visibility signals (food_visibility_changed, etc.)
    3. Call update_squid_state() periodically with squid position/direction
    4. Worker emits signals when visibility changes
"""

import time
import math
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition, QPointF


@dataclass
class SquidVisionState:
    """Snapshot of squid's vision-relevant state"""
    # Position
    squid_x: float = 0.0
    squid_y: float = 0.0
    squid_width: float = 100.0
    squid_height: float = 100.0
    
    # View direction
    current_view_angle: float = 0.0
    view_cone_angle: float = math.pi / 2.5  # ~72 degrees
    
    # Window bounds
    window_width: float = 1280.0
    window_height: float = 900.0
    
    # Timestamp
    timestamp: float = field(default_factory=time.time)


@dataclass
class SceneObject:
    """Lightweight representation of a scene object for vision calculations"""
    x: float
    y: float
    width: float = 64.0
    height: float = 64.0
    category: str = 'unknown'
    is_sushi: bool = False
    obj_id: int = 0  # For tracking identity


@dataclass
class VisionResult:
    """Results of a vision calculation"""
    visible_food: List[Tuple[float, float]] = field(default_factory=list)
    visible_plants: List[Tuple[float, float]] = field(default_factory=list)
    visible_rocks: List[Tuple[float, float]] = field(default_factory=list)
    visible_poop: List[Tuple[float, float]] = field(default_factory=list)
    
    # Cached values for quick access
    can_see_food: bool = False
    nearest_food_distance: float = float('inf')
    nearest_food_position: Optional[Tuple[float, float]] = None
    
    # Proximity detection (doesn't require vision cone)
    nearby_plants: List[Tuple[float, float]] = field(default_factory=list)
    plant_proximity_value: float = 0.0
    
    timestamp: float = field(default_factory=time.time)


class VisionWorker(QThread):
    """
    Background worker for squid vision calculations.
    
    Signals:
        food_visibility_changed: Emitted when food visibility changes
            - bool: can_see_food
            - list: visible food positions [(x, y), ...]
            
        plant_proximity_changed: Emitted when plant proximity changes
            - float: proximity value (0-100)
            - list: nearby plant positions
            
        visibility_update: Emitted with full visibility results
            - VisionResult: Complete vision state
            
        threat_detected: Emitted when potential threat enters vision
            - str: threat type
            - tuple: position (x, y)
    """
    
    food_visibility_changed = pyqtSignal(bool, list)
    plant_proximity_changed = pyqtSignal(float, list)
    visibility_update = pyqtSignal(object)  # VisionResult
    threat_detected = pyqtSignal(str, tuple)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Thread control
        self._running = True
        self._paused = False
        
        # Mutex for thread-safe access
        self._mutex = QMutex()
        self._condition = QWaitCondition()
        
        # Current state
        self._squid_state: Optional[SquidVisionState] = None
        self._scene_objects: List[SceneObject] = []
        self._state_dirty = False
        
        # Previous results for change detection
        self._last_result: Optional[VisionResult] = None
        self._last_food_visible = False
        self._last_plant_proximity = 0.0
        
        # Update frequency control
        self._update_interval = 1.0 / 20.0  # 20 Hz max
        self._last_update_time = 0.0
        
        # Performance stats
        self._calc_count = 0
        self._total_calc_time = 0.0
    
    def stop(self):
        """Stop the worker thread"""
        self._running = False
        self._mutex.lock()
        self._condition.wakeAll()
        self._mutex.unlock()
    
    def pause(self):
        """Pause vision calculations"""
        self._paused = True
    
    def resume(self):
        """Resume vision calculations"""
        self._paused = False
        self._mutex.lock()
        self._condition.wakeAll()
        self._mutex.unlock()
    
    def update_squid_state(self, state: SquidVisionState):
        """
        Update the squid's position and view state.
        Call this from the main thread when the squid moves.
        """
        with QMutexLocker(self._mutex):
            self._squid_state = state
            self._state_dirty = True
            self._condition.wakeOne()
    
    def update_scene_objects(self, objects: List[SceneObject]):
        """
        Update the list of scene objects to check visibility for.
        Call this when objects are added/removed from the scene.
        """
        with QMutexLocker(self._mutex):
            self._scene_objects = objects.copy()
            self._state_dirty = True
            self._condition.wakeOne()
    
    def get_last_result(self) -> Optional[VisionResult]:
        """Get the most recent vision result (thread-safe)"""
        with QMutexLocker(self._mutex):
            return self._last_result
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        avg_time = self._total_calc_time / max(1, self._calc_count)
        return {
            'calculation_count': self._calc_count,
            'avg_calc_time_ms': avg_time,
        }
    
    def run(self):
        """Main worker loop"""
        print("👁️ VisionWorker started")
        
        while self._running:
            should_calculate = False
            squid_state = None
            objects = None
            
            # Check if we need to calculate
            self._mutex.lock()
            try:
                if not self._state_dirty and self._running and not self._paused:
                    # Wait for state change or timeout (100ms)
                    self._condition.wait(self._mutex, 100)
                
                if self._state_dirty and not self._paused:
                    current_time = time.time()
                    if current_time - self._last_update_time >= self._update_interval:
                        should_calculate = True
                        squid_state = self._squid_state
                        objects = self._scene_objects.copy()
                        self._state_dirty = False
                        self._last_update_time = current_time
            finally:
                self._mutex.unlock()
            
            # Perform vision calculation
            if should_calculate and squid_state:
                start_time = time.perf_counter()
                
                try:
                    result = self._calculate_visibility(squid_state, objects or [])
                    
                    # Update cached result
                    with QMutexLocker(self._mutex):
                        self._last_result = result
                    
                    # Check for changes and emit signals
                    self._check_and_emit_changes(result)
                    
                    # Stats
                    calc_time = (time.perf_counter() - start_time) * 1000
                    self._calc_count += 1
                    self._total_calc_time += calc_time
                    
                except Exception as e:
                    print(f"👁️ Vision calculation error: {e}")
                    import traceback
                    traceback.print_exc()
        
        print("👁️ VisionWorker stopped")
    
    def _calculate_visibility(self, squid: SquidVisionState, 
                             objects: List[SceneObject]) -> VisionResult:
        """Calculate what the squid can see"""
        result = VisionResult(timestamp=time.time())
        
        # Get squid center
        squid_cx = squid.squid_x + squid.squid_width / 2
        squid_cy = squid.squid_y + squid.squid_height / 2
        
        # Vision cone length (diagonal of window)
        cone_length = math.sqrt(squid.window_width**2 + squid.window_height**2)
        
        # Half cone angle for comparison
        half_cone = squid.view_cone_angle / 2
        
        # Process each object
        food_items = []
        min_food_dist = float('inf')
        nearest_food = None
        
        for obj in objects:
            # Get object center
            obj_cx = obj.x + obj.width / 2
            obj_cy = obj.y + obj.height / 2
            
            # Calculate distance
            dx = obj_cx - squid_cx
            dy = obj_cy - squid_cy
            distance = math.sqrt(dx*dx + dy*dy)
            
            # Check if in vision cone
            in_cone = False
            if distance <= cone_length:
                # Calculate angle to object
                angle_to_obj = math.atan2(dy, dx)
                
                # Calculate angle difference (handle wrap-around)
                angle_diff = abs(angle_to_obj - squid.current_view_angle)
                while angle_diff > math.pi:
                    angle_diff = 2 * math.pi - angle_diff
                
                in_cone = angle_diff <= half_cone
            
            # Categorize visible objects
            pos = (obj.x, obj.y)
            
            if obj.category == 'food':
                if in_cone:
                    # Prioritize sushi
                    if obj.is_sushi:
                        food_items.insert(0, pos)
                    else:
                        food_items.append(pos)
                    
                    if distance < min_food_dist:
                        min_food_dist = distance
                        nearest_food = pos
            
            elif obj.category == 'plant':
                if in_cone:
                    result.visible_plants.append(pos)
                
                # Plant proximity (doesn't need vision cone)
                if distance < 300:  # Proximity range
                    result.nearby_plants.append(pos)
            
            elif obj.category == 'rock':
                if in_cone:
                    result.visible_rocks.append(pos)
            
            elif obj.category == 'poop':
                if in_cone:
                    result.visible_poop.append(pos)
        
        # Set food results
        result.visible_food = food_items
        result.can_see_food = len(food_items) > 0
        result.nearest_food_distance = min_food_dist
        result.nearest_food_position = nearest_food
        
        # Calculate plant proximity value
        if result.nearby_plants:
            # Closest plant determines proximity value
            min_plant_dist = float('inf')
            for px, py in result.nearby_plants:
                plant_cx = px + 32  # Assume 64x64 plants
                plant_cy = py + 32
                dist = math.sqrt((plant_cx - squid_cx)**2 + (plant_cy - squid_cy)**2)
                min_plant_dist = min(min_plant_dist, dist)
            
            # Scale to 0-100 (closer = higher)
            max_range = 300.0
            result.plant_proximity_value = max(0.0, 100.0 - (min_plant_dist / max_range * 100.0))
        
        return result
    
    def _check_and_emit_changes(self, result: VisionResult):
        """Check for changes and emit appropriate signals"""
        # Food visibility change
        if result.can_see_food != self._last_food_visible:
            self._last_food_visible = result.can_see_food
            self.food_visibility_changed.emit(result.can_see_food, result.visible_food)
        
        # Plant proximity change (with threshold to avoid noise)
        proximity_diff = abs(result.plant_proximity_value - self._last_plant_proximity)
        if proximity_diff > 5.0:  # 5% threshold
            self._last_plant_proximity = result.plant_proximity_value
            self.plant_proximity_changed.emit(result.plant_proximity_value, result.nearby_plants)
        
        # Always emit full update
        self.visibility_update.emit(result)


def extract_scene_objects(scene, food_items: List, 
                          decorations: Optional[List] = None) -> List[SceneObject]:
    """
    Helper function to extract SceneObject list from Qt scene.
    Call this from the main thread before updating the vision worker.
    
    Args:
        scene: QGraphicsScene instance
        food_items: List of food item graphics items
        decorations: Optional list of decoration items (if not provided, extracts from scene)
    
    Returns:
        List of SceneObject instances
    """
    objects = []
    obj_id = 0
    
    # Extract food items
    for item in food_items:
        try:
            pos = item.pos()
            rect = item.boundingRect()
            objects.append(SceneObject(
                x=pos.x(),
                y=pos.y(),
                width=rect.width(),
                height=rect.height(),
                category='food',
                is_sushi=getattr(item, 'is_sushi', False),
                obj_id=obj_id
            ))
            obj_id += 1
        except:
            pass
    
    # Extract decorations from scene if not provided
    if decorations is None:
        try:
            from ui import ResizablePixmapItem
            decorations = [item for item in scene.items() 
                          if isinstance(item, ResizablePixmapItem)]
        except ImportError:
            decorations = []
    
    for item in decorations:
        try:
            pos = item.pos()
            rect = item.boundingRect()
            category = getattr(item, 'category', 'unknown')
            
            # Skip non-categorized items
            if category not in ('plant', 'rock', 'poop'):
                continue
            
            objects.append(SceneObject(
                x=pos.x(),
                y=pos.y(),
                width=rect.width(),
                height=rect.height(),
                category=category,
                obj_id=obj_id
            ))
            obj_id += 1
        except:
            pass
    
    return objects


def create_squid_vision_state(squid) -> SquidVisionState:
    """
    Helper function to create SquidVisionState from a Squid instance.
    Call this from the main thread.
    """
    return SquidVisionState(
        squid_x=squid.squid_x,
        squid_y=squid.squid_y,
        squid_width=squid.squid_width,
        squid_height=squid.squid_height,
        current_view_angle=getattr(squid, 'current_view_angle', 0.0),
        view_cone_angle=getattr(squid, 'view_cone_angle', math.pi / 2.5),
        window_width=squid.ui.window_width,
        window_height=squid.ui.window_height,
        timestamp=time.time()
    )
