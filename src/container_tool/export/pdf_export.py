"""
pdf_export.py

Generates a comprehensive PDF export of the current packing‑project.
"""

from __future__ import annotations

import io
from collections import defaultdict
from datetime import datetime
from typing import List, Sequence, Optional

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
def _pil_to_reader(img: Image.Image, width_px: int = 800, height_px: int = 600) -> ImageReader:
    """Ensure *img* is exactly width_px × height_px and return an ImageReader."""
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    img = img.copy()
    img.thumbnail((width_px, height_px), Image.LANCZOS)

    if img.size != (width_px, height_px):
        padded = Image.new("RGB", (width_px, height_px), (255, 255, 255))
        off_x = (width_px - img.width) // 2
        off_y = (height_px - img.height) // 2
        padded.paste(img, (off_x, off_y))
        img = padded

    return ImageReader(img)


def _aggregate_boxes(boxes: Sequence["Box"]) -> List[List[str | int | float]]:
    """Aggregate identical boxes into rows: [Name, Count, L, B, H, Weight]."""
    grouped: dict[tuple, list] = defaultdict(lambda: [0])
    for b in boxes:
        key = (b.name, round(b.length, 2), round(b.width, 2),
               round(b.height, 2), round(b.weight, 2))
        grouped[key][0] += 1

    rows: List[List[str | int | float]] = []
    for (name, l, w, h, weight), (count,) in grouped.items():
        rows.append([name, count, l, w, h, weight])
    rows.sort(key=lambda r: r[0])
    return rows


def _build_table(rows: List[List[str | int | float]]) -> Table:
    """Return a styled ReportLab Table from *rows*."""
    data = [["Name", "Anzahl", "L", "B", "H", "Gewicht"]] + rows
    tbl = Table(data, hAlign="LEFT")

    style = TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ])

    for row in range(1, len(data)):
        if row % 2 == 0:
            style.add("BACKGROUND", (0, row), (-1, row), colors.whitesmoke)
    tbl.setStyle(style)
    return tbl


def _split_loaded_waiting(project: "Project") -> tuple[List["Box"], List["Box"]]:
    """Return (loaded, waiting) box lists based on footprint‑inside‑container check."""
    loaded, waiting = [], []
    ctn = project.container
    for b in project.boxes:
        if (0 <= b.x and 0 <= b.y and
                b.x + b.length <= ctn.length and
                b.y + b.width <= ctn.width):
            loaded.append(b)
        else:
            waiting.append(b)
    return loaded, waiting


def _draw_header_footer(c: canvas.Canvas, project_name: Optional[str] = None) -> None:
    """Draw header & footer on current page. If *project_name* is None, omit it."""
    pw, ph = A4
    m = 20 * mm
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.setFont("Helvetica-Bold", 12)
    header_text = ts if not project_name else f"{project_name} – {ts}"
    c.drawString(m, ph - m, header_text)
    c.setFont("Helvetica", 8)
    c.drawRightString(pw - m, m / 2, f"Seite {c.getPageNumber()}")


def _draw_labeled_image(c: canvas.Canvas, label: str, reader: ImageReader,
                        x: float, y: float, max_w: float) -> float:
    """Draw label + image, return new y‑cursor below the image."""
    img_w, img_h = 4 * 72, 3 * 72  # 800×600 @200 dpi → 4×3 in → pt
    if img_w > max_w:
        scale = max_w / img_w
        img_w *= scale
        img_h *= scale
    c.setFont("Helvetica-Bold", 10)
    c.drawString(x, y + img_h + 5, label)
    c.drawImage(reader, x, y, img_w, img_h, preserveAspectRatio=True, mask="auto")
    return y - img_h - 35


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def export_pdf(project: "Project",
               path: str,
               *,
               top_view: Image.Image | None = None,
               side_view: Image.Image | None = None,
               view_3d: Image.Image | None = None) -> None:
    """
    Create a PDF export for *project* at *path*.
    If images are None the function tries to import helper renderers.

    The function overwrites an existing file at *path* without confirmation.
    """
    from importlib import import_module

    if top_view is None:
        top_view = import_module("container_tool.render_2d").generate_top_view(project)
    if side_view is None:
        side_view = import_module("container_tool.render_2d").generate_side_view(project)
    if view_3d is None:
        view_3d = import_module("container_tool.render_3d").render_scene(project)

    top_r, side_r, view3d_r = map(_pil_to_reader, (top_view, side_view, view_3d))

    pw, ph = A4
    m = 20 * mm
    usable_w = pw - 2 * m
    c = canvas.Canvas(path, pagesize=A4)

    # Page 1 – Images
    _draw_header_footer(c)
    y = ph - m - 30
    for label, reader in (("Draufsicht (Top‑View)", top_r),
                          ("Seitenansicht (Side‑View)", side_r),
                          ("3‑D‑Ansicht", view3d_r)):
        y = _draw_labeled_image(c, label, reader, m, y, usable_w)
        if y < m + 300:
            c.showPage()
            _draw_header_footer(c)
            y = ph - m - 30
    c.showPage()

    # Page 2 – Tables
    _draw_header_footer(c)
    loaded, waiting = _split_loaded_waiting(project)
    tbl_loaded = _build_table(_aggregate_boxes(loaded))
    tbl_waiting = _build_table(_aggregate_boxes(waiting))

    y = ph - m - 30
    w, h = tbl_loaded.wrap(usable_w, ph)
    tbl_loaded.drawOn(c, m, y - h)
    y -= h + 30
    if y < m + h:           # start new page if not enough room
        c.showPage()
        _draw_header_footer(c)
        y = ph - m - 30
    w, h = tbl_waiting.wrap(usable_w, ph)
    tbl_waiting.drawOn(c, m, y - h)

    c.save()
