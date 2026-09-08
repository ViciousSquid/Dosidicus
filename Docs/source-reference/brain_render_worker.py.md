_Not to be confused with [brain_worker.py](../source-reference/brain_worker.py.md)_

#### brain_render_worker.py (938 lines)
An offscreen rendering engine running in its own QThread that paints the entire brain visualization to a QImage buffer. The main thread simply blits this cached image during paintEvent, dramatically improving UI responsiveness. The worker receives immutable state snapshots and handles all the complex drawing logic—connections with animated pulses, neurons with various shapes, localized labels, and visual effects for learning events.

#### RenderState Dataclass:

* Immutable snapshot containing positions, states, colors, weights, and animation parameters
* Created on main thread via `create_render_state_from_widget()` helper
* Includes pre-calculated localized neuron labels to avoid i18n lookups during render

#### Rendering Pipeline:

`request_render(state)` — throttled to 10 FPS
* Draws and animates neurons and connections
