"""A squid ventures out to another aquarium by its own network's decision.

  * enabling multiplayer only makes it possible: the first time another
    aquarium is heard on the network, the squid grows a sense for it
    (aquarium_nearby, a tick box) - whatever the brain's size, with no squid
    in view - wired by temperament;
  * it leaves only while that sense reports an aquarium, its exploring neuron
    is firing and the sense is pushing that exploring up; then it heads for
    the nearest side and leaves there - never the surface or the sand;
  * otherwise the tank's edges stop it, as with multiplayer off;
  * bad encounters move the sense's synapses: an adventurous squid that keeps
    getting hurt stops venturing out.
"""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                   # noqa: E402

from src import venturing                                       # noqa: E402
from src.brain_constants import AQUARIUM_SENSE, BINARY_NEURONS  # noqa: E402
from src.portable_brain import HeadlessBrain                    # noqa: E402
from src.social_learning import learn_from_encounter            # noqa: E402


def newborn(personality='adventurous'):
    brain = HeadlessBrain()
    brain.personality = personality
    return brain


def live(brain, ticks=1, **percepts):
    for _ in range(ticks):
        for name, value in percepts.items():
            brain.perceive(name, value)
        for stat, delta in brain.compute_neural_modulation().items():
            brain.state[stat] = max(0., min(100., brain.state[stat] + delta))
        brain.propagate()
    return brain


def heard(brain, ticks=1):
    return live(brain, ticks, aquarium_heard=100.)


def test_no_sense_until_another_aquarium_is_heard():
    brain = live(newborn(), ticks=3)
    assert AQUARIUM_SENSE not in brain.positions


def test_hearing_another_aquarium_grows_the_sense_even_at_the_cap_and_unseen():
    brain = newborn()
    brain.enhanced_neurogenesis.config.neurogenesis['max_neurons'] = len(brain.positions)
    heard(brain)
    assert AQUARIUM_SENSE in brain.positions and AQUARIUM_SENSE in BINARY_NEURONS
    assert brain.state[AQUARIUM_SENSE] == 100.
    assert 'can_see_squid' not in brain.positions        # nothing seen, nothing else
    assert not [edge for edge in brain.weights if edge[1] == AQUARIUM_SENSE]
    assert 'another aquarium' in brain.ledger.origins[AQUARIUM_SENSE].deficit_summary
    assert 'so I grew aquarium_nearby' in brain.social_thoughts[-1][1]
    live(brain, aquarium_heard=0.)
    assert brain.state[AQUARIUM_SENSE] == 0.


@pytest.mark.parametrize('personality,drawn', [('adventurous', True), ('energetic', True),
                                               ('timid', False), ('introvert', False)])
def test_temperament_decides_whether_another_aquarium_draws_it(personality, drawn):
    brain = heard(newborn(personality))
    assert (brain.weights[AQUARIUM_SENSE, 'act_move'] > 0) is drawn


def test_why_it_does_or_does_not_venture():
    weights = {(AQUARIUM_SENSE, 'act_move'): .9}
    out = {AQUARIUM_SENSE: 100., 'act_move': 80.}
    assert venturing.venturing(out, weights)
    assert venturing.why_not({**out, AQUARIUM_SENSE: 0.}, weights) == 'it senses no other aquarium'
    assert venturing.why_not(out, weights, fleeing=True) == 'it is fleeing'
    assert venturing.why_not(out, weights, chasing_food=True) == 'it is chasing food'
    assert venturing.why_not({**out, 'act_move': 0.}, weights) == 'it is not exploring'
    assert venturing.why_not(out, {(AQUARIUM_SENSE, 'act_move'): -.5}) == \
        'the other aquarium does not draw it'
    assert venturing.why_not(out, weights, can_visit=False) == 'it cannot visit'


def test_a_bold_squid_ventures_out_and_a_timid_one_stays_home():
    bold = heard(newborn('adventurous'), ticks=6)
    timid = heard(newborn('timid'), ticks=6)
    assert venturing.venturing(bold.state, bold.weights)
    assert not venturing.venturing(timid.state, timid.weights)


def test_bad_encounters_teach_an_adventurous_squid_to_stay_home():
    brain = heard(newborn('adventurous'))
    before = brain.weights[AQUARIUM_SENSE, 'act_move']
    for _ in range(12):
        learn_from_encounter(brain, -20., 'hostile', 'Manuel')
    assert brain.weights[AQUARIUM_SENSE, 'act_move'] < before
    assert brain.weights[AQUARIUM_SENSE, 'act_move'] <= 0
    assert brain.weights[AQUARIUM_SENSE, 'anxiety'] > 0
    assert 'and of other aquariums' in brain.social_thoughts[-1][1]
    live(brain, ticks=6, aquarium_heard=100.)
    assert venturing.why_not(brain.state, brain.weights) in (
        'the other aquarium does not draw it', 'it is not exploring')
    totals = brain.ledger.edge_totals((AQUARIUM_SENSE, 'act_move'))
    assert totals.get('encounter', 0) < 0                # its life, with provenance


