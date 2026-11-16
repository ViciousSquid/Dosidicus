"""Every language file stays in step with English.

English (`translations/en.py`) is the reference: the game falls back to it,
and it is the file a translator copies. These checks catch the mistakes that
are otherwise only found by playing the game in each language:

* a key defined twice in one file (the second silently replaces the first);
* a `{placeholder}` the code never supplies, which raises at display time;
* English keys a language lacks. Known gaps are recorded below and may only
  shrink, so a new English string cannot be forgotten in a finished language.
"""
import ast
import importlib
import string
from pathlib import Path

import pytest

TRANSLATIONS = Path(__file__).resolve().parents[1] / 'translations'
LANGUAGES = sorted(p.stem for p in TRANSLATIONS.glob('*.py'))

# How many English keys each language may still be missing. Lower a number
# when you translate some; never raise one.
KNOWN_MISSING = {
    'de': 493,
    'ml': 2,
}


def _table(code):
    return importlib.import_module(f'translations.{code}').translations


def _placeholders(text):
    return {name.split('.')[0].split('[')[0]
            for _, name, _, _ in string.Formatter().parse(text) if name}


ENGLISH = _table('en')


def test_english_is_present():
    assert 'en' in LANGUAGES and len(ENGLISH) > 500


@pytest.mark.parametrize('code', LANGUAGES)
def test_no_key_is_defined_twice(code):
    tree = ast.parse((TRANSLATIONS / f'{code}.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            repeated = sorted({k for k in keys if keys.count(k) > 1})
            assert not repeated, f'{code}.py defines these keys more than once: {repeated}'


@pytest.mark.parametrize('code', LANGUAGES)
def test_every_value_is_text(code):
    wrong = [k for k, v in _table(code).items() if not isinstance(v, str)]
    assert not wrong


@pytest.mark.parametrize('code', LANGUAGES)
def test_placeholders_are_ones_english_supplies(code):
    table = _table(code)
    wrong = {}
    for key, text in table.items():
        if key not in ENGLISH:
            continue
        try:
            extra = _placeholders(text) - _placeholders(ENGLISH[key])
        except ValueError as exc:          # unbalanced braces
            extra = {f'<malformed: {exc}>'}
        if extra:
            wrong[key] = sorted(extra)
    assert not wrong, f'{code}.py uses placeholders the English string does not have: {wrong}'


@pytest.mark.parametrize('code', [c for c in LANGUAGES if c != 'en'])
def test_missing_keys_do_not_grow(code):
    missing = sorted(set(ENGLISH) - set(_table(code)))
    allowed = KNOWN_MISSING.get(code, 0)
    assert len(missing) <= allowed, (
        f'{code}.py is missing {len(missing)} English keys (allowed: {allowed}). '
        f'First few: {missing[:10]}')
    assert len(missing) == allowed, (
        f'{code}.py is now missing only {len(missing)} keys - '
        f'lower KNOWN_MISSING[{code!r}] to {len(missing)} to lock that in.')
