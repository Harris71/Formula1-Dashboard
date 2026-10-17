from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import numpy as np

from f1_tracker.config import BG_PANEL, TEXT, TEXT_MUTED
from f1_tracker.visualizations.plots import _ensure, _track_geometry, draw_track, rotate_coordinates

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# Seconds of race time skipped per animation frame.
FRAME_STEP = 0.5


def _seconds(values):
    """Convert a timedelta-aware column to a float ndarray of seconds."""
    return values.astype("timedelta64[ns]").astype(np.float64) / 1e9


class DriverData:
    """Preprocessed position timeline for one driver."""

    __slots__ = (
        "number", "code", "team", "color", "is_leader",
        "t", "x", "y", "lap_starts",
    )

    def __init__(self, number: str, code: str, team: str, color: str, is_leader: bool = False) -> None:
        self.number = number
        self.code = code
        self.team = team
        self.color = color
        self.is_leader = is_leader
        self.t: Optional[np.ndarray] = None
        self.x: Optional[np.ndarray] = None
        self.y: Optional[np.ndarray] = None
        self.lap_starts: Optional[np.ndarray] = None


class ProgressMap:
    """Race telemetry preprocessed for smooth minimap-style playback.

    Build on a worker thread (heavy network + parse), then animate on the GUI
    thread via :meth:`render` which only touches the matplotlib figure.
    """

    def __init__(self, session, drivers: list[DriverData]) -> None:
        self.session = session
        self.drivers = drivers
        # Position samples include the pre-race phase (formation lap, ~1h).
        # Start playback when the first car actually moves so the timeline
        # begins at the race start rather than minutes of empty track.
        self.start = min(float(driver.t[0]) for driver in drivers if len(driver.t))
        self.end = max(float(driver.t[-1]) for driver in drivers if len(driver.t))
        self.frames = np.arange(self.start, self.end + FRAME_STEP, FRAME_STEP)
        self.total_laps = 0
        for driver in drivers:
            if driver.is_leader and driver.lap_starts is not None and len(driver.lap_starts):
                self.total_laps = int(len(driver.lap_starts))
        self._figure = None
        self._scatter = None
        self._labels: list = []
        self._lap_text = None
        self._time_text = None
        self.last_lap: Optional[int] = None
        self.standings: list = []

        # Track arc-length table — used to rank drivers live by comparing how
        # far along the circuit they are (computed once for the whole session).
        self._track, _ci, _angle = _track_geometry(session)
        segments = np.linalg.norm(np.diff(self._track, axis=0), axis=1)
        self._arc = np.concatenate(([0.0], np.cumsum(segments)))
        self._track_len = float(self._arc[-1]) or 1.0

    # ------------------------------------------------------------ figure
    def build_figure(self) -> "Figure":
        """Create the circuit figure with a live driver-dot scatter."""
        _ensure()
        from matplotlib.figure import Figure

        self._labels = []  # idempotent: repeated builds replace the figure

        fig = Figure(figsize=(8.6, 6.4), facecolor=BG_PANEL)
        ax = fig.add_subplot(111)
        ax.set_facecolor(BG_PANEL)
        for spine in ax.spines.values():
            spine.set_visible(False)
        draw_track(ax, self.session)

        colors = [driver.color for driver in self.drivers]
        sizes = np.array([210 if driver.is_leader else 95 for driver in self.drivers], dtype=np.float64)
        count = len(self.drivers)
        blank = np.full(count, np.nan)
        self._scatter = ax.scatter(
            blank, blank, s=sizes, c=colors, zorder=6,
            edgecolors="white", linewidths=0.8, alpha=1.0,
        )

        from matplotlib.colors import to_rgba_array

        self._rgba = to_rgba_array(colors)

        # Driver numbers drawn on top of their dots.
        for driver in self.drivers:
            size = 10 if driver.is_leader else 7.5
            label = ax.text(
                -1e6, -1e6, driver.number, color="white",
                fontsize=size, fontweight="bold", ha="center", va="center", zorder=7,
            )
            self._labels.append(label)

        self._lap_text = ax.text(
            0.02, 0.96, "", transform=ax.transAxes, color=TEXT,
            fontsize=13, fontweight="bold", va="top",
        )
        self._time_text = ax.text(
            0.98, 0.96, "", transform=ax.transAxes, color=TEXT_MUTED,
            fontsize=10, ha="right", va="top",
        )

        ax.set_xticks([])
        ax.set_yticks([])
        # Keep the whole circuit (incl. corner labels) inside the canvas at any
        # widget size: equal aspect grows the data limits rather than the box,
        # and the margin leaves room for the lap/clock overlays and labels.
        ax.set_aspect("equal", adjustable="datalim")
        ax.margins(x=0.06, y=0.12)
        fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        self._figure = fig
        return fig

    # ------------------------------------------------------------ animate
    def render(self, frame: int) -> None:
        """Move the dots to their interpolated positions for a frame index."""
        if self._scatter is None:
            return
        t = float(self.frames[max(0, min(frame, len(self.frames) - 1))])

        count = len(self.drivers)
        offsets = np.full((count, 2), np.nan)
        facecolors = self._rgba.copy()
        lapnum = np.full(count, -1, dtype=int)
        xs = np.full(count, np.nan)
        ys = np.full(count, np.nan)
        leader_lap: Optional[int] = None

        for i, driver in enumerate(self.drivers):
            point = self._driver_at(driver, t)
            if point is None:
                facecolors[i, 3] = 0.0  # not on track yet — invisible
                continue
            x, y, lap, alpha = point
            offsets[i, 0] = x
            offsets[i, 1] = y
            facecolors[i, 3] = alpha
            xs[i] = x
            ys[i] = y
            lapnum[i] = lap
            if driver.is_leader:
                leader_lap = lap

        self._scatter.set_offsets(offsets)
        self._scatter.set_facecolors(facecolors)

        # Driver-number labels follow their dots (translate rather than jump).
        for i, label in enumerate(self._labels):
            if not np.isnan(xs[i]):
                label.set_position((float(xs[i]), float(ys[i])))
                label.set_visible(True)
            else:
                label.set_visible(False)

        self.standings = self._build_standings(xs, ys, lapnum, t)
        self.last_lap = leader_lap

        if self._lap_text is not None:
            if leader_lap is None:
                text = "Lap 0"
            else:
                text = f"Lap {leader_lap}/{self.total_laps}"
            self._lap_text.set_text(text)

        if self._time_text is not None:
            self._time_text.set_text(_format_race_time(t - self.start))

    def _nearest_track(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Index of the closest track point for each live driver position."""
        dx = self._track[:, 0][:, None] - xs[None, :]
        dy = self._track[:, 1][:, None] - ys[None, :]
        distances = dx * dx + dy * dy
        return np.argmin(distances, axis=0)

    def _build_standings(
        self, xs: np.ndarray, ys: np.ndarray, lapnum: np.ndarray, t: float
    ) -> list:
        """Current ranking based on laps completed + distance along the circuit.

        Entries carry ``gap`` (seconds, or lapped) to the driver directly
        ahead, computed from each driver's own recent lap pace.
        """
        visible = ~np.isnan(xs)
        progress = np.full(len(self.drivers), -1.0)
        if np.any(visible):
            indices = visible.nonzero()[0]
            track_idx = self._nearest_track(xs[visible], ys[visible])
            fractions = np.clip(self._arc[track_idx] / self._track_len, 0.0, 0.99)
            progress[indices] = lapnum[indices].astype(float) + fractions

        order = np.argsort(-progress)
        rows: list = []  # (code, color, finished, leader, lap, distance_m, pace_s)
        for rank in order:
            driver = self.drivers[rank]
            if progress[rank] < 0:
                continue  # hasn't started yet
            finished = bool(int(lapnum[rank]) >= self.total_laps)
            # lapnum is the lap in progress (1-based); anchor distance to the
            # laps already completed so a car a lap down comes out a lap back.
            completed = max(0.0, progress[rank] - 1.0)
            distance_m = completed * self._track_len
            pace_s = self._recent_pace(driver, t)
            rows.append(
                (
                    driver.code, driver.color, finished, driver.is_leader,
                    int(lapnum[rank]), float(distance_m), pace_s,
                )
            )

        standings: list = []
        for i, row in enumerate(rows):
            code, color, finished, leader, lap, distance_m, pace_s = row
            if i == 0:
                gap = "—"  # race leader — no driver ahead
            elif pace_s is not None and pace_s > 0:
                gap_m = rows[i - 1][5] - distance_m
                if gap_m >= self._track_len:
                    laps = int(gap_m // self._track_len)
                    gap = f"+{laps} LAP" if laps == 1 else f"+{laps} LAPS"
                else:
                    gap = f"{gap_m * pace_s / self._track_len:+.1f}s"
            else:
                gap = ""
            standings.append((code, color, finished, leader, lap, gap))
        return standings

    @staticmethod
    def _recent_pace(driver: DriverData, t: float) -> Optional[float]:
        """Seconds per lap for the driver's most recent lap (pace for gap math)."""
        starts = driver.lap_starts
        if starts is None or not len(starts):
            return None
        li = int(np.searchsorted(starts, t, side="right"))  # completed laps
        if li >= 1:
            return max(1.0, t - float(starts[li - 1]))
        return max(1.0, t - float(driver.t[0]) + 1.0)

    @staticmethod
    def _driver_at(driver: DriverData, t: float):
        """Interpolated (x, y, lap, alpha) for one driver at race time t."""
        times = driver.t
        if times is None or len(times) < 2:
            return None
        if t < float(times[0]):
            return None  # not on track yet
        if t >= float(times[-1]):
            return (
                float(driver.x[-1]), float(driver.y[-1]),
                int(np.searchsorted(driver.lap_starts, t, side="right")),
                0.35,  # finished or retired — freeze, dimmed
            )

        i = int(np.searchsorted(times, t, side="right")) - 1
        i = max(i, 0)
        t0, t1 = float(times[i]), float(times[i + 1])
        fraction = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
        x = float(driver.x[i]) + fraction * (float(driver.x[i + 1]) - float(driver.x[i]))
        y = float(driver.y[i]) + fraction * (float(driver.y[i + 1]) - float(driver.y[i]))
        lap = int(np.searchsorted(driver.lap_starts, t, side="right"))
        return x, y, lap, 1.0


def _format_race_time(seconds: float) -> str:
    seconds = int(seconds)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes:02}m"
    return f"{minutes:02}:{secs:02}"


