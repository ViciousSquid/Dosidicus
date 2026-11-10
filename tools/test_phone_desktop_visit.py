#!/usr/bin/env python3
"""A phone's squid and a computer's squid visit each other's tanks.

One real desktop game (the Qt game, drawn off screen) and one real phone tank
(the Android engine: android/dosidicus_mobile/engine) run side by side on
this machine, each with its own socket, linked the way two players link them:
by friend code. Nothing is faked between them - every message crosses a real
UDP socket in the protocol's own encoding.

  1. The desktop's squid goes to the phone's tank, is given a body there,
     is steered by its own brain at home, and comes home.
  2. The phone's squid goes to the desktop's tank, likewise.

Whether a squid goes at all is its own network's decision, as always. Both
are adventurous newborns, which normally go within a minute of hearing
another aquarium; if one has not gone after WAIT_FOR_ITS_OWN_DECISION
seconds it is put at the side of its tank so the rest can be checked, and
the report says which happened.

    python tools/test_phone_desktop_visit.py OUTPUT_FOLDER

Writes OUTPUT_FOLDER/result.json and pictures of the desktop tank; exits 0
only if every check passed.
"""
import json
import os
from pathlib import Path
import socket
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'android'))
sys.path.insert(0, str(ROOT))

WAIT_FOR_ITS_OWN_DECISION = 45.0
PHASE_TIMEOUT = 110.0
PHONE_PINK = (255, 105, 180)
DESKTOP_BLUE = (120, 170, 255)


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main(output):
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    os.environ.setdefault('DOSIDICUS_SCREEN', '1920x1080')
    from test_lan_round_trip import _setup, _shutdown
    app, game = _setup(output / 'desktop')
    from PyQt5 import QtCore, QtGui
    from src.personality import Personality
    from plugins.multiplayer import friend_link
    from dosidicus_mobile.engine import Simulation, Squid
    from dosidicus_mobile.engine.personality import Personality as PhonePersonality
    from dosidicus_mobile.engine.tank_link import TankLink

    window = game.MainWindow(specified_personality=Personality.ADVENTUROUS)
    window.show()

    phone = Simulation(squid=Squid(PhonePersonality.ADVENTUROUS))
    phone.hatching = False
    phone.squid.name = 'Pocket'
    phone.squid.color_tint = tuple(c / 255.0 for c in PHONE_PINK)
    link = TankLink(phone, port=free_port(), stun_server='')

    state = {'stage': 'starting', 'checks': {}, 'notes': {}, 'plugin': None}
    started = time.monotonic()
    timer = QtCore.QTimer()
    last = {'at': time.monotonic()}

    def check(name, passed, detail=''):
        state['checks'][name] = {'passed': bool(passed), 'detail': str(detail)}
        print(f"{'ok  ' if passed else 'FAIL'}  {name}  {detail}", flush=True)

    def hold(squid, reason='held at home for this part of the test'):
        squid.why_not_venturing = lambda: reason

    def release(squid):
        squid.__dict__.pop('why_not_venturing', None)

    def comfortable(squid):
        squid.is_sleeping = False
        squid.health = 100.
        for drive, value in (('hunger', 15.), ('sleepiness', 5.), ('anxiety', 15.),
                             ('happiness', 70.), ('curiosity', 70.)):
            setattr(squid, drive, value)

    def finish(code):
        state['stage'] = 'done'
        state['passed'] = code == 0 and all(c['passed'] for c in state['checks'].values())
        (output / 'result.json').write_text(json.dumps(
            {k: v for k, v in state.items() if k != 'plugin'}, indent=1, default=str))
        link.stop()
        _shutdown(app, window, timer, state['plugin'], 0 if state['passed'] else 1)

    def tick():
        now = time.monotonic()
        elapsed, dt = now - started, now - last['at']
        last['at'] = now
        try:
            phone.update(min(dt, 0.2))
            plugin = state['plugin']
            desk = window.squid
            if plugin is None:
                if elapsed > 9 and window.splash._ended:
                    desk.name = 'Desky'
                    desk.apply_tint(QtGui.QColor(*DESKTOP_BLUE))
                    comfortable(desk)
                    comfortable(phone.squid)
                    assert window.plugin_manager.enable_plugin('multiplayer')
                    plugin = state['plugin'] = window.plugin_manager.plugins['multiplayer']['instance']
                    plugin.host_body.mating_chance = 0.
                    assert link.start()
                    # Each player reads their code to the other. On one
                    # machine both tanks have the same address, so the code's
                    # invitation is used and the address is this machine's.
                    for mine, theirs_code, theirs_port in (
                            (plugin, link.friend_code(), link.node.port),
                            (link, plugin.friend_code(), plugin.network_node.port)):
                        where = friend_link.parse_friend(theirs_code)
                        assert where.port == theirs_port and where.invitation
                        (mine.network_node if mine is plugin else mine.node).add_friend(
                            '127.0.0.1', where.port, where.invitation)
                    state['notes']['codes'] = {'phone': link.friend_code(),
                                               'desktop': plugin.friend_code()}
                    check('friend codes are 15 characters on both',
                          all(len(c.replace('-', '')) == 15 for c in state['notes']['codes'].values()),
                          state['notes']['codes'])
                    hold(phone.squid)
                    state.update(stage='desktop to phone', phase_at=now)
                return

            mind, phone_squid = plugin.visitor_mind, phone.squid
            waited = now - state['phase_at']

            if state['stage'] == 'desktop to phone':
                comfortable(desk) if not state.get('bedtime') else None
                if not state.get('linked') and plugin._peers_last_heard and link.tanks_heard():
                    state['linked'] = True
                    check('each tank hears the other through the link', True,
                          f"after {waited:.1f}s")
                if state.get('linked') and not mind.perception.away and not state.get('arrived') \
                        and waited > WAIT_FOR_ITS_OWN_DECISION and not state.get('pushed'):
                    state['pushed'] = True
                    state['notes']['desktop squid went by itself'] = False
                    state['notes']['desktop squid had not gone because'] = desk.why_not_venturing()
                    desk.why_not_venturing = lambda: None
                    desk.squid_x = window.user_interface.window_width - desk.squid_width - 1
                if link.hosted and not state.get('arrived'):
                    state['arrived'] = now
                    state['notes'].setdefault('desktop squid went by itself', True)
                    visit = next(iter(link.hosted.values()))[1]
                    state['start_x'] = visit.actor.x
                    body = visit.body
                    check('the desktop squid is given a body in the phone tank',
                          visit.actor.identity.name == 'Desky' and body in phone.visitors,
                          f"{visit.actor.identity.name} at ({visit.actor.x:.0f}, {visit.actor.y:.0f})")
                    shown = tuple(round(c * 255) for c in (body['tint'] or ())[:3])
                    check('it keeps its colour there', shown == DESKTOP_BLUE, f"tint {shown}")
                if state.get('arrived') and not state.get('steered'):
                    visit = next(iter(link.hosted.values()), (None, None))[1]
                    resident = getattr(mind.perception, 'resident', None)
                    if visit is not None and resident is not None and (
                            abs(visit.actor.x - state['start_x']) > 25 or now - state['arrived'] > 20):
                        state['steered'] = now
                        check('its home knows whose tank it is in',
                              resident.name == 'Pocket' and mind.perception.away,
                              f"resident {resident.name}")
                        check('its own brain, at home, moves its body in the phone tank',
                              abs(visit.actor.x - state['start_x']) > 25,
                              f"moved {abs(visit.actor.x - state['start_x']):.0f}px in "
                              f"{now - state['arrived']:.1f}s; action {visit.actor.action}")
                        window.grab().save(str(output / 'desktop-while-its-squid-is-on-the-phone.png'))
                        desk.sleepiness = 100.0       # hours pass; going home is its own
                        state['bedtime'] = now
                if state.get('steered') and not mind.perception.away:
                    state['home'] = True
                if state.get('home') and not link.hosted:
                    check('it comes home, and its body leaves the phone tank',
                          not any(v.get('remote') and not v['leaving'] for v in phone.visitors),
                          f"{now - state['bedtime']:.1f}s after bedtime")
                    comfortable(desk)
                    hold(desk)
                    release(phone_squid)
                    comfortable(phone_squid)
                    state.update(stage='phone to desktop', phase_at=now)
                elif waited > PHASE_TIMEOUT:
                    check('desktop squid visits the phone tank and comes home', False,
                          f"timed out: away={mind.perception.away} hosted={list(link.hosted)} "
                          f"why_not={desk.why_not_venturing()}")
                    finish(1)

            elif state['stage'] == 'phone to desktop':
                comfortable(phone_squid) if not state.get('phone_bedtime') else None
                if link.away is None and not state.get('phone_arrived') \
                        and waited > WAIT_FOR_ITS_OWN_DECISION and not state.get('phone_pushed'):
                    state['phone_pushed'] = True
                    state['notes']['phone squid went by itself'] = False
                    state['notes']['phone squid had not gone because'] = phone_squid.why_not_venturing()
                    phone_squid.why_not_venturing = lambda: None
                if state.get('phone_pushed') and link.away is None:
                    phone_squid.at_side = 'right'
                actors = list(plugin.host_body.visitors.values())
                if actors and not state.get('phone_arrived'):
                    state['phone_arrived'] = now
                    state['notes'].setdefault('phone squid went by itself', True)
                    actor = actors[0]
                    state['phone_start_x'] = actor.x
                    drawn = plugin.entity_manager.remote_squids.get(link.node.node_id, {})
                    check('the phone squid is given a body in the desktop tank',
                          actor.identity.name == 'Pocket' and drawn.get('visual') is not None,
                          f"{actor.identity.name} at ({actor.x:.0f}, {actor.y:.0f})")
                    check('it is pink there, as its player made it',
                          tuple(actor.identity.tint or ()) == PHONE_PINK, f"tint {actor.identity.tint}")
                if state.get('phone_arrived') and not state.get('phone_steered'):
                    actor = next(iter(plugin.host_body.visitors.values()), None)
                    resident = getattr(link.away.mind.perception, 'resident', None) if link.away else None
                    if actor is not None and resident is not None and (
                            abs(actor.x - state['phone_start_x']) > 25
                            or now - state['phone_arrived'] > 20):
                        state['phone_steered'] = now
                        check('the phone knows whose tank its squid is in',
                              resident.name == 'Desky' and phone.visiting() is not None,
                              phone.visiting_text())
                        check('its own brain, on the phone, moves its body in the desktop tank',
                              abs(actor.x - state['phone_start_x']) > 25,
                              f"moved {abs(actor.x - state['phone_start_x']):.0f}px in "
                              f"{now - state['phone_arrived']:.1f}s; action {actor.action}")
                        window.grab().save(str(output / 'desktop-with-the-phone-squid-in-it.png'))
                        phone_squid.sleepiness = 100.0
                        state['phone_bedtime'] = now
                if state.get('phone_steered') and link.away is None \
                        and not plugin.host_body.visitors:
                    check('it comes home to the phone, and its body leaves the desktop tank',
                          phone.visiting() is None,
                          f"{now - state['phone_bedtime']:.1f}s after bedtime")
                    grown = sorted(n for n in phone_squid.brain.positions
                                   if n in ('aquarium_nearby', 'can_see_squid'))
                    check('the phone squid grew its senses for other tanks and squid itself',
                          'aquarium_nearby' in grown, f"grown: {grown}")
                    state['notes']['phone log'] = [text for _at, text in link.events]
                    finish(0)
                elif waited > PHASE_TIMEOUT:
                    check('phone squid visits the desktop tank and comes home', False,
                          f"timed out: away={link.away is not None} "
                          f"visitors={len(plugin.host_body.visitors)} "
                          f"why_not={phone_squid.why_not_venturing()} log={[t for _a, t in link.events][-4:]}")
                    finish(1)
        except Exception:
            import traceback
            traceback.print_exc()
            state['error'] = traceback.format_exc()
            finish(1)

    timer.timeout.connect(tick)
    timer.start(33)
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else 'phone-desktop-visit').resolve()))
