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
        self.manual_path   = os.path.join(save_directory, "save_data.zip")
        self.backup_path   = os.path.join(save_directory, "autosave_backup.zip")

    # --------------------------------------------------
    # Public helpers
    # --------------------------------------------------
    def save_exists(self, autosave=False):
        path = self.autosave_path if autosave else self.manual_path
        return os.path.exists(path)

    def get_latest_save(self):
        if self.save_exists(autosave=True):
            return self.autosave_path
        if self.save_exists(autosave=False):
            return self.manual_path
        return None

    # --------------------------------------------------
    # Save API
    # --------------------------------------------------
    def save_game(self, save_data: dict, is_autosave: bool = False) -> str | None:
        """Autosave: silent rotating overwrite with ONE backup.
           Manual : refuse to overwrite unless user approves."""
        try:
            from PyQt5.QtWidgets import QMessageBox

            target_path = self.autosave_path if is_autosave else self.manual_path

            # ---- single autosave backup ----
            if is_autosave and os.path.exists(target_path):
                shutil.copy2(target_path, self.backup_path)

            # ---- manual save confirmation ----
            if not is_autosave and os.path.exists(target_path):
                reply = QMessageBox.question(
                    None, "Overwrite save?",
                    "A manual save already exists. Overwrite it?",
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
                zf.writestr("uuid.txt", f"SquidSignature    {save_data['game_state']['squid']['uuid']}")

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
        path = self.autosave_path if is_autosave else self.manual_path
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def get_save_timestamp(self, is_autosave: bool = False) -> float | None:
        path = self.autosave_path if is_autosave else self.manual_path
        return os.path.getmtime(path) if os.path.exists(path) else None

    def get_save_size(self, is_autosave: bool = False) -> int | None:
        path = self.autosave_path if is_autosave else self.manual_path
        return os.path.getsize(path) if os.path.exists(path) else None