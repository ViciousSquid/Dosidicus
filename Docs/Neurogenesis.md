Neurogenesis Implementation
===========================

1\. State Tracking
------------------

Neurogenesis is tracked through these data structures in `BrainWidget`:

```self.neurogenesis\_data = { 'novelty\_counter': 0, 'new\_neurons': \[\], # List of neuron names 'last\_neuron\_time': time.time() } self.neurogenesis\_config = { 'novelty\_threshold': 3, 'stress\_threshold': 0.7, 'cooldown': 300 # 5 minutes (seconds) }```

2\. Trigger Conditions
----------------------

Three factors can trigger neurogenesis (tracked in `tamagotchi_logic.py`):

```self.neurogenesis\_triggers = { 'novel\_objects': 0, # Counts new interactions 'high\_stress\_cycles': 0, # Duration of stress 'positive\_outcomes': 0 # Reward events }```

### Thresholds (from neurogenesis\_config.json):

*   Novelty: 3+ new objects
*   Stress: >0.7 sustained stress
*   Reward: 5+ positive outcomes

3\. Neuron Creation Logic
-------------------------

When `update_state()` is called, it checks conditions:

```def check\_neurogenesis(self, state): current\_time = time.time() # Debug bypass if state.get('\_debug\_forced\_neurogenesis', False): self.\_create\_neuron\_internal('debug', state) return True # Check cooldown period if current\_time - self.neurogenesis\_data\['last\_neuron\_time'\] > self.neurogenesis\_config\['cooldown'\]: # Check each trigger condition if state.get('novelty\_exposure', 0) > self.neurogenesis\_config\['novelty\_threshold'\]: self.\_create\_neuron\_internal('novelty', state) if state.get('sustained\_stress', 0) > self.neurogenesis\_config\['stress\_threshold'\]: self.\_create\_neuron\_internal('stress', state) if state.get('recent\_rewards', 0) > self.neurogenesis\_config\['reward\_threshold'\]: self.\_create\_neuron\_internal('reward', state)```

4\. Neuron Creation Process
---------------------------

```def \_create\_neuron\_internal(self, neuron\_type, trigger\_data): # Generate unique name (e.g., "novel\_1") base\_name = {'novelty': 'novel', 'stress': 'defense', 'reward': 'reward'}\[neuron\_type\] new\_name = f"{base\_name}\_{len(self.neurogenesis\_data\['new\_neurons'\])}" # Position near an active neuron base\_x, base\_y = random.choice(list(self.neuron\_positions.values())) self.neuron\_positions\[new\_name\] = ( base\_x + random.randint(-50, 50), base\_y + random.randint(-50, 50) ) # Initialize state (50 = medium activation) self.state\[new\_name\] = 50 # Set color based on type self.state\_colors\[new\_name\] = { 'novelty': (255, 255, 150), # Yellow 'stress': (255, 150, 150), # Red 'reward': (150, 255, 150) # Green }\[neuron\_type\] # Create default connections for target, weight in self.neurogenesis\_config\['default\_connections'\]\[neuron\_type\].items(): self.weights\[(new\_name, target)\] = weight self.weights\[(target, new\_name)\] = weight \* 0.5 # Weaker reciprocal # Track and visualize self.neurogenesis\_data\['new\_neurons'\].append(new\_name) self.neurogenesis\_data\['last\_neuron\_time'\] = time.time() self.\_highlight\_neuron(new\_name)```

5\. Visualization
-----------------

New neurons are drawn as triangles with type-specific colors:

```def draw\_triangular\_neuron(self, painter, x, y, value, label): # Get color based on neuron type prefix if label.startswith('novel'): color = QtGui.QColor(255, 255, 150) # Yellow elif label.startswith('defense'): color = QtGui.QColor(255, 150, 150) # Red else: # reward color = QtGui.QColor(150, 255, 150) # Green painter.setBrush(color) # Draw triangle triangle = QtGui.QPolygonF() size = 25 triangle.append(QtCore.QPointF(x - size, y + size)) triangle.append(QtCore.QPointF(x + size, y + size)) triangle.append(QtCore.QPointF(x, y - size)) painter.drawPolygon(triangle)```

6\. Personality Modifiers
-------------------------

From `neurogenesis_config.json`:

```"personality\_modifiers": { "timid": { "stress\_sensitivity": 1.5, # 50% more sensitive to stress "novelty\_sensitivity": 0.7 # 30% less sensitive to novelty }, "adventurous": { "novelty\_sensitivity": 1.8, # 80% more sensitive "reward\_sensitivity": 1.2 # 20% more sensitive } }```
