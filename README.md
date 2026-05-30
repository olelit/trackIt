# TrackIt

Desktop time tracker for KDE Plasma 6 on Wayland. Tracks active windows via KWin D-Bus, assigns tracked time to user-defined Activities, persists to SQLite.

## Requirements

- Linux with KDE Plasma 6 (Wayland session)
- Python 3.13+
- D-Bus session bus (for KWin integration)

## Quick Start

```bash
# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate
pip install -e .

# Run the app
python __main__.py
```

Or with the venv directly:

```bash
.venv/bin/pip install -e .
.venv/bin/python __main__.py
```

## Development

```bash
# Install dev dependencies
.venv/bin/pip install -e ".[dev]"

# Run tests
.venv/bin/python -m pytest tests/ -v

# Lint
.venv/bin/ruff check .

# Typecheck
MYPYPATH=. .venv/bin/mypy
```

## Architecture

```
/models        # Data models (Activity, WindowInfo, AppUsage)
/services      # Business logic (WindowTracker, ActivityService, TimeTrackingService, StorageService)
/ui            # PySide6 widgets (MainWindow, ActivityList, ActivityDetail)
/core          # App bootstrap and signal wiring
/storage       # SQLite schema, repository layer
```

**Event-driven flow:** KWin D-Bus signals → `WindowTrackerService` emits `window_changed` → `TimeTrackingService` accumulates durations per Activity.

## Window Tracking

Uses `org.kde.KWin` D-Bus interface to subscribe to active window changes. Falls back to 1s polling if D-Bus signals are unavailable (emits warning).

## Data Storage

SQLite database at `~/.local/share/trackit/trackit.db`. Schema managed in `storage/schema.py`. Two tables: `activity` and `app_usage` with foreign key cascade.
