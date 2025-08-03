"""
table_widget.py
~~~~~~~~~~~~~~~~
Ein QTableWidget‑basiertes Eingabedialog‑Widget zum Erfassen von Box‐ bzw.
Stack‑Daten.  Entwickelt für PySide6 v6.5.2 und exakt auf die im Projektplan
definierten Anforderungen abgestimmt.

• Spalten:  Name | Menge | L | B | H | Gewicht | Farbe
• Jede Zeile wird per  “+‑Button” (extern – z. B. im MainWindow) ergänzt,
  indem man `add_row()` aufruft.
• Sofortige Eingabe‑Validierung; ungültige Felder erhalten einen roten Rahmen
  und werden beim Erzeugen ignoriert.
• Farben werden aus einer farbenblind‑freundlichen Palette gezogen und sind
  garantiert eindeutig.
• Kein zusätzlicher Dialog – ein Klick auf den Farb‑Button wechselt einfach
  zur nächsten freien Farbe.
• Methode `read_boxes(stacked: bool)` liefert eine Liste von `Box`‑ oder
  `Stack`‑Instanzen.
• Signal `boxes_created(list)` kann von außen manuell (z. B. Toolbar‑Button
  “Erstellen”) über `emit_boxes(stacked)` ausgelöst werden.
"""

from __future__ import annotations

import itertools
import random
from typing import List, Set

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHeaderView,
)

# ---------------------------------------------------------------------------
# Externe Datenmodelle (müssen bereits im Projekt vorhanden sein):
# ---------------------------------------------------------------------------
try:
    # Standard‑Import‑Pfad laut Projektplan – ggf. anpassen.
    from container_tool.core.models import Box, Stack
except ModuleNotFoundError:  # Fallback für Autocompletion / Test‑Runner
    class Box:  # pragma: no cover
        def __init__(self, name, length_mm, width_mm, height_mm,
                     weight_kg, color_hex, pos=(0, 0), rotation_deg=0):
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
        pass


