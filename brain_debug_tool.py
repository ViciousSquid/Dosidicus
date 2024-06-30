import os
import datetime
import networkx as nx
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QTableWidget, QTableWidgetItem, QCheckBox, QSplitter, QLabel, QLineEdit, QComboBox, QMessageBox, QMenu
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QContextMenuEvent
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

class BrainDebugTool(QWidget):
    def __init__(self, brain):
        super().__init__()
        self.brain = brain
        self.init_ui()

    def init_ui(self):
        # Create a splitter widget
        splitter = QSplitter(Qt.Horizontal)

        # Create matplotlib Figure and FigureCanvas objects for the left section
        self.figure = plt.figure(figsize=(6, 8))
        self.canvas = FigureCanvas(self.figure)
        splitter.addWidget(self.canvas)

        # Create a widget for the right section
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # Create a table to display the neuron data for the right section
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Layer", "Name", "Value", "Connections"])
        self.table.itemSelectionChanged.connect(self.show_neuron_details)
        # Set the column widths manually
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 400)
        right_layout.addWidget(self.table)

        right_widget.setLayout(right_layout)
        splitter.addWidget(right_widget)

        # Create a new layout for the bottom section
        bottom_layout = QHBoxLayout()

        # Add controls for editing the network for the bottom section
        edit_layout = QHBoxLayout()
        self.neuron_combo = QComboBox()
        self.weight_input = QLineEdit()
        self.edit_button = QPushButton("Edit Weight")
        self.edit_button.clicked.connect(self.edit_weight)
        edit_layout.addWidget(self.neuron_combo)
        edit_layout.addWidget(self.weight_input)
        edit_layout.addWidget(self.edit_button)
        bottom_layout.addLayout(edit_layout)

        # Add controls for adding/removing neurons for the bottom section
        add_remove_layout = QHBoxLayout()
        self.new_neuron_name = QLineEdit()
        self.new_neuron_layer = QComboBox()
        self.new_neuron_layer.addItems(['input', 'hidden', 'output'])
        self.add_neuron_button = QPushButton("Add Neuron")
        self.add_neuron_button.clicked.connect(self.add_neuron)
        self.remove_neuron_button = QPushButton("Remove Neuron")
        self.remove_neuron_button.clicked.connect(self.remove_neuron)
        add_remove_layout.addWidget(self.new_neuron_name)
        add_remove_layout.addWidget(self.new_neuron_layer)
        add_remove_layout.addWidget(self.add_neuron_button)
        add_remove_layout.addWidget(self.remove_neuron_button)
        bottom_layout.addLayout(add_remove_layout)

        # Add a checkbox to toggle real-time updating for the bottom section
        self.update_checkbox = QCheckBox("Real-time updating")
        self.update_checkbox.stateChanged.connect(self.toggle_real_time_updating)
        bottom_layout.addWidget(self.update_checkbox)

        # Create a button to refresh the data for the bottom section
        self.refresh_button = QPushButton("Update")
        self.refresh_button.setStyleSheet("background-color: #8AFF8A")
        self.refresh_button.clicked.connect(self.update_visualization)
        bottom_layout.addWidget(self.refresh_button)

        # Create a main layout for the window
        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_layout.addLayout(bottom_layout)

        self.setLayout(main_layout)

        # Set the sizes of the left and right widgets in the splitter
        splitter.setSizes([300, 700])

        self.setWindowTitle('Brain Debug Tool')
        self.setGeometry(100, 100, 1200, 500)

        self.update_visualization()

    def update_visualization(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        G = nx.DiGraph()

        pos = {}
        colors = []
        layers = ['input', 'hidden', 'output']
        layer_counts = [len(self.brain.neurons[layer]) for layer in layers]
        max_count = max(layer_counts) if any(layer_counts) else 1  # Avoid division by zero

        for i, layer in enumerate(layers):
            neurons = self.brain.neurons[layer]
            for j, (name, neuron) in enumerate(neurons.items()):
                G.add_node(name)
                pos[name] = (i, (j - len(neurons)/2) / max_count if max_count > 0 else 0)
                if layer == 'hidden':
                    colors.append('purple')  # Use purple for hidden neurons
                else:
                    colors.append(['red', 'green', 'blue'][i])  # Use red, green, blue for input and output neurons

                if layer != 'output':
                    next_layer = layers[i+1]
                    for target, weight in neuron.connections.items():
                        if target in self.brain.neurons[next_layer]:
                            G.add_edge(name, target, weight=weight)

        if G.number_of_nodes() > 0:  # Only draw if there are nodes
            nx.draw_networkx_nodes(G, pos, ax=ax, node_size=1000, node_color=colors)
            nx.draw_networkx_labels(G, pos, ax=ax, font_size=8)
            edges = nx.draw_networkx_edges(G, pos, ax=ax, arrows=True, edge_color='gray')

            edge_labels = nx.get_edge_attributes(G, 'weight')
            edge_labels = {k: f'{v:.2f}' for k, v in edge_labels.items()}
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, ax=ax, font_size=6)

        ax.set_title("Brain Neurons")
        ax.axis('off')

        self.canvas.draw()

        self.update_table()
        self.update_neuron_combo()

    def update_table(self):
        neuron_data = self.brain.get_all_neurons_info()
        self.table.setRowCount(sum(len(neurons) for neurons in neuron_data.values()))
        row = 0
        for layer, neurons in neuron_data.items():
            for name, info in neurons.items():
                self.table.setItem(row, 0, QTableWidgetItem(layer))
                self.table.setItem(row, 1, QTableWidgetItem(name))
                self.table.setItem(row, 2, QTableWidgetItem(f"{info['value']:.4f}"))
                connections = ', '.join([f"{target}: {weight:.2f}" for target, weight in info['connections'].items()])
                self.table.setItem(row, 3, QTableWidgetItem(connections))
                row += 1

        # Set the context menu policy of the table widget to CustomContextMenu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        # Connect the customContextMenuRequested signal of the table widget to the show_neuron_menu method
        self.table.customContextMenuRequested.connect(self.show_neuron_menu)

    def show_neuron_menu(self, position):
        # Get the index of the selected item in the table widget
        index = self.table.indexAt(position)
        if index.isValid():
            # Get the name of the selected neuron
            name = self.table.item(index.row(), 1).text()
            # Create a context menu with an option to view detailed information about the neuron
            menu = QMenu()
            action = menu.addAction("View detailed information")
            # Connect the triggered signal of the action to the show_neuron_details method
            action.triggered.connect(lambda: self.show_neuron_details(name))
            # Show the context menu at the position of the right-click event
            menu.exec_(self.table.viewport().mapToGlobal(position))

    def show_neuron_details(self):
        # Get the selected item in the table widget
        selected_item = self.table.selectedItems()
        if selected_item:
            # Get the name of the selected neuron
            name = selected_item[1].text()
            # Get the detailed information about the neuron
            info = self.brain.get_neuron_info(name)
            # Create a new window to display the detailed information
            window = QWidget()
            layout = QVBoxLayout()
            layout.addWidget(QLabel(f"Name: {name}"))
            layout.addWidget(QLabel(f"Value: {info['value']:.4f}"))
            layout.addWidget(QLabel("Connections:"))
            for target, weight in info['connections'].items():
                layout.addWidget(QLabel(f"  {target}: {weight:.2f}"))
            window.setLayout(layout)
            window.setWindowTitle(f"Detailed information about {name}")
            window.show()

    def update_neuron_combo(self):
        self.neuron_combo.clear()
        for layer in ['input', 'hidden']:
            for name in self.brain.neurons[layer]:
                self.neuron_combo.addItem(f"{layer}: {name}")

    def toggle_real_time_updating(self, state):
        if state == Qt.Checked:
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_visualization)
            self.timer.start(1000)  # Update every second
        else:
            self.timer.stop()

    def edit_weight(self):
        selected = self.neuron_combo.currentText()
        if selected:
            layer, name = selected.split(': ')
            weight_text = self.weight_input.text()
            if weight_text:
                new_weight = float(weight_text)
                # Implement the logic to edit the weight
                # You'll need to add a method in the Brain class to handle this
                self.update_visualization()
            else:
                # Display a message box with the text "Field cannot be empty!"
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Warning)
                msg.setText("Field cannot be empty!")
                msg.setWindowTitle("Error")
                msg.exec_()

    def add_neuron(self):
        name = self.new_neuron_name.text()
        layer = self.new_neuron_layer.currentText()
        if self.brain.add_neuron(name, layer):
            self.update_visualization()

    def remove_neuron(self):
        selected = self.neuron_combo.currentText()
        if selected:
            layer, name = selected.split(': ')
            if self.brain.remove_neuron(name, layer):
                self.update_visualization()

    def closeEvent(self, event):
        event.accept()
