#!/usr/bin/env python3
"""An internet session, watched: up to four games in four homes, linked only
by friend codes, with nothing telling any squid what to do.

A real internet cannot be had on one machine, so this builds a small one out
of Linux network namespaces - the same kernel code a home router runs:

    home 1  192.168.1.2 --[router 1: NAT]-- 100.64.1.2 --+
    home 2  192.168.1.2 --[router 2: NAT]-- 100.64.2.2 --+-- "the internet"
    home 3  192.168.1.2 --[router 3: NAT]-- 100.64.3.2 --+    100.64.0.1: STUN
    home 4  192.168.1.2 --[router 4: NAT]-- 100.64.4.2 --+

  * Every home has the same private address, as real homes do, and its own
    router that rewrites it to the router's outside address (masquerade) and
    lets nothing in from outside that the home did not first send to.
  * No home can hear another's multicast: the tanks find each other only
    because the players exchange friend codes, as they would in a chat.
  * Each game asks the STUN server what address it is seen at, builds its
    friend code from the answer, and the codes are passed round.

Then the session is left alone for --minutes and everything that happens is
written down as it happens: links coming up, squid leaving and arriving,
what they grow, think, remember and believe, and every fight with its
reason. Nothing is nudged: the squid are new hatchlings with the drives the
game gave them, time runs at the game's own speed, and the chance of mating
is the game's own. What is chosen is what four players would choose: each
squid's name, its personality, and for three of them a colour.

What this does not show: a real home router. These routers keep a tank's
port the same whoever it talks to, which is what most home routers do and
what makes "both players enter each other's code" work; a router that gives
every destination a different port (some mobile and office networks) would
need the port forwarded instead.

Needs Linux and root (network namespaces). Run:

    sudo QT_QPA_PLATFORM=offscreen python tools/internet_session.py OUTPUT_DIR
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

PREFIX = 'dsq'
STUN_ADDRESS, STUN_PORT = '100.64.0.1', 3478
#: The four players' squid: name, personality, and the colour its player gave
#: it on the About tab (None: left as it hatched).
PLAYERS = (('Ziggy', 'ADVENTUROUS', None), ('Inky', 'TIMID', (120, 170, 255)),
           ('Pesto', 'GREEDY', (255, 105, 180)), ('Bolt', 'ENERGETIC', (120, 220, 140)))
#: The screen the games lay themselves out for (they draw offscreen).
SCREEN = '2560x1440'


# ---------------------------------------------------------------------------
# The private internet
# ---------------------------------------------------------------------------
def sh(*command, check=True, quiet=False):
    result = subprocess.run(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(command)}: {result.stderr.strip()}")
    return result.stdout if not quiet else ''


def inside(namespace, *command, **kwargs):
    return sh('ip', 'netns', 'exec', namespace, *command, **kwargs)


def tear_down(count=8):
    for name in [f'{PREFIX}-net'] + [f'{PREFIX}-{kind}{i}' for i in range(1, count + 1)
                                     for kind in ('r', 'h')]:
        sh('ip', 'netns', 'del', name, check=False)


def build_internet(homes):
    """Make the namespaces above. Returns what was built, for the record."""
    tear_down()
    net = f'{PREFIX}-net'
    sh('ip', 'netns', 'add', net)
    inside(net, 'ip', 'link', 'set', 'lo', 'up')
    inside(net, 'ip', 'addr', 'add', f'{STUN_ADDRESS}/32', 'dev', 'lo')
    inside(net, 'sysctl', '-qw', 'net.ipv4.ip_forward=1')
    built = []
    for i in range(1, homes + 1):
        router, home = f'{PREFIX}-r{i}', f'{PREFIX}-h{i}'
        outside, private = f'100.64.{i}.2', '192.168.1.2'
        sh('ip', 'netns', 'add', router)
        sh('ip', 'netns', 'add', home)
        # router <-> the internet
        sh('ip', 'link', 'add', f'{PREFIX}w{i}', 'type', 'veth', 'peer', 'name', f'{PREFIX}n{i}')
        sh('ip', 'link', 'set', f'{PREFIX}w{i}', 'netns', router)
        sh('ip', 'link', 'set', f'{PREFIX}n{i}', 'netns', net)
        inside(net, 'ip', 'addr', 'add', f'100.64.{i}.1/24', 'dev', f'{PREFIX}n{i}')
        inside(net, 'ip', 'link', 'set', f'{PREFIX}n{i}', 'up')
        inside(router, 'ip', 'link', 'set', f'{PREFIX}w{i}', 'name', 'wan')
        inside(router, 'ip', 'addr', 'add', f'{outside}/24', 'dev', 'wan')
        inside(router, 'ip', 'link', 'set', 'wan', 'up')
        inside(router, 'ip', 'link', 'set', 'lo', 'up')
        inside(router, 'ip', 'route', 'add', 'default', 'via', f'100.64.{i}.1')
        # home <-> router
        sh('ip', 'link', 'add', f'{PREFIX}l{i}', 'type', 'veth', 'peer', 'name', f'{PREFIX}e{i}')
        sh('ip', 'link', 'set', f'{PREFIX}l{i}', 'netns', router)
        sh('ip', 'link', 'set', f'{PREFIX}e{i}', 'netns', home)
        inside(router, 'ip', 'link', 'set', f'{PREFIX}l{i}', 'name', 'lan')
        inside(router, 'ip', 'addr', 'add', '192.168.1.1/24', 'dev', 'lan')
        inside(router, 'ip', 'link', 'set', 'lan', 'up')
        inside(home, 'ip', 'link', 'set', f'{PREFIX}e{i}', 'name', 'eth0')
        inside(home, 'ip', 'addr', 'add', f'{private}/24', 'dev', 'eth0')
        inside(home, 'ip', 'link', 'set', 'eth0', 'up')
        inside(home, 'ip', 'link', 'set', 'lo', 'up')
        inside(home, 'ip', 'route', 'add', 'default', 'via', '192.168.1.1')
        # The router: forward and rewrite what the home sends out; let back in
        # only answers to it; answer nothing itself.
        inside(router, 'sysctl', '-qw', 'net.ipv4.ip_forward=1')
        inside(router, 'iptables', '-t', 'nat', '-A', 'POSTROUTING', '-o', 'wan',
               '-j', 'MASQUERADE')
        inside(router, 'iptables', '-A', 'FORWARD', '-i', 'wan', '-m', 'conntrack',
               '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT')
        inside(router, 'iptables', '-A', 'FORWARD', '-i', 'wan', '-j', 'DROP')
        inside(router, 'iptables', '-A', 'INPUT', '-i', 'wan', '-j', 'DROP')
        built.append({'home': i, 'private_address': private, 'router_outside': outside})
    return built


def check_isolation(homes):
    """Proof the homes are apart: a home can reach the STUN server, cannot
    reach another home's private address (it is its own), and gets no answer
    from another home's router."""
    found = {}
    home = f'{PREFIX}-h1'
    probe = ("import socket,sys; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.settimeout(1.5);"
             "s.sendto(b'hello',(sys.argv[1],int(sys.argv[2])));\n"
             "try:\n    s.recvfrom(64); print('answered')\nexcept Exception as e:\n"
             "    print('no answer')")
    found['home 1 -> router 2 outside address, unasked'] = inside(
        home, sys.executable, '-c', probe, '100.64.2.2', '10000', check=False).strip()
    return found


