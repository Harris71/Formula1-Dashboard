from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure


class PlotCanvas:
    """Lazily-imported wrapper so matplotlib never loads at app startup."""

    _Canvas = None

    def __new__(cls, figure, parent=None):
        if cls._Canvas is None:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg

            cls._Canvas = FigureCanvasQTAgg
        canvas = cls._Canvas(figure)
        canvas.setMinimumSize(480, 320)
        return canvas


class PlotViewer(QDialog):
    """Frameless-ish dark dialog that hosts a matplotlib figure with save/close."""

    def __init__(self, figure: "Figure", title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(960, available.width() - 60), min(680, available.height() - 110))
        else:
            self.resize(960, 680)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        header.addWidget(title_label)
        header.addStretch(1)

        save_button = QPushButton("Save PNG")
        save_button.setObjectName("ghost")
        save_button.clicked.connect(self._save_png)
        close_button = QPushButton("Close")
        close_button.setObjectName("primary")
        close_button.clicked.connect(self.accept)
        header.addWidget(save_button)
        header.addWidget(close_button)
        layout.addLayout(header)

        self._figure = figure
        self._canvas = PlotCanvas(figure, self)
        layout.addWidget(self._canvas, 1)

    def _save_png(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        default = "".join(c if c.isalnum() else "_" for c in self.windowTitle()).strip("_").lower() or "race_plot"
        path, _ = QFileDialog.getSaveFileName(self, "Save chart", f"{default}.png", "PNG image (*.png)")
        if path:
            self._figure.savefig(path, dpi=160, facecolor=self._figure.get_facecolor())