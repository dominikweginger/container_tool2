<!--
  AGENTS.md — Guidance for ChatGPT Codex (codex‑1, release 2025‑06)
  This file is automatically parsed before Codex executes tasks in this repository.
  Keep rules deterministic; avoid ambiguous language. Lines over 120 chars will be ignored.
-->

# 🎯 Purpose

Enable **ChatGPT Codex** to act as an autonomous developer for **container\_tool2** by telling it **what matters, where to look and how to behave**.  Codex merges AGENTS files top‑down (global → repo root → sub‑folder) and gives precedence to the *closest* file ([github.com](https://github.com/openai/codex?utm_source=chatgpt.com)).

---

# 📂 Repository map (authoritative)

```
container_tool/
├─ src/container_tool/         # Python source
│  ├─ core/ …                  # Geometry & I/O logic
│  ├─ gui/  …                  # PySide6 widgets & windows
│  ├─ export/ …                # PDF & 3‑D output
│  └─ main.py                  # Entry‑point
├─ data/containers.json        # Container definitions
├─ tests/                      # pytest, pytest‑qt, benchmarks
├─ logs/                       # Rotating 7 days
├─ .github/workflows/build.yml # CI pipeline
├─ .pre‑commit‑config.yaml
└─ requirements*.txt           # runtime + dev deps
```

See **Projektplan\_.md** for the full architecture and milestone roadmap fileciteturn0file0.

---

# ⚙️ Runtime & build matrix

| Scope         | Value                                    |
| ------------- | ---------------------------------------- |
| Python        | **3.13.5** (fallback 3.12.x)             |
| GUI toolkit   | **PySide6 ≥ 6.9 < 6.10**                 |
| Graphics      | PyOpenGL 3.1.7, NumPy ≥ 1.28             |
| Packaging     | PyInstaller one‑file EXE (Windows 10/11) |
| CI            | GitHub Actions → lint → tests → build    |
| Target system | Offline desktop, iGPU                    |

*(All hard requirements originate from the project plan) fileciteturn0file0*

---

# 🧑‍💻 Coding conventions

1. **PEP‑8 + Black (line length ≤ 100) + Flake8** are enforced via pre‑commit hooks. Run `pre‑commit run --all-files` before every commit fileciteturn0file2.
2. All modules **must be typed** (`from __future__ import annotations`) and pass `mypy ‑‑strict`.
3. Use **dataclasses with `slots=True`** for all data models; keep them immutable unless mutation is specifically required.
4. **Thread‑safety**: core logic is stateless; UI calls must never block the Qt event loop—use `QThread`/`concurrent.futures`.
5. **Performance gates** (see `tests/test_performance.py`):

   * Collision ≤ 50 ms @ 200 boxes.
   * Zoom ≥ 25 fps; render lag ≤ 100 ms.
6. Prefer **py‑project‑relative imports** (`from container_tool.core import …`) over file‑relative dot‑imports.

---

# 🖥️ UX & functional rules

Codex **must** consult `UX Beschreibung.pdf` before altering GUI code; this file contains pixel‑perfect flows, mandatory button labels and color palette requirements fileciteturn0file1.
Key guarantees:

* **Exact scale**: 1 mm = 1 scene unit in both waiting area & container canvases.
* **Six toolbar actions** in the order defined in the UX spec.
* Live‑collision feedback by coloring the dragged item **red**.

---

# 📑 Data contracts

* **`containers.json`** schema is fixed (see project plan §1.1).  New fields are forbidden unless a migration note is added here.
* **`.clp` files** must validate against the loader in `core/io_clp.py`; write tests for every new attribute.
* **Stacks** respect ±10 mm snap tolerance and container door height.

---

# 🔍 Test & debug commands (Codex may run)

```bash
# Formatting / linting
black src tests && flake8 src tests

# Static typing
mypy src tests

# Fast unit & smoke tests
pytest -q

# Benchmarks (fail if regression >10 %)
pytest tests/test_performance.py --benchmark-only

# Build offline Windows EXE
pyinstaller --onefile src/container_tool/main.py
```

---

# 🧠 Lessons Learned — apply automatically

> The following distilled insights **override any generated code** when conflicts arise.

* **Replace Unicode NBSP** with spaces before any regex parsing of PDF/CLI data fileciteturn0file2.
* **Never block the GUI thread**; long tasks always run in background threads with progress callbacks.
* **Use rotating logs** and auto‑cleanup to keep the log directory sane.
* **Modular architecture**: parser/GUI/business logic in separate modules.
* **Smoke tests early** to prevent GUI regressions.

---

# 📝 Playbooks Codex may execute

| Scenario                        | Sequence                                                                                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| **Add new container type**      | 1) Update `data/containers.json`; 2) adjust `Container` validation; 3) write migration test; 4) update UX dropdown; 5) run full test suite |
| **Implement new stacking rule** | 1) Modify `core/stack.py`; 2) extend unit tests; 3) benchmark collision; 4) document here                                                  |
| **Bug in collision logic**      | 1) Reproduce with failing test; 2) fix `core/collision.py`; 3) ensure ≤ 50 ms; 4) add entry to Lessons Learned                             |

---

# 🛡️ Safeguards & constraints

* **NEVER** push code that breaks `pytest` or `mypy`.
* **NEVER** introduce external network calls; the app must stay 100 % offline.
* **ALWAYS** update version strings (`meta.version` and Git tag) atomically when releasing.
* **PROMPT** the human if a requirement cannot be met within existing constraints.

---

*(End of AGENTS.md)*
