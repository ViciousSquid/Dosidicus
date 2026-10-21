#!/bin/bash
# Run the console-enabled Dosidicus debug build from Finder's Terminal.
# Keep this file next to Dosidicus.app after extracting the ZIP.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HERE/Dosidicus.app/Contents/MacOS/Dosidicus"
LOG_DIR="$HOME/Library/Logs/Dosidicus"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/debug-$(date +%Y%m%d-%H%M%S).log"

export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
export QT_DEBUG_PLUGINS=1
export NSUnbufferedIO=YES

echo "============================================================"
echo "Dosidicus macOS debug launcher"
echo "Executable: $BIN"
echo "Output log: $LOG_FILE"
echo "User logs: $HOME/Library/Application Support/Dosidicus/logs"
echo "============================================================"
echo

if [[ ! -x "$BIN" ]]; then
    echo "ERROR: The debug executable was not found or is not executable." | tee "$LOG_FILE"
    STATUS=127
else
    # Capture Qt plugin diagnostics, Python tracebacks and native crash output.
    # PIPESTATUS keeps the program's exit code rather than tee's exit code.
    "$BIN" 2>&1 | tee "$LOG_FILE"
    STATUS="${PIPESTATUS[0]}"
fi

echo
echo "============================================================"
echo "Dosidicus exited with status $STATUS"
echo "Debug log: $LOG_FILE"
echo "For a native crash, also check ~/Library/Logs/DiagnosticReports/"
echo "============================================================"
echo
read -r -p "Press Return to close this Terminal window..." _
exit "$STATUS"
