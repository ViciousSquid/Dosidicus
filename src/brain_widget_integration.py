"""
brain_widget_integration.py - Integration code for BrainRenderWorker

This file contains the code to integrate BrainRenderWorker into brain_widget.py.
Apply these changes to your existing brain_widget.py file.

INTEGRATION STEPS:
1. Add the import at the top of brain_widget.py
2. Add initialization code in __init__
3. Replace/modify paintEvent
4. Add cleanup in closeEvent or destructor
"""

# =============================================================================
# STEP 1: ADD IMPORT (near top of brain_widget.py, with other imports)
# =============================================================================

IMPORT_CODE = '''
from .brain_render_worker import BrainRenderWorker, create_render_state_from_widget, RenderState
'''


# =============================================================================
# STEP 2: ADD TO __init__ (after other initialization, before end of __init__)
# =============================================================================

INIT_CODE = '''
        # ===== OFFSCREEN RENDERING SETUP =====
        # Initialize render worker for background rendering
        self._render_worker = BrainRenderWorker(self)
        self._render_worker.render_complete.connect(self._on_render_complete)
        self._render_worker.start()
        
        # Cached rendered image
        self._cached_render: Optional[QImage] = None
        self._render_dirty = True
        
        # Render throttling
        self._last_render_request = 0.0
        self._render_interval = 1.0 / 30.0  # 30 FPS target
        
        # State change tracking for smart re-rendering
        self._last_state_hash = None
        
        # Timer for periodic render requests (catches animation updates)
        self._render_timer = QtCore.QTimer(self)
        self._render_timer.timeout.connect(self._request_render_if_dirty)
        self._render_timer.start(33)  # ~30 FPS
'''


# =============================================================================
# STEP 3: ADD THESE NEW METHODS
# =============================================================================

NEW_METHODS = '''
    def _request_render_if_dirty(self):
        """Called by timer to request render if state has changed"""
        if self._render_dirty or self._has_active_animations():
            self._request_render()
    
    def _has_active_animations(self) -> bool:
        """Check if there are active animations requiring re-render"""
        current_time = time.time()
        
        # Check communication events (connection animations)
        for neuron, event_time in self.communication_events.items():
            if current_time - event_time < 0.5:  # 500ms animation
                return True
        
        # Check link fade animations
        for key, opacity in getattr(self, '_link_opacities', {}).items():
            target = getattr(self, '_link_targets', {}).get(key, opacity)
            if abs(opacity - target) > 0.01:
                return True
        
        return False
    
    def _request_render(self):
        """Request a new render from the worker thread"""
        current_time = time.time()
        
        # Throttle requests
        if current_time - self._last_render_request < self._render_interval:
            return
        
        self._last_render_request = current_time
        
        # Create state snapshot and send to worker
        try:
            state = create_render_state_from_widget(self)
            self._render_worker.request_render(state)
            self._render_dirty = False
        except Exception as e:
            print(f"Error creating render state: {e}")
    
    def _on_render_complete(self, image: QImage, render_time: float):
        """Called when render worker completes a frame"""
        self._cached_render = image
        # Trigger a lightweight repaint to show the new image
        self.update()
    
    def mark_render_dirty(self):
        """Call this when state changes that require re-render"""
        self._render_dirty = True
    
    def _cleanup_render_worker(self):
        """Clean up the render worker - call on widget destruction"""
        if hasattr(self, '_render_worker') and self._render_worker:
            self._render_worker.stop()
            self._render_worker.wait(1000)  # Wait up to 1 second
            self._render_worker = None
        
        if hasattr(self, '_render_timer') and self._render_timer:
            self._render_timer.stop()
'''


# =============================================================================
# STEP 4: REPLACE paintEvent WITH THIS OPTIMIZED VERSION
# =============================================================================

