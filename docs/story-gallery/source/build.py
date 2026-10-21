"""Build the story gallery from one desktop run and one Android run.

python build.py STORY_DIR ANDROID_DIR [--out DIR] [--fragment FILE]

STORY_DIR is what tools/capture_story.py wrote, ANDROID_DIR what
tools/capture_android.py wrote. Every caption, thought, message, number and
nudge on the page comes from their JSON. Writes index.html and img/*.webp in
--out (default: the folder above this one); --fragment also writes the page
without its document skeleton, for a host that supplies one.
"""
import argparse
import html
import json
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('story', type=Path)
parser.add_argument('android', type=Path)
parser.add_argument('--out', type=Path, default=HERE.parent)
parser.add_argument('--fragment', type=Path)
args = parser.parse_args()
story_dir, android_dir, OUT = args.story, args.android, args.out
story = json.loads((story_dir / 'story.json').read_text())
android = json.loads((android_dir / 'android.json').read_text())
(OUT / 'img').mkdir(parents=True, exist_ok=True)

SIZES = {}


def webp(src, name):
    im = Image.open(src).convert('RGB')
    out = OUT / 'img' / f'{name}.webp'
    im.save(out, 'WEBP', lossless=True, method=6)
    SIZES[name] = im.size
    return f'img/{name}.webp'


for name in story['shots']:
    webp(story_dir / 'shots' / f'{name}.png', name)
for name in android['shots']:
    webp(android_dir / 'shots' / f'{name}.png', name)

e = html.escape
ziggy, inky = story['notes']['ziggy'], story['notes']['inky']


def thought_after(thoughts, start):
    return next((t for t in thoughts if t.startswith(start)), None)


def fig(name, caption=None, wide=False):
    w, h = SIZES[name]
    caption = caption or story['shots'].get(name, android['shots'].get(name, {})).get('caption', '')
    return (f'<figure class="shot{" wide" if wide else ""}">'
            f'<button class="zoom" type="button" data-full="img/{name}.webp" data-caption="{e(caption)}" '
            f'aria-label="Enlarge: {e(caption)}">'
            f'<img src="img/{name}.webp" width="{w}" height="{h}" alt="{e(caption)}" loading="lazy">'
            f'</button><figcaption>{e(caption)}</figcaption></figure>')


def thoughts(who, lines):
    lines = [l for l in lines if l]
    if not lines:
        return ''
    items = ''.join(f'<li>{e(l)}</li>' for l in lines)
    return f'<aside class="mind"><p class="mind-label">{e(who)}’s own account</p><ul>{items}</ul></aside>'


def neurons(names):
    return ''.join(f'<span class="chip social">{e(n)}</span>' for n in names)


aware = [thought_after(ziggy['leave_thoughts'], 'It sensed another aquarium')]
leave = [thought_after(ziggy['leave_thoughts'], 'Another aquarium is nearby')]
fight_inky = [thought_after(inky['fight_thoughts'], 'I went for'),
              thought_after(inky['fight_thoughts'], 'I lost') or thought_after(inky['fight_thoughts'], 'I won')]
fight_ziggy = [thought_after(ziggy['home_thoughts'], 'Inky came at me'),
               thought_after(ziggy['home_thoughts'], 'I won') or thought_after(ziggy['home_thoughts'], 'I lost')]
home = [thought_after(ziggy['home_thoughts'], 'I am tired')]
inky_msgs = [m for _, m in story['messages']['inky']]
fight_msg = next((m for m in inky_msgs if m.startswith('Inky:')), '')
egg_msg = next((m for m in inky_msgs if 'produced an egg' in m), '')
epitaph = inky.get('epitaph', '').replace('<span>', '').replace('</span>', '').split('<br>')
won, lost = inky['fight']['won'], inky['fight']['lost']
death_cause = inky.get('death', {}).get('cause', '')
parents = ' and '.join(inky.get('inherited_parents') or inky.get('inherited_from') or [])
synapses = inky.get('inherited_synapses', 0)
pip_social = android['notes']['pip'].get('social', [])
nudges = story['nudges'] + [f'Android: {n}' for n in android['nudges']]

