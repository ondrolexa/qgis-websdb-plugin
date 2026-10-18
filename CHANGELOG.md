# CHANGELOG

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

<!--

## Unreleased - YYYY-DD-mm

-->

## 1.0.4 - 2026-10-18

- Code-quality cleanup for the plugin repository checks: flake8-clean plugin code
  (`read_structures` split into helpers), lint fixes in vendored APSG/geomag, unused APSG
  `shell.py` removed, executable bits removed from Python files.

## 1.0.3 - 2026-10-18

- Use scoped `Qgis` enums (`TransformDirection`, `WkbType`, `LayerFilter`,
  `FieldProxyModelFilter`) for QGIS 4 / PyQt6 compatibility.

## 1.0.2 - 2026-10-18

- Vendored APSG patched to pass the Bandit security scan: `assert` statements replaced with
  exceptions, `random` replaced with NumPy's generator, unused pickle-based `save()`/`load()`
  methods removed.
- Fixed "structures read successfully" and "grid points interpolated" notifications showing
  `{layer.featureCount()}` instead of the number of features.

## 1.0.1 - 2026-10-18

- Updated vendored APSG to 2.0.6 (new stereonet engine; contour densities are now in standard
  deviations above random).
- Stereonet contours now use the Kamb method; replaced the contour "Resolution" setting
  with "Sigma" (Kamb smoothing, default 3.0).

## 1.0.0 - 2026-08-03

- Refactored the plugin to read/write structural geology data over the WebSDB REST API instead of
  a local PySDB `.sdb` SQLite file: connect with a server URL/username/password, then pick a
  project to work with.
- The plugin is now read/plot/import plus a bulk "Create/Update sites..." action against the connected project.