OPTIMIZED_PAINT_EVENT = '''
    def paintEvent(self, event):
        """
        Optimized paintEvent that uses cached offscreen render.
        
        The heavy rendering is done in BrainRenderWorker. This method
        just blits the cached image and draws any overlay elements
        that need to be responsive (like hover effects).
        """
        # Performance tracking
        if _PERF_TRACKING_AVAILABLE:
            _paint_start = time.perf_counter()
            perf_tracker.increment("paint_calls")
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw cached render if available
        if self._cached_render and not self._cached_render.isNull():
            # Scale cached image to widget size if needed
            if (self._cached_render.width() != self.width() or 
                self._cached_render.height() != self.height()):
                # Request new render at correct size
                self._render_dirty = True
                # Draw scaled version for now
                scaled = self._cached_render.scaled(
                    self.width(), self.height(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                painter.drawImage(0, 0, scaled)
            else:
                painter.drawImage(0, 0, self._cached_render)
        else:
            # No cached render yet - draw background and request render
            bg_color = QtGui.QColor(*self.anim_background_colour)
            painter.fillRect(self.rect(), bg_color)
            self._render_dirty = True
        
        # Draw overlay elements that need immediate response
        self._draw_overlays(painter)
        
        painter.end()
        
        # Performance tracking
        if _PERF_TRACKING_AVAILABLE:
            _paint_elapsed = (time.perf_counter() - _paint_start) * 1000
            perf_tracker.record("paint_event", _paint_elapsed)
    
    def _draw_overlays(self, painter):
        """
        Draw overlay elements that need immediate response.
        These are drawn on top of the cached render.
        """
        # Tutorial glow effect
        if getattr(self, 'tutorial_glow_active', False):
            self._draw_tutorial_glow(painter)
        
        # Neurogenesis highlights
        if hasattr(self, 'neurogenesis_highlight'):
            nh = self.neurogenesis_highlight
            if nh.get('neuron') and time.time() - nh.get('start_time', 0) < nh.get('duration', 0):
                self._draw_neurogenesis_highlight(painter)
        
        # Drag preview if dragging a neuron
        if getattr(self, 'dragging', False) and getattr(self, 'dragged_neuron', None):
            self._draw_drag_preview(painter)
    
    def _draw_tutorial_glow(self, painter):
        """Draw tutorial glow border effect"""
        opacity = getattr(self, '_tutorial_glow_opacity', 0.0)
        if opacity > 0:
            glow_color = QtGui.QColor(255, 215, 0, int(150 * opacity))
            pen = QtGui.QPen(glow_color, 4)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))
    
    def _draw_neurogenesis_highlight(self, painter):
        """Draw highlight around newly created neurons"""
        # Calculate scale (same as in render worker)
        indicator_space = 0
        base_width = 1024
        base_height = 768 - indicator_space
        scale_x = self.width() / base_width
        scale_y = (self.height() - indicator_space) / max(1, base_height)
        scale = max(0.01, min(scale_x, scale_y))
        
        offset_x = 0
        if scale_x > scale_y:
            content_width = base_width * scale
            offset_x = (self.width() - content_width) / 2
        
        nh = self.neurogenesis_highlight
        neuron_name = nh.get('neuron')
        if neuron_name and neuron_name in self.neuron_positions:
            pos = self.neuron_positions[neuron_name]
            x = pos[0] * scale + offset_x
            y = pos[1] * scale + indicator_space
            
            # Pulsing effect
            elapsed = time.time() - nh.get('start_time', 0)
            pulse = 0.5 + 0.5 * math.sin(elapsed * 4)
            
            radius = 40 * scale * (1 + pulse * 0.2)
            alpha = int(200 * (1 - elapsed / nh.get('duration', 1)))
            
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0, alpha), 3))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)
    
    def _draw_drag_preview(self, painter):
        """Draw preview when dragging a neuron"""
        # This could show a ghost of the neuron at cursor position
        pass
'''


# =============================================================================
# STEP 5: MODIFY STATE-CHANGING METHODS TO MARK DIRTY
# =============================================================================

STATE_CHANGE_HOOKS = '''
# Add self.mark_render_dirty() call to these methods:
# - update_state()
# - set_neuron_value() 
# - add_neuron()
# - remove_neuron()
# - strengthen_connection()
# - Any method that modifies self.state, self.weights, or self.neuron_positions

# Example modification for update_state:
def update_state(self, state_dict):
    """Update neural state values"""
    for key, value in state_dict.items():
        self.state[key] = value
    
    # Mark for re-render
    self.mark_render_dirty()
    self.update()  # Trigger repaint
'''


# =============================================================================
# STEP 6: ADD CLEANUP (in closeEvent or __del__)
# =============================================================================

CLEANUP_CODE = '''
    def closeEvent(self, event):
        """Clean up worker thread on close"""
        self._cleanup_render_worker()
        super().closeEvent(event)
'''


# =============================================================================
# COMPLETE INTEGRATION EXAMPLE
# =============================================================================

def print_integration_guide():
    """Print the integration guide to console"""
    print("=" * 70)
    print("BRAIN WIDGET OFFSCREEN RENDERING INTEGRATION GUIDE")
    print("=" * 70)
    print()
    print("1. Copy brain_render_worker.py to your src/ directory")
    print()
    print("2. Add import at top of brain_widget.py:")
    print(IMPORT_CODE)
    print()
    print("3. Add to __init__ (before the final 'super().__init__()' or at end):")
    print(INIT_CODE)
    print()
    print("4. Add these new methods to BrainWidget class:")
    print(NEW_METHODS)
    print()
    print("5. Replace paintEvent with optimized version:")
    print("   (See OPTIMIZED_PAINT_EVENT in this file)")
    print()
    print("6. Add mark_render_dirty() calls to state-changing methods")
    print()
    print("7. Add cleanup in closeEvent")
    print()
    print("=" * 70)


if __name__ == '__main__':
    print_integration_guide()
