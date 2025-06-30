The following launch args are available


* `-d` or `--debug` - Debug (logs the console to console.txt, plugins and other logic will create their own logs too)
* `-nc` or `--neurocooldown` [VALUE]- Neuro cooldown (cooldown for neurogenesis [in seconds] )
* `-p` or `--personality` [VALUE] - Personality (forces generation of a specific personality)


 (example: `python main.py -d -p ADVENTUROUS` - Force creation of ADVENTUROUS personality type and also enable debugging

-------------------------

NOTE: It is not advisable to change neurocooldown (-nc) from the default (180 seconds) 
Too low a value will cause too rapid creation of new neurons leading to neural network instability and collapse. 
