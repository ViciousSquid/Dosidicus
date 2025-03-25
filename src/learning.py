import random
from PyQt5 import QtCore
import csv

class HebbianLearning:
    def __init__(self, squid, brain_window):
        self.squid = squid
        self.brain_window = brain_window
        self.learning_rate = 0.1
        self.threshold = 0.7
        self.learning_data = []  # Store learning data
        self.goal_weights = {
            'organize_decorations': 0.5,
            'interact_with_rocks': 0.7,
            'move_to_plants': 0.4
        }

    def get_learning_data(self):
        return self.learning_data
    
    def export_learning_data(self, file_name):
        with open(file_name, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Neuron 1", "Neuron 2", "Weight Change", "Goal Type"])
            writer.writerows(self.learning_data)

    def learn_from_eating(self):
        self.strengthen_connection('hunger', 'satisfaction', self.learning_rate)
        self.strengthen_connection('hunger', 'pursuing_food', self.learning_rate)

    def learn_from_decoration_interaction(self, decoration_category):
        if decoration_category == 'plant':
            self.strengthen_connection('curiosity', 'cleanliness', self.learning_rate)
        elif decoration_category == 'rock':
            self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 1.5)
            self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
            self.strengthen_connection('satisfaction', 'happiness', self.learning_rate * 0.5)

    def learn_from_organization(self):
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate * 2)
        self.strengthen_connection('cleanliness', 'satisfaction', self.learning_rate)
        self.strengthen_connection('organization', 'completion', self.learning_rate * 1.2)

    def learn_from_sickness(self):
        self.strengthen_connection('is_sick', 'cleanliness', self.learning_rate)
        self.strengthen_connection('is_sick', 'anxiety', self.learning_rate)

    def learn_from_curiosity(self):
        self.strengthen_connection('curiosity', 'happiness', self.learning_rate)
        self.strengthen_connection('curiosity', 'satisfaction', self.learning_rate)
        self.strengthen_connection('curiosity', 'exploration', self.learning_rate * 1.3)

    def learn_from_anxiety(self):
        self.strengthen_connection('anxiety', 'is_sick', self.learning_rate)
        self.strengthen_connection('anxiety', 'cleanliness', self.learning_rate)

    def strengthen_connection(self, neuron1, neuron2, learning_rate):
        if getattr(self.squid, neuron1) > self.threshold and getattr(self.squid, neuron2) > self.threshold:
            prev_weight = self.brain_window.brain_widget.weights[(neuron1, neuron2)]
            new_weight = prev_weight + learning_rate
            self.brain_window.brain_widget.weights[(neuron1, neuron2)] = new_weight
            self.brain_window.brain_widget.weights[(neuron2, neuron1)] = new_weight

            timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
            change_text = f"{timestamp} - Weight changed between {neuron1.upper()} and {neuron2.upper()}\n"
            change_text += f"Previous value: <font color='red'>{prev_weight:.4f}</font>\n"
            change_text += f"New value: <font color='green'>{new_weight:.4f}</font>\n\n"
            self.brain_window.weight_changes_text.append(change_text)

            self.learning_data.append((timestamp, neuron1, neuron2, new_weight - prev_weight, "GOAL" if (neuron1, neuron2) in self.goal_weights else "BASIC"))

            if self.brain_window.log_window and self.brain_window.log_window.isVisible():
                self.brain_window.log_window.update_log(change_text)

    def update_learning_rate(self, novelty_factor):
        self.learning_rate = 0.1 * novelty_factor
        for goal, weight in self.goal_weights.items():
            self.goal_weights[goal] = weight * novelty_factor

    def update_weights(self):
        # Apply goal-oriented reinforcement
        if self.squid.status == "organizing decorations":
            self.learn_from_organization()
        elif self.squid.status == "interacting with rocks":
            self.learn_from_decoration_interaction('rock')
        elif self.squid.status == "moving to plant":
            self.learn_from_decoration_interaction('plant')