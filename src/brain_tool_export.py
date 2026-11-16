"""Exporting what the Brain Tool shows: weights, learning data and decision
logs, as text, CSV, JSON and HTML.
"""
import csv
import time
from PyQt5 import QtCore, QtWidgets


class BrainExportMixin:
    """Part of SquidBrainWindow (see brain_tool.py); not used on its own."""

    def export_learning_tab_contents(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Learning Tab Contents", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write("Learning Data Table:\n")
                for row in range(self.learning_data_table.rowCount()):
                    row_data = []
                    for col in range(self.learning_data_table.columnCount()):
                        item = self.learning_data_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    file.write("\t".join(row_data) + "\n")

                file.write("\nWeight Changes Text:\n")
                file.write(self.weight_changes_text.toPlainText())

            QtWidgets.QMessageBox.information(self, "Export Successful", f"Learning tab contents exported to {file_name}")

    def export_associations(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Associations", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write(self.associations_text.toPlainText())
            QtWidgets.QMessageBox.information(self, "Export Successful", f"Associations exported to {file_name}")

    def export_brain_weights_text(self):
        """Return a human-readable block with every connection."""
        lines = ["# Squid brain weights – saved {}\n".format(
                    QtCore.QDateTime.currentDateTime().toString())]
        for (src, dst), w in sorted(self.brain_widget.weights.items(),
                                    key=lambda kv: abs(kv[1]), reverse=True):
            lines.append(f"{src:20} → {dst:20}  {w:+.4f}")
        return "\n".join(lines)

    def export_hebbian_json(self):
        """Return a JSON-serialisable list with the *entire* learning log."""
        # learning_data is already a list of lists:
        # [timestamp, n1, n2, Δw, direction]
        return {
            "saved_at": time.time(),
            "learning_interval_ms": self.config.hebbian.get('learning_interval', 30000),
            "history": getattr(self.brain_widget, 'learning_data', [])
        }

    def export_decision_engine_json(self):
        """Ask the DecisionEngine to serialise itself."""
        squid = getattr(self.tamagotchi_logic, 'squid', None)
        engine = getattr(squid, '_decision_engine', None) if squid else None
        if engine is None:
            return {}
        # Minimal example – extend as needed
        return {
            "epsilon": getattr(engine, 'epsilon', 0.1),
            "learning_rate": getattr(engine, 'learning_rate', 0.05),
            "q_table": getattr(engine, 'q_table', {}).copy()
        }

    def export_learning_data(self):
        """Export learning data with all available information"""
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Learning Data", "", "HTML Files (*.html);;CSV Files (*.csv);;Text Files (*.txt)")
        
        if not file_name:
            return
            
        try:
            if file_name.endswith('.html'):
                self.export_learning_data_html(file_name)
            elif file_name.endswith('.csv'):
                self.export_learning_data_csv(file_name)
            else:
                self.export_learning_data_text(file_name)
                
            # Show success message
            QtWidgets.QMessageBox.information(
                self, "Export Successful", f"Learning data exported to {file_name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Export Error", f"Error exporting data: {str(e)}")

    def export_learning_data_html(self, file_name):
        """Export learning data as rich HTML report"""
        with open(file_name, 'w') as f:
            # Start HTML document
            f.write("""<!DOCTYPE html>
            <html>
            <head>
                <title>Squid Brain Learning Data</title>
                <style>
                    body { font-family: Fio UI; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }
                    h1, h2, h3 { color: #2c3e50; }
                    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                    th { background-color: #f2f2f2; }
                    tr:hover { background-color: #f5f5f5; }
                    .positive { color: green; }
                    .negative { color: red; }
                    .stats-box { background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin: 15px 0; }
                    .stats-title { font-weight: bold; font-size: 18px; margin-bottom: 10px; }
                    .heatmap { overflow-x: auto; }
                </style>
            </head>
            <body>
                <h1>Squid Brain Learning Data</h1>
                <p>Export time: """ + time.strftime("%Y-%m-%d %H:%M:%S") + """</p>
            """)
            
            # Learning parameters
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Learning Parameters</div>
                    <table>
                        <tr>
                            <th>Parameter</th>
                            <th>Value</th>
                        </tr>
            """)
            
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    if param == 'learning_interval':
                        value = f"{value/1000} seconds"
                    f.write(f"<tr><td>{param}</td><td>{value}</td></tr>")
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Neuron information
            neurons = sorted(self.brain_widget.neuron_positions.keys())
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Neurons</div>
                    <p>Total neurons: """ + str(len(neurons)) + """</p>
                    <table>
                        <tr>
                            <th>Neuron</th>
                            <th>Position</th>
                            <th>Type</th>
                            <th>Current Value</th>
                        </tr>
            """)
            
            for neuron in neurons:
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                f.write(f"""
                    <tr>
                        <td>{neuron}</td>
                        <td>({position[0]:.1f}, {position[1]:.1f})</td>
                        <td>{neuron_type}</td>
                        <td>{value:.1f}</td>
                    </tr>
                """)
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Connection weights
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Connection Weights</div>
                    <p>Total connections: """ + str(len(self.brain_widget.weights)) + """</p>
                    <table>
                        <tr>
                            <th>Source</th>
                            <th>Target</th>
                            <th>Weight</th>
                        </tr>
            """)
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                weight_class = "positive" if weight > 0 else "negative"
                f.write(f"""
                    <tr>
                        <td>{source}</td>
                        <td>{target}</td>
                        <td class="{weight_class}">{weight:.3f}</td>
                    </tr>
                """)
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Simple text-based heatmap
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Weight Heatmap (Text Representation)</div>
                    <p>This is a simplified text representation of the weight matrix.</p>
                    <div class="heatmap">
                        <table>
                            <tr>
                                <th>Source / Target</th>
            """)
            
            # Column headers
            for neuron in neurons:
                f.write(f"<th>{neuron}</th>")
            
            f.write("</tr>")
            
            # Rows with data
            for src in neurons:
                f.write(f"<tr><th>{src}</th>")
                
                for dst in neurons:
                    if src == dst:
                        f.write("<td style='background-color: #f0f0f0;'>—</td>")
                    else:
                        weight = self.brain_widget.weights.get((src, dst), 
                                self.brain_widget.weights.get((dst, src), 0))
                        
                        # Style based on weight
                        if weight > 0:
                            intensity = min(255, int(weight * 255))
                            bg_color = f"rgba(0, {intensity}, 0, 0.2)"
                            text_color = "green"
                        else:
                            intensity = min(255, int(abs(weight) * 255))
                            bg_color = f"rgba({intensity}, 0, 0, 0.2)"
                            text_color = "red"
                        
                        f.write(f"<td style='background-color: {bg_color}; color: {text_color};'>{weight:.2f}</td>")
                
                f.write("</tr>")
            
            f.write("""
                        </table>
                    </div>
                </div>
            """)
            
            # End HTML document
            f.write("""
            </body>
            </html>
            """)

    def export_learning_data_csv(self, file_name):
        """Export learning data as CSV"""
        with open(file_name, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write neurons section
            writer.writerow(["NEURONS"])
            writer.writerow(["Neuron", "Position X", "Position Y", "Type", "Current Value"])
            
            for neuron in sorted(self.brain_widget.neuron_positions.keys()):
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                writer.writerow([neuron, position[0], position[1], neuron_type, value])
            
            # Blank row
            writer.writerow([])
            
            # Write connections section
            writer.writerow(["CONNECTIONS"])
            writer.writerow(["Source", "Target", "Weight"])
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                writer.writerow([source, target, weight])
            
            # Blank row
            writer.writerow([])
            
            # Write learning parameters
            writer.writerow(["LEARNING PARAMETERS"])
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    writer.writerow([param, value])

    def export_learning_data_text(self, file_name):
        """Export learning data as plain text"""
        with open(file_name, 'w') as f:
            f.write("SQUID BRAIN LEARNING DATA\n")
            f.write("=========================\n")
            f.write(f"Export time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Learning parameters
            f.write("LEARNING PARAMETERS\n")
            f.write("-----------------\n")
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    if param == 'learning_interval':
                        value = f"{value/1000} seconds"
                    f.write(f"{param}: {value}\n")
            
            f.write("\n")
            
            # Neuron information
            neurons = sorted(self.brain_widget.neuron_positions.keys())
            f.write(f"NEURONS ({len(neurons)} total)\n")
            f.write("-----------------\n")
            
            for neuron in neurons:
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                f.write(f"{neuron}: Position ({position[0]:.1f}, {position[1]:.1f}), Type: {neuron_type}, Value: {value:.1f}\n")
            
            f.write("\n")
            
            # Connection weights
            f.write(f"CONNECTION WEIGHTS ({len(self.brain_widget.weights)} total)\n")
            f.write("-----------------\n")
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                f.write(f"{source} → {target}: {weight:.3f}\n")
