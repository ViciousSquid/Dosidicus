"""Internet play: friend codes, direct links, and who a tank will listen to.

Everything is exercised on this machine: the codes are pure arithmetic, the
gate is called with addresses as they would arrive, and two real tanks talk to
each other over loopback on different ports.
"""
import socket
import struct
import threading
import time
import unittest

from plugins.multiplayer import friend_link as fl
from plugins.multiplayer.consent import ConsentPolicy
from plugins.multiplayer.mp_network_node import MAX_DIRECT_PEERS, NetworkNode

STRANGER = ('8.8.4.4', 40001)         # an address on the internet
FRIEND = ('1.1.1.1', 10000)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def node(name, port=None):
    made = NetworkNode(name, port=port or free_port())
    made.auto_reconnect = False
    return made


class FriendCodes(unittest.TestCase):

    def test_a_code_carries_the_address_the_port_and_the_invitation(self):
        code = fl.encode_friend_code('86.12.34.56', 10000, 0xBEEF1)
        self.assertRegex(code, r'^[0-9A-Z]{5}(-[0-9A-Z]{5}){2}$')
        where = fl.decode_friend_code(code)
        self.assertEqual((where.ip, where.port, where.invitation),
                         ('86.12.34.56', 10000, 0xBEEF1))

    def test_a_code_is_fifteen_characters_whatever_it_points_at(self):
        """Any address, any port a router might hand out, any invitation."""
        for ip, port, invitation in (('0.0.0.1', 1, 1), ('255.255.255.255', 65535, 0xFFFFF),
                                     ('192.168.1.2', 10000, 0), ('100.64.3.2', 51234, 77)):
            code = fl.encode_friend_code(ip, port, invitation)
            self.assertEqual((len(code.replace("-", "")), fl.CODE_LENGTH), (15, 15))
            self.assertEqual(fl.decode_friend_code(code), fl.Whereabouts(ip, port, invitation))

    def test_any_one_wrong_character_and_any_two_swapped_are_caught(self):
        """The two mistakes people make copying a code by hand. Every one of
        them, not most: the check character is built so none can slip by."""
        code = fl.encode_friend_code('86.12.34.56', 51234, 0xBEEF1).replace('-', '')
        for index in range(len(code)):
            for other in fl._ALPHABET:
                if other != code[index]:
                    with self.assertRaises(fl.FriendCodeError):
                        fl.decode_friend_code(code[:index] + other + code[index + 1:])
        for index in range(len(code) - 2):           # neighbours among the first fourteen
            if code[index] != code[index + 1]:
                swapped = code[:index] + code[index + 1] + code[index] + code[index + 2:]
                with self.assertRaises(fl.FriendCodeError):
                    fl.decode_friend_code(swapped)

    def test_an_older_longer_code_is_named_for_what_it_is(self):
        with self.assertRaises(fl.FriendCodeError) as raised:
            fl.parse_friend('00B48-00G49-RGX7G-YA081')
        self.assertIn('older', str(raised.exception))
        self.assertIn('15', str(raised.exception))

    def test_an_invitation_that_does_not_fit_is_refused_not_cut_short(self):
        with self.assertRaises(fl.FriendCodeError):
            fl.encode_friend_code('86.12.34.56', 10000, 1 << fl.INVITATION_BITS)

    def test_it_forgives_how_people_actually_type(self):
        code = fl.encode_friend_code('86.12.34.56', 10000, 12345)
        sloppy = code.lower().replace('-', ' ').replace('0', 'o').replace('1', 'l')
        self.assertEqual(fl.decode_friend_code(sloppy), fl.decode_friend_code(code))

    def test_one_wrong_character_is_caught_not_followed(self):
        code = fl.encode_friend_code('86.12.34.56', 10000, 12345)
        index = 3
        wrong = code[:index] + ('7' if code[index] != '7' else '8') + code[index + 1:]
        with self.assertRaises(fl.FriendCodeError) as raised:
            fl.decode_friend_code(wrong)
        self.assertIn('mistake', str(raised.exception))

    def test_nonsense_is_refused_with_words_a_player_can_use(self):
        for text in ('', 'hello', 'AAAAA-AAAAA', '999.1.1.1', '1.2.3.4:99999'):
            with self.subTest(text=text):
                with self.assertRaises(fl.FriendCodeError):
                    fl.parse_friend(text)

    def test_an_ip_address_typed_by_hand_is_an_address_with_no_invitation(self):
        self.assertEqual(fl.parse_friend(' 86.12.34.56 '),
                         fl.Whereabouts('86.12.34.56', fl.DEFAULT_PORT, 0))
        self.assertEqual(fl.parse_friend('86.12.34.56:4242').address,
                         ('86.12.34.56', 4242))

    def test_every_invitation_is_different_and_never_nothing(self):
        made = {fl.new_invitation() for _ in range(50)}
        self.assertGreaterEqual(len(made), 49)       # one in a million, each
        self.assertNotIn(0, made)
        self.assertTrue(all(value < 1 << fl.INVITATION_BITS for value in made))

    def test_home_network_addresses_are_told_from_the_internet(self):
        for ip in ('127.0.0.1', '192.168.1.20', '10.0.0.5', '169.254.3.3'):
            self.assertTrue(fl.is_local_address(ip), ip)
        for ip in ('8.8.4.4', '1.1.1.1', '86.12.34.56'):
            self.assertFalse(fl.is_local_address(ip), ip)


