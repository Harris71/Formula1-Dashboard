# 🏎️ F1 Tracker

**A desktop Formula 1 companion: race countdown, championship standings back to 1950, telemetry-driven race analysis, and a lap-by-lap race replay.**

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?logo=qt&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Plots-Matplotlib-11557c)
![FastF1](https://img.shields.io/badge/Telemetry-FastF1-E10600)

<p align="center">
  <img src="https://github.com/user-attachments/assets/9ad83e4d-fd66-439b-bdd5-776ad8ed3f5f" width="48%" alt="Race Control" />
  <img src="https://github.com/user-attachments/assets/a83389ad-1dc4-41b8-bf66-aecd701dfb96" width="48%" alt="Race Sessions" />
</p>



https://github.com/user-attachments/assets/eafb7523-9ccb-4095-a16d-0a96a8490844



## Contents

- [Features](#features)
- [Getting started](#getting-started)
- [Keyboard shortcuts](#keyboard-shortcuts)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Data sources](#data-sources)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits)

## Features

### 🏁 Race Control (Home)
- Live countdown to lights out for the next race
- Weekend timetable shown in **your local time zone**
- Championship leaders, season progress, top-five drivers and constructors
- Podium from the most recent race

### 📊 Race Sessions
- **Load Session**: race and qualifying classification, instantly, with team colours, podium badges, positions gained or lost, and status pills
- **Sprint Results** tab on sprint weekends, in the same format as the race classification
- **Load Telemetry** (2018 onwards): analysis charts powered by FastF1
  - Position changes
  - Tyre strategies
  - Team pace comparison
  - Lap-time distributions
  - Circuit map
- **Lap Progression**: replays the race on the circuit map with a running leaderboard, adjustable speed and a scrubber

### 🏆 Standings
- Drivers' and Constructors' tables for **any season since 1950**
- Gap to the leader and a race-by-race progression table
- Cumulative points chart across the season

### 📅 Season Calendar
- Every round with its status and session times in local time
- One-click jump to a past race's results
- **Export to `.ics`** for Google Calendar, Outlook and Apple Calendar

### 📴 Works offline
Jolpica responses are cached on disk. Finished seasons are kept permanently, the season in progress refreshes every 30 minutes, and the last cached copy is used whenever the network is unavailable.

## Getting started

**Requirements:** Python 3.11 or newer.

```bash
git clone https://github.com/Harris71/Formula1-Dashboard
cd Formula1-Dashboard

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

The first time you load a telemetry session, FastF1 downloads its data into a local `cache/` folder, so that load is slower than later ones.

## Keyboard shortcuts

| Shortcut     | Action                                                             |
| ------------ | ------------------------------------------------------------------ |
| `Ctrl+1`–`4` | Switch page                                                        |
| `F5`         | Refresh current page                                               |
| `Alt+Left`   | Back to the previous page or tab (also the mouse's back button)    |

## How it works

- **Two data layers.** Jolpica supplies lightweight data (calendar, standings, results) so pages open fast. FastF1 supplies heavy session telemetry, which only loads when you press **Load Telemetry**.
- **Never blocks the UI.** All network and parsing work runs on background workers (`QThreadPool`), and results are delivered back on the GUI thread.
- **Thread-safe plotting.** Charts use Matplotlib's `Figure` API directly rather than `pyplot`, with the Agg backend, so they can be built off the main thread.
- **Clean shutdown.** On exit the app drains the thread pool and pending callbacks before closing, which avoids Qt aborts from half-finished workers.

## Project structure

```
.
├── main.py                  # Entry point
├── requirements.txt
├── assets/
│   ├── fonts/               # Titillium Web (SIL OFL)
│   └── icons/
└── f1_tracker/
    ├── app.py               # Main window, sidebar navigation, shared data helpers
    ├── config.py            # Theme colours, API URLs, cache location
    ├── teams.py             # Team colours and naming
    ├── services/            # Data access
    │   ├── http.py          #   HTTP client with caching
    │   ├── schedule.py      #   Calendar
    │   ├── standings.py     #   Championship standings
    │   ├── results.py       #   Race and qualifying results
    │   └── sessions.py      #   FastF1 session loading
    ├── ui/
    │   ├── pages/           # Home, Race Sessions, Standings, Calendar
    │   ├── replay.py        # Lap progression panel
    │   ├── widgets.py       # Tables, cards, chips
    │   ├── workers.py       # Background worker helper
    │   ├── plot_viewer.py   # Chart window
    │   └── theme.py         # Application styling
    └── visualizations/
        ├── plots.py         # Analysis charts
        └── progress_map.py  # Circuit map animation
```

## Data sources

- [**Jolpica-F1**](https://github.com/jolpica/jolpica-f1): Ergast-compatible API for calendars, standings and results.
- [**FastF1**](https://github.com/theOehrly/Fast-F1): session timing and telemetry.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Telemetry won't load | Telemetry is available from 2018 onwards, and FastF1 needs network access the first time a session loads. |
| Data looks stale | Press `F5` to refresh. The current season is cached for 30 minutes. |
| Qt platform plugin error on Linux | Install your distro's Qt/XCB libraries (for example `libxcb-cursor0` on Debian/Ubuntu). |

## Credits

The UI font is [Titillium Web](https://fonts.google.com/specimen/Titillium+Web), licensed under the SIL Open Font License (`assets/fonts/OFL.txt`).

F1 Tracker is an unofficial fan project and is not associated with any Formula 1 companies. F1, FORMULA ONE and related marks are trademarks of Formula One Licensing B.V.
