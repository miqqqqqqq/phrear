"""Translations of the interface with the Qt system (``i18n/phrear_<lang>.qm``).

Source texts are in English and wrapped in :func:`tr` with a literal string, so
that ``scripts/plugin_i18n.py`` can extract them into ``i18n/phrear_it.ts``.
"""

from __future__ import annotations

from pathlib import Path

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QCoreApplication, QTranslator

CONTEXT = "Phrear"


def tr(text: str) -> str:
    return str(QCoreApplication.translate(CONTEXT, text))


def interface_language() -> str:
    """``it`` when QGIS runs in Italian, ``en`` otherwise (also for the core)."""
    locale = str(QgsApplication.locale() or "")
    return "it" if locale.lower().startswith("it") else "en"


def install_translator(plugin_dir: Path) -> QTranslator | None:
    path = plugin_dir / "i18n" / f"phrear_{interface_language()}.qm"
    if not path.is_file():
        return None
    translator = QTranslator()
    if not translator.load(str(path)):
        return None
    QCoreApplication.installTranslator(translator)
    return translator
