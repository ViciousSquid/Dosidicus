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
        # Using print here as logger might not be available/configured at this early stage of module loading
        print(f"Multiplayer Plugin (main.py) Warning: 'src' directory not reliably found from {current_file_dir}. Imports might fail.")
        # Default to a common structure if unsure (e.g., plugin is in 'project_root/plugins/plugin_name/')
        project_root = project_root_candidate_one_up

    if project_root and project_root not in sys.path:
        sys.path.insert(0, project_root)
        # Optional: print(f"Multiplayer Plugin (main.py): Added '{project_root}' to sys.path for src imports.")
    if current_file_dir not in sys.path: # Add current plugin directory to sys.path (for relative imports if run directly)
        sys.path.insert(0, current_file_dir)

except Exception as e:
    print(f"Multiplayer Plugin (main.py): Error setting up sys.path: {e}")
# --- End Python Path Setup ---

# Import after sys.path modifications
try:
    from src.tamagotchi_logic import TamagotchiLogic
except ImportError:
    # This print is important for diagnosing issues if the main application structure isn't found
    print("Multiplayer Plugin (main.py) CRITICAL IMPORT ERROR: TamagotchiLogic could not be imported. Ensure 'src' is in sys.path and contains tamagotchi_logic.py.")
    TamagotchiLogic = None # Define as None if import fails, plugin should handle this gracefully.

# Import plugin metadata constants (defined centrally)
from . import mp_constants # Use this to access PLUGIN_NAME, etc.

# Import the main plugin class
from .mp_plugin_logic import MultiplayerPlugin


# --- Plugin Registration Function ---
def initialize(plugin_manager_instance): # plugin_manager_instance is the actual PluginManager object
    """
    Initializes the Multiplayer plugin and registers it with the plugin manager.
    This function is called by the plugin system.
    """
    try:
        # Create an instance of the main plugin class
        plugin_instance = MultiplayerPlugin() # This is MultiplayerPlugin from mp_plugin_logic.py

        # --- MODIFICATION: Set plugin_manager on the instance ---
        # Explicitly set the plugin_manager on the plugin instance here.
        # This ensures it's available to the plugin instance's methods like enable() and particularly setup().
        # Assumes MultiplayerPlugin.__init__ defines self.plugin_manager = None
        plugin_instance.plugin_manager = plugin_manager_instance
        # --- END MODIFICATION ---

        # Define a unique key for the plugin (e.g., based on its name from constants)
        plugin_key = mp_constants.PLUGIN_NAME.lower().replace(" ", "_") # Example: "multiplayer"

        # Register the plugin with the plugin manager
        # The plugin manager will use this information to manage the plugin
        plugin_manager_instance.plugins[plugin_key] = {
            'instance': plugin_instance,          # The actual plugin object
            'name': mp_constants.PLUGIN_NAME,      # Display name of the plugin
            'version': mp_constants.PLUGIN_VERSION,# Version number
            'author': mp_constants.PLUGIN_AUTHOR,  # Author(s)
            'description': mp_constants.PLUGIN_DESCRIPTION, # Brief description
            'requires': mp_constants.PLUGIN_REQUIRES,      # List of dependencies (other plugin names)
            'is_setup': False,                    # Plugin's own setup method will set this to True
            'is_enabled_by_default': False         # Set to True if it should be enabled on start
        }

        # The plugin manager should ideally pass itself to the plugin instance,
        # which we now do above.
        # The MultiplayerPlugin.enable() method relies on self.plugin_manager being set.

        # This print uses the global print function, as an instance logger isn't set up for this main.py scope.
        print(f"{mp_constants.PLUGIN_NAME} (Version: {mp_constants.PLUGIN_VERSION} by {mp_constants.PLUGIN_AUTHOR}) has been registered with the plugin manager.")
        return True
    except Exception as e:
        # Use global print for errors at this very early stage if a logger isn't available/reliable
        print(f"Error during {mp_constants.PLUGIN_NAME} plugin initialization (in plugins/multiplayer/main.py): {e}")
        traceback.print_exc() # Print full traceback for diagnosing initialization errors
        return False

# --- End of Plugin Registration ---