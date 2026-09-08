Save and load functionality is handled by the [SaveManager](https://github.com/ViciousSquid/Dosidicus/blob/2.4.4_stable/src/save_manager.py) class. 

It uses a structured approach that packages all game data into a single, portable file. <h4>Save File Location and Types</h4> The SaveManager creates and manages files within a `saves` directory in the application's root folder. It maintains two distinct save slots: <ul> <li><code>`autosave.zip`</code>: This file is used for periodic, automatic saves that occur in the background.</li> <li><code>`save_data.zip`</code>: This file is used when the player manually saves their game through the File menu.</li> </ul> <h4>Save File Structure</h4> When `save_game()` is called, it bundles data into the following internal JSON files within the zip archive: <ul> <li><code>game_state.json</code>: Contains general game state information, such as the squid's core stats (hunger, happiness), and other top-level game variables.</li> <li><code>brain_state.json</code>: Stores the complete state of the neural network, including neurogenesis data and the `pattern buffer` of learned experiences.</li> <li><code>ShortTerm.json</code>: A snapshot of all memories currently in the squid's short-term memory.</li> <li><code>LongTerm.json</code>: A snapshot of all memories that have been consolidated into long-term memory.</li> <li><code>plugin_data.json</code>: Contains any persistent data that active plugins have chosen to save.</li> <li> <code>statistics.json</code>: Stores persistant statistics tracked over time such as squid age, distance swam, foods eaten, etc</li> <li><code>uuid.txt</code>: Unique squid identifier (128bit number)</li></ul> 

------------------------------------------

[SaveViewer.html](../extras/SaveViewer.md) is available for easy viewing and comparisons of save files. 

This tool can also convert old v1 saved games (pre 2.4.5.0) to the new v2 format (2.5.0.0+)

