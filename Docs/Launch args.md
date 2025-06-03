The following launch args are available

* `-c` - Clean start (skips hatching animations, laoding of saved games, tutorials and starts the simulation directly)
* `-d` - Debug (logs the console to console.txt, plugins and other logic will create their own logs too)
* `-nc` - Neuro cooldown (cooldown for neurogenesis [in seconds] )
* `-p` - Personality (forces generation of a specific personality)


* (example: `python main.py -c -d` - clean start with debugging ) Ideal for plugin development and testing
* (example: `python main.py -p ADVENTUROUS` - Force creation of ADVENTUROUS personality type

NOTE: It is not advisable to change neurocooldown (-nc) from the default (180 seconds) 
Too low a value will cause too rapid creation of new neurons leading to neural network instability and collapse. 
