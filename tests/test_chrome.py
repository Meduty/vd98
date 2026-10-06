"""Window move/resize bridge (SPEC V.15): edge mapping and GUI-thread dispatch."""

import threading
import time

import pytest
from qtpy import QtCore

from vd98.chrome import EDGES, WindowChrome, edges_for

Edge = QtCore.Qt.Edge


@pytest.mark.parametrize(
    "name,expected",
    [
        ("n", Edge.TopEdge),
        ("s", Edge.BottomEdge),
        ("e", Edge.RightEdge),
        ("w", Edge.LeftEdge),
        ("ne", Edge.TopEdge | Edge.RightEdge),
        ("nw", Edge.TopEdge | Edge.LeftEdge),
        ("se", Edge.BottomEdge | Edge.RightEdge),
        ("sw", Edge.BottomEdge | Edge.LeftEdge),
    ],
)
def test_edges_for_known_names(name, expected):
    assert edges_for(name) == expected


@pytest.mark.parametrize("bad", [None, "", "x", "north", "NE", 5, ["n"]])
def test_edges_for_rejects_unknown(bad):
    assert edges_for(bad) is None


def test_edge_names_match_ui_handles():
    """Every resize handle in index.html names an edge the bridge knows, and vice versa."""
    import re
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "src/vd98/web/index.html").read_text()
    assert set(re.findall(r'data-edge="(\w+)"', html)) == set(EDGES)


class FakeHandle:
    def __init__(self):
        self.calls = []

    def startSystemMove(self):
        self.calls.append(("move", None, threading.get_ident()))
        return True

    def startSystemResize(self, edges):
        self.calls.append(("resize", edges, threading.get_ident()))
        return True


class FakeNative(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.handle = FakeHandle()

    def windowHandle(self):
        return self.handle


def test_requests_from_worker_thread_run_on_gui_thread():
    """js_api calls arrive on worker threads; Qt window calls must run on the GUI thread."""
    app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
    native = FakeNative()
    gui_thread = threading.get_ident()

    def js_api_call():
        chrome = WindowChrome(native)
        chrome.request_move()
        chrome.request_resize("se")
        holder.append(chrome)

    holder = []
    worker = threading.Thread(target=js_api_call)
    worker.start()
    worker.join(5)

    deadline = time.monotonic() + 5
    while len(native.handle.calls) < 2 and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)

    assert [c[0] for c in native.handle.calls] == ["move", "resize"]
    assert native.handle.calls[1][1] == Edge.BottomEdge | Edge.RightEdge
    assert all(c[2] == gui_thread for c in native.handle.calls)


def test_unknown_edge_is_not_dispatched():
    native = FakeNative()
    assert WindowChrome(native).request_resize("bogus") is False
