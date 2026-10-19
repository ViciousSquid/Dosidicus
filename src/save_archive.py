"""The desktop save archive container, also used by Android autosaves/exports."""
from datetime import datetime
import json
import os
from pathlib import Path
from uuid import UUID
import zipfile


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def write_save_archive(path, sections, squid_uuid):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for key, data in sections.items():
                archive.writestr(f'{key}.json', json.dumps(data, indent=4, cls=DateTimeEncoder, allow_nan=False))
            archive.writestr('uuid.txt', f'SquidSignature    {squid_uuid}')
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return str(path)
