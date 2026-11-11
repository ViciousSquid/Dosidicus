"""Build the story gallery from one watched internet session.

python build.py SESSION_DIR [--platforms DIR] [--out DIR] [--fragment FILE]

SESSION_DIR is what tools/internet_session.py wrote: four games in four
homes, each behind its own router, linked only by friend codes and then left
alone. Every caption, thought, message, address, code and number on the page
comes from its session.json; nothing here is written for the page except the
headings and the sentences that join them. --platforms is the folder
tools/capture_platforms.py's pictures were committed to
(docs/platform-screenshots), for the last chapter.

Writes index.html and img/*.webp in --out (default: the folder above this
one); --fragment also writes the page without its document skeleton, for a
host that supplies one.
"""
import argparse
import html
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('session', type=Path)
parser.add_argument('--platforms', type=Path)
parser.add_argument('--out', type=Path, default=HERE.parent)
parser.add_argument('--fragment', type=Path)
args = parser.parse_args()
session_dir, OUT = args.session, args.out
session = json.loads((session_dir / 'session.json').read_text())
(OUT / 'img').mkdir(parents=True, exist_ok=True)
for old in (OUT / 'img').glob('*.webp'):
    old.unlink()

e = html.escape
SIZES = {}
players = session['players']
# What each player plays on: a computer, or a phone running the Android game.
_phones = sum(1 for p in players if p.get('platform') == 'phone')
_desktops = len(players) - _phones
games_in_words = (f'{len(players)} copies of the desktop game' if not _phones else
                  f"{_desktops} cop{'y' if _desktops == 1 else 'ies'} of the desktop game and "
                  f"{_phones} of the Android game on a phone")
names = [p['name'] for p in players]
timeline = session['timeline']
shots = session['shots']
began = session['codes_exchanged_at']
minutes = session['minutes']
final = session.get('final') or {}
#: The aggression a squid goes for another at, as the squids' own records give it.
record_threshold = next((float(k['aggression']['threshold']) for k in
                         ((v or {}).get('social_knowledge') or {} for v in final.values())
                         if isinstance(k.get('aggression'), dict) and k['aggression'].get('threshold')),
                        50.0)


def webp(src, name, width=None):
    image = Image.open(src).convert('RGB')
    if width and image.width > width:
        image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    image.save(OUT / 'img' / f'{name}.webp', 'WEBP', lossless=True, method=6)
    SIZES[name] = image.size


def fig(name, caption, source=None):
    """A picture with its caption; '' if the run did not take it."""
    if name not in SIZES:
        path = source or session_dir / 'shots' / f'{name}.png'
        if not path.exists():
            return ''
        webp(path, name)
    w, h = SIZES[name]
    return (f'<figure class="shot"><button class="zoom" type="button" data-full="img/{name}.webp" '
            f'data-caption="{e(caption)}" aria-label="Enlarge: {e(caption)}">'
            f'<img src="img/{name}.webp" width="{w}" height="{h}" alt="{e(caption)}" loading="lazy">'
            f'</button><figcaption>{e(caption)}</figcaption></figure>')


def row(figures, kind=None):
    figures = [f for f in figures if f]
    if not figures:
        return ''
    kind = kind or {1: 'one', 2: 'two'}.get(len(figures), 'three')
    return f'<div class="row {kind}">{"".join(figures)}</div>'


def mind(who, lines):
    lines = [line for line in lines if line]
    if not lines:
        return ''
    items = ''.join(f'<li>{e(line)}</li>' for line in lines)
    return (f'<aside class="mind"><p class="mind-label">{e(who)}’s own account</p>'
            f'<ul>{items}</ul></aside>')


def chips(neurons):
    return ''.join(f'<span class="chip social">{e(n)}</span>' for n in neurons)


def events(kind, who=None):
    return [ev for ev in timeline if ev['kind'] == kind and (who is None or ev['who'] == who)]


def clock(ev):
    return ev['clock']


def swatch(colour):
    if not colour:
        return 'as it hatched'
    return (f'<span class="swatch" style="background: rgb({colour[0]},{colour[1]},{colour[2]})">'
            f'</span> its player’s colour')


