"""Local peer-to-peer transport via Android Nearby Connections.

This wraps the Java ``NearbyBridge`` shim (see ``java/org/vicioussquid/nearby``)
through pyjnius. The shim subclasses Nearby's abstract callbacks and forwards
events to ``NearbyListener``, which we implement here in Python. Snapshots cross
as Base64 strings.

Everything is guarded so the module imports on any platform: ``is_available()``
returns False off-device (or if Play Services / the shim isn't present), and the
UI falls back to a preview-only mode.

Nearby callbacks arrive on a binder thread, so every event is marshalled onto
the Kivy main thread via ``Clock`` before it touches the UI or the simulation.
"""

import base64

from kivy.clock import Clock

SERVICE_ID = "org.vicioussquid.dosidicus.visit"

# Runtime permissions Nearby needs (string names so this works regardless of
# which are present in p4a's Permission enum).
NEARBY_PERMISSIONS = [
    "android.permission.BLUETOOTH_ADVERTISE",
    "android.permission.BLUETOOTH_CONNECT",
    "android.permission.BLUETOOTH_SCAN",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.ACCESS_COARSE_LOCATION",
    "android.permission.NEARBY_WIFI_DEVICES",
]


def _is_android():
    try:
        import android  # noqa: F401
        return True
    except ImportError:
        return False


def is_available():
    """True only when the Nearby bridge can actually be used (on-device build
    with Play Services and the Java shim compiled in)."""
    if not _is_android():
        return False
    try:
        from jnius import autoclass
        autoclass("org.vicioussquid.nearby.NearbyBridge")
        return True
    except Exception:
        return False


def request_permissions():
    if not _is_android():
        return
    try:
        from android.permissions import request_permissions as _req
        _req(NEARBY_PERMISSIONS)
    except Exception as e:
        print(f"[Dosidicus] nearby permission request failed: {e}")


def _build_listener(manager):
    """Create the pyjnius proxy implementing our Java NearbyListener. Defined
    lazily so importing this module never requires jnius."""
    from jnius import PythonJavaClass, java_method

    class _Listener(PythonJavaClass):
        __javainterfaces__ = ["org/vicioussquid/nearby/NearbyListener"]
        __javacontext__ = "app"   # use the app classloader (sees our shim)

        def __init__(self, mgr):
            super().__init__()
            self.mgr = mgr

        @java_method("(Ljava/lang/String;)V")
        def onStatus(self, message):
            self.mgr._emit("status", message)

        @java_method("(Ljava/lang/String;Ljava/lang/String;)V")
        def onEndpointFound(self, endpointId, name):
            self.mgr._emit("peer_found", endpointId, name)

        @java_method("(Ljava/lang/String;)V")
        def onEndpointLost(self, endpointId):
            self.mgr._emit("peer_lost", endpointId)

        @java_method("(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V")
        def onConnectionInitiated(self, endpointId, name, authDigits):
            self.mgr._emit("connection_initiated", endpointId, name, authDigits)

        @java_method("(Ljava/lang/String;)V")
        def onConnected(self, endpointId):
            self.mgr._emit("connected", endpointId)

        @java_method("(Ljava/lang/String;)V")
        def onRejected(self, endpointId):
            self.mgr._emit("rejected", endpointId)

        @java_method("(Ljava/lang/String;)V")
        def onDisconnected(self, endpointId):
            self.mgr._emit("disconnected", endpointId)

        @java_method("(Ljava/lang/String;Ljava/lang/String;)V")
        def onBytesReceived(self, endpointId, base64Data):
            self.mgr._emit("bytes", endpointId, base64Data)

    return _Listener(manager)


class NearbyManager:
    """Transport-only: the UI sets ``handlers`` (name -> callback) and calls
    host()/find()/request()/accept()/send()/stop()."""

    def __init__(self):
        self.handlers = {}
        self._bridge = None
        self._listener = None

    def start(self):
        if self._bridge is not None:
            return True
        if not is_available():
            return False
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        NearbyBridge = autoclass("org.vicioussquid.nearby.NearbyBridge")
        self._bridge = NearbyBridge(PythonActivity.mActivity, SERVICE_ID)
        self._listener = _build_listener(self)
        self._bridge.setListener(self._listener)
        return True

    # events are delivered from a binder thread -> hop to the Kivy main thread
    def _emit(self, event, *args):
        Clock.schedule_once(lambda dt: self._deliver(event, *args), 0)

    def _deliver(self, event, *args):
        cb = self.handlers.get(event)
        if cb:
            cb(*args)

    # ------------------------------------------------------------- actions
    def host(self, name):
        if self.start():
            self._bridge.startAdvertising(name)

    def find(self):
        if self.start():
            self._bridge.startDiscovery()

    def request(self, name, endpoint_id):
        if self._bridge:
            self._bridge.requestConnection(name, endpoint_id)

    def accept(self, endpoint_id):
        if self._bridge:
            self._bridge.acceptConnection(endpoint_id)

    def reject(self, endpoint_id):
        if self._bridge:
            self._bridge.rejectConnection(endpoint_id)

    def send(self, endpoint_id, data: bytes):
        if self._bridge:
            self._bridge.sendBytes(endpoint_id, base64.b64encode(data).decode("ascii"))

    def disconnect(self, endpoint_id):
        if self._bridge:
            self._bridge.disconnect(endpoint_id)

    def stop(self):
        if self._bridge:
            try:
                self._bridge.stopAll()
            except Exception:
                pass

    @staticmethod
    def decode(base64_data: str) -> bytes:
        return base64.b64decode(base64_data)
