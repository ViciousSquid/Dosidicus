
![image](https://github.com/user-attachments/assets/a6b74e77-98db-4e97-b03e-a067b0814c77)

 <p> The <strong>Decisions Tab</strong> provides a fascinating, step-by-step visualization of your squid's thought process. It breaks down how the squid goes from assessing his environment and internal needs to making a final, actionable decision. This view is updated every time the squid makes a new choice. </p> 

Decisions reflected here are made by the [Decision Engine](../engine/Decision-Engine.md) which is driven by the [Neural Network](../neural-network/Technical-Overview.md)



<h4>Interface Elements</h4> <ul> <li> <strong>Thought Process Path:</strong> A vertical flow-chart that visualizes the decision-making pipeline. <ol> <li><strong>📡 Sensing the World:</strong> This step shows the raw inputs the squid is currently processing. This includes his internal stats (hunger, happiness, etc.) and any objects he can see in his environment (food, poop, etc.).</li> 
<li><strong>⚖️ Calculating Base Urges:</strong> Based on the inputs, the tool calculates the initial "weight" or "urge" for each possible action. The action with the highest initial score is listed as the strongest urge.</li> <li><strong>🎭 Applying Personality & Memories:</strong> The base urges are then modified by the squid's personality and recent memories. For example, a "Timid" squid might have his urge to "explore" reduced, while a "Greedy" squid will have his urge to "eat" increased. This step shows how much each score was adjusted.</li> <li><strong>✅ Making the Final Decision:</strong> This step shows the final, adjusted scores for all possible actions. The action with the highest final score is the one the squid chooses.</li> </ol> </li> <li> <strong>Final Action Bar:</strong> A fixed bar at the bottom of the tab that prominently displays the squid's final chosen action (e.g., "Eat", "Sleep", "Explore") and his calculated confidence in that decision. </li> </ul> <hr>