class AskingWhatAddressTheTankIsSeenAt(unittest.TestCase):

    def _answer(self, ip, port, xor=True):
        if xor:
            value = struct.pack('>BBH', 0, 1, port ^ (fl.STUN_MAGIC >> 16)) + struct.pack(
                '>I', struct.unpack('>I', socket.inet_aton(ip))[0] ^ fl.STUN_MAGIC)
            attribute = struct.pack('>HH', 0x0020, 8) + value
        else:
            attribute = struct.pack('>HH', 0x0001, 8) + struct.pack(
                '>BBH', 0, 1, port) + socket.inet_aton(ip)
        return struct.pack('>HHI', 0x0101, len(attribute), fl.STUN_MAGIC) + b'x' * 12 + attribute

    def test_the_question_says_nothing_about_the_player(self):
        request = fl.stun_request()
        self.assertEqual(len(request), 20)
        self.assertTrue(fl.looks_like_stun(request))
        self.assertEqual(struct.unpack('>HH', request[:4]), (1, 0))

    def test_the_answer_is_read_in_either_form(self):
        self.assertEqual(fl.stun_mapped_address(self._answer('86.12.34.56', 51234)),
                         ('86.12.34.56', 51234))
        self.assertEqual(fl.stun_mapped_address(self._answer('86.12.34.56', 51234, xor=False)),
                         ('86.12.34.56', 51234))

    def test_a_game_message_is_never_mistaken_for_an_answer(self):
        self.assertFalse(fl.looks_like_stun(b'{"node_id": "squid_1", "type": "heartbeat"}'))
        self.assertIsNone(fl.stun_mapped_address(b'x\x9c' + b'\x00' * 40))

    def test_a_tank_finds_its_address_from_its_own_socket(self):
        """Against a stand-in server here, so nothing leaves this machine."""
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(('127.0.0.1', 0))
        server.settimeout(3.0)
        self.addCleanup(server.close)

        def serve():
            try:
                data, addr = server.recvfrom(64)
            except OSError:
                return
            if fl.looks_like_stun(data):
                server.sendto(self._answer('86.12.34.56', 51234), addr)

        threading.Thread(target=serve, daemon=True).start()
        tank = node('squid_stun')
        self.addCleanup(tank.close)
        tank.start_listening()
        found = tank.find_public_endpoint('127.0.0.1', server.getsockname()[1], timeout=3.0)
        self.assertEqual(found, ('86.12.34.56', 51234))
        where = fl.decode_friend_code(tank.friend_code())
        self.assertEqual((where.ip, where.port, where.invitation),
                         ('86.12.34.56', 51234, tank.invitation))

    def test_with_no_answer_the_code_points_at_the_home_network_address(self):
        tank = node('squid_offline')
        self.addCleanup(tank.close)
        self.assertIsNone(tank.public_endpoint)
        where = fl.decode_friend_code(tank.friend_code())
        self.assertEqual((where.ip, where.port), (tank.local_ip, tank.port))