# ---------------------------------------------------------------------------
# The STUN server on the internet
# ---------------------------------------------------------------------------
def stun_server(log_path):
    from plugins.multiplayer.friend_link import STUN_MAGIC
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((STUN_ADDRESS, STUN_PORT))
    with open(log_path, 'a', buffering=1) as log:
        log.write(json.dumps({'at': time.time(), 'listening': f'{STUN_ADDRESS}:{STUN_PORT}'}) + '\n')
        while True:
            data, (ip, port) = sock.recvfrom(2048)
            if len(data) < 20 or struct.unpack('>I', data[4:8])[0] != STUN_MAGIC:
                continue
            xport = port ^ (STUN_MAGIC >> 16)
            xip = struct.unpack('>I', socket.inet_aton(ip))[0] ^ STUN_MAGIC
            attribute = struct.pack('>HHBBHI', 0x0020, 8, 0, 0x01, xport, xip)
            answer = struct.pack('>HHI', 0x0101, len(attribute), STUN_MAGIC) + data[8:20] + attribute
            sock.sendto(answer, (ip, port))
            log.write(json.dumps({'at': time.time(), 'asked_from': f'{ip}:{port}'}) + '\n')


# ---------------------------------------------------------------------------
# One game, in one home
# ---------------------------------------------------------------------------
def worker(output, number):
    name, personality_name, colour = PLAYERS[number - 1]
    folder = output / f'home{number}'
    shots = output / 'shots'
    folder.mkdir(parents=True, exist_ok=True)
    shots.mkdir(parents=True, exist_ok=True)
    # The player's settings: where to ask "what is my address?".
    config = (ROOT / 'config.ini').read_text()
    config = config.replace('[Multiplayer]\n',
                            f'[Multiplayer]\nstun_server = {STUN_ADDRESS}:{STUN_PORT}\n', 1)
    (folder / 'config.ini').write_text(config)
    os.environ['DOSIDICUS_SCREEN'] = SCREEN

    from test_lan_round_trip import _setup, _shutdown
    app, main = _setup(folder)
    from PyQt5 import QtCore
    from src.personality import Personality
    from src import social_knowledge
    window = main.MainWindow(specified_personality=Personality[personality_name])
    window.show()
    started = time.monotonic()
    state = {'home': number, 'name': name, 'personality': personality_name.lower(),
             'stage': 'hatching', 'events': [], 'trace': [], 'shots': {}, 'plugin': None}
    seen = {'neurons': None, 'heard': set(), 'links': set(), 'visitors': {}, 'away': False,
            'thoughts': 0, 'memories': set(), 'beliefs': set(), 'revised': 0, 'second': -1,
            'shot_minute': -1, 'fights': set(), 'habits': set()}
    timer = QtCore.QTimer()

    def event(kind, text, **more):
        state['events'].append(dict(at=time.time(), home=number, who=name, kind=kind,
                                    text=text, **more))

    def write():
        data = {k: v for k, v in state.items() if k != 'plugin'}
        temporary = folder / 'status.tmp'
        temporary.write_text(json.dumps(data, indent=1, default=str))
        temporary.replace(folder / 'status.json')

    def shot(tag, caption, widget=None):
        key = f'home{number}-{tag}'
        if key in state['shots']:
            return
        (widget or window).grab().save(str(shots / f'{key}.png'))
        state['shots'][key] = {'at': time.time(), 'caption': caption}

    report_message = window.user_interface.show_message

    def show_message(message, *a, **k):
        event('message', str(message))
        return report_message(message, *a, **k)
    window.user_interface.show_message = show_message

    def brain():
        return window.brain_window.brain_widget

    def memories():
        manager = getattr(window.squid, 'memory_manager', None)
        try:
            return list(manager.get_all_short_term_memories(raw=True)) if manager else []
        except Exception:
            return []

    def watch(plugin):
        squid, b, node = window.squid, brain(), plugin.network_node
        # links coming up through the routers
        for (ip, port), peer in list(node.direct_peers.items()):
            if peer.get('last_heard') and (ip, port) not in seen['links']:
                seen['links'].add((ip, port))
                event('link', f"hears the tank at {ip}:{port} through its router"
                      + (" (they joined with this tank's code)" if peer.get('theirs') else ''))
        heard = set(plugin._peers_last_heard)
        for node_id in sorted(heard - seen['heard']):
            event('heard', 'now knows of another aquarium', node_id=node_id)
        seen['heard'] = heard
        # what it has grown
        neurons = set(b.neuron_positions)
        if seen['neurons'] is not None:
            for neuron in sorted(neurons - seen['neurons']):
                why = ''
                try:
                    why = social_knowledge._born_because(b, neuron) or ''
                except Exception:
                    pass
                event('grew', f'grew the neuron {neuron}' + (f' - {why}' if why else ''),
                      neuron=neuron)
                state['pending_brain_shot'] = neuron
            for neuron in sorted(seen['neurons'] - neurons):
                event('lost', f'lost the neuron {neuron}', neuron=neuron)
        seen['neurons'] = neurons
        # leaving and coming home
        away = bool(plugin.visitor_mind.perception.away)
        if away != seen['away']:
            seen['away'] = away
            if away:
                event('left', 'swam out of its own tank to visit another',
                      to_node=plugin._asked_to_visit)
                shot(f'empty-{len(state["shots"])}', f"{name}'s tank after it left")
            else:
                event('home', 'came home')
                shot(f'home-{len(state["shots"])}', f'{name} home again')
        # visitors in this tank
        visitors = {str(actor.identity.uuid): actor.identity.name
                    for actor in plugin.host_body.visitors.values()}
        for uuid, visitor in visitors.items():
            if uuid not in seen['visitors']:
                event('arrival', f'{visitor} arrived in this tank', visitor=visitor,
                      squid_in_tank=1 + len(visitors) - (1 if away else 0))
                state['pending_visitor_shot'] = time.monotonic() + 2.5
        for uuid, visitor in seen['visitors'].items():
            if uuid not in visitors:
                event('departure', f'{visitor} left this tank', visitor=visitor)
        seen['visitors'] = visitors
        # what it thinks
        thoughts = list(getattr(b, 'social_thoughts', None) or ())
        for entry in thoughts[seen['thoughts']:]:
            text = entry[1] if isinstance(entry, (tuple, list)) and len(entry) > 1 else str(entry)
            event('thought', str(text))
        seen['thoughts'] = len(thoughts)
        # what it remembers of other squid, fights among it
        for memory in memories():
            key = str(memory.get('key') or '')
            stamp = (key, memory.get('timestamp'))
            if stamp in seen['memories'] or not social_knowledge.is_social_memory(memory):
                continue
            seen['memories'].add(stamp)
            try:
                described = social_knowledge.describe_memory(memory)
            except Exception:
                described = None
            text = described if isinstance(described, str) else (
                ' - '.join(str(part) for part in described if part) if described else key)
            event('fight' if key.startswith('fight:') else 'memory', text, key=key)
            if key.startswith('fight:'):
                shot(f'fight-{len(seen["fights"]) + 1}', f"In {name}'s tank: {text}")
                seen['fights'].add(key)
        # what it believes about its world, and where it changed its mind
        ledger = getattr(b, 'causal_learning', None)
        if ledger is not None:
            try:
                for belief in ledger.beliefs():
                    statement = str(belief.get('statement') or belief)
                    if statement not in seen['beliefs']:
                        seen['beliefs'].add(statement)
                        event('belief', f'has come to believe: {statement}')
                revised = list(ledger.revised)
                for record in revised[seen['revised']:]:
                    event('revised', 'changed its mind: ' + str(record.get('statement')
                                                                 or record.get('was') or record))
                seen['revised'] = len(revised)
            except Exception:
                pass

    def trace(plugin):
        squid = window.squid
        state['trace'].append({
            'at': round(time.time(), 1), 'status': str(squid.status),
            'hunger': round(squid.hunger), 'anxiety': round(squid.anxiety),
            'happiness': round(squid.happiness), 'health': round(squid.health),
            'curiosity': round(squid.curiosity), 'sleepiness': round(squid.sleepiness),
            'away': seen['away'], 'visitors': sorted(seen['visitors'].values()),
            'why_not_leaving': squid.why_not_venturing() if not seen['away'] else ''})

    def finish(plugin):
        squid, b = window.squid, brain()
        known = {}
        try:
            known = social_knowledge.knowledge(b, memories())
        except Exception as exc:                        # noqa: BLE001
            known = {'error': repr(exc)}
        node = plugin.network_node
        state['final'] = {
            'neurons': sorted(b.neuron_positions),
            'social_knowledge': known,
            'squid': {'hunger': round(squid.hunger), 'anxiety': round(squid.anxiety),
                      'happiness': round(squid.happiness), 'health': round(squid.health)},
            'links': [{'address': f'{ip}:{port}', 'heard': bool(peer.get('last_heard')),
                       'they_joined_with_my_code': bool(peer.get('theirs'))}
                      for (ip, port), peer in node.direct_peers.items()],
            'packets_refused': node.packets_refused,
            'away_at_the_end': seen['away'],
        }
        shot('end', f"{name}'s tank at the end")
        window.brain_window.resize(1300, 1000)
        window.brain_window.show()

    def tick():
        now = time.monotonic() - started
        try:
            squid = window.squid
            plugin = state['plugin']
            if plugin is None:
                if now > 9 and window.splash._ended:
                    squid.name = name
                    if colour:                  # its player's choice, as on the About tab
                        from PyQt5 import QtGui
                        squid.apply_tint(QtGui.QColor(*colour))
                    state['colour'] = colour
                    state['uuid'] = str(squid.uuid)
                    shot('alone', f'{name}, a new {personality_name.lower()} hatchling, alone')
                    assert window.plugin_manager.enable_plugin('multiplayer')
                    plugin = state['plugin'] = window.plugin_manager.plugins['multiplayer']['instance']
                    node = plugin.network_node
                    state['node_id'] = node.node_id
                    state['private_address'] = f'{node.local_ip}:{node.port}'
                    state['friend_code'] = plugin.find_friend_code()
                    state['seen_from_outside_as'] = (
                        '%s:%s' % tuple(node.public_endpoint) if node.public_endpoint else None)
                    state['friend_code_note'] = plugin.friend_code_note()
                    state['stage'] = 'has a friend code'
                    seen['neurons'] = set(brain().neuron_positions)
                    write()
                return
            watch(plugin)
            if state['stage'] == 'has a friend code':
                state['heard_before_codes'] = len(plugin._peers_last_heard)
                codes = folder / 'codes.json'
                if codes.exists():
                    for friend, code in json.loads(codes.read_text()):
                        ok, said = plugin.connect_to_friend(code)
                        event('entered', f"entered {friend}'s friend code {code}: {said}", ok=ok)
                    state['stage'] = 'linked'
            pending = state.get('pending_visitor_shot')
            if pending and time.monotonic() >= pending:
                state['pending_visitor_shot'] = None
                names = ', '.join(sorted(seen['visitors'].values()))
                if names:
                    shot(f'visit-{len(state["shots"])}', f"{name}'s tank with {names} in it")
            if int(now) != seen['second']:
                seen['second'] = int(now)
                if int(now) % 2 == 0:
                    trace(plugin)
                if state['stage'] == 'linked' and int(now) // 60 != seen['shot_minute']:
                    seen['shot_minute'] = int(now) // 60
                    shot(f'minute-{int(now) // 60}', f"{name}'s tank, about minute {int(now) // 60}")
                write()
            if (output / 'stop').exists() and state['stage'] != 'ending':
                state['stage'] = 'ending'
                finish(plugin)
                state['ending_at'] = time.monotonic()
                write()
            if state['stage'] == 'ending' and time.monotonic() - state['ending_at'] > 3.0:
                shot('brain', f"{name}'s brain at the end", window.brain_window)
                state['stage'] = 'done'
                write()
                _shutdown(app, window, timer, plugin, 0)
        except Exception as exc:                        # noqa: BLE001
            import traceback
            traceback.print_exc()
            state['error'] = repr(exc)
            write()
            _shutdown(app, window, timer, state['plugin'], 1)

    timer.timeout.connect(tick)
    timer.start(250)
    return app.exec_()