def shot_caption(key):
    return shots[key]['caption']


def shots_like(prefix_of_tag, home=None):
    """Shot keys whose tag starts with prefix, oldest first."""
    found = [(info['at'], key) for key, info in shots.items()
             if key.split('-', 1)[1].startswith(prefix_of_tag)
             and (home is None or key.startswith(f'home{home}-'))]
    return [key for _, key in sorted(found)]


# ---------------------------------------------------------------- the facts
grew = events('grew')
links = events('link')
left = events('left')
arrivals = events('arrival')
homecomings = events('home')
beliefs = events('belief')
revised = events('revised')
fights = events('fight')
memories = events('memory')
entered = events('entered')
node_names = {}
for p in players:
    node_names[p['name']] = p
last_link = max((ev['at'] for ev in links), default=began) - began
codes_needed = len(players) * (len(players) - 1)
most_in_one_tank = max((ev.get('squid_in_tank', 0) for ev in arrivals), default=0)
stayed_home = [n for n in names if not events('left', n)]
home_of = {p['name']: p['home'] for p in players}


def thoughts_of(who, starts=None, contains=None, limit=4):
    found = []
    for ev in events('thought', who):
        text = ev['text']
        if starts and not text.startswith(starts):
            continue
        if contains and contains not in text:
            continue
        if text not in found:
            found.append(text)
    return found[:limit]


def visits_table():
    rows = []
    for ev in sorted(left + homecomings, key=lambda x: x['at']):
        if ev['kind'] == 'left':
            where = ev['line'].rsplit(' - ', 1)[-1] if ' - ' in ev['line'] else 'another tank'
            rows.append(f"<tr><td>{clock(ev)}</td><td>{e(ev['who'])}</td>"
                        f"<td>swam out of its own tank, to {e(where)}</td></tr>")
        else:
            rows.append(f"<tr><td>{clock(ev)}</td><td>{e(ev['who'])}</td><td>came home</td></tr>")
    return ''.join(rows)


def cast():
    cells = []
    for p in players:
        cells.append(
            f"<div><dt>{e(p['name'])}</dt><dd>{e(p['personality'])} · {swatch(p.get('colour'))}<br>"
            f"home {p['home']}: <code>{e(p['private_address'])}</code> inside, "
            f"<code>{e(p['seen_from_outside_as'] or 'not found')}</code> from outside<br>"
            f"friend code <code>{e(p['friend_code'])}</code></dd></div>")
    return ''.join(cells)


def grown_section():
    blocks = []
    for name in names:
        neurons = [ev['neuron'] for ev in events('grew', name)]
        account = thoughts_of(name, contains='so I grew', limit=4)
        if not neurons:
            blocks.append(f'<h3>{e(name)}</h3><p>Grew nothing new in these {minutes:g} minutes.</p>')
            continue
        blocks.append(f'<h3>{e(name)}</h3><p class="chips">{chips(neurons)}</p>'
                      + mind(name, account))
    return ''.join(blocks)


def belief_section():
    if not beliefs:
        return ('<p>No squid came to a belief about its world in this session: nothing '
                'happened often enough after anything it did.</p>')
    blocks = []
    for name in names:
        mine = events('belief', name)
        if not mine:
            continue
        lines = thoughts_of(name, starts='I think', limit=3) + thoughts_of(name, starts='I used to think', limit=3)
        blocks.append(mind(name, lines))
    count = len(beliefs)
    changed = len(revised)
    lead = (f'<p>{count} belief{"s" if count != 1 else ""} formed in the session'
            + (f', and {changed} of them {"were" if changed != 1 else "was"} given up again '
               f'when the squid’s own later experience did not bear {"them" if changed != 1 else "it"} out'
               if changed else '')
            + '. Nothing tells a squid what is true. It notices what follows what it does, takes '
              'that for how its world works, acts on it - and can find out it was wrong.</p>')
    return lead + f'<div class="row minds">{"".join(blocks)}</div>'


def _nearby_thoughts(who, at, before, after):
    return [ev['text'] for ev in timeline
            if ev['who'] == who and ev['kind'] in ('thought', 'grew', 'revised')
            and -before <= ev['at'] - at <= after]


