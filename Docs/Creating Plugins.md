# Plugin Template Structure


### Examine the `/plugins/multiplayer` directory for the multiplayer plugin example

When creating a plugin for Dosidicus, you should follow this structure:

```
plugins/
└── plugin_name/
    ├── main.py
    └── assets/
        └── (any images or other assets)
```


## Available Hooks

The following hooks are available for plugins to use:

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

## Using the Plugin API

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