# ---------------------------------------------------------------------------
# The session
# ---------------------------------------------------------------------------
def _status(output, number):
    try:
        return json.loads((output / f'home{number}' / 'status.json').read_text())
    except (OSError, ValueError):
        return {}


def clock(seconds):
    return f'{int(seconds) // 60}:{int(seconds) % 60:02d}'


def run(output, homes, minutes):
    if os.geteuid() != 0:
        print('Network namespaces need root.')
        return 2
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    session = {'homes': homes, 'minutes': minutes, 'players': []}
    children = []
    try:
        session['internet'] = build_internet(homes)
        stun = subprocess.Popen(['ip', 'netns', 'exec', f'{PREFIX}-net', sys.executable, __file__,
                                 str(output), '--stun'])
        children.append(('stun', stun, None))
        time.sleep(1.0)
        session['isolation'] = check_isolation(homes)
        print('The homes are apart:', session['isolation'])
        environment = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONUNBUFFERED='1')
        for i in range(1, homes + 1):
            log = open(output / f'home{i}.log', 'w')
            children.append((f'home{i}', subprocess.Popen(
                ['ip', 'netns', 'exec', f'{PREFIX}-h{i}', sys.executable, __file__,
                 str(output), '--player', str(i)],
                stdout=log, stderr=subprocess.STDOUT, env=environment), log))
        # Every game gets its friend code.
        deadline = time.time() + 120
        while time.time() < deadline:
            statuses = [_status(output, i) for i in range(1, homes + 1)]
            if all(s.get('friend_code') for s in statuses):
                break
            time.sleep(1.0)
        else:
            raise RuntimeError('not every game got a friend code')
        time.sleep(12.0)                    # long enough to hear a neighbour, were there one
        statuses = [_status(output, i) for i in range(1, homes + 1)]
        for s in statuses:
            session['players'].append({
                'home': s['home'], 'name': s['name'], 'personality': s['personality'],
                'colour': s.get('colour'),
                'private_address': s['private_address'],
                'seen_from_outside_as': s['seen_from_outside_as'],
                'friend_code': s['friend_code'],
                'tanks_heard_before_any_code': s.get('heard_before_codes', 0)})
            print(f"{s['name']:6} ({s['personality']}) at home {s['home']}: private "
                  f"{s['private_address']}, seen from outside as {s['seen_from_outside_as']}, "
                  f"friend code {s['friend_code']}, hears "
                  f"{s.get('heard_before_codes', 0)} other tanks")
        # The players pass their codes round: everyone enters everyone else's.
        for s in statuses:
            others = [(o['name'], o['friend_code']) for o in statuses if o['home'] != s['home']]
            (output / f"home{s['home']}" / 'codes.json').write_text(json.dumps(others))
        began = time.time()
        session['codes_exchanged_at'] = began
        print(f'\nCodes exchanged. Watching for {minutes} minutes.\n')
        printed = 0
        while time.time() - began < minutes * 60:
            time.sleep(5.0)
            printed = _print_new(output, homes, began, printed)
            for label, child, _log in children:
                if label != 'stun' and child.poll() not in (None, 0):
                    raise RuntimeError(f'{label} stopped early (see {label}.log)')
        (output / 'stop').write_text('stop')
        for label, child, log in children:
            if label == 'stun':
                continue
            child.wait(timeout=90)
            log.close()
        _print_new(output, homes, began, printed)
        session['ended_at'] = time.time()
        _write_up(output, homes, session, began)
    finally:
        for _label, child, _log in children:
            if child.poll() is None:
                child.terminate()
        tear_down(homes)
    return 0


