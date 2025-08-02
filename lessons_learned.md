<!-- Seite 1 -->
Kategorie              Beschreibung
Projektname            z. B. PDF‑Scanner für Rechnungen
Start/Ende             Zeitliche Einordnung
Ziel des Projekts      Kurzbeschreibung des Projektziels
Fehler/Problem         Was ist schiefgelaufen (inkl. Screenshotpfad oder Codeausschnitt)?
Lösung                 Wie wurde das Problem gelöst? (inkl. Quellen oder Links)
Lessons Learned        Was ziehst du für dich daraus? Was vermeidest du nächstes Mal?
Best Practices         Allgemeingültige Tipps, die du wiederverwenden willst
KI‑relevant?           (Ja/Nein) – kennzeichnet, ob diese Info für GPT besonders nützlich ist
Stichwörter/Tags       z. B. PDF, VBA, GUI, EXE, pypdf, Make.com, Performance, …

---

<!-- Seite 2 -->
**Projektüberblick**

*Projektziel*
Automatisiertes Auslesen von Artikelnummern (I‑XXXX‑XXX) und Mengen aus beliebig vielen PDF‑Packlisten, Aggregation in eine Pivot‑Excel‑Tabelle und Integration in die Master‑GUI des Logistik‑Teams.
Vorteile: kein manuelles Abschreiben, keine Tippfehler, jederzeit Fortschritts‑/Fehler‑Log.

*Technologien & Tools*
Python 3.13.5, pdfplumber, pandas, openpyxl, Tkinter/TkinterDnD2, tqdm, RotatingFileHandler, PyInstaller, pytest (>90 % Coverage); modularer Aufbau (parser/, excel/, gui/, util/, tests).

*Endergebnis*
Alle Anforderungen erfüllt: ≤ 30 s für 10 mehrseitige PDFs, automatische Pivot‑Speicherung, robustes Logging, GUI & CLI als One‑file‑EXE, offene OCR‑Erweiterung notiert.

**❌ Fehler & Lösungen**

| Problem | Lösung |
|---------|--------|
| Unicode‑Leerzeichen verhinderte Regex‑Treffer | `raw.replace("\u00A0", " ")` vor Analyse |
| Zweizeilige Layouts ohne Menge | FIFO‑Queue, die Qty+Unit puffert |
| GUI‑Freeze bei Batch‑Parsing | Hintergrund‑Thread + `after()`‑Callbacks |
| `PermissionError`, wenn Pivot offen | Existenz‑Check; MessageBox & Abbruch |
| Wachsende Log‑Verzeichnisse | Auto‑Cleanup (>30 d) beim Start |
| Fehlerhafte PDFs sollten Workflow nicht stoppen | CLI‑Flags `--fail-fast` / `--ignore-errors` |

**✅ Best Practices & Erkenntnisse**

* Modularität (Parser, Excel‑Writer, GUI, Logger)
* Regex‑Toleranz & Text‑Normalisierung
* Nicht blockierende GUIs (Threads / ProcessPool)
* Persistenter State & rotierende Logs
* Frühe Smoke‑ & Unit‑Tests
* Konfigurierbarkeit via JSON
* One‑file‑Distribution mit PyInstaller

**🧠 KI‑Wissensbausteine (Auswahl)**
Unicode‑Spaces vor Regex ersetzen • Daten puffern statt starre Zeilenpositionen • Threads/Prozesse für lange Aufgaben • Vor Schreibzugriff prüfen, ob Datei offen • Alte Logs automatisiert löschen • Kernlogik auslagern (CLI+GUI) • `re.IGNORECASE` & flexible Dezimal‑Separatoren • Fortschritt nur im UI‑Thread ändern • Hidden‑Imports in PyInstaller angeben

---

<!-- Seite 3 -->
Wenn du Unit‑Tests schreibst, achte darauf, auch leere oder kaputte Dateien als Fixtures zu testen, um Edge‑Cases abzudecken.

---

<!-- Seite 4 -->
**EXE‑Erstellung**
Immer `--noconsole` für GUI‑Skripte.
Unit‑Tests samt Testdateien anlegen.
Release‑ und Milestone‑Commits:
```bash
git commit -m "Release: v1.0.0 – Erste stabile Version"
git tag v1.0.0
