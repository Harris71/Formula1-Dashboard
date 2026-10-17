from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from f1_tracker.config import (
    BG_INPUT,
    BG_PANEL,
    BG_PANEL_2,
    BORDER,
    TEXT,
    TEXT_MUTED,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure

# Heavy plotting dependencies (matplotlib / seaborn / fastf1) are imported
# lazily so that opening the app stays fast and they never touch the critical
# startup import path.

_IMPORTED = False
_IMPORT_LOCK = threading.Lock()


def _ensure() -> None:
    """Import the heavy plotting stack on first use (inside a worker thread)."""
    global _IMPORTED, _IMPORT_LOCK
    if _IMPORTED:
        return
    with _IMPORT_LOCK:
        if _IMPORTED:
            return

        import matplotlib

        # Figures are built on worker threads and rendered by FigureCanvasQTAgg
        # (which uses the Agg renderer). Pin the non-GUI backend so seaborn /
        # pyplot never try to touch a Qt GUI from a background thread.
        matplotlib.use("Agg", force=True)
        import seaborn as sns  # noqa: F401  (registers useful style helpers)
        import fastf1.plotting

        fastf1.plotting.setup_mpl()
        matplotlib.rcParams.update({
            "figure.facecolor": BG_PANEL,
            "axes.facecolor": BG_PANEL_2,
            "axes.edgecolor": BORDER,
            "axes.labelcolor": TEXT,
            "axes.titlecolor": TEXT,
            "xtick.color": TEXT_MUTED,
            "ytick.color": TEXT_MUTED,
            "text.color": TEXT,
            "grid.color": BORDER,
            "grid.alpha": 0.35,
            "legend.facecolor": BG_PANEL,
            "legend.edgecolor": BORDER,
            "savefig.facecolor": BG_PANEL,
        })
        del matplotlib  # keep import surface minimal
        _IMPORTED = True


def _new_axes(figsize: tuple[float, float]):
    from matplotlib.figure import Figure

    fig = Figure(figsize=figsize, facecolor=BG_PANEL)
    ax = fig.add_subplot(111)
    ax.set_facecolor(BG_PANEL_2)
    for spine in ax.spines.values():
        spine.set_color(BORDER)
    ax.tick_params(colors=TEXT_MUTED, labelsize=9)
    return fig, ax


def require_session(session, session_name: str = "session") -> None:
    if session is None:
        raise ValueError(f"No {session_name} loaded yet.")


def rotate_coordinates(xy, *, angle: float) -> np.ndarray:
    rotation_matrix = np.array([
        [np.cos(angle), np.sin(angle)],
        [-np.sin(angle), np.cos(angle)],
    ])
    return np.matmul(xy, rotation_matrix)


def _track_geometry(session):
    """Track line + corner markers for a session's circuit (shared by plots)."""
    lap = session.laps.pick_fastest()
    position_data = lap.get_pos_data()
    circuit_info = session.get_circuit_info()

    track = position_data.loc[:, ("X", "Y")].to_numpy()
    track_angle = circuit_info.rotation / 180 * np.pi
    rotated_track = rotate_coordinates(track, angle=track_angle)
    return rotated_track, circuit_info, track_angle


def draw_track(ax, session) -> None:
    """Paint the rotated circuit track and its corner labels on an axes."""
    rotated_track, circuit_info, track_angle = _track_geometry(session)

    ax.plot(rotated_track[:, 0], rotated_track[:, 1], color="#F2F5F7", linewidth=2.1)

    offset_vector = [500, 0]
    for _, corner in circuit_info.corners.iterrows():
        label = f"{corner['Number']}{corner['Letter']}"
        offset_angle = corner["Angle"] / 180 * np.pi
        offset_x, offset_y = rotate_coordinates(offset_vector, angle=offset_angle)

        text_x, text_y = rotate_coordinates([corner["X"] + offset_x, corner["Y"] + offset_y], angle=track_angle)
        track_x, track_y = rotate_coordinates([corner["X"], corner["Y"]], angle=track_angle)

        ax.scatter(text_x, text_y, color=BG_PANEL_2, s=160, edgecolors=TEXT_MUTED, linewidths=0.8)
        ax.plot([track_x, text_x], [track_y, text_y], color=TEXT_MUTED, linewidth=0.9, alpha=0.8)
        ax.text(text_x, text_y, label, va="center", ha="center", size="small", color=TEXT)


# ---------------------------------------------------------------------------
# Plots (each returns a matplotlib Figure for embedding)
# ---------------------------------------------------------------------------
def plot_circuit(session) -> Figure:
    _ensure()
    require_session(session, "qualifying session")

    fig, ax = _new_axes((8.2, 6.2))
    fig.patch.set_facecolor(BG_INPUT)
    ax.set_facecolor(BG_INPUT)
    draw_track(ax, session)

    ax.set_title(
        f"{session.event['EventName']} · Circuit Map",
        color=TEXT,
        fontsize=12,
        fontweight="bold",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    ax.axis("equal")
    fig.tight_layout()
    return fig


def plot_position_changes(session) -> Figure:
    _ensure()
    require_session(session, "race session")
    import fastf1.plotting

    fastf1.plotting.setup_mpl(mpl_timedelta_support=True, color_scheme="fastf1")
    fig, ax = _new_axes((9.2, 5.2))

    result_index = "Driver" if "Driver" in session.results.columns else "Abbreviation"
    grid_positions = session.results.set_index(result_index)["GridPosition"]

    def _grid_position(abbreviation: str) -> int | None:
        if abbreviation not in grid_positions:
            return None
        value = grid_positions[abbreviation]
        try:
            if pd.isna(value) or not np.isfinite(float(value)):
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    for driver_number in session.drivers:
        driver_laps = session.laps.pick_drivers(driver_number)
        if driver_laps.empty:
            continue

        abbreviation = driver_laps["Driver"].iloc[0]
        style = fastf1.plotting.get_driver_style(
            identifier=abbreviation,
            style=["color", "linestyle"],
            session=session,
        )
        grid = _grid_position(abbreviation)
        if grid is not None:
            lap_zero = pd.DataFrame({"LapNumber": [0], "Position": [grid]})
            driver_laps = pd.concat([lap_zero, driver_laps], ignore_index=True)

        ax.plot(driver_laps["LapNumber"], driver_laps["Position"], label=abbreviation, **style)

    ax.set_ylim([20.5, 0.5])
    ax.set_yticks([1, 5, 10, 15, 20])
    ax.invert_yaxis()
    ax.set_xlabel("Lap")
    ax.set_ylabel("Position")
    ax.set_title("Position Changes Throughout The Race", fontsize=12, fontweight="bold")
    ax.grid(True, alpha=0.3)
    ax.legend(bbox_to_anchor=(1.0, 1.02), ncol=2, fontsize=8, frameon=False)
    fig.tight_layout()
    return fig


def plot_tire_strategies(session) -> Figure:
    _ensure()
    require_session(session, "race session")
    import fastf1.plotting

    fastf1.plotting.setup_mpl(mpl_timedelta_support=False, color_scheme="fastf1")
    driver_codes = [session.get_driver(driver)["Abbreviation"] for driver in session.drivers]
    stints = session.laps[["Driver", "Stint", "Compound", "LapNumber"]]
    stints = stints.groupby(["Driver", "Stint", "Compound"]).count().reset_index()
    stints = stints.rename(columns={"LapNumber": "StintLength"})

    fig, ax = _new_axes((6.2, 9.5))

    for driver in driver_codes:
        driver_stints = stints.loc[stints["Driver"] == driver]
        previous_stint_end = 0
        for _, row in driver_stints.iterrows():
            compound_color = fastf1.plotting.get_compound_color(row["Compound"], session=session)
            ax.barh(
                y=driver,
                width=row["StintLength"],
                left=previous_stint_end,
                color=compound_color,
                edgecolor="#0E1116",
                linewidth=1.4,
                fill=True,
            )
            previous_stint_end += row["StintLength"]

    ax.set_xlabel("Lap Number")
    ax.set_title("Tire Strategies", fontsize=12, fontweight="bold")
    ax.grid(False)
    ax.invert_yaxis()
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()
    return fig


def plot_laptimes(session) -> Figure:
    _ensure()
    require_session(session, "race session")
    import fastf1.plotting
    import seaborn as sns

    fastf1.plotting.setup_mpl(mpl_timedelta_support=True, color_scheme="fastf1")

    point_finishers = session.drivers[:10]
    driver_laps = session.laps.pick_drivers(point_finishers).pick_quicklaps().reset_index()
    finishing_order = [session.get_driver(driver)["Abbreviation"] for driver in point_finishers]
    driver_laps["LapTime (s)"] = driver_laps["LapTime"].dt.total_seconds()

    fig, ax = _new_axes((10.5, 5.4))
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)

    sns.violinplot(
        data=driver_laps,
        x="Driver",
        y="LapTime (s)",
        hue="Driver",
        inner=None,
        density_norm="area",
        order=finishing_order,
        palette=fastf1.plotting.get_driver_color_mapping(session=session),
        ax=ax,
        saturation=0.8,
    )
    sns.swarmplot(
        data=driver_laps,
        x="Driver",
        y="LapTime (s)",
        order=finishing_order,
        hue="Compound",
        palette=fastf1.plotting.get_compound_mapping(session=session),
        hue_order=driver_laps["Compound"].unique().tolist(),
        linewidth=0,
        size=4.2,
        ax=ax,
    )

    ax.set_xlabel("Driver")
    ax.set_ylabel("Lap Time (s)")
    ax.set_title(f"{session.event.year} {session.event['EventName']} · Lap Time Distributions", fontsize=12, fontweight="bold")
    sns.despine(left=True, bottom=True)
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    return fig


def plot_team_pace(session) -> Figure:
    _ensure()
    require_session(session, "race session")
    import fastf1.plotting
    import seaborn as sns

    fastf1.plotting.setup_mpl(mpl_timedelta_support=False, color_scheme="fastf1")

    laps = session.laps.pick_quicklaps()
    transformed_laps = laps.copy()
    transformed_laps.loc[:, "LapTime (s)"] = laps["LapTime"].dt.total_seconds()

    team_order = (
        transformed_laps[["Team", "LapTime (s)"]]
        .groupby("Team")
        .median()["LapTime (s)"]
        .sort_values()
        .index
    )
    team_palette = {team: fastf1.plotting.get_team_color(team, session=session) for team in team_order}

    fig, ax = _new_axes((10.5, 5.4))

    sns.boxplot(
        data=transformed_laps,
        x="Team",
        y="LapTime (s)",
        hue="Team",
        order=team_order,
        palette=team_palette,
        whiskerprops={"color": TEXT_MUTED},
        boxprops={"edgecolor": "white"},
        medianprops={"color": "white"},
        capprops={"color": TEXT_MUTED},
        ax=ax,
    )

    ax.set_title(f"{session.event['EventName']} {session.event.year} · Team Pace", fontsize=12, fontweight="bold")
    ax.grid(visible=False)
    ax.set(xlabel=None)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig

def plot_championship_progression(payload: dict, limit: int = 10) -> Figure:
    """Cumulative points per round for the top entrants (Jolpica payload)."""
    from f1_tracker.teams import team_color

    rounds = payload["rounds"]
    labels = payload["labels"]
    rows = payload["rows"][:limit]
    which = payload["kind"]

    fig, ax = _new_axes((11.0, 6.0))
    seen_colors: dict[str, int] = {}
    for entry in rows:
        team = entry["team"] if which == "drivers" else entry["name"]
        color = team_color(team)
        repeat = seen_colors.get(color, 0)
        seen_colors[color] = repeat + 1

        xs, ys = [], []
        total = 0.0
        for index, round_number in enumerate(rounds, start=1):
            cell = entry["cells"].get(round_number)
            if cell is not None:
                total = cell["total"]
            xs.append(index)
            ys.append(total)
        name = entry["name"]
        short = name.split()[-1] if which == "drivers" else name
        ax.plot(
            xs, ys,
            color=color,
            linewidth=2.4 if repeat == 0 else 1.8,
            linestyle="-" if repeat == 0 else (0, (4, 2)),
            marker="o", markersize=3.2,
            label=short,
        )
        ax.annotate(
            f" {short}", (xs[-1], ys[-1]),
            color=color, fontsize=8.5, fontweight="bold", va="center",
            annotation_clip=False,
        )

    tick_labels = [labels[r].replace("Grand Prix", "").strip()[:3].upper() for r in rounds]
    ax.set_xticks(range(1, len(rounds) + 1))
    ax.set_xticklabels(tick_labels, rotation=90, fontsize=8)
    ax.set_xlim(0.6, len(rounds) + 1.6)
    ax.set_ylabel("Points", color=TEXT)
    ax.grid(True, axis="y", alpha=0.25, color=BORDER)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    kind = "Drivers'" if which == "drivers" else "Constructors'"
    ax.set_title(f"{payload['year']} {kind} Championship · Points Progression", color=TEXT, fontsize=12, fontweight="bold", loc="left")
    legend = ax.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)
    for text in legend.get_texts():
        text.set_color(TEXT_MUTED)
    fig.tight_layout()
    return fig
