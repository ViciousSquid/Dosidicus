`decision_engine.py` Technical Manual
================================

Overview
--------

The Decision Engine is responsible for determining the Squid's behavior in a given moment, based on its internal state, environmental factors, neural network state, and active memories. The `make_decision` method implements a hybrid approach that combines neural network-based decision making with direct state checking for critical conditions.

Decision Making Process
-----------------------

### 1\. State Collection

The decision process begins by collecting a comprehensive view of the Squid's current state:
```python
current\_state = {
    "hunger": self.squid.hunger,
    "happiness": self.squid.happiness,
    "cleanliness": self.squid.cleanliness,
    "sleepiness": self.squid.sleepiness,
    "satisfaction": self.squid.satisfaction,
    "anxiety": self.squid.anxiety,
    "curiosity": self.squid.curiosity,
    "is\_sick": self.squid.is\_sick,
    "is\_sleeping": self.squid.is\_sleeping,
    "has\_food\_visible": bool(self.squid.get\_visible\_food()),
    "carrying\_rock": self.squid.carrying\_rock,
    "carrying\_poop": self.squid.carrying\_poop,
    "rock\_throw\_cooldown": getattr(self.squid, 'rock\_throw\_cooldown', 0),
    "poop\_throw\_cooldown": getattr(self.squid, 'poop\_throw\_cooldown', 0)
}
```
### 2\. Neural Network State Acquisition

The engine then retrieves the current state of the Squid's brain network, which provides an opportunity for emergent behavior:

brain\_state = self.squid.tamagotchi\_logic.squid\_brain\_window.brain\_widget.state

### 3\. Memory Influence

Active memories are collected and used to influence the current state, providing a form of short-term historical context:
```
active\_memories = self.squid.memory\_manager.get\_active\_memories\_data(3)
memory\_influence = {}
for memory in active\_memories:
    if isinstance(memory.get('raw\_value'), dict):
        for key, value in memory\['raw\_value'\].items():
            if key in memory\_influence:
                memory\_influence\[key\] += value \* 0.5
            else:
                memory\_influence\[key\] = value \* 0.5
```
These memory influences are then applied to the current state, modifying values like hunger, happiness, etc.:

for key, value in memory\_influence.items():
    if key in current\_state and isinstance(current\_state\[key\], (int, float)):
        current\_state\[key\] = min(100, max(0, current\_state\[key\] + value))

### 4\. Critical State Overrides

The engine checks for critical states that should override neural decisions:

#### Exhaustion Override
```
if self.squid.sleepiness >= 95:
    self.squid.go\_to\_sleep()
    return "exhausted"
```
#### Sleep State
```
if self.squid.is\_sleeping:
    if self.squid.sleepiness > 90:
        return "sleeping deeply"
    else:
        return "sleeping peacefully"
```
#### Emotional State Overrides

Emotional overrides for anxiety, curiosity, happiness, etc. take precedence over other decisions:
```
if self.squid.anxiety > 80:
    return "extremely anxious"
elif self.squid.anxiety > 60:
    return "anxious"
elif self.squid.anxiety > 40:
    return "nervous"
    
if self.squid.curiosity > 80:
    return "extremely curious"
```

### 5\. Neural Network Decision Weighting

If no critical overrides apply, the engine calculates weights for possible actions based on the neural state:
```
decision\_weights = {
    "exploring": brain\_state.get("curiosity", 50) \* 0.8 \* (1 - (brain\_state.get("anxiety", 50) / 100)),
    "eating": brain\_state.get("hunger", 50) \* 1.2 if self.squid.get\_visible\_food() else 0,
    "approaching\_rock": brain\_state.get("curiosity", 50) \* 0.7 if not self.squid.carrying\_rock else 0,
    "throwing\_rock": brain\_state.get("satisfaction", 50) \* 0.7 if self.squid.carrying\_rock else 0,
    "approaching\_poop": brain\_state.get("curiosity", 50) \* 0.7 if not self.squid.carrying\_poop and len(self.squid.tamagotchi\_logic.poop\_items) > 0 else 0,
    "throwing\_poop": brain\_state.get("satisfaction", 50) \* 0.7 if self.squid.carrying\_poop else 0,
    "avoiding\_threat": brain\_state.get("anxiety", 50) \* 0.9,
    "organizing": brain\_state.get("satisfaction", 50) \* 0.5
}
```
### 6\. Personality Modification