def _in_words(seconds):
    return f'{int(seconds) // 60}:{int(seconds) % 60:02d}'


def fight_chapter():
    """Each fight, from the two squids' own records of it: the picture taken
    while it was happening, why it started, how it was decided, what each
    remembers and what each took away."""
    if not fights:
        return ''
    by_fight = {}
    for ev in fights:
        by_fight.setdefault(ev.get('fight_id') or ev.get('key') or ev['at'], []).append(ev)
    parts = []
    for number, (fight_id, sides) in enumerate(
            sorted(by_fight.items(), key=lambda item: min(ev['at'] for ev in item[1])), 1):
        at = min(ev['at'] for ev in sides)
        first = sides[0]
        record = first.get('record') or {}
        detail = record.get('detail') or {}
        me, other = first['who'], record.get('opponent', 'another squid')
        attacker = me if detail.get('started_it') else other
        defender = other if attacker == me else me
        host = next((ev['who'] for ev in sides if not ev.get('was_away')), None)
        where = f"{host}’s tank" if host else 'a tank'
        winner = me if detail.get('won') else other
        mine, theirs = detail.get('mine') or {}, detail.get('theirs') or {}
        ability = {me: mine.get('ability'), other: theirs.get('ability')}
        chance = detail.get('chance')
        chance_of = {me: chance, other: (1 - chance) if isinstance(chance, (int, float)) else None}
        why = detail.get('why_started') or {}

        figures = [fig(key, f"Fight {number}, in {where}: the cloud over {attacker} and {defender}")
                   for key, info in sorted(shots.items(), key=lambda item: item[1]['at'])
                   if info.get('fight_id') == fight_id][:3]

        started = [f"{attacker} started it."]
        if why.get('aggression') is not None:
            started.append(f"Its aggression neuron was at {float(why['aggression']):.0f}; a squid "
                           f"goes for another once that passes {record_threshold:g}.")
        if why.get('provoked_by'):
            started.append(f"What it was aggressive about: {why['provoked_by']}.")
        born = ((final.get(attacker) or {}).get('social_knowledge') or {}).get('aggression', {}).get('born')
        if born:
            started.append(f"Where that aggression came from: {born}.")
        decided = []
        if ability.get(attacker) is not None and ability.get(defender) is not None:
            decided.append(f"{attacker}’s ability was {float(ability[attacker]):.0f} and "
                           f"{defender}’s {float(ability[defender]):.0f} - body, experience and how "
                           f"hard each one’s network committed.")
        if chance_of.get(winner) is not None:
            decided.append(f"That gave {winner} a {100 * chance_of[winner]:.0f}% chance. {winner} won.")
        for side_name, side in ((me, mine), (other, theirs)):
            reasons = side.get('fitness_reasons') or side.get('reasons')
            if isinstance(reasons, dict) and reasons:
                decided.append(f"{side_name}: " + ', '.join(
                    f"{key.replace('_', ' ')} {value:g}" if isinstance(value, (int, float))
                    else f"{key.replace('_', ' ')} {value}" for key, value in reasons.items()))
        cost = detail.get('consequences') or {}
        if cost:
            decided.append("What it cost: " + '; '.join(
                f"{key.replace('_', ' ')} {value}" for key, value in cost.items()))

        blocks = [f'<h3>Fight {number}: {e(attacker)} goes for {e(defender)}, {_in_words(at - began)} in, '
                  f'in {e(where)}</h3>',
                  row(figures) if figures else
                  '<p class="note">No picture was taken while this fight was happening.</p>',
                  f'<h4>Why it started</h4><p>{e(" ".join(started))}</p>',
                  mind(f'{attacker}, in the two minutes before',
                       _nearby_thoughts(attacker, at, 120, -3)[-6:]),
                  f'<h4>How it was decided</h4><p>{e(" ".join(decided))}</p>',
                  '<h4>What each remembers of it</h4>'
                  + ''.join(mind(ev['who'], [ev['text']]) for ev in sides),
                  '<h4>What each took from it</h4>'
                  + ''.join(mind(name, _nearby_thoughts(name, at, 3, 150)[:8])
                            for name in dict.fromkeys([attacker, defender]))]
        rises = [(name, rise) for name in (attacker, defender)
                 for rise in (((final.get(name) or {}).get('social_knowledge') or {})
                              .get('aggression', {}).get('rises') or [])
                 if abs(float(rise.get('at', 0)) - at) < 30]
        if rises:
            blocks.append('<p>' + e(' '.join(
                f"{name}’s aggression now rests at {rise['to']:g}, not {rise['from']:g}, for good: "
                f"it {rise['cause']}." for name, rise in rises)) + '</p>')
        parts.append(''.join(block for block in blocks if block))
    return (f'<section id="fight" class="chapter"><h2>The fight{"s" if len(parts) != 1 else ""}</h2>'
            f'<p>{len(parts)} fight{"s" if len(parts) != 1 else ""} broke out in the session. Nobody '
            'chose them: a fight starts in one squid’s own grown aggression neuron, and what follows '
            'is each squid’s own record of it.</p>' + ''.join(parts) + '</section>')


