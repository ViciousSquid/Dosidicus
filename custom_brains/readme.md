# Custom brains:

Included in this folder:


## "Dense connections" (The Reactive Brain)
This brain is characterized by high volatility and direct emotional feedback loops.

Emotional Interdependence: Almost every core drive is wired directly to another. For example, cleanliness has a strong positive weight toward happiness (0.391), meaning this squid finds significant joy in being clean.

The "Anxiety" Hub: anxiety is extremely "loud" in this brain. hunger significantly drives anxiety (0.333), but interestingly, satisfaction helps suppress it (-0.216). This squid likely feels "hangry" very easily but calms down quickly once it's content.

High-Friction Curiosity: anxiety has a strong inhibitory link to curiosity (-0.309). This squid is likely "Timid"; when it gets nervous, it completely stops exploring.

Cognitive Style: Because there are no hidden layers, this brain doesn't "think" before it acts. It is purely reflexive. If it sees food, that signal hits curiosity (0.27) and happiness (0.232) instantly.


-------------------------------------

## "Feed-Forward-Hidden-Layer" (The Analytical Brain)
This version (v1.1) represents a significant leap in "cognitive" complexity by introducing a hidden processing layer (hidden0_0 through hidden0_3).

The "Filter" Layer: Information doesn't just jump from a feeling to an action. It passes through four "pentagon" neurons first. This allows the squid to balance multiple conflicting needs (like being both hungry and sleepy) before deciding how it feels.

### Structured Influence:

- `Hidden0_0` (The Positivity Driver): This neuron is strongly activated by happiness (0.435) and can_see_food (0.499). It then heavily drives satisfaction and anxiety. It seems to be the "Excitement" processor.

- `Hidden0_3` (The Inhibitor): This neuron is strongly suppressed by sleepiness (-0.469) and can_see_food (-0.259). When it is active, it heavily suppresses satisfaction (-0.459).



- Better Learning Potential: By using hidden layers, this brain can learn non-linear relationships. It can "understand" that seeing food is good when hungry, but maybe less important when it's exhausted.

- Cognitive Style: This is a "contemplative" brain. It’s better at prioritizing and likely shows more stable, less erratic behavior than the "Dense Connections" model.


------------------------

## Plant-Seeker: 
This is a more complex specialized brain. It uses a unique plant_proximity sensor to drive its internal state. It has a very strong link where hunger spikes anxiety (0.348), creating a squid that is highly motivated to find those plants when its stomach is empty.


-------------------

## Change_colour_when_see_food:
 This squid has a very high novelty_object_investigation drive. Interestingly, investigating novelty significantly reduces its hunger (-0.728), suggesting that for this child, curiosity and discovery are almost as fulfilling as eating.

 This squid has an output binding (set in the designer) that makes it change colour when it can see food


--------------------


## Feeling-Blue:

 This structure is a study in depression. It features a fascinating connector_rescue neuron. You’ve wired it so that cleanliness and happiness both have powerful positive influences on sleepiness (0.81 and 0.566 respectively), creating a squid that likely retreats into sleep when it feels good—or perhaps uses sleep as a primary emotional regulator.


------------------


## Grasshopper:

 A high-anxiety model. Its anxiety has a very strong inhibitory effect on curiosity (-0.393), meaning this squid likely "freezes" or stops exploring the moment it feels stressed.


----------------


## Healthy Interests:

 This is one of your most balanced "offspring." It features strong reciprocal links, like satisfaction driving happiness (0.7), creating a stable positive feedback loop that helps the squid maintain a "healthy" mental state.




------------------


## L'insomniaque:

 This squid is physically incapable of rest. We have wired almost every drive—anxiety (-0.95), curiosity (-0.8), and even hunger (-0.5)—to inhibit sleepiness. This is a squid that stays awake as long as it has any internal stimulation.



-----------------


## Bathtub:
 This model seems focused on the joy of hygiene. It has a notable positive weight from cleanliness to happiness (0.296), making it a squid that specifically finds its "zen" in being clean.


---------------


## Minimal: 
This is the "blank slate" child. With very few active connections, it represents the base species before the environment and neurogenesis begin their work. It is the perfect starting point for watching how a brain grows from nothing.



