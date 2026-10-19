"""Touch controls for directed synapses, custom neurons and output bindings."""
import copy
import random

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput

from src.brain_constants import REQUIRED_NEURONS, ACTION_NEURONS, PURE_INPUT_NEURONS
from src.propagation import baseline_of
from ..engine.brain import NeuralBrain

HOOKS = {
    'Seek food': 'neuron_output_seek_food', 'Sleep': 'neuron_output_sleep',
    'Wake up': 'neuron_output_wake', 'Flee': 'neuron_output_flee',
    'Release ink': 'neuron_output_ink_cloud', 'Swim': 'neuron_output_wander',
    'Play with a rock': 'neuron_output_approach_rock', 'Seek shelter': 'neuron_output_seek_plant',
    'Pick up a rock': 'neuron_output_pick_up_rock', 'Throw a rock': 'neuron_output_throw_rock',
    'Eat nearby food': 'neuron_output_eat', 'Change colour': 'neuron_output_change_color',
    'Startle': 'neuron_output_startle', 'Calm down': 'neuron_output_calm',
    'Boost happiness': 'neuron_output_boost_happiness', 'Boost curiosity': 'neuron_output_boost_curiosity',
    'Reduce anxiety': 'neuron_output_reduce_anxiety',
}


def open_brain_editor(app):
    box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8), padding=dp(12))
    box.bind(minimum_height=box.setter('height'))
    scroll = ScrollView(); scroll.add_widget(box)
    content = BoxLayout(orientation='vertical', spacing=dp(8), padding=dp(6))
    content.add_widget(scroll)
    footer = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
    content.add_widget(footer)
    popup = Popup(title='Brain designer', content=content, size_hint=(.96, .94),
                  background_color=(.12, .15, .23, 1))
    snapshots = []
    app.editing_brain = True

    def label(text):
        widget = Label(text=text, size_hint_y=None, height=dp(52), font_size=sp(14))
        box.add_widget(widget)
        return widget

    label('Edit the live neural network.\nA -> B and B -> A are independent connections.')
    names = sorted(app.sim.squid.brain.positions)
    source = Spinner(text=names[0], values=names, size_hint_y=None, height=dp(48))
    target = Spinner(text=names[-1], values=names, size_hint_y=None, height=dp(48))
    box.add_widget(source); box.add_widget(target)
    weight = Slider(min=-1, max=1, value=0, step=.01, size_hint_y=None, height=dp(48))
    box.add_widget(weight)
    value = label('Weight: 0.00')
    status = label('Negative weights inhibit; positive weights excite.')
    weight.bind(value=lambda _, v: setattr(value, 'text', f'Weight: {v:+.2f}'))

    def remember():
        snapshots.append(copy.deepcopy(app.sim.squid.brain.to_dict()))
        del snapshots[:-20]

    def sync(*_):
        brain = app.sim.squid.brain
        names = sorted(brain.positions)
        source.values = target.values = names
        weight.value = brain.get_weight(source.text, target.text)
    source.bind(text=sync); target.bind(text=sync)

    def button(text, callback):
        btn = Button(text=text, size_hint_y=None, height=dp(48), font_size=sp(15),
                     background_normal='', background_color=(.25, .27, .40, 1))
        btn.bind(on_release=callback); box.add_widget(btn)

    def apply(*_):
        if source.text == target.text or target.text in PURE_INPUT_NEURONS:
            status.text = 'Choose different neurons; sensors are inputs only.'
            return
        remember()
        brain = app.sim.squid.brain
        brain.set_weight(source.text, target.text, weight.value)
        status.text = f'{source.text} -> {target.text}: {weight.value:+.2f}'
    button('Apply connection', apply)

    def remove_edge(*_):
        remember()
        app.sim.squid.brain.remove_weight((source.text, target.text), mechanism='manual', reason='edited in mobile designer')
        sync()
    button('Remove connection', remove_edge)

    name = TextInput(hint_text='New neuron name', multiline=False, size_hint_y=None, height=dp(48))
    box.add_widget(name)
    def add(*_):
        neuron = name.text.strip().replace(' ', '_')
        brain = app.sim.squid.brain
        if not neuron or neuron in brain.positions or len(neuron) > 80:
            status.text = 'Enter a new name (1–80 characters).'
            return
        if len(brain.positions) >= brain.config.max_neurons:
            status.text = 'The configured neuron limit has been reached.'
            return
        remember()
        brain.positions[neuron] = (random.uniform(100, 900), random.uniform(470, 700))
        brain.state[neuron] = baseline_of(neuron)
        brain.custom_neurons.add(neuron)
        status.text = f'Added {neuron}. Connect it or bind an output below.'
        sync(); source.text = neuron
    button('Add neuron', add)

    def remove_neuron(*_):
        neuron = source.text
        if neuron in REQUIRED_NEURONS or neuron in ACTION_NEURONS or neuron in PURE_INPUT_NEURONS:
            status.text = 'Required drives, senses and motor neurons are protected.'
            return
        remember()
        brain = app.sim.squid.brain
        for edge in list(brain.weights):
            if neuron in edge:
                brain.remove_weight(edge, mechanism='manual', reason='neuron removed in mobile designer')
        brain.positions.pop(neuron, None); brain.state.pop(neuron, None)
        brain.custom_neurons.discard(neuron); brain.new_neurons.discard(neuron)
        brain.forget_action_representation(neuron)
        brain.enhanced_neurogenesis.functional_neurons.pop(neuron, None)
        brain.output_bindings = [b for b in brain.output_bindings if b['neuron_name'] != neuron]
        brain.neurogenesis_data['new_neurons'] = [n for n in brain.neurogenesis_data['new_neurons'] if n != neuron]
        brain.install_bindings()
        source.text = sorted(brain.positions)[0]
        sync(); status.text = f'Removed {neuron}.'
    button('Remove selected custom neuron', remove_neuron)

    hook = Spinner(text=next(iter(HOOKS)), values=list(HOOKS), size_hint_y=None, height=dp(48))
    box.add_widget(hook)
    threshold = Slider(min=0, max=100, value=70, step=1, size_hint_y=None, height=dp(48))
    box.add_widget(threshold)
    firing = label('Output threshold: 70%')
    threshold.bind(value=lambda _, v: setattr(firing, 'text', f'Output threshold: {int(v)}%'))
    def bind(*_):
        remember()
        brain = app.sim.squid.brain
        brain.output_bindings = [b for b in brain.output_bindings if b['neuron_name'] != source.text]
        brain.output_bindings.append(dict(neuron_name=source.text, output_hook=HOOKS[hook.text],
            threshold=threshold.value, trigger_mode='rising', cooldown=1, enabled=True))
        brain.install_bindings()
        status.text = f'{source.text} now triggers {hook.text.lower()}.'
    button('Bind selected neuron to action', bind)

    def undo(*_):
        if snapshots:
            app.sim.squid.brain = NeuralBrain.from_dict(snapshots.pop())
            sync(); status.text = 'Previous edit restored.'
    for text, callback in (('Undo', undo), ('Save and close', lambda *_: popup.dismiss())):
        control = Button(text=text, background_normal='', background_color=(.42, .28, .65, 1))
        control.bind(on_release=callback); footer.add_widget(control)
    def close(*_):
        app.editing_brain = False
        app.brain.set_simulation(app.sim)
        app.save_now()
    popup.bind(on_dismiss=close)
    sync(); popup.open()
    return popup