def fight_section():
    if not fights:
        return ('<p>Nobody fought. A fight starts in a squid’s own grown aggression neuron, and in '
                f'these {minutes:g} minutes no squid grew one: none of them went at another while its '
                'anxiety was high. '
                + (f'{len(memories)} encounter{"s were" if len(memories) != 1 else " was"} remembered '
                   'instead:</p>' if memories else 'No encounter was remembered either.</p>')
                + mind('The squid', [f"{ev['who']}: {ev['text']}" for ev in memories][:6]))
    return ('<p>See <a href="#fight">the fight chapter</a> above: '
            + e('; '.join(f"{clock(ev)} {ev['who']}: {ev['text']}" for ev in fights)) + '</p>')


def visit_figures():
    figures = [fig(key, shot_caption(key)) for key in shots_like('visit')][:3]
    empties = [fig(key, shot_caption(key)) for key in shots_like('empty')][:3 - min(3, len(figures))]
    return row(figures + empties)


def platform_section():
    folder = args.platforms
    if not folder or not folder.is_dir():
        return ''
    labels = [('windows', 'Windows'), ('macos', 'macOS'), ('linux-x11', 'Linux, X11'),
              ('linux-wayland', 'Linux, Wayland')]
    tanks, brains = [], []
    for label, title in labels:
        tank, brain = folder / label / 'main.png', folder / label / 'brain-1.png'
        if tank.exists():
            webp(tank, f'platform-{label}-tank')
            tanks.append(fig(f'platform-{label}-tank', f'The tank on {title}'))
        if brain.exists():
            webp(brain, f'platform-{label}-brain')
            brains.append(fig(f'platform-{label}-brain', f'The Brain Tool on {title}'))
    if not tanks:
        return ''
    return f"""
<section id="everywhere" class="chapter">
  <h2><span class="num alt">6</span>The same game on every system</h2>
  <p>The four homes above could have been four different computers. The game brings its own font
  (Fio UI), its own emoji, its own widget style and one text engine, so its windows are the same size
  and the same layout on Windows, macOS and Linux, under X11 and under Wayland. These were taken on
  GitHub’s own machines of each kind by <code>tools/capture_platforms.py</code>; the measurements and
  the rest of the pictures are in <code>docs/platform-screenshots</code>.</p>
  <div class="row platforms">{''.join(tanks)}</div>
  <div class="row platforms">{''.join(brains)}</div>
</section>"""


first_left = left[0] if left else None
alone = row([fig(f"home{p['home']}-alone", shot_caption(f"home{p['home']}-alone"))
             for p in players if f"home{p['home']}-alone" in shots], 'platforms')
ends = row([fig(f"home{p['home']}-end", shot_caption(f"home{p['home']}-end"))
            for p in players if f"home{p['home']}-end" in shots], 'platforms')
brains = row([fig(f"home{p['home']}-brain", shot_caption(f"home{p['home']}-brain"))
              for p in players if f"home{p['home']}-brain" in shots][:2])
