# Mod Template Structure

When creating a mod for Dosidicus, you should follow this structure:

```
mods/
└── your_mod_name/
    ├── mod.json
    ├── main.py
    ├── README.md
    └── assets/
        └── (any images or other assets)
```

## mod.json

This file contains metadata about your mod:

```json
{
  "name": "Your Mod Name",
  "version": "0.1.0",
  "author": "Your Name",
  "description": "A brief description of what your mod does",
  "main_file": "main.py",
  "enabled": false
}
```

## main.py

This is the main entry point for your mod. It should define a class with hook methods and an `initialize()` function:

```python
# Import any required modules
from PyQt5 import QtWidgets, QtCore, QtGui
import random
import os

class MyModClass:
    """Main mod class."""
    
    def __init__(self):
        """Initialize your mod here."""
        self.name = "Your Mod Name"
        self.version = "0.1.0"
        print(f"{self.name} initialized!")
        
        # You can store any mod-specific state here
        self.my_custom_variable = 42
    
    def on_init(self, tamagotchi_logic):
        """Called when the game is initialized."""
        # Use this to set up your mod
        self.api = tamagotchi_logic.mod_api
        
        # Example: Register a custom menu
        self.my_menu = self.api.register_menu("My Mod Menu")
        self.api.register_action(self.my_menu, "Do Something", self.do_something)
    
    def do_something(self):
        """Custom action for the menu."""
        self.api.show_message("My mod did something!")
    
    def on_update(self, tamagotchi_logic):
        """Called every game update tick."""
        # This runs frequently - be efficient!
        pass
    
    def on_feed(self, tamagotchi_logic):
        """Called when the squid is fed."""
        # Return True to override default behavior
        return False
    
    # Define other hook methods as needed...
    
    def cleanup(self):
        """Called when the mod is unloaded."""
        print(f"{self.name} cleaned up!")

def initialize():
    """Initialize and return the mod instance."""
    return MyModClass()
```

## Available Hooks

The following hooks are available for mods to use:

1. `on_init(tamagotchi_logic)`: Called when the game is initialized
2. `on_update(tamagotchi_logic)`: Called every game update tick
3. `on_feed(tamagotchi_logic)`: Called when the squid is fed
4. `on_clean(tamagotchi_logic)`: Called when the environment is cleaned
5. `on_medicine(tamagotchi_logic)`: Called when medicine is given
6. `on_spawn_food(tamagotchi_logic, food_item)`: Called when food is spawned
7. `on_spawn_poop(tamagotchi_logic, poop_item)`: Called when poop is spawned
8. `on_save_game(tamagotchi_logic, save_data)`: Called when the game is saved
9. `on_load_game(tamagotchi_logic, save_data)`: Called when the game is loaded
10. `on_squid_state_change(squid, attribute, old_value, new_value)`: Called when a squid attribute changes
11. `on_setup_ui(ui)`: Called when the UI is being set up
12. `on_key_press(event)`: Called when a key is pressed
13. `on_scene_click(event)`: Called when the scene is clicked
14. `on_window_resize(event)`: Called when the window is resized
15. `on_menu_setup(menu_bar)`: Called when the menu bar is being set up

## Using the Mod API

The `tamagotchi_logic.mod_api` provides various helper methods for interacting with the game:

```python
# UI operations
api.show_message("Hello world!")
api.register_menu("My Menu")

# Game operations
api.spawn_food(x=100, y=100, is_sushi=True)
api.modify_stat("happiness", 10)  # Add 10 to happiness
api.add_memory("mod", "action", "Did something cool", importance=7)

# Custom graphics
pixmap = QtGui.QPixmap("path/to/image.png")
api.register_custom_graphic(pixmap, x=200, y=200)

# Timers
api.register_timer(1000, my_timer_callback)  # Call every 1 second

# Keyboard
api.register_keyboard_shortcut("Ctrl+M", my_shortcut_callback)
```

## Saving and Loading Mod Data

To save mod-specific data, use the `on_save_game` and `on_load_game` hooks:

```python
def on_save_game(self, tamagotchi_logic, save_data):
    # Create a section for your mod's data
    if 'mod_data' not in save_data:
        save_data['mod_data'] = {}
    
    save_data['mod_data']['my_mod'] = {
        'variable': self.my_custom_variable,
        'other_data': 'some value'
    }

def on_load_game(self, tamagotchi_logic, save_data):
    # Load your mod's data if it exists
    if 'mod_data' in save_data and 'my_mod' in save_data['mod_data']:
        mod_data = save_data['mod_data']['my_mod']
        self.my_custom_variable = mod_data.get('variable', 42)
        # Load other data...
```
