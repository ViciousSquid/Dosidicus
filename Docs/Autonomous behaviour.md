The squid acts autonomously depending on his environment. Here's an example of a reaction to the window being resized:


**Window Resize Event**: When the window is resized, the `handle_window_resize` method in the Ui class is called. This method does two important things:
* It updates the UI elements to fit the new window size.
* It informs the squid's brain about the resize event by calling:

```python
self.tamagotchi_logic.squid.brain.handle_window_resize(
    old_width, old_height, self.window_width, self.window_height)
```

**Brain Receives Resize Information**:
The `handle_window_resize` method in the Brain class is called with the old and new dimensions. This method determines if the environment got larger or smaller:

```python
def handle_window_resize(self, old_width, old_height, new_width, new_height):
    if new_width > old_width or new_height > old_height:
        self.react_to_larger_environment(new_width, new_height)
    else:
        self.react_to_smaller_environment()
```

**Brain Decides to Investigate**:
If the environment got larger, the `react_to_larger_environment` method is called. This method:
* First startles the squid:

```python
self.squid.mental_state_manager.set_state("startled", True)
```

* Then, after a short delay, it starts the investigation:

```python
QtCore.QTimer.singleShot(2000, lambda: self.start_investigation(new_width, new_height))
```

**Investigation Process**:
The `start_investigation` method initiates the curious state and sets up a timer for continuous investigation:

```python
def start_investigation(self, width, height):
    self.squid.mental_state_manager.set_state("curious", True)
    self.is_investigating = True
    self.investigation_timer = QtCore.QTimer()
    self.investigation_timer.timeout.connect(lambda: self.continue_investigation(width, height))
    self.investigation_timer.start(3000)  # Investigate every 3 seconds
```

**Continuing Investigation**:
Every 3 seconds, the continue_investigation method is called. This method:
* 1. Chooses a random position within the new window boundaries:

```python
new_x = random.randint(100, width - 150 - self.squid.squid_width)
new_y = random.randint(100, height - 170 - self.squid.squid_height)
```

* 2. Moves the squid to this new position:

```python
self.squid.move_to(new_x, new_y)
```

* 3. Has a 20% chance to finish the investigation each time:

```python
if random.random() < 0.2:
    self.finish_investigation()
```

**Finishing Investigation**:
When the investigation finishes, the `finish_investigation` method:
* Stops the investigation process
* Updates the squid's mental state
* Increases happiness and decreases curiosity

This process allows the squid's brain to autonomously react to changes in its environment. The investigation is not predetermined but rather a series of random explorations within the new boundaries. This creates a more natural and unpredictable behavior for the squid.

the brain is making decisions based on the information it receives, rather than following a predetermined script.