aquarium = [ev for ev in grew if ev['neuron'] == 'aquarium_nearby']
isolation = session.get('isolation', {})
unanswered = all(v == 'no answer' for v in isolation.values()) if isolation else None
heard_before = sum(p.get('tanks_heard_before_any_code', 0) for p in players)
refused = sum((session['final'].get(n) or {}).get('packets_refused', 0) for n in names)
counts = session.get('counts', {})

CSS = (HERE / 'style.css').read_text()
JS = (HERE / 'lightbox.js').read_text()

page = f"""<title>Dosidicus Story Gallery</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
{CSS}
</style>

<header class="hero">
  <p class="eyebrow">Dosidicus · internet play</p>
  <h1>{len(players)} squid, {len(players)} homes, {minutes:g} minutes</h1>
  <p class="lede">{games_in_words}, each in a home of its own behind its own router,
  found each other with friend codes and were then left alone for {minutes:g} minutes. Nothing told any squid
  what to do. This is what happened, as it was written down while it happened: every address, code, thought,
  message and number below is from the run.</p>
  <dl class="cast">{cast()}</dl>
  <nav class="toc" aria-label="Chapters">
    <a href="#onion-and-cuthbert">Player story · Onion and Cuthbert</a>
    <a href="#apart">1 · Apart</a><a href="#codes">2 · Friend codes</a><a href="#visits">3 · Who went where</a>
    <a href="#grew">4 · What they grew</a><a href="#believed">5 · What they came to believe</a>
    <a href="#everywhere">6 · Every system</a><a href="#timeline">Everything, in order</a>
  </nav>
</header>

<main>
<section id="onion-and-cuthbert" class="chapter">
  <h2>Onion and Cuthbert: a visit between two cities</h2>
  <p>On 11 November 2026, Onion left his tank to visit Cuthbert over the public internet.
  His caretaker saw an empty tank; the caretaker in the other city witnessed Cuthbert throwing rocks.
  Onion returned with a bad memory. Cuthbert recorded two hits, no fights, and enjoyment of rock play,
  alongside both negative and positive social records.</p>
  <p>This player story is separate from the private-network demonstration above.
  <a href="onion-and-cuthbert/README.md">Read the account and its evidence</a>.</p>
</section>


<section id="apart" class="chapter">
  <h2><span class="num">1</span>Apart</h2>
  <p>Every home has the same private address, <code>{e(players[0]['private_address'])}</code>, as real homes do,
  and a router that rewrites it to the router’s own outside address and lets nothing in that the home did not
  first send to. Before any code was entered, the {len(players)} tanks between them had heard
  <strong>{heard_before}</strong> other tanks{'' if unanswered is None else
  ', and a message sent unasked from one home to another home’s router got '
  + ('no answer' if unanswered else 'an answer')}.
  Each squid was a new hatchling, alone:</p>
  {alone}
</section>

<section id="codes" class="chapter">
  <h2><span class="num">2</span>Friend codes</h2>
  <p>Each game asked the address server on the shared network what address it was seen at, and built its friend
  code from the answer (the cast list above has them). The players passed the codes round: everyone entered
  everyone else’s, {len(entered)} entries in all. The last of the {len(links)} links through the routers came up
  <strong>{last_link:.0f} second{'s' if round(last_link) != 1 else ''}</strong> after the codes were entered;
  {refused} message{'s were' if refused != 1 else ' was'} refused for showing no invitation.</p>
  <p>Within moments {len(aquarium)} of the {len(players)} squid had grown a sense none of them hatched with:</p>
  <p class="chips">{chips(sorted({ev['neuron'] for ev in aquarium}))}</p>
  {mind(aquarium[0]['who'], thoughts_of(aquarium[0]['who'], contains='aquarium', limit=2)) if aquarium else ''}
</section>

<section id="visits" class="chapter">
  <h2><span class="num">3</span>Who went where</h2>
  <p>{f"{e(first_left['who'])} was first out, {clock(first_left)} after the codes went in." if first_left else
      'No squid left its tank.'}
  {f'{len(left)} departures in all; the most squid in one tank at once was {most_in_one_tank}.' if left else ''}
  {(e(', '.join(stayed_home)) + (' never left home.' if len(stayed_home) == 1 else ' never left home.')) if stayed_home and left else ''}
  A squid leaves when its own network takes it out, and comes home when its own rule says so; a tank whose squid
  is out can still be visited.</p>
  <table class="visits"><thead><tr><th>When</th><th>Who</th><th>What</th></tr></thead>
  <tbody>{visits_table()}</tbody></table>
  {visit_figures()}
  {mind(first_left['who'], thoughts_of(first_left['who'], starts='Another aquarium', limit=1)) if first_left else ''}
</section>

<section id="grew" class="chapter">
  <h2><span class="num">4</span>What they grew</h2>
  <p>A squid grows a neuron only for something it has no way to represent. None of them hatched knowing that
  other squid exist. In these {minutes:g} minutes they grew {len(grew)} neurons between them, each with the
  reason recorded in the squid’s own words:</p>
  {grown_section()}
  {brains}
</section>

{fight_chapter()}
<section id="believed" class="chapter">
  <h2><span class="num">5</span>What they came to believe, and what they remember</h2>
  {belief_section()}
  <h3>Fights</h3>
  {fight_section()}
  <h3>At the end</h3>
  {ends}
</section>
{platform_section()}

<section id="timeline" class="chapter">
  <h2>Everything, in order</h2>
  <p>{len(timeline)} things were written down between the codes going in and the end of the session
  ({', '.join(f'{count} {kind}' for kind, count in sorted(counts.items()))}). All of them:</p>
  <details><summary>The whole session, line by line</summary>
  <pre class="log">{e(chr(10).join(ev['line'] for ev in timeline))}</pre></details>
</section>

<section id="chosen" class="chapter disclosure">
  <h2>What was chosen, and what was not</h2>
  <ol>
    <li>Chosen, as four players would: each squid’s name and personality, and the colour three of them were
    given on the About tab. A squid’s colour goes with it, so it is the same colour in every tank it visits.</li>
    <li>Not touched: any drive, any timing, any chance. The squid were new hatchlings with the drives the game
    gave them, time ran at the game’s own speed, nobody fed or cleaned, and the chance of mating was the game’s
    own (a squid has to be an hour old before it can at all).</li>
    <li>The “internet” is a private one made on a single machine out of Linux network namespaces: real address
    translation and real routing, but not real home routers. These routers keep a tank’s port the same whoever
    it talks to, which is what most home routers do and what makes “both players enter each other’s code”
    work. A router that gives every destination a different port would need the port forwarded instead.</li>
    <li>What this session showed is missing: two visitors in the same tank sense the tank’s own squid, but not
    yet each other.</li>
  </ol>
</section>

<section class="chapter how">
  <h2>How this was made</h2>
  <ul>
    <li><code>tools/internet_session.py</code> builds the homes and routers, starts one real game process in
    each home (offscreen Qt), passes the friend codes round, and then only watches, writing every event to
    <code>session.json</code> and saving each window as it goes.</li>
    <li><code>docs/story-gallery/source/build.py</code> builds this page from that file. The thoughts and game
    messages are copied from the run, not written for the page.</li>
    <li>Run it again and the story is a different one: nothing here is scripted.</li>
  </ul>
</section>
</main>

<dialog id="lightbox" aria-label="Enlarged screenshot">
  <form method="dialog"><button class="close" aria-label="Close">×</button></form>
  <img alt="">
  <p class="lb-caption"></p>
</dialog>
<script>
{JS}
</script>
"""
if args.fragment:
    args.fragment.write_text(page)
