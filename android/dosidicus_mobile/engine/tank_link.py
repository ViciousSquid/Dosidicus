"""This tank on the game's own network: the same one the desktop game uses.

A squid on a phone and a squid on a computer visit each other's tanks, and
neither can tell what kind of device the other lives on. That works because
this is not a phone version of the protocol - it IS the protocol
(plugins/multiplayer/docs/protocol.md), spoken with the desktop's own
classes: the same socket code (NetworkNode), the same friend codes
(friend_link), the same consent rule, the same host body and visiting mind.
Only what a tank is made of differs, and that stays behind `sim`.

What the link does, and nothing more:

  * says the tank is here (a heartbeat every few seconds) and hears who else
    is - on the home network by itself, across the internet through friends
    the player has linked with a friend code;
  * tells the squid's brain that another aquarium is nearby (the
    `aquarium_heard` percept). Whether the squid ever goes is its own
    network's decision (src/venturing.py), exactly as on desktop;
  * when the squid has swum to the side of its tank, asks the tank it heard
    most recently to let it in (`squid_exit`), and hands the answer and every
    frame after it to the visit (peer_visit.PeerVisit);
  * when somebody else's squid asks to come in, decides (ConsentPolicy: the
    resident alive, room in the tank, the same protocol), answers, and gives
    it a body here.

No Kivy and no Android in this file: it runs anywhere Python does, which is
how it is tested against a real desktop game on one machine.
"""
import json
import logging
import os
import time
import uuid
from collections import deque

from . import shared  # noqa: F401 - locate src and the Qt-free multiplayer modules
from plugins.multiplayer import friend_link
from plugins.multiplayer.consent import (ConsentDecision, ConsentPolicy,
                                          REASON_ACCEPTED, REASON_CLOSED)
from plugins.multiplayer.identity import SquidIdentity
from plugins.multiplayer.mp_network_node import NetworkNode
from plugins.multiplayer.remote_protocol import REMOTE_MIND_MESSAGES
from src.venturing import HEARD_WITHIN, peer_heard

from .peer_visit import PeerVisit

#: As on desktop (mp_plugin_logic): how often the tank says it is here, how
#: often a squid waiting at the side asks again, and the behavioural cadence.
HEARTBEAT_SECONDS = 8.0
EXIT_RETRY_SECONDS = 3.0
SENSE_SECONDS = 0.5
#: A friend counts as connected while heard within this long.
CONNECTED_WITHIN = 15.0
#: The body size sent with a departure. The host draws its own picture of the
#: visitor; this only places it at the edge it comes in by.
BODY_SIZE = 56
STUN_SERVER = 'stun.l.google.com:19302'


