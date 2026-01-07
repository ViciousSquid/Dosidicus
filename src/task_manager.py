from PyQt5.QtCore import Qt
import time
import threading
from collections import deque
from PyQt5.QtCore import QTimer, QMutex, QMutexLocker
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView)

class TaskManagerWindow(QWidget):
    """Simple at-a-glance thread and timer monitor."""

    def __init__(self, brain_worker, parent=None):
        super().__init__(parent, flags=Qt.Window)
        self.setWindowTitle("Task Monitor")
        self.resize(500, 300)
        self._brain_worker_ref = brain_worker
        self._parent_ref = parent

        # Simple UI
        layout = QVBoxLayout(self)
        
        # Thread status (simple table)
        thread_group = QGroupBox("Threads")
        thread_layout = QVBoxLayout(thread_group)
        
        self.thread_table = QTableWidget(2, 3)
        self.thread_table.setHorizontalHeaderLabels(["Thread", "Status", "Queue"])
        self.thread_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.thread_table.setEditTriggers(QTableWidget.NoEditTriggers)
        thread_layout.addWidget(self.thread_table)
        layout.addWidget(thread_group)

        # Timers (simple list)
        timer_group = QGroupBox("Active Timers")
        timer_layout = QVBoxLayout(timer_group)
        self.timer_label = QLabel("No timers tracked")
        self.timer_label.setWordWrap(True)
        timer_layout.addWidget(self.timer_label)
        layout.addWidget(timer_group)

        # Simple refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_display)
        self.refresh_timer.start(1000)  # Update every second

    @property
    def brain_worker(self):
        """Get worker from parent if available (fallback for safety)"""
        if self._parent_ref and hasattr(self._parent_ref, 'brain_worker'):
            return self._parent_ref.brain_worker
        return self._brain_worker_ref
    
    def update_worker_reference(self, new_worker):
        """Update the worker reference when it's restarted"""
        self._brain_worker_ref = new_worker
        print(f"TaskManager: Updated worker reference to {id(new_worker)}")

    def _refresh_display(self):
        """Refresh the display with current status."""
        # Update threads
        self._update_threads()
        
        # Update timers (if parent has timer info)
        self._update_timers()

    def _update_threads(self):
        """Update thread table using comprehensive health status"""
        # Main thread
        main_alive = threading.main_thread().is_alive()
        
        # Worker thread
        worker = self.brain_worker
        worker_alive = False
        queue_size = 0
        health_info = {}

        if worker and hasattr(worker, 'isRunning'):
            worker_alive = worker.isRunning()
            
            # Use worker's built-in health status if available
            if hasattr(worker, 'get_health_status'):
                health_info = worker.get_health_status()
                queue_size = health_info.get('queue_size', '?')
                # Override isRunning with more comprehensive check
                worker_alive = health_info.get('is_healthy', worker_alive)
        
        # Update table
        threads = [
            ("Main Thread", "✅ Running" if main_alive else "❌ Stopped", "-"),
            ("BrainWorker", "✅ Healthy" if worker_alive else "❌ Dead/Unresponsive", str(queue_size))
        ]
        
        for row, (name, status, queue) in enumerate(threads):
            self.thread_table.setItem(row, 0, QTableWidgetItem(name))
            self.thread_table.setItem(row, 1, QTableWidgetItem(status))
            self.thread_table.setItem(row, 2, QTableWidgetItem(queue))

    def _update_timers(self):
        """Check for active timers in parent."""
        timers = []
        parent = self._parent_ref
        
        if parent and hasattr(parent, 'brain_window'):
            bw = parent.brain_window
            timer_attrs = ['hebbian_timer', 'countdown_timer', 'update_timer', 'neurogenesis_timer']
            
            for attr in timer_attrs:
                if hasattr(bw, attr):
                    timer = getattr(bw, attr)
                    if timer and timer.isActive():
                        timers.append(attr.replace('_timer', ''))
        
        if timers:
            self.timer_label.setText(f"Active: {', '.join(timers)}")
        else:
            self.timer_label.setText("No active timers")

    def closeEvent(self, event):
        """Clean up timer on close."""
        self.refresh_timer.stop()
        super().closeEvent(event)