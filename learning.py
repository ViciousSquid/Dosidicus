import random
from PyQt5 import QtCore

class HebbianLearning:
    def __init__(self, squid, brain_window):
        self.squid = squid
        self.brain_window = brain_window
        self.learning_rate = 0.1
        self.threshold = 0.7
        self.learning_data = []  # Store learning data


    def get_learning_data(self):
        return self.learning_data
    
    def export_learning_data(self, file_name):
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Neuron 1", "Neuron 2", "Weight Change"])
            writer.writerows(self.learning_data)

    def learn_from_eating(self):
        # Strengthen connections between hunger neuron and food-seeking or satisfaction neurons
        self.strengthen_connection('hunger', 'satisfaction', self.learning_rate)
        self.strengthen_connection('hunger', 'pursuing_food', self.learning_rate)

    def learn_from_decoration_interaction(self, decoration_category):
        # Strengthen connections between curiosity neuron and neurons associated with the decoration category
        if decoration_category == 'plant':
            self.strengthen_connection('curiosity', 'cleanliness', self.learning_rate)
        elif decoration_category == 'rock':
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate)

    def learn_from_sickness(self):
        # Strengthen connections between sickness neuron and cleanliness or anxiety neurons
        self.strengthen_connection('is_sick', 'cleanliness', self.learning_rate)
        self.strengthen_connection('is_sick', 'anxiety', self.learning_rate)

    def learn_from_curiosity(self):
        # Strengthen connections between curiosity neuron and exploration or memory-related neurons
        self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate)

    def learn_from_anxiety(self):
        # Strengthen connections between anxiety neuron and avoidance or stress-related neurons
        self.strengthen_connection('anxiety', 'is_sick', self.learning_rate)
        self.strengthen_connection('anxiety', 'cleanliness', self.learning_rate)

    def strengthen_connection(self, neuron1, neuron2, learning_rate):
        # Check if the activation levels of both neurons exceed the threshold
        if getattr(self.squid, neuron1) > self.threshold and getattr(self.squid, neuron2) > self.threshold:
            # Strengthen the connection between the neurons
            prev_weight = self.brain_window.brain_widget.weights[(neuron1, neuron2)]
            new_weight = prev_weight + learning_rate
            self.brain_window.brain_widget.weights[(neuron1, neuron2)] = new_weight
            self.brain_window.brain_widget.weights[(neuron2, neuron1)] = new_weight

            # Display the weight change in text format
            timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
            change_text = f"{timestamp} - Weight changed between {neuron1.upper()} and {neuron2.upper()}\n"
            change_text += f"Previous value: <font color='red'>{prev_weight:.4f}</font>\n"
            change_text += f"New value: <font color='green'>{new_weight:.4f}</font>\n\n"
            self.brain_window.weight_changes_text.append(change_text)

            # Store the learning data
            self.learning_data.append((timestamp, neuron1, neuron2, new_weight - prev_weight))

            # Update log window if open
            if self.brain_window.log_window and self.brain_window.log_window.isVisible():
                self.brain_window.log_window.update_log(change_text)

    def update_learning_rate(self, novelty_factor):
        # Adjust the learning rate based on the novelty of the stimuli
        self.learning_rate = 0.1 * novelty_factor

    def update_weights(self):
        # Apply selective reinforcement and temporal association rules when updating weights
        # Implement the logic based on your specific requirements
        pass