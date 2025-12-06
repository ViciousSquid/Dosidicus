import json
import os
import zipfile
import shutil
from datetime import datetime
from uuid import UUID
from PyQt5.QtCore import QDateTime

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
        if self.save_exists(autosave=True):
            return self.autosave_path
        if self.save_exists(autosave=False):
            return self._get_manual_save_path()
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

    def _get_save_path_for_uuid(self, uuid_str):
        """Generate save path for a specific UUID"""
        safe_uuid = str(uuid_str).replace('-', '_')  # Make UUID filename-safe
        return os.path.join(self.save_directory, f"{safe_uuid}.zip")
    
    def get_manual_save_list(self):
        """Get list of manual save files with metadata for selection dialog"""
        saves = []
        try:
            for f in os.listdir(self.save_directory):
                if f.endswith('.zip') and f not in ['autosave.zip', 'autosave_backup.zip']:
                    filepath = os.path.join(self.save_directory, f)
                    try:
                        with zipfile.ZipFile(filepath, 'r') as zf:
                            name = "Unnamed Squid"
                            personality = "Unknown"
                            
                            if 'game_state.json' in zf.namelist():
                                game_data = json.loads(zf.read('game_state.json').decode('utf-8'))
                                squid_data = game_data.get('squid', {})
                                name = squid_data.get('name', 'Unnamed Squid')
                                personality = squid_data.get('personality', 'Unknown')
                            
                            saves.append({
                                'path': filepath,
                                'filename': f,
                                'name': name,
                                'personality': personality,
                                'modified': os.path.getmtime(filepath),
                                'size': os.path.getsize(filepath)
                            })
                    except Exception as e:
                        print(f"[SaveManager] Error reading {f}: {e}")
        except:
            pass
        
        return sorted(saves, key=lambda x: x['modified'], reverse=True)
    
    def load_from_path(self, path):
        """Load save data from a specific file path"""
        return self._load_zip_data(path)
    
    def _load_zip_data(self, path):
        """Internal: Load data from zip file"""
        if not os.path.exists(path):
            return None
        
        data = {}
        squid_uuid = None
        with zipfile.ZipFile(path, 'r') as zf:
            for fname in zf.namelist():
                if fname == "uuid.txt":
                    squid_uuid = zf.read(fname).decode().strip()
                    if 'SquidSignature' in squid_uuid:
                        squid_uuid = squid_uuid.split('SquidSignature    ')[-1]
                    continue
                with zf.open(fname) as f:
                    raw = f.read()
                    if not raw:
                        continue
                    key = os.path.splitext(fname)[0]
                    data[key] = json.loads(raw.decode('utf-8'))
        
        data["_uuid"] = squid_uuid
        return data

    # --------------------------------------------------
    # Save API
    # --------------------------------------------------
    def save_game(self, save_data: dict, is_autosave: bool = False) -> str | None:
        """Autosave: silent rotating overwrite with ONE backup.
           Manual : refuse to overwrite unless user approves."""
        try:
            from PyQt5.QtWidgets import QMessageBox

            # Extract UUID from save data
            squid_uuid = save_data.get('game_state', {}).get('squid', {}).get('uuid')
            if not squid_uuid and not is_autosave:
                print("[SaveManager] Warning: No UUID found in save data for manual save")
                return None

            if is_autosave:
                target_path = self.autosave_path
            else:
                target_path = self._get_save_path_for_uuid(squid_uuid)

            # ---- single autosave backup ----
            if is_autosave and os.path.exists(target_path):
                shutil.copy2(target_path, self.backup_path)

            # ---- manual save confirmation ----
            if not is_autosave and os.path.exists(target_path):
                reply = QMessageBox.question(
                    None, "Overwrite save?",
                    "A save already exists for this squid. Overwrite it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return None  # user cancelled

            # ---- atomic write ----
            temp_path = target_path + ".tmp"
            with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                # 1) usual game files
                for key, data in save_data.items():
                    zf.writestr(f"{key}.json",
                                json.dumps(data, indent=4, cls=DateTimeEncoder))
                # 2) immutable squid UUID
                zf.writestr("uuid.txt", f"SquidSignature    {squid_uuid}")

            if os.path.exists(target_path):
                os.replace(target_path, target_path + ".old")
            os.replace(temp_path, target_path)
            return target_path

        except Exception as e:
            print(f"[SaveManager] Save failed: {e}")
            import traceback
            traceback.print_exc()
            return None

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