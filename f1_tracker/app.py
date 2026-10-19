from __future__ import annotations

import time

from datetime import date, datetime, timezone

from PyQt6.QtCore import QEvent, QSize, Qt, QThreadPool, QTimer
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from f1_tracker.config import APP_TITLE, CACHE_DIR, MIN_WINDOW_SIZE, VERSION, WINDOW_SIZE
from f1_tracker.services.schedule import fetch_schedule, next_race
from f1_tracker.services.sessions import load_f1_session
from f1_tracker.ui.pages.calendar import CalendarPage
from f1_tracker.ui.pages.home import HomePage
from f1_tracker.ui.pages.race_sessions import RaceSessionsPage
from f1_tracker.ui import theme
from f1_tracker.ui.icons import BrandMark, app_icon, nav_icon
from f1_tracker.ui.pages.standings import StandingsPage
from f1_tracker.ui.workers import Worker


_HISTORY_LIMIT = 50


class F1App(QMainWindow):
    """Modern PyQt6 F1 dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(*MIN_WINDOW_SIZE)
        self._fit_to_screen()
        self.setWindowIcon(app_icon())

        self.race_session = None
        self.quali_session = None
        self._schedule_cache: dict[int, list] = {}
        self._schedule_worker = Worker()
        self._schedule_pending: dict[int, list] = {}
        self._nav_buttons: list[QPushButton] = []
        self._nav_keys: list[str] = []
        # Where the user has been, as (page key, tab index or None); back_button
        # walks it. _current is the entry on screen, so it is never in _history.
        self._history: list[tuple[str, int | None]] = []
        self._current: tuple[str, int | None] | None = None
        self._restoring = False

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = self._build_sidebar()
        layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self._pages: dict[str, QWidget] = {}
        self._containers: dict[str, QWidget] = {}
        self._register("home", HomePage(self), "Home", scroll=False)  # scrolls itself
        self._register("race", RaceSessionsPage(self), "Race Sessions")
        self._register("standings", StandingsPage(self), "Standings")
        self._register("calendar", CalendarPage(self), "Season Calendar")

        self._install_shortcuts()
        self.navigate("home")

        self._sidebar_race = None
        self._sidebar_timer = QTimer(self)
        self._sidebar_timer.setInterval(1000)
        self._sidebar_timer.timeout.connect(self._tick_sidebar)
        self.load_schedule_async(date.today().year, self._on_sidebar_schedule)

    def closeEvent(self, event) -> None:
        # Finish in-flight fetches while the event loop is still live so their
        # queued GUI callbacks get delivered safely instead of aborting Qt at
        # interpreter shutdown.
        pool = QThreadPool.globalInstance()
        pool.clear()
        deadline = time.monotonic() + 15
        while not pool.waitForDone(0):
            QApplication.processEvents()
            if time.monotonic() > deadline:
                break
        event.accept()

    # ------------------------------------------------------------------ chrome
    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(248)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 18)
        layout.setSpacing(6)

        layout.addWidget(BrandMark(theme.ACTIVE_FONT))

        subtitle = QLabel("FORMULA ONE COMPANION")
        subtitle.setObjectName("brandSubtitle")
        subtitle.setContentsMargins(2, 0, 0, 0)
        layout.addWidget(subtitle)

        layout.addSpacing(28)
        menu_row = QHBoxLayout()
        menu_row.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("MENU")
        heading.setObjectName("navHeading")
        menu_row.addWidget(heading)
        menu_row.addStretch(1)
        self.back_button = QPushButton("←  Back")
        self.back_button.setObjectName("linkButton")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.setToolTip("Back to the previous page or tab  (Alt+Left)")
        self.back_button.setEnabled(False)
        self.back_button.clicked.connect(self.go_back)
        menu_row.addWidget(self.back_button)
        layout.addLayout(menu_row)
        layout.addSpacing(4)

        self._nav_container = QVBoxLayout()
        self._nav_container.setSpacing(4)
        layout.addLayout(self._nav_container)
        layout.addStretch(1)

        layout.addWidget(self._build_next_race_widget())
        layout.addSpacing(10)

        footer = QLabel(f"v{VERSION}  ·  Data: Jolpica-F1 & FastF1")
        footer.setObjectName("sidebarFooter")
        footer.setContentsMargins(4, 0, 0, 0)
        layout.addWidget(footer)
        return sidebar

    def _build_next_race_widget(self) -> QFrame:
        card = QFrame()
        card.setObjectName("sidebarCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda _event: self.navigate("calendar")
        col = QVBoxLayout(card)
        col.setContentsMargins(14, 12, 14, 12)
        col.setSpacing(2)
        title = QLabel("NEXT RACE")
        title.setObjectName("sidebarCardTitle")
        col.addWidget(title)
        self._sidebar_name = QLabel("Loading calendar…")
        self._sidebar_name.setObjectName("sidebarCardValue")
        self._sidebar_name.setWordWrap(True)
        col.addWidget(self._sidebar_name)
        self._sidebar_countdown = QLabel("")
        self._sidebar_countdown.setObjectName("sidebarCardCountdown")
        col.addWidget(self._sidebar_countdown)
        self._sidebar_card = card
        return card

    def _on_sidebar_schedule(self, schedule: list) -> None:
        race = next_race(schedule)
        if race is None and schedule and schedule[0].race_date.year == date.today().year:
            # Season finished: look ahead to next year's opener.
            self.load_schedule_async(date.today().year + 1, self._on_sidebar_schedule)
            return
        self._sidebar_race = race
        if race is None:
            self._sidebar_name.setText("Calendar unavailable")
            self._sidebar_countdown.setText("")
            return
        self._sidebar_name.setText(race.name.replace("Grand Prix", "GP"))
        self._tick_sidebar()
        self._sidebar_timer.start()

    def _tick_sidebar(self) -> None:
        race = self._sidebar_race
        if race is None:
            return
        start = race.start_utc or datetime.combine(race.race_date, datetime.min.time(), tzinfo=timezone.utc)
        remaining = int((start - datetime.now(timezone.utc)).total_seconds())
        if remaining <= 0:
            self._sidebar_countdown.setText("LIGHTS OUT" if remaining > -7200 else "")
            return
        days, rem = divmod(remaining, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        if days:
            self._sidebar_countdown.setText(f"{days}d {hours:02}h {minutes:02}m")
        else:
            self._sidebar_countdown.setText(f"{hours:02}:{minutes:02}:{seconds:02}")

    def _install_shortcuts(self) -> None:
        for index, key in enumerate(self._nav_keys, start=1):
            shortcut = QShortcut(QKeySequence(f"Ctrl+{index}"), self)
            shortcut.activated.connect(lambda k=key: self.navigate(k))
        refresh = QShortcut(QKeySequence("F5"), self)
        refresh.activated.connect(self._refresh_current)
        back = QShortcut(QKeySequence("Alt+Left"), self)
        back.activated.connect(self.go_back)

    def _refresh_current(self) -> None:
        current = self.stack.currentWidget()
        page = next((p for k, p in self._pages.items() if self._containers[k] is current), None)
        if hasattr(page, "refresh"):
            page.refresh()

    def _fit_to_screen(self) -> None:
        """Default size, shrunk to fit small displays (e.g. 1366x768 laptops)."""
        screen = QApplication.primaryScreen()
        width, height = WINDOW_SIZE
        if screen is not None:
            available = screen.availableGeometry()
            # Leave room for window decorations and desktop panels, which
            # Wayland does not subtract from availableGeometry().
            width = min(width, available.width() - 40)
            height = min(height, available.height() - 90)
        self.resize(max(width, MIN_WINDOW_SIZE[0]), max(height, MIN_WINDOW_SIZE[1]))

    def prefers_maximized(self) -> bool:
        screen = QApplication.primaryScreen()
        if screen is None:
            return False
        available = screen.availableGeometry()
        return available.width() < WINDOW_SIZE[0] + 80 or available.height() < WINDOW_SIZE[1] + 90

    def _register(self, key: str, page: QWidget, label: str, scroll: bool = True) -> None:
        self._pages[key] = page
        container = page
        if scroll:
            # On short screens pages scroll instead of forcing the window to
            # grow past the display (which also blocks maximising it).
            container = QScrollArea()
            container.setWidgetResizable(True)
            container.setFrameShape(QFrame.Shape.NoFrame)
            container.setWidget(page)
            page.setAutoFillBackground(False)  # setWidget() turns this on
        self._containers[key] = container
        self.stack.addWidget(container)

        button = QPushButton(f"  {label}")
        button.setObjectName("navButton")
        button.setIcon(nav_icon(key))
        button.setIconSize(QSize(20, 20))
        button.setToolTip(f"{label}  (Ctrl+{len(self._nav_keys) + 1})")
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda _=False, k=key: self.navigate(k))
        self._nav_buttons.append(button)
        self._nav_keys.append(key)
        self._nav_container.addWidget(button)

        tabs = getattr(page, "tabs", None)
        if tabs is not None:
            tabs.currentChanged.connect(lambda index, k=key: self._on_tab_changed(k, index))
            # A tab bar switches tabs on the mouse wheel, so scrolling a long page
            # past it flipped tabs; pass the wheel on to the page instead.
            tabs.tabBar().installEventFilter(self)

    # ------------------------------------------------------------------ nav
    def navigate(self, key: str) -> None:
        if key not in self._pages:
            return
        self._show(key)
        if not self._restoring:
            self._record((key, self._page_tab(key)))

    def _page_tab(self, key: str) -> int | None:
        tabs = getattr(self._pages[key], "tabs", None)
        return tabs.currentIndex() if tabs is not None else None

    def _record(self, state: tuple[str, int | None]) -> None:
        if state == self._current:
            return
        if self._current is not None:
            self._history.append(self._current)
            del self._history[:-_HISTORY_LIMIT]
        self._current = state
        self.back_button.setEnabled(bool(self._history))

    def _on_tab_changed(self, key: str, index: int) -> None:
        # Only tab changes the user makes on the page they are looking at count;
        # a tab preset on a page that is not shown yet is recorded on arrival.
        if self._restoring or self._current is None or self._current[0] != key:
            return
        self._record((key, index))

    def go_back(self) -> None:
        """Return to the previous page, and the tab it was on."""
        while self._history:
            key, tab = self._history.pop()
            tabs = getattr(self._pages[key], "tabs", None)
            if tabs is not None and tab is not None and not tabs.isTabVisible(tab):
                continue  # a tab that no longer applies (e.g. Sprint Results on a normal weekend)
            if (key, tab) == self._current:
                continue  # already here; a Back press must visibly go somewhere
            self._current = (key, tab)
            self._restoring = True
            try:
                self._show(key)
                if tabs is not None and tab is not None:
                    tabs.setCurrentIndex(tab)
            finally:
                self._restoring = False
            break
        self.back_button.setEnabled(bool(self._history))

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and isinstance(obj, QTabBar):
            area = obj.parentWidget()
            while area is not None and not isinstance(area, QScrollArea):
                area = area.parentWidget()
            if area is not None:
                QApplication.sendEvent(area.viewport(), event)
            else:
                event.ignore()  # nothing to scroll here: let a parent have it, never switch tabs
            return True  # sideways wheel too: a tab bar has nothing to scroll sideways
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.BackButton:  # the mouse's back thumb button
            self.go_back()
            return
        super().mousePressEvent(event)

    def _show(self, key: str) -> None:
        self.stack.setCurrentWidget(self._containers[key])
        index = self._nav_keys.index(key)
        for i, button in enumerate(self._nav_buttons):
            button.setChecked(i == index)
        page = self._pages[key]
        if hasattr(page, "on_show"):
            page.on_show()

    def open_race(self, year: int, grand_prix: str) -> None:
        """Jump to Race Sessions with a round preselected (e.g. from the calendar)."""
        page = self._pages.get("race")
        if page is not None and hasattr(page, "preset"):
            page.preset(year, grand_prix)
        self.navigate("race")

    def open_standings(self, year: int, kind: str = "drivers") -> None:
        """Jump to Standings for a season, on the drivers' or constructors' tab."""
        page = self._pages.get("standings")
        if page is not None and hasattr(page, "preset"):
            page.preset(year, kind)
        self.navigate("standings")

    # ------------------------------------------------------------------ data
    def get_schedule(self, year: int) -> list:
        """Blocking calendar lookup. Only call from a worker thread."""
        if year not in self._schedule_cache:
            try:
                schedule = fetch_schedule(year)
            except Exception:
                return []  # don't memoise failures; the next call retries
            if schedule:
                self._schedule_cache[year] = schedule
            return schedule
        return self._schedule_cache[year]

    def load_schedule_async(self, year: int, on_done) -> None:
        """Fetch a season calendar off the GUI thread (safe to call from __init__)."""
        if year in self._schedule_cache:
            on_done(self._schedule_cache[year])
            return
        if year in self._schedule_pending:
            self._schedule_pending[year].append(on_done)
            return

        self._schedule_pending[year] = [on_done]

        def work() -> list:
            return fetch_schedule(year)

        def finished(results) -> None:
            if results:
                self._schedule_cache[year] = results
            for callback in self._schedule_pending.pop(year, []):
                callback(results)

        def failed(_exc: Exception) -> None:
            for callback in self._schedule_pending.pop(year, []):
                callback([])

        self._schedule_worker.run(
            work,
            on_done=finished,
            on_error=failed,
        )

    def load_session(self, year: int, grand_prix: str, session_type: str):
        """Load a FastF1 session (blocking — call via a Worker off the UI thread)."""
        return load_f1_session(year, grand_prix, session_type, CACHE_DIR)