(OUT / 'index.html').write_text(
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    + page.replace('<header class="hero">', '</head>\n<body>\n<header class="hero">', 1)
    + '</body>\n</html>\n')


# ------------------------------------------------- the same story for GitHub
# GitHub shows a folder's README, not its index.html: the short version, with
# the pictures, for anyone who arrives there.
def md_images(keys, limit=4):
    cells = [f'![{shots[k]["caption"]}](img/{k}.webp)' for k in keys if k in SIZES][:limit]
    if not cells:
        return ''
    return '| ' + ' | '.join(cells) + ' |\n|' + '---|' * len(cells) + '\n'


md = [f'# {len(players)} squid, {len(players)} homes, {minutes:g} minutes', '',
      f'{games_in_words}, each in a home of its own behind its own router, '
      f'found each other with friend codes and were then left alone for {minutes:g} minutes. Nothing '
      'told any squid what to do. Every address, code, thought and number here is from the run.', '',
      '**The full page, with every picture and the whole session line by line, is '
      '[index.html](index.html)** (open it in a browser).', '',
      '| Squid | Personality | Colour | Home address | Seen from outside as | Friend code |',
      '|---|---|---|---|---|---|']
md[2:2] = ['**Player story:** [Onion and Cuthbert: an intercity visit, two rocks, and an empty tank](onion-and-cuthbert/README.md). A real public-internet encounter on 11 November 2026, documented separately from the demonstration below.', '']
for p in players:
    colour = 'rgb({},{},{})'.format(*p['colour']) if p.get('colour') else 'as it hatched'
    md.append(f"| {p['name']} | {p['personality']} | {colour} | `{p['private_address']}` | "
              f"`{p['seen_from_outside_as']}` | `{p['friend_code']}` |")