CSS = (HERE / 'style.css').read_text()
JS = (HERE / 'lightbox.js').read_text()

page = f"""<title>Dosidicus Story Gallery</title>
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<style>
{CSS}
</style>

<header class="hero">
  <p class="eyebrow">Dosidicus · peer-to-peer evolution</p>
  <h1>A life across two tanks</h1>
  <p class="lede">Two copies of the desktop game, networked over the multiplayer plugin’s LAN protocol, and two copies
  of the Android app linked for a visit, captured as they ran. One squid notices another tank, goes there, fights,
  mates, and dies. Its egg then starts a new game. Every squid here is moved by its own network, and every
  number and line of thought is from the run.</p>
  <dl class="cast">
    <div><dt>Ziggy</dt><dd>adventurous · the traveller</dd></div>
    <div><dt>Inky</dt><dd>timid · the resident</dd></div>
    <div><dt>Pip &amp; Nova</dt><dd>the Android pair</dd></div>
  </dl>
  <nav class="toc" aria-label="Chapters">
    <a href="#aware">1 Aware</a><a href="#visit">2 Visit</a><a href="#fight">3 Fight</a><a href="#mate">4 Mate</a>
    <a href="#dies">5 Dies</a><a href="#new-game">6 New game</a><a href="#networked">Two desktops</a>
    <a href="#android">Android</a><a href="#nudges">What was nudged</a>
  </nav>
</header>

<main>
<section id="aware" class="chapter">
  <h2><span class="num">1</span>Ziggy becomes aware of another tank</h2>
  <p>Inky’s game comes up on the same network. Ziggy had no way to sense another aquarium, so its brain grew one:
  <code>aquarium_nearby</code>, the first neuron on a SOCIAL band that did not exist a moment before. Nothing is
  pre-wired; social senses grow only from encounters.</p>
  <div class="row two">{fig('ziggy-aware-tank')}{fig('ziggy-aware-brain')}</div>
  {thoughts('Ziggy', aware)}
</section>

<section id="visit" class="chapter">
  <h2><span class="num">2</span>It decides to visit</h2>
  <p>No rule sends it. With curiosity high, Ziggy’s own network takes it to the edge of its tank and out. Its body
  crosses into Inky’s tank, but its brain keeps running at home. Inky’s game sends it what its body perceives,
  and it sends back what it means to do.</p>
  <div class="row one">{fig('ziggy-leaving', wide=True)}</div>
  {thoughts('Ziggy', leave)}
</section>

<section id="networked" class="chapter split">
  <h2><span class="num alt">⇄</span>Two desktop games, networked</h2>
  <p>The same moment in two separate desktop processes, talking over UDP multicast, the same as two PCs on a LAN.
  On the left, Ziggy’s home tank stands empty while Ziggy is away. On the right, Ziggy’s body enters Inky’s tank,
  driven from the other process.</p>
  <div class="row two pair">
    {fig('ziggy-away-home', 'Ziggy’s game: its tank while Ziggy is away')}
    {fig('inky-arrival', 'Inky’s game: Ziggy’s body arrives; its brain is still at home')}
  </div>
</section>

<section id="fight" class="chapter">
  <h2><span class="num">3</span>They get into a fight</h2>
  <p>Inky is holding a rock. When Ziggy comes close, the rock between them flashes dark red: it is what they are
  fighting over. Then the scuffle. Who starts it is each squid’s aggression, and who wins comes from each one’s
  ability, personality, experience and condition, never a script.</p>
  <div class="row two">{fig('inky-fight-leadin')}{fig('inky-fight-cloud')}</div>
  <div class="row two minds">{thoughts('Inky', fight_inky)}{thoughts('Ziggy', fight_ziggy)}</div>
  {f'<p class="game-msg"><span>Inky’s game says</span>{e(fight_msg)}</p>' if fight_msg else ''}
</section>

<section id="mate" class="chapter">
  <h2><span class="num">4</span>They mate</h2>
  <p>Still in contact after the fight, the two mate: one heart beats over the pair. Inky lays an egg and, as a
  parent, stops eating. The egg holds both parents’ weights; Ziggy’s came over the network as a gamete.</p>
  <div class="row two">{fig('inky-mating')}{fig('inky-egg')}</div>
  {f'<p class="game-msg"><span>Inky’s game says</span>{e(egg_msg)}</p>' if egg_msg else ''}
  <h3>Ziggy goes home, changed</h3>
  <p>Tired, Ziggy goes home to sleep, by its own rule. It comes back with a social network it did not have before
  the visit:</p>
  <p class="chips">{neurons(ziggy.get('social', []))}</p>
  <div class="row two">{fig('ziggy-home')}{fig('ziggy-home-brain')}</div>
  {thoughts('Ziggy', home)}
</section>

<section id="dies" class="chapter">
  <h2><span class="num">5</span>Inky dies</h2>
  <p>A parent keeps its egg and will not eat. Inky {e('starves' if death_cause == 'starved' else 'dies')}, and a
  headstone marks the spot, beside the egg. Hovering over the headstone shows the epitaph:</p>
  <div class="row one">{fig('inky-dead', wide=True)}</div>
  <blockquote class="epitaph">{'<br>'.join(e(line) for line in epitaph)}</blockquote>
</section>

<section id="new-game" class="chapter">
  <h2><span class="num">6</span>A new game starts</h2>
  <p>The egg hatches, and that is a new game. There is no way out, just as a game starts with no save. The
  hatchling begins with a newborn brain overlaid with half of each parent’s weights:
  <strong>{synapses}</strong> synapses inherited from {e(parents)}, each recorded in the brain’s ledger with the
  parent it came from. It has no memories, and its parent’s headstone stays in the tank.</p>
  <div class="row three">{fig('inky-hatching')}{fig('inky-hatchling')}{fig('inky-hatchling-brain')}</div>
</section>

<section id="android" class="chapter">
  <h2><span class="num alt">▣</span>An Android multiplayer session</h2>
  <p>Two copies of the Android app (its Kivy UI and engine, phone-sized), each in its own process. Pip hosts, and
  Nova finds Pip and connects. Nova’s body swims in Pip’s tank while its brain stays on Nova’s phone, which says
  so. Pip, spoiling for a fight, scuffles with it, and Pip’s brain grows its own SOCIAL band:</p>
  <p class="chips">{neurons(pip_social)}</p>
  <div class="phones">
    {fig('android-nova-home')}{fig('android-nova-found')}{fig('android-nova-connected')}
    {fig('android-pip-connected')}{fig('android-pip-visitor')}{fig('android-nova-away')}
    {fig('android-pip-fight')}{fig('android-pip-brain')}
  </div>
  <p class="note">Google Nearby needs two phones with real radios, so for this capture a loopback socket stands in
  for it. It delivers the same events in the same order (peer found, connection initiated, accepted, connected,
  bytes) behind the same <code>NearbyManager</code> calls. Everything above the transport is the app as shipped.</p>
</section>

<section id="nudges" class="chapter disclosure">
  <h2>What was nudged</h2>
  <p>A lifetime has to fit in a few minutes, and the scenes have to happen while the camera is on. So the capture
  scripts set some drives and timings and log each change. They never choose an action for a squid. Every nudge,
  as logged:</p>
  <ol>{''.join(f'<li>{e(n)}</li>' for n in nudges)}</ol>
</section>

<section class="chapter how">
  <h2>How these were made</h2>
  <ul>
    <li><strong>Desktop:</strong> <code>tools/capture_story.py</code> runs two real game processes (offscreen Qt)
    with the multiplayer plugin on its multicast protocol, and screenshots each window.</li>
    <li><strong>Android:</strong> <code>tools/capture_android.py</code> runs the Kivy app twice under a virtual
    display and presses the buttons a player would: Host on one phone, Find and Connect on the other.</li>
    <li>The game messages and thoughts quoted here are copied from each run’s log, not written for the page:
    <code>docs/story-gallery/source/build.py</code> builds the page from the two runs’ JSON.</li>
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
total = sum(p.stat().st_size for p in (OUT / 'img').iterdir())
print('ok', len(SIZES), 'images', round(total / 1024), 'KiB')
