"""Filesystem + share/pick helpers that work on Android and on the desktop.

Android specifics use pyjnius / plyer and are wrapped in try/except so the same
code runs on a desktop for development. The export always lands in a
user-accessible folder; sharing via an Intent is attempted on top of that.
"""

import os


def is_android():
    try:
        import android  # noqa: F401  (only importable on-device)
        return True
    except ImportError:
        return False


def export_dir(app):
    """A directory the user can reach. On Android this is the app's external
    files dir (visible in Files under Android/data/<pkg>/files); on desktop it's
    an ``exports`` folder next to the save."""
    if is_android():
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            ext = PythonActivity.mActivity.getExternalFilesDir(None)
            if ext is not None:
                d = os.path.join(ext.getAbsolutePath(), "exports")
                os.makedirs(d, exist_ok=True)
                return d
        except Exception:
            pass
    d = os.path.join(app.user_data_dir, "exports")
    os.makedirs(d, exist_ok=True)
    return d


def share_file(path, title="Share squid"):
    """Best-effort Android share sheet for a file. Returns True if launched."""
    if not is_android():
        return False
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        File = autoclass("java.io.File")
        FileProvider = autoclass("androidx.core.content.FileProvider")

        activity = PythonActivity.mActivity
        jfile = File(path)
        authority = activity.getPackageName() + ".fileprovider"
        uri = FileProvider.getUriForFile(activity, authority, jfile)

        intent = Intent(Intent.ACTION_SEND)
        intent.setType("application/zip")
        intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        chooser = Intent.createChooser(intent, cast("java.lang.CharSequence",
                                                    autoclass("java.lang.String")(title)))
        activity.startActivity(chooser)
        return True
    except Exception as e:
        print(f"[Dosidicus] share intent failed ({e}); file saved at {path}")
        return False


def pick_file(on_choice):
    """Open a file picker for a .zip. Calls on_choice(path) or on_choice(None).
    Returns True if a native/plyer picker was launched, False if the caller
    should fall back to its own chooser (desktop)."""
    if is_android():
        try:
            from plyer import filechooser

            def _cb(selection):
                on_choice(selection[0] if selection else None)
            filechooser.open_file(on_selection=_cb,
                                  filters=[("Squid zip", "*.zip")])
            return True
        except Exception as e:
            print(f"[Dosidicus] plyer filechooser failed: {e}")
    return False
