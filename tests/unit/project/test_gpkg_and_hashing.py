"""GeoPackage creation, timestamp triggers and content hashes."""

from __future__ import annotations

import sqlite3
import struct
import time
from pathlib import Path

import pyogrio
import pytest
import shapely

from phrear.project import gpkg, hashing
from phrear.project.schema import TABLES, TABLES_BY_NAME


@pytest.fixture(scope="module")
def template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("gpkg") / "model.gpkg"
    gpkg.create_gpkg(path, 7791)
    return path


@pytest.fixture
def model(template: Path, tmp_path: Path) -> Path:
    path = tmp_path / "model.gpkg"
    path.write_bytes(template.read_bytes())
    return path


def test_all_tables_exist_with_expected_geometry(template: Path) -> None:
    layers = {name: geom for name, geom in pyogrio.list_layers(template)}
    for table in TABLES:
        assert table.name in layers
        expected = table.geometry.value if table.geometry else None
        assert layers[table.name] == expected, table.name
    assert gpkg.missing_tables(template) == []


def test_fields_and_crs_are_readable_by_gdal(template: Path) -> None:
    info = pyogrio.read_info(template, layer="wells")
    assert info["crs"] == "EPSG:7791"
    assert list(info["fields"]) == list(TABLES_BY_NAME["wells"].field_names)
    dtypes = dict(zip(info["fields"], info["dtypes"], strict=True))
    assert dtypes["screen_top"] == "float64"
    assert dtypes["active"] == "bool"
    assert dtypes["created_at"].startswith("datetime64")


def test_application_id_is_geopackage(template: Path) -> None:
    conn = sqlite3.connect(template)
    try:
        assert conn.execute("PRAGMA application_id").fetchone()[0] == 0x47504B47
    finally:
        conn.close()


def _insert_well(path: Path, name: str) -> int:
    with gpkg.connect(path) as conn:
        cur = conn.execute(
            'INSERT INTO "wells" ("name", "active", "screen_top", "screen_bottom") '
            "VALUES (?, 1, 10.0, 20.0)",
            (name,),
        )
        return int(cur.lastrowid or 0)


def test_triggers_fill_and_update_timestamps(model: Path) -> None:
    fid = _insert_well(model, "P1")
    with gpkg.connect(model) as conn:
        created, modified = conn.execute(
            'SELECT created_at, modified_at FROM "wells" WHERE fid = ?', (fid,)
        ).fetchone()
    assert created and created.endswith("Z") and modified == created
    time.sleep(0.01)
    with gpkg.connect(model) as conn:
        conn.execute('UPDATE "wells" SET "screen_top" = 11.0 WHERE fid = ?', (fid,))
        created2, modified2 = conn.execute(
            'SELECT created_at, modified_at FROM "wells" WHERE fid = ?', (fid,)
        ).fetchone()
    assert created2 == created and modified2 > modified


def test_unique_index_rejects_duplicates(model: Path) -> None:
    with gpkg.connect(model) as conn:
        conn.execute('INSERT INTO "hydro_units" ("position", "name") VALUES (1, \'A\')')
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute('INSERT INTO "hydro_units" ("position", "name") VALUES (1, \'B\')')


def test_table_hash_ignores_timestamps_and_tracks_values(model: Path) -> None:
    fid = _insert_well(model, "P1")
    before = hashing.gpkg_hashes(model)
    with gpkg.connect(model) as conn:
        conn.execute(
            'UPDATE "wells" SET "modified_at" = \'2000-01-01T00:00:00.000Z\' WHERE fid = ?', (fid,)
        )
    assert hashing.gpkg_hashes(model) == before
    with gpkg.connect(model) as conn:
        conn.execute('UPDATE "wells" SET "screen_top" = 12.0 WHERE fid = ?', (fid,))
    after = hashing.gpkg_hashes(model)
    changed = {k for k in before if before[k] != after[k]}
    assert changed == {"model.gpkg/wells"}


def test_layer_styles_do_not_change_hashes(model: Path) -> None:
    before = hashing.gpkg_hashes(model)
    with gpkg.connect(model) as conn:
        conn.execute("CREATE TABLE layer_styles (id INTEGER PRIMARY KEY, styleQML TEXT)")
        conn.execute("INSERT INTO layer_styles (styleQML) VALUES ('<qgis/>')")
    assert hashing.gpkg_hashes(model) == before


def _gpkg_blob(geometry: shapely.Geometry, *, envelope: bool) -> bytes:
    """GeoPackage blob with big-endian WKB, with or without the XY envelope."""
    wkb = bytes(shapely.to_wkb(geometry, byte_order=0))
    srs = (7791).to_bytes(4, "little")
    if not envelope:
        return b"GP\x00\x01" + srs + wkb
    minx, miny, maxx, maxy = geometry.bounds
    return b"GP\x00\x03" + srs + struct.pack("<4d", minx, maxx, miny, maxy) + wkb


def test_geometry_hash_is_independent_of_header_and_byte_order() -> None:
    point = shapely.Point(681000.5, 4850000.25)
    plain = hashing.gpkg_blob_to_wkb(_gpkg_blob(point, envelope=False))
    with_env = hashing.gpkg_blob_to_wkb(_gpkg_blob(point, envelope=True))
    assert plain == with_env == shapely.to_wkb(point, byte_order=1)


def test_layers_accept_geometries_through_plain_sqlite(model: Path) -> None:
    """The R-tree triggers need the ST_* functions registered by gpkg.connect."""
    import geopandas as gpd

    frame = gpd.GeoDataFrame(
        {"name": ["P1"], "screen_top": [5.0], "screen_bottom": [15.0]},
        geometry=[shapely.Point(681000.0, 4850000.0)],
        crs="EPSG:7791",
    )
    pyogrio.write_dataframe(frame, model, layer="wells", append=True)
    with gpkg.connect(model) as conn:
        conn.execute('UPDATE "wells" SET "screen_top" = 6.0')
        conn.execute(
            'INSERT INTO "wells" ("name", "screen_top", "screen_bottom", "geom") '
            "SELECT 'P2', 1.0, 2.0, geom FROM \"wells\" WHERE name = 'P1'"
        )
        n = conn.execute('SELECT COUNT(*) FROM "rtree_wells_geom"').fetchone()[0]
    assert n == 2
    read = pyogrio.read_dataframe(model, layer="wells")
    assert sorted(read["name"]) == ["P1", "P2"]


def test_file_and_combined_hash(tmp_path: Path) -> None:
    raster = tmp_path / "a.tif"
    raster.write_bytes(b"abc")
    assert hashing.file_hash(raster) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    assert hashing.combined_hash({"b": "2", "a": "1"}) == hashing.combined_hash(
        {"a": "1", "b": "2"}
    )
