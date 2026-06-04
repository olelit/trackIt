# Debug Panel with App Info — Design

**Date:** 2026-06-04
**Status:** Approved
**Scope:** Feature #3 of 3 (default pause / task detection / debug panel)

## Goal

Add a debug panel to TrackIt that shows, for the currently active window:
- Application name and window title
- PID
- RAM usage of the application process
- Command-line arguments
- Best-effort guess at "what is open" (a path to a folder, when one can be derived from argv)

The panel is **toggleable** — by default it shows a single status line; the user can expand it for full details. It does not influence tracking. It is a passive observer of the window tracker and the running processes.

## Background

A debug panel existed before (commits `cf53b3b` through `3c41930`) and was removed in `d654ae5 refactor: remove debug panel` because it was redundant with the per-app real-time display in `ActivityDetailWidget`. This is a deliberate rebuild, scoped to a different purpose: **diagnostic visibility into the tracked window**, not activity time tracking.

## Architecture

```
KWin D-Bus → WindowTrackerService._poll
                ↓ (now also reads `pid` from props)
            window_changed(WindowInfo{pid, app_name, window_title})
                ↓
            AppInfoService._on_window_changed:
                psutil.Process(pid).memory_info().rss → ram_mb
                /proc/<pid>/cmdline → argv
                heuristic(argv) → opened_path
                AppInfo = (pid, app_name, title, ram_mb, argv, opened_path)
                info_updated.emit(AppInfo)
                ↓
            DebugPanel._on_info_updated: render labels

QTimer 1s → AppInfoService._refresh_ram_only:
                psutil.Process(pid).memory_info().rss → new ram_mb
                info_updated.emit(updated AppInfo)
                ↓
            DebugPanel._on_info_updated: render labels
```

The service layer is the source of truth. The widget is a pure renderer. `WindowTrackerService` continues to be a thin wrapper around the KWin D-Bus polling — it gains one extra property read (`pid`) but no new logic.

## Data Model

**New file** `models/app_info.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    pid: int | None
    app_name: str
    window_title: str
    ram_mb: int | None
    argv: tuple[str, ...]
    opened_path: str | None
```

`frozen=True` because `AppInfo` is a value object passed across signals; immutability prevents accidental aliasing bugs.

`tuple` (not `list`) for `argv` to keep the dataclass hashable and safe for use as a Qt signal payload.

## New Service

**New file** `services/app_info_service.py`:

```python
class AppInfoService(QObject):
    info_updated = Signal(AppInfo)
    
    def __init__(self, window_tracker: WindowTrackerService, parent: QObject | None = None) -> None: ...
    @property
    def current_info(self) -> AppInfo | None: ...
    def stop(self) -> None: ...   # disconnects the RAM timer
```

The constructor:
1. Stores `window_tracker`.
2. Connects `window_tracker.window_changed` → `_on_window_changed`.
3. Starts a `QTimer(1000)` that fires `_refresh_ram_only`.
4. Initializes `self._current_info = None`.

`_on_window_changed(winfo)`:
1. Calls `_build_info(winfo)` to construct a fresh `AppInfo` (calls psutil + /proc).
2. Stores it in `self._current_info`.
3. Emits `info_updated`.

`_refresh_ram_only()`:
1. If `current_info` is None or `pid` is None, do nothing.
2. Re-read RAM via `psutil.Process(pid).memory_info().rss // (1024 * 1024)`.
3. Construct a new `AppInfo` with the same fields but updated `ram_mb`.
4. Emit `info_updated`.

`_build_info(winfo)`:
1. `ram_mb = _read_ram_mb(winfo.pid)`
2. `argv = _read_argv(winfo.pid)`
3. `opened_path = _detect_opened_path(argv)`
4. Return `AppInfo(pid=winfo.pid, app_name=winfo.app_name, window_title=winfo.window_title, ram_mb=ram_mb, argv=argv, opened_path=opened_path)`.

`_read_ram_mb(pid)`:
- `None` if `pid is None`.
- `None` on `psutil.NoSuchProcess` / `psutil.AccessDenied` / `ProcessLookupError`.
- Otherwise: `psutil.Process(pid).memory_info().rss // (1024 * 1024)`.

