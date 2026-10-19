from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from f1_tracker.config import BRONZE, CACHE_DIR, F1_SEASON_RANGE, GOLD, SILVER
from f1_tracker.services.results import RaceWeekend, fetch_race_weekend, weekend_span
from f1_tracker.services.sessions import load_f1_session
from f1_tracker.ui.pages.base import BasePage
from f1_tracker.ui.plot_viewer import PlotViewer
from f1_tracker.ui.replay import LapProgressionPanel
from f1_tracker.teams import team_color
from f1_tracker.ui.widgets import F1Table, TeamStripe, clear_layout, make_card, make_chip, make_title
from f1_tracker.visualizations import plots

_PODIUM = ((1, GOLD), (2, SILVER), (3, BRONZE))
_TITLE_MIN_PX = 20  # smallest event-card name size before it is elided; the largest is the theme's title size


class _FlatTable(F1Table):
    """A results table that shows every row: the page scrolls as one list,
    and the mouse wheel over the table scrolls the page rather than the table."""

    def fit_height(self) -> None:
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rows = self.rowCount() or 2  # an empty table keeps a little body
        height = self.horizontalHeader().sizeHint().height() + rows * self.ROW_HEIGHT + 2 * self.frameWidth()
        if self.horizontalScrollBar().maximum() > 0:  # narrow window: room for its scrollbar
            height += self.horizontalScrollBar().sizeHint().height()
        if self.minimumHeight() != height or self.maximumHeight() != height:
            self.setFixedHeight(height)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.angleDelta().x() and not event.angleDelta().y():
            super().wheelEvent(event)  # sideways scrolling stays with the table
            return
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        if parent is None:
            event.ignore()
            return
        QApplication.sendEvent(parent.viewport(), event)


def _results_table() -> _FlatTable:
    """A race-style classification table (used for the Grand Prix and the sprint)."""
    center = Qt.AlignmentFlag.AlignCenter
    return _FlatTable(
        [
            ("Pos", 60, center),
            ("Driver", 210, None),
            ("Team", 190, None),
            ("Grid", 60, center),
            ("+/-", 60, center),
            ("Time / Gap", 130, center),
            ("Status", 110, center),
            ("Points", 70, center),
        ],
        team_columns={1: 2, 2: None},
        pill_columns=(6,),
        bold_columns=(1, 7),
    )


def _status_text(status) -> str:
    """Collapse Ergast/FastF1 result statuses into a pill label."""
    lowered = str(status or "").strip().lower()
    if not lowered or lowered == "nan":
        return ""
    if lowered == "finished":
        return "Finished"
    if lowered.startswith("+") or lowered == "lapped":
        return "Lapped"
    if "disqualified" in lowered:
        return "DSQ"
    if "did not start" in lowered or lowered == "withdrew":
        return "DNS"
    return "DNF"


