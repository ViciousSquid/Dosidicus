import json
import os
import zipfile
import shutil
from datetime import datetime
from uuid import UUID

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)

class SaveManager:
    def __init__(self, save_directory="saves"):
        self.save_directory = save_directory
        os.makedirs(save_directory, exist_ok=True)

        self.autosave_path = os.path.join(save_directory, "autosave.zip")
        self.manual_path = os.path.join(save_directory, "save_data.zip")  # This will be updated dynamically
        self.backup_path = os.path.join(save_directory, "autosave_backup.zip")

    # --------------------------------------------------
    # Public helpers
    # --------------------------------------------------
    def save_exists(self, autosave=False):
        if autosave:
            return os.path.exists(self.autosave_path)
        else:
            # For manual saves, we need to check if any UUID-based save exists
            return self._get_manual_save_path() is not None

    def get_latest_save(self):
        """Return the most recent save: permanent manual > autosave > nothing"""
        # 1. Look for permanent manual save: {uuid}.zip
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and self.tamagotchi_logic.squid:
            uuid_str = str(self.tamagotchi_logic.squid.uuid)
            manual_path = self._get_save_path_for_uuid(uuid_str, is_autosave=False)
            if os.path.exists(manual_path):
                return manual_path

        # 2. Fallback: autosave for this UUID
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and self.tamagotchi_logic.squid:
            uuid_str = str(self.tamagotchi_logic.squid.uuid)
            autosave_path = self._get_save_path_for_uuid(uuid_str, is_autosave=True)
            if os.path.exists(autosave_path):
                return autosave_path

        # Optional: fallback to any old-style timestamped save (for backward compatibility)
        old_manual = self._get_manual_save_path()
        if old_manual:
            return old_manual

        return None

    def _get_manual_save_path(self):
        """Find the most recent manual save file (UUID-based)"""
        try:
            # Look for any .zip files in save directory that aren't autosave or backup
            save_files = [f for f in os.listdir(self.save_directory) 
                         if f.endswith('.zip') and f not in ['autosave.zip', 'autosave_backup.zip']]
            
            if save_files:
                # Return the most recently modified one
                save_files = [os.path.join(self.save_directory, f) for f in save_files]
                return max(save_files, key=os.path.getmtime)
            return None
        except (FileNotFoundError, ValueError):
            return None

    def _get_save_path_for_uuid(self, uuid_str, is_autosave=False):
        """Generate save path for a specific UUID.
        
        - Autosaves → {uuid}_autosave.zip
        - Manual saves → {uuid}.zip   ← PERMANENT, single file (no timestamp)
        """
        safe_uuid = str(uuid_str).replace('-', '_')
        
        if is_autosave:
            return os.path.join(self.save_directory, f"{safe_uuid}_autosave.zip")
        else:
            # Single permanent manual save file — no timestamp!
            return os.path.join(self.save_directory, f"{safe_uuid}.zip")

    # --------------------------------------------------
    # Save API
    # --------------------------------------------------

    def save_game(self, save_data: dict, is_autosave: bool = False) -> str | None:
        """Save game with proper UUID management."""
        try:
            from PyQt5.QtWidgets import QMessageBox
            import uuid

            # === PRIORITY 1: Use the live squid's UUID if available (most reliable) ===
            live_squid = None
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                live_squid = getattr(self.tamagotchi_logic, 'squid', None)

            if live_squid and hasattr(live_squid, 'uuid') and live_squid.uuid:
                squid_uuid = str(live_squid.uuid)
                print(f"[SaveManager] Using live squid UUID: {squid_uuid}")
            else:
                # Fallback: extract from save_data (old behavior)
                squid_uuid = save_data.get('game_state', {}).get('squid', {}).get('uuid')
                if not squid_uuid:
                    squid_uuid = str(uuid.uuid4())
                    save_data.setdefault('game_state', {}).setdefault('squid', {})['uuid'] = squid_uuid
                    print(f"[SaveManager] Generated new UUID (no live squid): {squid_uuid}")

            # Ensure UUID is in save_data for consistency
            save_data.setdefault('game_state', {}).setdefault('squid', {})['uuid'] = squid_uuid

            # Determine save path
            target_path = self._get_save_path_for_uuid(squid_uuid, is_autosave=is_autosave)

            # Skip if identical
            if os.path.exists(target_path):
                existing_data = self._load_single_save(target_path)
                if existing_data and self._are_saves_identical(existing_data, save_data):
                    print(f"[SaveManager] Identical save already exists → skipping: {target_path}")
                    return target_path

            # Backup old save
            backup_path = None
            if os.path.exists(target_path):
                backup_path = target_path + ".backup"
                shutil.copy2(target_path, backup_path)

            # Write to temp file
            temp_path = target_path + ".tmp"
            with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for key, data in save_data.items():
                    zf.writestr(f"{key}.json", json.dumps(data, indent=4, cls=DateTimeEncoder))
                zf.writestr("uuid.txt", f"SquidSignature    {squid_uuid}")

            # Atomic replace
            if os.path.exists(target_path):
                os.replace(target_path, target_path + ".old")
            os.replace(temp_path, target_path)

            # Cleanup
            for old in [f for f in os.listdir(self.save_directory) if f.endswith(('.old', '.backup'))]:
                try:
                    os.remove(os.path.join(self.save_directory, old))
                except:
                    pass

            print(f"[SaveManager] Save successful → {target_path}")
            return target_path

        except Exception as e:
            print(f"[SaveManager] Save failed: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _are_saves_identical(self, save1, save2):
        """Compare two save dictionaries for equality."""
        try:
            # Remove any volatile fields that might differ between saves
            ignore_fields = ['_save_timestamp', 'autosave_count']
            
            def clean_save(save):
                if isinstance(save, dict):
                    return {k: clean_save(v) for k, v in save.items() 
                        if k not in ignore_fields}
                elif isinstance(save, list):
                    return [clean_save(item) for item in save]
                else:
                    return save
            
            cleaned1 = clean_save(save1)
            cleaned2 = clean_save(save2)
            
            return cleaned1 == cleaned2
        except Exception as e:
            print(f"[SaveManager] Error comparing saves: {e}")
            return False

    def _load_single_save(self, path):
        """Load a single save file."""
        try:
            data = {}
            with zipfile.ZipFile(path, 'r') as zf:
                for fname in zf.namelist():
                    if fname.endswith('.json'):
                        with zf.open(fname) as f:
                            key = os.path.splitext(fname)[0]
                            data[key] = json.loads(f.read().decode('utf-8'))
            return data
        except Exception as e:
            print(f"[SaveManager] Error loading save {path}: {e}")
            return None
        

    def cleanup_duplicate_saves(self):
        """Remove duplicate save files with identical content."""
        try:
            # Get all save files
            save_files = [f for f in os.listdir(self.save_directory) 
                        if f.endswith('.zip')]
            
            # Group by UUID
            saves_by_uuid = {}
            for save_file in save_files:
                if '_autosave.zip' in save_file:
                    uuid = save_file.replace('_autosave.zip', '')
                else:
                    # Extract UUID from timestamped files
                    parts = save_file.split('_')
                    if len(parts) >= 6:  # UUID has 5 parts when split by '_'
                        uuid = '_'.join(parts[:5])
                    else:
                        continue
                
                if uuid not in saves_by_uuid:
                    saves_by_uuid[uuid] = []
                saves_by_uuid[uuid].append(save_file)
            
            # Check each group for duplicates
            for uuid, files in saves_by_uuid.items():
                if len(files) > 1:
                    print(f"[SaveManager] Found {len(files)} saves for UUID {uuid}")
                    
                    # Load and compare saves
                    save_contents = {}
                    for file in files:
                        path = os.path.join(self.save_directory, file)
                        content = self._load_single_save(path)
                        if content:
                            save_contents[file] = content
                    
                    # Find unique saves
                    unique_saves = {}
                    for file1, content1 in save_contents.items():
                        is_duplicate = False
                        for file2, content2 in unique_saves.items():
                            if self._are_saves_identical(content1, content2):
                                is_duplicate = True
                                print(f"[SaveManager] {file1} is duplicate of {file2}")
                                # Keep the newer file
                                time1 = os.path.getmtime(os.path.join(self.save_directory, file1))
                                time2 = os.path.getmtime(os.path.join(self.save_directory, file2))
                                if time1 > time2:
                                    # Delete the older one
                                    os.remove(os.path.join(self.save_directory, file2))
                                    unique_saves[file2] = content1
                                else:
                                    # Delete the newer one
                                    os.remove(os.path.join(self.save_directory, file1))
                                break
                        
                        if not is_duplicate:
                            unique_saves[file1] = content1
                            
        except Exception as e:
            print(f"[SaveManager] Error cleaning duplicate saves: {e}")

    # --------------------------------------------------
    # Load
    # --------------------------------------------------
    def load_game(self) -> dict | None:
        latest = self.get_latest_save()
        if not latest:
            return None
        data = {}
        squid_uuid = None
        with zipfile.ZipFile(latest, 'r') as zf:
            for fname in zf.namelist():
                if fname == "uuid.txt":
                    squid_uuid = zf.read(fname).decode().strip()
                    continue
                with zf.open(fname) as f:
                    raw = f.read()
                    if not raw:
                        continue
                    key = os.path.splitext(fname)[0]
                    data[key] = json.loads(raw.decode('utf-8'))
        # inject UUID into returned dict
        data["_uuid"] = squid_uuid
        return data

    # --------------------------------------------------
    # House-keeping
    # --------------------------------------------------
    def delete_save(self, is_autosave: bool = False) -> bool:
        if is_autosave:
            path = self.autosave_path
        else:
            path = self._get_manual_save_path()
        
        if path and os.path.exists(path):
            os.remove(path)
            return True
        return False

    def get_save_timestamp(self, is_autosave: bool = False) -> float | None:
        if is_autosave:
            path = self.autosave_path
        else:
            path = self._get_manual_save_path()
        
        return os.path.getmtime(path) if path and os.path.exists(path) else None

    def get_save_size(self, is_autosave: bool = False) -> int | None:
        if is_autosave:
            path = self.autosave_path
        else:
            path = self._get_manual_save_path()
        
        return os.path.getsize(path) if path and os.path.exists(path) else None