def test_it_leaves_by_the_nearest_side():
    assert venturing.way_out(100, 300, 60, 40, 1280)[0] == 'left'
    side, (x, y) = venturing.way_out(900, 300, 60, 40, 1280)
    assert side == 'right' and x > 1280 and y == 320


def test_another_aquarium_is_nearby_while_heard_lately():
    assert venturing.peer_heard({'a': 100.}, 110.) == 100.
    assert venturing.peer_heard({'a': 100.}, 100. + venturing.HEARD_WITHIN + 1) == 0.
    assert venturing.peer_heard({}, 0.) == 0.


def test_the_plugin_reports_aquariums_heard_and_forgets_them_when_disabled():
    from plugins.multiplayer.mp_plugin_logic import MultiplayerPlugin
    brain = newborn()
    plugin = MultiplayerPlugin()
    plugin.logger = SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None)
    plugin.network_node = SimpleNamespace(node_id='me', known_nodes={})
    plugin.status_widget = plugin.status_bar = None
    plugin.tamagotchi_logic = SimpleNamespace(brain_window=SimpleNamespace(brain_widget=brain))
    plugin.handle_heartbeat(None, {'payload': {'node_id': 'me'}}, None)   # its own: ignored
    plugin._perceive_aquariums()
    assert brain.percepts['aquarium_heard'] == 0.
    plugin.handle_heartbeat(None, {'payload': {'node_id': 'peer'}}, None)
    plugin._perceive_aquariums()
    assert brain.percepts['aquarium_heard'] == 100.
    plugin._perceive_aquariums(now=plugin._peers_last_heard['peer'] + 60.)
    assert brain.percepts['aquarium_heard'] == 0.


def squid_at(x, venture=True, multiplayer=True):
    """A desktop Squid at the left (x=0) or anywhere, with a network node."""
    from src.squid import Squid
    sent = []
    squid = Squid.__new__(Squid)
    node = SimpleNamespace(node_id='me', is_connected=True,
                           send_message=lambda kind, data: sent.append((kind, data)))
    plugins = SimpleNamespace(get_enabled_plugins=lambda: ['multiplayer'] if multiplayer else [],
                              plugins={})
    brain = newborn()
    if venture:
        brain.state.update({AQUARIUM_SENSE: 100., 'act_move': 90.})
        brain.positions[AQUARIUM_SENSE] = (0, 0)
        brain.weights[AQUARIUM_SENSE, 'act_move'] = .9
    squid.tamagotchi_logic = SimpleNamespace(plugin_manager=plugins, network_node=node,
                                             brain_window=SimpleNamespace(brain_widget=brain),
                                             show_message=lambda *a: None)
    squid.lifecycle = SimpleNamespace(can_visit=True)
    squid.ui = SimpleNamespace(window_width=1280, window_height=900)
    squid.squid_x, squid.squid_y, squid.squid_width, squid.squid_height = x, 300, 60, 40
    squid.is_fleeing = squid.pursuing_food = False
    squid.uuid, squid.name, squid.personality = 'u', 'Squiddy', None
    squid._squid_color = (1, 2, 3)
    return squid, sent


def test_desktop_it_leaves_only_while_venturing_and_only_by_the_sides():
    squid, sent = squid_at(0)
    assert squid.check_boundary_exit()
    assert sent[0][0] == 'squid_exit' and sent[0][1]['payload']['direction'] == 'left'
    assert not squid.check_boundary_exit()               # one request per retry window
    still, nothing = squid_at(0, venture=False)
    assert still.why_not_venturing() == 'it senses no other aquarium'
    assert not still.check_boundary_exit() and not nothing
    top, sent_top = squid_at(600)
    top.squid_y = 0                                      # the surface is not a way out
    assert not top.check_boundary_exit() and not sent_top


def test_desktop_exploring_with_an_aquarium_nearby_heads_for_the_nearest_side():
    squid, _ = squid_at(900)
    assert squid._steer_by_neural_drive({'action': 'wander'})
    assert (squid.squid_direction, squid.status) == ('right', 'venturing out')
    squid.squid_x = 100
    squid._steer_by_neural_drive({'action': 'wander'})
    assert squid.squid_direction == 'left'


def test_the_exit_request_carries_the_protocol_hosts_accept():
    from plugins.multiplayer.identity import ENCOUNTER_PROTOCOL_VERSION, SquidIdentity
    squid, sent = squid_at(0)
    squid.uuid = '12345678-1234-4234-8234-123456789abc'
    assert squid.check_boundary_exit()
    identity = SquidIdentity.from_payload(sent[0][1]['payload']['identity'])
    assert identity is not None and identity.is_compatible()
    assert identity.protocol == ENCOUNTER_PROTOCOL_VERSION and identity.name == 'Squiddy'
