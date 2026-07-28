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


def _android_sdk_int():
    from jnius import autoclass
    return autoclass("android.os.Build$VERSION").SDK_INT


def save_to_downloads(src_path, filename, mime="application/zip"):
    """Copy ``src_path`` into the device's public **Downloads** folder so the
    user can actually find it (no more buried app-private folder).

    Returns ``(location, uri)`` where ``location`` is a human-readable place
    ("Downloads/<name>") and ``uri`` is a shareable ``content://`` URI (or None
    off-Android). On API 29+ this uses MediaStore (no storage permission and it
    hands back a content URI we can share without a FileProvider). Raises on
    failure so the caller can fall back.
    """
    if not is_android():
        # Desktop dev: drop it in ~/Downloads if that exists, else next to it.
        home_dl = os.path.join(os.path.expanduser("~"), "Downloads")
        dest_dir = home_dl if os.path.isdir(home_dl) else os.path.dirname(src_path)
        dest = os.path.join(dest_dir, filename)
        if os.path.abspath(dest) != os.path.abspath(src_path):
            import shutil
            shutil.copyfile(src_path, dest)
        return dest, None

    from jnius import autoclass
    if _android_sdk_int() >= 29:
        # Scoped storage: insert into the Downloads collection via MediaStore.
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        ContentValues = autoclass("android.content.ContentValues")
        Downloads = autoclass("android.provider.MediaStore$Downloads")
        activity = PythonActivity.mActivity
        resolver = activity.getContentResolver()
        values = ContentValues()
        values.put("_display_name", filename)
        values.put("mime_type", mime)
        values.put("relative_path", "Download")
        uri = resolver.insert(Downloads.EXTERNAL_CONTENT_URI, values)
        stream = resolver.openOutputStream(uri)
        try:
            with open(src_path, "rb") as f:
                stream.write(f.read())  # pyjnius maps Python bytes -> byte[]
        finally:
            stream.flush()
            stream.close()
        return "Downloads/" + filename, uri

    # Legacy (API 24-28): write straight to the public Downloads directory.
    Environment = autoclass("android.os.Environment")
    dl = Environment.getExternalStoragePublicDirectory(
        Environment.DIRECTORY_DOWNLOADS).getAbsolutePath()
    os.makedirs(dl, exist_ok=True)
    dest = os.path.join(dl, filename)
    import shutil
    shutil.copyfile(src_path, dest)
    return "Downloads/" + filename, None


def share_uri(uri, title="Share your squid", mime="application/zip"):
    """Launch the Android share sheet for a ``content://`` URI. Returns True on
    success. Works without a FileProvider because MediaStore already gives us a
    shareable content URI."""
    if not is_android() or uri is None:
        return False
    try:
        from jnius import autoclass, cast
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        activity = PythonActivity.mActivity
        intent = Intent(Intent.ACTION_SEND)
        intent.setType(mime)
        intent.putExtra(Intent.EXTRA_STREAM, cast("android.os.Parcelable", uri))
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        chooser = Intent.createChooser(
            intent, cast("java.lang.CharSequence", autoclass("java.lang.String")(title)))
        chooser.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(chooser)
        return True
    except Exception as e:
        print(f"[Dosidicus] share_uri failed: {e}")
        return False


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


def open_url(url):
    """Open a URL in the device browser. Uses an Android VIEW intent on-device,
    and falls back to the desktop's default browser. Returns True on success."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if is_android():
        try:
            from jnius import autoclass, cast
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            Intent = autoclass("android.content.Intent")
            Uri = autoclass("android.net.Uri")
            intent = Intent(Intent.ACTION_VIEW)
            intent.setData(Uri.parse(url))
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            PythonActivity.mActivity.startActivity(intent)
            return True
        except Exception as e:
            print(f"[Dosidicus] open_url intent failed: {e}")
            return False
    try:
        import webbrowser
        return webbrowser.open(url)
    except Exception as e:
        print(f"[Dosidicus] webbrowser.open failed: {e}")
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
