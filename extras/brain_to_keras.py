import json
import numpy as np
import os
import argparse

# Try to import keras, handle if not installed
try:
    import keras
    from keras import ops
except ImportError:
    print("Error: Keras v3 is required. Please install it via 'pip install keras'")
    exit(1)

class HybridActivation(keras.layers.Layer):
    """
    Applies different activation functions to different slices of the input tensor.
    This is necessary because the Brain Designer allows per-neuron activation settings.
    """
    def __init__(self, activation_map, units, **kwargs):
        """
        activation_map: dict mapping activation name ('relu', 'sigmoid') to list of indices
        units: total number of neurons
        """
        super().__init__(**kwargs)
        self.activation_map = activation_map
        self.units = units
        
        # Create boolean masks for each activation type for vectorized application
        self.masks = {}
        for act_name, indices in activation_map.items():
            mask = np.zeros(units, dtype="float32")
            mask[indices] = 1.0
            self.masks[act_name] = mask

    def call(self, inputs):
        output = ops.zeros_like(inputs)
        
        for act_name, mask in self.masks.items():
            # Convert mask to tensor
            mask_tensor = ops.convert_to_tensor(mask)
            
            # Apply standard keras activations
            if act_name == 'relu':
                activated = keras.activations.relu(inputs)
            elif act_name == 'sigmoid':
                activated = keras.activations.sigmoid(inputs)
            elif act_name == 'tanh':
                activated = keras.activations.tanh(inputs)
            elif act_name == 'linear':
                activated = inputs
            else:
                # Default to linear if unknown
                activated = inputs
            
            # Add masked contribution to output
            output = output + (activated * mask_tensor)
            
        return output

    def get_config(self):
        config = super().get_config()
        config.update({
            "activation_map": self.activation_map,
            "units": self.units
        })
        return config

class BrainCell(keras.layers.Layer):
    """
    A Custom RNN Cell that mimics the exact topology of the JSON brain design.
    """
    def __init__(self, input_units, state_units, 
                 input_weights_init, recurrent_weights_init, 
                 activation_map, output_indices, **kwargs):
        super().__init__(**kwargs)
        self.input_units = input_units
        self.state_units = state_units
        self.state_size = state_units
        self.output_size = len(output_indices) # We only output specific neurons
        self.output_indices = output_indices
        
        # Initializers (passed as numpy arrays from the converter)
        self.w_in_init = input_weights_init
        self.w_rec_init = recurrent_weights_init
        self.activation_map = activation_map

    def build(self, input_shape):
        # Input Kernel (Input Neurons -> State Neurons)
        self.kernel = self.add_weight(
            shape=(self.input_units, self.state_units),
            initializer=keras.initializers.Constant(self.w_in_init),
            name="input_kernel",
            trainable=True # Set to False to freeze the design structure exactly
        )
        
        # Recurrent Kernel (State Neurons -> State Neurons)
        self.recurrent_kernel = self.add_weight(
            shape=(self.state_units, self.state_units),
            initializer=keras.initializers.Constant(self.w_rec_init),
            name="recurrent_kernel",
            trainable=True
        )
        
        self.bias = self.add_weight(
            shape=(self.state_units,),
            initializer="zeros",
            name="bias"
        )
        
        self.hybrid_activation = HybridActivation(self.activation_map, self.state_units)
        self.built = True

    def call(self, inputs, states):
        prev_output = states[0]
        
        # Standard RNN math: h' = Act(Wx + Uh + b)
        # inputs shape: (batch, input_units)
        # prev_output shape: (batch, state_units)
        
        h_in = ops.matmul(inputs, self.kernel)
        h_rec = ops.matmul(prev_output, self.recurrent_kernel)
        
        total_input = h_in + h_rec + self.bias
        
        # Apply per-neuron activations
        output = self.hybrid_activation(total_input)
        
        return output, [output]

    def get_config(self):
        config = super().get_config()
        # Note: We don't serialize large numpy arrays in config typically, 
        # but for reconstruction within this tool it's handled via the loader.
        # For saving/loading the Keras model strictly, rely on model.save() 
        # which handles weight serialization automatically.
        config.update({
            "input_units": self.input_units,
            "state_units": self.state_units,
            "output_indices": self.output_indices,
            "activation_map": self.activation_map,
            # We cannot serialize numpy arrays directly in config for JSON safety
            # If rebuilding from config, standard initializers would be used
            # unless we implement custom logic.
        })
        return config

def load_brain_json(filepath):
    """Parses the Brain Designer JSON file."""
    with open(filepath, 'r') as f:
        data = json.load(f)
    return data

