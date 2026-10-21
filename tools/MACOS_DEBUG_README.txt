DOSIDICUS — MACOS DEBUG BUILD
===========================

This diagnostic build is separate from the normal macOS release. It is
compiled with Nuitka's macOS console mode enabled so that Python output,
Qt plugin diagnostics and native crash messages can be inspected.

1. Extract the full ZIP; keep Dosidicus.app and the .command file together.
2. Double-click "Run Dosidicus Debug.command". Terminal will open.
3. Reproduce the crash. The launcher WAITS for Return after Dosidicus exits.
4. Copy the console output or attach the saved log:

   ~/Library/Logs/Dosidicus/debug-YYYYMMDD-HHMMSS.log

   Python application errors may also be logged under:
   ~/Library/Application Support/Dosidicus/logs/

   For a native crash, check:
   ~/Library/Logs/DiagnosticReports/

If Gatekeeper prevents a downloaded, ad-hoc-signed app from launching,
Control-click the .command file and choose Open. You can also open Terminal
yourself and run:

   bash "/path/to/Run Dosidicus Debug.command"

This debug build uses the same user profile and saves as the normal build.
It is diagnostic only; keep using the normal macOS artifact for distribution.
