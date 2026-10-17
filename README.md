# F1 Tracker

A desktop Formula 1 companion built with PyQt6: live countdown to the next
race, championship standings for every season since 1950, race results with
telemetry analysis, a lap-by-lap race replay and the full season calendar in
your own time zone.

## Features

- **Race Control (Home)**: a live countdown to lights out, the weekend
  timetable in your local time, the championship leaders, season progress,
  the top-five drivers and constructors, and the podium from the last race.
- **Race Sessions**: **Load Session** shows race and qualifying
  classification instantly from Jolpica, with team colours, podium badges,
  positions gained or lost, and status pills. **Load Telemetry** (2018 onwards)
  then fetches FastF1 data for the analysis charts (positions, tyre strategy,
  team pace, lap-time distributions, circuit map) and the **Lap Progression**
  tab, which replays the race on the circuit map with a running leaderboard,
  adjustable speed and a scrubber.
- **Standings**: Drivers' and Constructors' tables for any season, with the
  gap to the leader, a race-by-race progression table and a cumulative
  points chart.
- **Season Calendar**: every round with its status, weekend session times in
  local time, one-click access to a past race's results, and **export to
  `.ics`** for Google Calendar, Outlook and Apple Calendar.
- **Works offline**: Jolpica responses are cached on disk. Finished seasons
  are kept for good. Data for the season in progress refreshes every 30
  minutes, and the last copy is used when the network is unavailable.

## Keyboard shortcuts

| Shortcut       | Action                 |
| -------------- | ---------------------- |
| `Ctrl+1`–`4`   | Switch page            |
| `F5`           | Refresh current page   |
| `Alt+Left`     | Back to the previous page or tab (also the mouse's back button) |

## Running

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Python 3.11+ is recommended.

## Data sources

- [Jolpica-F1](https://github.com/jolpica/jolpica-f1) (Ergast-compatible API)
  for calendars, standings and results.
- [FastF1](https://github.com/theOehrly/Fast-F1) for session timing and
  telemetry. The first time a session loads, its data is downloaded to
  `cache/`.

## Credits

The UI font is [Titillium Web](https://fonts.google.com/specimen/Titillium+Web),
licensed under the SIL Open Font License (`assets/fonts/OFL.txt`). F1 Tracker
is an unofficial fan project and is not associated with Formula 1 companies.
F1, FORMULA ONE and related marks are trademarks of Formula One Licensing B.V.
