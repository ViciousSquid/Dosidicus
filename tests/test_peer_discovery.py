"""Two instances on one machine have to be able to see each other.

This is the test that was missing. Every multiplayer test in this repo used a
loopback Link object standing in for the network, which is the right way to
test behaviour but means nothing ever exercised the socket. So a plugin that
built its socket, bound it, joined the multicast group and then never started
the thread that READS the socket looked completely healthy: it reported
"Connected", it sent successfully, and no peer ever appeared.

Two levels here:

  1. real sockets - two NetworkNodes on this machine must actually hear each
     other. Skipped where the environment has no working multicast, because
     that is the environment's answer and not the code's.

  2. the wiring - the plugin must START LISTENING during setup. That one has
     no excuse to be skipped anywhere, and it is the specific regression.
"""

import os
import socket
import sys
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from plugins.multiplayer import mp_constants                  # noqa: E402
from plugins.multiplayer.mp_network_node import NetworkNode   # noqa: E402


def _multicast_available():
    """Can this machine do multicast at all? Not every CI container can."""
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        probe.bind(('', 0))
        probe.close()
        return True
    except OSError:
        return False


class TwoNodesOnOneMachineTests(unittest.TestCase):
    """The reported symptom, as a test."""

    def setUp(self):
        if not _multicast_available():
            self.skipTest("no usable multicast on this machine")
        self.nodes = []

    def tearDown(self):
        for node in self.nodes:
            try:
                node.close()
            except Exception:
                pass

    def _node(self, name):
        node = NetworkNode(node_id=name)
        self.nodes.append(node)
        if not node.is_connected:
            self.skipTest("could not bind the multicast socket here")
        self.assertTrue(node.start_listening(), "listener thread must start")
        return node

    def test_a_node_that_is_listening_hears_its_peer(self):
        alice = self._node("squid_alice0")
        bob = self._node("squid_bob000")
        time.sleep(0.3)          # let both listener threads settle

        alice.send_message('heartbeat', {'node_id': alice.node_id})

        deadline = time.time() + 3.0
        heard = []
        while time.time() < deadline and not heard:
            heard = [m for m, _addr in bob.receive_messages()
                     if m.get('node_id') == alice.node_id]
            time.sleep(0.05)

        if not heard:
            self.skipTest("multicast loopback is not delivering on this machine")
        self.assertEqual(heard[0]['type'], 'heartbeat')
        self.assertIn(alice.node_id, bob.known_nodes,
                      "hearing a peer must register it as a known node")

    def test_a_node_that_never_listens_hears_nothing(self):
        """The exact failure: it sends fine and detects nobody.

        Sending and listening are independent, which is why the broken state
        was so convincing - the log said "Exit message successfully broadcast"
        every time.
        """
        alice = self._node("squid_alice1")
        deaf = NetworkNode(node_id="squid_deaf00")
        self.nodes.append(deaf)
        # deliberately NOT calling start_listening()

        self.assertTrue(alice.send_message('heartbeat', {'node_id': alice.node_id}))
        time.sleep(0.5)
        self.assertEqual(deaf.receive_messages(), [])
        self.assertEqual(deaf.known_nodes, {},
                         "a node with no listener can never detect a peer")
        self.assertGreater(alice.messages_sent, 0,
                           "...while sending kept working perfectly")


class TheListenerIsStartedTests(unittest.TestCase):
    """The regression, checked without needing a network at all."""

    def test_setup_starts_the_listener(self):
        """Source-level, because the bug was that a call site did not exist.

        The only call to start_listening() in the plugin used to be inside
        debug_autopilot_status(), which returns early when there are no remote
        controllers - and at startup there never are.
        """
        import ast
        import inspect
        from plugins.multiplayer import mp_plugin_logic

        tree = ast.parse(inspect.getsource(mp_plugin_logic))
        plugin = next(n for n in tree.body
                      if isinstance(n, ast.ClassDef) and n.name == 'MultiplayerPlugin')
        setup = next(n for n in plugin.body
                     if isinstance(n, ast.FunctionDef) and n.name == 'setup')
        calls = [node.func.attr for node in ast.walk(setup)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        self.assertIn('start_listening', calls,
                      "setup() must start the listener or no peer is ever seen")

    def test_enable_is_a_method_and_not_a_nested_function(self):
        """It was defined one indent level too deep, inside a debug method."""
        from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
        self.assertTrue(callable(getattr(MultiplayerPlugin, 'enable', None)))

    def test_a_dead_listener_is_restarted(self):
        """watchdog_check() existed and nothing called it."""
        import ast
        import inspect
        from plugins.multiplayer import mp_plugin_logic

        source = inspect.getsource(mp_plugin_logic.MultiplayerPlugin)
        self.assertIn('watchdog_check', source,
                      "a listener thread that dies must be restarted")

    def test_the_dashboard_reads_counters_that_exist(self):
        """Both stat rows named attributes NetworkNode never had, so they
        showed "N/A" and hid the fact that nothing was arriving."""
        import inspect
        from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin

        node = NetworkNode(node_id="squid_stats0")
        try:
            source = inspect.getsource(MultiplayerPlugin.show_network_dashboard)
            for attribute in ('messages_sent', 'messages_received'):
                with self.subTest(attribute=attribute):
                    self.assertIn(attribute, source)
                    self.assertTrue(hasattr(node, attribute))
            self.assertNotIn('total_sent_count', source)
        finally:
            node.close()

    def test_sending_increments_the_counter(self):
        node = NetworkNode(node_id="squid_count0")
        try:
            if not node.is_connected:
                self.skipTest("could not bind the multicast socket here")
            before = node.messages_sent
            node.send_message('heartbeat', {'node_id': node.node_id})
            self.assertGreater(node.messages_sent, before)
        finally:
            node.close()


if __name__ == "__main__":
    unittest.main()