def parse_design(data):
    """
    Analyzes the JSON data to build matrices.
    Returns: input_ids, state_ids, output_ids, W_in, W_rec, act_map
    """
    
    # 1. Identify Neurons
    neurons = data.get('neurons', {})
    if isinstance(neurons, list): # Handle array format
        # Convert list to dict map
        temp = {}
        for n in neurons:
            temp[n['name']] = n
        neurons = temp
    
    # Sort into Input (Sensors) vs State (Everything else)
    # Note: In BrainDesigner logic, sensors are just neurons with 0 inputs typically, 
    # but strictly speaking, they are the interface to the outside world.
    
    input_names = []
    state_names = []
    
    # Keras needs fixed indices
    name_to_idx = {}
    
    # Logic to distinguish inputs:
    # Look for 'sensor' type or specific names in standard inputs
    known_inputs = [
        'external_stimulus', 'plant_proximity', 'threat_level', 
        'pursuing_food', 'is_sick', 'is_fleeing', 'is_eating', 
        'is_sleeping', 'is_startled', 'can_see_food'
    ]
    
    for name, props in neurons.items():
        n_type = props.get('type', props.get('neuron_type', 'hidden')).lower()
        
        # Determine if it's an input source or a stateful neuron
        if n_type == 'sensor' or name in known_inputs:
            input_names.append(name)
        else:
            state_names.append(name)
            
    # Sort for determinism
    input_names.sort()
    state_names.sort()
    
    input_map = {name: i for i, name in enumerate(input_names)}
    state_map = {name: i for i, name in enumerate(state_names)}
    
    print(f"Parsed {len(input_names)} inputs and {len(state_names)} state neurons.")
    
    # 2. Build Matrices
    n_in = len(input_names)
    n_state = len(state_names)
    
    W_in = np.zeros((n_in, n_state), dtype="float32")
    W_rec = np.zeros((n_state, n_state), dtype="float32")
    
    # Helper to find where a name belongs
    def get_loc(name):
        if name in state_map: return ('state', state_map[name])
        if name in input_map: return ('input', input_map[name])
        return (None, -1)

    # Parse Connections
    connections = data.get('connections', [])
    
    # Normalize connection format (list of dicts vs dict of strings)
    conn_list = []
    if isinstance(connections, dict):
        for k, w in connections.items():
            if '->' in k: s, t = k.split('->')
            elif '|' in k: s, t = k.split('|')
            else: continue
            conn_list.append((s, t, w))
    else:
        for c in connections:
            conn_list.append((c['source'], c['target'], c['weight']))
            
    for source, target, weight in conn_list:
        # We only care about connections going TO a state neuron.
        # Connections TO an input neuron are ignored (inputs are forced).
        
        target_type, t_idx = get_loc(target)
        if target_type != 'state':
            continue
            
        source_type, s_idx = get_loc(source)
        
        if source_type == 'input':
            W_in[s_idx, t_idx] = weight
        elif source_type == 'state':
            W_rec[s_idx, t_idx] = weight
            
    # 3. Activation Mapping
    # Group state indices by activation function
    act_map = {
        'relu': [], 'sigmoid': [], 'tanh': [], 'linear': []
    }
    
    for name in state_names:
        idx = state_map[name]
        props = neurons[name]
        
        # Default logic based on type if explicit activation not found
        act = props.get('activation')
        if not act:
            n_type = props.get('type', props.get('neuron_type', 'hidden')).lower()
            if n_type == 'output': act = 'sigmoid'
            elif n_type == 'core': act = 'relu'
            elif props.get('is_binary'): act = 'step' # approximate step with sigmoid*100 or tanh
            else: act = 'relu'
            
        if act == 'step': act = 'sigmoid' # Keras doesn't have hard step usually, mapping to sigmoid
        
        if act not in act_map:
            act_map[act] = []
        act_map[act].append(idx)

    # 4. Output Indices
    # By default, treat 'output' type or 'core' type as model outputs
    output_indices = []
    for name in state_names:
        n_type = neurons[name].get('type', neurons[name].get('neuron_type', '')).lower()
        if n_type in ['output', 'core']:
            output_indices.append(state_map[name])
            
    return n_in, n_state, W_in, W_rec, act_map, output_indices, input_names, state_names

def convert_to_keras_model(json_path, output_path):
    print(f"Loading {json_path}...")
    data = load_brain_json(json_path)
    
    # Parse topology
    n_in, n_state, W_in, W_rec, act_map, out_idx, in_names, st_names = parse_design(data)
    
    # Create the custom cell
    # Note: We must pass weights as list to `Constant` initializer or load them after.
    # Here we pass them to the constructor to initialize the layers.
    cell = BrainCell(
        input_units=n_in,
        state_units=n_state,
        input_weights_init=W_in,
        recurrent_weights_init=W_rec,
        activation_map=act_map,
        output_indices=out_idx
    )
    
    # Create the RNN Layer
    # return_sequences=True gives output at every time step
    rnn_layer = keras.layers.RNN(cell, return_sequences=True, name="brain_rnn")
    
    # Define Input
    # Shape: (None, input_features) -> Timesteps is flexible
    inputs = keras.Input(shape=(None, n_in), name="sensor_inputs")
    
    # Get RNN outputs (this returns the full state vector at every step)
    whole_state_sequence = rnn_layer(inputs)
    
    # If we want to filter only specific "Output" neurons:
    # We use a Lambda layer or slicing. Keras slicing layer is cleaner.
    if out_idx:
        # Sort indices to ensure deterministic output order
        out_idx.sort() 
        def filter_outputs(x):
            return x[:, :, out_idx] # Batch, Time, Indices
        
        # Note: Lambda layers can be tricky for saving/loading without custom objects.
        # But `ops.take` or slicing is fine.
        final_output = keras.layers.Lambda(
            lambda x: ops.take(x, indices=out_idx, axis=-1),
            name="filter_outputs"
        )(whole_state_sequence)
    else:
        final_output = whole_state_sequence

    model = keras.Model(inputs=inputs, outputs=final_output, name="DosidicusBrain")
    
    # Compile just to finalize
    model.compile(loss="mse", optimizer="adam")
    
    model.summary()
    
    # Save
    print(f"Saving Keras model to {output_path}...")
    model.save(output_path)
    print("Done.")
    
    # Print input mapping for the user
    print("\n--- Input Mapping (Index: Name) ---")
    for i, name in enumerate(in_names):
        print(f"{i}: {name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Dosidicus Brain JSON to Keras v3 Model")
    parser.add_argument("input", help="Path to input JSON file")
    parser.add_argument("output", help="Path to output .keras file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
    else:
        convert_to_keras_model(args.input, args.output)
