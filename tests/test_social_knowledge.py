"""What a squid knows about other squid - read from the squid, shown apart.

  * social memories (category 'social') are kept apart from what it knows of
    its tank: the Memory tab shows them on their own Social page;
  * its aggression is described in words, with where it rests and every
    event that raised that for good;
  * how it meets strangers is read from can_see_squid's synapses, with how
    much of that its encounters put there;
  * every fight it remembers says who started it and why;
  * social events reach the Decisions tab as thoughts, with their reasons.
"""
import io
import os
from contextlib import redirect_stdout
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5 import QtWidgets                                     # noqa: E402

from src import social_knowledge as sk                          # noqa: E402
from src.portable_brain import HeadlessBrain                    # noqa: E402
from src.social_learning import learn_from_encounter            # noqa: E402

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def met_a_squid(personality='adventurous'):
    brain = HeadlessBrain()
    brain.personality = personality
    brain.perceive('squid_in_view', 100.)
    assert brain.enhanced_neurogenesis.observe_social() == 'can_see_squid'
    return brain


def with_aggression(brain):
    brain.state.update(act_play=90., anxiety=80.)
    assert brain.enhanced_neurogenesis._grow_social_neuron(
        'aggression', ['act_play', 'anxiety']) == 'aggression'
    return brain


FIGHT = {'category': 'social', 'key': 'fight:f1', 'timestamp': 200.,
         'value': {'valence': -8., 'outcome': 'lost', 'opponent': 'Manuel',
                   'opponent_uuid': 'uuid-m', 'summary': 'Lost a fight it started.',
                   'detail': {'started_it': True, 'why_started': {'aggression': 72.},
                              'mine': {'committed_by': 'aggression', 'commitment': 72.},
                              'chance': .4}}}
DEFENDED = {'category': 'social', 'key': 'fight:f2', 'timestamp': 300.,
            'value': {'valence': 5., 'outcome': 'won', 'opponent': 'Manuel',
                      'opponent_uuid': 'uuid-m', 'summary': 'Won when it was attacked.',
                      'detail': {'started_it': False,
                                 'mine': {'committed_by': 'alarm', 'commitment': 85.}}}}
MET = {'category': 'social', 'key': 'peer:uuid-m', 'timestamp': 310.,
       'value': {'valence': -12., 'peer_name': 'Manuel', 'peer_personality': 'stubborn',
                 'outcome': 'hostile', 'detail': {'encounters': 2, 'fights_lost': 1,
                                                  'fights_won': 1, 'duration': 40.}}}
STRUCK = {'category': 'social', 'key': 'rock:t1', 'timestamp': 320.,
          'value': {'peer_uuid': 'uuid-m', 'hits_taken': 1, 'health': -2.}}
SNACK = {'category': 'food', 'key': 'sushi', 'value': 'Ate sushi', 'timestamp': 5.}


def test_social_memories_are_kept_apart_from_the_tank():
    social, environment = sk.split_memories([SNACK, FIGHT, MET, STRUCK])
    assert social == [FIGHT, MET, STRUCK] and environment == [SNACK]


def test_aggression_in_words_from_placid_to_fully_aggro():
    assert sk.aggression_in_words(0) == 'placid and relaxed'
    assert sk.aggression_in_words(50) == 'spoiling for a fight'
    assert sk.aggression_in_words(100) == 'fully aggro'


def test_a_squid_without_the_neuron_is_placid_and_starts_nothing():
    known = sk.aggression(HeadlessBrain())
    assert not known['grown'] and known['words'] == 'placid and relaxed'
    assert not known['starts_fights'] and known['rises'] == []


def test_aggression_says_where_it_rests_and_what_raised_it_for_good():
    brain = with_aggression(met_a_squid())
    brain.enhanced_neurogenesis.raise_resting_level('aggression', 8., 'lost a fight with Manuel')
    brain.state['aggression'] = 64.
    known = sk.aggression(brain)
    assert known['grown'] and known['starts_fights']
    assert (known['level'], known['words']) == (64., 'spoiling for a fight')
    assert (known['resting'], known['resting_words']) == (8., 'placid and relaxed')
    assert [r['cause'] for r in known['rises']] == ['lost a fight with Manuel']
    assert 'went at another squid' in known['born']


