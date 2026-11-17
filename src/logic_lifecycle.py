"""A squid's life beyond a single day: mating, the egg, death, the headstone
and the hatchling that follows (see src/lifecycle.py for the rules).
"""
import logging
from PyQt5 import QtCore, QtGui, QtWidgets
import random
import os
from .ui import ResizablePixmapItem
from .lifecycle import (Lifecycle, EGG_HATCHING, CAUSE_STARVED,
                        CAUSE_NEGLECTED, CAUSE_SICKNESS, CAUSE_INJURED)

_LOG = logging.getLogger(__name__)


class LifecycleLogicMixin:
    """Part of TamagotchiLogic (see tamagotchi_logic.py); not used on its own."""

    # ------------------------------------------------------------------
    # Reproduction, parental starvation and the egg (see src/lifecycle.py)
    # ------------------------------------------------------------------
    #: Pause between the parent dying and its egg starting to hatch, so the
    #: player sees the one happen before the other.
    HATCH_DELAY_MS = 3000

    def _lifecycle_setting(self, key):
        config = getattr(self, 'lifecycle_config', None)
        if not config:
            from .lifecycle import DEFAULT_CONFIG
            config = DEFAULT_CONFIG
        return config[key]

    def record_reproduction(self, mating_id, mate_uuid, mate_name="Squid"):
        """The host has resolved a mating with this tank's resident.

        One state change and one save: the resident becomes a parent and its
        egg is laid in the same Lifecycle record, which is written in a single
        atomic save before this returns. The caller only tells the visiting
        squid afterwards, so a crash can lose the visitor's news of the event
        but never the event itself, and can never write half of it.

        Returns True only the first time; a repeat lays nothing.
        """
        squid = self.squid
        if squid is None:
            return False
        x, y = self._egg_position()
        if not squid.lifecycle.record_reproduction(mating_id, mate_uuid,
                                                   mate_name, x, y):
            return False
        # This parent's half of the hatchling's weights, taken now, from the
        # brain that mated (src/inheritance.py). The mate's half arrives from
        # its own machine (add_mate_genes).
        brain = getattr(getattr(self, 'brain_window', None), 'brain_widget', None)
        weights = getattr(brain, 'weights', None)
        if isinstance(weights, dict) and weights:
            try:
                from .inheritance import gamete
                squid.lifecycle.add_genes(mating_id, squid.name, gamete(weights))
            except Exception as e:
                # The egg is laid regardless; it hatches from what it carries.
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Lifecycle] could not take this parent's genes: {e}")
        self._place_egg()
        try:
            self.save_game()
        except Exception as e:
            # The record is still held in memory and goes out with the next
            # save; the event is not undone because a write failed.
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Lifecycle] could not save the mating immediately: {e}")
        self.show_message(f"{squid.name} and {mate_name} produced an egg. "
                          f"{squid.name} has stopped eating.")
        return True

    def on_rock_hit(self, target_item, throw):
        """Something thrown - a rock, or poop (throw['what']) - struck a squid.
        Tell the plugins - the multiplayer host lets the struck squid feel it -
        with the fact only: what, and how hard, never why."""
        own_body = target_item is self.squid.squid_item
        felt = self.feel_rock_hit(throw) if own_body else False
        manager = getattr(self, 'plugin_manager', None)
        results = []
        if manager is not None and hasattr(manager, 'trigger_hook'):
            results = manager.trigger_hook('on_rock_hit',
                                 target_uuid=(str(self.squid.uuid) if target_item is self.squid.squid_item
                                              else str(getattr(target_item, 'peer_uuid', '') or '')),
                                 throw=throw)
        if own_body and felt and not any(result is True for result in results):
            # Disabling the transport cannot undo a projectile already in
            # flight. Keep the physical fact even without an active plugin.
            what = throw.get('what', 'rock')
            self.squid.memory_manager.add_short_term_memory('social', f"{what}:{throw['throw_id']}",
                dict({'peer_uuid': throw.get('source_uuid', ''), 'hits_taken': 1, 'what': what},
                     **felt), importance=3)

    def feel_rock_hit(self, throw):
        """The resident's body owns damage/startle, once per physical impact."""
        throw_id = (throw or {}).get('throw_id')
        if not isinstance(throw_id, str) or not throw_id:
            return False
        hits = getattr(self, '_felt_rock_hits', None)
        if hits is None:
            self._felt_rock_hits = hits = set()
        if throw_id in hits:
            return False
        hits.add(throw_id)
        from .throwing import feel_hit
        # What changed, or True for a strike that changed nothing it measures.
        return feel_hit(self.squid, (throw or {}).get('what', 'rock'),
                        startle=lambda source: self.startle_squid(source=source)) or True

    def throw_visitor_rock(self, actor, rock, intent):
        plugin = self.plugin_manager.plugins.get('multiplayer', {}).get('instance')
        if plugin is None:
            return None
        node = plugin.visit_node_ids.get(actor.uuid)
        visual = plugin.entity_manager.remote_squids.get(node, {}).get('visual')
        if visual is None:
            return None
        return self.rock_interaction.throw_from_visitor(actor, rock, intent, visual)

    def ink_visitor(self, actor):
        self.create_ink_cloud((actor.x + self.squid.squid_width/2,
                               actor.y + self.squid.squid_height/2), record=False)

    def add_mate_genes(self, mating_id, mate_name, genes):
        """The mate's half of the hatchling's weights has arrived: keep it with
        the egg and save. True if it was kept now (once, for this egg only)."""
        squid = self.squid
        if squid is None or not squid.lifecycle.add_genes(mating_id, mate_name, genes):
            return False
        try:
            self.save_game()
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Lifecycle] could not save the mate's genes immediately: {e}")
        return True

    def _egg_position(self):
        """On the tank floor, below where the parent is."""
        ui = self.user_interface
        width = float(getattr(ui, 'window_width', 1280))
        height = float(getattr(ui, 'window_height', 900))
        squid = self.squid
        x = float(getattr(squid, 'squid_x', width / 2))
        x = max(50.0, min(width - 120.0, x))
        y = max(50.0, height - 120.0 - 92.0)
        return x, y

    def _place_egg(self):
        """Put the egg in the tank. Safe to call repeatedly."""
        egg = self.squid.lifecycle.egg if self.squid else None
        if not egg:
            return None
        existing = getattr(self, 'egg_item', None)
        if existing is not None and getattr(existing, 'egg_id', None) == egg['egg_id']:
            try:
                if existing.scene() is not None:
                    return existing
            except RuntimeError:
                pass
        self._remove_egg_item()
        from .display_scaling import DisplayScaling
        item = QtWidgets.QGraphicsPixmapItem(
            DisplayScaling.to_points(QtGui.QPixmap(os.path.join("images", "egg.png"))))
        # A category nothing else recognises: it is not food, a rock or a
        # decoration, so it is not eaten, carried, contested or saved twice.
        item.category = 'egg'
        item.egg_id = egg['egg_id']
        item.setPos(egg['x'], egg['y'])
        self.user_interface.scene.addItem(item)
        self.egg_item = item
        if hasattr(self.squid, 'mark_scene_objects_dirty'):
            self.squid.mark_scene_objects_dirty()
        return item

    def _remove_egg_item(self):
        item = getattr(self, 'egg_item', None)
        self.egg_item = None
        if item is None:
            return
        try:
            scene = item.scene()
            if scene is not None:
                scene.removeItem(item)
        except RuntimeError:
            pass

    def _restore_lifecycle(self, data):
        """Bring the lifecycle back from a save, and resume where it was."""
        squid = self.squid
        squid.lifecycle = Lifecycle.from_dict(data)
        self._remove_egg_item()
        if squid.lifecycle.egg:
            self._place_egg()
        if squid.lifecycle.is_dead:
            # Closed while the squid was dead or its egg was hatching. Its
            # headstone came back with the decorations; what follows picks up
            # from the saved state, and only once.
            self._lay_to_rest()
            QtCore.QTimer.singleShot(self.HATCH_DELAY_MS, self.continue_after_death)

    def _lay_to_rest(self):
        """A dead squid stops, and its body gives way to its headstone."""
        squid = self.squid
        squid.can_move = False
        squid.is_fleeing = False
        squid.pursuing_food = False
        squid.status = "dead"
        if hasattr(squid, 'clear_neural_drive'):
            squid.clear_neural_drive()
        if hasattr(squid, 'remove_view_cone'):
            squid.remove_view_cone()
        item = getattr(squid, 'squid_item', None)
        if item is not None:
            item.setVisible(False)

    def _place_headstone(self):
        """One of the stones in images/headstones, at random, on the tank
        floor beneath where the squid died, bearing its name. A decoration
        like any other, except that it is never carried, thrown or deleted.
        """
        from .ui import HEADSTONE_DIR
        squid = self.squid
        try:
            stones = sorted(n for n in os.listdir(HEADSTONE_DIR)
                            if n.lower().endswith('.png'))
        except OSError:
            stones = []
        if not stones:
            return None
        path = os.path.join(HEADSTONE_DIR, random.choice(stones))
        item = ResizablePixmapItem(QtGui.QPixmap(path), path)
        # Its name, how long it lived and its fights, for its epitaph.
        from .lifecycle import headstone_record
        statistics = getattr(squid, 'statistics', None)
        age = getattr(statistics, 'get_total_age_seconds', None)
        item.set_epitaph(headstone_record(
            squid, age() if callable(age) else 0.0,
            getattr(statistics, 'fights_won', 0), getattr(statistics, 'fights_lost', 0)))
        item.limit_headstone(squid)
        stone = item.pixmap()
        ui = self.user_interface
        width = float(getattr(ui, 'window_width', 1280))
        height = float(getattr(ui, 'window_height', 900))
        centre = float(squid.squid_x) + float(getattr(squid, 'squid_width', 0)) / 2
        item.setPos(max(0.0, min(width - stone.width(), centre - stone.width() / 2)),
                    max(0.0, height - 120.0 - stone.height()))
        ui.scene.addItem(item)
        if hasattr(squid, 'mark_scene_objects_dirty'):
            squid.mark_scene_objects_dirty()
        return item

    #: How each death is told.
    DEATH_MESSAGES = {
        CAUSE_STARVED: "{name} has died.",
        CAUSE_NEGLECTED: "{name} has died of neglect.",
        CAUSE_SICKNESS: "{name} has died of sickness.",
        CAUSE_INJURED: "{name} has died of its injuries.",
    }

    def on_squid_died(self):
        """The squid has died, of any cause. Called once, by the transition."""
        squid = self.squid
        # The multiplayer plugin, if it is running, ends visits to and by this
        # squid, so nothing is left pointing at it; the achievements plugin
        # awards CIRCLE OF LIFE to a parent. First: ending its own visit gives
        # a squid its body back, and nothing a plugin shows may replace the
        # news of the death.
        plugin_manager = getattr(self, 'plugin_manager', None)
        if plugin_manager is not None:
            try:
                plugin_manager.register_hook("on_squid_died")
                plugin_manager.trigger_hook("on_squid_died", tamagotchi_logic=self,
                                            squid=squid)
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Lifecycle] on_squid_died hook failed: {e}")
        self._lay_to_rest()
        self._place_headstone()
        message = self.DEATH_MESSAGES.get(squid.lifecycle.death_cause,
                                          self.DEATH_MESSAGES[CAUSE_STARVED])
        self.show_message(message.format(name=squid.name))
        try:
            self.save_game()
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Lifecycle] could not save the death: {e}")
        QtCore.QTimer.singleShot(self.HATCH_DELAY_MS, self.continue_after_death)

    def continue_after_death(self):
        """What follows a death: the parent's egg hatches, or - with no egg -
        a new squid hatches from a fresh one. The headstone stays either way.
        """
        lifecycle = getattr(self.squid, 'lifecycle', None)
        if lifecycle is None or not lifecycle.is_dead:
            return False
        if lifecycle.egg is not None:
            return self.begin_egg_hatching()
        window = getattr(self.user_interface, 'window', None)
        replace = getattr(window, 'replace_dead_squid', None)
        if not callable(replace):
            return False
        return bool(replace(str(self.squid.uuid)))

    def begin_egg_hatching(self):
        """The dead parent's egg hatches into a new game. No cancel.

        The egg is marked hatching and saved before anything else, so a crash
        from here on resumes this hatch rather than starting a second one.
        The new game itself is the main window's, the same sequence as a
        start with no save.
        """
        squid = self.squid
        lifecycle = getattr(squid, 'lifecycle', None)
        if lifecycle is None or not lifecycle.is_dead or lifecycle.egg is None:
            return False
        if lifecycle.begin_hatching():
            try:
                self.save_game()
            except Exception as e:
                _LOG.warning('Handled exception', exc_info=True)
                print(f"[Lifecycle] could not save the hatching egg: {e}")
        elif lifecycle.egg_state != EGG_HATCHING:
            return False
        window = getattr(self.user_interface, 'window', None)
        hatch = getattr(window, 'hatch_egg', None)
        if not callable(hatch):
            return False
        return bool(hatch(lifecycle.egg['egg_id']))

    def game_over(self):
        game_over_dialog = QtWidgets.QMessageBox()
        game_over_dialog.setIcon(QtWidgets.QMessageBox.Critical)
        game_over_dialog.setText("Game Over")
        game_over_dialog.setInformativeText("Your squid has died due to poor health.")
        game_over_dialog.setWindowTitle("Game Over")
        game_over_dialog.exec_()
        self.user_interface.window.close()

        # Add any additional game over logic or cleanup here
        print("Game Over - Squid died due to poor health")

        # Save the game state before resetting
        self.save_game()

        # Reset the game state
        self.reset_game()