`_read_argv(pid)`:
- `()` if `pid is None`.
- `()` on `OSError` / `FileNotFoundError` / `ProcessLookupError`.
- Otherwise: read `/proc/<pid>/cmdline` as bytes, split on `\x00`, decode each non-empty piece as UTF-8 with `errors="replace"`, return as a tuple.

`_detect_opened_path(argv)`:
- Iterate `argv[1:]` in reverse (skip the executable itself).
- For each token that starts with `/` or `~` and does not start with `--`:
  - Expand `~` to the user home.
  - If the result is an existing directory, return it.
- Return `None` if nothing matches.

## New Widget

**New file** `ui/debug_panel.py`:

```python
class DebugPanel(QWidget):
    def __init__(self, app_info_service: AppInfoService, parent: QWidget | None = None) -> None: ...
    def set_collapsed(self, collapsed: bool) -> None: ...
    def is_collapsed(self) -> bool: ...
```

Layout:
```
QVBoxLayout
├── QHBoxLayout (header)
│   ├── QLabel "Debug"
│   ├── stretch
│   └── QPushButton "▼" / "▲" (collapse toggle)
├── QFrame (separator line)
├── QLabel (summary line, always visible):  "Window: <app> — <title> | RAM: <N> MB"
└── QWidget (details, visibility toggled)
    ├── QLabel "PID: <pid>"
    ├── QLabel "Argv: <argv tokens joined by spaces, truncated>"
    └── QLabel "Opened: <opened_path or '—'>"
```

State:
- Default: collapsed. Only the summary line and the toggle button are visible.
- Expanded: details section becomes visible. Toggle button text changes from `▼` to `▲`.

The widget:
- Subscribes to `app_info_service.info_updated` in `__init__`.
- On signal, updates the labels.
- Does not own any timer or perform I/O.
- Truncates long window titles and argv for display only (the full data stays in `AppInfo`).

## Modifications to Existing Code

### `services/window_tracker.py:_poll`

Add one line: read `pid` from the props dict and pass it through to `_on_window_info`:

```python
pid = int(props.get("pid", 0) or 0)
self._on_window_info(app_name, window_title, pid)
```

`_on_window_info` already accepts `pid: int` and stores it in `WindowInfo.pid` (which currently defaults to `None` because callers pass `0`). With this change, `pid` will be populated whenever KWin provides it (KDE Plasma 6 does).

### `core/app.py:main`

After `create_services(storage)` and `storage.reset_active()`, add:

```python
app_info_service = AppInfoService(window_tracker)
```

Pass it to `MainWindow` constructor.

After `app.exec()` returns (currently where `window_tracker.stop()` is called), also call `app_info_service.stop()` to disconnect the RAM refresh timer.

### `ui/main_window.py`

`MainWindow.__init__` accepts a new `app_info_service: AppInfoService` parameter.

The main layout becomes a `QSplitter(Qt.Orientation.Vertical)` containing the existing horizontal splitter (with activity list and detail) and the new `DebugPanel`:

```python
outer = QSplitter(Qt.Orientation.Vertical)
outer.addWidget(self._activity_splitter)   # existing horizontal splitter
outer.addWidget(self._debug_panel)
outer.setSizes([400, 100])                # most space for activity, smaller for debug
```

### `pyproject.toml`

Add to `dependencies`:

```
"psutil>=5.9",
```

## Testing

### `tests/test_app_info_service.py` (no Qt, pure unit)