class TankLink:
    """One tank's place on the network. Call tick() often; it never blocks."""

    def __init__(self, sim, port=None, store=None, node=None, clock=time.time,
                 logger=None, stun_server=STUN_SERVER):
        self.sim = sim
        self.clock = clock
        self.store = store                    # where linked friends are remembered
        self.stun_server = stun_server
        self.logger = logger or logging.getLogger('dosidicus.tank_link')
        self.node = node or NetworkNode(f"squid_{uuid.uuid4().hex[:6]}",
                                        logger=self.logger, port=port)
        self.consent = ConsentPolicy(clock=clock)      # open, three visitors
        self.peers_last_heard = {}            # node id -> when its heartbeat was heard
        self.hosted = {}                      # visitor uuid -> (node id, PeerVisit)
        self.away = None                      # this squid's own visit, while it is out
        self.asked = ''                       # the node it asked to visit
        self.events = deque(maxlen=40)        # what happened, in words, for the screen
        self._last_heartbeat = self._last_exit = self._last_sense = 0.0
        self.running = False

    # ------------------------------------------------------------ lifecycle
    def start(self):
        """Open the socket. True if the tank is now on the network."""
        if not self.running:
            self.node.auto_reconnect = True
            self.running = bool(self.node.start_listening() or self.node.is_connected)
            if self.running:
                self._restore_friends()
                self._attach(self.sim)
                self._say(f"On the network, port {self.node.port}.")
        return self.running

    def stop(self):
        """Leave the network: every visit ends, and no aquarium is nearby."""
        for _node, visit in list(self.hosted.values()):
            visit.close()
        self.hosted.clear()
        if self.away is not None:
            self.away.close()
            self.away = None
        self.peers_last_heard.clear()
        self._sense(force=True)
        if self.running:
            try:
                self.node.send_message('player_leave', {
                    'node_id': self.node.node_id, 'reason': 'plugin_disabled'})
            except Exception:
                pass
        squid = getattr(self.sim, 'squid', None)
        if squid is not None:
            squid.can_venture = False
        if getattr(self.sim, 'tank_link', None) is self:
            self.sim.tank_link = None
        self.node.close()
        self.running = False

    def use_simulation(self, sim):
        """The app has loaded or begun another game: the link carries on."""
        for _node, visit in list(self.hosted.values()):
            visit.close()
        self.hosted.clear()
        if self.away is not None:
            self.away.close()
            self.away = None
        self.sim = sim
        if self.running:
            self._attach(sim)

    def _attach(self, sim):
        sim.tank_link = self
        sim.squid.can_venture = True

    # ------------------------------------------------------------- the tick
    def tick(self, dt=0.0):
        if not self.running:
            return
        now = self.clock()
        self.sim.squid.can_venture = True       # a newly hatched squid too
        for message, addr in self.node.receive_messages():
            try:
                self._handle(message, addr, now)
            except Exception as exc:              # nothing from the wire may stop the game
                self.logger.warning(f"Could not take a {message.get('type')!r}: {exc}")
        self._prune()
        if now - self._last_heartbeat >= HEARTBEAT_SECONDS:
            self.say_hello(now)
        self._sense(now)
        self._ask_to_visit(now)

    def say_hello(self, now=None):
        """The heartbeat. Also what opens the way through a router to a
        friend just linked, which is why linking sends one at once."""
        self._last_heartbeat = self.clock() if now is None else now
        squid = self.sim.squid
        return self._post('heartbeat', {'node_id': self.node.node_id, 'status': 'active',
                                        'squid_pos': [round(squid.x, 1), round(squid.y, 1)]})

    def _post(self, kind, payload):
        try:
            return bool(self.node.send_message(kind, payload))
        except Exception as exc:
            self.logger.warning(f"Could not send {kind}: {exc}")
            return False

    def _say(self, text):
        self.events.append((self.clock(), text))
        self.logger.info(text)

    def _prune(self):
        for peer_uuid, (_node, visit) in list(self.hosted.items()):
            if visit.closed:
                del self.hosted[peer_uuid]
                self.consent.forget(peer_uuid)
                self._say(f"{visit.actor.identity.name if visit.actor else 'A visitor'} has left.")
        if self.away is not None and (self.away.closed or not self.away.away):
            if not self.away.closed:
                self.away.close(notify=False)      # its own mind came home
            self.away = None
            self.asked = ''
            self._say(f"{self.sim.squid.name} is home again.")

    # ------------------------------------------------- hearing other tanks
    def _sense(self, now=None, force=False):
        """Whether another aquarium is nearby: the squid's own percept. The
        first time, it grows the sense for it; what it does then is its own."""
        now = self.clock() if now is None else now
        if not force and now - self._last_sense < SENSE_SECONDS:
            return
        self._last_sense = now
        brain = getattr(getattr(self.sim, 'squid', None), 'brain', None)
        if hasattr(brain, 'perceive'):
            brain.perceive('aquarium_heard', peer_heard(self.peers_last_heard, now))

    def tanks_heard(self, now=None):
        now = self.clock() if now is None else now
        return {node: at for node, at in self.peers_last_heard.items()
                if now - at <= HEARD_WITHIN}

    def visit_destination(self, now=None):
        """The aquarium a squid venturing out asks: the one heard most recently."""
        heard = self.tanks_heard(now)
        return max(heard, key=heard.get) if heard else ''

    # ------------------------------------------------------------ messages
    def _handle(self, message, addr, now):
        kind = message.get('type')
        payload = message.get('payload')
        sender = message.get('node_id')
        if not isinstance(payload, dict) or not sender:
            return
        if kind == 'heartbeat':
            node_id = payload.get('node_id')
            if node_id and node_id != self.node.node_id:
                if node_id not in self.peers_last_heard:
                    self._say("Another tank is on the network.")
                self.peers_last_heard[str(node_id)] = now
        elif kind == 'squid_exit':
            self._on_exit(payload.get('payload'), now)
        elif kind == 'visit_response':
            self._on_response(sender, payload)
        elif kind in REMOTE_MIND_MESSAGES:
            self._on_visit_message(sender, kind, payload)

    def _on_visit_message(self, sender, kind, payload):
        """perception_frame, action_intent, consequence, visit_end, gamete:
        everything is sent to every tank, so each is taken only by the visit
        it belongs to - this squid's own, from the tank it asked; or a
        visitor's, from the tank that visitor came from."""
        if self.away is not None and sender == self.asked \
                and kind in ('perception_frame', 'consequence', 'visit_end'):
            if kind == 'visit_end' and not self.away.mind.visit_id:
                return
            if self.away.handle(kind, payload):
                return
        visit_id = payload.get('visit_id')
        for node_id, visit in list(self.hosted.values()):
            if node_id == sender and visit.actor is not None \
                    and visit.actor.visit_id == visit_id:
                visit.handle(kind, payload)
                return

    # ------------------------------------------------- somebody is at the door
    def _resident_cannot_host(self):
        squid = self.sim.squid
        return bool(squid.lifecycle.is_dead or getattr(self.sim, 'hatching', False))

    def _on_exit(self, exit_data, now):
        """Another tank's squid has reached the side and is asking to come in."""
        if not isinstance(exit_data, dict):
            return
        source = exit_data.get('node_id')
        if not source or source == self.node.node_id:
            return
        addressed = exit_data.get('to')
        if addressed and addressed != self.node.node_id:
            return                                  # asking some other tank
        identity = SquidIdentity.from_payload(exit_data.get('identity') or {})
        peer_uuid = getattr(identity, 'uuid', '') or ''
        if peer_uuid and peer_uuid in self.hosted and not self.hosted[peer_uuid][1].closed \
                and self.hosted[peer_uuid][0] == source:
            # It is already in: its home did not hear the answer. Say it again.
            self._post('visit_response', {'accepted': True, 'reason': REASON_ACCEPTED,
                                          'peer_uuid': peer_uuid, 'to': source})
            return
        if self._resident_cannot_host():
            decision = ConsentDecision(False, REASON_CLOSED, peer_uuid)
        else:
            decision = self.consent.evaluate(identity, current_visitors=len(self.hosted))
        self._post('visit_response', dict(decision.to_payload(), to=source))
        if not decision.accepted:
            self._say(f"Refused {getattr(identity, 'name', 'a squid')}: {decision.reason}.")
            return
        width, height = self.sim.tank_size
        # In by the side opposite the one it left by, at the height it left at.
        from_left = exit_data.get('direction') == 'right'
        try:
            there = float(exit_data.get('window_height') or 0.0)
            level = float((exit_data.get('position') or {}).get('y', 0.0)) / there if there else 0.5
        except (TypeError, ValueError):
            level = 0.5
        y = min(max(level, 0.2), 0.7) * height
        visit = PeerVisit(self.sim, hosting=True, clock=self.clock,
                          post=self._post, link_timeout=None)
        if not visit.admit(identity, x=80.0 if from_left else width - 80.0, y=y,
                           facing='right' if from_left else 'left'):
            visit.close(notify=False)
            return
        self.hosted[peer_uuid] = (source, visit)
        visit.send_frame()          # straight away: its brain has nothing to go on yet
        self._say(f"{identity.name} has come to visit.")

    # ---------------------------------------------------- this squid goes out
    def _ask_to_visit(self, now):
        """The squid has taken itself to the side of its tank (Squid.at_side):
        ask the tank heard most recently to let it in."""
        squid = self.sim.squid
        side = getattr(squid, 'at_side', None)
        if side is None or self.away is not None or self.sim.visiting() is not None:
            return
        if now - self._last_exit < EXIT_RETRY_SECONDS:
            return
        if squid.is_sleeping or not squid.lifecycle.can_visit or not squid.is_venturing():
            return
        destination = self.visit_destination(now)
        if not destination:
            return
        identity = SquidIdentity.from_squid(squid)
        if identity is None:
            return
        self._last_exit = now
        self.asked = destination
        width, height = self.sim.tank_size
        self._post('squid_exit', {'payload': {
            'node_id': self.node.node_id, 'direction': side,
            'position': {'x': round(squid.x - BODY_SIZE / 2, 1),
                         'y': round(squid.y - BODY_SIZE / 2, 1)},
            'color': list(identity.tint or (200, 200, 200)),
            'squid_width': BODY_SIZE, 'squid_height': BODY_SIZE,
            'window_width': width, 'window_height': height,
            'identity': identity.to_payload(), 'to': destination}})

    def _on_response(self, sender, payload):
        """The tank it asked has answered."""
        squid = self.sim.squid
        if sender != self.asked or self.away is not None:
            return
        mine = payload.get('to') == self.node.node_id
        if not (payload.get('peer_uuid') == str(squid.uuid)
                or (mine and not payload.get('accepted'))):
            return                                   # somebody else's answer
        if not payload.get('accepted'):
            self._say(f"The other tank said no ({payload.get('reason')}).")
            return
        if not squid.lifecycle.can_visit or self._resident_cannot_host():
            return
        self.away = PeerVisit(self.sim, hosting=False, clock=self.clock, post=self._post)
        self.away.mind.begin_visit(None)             # the first frame says whose tank
        squid.at_side = None
        self._say(f"{squid.name} has gone to visit another tank.")

    # ------------------------------------------------------------- friends
    def friend_code(self):
        return self.node.friend_code()

    def friend_code_known(self):
        """Has the tank found the address it is seen at from the internet?"""
        return bool(self.node.public_endpoint)

    def find_friend_code(self):
        """Ask a public server what address this tank is seen at (one
        twenty-byte question that says nothing about the player) and return
        the friend code built from it. Takes a moment: call it off the UI
        thread."""
        if self.stun_server:
            host, _, port = self.stun_server.partition(':')
            self.node.find_public_endpoint(host, int(port or 3478))
        return self.node.friend_code()

    def friend_code_note(self):
        if self.friend_code_known():
            ip, port = self.node.public_endpoint
            return (f"This code points at {ip}:{port}, the address your tank is "
                    f"seen at from the internet. Give it only to someone you "
                    f"would give that address to.")
        return ("Your internet address could not be found (offline, or the "
                "address server is blocked), so this code points at your "
                "address on your own network. It will work for a friend on "
                "the same Wi-Fi.")

    def new_friend_code(self):
        return self.node.new_friend_code()

    def connect_to_friend(self, text):
        """Link to a friend's tank from their friend code or IP address.
        Returns (ok, what to tell the player)."""
        try:
            where = friend_link.parse_friend(text)
            self.node.add_friend(where.ip, where.port, where.invitation)
        except (friend_link.FriendCodeError, ValueError) as exc:
            return False, str(exc).capitalize() + "."
        self._remember_friends()
        self.say_hello()
        if where.invitation:
            return True, (f"Linked to {where.ip}:{where.port}. If their tank "
                          f"does not answer, ask them to enter your code too.")
        return True, (f"Linked to {where.ip}:{where.port}. Without a friend "
                      f"code they have to add your address as well.")

    def forget_friend(self, ip, port=None):
        gone = self.node.remove_friend(ip, port)
        if gone:
            self._remember_friends()
        return gone

    def friends(self, now=None):
        """The tanks this one is linked to, for the Friends screen."""
        now = time.time() if now is None else now     # the node stamps with time.time
        rows = []
        for (ip, port), peer in self.node.direct_peers.items():
            heard = peer.get('last_heard', 0.0)
            state = ('no answer yet' if not heard else 'connected'
                     if now - heard < CONNECTED_WITHIN else f'last heard {int(now - heard)}s ago')
            rows.append({'ip': ip, 'port': port, 'last_heard': heard, 'state': state,
                         'theirs': bool(peer.get('theirs'))})
        return rows

    def _remember_friends(self):
        """Only the ones the player added: someone who joined with this
        tank's code is let in while they keep showing it, not for ever."""
        if not self.store:
            return
        friends = [[ip, port, peer.get('invitation', 0)]
                   for (ip, port), peer in self.node.direct_peers.items()
                   if not peer.get('theirs')]
        try:
            with open(self.store + '.tmp', 'w') as handle:
                json.dump({'friends': friends}, handle)
            os.replace(self.store + '.tmp', self.store)
        except OSError as exc:
            self.logger.warning(f"Could not save the friends list: {exc}")

    def _restore_friends(self):
        if not self.store or not os.path.exists(self.store):
            return
        try:
            with open(self.store) as handle:
                friends = json.load(handle).get('friends', [])
            for ip, port, invitation in friends:
                self.node.add_friend(str(ip), int(port), int(invitation))
        except (OSError, ValueError, TypeError) as exc:
            self.logger.warning(f"Could not read the friends list: {exc}")

    # -------------------------------------------------------------- status
    def status_text(self):
        """One line for the screen: what the link is doing now."""
        if not self.running:
            return "Not on the network."
        heard = len(self.tanks_heard())
        if self.away is not None:
            return self.sim.visiting_text()
        visitors = [v.actor.identity.name for _n, v in self.hosted.values() if v.actor]
        if visitors:
            return "Visiting you: " + ", ".join(visitors)
        if heard:
            return (f"{heard} other tank{'s' if heard != 1 else ''} nearby. "
                    f"{self.sim.squid.name} decides for itself whether to visit.")
        return "No other tank heard yet."
