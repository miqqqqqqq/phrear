"""Project rules of the plugin: folders, new projects, layers from the schema."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

from phrear import cli
from phrear_qgis.client.project import (
    LayerSpec,
    epsg_code,
    folder_free,
    is_project,
    layer_plan,
    new_project_args,
    new_project_problems,
    slug,
    table_rows,
    upgraded_uri,
)


def test_slug() -> None:
    assert slug("Piana dell'Arno – 2025") == "Piana_dell_Arno_2025"
    assert slug("città") == "citta"
    assert slug("   ") == "progetto"


def test_folders(tmp_path: Path) -> None:
    assert folder_free(tmp_path / "new") and folder_free(tmp_path)
    (tmp_path / "x.txt").write_text("x", encoding="utf-8")
    assert not folder_free(tmp_path)
    assert not is_project(tmp_path)
    (tmp_path / "project.toml").write_text("", encoding="utf-8")
    (tmp_path / "model.gpkg").write_bytes(b"")
    assert is_project(tmp_path)


def test_new_project_rules(tmp_path: Path) -> None:
    start, end = date(2025, 1, 1), date(2026, 1, 1)
    assert new_project_problems("Prova", tmp_path, "prova", start, end, "EPSG:7791") == []
    assert new_project_problems(" ", tmp_path / "no", "p", end, start, "USER:1") == [
        "name_missing",
        "parent_missing",
        "dates_order",
        "crs_not_epsg",
    ]
    (tmp_path / "used").mkdir()
    (tmp_path / "used" / "f").write_text("x", encoding="utf-8")
    assert new_project_problems("P", tmp_path, "used", start, end, "epsg:3003") == ["folder_used"]
    assert epsg_code("epsg:3003") == 3003 and epsg_code("ESRI:102001") is None


def test_new_project_args_create_a_project(tmp_path: Path) -> None:
    args = new_project_args(
        " Prova ", tmp_path / "p", date(2025, 1, 1), date(2026, 1, 1), "EPSG:7792"
    )
    assert args[:2] == ["new", str(tmp_path / "p")]
    assert cli.main(args, text_stdout=io.StringIO(), stdout=io.BytesIO()) == 0
    assert is_project(tmp_path / "p")
    assert 'name = "Prova"' in (tmp_path / "p" / "project.toml").read_text(encoding="utf-8")


def test_layer_plan_follows_the_schema(schema: dict[str, object]) -> None:
    plan = layer_plan(schema, "it")
    layers = [s for s in plan if not s.is_table]
    tables = [s for s in plan if s.is_table]
    order = ["Point", "MultiLineString", "MultiPolygon"]
    ranks = [order.index(s.geometry or "") for s in layers]
    assert ranks == sorted(ranks)
    assert {s.name for s in layers} == {"domain", "wells", "fixed_head_lines", "fixed_head_areas",
                                        "line_stations", "recharge_zones"}  # fmt: skip
    assert plan.index(tables[0]) == len(layers)  # tables after the layers
    assert next(s for s in plan if s.name == "wells").label == "Pozzi"
    assert next(s for s in layer_plan(schema, "en") if s.name == "wells").label == "Wells"
    assert (
        LayerSpec("wells", "Pozzi", "Point")
        .uri(Path("C:/p/model.gpkg"))
        .endswith("model.gpkg|layername=wells|option:NOLOCK=NO")
    )


def test_layer_sources_saved_without_the_option_are_upgraded() -> None:
    assert upgraded_uri("C:/p/model.gpkg|layername=wells") == (
        "C:/p/model.gpkg|layername=wells|option:NOLOCK=NO"
    )
    assert upgraded_uri("C:/p/model.gpkg|layername=wells|option:NOLOCK=YES") == (
        "C:/p/model.gpkg|layername=wells|option:NOLOCK=NO"
    )
    assert upgraded_uri("C:/p/model.gpkg|layername=wells|option:NOLOCK=NO") is None
    assert upgraded_uri("C:/p/heads.nc") is None


def test_table_rows(schema: dict[str, object]) -> None:
    rows = table_rows({"tables": {"wells": 2}}, schema, "it")
    assert ("Pozzi", 2) in rows and ("Dominio del modello", 0) in rows
    assert len(rows) == 14
