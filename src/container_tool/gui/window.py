"""
src/container_tool/gui/window.py

Hauptfenster des Container‑Ladetools
------------------------------------
Verbindet Tabelle, Wartebereich, Container‑Canvas und die sechs Toolbar‑Aktionen.
Erfüllt sämtliche Vorgaben aus Projektplan und UX‑Beschreibung.

Abhängigkeiten
--------------
PySide6  (Qt 6)
Eigene Module:
    - container_tool.gui.table_widget.TableWidget
    - container_tool.gui.canvas2d.Canvas2D
    - container_tool.io.io_clp   (load_clp / save_clp)
    - container_tool.io.export   (export_pdf)
    - data/containers.json       (Definition der Containertypen)

Der Code ist 1‑zu‑1 kopierbar nach VS Code.
"""

from __future__ import annotations

import json
import logging
import sys
import os
from pathlib import Path
from typing import Callable, Any

from PySide6.QtCore import Qt, QObject, Signal, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QSplitter,
    QToolBar,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QStatusBar,
)

# ──────────────────────────────────────────────────────────────────────────────
# Eigene Importe (late import vermeidet zirkuläre Abhängigkeiten beim Testen)
# ──────────────────────────────────────────────────────────────────────────────
from container_tool.gui.table_widget import TableWidget       # noqa: E402
from container_tool.gui.canvas_2d import Canvas2D              # noqa: E402
from container_tool.core import io_clp                         # noqa: E402
from container_tool.export.pdf_export import export_pdf        # noqa: E402


# ──────────────────────────────────────────────────────────────────────────────
# Helfer: Generischer Worker für lange Operationen (Variante A – eigener QThread)
# ──────────────────────────────────────────────────────────────────────────────
class _Worker(QObject):
    """Führt *fn* mit *args/kwargs* in einem separaten Thread aus."""

    finished: Signal = Signal(object)  # Ergebnisobjekt
    error: Signal = Signal(str)        # Fehlermeldung als Text

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as exc:  # pragma: no cover
            logger.exception("Fehler im Worker‑Thread")
            self.error.emit(str(exc))


def _run_in_thread(
    parent: "MainWindow",
    fn: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> None:
    """
    Hilfsfunktion:
    Erstellt einen Worker + QThread, startet ihn und verbindet Signale mit Slots
    im *parent* (dem MainWindow).

    *parent* muss Methoden *_on_action_success* und *_on_action_error* besitzen.
    """
    worker = _Worker(fn, *args, **kwargs)
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)  # type: ignore[arg-type]

    # Ergebnisse zurück in den GUI‑Thread
    worker.finished.connect(parent._on_action_success)  # type: ignore[arg-type]
    worker.error.connect(parent._on_action_error)       # type: ignore[arg-type]

    # Aufräumen
    worker.finished.connect(thread.quit)                # type: ignore[arg-type]
    worker.finished.connect(worker.deleteLater)         # type: ignore[arg-type]
    thread.finished.connect(thread.deleteLater)         # type: ignore[arg-type]

    thread.start()


