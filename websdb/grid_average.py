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

"""Spatially-weighted interpolation of structural orientations onto a
regular grid. Pure Python/numpy/scipy/apsg — no ``qgis`` import, so it can be
exercised by ``tests/unit`` without a live QGIS install."""

import os
import sys

import numpy as np
from scipy.spatial.transform import Rotation as SciRot

# the vendored apsg package lives at websdb/apsg/ - extend sys.path the same
# way plugin_main.py does, so this module also resolves it when imported
# standalone (e.g. from tests/unit, without plugin_main.py having run first)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apsg import fol, lin, rotation  # noqa: E402


def bounding_box(points):
    """points: iterable of (x, y). Returns (xmin, xmax, ymin, ymax)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)


def preset_grid_size(xmin, xmax, ymin, ymax, target_cells=6400, fallback=1.0):
    """(bbox area / target_cells) ** 0.5; degenerate bbox (zero-area) falls
    back to span/sqrt(target_cells) along whichever axis is non-zero, or a
    fixed fallback if both axes are zero (single point / all coincident)."""
    width, height = xmax - xmin, ymax - ymin
    area = width * height
    if area > 0:
        return (area / target_cells) ** 0.5
    span = max(width, height)
    return span / (target_cells**0.5) if span > 0 else fallback


def build_grid_axes(xmin, xmax, ymin, ymax, grid_size):
    """Regular axes, step=grid_size, covering the bbox extended by
    grid_size/2 on each side."""
    xmin_ext, xmax_ext = xmin - grid_size / 2, xmax + grid_size / 2
    ymin_ext, ymax_ext = ymin - grid_size / 2, ymax + grid_size / 2
    nx = int(np.ceil((xmax_ext - xmin_ext) / grid_size)) + 1
    ny = int(np.ceil((ymax_ext - ymin_ext) / grid_size)) + 1
    return xmin_ext + np.arange(nx) * grid_size, ymin_ext + np.arange(ny) * grid_size


def interpolate_grid(points, is_planar, grid_size, weigth_limit):
    """points: list of (x, y, azi, inc). Returns a list of
    {"x", "y", "azi", "inc", "weight"} dicts, one per grid point whose
    accumulated Gaussian weight exceeds weigth_limit."""
    if not points or grid_size <= 0:
        return []

    allx = np.array([p[0] for p in points])
    ally = np.array([p[1] for p in points])

    ref = fol(0, 0) if is_planar else lin(0, 0)
    rots = [
        rotation.from_two_vectors(ref, fol(azi, inc) if is_planar else lin(azi, inc))
        for _, _, azi, inc in points
    ]
    scirots = SciRot.from_matrix(np.array([np.asarray(R) for R in rots]))

    xmin, xmax, ymin, ymax = bounding_box([(p[0], p[1]) for p in points])
    xs, ys = build_grid_axes(xmin, xmax, ymin, ymax, grid_size)

    results = []
    for gx in xs:
        for gy in ys:
            w = np.exp(-((gx - allx) ** 2 + (gy - ally) ** 2) / (2 * grid_size**2))
            wt = float(w.sum())
            if wt <= weigth_limit:
                continue
            mean_rot = rotation(scirots.mean(weights=w).as_matrix())
            azi, inc = ref.transform(mean_rot).geo
            results.append(
                {
                    "x": float(gx),
                    "y": float(gy),
                    "azi": float(azi),
                    "inc": float(inc),
                    "weight": wt,
                }
            )
    return results
