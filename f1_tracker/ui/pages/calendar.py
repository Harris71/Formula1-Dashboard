from __future__ import annotations

from datetime import date, datetime, timezone

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from f1_tracker.config import F1_SEASON_RANGE, GOLD, TEXT_DIM
from f1_tracker.services.schedule import next_race, schedule_to_ics
from f1_tracker.ui.pages.base import BasePage
from f1_tracker.ui.widgets import F1Table, clear_layout, make_card, make_chip, make_divider, make_title


def _status(race, today: date, upcoming) -> str:
    if race.race_date < today:
        return "Completed"
    if race.race_date == today:
        return "Race day"
    if upcoming is not None and race.round == upcoming.round:
        return "Race week" if (race.race_date - today).days <= 6 else "Next"
    return "Upcoming"


class CalendarPage(BasePage):
    def __init__(self, controller) -> None:
        super().__init__(controller)
        self._year = datetime.now().year
        self._schedule: list = []
        self._build()
        self.refresh()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)

        root.addWidget(make_title("Season Calendar", "Every round of the season with session times in your time zone.", kicker="Schedule"))

        controls = make_card()
        row = QHBoxLayout()
        row.setSpacing(10)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(F1_SEASON_RANGE[0], F1_SEASON_RANGE[1] + 1)
        self.year_spin.setValue(self._year)
        self.year_spin.setFixedWidth(96)
        row.addWidget(self.year_spin)

        refresh = QPushButton("Refresh")
        refresh.setObjectName("ghost")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        row.addWidget(self.status_label, 1)

        self.export_button = QPushButton("Export to Calendar (.ics)")
        self.export_button.setObjectName("primary")
        self.export_button.setToolTip("Save every session of the season as an iCalendar file")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._export_ics)
        row.addWidget(self.export_button)
        controls.layout().addLayout(row)
        root.addWidget(controls)

        body = QHBoxLayout()
        body.setSpacing(16)

        center = Qt.AlignmentFlag.AlignCenter
        self.table = F1Table(
            [
                ("Rd", 52, center),
                ("Grand Prix", 220, None),
                ("Circuit", 230, None),
                ("Date", 80, center),
                ("Start", 100, center),
                ("Status", 120, center),
            ],
            podium=False,
            pill_columns=(5,),
            bold_columns=(1,),
            stretch_column=1,
        )
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSortingEnabled(False)
        self.table.horizontalHeader().setSortIndicatorShown(False)
        self.table.itemSelectionChanged.connect(self._on_selection)
        body.addWidget(self.table, 1)

        self.detail = make_card()
        self.detail.setFixedWidth(310)
        self.detail_layout = QVBoxLayout()
        self.detail_layout.setSpacing(10)
        self.detail.layout().addLayout(self.detail_layout)
        self.detail.layout().addStretch(1)
        body.addWidget(self.detail)
        self.table.setMinimumHeight(420)
        root.addLayout(body, 1)

        self.year_spin.valueChanged.connect(self.refresh)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        # The circuit is repeated in the detail panel; drop it when space is tight.
        self.table.setColumnHidden(2, self.table.width() < 820)

    def refresh(self) -> None:
        self._year = self.year_spin.value()
        self.status_label.setText("Fetching calendar…")
        self.export_button.setEnabled(False)
        year = self._year
        self.worker.run(
            lambda: self.controller.get_schedule(year),
            on_done=lambda schedule: self._populate(schedule, year),
            on_error=self._on_error,
        )

    def _populate(self, schedule, year: int) -> None:
        if year != self.year_spin.value():
            return  # a newer request superseded this one
        self._schedule = schedule
        today = date.today()
        upcoming = next_race(schedule, today)

        rows = []
        for race in schedule:
            local = race.start_local()
            start = local.strftime("%a %H:%M") if local else "TBC"
            rows.append((
                race.round, race.name, race.circuit,
                f"{race.race_date:%d %b}", start, _status(race, today, upcoming),
            ))
        self.table.fill(rows)

        if not schedule:
            self.status_label.setText("No calendar available for this season.")
            self._show_detail(None)
            return
        sprints = sum(1 for race in schedule if race.is_sprint)
        summary = f"{len(schedule)} rounds"
        if sprints:
            summary += f"  ·  {sprints} sprint weekends"
        summary += f"  ·  Next: {upcoming.name}" if upcoming else "  ·  Season complete"
        self.status_label.setText(summary)
        self.export_button.setEnabled(True)

        bold = QFont(self.table.font())
        bold.setBold(True)
        for row, race in enumerate(schedule):
            done = race.race_date < today
            for col in range(self.table.columnCount() - 1):
                item = self.table.item(row, col)
                if item is None:
                    continue
                if upcoming is not None and race.round == upcoming.round:
                    item.setForeground(QBrush(QColor(GOLD)))
                    item.setFont(bold)
                elif done:
                    item.setForeground(QBrush(QColor(TEXT_DIM)))

        focus = schedule.index(upcoming) if upcoming else len(schedule) - 1
        self.table.selectRow(focus)
        self.table.scrollToItem(self.table.item(focus, 0))

    def _on_selection(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows or rows[0].row() >= len(self._schedule):
            return
        self._show_detail(self._schedule[rows[0].row()])

    # ------------------------------------------------------------- detail
    def _show_detail(self, race) -> None:
        layout = self.detail_layout
        clear_layout(layout)
        if race is None:
            empty = QLabel("Select a round to see its weekend schedule.")
            empty.setObjectName("emptyState")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return

        today = date.today()
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(make_chip(f"ROUND {race.round:02d}", accent=True))
        if race.is_sprint:
            chips.addWidget(make_chip("SPRINT", variant="warning"))
        if race.race_date < today:
            chips.addWidget(make_chip("COMPLETED"))
        elif (race.race_date - today).days <= 6:
            chips.addWidget(make_chip("THIS WEEK", variant="success"))
        chips.addStretch(1)
        layout.addLayout(chips)

        title = QLabel(race.name)
        title.setObjectName("sectionTitle")
        title.setStyleSheet("font-size: 22px;")
        title.setWordWrap(True)
        layout.addWidget(title)

        local = race.start_local()
        day = local if local is not None else race.race_date
        info = QLabel(f"{race.circuit}\n{race.location}\n{day:%A %d %B %Y}")
        info.setObjectName("muted")
        info.setWordWrap(True)
        layout.addWidget(info)

        if race.race_date >= today:
            days = (race.race_date - today).days
            when = QLabel("Lights out today" if days == 0 else f"Lights out in {days} day{'s' if days != 1 else ''}")
            when.setObjectName("listPrimary")
            when.setStyleSheet("color: #FF1801;")
            layout.addWidget(when)

        layout.addWidget(make_divider())
        heading = QLabel("WEEKEND SCHEDULE  ·  YOUR TIME")
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)

        now = datetime.now(timezone.utc)
        for session in race.weekend():
            row = QHBoxLayout()
            name = QLabel(session.name)
            local = session.local()
            when = QLabel(f"{local:%a %d %b · %H:%M}" if local else f"{session.day:%a %d %b}")
            done = session.start_utc is not None and session.start_utc < now
            name.setObjectName("dim" if done else ("listPrimary" if session.name == "Race" else "muted"))
            when.setObjectName("dim" if done else "listPrimary")
            row.addWidget(name)
            row.addStretch(1)
            row.addWidget(when)
            layout.addLayout(row)

        layout.addSpacing(6)
        results = QPushButton("View Race Results")
        results.setObjectName("primary")
        results.setMinimumHeight(40)
        results.setEnabled(race.race_date < today)
        results.setToolTip("Open this round in Race Sessions" if race.race_date < today else "Available after the race")
        results.clicked.connect(lambda _=False, r=race: self.controller.open_race(self._year, r.name))
        layout.addWidget(results)

    # ------------------------------------------------------------- export
    def _export_ics(self) -> None:
        if not self._schedule:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export season calendar", f"F1_{self._year}_calendar.ics", "iCalendar (*.ics)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(schedule_to_ics(self._year, self._schedule))
        except OSError as exc:
            self.show_error(exc, prefix="Export failed")
            return
        self.status_label.setText(f"Saved {len(self._schedule)} rounds to {path}")

    def _on_error(self, exc: Exception) -> None:
        self.show_error(exc, prefix="Calendar error")
