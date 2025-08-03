"""
table_widget.py
~~~~~~~~~~~~~~~~
QTableWidget‑basiertes Eingabe‑Widget zum Erfassen von Box‑ bzw. Stack‑Daten
für das Container‑Tool‑Projekt.

* Spalten:  Name | Menge | L | B | H | Gewicht | Farbe
* Jede Zeile wird per externem “+‑Button” (MainWindow) über ``add_row`` ergänzt.
* Sofortige Eingabe‑Validierung: ungültige Zellen werden rot markiert.
* Farben‑Button wechselt bei Klick zur nächsten unverbrauchten Farbe.
* Kontextmenü (Rechtsklick) **und** Delete/Backspace‑Shortcut löschen Zeilen.
* ``read_boxes`` gibt eine Liste ``Box``‑ oder ``Stack``‑Objekte zurück.
* ``boxes_created``‑Signal kann vom MainWindow ausgelöst werden, um die
  erzeugten Objekte zu erhalten.

Änderungen (03 Aug 2025)
------------------------
* **Bug‑Fix:** Beim Import wird *kein* ``QWidget`` mehr erzeugt –
  löst das »QWidget: Must construct a QApplication before a QWidget«‑Problem.
* Datei bis zum Ende vervollständigt (die vorherige Version war abgeschnitten).
* Demo‑/Test‑Code sauber hinter ``if __name__ == "__main__":``.
"""

from __future__ import annotations

import itertools
import random
from typing import List, Set, Tuple

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
    QMenu,
)

# ---------------------------------------------------------------------------
# Externe Datenmodelle (gem. Projektplan) – Fallback für Autocompletion
# ---------------------------------------------------------------------------
try:
    from container_tool.core.models import Box, Stack
except ModuleNotFoundError:  # pragma: no cover
    class Box:  # Minimal‑Stub
        def __init__(
            self,
            name,
            length_mm,
            width_mm,
            height_mm,
            weight_kg,
            color_hex,
            pos: Tuple[int, int] = (0, 0),
            rotation_deg: int = 0,
        ):
            self.name = name
            self.length_mm = length_mm
            self.width_mm = width_mm
            self.height_mm = height_mm
            self.weight_kg = weight_kg
            self.color_hex = color_hex
            self.pos = pos
            self.rotation_deg = rotation_deg

    class Stack(Box):  # pragma: no cover
        """Repräsentiert gestapelte Boxen (height_mm skaliert mit Menge)."""

        def __init__(self, name: str, _boxes: List[Box]):
            total_height = sum(b.height_mm for b in _boxes)
            first = _boxes[0]
            super().__init__(
                name=name,
                length_mm=first.length_mm,
                width_mm=first.width_mm,
                height_mm=total_height,
                weight_kg=sum(b.weight_kg for b in _boxes),
                color_hex=first.color_hex,
            )
            self.boxes = _boxes


# ---------------------------------------------------------------------------


class _ColorButton(QPushButton):
    """Kleiner, vollflächig gefärbter Button, speichert seine Hex‑Farbe."""

    def __init__(self, color_hex: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(24, 24))
        self.set_color(color_hex)

    @property
    def color_hex(self) -> str:
        return self._color_hex

    def set_color(self, color_hex: str) -> None:
        self._color_hex = color_hex
        self.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #555;")


