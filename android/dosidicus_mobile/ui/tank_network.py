"""Putting the phone's tank on the network, and taking it off.

The link itself is engine/tank_link.py and knows nothing of Android. This is
the part that does: where the friends list is kept, the lock Android wants
held before it will deliver the home network's multicast to an app, and
whether the player left multiplayer on last time.
"""
import os

from ..engine.tank_link import TankLink

#: Present while the player has multiplayer on, so it is on again next time.
ON_FLAG = "multiplayer_link_on"
FRIENDS_FILE = "friends.json"


def _multicast_lock():
    """Android drops multicast to save power unless an app holds this. With
    no Wi-Fi, or off Android, there is nothing to hold - and friend codes,
    which need no multicast, work regardless."""
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        context = autoclass("android.content.Context")
        wifi = activity.getApplicationContext().getSystemService(context.WIFI_SERVICE)
        lock = wifi.createMulticastLock("dosidicus")
        lock.setReferenceCounted(False)
        lock.acquire()
        return lock
    except Exception:
        return None


def _flag(app):
    return os.path.join(getattr(app, "user_data_dir", "") or ".", ON_FLAG)


def link_of(app):
    link = getattr(app, "tank_link", None)
    return link if link is not None and link.running else None


def was_left_on(app):
    return os.path.exists(_flag(app))


def start(app):
    """Go on the network. Returns the link, or None if the socket would not open."""
    link = link_of(app)
    if link is not None:
        return link
    app._multicast_lock = getattr(app, "_multicast_lock", None) or _multicast_lock()
    store = os.path.join(getattr(app, "user_data_dir", "") or ".", FRIENDS_FILE)
    # A port or address server other than the usual ones: only ever set by
    # the tools that run several tanks on one machine.
    options = {name: getattr(app, 'link_' + name) for name in ('port', 'stun_server')
               if getattr(app, 'link_' + name, None) is not None}
    link = TankLink(app.sim, store=store, **options)
    if not link.start():
        return None
    app.tank_link = link
    app._link_events_seen = 0.0
    try:
        with open(_flag(app), "w") as handle:
            handle.write("1")
    except OSError:
        pass
    return link


def stop(app, forget=True):
    """Leave the network. `forget` is the player turning multiplayer off;
    without it (the app closing) it comes back on next time."""
    link = getattr(app, "tank_link", None)
    if link is not None:
        link.stop()
    app.tank_link = None
    lock = getattr(app, "_multicast_lock", None)
    if lock is not None:
        try:
            lock.release()
        except Exception:
            pass
        app._multicast_lock = None
    if forget:
        try:
            os.remove(_flag(app))
        except OSError:
            pass


def new_events(app):
    """What has happened on the link since this was last asked, in words."""
    link = link_of(app)
    if link is None:
        return []
    seen = getattr(app, "_link_events_seen", 0.0)
    fresh = [(at, text) for at, text in link.events if at > seen]
    if fresh:
        app._link_events_seen = fresh[-1][0]
    return [text for _at, text in fresh]
