"""Move and resize the frameless window through the window manager.

pywebview's built-in drag calls ``QWidget.move()``, which Wayland ignores (clients may not
position their own windows), and a frameless window has no borders to resize from.
``QWindow.startSystemMove()`` / ``startSystemResize()`` hand the gesture to the compositor
instead and work on Wayland and X11. They must run on the GUI thread while the mouse button
is still held. js_api calls arrive on worker threads, so a QObject living on the GUI thread
receives them through queued signals.
"""

from qtpy import QtCore

_Edge = QtCore.Qt.Edge

# Handle names used by data-edge="…" in web/index.html.
EDGES = {
    "n": _Edge.TopEdge,
    "s": _Edge.BottomEdge,
    "e": _Edge.RightEdge,
    "w": _Edge.LeftEdge,
    "ne": _Edge.TopEdge | _Edge.RightEdge,
    "nw": _Edge.TopEdge | _Edge.LeftEdge,
    "se": _Edge.BottomEdge | _Edge.RightEdge,
    "sw": _Edge.BottomEdge | _Edge.LeftEdge,
}


def edges_for(name):
    """Qt edge flags for a handle name, or None if the name is unknown."""
    return EDGES.get(name) if isinstance(name, str) else None


class WindowChrome(QtCore.QObject):
    _move_requested = QtCore.Signal()
    _resize_requested = QtCore.Signal(str)

    def __init__(self, native):
        super().__init__()
        self._native = native
        # Created on a js_api worker thread; live on the GUI thread so slots run there.
        self.moveToThread(native.thread())
        queued = QtCore.Qt.ConnectionType.QueuedConnection
        self._move_requested.connect(self._start_move, queued)
        self._resize_requested.connect(self._start_resize, queued)

    def request_move(self) -> bool:
        self._move_requested.emit()
        return True

    def request_resize(self, name) -> bool:
        if edges_for(name) is None:
            return False
        self._resize_requested.emit(name)
        return True

    @QtCore.Slot()
    def _start_move(self):
        handle = self._native.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    @QtCore.Slot(str)
    def _start_resize(self, name):
        handle = self._native.windowHandle()
        edges = edges_for(name)
        if handle is not None and edges is not None:
            handle.startSystemResize(edges)
