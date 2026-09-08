### Design your own (GPL!) squid brain!

Add new **neurons** / **layers** - see how they affect the squid's ability to process his environment
 
<img src="https://github.com/user-attachments/assets/a488556a-1326-4a07-a0f0-b9c284d94af3" width="70">

Click the brain button in the bottom right of the 
 [network tab](../brain-tool/Network-Tab.md) to swich into Designer mode

<img src="https://github.com/user-attachments/assets/5b2d88f2-53c0-4af8-ab81-7e501cfcfbf1" width="800">

FROM LEFT TO RIGHT:

1. -- Fast-Generate a random network with no prompt
2. -- Generate a random network with controls
3. -- Add a new Custom/Input Neuron
4. -- Export the brain to a .json file
5. -- Clear all connections
6. -- Quick-generate a network from template

--------------------------------------

If designer mode is launched from within the simulation (default behaviour):

* The running brain will be automatically imported into the designer. 
* The purple '**Switch to Game**' button passes the brain from the designer to the running brain tool

```
Some buttons will not be available if the designer is launched standalone (main.py -designer)
```

---------------------------------
#### CONTROLS:

* <img src="https://github.com/user-attachments/assets/0f9eb326-eee9-4ada-a1a9-2d70d4770765" width="100"> to add a neuron


* Mouse wheel on the canvas to zoom in/out, hold right mouse button to drag
* Click on a neuron and hold to drag a connection line - release on another neuron
* Select a link and use the mouse wheel to increase/decrease the connection weight (range: -1.00 to +1.00)
* negative weights are inhibitory (red), positive weights are excitory (green). 
* Press **DEL** to delete a connection link
* **SPACE** to change the direction of a connecting line (indicated with arrows)
* Stronger weights are indicated with thicker lines.
* **Ctrl-click-and drag** to reposition any neuron.
* Use the Layers tab to create more complicated brains with additional layers
* The Sensors tab shows available INPUT neurons
* The Output tab lists Output bindings for bridging neuron activations to game behaviours:

Choose a **source neuron**, a **trigger**, and **behaviour** for that trigger

EXAMPLES:
```
IF .. can_see_food .. THEN .. change colour
IF .. happiness = <30 .. THEN .. pick up a rock
IF .. anxiety = >60 .. THEN .. seek plant
```

These can be combined to create reactive behaviours (simulated _biological drives/**urges**_)

<img src="https://github.com/user-attachments/assets/08f3ab4a-5790-4df6-b5dd-59547039cfe1" width="300">


------------------------

### `Generate sparse network`

The 'generate sparse network' button creates biologically-inspired neural networks using the core 8 neurons. Each generated brain is unique and randomised.


<img src="https://github.com/user-attachments/assets/d15321ca-cc53-44f8-bc45-c4f787995f38" width="300">
