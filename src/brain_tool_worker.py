"""Keeping the background brain worker alive: health checks, restarts, and
receiving its results.
"""
import logging
import time
from PyQt5 import QtCore
from .brain_worker import BrainWorker 

_LOG = logging.getLogger(__name__)


class BrainWorkerSupervisionMixin:
    """Part of SquidBrainWindow (see brain_tool.py); not used on its own."""

    def _keep_worker_alive(self):
        """Keep worker thread alive with periodic health checks"""
        if self.brain_worker and self.brain_worker.isRunning():
            # Queue a health check every 30 seconds
            self.brain_worker.queue_state_update({'health_check': True})
            QtCore.QTimer.singleShot(30000, self._keep_worker_alive)

    def check_worker_health(self):
        """
        Periodically check if the BrainWorker thread is alive and responsive.
        If it's dead or completely stalled, restart it safely.
        """
        if not hasattr(self, 'brain_worker') or not self.brain_worker:
            print("BrainWorker missing – creating new one")
            self._restart_brain_worker()
            return

        # Case 1: Thread object exists but is not running
        if not self.brain_worker.isRunning():
            print("BrainWorker thread not running – restarting")
            self._restart_brain_worker()
            return

        # Case 2: Thread is running but has been completely silent for too long
        if not self.is_worker_healthy():
            print("BrainWorker stalled (no activity in 15s) – forcing restart")
            self._restart_brain_worker()
            return

        # Everything looks fine
        # print("BrainWorker healthy")  # Uncomment only for deep debugging

    # SquidBrainWindow._restart_brain_worker
    def _restart_brain_worker(self):
        # --- stop old worker
        if hasattr(self, 'brain_worker') and self.brain_worker:
            print("Stopping old BrainWorker...")
            # Disconnect signals BEFORE stopping to prevent duplicate connections
            try:
                self.brain_worker.neurogenesis_result.disconnect(self._on_worker_activity)
                self.brain_worker.hebbian_result.disconnect(self._on_worker_activity)
                self.brain_worker.state_update_result.disconnect(self._on_worker_activity)
                self.brain_worker.error_occurred.disconnect(self._on_worker_error)
            except:
                _LOG.debug('Ignored exception', exc_info=True)  # Ignore if signals weren't connected
            
            self.brain_worker.stop()
            self.brain_worker.wait(3000)

        # --- create & start new worker
        self.brain_worker = BrainWorker(brain_widget=self.brain_widget)
        
        # Reconnect signals for new worker
        self.brain_worker.neurogenesis_result.connect(self._on_worker_activity)
        self.brain_worker.hebbian_result.connect(self._on_worker_activity)
        self.brain_worker.state_update_result.connect(self._on_worker_activity)
        self.brain_worker.error_occurred.connect(self._on_worker_error)
        
        self.brain_worker.start()

        # Update cache for new worker
        if hasattr(self.brain_widget, 'set_brain_worker'):
            self.brain_widget.set_brain_worker(self.brain_worker)
            self.brain_widget._update_worker_cache()
        
        # --- CRITICAL: Update TaskManager's worker reference ---
        if hasattr(self, 'task_manager') and self.task_manager:
            self.task_manager.update_worker_reference(self.brain_worker)
        
        # --- Keep-alive timer ---
        QtCore.QTimer.singleShot(1000, lambda: self._keep_worker_alive())
        print("BrainWorker successfully restarted and re-cached")

    def _on_worker_activity(self, result):
        """Update worker health when activity is detected"""
        self._last_worker_activity = time.time()
        self._worker_healthy = True

        # print(f"🧠 Worker activity detected: {time.time() - self._last_worker_activity:.1f}s ago")

    def _on_worker_error(self, error_msg):
        """Handle worker errors"""
        print(f"⚠️ Worker error: {error_msg}")
        self._worker_healthy = False

    def is_worker_healthy(self):
        """Check if worker is healthy based on recent activity"""
        if not self.brain_worker or not self.brain_worker.isRunning():
            return False
        
        # Consider worker healthy if it had activity in last 10 seconds
        time_since_activity = time.time() - self._last_worker_activity
        return time_since_activity < 10.0 and self._worker_healthy

    def on_neurogenesis_result(self, result):
        """Handle neurogenesis results from worker thread"""
        if result.get('should_create'):
            # This now runs on main thread - safe to modify brain_widget
            self.brain_widget.handle_neurogenesis_result(result)

    def on_hebbian_result(self, result):
        """Handle Hebbian learning results from worker thread"""
        if result.get('updated_pairs'):
            self.brain_widget.handle_hebbian_result(result)

    def on_state_update_result(self, result):
        """Handle processed state updates"""
        if result.get('processed_state'):
            self.brain_widget.update_state(result['processed_state'])

    def on_worker_error(self, error_msg):
        """Handle errors from worker thread"""
        print(f"⚠️ BrainWorker error: {error_msg}")
        # Optional: Show in UI
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage(f"Worker error: {error_msg}", 5000)
