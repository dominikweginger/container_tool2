# Projektplan „Container-Ladetool“ – v Perfect

---

## 0 · Prämissen

| Thema             | Festlegung                                                                     |
| ----------------- | ------------------------------------------------------------------------------ |
| **Projektumfang** | 1 Container pro Projekt; manuelles Drag-&-Drop-Beladen inkl. Stapel-Funktion   |
| **Technik-Stack** | Python 3.13.5 (Fallback 3.12.x), PySide6 6.5.2, PyOpenGL, NumPy, ReportLab     |
| **Zielsystem**    | Windows 10/11 (Desktop, integrierte GPU), 100 % Offline, Update per EXE-Tausch |
| **CI/CD**         | GitHub Actions → Lint → Unit/Perf-Tests → PyInstaller-Build (one-file EXE)     |
| **Logs**          | `logs/error.log` (rotierend 7 Tage)                                            |
| **Versionierung** | SemVer `vMAJOR.MINOR.PATCH` in `meta.version` der `.clp`-Datei                 |

---

## 1 · Datenmodelle & Persistenz

### 1.1 `data/containers.json`

```json
[
  {
    "id": "40ft-std",
    "name": "40 ft Standard Container",
    "inner_length_mm": 12000,
    "inner_width_mm": 2300,
    "inner_height_mm": 2393,
    "door_height_mm": 2228
  }
]
```

*(Felder wie `door_width_mm` oder `max_payload_kg` werden nicht benötigt.)*

### 1.2 Box-Schema

| Feld        | Typ     | Einheit  | Pflicht    |
| ----------- | ------- | -------- | ---------- |
| `name`      | string  | –        | ✓          |
| `length_mm` | integer | mm       | ✓          |
| `width_mm`  | integer | mm       | ✓          |
| `height_mm` | integer | mm       | ✓          |
| `weight_kg` | number  | kg       | (optional) |
| `color_hex` | string  | Hex      | ✓          |
| `pos_x_mm`  | integer | mm       | ✓          |
| `pos_y_mm`  | integer | mm       | ✓          |
| `rot_deg`   | integer | ° (0/90) | ✓          |

### 1.3 `.clp`-Datei (JSON-Format)

```json
{
  "container": { /* Container-Objekt */ },
  "boxes": [ /* Box-Objekte */ ],
  "meta": {
    "created_at": "2025-07-31T10:19:00Z",
    "version": "1.0.0",
    "user": "initials"
  }
}
```

---

## 2 · Funktionale Anforderungen

|  Nr. | Requirement           | Detail/Parameter                                                                                                       |      |       |                                                                |
| ---: | --------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---- | ----- | -------------------------------------------------------------- |
| F-01 | Kisten-Eingabetabelle | Spalten: Name, Menge, L, B, H (mm int), Gewicht (kg float ≤ 2 Nachkommastellen). Ungültige Werte → rote Zellumrandung. |      |       |                                                                |
| F-02 | Kisten-Generierung    | Buttons **„gestapelt“** / **„einzeln“**. Zweiter Klick löscht alte Grafiken & Daten.                                   |      |       |                                                                |
| F-03 | Farbcodes             | Zufällig, farbenblind-freundlich; Inline-Palette zum Ändern; Farbe in GUI & PDF identisch.                             |      |       |                                                                |
| F-04 | Wartebereich          | Maßstäbliche 2-D-Darstellung aller Boxen/Stapel.                                                                       |      |       |                                                                |
| F-05 | Containerauswahl      | Button-Gruppe (20 ft, 40 ft, 40 ft HC, 40 ft OT).                                                                      |      |       |                                                                |
| F-06 | Drag-&-Drop           | Live-Kollisionsprüfung bei `mouseMove`; Verstoß → Box rot, bleibt liegen.                                              |      |       |                                                                |
| F-07 | Manuelles Stapeln     | Snap-Toleranz ± 10 mm (Mitte auf Mitte) erzeugt **Stack**.                                                             |      |       |                                                                |
| F-08 | Zoom                  | Feste Stufen 25 %                                                                                                      | 50 % | 100 % | 200 % via `Ctrl + Mausrad`; Wartebereich & Container synchron. |
| F-09 | PDF-Export            | A4 hoch (20 mm Ränder, 200 dpi), 2-D/3-D-Ansichten (800 × 600 px), Tabellen verladen & unverladen.                     |      |       |                                                                |
| F-10 | Projekt-Load/Save     | `.clp` laden/speichern; neue Box-Typen ergänzbar.                                                                      |      |       |                                                                |
| F-11 | Undo/Redo             | Nicht implementiert.                                                                                                   |      |       |                                                                |

---

## 3 · Nicht-funktionale Anforderungen

| Aspekt           | Zielwert                                                 |
| ---------------- | -------------------------------------------------------- |
| Kollisions-Check | ≤ 50 ms bei 200 Boxen / 40 Typen                         |
| Zoom-Performance | ≥ 25 fps, Render-Lag ≤ 100 ms                            |
| Speicherbedarf   | ≤ 250 MB RAM bei Maximalprojekt                          |
| PDF-Renderzeit   | ≤ 5 s bei Maximalprojekt                                 |
| Accessibility    | Farbpalette farbenblind-freundlich (kein Extra-Shortcut) |

---

## 4 · GUI-Layout & Flows

