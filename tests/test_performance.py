"""
Performance benchmarks for container_tool.

Run with:
    pytest tests/test_performance.py --benchmark-only
"""

from __future__ import annotations

import pytest

from container_tool.core.collision import check_collisions
from container_tool.core.models import Box, Container

# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_scene():
    """
    Returns a tuple (candidate_box, placed_boxes, container) prepared for
    performance testing.

    • 40 ft container (inner dimensions 12 000 × 2 300 mm)
    • 200 pre-placed boxes (40 distinct types × 5 each)
    """
    container = Container(
        id="40ft-std",
        name="40 ft Standard Container",
        inner_length_mm=12_000,
        inner_width_mm=2_300,
        inner_height_mm=2_393,
        door_height_mm=2_228,
    )

    placed: list[Box] = []
    spacing = 50  # mm gap between boxes
    cur_x = 0
    cur_y = 0

    for t in range(40):  # 40 types
        length = 500 + t * 5
        width = 400 + (t % 8) * 3
        height = 300
        for n in range(5):  # 5 boxes per type → 200 boxes total
            box = Box(
                name=f"type{t}_box{n}",
                length_mm=length,
                width_mm=width,
                height_mm=height,
                color_hex=f"#{(t * 57347) & 0xFFFFFF:06X}",
                pos_x_mm=cur_x,
                pos_y_mm=cur_y,
                rot_deg=0,
            )
            placed.append(box)
            cur_x += length + spacing
            if cur_x + length > container.inner_length_mm:
                cur_x = 0
                cur_y += width + spacing

    candidate = Box(
        name="candidate",
        length_mm=placed[0].length_mm,
        width_mm=placed[0].width_mm,
        height_mm=placed[0].height_mm,
        color_hex="#000000",
        pos_x_mm=cur_x,
        pos_y_mm=cur_y,
        rot_deg=0,
    )
    return candidate, placed, container


# ------------------------------------------------------------------------------
# Collision benchmark
# ------------------------------------------------------------------------------


@pytest.mark.benchmark(group="collision")
def test_check_collisions_under_50ms(benchmark, sample_scene):
    """
    The median runtime of `check_collisions()` must stay below 50 ms
    with 200 already placed boxes.
    """
    candidate, placed, container = sample_scene

    def _run():
        check_collisions(candidate, placed, container)

    result = benchmark(_run)
    median_ms = result.stats["median"] * 1_000  # seconds → ms
    assert median_ms < 50, f"Median {median_ms:.2f} ms exceeds 50 ms"


# ------------------------------------------------------------------------------
# Optional zoom benchmark (requires PySide6)
# ------------------------------------------------------------------------------


@pytest.mark.benchmark(group="zoom")
def test_canvas_zoom_performance(benchmark):
    """
    Optional: ensure 100 consecutive scale operations achieve
    ≥ 25 FPS and < 100 ms per frame latency.

    Skips automatically if PySide6 is not available.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from container_tool.gui.canvas_2d import Canvas2D

    app = QApplication.instance() or QApplication([])  # noqa: F841

    canvas = Canvas2D(scene_name="waiting_area")

    def _zoom():
        for _ in range(50):  # 50× in & out = 100 operations
            canvas.scale(1.1, 1.1)
            canvas.scale(0.9, 0.9)

    result = benchmark(_zoom)
    total_s = result.stats["mean"]              # seconds for 100 ops
    fps = 100 / total_s if total_s else float("inf")
    latency_ms = (total_s / 100) * 1_000

    assert fps >= 25, f"FPS too low: {fps:.1f}"
    assert latency_ms < 100, f"Latency {latency_ms:.1f} ms exceeds limit"
