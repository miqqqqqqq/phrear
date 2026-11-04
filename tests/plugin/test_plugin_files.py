"""Metadata, licence, translations, packaging, and the Qt-free boundary of the plugin."""

from __future__ import annotations

import ast
import configparser
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import plugin_i18n
import plugin_package

from .conftest import PLUGIN


def test_metadata_for_qgis_4() -> None:
    parser = configparser.ConfigParser()
    parser.read(PLUGIN / "metadata.txt", encoding="utf-8")
    general = parser["general"]
    for key in ("name", "description", "version", "author", "email", "about", "repository"):
        assert general.get(key), key
    assert (general["qgisMinimumVersion"], general["qgisMaximumVersion"]) == ("4.0", "4.99")
    assert "supportsQt6" not in general  # removed from QGIS 4
    assert (PLUGIN / general["icon"]).is_file()


def test_licence_is_gpl_2_or_later() -> None:
    text = (PLUGIN / "LICENSE").read_text(encoding="utf-8")
    assert "either version 2 of the License, or (at your option) any later" in text
    assert "GNU GENERAL PUBLIC LICENSE\nVersion 2, June 1991" in text


def test_client_does_not_import_qgis_or_qt() -> None:
    for path in (PLUGIN / "client").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert not name.startswith(("qgis", "PyQt", "PySide")), (path.name, name)


def test_every_text_has_an_italian_translation() -> None:
    texts = plugin_i18n.extract()
    translations = plugin_i18n.read_translations()
    assert texts and plugin_i18n.problems(texts, translations) == []
    compiled = (PLUGIN / "i18n" / "phrear_it.qm").read_bytes()
    for source in {t.source for t in texts}:
        # .qm files store the translations in UTF-16 big endian
        assert translations[source].encode("utf-16-be") in compiled, source


def test_translations_keep_the_placeholders() -> None:
    root = ET.parse(PLUGIN / "i18n" / "phrear_it.ts").getroot()
    for message in root.iter("message"):
        source, translation = message.findtext("source") or "", message.findtext("translation")
        assert translation is not None
        for name in {p.split("}")[0] for p in source.split("{")[1:]}:
            assert "{" + name + "}" in translation, (source, translation)


def test_zip_contains_the_plugin_only(tmp_path: Path) -> None:
    archive = plugin_package.build_zip(tmp_path)
    assert archive.name == f"phrear_qgis-{plugin_package.version()}.zip"
    names = zipfile.ZipFile(archive).namelist()
    assert all(n.startswith("phrear_qgis/") for n in names)
    for required in ("__init__.py", "metadata.txt", "LICENSE", "plugin.py", "icons/phrear.svg",
                     "i18n/phrear_it.qm", "client/command.py"):  # fmt: skip
        assert f"phrear_qgis/{required}" in names, required
    assert not any("__pycache__" in n or n.endswith((".pyc", ".ts")) for n in names)


def test_link_reuses_its_own_link_and_never_replaces(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    target = plugin_package.link(plugins)
    assert target.resolve() == PLUGIN.resolve()
    assert plugin_package.link(plugins) == target  # already linked: nothing to do
    other = tmp_path / "other" / "plugins"
    (other / "phrear_qgis").mkdir(parents=True)
    try:
        plugin_package.link(other)
    except SystemExit as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("an existing folder must not be replaced")