```mermaid
flowchart TD
  Table["Kisten-Tabelle\nInline-Farbpalette"] -->|Erstellen| Gen[Kisten-Generator]
  Gen --> Wait[Wartebereich 2-D]
  Wait -->|Drag| Canvas[Container-Canvas 2-D]
  Canvas --> Coll[Core: Collision + Stack]
  Coll --OK--> Canvas
  Coll --Verstoß--> Red[Rot-Markierung]
  buttons((6 Buttons)) -->|Events| Gen - Ein Button zur Erstellung einer zusätzlichen Kiste ist OK.
  buttons -->|Load/Save| IO[.clp-IO]
  buttons -->|Export| PDF
  Canvas --> PDF
  Wait --> PDF
  style Red fill:#ffcccc,stroke:#d55
```

---

## 5 · Architektur & Dateistruktur

```bash
container_tool/
├─ src/container_tool/
│  ├─ core/
│  │  ├─ models.py
│  │  ├─ collision.py
│  │  ├─ stack.py
│  │  └─ io_clp.py
│  ├─ gui/
│  │  ├─ window.py
│  │  ├─ table_widget.py
│  │  └─ canvas_2d.py
│  ├─ export/
│  │  ├─ pdf_export.py
│  │  └─ render_3d.py
│  └─ main.py
├─ data/containers.json
├─ tests/
│  ├─ test_models.py
│  ├─ test_collision.py
│  ├─ test_stack.py
│  ├─ test_io.py
│  ├─ test_performance.py
│  └─ smoke_gui.py
└─ logs/error.log
```

---

## 6 · Prompt-Guidelines (pro Datei)

| Datei                  | Zweck                                 | Input von          | Output an      | Muss enthalten                       |
| ---------------------- | ------------------------------------- | ------------------ | -------------- | ------------------------------------ |
| `core/models.py`       | Daten- & Geometrie-Klassen            | –                  | alle           | `class Box`, `class Stack`, `bbox()` |
| `core/stack.py`        | Stapel-Logik                          | models             | collision, gui | `create_stack()`                     |
| `core/collision.py`    | XY-Kollision & Türprüfung             | models/stack       | gui            | `check_collisions()`                 |
| `gui/table_widget.py`  | Tabelle → Box-Objekte, Inline-Palette | Qt                 | io\_clp        | Signal `boxes_created(list[Box])`    |
| `gui/canvas_2d.py`     | Rendering, Drag, Zoom                 | Qt                 | collision      | `on_drag_move(event)`                |
| `export/pdf_export.py` | PDF-Writer                            | models, render\_3d | –              | `export_pdf(project, path)`          |

---

## 7 · Tests & Quality Gates

| Ebene       | Tool               | Inhalte / Benchmarks                      |
| ----------- | ------------------ | ----------------------------------------- |
| Unit        | `pytest`           | Models-Roundtrip, Stack-Height, Collision |
| Performance | `pytest-benchmark` | Collision ≤ 50 ms, Zoom ≥ 25 fps          |
| GUI-Smoke   | `pytest-qt`        | Fenster öffnet, Boxen generierbar         |
| PDF         | Hash-Vergleich     | Referenz-PDF identisch                    |
| Manuelle QA | Demo-Projekt + MD  | Checkliste in Textform                    |

---

## 8 · Roadmap & Meilensteine

| Phase | Deliverable                            | Akzeptanzkriterium              |
| ----: | -------------------------------------- | ------------------------------- |
|     1 | Repo-Skeleton, CI-Workflow             | Actions-Run grün                |
|     2 | `models.py`, `io_clp.py` + Tests       | Round-Trip ok                   |
|     3 | `collision.py` + Benchmarks            | ≤ 50 ms                         |
|     4 | `table_widget.py` (Inline-Palette)     | Box-Gen visuell                 |
|     5 | `canvas_2d.py` (Drag, Live-Coll, Zoom) | 30 fps, Rot-Markierung          |
|     6 | `stack.py` + Stapel-GUI                | Stack = Einheit                 |
|     7 | `pdf_export.py` + `render_3d.py`       | Export-PDF gem. F-09            |
|     8 | PyInstaller-Build (.exe)               | Startet auf Clean-PC            |
|     9 | UAT & README                           | Demo-Projekt erfüllt Checkliste |

---

## 9 · Fehlerbehandlung & Logging

| Situation               | Reaktion                                   |
| ----------------------- | ------------------------------------------ |
| Ungültige Zahleneingabe | Zelle rot, Wert ignoriert                  |
| `.clp`-Parse-Error      | Error-Dialog + Stacktrace in Log           |
| Drag Out-of-Bounds      | Box rot, bleibt liegen                     |
| PDF-Render-Fail         | Dialog + Log-Eintrag, Projekt bleibt offen |

---

## 10 · Glossar

| Begriff          | Bedeutung                                                     |
| ---------------- | ------------------------------------------------------------- |
| **Stack**        | Verbund identischer Boxen, entsteht bei Snap-Toleranz ± 10 mm |
| **Snap**         | Ausrichtung Box-Mitte auf Box-Mitte                           |
| **Top-View**     | Draufsicht (X/Y), Hauptinteraktions-Fläche                    |
| **Wartebereich** | Ablagezone noch nicht verladen­er Boxen/Stapel                |

---

## 11 · Nächste Schritte

1. Ordner & leere Module gemäß *Architektur* anlegen.
2. `containers.json` um weitere Größen erweitern.
3. Demo-Projekt `demo_project.clp` erstellen.
4. CI-Workflow (`.github/workflows/build.yml`) implementieren.
5. Phase 1 starten, dann iterativ laut *Roadmap* fortfahren.
