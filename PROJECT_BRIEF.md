# F1 Tracker — Handoff Brief

You are continuing development of "F1 Tracker", a PyQt6 desktop app. Do a
thorough read of the codebase before proposing or making changes, and follow
the existing conventions exactly (see Conventions). This brief supersedes
any previous plan discussions only where noted.

## Project

Location: C:\Users\HP\Downloads\Formula1 Tracker
Entry point: main.py (installs matplotlib Agg backend, runs F1App)
Stack: Python 3.13, PyQt6, matplotlib, pandas, numpy, requests, seaborn.
There is NO git repo — commit nothing.

## Current architecture

- `f1_tracker/app.py` — F1App QMainWindow; owns sidebar nav, a QStackedWidget
  of pages, and shared data helpers (get_schedule / load_schedule_async /
  load_session). Pages register via _register(key, page, label).
- `f1_tracker/config.py` — theme colors, FONT "Segoe UI", CACHE_DIR,
  JOLPICA_BASE_URL = https://api.jolpi.ca/ergast/f1, F1_SEASON_RANGE (1950, now).
- `f1_tracker/ui/workers.py` — Worker class: run(fn, on_done, on_error,
  progress). ALWAYS run blocking network/parse work through it; callbacks
  fire on the GUI thread and exceptions are swallowed safely. Never block the
  GUI thread directly.
- `f1_tracker/ui/widgets.py` — F1Table (sortable, numeric), make_card,
  make_chip, make_title, make_stat_card, time_formatted, etc.
- `f1_tracker/ui/plot_viewer.py` — PlotViewer(figure, title, parent) window.
- `f1_tracker/ui/pages/base.py` — BasePage (gives self.controller, self.worker,
  show_error).
- `f1_tracker/visualizations/plots.py` — lazy-imported plotting stack, built
  on worker threads. Figures use the pure Figure API (no pyplot) for thread
  safety; matplotlib is pinned to Agg backend in main.py.
- `f1_tracker/visualizations/progress_map.py` — ProgressMap (minimap animation)
  + build_progress(session). Currently tightly coupled to fastf1.
- `f1_tracker/services/` — sessions.py (fastf1 loader), schedule.py (Jolpica
  calendar + all-time champions cache), standings.py (Jolpica standings).
