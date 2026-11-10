#!/usr/bin/env python3
"""Make the game's two emoji fonts: the emoji the game uses, and no others.

  src/fonts/DosidicusEmoji.ttf       in colour, from Noto Color Emoji
  src/fonts/DosidicusLineEmoji.ttf   black-and-white line drawings, from Noto
                                     Emoji - for where a plain one is wanted
                                     (the Brain Designer button)

Every system draws emoji with its own font, so the same button showed three
different brains on Windows, a Mac and Linux. The game now carries its own:
Noto Color Emoji (Google, SIL Open Font License 1.1), cut down to the emoji
that appear in the game's own text - about a megabyte instead of eleven -
and renamed "Dosidicus Emoji" so it can never be confused with a full Noto
Color Emoji installed on the system.

Run this again after adding an emoji to the game (tests/test_desktop_style.py
fails until it is in the font):

    pip install fonttools
    python tools/subset_emoji_font.py /path/to/NotoColorEmoji.ttf \
        --line "/path/to/NotoEmoji[wght].ttf"

NotoColorEmoji.ttf: https://github.com/googlefonts/noto-emoji (fonts/), or
the fonts-noto-color-emoji package on Debian and Ubuntu
(/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf).
NotoEmoji[wght].ttf: https://github.com/google/fonts (ofl/notoemoji/).
"""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'src' / 'fonts' / 'DosidicusEmoji.ttf'
FAMILY = 'Dosidicus Emoji'
LINE_OUTPUT = ROOT / 'src' / 'fonts' / 'DosidicusLineEmoji.ttf'
LINE_FAMILY = 'Dosidicus Line Emoji'
#: How heavy the lines are (Noto Emoji goes from 300 to 700).
LINE_WEIGHT = 400
#: Where the game's own text is.
SOURCES = ('main.py', 'src', 'plugins', 'translations', 'custom_brains', 'config.ini')
SUFFIXES = {'.py', '.json', '.ini', '.txt', '.md', '.html'}
#: Emoji and pictographs (not arrows and ticks: those are text, and come from
#: the text fonts).
EMOJI = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿⌚-⏿⤴⤵'
                   '▪-◾↔-↪〰〽㊗㊙©®™]')
#: Joiners and selectors that hold sequences together, the keycap mark, and
#: the five skin tones.
ALWAYS = '‍️︎⃣' + ''.join(chr(c) for c in range(0x1F3FB, 0x1F400))


def emoji_in_the_game():
    """Every emoji character in the game's own text."""
    found = set()
    for name in SOURCES:
        path = ROOT / name
        files = [path] if path.is_file() else [p for p in path.rglob('*')
                                               if p.is_file() and p.suffix in SUFFIXES]
        for file in files:
            try:
                found.update(EMOJI.findall(file.read_text(encoding='utf-8')))
            except (UnicodeDecodeError, OSError):
                continue
    return found


def make(source, output=OUTPUT, family=FAMILY, parent='Noto Color Emoji', weight=None):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    FAMILY = family                                 # the name written into the font
    wanted = ''.join(sorted(emoji_in_the_game())) + ALWAYS
    options = subset.Options()
    options.layout_features = ['*']             # the joins that make sequences
    options.name_IDs = ['*']
    options.notdef_outline = True
    options.glyph_names = False
    font = TTFont(str(source))
    if weight is not None and 'fvar' in font:       # one weight of a variable font
        from fontTools.varLib import instancer
        font = instancer.instantiateVariableFont(font, {'wght': weight})
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=wanted)
    subsetter.subset(font)
    for record in font['name'].names:
        if record.nameID in (1, 16):
            record.string = FAMILY
        elif record.nameID == 4:
            record.string = FAMILY
        elif record.nameID == 6:
            record.string = FAMILY.replace(' ', '')
        elif record.nameID == 3:
            record.string = f'{FAMILY}: a subset of {parent}'
    output.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(output))
    kept = len(set(font.getBestCmap()))
    return kept, output.stat().st_size


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('noto_color_emoji', type=Path, help='the full NotoColorEmoji.ttf')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--line', type=Path,
                        help='the variable NotoEmoji[wght].ttf: also make the line font')
    parser.add_argument('--line-output', type=Path, default=LINE_OUTPUT)
    args = parser.parse_args()
    if not args.noto_color_emoji.is_file():
        sys.exit(f'{args.noto_color_emoji} is not there')
    characters, size = make(args.noto_color_emoji, args.output)
    print(f'{args.output}: {characters} characters, {size / 1024:.0f} KB '
          f'({len(emoji_in_the_game())} emoji found in the game)')
    if args.line:
        if not args.line.is_file():
            sys.exit(f'{args.line} is not there')
        characters, size = make(args.line, args.line_output, LINE_FAMILY, 'Noto Emoji',
                                LINE_WEIGHT)
        print(f'{args.line_output}: {characters} characters, {size / 1024:.0f} KB')
