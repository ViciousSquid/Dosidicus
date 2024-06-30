## Detailed Overview of Classes and Functions

**1. Neuron Class**

* **Purpose:** Represents a single neuron in the neural network.
* **Attributes:**
    * `name (str)`: Unique identifier for the neuron.
    * `layer (str)`: Layer the neuron belongs to (input, hidden, or output).
    * `connections (dict)`: Dictionary storing connections to other neurons. Keys are neuron names, values are the weight of the connection.
    * `value (float)`: Current activation value of the neuron.
* **Methods:**
    * `activate(self, input_value)`: Applies the sigmoid activation function (1 / (1 + exp(-input_value))) to the input value and updates the neuron's value.

**2. Brain Class**

* **Purpose:** Represents the entire artificial neural network.
* **Attributes:**
    * `brain_folder (str)`: Folder path where neuron data files are stored.
    * `neurons (dict)`: Dictionary containing all neurons in the network, organized by layer (input, hidden, output). Each layer's value is another dictionary with neuron names as keys and Neuron objects as values.
    * `paused (bool)`: Flag indicating if the brain is currently paused (not processing inputs).
* **Initialization Methods:**
    * `__init__(self, brain_folder="neurons")`:
        * Sets the `brain_folder` attribute.
        * Checks if the folder exists.
            * If not, creates the folder and calls `create_initial_brain` to initialize the brain.
            * If it exists and is not empty, calls `load_brain` to load neuron data from files.
            * If it exists but is empty, calls `create_initial_brain`.
    * `create_initial_brain(self)`:
        * Defines predefined names for input, hidden, and output neurons.
        * Creates Neuron objects for each neuron name and adds them to the `neurons` dictionary with their respective layers.
        * Establishes random initial connections between neurons in adjacent layers by assigning random weights (-1 to 1) to connections in the `connections` dictionary of each neuron.
        * Calls `save_brain` to save the initial brain data to neuron files.
* **Loading and Saving Methods:**
    * `load_brain(self)`:
        * Iterates through all files in the `brain_folder`.
        * For each file ending with ".json" (assuming neuron data files), calls `load_neuron` to load the data and create the corresponding Neuron object.
    * `load_neuron(self, neuron_name)`:
        * Constructs the file path for the given neuron's data file.
        * If the file exists, opens it, reads the JSON data, and creates a Neuron object with the loaded attributes (layer, connections, value).
        * Adds the created Neuron object to the `neurons` dictionary under its corresponding layer.
    * `save_brain(self)`:
        * Iterates through all neurons in the `neurons` dictionary (across all layers).
        * For each neuron, calls `save_neuron` to save its data to a separate JSON file in the `brain_folder`.
    * `save_neuron(self, neuron)`:
        * Constructs the file path for the neuron's data file.
        * Creates a dictionary containing the neuron's layer, connections, and value.
        * Saves the dictionary as JSON data to the corresponding file path.
* **Information Retrieval Method:**
    * `get_all_neurons_info(self)`:
        * Creates a dictionary to store information about all neurons.
        * Iterates through each layer in the `neurons` dictionary.
            * For each neuron in the layer, creates a dictionary with its name, value, and connections.
        * Adds the layer's neuron information dictionary to the main information dictionary.
        * Returns the main dictionary containing information about all neurons in the network.
* **Thinking Method:**
    * `think(self, inputs)`:
        * Takes a dictionary `inputs` where keys are input neuron names and values are their activation values.