class WhoATankListensTo(unittest.TestCase):

    def setUp(self):
        self.tank = node('squid_home')
        self.addCleanup(self.tank.close)

    def test_the_home_network_is_heard_as_it_always_was(self):
        self.assertTrue(self.tank._admit(('192.168.1.30', 10000), {'node_id': 'a'}))
        self.assertEqual(self.tank.direct_peers, {})

    def test_a_stranger_on_the_internet_is_not_answered(self):
        self.assertFalse(self.tank._admit(STRANGER, {'node_id': 'x'}))
        self.assertFalse(self.tank._admit(STRANGER, {'node_id': 'x', 'invite': 12345}))
        self.assertFalse(self.tank._admit(STRANGER, {'node_id': 'x', 'invite': True}))
        self.assertEqual(self.tank.direct_peers, {})

    def test_someone_showing_this_tanks_invitation_is_let_in_and_stays_in(self):
        self.assertTrue(self.tank._admit(
            STRANGER, {'node_id': 'x', 'invite': self.tank.invitation}))
        self.assertTrue(self.tank.direct_peers[STRANGER]['theirs'])
        self.assertTrue(self.tank._admit(STRANGER, {'node_id': 'x'}))   # no need to show it again

    def test_a_friend_the_player_added_is_heard_without_any_invitation(self):
        self.tank.add_friend(*FRIEND)
        self.assertTrue(self.tank._admit(FRIEND, {'node_id': 'f'}))

    def test_a_friend_whose_router_changed_their_port_is_still_that_friend(self):
        self.tank.add_friend(*FRIEND, invitation=77)
        self.assertTrue(self.tank._admit((FRIEND[0], 53999), {'node_id': 'f'}))
        self.assertEqual(list(self.tank.direct_peers), [(FRIEND[0], 53999)])
        self.assertEqual(self.tank.direct_peers[(FRIEND[0], 53999)]['invitation'], 77)

    def test_a_new_code_shuts_out_anyone_holding_the_old_one(self):
        old = self.tank.invitation
        self.tank.new_friend_code()
        self.assertNotEqual(self.tank.invitation, old)
        self.assertFalse(self.tank._admit(STRANGER, {'node_id': 'x', 'invite': old}))

    def test_trying_invitations_one_after_another_shuts_the_door(self):
        """An invitation is one number in a million. Whoever shows many
        different wrong ones is trying them all: after a few, nobody new is
        let in with a code for a minute - the right one included."""
        from plugins.multiplayer.mp_network_node import WRONG_INVITATIONS_ALLOWED
        right = self.tank.invitation
        wrong = [value for value in range(1, 40) if value != right]
        for value in wrong[:WRONG_INVITATIONS_ALLOWED]:
            self.assertFalse(self.tank._admit(STRANGER, {'node_id': 'x', 'invite': value}))
        self.assertFalse(self.tank._admit(STRANGER, {'node_id': 'x', 'invite': right}))
        self.assertEqual(self.tank.direct_peers, {})
        # ...and it opens again afterwards.
        self.tank._invitations_shut_until = time.time() - 1
        self.assertTrue(self.tank._admit(STRANGER, {'node_id': 'x', 'invite': right}))

    def test_a_friend_with_an_out_of_date_code_does_not_shut_the_door(self):
        """Their game shows the same wrong invitation with every message.
        That is one wrong number, however often it is shown."""
        stale = self.tank.invitation ^ 1
        for _ in range(50):
            self.assertFalse(self.tank._admit(FRIEND, {'node_id': 'f', 'invite': stale}))
        self.assertTrue(self.tank._admit(
            STRANGER, {'node_id': 'x', 'invite': self.tank.invitation}))

    def test_a_friend_already_linked_is_heard_while_the_door_is_shut(self):
        self.tank.add_friend(*FRIEND)
        self.tank._invitations_shut_until = time.time() + 60
        self.assertTrue(self.tank._admit(FRIEND, {'node_id': 'f'}))

    def test_there_is_a_limit_to_how_many_tanks_can_link(self):
        for index in range(MAX_DIRECT_PEERS):
            self.tank.add_friend(f'8.8.8.{index + 1}')
        with self.assertRaises(ValueError):
            self.tank.add_friend('9.9.9.9')
        self.assertFalse(self.tank._admit(
            STRANGER, {'node_id': 'x', 'invite': self.tank.invitation}))

    def test_a_tank_holds_its_own_squid_and_up_to_three_visitors(self):
        self.assertEqual(ConsentPolicy().max_visitors, 3)


