from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from f1_tracker.config import F1_SEASON_RANGE
from f1_tracker.services.standings import (
    fetch_constructor_standings,
    fetch_driver_standings,
    fetch_progression_table,
)
from f1_tracker.ui.pages.base import BasePage
from f1_tracker.ui.plot_viewer import PlotViewer
from f1_tracker.ui.widgets import F1Table, clear_layout, make_card, make_chip, make_title

_MODES = (
    ("Race Positions", "pos"),
    ("Points Per Race", "race"),
    ("Total Points", "total"),
)


def _num(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    return int(number) if number.is_integer() else number


def _short_round_name(name: str) -> str:
    base = name.replace("Grand Prix", "").strip()
    words = [w for w in base.split() if w]
    return words[0][:3].upper() if words else "GP"


class StandingsPage(BasePage):
    def __init__(self, controller) -> None:
        super().__init__(controller)
        self._year = datetime.now().year
        self._progression_payload: dict | None = None
        self.progression_table: F1Table | None = None
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)

        root.addWidget(make_title("Championship Standings", "Drivers' and Constructors' classification for any season since 1950.", kicker="Championships"))

        controls = make_card()
        row = QHBoxLayout()
        row.setSpacing(10)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(F1_SEASON_RANGE[0], F1_SEASON_RANGE[1])
        self.year_spin.setValue(self._year)
        self.year_spin.setFixedWidth(96)
        row.addWidget(self.year_spin)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter drivers / teams…")
        self.search_input.setMinimumWidth(240)
        self.search_input.textChanged.connect(self._filter)
        row.addWidget(self.search_input, 1)

        refresh = QPushButton("Refresh")
        refresh.setObjectName("ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)

        controls.layout().addLayout(row)
        leader_row = QHBoxLayout()
        leader_row.setSpacing(10)
        self.leader_chip = make_chip("LEADER", accent=True)
        self.leader_chip.setVisible(False)
        leader_row.addWidget(self.leader_chip)
        self.leader_label = QLabel("")
        self.leader_label.setObjectName("muted")
        leader_row.addWidget(self.leader_label, 1)
        controls.layout().addLayout(leader_row)
        root.addWidget(controls)

        tabs = QTabWidget()
        self.tabs = tabs
        center = Qt.AlignmentFlag.AlignCenter
        self.drivers_table = F1Table(
            [
                ("Pos", 64, center),
                ("Driver", 230, None),
                ("No", 56, center),
                ("Nationality", 130, None),
                ("Team", 210, None),
                ("Points", 90, center),
                ("Gap", 90, center),
                ("Wins", 70, center),
            ],
            team_columns={1: 4, 4: None},
            bold_columns=(1, 5),
        )
        self.constructors_table = F1Table(
            [
                ("Pos", 64, center),
                ("Constructor", 320, None),
                ("Points", 120, center),
                ("Gap", 120, center),
                ("Wins", 100, center),
            ],
            team_columns={1: None},
            bold_columns=(1, 2),
        )
        tabs.addTab(self._tab(self.drivers_table), "Drivers' Championship")
        tabs.addTab(self._tab(self.constructors_table), "Constructors' Championship")
        tabs.addTab(self._build_progression_tab(), "Progression")
        tabs.setMinimumHeight(380)
        root.addWidget(tabs, 1)

        self.year_spin.valueChanged.connect(self.refresh)

    @staticmethod
    def _tab(table: F1Table) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(table)
        return wrapper

    # ------------------------------------------------------ progression tab
    def _build_progression_tab(self) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)

        self.progression_kind = QComboBox()
        self.progression_kind.addItem("Drivers' Championship", "drivers")
        self.progression_kind.addItem("Constructors' Championship", "constructors")
        row.addWidget(self.progression_kind)

        self.progression_mode = QComboBox()
        for label, data in _MODES:
            self.progression_mode.addItem(label, data)
        row.addWidget(self.progression_mode)

        self.progression_load = QPushButton("Load Table")
        self.progression_load.setObjectName("primary")
        self.progression_load.clicked.connect(self.load_progression)
        row.addWidget(self.progression_load)

        self.progression_chart = QPushButton("Points Chart")
        self.progression_chart.setObjectName("ghost")
        self.progression_chart.setToolTip("Cumulative points race by race for the top 10")
        self.progression_chart.setEnabled(False)
        self.progression_chart.clicked.connect(self._show_progression_chart)
        row.addWidget(self.progression_chart)
        row.addStretch(1)
        layout.addLayout(row)

        self.progression_progress = QProgressBar()
        self.progression_progress.setRange(0, 1)
        self.progression_progress.setValue(0)
        self.progression_progress.setVisible(False)
        self.progression_progress.setFixedHeight(14)
        layout.addWidget(self.progression_progress)

        self.progression_status = QLabel("")
        self.progression_status.setObjectName("muted")
        layout.addWidget(self.progression_status)

        self.table_holder = QWidget()
        self.table_layout = QVBoxLayout(self.table_holder)
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table_holder, 1)

        self.progression_kind.currentIndexChanged.connect(self._on_progression_view_changed)
        self.progression_mode.currentIndexChanged.connect(self._on_progression_view_changed)
        return wrapper

    def load_progression(self) -> None:
        year = self.year_spin.value()
        which = self.progression_kind.currentData() or "drivers"
        self.progression_load.setEnabled(False)
        self.progression_progress.setVisible(True)
        self.progression_progress.setValue(0)
        self.progression_status.setText(f"Fetching race-by-race results for {year}…")

        def work(progress):
            schedule = self.controller.get_schedule(year)
            today = datetime.now().date()
            rounds = sorted({race.round for race in schedule if race.race_date <= today})
            if not rounds:
                raise ValueError(f"No completed rounds yet for {year}.")
            labels = {race.round: race.name for race in schedule}
            rows = fetch_progression_table(year, rounds, which, progress=progress)
            return {"year": year, "kind": which, "rounds": rounds, "labels": labels, "rows": rows}

        self.worker.run(
            work,
            on_done=self._apply_progression,
            on_error=self._on_progression_error,
            progress=self._update_progression_progress,
        )

    def _update_progression_progress(self, current: int, total: int) -> None:
        if self.progression_progress.maximum() != total:
            self.progression_progress.setRange(0, total)
        self.progression_progress.setValue(current)

    def _apply_progression(self, payload: dict) -> None:
        self._progression_payload = payload
        self.progression_load.setEnabled(True)
        self.progression_chart.setEnabled(bool(payload["rows"]))
        self.progression_progress.setVisible(False)
        self.progression_progress.setValue(0)
        self._render_progression_table()

    @staticmethod
    def _progression_cell(cell: dict | None, mode: str):
        if cell is None:
            return ""
        if mode == "pos":
            return cell["position"] if cell["position"] is not None else ""
        value = cell["total"] if mode == "total" else cell["points"]
        return int(value) if float(value).is_integer() else value

    def _render_progression_table(self) -> None:
        payload = self._progression_payload
        if not payload or not payload["rows"]:
            return

        which = payload["kind"]
        mode = self.progression_mode.currentData() or "pos"

        clear_layout(self.table_layout)

        columns = [
            ("P", 44, Qt.AlignmentFlag.AlignCenter),
            ("Pts", 54, Qt.AlignmentFlag.AlignCenter),
        ]
        name_header = "Constructor" if which == "constructors" else "Driver"
        columns.append((name_header, 170, None))
        if which == "drivers":
            columns.append(("No", 48, Qt.AlignmentFlag.AlignCenter))
        columns.append(("Team", 150, None))
        for round_number in payload["rounds"]:
            columns.append((_short_round_name(payload["labels"][round_number]), 52, Qt.AlignmentFlag.AlignCenter))

        team_col = len(columns) - len(payload["rounds"]) - 1
        stripes = {2: team_col, team_col: None} if which == "drivers" else {2: None}
        table = F1Table(columns, team_columns=stripes, bold_columns=(1,))
        for col_index, round_number in enumerate(payload["rounds"], start=len(columns) - len(payload["rounds"])):
            header_item = table.horizontalHeaderItem(col_index)
            header_item.setToolTip(f"R{round_number} · {payload['labels'][round_number]}")

        rows = []
        for entry in payload["rows"]:
            values = [entry["position"], _num(entry["points"]), entry["name"]]
            if which == "drivers":
                values.append(entry["number"])
            values.append(entry["team"])
            for round_number in payload["rounds"]:
                values.append(self._progression_cell(entry["cells"].get(round_number), mode))
            rows.append(values)

        table.fill(rows)
        self.table_layout.addWidget(table)
        self.progression_table = table
        table.filter_rows(self.search_input.text())

        label = "Drivers'" if which == "drivers" else "Constructors'"
        mode_text = dict((data, text) for text, data in _MODES)[mode].lower()
        self.progression_status.setText(
            f"{payload['year']} {label} Championship · showing {mode_text}. "
            f"Blank cells mean the entrant missed that round."
        )

    def _on_progression_view_changed(self) -> None:
        payload = self._progression_payload
        current_year = self.year_spin.value()
        current_kind = self.progression_kind.currentData() or "drivers"
        if payload and payload["year"] == current_year and payload["kind"] == current_kind:
            self._render_progression_table()

    def _reset_progression_table(self) -> None:
        self._progression_payload = None
        self.progression_table = None
        if hasattr(self, "table_layout"):
            clear_layout(self.table_layout)
        self.progression_chart.setEnabled(False)
        self.progression_status.setText("Load the table to see every round of the season.")
        self.progression_progress.setVisible(False)

    def _show_progression_chart(self) -> None:
        payload = self._progression_payload
        if not payload or not payload["rows"]:
            return
        from f1_tracker.visualizations.plots import plot_championship_progression

        label = "Drivers'" if payload["kind"] == "drivers" else "Constructors'"
        self.worker.run(
            lambda: plot_championship_progression(payload),
            on_done=lambda fig: PlotViewer(fig, f"{payload['year']} {label} Championship", self).show(),
            on_error=self._on_progression_error,
        )

    def _on_progression_error(self, exc: Exception) -> None:
        self.progression_load.setEnabled(True)
        self.progression_progress.setVisible(False)
        self.progression_status.setText(f"<span style='color:#E74C3C;'>Progression error: {exc}</span>")
        import traceback

        traceback.print_exc()

    # ---------------------------------------------------------- standings
    def preset(self, year: int, kind: str = "drivers") -> None:
        """Load a season's table on the given tab (used by Home's "View all")."""
        self.tabs.setCurrentIndex(1 if kind == "constructors" else 0)
        self.search_input.clear()  # "View all" means the whole table
        if self.year_spin.value() != year:
            self.year_spin.setValue(year)  # triggers refresh
        else:
            self.refresh()

    def refresh(self) -> None:
        self._year = self.year_spin.value()
        self._reset_progression_table()
        self.leader_chip.setVisible(False)
        self.leader_label.setText("Fetching standings…")
        self.worker.run(
            lambda: self._fetch(),
            on_done=self._populate,
            on_error=self._on_error,
        )

    def _fetch(self) -> dict:
        return {
            "drivers": fetch_driver_standings(self._year),
            "constructors": fetch_constructor_standings(self._year),
            "year": self._year,
        }

    def _populate(self, data: dict) -> None:
        year = data["year"]
        if year != self.year_spin.value():
            return  # a newer request superseded this one
        drivers = data["drivers"]
        constructors = data["constructors"]

        def gap(points, leader_points) -> str:
            diff = _num(float(leader_points) - float(points))
            return "—" if diff == 0 else f"-{diff}"

        driver_top = drivers[0].points if drivers else 0
        self.drivers_table.fill([
            (s.position, s.driver, _num(s.number), s.nationality, s.team, _num(s.points), gap(s.points, driver_top), _num(s.wins))
            for s in drivers
        ])
        team_top = constructors[0].points if constructors else 0
        self.constructors_table.fill([
            (s.position, s.constructor, _num(s.points), gap(s.points, team_top), _num(s.wins)) for s in constructors
        ])

        final = year < datetime.now().year
        self.leader_chip.setVisible(bool(drivers or constructors))
        if final:
            self.leader_chip.setText("WORLD CHAMPION")
            self.leader_chip.setObjectName("chipGold")
        else:
            self.leader_chip.setText("CHAMPIONSHIP LEADER")
            self.leader_chip.setObjectName("chipAccent")
        self.leader_chip.style().unpolish(self.leader_chip)
        self.leader_chip.style().polish(self.leader_chip)
        self.leader_chip.adjustSize()

        if drivers:
            leader = drivers[0]
            team_note = f" — Constructors': {constructors[0].constructor}" if constructors else ""
            if final:
                self.leader_label.setText(
                    f"<b style='color:#F2F5F7;'>{leader.driver}</b> — {year} World Champion "
                    f"({leader.team}, {_num(leader.points)} pts, {leader.wins} wins){team_note}"
                )
            else:
                margin = ""
                if len(drivers) > 1:
                    margin = f", {_num(float(leader.points) - float(drivers[1].points))} pts clear of {drivers[1].driver}"
                self.leader_label.setText(
                    f"<b style='color:#F2F5F7;'>{leader.driver}</b> leads with {_num(leader.points)} pts "
                    f"({leader.team}){margin}."
                )
        elif constructors:
            self.leader_label.setText(f"{constructors[0].constructor} leads the Constructors' Championship.")
        else:
            self.leader_label.setText("No standings returned for this season.")
        self._filter()

    def _filter(self) -> None:
        query = self.search_input.text()
        self.drivers_table.filter_rows(query)
        self.constructors_table.filter_rows(query)
        if self.progression_table is not None:
            self.progression_table.filter_rows(query)

    def _on_error(self, exc: Exception) -> None:
        self.leader_label.setText(f"<span style='color:#E74C3C;'>Standings error: {exc}</span>")
        import traceback

        traceback.print_exc()
