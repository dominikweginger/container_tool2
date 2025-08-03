"""
container_tool.gui.canvas_2d
===========================

Zentraler 2‑D‑Canvas für Container‑ und Wartebereich‑Darstellung
----------------------------------------------------------------
*   maßstabsgetreue Top‑View (Einheit **mm** = 1 Scene‑Einheit)
*   Drag‑&‑Drop, Live‑Kollision, manuelles Stapeln, Rotation (Shortcut **R**)
*   feste Zoom‑Stufen 25 / 50 / 100 / 200 %, synchron über alle Canvas‑Instanzen
*   Signale:
        - zoomChanged(float factor)
        - objectsChanged(list[Box|Stack])
        - stackCreated(Stack)
        - collisionOccurred(Box, list[Box])
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union

from PySide6.QtCore import (
    QObject,
    QPointF,
    QRectF,
    Qt,
    QEvent,
    QSize,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QBrush,
    QPen,
    QTransform,
    QWheelEvent,
    QMouseEvent,
    QKeyEvent,
    QPainter,
    QImage,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

# ────────────────────────────────────────────────────────────────────────────────
# Domain‑Model‑Imports (liegen in anderen Modulen des Projekts)
# ────────────────────────────────────────────────────────────────────────────────
from container_tool.core.collision import check_collisions  # type: ignore
from container_tool.core.stack import create_stack  # type: ignore
from container_tool.core.models import Box, Stack


# ────────────────────────────────────────────────────────────────────────────────
# Hilfsklassen
# ────────────────────────────────────────────────────────────────────────────────
_ZOOM_LEVELS: Tuple[float, ...] = (0.25, 0.5, 1.0, 2.0)


class BoxGraphicsItem(QGraphicsRectItem):
    """Grafische Repräsentation einer einzelnen Box oder eines Stapels."""

    __slots__ = (
        "_model",
        "_brush_normal",
        "_brush_error",
        "_text_item",
        "_colliding",
    )

    def __init__(self, model: Union[Box, Stack], color: QColor, parent: Optional[QGraphicsItem] = None) -> None:
        super().__init__(parent)

        self._model: Union[Box, Stack] = model
        self._colliding: bool = False

        # Geometrie (Scene‑Einheit = mm)
        self.setRect(0, 0, model.length_mm, model.width_mm)

        # Darstellung
        self._brush_normal = QBrush(color)
        self._brush_error = QBrush(QColor(255, 0, 0))
        self.setBrush(self._brush_normal)
        self.setPen(QPen(Qt.NoPen))

        # Beschriftung
        self._text_item = QGraphicsSimpleTextItem(self)
        self._text_item.setFlag(QGraphicsItem.ItemIgnoresTransformations)
        self._update_label()

        # Flags
        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)

    # --------------------------------------------------------------------- API --

    @property
    def model(self) -> Union[Box, Stack]:
        return self._model

    def set_colliding(self, value: bool) -> None:
        if self._colliding != value:
            self._colliding = value
            self.setBrush(self._brush_error if value else self._brush_normal)

    # ----------------------------------------------------------- QGraphicsItem --

    def itemChange(self, change: "QGraphicsItem.GraphicsItemChange", value):
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Label zentrieren (da ItemIgnoresTransformations)
            rect = self.rect()
            self._text_item.setPos(rect.width() / 2 - self._text_item.boundingRect().width() / 2,
                                   rect.height() / 2 - self._text_item.boundingRect().height() / 2)
        return super().itemChange(change, value)

    # ----------------------------------------------------------------- Helpers --

    def _update_label(self) -> None:
        if isinstance(self._model, Stack):
            line1 = f"{self._model.name}"
            line2 = f"{self._model.count} × {self._model.single_height_mm} mm = {self._model.height_mm} mm"
        else:
            line1 = f"{self._model.name}"
            line2 = f"{self._model.length_mm}×{self._model.width_mm}×{self._model.height_mm} mm"

        self._text_item.setText(f"{line1}\n{line2}")


# ────────────────────────────────────────────────────────────────────────────────
# Haupt‑Canvas
# ────────────────────────────────────────────────────────────────────────────────
class Canvas2D(QGraphicsView):
    """Darstellung & Interaktion für *eine* Szene (Wartebereich **oder** Container)."""

    # ---------------------------------------------------------------- Signals --

    zoomChanged: Signal = Signal(float)
    objectsChanged: Signal = Signal(list)
    stackCreated: Signal = Signal(Stack)
    collisionOccurred: Signal = Signal(Box, list)

    # ---------------------------------------------------------------- Registry --

    _instances: List["Canvas2D"] = []  # <— für Peer‑to‑Peer‑Zoom

    # ---------------------------------------------------------------- Init / UI --

    def __init__(
        self,
        scene_name: str,
        *,
        container_inner_rect_mm: Optional[QRectF] = None,
        base_scale_px_per_mm: float = 1.0,
        parent: Optional[QObject] = None,
    ) -> None:
        """
        :param scene_name: „container“ oder „waiting“
        :param container_inner_rect_mm: Innenabmessungen; nur für Container‑Scene
        :param base_scale_px_per_mm: Faktor für 100 %‑Zoom (Scene‑->View)
        """
        super().__init__(parent)

        # Scene
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._scene_name = scene_name.lower()
        self._container_ref = None

        # Container‑Rahmen zeichnen
        self._container_rect_mm: Optional[QRectF] = container_inner_rect_mm
        if self._scene_name == "container" and container_inner_rect_mm:
            border_pen = QPen(QColor(100, 100, 100))
            border_pen.setWidth(2)
            self._scene.addRect(container_inner_rect_mm, border_pen, QBrush(Qt.NoBrush))
            self._scene.setSceneRect(container_inner_rect_mm)
        else:
            # großzügige Standard‑Scene für Wartebereich
            self._scene.setSceneRect(0, 0, 8000, 4000)

        # View‑Konfiguration
        self.setViewportUpdateMode(QGraphicsView.BoundingRectViewportUpdate)
        self.setRenderHint(QPainter.Antialiasing, False)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._base_scale_px_per_mm = base_scale_px_per_mm
        self._zoom_level_index: int = _ZOOM_LEVELS.index(1.0)  # start bei 100 %
        self.resetTransform()
        self.scale(base_scale_px_per_mm, base_scale_px_per_mm)

        # Drag‑State
        self._drag_item: Optional[BoxGraphicsItem] = None
        self._last_collision_pos: Optional[QPointF] = None

        # Peer‑Zoom‑Verdrahtung
        self._register_instance()

    # ------------------------------------------------------------------ Cleanup --

    def closeEvent(self, event: QEvent) -> None:
        self._unregister_instance()
        super().closeEvent(event)

    # ------------------------------------------------------------ Public API  --

    # ––– Objekt‑Erzeugung ------------------------------------------------------

    def add_box(self, model: Union[Box, Stack], color: QColor = QColor(120, 170, 255)) -> BoxGraphicsItem:
        """Neues Box/Stack‑Item in der Scene erzeugen und zurückgeben."""
        item = BoxGraphicsItem(model, color)
        self._scene.addItem(item)
        self.objectsChanged.emit(self.to_box_models())
        return item

    # ––– Persistenz ------------------------------------------------------------

    def to_box_models(self) -> List[Union[Box, Stack]]:
        """Aktuellen Scene‑Inhalt als Domain‑Model‑Liste zurückgeben."""
        models: List[Union[Box, Stack]] = []
        for item in self._scene.items():
            if isinstance(item, BoxGraphicsItem):
                models.append(item.model)
        return models

    # ––– PDF‑Export ------------------------------------------------------------

    def render_to_image(self, dpi: int = 300) -> QImage:
        """
        Szene off‑screen in ein Bitmap rendern (für PDF‑Export).

        :param dpi: Ausgabeauflösung
        """
        mm_per_inch = 25.4
        scene_sz_mm = self._scene.sceneRect().size()
        img_size_px = QSize(
            int(scene_sz_mm.width() / mm_per_inch * dpi),
            int(scene_sz_mm.height() / mm_per_inch * dpi),
        )
        image = QImage(img_size_px, QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.white)
        painter = QPainter(image)
        self._scene.render(painter)
        painter.end()
        return image

    # ----------------------------------------------------------------- Events --

    # ––– Wheel / Zoom ----------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                return

            # Ziel‑Zoom‑Index bestimmen
            new_idx = self._zoom_level_index + (1 if delta > 0 else -1)
            new_idx = max(0, min(new_idx, len(_ZOOM_LEVELS) - 1))
            if new_idx == self._zoom_level_index:
                return  # keine Änderung

            new_level = _ZOOM_LEVELS[new_idx]
            old_level = _ZOOM_LEVELS[self._zoom_level_index]
            factor = new_level / old_level

            self.scale(factor, factor)
            self._zoom_level_index = new_idx
            # Peer‑Notify
            self.zoomChanged.emit(new_level)
            event.accept()
            return
        super().wheelEvent(event)

    # ––– Mouse ---------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            if isinstance(item, BoxGraphicsItem):
                self._drag_item = item
                self._last_collision_pos = item.pos()
                self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_item:
            super().mouseMoveEvent(event)

            # live collision throttle: 2 px → Scene‑Units
            pos_scene = self.mapToScene(event.pos())
            if self._last_collision_pos is None:
                self._last_collision_pos = pos_scene
            view_px_per_scene = 1 / self.transform().m11()
            if (
                (pos_scene - self._last_collision_pos).manhattanLength()
                >= 2 * view_px_per_scene
            ):
                self._last_collision_pos = pos_scene
                self._run_live_collision_check(self._drag_item)

        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_item:
            self.setCursor(Qt.ArrowCursor)
            # End‑Collision / Out‑Of‑Bounds
            blockers = self._run_live_collision_check(self._drag_item)

            # Snap / Stapel
            if not blockers:
                snapped = self._attempt_stack_snap(self._drag_item)
                if snapped:
                    self._drag_item = None
                    self.objectsChanged.emit(self.to_box_models())
                    return

            self.objectsChanged.emit(self.to_box_models())
            self._drag_item = None
        super().mouseReleaseEvent(event)

    # ––– Key‑Rotation ----------------------------------------------------------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_R, Qt.Key_F4):
            # Drehe selektierte Boxes um 90°
            for item in self._scene.selectedItems():
                if isinstance(item, BoxGraphicsItem):
                    self._rotate_box_item(item)
            self.objectsChanged.emit(self.to_box_models())
            return
        super().keyPressEvent(event)

    # ---------------------------------------------------------------- Handlers --

    # ––– Collision -------------------------------------------------------------

    def _run_live_collision_check(self, moving: BoxGraphicsItem) -> List[BoxGraphicsItem]:
        """Prüft aktuelle Position des Drag‑Items gegen alle anderen."""
        others: List[BoxGraphicsItem] = [
            itm
            for itm in self._scene.items()
            if isinstance(itm, BoxGraphicsItem) and itm is not moving
        ]
        moving_rect_mm = self._item_rect_mm(moving)
        blocker_models = []
        for itm in others:
            ok, _ = check_collisions(               # richtiger Aufruf
                candidate=moving.model,
                placed=[itm.model],                 # Liste statt Einzelobjekt
                container=self._container_ref,      # kann None sein (Wartebereich)
            )
            if not ok:                              # Kollision → Item rot markieren
                itm.set_colliding(True)
                blocker_models.append(itm)
            else:
                itm.set_colliding(False)

        moving.set_colliding(bool(blocker_models))

        if blocker_models:
            self.collisionOccurred.emit(moving.model, [b.model for b in blocker_models])
        return blocker_models

    # ––– Stapel‑Snap -----------------------------------------------------------

    def _attempt_stack_snap(self, moving: BoxGraphicsItem) -> bool:
        tolerance_mm = 10.0
        best_target: Optional[BoxGraphicsItem] = None
        best_dist = tolerance_mm + 1.0

        for itm in self._scene.items():
            if not isinstance(itm, BoxGraphicsItem) or itm is moving:
                continue
            if not self._same_footprint(itm.model, moving.model):
                continue
            dist = self._center_distance_mm(itm, moving)
            if dist <= tolerance_mm and dist < best_dist:
                best_dist = dist
                best_target = itm

        if best_target is None:
            return False

        # Stack erzeugen
        new_stack = create_stack(best_target.model, moving.model)  # type: ignore[arg-type]
        # Alte Items entfernen & neues an Ziel‑Pos einfügen
        pos = best_target.pos()
        self._scene.removeItem(best_target)
        self._scene.removeItem(moving)
        new_item = self.add_box(new_stack, QColor(150, 220, 100))
        new_item.setPos(pos)
        self.stackCreated.emit(new_stack)
        return True

    # ––– Rotation --------------------------------------------------------------

    def _rotate_box_item(self, item: BoxGraphicsItem) -> None:
        # Domain‑Modell drehen
        item.model.rotate()  # type: ignore[attr-defined]
        # Geometrie anpassen
        rect = item.rect()
        item.setRect(0, 0, rect.height(), rect.width())
        # Label / Collision‑Check
        item._update_label()
        self._run_live_collision_check(item)

    # ---------------------------------------------------------------- Internes --

    # ––– Peer‑Zoom‑Weiche ------------------------------------------------------

    def _register_instance(self) -> None:
        for peer in Canvas2D._instances:
            # bidirektionale Verbindungen
            self.zoomChanged.connect(peer._apply_external_zoom)
            peer.zoomChanged.connect(self._apply_external_zoom)
        Canvas2D._instances.append(self)

    def _unregister_instance(self) -> None:
        if self in Canvas2D._instances:
            Canvas2D._instances.remove(self)
        for peer in Canvas2D._instances:
            try:
                self.zoomChanged.disconnect(peer._apply_external_zoom)
            except (TypeError, RuntimeError):
                pass
            try:
                peer.zoomChanged.disconnect(self._apply_external_zoom)
            except (TypeError, RuntimeError):
                pass

    def _apply_external_zoom(self, factor: float) -> None:
        """Reagiert auf zoomChanged‑Signale anderer Canvas‑Instanzen."""
        try:
            idx = _ZOOM_LEVELS.index(factor)
        except ValueError:
            return
        if idx == self._zoom_level_index:
            return
        old_level = _ZOOM_LEVELS[self._zoom_level_index]
        scale_factor = factor / old_level
        self.scale(scale_factor, scale_factor)
        self._zoom_level_index = idx

    # ––– Geometrie‑Hilfen ------------------------------------------------------

    @staticmethod
    def _same_footprint(a: Union[Box, Stack], b: Union[Box, Stack]) -> bool:
        return {a.length_mm, a.width_mm} == {b.length_mm, b.width_mm}

    @staticmethod
    def _center_distance_mm(a_item: BoxGraphicsItem, b_item: BoxGraphicsItem) -> float:
        a_center = a_item.mapToScene(a_item.rect().center())
        b_center = b_item.mapToScene(b_item.rect().center())
        return math.hypot(a_center.x() - b_center.x(), a_center.y() - b_center.y())

    @staticmethod
    def _item_rect_mm(item: BoxGraphicsItem) -> QRectF:
        return QRectF(item.pos().x(), item.pos().y(), item.rect().width(), item.rect().height())

    def has_boxes(self) -> bool:
        """Gibt *True* zurück, sobald mindestens ein Box‑Element existiert."""
        return any(isinstance(itm, BoxGraphicsItem) for itm in self._scene.items())

    def clear_boxes(self) -> None:
        """Entfernt alle Box‑ bzw. Stack‑Grafiken aus der Szene."""
        for itm in list(self._scene.items()):
            if isinstance(itm, BoxGraphicsItem):
                self._scene.removeItem(itm)
        self.objectsChanged.emit([])

    def add_boxes(
        self,
        models: List[Union[Box, Stack]],
        color: QColor = QColor(120, 170, 255),
    ):
        """Fügt mehrere Modelle auf einmal hinzu und liefert ihre Grafik‑Objekte."""
        items = [self.add_box(m, color) for m in models]
        self.objectsChanged.emit(self.to_box_models())
        return items

    def serialize(self) -> List[dict]:
        """Wandelt alle derzeit sichtbaren Modelle in Dictionaries um."""
        return [m.to_dict() for m in self.to_box_models()]

    def set_container_type(self, container_name: str) -> None:
        """
        Passt die Zeichenfläche an die Abmessungen des gewählten Containers an.
        """
        from container_tool.core import io_clp          # Late‑Import vermeidet Kreis‑Imports
        defs = io_clp.load_containers_definitions()
        for ct in defs.values():                       # Suche passenden Container
            if getattr(ct, "name", "") == container_name:
                self._container_ref = ct
                new_rect = QRectF(0, 0, ct.inner_length_mm, ct.inner_width_mm)
                self._scene.setSceneRect(new_rect)     # Szene vergrößern / verkleinern
                self.fitInView(new_rect, Qt.KeepAspectRatio)  # Ansicht anpassen
                return
        raise ValueError(f"Containertyp {container_name!r} unbekannt")
