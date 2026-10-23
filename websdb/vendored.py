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

"""Housekeeping for the vendored top-level packages (``apsg``, ``geomag``).
Pure Python — no ``qgis`` import, so it can be exercised by ``tests/unit``."""

import os
import sys

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
VENDORED_PACKAGES = ("apsg", "geomag")


def unload_vendored_packages(plugin_dir=PLUGIN_DIR):
    """Forget the vendored packages imported from ``plugin_dir``.

    They are imported as top-level packages (``plugin_dir`` is put on
    ``sys.path``), so QGIS's plugin reload, which only drops ``websdb.*``
    modules, would keep the old copies in ``sys.modules`` after a plugin
    upgrade until QGIS is restarted. Also removes every ``plugin_dir`` entry
    from ``sys.path``; each plugin load inserts another one.

    :return: names of the removed modules
    :rtype: list
    """
    root = os.path.realpath(plugin_dir) + os.sep
    removed = []
    for name, module in list(sys.modules.items()):
        if name.split(".")[0] not in VENDORED_PACKAGES:
            continue
        path = getattr(module, "__file__", None)
        if path and os.path.realpath(path).startswith(root):
            del sys.modules[name]
            removed.append(name)
    sys.path[:] = [
        p
        for p in sys.path
        if os.path.realpath(p or ".") != os.path.realpath(plugin_dir)
    ]
    return removed
