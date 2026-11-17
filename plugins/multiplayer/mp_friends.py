"""Friends over the internet: friend codes, remembering who was added, and
the dialog for it (friend_link.py holds the codes themselves).
"""
import logging
from . import mp_constants # Access constants like mp_constants.PLUGIN_NAME

_LOG = logging.getLogger(__name__)


class FriendsMixin:
    """Part of MultiplayerPlugin (see mp_plugin_logic.py); not used on its own."""

    # ------------------------------------------------------------------
    # Friends over the internet. Linking two tanks only makes a meeting
    # possible: each squid still decides for itself whether to go
    # (src/venturing.py), and the tank still admits at most three visitors.
    # ------------------------------------------------------------------
    def _config(self):
        return getattr(self.tamagotchi_logic, 'config_manager', None)

    def listening_port(self) -> int:
        return int(getattr(self.network_node, 'port', mp_constants.MULTICAST_PORT))

    def _restore_friends(self) -> None:
        """Friends added in an earlier session are friends still."""
        config = self._config()
        if config is None or self.network_node is None \
                or not hasattr(config, 'get_multiplayer_friends'):
            return
        for ip, port, invitation in config.get_multiplayer_friends():
            try:
                self.network_node.add_friend(ip, port, invitation)
            except ValueError:
                break

    def _remember_friends(self) -> None:
        config = self._config()
        if config is None or self.network_node is None \
                or not hasattr(config, 'set_multiplayer_friends'):
            return
        # Only the ones the player added. Someone who joined with this tank's
        # code is let in for as long as they keep showing it, not for ever.
        config.set_multiplayer_friends(
            [(ip, port, peer.get('invitation', 0))
             for (ip, port), peer in self.network_node.direct_peers.items()
             if not peer.get('theirs')])

    def friends(self):
        """The tanks this one is linked to, for the Friends window."""
        if self.network_node is None:
            return []
        return [{'ip': ip, 'port': port, 'last_heard': peer.get('last_heard', 0.0),
                 'theirs': bool(peer.get('theirs'))}
                for (ip, port), peer in self.network_node.direct_peers.items()]

    def connect_to_friend(self, text: str):
        """Link to a friend's tank from their friend code or IP address.
        Returns (ok, what to tell the player)."""
        from .friend_link import FriendCodeError, parse_friend
        if self.network_node is None:
            return False, "Multiplayer is not running."
        try:
            where = parse_friend(text)
            self.network_node.add_friend(where.ip, where.port, where.invitation)
        except (FriendCodeError, ValueError) as exc:
            return False, str(exc).capitalize() + "."
        self._remember_friends()
        # Say hello straight away rather than waiting for the next heartbeat:
        # it is this first message that opens the way through a router.
        try:
            self.network_node.send_message('heartbeat', {
                'node_id': self.network_node.node_id, 'status': 'alive',
                'squid_pos': None})
        except Exception:
            _LOG.debug('Ignored exception', exc_info=True)
        if where.invitation:
            return True, (f"Linked to {where.ip}:{where.port}. If their tank "
                          f"does not answer, ask them to enter your code too.")
        return True, (f"Linked to {where.ip}:{where.port}. Without a friend "
                      f"code they have to add your address as well before "
                      f"either tank will listen to the other.")

    def forget_friend(self, ip: str, port: int = None) -> bool:
        if self.network_node is None:
            return False
        gone = self.network_node.remove_friend(ip, port)
        if gone:
            self._remember_friends()
        return gone

    def friend_code(self) -> str:
        return self.network_node.friend_code() if self.network_node is not None else ''

    def friend_code_known(self) -> bool:
        """Has the tank found the address it is seen at from outside?"""
        return bool(getattr(self.network_node, 'public_endpoint', None))

    def find_friend_code(self) -> str:
        """Find the tank's outside address (one question to a public STUN
        server) and return the friend code built from it."""
        if self.network_node is None:
            return ''
        config = self._config()
        server = (config.get_multiplayer_stun_server()
                  if hasattr(config, 'get_multiplayer_stun_server')
                  else 'stun.l.google.com:19302')
        if server:
            host, _, port = server.partition(':')
            self.network_node.find_public_endpoint(host, int(port or 3478))
        return self.network_node.friend_code()

    def friend_code_note(self) -> str:
        if self.friend_code_known():
            ip, port = self.network_node.public_endpoint
            return (f"This code points at {ip}:{port}, the address your tank is "
                    f"seen at from the internet. Give it only to someone you "
                    f"would give that address to.")
        return ("Your internet address could not be found (offline, or the "
                "address server is blocked), so this code points at your "
                "address on your own network. It will work for a friend on "
                "the same network or VPN; for anyone else, give them your "
                "public IP address instead and forward the port.")

    def new_friend_code(self) -> str:
        return self.network_node.new_friend_code() if self.network_node is not None else ''

    def show_friends_dialog(self):
        from .friends_dialog import FriendsDialog
        parent = getattr(getattr(self.tamagotchi_logic, 'user_interface', None),
                         'window', None)
        dialog = getattr(self, '_friends_dialog', None)
        if dialog is None:
            dialog = self._friends_dialog = FriendsDialog(self, parent)
        dialog.show()
        dialog.raise_()