The engine applies personality-specific modifiers to the decision weights:
```
if self.squid.personality == Personality.TIMID:
    decision\_weights\["avoiding\_threat"\] \*= 1.5
    decision\_weights\["approaching\_rock"\] \*= 0.7
    decision\_weights\["approaching\_poop"\] \*= 0.7
elif self.squid.personality == Personality.ADVENTUROUS:
    decision\_weights\["exploring"\] \*= 1.3
    decision\_weights\["approaching\_rock"\] \*= 1.2
    decision\_weights\["approaching\_poop"\] \*= 1.2
elif self.squid.personality == Personality.GREEDY:
    decision\_weights\["eating"\] \*= 1.5
```
### 7\. Randomization

To create more unpredictable behavior, randomness is added to each decision weight:
```
for key in decision\_weights:
    decision\_weights\[key\] \*= random.uniform(0.85, 1.15)
```
### 8\. Decision Selection

The engine selects the highest weighted decision:

`best\_decision = max(decision\_weights, key=decision\_weights.get)`

### 9\. Action Implementation

Based on the selected decision, specific actions are implemented:

#### Eating
```
if best\_decision == "eating" and self.squid.get\_visible\_food():
    closest\_food = min(self.squid.get\_visible\_food(), 
                    key=lambda f: self.squid.distance\_to(f\[0\], f\[1\]))
    self.squid.move\_towards(closest\_food\[0\], closest\_food\[1\])
    
    # Food-specific statuses based on hunger and distance
    food\_distance = self.squid.distance\_to(closest\_food\[0\], closest\_food\[1\])
    if food\_distance > 100:
        return "eyeing food"
    elif food\_distance > 50:
        if self.squid.hunger > 70:
            return "approaching food eagerly"
        else:
            return "cautiously approaching food"
    else:
        return "moving toward food"
```
#### Rock Interaction
```
elif best\_decision == "approaching\_rock" and not self.squid.carrying\_rock:
    nearby\_rocks = \[d for d in self.squid.tamagotchi\_logic.get\_nearby\_decorations(
        self.squid.squid\_x, self.squid.squid\_y, 150)
        if getattr(d, 'can\_be\_picked\_up', False)\]
    if nearby\_rocks:
        self.squid.current\_rock\_target = random.choice(nearby\_rocks)
        
        rock\_distance = self.squid.distance\_to(
            self.squid.current\_rock\_target.pos().x(), 
            self.squid.current\_rock\_target.pos().y())
            
        if rock\_distance > 70:
            return "interested in rock"
        else:
            return "examining rock curiously"
```
#### Rock Throwing
```
elif best\_decision == "throwing\_rock" and self.squid.carrying\_rock:
    direction = random.choice(\["left", "right"\])
    if self.squid.throw\_rock(direction):
        if random.random() < 0.3:
            return "tossing rock around"
        else:
            return "playfully throwing rock"
```
#### Poop Interaction
```
elif best\_decision == "approaching\_poop" and not self.squid.carrying\_poop:
    nearby\_poops = \[d for d in self.squid.tamagotchi\_logic.poop\_items 
                    if self.squid.distance\_to(d.pos().x(), d.pos().y()) < 150\]
    if nearby\_poops:
        self.squid.current\_poop\_target = random.choice(nearby\_poops)
        return "approaching poop"
```
#### Poop Throwing
```
elif best\_decision == "throwing\_poop" and self.squid.carrying\_poop:
    direction = random.choice(\["left", "right"\])
    if self.squid.throw\_poop(direction):
        return "throwing poop"
```
#### Decoration Organization
```
elif best\_decision == "organizing" and self.squid.should\_organize\_decorations():
    action = self.squid.organize\_decorations()
    if action == "hoarding":
        if self.squid.personality == Personality.GREEDY:
            return "hoarding items"
        else:
            return "organizing decorations"
    elif action == "approaching\_decoration":
        return "redecorating"
    else:
        return "arranging environment"
```
#### Threat Avoidance
```
elif best\_decision == "avoiding\_threat" and self.squid.anxiety > 70:
    # Move away from potential threats
    if len(self.squid.tamagotchi\_logic.poop\_items) > 0:
        self.squid.move\_erratically()
        return "feeling uncomfortable"
    if self.squid.personality == Personality.TIMID:
        if self.squid.is\_near\_plant():
            return "hiding behind plant"
        else:
            return "nervously watching"
    return "hiding"
```
### 10\. Default Exploration