def build_progress(session) -> ProgressMap:
    """Load each driver's position timeline and build the playback model."""
    import fastf1.plotting  # noqa: F401  (registers team colour helpers)

    results = session.results
    try:
        position_col = results["Position"].astype(float)
        leader_number = str(results.loc[position_col == 1.0, "DriverNumber"].iloc[0])
    except Exception:
        leader_number = str(session.drivers[0])

    drivers: list[DriverData] = []
    for number in session.drivers:
        laps = session.laps.pick_drivers(number)
        if laps.empty:
            continue
        code = laps["Driver"].iloc[0]
        team = laps["Team"].iloc[0]
        color = "#4FC3F7"
        try:
            color = fastf1.plotting.get_team_color(team, session=session)
        except Exception:
            pass
        is_leader = number == leader_number

        pos = laps.get_pos_data()
        if pos.empty:
            continue

        track_angle = session.get_circuit_info().rotation / 180 * np.pi
        xy = np.column_stack((pos["X"].to_numpy(), pos["Y"].to_numpy()))
        xy = rotate_coordinates(xy, angle=track_angle)

        data = DriverData(number, code, team, color, is_leader)
        data.t = _seconds(pos["SessionTime"].to_numpy())
        data.x = xy[:, 0]
        data.y = xy[:, 1]
        starts = _seconds(laps["LapStartTime"].to_numpy())
        data.lap_starts = starts[np.isfinite(starts)]
        drivers.append(data)

    return ProgressMap(session, drivers)