from __future__ import annotations

import traceback

from PyQt6.QtWidgets import QMessageBox, QWidget

from f1_tracker.ui.workers import Worker


class BasePage(QWidget):
    """Shared plumbing for every page: controller access + background worker."""

    def __init__(self, controller, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.worker = Worker()

    def on_show(self) -> None:
        """Hook called by the controller whenever this page becomes visible."""

    def show_error(self, exc: Exception, prefix: str = "Could not load") -> None:
        traceback.print_exc()
        label = getattr(self, "status_label", None)
        if label is not None:
            label.setText(f"<span style='color:#E74C3C;'>{prefix}: {exc}</span>")
            return
        QMessageBox.critical(self, prefix, str(exc))