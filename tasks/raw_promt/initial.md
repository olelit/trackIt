You are a senior Linux desktop engineer building a production-quality time tracking application for KDE Plasma on Wayland (CachyOS Linux).

Your task is to generate a complete working Python application using PySide6 that tracks the user's active window in real time and assigns tracked time to user-defined "Activities".

The code must be production-like: clean architecture, maintainable, typed, and efficient. Avoid toy examples.

---

# CORE GOAL

Build a desktop application that:

1. Tracks the currently active window in KDE Plasma (Wayland)
2. Automatically assigns active window time to the currently selected Activity
3. Displays Activities in a GUI with per-app usage breakdown
4. Persists all data locally in SQLite
5. Works without any backend server

---

# TARGET ENVIRONMENT

* Linux (CachyOS)
* KDE Plasma 6
* Wayland session
* Python 3.13
* PySide6 (Qt6)
* D-Bus (KWin integration)

---

# CORE FUNCTIONALITY (MUST IMPLEMENT)

## 1. Active Window Tracking (REAL, NOT MOCK)

You MUST implement real active window tracking using KDE KWin D-Bus interface.

Requirements:

* Subscribe to active window change events via KWin D-Bus signals
* Retrieve:

  * application name
  * window title
  * process id (if available)
* Do NOT use polling unless absolutely necessary (max fallback 1s interval)

The system must react immediately to window focus changes.

---

## 2. Activity System

Users can create "Activities" (work contexts), such as:

* "Learning Node.js"
* "CRM-482 Task"
* "Work"
* "Side Project"

Only ONE Activity can be active at a time.

Each Activity stores:

* id (int)
* name (string)
* icon_path (optional)
* is_active (bool)
* total_duration_seconds (int)

---

## 3. App Usage Tracking

For each Activity track per-application usage:

Example:

Activity: "Learning Node.js"

* Firefox → 2h 10m
* Zed → 1h 05m
* Terminal → 0h 30m

Data model:

AppUsage:

* id
* activity_id
* app_name
* window_title (optional)
* duration_seconds
* last_seen_timestamp

---

## 4. TIME TRACKING LOGIC (CRITICAL)

Implement a precise time accumulation system:

* On active window change:

  * close previous time segment
  * assign duration to previous app under current Activity
  * start new segment for new window

Edge cases:

* same window remains active → no duplicate entries
* Activity switch → flush current tracking session
* system idle (optional future extension, but structure must allow it)

---

## 5. GUI REQUIREMENTS

Use PySide6 with clean, modern Qt layout.

### Layout:

LEFT PANEL:

* List of Activities
* Button: "+" create Activity
* Each Activity row shows:

  * name
  * total time
  * active indicator

Each Activity row MUST include a kebab menu button:

[⋮]

Menu contains:

* Set Active
* Rename
* Export (stub)
* Duplicate (stub)
* Delete

IMPORTANT:

* Use QMenu (not custom widgets)
* Actions can be stubbed but must exist structurally

---

RIGHT PANEL:
Shows selected Activity:

* Activity name
* Total tracked time
* List of AppUsage entries:

  * app icon placeholder
  * app name
  * duration

---

# ARCHITECTURE (MANDATORY)

You MUST structure the project cleanly:

/models
/services
/ui
/core
/storage

---

## SERVICES

### WindowTrackerService (REAL IMPLEMENTATION)

* Connects to KDE KWin via D-Bus
* Emits signal when active window changes
* Provides:

  * app_name
  * window_title
  * pid (if possible)

Must be event-driven.

---

### ActivityService

* Manages activities
* Handles switching active activity
* Aggregates usage time
* Coordinates with WindowTrackerService

---

### TimeTrackingService

* Core logic for:

  * starting session
  * stopping session
  * calculating durations
* Must be independent from UI

---

### StorageService

* SQLite persistence
* Stores:

  * activities
  * app usage
  * sessions

Must be efficient (batch writes preferred over frequent disk IO).

---

# PERFORMANCE REQUIREMENTS

* No busy polling loops
* Event-driven architecture preferred
* Minimal CPU usage when idle
* Avoid blocking UI thread
* Use signals/slots correctly
* Use background threads only when necessary

---

# CODE QUALITY REQUIREMENTS

This is NOT a prototype.

You MUST:

* Use type hints everywhere
* Use dataclasses or typed models
* Separate UI from business logic strictly
* Avoid logic inside UI classes
* Use logging module properly
* Write readable production-grade code
* Avoid overengineering but keep extensibility

---

# FUTURE EXTENSIONS (MUST PREPARE FOR)

Architecture must allow later addition of:

* OCR screenshot analysis
* Git branch detection
* AI-based task inference (LLM integration)
* YouTrack / Jira integration
* System idle detection
* Multi-monitor awareness

---

# OUTPUT REQUIREMENTS

Generate:

1. Full project structure
2. All Python source code
3. Working PySide6 GUI
4. Working KDE KWin D-Bus active window tracking
5. SQLite schema
6. Minimal runnable application

---

# IMPORTANT DESIGN RULE

This system is not just a window logger.

It is a foundation for a professional-grade activity intelligence tracker.

Build it accordingly.
