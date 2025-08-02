import pytest

from container_tool.core.collision import (
    is_within_container,
    check_collisions,
    DOOR_HEIGHT_COLLISION,
)
from container_tool.core.models import Container, Box, Stack


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def container() -> Container:
    """A small 1 m × 1 m test container with a 2 m door height."""
    return Container(
        id="test-ctn",
        name="Test-Container",
        inner_length_mm=1_000,
        inner_width_mm=1_000,
        inner_height_mm=2_500,
        door_height_mm=2_000,
    )


# --------------------------------------------------------------------------- #
# is_within_container
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "pos_x,pos_y,len_mm,wid_mm,expected_inside",
    [
        (100, 100, 400, 400, True),   # komplett innerhalb
        (800, 800, 300, 300, False),  # L & B überschreiten Grenze
        (950, 0,   100, 100, False),  # Länge überschreitet
        (0,   900, 200, 200, False),  # Breite überschreitet
        (0,   0,   1_000, 1_000, True),  # exakt an den Kanten  → gültig
    ],
)
def test_is_within_container(container, pos_x, pos_y, len_mm, wid_mm, expected_inside):
    box = Box(
        name="box",
        length_mm=len_mm,
        width_mm=wid_mm,
        height_mm=100,
        color_hex="#abcdef",
        pos_x_mm=pos_x,
        pos_y_mm=pos_y,
    )
    assert is_within_container(box, container) is expected_inside


# --------------------------------------------------------------------------- #
# check_collisions – Überlappungen
# --------------------------------------------------------------------------- #
def test_check_collisions_overlap_vs_free(container):
    # Platzierte Box (links-vorn)
    fixed = Box(
        name="fixed",
        length_mm=400,
        width_mm=400,
        height_mm=200,
        color_hex="#ff0000",
        pos_x_mm=0,
        pos_y_mm=0,
    )

    # 1) Überlappt mit `fixed`
    overlapping = Box(
        name="overlap",
        length_mm=400,
        width_mm=400,
        height_mm=200,
        color_hex="#00ff00",
        pos_x_mm=200,  # Verschiebung nur um 200 mm  → Überdeckungs­fläche vorhanden
        pos_y_mm=200,
    )
    ok, collisions = check_collisions(overlapping, [fixed], container)
    assert not ok
    # Die bestehende Box soll als Kollision gemeldet werden
    assert fixed in collisions
    assert len(collisions) == 1

    # 2) Kollisionsfrei platzierbar (rechts)
    free = Box(
        name="free",
        length_mm=400,
        width_mm=400,
        height_mm=200,
        color_hex="#0000ff",
        pos_x_mm=500,
        pos_y_mm=0,
    )
    ok, collisions = check_collisions(free, [fixed], container)
    assert ok
    assert collisions == []


# --------------------------------------------------------------------------- #
# check_collisions – Türhöhen-Prüfung (Stacks)
# --------------------------------------------------------------------------- #
def _make_stack(box_height_mm: int, count: int) -> Stack:
    """Hilfs-Factory: erzeugt einen Stack aus *count* identischen Boxen."""
    boxes = [
        Box(
            name=f"b{i}",
            length_mm=500,
            width_mm=500,
            height_mm=box_height_mm,
            color_hex="#123456",
            pos_x_mm=0,
            pos_y_mm=0,
        )
        for i in range(count)
    ]
    stack = Stack(name="test_stack", _boxes=boxes)
    # Kollisions-Logik prüft `height` → Expose reale Stapelhöhe als Attribut
    stack.height = stack.total_height_mm()
    return stack


def test_check_collisions_door_height(container):
    # Stapel mit 3 × 800 mm = 2 400 mm  > 2 000 mm Türhöhe  → Fehler
    violating_stack = _make_stack(800, 3)
    ok, collisions = check_collisions(violating_stack, [], container)
    assert not ok
    assert DOOR_HEIGHT_COLLISION in collisions

    # Stapel mit 2 × 800 mm = 1 600 mm  < Türhöhe  → ok
    valid_stack = _make_stack(800, 2)
    ok, collisions = check_collisions(valid_stack, [], container)
    assert ok
    assert collisions == []
