What if a Tamagotchi had a neural network and could learn stuff?
# Dosidicus electronicae
### A digital pet with a simple neural network [research project]
* Includes detailed tools for visualising and understanding how neural networks and Hebbian learning work

* requires `PyQt5` and `numpy`
* a compiled binary for Windows is available on the [Releases](https://github.com/ViciousSquid/Dosidicus/releases) page

![image](https://github.com/user-attachments/assets/6102225a-52d6-440c-adfb-a58fd800f1cd)







### Autonomous Behavior:

* The squid moves autonomously, making decisions based on his current state (hunger, sleepiness, etc.).
* Implements a vision cone for food detection, simulating realistic foraging behavior.


### Needs Management System:

* Tracks various needs like hunger, sleepiness, happiness, and cleanliness.
* Needs change over time and affect the pet's health and behavior.
* The squid can become sick if his needs are neglected.

Be aware the squid hates taking medicine and will become depressed and need sleep if made to do so.

### Personality system

* Seven different [personality types](https://github.com/ViciousSquid/Dosidicus/blob/main/Docs/Personalities.md) which influence behaviour

### Decorate and customise!

* Choose decorations to be placed into the environment which the squid will interact with!

### Debug Tools:

* View and edit the squid's internal state. 
* Behaviour can be influenced by editing neurons and weights
* Ability to record brain state and apply Hebbian learning