def _all_events(output, homes):
    events = []
    for i in range(1, homes + 1):
        events.extend(_status(output, i).get('events', []))
    return sorted(events, key=lambda e: e['at'])


def _line(event, began, names):
    text = event['text']
    if event['kind'] == 'heard':
        text += f" ({names.get(event.get('node_id'), 'unknown')}'s)"
    if event['kind'] == 'left' and event.get('to_node'):
        text += f" - {names.get(event['to_node'], 'unknown')}'s"
    return f"{clock(max(0, event['at'] - began)):>5}  {event['who']:6} {text}"


def _print_new(output, homes, began, printed):
    names = {_status(output, i).get('node_id'): _status(output, i).get('name')
             for i in range(1, homes + 1)}
    events = _all_events(output, homes)
    for event in events[printed:]:
        print(_line(event, began, names), flush=True)
    return len(events)


def _write_up(output, homes, session, began):
    statuses = [_status(output, i) for i in range(1, homes + 1)]
    names = {s.get('node_id'): s.get('name') for s in statuses}
    events = _all_events(output, homes)
    session['timeline'] = [dict(e, clock=clock(max(0, e['at'] - began)),
                                line=_line(e, began, names)) for e in events]
    session['final'] = {s['name']: s.get('final') for s in statuses}
    session['shots'] = {key: info for s in statuses for key, info in s.get('shots', {}).items()}
    session['traces'] = {s['name']: s.get('trace', []) for s in statuses}
    session['counts'] = {}
    for event in events:
        session['counts'][event['kind']] = session['counts'].get(event['kind'], 0) + 1
    try:
        session['stun_log'] = [json.loads(line) for line in
                               (output / 'stun.log').read_text().splitlines() if line.strip()]
    except OSError:
        session['stun_log'] = []
    (output / 'session.json').write_text(json.dumps(session, indent=1, default=str))
    print('\nCounts:', session['counts'])
    print('Written to', output / 'session.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('output', type=Path)
    parser.add_argument('--homes', type=int, default=4, choices=(2, 3, 4))
    parser.add_argument('--minutes', type=float, default=5.0)
    parser.add_argument('--player', type=int)
    parser.add_argument('--stun', action='store_true')
    args = parser.parse_args()
    if args.stun:
        stun_server(args.output / 'stun.log')
    elif args.player:
        sys.exit(worker(args.output.resolve(), args.player))
    else:
        sys.exit(run(args.output, args.homes, args.minutes))
