"""Looking at the brain: zoom, pan, and what the mouse is pointing at.

The view transform, hit-testing of neurons and connections, and the mouse
and wheel events that use them.
"""
import time
import random
from PyQt5 import QtCore, QtWidgets
from .brain_constants import (
    NEURON_HIT_FACTOR,
    view_transform, VIEW_ZOOM_MIN, VIEW_ZOOM_MAX,
)
from .laboratory import NeuronLaboratory


class BrainViewMixin:
    """Part of BrainWidget (see brain_widget.py); not used on its own."""

    # ------------------------------------------------------------------
    # Zoom and pan
    # ------------------------------------------------------------------
    def _view_transform(self):
        """(scale, offset_x, offset_y, fit_scale) for the current view: screen
        = logical * scale + offset. The render worker uses the same function
        (brain_constants.view_transform), so what is hit is what is drawn."""
        return view_transform(self.width(), self.height(),
                              self.view_zoom, self.view_pan, self._view_bounds())

    #: How fast the view draws back when the squid grows a neuron outside
    #: what is being shown: the share of the remaining distance covered by
    #: each step, and the time between steps.
    VIEW_EASE = 0.22

    VIEW_EASE_MS = 30

    def _view_bounds(self):
        """The part of the canvas being shown, right now: the rows, and as
        much of the growth space as the squid has grown into
        (brain_constants.content_bounds). When that changes - a neuron grows -
        the view does not jump: it eases to the new bounds over a few
        hundred milliseconds, so the network is seen to make room."""
        from .brain_constants import content_bounds
        shown = getattr(self, '_shown_bounds', None)
        if getattr(self, 'dragging', False) and shown is not None:
            return shown                    # not while a neuron is being dragged about
        target = content_bounds(self.neuron_positions)
        if shown is None:
            self._shown_bounds = target
            return target
        if shown != target:
            self._bounds_target = target
            timer = getattr(self, '_bounds_timer', None)
            if timer is None:
                timer = self._bounds_timer = QtCore.QTimer(self)
                timer.setInterval(self.VIEW_EASE_MS)
                timer.timeout.connect(self._ease_view_bounds)
            if not timer.isActive():
                timer.start()
        return shown

    def _ease_view_bounds(self):
        shown = getattr(self, '_shown_bounds', None)
        target = getattr(self, '_bounds_target', None)
        if shown is None or target is None:
            self._bounds_timer.stop()
            return
        stepped = tuple(a + (b - a) * self.VIEW_EASE for a, b in zip(shown, target))
        if max(abs(a - b) for a, b in zip(stepped, target)) < 0.5:
            stepped = target
            self._bounds_timer.stop()
        self._shown_bounds = stepped
        self._view_changed()

    def _view_changed(self):
        self._render_dirty = True
        if hasattr(self, 'tooltip_manager'):
            self.tooltip_manager.hide_tooltip()
        self.update()

    def zoom_at(self, widget_pos, factor):
        """Zoom by `factor` keeping the logical point under widget_pos still."""
        new_zoom = min(VIEW_ZOOM_MAX, max(VIEW_ZOOM_MIN, self.view_zoom * factor))
        if abs(new_zoom - self.view_zoom) < 1e-9:
            return
        logical = self._get_logical_coords(widget_pos)
        self.view_zoom = new_zoom
        # Offsets with no pan, at the new zoom; the pan is whatever puts the
        # same logical point back under the cursor.
        scale, base_x, base_y, _fit = view_transform(
            self.width(), self.height(), new_zoom, (0.0, 0.0), self._view_bounds())
        self.view_pan = (widget_pos.x() - logical.x() * scale - base_x,
                         widget_pos.y() - logical.y() * scale - base_y)
        self._view_changed()

    def pan_by(self, dx, dy):
        if not dx and not dy:
            return
        self.view_pan = (self.view_pan[0] + dx, self.view_pan[1] + dy)
        self._view_changed()

    def reset_view(self):
        """Back to the whole network fitted to the widget."""
        if self.view_zoom == 1.0 and self.view_pan == (0.0, 0.0):
            return
        self.view_zoom = 1.0
        self.view_pan = (0.0, 0.0)
        self._view_changed()

    def wheelEvent(self, event):
        """A mouse wheel zooms about the cursor. A trackpad's two-finger
        scroll (which arrives as pixel deltas) pans, as it does in any map;
        with Ctrl/Cmd held it zooms instead."""
        pixel = event.pixelDelta()
        angle = event.angleDelta()
        zoom_mod = event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.MetaModifier)
        if not pixel.isNull() and not zoom_mod:
            self.pan_by(pixel.x(), pixel.y())
        else:
            steps = (angle.y() or angle.x()) / 120.0
            if not steps and not pixel.isNull():
                steps = pixel.y() / 60.0
            if steps:
                self.zoom_at(event.pos(), 1.15 ** steps)
        event.accept()

    def event(self, event):
        # Trackpad pinch on macOS arrives as a native zoom gesture.
        if event.type() == QtCore.QEvent.NativeGesture:
            try:
                if event.gestureType() == QtCore.Qt.ZoomNativeGesture:
                    self.zoom_at(event.pos(), 1.0 + event.value())
                    return True
                if event.gestureType() == QtCore.Qt.SmartZoomNativeGesture:
                    self.reset_view()
                    return True
            except AttributeError:
                pass
        return super().event(event)

    def _get_logical_coords(self, widget_pos):
        """
        Maps widget pixels back to logical neuron coordinates.
        MUST MATCH brain_render_worker.py scaling logic exactly.
        """
        scale, offset_x, offset_y, _fit = self._view_transform()

        # Inverse Transform: (Screen - Offset) / Scale = Logical
        lx = (widget_pos.x() - offset_x) / scale
        ly = (widget_pos.y() - offset_y) / scale
        
        return QtCore.QPointF(lx, ly)

    def get_connection_at_pos(self, widget_pos):
        logical_pos = self._get_logical_coords(widget_pos)
        threshold = 15.0  # logical pixels tolerance
        closest_dist = float('inf')
        closest_conn = None

        # Helper to convert tuple coords to QPointF
        to_pt = lambda c: QtCore.QPointF(c[0], c[1])

        for (u, v) in self.weights.keys():
            # Skip invisible/excluded
            if u not in self.neuron_positions or v not in self.neuron_positions: continue
            if u in self.excluded_neurons or v in self.excluded_neurons: continue
            if not self.show_links: continue

            # If strictly 2-element tuple
            p1 = to_pt(self.neuron_positions[u])
            p2 = to_pt(self.neuron_positions[v])
            
            d2 = self._dist_to_segment_squared(logical_pos, p1, p2)
            
            if d2 < threshold**2 and d2 < closest_dist:
                closest_dist = d2
                closest_conn = (u, v)

        return closest_conn

    def _dist_to_segment_squared(self, p, v, w):
        l2 = (v.x() - w.x())**2 + (v.y() - w.y())**2
        if l2 == 0: return (p.x() - v.x())**2 + (p.y() - v.y())**2
        t = ((p.x() - v.x()) * (w.x() - v.x()) + (p.y() - v.y()) * (w.y() - v.y())) / l2
        t = max(0, min(1, t))
        dist_x = p.x() - (v.x() + t * (w.x() - v.x()))
        dist_y = p.y() - (v.y() + t * (w.y() - v.y()))
        return dist_x**2 + dist_y**2

    def get_neuron_at_pos(self, widget_pos):
        """Finds a neuron at the given QPoint widget coordinates."""
        logical_pos = self._get_logical_coords(widget_pos)
        # Generous next to the drawn circle, because a neuron is a small
        # target - but derived from the neuron's size rather than a flat 50,
        # which is wider than half the gap between neighbours in a row and so
        # claimed clicks belonging to the neuron next door.
        neuron_radius = self.neuron_radius * NEURON_HIT_FACTOR
        for name, pos in self.neuron_positions.items():
            dist_sq = (logical_pos.x() - pos[0])**2 + (logical_pos.y() - pos[1])**2
            if dist_sq <= neuron_radius**2:
                return name
        return None

    def toggle_links(self, state):
        """
        Public slot connected to the checkbox.
        Triggers a staggered, organic fade animation for connections.
        """
        from PyQt5 import QtCore
        import time
        
        want_visible = (state == QtCore.Qt.Checked)
        
        # CRITICAL: We must enable the render loop immediately so the fade animation can play
        if want_visible:
            self.show_links = True
            
        now = time.time()
        
        # Calculate staggering based on number of connections to ensure smooth waves
        count = len(self.weights)
        
        for i, key in enumerate(self.weights.keys()):
            self._link_targets[key] = 1.0 if want_visible else 0.0
            
            # Organic staggering: 0.0 to 1.2 seconds delay based on randomness
            # This creates the \"not all at once\" effect
            delay = random.uniform(0.0, 1.2)
            
            self._link_start_times[key] = now + delay
            self._link_fade_speeds[key] = random.uniform(1.5, 4.0) # Variable fade speeds
            
            # Initialize opacity if tracking is missing
            if key not in self._link_opacities:
                self._link_opacities[key] = 0.0 if want_visible else 1.0
        
        # Ensure the fade timer is running to process the animation frames
        if not self._link_fade_timer.isActive():
            self._link_fade_timer.start()
            
        self.mark_render_dirty()

    def toggle_weights(self, state):
        self.show_weights = (state == QtCore.Qt.Checked)
        self.mark_render_dirty()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MiddleButton:
            self._pan_last = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() != QtCore.Qt.LeftButton:
            super().mousePressEvent(event)
            return

        logical_pos = self._get_logical_coords(event.pos())
        neuron = self.get_neuron_at_pos(event.pos())
        
        if not neuron:
            self.dragged_neuron = None
            self.dragging = False
            # Dragging empty space pans the view.
            self._pan_last = event.pos()
            self.setCursor(QtCore.Qt.ClosedHandCursor)
            super().mousePressEvent(event)
            return

        # Allow dragging any neuron
        self.dragged_neuron = neuron
        self.dragging = True
        self.drag_start_pos = event.pos()
        
        # Debug info
        is_neuro = self.is_neurogenesis_neuron(neuron)
        neuron_type = "Neurogenesis" if is_neuro else "Core"
        
        # Debug: Check if neuron is in functional_neurons
        if hasattr(self, 'enhanced_neurogenesis') and neuron in self.enhanced_neurogenesis.functional_neurons:
            print(f"   Functional neuron details: {self.enhanced_neurogenesis.functional_neurons[neuron]}")
        
        self.update()
        super().mousePressEvent(event)

    def handle_neuron_clicked(self, neuron_name):
        print("")

    def mouseMoveEvent(self, event):
        """Handle mouse movement for tooltips, hover tracking, and dragging"""
        if self._pan_last is not None:
            delta = event.pos() - self._pan_last
            self._pan_last = event.pos()
            self.pan_by(delta.x(), delta.y())
            event.accept()
            return
        if hasattr(self, 'tooltip_manager'):
            self.tooltip_manager.show_tooltip_for_position(event)

        # 1. Track hover state for neurons
        neuron = self.get_neuron_at_pos(event.pos())
        
        # Determine if neuron hover state changed
        if neuron != self.hovered_neuron:
            self.hovered_neuron = neuron
            self.hover_animation_time = time.time()
            self.hover_value_opacity = 0.0
            self.hover_value_display_active = neuron is not None
            self.update() 

        # 2. [NEW] Track hover state for connections (only if not hovering a neuron)
        if not neuron:
            conn = self.get_connection_at_pos(event.pos())
            if conn != self.hovered_connection:
                self.hovered_connection = conn
                self.update() # Trigger repaint for overlay
        else:
            # If hovering neuron, clear connection highlight
            if self.hovered_connection is not None:
                self.hovered_connection = None
                self.update()

        # 3. Dragging logic
        if getattr(self, 'dragging', False) and getattr(self, 'dragged_neuron', None):
            if self.is_neurogenesis_neuron(self.dragged_neuron):
                logical_pos = self._get_logical_coords(event.pos())
                self.neuron_positions[self.dragged_neuron] = (logical_pos.x(), logical_pos.y())
                self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Clear hover state when mouse leaves widget."""
        if self.hovered_neuron is not None:
            self.hovered_neuron = None
            self.hover_value_display_active = False
            self.hover_value_opacity = 0.0
            self.update()
        super().leaveEvent(event)

    def mouseDoubleClickEvent(self, event):
        """
        Handle double-click on a neuron to open the Neuron Laboratory instead of the Inspector.
        """
        if event.button() == QtCore.Qt.LeftButton:
            neuron_name = self.get_neuron_at_pos(event.pos())
            
            if not neuron_name:
                # Double-clicking empty space brings the whole network back.
                self.reset_view()
                event.accept()
                return

            if neuron_name:
                print(f"Double-clicked on neuron: {neuron_name}")
                
                # Close the old Inspector if it's currently open (compatibility cleanup)
                if hasattr(self, '_inspector') and self._inspector and self._inspector.isVisible():
                    self._inspector.close()
                    self._inspector = None # Clear the old reference

                # Open or show the Neuron Laboratory
                if self._laboratory is None:
                    self._laboratory = NeuronLaboratory(self, parent=self.window() or self.parent()) 
                
                self._laboratory.show()
                self._laboratory.raise_() # Bring the window to the front

                # CALL A NEW METHOD: Pass the neuron name for selection
                if hasattr(self._laboratory, 'select_neuron_by_name'):
                    self._laboratory.select_neuron_by_name(neuron_name)
                
                self.update() # Redraw the brain visualization
                event.accept()
                return
            
        super().mouseDoubleClickEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pan_last is not None and event.button() in (
                QtCore.Qt.LeftButton, QtCore.Qt.MiddleButton):
            self._pan_last = None
            self.unsetCursor()
            if event.button() == QtCore.Qt.MiddleButton:
                event.accept()
                return
        if event.button() == QtCore.Qt.LeftButton:
            is_click = False
            if self.dragged_neuron and self.drag_start_pos:
                distance = (event.pos() - self.drag_start_pos).manhattanLength()
                if distance < QtWidgets.QApplication.startDragDistance():
                    is_click = True
            if is_click:
                self.neuronClicked.emit(self.dragged_neuron)
            self.dragging = False
            self.dragged_neuron = None
            self.drag_start_pos = None
            self.update()
            # Only apply repulsion to neurogenesis neurons
            #if hasattr(self, 'enhanced_neurogenesis'):
            #    self.apply_repulsion_force()
        super().mouseReleaseEvent(event)

    def _is_click_on_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return (abs(scaled_x - point.x()) <= 25 * scale and abs(scaled_y - point.y()) <= 25 * scale)

    def is_point_inside_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return ((scaled_x - 25 * scale) <= point.x() <= (scaled_x + 25 * scale) and (scaled_y - 25 * scale) <= point.y() <= (scaled_y + 25 * scale))
