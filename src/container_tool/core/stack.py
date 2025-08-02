Implementiert die Stapel‑Logik für Container‑Packprojekte.

Funktionen
----------
can_stack(box_a, box_b, container)  -> bool
    Prüft, ob zwei Boxen stapelbar sind.

create_stack(boxes, container)      -> Stack
    Baut aus kompatiblen Boxen einen neuen Stapel.

add_to_stack(stack, box, container) -> Stack
    Fügt einem existierenden Stapel eine weitere Box hinzu.

Alle Prüfungen stützen sich auf die Konstanten und Dataklassen in
`models.py`, insbesondere auf `Stack.SNAP_TOLERANCE_MM`.
"""

from __future__ import annotations

from typing import List

from models import Box, Container, Stack, GeometryError

# ---------------------------------------------------------------------------#
# Hilfsfunktionen                                                           #
# ---------------------------------------------------------------------------#


def _snap_tolerance() -> int:
    """Liefert die projektweit definierte Snap‑Toleranz in Millimetern."""
    return getattr(Stack, "SNAP_TOLERANCE_MM", 10)


def _box_center(box: Box) -> tuple[float, float]:
    """
    Berechnet den Mittelpunkt einer Box.

    Falls `center_x_mm/center_y_mm` existieren, werden diese Werte genutzt.
    Andernfalls wird der Mittelpunkt aus der Position plus
    halber Länge/Breite ermittelt.
    """
    if hasattr(box, "center_x_mm") and hasattr(box, "center_y_mm"):
        return float(box.center_x_mm), float(box.center_y_mm)

    # Fallback‑Berechnung: pos + ½ * (Kantenlänge)
    return float(box.pos_x_mm + box.length_mm / 2), float(box.pos_y_mm + box.width_mm / 2)


def _dimensions_identical(a: Box, b: Box) -> bool:
    """Prüft, ob Länge, Breite und Rotation zweier Boxen identisch sind."""
    return (
        a.length_mm == b.length_mm
        and a.width_mm == b.width_mm
        and a.rot_deg == b.rot_deg
    )


def _within_snap_tolerance(a: Box, b: Box) -> bool:
    """True, wenn sich die Box‑Mittelpunkte in X- und Y‑Richtung maximal ±Toleranz unterscheiden."""
    tol = _snap_tolerance()
    acx, acy = _box_center(a)
    bcx, bcy = _box_center(b)
    return abs(acx - bcx) <= tol and abs(acy - bcy) <= tol


def _remaining_height_ok(current_height_mm: int, next_height_mm: int, door_height_mm: int) -> bool:
    """Prüft, ob die resultierende Stapelhöhe noch unterhalb der Türhöhe liegt."""
    return current_height_mm + next_height_mm <= door_height_mm


def _raise_geometry(msg: str) -> None:
    """Kapselt das Werfen einer zentralen GeometryError‑Exception."""
    raise GeometryError(msg)


# ---------------------------------------------------------------------------#
# Öffentliche API                                                            #
# ---------------------------------------------------------------------------#


def can_stack(box_a: Box, box_b: Box, container: Container) -> bool:
    """
    Liefert *True*, wenn `box_a` und `box_b` miteinander stapelbar sind.

    Bedingungen
    -----------
    1. Identische Länge, Breite **und** Rotation
    2. Mittelpunkte liegen innerhalb ±10 mm (Snap‑Toleranz)
    3. Gesamthöhe überschreitet nicht die Container‑Türhöhe
    """
    if not _dimensions_identical(box_a, box_b):
        return False

    if not _within_snap_tolerance(box_a, box_b):
        return False

    if not _remaining_height_ok(box_a.height_mm, box_b.height_mm, container.door_height_mm):
        return False

    return True


def create_stack(boxes: List[Box], container: Container) -> Stack:
    """
    Erzeugt einen neuen Stapel aus einer Liste kompatibler Boxen.

    * Die Funktion verändert **keine** Listenreferenzen der Aufrufer‑Seite,
      mutiert jedoch die Box‑Objekte selbst, um sie exakt auf den Stapel
      zu „snappen“ (pos_x_mm/pos_y_mm).
    * Bei Inkompatibilität wird `GeometryError` geworfen.
    """
    if not boxes:
        _raise_geometry("Die Box‑Liste ist leer; ein Stapel benötigt mindestens eine Box.")

    first = boxes[0]

    # Validierung aller Boxen
    for idx, bx in enumerate(boxes[1:], start=2):
        if not can_stack(first, bx, container):
            _raise_geometry(
                f"Box {idx} ist nicht stapelbar mit der ersten Box – "
                "prüfe Abmessungen, Rotation, Snap‑Toleranz oder Türhöhe."
            )

    total_height = sum(b.height_mm for b in boxes)
    if total_height > container.door_height_mm:
        _raise_geometry(
            f"Gesamthöhe {total_height} mm überschreitet die Türhöhe "
            f"({container.door_height_mm} mm) des Containers."
        )

    # Alle Boxen exakt auf die Koordinaten der ersten Box ausrichten
    for b in boxes:
        b.pos_x_mm = first.pos_x_mm
        b.pos_y_mm = first.pos_y_mm

    # Neuen Stapel erzeugen (Name: „Stack_<FirstBoxName>“)
    stack_name = f"Stack_{getattr(first, 'name', 'unnamed')}"
    new_stack = Stack(
        name=stack_name,
        boxes=list(boxes),  # Kopie der Referenzen
        pos_x_mm=first.pos_x_mm,
        pos_y_mm=first.pos_y_mm,
        height_mm=total_height,
    )
    return new_stack


def add_to_stack(stack: Stack, box: Box, container: Container) -> Stack:
    """
    Fügt `box` dem bestehenden `stack` hinzu, sofern alle Bedingungen erfüllt sind.

    * Mutiert **sowohl** den Stapel als auch die Box in‑place.
    * Wirft `GeometryError`, falls Stapeln nicht möglich ist.
    * Gibt dieselbe Stapel‑Instanz zurück (Fluent‑Style).
    """
    if not stack.boxes:
        _raise_geometry("Ungültiger Stapel: enthält keine Boxen.")

    reference_box = stack.boxes[0]

    if not _dimensions_identical(reference_box, box):
        _raise_geometry("Box‑Abmessungen oder Rotation passen nicht zum bestehenden Stapel.")

    # Snap‑Toleranz prüfen
    if not _within_snap_tolerance(reference_box, box):
        _raise_geometry(
            "Box liegt außerhalb der zulässigen Snap‑Toleranz "
            f"({_snap_tolerance()} mm) zum Stapel."
        )

    # Höhe prüfen
    if not _remaining_height_ok(stack.height_mm, box.height_mm, container.door_height_mm):
        _raise_geometry(
            f"Neue Stapelhöhe ({stack.height_mm + box.height_mm} mm) "
            f"überschreitet die zulässige Türhöhe ({container.door_height_mm} mm)."
        )

    # Box exakt auf Stapel‑Position setzen
    box.pos_x_mm = stack.pos_x_mm
    box.pos_y_mm = stack.pos_y_mm

    # Stapel aktualisieren
    stack.boxes.append(box)
    stack.height_mm += box.height_mm

    return stack
