 #### custom_brain_loader.py
The brain architecture import/export system that allows custom neural network designs from the Brain Designer tool to be loaded into the live simulation. It handles parsing various brain file formats, applying the architecture to the running BrainWidget, and integrating with the save/load system so custom brains persist across game sessions. This is what makes the Brain Designer's output actually playable.

#### Global State Tracking:

* Tracks currently loaded custom brain name, definition, and source file path
* `has_custom_brain()` / `get_custom_brain_name()` — API for querying current state

#### BrainLoader Class:

* `show_dialog()` — opens brain selection UI
* `_parse(raw_data)` — normalizes different brain file formats into consistent structure
* `_apply(parsed_brain)` — applies positions, weights, and output bindings to live BrainWidget
* `reset_positions_to_default()` — restores original layout while preserving network structure

#### Save/Load Integration:

* `get_custom_brain_save_data()` — packages custom brain definition for game saves
* `restore_custom_brain_from_save()` — restores custom brain when loading a save
* `validate_custom_brain_save()` — checks if a save file's custom brain can be loaded
* `show_custom_brain_load_warning()` — warns user when loading saves with custom brains

#### BrainSelectDialog:

* File browser UI for .json brain files in the brains folder
* Shows metadata preview (neuron count, connection count, description)
* Supports browsing to external files or opening the brains folder