# Dosidicus electronicae
A Tamagotchi digital pet with a simple neural network
* Includes detailed tools for visualising and understanding how neural networks and Hebbian learning work

* requires **PyQt5** and **pyqtgraph**

![image](https://github.com/user-attachments/assets/78ff4252-6d7a-4bbd-bf91-261e25ac5ef4)





### Autonomous Behavior:

* The squid moves autonomously, making decisions based on his current state (hunger, sleepiness, etc.).
* Implements a vision cone for food detection, simulating realistic foraging behavior.


### Needs Management System:

* Tracks various needs like hunger, sleepiness, happiness, and cleanliness.
* Needs change over time and affect the pet's health and behavior.
* The squid can become sick if his needs are neglected.


Be aware the squid hates taking mecicine and will become depressed and need sleep if made to do so.



### Debug Tools:

* View and edit the squid's internal state. 
* Behaviour can be influenced by editing neurons and weights
* Ability to record brain state and apply Hebbian learning