# ──────────────────────────────────────────────────────────────────────────────
# MainWindow
# ──────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """
    Hauptfenster mit Tabelle (links) und zwei Canvas‑Bereichen (rechts),
    plus Symbolleiste und Statusbar.
    """

    CONTAINER_JSON_PATH = Path(__file__).resolve().parents[2] / "data" / "containers.json"

    # ..........................................................................
    # Initialisierung
    # ..........................................................................
    def __init__(self, container_defs: dict[str, Any] | None = None) -> None:  # ← CHANGED
        super().__init__()
        self._container_defs: dict[str, Any] = container_defs or {}            # ← CHANGED
        self.setWindowTitle("Container‑Ladetool")

        # ---------- zentrale Widgets --------------------------------------------------
        self._table = TableWidget(parent=self)

        self._waiting_canvas = Canvas2D(scene_name="waiting_area", parent=self)
        self._container_canvas = Canvas2D(scene_name="container", parent=self)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane) # Nur das Eltern-Widget übergeben
        right_layout.setSpacing(2)
        right_layout.setContentsMargins(0, 0, 0, 0) # Ränder separat setzen
        right_layout.addWidget(self._waiting_canvas)
        right_layout.addWidget(self._container_canvas)

        self._splitter = QSplitter(Qt.Horizontal, self)
        self._splitter.addWidget(self._table)
        self._splitter.addWidget(right_pane)
        self._splitter.setStretchFactor(0, 2)  # Tabelle etwas breiter
        self._splitter.setStretchFactor(1, 3)

        container = QWidget(self)
        container.setLayout(QVBoxLayout())
        container.layout().addWidget(self._splitter)
        self.setCentralWidget(container)

        # ---------- Toolbar -----------------------------------------------------------
        self._build_toolbar()

        # ---------- Statusbar ---------------------------------------------------------
        self._statusbar = QStatusBar(self)
        self.setStatusBar(self._statusbar)

        self._set_status("Bereit")

    # ..........................................................................
    # Aufbau Toolbar
    # ..........................................................................
    def _build_toolbar(self) -> None:
        tb = QToolBar("Haupt‑Aktionen", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        # --- (1) neuer Button direkt nach der Containerauswahl -------------
        act_add_row = QAction("Neue Zeile (+)", self)
        act_add_row.setToolTip("Leere Tabellenzeile hinzufügen")
        act_add_row.triggered.connect(self._table.add_row)
        tb.addAction(act_add_row)

        # Containerauswahl (Dropdown):
        self._combo_container = QComboBox(tb)
        for ctype in self._load_container_types():
            self._combo_container.addItem(ctype)
        self._combo_container.currentTextChanged.connect(self._on_container_changed)
        tb.addWidget(self._combo_container)

        tb.addSeparator()

        # Gestapelt erstellen
        self._act_create_stacked = QAction("Kisten gestapelt erstellen", self)
        self._act_create_stacked.triggered.connect(
            lambda: self._handle_box_creation(mode="stacked")
        )
        tb.addAction(self._act_create_stacked)

        # Einzeln erstellen
        self._act_create_single = QAction("Kisten einzeln erstellen", self)
        self._act_create_single.triggered.connect(
            lambda: self._handle_box_creation(mode="single")
        )
        tb.addAction(self._act_create_single)

        tb.addSeparator()

        # Projekt laden
        self._act_load = QAction("Projekt laden", self)
        self._act_load.triggered.connect(self._on_load_project)
        tb.addAction(self._act_load)

        # Projekt speichern
        self._act_save = QAction("Projekt speichern", self)
        self._act_save.triggered.connect(self._on_save_project)
        tb.addAction(self._act_save)

        tb.addSeparator()

        # Export / Projekt abschließen
        self._act_export = QAction("Projekt abgeschlossen / Daten exportieren", self)
        self._act_export.triggered.connect(self._on_export_project)
        tb.addAction(self._act_export)

    # ..........................................................................
    # Status‑/Helper‑Funktionen
    # ..........................................................................
    def _load_container_types(self) -> list[str]:
        """
        Lädt Containertypen aus übergebenen *container_defs* oder – falls leer –
        aus *containers.json*; fällt bei Fehler auf eine Standardliste zurück.
        """
        if self._container_defs:                                            # ← CHANGED
            return [c["name"] if isinstance(c, dict) else c.name            # ← CHANGED
                    for c in self._container_defs.values()]                 # ← CHANGED

        try:
            with open(self.CONTAINER_JSON_PATH, "r", encoding="utf-8") as fp:
                data = json.load(fp)
            return [item["name"] for item in data]  # type: ignore[index]
        except Exception as exc:  # pragma: no cover
            logger.warning("Kann Containerliste nicht laden: %s", exc)
            return ["20 ft", "40 ft", "40 ft HC", "40 ft OT"]

    def _set_status(self, text: str) -> None:
        """Aktuellen Status in der Statusleiste anzeigen."""
        self.statusBar().showMessage(text)

    # ..........................................................................
    # Slots – Benutzeraktionen
    # ..........................................................................
    # -- Containerauswahl -------------------------------------------------------
    def _on_container_changed(self, ctype: str) -> None:
        """
        Container‑Typ geändert → Container‑Canvas neu skalieren.
        """
        try:
            self._container_canvas.set_container_type(ctype)
            self._set_status(f"Containertyp gesetzt: {ctype}")
        except Exception as exc:
            logger.exception("Fehler beim Setzen des Containertyps")
            QMessageBox.critical(self, "Fehler", str(exc))

    # -- Kisten erstellen -------------------------------------------------------
    def _handle_box_creation(self, *, mode: str) -> None:
        """
        Ruft TableWidget.read_boxes() auf und übergibt die Boxen
        an die Waiting‑Area‑Scene.

        *mode* ∈ {"stacked", "single"}
        """
        # Bestehende Objekte? → Warnhinweis
        if self._waiting_canvas.has_boxes() or self._container_canvas.has_boxes():
            ret = QMessageBox.question(
                self,
                "Neu generieren?",
                "Es sind bereits Kisten vorhanden. "
                "Möchtest du wirklich neu generieren und alle vorhandenen "
                "Kisten löschen?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if ret != QMessageBox.Yes:
                return

            self._waiting_canvas.clear_boxes()
            self._container_canvas.clear_boxes()

        try:
            boxes = self._table.read_boxes(stacked=(mode == "stacked"))
            self._waiting_canvas.add_boxes(boxes)
            self._set_status(f"{len(boxes)} Kisten erzeugt ({mode}).")
        except Exception as exc:
            logger.exception("Fehler beim Erzeugen der Kisten")
            QMessageBox.critical(self, "Fehler", str(exc))

    # -- Projekt laden ----------------------------------------------------------
    def _on_load_project(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Projekt laden",
            "",
            "Container‑Projekt (*.clp)",
        )
        if not filename:
            return

        self._set_status("Projekt wird geladen …")
        _run_in_thread(self, io_clp.load_clp, filename)

    # -- Projekt speichern ------------------------------------------------------
    def _on_save_project(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Projekt speichern",
            "",
            "Container‑Projekt (*.clp)",
        )
        if not filename:
            return

        self._set_status("Projekt wird gespeichert …")
        project = self._build_project_object()
        _run_in_thread(self, io_clp.save_clp,
                        project, filename, user=os.getlogin(), version="1.0.0")

    # -- Export / Abschluss -----------------------------------------------------
    def _on_export_project(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "PDF exportieren",
            "",
            "PDF‑Datei (*.pdf)",
        )
        if not filename:
            return

        self._set_status("Export läuft …")
        project_state = self._gather_project_state()
        _run_in_thread(self, export_pdf, filename, project_state)

    # ..........................................................................
    # Callback‑Slots aus Worker‑Threads
    # ..........................................................................
    def _on_action_success(self, result: object) -> None:  # noqa: D401
        """Wird aufgerufen, wenn ein Worker erfolgreich abgeschlossen ist."""
        self._set_status("Aktion abgeschlossen")
        QMessageBox.information(self, "Fertig", "Aktion erfolgreich abgeschlossen.")

    def _on_action_error(self, message: str) -> None:  # noqa: D401
        """Wird aufgerufen, wenn ein Worker einen Fehler liefert."""
        self._set_status("Fehler")
        QMessageBox.critical(self, "Fehler", message)

    # ..........................................................................
    # Hilfsfunktionen
    # ..........................................................................
    def _gather_project_state(self) -> dict[str, Any]:
        """
        Aggregiert alle relevanten Informationen (Canvas + Tabelle)
        in ein dict, das an io_clp / export_pdf übergeben wird.
        """
        return {
            "container_type": self._combo_container.currentText(),
            "table": self._table.serialize(),
            "container_boxes": self._container_canvas.serialize(),
            "waiting_boxes": self._waiting_canvas.serialize(),
        }

    # ----------------------------------------------------------------------
    # Privater Helfer: GUI‑Zustand ➜ Project‑Objekt
    # ----------------------------------------------------------------------
    def _build_project_object(self):
        """
        Erstellt aus dem aktuellen GUI‑Zustand ein Project‑Objekt,
        wie es io_clp.save_clp() erwartet.
        """
        from container_tool.core import io_clp
        from container_tool.core.models import Box, Stack, Project

        state = self._gather_project_state()

        # 1) Container‑Objekt ermitteln (Name ➜ Definition)
        defs = io_clp.load_containers_definitions()
        container = next(c for c in defs.values()
                         if getattr(c, "name", "") == state["container_type"])

        # 2) Box‑/Stack‑Instanzen aus den Canvas‑Daten erzeugen
        boxes_raw = state["container_boxes"] + state["waiting_boxes"]
        boxes = [
            Box.from_dict(b) if b.get("type") == "box" else Stack.from_dict(b)
            for b in boxes_raw
        ]

        # 3) Project zusammenstellen (Meta‑Infos fügt save_clp selbst hinzu)
        return Project(container=container, boxes=boxes)


# ──────────────────────────────────────────────────────────────────────────────
# Bequemer Stand‑Alone‑Test: `python -m container_tool.gui.window`
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":  # pragma: no cover
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1280, 720)
    win.show()
    sys.exit(app.exec())
