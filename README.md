# Dosidicus electronicae
### A digital pet with a simple neural network
### 50% Tamagotchi, 50% research project
* Includes detailed tools for visualising and understanding how neural networks and Hebbian learning work

* requires `python 3.10`+ with `PyQt5` and `numpy`
* a compiled binary for Windows is available on the [Releases](https://github.com/ViciousSquid/Dosidicus/releases) page

![image](https://github.com/user-attachments/assets/78ff4252-6d7a-4bbd-bf91-261e25ac5ef4)





### Autonomous Behavior:

* The squid moves autonomously, making decisions based on his current state (hunger, sleepiness, etc.).
* Implements a vision cone for food detection, simulating realistic foraging behavior.


### Needs Management System:

* Tracks various needs like hunger, sleepiness, happiness, and cleanliness.
* Needs change over time and affect the pet's health and behavior.
* The squid can become sick if his needs are neglected.

### Personality System:

* Seven possible different personality types which influence behaviour - [see here](https://github.com/ViciousSquid/Dosidicus/blob/main/Docs/Personalities.md)


Be aware the squid hates taking medicine and will become depressed and need sleep if made to do so.


Please Read the [Documentation](https://github.com/ViciousSquid/Dosidicus/tree/main/Docs)



### Debug Tools:

* View and edit the squid's internal state. 
* Behaviour can be influenced by editing neurons and weights
* Ability to record brain state and apply Hebbian learning