class RaceSessionsPage(BasePage):
    _TABS_MIN_HEIGHT = 470
    _SPRINT_TAB = 1

    def __init__(self, controller) -> None:
        super().__init__(controller)
        self.weekend: RaceWeekend | None = None
        self.race_session = None  # FastF1 telemetry, loaded on demand
        self._pending_gp: str | None = None
        self._load_token = 0
        self._replay_token = 0
        self._watched_area: QScrollArea | None = None
        self._event_title: QLabel | None = None
        self._event_title_name = ""
        self._event_title_max_px = 30
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)

        root.addWidget(make_title("Race Sessions", "Pick a season and round to explore results, qualifying, telemetry analysis and a lap-by-lap replay.", kicker="Results & Telemetry"))

        controls = make_card()
        control_row = QHBoxLayout()
        control_row.setSpacing(10)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(F1_SEASON_RANGE[0], F1_SEASON_RANGE[1] + 1)
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setFixedWidth(96)
        control_row.addWidget(self.year_spin)

        self.gp_combo = QComboBox()
        self.gp_combo.setEditable(True)
        self.gp_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.gp_combo.setMinimumWidth(150)  # stretches; a high floor overflowed small windows
        control_row.addWidget(self.gp_combo, 1)

        self.load_button = QPushButton("Load Session")
        self.load_button.setObjectName("primary")
        self.load_button.setFixedHeight(38)
        self.load_button.clicked.connect(self.load_session)
        control_row.addWidget(self.load_button)

        self.telemetry_button = QPushButton("Load Telemetry")
        self.telemetry_button.setObjectName("ghost")
        self.telemetry_button.setFixedHeight(38)
        self.telemetry_button.setEnabled(False)
        self.telemetry_button.setToolTip("Load a session first (telemetry exists from 2018)")
        self.telemetry_button.clicked.connect(self.load_telemetry)
        control_row.addWidget(self.telemetry_button)

        controls.layout().addLayout(control_row)
        self.loading_bar = QProgressBar()
        self.loading_bar.setObjectName("thinBar")
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setRange(0, 0)
        self.loading_bar.setVisible(False)
        controls.layout().addWidget(self.loading_bar)
        self.status_label = QLabel("Results load instantly. Load Telemetry (2018 onwards) adds the analysis charts and lap progression replay; the first download of a race can take a minute.")
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        controls.layout().addWidget(self.status_label)
        root.addWidget(controls)

        self.event_card = make_card()
        self.event_card.setVisible(False)
        self.event_card.layout().addWidget(QLabel(""))
        root.addWidget(self.event_card)

        tabs = QTabWidget()
        self.tabs = tabs
        center = Qt.AlignmentFlag.AlignCenter
        self.race_table = _results_table()
        self.sprint_table = _results_table()
        self.quali_table = _FlatTable(
            [
                ("Pos", 60, center),
                ("Driver", 210, None),
                ("Team", 190, None),
                ("Q1", 110, center),
                ("Q2", 110, center),
                ("Q3", 110, center),
            ],
            team_columns={1: 2, 2: None},
            bold_columns=(1, 5),
        )
        tabs.addTab(self._tab_page(self.race_table), "Race Results")
        tabs.addTab(self._tab_page(self.sprint_table), "Sprint Results")
        tabs.setTabVisible(self._SPRINT_TAB, False)  # only sprint weekends have one
        tabs.addTab(self._tab_page(self.quali_table), "Qualifying")
        self.replay = LapProgressionPanel()
        tabs.addTab(self.replay, "Lap Progression")
        root.addWidget(tabs)
        root.addStretch(1)

        # Analysis charts live in one compact menu in the tab bar's corner.
        plot_row = QWidget()
        plot_layout = QHBoxLayout(plot_row)
        plot_layout.setContentsMargins(0, 0, 0, 6)
        self.charts_button = QPushButton("Charts")
        self.charts_button.setObjectName("ghost")
        self.charts_button.setEnabled(False)
        self.charts_button.setToolTip("Load telemetry to enable")
        menu = QMenu(self.charts_button)
        for label, target in (
            ("Position Changes", self._plot_position_changes),
            ("Tyre Strategies", self._plot_tire_strategies),
            ("Team Pace", self._plot_team_pace),
            ("Lap Time Distribution", self._plot_laptimes),
            ("Circuit Map", self._plot_circuit),
        ):
            menu.addAction(label, target)
        self.charts_button.setMenu(menu)
        plot_layout.addWidget(self.charts_button)
        tabs.setCornerWidget(plot_row, Qt.Corner.TopRightCorner)
        self._plot_row = plot_row
        tabs.currentChanged.connect(self._on_tab_changed)

        self.year_spin.valueChanged.connect(self._populate_gps)
        self._populate_gps(self.year_spin.value())
        self._fit_tables()

    @staticmethod
    def _tab_page(table: F1Table) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(table)
        return wrapper

    # ------------------------------------------------------------ layout
    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        area = self._scroll_area()
        if area is not None and area is not self._watched_area:
            # The replay is sized to the visible area, which can change without
            # this page being resized (the page is taller than the viewport).
            self._watched_area = area
            area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Resize:
            if obj is getattr(self, "_event_title", None):
                self._fit_title()
            elif self.tabs.currentWidget() is self.replay:
                QTimer.singleShot(0, self._sync_tab_height)
        return super().eventFilter(obj, event)

    def _scroll_area(self) -> QScrollArea | None:
        viewport = self.parentWidget()
        area = viewport.parentWidget() if viewport is not None else None
        return area if isinstance(area, QScrollArea) else None

    def _on_tab_changed(self, _index: int) -> None:
        on_replay = self.tabs.currentWidget() is self.replay
        self._plot_row.setVisible(not on_replay)
        self._sync_tab_height()
        if on_replay:
            # Bring the replay to the top so the whole map is on screen.
            QTimer.singleShot(0, self._scroll_to_tabs)

    def _sync_tab_height(self) -> None:
        """Size the tab area to its current tab.

        Results tabs are as tall as their full table, so the page scrolls as
        one list. The replay tab is pinned to one screenful: the map canvas
        asks for its full figure size, which would otherwise push the
        transport controls off-screen.
        """
        current = self.tabs.currentWidget()
        on_replay = current is self.replay
        if on_replay:
            area = self._scroll_area()
            viewport = area.viewport().height() if area is not None else 0
            height = max(self._TABS_MIN_HEIGHT, viewport - 16)
        else:
            height = self.tabs.tabBar().sizeHint().height() + current.sizeHint().height() + 4
        if (self.tabs.minimumHeight(), self.tabs.maximumHeight()) != (height, height):
            self.tabs.setMinimumHeight(height)
            self.tabs.setMaximumHeight(height)
            if on_replay:
                QTimer.singleShot(0, self._scroll_to_tabs)

    def _fit_tables(self) -> None:
        for table in (self.race_table, self.sprint_table, self.quali_table):
            table.fit_height()
        self._sync_tab_height()

    def _scroll_to_tabs(self, attempts: int = 8) -> None:
        area = self._scroll_area()
        if area is None:
            return
        bar = area.verticalScrollBar()
        target = max(0, self.tabs.y() - 8)
        bar.setValue(target)
        # The scroll range only grows once the scroll area re-lays out the
        # taller page, so retry briefly until the target is reachable.
        if bar.value() < target and attempts > 0:
            QTimer.singleShot(40, lambda: self._scroll_to_tabs(attempts - 1))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if event.oldSize().width() != event.size().width():
            # A narrower window may add the tables' horizontal scrollbar.
            QTimer.singleShot(0, self._fit_tables)
        self._sync_tab_height()
        self._sync_event_direction()
        if self.tabs.currentWidget() is self.replay:
            QTimer.singleShot(120, self._scroll_to_tabs)  # after the relayout settles

    def _sync_event_direction(self) -> None:
        row = getattr(self, "_event_row", None)
        if row is None:
            return
        try:
            row.setDirection(
                QBoxLayout.Direction.LeftToRight if self.width() >= 1050 else QBoxLayout.Direction.TopToBottom
            )
        except RuntimeError:  # layout already deleted with the old event card
            self._event_row = None

    # ------------------------------------------------------------ data
    def preset(self, year: int, grand_prix: str) -> None:
        """Preselect a round (and load it) — used by Home and the Calendar."""
        self._pending_gp = grand_prix
        if self.year_spin.value() != year:
            self.year_spin.setValue(year)  # triggers _populate_gps
        else:
            self._populate_gps(year)

    def _populate_gps(self, year: int) -> None:
        current = self.gp_combo.currentText().strip()
        self.gp_combo.clear()
        self.gp_combo.addItem("Loading calendar…", None)

        def on_schedule(schedule: list) -> None:
            self.gp_combo.clear()
            if schedule:
                for race in schedule:
                    self.gp_combo.addItem(f"Round {race.round:02d} · {race.name}", race.name)
            else:
                self.gp_combo.addItem("Schedule unavailable — type a Grand Prix name", None)
            self.gp_combo.setCurrentIndex(-1)
            self.gp_combo.setEditText(current or "")
            pending, self._pending_gp = self._pending_gp, None
            if pending:
                index = self.gp_combo.findData(pending)
                if index >= 0:
                    self.gp_combo.setCurrentIndex(index)
                else:
                    self.gp_combo.setEditText(pending)
                if self.load_button.isEnabled():
                    self.load_session()

        self.controller.load_schedule_async(year, on_schedule)

    def load_session(self) -> None:
        gp = self.gp_combo.itemData(self.gp_combo.currentIndex())
        if not gp:
            gp = self.gp_combo.currentText().strip()
        if not gp:
            self.status_label.setText("Please choose or type a Grand Prix name.")
            return

        year = self.year_spin.value()
        self._load_token += 1
        token = self._load_token
        self._reset_telemetry("Load telemetry to replay this race.")
        self.telemetry_button.setEnabled(False)
        self.load_button.setEnabled(False)
        self.loading_bar.setVisible(True)
        self.status_label.setText(f"Loading {year} {gp} results…")
        self.worker.run(
            lambda: fetch_race_weekend(year, gp),
            on_done=lambda weekend: self._on_loaded(weekend, token),
            on_error=lambda exc: self._on_load_error(exc, token),
        )

    def _on_loaded(self, weekend: RaceWeekend, token: int) -> None:
        if token != self._load_token:
            return  # a newer selection superseded this load
        self.load_button.setEnabled(True)
        self.loading_bar.setVisible(False)
        self.weekend = weekend
        race = weekend.race

        self._fill_results(self.race_table, weekend.results)
        self._fill_results(self.sprint_table, weekend.sprint)
        self._show_sprint_tab(bool(weekend.sprint))
        self._fill_quali_table(weekend)
        self._fit_tables()
        self._update_event_card()

        supported = weekend.year >= 2018
        has_results = bool(weekend.results)
        self.telemetry_button.setEnabled(supported and has_results)
        if not has_results:
            self.telemetry_button.setToolTip("Telemetry is available once the race has been run")
            if weekend.sprint:
                self.status_label.setText(
                    f"The {weekend.year} {race.name} race hasn't been run yet. The sprint is in the Sprint Results tab."
                )
            else:
                self.status_label.setText(f"No results yet for the {weekend.year} {race.name}.")
            self._reset_telemetry("This race hasn't been run yet.")
        elif not supported:
            self.telemetry_button.setToolTip("Telemetry exists from 2018 onwards")
            self.status_label.setText(f"Loaded {weekend.year} {race.name} results. Telemetry exists from 2018 onwards.")
            self._reset_telemetry("Lap progression replays need position data, available from 2018 onwards.")
        else:
            self.telemetry_button.setToolTip("Download timing and position data for charts and the replay")
            self.status_label.setText(
                f"Loaded {weekend.year} {race.name} results. Press Load Telemetry for charts and the lap progression replay."
            )

    def _on_load_error(self, exc: Exception, token: int) -> None:
        if token != self._load_token:
            return
        self.load_button.setEnabled(True)
        self.loading_bar.setVisible(False)
        # Don't leave the previous round on screen under a failed selection.
        self.weekend = None
        self.race_table.fill([])
        self.sprint_table.fill([])
        self._show_sprint_tab(False)
        self.quali_table.fill([])
        self._fit_tables()
        self.event_card.setVisible(False)
        self._reset_telemetry("Load a race session to replay it here.")
        self.show_error(exc, prefix="Could not load session")

    # --------------------------------------------------------- telemetry
    def _reset_telemetry(self, message: str) -> None:
        """Drop any telemetry from a previous round and disable what needs it."""
        self.race_session = None
        self._replay_token += 1
        self.charts_button.setEnabled(False)
        self.charts_button.setToolTip("Load telemetry to enable")
        self.replay.show_message(message)

    def load_telemetry(self) -> None:
        weekend = self.weekend
        if weekend is None:
            return
        token = self._load_token
        year, gp = weekend.year, weekend.race.name
        self.telemetry_button.setEnabled(False)
        self.load_button.setEnabled(False)
        self.loading_bar.setVisible(True)
        self.status_label.setText(f"Downloading {year} {gp} telemetry — the first load can take a minute, later loads are instant…")
        self.replay.show_message("Loading telemetry…")

        def done(session) -> None:
            if token != self._load_token:
                return
            self.load_button.setEnabled(True)
            self.loading_bar.setVisible(False)
            self.race_session = session
            self.telemetry_button.setToolTip("Telemetry is loaded for this round")
            self.charts_button.setEnabled(True)
            self.charts_button.setToolTip("")
            self.status_label.setText(f"Telemetry loaded for {year} {gp}. Charts and lap progression are ready.")
            self._build_replay()

        def failed(exc: Exception) -> None:
            if token != self._load_token:
                return
            self.load_button.setEnabled(True)
            self.loading_bar.setVisible(False)
            self.telemetry_button.setEnabled(True)
            self.replay.show_message("Telemetry could not be loaded.")
            self.show_error(exc, prefix="Could not load telemetry")

        self.worker.run(lambda: load_f1_session(year, gp, "R", CACHE_DIR), on_done=done, on_error=failed)

    def _build_replay(self) -> None:
        """Prepare the lap progression replay from the loaded telemetry."""
        session = self.race_session
        self._replay_token += 1
        token = self._replay_token
        if session is None:
            return
        self.replay.show_message("Preparing the race replay…")

        def work():
            from f1_tracker.visualizations.progress_map import build_progress

            return build_progress(session)

        def done(progress) -> None:
            if token == self._replay_token:  # ignore results for an older load
                self.replay.show_map(progress)

        def failed(exc: Exception) -> None:
            if token == self._replay_token:
                self.replay.show_message(f"Replay unavailable for this race: {exc}")

        self.worker.run(work, on_done=done, on_error=failed)

    # ----------------------------------------------------------- tables
    def _show_sprint_tab(self, visible: bool) -> None:
        if not visible and self.tabs.currentIndex() == self._SPRINT_TAB:
            self.tabs.setCurrentIndex(0)  # Race Results; hiding the tab first would jump to Qualifying
        self.tabs.setTabVisible(self._SPRINT_TAB, visible)

    @staticmethod
    def _fill_results(table: _FlatTable, results) -> None:
        rows = []
        for res in results:
            gained = ""
            if res.grid:
                delta = res.grid - res.position
                gained = f"+{delta}" if delta > 0 else ("—" if delta == 0 else str(delta))
            status = _status_text(res.status)
            rows.append((
                res.position,
                res.driver,
                res.team,
                res.grid if res.grid else "PL",
                gained,
                res.time if status in ("Finished", "Lapped") else "",
                status,
                int(res.points) if res.points.is_integer() else res.points,
            ))
        table.fill(rows)

    def _fill_quali_table(self, weekend: RaceWeekend) -> None:
        self.quali_table.fill([
            (row.position, row.driver, row.team, row.q1, row.q2, row.q3) for row in weekend.qualifying
        ])

    def _update_event_card(self) -> None:
        weekend = self.weekend
        if weekend is None:
            return
        race = weekend.race
        card = self.event_card
        card.setVisible(True)

        # Detach the previous content atomically. The card's dynamic content
        # lives inside one container widget, so removing that single widget
        # (setParent(None)) guarantees nothing from the old load lingers on
        # screen — unlike deleteLater-only, which defers until the next event
        # loop pass and lets stale labels overlap the freshly added ones.
        clear_layout(card.layout())

        container = QWidget()
        col = QVBoxLayout(container)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)

        # One line, left-aligned. Its width never sizes the page; _fit_title
        # shrinks the text to the room the card gives it instead.
        title = QLabel(race.name)
        title.setObjectName("pageTitle")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        title.installEventFilter(self)
        title.ensurePolished()
        self._event_title, self._event_title_name = title, race.name
        self._event_title_max_px = title.font().pixelSize()  # the theme's title size
        col.addWidget(title)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        chips.addWidget(make_chip(f"ROUND {race.round}", accent=True))
        chips.addWidget(make_chip(str(weekend.year)))
        if race.is_sprint:
            chips.addWidget(make_chip("SPRINT", variant="warning"))
        chips.addStretch(1)
        col.addLayout(chips)

        info = QLabel(f"{race.circuit}\n{race.location}  ·  {weekend_span(race)}")
        info.setWordWrap(True)
        info.setObjectName("heroInfo")
        col.addWidget(info)
        col.addStretch(1)

        outer = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        outer.setSpacing(16)
        self._event_row = outer
        self._sync_event_direction()
        outer.addWidget(container, 1)
        podium = self._podium_widget()
        if podium is not None:
            # Natural height, centred, so a taller text column does not stretch the tiles.
            outer.addWidget(podium, 0, Qt.AlignmentFlag.AlignVCenter)
        wrapper = QWidget()
        wrapper.setLayout(outer)
        outer.setContentsMargins(0, 0, 0, 0)
        card.layout().addWidget(wrapper)

    def _fit_title(self) -> None:
        """Largest size (down to a floor, then eliding) at which the name fits its line."""
        title = getattr(self, "_event_title", None)
        if title is None:
            return
        try:
            available = title.width() - 4
        except RuntimeError:  # deleted with the previous card
            self._event_title = None
            return
        if available <= 40:
            return  # not laid out yet
        name = self._event_title_name
        title.ensurePolished()  # take family and weight from the stylesheet, not the app default
        font = QFont(title.font())
        size = self._event_title_max_px
        while size > _TITLE_MIN_PX:
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(name) <= available:
                break
            size -= 1
        font.setPixelSize(size)
        text = QFontMetrics(font).elidedText(name, Qt.TextElideMode.ElideRight, available)
        if title.text() != text:
            title.setText(text)
        title.setToolTip(name if text != name else "")
        css = f"font-size: {size}px;"
        if title.styleSheet() != css:
            title.setStyleSheet(css)

    def _podium_widget(self) -> QWidget | None:
        results = self.weekend.results if self.weekend is not None else ()
        if not results:
            return None
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        for (place, color), res in zip(_PODIUM, results[:3]):
            tile = QFrame()
            tile.setObjectName("podiumCard")
            tile.setMinimumWidth(170)
            layout = QHBoxLayout(tile)
            layout.setContentsMargins(12, 10, 14, 10)
            layout.setSpacing(10)
            badge = QLabel(f"P{place}")
            badge.setObjectName("positionBadge")
            badge.setStyleSheet(f"color: {color}; font-size: 20px;")
            layout.addWidget(badge)
            team = res.team
            layout.addWidget(TeamStripe(team_color(team), 4, 34))
            text = QVBoxLayout()
            text.setSpacing(0)
            name = QLabel(res.family_name)
            name.setObjectName("listPrimary")
            sub = QLabel(team)
            sub.setObjectName("listSecondary")
            text.addWidget(name)
            text.addWidget(sub)
            layout.addLayout(text, 1)
            row.addWidget(tile)
        return widget

    # ------------------------------------------------------------ plots
    def _show_figure(self, fn, session, *, title: str) -> None:
        if session is None:
            return
        self.status_label.setText(f"Rendering {title.lower()}…")

        def done(fig) -> None:
            self.status_label.setText("")
            PlotViewer(fig, title, self).show()

        self.worker.run(lambda: fn(session), on_done=done, on_error=self.show_error)

    def _plot_position_changes(self) -> None:
        self._show_figure(plots.plot_position_changes, self.race_session, title="Position Changes")

    def _plot_tire_strategies(self) -> None:
        self._show_figure(plots.plot_tire_strategies, self.race_session, title="Tyre Strategies")

    def _plot_team_pace(self) -> None:
        self._show_figure(plots.plot_team_pace, self.race_session, title="Team Pace")

    def _plot_laptimes(self) -> None:
        self._show_figure(plots.plot_laptimes, self.race_session, title="Lap Times")

    def _plot_circuit(self) -> None:
        self._show_figure(plots.plot_circuit, self.race_session, title="Circuit Map")