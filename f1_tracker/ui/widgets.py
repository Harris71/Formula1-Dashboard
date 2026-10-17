from __future__ import annotations

from typing import Iterable, Optional, Sequence

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QProgressBar,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from f1_tracker.config import (
    BG_DARK,
    BRONZE,
    DANGER,
    GOLD,
    INFO,
    SILVER,
    SUCCESS,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    WARNING,
)
from f1_tracker.teams import team_color

_CHIP_VARIANTS = {
    "default": "chip",
    "accent": "chipAccent",
    "success": "chipSuccess",
    "gold": "chipGold",
    "info": "chipInfo",
    "warning": "chipWarning",
}

# Status text -> (pill colour) for PillDelegate.
PILL_COLORS = {
    "completed": TEXT_DIM,
    "finished": SUCCESS,
    "race day": DANGER,
    "race week": WARNING,
    "next": GOLD,
    "upcoming": INFO,
    "dnf": DANGER,
    "dsq": DANGER,
    "dns": DANGER,
    "lapped": WARNING,
}


def make_title(text: str, sub: str = "", kicker: str = "") -> QWidget:
    """Page header with optional kicker, title + subtitle."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    if kicker:
        kicker_label = QLabel(kicker.upper())
        kicker_label.setObjectName("pageKicker")
        layout.addWidget(kicker_label)
    label = QLabel(text)
    label.setObjectName("pageTitle")
    layout.addWidget(label)
    if sub:
        sub_label = QLabel(sub)
        sub_label.setObjectName("pageSubtitle")
        sub_label.setWordWrap(True)
        layout.addWidget(sub_label)
    return widget


def make_card(layout=None, name: str = "card") -> QFrame:
    card = QFrame()
    card.setObjectName(name)
    if layout is None:
        layout = QVBoxLayout(card)
    else:
        card.setLayout(layout)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(10)
    return card


class StatCard(QFrame):
    """Compact KPI tile: label, big value, optional sub line and colour accent."""

    def __init__(self, title: str, value: str = "—", sub: str = "", accent: Optional[str] = None) -> None:
        super().__init__()
        self.setObjectName("statCard")
        self._accent = accent
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 16, 16)
        layout.setSpacing(4)
        self.title_label = QLabel(title.upper())
        self.title_label.setObjectName("cardTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("valueSmall")
        self.value_label.setWordWrap(True)
        self.sub_label = QLabel(sub)
        self.sub_label.setObjectName("listSecondary")
        self.sub_label.setWordWrap(True)
        self.sub_label.setVisible(bool(sub))
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.sub_label)
        layout.addStretch(1)

    def set(self, value: str, sub: str = "", accent: Optional[str] = None) -> None:
        self.value_label.setText(value)
        self.sub_label.setText(sub)
        self.sub_label.setVisible(bool(sub))
        self._accent = accent
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if not self._accent:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._accent))
        painter.drawRoundedRect(QRectF(8, 16, 4, self.height() - 32), 2, 2)


def make_stat_card(title: str, value: str, sub: str = "", accent: Optional[str] = None) -> StatCard:
    return StatCard(title, value, sub, accent)


def make_chip(text: str, accent: bool = False, variant: str = "default") -> QLabel:
    chip = QLabel(text)
    chip.setObjectName(_CHIP_VARIANTS.get("accent" if accent else variant, "chip"))
    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
    chip.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return chip


def make_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    return line


def make_thin_bar(value: int = 0, maximum: int = 100) -> QProgressBar:
    bar = QProgressBar()
    bar.setObjectName("thinBar")
    bar.setTextVisible(False)
    bar.setRange(0, max(1, maximum))
    bar.setValue(value)
    return bar


class TeamStripe(QWidget):
    """Short vertical team-colour bar used beside driver/team names."""

    def __init__(self, color: str, width: int = 4, height: int = 30) -> None:
        super().__init__()
        self._color = QColor(color)
        self.setFixedSize(width, height)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawRoundedRect(QRectF(self.rect()), 2, 2)


def clear_layout(layout: QLayout) -> None:
    """Detach and delete every widget/sub-layout (see _update_event_card)."""
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


# ---------------------------------------------------------------------------
# Table delegates
# ---------------------------------------------------------------------------
class _BaseDelegate(QStyledItemDelegate):
    def _background(self, painter: QPainter, option, index) -> QStyleOptionViewItem:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget is not None else None
        if style is not None:
            style.drawPrimitive(QStyle.PrimitiveElement.PE_PanelItemViewItem, opt, painter, widget)
        return opt


class TeamDelegate(_BaseDelegate):
    """Paints a team-colour stripe in front of the cell text."""

    def __init__(self, parent=None, color_column: Optional[int] = None) -> None:
        super().__init__(parent)
        self._color_column = color_column

    def paint(self, painter: QPainter, option, index) -> None:
        opt = self._background(painter, option, index)
        source = index if self._color_column is None else index.siblingAtColumn(self._color_column)
        color = QColor(team_color(source.data() or ""))
        rect = opt.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        bar_h = max(10, rect.height() - 18)
        painter.drawRoundedRect(QRectF(rect.left() + 8, rect.center().y() - bar_h / 2 + 1, 4, bar_h), 2, 2)
        painter.setPen(QColor(TEXT))
        font = QFont(opt.font)
        painter.setFont(font)
        text_rect = rect.adjusted(22, 0, -6, 0)
        text = painter.fontMetrics().elidedText(opt.text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), text)
        painter.restore()


class PositionDelegate(_BaseDelegate):
    """Gold / silver / bronze badges for the podium, bold numerals otherwise."""

    _PODIUM = {1: GOLD, 2: SILVER, 3: BRONZE}

    def paint(self, painter: QPainter, option, index) -> None:
        opt = self._background(painter, option, index)
        value = index.data()
        try:
            position = int(value)
        except (TypeError, ValueError):
            position = None
        rect = opt.rect
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(opt.font)
        font.setBold(True)
        painter.setFont(font)
        if position in self._PODIUM:
            badge = QRectF(rect.center().x() - 14, rect.center().y() - 11, 28, 22)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._PODIUM[position]))
            painter.drawRoundedRect(badge, 6, 6)
            painter.setPen(QColor(BG_DARK))
            painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), str(position))
        else:
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "" if value is None else str(value))
        painter.restore()


class PillDelegate(_BaseDelegate):
    """Status text rendered as a coloured pill."""

    def __init__(self, parent=None, colors: Optional[dict[str, str]] = None) -> None:
        super().__init__(parent)
        self._colors = colors or PILL_COLORS

    def paint(self, painter: QPainter, option, index) -> None:
        opt = self._background(painter, option, index)
        text = str(index.data() or "")
        if not text:
            return
        lowered = text.lower()
        color = QColor(self._colors.get(lowered, TEXT_MUTED))
        for key, value in self._colors.items():
            if lowered.startswith(key):
                color = QColor(value)
                break
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(opt.font)
        font.setBold(True)
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
        painter.setFont(font)
        label = text.upper()
        width = painter.fontMetrics().horizontalAdvance(label) + 20
        rect = opt.rect
        pill = QRectF(rect.center().x() - width / 2, rect.center().y() - 11, width, 22)
        fill = QColor(color)
        fill.setAlpha(38)
        border = QColor(color)
        border.setAlpha(110)
        painter.setPen(border)
        painter.setBrush(fill)
        painter.drawRoundedRect(pill, 11, 11)
        painter.setPen(color)
        painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), label)
        painter.restore()


def _make_cell(text, *, bold: bool = False, color: Optional[str] = None, align: Qt.AlignmentFlag | None = None) -> QTableWidgetItem:
    is_number = isinstance(text, (int, float)) and not isinstance(text, bool)
    item = QTableWidgetItem()
    if is_number:
        item.setData(Qt.ItemDataRole.DisplayRole, text)  # numeric sort data
    else:
        item.setText("" if text is None else str(text))
    if align is None:
        align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
    item.setTextAlignment(align)
    if bold:
        font = QFont()
        font.setBold(True)
        item.setFont(font)
    if color:
        item.setForeground(QBrush(QColor(color)))
    return item


class F1Table(QTableWidget):
    """Dark themed, sortable table with native filtering support.

    ``podium`` badges column 0 as a finishing position; ``team_columns`` paint
    a livery stripe (optionally coloured from another column, e.g. a driver
    name coloured by their team); ``pill_columns`` render status pills;
    ``bold_columns`` emphasise key values such as points.
    """

    ROW_HEIGHT = 42

    def __init__(
        self,
        columns: Sequence[tuple[str, int, Optional[Qt.AlignmentFlag]]],
        *,
        podium: bool = True,
        team_columns: Optional[dict[int, Optional[int]]] = None,
        pill_columns: Sequence[int] = (),
        bold_columns: Sequence[int] = (),
        stretch_column: Optional[int] = None,
    ) -> None:
        super().__init__(0, len(columns))
        self._columns = columns
        self._bold = set(bold_columns)
        self._delegates: list[QStyledItemDelegate] = []
        self.setHorizontalHeaderLabels([c[0].upper() for c in columns])

        header = self.horizontalHeader()
        for col, (_, width, _) in enumerate(columns):
            if width >= 0:
                self.setColumnWidth(col, width)
        if stretch_column is None:
            header.setStretchLastSection(True)
        else:
            header.setSectionResizeMode(stretch_column, header.ResizeMode.Stretch)
        header.setSectionsClickable(True)
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col, (_, _, align) in enumerate(columns):
            item = self.horizontalHeaderItem(col)
            if item is not None and align is not None:
                item.setTextAlignment(align)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(self.ROW_HEIGHT)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        self.setSortingEnabled(True)
        header.setSortIndicatorShown(True)
        header.setSortIndicator(0, Qt.SortOrder.AscendingOrder)

        if podium:
            self._use(0, PositionDelegate(self))
        for col, color_col in (team_columns or {}).items():
            self._use(col, TeamDelegate(self, color_col))
        for col in pill_columns:
            self._use(col, PillDelegate(self))

    def _use(self, column: int, delegate: QStyledItemDelegate) -> None:
        self._delegates.append(delegate)  # Qt does not take ownership
        self.setItemDelegateForColumn(column, delegate)

    def fill(self, rows: Iterable[Sequence]) -> None:
        self.setSortingEnabled(False)
        self.setRowCount(0)
        for values in rows:
            row = self.rowCount()
            self.insertRow(row)
            for col, value in enumerate(values):
                item = _make_cell(value, bold=col in self._bold, align=self._columns[col][2])
                self.setItem(row, col, item)
        self.setSortingEnabled(True)

    def filter_rows(self, search: str) -> None:
        search = search.strip().lower()
        for row in range(self.rowCount()):
            haystack = " ".join(
                (self.item(row, col).text() if self.item(row, col) else "")
                for col in range(self.columnCount())
            ).lower()
            self.setRowHidden(row, not (search in haystack if search else True))


def time_formatted(value) -> str:
    if value is None:
        return "-"
    seconds = _to_seconds(value)
    if seconds is None or seconds != seconds:  # NaN guard
        return "-"
    total_ms = int(round(seconds * 1000))
    minutes, rem = divmod(total_ms, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{minutes:02}:{secs:02}.{ms:03}"


def _to_seconds(value) -> float | None:
    if hasattr(value, "total_seconds"):  # datetime.timedelta, pd.Timedelta
        try:
            return float(value.total_seconds())
        except Exception:
            return None
    if type(value).__name__ == "timedelta64":  # numpy scalar
        try:
            np = __import__("numpy")
            return float(value / np.timedelta64(1, "s"))
        except Exception:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def make_dialog_frame() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 20, 20, 20)
    layout.setSpacing(10)
    return frame, layout


def hbox(*widgets, spacing: int = 10) -> QWidget:
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for w in widgets:
        if w is not None:
            layout.addWidget(w)
    layout.addStretch(1)
    return widget


def vbox(*widgets, spacing: int = 10) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for w in widgets:
        if w is not None:
            layout.addWidget(w)
    layout.addStretch(1)
    return widget
