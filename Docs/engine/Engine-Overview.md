## `S`imulated `T`amagotchi `R`eactions via `I`nferencing and `N`eurogenesis `(STRINg)`

### simulation engine overview:

The architecture of Dosidicus is a "Bottom-Up" sensory system where raw environmental data is distilled into neural inputs, which are then filtered through the squid's [personality](https://github.com/ViciousSquid/Dosidicus/wiki/Personality) to produce behavior.

**brains**: small neural networks ([custom **json** format](https://github.com/ViciousSquid/Dosidicus/tree/2.6.1.2_tattoo/headless#brain-json-format)) with **applied inputs**, **learning**, **memories** and **neuron growth**.  

* Default networks are [biologically-inspired](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer#generate-sparse-network) semi-random single layers with **8 core neurons**

### * **No Tensorflow, No Pytorch**
* Rejects the standard "black box" approach in favour of transparent, biologically inspired learning.
* [decision engine](https://github.com/ViciousSquid/Dosidicus/wiki/Decision-Engine) is **entirely neural network driven**

---------------------


- Network grows via **[neurogenesis](https://github.com/ViciousSquid/Dosidicus/wiki/Neurogenesis)** and self-trains via **[Hebbian learning](https://github.com/ViciousSquid/Dosidicus/wiki/Hebbian-learning)**

- Automatic **pruning** of redundant neurons and weights (can be turned off)
- [Experience buffer](https://github.com/ViciousSquid/Dosidicus/wiki/Experience-Buffer) records and encodes learned experiences
- [decision_engine](https://github.com/ViciousSquid/Dosidicus/wiki/Decision-Engine) uses neural data to make decisions


------------------

* Beta (and optional) support for [AI accelerators via ONNX Runtime](https://github.com/ViciousSquid/Dosidicus/wiki/AI-accelerator-support)
* _Experimental and a work in progress_
* _Probably not the best way to do this!_ 😃

---------------------------------




## Read Next: [Data flow Summary](https://github.com/ViciousSquid/Dosidicus/wiki/Data-Flow-Summary) overview

#### Further engine studies:

- [Decision Engine](https://github.com/ViciousSquid/Dosidicus/wiki/Decision-Engine)
- [Brain Widget](https://github.com/ViciousSquid/Dosidicus/wiki/brain_widget.py)
