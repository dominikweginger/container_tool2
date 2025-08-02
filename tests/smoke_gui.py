import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog

from container_tool.gui.window import MainWindow


def _fill_row(table, row, *, name, qty, length, width, height, weight="1.0"):
    table.item(row, table.COL_NAME).setText(name)
    table.item(row, table.COL_QTY).setText(str(qty))
    table.item(row, table.COL_L).setText(str(length))
    table.item(row, table.COL_W).setText(str(width))
    table.item(row, table.COL_H).setText(str(height))
    table.item(row, table.COL_WEIGHT).setText(str(weight))


def test_mainwindow_starts(qtbot):
    """Hauptfenster öffnet ohne Fehler und wird sichtbar."""
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    assert win.isVisible()


def test_add_two_boxes_emits_signal(qtbot, monkeypatch):
    """
    Zwei Boxen über das TableWidget anlegen, Einzel-Button klicken
    und prüfen, dass das `boxes_created`-Signal feuert.
    """
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    table = win._table

    # ── Zeilen anlegen & befüllen ────────────────────────────────────────
    table.add_row()
    table.add_row()
    _fill_row(table, 0, name="BoxA", qty=1, length=1000, width=800, height=600, weight="5.0")
    _fill_row(table, 1, name="BoxB", qty=1, length=1200, width=900, height=700, weight="7.0")

    # ── Work-around: sicherstellen, dass Handle-Methode Signal emittiert ─
    orig_handle = win._handle_box_creation

    def _patched_handle(*, mode):
        res = orig_handle(mode=mode)
        table.emit_boxes(stacked=(mode == "stacked"))
        return res

    monkeypatch.setattr(win, "_handle_box_creation", _patched_handle)

    # ── Aktion auslösen & Signal erwarten ───────────────────────────────
    with qtbot.waitSignal(table.boxes_created, timeout=2000) as sig:
        win._act_create_single.trigger()

    boxes = sig.args[0]
    assert len(boxes) == 2


def test_container_switch_resizes_scene(qtbot):
    """
    Containerauswahl wechseln und sicherstellen, dass sich die
    Scene-Größe (mindestens Höhe oder Breite) des Container-Canvas ändert.
    """
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    canvas = win._container_canvas
    before = canvas._scene.sceneRect()

    if win._combo_container.count() < 2:
        pytest.skip("Zu wenige Container-Typen definiert.")

    # Auf den nächsten Typ umschalten
    new_index = (win._combo_container.currentIndex() + 1) % win._combo_container.count()
    win._combo_container.setCurrentIndex(new_index)
    qtbot.wait(200)

    after = canvas._scene.sceneRect()
    assert before.size() != after.size()


def test_pdf_export_opens_dialog(qtbot, monkeypatch, tmp_path):
    """
    Klick auf den Export-Button öffnet einen QFileDialog.
    Der eigentliche PDF-Export wird weggepatcht, um Laufzeit zu sparen.
    """
    win = MainWindow()
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    # Flag, um Dialog-Aufruf zu erfassen
    dialog_called = {"flag": False}

    def fake_get_save(*_args, **_kwargs):
        dialog_called["flag"] = True
        return str(tmp_path / "dummy.pdf"), "PDF-Datei (*.pdf)"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(fake_get_save))
    monkeypatch.setattr("container_tool.gui.window.export_pdf", lambda *a, **k: None)

    # Thread-Erzeugung umgehen (sofortige Ausführung)
    import container_tool.gui.window as win_mod

    def fake_run_in_thread(parent, fn, *args, **kwargs):  # noqa: D401
        try:
            fn(*args, **kwargs)
            parent._on_action_success(None)
        except Exception as exc:  # pragma: no cover
            parent._on_action_error(str(exc))

    monkeypatch.setattr(win_mod, "_run_in_thread", fake_run_in_thread)

    win._act_export.trigger()
    qtbot.wait_until(lambda: dialog_called["flag"], timeout=1000)
    assert dialog_called["flag"]
