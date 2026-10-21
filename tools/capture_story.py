#!/usr/bin/env python3
"""Capture a squid's story across two networked desktop games, for a gallery.

Two real desktop processes on the real multicast LAN protocol:

  Ziggy (adventurous) - the traveller           Inky (timid) - the resident

  1. AWARE      Ziggy hears Inky's aquarium and grows aquarium_nearby
  2. VISIT      Ziggy's own network takes it out of its tank, to Inky's
  3. FIGHT      over the rock Inky is holding: the rock flashes, then a scuffle
  4. MATE       the two stay in contact; Inky lays an egg
  5. DIES       Inky, a parent, stops eating and starves
  6. NEW GAME   Inky's egg hatches into a hatchling with both parents' weights

What moves the squid and decides what they do is their own networks and the
game's rules. To fit a lifetime into a few minutes the capture NUDGES, and
records every nudge in nudges.json for the gallery to disclose: drives held
for the scene (Inky alarmed and aggressive, Ziggy playful and unafraid), a
rock put in Inky's tentacles and held, Inky held still while the two are
close, the mating chance (2% per visit) made certain after the fight, a night
compressed so Ziggy goes home to sleep, and Inky's starvation compressed.

Run: QT_QPA_PLATFORM=offscreen python tools/capture_story.py OUTPUT_DIR
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
ROLES = ('ziggy', 'inky')
NAMES = {'ziggy': 'Ziggy', 'inky': 'Inky'}
TIMEOUT = 420.0
# A large brain window for the brain shots, so the network and its labels are
# drawn big enough to read. In between it is kept smaller: a larger brain
# redrawn every frame in two processes slowed the scene enough that the squid
# stopped meeting.
BRAIN_WINDOW = (1300, 1100)
WORKING_BRAIN = (1200, 860)


def worker(role, output):
    from test_lan_round_trip import _setup, _shutdown, _social_structure
    folder = output / role
    shots = output / 'shots'
    shots.mkdir(parents=True, exist_ok=True)
    app, main = _setup(folder)
    from PyQt5 import QtCore, QtGui, QtWidgets
    from src.brain_constants import AQUARIUM_SENSE
    from src.personality import Personality
    window = main.MainWindow(specified_personality=(Personality.ADVENTUROUS if role == 'ziggy'
                                                    else Personality.TIMID))
    window.show()
    window.resize(1100, 800)
    started = time.monotonic()
    other = output / ('inky' if role == 'ziggy' else 'ziggy') / 'status.json'
    state = {'role': role, 'stage': 'start', 'plugin': None, 'shots': {}, 'notes': {},
             'nudges': [], 'messages': []}
    timer = QtCore.QTimer()

    report_message = window.user_interface.show_message

    def show_message(message, *a, **k):
        state['messages'].append([round(time.monotonic() - started, 1), str(message)])
        return report_message(message, *a, **k)
    window.user_interface.show_message = show_message

    def elapsed():
        return time.monotonic() - started

    def write():
        data = {k: v for k, v in state.items() if k != 'plugin'}
        (folder / 'status.json').write_text(json.dumps(data, indent=2, default=str))

    def other_stage():
        try:
            return json.loads(other.read_text()).get('stage', '')
        except (OSError, ValueError):
            return ''

    def nudge(text):
        if text not in state['nudges']:
            state['nudges'].append(text)

    def shot(name, widget=None, caption=''):
        """Grab once, after `at` - the moment it was first wanted - plus a settle."""
        if name in state['shots']:
            return
        (widget or window).grab().save(str(shots / f'{role}-{name}.png'))
        state['shots'][name] = {'at': round(elapsed(), 1), 'caption': caption}
        write()

    def later(name, delay):
        """True once `delay` seconds have passed since `name` was first asked for."""
        key = f'_wait_{name}'
        state.setdefault(key, elapsed())
        return elapsed() - state[key] >= delay

    def brain():
        return window.brain_window.brain_widget

    def brain_shot(name, caption, settle=1.5):
        """The brain window at shot size, grabbed once it has redrawn."""
        if name in state['shots']:
            return
        if f'_sized_{name}' not in state:
            window.brain_window.resize(*BRAIN_WINDOW)
            state[f'_sized_{name}'] = elapsed()
        if elapsed() - state[f'_sized_{name}'] >= settle:
            shot(name, window.brain_window, caption=caption)
            window.brain_window.resize(*WORKING_BRAIN)

    def pin(**values):
        b = brain()
        for name, value in values.items():
            b.state[name] = value

    def thoughts():
        return [t for _, t in getattr(brain(), 'social_thoughts', [])][-8:]

    # ------------------------------------------------------------- Ziggy
    def ziggy(plugin, squid):
        mind = plugin.visitor_mind
        if state['stage'] == 'start' and AQUARIUM_SENSE in brain().neuron_positions:
            state['stage'] = 'aware'
            state['notes']['aware_thoughts'] = thoughts()
        if AQUARIUM_SENSE in brain().neuron_positions and not mind.perception.away:
            if later('aware', .4):
                shot('aware-tank', caption='Ziggy hears another aquarium and grows a sense for it')
        # Its brain stays at home: the shot is finished even if Ziggy has left.
        if AQUARIUM_SENSE in brain().neuron_positions and 'aware-brain' not in state['shots']:
            if later('aware-brain', .6):
                brain_shot('aware-brain',
                           caption="aquarium_nearby, the first neuron on Ziggy's SOCIAL band")
                state['notes']['aware_thoughts'] = thoughts()
        if state['stage'] == 'aware' and 'aware-brain' in state['shots']:
            state['stage'] = 'restless'
        if state['stage'] in ('aware', 'restless') and 'venturing' in str(squid.status):
            state['stage'] = 'leaving'
            state['notes']['why_venture'] = squid.why_not_venturing() or 'it wants to explore'
        if state['stage'] == 'leaving':
            x = float(squid.squid_x)
            if x < 160 or x > window.user_interface.window_width - 300 or mind.perception.away:
                shot('leaving', caption='Its own network takes Ziggy to the edge of its tank')
        if mind.perception.away and state['stage'] in ('aware', 'restless', 'leaving'):
            state['stage'] = 'away'
            state['notes']['asked'] = plugin._asked_to_visit
            state['notes']['leave_thoughts'] = thoughts()
        if state['stage'] == 'away':
            if later('away', 3.0):
                shot('away-home', caption="Ziggy's own tank while it is away")
            if other_stage() in ('square_up', 'fight', 'court'):
                # Held for the scene: playful, unafraid, fed and awake, so it
                # goes for what Inky holds and stays rather than fleeing home.
                nudge('Ziggy kept playful and unafraid while visiting (act_play 85, flee/rest/shelter 0, '
                      'anxiety 30, fed and rested)')
                pin(act_play=85., act_flee=0., act_rest=0., act_shelter=0., act_eat=0.,
                    act_move=0., anxiety=30.)
                squid.hunger, squid.sleepiness = 20., 10.
            if other_stage() == 'night':
                nudge("A night compressed: Ziggy's sleepiness set to 100 once it had mated, "
                      "so it goes home to sleep by its own rule")
                squid.sleepiness = 100.
                state['stage'] = 'night'
        if state['stage'] == 'night' and not mind.perception.away:
            state['stage'] = 'home'
            state['notes']['home_thoughts'] = thoughts()
        if state['stage'] == 'home' and later('home', .5):
            shot('home', caption='Ziggy home again, asleep - changed by what happened')
            # Rested after a compressed night, Ziggy sets off again within
            # seconds - its own decision, and Inky, aggressive now, would
            # fight it every time.
            nudge("Ziggy's player switched multiplayer off once Ziggy was home, so the story "
                  "can follow Inky")
            window.plugin_manager.disable_plugin('multiplayer')
            state['plugin_off'] = True
            state['stage'] = 'home-brain'

    def ziggy_home_brain():
        """Multiplayer is off by now: the brain the visit left behind."""
        if later('home-brain', 2.0):
            brain_shot('home-brain',
                       caption="Ziggy's brain after the visit: its social band has grown")
        if 'home-brain' in state['shots']:
            state['notes']['social'] = _social_structure(brain())
            state['stage'] = 'waiting'
        if state['stage'] == 'waiting' and other_stage() == 'done':
            state['stage'] = 'done'

    # -------------------------------------------------------------- Inky
    def inky(plugin, squid):
        logic = window.tamagotchi_logic
        actors = list(plugin.host_body.visitors.values()) if plugin.host_body else []
        actor = actors[0] if actors else None
        stats = squid.statistics
        if state['stage'] == 'start' and actor is not None:
            state['stage'] = 'met'
            state['notes']['visitor'] = actor.identity.name
        if state['stage'] == 'met':
            if later('met', 3.0):
                shot('arrival', caption='Ziggy arrives in Inky’s tank: its body here, its brain at home')
            if later('square', 9.0):
                state['stage'] = 'square_up'
                state['fights_before'] = stats.fights_won + stats.fights_lost
        if state['stage'] == 'square_up':
            rock = state.get('rock_item')
            if rock is None:
                nudge('A rock put in Inky’s tentacles and held (carry time raised to 60 s)')
                nudge('Inky placed mid-tank and held still, facing Ziggy, while the two are close')
                squid.animation_speed = 0
                squid.squid_x, squid.squid_y = 420., 330.
                squid.squid_item.setPos(squid.squid_x, squid.squid_y)
                squid.squid_direction = 'right' if actor.x > squid.squid_x else 'left'
                squid.squid_item.setPixmap(squid.current_image())
                rocks = logic.rock_interaction
                rocks.rock_config['min_carry_duration'] = rocks.rock_config['max_carry_duration'] = 60.
                pix = QtGui.QPixmap(os.path.join('images', 'decoration', 'rock01.png'))
                from src.ui import ResizablePixmapItem
                rock = ResizablePixmapItem(pix, os.path.join('images', 'decoration', 'rock01.png'))
                rock.setScale(.5)
                window.user_interface.scene.addItem(rock)
                if rocks.attach_rock_to_squid(rock):
                    state['rock_item'] = rock
            # Alarmed and aggressive for the scene: what a fight needs from
            # its own network (an aggression neuron reading 50 or more).
            nudge('Inky alarmed and aggressive for the scene (anxiety 75, aggression 85)')
            pin(anxiety=75., aggression=85., act_play=0.)
            squid.anxiety = 75.
            flashes = getattr(plugin.entity_manager, '_contest_flashes', {})
            if flashes or plugin.entity_manager._scuffles:
                state['stage'] = 'fight'
        if state['stage'] == 'fight':
            pin(anxiety=75., aggression=85.)
            rock = state.get('rock_item')
            effect = rock.graphicsEffect() if rock is not None else None
            if (effect is not None and isinstance(effect, QtWidgets.QGraphicsColorizeEffect)
                    and effect.strength() >= 1.0):
                shot('fight-leadin', caption='The rock they are fighting over flashes dark red')
            if plugin.entity_manager._fight_clouds and later('cloud', 1.2):
                shot('fight-cloud', caption='The scuffle: one cloud over the pair')
            if stats.fights_won + stats.fights_lost > state['fights_before']:
                state['notes']['fight'] = {'won': stats.fights_won, 'lost': stats.fights_lost}
                state['notes']['fight_thoughts'] = thoughts()
                nudge('Mating chance (2% per visit) made certain after the fight')
                actor.mating_rolled, actor.contact_since = False, None
                plugin.host_body.mating_chance = 1.0
                state['stage'] = 'court'
        if state['stage'] == 'court':
            pin(anxiety=40., aggression=20.)
            if squid.lifecycle.stage == 'parent':
                state['stage'] = 'parent'
        if state['stage'] == 'parent':
            if later('heart', .6):
                shot('mating', caption='A mating: one beating heart over the pair')
            if later('egg', 4.0):
                shot('egg', caption='Inky has laid an egg, and has stopped eating')
                state['notes']['egg'] = dict(squid.lifecycle.egg or {})
                state['stage'] = 'night'
        if state['stage'] == 'night' and not actors and other_stage() in (
                'home', 'home-brain', 'waiting') and later('gone', 3.0):
            squid.animation_speed = getattr(logic, 'simulation_speed', 1) or 1
            nudge('Starvation compressed: Inky’s hunger set to 100 and health to 1.5 '
                  '(a parent loses 0.1 health a second once starving)')
            squid.hunger, squid.health, squid.is_sleeping = 100., 1.5, False
            state['stage'] = 'starving'
        if state['stage'] == 'starving':
            squid.hunger = 100.
            if squid.lifecycle.is_dead:
                state['stage'] = 'dead'
                state['notes']['death'] = dict(squid.lifecycle.death or {})
                stones = [i for i in window.user_interface.scene.items()
                          if getattr(i, 'is_headstone', False)]
                if stones:
                    state['notes']['epitaph'] = stones[0].epitaph()
        if state['stage'] == 'dead' and later('dead', 1.2):
            shot('dead', caption='Inky has died. A headstone marks where.')
            state['stage'] = 'hatch'
            state['uuid'] = str(squid.uuid)

    def after_death():
        """The new game: Inky's egg hatches. The plugin was taken down with Inky."""
        splash = getattr(window, 'splash', None)
        if splash is not None and splash.isVisible() and getattr(splash, 'frame_index', 0) >= 2:
            shot('hatching', caption='Inky’s egg hatches: a new game, with no way out')
        if (str(window.squid.uuid) != state.get('uuid') and splash is not None
                and getattr(splash, '_ended', False)):
            if later('hatched', 3.0) and 'hatchling' not in state['shots']:
                shot('hatchling', caption='The hatchling, beside its parent’s headstone')
                window.brain_window.show(); window.brain_window.resize(*WORKING_BRAIN)
                state['notes']['inherited_from'] = getattr(window.squid, 'inherited_from', [])
            if later('hatched-brain', 6.0):
                brain_shot('hatchling-brain',
                           caption='A newborn brain, overlaid with half of each parent’s weights')
            if 'hatchling-brain' in state['shots']:
                ledger = getattr(brain(), 'ledger', None)
                events = [e for e in getattr(ledger, '_recent', []) if e.mechanism == 'inheritance']
                state['notes']['inherited_synapses'] = len(events)
                state['notes']['inherited_parents'] = sorted({e.detail.get('parent') for e in events})
                state['stage'] = 'done'

    def tick():
        try:
            if elapsed() > 9 and window.splash._ended and state['plugin'] is None:
                squid = window.squid
                squid.name = NAMES[role]
                squid.is_sleeping = False
                squid.health = 100.
                for drive, value in (('hunger', 15.), ('sleepiness', 5.), ('anxiety', 15.),
                                     ('happiness', 70.), ('curiosity', 70.)):
                    setattr(squid, drive, value)
                assert window.plugin_manager.enable_plugin('multiplayer')
                plugin = window.plugin_manager.plugins['multiplayer']['instance']
                state['plugin'] = plugin
                plugin.host_body.mating_chance = 0.
                state['node_id'] = plugin.network_node.node_id
                window.brain_window.show()
                window.brain_window.resize(*WORKING_BRAIN)
            plugin = state['plugin']
            if plugin is None:
                return
            if int(elapsed()) != state.get('second'):
                state['second'] = int(elapsed())
                if state['stage'] not in ('hatch', 'done') and not state.get('plugin_off'):
                    plugin.network_node.send_message('heartbeat', {'status': 'active'})
                write()
            if role == 'ziggy' and state.get('plugin_off'):
                if state['stage'] == 'home-brain':
                    ziggy_home_brain()
                elif other_stage() == 'done':
                    state['stage'] = 'done'
            elif role == 'ziggy':
                ziggy(plugin, window.squid)
            elif state['stage'] in ('hatch', 'done'):
                after_death()
            else:
                inky(plugin, window.squid)
            done = state['stage'] == 'done' and (role == 'ziggy' or other_stage() == 'done')
            if done or elapsed() > TIMEOUT:
                state['finished_at'] = round(elapsed(), 1)
                write()
                live = None if state.get('plugin_off') or state['stage'] == 'done' and role == 'inky' \
                    else state['plugin']
                _shutdown(app, window, timer, live, 0 if done else 3)
        except Exception:
            import traceback
            (folder / 'error.txt').write_text(traceback.format_exc())
            timer.stop()
            app.exit(1)

    timer.timeout.connect(tick)
    timer.start(100)
    return app.exec_()


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    children = []
    for role in ROLES:
        log = open(output / (role + '.log'), 'w')
        command = [sys.executable, __file__, str(output), '--role', role]
        if os.environ.get('CAPTURE_GDB') == role:      # a native backtrace on a crash
            command = ['gdb', '-batch', '-ex', 'run', '-ex', 'bt 40', '--args'] + command
        children.append((role, subprocess.Popen(
            command,
            stdout=log, stderr=subprocess.STDOUT), log))
    codes = {}
    for role, child, log in children:
        codes[role] = child.wait(timeout=TIMEOUT + 60)
        log.close()
    status = {role: json.loads((output / role / 'status.json').read_text()) for role in ROLES}
    summary = {
        'exit_codes': codes,
        'stages': {role: status[role]['stage'] for role in ROLES},
        'shots': {f'{role}-{name}': info for role in ROLES
                  for name, info in status[role]['shots'].items()},
        'notes': {role: status[role]['notes'] for role in ROLES},
        'nudges': status['ziggy']['nudges'] + status['inky']['nudges'],
        'messages': {role: status[role]['messages'] for role in ROLES},
    }
    (output / 'story.json').write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps({k: summary[k] for k in ('exit_codes', 'stages')}, indent=2))
    print('shots:', ', '.join(summary['shots']))
    return 0 if all(code == 0 for code in codes.values()) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--role', choices=ROLES)
    args = parser.parse_args()
    if args.role:
        sys.exit(worker(args.role, args.output))
    sys.exit(run(args.output))