class TableWidget(QTableWidget):
    """
    Komfortables Tabellen‑Widget zur Eingabe von Box‑Daten.

    Öffentliche API
    ---------------
    add_row()                – Neue Zeile anhängen.
    remove_selected_rows()   – Markierte Zeilen löschen.
    read_boxes(stacked=True) – Liste Box/Stack‑Objekte erzeugen.
    emit_boxes(stacked)      – Signal mit erzeugten Objekten senden.
    boxes_created            – Qt‑Signal(list)
    """

    boxes_created: Signal = Signal(list)  # extern verbinden (MainWindow)

    # Spalten‑Indizes
    COL_NAME, COL_QTY, COL_L, COL_W, COL_H, COL_WEIGHT, COL_COLOR = range(7)

    # Okabe‑Ito‑Palette + Ergänzungen
    _PALETTE: list[str] = [
        "#E69F00",
        "#56B4E9",
        "#009E73",
        "#F0E442",
        "#0072B2",
        "#D55E00",
        "#CC79A7",
        "#999999",
        "#332288",
        "#117733",
        "#DDCC77",
        "#88CCEE",
        "#44AA99",
        "#AA4499",
        "#DDDDDD",
    ]

    # ------------------------------------------------------------------ #
    # Konstruktor / Setup
    # ------------------------------------------------------------------ #
    def __init__(self, parent=None) -> None:
        super().__init__(0, 7, parent)
        self._used_colors: Set[str] = set()
        self._invalid_cells: Set[Tuple[int, int]] = set()

        self._init_ui()
        self.itemChanged.connect(self._validate_item)

    # ------------------------------------------------------------------ #
    # Öffentliche Methoden
    # ------------------------------------------------------------------ #
    def add_row(self) -> None:
        """Extern aufrufen: fügt eine neue Eingabe‑Zeile an."""
        row = self.rowCount()
        self.insertRow(row)

        defaults = ["", "1", "", "", "", "", ""]  # Menge default = 1
        for col, value in enumerate(defaults):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.setItem(row, col, item)

        # Farbe vergeben
        color_hex = self._assign_unique_color()
        btn = _ColorButton(color_hex)
        btn.clicked.connect(lambda _, r=row: self._cycle_color(r))
        self.setCellWidget(row, self.COL_COLOR, btn)

        # Gleich prüfen
        for col in range(self.columnCount() - 1):
            self._validate_cell(row, col)

    def remove_selected_rows(self) -> None:
        """Löscht alle markierten Zeilen (Kontextmenü / DEL)."""
        rows = {idx.row() for idx in self.selectedIndexes()}
        if not rows:
            return

        for row in sorted(rows, reverse=True):
            btn = self.cellWidget(row, self.COL_COLOR)
            if isinstance(btn, _ColorButton):
                self._used_colors.discard(btn.color_hex)
            self.removeRow(row)

    def read_boxes(self, *, stacked: bool = False) -> List[Box]:
        """Erzeugt Box‑ oder Stack‑Objekte aus *gültigen* Zeilen."""
        boxes: list[Box] = []
        for row in range(self.rowCount()):
            if any((row, c) in self._invalid_cells for c in range(self.columnCount())):
                continue  # ungültige Zeile überspringen

            name = (self.item(row, self.COL_NAME).text() or f"Box_{row+1}").strip()
            qty = int(self.item(row, self.COL_QTY).text())
            l_mm = int(self.item(row, self.COL_L).text())
            w_mm = int(self.item(row, self.COL_W).text())
            h_mm = int(self.item(row, self.COL_H).text())
            weight_txt = self.item(row, self.COL_WEIGHT).text().strip()
            weight_kg = float(weight_txt) if weight_txt else 0.0
            color_hex = self._color_at_row(row)

            if stacked:
                singles = [
                    Box(
                        name=f"{name}_{i+1}",
                        length_mm=l_mm,
                        width_mm=w_mm,
                        height_mm=h_mm,
                        weight_kg=weight_kg,
                        color_hex=color_hex,
                    )
                    for i in range(qty)
                ]
                boxes.append(Stack(name=name, _boxes=singles))
            else:
                for i in range(qty):
                    boxes.append(
                        Box(
                            name=f"{name}_{i+1}" if qty > 1 else name,
                            length_mm=l_mm,
                            width_mm=w_mm,
                            height_mm=h_mm,
                            weight_kg=weight_kg,
                            color_hex=color_hex,
                        )
                    )
        return boxes

    def emit_boxes(self, *, stacked: bool = False) -> None:
        """Vom MainWindow‑Button aufrufbar."""
        self.boxes_created.emit(self.read_boxes(stacked=stacked))

    # ------------------------------------------------------------------ #
    # Events (Kontextmenü, Shortcuts)
    # ------------------------------------------------------------------ #
    def contextMenuEvent(self, ev):  # noqa: D401 – Qt Signature
        menu = QMenu(self)
        act_del = menu.addAction("Markierte Zeile(n) löschen")
        act_del.triggered.connect(self.remove_selected_rows)
        menu.exec(ev.globalPos())

    def keyPressEvent(self, ev):  # noqa: D401 – Qt Signature
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.remove_selected_rows()
            return
        super().keyPressEvent(ev)

    # ------------------------------------------------------------------ #
    # Private Helfer
    # ------------------------------------------------------------------ #
    def _init_ui(self) -> None:
        self.setHorizontalHeaderLabels(
            ["Name", "Menge", "L", "B", "H", "Gewicht", "Farbe"]
        )
        header: QHeaderView = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_COLOR, QHeaderView.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setMinimumSize(QSize(640, 360))
        self.setAlternatingRowColors(True)

    # ---------- Farb‑Logik ---------- #
    def _assign_unique_color(self) -> str:
        available = [c for c in self._PALETTE if c not in self._used_colors]
        if not available:  # Palette erschöpft → zufällige Farbe
            while True:
                col = QColor.fromRgb(
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                ).name()
                if col not in self._used_colors:
                    available.append(col)
                    break
        color_hex = random.choice(available)
        self._used_colors.add(color_hex)
        return color_hex

    def _cycle_color(self, row: int) -> None:
        """Wechselt auf die nächste freie Farbe in der Palette."""
        current = self._color_at_row(row)
        palette_cycle = itertools.cycle(self._PALETTE)

        # bis zur aktuellen Farbe drehen
        for _ in range(len(self._PALETTE)):
            if next(palette_cycle) == current:
                break

        # nächste unbelegte Farbe suchen
        for _ in range(len(self._PALETTE)):
            new_col = next(palette_cycle)
            if new_col not in self._used_colors:
                break
        else:  # alle belegt → neue zufällige
            new_col = self._assign_unique_color()

        btn = self.cellWidget(row, self.COL_COLOR)
        if isinstance(btn, _ColorButton):
            btn.set_color(new_col)
        self._used_colors.discard(current)
        self._used_colors.add(new_col)

    def _color_at_row(self, row: int) -> str:
        btn = self.cellWidget(row, self.COL_COLOR)
        return btn.color_hex if isinstance(btn, _ColorButton) else "#000000"

    # ---------- Validierung ---------- #
    def _validate_item(self, item: QTableWidgetItem) -> None:
        self._validate_cell(item.row(), item.column())

    def _validate_cell(self, row: int, col: int) -> None:
        text = self.item(row, col).text().strip()
        valid = True

        if col == self.COL_NAME:
            valid = bool(text)
        elif col == self.COL_QTY:
            valid = text.isdigit() and int(text) > 0
        elif col in (self.COL_L, self.COL_W, self.COL_H):
            valid = text.isdigit() and int(text) > 0
        elif col == self.COL_WEIGHT:
            if text:
                try:
                    valid = float(text) >= 0
                except ValueError:
                    valid = False

        self._set_cell_valid(row, col, valid)

    def _set_cell_valid(self, row: int, col: int, valid: bool) -> None:
        if valid:
            self._invalid_cells.discard((row, col))
            self.item(row, col).setBackground(QBrush())
        else:
            self._invalid_cells.add((row, col))
            self.item(row, col).setBackground(QBrush(QColor("#ffe6e6")))


# ---------------------------------------------------------------------------
# Demo / Test – läuft nur, wenn die Datei direkt gestartet wird
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    w = TableWidget()
    w.add_row()
    w.setWindowTitle("TableWidget – Demo")
    w.show()
    sys.exit(app.exec())
