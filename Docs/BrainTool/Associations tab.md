### Associations tab

This tab shows the learned associations between different neural states of the squid. These associations are formed and upodated regularly through the Hebbian learning process. The strength of an association is determined by how often these states occur together or influence each other. Positive associations mean that as one state increases, the other tends to increase as well. Negative associations (indicated by 'reduced') mean that as one state increases, the other tends to decrease. 
These associations help us understand how the squid's experiences shape its behavior and decision-making processes.

The squid brain always considers the FIFTEEN strongest associations at a time.

```python
def generate_association_summary(self, neuron1, neuron2, weight):
        strength = "strongly" if abs(weight) > 0.8 else "moderately"
        if weight > 0:
            relation = "associated with"
        else:
            relation = "associated with reduced"

        # Correct grammar for specific neurons
        neuron1_text = self.get_neuron_display_name(neuron1)
        neuron2_text = self.get_neuron_display_name(neuron2)

        summaries = {
            "hunger-satisfaction": f"{neuron1_text} is {strength} associated with satisfaction (probably from eating)",
            "satisfaction-hunger": f"Feeling satisfied is {strength} associated with reduced hunger",
            "cleanliness-anxiety": f"{neuron1_text} is {strength} {relation} anxiety",
            "anxiety-cleanliness": f"Feeling anxious is {strength} associated with reduced cleanliness",
            "curiosity-happiness": f"{neuron1_text} is {strength} associated with happiness",
            "happiness-curiosity": f"Being happy is {strength} associated with increased curiosity",
            "hunger-anxiety": f"{neuron1_text} is {strength} associated with increased anxiety",
            "sleepiness-satisfaction": f"{neuron1_text} is {strength} {relation} satisfaction",
            "happiness-cleanliness": f"Being happy is {strength} associated with cleanliness",
        }

        key = f"{neuron1}-{neuron2}"
        if key in summaries:
            return summaries[key]
        else:
            return f"{neuron1_text} is {strength} {relation} {neuron2_text}"
```

Output:

Example associations:

```
Being sleepy is strongly associated with reduced Being anxious

Satisfaction is strongly associated with reduced Being anxious

Being sleepy is strongly associated with Curiosity

Being hungry is moderately associated with Being happy

Being clean is moderately associated with Satisfaction

Being clean is moderately associated with anxiety

Being happy is moderately associated with reduced Being sleepy

Being hungry is moderately associated with satisfaction (probably from eating)

Being hungry is moderately associated with reduced Being clean

Being hungry is moderately associated with Being sleepy

Being clean is moderately associated with Being sleepy

Being hungry is moderately associated with reduced Curiosity

Being happy is moderately associated with cleanliness

Satisfaction is moderately associated with reduced Curiosity

Being happy is moderately associated with reduced Satisfaction
```

This gives an insight into what the squid has learned/is learning via hebbian learning in real time.