def test_how_it_meets_strangers_is_its_own_wiring_and_says_what_life_did():
    brain = met_a_squid('adventurous')
    before = sk.towards_strangers(brain)
    assert before['grown'] and before['learned'] == 0.
    for _ in range(6):
        learn_from_encounter(brain, -20., 'hostile', 'Manuel')
    after = sk.towards_strangers(brain)
    assert after['net'] < before['net'] and after['learned'] < 0
    assert sk.towards_strangers(HeadlessBrain())['words'] == 'has never seen another squid'


def test_the_grown_network_says_what_each_part_stands_for_and_why_it_grew():
    rows = sk.grown_network(with_aggression(met_a_squid()))
    assert [(r['name'], r['kind']) for r in rows] == [('can_see_squid', 'sense'),
                                                       ('aggression', 'neuron')]
    assert 'I see another squid' in rows[0]['concept'] and rows[0]['born']
    assert sk.grown_network(HeadlessBrain()) == []


def test_every_fight_says_who_started_it_and_why():
    rows = sk.fights([SNACK, FIGHT, DEFENDED])
    assert [r['key'] for r in rows] == ['fight:f2', 'fight:f1']   # newest first
    assert 'attacked' in rows[0]['how_it_started'] and '85' in rows[0]['how_it_started']
    assert rows[1]['started_it'] and 'aggression was 72' in rows[1]['how_it_started']


def test_it_remembers_individuals_from_encounters_fights_and_rocks():
    [manuel] = sk.acquaintances([MET, STRUCK, SNACK])
    assert manuel['name'] == 'Manuel' and manuel['personality'] == 'stubborn'
    assert (manuel['encounters'], manuel['hits_taken']) == (2, 1)
    assert manuel['feeling'] == 'remembers it badly'


def test_social_cards_read_as_sentences_not_dicts():
    assert sk.describe_memory(FIGHT)[:1] == ('Lost a fight with Manuel',)
    assert sk.describe_memory(FIGHT)[2] == -1
    title, text, sign = sk.describe_memory(MET)
    assert title == 'Hostile encounter with Manuel' and '{' not in text and sign == -1
    assert 'cannot know' in sk.describe_memory(STRUCK)[1]


def test_the_page_for_a_squid_with_no_social_neurons_says_only_enable_multiplayer():
    html = sk.to_html(sk.knowledge(HeadlessBrain(), [SNACK, FIGHT]))
    assert sk.NO_SOCIAL_NEURONS in html
    for absent in ('Social knowledge', 'Aggression', 'Manuel', 'Fights'):
        assert absent not in html


def test_the_message_is_translated_into_every_language():
    import importlib
    from pathlib import Path
    from src.localisation import Localisation
    languages = sorted(p.stem for p in (Path(__file__).resolve().parents[1]
                                        / 'translations').glob('*.py'))
    assert len(languages) >= 7
    seen = {}
    loc = Localisation.instance()
    try:
        for lang in languages:
            table = importlib.import_module(f'translations.{lang}').translations
            assert table.get(sk.NO_SOCIAL_NEURONS_KEY), lang
            assert table.get('social_knowledge'), lang
            loc.load_language(lang)
            html = sk.to_html(sk.knowledge(HeadlessBrain(), []))
            assert table[sk.NO_SOCIAL_NEURONS_KEY].replace("'", '&#x27;') in html, lang
            seen[lang] = table[sk.NO_SOCIAL_NEURONS_KEY]
    finally:
        loc.load_language('en')
    assert seen['en'] == sk.NO_SOCIAL_NEURONS
    others = [text for lang, text in seen.items() if lang not in ('en', 'ml')]
    assert sk.NO_SOCIAL_NEURONS not in others        # each really translated


def test_the_memory_tab_social_page_is_blank_without_social_neurons():
    from src.brain_memory_tab import MemoryTab
    legacy = {'category': 'social', 'key': 'squid_meeting', 'value': 'Met a squid',
              'timestamp': 9.}
    manager = SimpleNamespace(get_all_short_term_memories=lambda: [SNACK, legacy],
                              get_all_long_term_memories=lambda: [FIGHT])
    logic = SimpleNamespace(squid=SimpleNamespace(memory_manager=manager))
    with redirect_stdout(io.StringIO()):
        tab = MemoryTab(tamagotchi_logic=logic, brain_widget=HeadlessBrain())
        tab.update_memory_display()
    assert tab.social_cards_layout.count() == 0
    assert sk.NO_SOCIAL_NEURONS in tab.social_summary.text()
    assert tab.stm_content_layout.count() == 1            # the tank is unaffected
    tab.deleteLater()


