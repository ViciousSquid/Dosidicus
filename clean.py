from pathlib import Path
import shutil

root = Path.cwd()

for folder in root.rglob("__pycache__"):
    if folder.is_dir():
        try:
            shutil.rmtree(folder)
            print(f"Deleted: {folder}")
        except Exception as e:
            print(f"Failed to delete {folder}: {e}")

print("\nFinished.")