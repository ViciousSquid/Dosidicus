#!/usr/bin/env bash
# Start a built Dosidicus.app the way Finder would and require it to stay up.
#
#   bash tools/macos_smoke_test.sh /path/to/Dosidicus.app [arm64|x86_64]
#
# With an architecture, the app must be running as that one (a universal app
# on its own kind of Mac): the script refuses to pass on the wrong machine.
# Started from /, not from the app's folder - Finder promises no working
# directory - with its settings and saves in a throwaway folder.
set -euo pipefail

APP="${1:?the path to Dosidicus.app}"
WANT="${2:-}"
BIN="$APP/Contents/MacOS/Dosidicus"
test -x "$BIN"
if [[ -n "$WANT" ]]; then
  test "$(uname -m)" = "$WANT" || { echo "This Mac is $(uname -m), not $WANT" >&2; exit 2; }
  lipo "$BIN" -verify_arch "$WANT"
fi

LOG="${SMOKE_LOG:-$PWD/smoke-macos.log}"
export DOSIDICUS_DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/dosidicus-smoke.XXXXXX")"
export DOSIDICUS_SKIP_LANGUAGE_SPLASH=1
cd /
QT_DEBUG_PLUGINS=1 "$BIN" > "$LOG" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true' EXIT

# "Applied language" is printed near the start of the main window. Fifteen
# more seconds alive catches what follows: exceptions, native Qt crashes, a
# data folder that cannot be written.
READY=0
for _ in $(seq 1 60); do
  sleep 1
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "::error::The app exited before it had finished starting"
    cat "$LOG"
    wait "$PID" || true
    exit 1
  fi
  if grep -q "Applied language from config" "$LOG"; then
    READY=$((READY + 1))
    if [ "$READY" -ge 15 ]; then
      test -f "$DOSIDICUS_DATA_DIR/config.ini"
      echo "Started and stayed up as $(uname -m), with its data in a writable folder"
      exit 0
    fi
  fi
done
echo "::error::The app did not finish starting in 60 seconds"
cat "$LOG"
exit 1
