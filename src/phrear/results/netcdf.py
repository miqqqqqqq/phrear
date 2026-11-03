"""Heads of a run as NetCDF UGRID, for the mesh layers of QGIS (docs/SPEC.md, section 17).

The mesh has one face per grid column, with counter-clockwise nodes and the MF6
DIS geometry read from the binary grid file of the run, so the file describes the
run even if the project changed afterwards. Variables, all on faces:

- ``head_l<k>`` (time, face): head of layer k, m a.s.l.; missing where the cell is
  inactive or pass-through, or dry (convertible cell with head below its bottom);
- ``head_upper`` (time, face): head of the uppermost saturated active cell, the
  water table of unconfined columns and the piezometric head of confined ones;
- ``top``, ``bottom_l<k>``, ``idomain_l<k>``: geometry of the layers.

Time is in days since the model start date: the initial steady state is at 0 and
every later value at the end of its time step. The CRS is written as a CF grid
mapping and with the attributes read by MDAL, the library behind QGIS meshes.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Final

import flopy
import numpy as np
import numpy.typing as npt
import pyproj
import xarray as xr

from phrear.errors import ResultsError
from phrear.grid.structured import StructuredGeometry
from phrear.modflow.simulation import HEAD_FILE, MODEL

HEADS_NC: Final = "heads.nc"
MESH: Final = "mesh2d"
CRS_VAR: Final = "projected_coordinate_system"
_INACTIVE: Final = 1e29
FloatArray = npt.NDArray[np.float64]


def _geometry(grb: Any) -> StructuredGeometry:
    return StructuredGeometry(
        nrow=int(grb.nrow),
        ncol=int(grb.ncol),
        cell_size=float(grb.delr[0]),
        xorigin=float(grb.xorigin),
        yorigin=float(grb.yorigin),
        angrot=float(grb.angrot),
    )


def _mesh(geometry: StructuredGeometry) -> dict[str, Any]:
    x, y = geometry.corners()
    nrow, ncol = geometry.nrow, geometry.ncol
    index = np.arange((nrow + 1) * (ncol + 1)).reshape(nrow + 1, ncol + 1)
    # counter-clockwise: top-left, bottom-left, bottom-right, top-right (row 0 is north)
    faces = np.stack(
        [index[:-1, :-1], index[1:, :-1], index[1:, 1:], index[:-1, 1:]], axis=-1
    ).reshape(-1, 4)
    cx, cy = geometry.centers()
    return {
        "node_x": x.ravel(),
        "node_y": y.ravel(),
        "faces": faces.astype(np.int32),
        "face_x": cx.ravel(),
        "face_y": cy.ravel(),
    }


def heads_dataset(folder: Path, manifest: dict[str, Any], created: datetime) -> xr.Dataset:
    grb = flopy.mf6.utils.MfGrdFile(str(folder / f"{MODEL}.dis.grb"), verbose=False)
    geometry = _geometry(grb)
    nlay, nface = int(grb.nlay), geometry.ncell
    top = np.asarray(grb.top, dtype=np.float64).reshape(nface)
    botm = np.asarray(grb.bot, dtype=np.float64).reshape(nlay, nface)
    idomain = np.asarray(grb.idomain).reshape(nlay, nface)
    layers = manifest["model"]["layers"]
    convertible = np.array([bool(layer["convertible"]) for layer in layers])

    head_file = flopy.utils.HeadFile(str(folder / HEAD_FILE))
    times = np.asarray(head_file.get_times(), dtype=np.float64) - manifest["model"]["offset_d"]
    raw = np.stack([head_file.get_data(totim=t) for t in head_file.get_times()]).reshape(
        len(times), nlay, nface
    )
    heads = np.where(np.abs(raw) > _INACTIVE, np.nan, raw)
    heads = np.where(idomain[None] > 0, heads, np.nan)
    dry = convertible[None, :, None] & (heads < botm[None])
    heads = np.where(dry, np.nan, heads)
    upper = np.full((len(times), nface), np.nan)
    for k in reversed(range(nlay)):
        upper = np.where(np.isnan(heads[:, k]), upper, heads[:, k])

    mesh = _mesh(geometry)
    face, time = f"{MESH}_nFaces", "time"
    data: dict[str, Any] = {
        MESH: (
            (),
            np.int32(0),
            {
                "cf_role": "mesh_topology",
                "long_name": "Topology of the model grid columns",
                "topology_dimension": 2,
                "node_coordinates": f"{MESH}_node_x {MESH}_node_y",
                "face_node_connectivity": f"{MESH}_face_nodes",
                "face_dimension": face,
                "face_coordinates": f"{MESH}_face_x {MESH}_face_y",
            },
        ),
        f"{MESH}_node_x": (f"{MESH}_nNodes", mesh["node_x"], _coord("x", "node")),
        f"{MESH}_node_y": (f"{MESH}_nNodes", mesh["node_y"], _coord("y", "node")),
        f"{MESH}_face_x": (face, mesh["face_x"], _coord("x", "face")),
        f"{MESH}_face_y": (face, mesh["face_y"], _coord("y", "face")),
        f"{MESH}_face_nodes": (
            (face, f"{MESH}_nMax_face_nodes"),
            mesh["faces"],
            {
                "cf_role": "face_node_connectivity",
                "long_name": "Vertex nodes of the faces, counter-clockwise",
                "start_index": 0,
            },
        ),
        CRS_VAR: ((), np.int32(0), _crs(int(manifest["settings"]["crs"]))),
        "top": (face, top, _face("Top of the model", "Tetto del modello")),
        "head_upper": (
            (time, face),
            upper,
            _face(
                "Head of the uppermost saturated active cell",
                "Carico della prima cella attiva satura dall'alto",
                head=True,
            ),
        ),
    }
    for k in range(nlay):
        n = k + 1
        data[f"head_l{n}"] = (
            (time, face),
            heads[:, k],
            _face(f"Head in layer {n}", f"Carico nel layer {n}", head=True),
        )
        data[f"bottom_l{n}"] = (face, botm[k], _face(f"Bottom of layer {n}", f"Base del layer {n}"))
        attrs = _face(f"IDOMAIN of layer {n}", f"IDOMAIN del layer {n}")
        attrs.pop("units")
        data[f"idomain_l{n}"] = (face, idomain[k].astype(np.int32), attrs)
    start = datetime.fromisoformat(manifest["model"]["start_date"])
    coords = {
        time: (
            time,
            times,
            {
                "standard_name": "time",
                "long_name": "Time since the model start date",
                "units": f"days since {start.isoformat(sep=' ')}",
                "calendar": "standard",
                "axis": "T",
            },
        )
    }
    return xr.Dataset(
        data_vars=data,
        coords=coords,
        attrs={
            "Conventions": "CF-1.8 UGRID-1.0",
            "title": f"Heads of run {manifest['run_id']}",
            "source": f"phrear {manifest['software']['version']}, "
            f"MODFLOW 6 {manifest['engine'].get('version', 'unknown')}",
            "project": manifest["project"]["name"],
            "project_content_hash": manifest["project"]["content_hash"],
            "run_id": manifest["run_id"],
            "history": f"{created.isoformat(timespec='seconds')} phrear export",
        },
    )


def _coord(axis: str, where: str) -> dict[str, Any]:
    return {
        "standard_name": f"projection_{axis}_coordinate",
        "long_name": f"{axis} coordinate of the {where}s",
        "units": "m",
        "grid_mapping": CRS_VAR,
    }


def _face(en: str, it: str, *, head: bool = False) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "long_name": en,
        "long_name_it": it,
        "units": "m",
        "mesh": MESH,
        "location": "face",
        "coordinates": f"{MESH}_face_x {MESH}_face_y",
        "grid_mapping": CRS_VAR,
    }
    if head:
        attrs["comment"] = "m a.s.l.; missing where the cell is inactive, pass-through or dry"
    return attrs


def _crs(epsg: int) -> dict[str, Any]:
    crs = pyproj.CRS.from_epsg(epsg)
    wkt = crs.to_wkt()
    return {
        **crs.to_cf(),
        "name": crs.name,
        "epsg": np.int32(epsg),
        "EPSG_code": f"EPSG:{epsg}",
        "wkt": wkt,
        "spatial_ref": wkt,
    }


def write_heads(folder: Path, manifest: dict[str, Any], created: datetime) -> Path:
    """Write ``heads.nc`` in the run folder, replacing it only once complete."""
    dataset = heads_dataset(folder, manifest, created)
    target = folder / HEADS_NC
    temporary = folder / f".{HEADS_NC}.tmp"
    encoding: dict[str, dict[str, Any]] = {
        str(name): {"zlib": True, "complevel": 4, "_FillValue": np.nan}
        for name, var in dataset.data_vars.items()
        if var.dtype.kind == "f" and var.ndim > 0
    }
    dataset.to_netcdf(temporary, engine="netcdf4", encoding=encoding)
    try:
        temporary.replace(target)
    except PermissionError as exc:
        raise ResultsError("results.file_locked", path=str(target)) from exc
    return target
