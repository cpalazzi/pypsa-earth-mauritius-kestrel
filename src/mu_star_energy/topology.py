"""Propose transmission-line connections from mapped routes and substations."""

from __future__ import annotations

from dataclasses import dataclass

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString
from shapely.ops import substring

METRIC_CRS = "EPSG:32740"


@dataclass(frozen=True)
class TopologyResult:
    buses: gpd.GeoDataFrame
    lines: gpd.GeoDataFrame
    ignored_route_parts: int


def _explode_lines(routes: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    exploded = routes.explode(index_parts=True).reset_index(drop=True)
    return exploded[exploded.geometry.geom_type.eq("LineString")].copy()


def build_substation_topology(
    substations: gpd.GeoDataFrame,
    routes: gpd.GeoDataFrame,
    *,
    snap_tolerance_m: float = 2500,
    default_voltage_kv: float = 66,
) -> TopologyResult:
    """Connect consecutive substations lying near each mapped route.

    The source route shapefile groups multiple line strings into a small number
    of records. This function separates them, finds nearby substations and
    connects consecutive substations along each route. Maximum line power
    remains unset until confirmed CEB data are supplied.
    """
    required = {"bus_id", "geometry"}
    missing = required - set(substations.columns)
    if missing:
        raise ValueError(f"Substations missing columns: {sorted(missing)}")

    buses = substations.to_crs(METRIC_CRS).copy()
    route_parts = _explode_lines(routes.to_crs(METRIC_CRS))
    candidates: list[dict[str, object]] = []
    ignored = 0

    for part_index, route in route_parts.iterrows():
        line = route.geometry
        nearby = buses[buses.geometry.distance(line) <= snap_tolerance_m].copy()
        if len(nearby) < 2:
            ignored += 1
            continue
        nearby["position"] = nearby.geometry.apply(line.project)
        nearby = nearby.sort_values("position").drop_duplicates("bus_id")

        for (_, start), (_, end) in zip(nearby.iloc[:-1].iterrows(), nearby.iloc[1:].iterrows()):
            if start["bus_id"] == end["bus_id"]:
                continue
            start_pos = float(start["position"])
            end_pos = float(end["position"])
            segment = substring(line, start_pos, end_pos)
            if not isinstance(segment, LineString) or segment.length == 0:
                segment = LineString([start.geometry, end.geometry])
            voltage_hint = route.get("voltage_kv_hint")
            voltage_kv = (
                float(voltage_hint) if pd.notna(voltage_hint) else float(default_voltage_kv)
            )
            candidates.append(
                {
                    "bus0": str(start["bus_id"]),
                    "bus1": str(end["bus_id"]),
                    "route_part": int(part_index),
                    "v_nom_kv": voltage_kv,
                    "length_km": segment.length / 1000,
                    "s_nom_mva": float("nan"),
                    "geometry": segment,
                }
            )

    lines = gpd.GeoDataFrame(candidates, geometry="geometry", crs=METRIC_CRS)
    if not lines.empty:
        lines["pair"] = lines.apply(
            lambda row: "::".join(sorted((row["bus0"], row["bus1"]))), axis=1
        )
        lines = (
            lines.sort_values("length_km")
            .drop_duplicates("pair")
            .drop(columns="pair")
            .reset_index(drop=True)
        )
        lines["line_id"] = [f"LINE_{index + 1:03d}" for index in lines.index]
        lines = lines[
            [
                "line_id",
                "bus0",
                "bus1",
                "v_nom_kv",
                "length_km",
                "s_nom_mva",
                "route_part",
                "geometry",
            ]
        ]

    buses = buses.to_crs("EPSG:4326")
    if lines.empty:
        lines = gpd.GeoDataFrame(
            columns=[
                "line_id",
                "bus0",
                "bus1",
                "v_nom_kv",
                "length_km",
                "s_nom_mva",
                "route_part",
                "geometry",
            ],
            geometry="geometry",
            crs="EPSG:4326",
        )
    else:
        lines = lines.to_crs("EPSG:4326")
    return TopologyResult(buses=buses, lines=lines, ignored_route_parts=ignored)
