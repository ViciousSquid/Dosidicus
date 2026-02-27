## `S`imulated `T`amagotchi `R`eactions via `I`nferencing and `N`eurogenesis `(STRINg)`

### simulation engine overview:

The architecture of Dosidicus is a "Bottom-Up" sensory system where raw environmental data is distilled into neural inputs, which are then filtered through the squid's personality to produce behavior.

**brains**: small neural networks ([custom **json** format](https://github.com/ViciousSquid/Dosidicus/tree/2.6.1.2_tattoo/headless#brain-json-format)) with **applied inputs**, **learning**, **memories** and **neuron growth**.  

* Default networks are [biologically-inspired](../brain-tool/Brain-Designer.md#generate-sparse-network) semi-random single layers with **8 core neurons**

### * **No Tensorflow, No Pytorch**
* Rejects the standard "black box" approach in favour of transparent, biologically inspired learning.
* [decision engine](../engine/Decision-Engine.md) is **entirely neural network driven**

---------------------


1. From **8 core neurons**, randomly generate weights for each unique brain
2. Network grows via **[neurogenesis](../neural-network/Neurogenesis.md)** and self-trains via **[Hebbian learning](../neural-network/Hebbian-Learning.md)**

3. Automatic **pruning** of redundant neurons and weights (can be turned off)
4. [Experience buffer](../neural-network/Experience-Buffer.md) records and encodes learned experiences
5. [decision_engine](../engine/Decision-Engine.md) uses neural data to make decisions


------------------

* Beta (and optional) support for [AI accelerators via ONNX Runtime](../neural-network/AI-Accelerator-Support.md)
* **Plugin system** create MODs using Python - 50 achievements included
* _Experimental and a work in progress_
* _Probably not the best way to do this!_ 😃

---------------------------------




## Read Next: [Data flow Summary](../engine/Data-Flow-Summary.md) overview

#### Further engine studies:

- [Decision Engine](../engine/Decision-Engine.md)
- [Brain Widget](../source-reference/brain_widget.py.md)
