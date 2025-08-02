"""
render_3d.py
============

Offline 3‑D renderer for a loaded container scene.

Dieses Modul erzeugt einen **unsichtbaren OpenGL‑Kontext** (pygame‑Fenster
1 × 1 px, Flag HIDDEN) und rendert den beladenen Container aus fester,
isometrischer Perspektive. Das Ergebnis wird als ``PIL.Image`` in
800 × 600 Pixel (RGBA) zurückgegeben.

Achsen­belegung
---------------
X‑Achse → Containerlänge
Y‑Achse → Containerbreite
Z‑Achse → Containerhöhe

Abhängigkeiten
--------------
PyOpenGL ≥ 3.1, numpy, Pillow, pygame ≥ 2.0

Öffentliche API
---------------
    render_scene(project: Project) -> PIL.Image

Die Funktion ist **synchron** – Threading wird extern (z. B. im
PDF‑Export) gehandhabt. Bei fatalen Fehlern wird ein Platzhalterbild
zurückgegeben; das GUI bleibt dadurch reaktionsfähig.
"""
from __future__ import annotations

import logging
from typing import Any, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# -------------------------------------------------------------------------
# Optionale Runtime‑Abhängigkeit (GL‑Kontext via verstecktem Fenster)
try:
    import pygame
    from pygame import display
    from pygame.locals import DOUBLEBUF, OPENGL, HIDDEN
except ImportError:  # pragma: no cover
    pygame = None  # type: ignore

# PyOpenGL – Import wird verzögert behandelt, um Placeholder zu erlauben
try:
    from OpenGL.GL import (
        glBegin,
        glClear,
        glClearColor,
        glColor4f,
        glEnable,
        glEnd,
        glLineWidth,
        glLoadIdentity,
        glMatrixMode,
        glReadPixels,
        glVertex3f,
        GL_COLOR_BUFFER_BIT,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_LINES,
        GL_MODELVIEW,
        GL_PROJECTION,
        GL_QUADS,
        GL_LIGHTING,
        GL_LIGHT0,
        GL_LIGHT1,
        glLightfv,
        GL_AMBIENT,
        GL_DIFFUSE,
        GL_POSITION,
        GL_MULTISAMPLE,
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        glViewport,
    )
    from OpenGL.GLU import gluLookAt, gluPerspective
except Exception as exc:  # pragma: no cover
    OpenGL_import_error = exc
else:
    OpenGL_import_error = None

# -------------------------------------------------------------------------
_WIDTH, _HEIGHT = 800, 600
logger = logging.getLogger(__name__)

# ============================== Hilfsfunktionen ===========================


