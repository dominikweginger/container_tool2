import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import pytest

from container_tool.core import io_clp
from container_tool.core.io_clp import (
    ClpFormatError,
    ContainerNotFoundError,
    load_clp,
    save_clp,
)
from container_tool.core.models import Box, Container, Project, Stack


# ---------------------------------------------------------------------------
# Helper / fixture data
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_container() -> Container:
    return Container(
        id="test-ctn",
        name="Test-Container",
        inner_length_mm=1_000,
        inner_width_mm=500,
        inner_height_mm=400,
        door_height_mm=350,
    )


@pytest.fixture()
def sample_project(sample_container: Container) -> Project:
    # one loose box …
    loose_box = Box(
        name="Single",
        length_mm=100,
        width_mm=50,
        height_mm=30,
        weight_kg=5.5,
        color_hex="#FF0000",
        pos_x_mm=10,
        pos_y_mm=20,
        rot_deg=0,
    )
    # … and a 2-high stack
    sb1 = Box(
        name="S1_A",
        length_mm=120,
        width_mm=60,
        height_mm=40,
        weight_kg=6.0,
        color_hex="#00FF00",
        pos_x_mm=0,
        pos_y_mm=0,
        rot_deg=0,
    )
    sb2 = Box(
        name="S1_B",
        length_mm=120,
        width_mm=60,
        height_mm=40,
        weight_kg=6.0,
        color_hex="#00FF00",
        pos_x_mm=0,
        pos_y_mm=0,
        rot_deg=0,
    )
    stack = Stack(name="Stack1", _boxes=[sb1, sb2])

    # ProjectMeta ist im Original ein Dataclass – für save_clp genügt ein Dict
    meta: Dict[str, str] = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "user": "pytest",
    }

    return Project(container=sample_container, boxes=[loose_box, stack], meta=meta)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_round_trip_clp(tmp_path, monkeypatch, sample_project, sample_container):
    """Speichern → Laden → Daten identisch & relative Pfade funktionsfähig."""
    # Stub der Container-Definitionen, damit load_clp nichts Externes braucht
    monkeypatch.setattr(
        io_clp,
        "load_containers_definitions",
        lambda path=None: {sample_container.id: sample_container},
    )

    # relativer Pfad: wir wechseln ins tmp-Verzeichnis
    monkeypatch.chdir(tmp_path)
    save_path = Path("project_rel.clp")

    # Version wird beim Speichern überschrieben
    save_clp(sample_project, save_path, user="pytest", version="2.0.0")
    loaded = load_clp(save_path)

    # Container-Daten
    assert loaded.container.to_dict() == sample_container.to_dict()

    # Box-/Stack-Listen (Reihenfolge egal)
    orig_boxes: List[Dict] = sorted(
        (b.to_dict() for b in sample_project.boxes), key=lambda d: d["name"]
    )
    loaded_boxes: List[Dict] = sorted(
        (b.to_dict() for b in loaded.boxes), key=lambda d: d["name"]
    )
    assert loaded_boxes == orig_boxes

    # Meta-Infos
    assert loaded.meta.version == "2.0.0"
    assert loaded.meta.user == "pytest"


def test_load_unknown_container_type(tmp_path, monkeypatch):
    """Ein unbekannter Container-Typ muss ContainerNotFoundError auslösen."""
    bad_data = {
        "containers": [
            {
                "id": "does-not-exist",
                "name": "Nope",
                "inner_length_mm": 100,
                "inner_width_mm": 100,
                "inner_height_mm": 100,
                "door_height_mm": 90,
            }
        ],
        "boxes": [],
        "meta": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "user": "pytest",
        },
    }
    bad_file = tmp_path / "bad.clp"
    bad_file.write_text(json.dumps(bad_data), encoding="utf-8")

    # Leere Definitions-Liste ⇒ Container definitiv unbekannt
    monkeypatch.setattr(io_clp, "load_containers_definitions", lambda path=None: {})

    with pytest.raises(ContainerNotFoundError):
        load_clp(bad_file)


def test_load_permission_error(tmp_path, monkeypatch):
    """Wenn die Datei nicht lesbar ist, muss PermissionError durchgereicht werden."""
    blocked = tmp_path / "blocked.clp"
    blocked.write_text("{}", encoding="utf-8")

    def _raise_perm(self, encoding="utf-8"):  # noqa: D401
        raise PermissionError("no access")

    monkeypatch.setattr(Path, "read_text", _raise_perm)

    with pytest.raises(PermissionError):
        load_clp(blocked)


def test_load_invalid_json(tmp_path):
    """Ungültiges JSON → ClpFormatError."""
    invalid = tmp_path / "invalid.clp"
    invalid.write_text("{ not valid json ", encoding="utf-8")

    with pytest.raises(ClpFormatError):
        load_clp(invalid)
