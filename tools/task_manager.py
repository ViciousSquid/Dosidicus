"""
Enhanced Task Manager with improved thread monitoring
Fixes the race condition issue where Task Manager incorrectly reports thread as DEAD
"""

import time
import threading
from collections import deque
from PyQt5.QtGui import QColor
from PyQt5.QtCore import QTimer, Qt, QMutex, QMutexLocker
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QGroupBox, QProgressBar, QTableWidget,
                             QTableWidgetItem, QHeaderView, QMessageBox)

class TaskManagerWindow(QWidget):
    """Enhanced technical monitor for main + worker threads with robust health checking."""

    def __init__(self, brain_worker, parent=None):
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("Enhanced Task-Manager")
        self.resize(600, 480)
        self._brain_worker_ref = brain_worker  # Keep initial reference
        self._parent_ref = parent  # Store parent reference for dynamic lookup
        
        # Initialize UI and timers
        self._init_ui_and_timers()

    @property
    def brain_worker(self):
        """
        Dynamically get the brain_worker reference.
        Tries parent first (authoritative), falls back to stored reference.
        """
        # Try to get from parent (most reliable - parent maintains the live reference)
        if self._parent_ref and hasattr(self._parent_ref, 'brain_worker'):
            worker = self._parent_ref.brain_worker
            if worker is not None:
                return worker
        
        # Fallback to stored reference
        return self._brain_worker_ref
    
    @brain_worker.setter
    def brain_worker(self, value):
        """Allow external updates to brain_worker reference."""
        self._brain_worker_ref = value

    def _init_ui_and_timers(self):
        """Initialize UI components and timers - called from __init__"""
        # Health monitoring state
        self._last_health_check = 0
        self._health_check_interval = 2.0  # seconds
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

        # ---- UI ----
        lay = QVBoxLayout(self)

        # Thread status group
        thread_group = QGroupBox("Thread Status")
        thread_layout = QVBoxLayout(thread_group)

        # Enhanced thread table
        self.table = QTableWidget(2, 7)
        self.table.setHorizontalHeaderLabels([
            "Thread", "Status", "Health", "CPU (s)", "Queue", "Last Job", "Heartbeat"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        thread_layout.addWidget(self.table)

        # Health indicators
        health_layout = QHBoxLayout()
        
        # Thread health status
        self.health_label = QLabel("Health: Checking...")
        self.health_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        health_layout.addWidget(self.health_label)
        
        # Last heartbeat time
        self.heartbeat_label = QLabel("Heartbeat: N/A")
        self.heartbeat_label.setStyleSheet("font-size: 11px; color: #666;")
        health_layout.addWidget(self.heartbeat_label)
        
        thread_layout.addLayout(health_layout)
        lay.addWidget(thread_group)

        # Performance metrics
        perf_group = QGroupBox("Performance Metrics")
        perf_layout = QVBoxLayout(perf_group)

        # Thread utilization
        self.utilization_bar = QProgressBar()
        self.utilization_bar.setMaximum(100)
        self.utilization_bar.setFormat("Thread Utilization: %v%")
        perf_layout.addWidget(self.utilization_bar)
        
        lay.addWidget(perf_group)

        # Status and controls
        status_layout = QHBoxLayout()
        
        # Status label
        self.status = QLabel("Initializing...")
        status_layout.addWidget(self.status)
        
        # Health check button
        self.health_check_btn = QLabel("🔄 Auto")
        self.health_check_btn.setStyleSheet("font-size: 16px; cursor: pointer;")
        self.health_check_btn.mousePressEvent = lambda e: self._force_health_check()
        status_layout.addWidget(self.health_check_btn)
        
        lay.addLayout(status_layout)

        # --- timers ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update)
        self.timer.start(1000)  # refresh time

        # Health check timer (slower)
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self._health_check_update)
        self.health_timer.start(2000)  # 2 second health checks

    # ------------------------------------------------------------------
    def _update(self):
        """Refresh every 1000 ms with basic metrics."""
        # ----------------------------------------------------------
        # MAIN thread
        main_alive = threading.main_thread().is_alive()
        main_cpu = threading.main_thread().native_id or 0
        main_cpu_s = "-" if not main_alive else f"{main_cpu/1000:.2f}"

        # ----------------------------------------------------------
        # WORKER thread - Enhanced monitoring
        worker_data = self._get_worker_status()

        # ----------------------------------------------------------
        # Fill table with enhanced data
        for row, (name, status_data) in enumerate([
            ("Main", {
                "status": "✅ RUNNING" if main_alive else "❌ STOPPED",
                "health": "✅ HEALTHY" if main_alive else "❌ DEAD",
                "cpu": main_cpu_s,
                "queue": "-",
                "job": "-",
                "heartbeat": "N/A"
            }),
            ("BrainWorker", worker_data)
        ]):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(status_data["status"]))
            self.table.setItem(row, 2, QTableWidgetItem(status_data["health"]))
            self.table.setItem(row, 3, QTableWidgetItem(str(status_data["cpu"])))
            self.table.setItem(row, 4, QTableWidgetItem(str(status_data["queue"])))
            self.table.setItem(row, 5, QTableWidgetItem(str(status_data["job"])))
            self.table.setItem(row, 6, QTableWidgetItem(str(status_data["heartbeat"])))

        # Color code rows based on health
        self._color_code_rows()

    def _get_worker_status(self):
        """Get comprehensive worker thread status."""
        worker = self.brain_worker
        
        # Debug: Check what we actually have
        if worker is None:
            return {
                "status": "❌ NO REF",
                "health": "❌ DEAD",
                "cpu": "-",
                "queue": "0",
                "job": "-",
                "heartbeat": "N/A"
            }
        
        if not hasattr(worker, 'isRunning'):
            return {
                "status": f"❌ BAD TYPE ({type(worker).__name__})",
                "health": "❌ DEAD",
                "cpu": "-",
                "queue": "0",
                "job": "-",
                "heartbeat": "N/A"
            }

        # Basic status from Qt
        try:
            worker_running = worker.isRunning()
        except Exception as e:
            return {
                "status": f"❌ ERROR: {e}",
                "health": "❌ DEAD",
                "cpu": "-",
                "queue": "0",
                "job": "-",
                "heartbeat": "N/A"
            }
        
        # Queue info
        queue_len = 0
        if hasattr(worker, '_work_queue'):
            try:
                with QMutexLocker(worker._queue_mutex):
                    queue_len = len(worker._work_queue)
            except:
                queue_len = "?"

        # Last job info
        last_job = getattr(worker, '_last_job', "-")
        
        # Heartbeat (if available)
        heartbeat = getattr(worker, '_last_heartbeat', 0)
        if heartbeat:
            time_since_heartbeat = time.time() - heartbeat
            heartbeat_str = f"{time_since_heartbeat:.1f}s ago"
        else:
            heartbeat_str = "N/A"

        # Use worker's own health check if available
        is_healthy = False
        if hasattr(worker, 'is_healthy'):
            try:
                is_healthy = worker.is_healthy()
            except:
                is_healthy = self._determine_worker_health(worker_running, queue_len, heartbeat)
        else:
            is_healthy = self._determine_worker_health(worker_running, queue_len, heartbeat)
        
        # Status text - use multiple indicators
        if worker_running:
            status_text = "✅ RUNNING"
        elif is_healthy:
            status_text = "⏸️ IDLE"  # Not running but healthy (waiting for work)
        else:
            status_text = "⚠️ STOPPED"

        return {
            "status": status_text,
            "health": "✅ HEALTHY" if is_healthy else "❌ UNHEALTHY",
            "cpu": "-",  # Could be enhanced with actual CPU usage
            "queue": str(queue_len),
            "job": str(last_job),
            "heartbeat": heartbeat_str
        }

    def _determine_worker_health(self, is_running, queue_len, last_heartbeat):
        """Enhanced health determination using multiple indicators."""
        # Factor 1: isRunning() status
        running_status = is_running
        
        # Factor 2: Recent heartbeat (if implemented)
        heartbeat_recent = False
        if last_heartbeat:
            time_since_heartbeat = time.time() - last_heartbeat
            heartbeat_recent = time_since_heartbeat < 5.0  # Within 5 seconds
        
        # Factor 3: Queue activity
        has_queued_work = queue_len != "?" and int(queue_len) > 0
        
        # Factor 4: Recent activity from parent (if available)
        parent_recent_activity = False
        if hasattr(self.parent(), '_last_worker_activity'):
            time_since_activity = time.time() - self.parent()._last_worker_activity
            parent_recent_activity = time_since_activity < 10.0
        
        # Health logic: Thread is healthy if ANY of these are true
        return (
            running_status or  # Qt says it's running
            heartbeat_recent or  # Recent heartbeat
            has_queued_work or  # Has work to do
            parent_recent_activity  # Parent detected recent activity
        )

    def _color_code_rows(self):
        """Apply color coding to table rows based on health status."""
        for row in range(self.table.rowCount()):
            health_item = self.table.item(row, 2)  # Health column
            if health_item:
                health_text = health_item.text()
                if "HEALTHY" in health_text:
                    color = "#d1fae5"  # Green
                elif "UNHEALTHY" in health_text or "DEAD" in health_text:
                    color = "#fee2e2"  # Red
                else:
                    color = "#fef3c7"  # Yellow
                
                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor(color))  # Convert string to QColor

    def _health_check_update(self):
        """Less frequent health check updates."""
        if not self.brain_worker:
            return

        # Get current health status
        worker_data = self._get_worker_status()
        is_healthy = "HEALTHY" in worker_data["health"]
        
        # Update health label
        if is_healthy:
            self.health_label.setText("✅ Health: EXCELLENT")
            self.health_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #10b981;")
            self._consecutive_failures = 0
        else:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_consecutive_failures:
                self.health_label.setText(f"❌ Health: CRITICAL ({self._consecutive_failures} failures)")
                self.health_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #ef4444;")
            else:
                self.health_label.setText(f"⚠️ Health: DEGRADED ({self._consecutive_failures}/{self._max_consecutive_failures})")
                self.health_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #f59e0b;")

        # Update heartbeat info
        heartbeat = getattr(self.brain_worker, '_last_heartbeat', 0)
        if heartbeat:
            time_since = time.time() - heartbeat
            self.heartbeat_label.setText(f"Heartbeat: {time_since:.1f}s ago")
        else:
            self.heartbeat_label.setText("Heartbeat: Not implemented")

        # Update main status
        if is_healthy:
            self.status.setText(f"<b style='color:green;'>✅ All systems operational</b> - Queue: {worker_data['queue']}")
        else:
            self.status.setText(f"<b style='color:red;'>⚠️ Worker thread health issues detected</b>")
            
            # Show warning dialog for critical health issues
            if self._consecutive_failures == self._max_consecutive_failures:
                QMessageBox.warning(self, "Thread Health Alert", 
                    f"Worker thread has been unhealthy for {self._max_consecutive_failures} consecutive checks. "
                    "This may indicate a serious issue that requires attention.")

        # Update utilization (simplified)
        queue_size = int(worker_data['queue']) if worker_data['queue'] != "?" and worker_data['queue'] != "-" else 0
        utilization = min(100, queue_size * 20)  # Rough estimate
        self.utilization_bar.setValue(int(utilization))

    def _force_health_check(self):
        """Force an immediate health check."""
        self.health_check_btn.setText("🔄 Checking...")
        self._health_check_update()
        
        # Reset the button after a moment
        QTimer.singleShot(1000, lambda: self.health_check_btn.setText("🔄 Auto"))

    def update_worker_status(self):
        """Update the worker status display - compatibility method."""
        self._health_check_update()

    def closeEvent(self, event):
        """Clean up timers when closing."""
        self.timer.stop()
        self.health_timer.stop()
        super().closeEvent(event)