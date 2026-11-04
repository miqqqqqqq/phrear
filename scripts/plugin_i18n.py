"""Translations of the QGIS plugin: extract the texts, update the .ts, compile the .qm.

    pixi run plugin-i18n            update i18n/phrear_it.ts and compile it
    pixi run plugin-i18n --check    fail if texts are missing or untranslated

Texts are the literal strings passed to ``tr(...)`` in the plugin sources. The
.ts keeps existing translations; new texts are added as unfinished, texts no
longer used are dropped. Compiling needs lrelease from the ``i18n`` environment
(``pixi install -e i18n``).
"""

from __future__ import annotations

import argparse
import ast
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "qgis_plugin" / "phrear_qgis"
TS = PLUGIN / "i18n" / "phrear_it.ts"
QM = TS.with_suffix(".qm")
CONTEXT = "Phrear"


@dataclass(frozen=True)
class Text:
    source: str
    filename: str
    line: int


def extract(plugin: Path = PLUGIN) -> list[Text]:
    """Literal arguments of tr(...) calls, in file and line order, without duplicates."""
    found: dict[str, Text] = {}
    for path in sorted(plugin.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "tr"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                text = node.args[0].value
                relative = path.relative_to(plugin).as_posix()
                found.setdefault(text, Text(text, relative, node.lineno))
    return sorted(found.values(), key=lambda t: (t.filename, t.line))


def read_translations(path: Path = TS) -> dict[str, str]:
    if not path.is_file():
        return {}
    root = ET.parse(path).getroot()
    result: dict[str, str] = {}
    for message in root.iter("message"):
        source = message.findtext("source") or ""
        node = message.find("translation")
        if node is not None and node.get("type") not in ("unfinished", "obsolete") and node.text:
            result[source] = node.text
    return result


def write_ts(texts: list[Text], translations: dict[str, str], path: Path = TS) -> None:
    root = ET.Element("TS", version="2.1", language="it_IT", sourcelanguage="en")
    context = ET.SubElement(root, "context")
    ET.SubElement(context, "name").text = CONTEXT
    for t in texts:
        message = ET.SubElement(context, "message")
        ET.SubElement(message, "location", filename=f"../{t.filename}", line=str(t.line))
        ET.SubElement(message, "source").text = t.source
        translation = ET.SubElement(message, "translation")
        if t.source in translations:
            translation.text = translations[t.source]
        else:
            translation.set("type", "unfinished")
    ET.indent(root, space="    ")
    body = ET.tostring(root, encoding="unicode")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE TS>\n' + body + "\n", encoding="utf-8"
    )


def lrelease() -> Path:
    env = REPO / ".pixi" / "envs" / "i18n"
    for candidate in (
        env / "Library" / "bin" / "lrelease6.exe",
        env / "Library" / "bin" / "lrelease.exe",
        env / "Library" / "lib" / "qt6" / "bin" / "lrelease.exe",
        env / "bin" / "lrelease6",
        env / "lib" / "qt6" / "bin" / "lrelease",
    ):
        if candidate.is_file():
            return candidate
    found = shutil.which("lrelease6") or shutil.which("lrelease")
    if found:
        return Path(found)
    raise SystemExit("lrelease not found: run `pixi install -e i18n` first")


def problems(texts: list[Text], translations: dict[str, str]) -> list[str]:
    missing = [t.source for t in texts if t.source not in translations]
    listed = set(_ts_sources())
    stale = sorted(listed ^ {t.source for t in texts})
    return [f"untranslated: {m!r}" for m in missing] + [f"not in sync: {s!r}" for s in stale]


def _ts_sources() -> list[str]:
    if not TS.is_file():
        return []
    return [m.findtext("source") or "" for m in ET.parse(TS).getroot().iter("message")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only check, do not write")
    args = parser.parse_args(argv)
    texts = extract()
    translations = read_translations()
    if args.check:
        found = problems(texts, translations)
        for line in found:
            print(line)
        return 1 if found else 0
    write_ts(texts, translations)
    untranslated = [t.source for t in texts if t.source not in translations]
    subprocess.run([str(lrelease()), str(TS), "-qm", str(QM)], check=True)
    print(f"{len(texts)} texts, {len(untranslated)} to translate in {TS.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
