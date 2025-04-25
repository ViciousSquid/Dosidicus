What if a Tamagotchi had a neural network and could learn stuff?
# Dosidicus electronicae
### A digital pet with a simple neural network [research project]
* Includes tools for visualising and understanding neural networks, Hebbian learning and Neurogenesis

* requires `PyQt5` and `numpy`

  Check releases: https://github.com/ViciousSquid/Dosidicus/releases/


![image](https://github.com/user-attachments/assets/6102225a-52d6-440c-adfb-a58fd800f1cd)







### Autonomous Behavior:

* The squid moves autonomously, making decisions based on his current state (hunger, sleepiness, etc.).
* Implements a vision cone for food detection, simulating realistic foraging behavior.
* Neural network can make decisions and form associations
* Weights are analysed, tweaked and trained by Hebbian learning algorithm
* Experiences from short-term and long-term memory can influence decision-making
* Squid can create new neurons in response to his environment (Neurogenesis)

I'm trying to document everything!
[https://github.com/ViciousSquid/Dosidicus/tree/main/Docs]

### Needs Management System:

* Tracks various needs like hunger, sleepiness, happiness, and cleanliness.
* Needs change over time and affect the pet's health and behavior.
* The squid can become sick and die if his needs are neglected.

Be aware the squid hates taking medicine and will become depressed and need sleep if made to do so.

### Personality system

* Seven different [personality types](https://github.com/ViciousSquid/Dosidicus/blob/main/Docs/Personalities.md) which influence behaviour

### Decorate and customise!

* Choose decorations to be placed into the environment which the squid will interact with!

### Debug Tools:

* Directly View and edit the squid's internal states 
