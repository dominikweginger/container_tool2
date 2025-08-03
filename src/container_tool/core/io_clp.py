"""
src/container_tool/core/io_clp.py

Ein‑/Ausgabe‑Routinen für das proprietäre *.clp*-Format.
Alle Operationen sind **thread‑sicher**, nutzen nur die
Python‑Standardbibliothek und die Datenklassen aus *models.py*.

Funktionen
----------
load_containers_definitions(path: str | None) -> dict[str, Container]
load_clp(path: str) -> Project
save_clp(project: Project, path: str, user: str, version: str) -> None
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Final

# ----------------------------------------------------------------------------------------------------------------------
# relative Imports aus dem Projekt
# (Pfad: src/container_tool/core/models.py laut Projektplan)
# ----------------------------------------------------------------------------------------------------------------------
from .models import Box, Container, Project, Stack  # type: ignore[attr-defined]

__all__ = [
    "ClpError",
    "ClpFormatError",
    "ContainerNotFoundError",
    "FileLockedError",
    "load_containers_definitions",
    "load_clp",
    "save_clp",
]

# ======================================================================================================================
# Exceptions
# ======================================================================================================================


class ClpError(Exception):
    """Basisklasse aller .clp‑spezifischen Fehler."""


class ClpFormatError(ClpError):
    """Das *.clp*‑Dokument verletzt die Format‑Spezifikation."""


class ContainerNotFoundError(ClpError):
    """Im Projekt referenzierter Container ist in *containers.json* nicht definiert."""


class FileLockedError(ClpError):
    """Die Zieldatei ist schreibgeschützt oder durch ein anderes Programm gesperrt."""


# ======================================================================================================================
# Konstanten & Globals
# ======================================================================================================================

_LOGGER: Final[logging.Logger] = logging.getLogger("container_tool.core.io_clp")

# SemVer‑Validierung (nach <https://semver.org>)
_SEMVER_RE: Final[re.Pattern[str]] = re.compile(
    r"""
    ^
    (0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)            # X.Y.Z
    (?:-(?:0|[1-9A-Za-z-][0-9A-Za-z-]*)                 # Prä‑Release
        (?:\.(?:0|[1-9A-Za-z-][0-9A-Za-z-]*))* )?
    (?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?            # Build‑Meta
    $
    """,
    re.VERBOSE,
)

# Thread‑Lock für *save_clp* (Auto‑Save, gleichzeitiges Speichern)
_SAVE_LOCK: Final[RLock] = RLock()

# Cache für Container‑Definitionen (wird lazy geladen)
_CONTAINER_DEFINITIONS: dict[str, Container] | None = None


# ======================================================================================================================
# Hilfsfunktionen
# ======================================================================================================================


def _project_root() -> Path:
    """
    Liefert das Projekt‑Root‑Verzeichnis (= drei Ebenen über dieser Datei).

    Struktur gem. Projektplan:
        container_tool/
            └─ core/
                └─ io_clp.py   ← *hier*
        data/
            └─ containers.json
    """
    return Path(__file__).resolve().parents[3]


def _data_dir() -> Path:
    """Pfad zum *data/*‑Verzeichnis."""
    return _project_root() / "data"


def _validate_semver(version: str) -> None:
    if not _SEMVER_RE.match(version):
        raise ClpFormatError(f"Ungültige SemVer‑Version: {version!r}")


def _validate_iso_datetime(dt_str: str) -> datetime:
    try:
        dt = datetime.fromisoformat(dt_str)
    except ValueError as exc:
        raise ClpFormatError(f"Ungültiger ISO‑Zeitstempel: {dt_str!r}") from exc

    # → Immer als UTC interpretieren (fehlende TZ = UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _ensure_writeable(target: Path) -> None:
    """
    Prüft, ob *target* beschrieben werden kann.

    Strategie:
    - Existiert die Datei, wird sie im **Append‑Modus** exklusiv geöffnet.
      Windows verweigert dadurch den Zugriff, wenn Notepad/Excel die Datei hält.
    - Temporäre Öffnung wird sofort wieder geschlossen.
    """
    if not target.exists():
        # Schreibbarkeit des Verzeichnisses testen
        if not target.parent.exists():
            raise FileNotFoundError(str(target.parent))
        if not target.parent.is_dir():
            raise FileLockedError(f"{target.parent} ist kein Verzeichnis")
        return

    try:
        with target.open("a", encoding="utf-8"):
            pass
    except OSError as exc:  # schreibgeschützt / gelockt
        raise FileLockedError(
            f"Datei {target} ist gesperrt oder schreibgeschützt – bitte schließen & erneut versuchen"
        ) from exc


def _atomic_write(data: str, target: Path) -> None:
    """
    Schreibt *data* atomar nach *target*.

    Vorgehen:
    1. In eine **named** Temporary‑Datei im selben Verzeichnis schreiben.
    2. Mit `Path.replace()` (≙ `os.replace`) auf *target* verschieben.
       → Atomic auf allen gängigen OS.
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=str(target.parent),
        delete=False,
        suffix=".tmp",
    ) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    # Replace ist atomic (selbst auf Windows), überschreibt bestehende Datei
    tmp_path.replace(target)


# ======================================================================================================================
# API
# ======================================================================================================================


def load_containers_definitions(path: str | Path | None = None) -> dict[str, Container]:
    """
    Lädt die Container‑Definitionen aus *containers.json*.

    Parameter
    ---------
    path:
        Optionaler alternativer Pfad (Unit‑Tests).
        *None* ⇒ *data/containers.json* relativ zum Projekt‑Root.

    Returns
    -------
    dict[str, Container]
        Key = Container‑ID.

    Raises
    ------
    FileNotFoundError, ClpFormatError
    """
    global _CONTAINER_DEFINITIONS  # noqa: PLW0603 – bewusstes Caching

    if _CONTAINER_DEFINITIONS is not None and path is None:
        return _CONTAINER_DEFINITIONS

    json_path = Path(path) if path else _data_dir() / "containers.json"
    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        _LOGGER.exception("containers.json enthält ungültiges JSON")
        raise ClpFormatError("containers.json enthält ungültiges JSON") from exc

    if not isinstance(raw, list):
        raise ClpFormatError("containers.json muss eine Liste von Containern enthalten")

    defs: dict[str, Container] = {}
    for entry in raw:
        try:
            container = Container.from_dict(entry)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            raise ClpFormatError("Fehlerhafte Container‑Definition") from exc
        defs[container.id] = container  # type: ignore[attr-defined]

    if path is None:
        _CONTAINER_DEFINITIONS = defs  # cache

    return defs


def load_clp(path: str | Path) -> Project:
    """
    Liest eine *.clp*‑Datei und instanziiert ein :class:`Project`.

    Raises
    ------
    FileNotFoundError
    ClpFormatError
    ContainerNotFoundError
    """
    path = Path(path)

    try:
        raw: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        _LOGGER.exception("Ungültige JSON‑Struktur in %s", path)
        raise ClpFormatError("Die .clp‑Datei enthält ungültiges JSON") from exc

    # --- Meta ---------------------------------------------------------------
    meta = raw.get("meta", {})
    if not isinstance(meta, dict):
        raise ClpFormatError("Feld 'meta' fehlt oder ist kein Objekt")

    version = meta.get("version", "")
    _validate_semver(version)

    _validate_iso_datetime(meta.get("created_at", ""))  # nur Validierung – Wert wird im Project gespeichert
    if "user" not in meta or not isinstance(meta["user"], str):
        raise ClpFormatError("Feld 'meta.user' fehlt oder ist kein String")

    # --- Container‑Definition(en) --------------------------------------------
    container_defs = load_containers_definitions()

    # Abwärts­kompatibilität:
    #   • neues Format:  "container": { … }
    #   • altes Format:  "containers": [ { … } ]
    container_raw = raw.get("container")
    if container_raw is None:
        containers_list = raw.get("containers")
        if isinstance(containers_list, list) and len(containers_list) == 1:
            container_raw = containers_list[0]

    if not isinstance(container_raw, dict):
        raise ClpFormatError("'container' muss ein Objekt sein")

    container_id = container_raw.get("id")
    try:
        container = container_defs[container_id]
    except KeyError:
        raise ContainerNotFoundError(f"Container‑Typ '{container_id}' unbekannt")

    # --- Boxes & Stacks -----------------------------------------------------
    boxes_raw = raw.get("boxes", [])
    if not isinstance(boxes_raw, list):
        raise ClpFormatError("'boxes' muss eine Liste sein")

    boxes: list[Box | Stack] = []
    for item in boxes_raw:
        if not isinstance(item, dict) or "type" not in item:
            raise ClpFormatError("Box/Stack‑Eintrag ist fehlerhaft")

        box_type = item["type"]
        try:
            if box_type == "box":
                boxes.append(Box.from_dict(item))  # type: ignore[attr-defined]
            elif box_type == "stack":
                boxes.append(Stack.from_dict(item))  # type: ignore[attr-defined]
            else:
                raise ClpFormatError(f"Unbekannter Box/Stack‑Typ: {box_type!r}")
        except Exception as exc:  # pragma: no cover
            _LOGGER.exception("Fehler beim Parsen von %s‑Eintrag", box_type)
            raise ClpFormatError(f"Fehlerhaftes {box_type}‑Objekt") from exc

    # --- Project‑Objekt -----------------------------------------------------
    try:
        project = Project.from_dict(
            {
                "meta": meta,
                "container": container.to_dict(),
                "boxes": [b.to_dict() for b in boxes],  # type: ignore[attr-defined]
            }
        )
    except Exception as exc:  # pragma: no cover
        raise ClpFormatError("Konnte Project‑Objekt nicht erzeugen") from exc

    return project


def save_clp(project: Project, path: str | Path, user: str, version: str) -> None:
    """
    Serialisiert *project* und schreibt es atomar nach *path*.

    Thread‑Safe: gleichzeitige Aufrufe werden per RLock verhindert.

    Parameters
    ----------
    project:
        Das zu speichernde Projekt.
    path:
        Zielpfad (.clp)
    user:
        Benutzername – wird in *meta.user* geschrieben.
    version:
        Neue SemVer‑Version (wird **nicht** auf Größer prüfen, wie gewünscht)
    """
    path = Path(path)

    with _SAVE_LOCK:
        # -- Schreibbarkeit prüfen ------------------------------------------
        _ensure_writeable(path)

        # -- Meta aktualisieren --------------------------------------------
        _validate_semver(version)  # frühe Validierung
        now_iso = datetime.now(tz=timezone.utc).isoformat()

        project.meta["created_at"] = now_iso  # type: ignore[attr-defined]
        project.meta["user"] = user  # type: ignore[attr-defined]
        project.meta["version"] = version  # type: ignore[attr-defined]

        # -- Serialisieren --------------------------------------------------
        try:
            serialised = project.to_dict()  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover
            raise ClpFormatError("Fehler beim Serialisieren des Projekts") from exc

        json_str = json.dumps(serialised, indent=2, ensure_ascii=False)

        # -- Atomar schreiben ----------------------------------------------
        try:
            _atomic_write(json_str, path)
        except FileLockedError:
            raise  # wurde bereits geloggt
        except Exception as exc:  # pragma: no cover
            _LOGGER.exception("Schreibfehler für %s", path)
            raise