- `cache/` — local disk cache dir (was fastf1's).

## CONFIRMED PRODUCT DECISIONS (build exactly these)

1. SIDEBAR becomes 4 items, in order: Home, Race Sessions, Standings,
   Season Calendar. Remove the Lap Progression and World Champions menu items
   (and their pages' registration/chrome).
2. Race Sessions page keeps its session picker + event card, and its tabs
   become: Race Results | Qualifying Results | Lap Progression. The Lap
   Progression feature moves here as the third tab and REUSES the already
   loaded race session — one "Load Session" drives results, plots, and the
   minimap. Delete the separate Lap Progression page and its own loader.
3. Standings page is rebuilt as a year-selectable Championship view:
   - A year selector (QSpinBox) at the top, defaulting to the CURRENT season.
   - Loading any year fetches BOTH drivers' and constructors' championship
     tables for that year (Jolpica).
   - Add a third tab: "Progression" — a race-by-race championship chart built
     by fetching Jolpica driverstandings/constructorstandings per round
     (rounds 1..N) and plotting cumulative points per driver/team per round.
   - Keep the existing search/filter behavior on the tables.
   - Historical champion browsing (the old World Champions page) is covered by
     selecting older years here — e.g. the top row + a leader line can read
     "X — YYYY World Champion (Team)".
4. Delete f1_tracker/ui/pages/champions.py and its integration. Remove the
   Home page "World Champions" quick button and the fetch_champions
   machinery in services/schedule.py.

## DATA SOURCE STRATEGY (authoritative)

- JOLPICA (https://api.jolpi.ca/ergast/f1) is the source for ALL standings,
  calendar, and championship/history data — every year back to 1950 including
  the current season. Driver standings accept a round filter:
    GET /ergast/f1/{year}/driverstandings
    GET /ergast/f1/{year}/{round}/driverstandings   (standings as of round N)
    GET /ergast/f1/{year}/{round}/constructorstandings
  Jolpica requires a custom User-Agent and has rate limits; batch/paginate and
  disk-cache per (year) and per (year, round) like the existing
  _load_champions_cache pattern, and pace requests.
- OPENF1 (https://api.openf1.org/v1/) is the replacement for fastf1 for
  session-level data only: session_result, starting_grid, laps, location,
  position, intervals, stints, car_data, drivers, sessions, meetings.
  Historical (2023+) is free, no auth; free tier is 3 req/s and 30 req/min —
  throttle and disk-cache. Fields confirmed from the docs:
  session_result → dnf/dns/dsq flags, driver_number, duration, gap_to_leader,
  number_of_laps, position. starting_grid → position, driver_number,
  lap_duration. drivers → full_name, name_acronym, driver_number, team_name,
  team_colour (hex, NO '#'), headshot_url. laps → lap_number, lap_duration,
  duration_sector_1/2/3, is_pit_out_lap, i1_speed/i2_speed/st_speed,
  date_start. location → date, driver_number, x, y, z. position → date,
  driver_number, position. intervals → date, driver_number, gap_to_leader,
  interval (gap to car ahead; null/lapped strings may appear). stints →
  compound, driver_number, lap_start, lap_end, stint_number. car_data → date,
  driver_number, rpm, n_gear, speed, throttle, brake, drs.
- REMOVE fastf1 entirely: services/sessions.py, the fastf1 lazy imports in
  plots.py, fastf1.plotting usages (rewrite color/style helpers locally with
  team colours), requirements.txt fastf1 line, and the fastf1 cache usage.
  Build services/openf1.py (thin client + JSON disk cache + throttle) and a
  small session-key resolver (find race + qualifying session keys for a given
  year + GP name via /sessions, ordered by /meetings dates).

## BUILD ORDER (do not skip ahead)

A. Sidebar/nav cleanup + delete champions page + home button + schedule.py
   champions code.
B. Standings page: year selector (current season default) + WDC/WCC tables
   via Jolpica.
C. Standings "Progression" tab: Jolpica per-round fetch (paced/cached,
   progress signal) + cumulative points chart (matplotlib Figure, following
   plots.py conventions).
D. Fold Lap Progression into Race Sessions as the third tab, reusing the
   loaded session via the OpenF1 data layer (progress_map.py rewritten to
   consume OpenF1 data: location for x/y, position for order/time, intervals
   for gaps, drivers for team colours/names).
E. Rewrite the remaining plot functions in plots.py off fastf1 onto OpenF1/
   plain pandas (position changes from /position, tire strategies from
   /stints, lap times from /laps, team pace from /laps).
F. requirements.txt update + app smoke test + verify every page still loads.

## Conventions (already established — preserve them)

- PyQt6, object names drive the theme (e.g. "primary", "ghost", "pageTitle",
  "muted", "heroInfo", "navButton", "brandTitle", "pageSubtitle").
- Never call _ensure()/heavy imports on startup; lazy-import inside worker
  functions only. matplotlib.use("Agg", force=True) must stay in main.py.
- All network calls run through Worker; refresh-on-show pages (on_show) exist
  for home/champions today — mirror patterns from standings.py/calendar.py.
- When swapping a page's dynamic content, remove old widgets with setParent(None)
  + deleteLater (see _update_event_card in race_sessions.py) to avoid overlap.
- Do NOT add comments beyond what matches existing style; match file style;
  no emojis. Do not create new dependencies; drop fastf1, keep the rest.
- Do not change the Home page beyond the champions-button removal unless a
  decision below or a bug forces it.

When finished, run: python -m py_compile on every file, then launch the app
and manually exercise all four sidebar pages + the new tabs. Report any bug,
pace/rate-limit concern, or schema mismatch you hit with the exact fix you
applied.