from __future__ import annotations

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from f1_tracker.config import TEXT_DIM
from f1_tracker.ui.widgets import clear_layout, make_card, make_chip

# Frames skipped per timer tick per speed step. A tick is 33 ms and each frame
# is 0.5 s of race time, so at 1x the race runs at a readable minimap pace.
_TICK_MS = 33
_FRAMES_PER_TICK = 1.6
_SPEEDS = ("0.25×", "0.5×", "1×", "2×", "4×", "8×")


class _LeaderboardTable(QTableWidget):
    """Compact live leaderboard: fixed Pos/Gap columns, Driver takes the rest,
    and the rows shrink to fit the height so a full grid needs no scrolling."""

    _GRID = 20  # a full modern grid; keeps row height steady as cars appear
    _MIN_ROW, _MAX_ROW = 18, 30
    _POS_WIDTH, _GAP_WIDTH = 40, 68

    def __init__(self) -> None:
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(["POS", "DRIVER", "GAP"])
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalHeader().setVisible(False)
        self.setStyleSheet(
            "QTableWidget { background: transparent; border: none; }"
            "QHeaderView::section { padding: 6px 4px; }"
            "QTableWidget::item { padding: 0px 4px; }"
            "QTableWidget::item:hover { background: transparent; }"  # rows re-order live; no hover tint
        )
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.setColumnWidth(0, self._POS_WIDTH)
        self.setColumnWidth(2, self._GAP_WIDTH)
        for column, align in enumerate((Qt.AlignmentFlag.AlignCenter, Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight)):
            self.horizontalHeaderItem(column).setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.setShowGrid(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)  # one size for every row
        self.verticalHeader().setMinimumSectionSize(self._MIN_ROW)  # Qt's default floor is higher
        self.verticalHeader().setDefaultSectionSize(self._MAX_ROW)

    @property
    def text_px(self) -> int:
        """Text size that fits the current row height (13px at normal sizes)."""
        return max(11, min(13, self.verticalHeader().defaultSectionSize() - 7))

    def fit_rows(self) -> None:
        # Measure from the widget, not the viewport: during a resize the
        # viewport still has its old height.
        available = self.height() - self.horizontalHeader().height() - 2 * self.frameWidth()
        size = max(self._MIN_ROW, min(self._MAX_ROW, available // max(self.rowCount(), self._GRID)))
        if self.verticalHeader().defaultSectionSize() != size:
            self.verticalHeader().setDefaultSectionSize(size)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.fit_rows()


class LapProgressionPanel(QWidget):
    """Minimap race replay with a live leaderboard.

    Holds no loader of its own: the Race Sessions page builds a ProgressMap
    from its already-loaded race session and hands it over via show_map().
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.map = None
        self.canvas = None
        self._frame = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._advance)
        self._build()

    # -------------------------------------------------------------- UI
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 10, 0, 0)
        root.setSpacing(10)

        middle = QHBoxLayout()
        middle.setSpacing(12)

        self.canvas_holder = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_holder)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_card = make_card()
        canvas_card.layout().setContentsMargins(6, 6, 6, 6)
        canvas_card.layout().addWidget(self.canvas_holder)
        middle.addWidget(canvas_card, 1)

        standings_card = make_card()
        standings_card.setFixedWidth(230)
        standings_card.layout().setContentsMargins(14, 14, 14, 10)
        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(make_chip("LIVE", accent=True))
        standings_label = QLabel("LEADERBOARD")
        standings_label.setObjectName("cardTitle")
        header.addWidget(standings_label)
        header.addStretch(1)
        standings_card.layout().addLayout(header)

        self.standings_table = _LeaderboardTable()
        standings_card.layout().addWidget(self.standings_table, 1)
        middle.addWidget(standings_card)
        root.addLayout(middle, 1)

        transport = QHBoxLayout()
        transport.setSpacing(10)

        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("primary")
        self.play_button.setFixedWidth(90)
        self.play_button.clicked.connect(self._toggle_play)
        transport.addWidget(self.play_button)

        self.reset_button = QPushButton("Restart")
        self.reset_button.setObjectName("ghost")
        self.reset_button.clicked.connect(self._reset)
        transport.addWidget(self.reset_button)

        self.speed_combo = QComboBox()
        for speed in _SPEEDS:
            self.speed_combo.addItem(speed)
        self.speed_combo.setCurrentIndex(2)
        self.speed_combo.setToolTip("Playback speed")
        transport.addWidget(self.speed_combo)

        self.frame_slider = QSlider(Qt.Orientation.Horizontal)
        self.frame_slider.sliderMoved.connect(self._seek)
        transport.addWidget(self.frame_slider, 1)

        self.lap_label = QLabel("")
        self.lap_label.setObjectName("heroInfo")
        self.lap_label.setMinimumWidth(130)
        self.lap_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        transport.addWidget(self.lap_label)
        root.addLayout(transport)

        self.show_message("Load a race session to replay it here.")

        # The map, leaderboard, slider and speed box would each keep the mouse
        # wheel; pass it to the page so it scrolls from anywhere over the replay.
        for widget in (
            self.standings_table, self.standings_table.viewport(), self.frame_slider, self.speed_combo,
            self.standings_table.verticalScrollBar(), self.play_button, self.reset_button, self.lap_label,
        ):
            widget.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Wheel and not (event.angleDelta().x() and not event.angleDelta().y()):
            # (sideways-only wheel stays with the widget, as in the results tables)
            area = self._page_scroll_area()
            if area is not None:
                QApplication.sendEvent(area.viewport(), event)
                return True
        return super().eventFilter(obj, event)

    def _page_scroll_area(self) -> QScrollArea | None:
        parent = self.parentWidget()
        while parent is not None and not isinstance(parent, QScrollArea):
            parent = parent.parentWidget()
        return parent

    # ------------------------------------------------------------ state
    def show_message(self, text: str) -> None:
        """Clear any replay and show a centred message instead."""
        self.pause()
        self.map = None
        self.canvas = None
        clear_layout(self.canvas_layout)
        label = QLabel(text)
        label.setObjectName("emptyState")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        self.canvas_layout.addWidget(label)
        self.standings_table.setRowCount(0)
        self.lap_label.setText("")
        self._set_controls_enabled(False)

    def show_map(self, progress) -> None:
        """Install a ProgressMap built on a worker thread (GUI thread only)."""
        self.pause()
        self.map = progress
        self._install_canvas(progress.build_figure())
        self.frame_slider.setRange(0, len(progress.frames) - 1)
        self.frame_slider.setValue(0)
        self._set_controls_enabled(True)
        self._frame = 0.0
        progress.render(0)
        self._sync_readouts(0)
        self.canvas.draw_idle()
        self.play_button.setText("Play")

    def pause(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
            self.play_button.setText("Play")

    def hideEvent(self, event) -> None:  # noqa: N802
        # Switching tab or page stops playback instead of burning CPU unseen.
        self.pause()
        super().hideEvent(event)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.play_button, self.reset_button, self.speed_combo, self.frame_slider):
            widget.setEnabled(enabled)

    # -------------------------------------------------------- animation
    def _install_canvas(self, figure) -> None:
        """Create the matplotlib canvas on the GUI thread and embed it."""
        clear_layout(self.canvas_layout)
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

        self.canvas = FigureCanvasQTAgg(figure)
        self.canvas.installEventFilter(self)
        self.canvas.setMinimumSize(320, 240)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.canvas_layout.addWidget(self.canvas)

    def _toggle_play(self) -> None:
        if self.map is None:
            return
        if self._timer.isActive():
            self.pause()
            return
        if int(self._frame) >= len(self.map.frames) - 1:
            self._frame = 0.0
        self.play_button.setText("Pause")
        self._timer.start()

    def _advance(self) -> None:
        if self.map is None or self.canvas is None:
            self._timer.stop()
            return
        speed = float(self.speed_combo.currentText().replace("×", ""))
        self._frame += speed * _FRAMES_PER_TICK
        last = len(self.map.frames) - 1
        if int(self._frame) >= last:
            self._frame = float(last)
            self._timer.stop()
            self.play_button.setText("Replay")
        frame = int(self._frame)
        self.map.render(frame)
        self.frame_slider.setValue(frame)
        self._sync_readouts(frame)
        self.canvas.draw_idle()

    def _seek(self, value: int) -> None:
        self.pause()
        if self.map is None:
            return
        self._frame = float(value)
        self.map.render(value)
        self._sync_readouts(value)
        self.canvas.draw_idle()

    def _reset(self) -> None:
        self.pause()
        if self.map is None:
            return
        self._frame = 0.0
        self.frame_slider.setValue(0)
        self.map.render(0)
        self._sync_readouts(0)
        self.canvas.draw_idle()

    def _sync_readouts(self, frame: int) -> None:
        if self.map is None:
            return
        t = int(float(self.map.frames[frame]) - self.map.start)
        minutes, rem = divmod(t, 60)
        lap = self.map.last_lap or 0
        self.lap_label.setText(f"Lap {lap}/{self.map.total_laps} · {minutes:02}:{rem:02}")
        self._update_standings()

    def _update_standings(self) -> None:
        entries = self.map.standings if self.map is not None else []
        table = self.standings_table
        table.setRowCount(len(entries))
        table.fit_rows()
        for row, (code, color, finished, leader, lap, gap) in enumerate(entries):
            pos_item = QTableWidgetItem(str(row + 1))
            pos_font = QFont()
            pos_font.setPixelSize(table.text_px)
            pos_item.setFont(pos_font)
            pos_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code_item = QTableWidgetItem(code)
            font = QFont()
            font.setBold(True)
            font.setPixelSize(table.text_px + (1 if leader else 0))
            code_item.setFont(font)
            code_item.setForeground(QBrush(QColor(TEXT_DIM if finished and not leader else color)))
            gap_item = QTableWidgetItem(gap)
            gap_font = QFont()
            gap_font.setPixelSize(table.text_px)
            gap_item.setFont(gap_font)
            gap_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            gap_item.setForeground(QBrush(QColor(TEXT_DIM)))
            table.setItem(row, 0, pos_item)
            table.setItem(row, 1, code_item)
            table.setItem(row, 2, gap_item)
