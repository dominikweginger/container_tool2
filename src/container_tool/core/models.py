from __future__ import annotations
import datetime
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Tuple, Union


# --------------------------------------------------------------------------- #
#  Eigene Fehlertypen
# --------------------------------------------------------------------------- #
class ModelError(Exception):
    """Basisfehler für Modell-Operationen."""


class GeometryError(ModelError):
    """Fehler bei geometrischen Prüfungen (z. B. Stapel-Passung)."""


class ValidationError(ModelError):
    """Fehlerhafte Eingabewerte oder unzulässiger Zustand."""


# --------------------------------------------------------------------------- #
#  Container
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Container:
    id: str
    name: str
    inner_length_mm: int
    inner_width_mm: int
    inner_height_mm: int
    door_height_mm: int
    # --- Kompatibilitäts‑Aliase für den PDF‑Export ---
    length = property(lambda self: self.inner_length_mm)
    width = property(lambda self: self.inner_width_mm)

    def __post_init__(self) -> None:
        if any(v <= 0 for v in (
            self.inner_length_mm,
            self.inner_width_mm,
            self.inner_height_mm,
            self.door_height_mm,
        )):
            raise ValidationError("Container-Maße müssen positiv sein.")

    # ------------------------------------------------------------------ #
    #  Serialisierung
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "inner_length_mm": self.inner_length_mm,
            "inner_width_mm": self.inner_width_mm,
            "inner_height_mm": self.inner_height_mm,
            "door_height_mm": self.door_height_mm,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Container":
        return cls(**data)


# --------------------------------------------------------------------------- #
#  Box
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Box:
    name: str
    length_mm: int
    width_mm: int
    height_mm: int
    weight_kg: float = 0.0
    color_hex: str = "#FFFFFF"
    pos_x_mm: int = 0
    pos_y_mm: int = 0
    rot_deg: int = 0  # 0 oder 90
    # --- Kompatibilitäts-Aliase für den PDF-Export ---
    x = property(lambda self: self.pos_x_mm)
    y = property(lambda self: self.pos_y_mm)
    length = property(lambda self: self.length_mm)
    width = property(lambda self: self.width_mm)
    height = property(lambda self: self.height_mm)
    weight = property(lambda self: self.weight_kg)

    # ---------------------------- Validierung ---------------------------- #
    def __post_init__(self) -> None:
        if self.rot_deg not in (0, 90):
            raise ValidationError("rot_deg muss 0 oder 90 sein.")
        if any(v <= 0 for v in (self.length_mm, self.width_mm, self.height_mm)):
            raise ValidationError("Box-Maße müssen positiv sein.")
        if not (isinstance(self.color_hex, str) and self.color_hex.startswith("#")):
            raise ValidationError("color_hex muss ein Hex-String sein.")
        if self.weight_kg is None:
            self.weight_kg = 0.0

    # ----------------------- Geometrische Helfer ------------------------ #
    def bbox(self) -> Tuple[int, int, int, int]:
        """(x_min, y_min, x_max, y_max) in mm – abhängig von rot_deg."""
        if self.rot_deg == 0:
            return (
                self.pos_x_mm,
                self.pos_y_mm,
                self.pos_x_mm + self.length_mm,
                self.pos_y_mm + self.width_mm,
            )
        return (
            self.pos_x_mm,
            self.pos_y_mm,
            self.pos_x_mm + self.width_mm,
            self.pos_y_mm + self.length_mm,
        )

    def center(self) -> Tuple[float, float]:
        x_min, y_min, x_max, y_max = self.bbox()
        return ((x_min + x_max) / 2, (y_min + y_max) / 2)

    @property
    def volume_mm3(self) -> int:
        return self.length_mm * self.width_mm * self.height_mm

    @property
    def footprint_mm2(self) -> int:
        return self.length_mm * self.width_mm

    # --------------------------- Operationen ---------------------------- #
    def rotate(self) -> None:
        """Toggle-Drehung um 90 °. Höhe bleibt unverändert."""
        self.rot_deg = 90 if self.rot_deg == 0 else 0

    # ---------------------------- Gleichheit ---------------------------- #
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Box):
            return NotImplemented
        return self.length_mm == other.length_mm and self.width_mm == other.width_mm

    def __hash__(self) -> int:  # erlaubt Nutzung in Sets/Dicts
        return hash((self.length_mm, self.width_mm))

    # --------------------------- Serialisierung ------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "box",
            "name": self.name,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "weight_kg": self.weight_kg,
            "color_hex": self.color_hex,
            "pos_x_mm": self.pos_x_mm,
            "pos_y_mm": self.pos_y_mm,
            "rot_deg": self.rot_deg,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Box":
        data = dict(data)
        data.pop("type", None)
        return cls(**data)


