# tests/test_models.py
"""
Unit-Tests für die Datenmodelle in src/container_tool/core/models.py
-------------------------------------------------------------------
Läuft mit `pytest` innerhalb weniger Millisekunden.
"""
from __future__ import annotations

import pathlib
import sys
from typing import List

import pytest

# --------------------------------------------------------------------------- #
#  Quell-Pfad (src/) zu sys.path hinzufügen, falls nicht installiert
# --------------------------------------------------------------------------- #
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if SRC_PATH.exists() and str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# --------------------------------------------------------------------------- #
#  Modelle importieren
# --------------------------------------------------------------------------- #
from container_tool.core.models import Box, Container, Project, Stack

# --------------------------------------------------------------------------- #
#  Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture()
def sample_container() -> Container:
    """Minimal gültiger 40 ft-Container."""
    return Container(
        id="40ft-std",
        name="40 ft Standard",
        inner_length_mm=12_000,
        inner_width_mm=2_300,
        inner_height_mm=2_393,
        door_height_mm=2_228,
    )


@pytest.fixture()
def box_0deg() -> Box:
    """Box ohne Rotation."""
    return Box(
        name="Box_A",
        length_mm=1_000,
        width_mm=800,
        height_mm=600,
        weight_kg=10.0,
        color_hex="#FF0000",
        pos_x_mm=100,
        pos_y_mm=200,
        rot_deg=0,
    )


@pytest.fixture()
def box_90deg() -> Box:
    """Box mit 90°-Rotation."""
    return Box(
        name="Box_B",
        length_mm=1_000,
        width_mm=800,
        height_mm=600,
        weight_kg=0.0,  # bewusst 0 kg
        color_hex="#00FF00",
        pos_x_mm=50,
        pos_y_mm=75,
        rot_deg=90,
    )


@pytest.fixture()
def sample_stack() -> Stack:
    """Stapel aus drei identischen Boxen (je 5 kg)."""
    boxes: List[Box] = [
        Box(
            name=f"StackBox_{i}",
            length_mm=600,
            width_mm=400,
            height_mm=300,
            weight_kg=5.0,
            color_hex="#0000FF",
            pos_x_mm=0,
            pos_y_mm=0,
            rot_deg=0,
        )
        for i in range(3)
    ]
    return Stack(name="Stack_Test", _boxes=boxes)


@pytest.fixture()
def sample_project(sample_container, box_0deg, box_90deg, sample_stack) -> Project:
    """Projekt mit zwei Einzelboxen und einem Stapel."""
    return Project(
        container=sample_container,
        boxes=[box_0deg, box_90deg, sample_stack],
    )


# --------------------------------------------------------------------------- #
#  Tests
# --------------------------------------------------------------------------- #
def test_box_roundtrip_serialization(box_0deg):
    """Box → dict → Box muss identische Attribute liefern."""
    data = box_0deg.to_dict()
    restored = Box.from_dict(data)
    assert restored.to_dict() == data


def test_box_from_dict_missing_weight():
    """weight_kg kann fehlen und wird dann als 0.0 gesetzt."""
    raw = {
        "type": "box",
        "name": "NoWeight",
        "length_mm": 500,
        "width_mm": 500,
        "height_mm": 500,
        "color_hex": "#ABCDEF",
        "pos_x_mm": 0,
        "pos_y_mm": 0,
        "rot_deg": 0,
    }
    box = Box.from_dict(raw)  # weight_kg fehlt absichtlich
    assert box.weight_kg == 0.0


@pytest.mark.parametrize(
    "box,expected_bbox",
    [
        (
            pytest.lazy_fixture("box_0deg"),
            (100, 200, 1100, 1000),  # x, y, x+L, y+B
        ),
        (
            pytest.lazy_fixture("box_90deg"),
            (50, 75, 850, 1075),  # x, y, x+B, y+L (Rot. 90°)
        ),
    ],
)
def test_box_bbox(box, expected_bbox):
    """bbox() muss Länge/Breite abhängig von rot_deg korrekt berechnen."""
    assert box.bbox() == expected_bbox


def test_stack_total_height(sample_stack):
    """Stapel-Gesamthöhe = Anzahl * Einzelhöhe."""
    expected = len(sample_stack) * sample_stack.height_mm
    assert sample_stack.total_height_mm() == expected


def test_project_metrics(sample_project):
    """Project berechnet Gesamtgewicht und Boxanzahl korrekt."""
    # Erwartete Werte berechnen
    total_weight = (
        sample_project.boxes[0].weight_kg
        + sample_project.boxes[1].weight_kg
        + sample_project.boxes[2].total_weight_kg()
    )
    total_boxes = (
        1
        + 1
        + sample_project.boxes[2].box_count()
    )

    assert pytest.approx(sample_project.total_weight_kg(), rel=1e-9) == total_weight
    assert (
        sum(item.box_count() if isinstance(item, Stack) else 1 for item in sample_project.boxes)
        == total_boxes
    )
