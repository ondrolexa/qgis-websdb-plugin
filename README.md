# WebSDB - QGIS Plugin

QGIS plugin to read structural geology data from a [WebSDB](https://github.com/ondrolexa/websdb) server and plot it on the map or stereonet.

The plugin connects to a WebSDB server over its REST API (log in with a server URL, username, and password, then pick a project to work with) rather than opening a local database file.

## Features

1. Read sites and structural data from the connected project, filtering by structure group, unit, foliation/lineation type, tags, and active selection in the sites layer.
2. Can automatically correct symbol rotation according to grid convergence and magnetic declination (using NOAA data).
3. Contains a basic set of SVG symbols used by structural geologists.
4. Plot selected data on a stereonet using the [APSG](https://github.com/ondrolexa/apsg) python package for structural geologists.
5. Create or update a project's sites from an existing QGIS point layer.

## Requirements

- QGIS 3.40 or newer (QGIS 4 is supported).
- Access to a WebSDB server (server URL, username, and password).

## Installation

The plugin is available in the official QGIS plugin repository and can be installed with the QGIS plugin manager. It is still marked as **experimental**, so experimental plugins must be allowed first:

1. In QGIS, open **Plugins ▸ Manage and Install Plugins…**.
2. On the **Settings** tab, check **Show also experimental plugins**.
3. On the **All** tab, search for **WebSDB**, select it, and click **Install Plugin**.

Once installed, a WebSDB toolbar appears and the plugin's actions are added under **Database ▸ WebSDB**. Use **Connect to websdb server…** to log in and choose a project. The other actions are enabled once the connection succeeds.

----

## License

Distributed under the terms of the [`GPLv2+` license](LICENSE).
