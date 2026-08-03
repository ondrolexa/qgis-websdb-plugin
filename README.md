# WebSDB - QGIS Plugin

QGIS plugin to read structural geology data from a [WebSDB](https://github.com/ondrolexa/qgis-websdb-plugin) server and plot it on the map or stereonet.

The plugin connects to a WebSDB server over its REST API (log in with a server URL, username, and password, then pick a project to work with) rather than opening a local database file.
The plugin provides the following functionalities:
1) Read sites and structural data from the connected project, filtering by structure group, unit, foliation/lineation type, tags, and active selection in the sites layer.
2) Can automatically correct symbol rotation according to grid convergence and magnetic declination (using NOAA data).
3) Contains a basic set of SVG symbols used by structural geologists.
4) Plot selected data on a stereonet using the [APSG](https://github.com/ondrolexa/apsg) python package for structural geologists.
5) Create or update a project's sites from an existing QGIS point layer.

----

## License

Distributed under the terms of the [`GPLv2+` license](LICENSE).
