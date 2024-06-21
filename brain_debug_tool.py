import os
import datetime
import networkx as nx
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QTableWidget, QTableWidgetItem, QCheckBox, QSplitter
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class BrainDebugTool(QWidget):
    def __init__(self, brain):
        super().__init__()
        self.brain = brain
        self.init_ui()

    def init_ui(self):
        # Main layout
        layout = QHBoxLayout()

        # Create matplotlib Figure and FigureCanvas objects
        self.figure = plt.figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.figure)

        # Add the canvas to the layout
        layout.addWidget(self.canvas)

        # Create a table to display the neuron data
        self.table = QTableWidget(10, 2)
        self.table.setHorizontalHeaderLabels(["Name", "Value"])
        self.table.setFixedWidth(300)

        # Add the table to the layout
        layout.addWidget(self.table)

        # Create a checkbox to toggle real-time updating
        self.update_checkbox = QCheckBox("Real-time updating")
        self.update_checkbox.stateChanged.connect(self.toggle_real_time_updating)

        # Create a button to save a snapshot of the neural network status
        #self.save_button = QPushButton("Save snapshot")
        #self.save_button.clicked.connect(self.save_snapshot)

        # Create a button to refresh the data
        #self.refresh_button = QPushButton("Update")
        #self.refresh_button.setStyleSheet("background-color: green")
        #self.refresh_button.clicked.connect(self.update_neuron_data)

        # Create a vertical layout for the buttons and checkbox
        button_layout = QVBoxLayout()
        #button_layout.addWidget(self.update_checkbox)
        #button_layout.addWidget(self.save_button)
        #button_layout.addWidget(self.refresh_button)

        # Add the button layout to the main layout
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setWindowTitle('Brain Debug Tool')
        self.setGeometry(500, 500, 800, 400)

        self.update_visualization()

    def update_visualization(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        G = nx.DiGraph()

        # Add nodes and edges based on the brain's structure
        for neuron_name, neuron_info in self.brain.get_all_neurons_info().items():
            G.add_node(neuron_name)
            for target_name, weight in neuron_info['connections'].items():
                G.add_edge(neuron_name, target_name, label=f'{weight:.2f}')

        # Use spring layout to generate positions for nodes
        pos = nx.spring_layout(G)

        # Draw nodes
        nx.draw_networkx_nodes(G, pos, ax=ax, node_size=500, node_color='lightblue')
        nx.draw_networkx_labels(G, pos, ax=ax, font_size=8)

        # Draw edges
        nx.draw_networkx_edges(G, pos, ax=ax, arrows=True)

        # Add edge labels
        edge_labels = nx.get_edge_attributes(G, 'label')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax, font_size=6)

        ax.set_title("Brain Neural Network")
        ax.axis('off')

        self.canvas.draw()

        # Update the neuron data table
        self.update_neuron_data()

    def update_neuron_data(self):
        # Get the neuron data from the brain
        neuron_data = self.brain.get_all_neurons_info()

        # Update the table with the neuron data
        for i, (neuron_name, neuron_info) in enumerate(neuron_data.items()):
            self.table.setItem(i, 0, QTableWidgetItem(neuron_name))
            self.table.setItem(i, 1, QTableWidgetItem(str(neuron_info["value"])))

        # Indicate when a neuron fires
        for i, neuron_info in enumerate(neuron_data.values()):
            if neuron_info["value"] > 0:
                self.table.item(i, 0).setBackground(Qt.red)
            else:
                self.table.item(i, 0).setBackground(Qt.white)

    def toggle_real_time_updating(self, state):
        if state == Qt.Checked:
            # Start periodic updates of the neuron data
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_neuron_data)
            self.timer.start(100)  # Update every 100 milliseconds
        else:
            # Stop periodic updates of the neuron data
            self.timer.stop()

    def save_snapshot(self):
        # Get the current timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        # Create a directory to store the snapshots
        if not os.path.exists("snapshots"):
            os.makedirs("snapshots")

        # Save the figure as a PNG image with the timestamp in the filename
        self.figure.savefig(f"snapshots/snapshot_{timestamp}.png")

    def closeEvent(self, event):
        event.accept()

# If you want to test the BrainDebugTool independently:
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    from brain import Brain  # Make sure to import your Brain class

    app = QApplication(sys.argv)
    brain = Brain()  # Create a Brain instance
    debug_tool = BrainDebugTool(brain)
    debug_tool.show()
    sys.exit(app.exec_())
