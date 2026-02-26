The <strong>Network Tab</strong> provides a live, visual representation of the overall structure and health of the neural network in real-time. 

<img src="https://github.com/user-attachments/assets/0e5ecc7e-9b15-47d7-a454-276769635b58" width="600">


- Each neural network is unique and randomly generated (with rules) when the squid is hatched
- Red lines represent Excitory (positive) connections between neurons
- Green lines represent Inhibitory (negative) connections
- The thicker the line, the stronger the connection



  <h4>Interface Elements</h4> <ul> <li> <strong>Neural Visualizer:</strong> The main canvas displaying the neurons as nodes and their connections as lines. The pulsing and glowing of neurons and links indicate activity and learning events. </li> <li> <strong>Metrics Bar:</strong> Located at the top, this bar provides at-a-glance statistics: <ul> <li><strong>Neurons:</strong> The total number of neurons currently in the brain.</li> <li><strong>Connections:</strong> The total number of weighted connections between neurons.</li> <li><strong>Network Health:</strong> Overall stability and efficiency of the network, primarily based on average connection strength.</li> </ul> </li> <li> <strong>Hebbian Timer:</strong> A countdown (e.g., "Hebbian: 25") showing the time remaining until the next Hebbian learning cycle is performed. </li> <li> <strong>Control Checkboxes:</strong> <ul> <li><strong>Show links:</strong> Toggles the visibility of the lines connecting the neurons.</li> <li><strong>Show weights:</strong> Toggles the display of the numerical weight on each connection line.</li> <li><strong>Enable pruning:</strong> Toggles the automatic removal of old, weak, or unused neurons to maintain network stability. Disabling this can lead to an unconstrained and potentially unstable network.</li> </ul></ul>

The big button with the brain on it opens the [Brain Designer](../brain-tool/Brain-Designer.md) which allows you to build and edit custom brains and behaviours
