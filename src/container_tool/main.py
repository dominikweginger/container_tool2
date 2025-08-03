import logging
from logging.handlers import TimedRotatingFileHandler
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from container_tool.core import io_clp

# --------------------------------------------------------------------------- #
# Global logger (einzige erlaubte globale Variable)
# --------------------------------------------------------------------------- #
logger = logging.getLogger("container_tool")

# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def _setup_logging() -> None:
    """Initialisiert Rotating‑Logfile logs/error.log (Retention 7 Tage)."""
    base_dir = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(exist_ok=True)

    handler = TimedRotatingFileHandler(
        log_dir / "error.log",
        when="D",
        interval=1,
        backupCount=7,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))

    logger.setLevel(logging.DEBUG)     # Standard‑Logstufe: DEBUG
    logger.addHandler(handler)
    logger.propagate = False


def _install_exception_hook() -> None:
    """Schreibt unbehandelte Exceptions ins Log und zeigt einen Dialog an."""
    def _handler(exc_type, exc_value, exc_tb):  # noqa: N802
        logger.exception("Unbehandelte Ausnahme", exc_info=(exc_type, exc_value, exc_tb))
        stacktrace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        QMessageBox.critical(None, "Unbehandelte Ausnahme", stacktrace)

    sys.excepthook = _handler


def _create_qt_application() -> QApplication:
    """Erzeugt die QApplication mit DPI‑Einstellungen."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    return QApplication(sys.argv)


def _load_container_definitions():
    """Lädt Containerdefinitionen; gibt bei Fehlern eine Warnung aus."""
    try:
        containers = io_clp.load_containers_definitions()
        if not containers:
            raise ValueError("Leere Containerdefinitionen.")
        return containers
    except Exception as err:  # pylint: disable=broad-except
        logger.error("Fehler beim Laden der Containerdefinitionen: %s", err, exc_info=True)
        QMessageBox.warning(None, "Fehler", "containers.json fehlt oder ist defekt. Bitte prüfen.")
        return []

# --------------------------------------------------------------------------- #
# Einstiegspunkt
# --------------------------------------------------------------------------- #
def main() -> None:
    _setup_logging()
    _install_exception_hook()

    # GUI‑Klasse *nach* Logger‑Initialisierung importieren
    from container_tool.gui.window import MainWindow

    app = _create_qt_application()
    container_defs = _load_container_definitions()

    main_window = MainWindow(container_defs)
    main_window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