def _hex_to_rgb_f(hx: str) -> tuple[float, float, float]:
    """``#RRGGBB`` → (r, g, b) im Bereich 0 … 1 (float)."""
    hx = hx.lstrip("#")
    if len(hx) != 6:
        raise ValueError(f"Invalid HEX color: {hx!r}")
    r, g, b = (int(hx[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    return r, g, b


def _placeholder_image(msg: str) -> Image.Image:
    """Erzeugt ein weißes 800 × 600‑PNG mit roter Fehlermeldung."""
    img = Image.new("RGBA", (_WIDTH, _HEIGHT), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()
    tw, th = draw.textbbox((0, 0), msg, font=font)[2:]
    draw.text(((_WIDTH - tw) // 2, (_HEIGHT - th) // 2), msg, fill=(255, 0, 0), font=font)
    return img


# ----------------------------- OpenGL‑Primitives --------------------------


def _draw_box(x: float, y: float, z: float, dx: float, dy: float, dz: float) -> None:
    """Zeichnet einen opaken Quader (Immediate‑Mode)."""
    v = [
        (x, y, z),
        (x + dx, y, z),
        (x + dx, y + dy, z),
        (x, y + dy, z),
        (x, y, z + dz),
        (x + dx, y, z + dz),
        (x + dx, y + dy, z + dz),
        (x, y + dy, z + dz),
    ]
    faces: Sequence[Sequence[int]] = [
        (0, 1, 2, 3),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (2, 3, 7, 6),
        (1, 2, 6, 5),
        (3, 0, 4, 7),
    ]
    glBegin(GL_QUADS)
    for face in faces:
        for idx in face:
            glVertex3f(*v[idx])
    glEnd()


def _draw_wire_cube(l: float, w: float, h: float) -> None:
    """Kantenmodell des Containers (etwas kräftigere Linien)."""
    verts = [
        (0, 0, 0),
        (l, 0, 0),
        (l, w, 0),
        (0, w, 0),
        (0, 0, h),
        (l, 0, h),
        (l, w, h),
        (0, w, h),
    ]
    edges = [
        (0, 1),
        (1, 2),
        (2, 3),
        (3, 0),
        (4, 5),
        (5, 6),
        (6, 7),
        (7, 4),
        (0, 4),
        (1, 5),
        (2, 6),
        (3, 7),
    ]
    glLineWidth(2.5)
    glBegin(GL_LINES)
    for a, b in edges:
        glVertex3f(*verts[a])
        glVertex3f(*verts[b])
    glEnd()
    glLineWidth(1.0)


# ============================== Hauptfunktion ============================


def render_scene(project: Any) -> Image.Image:
    """
    Rendert *project* in ein 800 × 600‑RGBA‑Bild.

    Erwartete Attribute des Project‑Objekts
    ---------------------------------------
    * ``container_length``, ``container_width``, ``container_height``
    * ``boxes`` (Iterable), jedes Box‑Objekt mit
      ``x``, ``y``, ``z``, ``length``, ``width``, ``height``, ``color`` (HEX)
    """
    # ------------------------------------------------------------------ Prüfungen
    if pygame is None or OpenGL_import_error is not None:  # pragma: no cover
        logger.error("OpenGL initialisation failed", exc_info=True)
        return _placeholder_image("OpenGL not available")

    try:
        # ---------------- Kontext (verstecktes Fenster) anlegen --------
        pygame.display.init()
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(pygame.GL_MULTISAMPLESAMPLES, 4)
        display.set_mode((1, 1), DOUBLEBUF | OPENGL | HIDDEN)
        glViewport(0, 0, _WIDTH, _HEIGHT)

        # ---------------- OpenGL‑Grundsetup ---------------------------
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_MULTISAMPLE)
        glClearColor(1.0, 1.0, 1.0, 0.0)

        # Lichtquellen
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, (1.0, 1.0, 2.0, 0.0))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (1.0, 1.0, 1.0, 1.0))
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.2, 0.2, 0.2, 1.0))

        glEnable(GL_LIGHT1)
        glLightfv(GL_LIGHT1, GL_POSITION, (-1.0, -1.0, 1.0, 0.0))
        glLightfv(GL_LIGHT1, GL_DIFFUSE, (0.5, 0.5, 0.5, 1.0))
        glLightfv(GL_LIGHT1, GL_AMBIENT, (0.1, 0.1, 0.1, 1.0))

        # Projektion & Kamera (isometrisch)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, _WIDTH / _HEIGHT, 0.1, 10_000.0)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        L = float(getattr(project, "container_length", 1.0))
        W = float(getattr(project, "container_width", 1.0))
        H = float(getattr(project, "container_height", 1.0))

        dist = max(L, W, H) * 2.2
        gluLookAt(dist, dist, dist * 0.7, L / 2, W / 2, H / 2, 0, 0, 1)

        # ---------------- Szene zeichnen ------------------------------
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # Container (Drahtmodell, leicht transparent)
        glColor4f(0.3, 0.3, 0.3, 0.5)
        _draw_wire_cube(L, W, H)

        # Boxen
        for box in getattr(project, "boxes", []):
            try:
                x = float(getattr(box, "x"))
                y = float(getattr(box, "y"))
                z = float(getattr(box, "z"))
                dx = float(getattr(box, "length"))
                dy = float(getattr(box, "width"))
                dz = float(getattr(box, "height"))
                hex_color = str(getattr(box, "color", "#808080"))
            except Exception as exc:  # pragma: no cover
                logger.error("Invalid box object: %s", exc, exc_info=True)
                continue

            r, g, b = _hex_to_rgb_f(hex_color)
            glColor4f(r, g, b, 1.0)
            _draw_box(x, y, z, dx, dy, dz)

        # ---------------- Back‑Buffer auslesen ------------------------
        pixels = glReadPixels(0, 0, _WIDTH, _HEIGHT, GL_RGBA, GL_UNSIGNED_BYTE)
        img = Image.frombuffer("RGBA", (_WIDTH, _HEIGHT), pixels, "raw", "RGBA", 0, 1)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)  # OpenGL‑Koordinaten → Bildkoordinaten
        return img

    except Exception:  # pragma: no cover
        logger.error("Render failed", exc_info=True)
        return _placeholder_image("Render error")

    finally:  # OpenGL‑Kontext sauber schließen
        try:
            pygame.display.quit()
            pygame.quit()
        except Exception:  # pragma: no cover
            pass
