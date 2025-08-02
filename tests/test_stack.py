import pytest

from container_tool.core.models import Box, Container, Stack, GeometryError
from container_tool.core.stack import can_stack, create_stack, add_to_stack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def container() -> Container:
    """Standard-Container 40 ft mit 2 228 mm Türhöhe."""
    return Container(
        id="40ft-std",
        name="40 ft Standard Container",
        inner_length_mm=12_000,
        inner_width_mm=2_300,
        inner_height_mm=2_393,
        door_height_mm=2_228,
    )


@pytest.fixture()
def base_boxes() -> list[Box]:
    """Drei identische Boxen (1 000 × 1 000 × 500 mm) auf gleicher Position."""
    return [
        Box(
            name=f"Box{i}",
            length_mm=1_000,
            width_mm=1_000,
            height_mm=500,
            pos_x_mm=100,
            pos_y_mm=200,
            rot_deg=0,
        )
        for i in range(3)
    ]


# ---------------------------------------------------------------------------
# can_stack
# ---------------------------------------------------------------------------

def test_can_stack_true_with_identical_boxes(container, base_boxes):
    a, b = base_boxes[0], base_boxes[1]
    assert can_stack(a, b, container) is True


@pytest.mark.parametrize(
    "modify",
    [
        lambda b: setattr(b, "length_mm", 900),          # abweichende Länge
        lambda b: setattr(b, "rot_deg", 90),             # andere Rotation
        lambda b: setattr(b, "pos_x_mm", 200),           # Abstand > Snap
    ],
)
def test_can_stack_false_with_incompatible_boxes(container, base_boxes, modify):
    a, b = base_boxes[0], base_boxes[1]
    modify(b)
    assert can_stack(a, b, container) is False


# ---------------------------------------------------------------------------
# create_stack
# ---------------------------------------------------------------------------

def test_create_stack_sums_height_and_keeps_position(container, base_boxes):
    stack = create_stack(base_boxes, container)
    assert isinstance(stack, Stack)
    assert stack.box_count() == 3
    assert stack.total_height_mm() == 3 * 500
    assert stack.pos_x_mm == base_boxes[0].pos_x_mm
    assert stack.pos_y_mm == base_boxes[0].pos_y_mm


def test_create_stack_raises_when_exceeding_door_height(container):
    tall_boxes = [
        Box(
            name=f"Tall{i}",
            length_mm=1_000,
            width_mm=1_000,
            height_mm=1_200,  # zwei Stück überschreiten Türhöhe 2 228 mm
            pos_x_mm=0,
            pos_y_mm=0,
        )
        for i in range(2)
    ]
    with pytest.raises(GeometryError):
        create_stack(tall_boxes, container)


# ---------------------------------------------------------------------------
# add_to_stack
# ---------------------------------------------------------------------------

def test_add_to_stack_extends_stack_and_counts(container, base_boxes):
    # Starte mit zwei Boxen im Stapel
    initial_stack = create_stack(base_boxes[:2], container)
    before_count = initial_stack.box_count()
    before_height = initial_stack.total_height_mm()

    # Füge dritte Box hinzu
    updated_stack = add_to_stack(initial_stack, base_boxes[2], container)

    assert updated_stack is initial_stack                # gleicher Stapel-Ref
    assert updated_stack.box_count() == before_count + 1
    assert updated_stack.total_height_mm() == before_height + base_boxes[2].height_mm