def test_the_page_tells_the_whole_social_story():
    brain = with_aggression(met_a_squid())
    brain.enhanced_neurogenesis.raise_resting_level('aggression', 8., 'lost a fight with Manuel')
    html = sk.to_html(sk.knowledge(brain, [FIGHT, MET, STRUCK, SNACK]))
    for part in ('Aggression', 'lost a fight with Manuel', 'Towards squid it does not know',
                 'can_see_squid', 'Manuel', 'aggression was 72'):
        assert part in html
    assert 'Ate sushi' not in html


def test_the_memory_tab_shows_social_knowledge_on_its_own_page():
    from src.brain_memory_tab import MemoryTab
    brain = with_aggression(met_a_squid())
    manager = SimpleNamespace(get_all_short_term_memories=lambda: [SNACK, MET],
                              get_all_long_term_memories=lambda: [FIGHT])
    logic = SimpleNamespace(squid=SimpleNamespace(memory_manager=manager))
    with redirect_stdout(io.StringIO()):
        tab = MemoryTab(tamagotchi_logic=logic, brain_widget=brain)
        tab.update_memory_display()
    environment = [tab.stm_content_layout.itemAt(i).widget()
                   for i in range(tab.stm_content_layout.count())]
    social = [tab.social_cards_layout.itemAt(i).widget()
              for i in range(tab.social_cards_layout.count())]
    assert len(environment) == 1 and tab.ltm_content_layout.count() == 0
    assert len(social) == 2
    assert 'Social knowledge' in tab.social_summary.text()
    assert 'aggression was 72' in tab.social_summary.text()
    tab.deleteLater()


def test_the_laboratory_describes_aggression_and_its_history():
    from src.laboratory import NeuronLaboratory
    brain = with_aggression(met_a_squid())
    brain.enhanced_neurogenesis.raise_resting_level('aggression', 8., 'lost a fight with Manuel')
    brain.state['aggression'] = 30.
    lab = SimpleNamespace(bw=brain)
    lab._card = lambda title, html: NeuronLaboratory._card(lab, title, html)

    def card(name):
        return NeuronLaboratory._card_social(lab, name)
    aggression = card('aggression')
    text = aggression.findChild(QtWidgets.QLabel).text()
    assert 'edgy' in text and 'rests at <b>8</b>' in text
    assert 'lost a fight with Manuel' in text and 'would not start a fight' in text
    sensor = card('can_see_squid')
    assert 'Seeing any squid' in sensor.findChild(QtWidgets.QLabel).text()
    assert card('anxiety') is None


def test_social_events_become_thoughts_with_their_reasons():
    brain = met_a_squid()
    thoughts = [text for _, text in brain.social_thoughts]
    assert 'so I grew can_see_squid' in thoughts[-1]
    with_aggression(brain)
    brain.enhanced_neurogenesis.raise_resting_level('aggression', 4., 'lost a fight with Manuel')
    assert 'rests at 4 now, not 0, and always will - I lost a fight with Manuel' in \
        brain.social_thoughts[-1][1]
    learn_from_encounter(brain, 20., 'friendly', 'Manuel')
    assert 'more drawn to squid' in brain.social_thoughts[-1][1]
    shown = []
    window = SimpleNamespace(brain_widget=brain, add_thought=shown.append)
    sk.think(SimpleNamespace(brain_window=window), 'hello')
    assert shown == ['hello'] and brain.social_thoughts[-1][1] == 'hello'


def test_a_fight_is_told_as_why_it_started_and_why_it_ended():
    record = {'first_won': False, 'first_chance': .3, 'opponent': 'Manuel',
              'why': {'aggression': 72.},
              'first': {'role': 'attacker', 'ability': 40.},
              'second': {'role': 'defender', 'ability': 70.}}
    started, ended = sk.fight_thoughts(record, 'first')
    assert started.startswith('I went for Manuel: my aggression was 72')
    assert ended == 'I lost: my ability 40 against their 70 gave me a 30% chance.'
    record['opponent'] = 'Resident'
    defended, won = sk.fight_thoughts(record, 'second')
    assert defended.startswith('Resident came at me') and won.startswith('I won')
    assert '70%' in won