If no specific action is chosen, the Squid defaults to exploration with personality-specific variations:
```
\# Create more descriptive exploration states
exploration\_options = \[\]

# Add personality-specific exploration options
if self.squid.personality == Personality.TIMID:
    exploration\_options.extend(\["cautiously exploring", "nervously watching"\])
elif self.squid.personality == Personality.ADVENTUROUS:
    exploration\_options.extend(\["boldly exploring", "seeking adventure", "investigating bravely"\])


# Select a random exploration style
exploration\_style = random.choice(exploration\_options)

if exploration\_style in \["resting comfortably", "conserving energy", "lounging"\]:
    self.squid.move\_slowly()
elif exploration\_style in \["zooming around", "buzzing with energy", "restlessly swimming"\]:
    self.squid.move\_erratically()
else:
    self.squid.move\_randomly()

return exploration\_style
```
Key Neural Decision Factors
---------------------------

### Primary Neural Nodes

The Decision Engine primarily uses these neural nodes for decision weighting:

*   **curiosity**: Drives exploration and interaction with objects
*   **anxiety**: Inhibits exploration and increases avoidance behaviors
*   **satisfaction**: Influences decoration interaction and organization
*   **hunger**: Drives food-seeking behavior

### Key Neural Connections

Important neural connections that affect decisions:

*   **curiosity → satisfaction**: Reinforced by successful exploration
*   **anxiety → curiosity**: Inhibitory connection (high anxiety reduces curiosity)
*   **satisfaction → happiness**: Positive feedback loop
*   **hunger → satisfaction**: Reinforced by successful feeding

### Learning Influence

The Hebbian learning system modifies these connections over time based on experiences:

*   Successful feeding strengthens the connection between hunger and satisfaction
*   Decoration interaction strengthens connections based on personality
*   Rock/poop throwing modifies satisfaction and happiness connections

Personality Impact on Decision Making
-------------------------------------

Each personality type influences decisions in specific ways:

### TIMID

*   50% stronger threat avoidance behavior
*   30% reduced rock/poop interaction
*   Preference for "cautiously exploring" and "nervously watching" states
*   Will hide behind plants when anxious

### ADVENTUROUS

*   30% increased exploration behavior
*   20% increased object interaction
*   Preference for "boldly exploring" and "seeking adventure" states

### GREEDY

*   50% increased food-seeking behavior
*   Tendency to "hoard items" when organizing
*   Preference for "searching for treasures" state

### STUBBORN

*   Resistant to new interactions
*   Preference for "stubbornly patrolling" state

Memory Influence on Decisions
-----------------------------

Short-term memories affect the Squid's current state and thus its decisions:

*   Positive food memories can temporarily reduce hunger sensation
*   Negative memories (like being startled) can increase anxiety
*   Recent decoration interactions affect satisfaction

Debugging Decision Making
-------------------------

To debug decision making, examine:

1.  The current brain state retrieved from `brain_window.brain_widget.state`
2.  The calculated `decision_weights` before and after personality modifications
3.  The active memories influencing the current state
4.  The final `best_decision` value and associated action

Extending the Decision Engine
-----------------------------

To add new decision types:

1.  Add a new key to the `decision_weights` dictionary with appropriate weighting formula
2.  Add personality-specific modifiers if needed
3.  Implement the action handling in the decision selection section
4.  Consider adding appropriate neural connections to the brain model