md += ['', '## Apart, then linked', '',
       f'Before any code was entered the tanks had heard {heard_before} other tanks between them. '
       f'Everyone entered everyone else’s code; the last of the {len(links)} links through the routers '
       f'came up {last_link:.0f} s later.', '',
       md_images([f"home{p['home']}-alone" for p in players]),
       '## Who went where', '', '| When | Who | What |', '|---|---|---|']
for ev in sorted(left + homecomings, key=lambda x: x['at']):
    if ev['kind'] == 'left':
        where = ev['line'].rsplit(' - ', 1)[-1] if ' - ' in ev['line'] else 'another tank'
        md.append(f"| {clock(ev)} | {ev['who']} | swam out of its own tank, to {where} |")
    else:
        md.append(f"| {clock(ev)} | {ev['who']} | came home |")
md += ['', md_images(shots_like('visit') + shots_like('empty'), 3),
       '## What they grew', '']
for name in names:
    neurons = [ev['neuron'] for ev in events('grew', name)]
    md.append(f"- **{name}**: " + (', '.join(f'`{n}`' for n in neurons) if neurons else 'nothing new'))
md += ['', '## What they came to believe', '']
for ev in beliefs:
    md.append(f"- {clock(ev)} {ev['who']} {ev['text']}")
for ev in revised:
    md.append(f"- {clock(ev)} {ev['who']} {ev['text']}")
if not beliefs:
    md.append('Nothing, in this session.')
# A fight written up by hand from a session's records (source/fight.md), if
# there is one: it goes in ahead of this session's own list.
_written_up = HERE / 'fight.md'
if _written_up.exists():
    md += ['', _written_up.read_text().rstrip()]
md += ['', '## Fights in the four-tank session' if _written_up.exists() else '## Fights', '']
if fights:
    fight_pictures = [key for key, info in sorted(shots.items(), key=lambda item: item[1]['at'])
                      if info.get('fight_id')]
    if fight_pictures:
        md += [md_images(fight_pictures[:3]), '']
    for ev in fights:
        detail = (ev.get('record') or {}).get('detail') or {}
        why = detail.get('why_started') or {}
        md.append(f"- {clock(ev)} **{ev['who']}**: {ev['text']}"
                  + (f" It started it, with its aggression at {float(why['aggression']):.0f}."
                     if detail.get('started_it') and why.get('aggression') is not None else ''))
    md += ['', 'Why each fight started, how it was decided, and what each squid thought, '
               'remembers and took from it are in the fight chapter of [index.html](index.html).']
else:
    md.append('Nobody fought in this session.')
md += ['', md_images([f"home{p['home']}-end" for p in players]),
       '---', '',
       'Made by `tools/internet_session.py` (the session) and '
       '`docs/story-gallery/source/build.py` (this page and index.html). Nothing was nudged: '
       'only each squid’s name, personality and colour were chosen. The “internet” is a private one '
       'made on one machine out of network namespaces - real address translation, not real home '
       'routers.', '']
(OUT / 'README.md').write_text('\n'.join(md))
total = sum(p.stat().st_size for p in (OUT / 'img').iterdir())
print('ok', len(SIZES), 'images', round(total / 1024), 'KiB')

