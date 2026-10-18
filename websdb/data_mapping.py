# -*- coding: utf-8 -*-

# ----------------------------------------------------------
# WebSDB QGIS Plugin
# Copyright (C) 2026 Ondrej Lexa
# ----------------------------------------------------------
# Licensed under the terms of GNU GPL 2
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# --------------------------------------------------------------------

"""Pure data-mapping helpers bridging websdb-app's Site/Rock/Geodata shapes to
the flat site/structure rows the plugin builds QGIS layers from.

Free of any qgis import so this logic is importable and testable in
tests/unit without a QGIS install.
"""


def resolve_rock_map(rocks):
    """Turn a list of RockResponse dicts into {rock_id: {site_id, name, unit_id}}."""
    return {
        rock["id"]: {
            "site_id": rock["site_id"],
            "name": rock["name"],
            "unit_id": rock.get("unit_id"),
        }
        for rock in rocks
    }


def filter_geodata(
    geodata_rows, rock_map, datatype=None, unit_id=None, tags=None, site_ids=None
):
    """Join raw GeodataResponse dicts against a rock_id -> rock map and filter them.

    Fault records are always excluded (out of scope for this plugin - no
    equivalent in the legacy SDB schema, no symbology/plotting support), even
    when no explicit datatype filter ("Any") is requested.

    :param datatype: "Foliation"/"Lineation"/None (no filter beyond excluding Fault).
    :param unit_id: None includes geodata from rocks with any (or no) unit; an int
        restricts to geodata whose rock belongs to that unit.
    :param tags: iterable of required tag strings (row must contain all of them), or None.
    :param site_ids: iterable restricting to specific site ids, or None for all sites.
    :returns: list of flat dicts (id/site_id/rock/unit_id/structype_id/pair_id/
        description/tags/datatype/azimuth/inclination) ready for layer building.
    """
    required_tags = set(tags) if tags else None
    site_id_filter = set(site_ids) if site_ids else None
    result = []
    for row in geodata_rows:
        value = row.get("value") or {}
        row_datatype = value.get("datatype")
        if row_datatype not in ("Foliation", "Lineation"):
            continue
        if datatype and row_datatype != datatype:
            continue
        rock = rock_map.get(row.get("rock_id"))
        if rock is None:
            continue
        if unit_id is not None and rock.get("unit_id") != unit_id:
            continue
        if site_id_filter is not None and rock["site_id"] not in site_id_filter:
            continue
        row_tags = set((value.get("kwargs") or {}).get("tags") or [])
        if required_tags and not required_tags.issubset(row_tags):
            continue
        args = value.get("args") or [None, None]
        result.append(
            {
                "id": row["id"],
                "site_id": rock["site_id"],
                "rock": rock["name"],
                "unit_id": rock.get("unit_id"),
                "structype_id": row.get("structype_id"),
                "pair_id": row.get("pair_id"),
                "description": row.get("description"),
                "tags": sorted(row_tags),
                "datatype": row_datatype,
                "azimuth": args[0],
                "inclination": args[1],
            }
        )
    return result


def group_by_datatype(rows):
    """Split filtered geodata rows into {datatype: [rows]} so each output layer
    stays an unambiguous single datatype."""
    groups = {}
    for row in rows:
        groups.setdefault(row["datatype"], []).append(row)
    return groups


def build_geojson_feature(name, lon, lat, description=""):
    """Build a single GeoJSON Point Feature dict (WGS84 lon/lat expected)."""
    return {
        "type": "Feature",
        "properties": {"name": name, "description": description or ""},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }
