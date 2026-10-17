from __future__ import annotations

import inspect
import traceback
from typing import Any, Callable, Optional

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

OnDone = Callable[[Any], None]
OnError = Callable[[Exception], None]


class _Signals(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(object, str)
    progress = pyqtSignal(int, int)


class _Runner(QRunnable):
    def __init__(self, fn: Callable, signals: _Signals, on_done: Optional[OnDone], on_error: Optional[OnError]) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals
        self._on_done = on_done
        self._on_error = on_error

    @pyqtSlot()
    def run(self) -> None:
        try:
            # If the target function accepts `progress`, hand it a live emitter.
            signature = inspect.signature(self._fn)
            kwargs = {}
            if "progress" in signature.parameters:
                kwargs["progress"] = lambda current, total: self._signals.progress.emit(current, total)
                result = self._fn(**kwargs)
            else:
                result = self._fn()
            self._signals.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self._signals.failed.emit(exc, traceback.format_exc())


class Worker:
    """Run a blocking function off the UI thread; callbacks fire on the GUI thread."""

    def __init__(self) -> None:
        self._pool = QThreadPool.globalInstance()

    def run(
        self,
        fn: Callable,
        on_done: Optional[OnDone] = None,
        on_error: Optional[OnError] = None,
        progress: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        signals = _Signals()
        runner = _Runner(fn, signals, on_done, on_error)

        # Wrap every GUI-side slot so a raised exception can never abort Qt.
        signals.finished.connect(lambda value: self._safe(on_done, value))
        signals.failed.connect(lambda exc, _tb: self._safe(on_error, exc))
        if progress:
            signals.progress.connect(lambda cur, tot: self._safe(progress, cur, tot))

        self._pool.start(runner)

    @staticmethod
    def _safe(func, *args) -> None:
        if func is None:
            return
        try:
            func(*args)
        except Exception:  # noqa: BLE001
            traceback.print_exc()