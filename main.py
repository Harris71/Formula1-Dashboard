import sys
import time

from PyQt6.QtCore import QThreadPool
from PyQt6.QtWidgets import QApplication

from f1_tracker.app import F1App
from f1_tracker.config import APP_TITLE
from f1_tracker.ui.icons import app_icon
from f1_tracker.ui.theme import apply_theme

# Max time (s) to let background fetches finish before closing.
_DRAIN_SECONDS = 60


def _drain_thread_pool(app: QApplication) -> None:
    """Wait for worker threads and flush leftover queued GUI callbacks.

    Worker threads use the shared QThreadPool. If the interpreter exits while
    one is still publishing results (or with queued callbacks undelivered), Qt
    can abort with a fatal assert. We therefore keep the event loop pumping
    until the pool is idle and the post-event queue is settled.
    """
    pool = QThreadPool.globalInstance()
    pool.clear()
    deadline = time.monotonic() + _DRAIN_SECONDS

    while True:
        app.processEvents()
        if pool.waitForDone(0):
            # A thread may have published one final result right as we checked.
            time.sleep(0.05)
            app.processEvents()
            if pool.waitForDone(0):
                break
        if time.monotonic() > deadline:
            break


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setDesktopFileName("f1-tracker")
    apply_theme(app)
    app.setWindowIcon(app_icon())

    window = F1App()
    if window.prefers_maximized():
        window.showMaximized()
    else:
        window.show()
    rc = app.exec()

    _drain_thread_pool(app)
    sys.exit(rc)


if __name__ == "__main__":
    main()