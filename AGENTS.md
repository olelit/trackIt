# TrackIt — Agent Instructions

## Overview
PySide6 desktop time tracker for KDE Plasma 6 on Wayland. Tracks active windows via KWin D-Bus, assigns tracked time to user-defined "Activities", persists to SQLite.

## Target Environment
- **OS**: CachyOS Linux, KDE Plasma 6, **Wayland only** (no X11, no xdotool)
- **Python**: 3.13
- **UI**: PySide6 (Qt6)
- **IPC**: D-Bus (KWin integration)
- **DB**: SQLite (local only, no server)

## Mandatory Project Structure
Flat packages at repo root (no `src/` nesting):
```
/models        # dataclasses / typed models (Activity, AppUsage, Session)
/services      # business logic (WindowTracker, ActivityService, TimeTrackingService, StorageService)
/ui            # PySide6 widgets, windows, dialogs
/core          # app bootstrap, signal wiring, config
/storage       # SQLite schema, migrations, DAO layer
```

## Critical Constraints (DO NOT VIOLATE)

### Window Tracking
- **Real KWin D-Bus only** — subscribe to `org.kde.KWin` active window change **signals** (not polling)
- No xdotool, no wlr-foreign-toplevel, no X11 tools
- Fallback polling at 1s max only if D-Bus signals unavailable (must emit warning)

### Architecture
- **Event-driven**: KWin D-Bus signals feed `WindowTrackerService` → emits Qt signals → `TimeTrackingService` reacts
- **No logic in UI classes**: widgets only render data and emit user intents; all state lives in services
- **Strict UI/business separation**: services never import from `ui`

### Code Quality
- Type hints on **all** functions/methods (Python 3.13+ syntax)
- Use `dataclasses` or `NamedTuple` for models
- Use `logging` module (no `print`)
- No busy-loops, no blocking the UI thread
- Signals/slots for cross-service communication (QThread only when absolutely needed)

## Data Model at a Glance
| Table      | Key fields |
|------------|-----------|
| Activity   | id, name, icon_path?, is_active, total_duration_seconds |
| AppUsage   | id, activity_id, app_name, window_title?, duration_seconds, last_seen_ts |
| Session    | id, activity_id, start_ts, end_ts |

- Only **one** Activity active at a time
- On window change: close previous segment → assign duration to previous app under current Activity → start new segment
- On Activity switch: flush all open tracking segments

## Commands (to be created)
```bash
python -m trackit              # launch GUI
python -m pytest               # run all tests
ruff check .                   # lint
mypy .                         # typecheck
```

## What NOT to Do
- Do **not** import PySide6 outside `/ui` or `/core` (app bootstrap)
- Do **not** mock `WindowTrackerService` for the final app — dev testing stubs allowed but real D-Bus is the target
- Do **not** add a backend server or REST API (fully local app)
- Do **not** poll for window changes unless D-Bus signals genuinely unavailable

## Future Extensions (Design Must Allow)
Architecture should not block later additions: OCR screenshot analysis, git branch detection, LLM-based task inference, YouTrack/Jira integration, system idle detection, multi-monitor awareness. Keep services pluggable.

## Source of Truth
Full spec: `tasks/raw_promt/initial.md`
