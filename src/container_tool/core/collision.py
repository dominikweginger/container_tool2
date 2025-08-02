Kollisions‑ und Türhöhen‑Logik für das 2D‑Packing‑GUI.
Das Modul ist **rein logisch** (kein GUI‑Import) und
komplett *stateless*, sodass es gefahrlos aus
mehreren Threads aufgerufen werden kann.

Public API
----------
- `check_collisions(candidate, placed, container)`
- `is_within_container(obj, container)`
- `overlaps(a_bbox, b_bbox)`

Konstanten
----------
- `DOOR_HEIGHT_COLLISION` – Sentinel‑String, der eine
  Verletzung der Container‑Türhöhe kennzeichnet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple, Union

# Typ‑Aliase ---------------------------------------------------------------
BBox = Tuple[float, float, float, float]  # (x_min, y_min, x_max, y_max)

# Sentinel für GUI‑Layer (Türhöhe überschritten)
DOOR_HEIGHT_COLLISION: str = "_door_height_"

# Cell‑Größe für Spatial Grid (mm). Kann ggf. projektweit konfiguriert werden.
_CELL_SIZE: float = 1_000.0

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------- #
# Hilfsfunktionen                                                            #
# -------------------------------------------------------------------------- #
def overlaps(a: BBox, b: BBox) -> bool:
    """
    Prüft, ob sich zwei Axis‑Aligned‑Bounding‑Boxes *überlappen*.

    Kante‑an‑Kante (dist == 0) gilt **nicht** als Überlappung.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    # Keine Überlappung, wenn eine Box vollständig links/rechts/oben/unten liegt
    if ax1 <= bx0 or bx1 <= ax0:  # X‑Achse (Kante an Kante erlaubt)
        return False
    if ay1 <= by0 or by1 <= ay0:  # Y‑Achse
        return False
    return True


def is_within_container(obj: Union["Box", "Stack"], container: "Container") -> bool:
    """
    True, wenn sich das Objekt vollständig innerhalb der Innenabmessungen
    des Containers befindet (Kante‑an‑Kante erlaubt).

    Benötigt Container‑Attribute:
        - inner_length oder length
        - inner_width  oder width
    """
    x0, y0, x1, y1 = _get_bbox(obj)

    length = getattr(container, "inner_length", None) or getattr(container, "length", None)
    width = getattr(container, "inner_width", None) or getattr(container, "width", None)

    if length is None or width is None:
        raise ValueError("Container muss 'inner_length/length' und 'inner_width/width' besitzen.")

    inside = 0.0 <= x0 and x1 <= length and 0.0 <= y0 and y1 <= width
    logger.debug("is_within_container: %s (len=%s, wid=%s) -> %s", obj, length, width, inside)
    return inside


# -------------------------------------------------------------------------- #
# Kernfunktion                                                               #
# -------------------------------------------------------------------------- #
def check_collisions(
    candidate: Union["Box", "Stack"],
    placed: List[Union["Box", "Stack"]],
    container: "Container",
) -> Tuple[bool, List[Union["Box", "Stack", str]]]:
    """
    Prüft, ob *candidate* ohne Kollision in den Container gelegt werden kann.

    Rückgabe
    --------
    ok : bool
        True, wenn keine Kollisionen vorliegen.
    kollidierende : list[Box | Stack | str]
        Liste der kollidierenden Objekte. Enthält zusätzlich
        `DOOR_HEIGHT_COLLISION`, falls die Türhöhe überschritten wurde.
    """
    collisions: List[Union["Box", "Stack", str]] = []

    # 1) Container‑Grenzen ---------------------------------------------------
    if not is_within_container(candidate, container):
        logger.debug("Boundary‑Kollision mit Container.")
        collisions.append(candidate)  # candidate selbst markiert GUI als Rot

    # 2) Türhöhe (nur für Stacks) -------------------------------------------
    if _is_stack(candidate) and _exceeds_door_height(candidate, container):
        logger.debug("Türhöhe überschritten (%.2f mm).", _get_height(candidate))
        collisions.append(DOOR_HEIGHT_COLLISION)

    # Früher Abbruch, wenn schon Grenz‑/Türkollision
    # (spart Grid‑Aufbau, aber nur wenn tatsächlich Kollision vorliegt)
    # -> bewusst *kein* Return hier: GUI möchte evtl. ALLE Fehler sehen
    # ----------------------------------------------------------------------

    # 3) Überlappungen gegen vorhandene Objekte -----------------------------
    spatial_index = _build_spatial_grid(placed)
    cand_bbox = _get_bbox(candidate)

    for cell in _cells_for_bbox(cand_bbox):
        for other in spatial_index.get(cell, ()):
            # Eigene Bounding‑Box bereits im Grid; Duplikat‑Check über 'is'
            if other is candidate:
                continue
            if overlaps(cand_bbox, _get_bbox(other)):
                logger.debug("Überlappung mit %s", other)
                collisions.append(other)

    ok = len(collisions) == 0
    return ok, collisions


# -------------------------------------------------------------------------- #
# Interne Helfer                                                             #
# -------------------------------------------------------------------------- #
def _get_bbox(obj: Union["Box", "Stack"]) -> BBox:
    """Ermittelt die Bounding‑Box eines Objekts, bevorzugt über `bbox()`."""
    if hasattr(obj, "bbox") and callable(obj.bbox):  # type: ignore[attr-defined]
        return tuple(map(float, obj.bbox()))  # type: ignore[return-value]
    # Fallback: Versuche generische Attribute
    try:
        x = float(obj.x)
        y = float(obj.y)
        length = float(getattr(obj, "length", obj.length_mm))  # type: ignore[attr-defined]
        width = float(getattr(obj, "width", obj.width_mm))    # type: ignore[attr-defined]
    except AttributeError as exc:
        raise ValueError(f"Objekt {obj!r} besitzt keine bbox() und keine (x,y,length,width)‑Attribute.") from exc
    return (x, y, x + length, y + width)


def _get_height(obj: "Stack") -> float:
    """Liefert die absolute Höhe eines Stacks (mm)."""
    return float(getattr(obj, "height", getattr(obj, "height_mm", 0.0)))


def _is_stack(obj: Union["Box", "Stack"]) -> bool:  # duck‑typing‑Check
    return obj.__class__.__name__.lower().startswith("stack") or hasattr(obj, "layers")


def _exceeds_door_height(stack: "Stack", container: "Container") -> bool:
    door_height = getattr(container, "door_height", None) or getattr(
        container, "door_height_mm", None
    )
    if door_height is None:
        raise ValueError("Container muss 'door_height' bzw. 'door_height_mm' besitzen.")
    return _get_height(stack) > float(door_height)


# Spatial Grid -------------------------------------------------------------
Grid = Dict[Tuple[int, int], List[Union["Box", "Stack"]]]


def _build_spatial_grid(objs: Iterable[Union["Box", "Stack"]]) -> Grid:
    """Erstellt ein einfaches Spatial Hash Grid für schnelle Nachbarsuche."""
    grid: Grid = {}
    for obj in objs:
        for cell in _cells_for_bbox(_get_bbox(obj)):
            grid.setdefault(cell, []).append(obj)
    logger.debug("Spatial‑Grid gebaut: %d Zellen", len(grid))
    return grid


def _cells_for_bbox(bbox: BBox) -> List[Tuple[int, int]]:
    """
    Liefert alle Zellkoordinaten, die eine Bounding‑Box schneidet.

    Das Uniform‑Grid hat feste Rastergröße `_CELL_SIZE` in mm.
    """
    x0, y0, x1, y1 = bbox
    x_start = int(x0 // _CELL_SIZE)
    y_start = int(y0 // _CELL_SIZE)
    x_end = int((x1) // _CELL_SIZE)
    y_end = int((y1) // _CELL_SIZE)

    return [(ix, iy) for ix in range(x_start, x_end + 1) for iy in range(y_start, y_end + 1)]


# -------------------------------------------------------------------------- #
# Modul‑Konfiguration                                                        #
# -------------------------------------------------------------------------- #
__all__ = [
    "check_collisions",
    "is_within_container",
    "overlaps",
    "DOOR_HEIGHT_COLLISION",
]