class TableWidget(QTableWidget):
    """
    QTableWidget zur komfortablen Eingabe von Box‑Daten.

    Öffentliche API
    ---------------
    add_row()                – Fügt eine neue Leerzeile hinzu.
    read_boxes(stacked=True) – Erstellt eine Liste Box/Stack‐Objekte.
    emit_boxes(stacked)      – Liest & sendet die Objekte per Signal.
    boxes_created            – Qt‑Signal(list) mit zurückgelieferten Instanzen.
    """

    # ------------------------------------------------------------------ #
    # Qt‑Signal: wird extern mit BTN “Erstellen” im MainWindow verbunden. #
    # ------------------------------------------------------------------ #
    boxes_created: Signal = Signal(list)

    # Spalten‑Indizes (lesbarer → keine Magic‑Numbers).
    COL_NAME, COL_QTY, COL_L, COL_W, COL_H, COL_WEIGHT, COL_COLOR = range(7)

    # Farbenblinde‑freundliche Palette (Okabe‑Ito + zusätzliche Abstufungen).
    _PALETTE: list[str] = [
        "#E69F00", "#56B4E9", "#009E73", "#F0E442",
        "#0072B2", "#D55E00", "#CC79A7", "#999999",
        "#332288", "#117733", "#DDCC77", "#88CCEE",
        "#44AA99", "#AA4499", "#DDDDDD",
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(0, 7, parent)           # Start mit 0 Zeilen
        self._used_colors: Set[str] = set()      # Vergebene Farben
        self._invalid_cells: Set[tuple[int, int]] = set()

        self._init_ui()
        self.itemChanged.connect(self._validate_item)

    # ----------------- Öffentliche Methoden ---------------------------- #

    def add_row(self) -> None:
        """Extern aufzurufen: fügt eine neue Datensatz‑Zeile hinzu."""
        row = self.rowCount()
        self.insertRow(row)

        # Default‑Items anlegen
        defaults = ["", "1", "", "", "", "", ""]
        for col, value in enumerate(defaults):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            self.setItem(row, col, item)

        # Einmalige Farbe vergeben und Button setzen
        color_hex = self._assign_unique_color()
        btn = _ColorButton(color_hex)
        btn.clicked.connect(lambda _, r=row: self._cycle_color(r))
        self.setCellWidget(row, self.COL_COLOR, btn)

        # Sofort alle Felder prüfen (z. B. Default‑Menge = 1)
        for col in range(self.columnCount() - 1):  # Farbe nicht prüfen
            self._validate_cell(row, col)

    def read_boxes(self, *, stacked: bool = False) -> List[Box]:
        """Liest alle gültigen Zeilen ein und generiert Box‑ bzw. Stack‑Objekte."""
        boxes: list[Box] = []

        for row in range(self.rowCount()):
            if any((row, c) in self._invalid_cells for c in range(self.columnCount())):
                # Zeile enthält ungültige Daten → komplett überspringen
                continue

            name = self.item(row, self.COL_NAME).text().strip() or f"Box_{row+1}"
            qty  = int(self.item(row, self.COL_QTY).text())
            l_mm = int(self.item(row, self.COL_L).text())
            w_mm = int(self.item(row, self.COL_W).text())
            h_mm = int(self.item(row, self.COL_H).text())
            weight_raw = self.item(row, self.COL_WEIGHT).text().strip()
            weight_kg = float(weight_raw) if weight_raw else 0.0

            color_hex = self._color_at_row(row)

            if stacked:
                single_boxes = [
                    Box(name=f"{name}_{i+1}", length_mm=l_mm, width_mm=w_mm,
                          height_mm=h_mm, weight_kg=weight_kg, color_hex=color_hex)
                          for i in range(qty)
                ]
                boxes.append(Stack(name=name, _boxes=single_boxes))
            else:
                for i in range(qty):
                    boxes.append(
                        Box(name=f"{name}_{i+1}" if qty > 1 else name,
                            length_mm=l_mm, width_mm=w_mm, height_mm=h_mm,
                            weight_kg=weight_kg, color_hex=color_hex)
                    )
        return boxes

    def emit_boxes(self, *, stacked: bool = False) -> None:
        """Kann vom MainWindow‑Button aus aufgerufen werden."""
        self.boxes_created.emit(self.read_boxes(stacked=stacked))

    # ----------------- Private Hilfsfunktionen ------------------------- #

    def _init_ui(self) -> None:
        """Tabellen‑Header & ‑Eigenschaften initialisieren."""
        self.setHorizontalHeaderLabels(
            ["Name", "Menge", "L", "B", "H", "Gewicht", "Farbe"]
        )
        header: QHeaderView = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(self.COL_COLOR, QHeaderView.ResizeToContents)
        self.verticalHeader().setVisible(False)
        self.setMinimumSize(QSize(640, 360))
        self.setAlternatingRowColors(True)

    # ---------- Farblogik ---------- #

    def _assign_unique_color(self) -> str:
        """Gibt einen noch nicht vergebenen Hex‑Farbwert aus der Palette zurück."""
        available = [c for c in self._PALETTE if c not in self._used_colors]
        if not available:                   # Palette erschöpft → zufällige neue Farbe
            while True:
                col = QColor.fromRgb(
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255)
                ).name()
                if col not in self._used_colors:
                    available.append(col)
                    break

        color_hex = random.choice(available)
        self._used_colors.add(color_hex)
        return color_hex

    def _cycle_color(self, row: int) -> None:
        """Bei Klick auf den Farb‑Button → nächste freie Farbe zuweisen."""
        current = self._color_at_row(row)
        palette_cycle = itertools.cycle(self._PALETTE)

        # Bis aktuelle Farbe erreicht ist …
        for col in palette_cycle:
            if col == current:
                break

        # … dann zu nächster Farbe springen, die noch frei ist
        for next_color in palette_cycle:
            if next_color not in self._used_colors:
                break
        else:
            next_color = self._assign_unique_color()  # Fallback zufällig

        # Farben‑Sets aktualisieren
        self._used_colors.discard(current)
        self._used_colors.add(next_color)

        btn: _ColorButton = self.cellWidget(row, self.COL_COLOR)  # type: ignore[assignment]
        btn.set_color(next_color)

    def _color_at_row(self, row: int) -> str:
        btn: _ColorButton = self.cellWidget(row, self.COL_COLOR)  # type: ignore[assignment]
        return btn.color_hex

    # ---------- Validierung ---------- #

    def _validate_item(self, item: QTableWidgetItem) -> None:
        """Qt‑Slot: Prüft das geänderte Item und setzt ggf. Fehler‑Rahmen."""
        self._validate_cell(item.row(), item.column())

    def _validate_cell(self, row: int, col: int) -> None:
        """Markiert Zelle rot, falls Eingabe ungültig ist."""
        item = self.item(row, col)
        if item is None:  # z. B. Farb‑Spalte → Button, kein Item
            return

        valid = True
        text = item.text().strip()

        if col == self.COL_NAME:
            valid = bool(text)
        elif col in {self.COL_QTY, self.COL_L, self.COL_W, self.COL_H}:
            valid = text.isdigit() and int(text) > 0
        elif col == self.COL_WEIGHT:
            if not text:  # Gewicht darf leer sein
                valid = True
            else:
                try:
                    value = float(text)
                    decimals = text.split(".")[1] if "." in text else ""
                    valid = value >= 0 and len(decimals) <= 2
                except ValueError:
                    valid = False

        # Item‑Rahmen über Stylesheet simulieren (kein Delegate benötigt)
        if valid:
            item.setData(Qt.UserRole, True)
            item.setForeground(QBrush())
            item.setBackground(QBrush())
            self._invalid_cells.discard((row, col))
        else:
            item.setData(Qt.UserRole, False)
            red = QColor(255, 0, 0)
            item.setForeground(QBrush())
            item.setBackground(QBrush(QColor(255, 230, 230)))  # sanftes Rot
            self._invalid_cells.add((row, col))


# ---------------------------------------------------------------------------


class _ColorButton(QPushButton):
    """Kleiner Farb‑Button, der die aktuelle Farbe in der Tabelle darstellt."""

    def __init__(self, color_hex: str) -> None:
        super().__init__()
        self.setFixedWidth(40)
        self.set_color(color_hex)

    # ------------------------------------------------------------------ #
    # Öffentliche Hilfsfunktion – ändert Hintergrund & gespeicherten Hex #
    # ------------------------------------------------------------------ #
    def set_color(self, color_hex: str) -> None:
        self.color_hex = color_hex
        self.setStyleSheet(
            f"QPushButton {{ background-color: {color_hex}; border: 1px solid #444; }}"
        )
