

Neurogenesis Implementation
===========================

Neurogenesis is the process of creating new neurons in the squid's neural network network based on experiences.

1\. State Tracking
------------------

The system tracks neurogenesis data in the `BrainWidget` class:

\# In BrainWidget.\_\_init\_\_() self.neurogenesis\_data = { 'novelty\_counter': 0, # Counts novel experiences 'new\_neurons': \[\], # List of created neurons 'last\_neuron\_time': time.time() # Timestamp of last creation } # Configuration from neurogenesis\_config.json self.neurogenesis\_config = { 'novelty\_threshold': 3, # Required novel experiences 'stress\_threshold': 0.7, # Stress level needed 'reward\_threshold': 5, # Positive outcomes needed 'cooldown': 300 # 5 min cooldown (seconds) }

2\. Trigger Conditions
----------------------

Three experience types can trigger neurogenesis:

*   Novelty: New objects/interactions
*   Stress: Sustained high anxiety
*   Reward: Positive outcomes (eating, playing)

These are tracked in `tamagotchi_logic.py`:

\# In TamagotchiLogic.\_\_init\_\_() self.neurogenesis\_triggers = { 'novel\_objects': 0, # Count of new objects encountered 'high\_stress\_cycles': 0, # Duration of stress periods 'positive\_outcomes': 0 # Count of rewards received }

3\. Neuron Creation Process
---------------------------

When thresholds are met, new neurons are created:

```def \_create\_neuron\_internal(self, neuron\_type, trigger\_data): # Generate unique name (e.g., "novel\_1", "defense\_2") name\_map = {'novelty': 'novel', 'stress': 'defense', 'reward': 'reward'} new\_name = f"{name\_map\[neuron\_type\]}\_{len(self.neurogenesis\_data\['new\_neurons'\])}" # Position near an active neuron (or center if none) if self.neuron\_positions: center\_x = sum(x for x,y in self.neuron\_positions.values())/len(self.neuron\_positions) center\_y = sum(y for x,y in self.neuron\_positions.values())/len(self.neuron\_positions) else: center\_x, center\_y = 600, 300 self.neuron\_positions\[new\_name\] = ( center\_x + random.randint(-100, 100), center\_y + random.randint(-100, 100) ) # Initialize state and color self.state\[new\_name\] = 80 # High initial activation self.state\_colors\[new\_name\] = { 'novelty': (255, 255, 150), # Yellow 'stress': (255, 150, 150), # Red 'reward': (150, 255, 150) # Green }\[neuron\_type\] # Create connections to existing neurons for existing in self.neuron\_positions: if existing != new\_name: self.weights\[(new\_name, existing)\] = random.uniform(-0.5, 0.5) if (existing, new\_name) not in self.weights: self.weights\[(existing, new\_name)\] = random.uniform(-0.5, 0.5) # Update tracking data self.neurogenesis\_data\['new\_neurons'\].append(new\_name) self.neurogenesis\_data\['last\_neuron\_time'\] = time.time() # Visual highlight self.neurogenesis\_highlight = { 'neuron': new\_name, 'start\_time': time.time(), 'duration': 5.0 } self.update() # Redraw the display```

4\. Visualization
-----------------

New neurons are visually distinct:

```def draw\_triangular\_neuron(self, painter, x, y, value, label, scale=1.0): # Determine color by neuron type prefix if label.startswith('defense'): color = QtGui.QColor(255, 150, 150) # Light red elif label.startswith('novel'): color = QtGui.QColor(255, 255, 150) # Pale yellow else: # reward color = QtGui.QColor(150, 255, 150) # Light green painter.setBrush(color) # Draw triangle triangle = QtGui.QPolygonF() size = 25 \* scale triangle.append(QtCore.QPointF(x - size, y + size)) triangle.append(QtCore.QPointF(x + size, y + size)) triangle.append(QtCore.QPointF(x, y - size)) painter.drawPolygon(triangle) # Draw label painter.setPen(QtGui.QColor(0, 0, 0)) font = painter.font() font.setPointSize(int(8 \* scale)) painter.setFont(font) painter.drawText(int(x - 30 \* scale), int(y + 40 \* scale), int(60 \* scale), int(20 \* scale), QtCore.Qt.AlignCenter, label)```

Key Features:

*   New neurons are triangular (vs original circular/square neurons)
*   Color-coded by type (yellow=novelty, red=stress, green=reward)
*   Highlighted for 5 seconds after creation
*   Connected to existing neurons with randomized weights
