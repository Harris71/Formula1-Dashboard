from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QWidget

from f1_tracker.config import ACCENT, ACCENT_HOVER, TEXT, TEXT_MUTED

# Icons are drawn on a 64x64 canvas and scaled down, so strokes stay crisp.
_CANVAS = 64


def _pen(color: QColor, width: float = 5.0) -> QPen:
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _draw_home(p: QPainter, c: QColor) -> None:
    p.setPen(_pen(c))
    p.drawPolyline(QPolygonF([QPointF(10, 30), QPointF(32, 11), QPointF(54, 30)]))
    p.drawPolyline(QPolygonF([QPointF(16, 26), QPointF(16, 53), QPointF(48, 53), QPointF(48, 26)]))
    p.drawLine(QPointF(27, 53), QPointF(27, 39))
    p.drawLine(QPointF(27, 39), QPointF(37, 39))
    p.drawLine(QPointF(37, 39), QPointF(37, 53))


def _draw_flag(p: QPainter, c: QColor) -> None:
    p.setPen(_pen(c))
    p.drawLine(QPointF(14, 8), QPointF(14, 58))
    p.drawRect(QRectF(14, 10, 38, 26))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    cell = 38 / 4
    for row in range(3):
        for col in range(4):
            if (row + col) % 2 == 0:
                p.drawRect(QRectF(14 + col * cell, 10 + row * (26 / 3), cell, 26 / 3))


def _draw_trophy(p: QPainter, c: QColor) -> None:
    p.setPen(_pen(c))
    cup = QPainterPath(QPointF(18, 10))
    cup.lineTo(46, 10)
    cup.lineTo(46, 24)
    cup.cubicTo(QPointF(46, 34), QPointF(39, 40), QPointF(32, 40))
    cup.cubicTo(QPointF(25, 40), QPointF(18, 34), QPointF(18, 24))
    cup.closeSubpath()
    p.drawPath(cup)
    p.drawArc(QRectF(6, 13, 14, 14), 90 * 16, 180 * 16)
    p.drawArc(QRectF(44, 13, 14, 14), -90 * 16, 180 * 16)
    p.drawLine(QPointF(32, 40), QPointF(32, 48))
    p.drawLine(QPointF(20, 54), QPointF(44, 54))
    p.drawLine(QPointF(24, 48), QPointF(40, 48))


def _draw_calendar(p: QPainter, c: QColor) -> None:
    p.setPen(_pen(c))
    p.drawRoundedRect(QRectF(10, 14, 44, 42), 6, 6)
    p.drawLine(QPointF(10, 26), QPointF(54, 26))
    p.drawLine(QPointF(22, 8), QPointF(22, 18))
    p.drawLine(QPointF(42, 8), QPointF(42, 18))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c)
    for x in (20, 32, 44):
        for y in (36, 47):
            p.drawEllipse(QPointF(x, y), 3, 3)


_DRAWERS = {
    "home": _draw_home,
    "race": _draw_flag,
    "standings": _draw_trophy,
    "calendar": _draw_calendar,
}


def _pixmap(name: str, color: str, size: int) -> QPixmap:
    ratio = 2.0
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / _CANVAS, size / _CANVAS)
    _DRAWERS[name](painter, QColor(color))
    painter.end()
    return pixmap


def nav_icon(name: str, size: int = 20) -> QIcon:
    """Muted icon that turns white (and red-tinted) when the nav item is active."""
    icon = QIcon()
    if name not in _DRAWERS:
        return icon
    icon.addPixmap(_pixmap(name, TEXT_MUTED, size), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_pixmap(name, TEXT, size), QIcon.Mode.Active, QIcon.State.Off)
    icon.addPixmap(_pixmap(name, ACCENT_HOVER, size), QIcon.Mode.Normal, QIcon.State.On)
    icon.addPixmap(_pixmap(name, ACCENT_HOVER, size), QIcon.Mode.Active, QIcon.State.On)
    return icon


def _paint_mark(painter: QPainter, rect: QRectF) -> None:
    """Three forward-leaning speed stripes — the app's brand mark."""
    w, h = rect.width(), rect.height()
    slant = w * 0.32
    stripe = w * 0.2
    gap = w * 0.07
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0, QColor(ACCENT_HOVER))
    gradient.setColorAt(1, QColor("#A00400"))
    for i in range(3):
        x = rect.left() + i * (stripe + gap)
        top = rect.top() + h * (0.08 * i)
        poly = QPolygonF([
            QPointF(x + slant, top),
            QPointF(x + slant + stripe, top),
            QPointF(x + stripe, rect.bottom()),
            QPointF(x, rect.bottom()),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient) if i < 2 else QColor(TEXT))
        painter.drawPolygon(poly)


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#12161E"))
        painter.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        inset = size * 0.2
        _paint_mark(painter, QRectF(inset, inset * 1.1, size - inset * 2, size - inset * 2.2))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


class BrandMark(QWidget):
    """Sidebar logo: speed-stripe mark + wordmark."""

    def __init__(self, font_family: str) -> None:
        super().__init__()
        self._family = font_family
        self.setFixedHeight(40)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        _paint_mark(painter, QRectF(2, 8, 34, 24))

        font = QFont(self._family)
        font.setPixelSize(24)
        font.setWeight(QFont.Weight.Black)
        font.setItalic(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        painter.drawText(QRectF(46, 0, self.width() - 46, self.height()), int(Qt.AlignmentFlag.AlignVCenter), "F1")
        offset = 46 + painter.fontMetrics().horizontalAdvance("F1 ")

        font.setWeight(QFont.Weight.Bold)
        font.setItalic(False)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.5)
        font.setPixelSize(17)
        painter.setFont(font)
        painter.setPen(QColor(ACCENT))
        painter.drawText(QRectF(offset, 2, self.width() - offset, self.height()), int(Qt.AlignmentFlag.AlignVCenter), "TRACKER")
