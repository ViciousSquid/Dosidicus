"""Saving and loading a game, autosave, and starting a new one.
"""
import logging
from PyQt5 import QtCore
import os
import zipfile
import json
from .tint import rgb_of
from .custom_brain_loader import (
    get_custom_brain_save_data, 
    restore_custom_brain_from_save,
    show_custom_brain_load_warning
)

_LOG = logging.getLogger(__name__)


class SaveLoadMixin:
    """Part of TamagotchiLogic (see tamagotchi_logic.py); not used on its own."""

    def reset_game(self):
        # Reset squid attributes
        self.squid.hunger = 25
        self.squid.sleepiness = 30
        self.squid.happiness = 100
        self.squid.cleanliness = 100
        self.squid.is_sleeping = False
        self.squid.health = 100
        self._set_sickness_state(False)

        # Reset new neurons
        self.squid.satisfaction = 50
        self.squid.anxiety = 10
        self.squid.curiosity = 70

        # Reset game variables
        self.cleanliness_threshold_time = 0
        self.hunger_threshold_time = 0
        self.last_clean_time = 0

        # Clear food and poop items
        for food_item in self.food_items:
            self.user_interface.scene.removeItem(food_item)
        self.food_items.clear()

        for poop_item in self.poop_items:
            self.user_interface.scene.removeItem(poop_item)
        self.poop_items.clear()
        
        # Clear all DIRTY text on reset
        self.user_interface.clear_dirty_text()

        # Reset squid position
        self.squid.squid_x = self.squid.center_x
        self.squid.squid_y = self.squid.center_y
        self.squid.squid_item.setPos(self.squid.squid_x, self.squid.squid_y)

        # Notify vision worker of scene change (cleared objects)
        if hasattr(self.squid, 'mark_scene_objects_dirty'):
            self.squid.mark_scene_objects_dirty()

        # Show a message
        self.show_message("Game reset. Take better care of your squid!")

        # Force an update of the scene
        self.user_interface.scene.update()

        # Save the game state after resetting
        self.save_game()

    def load_game(self) -> bool:
        # Use save_manager
        latest = self.save_manager.get_latest_save()
        if not latest:
            print("[Load] No save file found")
            return False

        try:
            data = {}
            squid_uuid = None

            with zipfile.ZipFile(latest, 'r') as zf:
                for fname in zf.namelist():
                    if fname == "uuid.txt":
                        raw = zf.read(fname).decode('utf-8').strip()
                        if "SquidSignature" in raw:
                            squid_uuid = raw.split("SquidSignature")[-1].strip()
                        else:
                            squid_uuid = raw
                        continue

                    if fname.endswith('.json'):
                        with zf.open(fname) as f:
                            key = os.path.splitext(fname)[0]
                            json_data = f.read().decode('utf-8')
                            if json_data.strip():
                                data[key] = json.loads(json_data)

            # === RESTORE UUID INTO LIVE SQUID ===
            if squid_uuid and self.squid:
                try:
                    import uuid
                    restored_uuid = uuid.UUID(squid_uuid)
                    old_uuid = self.squid.uuid
                    self.squid.uuid = restored_uuid
                    print(f"[Load] Restored Squid UUID: {restored_uuid} (was {old_uuid})")
                except ValueError as e:
                    print(f"[Load] Invalid UUID format in save: {squid_uuid} → {e}")

            # === Load game state ===
            game_state = data.get('game_state', {})
            if not game_state:
                print("[Load] No game_state found")
                return False

            squid_data = game_state.get('squid', {})
            if squid_data:
                for attr, value in squid_data.items():
                    # Statistics are a canonical model, not replaceable squid
                    # state. Older saves may nest their persisted values here.
                    if attr != 'statistics' and hasattr(self.squid, attr):
                        setattr(self.squid, attr, value)
                # Whose egg it hatched from is read off its lineage. A squid
                # that hatched from a fresh egg has no such attribute at all,
                # so the loop above never restored it and an heir forgot,
                # at its first reload, that it was one.
                lineage = squid_data.get('lineage')
                self.squid.lineage = lineage if isinstance(lineage, dict) else None
                if self.squid.lineage:
                    self.squid.inherited_from = [
                        str(parent) for parent in (self.squid.lineage.get('parents') or [])][:2]

            # Restore personality
            if 'personality' in squid_data:
                from .squid import Personality
                try:
                    self.squid.personality = Personality(squid_data['personality'])
                except ValueError:
                    pass

            # Restore the canonical statistics model after squid state so an
            # already-active sickness episode is resumed rather than recounted.
            statistics_data = data.get(
                'statistics',
                squid_data.get('statistics', {}),
            )
            self.squid.statistics.load_statistics(statistics_data)
            self._set_sickness_state(getattr(self.squid, 'is_sick', False))
            self._restore_lifecycle(game_state.get('lifecycle'))

            # Load custom brain (Logic patched to load output bindings)
            custom_brain_data = data.get('custom_brain', {})
            custom_brain_loaded = False
            
            if custom_brain_data and custom_brain_data.get('is_custom_brain'):
                success, msg = restore_custom_brain_from_save(data, self.brain_window.brain_widget)
                print(f"[Load] Custom brain: {msg}")
                
                # Manually load bindings from custom brain definition ---
                if success and hasattr(self, 'neuron_output_monitor'):
                    brain_def = custom_brain_data.get('brain_definition', {})
                    if brain_def:
                        self.neuron_output_monitor.load_bindings_from_brain(brain_def)
                        custom_brain_loaded = True
                        print("     + Synced custom output bindings to monitor")

            # Load brain state (Standard)
            brain_state = data.get('brain_state', {})
            if brain_state and hasattr(self, 'brain_window'):
                self.brain_window.set_brain_state(brain_state)
                self.refresh_neuron_count()
                
                # Manually load bindings if not using custom brain
                # This handles standard saves where bindings are stored in 'brain_state'
                if not custom_brain_loaded and hasattr(self, 'neuron_output_monitor'):
                    self.neuron_output_monitor.load_bindings_from_brain(brain_state)
                    print("     + Synced standard output bindings to monitor")

            # Load memories
            self.squid.memory_manager.short_term_memory = data.get('ShortTerm', [])
            self.squid.memory_manager.long_term_memory = data.get('LongTerm', [])

            # Load decorations
            decorations_data = game_state.get('decorations', [])
            self.user_interface.load_decorations_data(decorations_data)

            # Load logic state
            logic_data = game_state.get('tamagotchi_logic', {})
            self.cleanliness_threshold_time = logic_data.get('cleanliness_threshold_time', 0)
            self.hunger_threshold_time = logic_data.get('hunger_threshold_time', 0)
            self.last_clean_time = logic_data.get('last_clean_time', 0)
            self.points = logic_data.get('points', 0)
            
            # Restore achievements if available
            if 'achievements' in data:
                self._restore_achievements_data(data['achievements'])

            if hasattr(self, 'statistics_window'):
                self.statistics_window.set_score(self.points)
                self.statistics_window.update_statistics()

            print(f"[Load] Successfully loaded: {os.path.basename(latest)}")
            # Only a new game started the autosave timer (after its hatching
            # splash): a game that began from a save was never autosaved.
            # A load is never failed by its timer.
            if getattr(self, 'autosave_timer', None) is not None:
                self.start_autosave()
            return True

        except Exception as e:
            print(f"[Load] Failed to load game: {e}")
            import traceback
            traceback.print_exc()
            return False

    def save_game(self, is_autosave=False):
        """
        Save the complete game state including decorations.

        Args:
            is_autosave: Whether this is an autosave (True) or manual save (False)
        """
        # Import hashlib for duplicate detection
        import hashlib
        import json
        import uuid
        
        # Collect squid state
        squid_data = {
            'hunger': self.squid.hunger,
            'sleepiness': self.squid.sleepiness,
            'happiness': self.squid.happiness,
            'cleanliness': self.squid.cleanliness,
            'health': self.squid.health,
            'is_sick': self.squid.is_sick,
            'squid_x': self.squid.squid_x,
            'squid_y': self.squid.squid_y,
            'satisfaction': self.squid.satisfaction,
            'anxiety': self.squid.anxiety,
            'curiosity': self.squid.curiosity,
            'personality': self.squid.personality.value,
            'uuid': str(self.squid.uuid),  # Convert UUID to string
            'name': getattr(self.squid, 'name', 'Squid'),  # Save squid name if it exists
            # Its colour, as its player chose it. Loading has always read
            # this; saving never wrote it, so a coloured squid came back
            # from every save as plain as it hatched.
            'tint_color': rgb_of(getattr(self.squid, 'tint_color', None)),
            # A hatchling's parents and what it inherited from each
            # (src/inheritance.py). Kept with the squid for good: it used to
            # be known only until the game was closed.
            'lineage': getattr(self.squid, 'lineage', None),
        }

        # Statistics are owned by the model. The tab is a read-only projection.
        statistics_data = self.squid.statistics.to_dict()

        # Collect tamagotchi logic state
        tamagotchi_logic_data = {
            'cleanliness_threshold_time': self.cleanliness_threshold_time,
            'hunger_threshold_time': self.hunger_threshold_time,
            'last_clean_time': self.last_clean_time,
            'points': self.statistics_window.score
        }

        # Collect brain state
        brain_state = self.brain_window.get_brain_state()

        # Collect memory state
        short_term_memory = self.squid.memory_manager.short_term_memory
        long_term_memory = self.squid.memory_manager.long_term_memory

        # Collect decoration data from UI
        decorations_data = self.user_interface.get_decorations_data()

        # Collect achievement data from Achievements plugin (if enabled)
        achievements_data = None
        try:
            if hasattr(self, 'plugin_manager') and 'achievements' in self.plugin_manager.plugins:
                plugin_info = self.plugin_manager.plugins['achievements']
                if 'instance' in plugin_info:
                    instance = plugin_info['instance']
                    if hasattr(instance, 'get_save_data'):
                        achievements_data = instance.get_save_data()
        except Exception as e:
            # If plugin method fails, log warning and continue without achievements
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Warning] Could not collect achievement data: {e}")
            achievements_data = None

        # Assemble complete save data
        save_data = {
            'game_state': {
                'squid': squid_data,
                'tamagotchi_logic': tamagotchi_logic_data,
                'decorations': decorations_data,
                # The parent's state and its egg, as one record, in the same
                # atomic write as everything else.
                'lifecycle': self.squid.lifecycle.to_dict()
                             if hasattr(self.squid, 'lifecycle') else None,
            },
            'brain_state': brain_state,
            'statistics': statistics_data,
            'ShortTerm': short_term_memory,
            'LongTerm': long_term_memory,
            'custom_brain': get_custom_brain_save_data()
        }

        # The life in order - every event that shaped this squid and the
        # brain it had at each (src/life_timeline.py), written beside the
        # rest as timeline.json for the Laboratory pages in extras/. Built
        # from what is already above; a save is never held up by it.
        try:
            from .life_timeline import build as build_timeline
            from .life_journey import build_journey, gather_facts
            chapters = None
            try:
                chapters = build_journey(gather_facts(
                    logic=self, brain=self.brain_window.brain_widget, squid=self.squid))
            except Exception:
                chapters = None
            save_data['timeline'] = build_timeline(save_data, journey=chapters)
        except Exception as problem:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Warning] Could not write the life timeline: {problem}")

        # Add achievements data if available (will be saved as achievements.json in the ZIP)
        if achievements_data is not None:
            save_data['achievements'] = achievements_data
            
        # === DUPLICATE DETECTION LOGIC ===
        # Create hash of save data to detect duplicates
        
        # Add timestamp for duplicate detection (not saved to file)
        save_data_for_hash = save_data.copy()
        # Remove any volatile fields that shouldn't affect hash
        save_data_for_hash.pop('achievements', None)
        
        # Create a custom JSON encoder that handles UUID objects
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, uuid.UUID):
                    return str(obj)
                # Let the base class default method raise the TypeError
                return json.JSONEncoder.default(self, obj)
        
        # Create hash of the save content
        save_hash = hashlib.md5(
            json.dumps(save_data_for_hash, sort_keys=True, cls=CustomJSONEncoder).encode()
        ).hexdigest()
        
        # Check if this is identical to the last save
        if hasattr(self, 'last_save_hash') and save_hash == self.last_save_hash:
            # Only skip for autosaves, allow manual saves even if identical
            if is_autosave:
                print("     Autosave skipped: identical to previous save")
                return False
            else:
                print("     Manual save detected as identical to previous save, but saving anyway")
        
        # Update last save hash
        self.last_save_hash = save_hash
        
        # Save using SaveManager
        filepath = self.save_manager.save_game(save_data, is_autosave)

        if filepath:
            save_type = "autosaved" if is_autosave else "saved"
            print(f"Game {save_type} successfully to {filepath}")
            
            # Update save count if tracking
            if not hasattr(self, 'save_count'):
                self.save_count = 0
            self.save_count += 1
            
            # Track autosave count separately
            if is_autosave:
                if not hasattr(self, 'autosave_count'):
                    self.autosave_count = 0
                self.autosave_count += 1
                print(f"     Autosave #{self.autosave_count}")
                    
            return True
        else:
            print("Failed to save game")
            return False

    def _restore_achievements_data(self, achievements_data):
        """Restore achievement data to the achievements plugin after loading save."""
        if not achievements_data:
            return
        try:
            if 'achievements' in self.plugin_manager.plugins:
                plugin_info = self.plugin_manager.plugins['achievements']
                instance = plugin_info.get('instance')
                if instance and hasattr(instance, 'load_save_data'):
                    instance.load_save_data(achievements_data)
                    unlocked_count = len(achievements_data.get('unlocked', {}))
                    print(f"✓ Restored {unlocked_count} achievements")
        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"[Warning] Could not restore achievements: {e}")

    def _apply_save_data(self, save_data):
        """Apply loaded save data to game state"""
        if not save_data:
            return False
        
        # Check custom brain warning
        if not show_custom_brain_load_warning(self.user_interface, save_data):
            return False
        
        try:
            # Extract and apply game state
            game_state = save_data['game_state']
            squid_data = game_state['squid']
            
            self.squid.load_state(squid_data)
            self.squid.statistics.load_statistics(save_data.get('statistics', {}))
            self._set_sickness_state(getattr(self.squid, 'is_sick', False))
            self._restore_lifecycle(game_state.get('lifecycle'))
            
            # Load custom brain
            custom_brain_data = save_data.get('custom_brain')
            if custom_brain_data and custom_brain_data.get('is_custom_brain'):
                success, msg = restore_custom_brain_from_save(save_data, self.brain_window.brain_widget)
                print(f"✅ {msg}" if success else f"⚠️ {msg}")
            
            # Load brain state
            brain_state = save_data.get('brain_state', {})
            self.brain_window.set_brain_state(brain_state)
            self.refresh_neuron_count()
            
            # Load memories
            self.squid.memory_manager.short_term_memory = save_data.get('ShortTerm', [])
            self.squid.memory_manager.long_term_memory = save_data.get('LongTerm', [])

            # Load decorations
            decorations_data = game_state.get('decorations', [])
            self.user_interface.load_decorations_data(decorations_data)

            # Notify vision worker of scene change (decorations loaded)
            if hasattr(self.squid, 'mark_scene_objects_dirty'):
                self.squid.mark_scene_objects_dirty()
            
            # Load game state
            logic_data = game_state['tamagotchi_logic']
            self.cleanliness_threshold_time = logic_data['cleanliness_threshold_time']
            self.hunger_threshold_time = logic_data['hunger_threshold_time']
            self.last_clean_time = logic_data['last_clean_time']
            self.points = logic_data['points']
            
            # UPDATE SCORE DISPLAY
            if hasattr(self, 'statistics_window'):
                self.statistics_window.set_score(self.points)
            
            print(f"✅ Loaded {len(decorations_data)} decorations")
            
            # UPDATE STATISTICS DISPLAY
            if hasattr(self, 'statistics_window'):
                self.statistics_window.update_statistics()
            
            self.set_simulation_speed(1)
            return True
            
        except Exception as e:
            print(f"❌ Error loading game: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _get_pixmap_data(self, item):
        """Get pixmap data from a QGraphicsPixmapItem for serialization"""
        if hasattr(item, 'pixmap'):
            pixmap = item.pixmap()
            if not pixmap.isNull():
                # Convert pixmap to base64 encoded PNG data
                byte_array = QtCore.QByteArray()
                buffer = QtCore.QBuffer(byte_array)
                buffer.open(QtCore.QIODevice.WriteOnly)
                pixmap.save(buffer, "PNG")
                return byte_array.toBase64().data().decode('utf-8')
        return None

    def start_autosave(self):
        self.autosave_timer.start(300000)  # 300000 ms = 5 minutes

    def autosave(self):
        """Save on the timer. Whatever goes wrong with a save, the game goes
        on: an error raised from a timer ends the whole program, and a squid
        lost to a failed autosave is worse than one autosave missed."""
        print("     Autosaving...")
        try:
            self.save_game(is_autosave=True)
        except Exception as problem:
            import traceback
            traceback.print_exc()
            print(f"     Autosave failed and was skipped: {problem}")
