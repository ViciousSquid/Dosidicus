Personality affects squid needs and behaviour. A random personality is assigned every time a new squid is born, and could be thought of as a sort of "difficulty level" with 'Lazy' being the easiest and 'Stubborn' being hardest.

There are seven different squid personalities that affect their needs and how they behave: 

* `Timid`: Higher chance of becoming anxious 
* `Adventurous`: Increased curiosity and exploration 
* `Lazy`: Slower movement and energy consumption 
* `Energetic`: Faster movement and higher activity levels 
* `Introvert`: Prefers solitude and quiet environments 
* `Greedy`: More focused on food and resources
* `Stubborn`: Fussy and difficult 

One of these is randomly chosen at launch

### How personality reaches behaviour

Since v5.0, personality is **innate synaptic weight**, not a rule applied to
decisions. A timid squid is one born with a stronger startle reflex: the
tilt in `brain_constants.INNATE_PERSONALITY_BIAS` is applied once, to the
squid's innate synapses, the moment its personality becomes known.

It used to be a per-personality multiplier table the decision engine applied to
finished behaviour weights. That put personality *outside* the network
entirely: nothing the squid experienced could ever change it, and it appeared
nowhere in the brain the player was looking at.

Because it is now ordinary weight, ordinary learning can reach it — so a timid
squid that is never frightened can genuinely grow out of it, and you can see
that happen in the [Knowledge tab](../brain-tool/Knowledge-Tab.md).

A personality type can be forced at launch using the `-p` flag followed by the personality name above (example: `main.py -p lazy`) 

Each personality type presents unique challenges and requirements for the player to manage. Understanding and accommodating the specific needs and behaviors of each personality type is crucial for the player's success in caring for the squid and maintaining its well-being.

Here's a description of the different personality types and their corresponding behaviors in the game:

### `Timid` Personality:

* Tendency to become anxious, especially when not near plants.
* Moves slowly and prefers quiet, solitary environments.
* Curiosity level is lower than other personalities.
* Has a higher chance of becoming startled by decorations or other environmental factors.


### `Adventurous` Personality:

* Curious and exploratory, with a higher chance of entering the "curious" state.
* Moves faster and is more active compared to other personalities.
* Curiosity level is higher, leading to increased exploration and interaction with the environment.


### `Lazy` Personality:

* Moves and consumes energy at a slower pace.
* Takes more time to fulfill their needs, such as eating and sleeping.
* May be less responsive to environmental changes or stimuli.


### `Energetic` Personality:

* Moves and acts at a faster pace.
* Tends to have higher activity levels and may expend energy more quickly.
* May be more prone to restlessness or agitation.


### `Introvert` Personality:

* Prefers solitary environments and is content when alone.
* May become unhappy or anxious when forced to interact with the environment or decorations.
* Curiosity level is balanced, not too high or too low.


### `Greedy` Personality:

* Highly focused on food and resources, becoming anxious and hungry when those needs are not met.
* Curiosity level may be higher, leading to more exploration, but this is primarily driven by the desire for food.
* May become more aggressive or assertive in obtaining food or resources.


### `Stubborn` Personality:

* Only eats its favorite food (sushi), often refusing to consume any other type of food (cheese).
* Displays the message "Fussy squid does not like that type of food!" when presented with non-favorite food.
* Has a chance of refusing to sleep when its sleepiness is high, instead moving randomly.
* Moves slowly and stubbornly when not actively searching for its favorite food.
* Prioritizes sushi over cheese in its vision cone when searching for food.
