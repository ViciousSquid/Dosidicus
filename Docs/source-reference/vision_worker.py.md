#### vision_worker.py
This is the computational engine of the squid's perception. It runs as a background thread (QThread) to ensure that geometric calculations do not "freeze" the main game animations.

#### Core Responsibilities:
* **Asynchronous Calculation**: Performs vision cone and proximity checks at a fixed frequency (20Hz) **independently of the main game loop**.
* **Vision Cone Logic**: Determines if objects (food, rocks, plants) are within the squid's 80-degree field of view by calculating the angular difference between the squid's gaze and the object's position.
* **Proximity Sensing**: Calculates "tactile" proximity to plants. Unlike the vision cone, this uses bounding-box edge distances to detect if the squid is touching or near a plant (0–100 range).
* **Change Detection**: It monitors the environment and only "alerts" the squid via signals when something meaningful changes (e.g., food just appeared in view).

#### Key Functions:

* `_calculate_visibility()` - The math core; checks every scene object against the vision cone and calculates distances.
* `update_squid_state()` - Receives the squid's current X/Y and gaze angle from the main thread.
* `update_scene_objects()` - Receives a lightweight list of all items currently in the tank.
* `_check_and_emit_changes()` - Fires signals like `food_visibility_changed` or `plant_proximity_changed` only when state shifts.

#### Key internal objects

* `SquidVisionState`: A data class containing a snapshot of the squid's position, size, and gaze angle.
* `SceneObject`: A lightweight representation of a world object (food, plant, rock) used for visibility checks.
* `VisionResult`: A container for the output of a vision cycle, listing visible items and proximity values.
* `VisionWorker`: The QThread subclass that constantly calculates what is inside the vision cone.


----------------------

#### "Producer-Consumer" model:

1.  **Input**: [`Squid.py`](../source-reference/squid.py.md) periodically sends its position to the `VisionWorker`.
2.  **Processing**: `VisionWorker` (in the background) identifies what is visible and sends a `VisionResult` back to the Squid.
3.  **Behaviour**: The Squid uses that result to decide if it should chase food or feel calm near a plant.
4.  **Display**: If the VisionWindow is open, it reads those same results to display the "Visible Objects" list to the user.

* **Note:** The VisionWorker includes a "Circuit Breaker" logic to prevent the squid from chasing "ghost food" that was just eaten but hasn't been cleared from the background thread's cache yet.