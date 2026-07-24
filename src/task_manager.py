from PyQt5.QtCore import Qt
import time
import threading
from collections import deque
from PyQt5.QtCore import QTimer, QMutex, QMutexLocker
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
                             QCheckBox, QPushButton)


class PerfTracker:
    """Lightweight, opt-in performance counter / timer store.

    The hot paths (simulation tick, animation update, paint, connection
    drawing) are already instrumented with guards of the form::

        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            ...time.perf_counter()...

    Profiling is *disabled by default*, so those guards cost only a single
    boolean check per frame and add no measurable overhead. Enabling it from
    the Task Monitor starts collecting rolling timings that the monitor then
    displays.

    All callers run on the Qt main thread (the simulation timer and the
    widget paint/draw routines), and the monitor reads the data from the same
    thread, so no locking is required.
    """

    def __init__(self, maxlen: int = 240):
        self.enabled = False
        self._maxlen = maxlen
        self._counters = {}   # name -> int
        self._timings = {}    # name -> deque[float] (milliseconds)

    def set_enabled(self, value: bool):
        """Turn profiling on/off. Clears stale data when turning on."""
        value = bool(value)
        if value and not self.enabled:
            self.reset()
        self.enabled = value

    def increment(self, name: str, amount: int = 1):
        if not self.enabled:
            return
        self._counters[name] = self._counters.get(name, 0) + amount

    def record(self, name: str, ms: float):
        if not self.enabled:
            return
        dq = self._timings.get(name)
        if dq is None:
            dq = deque(maxlen=self._maxlen)
            self._timings[name] = dq
        dq.append(ms)

    def reset(self):
        self._counters.clear()
        self._timings.clear()

    def snapshot(self):
        """Return aggregated timings and counters for display."""
        timings = {}
        for name, dq in list(self._timings.items()):
            if dq:
                vals = list(dq)
                timings[name] = {
                    'count': len(vals),
                    'avg_ms': sum(vals) / len(vals),
                    'max_ms': max(vals),
                    'last_ms': vals[-1],
                }
        return {'timings': timings, 'counters': dict(self._counters)}


# Module-level singleton imported by the instrumented hot paths
# (brain_widget, tamagotchi_logic). Importing this successfully is what flips
# their _PERF_TRACKING_AVAILABLE flag to True.
perf_tracker = PerfTracker()


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

        # Performance profiling (opt-in)
        perf_group = QGroupBox("Performance (hot paths)")
        perf_layout = QVBoxLayout(perf_group)

        controls = QHBoxLayout()
        self.perf_checkbox = QCheckBox("Enable profiling")
        self.perf_checkbox.setChecked(perf_tracker.enabled)
        self.perf_checkbox.toggled.connect(self._on_perf_toggled)
        controls.addWidget(self.perf_checkbox)
        self.perf_reset_button = QPushButton("Reset")
        self.perf_reset_button.clicked.connect(perf_tracker.reset)
        controls.addWidget(self.perf_reset_button)
        controls.addStretch(1)
        perf_layout.addLayout(controls)

        self.perf_table = QTableWidget(0, 4)
        self.perf_table.setHorizontalHeaderLabels(["Metric", "Avg (ms)", "Max (ms)", "Count"])
        self.perf_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.perf_table.setEditTriggers(QTableWidget.NoEditTriggers)
        perf_layout.addWidget(self.perf_table)
        layout.addWidget(perf_group)

        # Simple refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_display)
        self.refresh_timer.start(1000)  # Update every second

    def _on_perf_toggled(self, checked):
        """Enable/disable the shared performance tracker."""
        perf_tracker.set_enabled(checked)

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

        # Update performance metrics
        self._update_perf()

    def _update_perf(self):
        """Populate the performance table from the shared tracker snapshot."""
        if not perf_tracker.enabled:
            self.perf_table.setRowCount(1)
            self.perf_table.setItem(0, 0, QTableWidgetItem("Profiling disabled"))
            for col in range(1, 4):
                self.perf_table.setItem(0, col, QTableWidgetItem("-"))
            return

        snap = perf_tracker.snapshot()
        timings = snap['timings']
        counters = snap['counters']

        # Timings first (sorted by average cost, most expensive on top), then
        # any counters that have no matching timing.
        timing_rows = sorted(timings.items(), key=lambda kv: kv[1]['avg_ms'], reverse=True)
        counter_only = [(n, c) for n, c in counters.items() if n not in timings]

        self.perf_table.setRowCount(len(timing_rows) + len(counter_only))
        row = 0
        for name, stats in timing_rows:
            self.perf_table.setItem(row, 0, QTableWidgetItem(name))
            self.perf_table.setItem(row, 1, QTableWidgetItem(f"{stats['avg_ms']:.3f}"))
            self.perf_table.setItem(row, 2, QTableWidgetItem(f"{stats['max_ms']:.3f}"))
            count = counters.get(name, stats['count'])
            self.perf_table.setItem(row, 3, QTableWidgetItem(str(count)))
            row += 1

        for name, count in counter_only:
            self.perf_table.setItem(row, 0, QTableWidgetItem(name))
            self.perf_table.setItem(row, 1, QTableWidgetItem("-"))
            self.perf_table.setItem(row, 2, QTableWidgetItem("-"))
            self.perf_table.setItem(row, 3, QTableWidgetItem(str(count)))
            row += 1

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