# File: main.py (Plugin Entry Point)

import os
import sys
import traceback # For initialize function error handling

# --- Python Path Setup ---
# Adjust these paths if your project structure is different.
# This setup helps Python find your 'src' directory and other plugin modules.
try:
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming 'main.py' is in 'project_root/plugins/your_plugin_name/'
    project_root_candidate_one_up = os.path.abspath(os.path.join(current_file_dir, '..', '..')) # plugins folder is one up, project root is two up
    project_root_candidate_two_up = os.path.abspath(os.path.join(current_file_dir, '..', '..', '..')) # If nested deeper

    project_root = None
    # Check if 'src' directory exists at the determined project root level
    if os.path.isdir(os.path.join(project_root_candidate_one_up, 'src')):
        project_root = project_root_candidate_one_up
    elif os.path.isdir(os.path.join(project_root_candidate_two_up, 'src')): # Fallback for deeper nesting
        project_root = project_root_candidate_two_up
    else:
        print(f"Multiplayer Plugin Warning: 'src' directory not reliably found from {current_file_dir}. Imports might fail.")
        # Default to a common structure if unsure (e.g., plugin is in 'project_root/plugins/plugin_name/')
        project_root = project_root_candidate_one_up

    if project_root and project_root not in sys.path:
        sys.path.insert(0, project_root)
        print(f"Multiplayer Plugin: Added '{project_root}' to sys.path for src imports.")
    if current_file_dir not in sys.path: # Add current plugin directory to sys.path (for relative imports if run directly)
        sys.path.insert(0, current_file_dir)

except Exception as e:
    print(f"Multiplayer Plugin: Error setting up sys.path in main.py: {e}")
# --- End Python Path Setup ---

# Import after sys.path modifications
try:
    from src.tamagotchi_logic import TamagotchiLogic
except ImportError:
    print("Multiplayer Plugin: TamagotchiLogic could not be imported. Ensure 'src' is in sys.path and contains tamagotchi_logic.py.")
    TamagotchiLogic = None # Define as None if import fails, plugin should handle this.

# Import plugin metadata constants (defined centrally)
from .mp_constants import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_AUTHOR,
    PLUGIN_DESCRIPTION, PLUGIN_REQUIRES
)

# Import the main plugin class
from .mp_plugin_logic import MultiplayerPlugin


# --- Plugin Registration Function ---
def initialize(plugin_manager_instance):
    """
    Initializes the Multiplayer plugin and registers it with the plugin manager.
    This function is called by the plugin system.
    """
    try:
        # Create an instance of the main plugin class
        plugin_instance = MultiplayerPlugin()

        # Define a unique key for the plugin (e.g., based on its name)
        plugin_key = PLUGIN_NAME.lower().replace(" ", "_") # Example: "multiplayer"

        # Register the plugin with the plugin manager
        # The plugin manager will use this information to manage the plugin
        plugin_manager_instance.plugins[plugin_key] = {
            'instance': plugin_instance,          # The actual plugin object
            'name': PLUGIN_NAME,                  # Display name of the plugin
            'version': PLUGIN_VERSION,            # Version number
            'author': PLUGIN_AUTHOR,              # Author(s)
            'description': PLUGIN_DESCRIPTION,    # Brief description
            'requires': PLUGIN_REQUIRES,          # List of dependencies (other plugin names)
            'is_setup': False,                    # Plugin's own setup method will set this to True
            'is_enabled_by_default': False        # Set to True if it should be enabled on start
        }

        # The plugin manager should ideally pass itself to the plugin instance,
        # for example, by calling a method like plugin_instance.set_plugin_manager(plugin_manager_instance)
        # or when calling plugin_instance.setup(plugin_manager_instance).
        # The MultiplayerPlugin.enable() method also has a fallback to find the plugin_manager.

        print(f"{PLUGIN_NAME} (Version: {PLUGIN_VERSION} by {PLUGIN_AUTHOR}) has been registered with the plugin manager.")
        return True
    except Exception as e:
        print(f"Error during {PLUGIN_NAME} plugin initialization: {e}")
        traceback.print_exc()
        return False

# --- End of Plugin Registration ---