class TwoTanksLinkedDirectly(unittest.TestCase):
    """Two real tanks on this machine, on different ports, with no multicast
    between them: everything that arrives came down the direct link."""

    def setUp(self):
        self.mine, self.theirs = node('squid_mine'), node('squid_theirs')
        for tank in (self.mine, self.theirs):
            self.addCleanup(tank.close)
            tank.start_listening()

    def _heard(self, tank, wait=2.0):
        deadline, got = time.time() + wait, []
        while time.time() < deadline and not got:
            got = [m for m, _addr in tank.receive_messages()]
            time.sleep(0.02)
        return got

    def test_a_friend_reached_two_ways_is_heard_once(self):
        """A friend on the same network is reached by multicast and, with
        the invitation added, directly: the same message, differing in that
        one field. Taken as two, a squid asking to come in was admitted
        twice. Two different messages are still two."""
        self.theirs.add_friend('127.0.0.1', self.mine.port)
        message = {'node_id': 'squid_mine', 'timestamp': 1760958000.25, 'type': 'squid_exit',
                   'payload': {'payload': {'node_id': 'squid_mine', 'direction': 'right'}}}
        target = ('127.0.0.1', self.theirs.port)
        self.mine.socket.sendto(self.mine._encode(message), target)
        self.mine.socket.sendto(self.mine._encode(dict(message, invite=4242)), target)
        deadline, got = time.time() + 2.0, []
        while time.time() < deadline:
            got += [m for m, _addr in self.theirs.receive_messages()]
            time.sleep(0.02)
        self.assertEqual([m['type'] for m in got], ['squid_exit'])
        self.assertEqual(self.theirs.packets_dropped_duplicate, 1)

        self.mine.socket.sendto(self.mine._encode(dict(message, timestamp=1760958003.5)), target)
        self.assertEqual([m['type'] for m in self._heard(self.theirs)], ['squid_exit'])

    def test_entering_a_friends_code_links_both_tanks(self):
        code = self.theirs.friend_code()                 # they read it out...
        where = fl.parse_friend(code)                    # ...I type it in
        self.mine.add_friend('127.0.0.1', self.theirs.port, where.invitation)

        self.mine.send_message('heartbeat', {'node_id': 'squid_mine'})
        got = self._heard(self.theirs)
        self.assertEqual([m['type'] for m in got], ['heartbeat'])
        self.assertEqual(got[0]['invite'], self.theirs.invitation)

        # Their tank learned where I am from my showing their invitation, so
        # its own messages reach me without my address ever being typed there.
        self.assertIn(('127.0.0.1', self.mine.port), self.theirs.direct_peers)
        self.theirs.send_message('heartbeat', {'node_id': 'squid_theirs'})
        self.assertEqual([m['node_id'] for m in self._heard(self.mine)], ['squid_theirs'])

    def test_a_batch_goes_down_the_link_too(self):
        self.mine.add_friend('127.0.0.1', self.theirs.port, self.theirs.invitation)
        self.mine.send_message_batch([('squid_move', {'x': 1}), ('object_sync', {})])
        got = self._heard(self.theirs)
        self.assertTrue(got and got[0].get('batch'))

    def test_removing_a_friend_stops_the_messages(self):
        self.mine.add_friend('127.0.0.1', self.theirs.port, self.theirs.invitation)
        self.assertTrue(self.mine.remove_friend('127.0.0.1', self.theirs.port))
        self.mine.send_message('heartbeat', {'node_id': 'squid_mine'})
        self.assertEqual(self._heard(self.theirs, wait=0.4), [])


class ThePluginsSideOfIt(unittest.TestCase):

    def _plugin(self):
        from types import SimpleNamespace
        from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
        saved = []
        config = SimpleNamespace(
            get_multiplayer_friends=lambda: [('1.1.1.1', 10000, 5)],
            set_multiplayer_friends=saved.append,
            get_multiplayer_stun_server=lambda: '')
        plugin = MultiplayerPlugin.__new__(MultiplayerPlugin)
        plugin.tamagotchi_logic = SimpleNamespace(config_manager=config)
        plugin.network_node = node('squid_plugin')
        self.addCleanup(plugin.network_node.close)
        return plugin, saved

    def test_friends_from_last_time_are_friends_still(self):
        plugin, _saved = self._plugin()
        plugin._restore_friends()
        self.assertEqual([(f['ip'], f['port']) for f in plugin.friends()],
                         [('1.1.1.1', 10000)])

    def test_connecting_by_code_or_by_address_says_what_to_do_next(self):
        plugin, saved = self._plugin()
        ok, said = plugin.connect_to_friend(fl.encode_friend_code('8.8.4.4', 10000, 99))
        self.assertTrue(ok)
        self.assertIn('enter your code too', said)
        ok, said = plugin.connect_to_friend('9.9.9.9:4242')
        self.assertTrue(ok)
        self.assertIn('add your address as well', said)
        self.assertEqual(saved[-1], [('8.8.4.4', 10000, 99), ('9.9.9.9', 4242, 0)])

    def test_a_mistyped_code_is_explained_and_changes_nothing(self):
        plugin, saved = self._plugin()
        ok, said = plugin.connect_to_friend('not a code')
        self.assertFalse(ok)
        self.assertTrue(said.endswith('.'))
        self.assertEqual(saved, [])
        self.assertEqual(plugin.friends(), [])

    def test_someone_who_joined_with_my_code_is_not_saved_as_my_friend(self):
        plugin, saved = self._plugin()
        plugin.network_node._admit(STRANGER, {'node_id': 'x',
                                              'invite': plugin.network_node.invitation})
        plugin.connect_to_friend('9.9.9.9')
        self.assertEqual(saved[-1], [('9.9.9.9', 10000, 0)])


if __name__ == '__main__':
    unittest.main()
