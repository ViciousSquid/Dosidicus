import random
from PyQt5 import QtCore, QtGui, QtWidgets
from src.squid import Personality

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
        # Move squid to bottom left
        self.tamagotchi_logic.move_squid_to_bottom_left(self.create_game_window)

    def create_game_window(self):
        # Pause the simulation
        self.tamagotchi_logic.set_simulation_speed(0)

        # Change squid image
        self.squid.change_to_rps_image()

        self.game_window = QtWidgets.QWidget()
        self.game_window.setWindowTitle("Rock, Paper, Scissors")
        layout = QtWidgets.QVBoxLayout()

        for choice in self.choices:
            button = QtWidgets.QPushButton(choice.capitalize())
            button.clicked.connect(lambda _, c=choice: self.play_round(c))
            layout.addWidget(button)

        self.result_label = QtWidgets.QLabel("Make your choice!")
        layout.addWidget(self.result_label)

        self.squid_choice_label = QtWidgets.QLabel("Squid's choice: ")
        layout.addWidget(self.squid_choice_label)

        self.game_window.setLayout(layout)
        self.game_window.show()

        # Connect the close event
        self.game_window.closeEvent = self.handle_close_event

    def handle_close_event(self, event):
        self.end_game()
        event.accept()

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

        # Check if the "Play Again" button already exists in the layout
        play_again_button = self.find_button("Play Again")
        if play_again_button is None:
            # Add a button to play again
            play_again_button = QtWidgets.QPushButton("Play Again")
            play_again_button.clicked.connect(self.reset_game)
            self.game_window.layout().addWidget(play_again_button)

        # Check if the "End Game" button already exists in the layout
        end_game_button = self.find_button("End Game")
        if end_game_button is None:
            # Add a button to end the game
            end_game_button = QtWidgets.QPushButton("End Game")
            end_game_button.clicked.connect(self.end_game)
            self.game_window.layout().addWidget(end_game_button)

    def find_button(self, text):
        # Helper function to find a button with the given text
        layout = self.game_window.layout()
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, QtWidgets.QPushButton) and widget.text() == text:
                return widget
        return None

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

    def reset_game(self):
        # Remove play again and end game buttons
        layout = self.game_window.layout()
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, QtWidgets.QPushButton) and widget.text() in ["Play Again", "End Game"]:
                layout.removeWidget(widget)
                widget.deleteLater()

        # Reset labels
        self.result_label.setText("Make your choice!")
        self.squid_choice_label.setText("Squid's choice: ")

    def end_game(self):
        if self.game_window:
            self.game_window.close()
            self.game_window = None
        self.squid.restore_normal_image()
        self.tamagotchi_logic.set_simulation_speed(1)  # Resume normal speed