- `test_builds_info_from_window_info` — given a `WindowInfo` with pid, the resulting `AppInfo` has matching `app_name`, `window_title`, `pid`.
- `test_read_ram_returns_mb_for_valid_pid` — mock `psutil.Process(pid).memory_info().rss` to return a known byte count, verify the MB conversion.
- `test_read_ram_returns_none_for_dead_pid` — mock `psutil.NoSuchProcess`, verify `None`.
- `test_read_ram_returns_none_for_none_pid` — `pid=None` → `ram_mb=None`.
- `test_read_argv_parses_null_separated_proc` — use the actual `/proc/self/cmdline` (always exists during tests), verify it parses into a non-empty tuple.
- `test_read_argv_returns_empty_for_none_pid` — `pid=None` → `argv=()`.
- `test_heuristic_finds_existing_directory` — `argv=("code", "/tmp")` → `"/tmp"` (Linux always has `/tmp`).
- `test_heuristic_returns_none_for_no_path_args` — `argv=("firefox", "--new-window")` → `None`.
- `test_heuristic_skips_flags_starting_with_dashes` — `argv=("code", "--wait", "/tmp")` → `"/tmp"`.
- `test_emits_info_updated_on_window_change` — `qtbot.waitSignal` after calling `_on_window_changed` directly.
- `test_emits_info_updated_on_ram_timer` — short timer, verify RAM update signal fires.

### `tests/test_ui_debug_panel.py` (UI)

- `test_collapsed_state_shows_summary` — send `AppInfo`, verify summary label text contains app name and RAM.
- `test_expanded_state_shows_details` — toggle to expanded, verify details section is visible and labels have content.
- `test_toggle_button_switches_collapsed_state` — initial collapsed → click button → expanded; click again → collapsed.
- `test_handles_empty_info_gracefully` — `app_info_service.current_info is None`, verify labels show `—` or `none`.
- `test_updates_labels_on_info_signal` — send two different `AppInfo` objects, verify the summary label text changed.

## Out of Scope (Explicitly)

- D-Bus introspection for specific applications (Dolphin, Gwenview, VSCode) to get authoritative "open folder" information. The argv heuristic covers the common case at zero D-Bus complexity.
- Showing CPU usage, network I/O, or disk I/O. Easy to add later as additional fields on `AppInfo`; not in this scope.
- Persisting the collapsed/expanded state across launches (QSettings). Default is always collapsed; user can add QSettings later.
- Localization. All UI text is in English.
- macOS / Windows support. The `/proc/<pid>/cmdline` read is Linux-only; on other platforms `argv` will always be `()`. RAM and the rest still work (psutil is cross-platform).
- Window title that contains a folder path (e.g., Dolphin showing `~/projects` in the title) being treated as "Opened". We do not parse window titles — only argv. This keeps the heuristic explicit and the testable.
- Showing the active Activity in the debug panel. The user asked for window + RAM + app info only; coupling the panel to `ActivityService` would add a second service dependency for a value the user can already see in the main UI.

## Edge Cases (Documented, Not Specially Handled)

- Process dies between window change and RAM refresh: `psutil.NoSuchProcess` → `ram_mb = None`, panel shows `RAM: —`.
- `/proc/<pid>/cmdline` becomes unreadable: `OSError` → `argv = ()`, panel shows `Argv: —`.
- Long window title (>100 chars): truncated in UI to 80+`…`. The full title is still in `AppInfo` for callers that want it.
- Long argv (VSCode with many flags): truncated to 200 chars in UI display.
- Window not yet detected on app start: `current_info is None`, all labels show `—` or `none`.
- Multiple TrackIt instances: each has its own `AppInfoService` and `DebugPanel`; no cross-talk.

## Risk Assessment

- **psutil dependency**: low. psutil is mature, used in thousands of projects, available on PyPI. No system deps.
- **Reading `/proc/<pid>/cmdline`**: same approach as `psutil.Process(pid).cmdline()`. We read directly to keep the implementation explicit and easy to test. psutil is used only for RAM.
- **KWin not providing `pid`**: KWin Plasma 6's `getWindowInfo` returns a properties dict that includes `pid` (alongside `resourceClass` and `caption`). Verified in the KWin scripting API. If for some reason it doesn't, the panel gracefully shows `RAM: —` and `Opened: —`.

## Future Extension Points (Not In Scope)

- Add `cpu_percent`, `num_threads`, `disk_io` to `AppInfo`. Just add fields and corresponding reader methods.
- Add a `QSettings` to remember collapsed/expanded state.
- Add a "copy" button on the debug panel that copies `AppInfo` as JSON to the clipboard (for bug reports).
- D-Bus introspection for specific apps. Could be added as a separate service that augments `AppInfo` with extra fields when the app is recognized.