# --------------------------------------------------------------------------- #
#  Stack
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Stack:
    name: str
    _boxes: List[Box] = field(default_factory=list)
    SNAP_TOLERANCE_MM: int = 10

    # ---------------------------- Validierung --------------------------- #
    def __post_init__(self) -> None:
        if not self._boxes:
            raise ValidationError("Ein Stack benötigt mindestens eine Box.")
        first = self._boxes[0]
        for b in self._boxes[1:]:
            if not (
                b.length_mm == first.length_mm
                and b.width_mm == first.width_mm
                and b.rot_deg == first.rot_deg
            ):
                raise ValidationError(
                    "Alle Boxen in einem Stack müssen Länge, Breite und Rotation teilen."
                )

    # ------------------------ Eigenschaften ---------------------------- #
    @property
    def pos_x_mm(self) -> int:  # Position ist für alle Boxen identisch
        return self._boxes[0].pos_x_mm

    @property
    def pos_y_mm(self) -> int:
        return self._boxes[0].pos_y_mm

    @property
    def rot_deg(self) -> int:
        return self._boxes[0].rot_deg

    @property
    def length_mm(self) -> int:
        return self._boxes[0].length_mm if self.rot_deg == 0 else self._boxes[0].width_mm

    @property
    def width_mm(self) -> int:
        return self._boxes[0].width_mm if self.rot_deg == 0 else self._boxes[0].length_mm

    @property
    def height_mm(self) -> int:
        return self._boxes[0].height_mm

    # ------------------------- Geometrie ------------------------------- #
    def bbox(self) -> Tuple[int, int, int, int]:
        if self.rot_deg == 0:
            return (
                self.pos_x_mm,
                self.pos_y_mm,
                self.pos_x_mm + self.length_mm,
                self.pos_y_mm + self.width_mm,
            )
        return (
            self.pos_x_mm,
            self.pos_y_mm,
            self.pos_x_mm + self.width_mm,
            self.pos_y_mm + self.length_mm,
        )

    def _center(self) -> Tuple[float, float]:
        return self._boxes[0].center()

    # --------------------------- Metriken ------------------------------ #
    def total_height_mm(self) -> int:
        return self.height_mm * len(self._boxes)

    def total_weight_kg(self) -> float:
        return sum(b.weight_kg for b in self._boxes)

    def box_count(self) -> int:
        return len(self._boxes)

    # -------------------------- Iterator ------------------------------- #
    def __iter__(self) -> Iterator[Box]:
        yield from self._boxes

    def __len__(self) -> int:
        return len(self._boxes)

    # ---------------------- Stapel-Operationen ------------------------- #
    def fits(self, box: Box) -> bool:
        """Prüft, ob `box` zu diesem Stapel passt."""
        first = self._boxes[0]
        if not (
            box.length_mm == first.length_mm
            and box.width_mm == first.width_mm
            and box.rot_deg == first.rot_deg
        ):
            return False
        cx1, cy1 = self._center()
        cx2, cy2 = box.center()
        return (
            abs(cx1 - cx2) <= self.SNAP_TOLERANCE_MM
            and abs(cy1 - cy2) <= self.SNAP_TOLERANCE_MM
        )

    def add_box(self, box: Box) -> None:
        """Fügt eine Box hinzu oder wirft GeometryError."""
        if not self.fits(box):
            raise GeometryError("Box passt nicht auf diesen Stapel.")
        box.pos_x_mm = self.pos_x_mm  # auf exakte Position klemmen
        box.pos_y_mm = self.pos_y_mm
        self._boxes.append(box)

    def rotate(self) -> None:
        """Dreht den gesamten Stapel (alle Boxen) um 90 °."""
        for b in self._boxes:
            b.rotate()

    # ------------------------- Serialisierung -------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        first = self._boxes[0]
        return {
            "type": "stack",
            "name": self.name,
            "pos_x_mm": self.pos_x_mm,
            "pos_y_mm": self.pos_y_mm,
            "rot_deg": self.rot_deg,
            "count": len(self._boxes),
            "length_mm": first.length_mm,
            "width_mm": first.width_mm,
            "height_mm": first.height_mm,
            "weight_kg": first.weight_kg,
            "color_hex": first.color_hex,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stack":
        data = dict(data)
        data.pop("type", None)
        count = data.pop("count")
        name = data.pop("name")
        pos_x = data.pop("pos_x_mm")
        pos_y = data.pop("pos_y_mm")
        rot_deg = data.pop("rot_deg")
        length_mm = data.pop("length_mm")
        width_mm = data.pop("width_mm")
        height_mm = data.pop("height_mm")
        weight_kg = data.pop("weight_kg")
        color_hex = data.pop("color_hex")

        boxes = [
            Box(
                name=f"{name}_{i+1}",
                length_mm=length_mm,
                width_mm=width_mm,
                height_mm=height_mm,
                weight_kg=weight_kg,
                color_hex=color_hex,
                pos_x_mm=pos_x,
                pos_y_mm=pos_y,
                rot_deg=rot_deg,
            )
            for i in range(count)
        ]
        return cls(name=name, _boxes=boxes)


# --------------------------------------------------------------------------- #
#  Project-Meta
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class ProjectMeta:
    created_at: datetime.datetime
    version: str
    user: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "user": self.user,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectMeta":
        return cls(
            created_at=datetime.datetime.fromisoformat(data["created_at"]),
            version=data["version"],
            user=data["user"],
        )


# --------------------------------------------------------------------------- #
#  Project
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Project:
    container: Container
    boxes: List[Union[Box, Stack]] = field(default_factory=list)
    meta: ProjectMeta = field(
        default_factory=lambda: ProjectMeta(
            datetime.datetime.utcnow(), "1.0.0", "unknown"
        )
    )
    _lock: threading.RLock = field(init=False, repr=False, default_factory=threading.RLock)

    # ----------------------- Thread-sichere Ops ------------------------- #
    def add(self, item: Union[Box, Stack]) -> None:
        with self._lock:
            self.boxes.append(item)

    def remove(self, item: Union[Box, Stack]) -> None:
        with self._lock:
            self.boxes.remove(item)

    # ----------------------------- Metriken ---------------------------- #
    def total_weight_kg(self) -> float:
        with self._lock:
            return sum(
                item.weight_kg if isinstance(item, Box) else item.total_weight_kg()
                for item in self.boxes
            )

    def max_height_mm(self) -> int:
        with self._lock:
            max_h = 0
            for item in self.boxes:
                if isinstance(item, Box):
                    max_h = max(max_h, item.height_mm)
                else:
                    max_h = max(max_h, item.total_height_mm())
            return max_h

    # ------------------------- Serialisierung -------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "container": self.container.to_dict(),
                "boxes": [item.to_dict() for item in self.boxes],
                "meta": self.meta.to_dict(),
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Project":
        container = Container.from_dict(data["container"])
        boxes: List[Union[Box, Stack]] = []
        for raw in data["boxes"]:
            item_type = raw.get("type")
            if item_type == "box":
                boxes.append(Box.from_dict(raw))
            elif item_type == "stack":
                boxes.append(Stack.from_dict(raw))
            else:
                raise ValidationError(f"Unbekannter Item-Typ: {item_type!r}")
        meta = ProjectMeta.from_dict(data["meta"])
        return cls(container=container, boxes=boxes, meta=meta)
