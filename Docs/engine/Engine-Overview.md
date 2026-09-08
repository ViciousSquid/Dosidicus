## `S`imulated `T`amagotchi `R`eactions via `I`nferencing and `N`eurogenesis `(STRINg)`

### simulation engine overview:

The architecture of Dosidicus is a "Bottom-Up" sensory system where raw environmental data is distilled into neural inputs, which are then filtered through the squid's [personality](https://github.com/ViciousSquid/Dosidicus/wiki/Personality) to produce behaviour.

Built from scratch using NumPy.

- No TensorFlow.
- No PyTorch.

### Core properties:
* Explicit neuron-level simulation
* Hebbian plasticity
* Structural growth (neurogenesis)
* Dual memory system (short-term and long-term)
* Headless training capability
* Plugin extensibility
* STRINg is optimised for interpretability not scale.

It treats neural networks not as static architectures, but as evolving structures.

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

External links

* https://medium.com/@reutdayan1/hebbian-learning-biologically-plausible-alternative-to-backpropagation-6ee0a24deb00
* https://informatics.ed.ac.uk/sites/default/files/2024-03/Qiuye%20Zhang%20Lovelace%20Colloquium%20Poster.pdf
* https://en.wikipedia.org/wiki/Hebbian_theory
* https://www.youtube.com/watch?v=TvTQQO5yTa4



