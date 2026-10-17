from __future__ import annotations

from datetime import date, datetime, timezone

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPolygonF
from PyQt6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from f1_tracker.config import ACCENT, BORDER, BRONZE, GOLD, SILVER, TEXT_DIM
from f1_tracker.services.schedule import next_race, previous_race
from f1_tracker.services.standings import (
    fetch_constructor_standings,
    fetch_driver_standings,
    fetch_last_race,
)
from f1_tracker.teams import team_color
from f1_tracker.ui.pages.base import BasePage
from f1_tracker.ui.widgets import (
    StatCard,
    TeamStripe,
    clear_layout,
    make_card,
    make_chip,
    make_thin_bar,
    make_title,
)

_PODIUM_COLORS = {"1": GOLD, "2": SILVER, "3": BRONZE}


class HeroCard(QFrame):
    """Gradient card with painted speed stripes in the top-right corner."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("heroCard")

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        w = self.width()
        for i, alpha in enumerate((34, 22, 12)):
            color = QColor(ACCENT)
            color.setAlpha(alpha)
            painter.setBrush(color)
            x = w - 330 + i * 70
            painter.drawPolygon(QPolygonF([
                QPointF(x + 120, 1), QPointF(x + 160, 1), QPointF(x + 40, 150), QPointF(x, 150),
            ]))


class PointsBar(QWidget):
    """Thin horizontal bar showing a value relative to the leader."""

    def __init__(self, ratio: float, color: str) -> None:
        super().__init__()
        self._ratio = max(0.0, min(1.0, ratio))
        self._color = QColor(color)
        self.setFixedHeight(4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(BORDER))
        painter.drawRoundedRect(QRectF(self.rect()), 2, 2)
        painter.setBrush(self._color)
        painter.drawRoundedRect(QRectF(0, 0, self.width() * self._ratio, self.height()), 2, 2)


def _countdown_block(unit: str) -> tuple[QFrame, QLabel]:
    block = QFrame()
    block.setObjectName("countdownBlock")
    block.setFixedSize(92, 92)
    col = QVBoxLayout(block)
    col.setContentsMargins(0, 8, 0, 10)
    col.setSpacing(0)
    value = QLabel("--")
    value.setObjectName("countdownValue")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label = QLabel(unit)
    label.setObjectName("countdownUnit")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    col.addWidget(value, 1)
    col.addWidget(label)
    return block, value


def _to_number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_points(value) -> str:
    number = _to_number(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


class HomePage(BasePage):
    def __init__(self, controller) -> None:
        super().__init__(controller)
        self._year = datetime.now().year
        self._race = None
        self._last_race = None
        self._loaded_at: datetime | None = None
        self._standings_year = self._year
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._build()

    # ------------------------------------------------------------------ UI
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        body = QWidget()
        body.setObjectName("scrollBody")
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        header = QHBoxLayout()
        header.addWidget(
            make_title(
                "Race Control",
                "Live countdown, championship picture and the latest results at a glance.",
                kicker=f"{datetime.now():%A %d %B %Y}",
            ),
            1,
        )
        refresh = QPushButton("Refresh")
        refresh.setObjectName("ghost")
        refresh.setToolTip("Reload all data (F5)")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(header)

        self.status_label = QLabel("")
        self.status_label.setObjectName("muted")
        self.status_label.setVisible(False)
        root.addWidget(self.status_label)

        root.addWidget(self._build_hero())

        tiles = QGridLayout()
        tiles.setHorizontalSpacing(14)
        tiles.setVerticalSpacing(14)
        self.wdc_tile = StatCard("Drivers' leader")
        self.wcc_tile = StatCard("Constructors' leader")
        self.winner_tile = StatCard("Last winner")
        self.progress_tile = StatCard("Season progress")
        self.progress_bar = make_thin_bar()
        self.progress_tile.layout().insertWidget(3, self.progress_bar)
        self._tiles = tiles
        self._tile_cards = (self.wdc_tile, self.wcc_tile, self.winner_tile, self.progress_tile)
        for tile in self._tile_cards:
            tile.setMinimumHeight(118)
        root.addLayout(tiles)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        drivers_card, self.drivers_list = self._list_card("Drivers' Championship", "drivers")
        teams_card, self.teams_list = self._list_card("Constructors' Championship", "constructors")
        podium_card, self.podium_list = self._list_card("Last Race", None)
        self.podium_title = podium_card.findChild(QLabel, "cardTitle")
        self.podium_link = QPushButton("Full results  →")
        self.podium_link.setObjectName("linkButton")
        self.podium_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.podium_link.setVisible(False)
        self.podium_link.clicked.connect(self._open_last_race)
        podium_card.layout().itemAt(0).layout().addWidget(self.podium_link)
        self._grid = grid
        self._grid_cards = (drivers_card, teams_card, podium_card)
        self._grid_columns = 0
        self._layout_grid(3)
        root.addLayout(grid)
        root.addStretch(1)

        for layout in (self.drivers_list, self.teams_list, self.podium_list):
            self._placeholder(layout, "Loading…")

        self.refresh()

    def _build_hero(self) -> QFrame:
        card = HeroCard()
        col = QVBoxLayout(card)
        col.setContentsMargins(28, 24, 28, 22)
        col.setSpacing(18)

        top = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        top.setSpacing(24)
        self._hero_top = top

        info = QVBoxLayout()
        info.setSpacing(6)
        self.hero_chips = QHBoxLayout()
        self.hero_chips.setSpacing(8)
        self.hero_chips.addWidget(make_chip("NEXT RACE", accent=True))
        self.hero_chips.addStretch(1)
        info.addLayout(self.hero_chips)
        info.addSpacing(4)

        self.next_value = QLabel("Checking the calendar…")
        self.next_value.setObjectName("heroTitle")
        self.next_value.setWordWrap(True)
        info.addWidget(self.next_value)

        self.next_extra = QLabel("")
        self.next_extra.setObjectName("heroInfo")
        self.next_extra.setWordWrap(True)
        info.addWidget(self.next_extra)

        self.next_days = QLabel("")
        self.next_days.setObjectName("heroInfo")
        info.addWidget(self.next_days)
        info.addStretch(1)
        top.addLayout(info, 1)

        countdown = QHBoxLayout()
        countdown.setSpacing(10)
        self._countdown_values: list[QLabel] = []
        for unit in ("DAYS", "HRS", "MIN", "SEC"):
            block, value = _countdown_block(unit)
            countdown.addWidget(block)
            self._countdown_values.append(value)
        countdown.addStretch(1)
        top.addLayout(countdown)
        col.addLayout(top)

        self.timetable = QHBoxLayout()
        self.timetable.setSpacing(10)
        col.addLayout(self.timetable)
        return card

    def _list_card(self, title: str, standings_kind: str | None) -> tuple[QFrame, QVBoxLayout]:
        card = make_card()
        card.layout().setContentsMargins(20, 18, 20, 16)
        header = QHBoxLayout()
        label = QLabel(title.upper())
        label.setObjectName("cardTitle")
        header.addWidget(label)
        header.addStretch(1)
        if standings_kind:
            link = QPushButton("View all  →")
            link.setObjectName("linkButton")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            # Open the season shown here, on the matching championship tab.
            link.clicked.connect(
                lambda _=False, k=standings_kind: self.controller.open_standings(self._standings_year, k)
            )
            header.addWidget(link)
        card.layout().addLayout(header)
        body = QVBoxLayout()
        body.setSpacing(12)
        card.layout().addLayout(body)
        card.layout().addStretch(1)
        return card, body

    # ------------------------------------------------------------- responsive
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        width = self.width()
        self._hero_top.setDirection(
            QBoxLayout.Direction.LeftToRight if width >= 1000 else QBoxLayout.Direction.TopToBottom
        )
        self._layout_grid(3 if width >= 1000 else 2)

    def _layout_grid(self, columns: int) -> None:
        if columns == self._grid_columns:
            return
        self._grid_columns = columns
        self._place(self._grid, self._grid_cards, columns)
        self._place(self._tiles, self._tile_cards, 4 if columns == 3 else 2)

    @staticmethod
    def _place(grid: QGridLayout, cards, columns: int) -> None:
        for card in cards:
            grid.removeWidget(card)
        for index, card in enumerate(cards):
            grid.addWidget(card, index // columns, index % columns)
        for col in range(4):
            grid.setColumnStretch(col, 1 if col < columns else 0)

    @staticmethod
    def _placeholder(layout: QVBoxLayout, text: str) -> None:
        clear_layout(layout)
        label = QLabel(text)
        label.setObjectName("emptyState")
        layout.addWidget(label)

    # ------------------------------------------------------------- data
    def refresh(self) -> None:
        self.worker.run(
            self._fetch_all,
            on_done=self._apply,
            on_error=self._on_error,
        )

    def on_show(self) -> None:
        # Pick up results from a weekend that finished while the app was open.
        if self._loaded_at and (datetime.now() - self._loaded_at).total_seconds() > 30 * 60:
            self.refresh()

    def _fetch_all(self) -> dict:
        schedule = self.controller.get_schedule(self._year)
        year = self._year
        if schedule and next_race(schedule) is None:
            following = self.controller.get_schedule(self._year + 1)
            if following:
                schedule, year = following, self._year + 1

        def safe(fn, *args):
            try:
                return fn(*args)
            except Exception:  # noqa: BLE001
                return None

        standings_year = self._year
        drivers = safe(fetch_driver_standings, standings_year) or []
        if not drivers:
            standings_year -= 1  # pre-season: show last year's final table
            drivers = safe(fetch_driver_standings, standings_year) or []
        constructors = safe(fetch_constructor_standings, standings_year) or []
        last = safe(fetch_last_race, self._year) or safe(fetch_last_race, self._year - 1)
        current_schedule = self.controller.get_schedule(self._year)
        completed = sum(1 for race in current_schedule if race.race_date < date.today())
        return {
            "schedule": schedule,
            "schedule_year": year,
            "completed": completed,
            "total": len(current_schedule),
            "drivers": drivers,
            "constructors": constructors,
            "standings_year": standings_year,
            "last": last,
        }

    def _on_error(self, exc: Exception) -> None:
        self.status_label.setVisible(True)
        self.show_error(exc)

    def _apply(self, data: dict) -> None:
        self._loaded_at = datetime.now()
        self.status_label.setVisible(False)
        schedule = data["schedule"]
        self._apply_hero(schedule)
        self._apply_tiles(data)
        self._apply_lists(data)

    # ------------------------------------------------------------- hero
    def _apply_hero(self, schedule: list) -> None:
        nxt = next_race(schedule)
        self._race = nxt
        clear_layout(self.hero_chips)
        clear_layout(self.timetable)

        if nxt is None:
            last = previous_race(schedule) if schedule else None
            self.hero_chips.addWidget(make_chip("SEASON COMPLETE", variant="gold"))
            self.hero_chips.addStretch(1)
            self.next_value.setText(last.name if last else "No races scheduled")
            self.next_extra.setText("The season is over — see you next year." if last else "The calendar could not be loaded.")
            self.next_days.setText("")
            for value in self._countdown_values:
                value.setText("--")
            self._timer.stop()
            return

        self.hero_chips.addWidget(make_chip("NEXT RACE", accent=True))
        self.hero_chips.addWidget(make_chip(f"ROUND {nxt.round:02d} / {len(schedule):02d}"))
        if nxt.is_sprint:
            self.hero_chips.addWidget(make_chip("SPRINT WEEKEND", variant="warning"))
        days_out = (nxt.race_date - date.today()).days
        if days_out <= 3:
            self.hero_chips.addWidget(make_chip("RACE WEEK" if days_out else "RACE DAY", variant="success"))
        self.hero_chips.addStretch(1)

        self.next_value.setText(nxt.name)
        self.next_extra.setText(f"{nxt.circuit}  ·  {nxt.location}")
        local = nxt.start_local()
        if local is not None:
            self.next_days.setText(
                f"{local:%A %d %B}  ·  Lights out <b style='color:#FFFFFF;'>{local:%H:%M}</b> "
                f"<span style='color:{TEXT_DIM};'>{local:%Z} (your time)</span>"
            )
        else:
            self.next_days.setText(f"{nxt.race_date:%A %d %B %Y}")

        now = datetime.now(timezone.utc)
        for session in nxt.weekend():
            self.timetable.addWidget(self._session_tile(session, now), 1)

        self._tick()
        self._timer.start()

    @staticmethod
    def _session_tile(session, now: datetime) -> QFrame:
        tile = QFrame()
        done = session.start_utc is not None and session.start_utc < now
        if session.name == "Race":
            tile.setObjectName("sessionTileRace")
        elif done:
            tile.setObjectName("sessionTileDone")
        else:
            tile.setObjectName("sessionTile")
        col = QVBoxLayout(tile)
        col.setContentsMargins(12, 8, 12, 9)
        col.setSpacing(1)
        name = QLabel(session.name.upper())
        name.setObjectName("cardTitle")
        local = session.local()
        when = QLabel(f"{local:%a %H:%M}" if local else f"{session.day:%a %d %b}")
        when.setObjectName("listPrimary" if not done else "dim")
        col.addWidget(name)
        col.addWidget(when)
        return tile

    def _tick(self) -> None:
        race = self._race
        if race is None:
            return
        start = race.start_utc or datetime.combine(race.race_date, datetime.min.time(), tzinfo=timezone.utc)
        remaining = max(0, int((start - datetime.now(timezone.utc)).total_seconds()))
        days, rem = divmod(remaining, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        for label, value in zip(self._countdown_values, (days, hours, minutes, seconds)):
            label.setText(f"{value:02}")

    # ------------------------------------------------------------- tiles
    def _apply_tiles(self, data: dict) -> None:
        drivers = data["drivers"]
        constructors = data["constructors"]
        year = data["standings_year"]
        self._standings_year = year
        if drivers:
            leader = drivers[0]
            gap = ""
            if len(drivers) > 1:
                gap = f"  ·  +{_fmt_points(_to_number(leader.points) - _to_number(drivers[1].points))} to P2"
            self.wdc_tile.set(leader.driver, f"{_fmt_points(leader.points)} pts{gap}", team_color(leader.team))
        else:
            self.wdc_tile.set("—", "No standings yet")
        if constructors:
            leader = constructors[0]
            self.wcc_tile.set(leader.constructor, f"{_fmt_points(leader.points)} pts  ·  {leader.wins} wins", team_color(leader.constructor))
        else:
            self.wcc_tile.set("—", "No standings yet")
        if year != self._year:
            self.wdc_tile.title_label.setText(f"{year} DRIVERS' CHAMPION")
            self.wcc_tile.title_label.setText(f"{year} CONSTRUCTORS' CHAMPION")

        last = data["last"]
        if last and last.results:
            winner = last.results[0]
            self.winner_tile.set(winner.driver, f"{last.name}  ·  {winner.team}", team_color(winner.team))
        else:
            self.winner_tile.set("—", "No races completed yet")

        total = data["total"]
        completed = data["completed"]
        self.progress_tile.set(f"{completed} / {total} races", f"{max(0, total - completed)} rounds remaining" if total else "")
        self.progress_bar.setRange(0, max(1, total))
        self.progress_bar.setValue(completed)

    # ------------------------------------------------------------- lists
    def _apply_lists(self, data: dict) -> None:
        drivers = data["drivers"][:5]
        clear_layout(self.drivers_list)
        if drivers:
            top = _to_number(drivers[0].points) or 1.0
            for s in drivers:
                self.drivers_list.addWidget(
                    self._leader_row(str(s.position), s.driver, s.team, _fmt_points(s.points), team_color(s.team), _to_number(s.points) / top)
                )
        else:
            self._placeholder(self.drivers_list, "No standings available.")

        constructors = data["constructors"][:5]
        clear_layout(self.teams_list)
        if constructors:
            top = _to_number(constructors[0].points) or 1.0
            for s in constructors:
                self.teams_list.addWidget(
                    self._leader_row(str(s.position), s.constructor, f"{s.wins} wins", _fmt_points(s.points), team_color(s.constructor), _to_number(s.points) / top)
                )
        else:
            self._placeholder(self.teams_list, "No standings available.")

        last = data["last"]
        self._last_race = last
        clear_layout(self.podium_list)
        if last and last.results:
            self.podium_title.setText(f"LAST RACE  ·  ROUND {last.round}")
            name = QLabel(last.name)
            name.setObjectName("sectionTitle")
            self.podium_list.addWidget(name)
            for res in last.results[:3]:
                self.podium_list.addWidget(self._podium_row(res))
            fastest = QLabel(f"{len(last.results)} classified entries  ·  {last.circuit}")
            fastest.setObjectName("dim")
            fastest.setWordWrap(True)
            self.podium_list.addWidget(fastest)
            self.podium_link.setVisible(True)
        else:
            self._placeholder(self.podium_list, "No race results yet.")
            self.podium_link.setVisible(False)

    @staticmethod
    def _leader_row(position: str, name: str, sub: str, value: str, color: str, ratio: float) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        pos = QLabel(position)
        pos.setObjectName("positionBadge")
        pos.setFixedWidth(22)
        pos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if position in _PODIUM_COLORS:
            pos.setStyleSheet(f"color: {_PODIUM_COLORS[position]};")
        layout.addWidget(pos)
        layout.addWidget(TeamStripe(color, 4, 34))

        text = QVBoxLayout()
        text.setSpacing(3)
        primary = QLabel(name)
        primary.setObjectName("listPrimary")
        secondary = QLabel(sub)
        secondary.setObjectName("listSecondary")
        text.addWidget(primary)
        bar_row = QHBoxLayout()
        bar_row.setSpacing(8)
        bar_row.addWidget(secondary)
        bar_row.addWidget(PointsBar(ratio, color), 1)
        text.addLayout(bar_row)
        layout.addLayout(text, 1)

        points = QLabel(value)
        points.setObjectName("listValue")
        points.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        points.setMinimumWidth(40)
        layout.addWidget(points)
        return row

    @staticmethod
    def _podium_row(res) -> QWidget:
        row = QFrame()
        row.setObjectName("podiumCard")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 14, 8)
        layout.setSpacing(10)
        pos = QLabel(f"P{res.position}")
        pos.setObjectName("positionBadge")
        pos.setStyleSheet(f"color: {_PODIUM_COLORS.get(res.position, '#8B96A5')};")
        pos.setFixedWidth(30)
        layout.addWidget(pos)
        layout.addWidget(TeamStripe(team_color(res.team), 4, 30))
        text = QVBoxLayout()
        text.setSpacing(0)
        name = QLabel(res.driver)
        name.setObjectName("listPrimary")
        team = QLabel(res.team)
        team.setObjectName("listSecondary")
        text.addWidget(name)
        text.addWidget(team)
        layout.addLayout(text, 1)
        time = QLabel(res.time)
        time.setObjectName("listSecondary")
        layout.addWidget(time)
        return row

    def _open_last_race(self) -> None:
        last = self._last_race
        if last is None:
            return
        year = int(last.date[:4]) if last.date[:4].isdigit() else self._year
        self.controller.open_race(year, last.name)
