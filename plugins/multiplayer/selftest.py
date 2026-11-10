"""Does multiplayer networking work in THIS copy of the game?

    Dosidicus --network-self-test         (or: python main.py --network-self-test)

A built game is not the source it was built from: a module left out of the
build is found only when a player opens the Friends window. This runs the
real thing inside whatever it is started from - the compiled game included -
without opening a window: the game's own network code is loaded, two tanks
are opened on this machine and linked by a friend code, and one hears the
other. Nothing leaves the machine. The release build runs it on Windows,
macOS and Linux (.github/workflows/build-nuitka.yml).
"""
import socket
import sys
import time


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def checks():
    """Yield (what, passed, detail) for each thing a visit depends on."""
    # Everything a visit loads, by name, so a missing module is named.
    import importlib
    for name in ('friend_link', 'mp_constants', 'network_utilities', 'mp_network_node',
                 'consent', 'identity', 'remote_protocol', 'peer_ledger', 'encounter',
                 'host_body', 'visitor_mind'):
        try:
            importlib.import_module(f'plugins.multiplayer.{name}')
            yield f'{name} is in this build', True, ''
        except Exception as exc:                       # noqa: BLE001 - named for the player
            yield f'{name} is in this build', False, repr(exc)
            return

    from plugins.multiplayer import friend_link
    from plugins.multiplayer.mp_network_node import NetworkNode

    code = friend_link.encode_friend_code('86.12.34.56', 51234, 0xBEEF1)
    where = friend_link.decode_friend_code(code.lower().replace('-', ' '))
    yield ('a friend code is 15 characters and reads back',
           len(code.replace('-', '')) == 15
           and (where.ip, where.port, where.invitation) == ('86.12.34.56', 51234, 0xBEEF1), code)

    mine = NetworkNode('squid_self_a', port=_free_port())
    theirs = NetworkNode('squid_self_b', port=_free_port())
    try:
        for tank in (mine, theirs):
            tank.auto_reconnect = False
        opened = bool(mine.start_listening()) and bool(theirs.start_listening())
        yield 'two tanks open their sockets', opened, f'ports {mine.port} and {theirs.port}'
        if not opened:
            return

        # A stranger on the internet is not answered; the invitation lets one in.
        stranger = ('8.8.4.4', 40001)
        refused = not theirs._admit(stranger, {'node_id': 'x'})
        admitted = theirs._admit(stranger, {'node_id': 'x', 'invite': theirs.invitation})
        theirs.remove_friend(*stranger)
        yield 'a tank answers only whoever shows its invitation', refused and admitted, ''

        # Their code, read out; typed in here.
        their_code = theirs.friend_code()
        entered = friend_link.parse_friend(their_code)
        mine.add_friend('127.0.0.1', entered.port, entered.invitation)
        mine.send_message('heartbeat', {'node_id': mine.node_id, 'status': 'active'})
        deadline, heard = time.time() + 5.0, []
        while time.time() < deadline and not heard:
            heard = [m for m, _addr in theirs.receive_messages() if m.get('type') == 'heartbeat']
            time.sleep(0.02)
        yield ('a tank linked by friend code is heard by the other',
               bool(heard) and heard[0].get('invite') == theirs.invitation
               and heard[0]['payload'].get('node_id') == mine.node_id,
               f'code {their_code}')

        # And back: whoever showed the invitation is answered without one.
        theirs.send_message('heartbeat', {'node_id': theirs.node_id, 'status': 'active'})
        deadline, answer = time.time() + 5.0, []
        while time.time() < deadline and not answer:
            answer = [m for m, _addr in mine.receive_messages() if m.get('type') == 'heartbeat']
            time.sleep(0.02)
        yield 'and hears it back', bool(answer), ''
    finally:
        for tank in (mine, theirs):
            try:
                tank.close()
            except Exception:                           # noqa: BLE001
                pass


class _Both:
    """Where the result is written: the console if this copy of the game has
    one (a Windows build made without a console does not), and the file
    named by DOSIDICUS_SELF_TEST_LOG if there is one."""

    def __init__(self, console, path):
        self.console = console
        self.log = open(path, 'w', encoding='utf-8') if path else None

    def write(self, text):
        for stream in (self.console, self.log):
            if stream is not None:
                try:
                    stream.write(text)
                except (OSError, ValueError):
                    pass

    def flush(self):
        for stream in (self.console, self.log):
            if stream is not None:
                try:
                    stream.flush()
                except (OSError, ValueError):
                    pass


def run(out=None) -> int:
    """Run the checks, say what happened, and return the exit code."""
    import os
    out = out or _Both(sys.stdout, os.environ.get('DOSIDICUS_SELF_TEST_LOG'))
    failed = total = 0
    try:
        for what, passed, detail in checks():
            total += 1
            failed += 0 if passed else 1
            print(f"{'ok  ' if passed else 'FAIL'}  {what}" + (f'  ({detail})' if detail else ''),
                  file=out, flush=True)
    except Exception as exc:                            # noqa: BLE001
        import traceback
        traceback.print_exc(file=out)
        print(f'FAIL  the self-test itself stopped: {exc!r}', file=out, flush=True)
        failed += 1
    if failed:
        print(f'Network self-test FAILED: {failed} of {total} checks.', file=out, flush=True)
        return 1
    print(f'Network self-test passed: {total} checks.', file=out, flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(run())
