import random
from PyQt5 import QtCore, QtGui, QtWidgets

class RPSGame:
    def __init__(self, tamagotchi_logic):
        self.tamagotchi_logic = tamagotchi_logic
        self.squid = tamagotchi_logic.squid
        self.choices = ['rock', 'paper', 'scissors']
        self.game_window = None
        self.player_choice = None
        self.squid_choice = None
        self.result = None

    def start_game(self):
        self.create_game_window()
        self.game_window.show()

    def create_game_window(self):
        self.game_window = QtWidgets.QWidget()
        self.game_window.setWindowTitle("Rock, Paper, Scissors")
        layout = QtWidgets.QVBoxLayout()

        # Create buttons for rock, paper, scissors
        for choice in self.choices:
            button = QtWidgets.QPushButton(choice.capitalize())
            button.clicked.connect(lambda _, c=choice: self.play_round(c))
            layout.addWidget(button)

        # Result label
        self.result_label = QtWidgets.QLabel("Make your choice!")
        layout.addWidget(self.result_label)

        # Squid's choice label
        self.squid_choice_label = QtWidgets.QLabel("Squid's choice: ")
        layout.addWidget(self.squid_choice_label)

        self.game_window.setLayout(layout)

    def play_round(self, player_choice):
        self.player_choice = player_choice
        self.squid_choice = self.get_squid_choice()
        self.squid_choice_label.setText(f"Squid's choice: {self.squid_choice.capitalize()}")

        if self.player_choice == self.squid_choice:
            self.result = "It's a tie!"
        elif (
            (self.player_choice == 'rock' and self.squid_choice == 'scissors') or
            (self.player_choice == 'paper' and self.squid_choice == 'rock') or
            (self.player_choice == 'scissors' and self.squid_choice == 'paper')
        ):
            self.result = "You win!"
            self.handle_player_win()
        else:
            self.result = "Squid wins!"
            self.handle_squid_win()

        self.result_label.setText(self.result)
        self.update_squid_stats()

    def get_squid_choice(self):
        # Biased choice based on squid's curiosity
        if self.squid.curiosity > 70:
            # More likely to choose a random option
            return random.choice(self.choices)
        else:
            # More likely to choose a "safe" option (rock)
            return random.choices(self.choices, weights=[0.5, 0.25, 0.25])[0]

    def handle_player_win(self):
        self.squid.happiness = min(100, self.squid.happiness + 5)
        self.squid.curiosity = min(100, self.squid.curiosity + 10)
        self.tamagotchi_logic.points += 5

    def handle_squid_win(self):
        self.squid.happiness = min(100, self.squid.happiness + 10)
        self.squid.satisfaction = min(100, self.squid.satisfaction + 5)
        self.tamagotchi_logic.points += 2

    def update_squid_stats(self):
        self.squid.sleepiness = min(100, self.squid.sleepiness + 5)
        self.squid.hunger = min(100, self.squid.hunger + 3)
        self.tamagotchi_logic.update_statistics()
        self.tamagotchi_logic.user_interface.update_points(self.tamagotchi_logic.points)