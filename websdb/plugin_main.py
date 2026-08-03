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

import json
import os
import sys
from datetime import date, datetime
from math import cos, pi, sin
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsMemoryProviderUtils,
    QgsPointXY,
    QgsProject,
    QgsSettings,
    QgsWkbTypes,
)
from qgis.PyQt import uic
from qgis.PyQt.QtCore import (
    QCoreApplication,
    QDate,
    QDir,
    QLocale,
    QSettings,
    Qt,
    QTranslator,
    QVariant,
    qVersion,
)
from qgis.PyQt.QtGui import QCursor, QIcon
from qgis.PyQt.QtWidgets import QAction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# import included packages
from apsg import folset, linset
from geomag import geomag

# project
from websdb.__about__ import (
    DIR_PLUGIN_ROOT,
    __title__,
)
from websdb.api_response import ApiAuthError, ApiConnectionError, ApiError
from websdb.data_mapping import (
    build_geojson_feature,
    filter_geodata,
    group_by_datatype,
    resolve_rock_map,
)
from websdb.toolbelt import PlgLogger
from websdb.toolbelt.api_client import ApiClient

# Import the code for the dialog
from .websdb_import import WebSDBImportLayer
from .websdb_open import WebSDBOpenDialog
from .websdb_options import WebSDBOptionsDialog
from .websdb_plot import WebSDBPlotDialog
from .websdb_structures import WebSDBStructuresDialog

GM = geomag.GeoMag()

structure_fields = {
    "name": QVariant.String,
    "unit": QVariant.String,
    "azi": QVariant.Double,
    "inc": QVariant.Double,
    "struct": QVariant.String,
    "tags": QVariant.String,
    "desc": QVariant.String,
    "planar": QVariant.Int,
    "rotate": QVariant.Double,
    "label": QVariant.String,
    "lbloff": QVariant.String,
    "rock": QVariant.String,
    "pair_id": QVariant.Int,
}

site_fields = {
    "id": QVariant.Int,
    "name": QVariant.String,
    "description": QVariant.String,
}


def restore_cursor():
    while (
        QgsApplication.instance().overrideCursor() is not None
        and QgsApplication.instance().overrideCursor().shape()
        == Qt.CursorShape.WaitCursor
    ):
        QgsApplication.instance().restoreOverrideCursor()


# ##################################
# ########## Classes ###############
# ##################################


class WebSDBPlugin:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # logger
        self.log = PlgLogger().log
        # translation
        # initialize the locale
        self.locale: str = QgsSettings().value("locale/userLocale", QLocale().name())[
            0:2
        ]
        locale_path: Path = (
            DIR_PLUGIN_ROOT
            / "resources"
            / "i18n"
            / f"{__title__.lower()}_{self.locale}.qm"
        )
        self.log(
            message=f"Translation: {self.locale}, {locale_path}",
            log_level=Qgis.MessageLevel.NoLevel,
        )
        if locale_path.exists():
            self.translator = QTranslator()
            self.translator.load(str(locale_path.resolve()))
            QCoreApplication.installTranslator(self.translator)
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # register a search path for the plugin's own icons, so they can be
        # loaded as QIcon("icons:icon_xxx.png") without a compiled .qrc/rcc step
        QDir.addSearchPath("icons", os.path.join(self.plugin_dir, "icons"))
        # check SVG dirs
        websdb_svg_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "svg"
        )
        svg_paths = QgsSettings().value("svg/searchPathsForSVG")
        if svg_paths is None:
            QgsSettings().setValue("svg/searchPathsForSVG", [websdb_svg_path])
        elif isinstance(svg_paths, str):
            QgsSettings().setValue(
                "svg/searchPathsForSVG", [svg_paths, websdb_svg_path]
            )
        else:
            if websdb_svg_path not in svg_paths:
                svg_paths.append(websdb_svg_path)
                QgsSettings().setValue("svg/searchPathsForSVG", svg_paths)
        # initialize locale
        if QSettings().value("locale/userLocale"):
            locale = QSettings().value("locale/userLocale")[0:2]
            locale_path = os.path.join(
                self.plugin_dir, "i18n", "WebSDB_{}.qm".format(locale)
            )

            if os.path.exists(locale_path):
                self.translator = QTranslator()
                self.translator.load(locale_path)

                if qVersion() > "4.3.3":
                    QCoreApplication.installTranslator(self.translator)

        # Get the params from last session.
        self.settings = QSettings("LX", "websdb")
        if self.settings.value("offset") is None:
            self.settings.setValue("offset", 3.5)
        if self.settings.value("linmulti") is None:
            self.settings.setValue("linmulti", 1.7)
        if self.settings.value("angle_gc") is None:
            self.settings.setValue("angle_gc", 0)
        if self.settings.value("angle_md") is None:
            self.settings.setValue("angle_md", 0)
        if self.settings.value("auto_gc") is None:
            self.settings.setValue("auto_gc", True)
        if self.settings.value("auto_md") is None:
            self.settings.setValue("auto_md", True)

        # API session state - only the JWT is ever persisted, never the password
        self.api = ApiClient(
            self.settings.value("server_url", "http://localhost:8080", type=str)
        )
        self.api.token = self.settings.value("token", "", type=str) or None
        self.project_id = self.settings.value("project_id", 0, type=int) or None
        self.project_name = self.settings.value("project_name", "", type=str) or None

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr("&WebSDB")
        # create toolbar
        self.toolbar = self.iface.addToolBar("WebSDB")
        self.toolbar.setObjectName("WebSDB")

        # Create the dialogs (after translation) and keep reference
        self.open_dlg = WebSDBOpenDialog(self)
        self.options_dlg = WebSDBOptionsDialog(self)
        self.structures_dlg = WebSDBStructuresDialog(self)
        self.plot_dlg = WebSDBPlotDialog(self)

        # logging
        self.log = QgsApplication.messageLog()
        self.bar = self.iface.messageBar()

        # Store sites layer
        self.dbok = False
        self.sites_layer = None

    def check_connection(self):
        """Validate the stored session/project and enable actions accordingly."""
        try:
            if not self.project_id:
                raise ValueError
            self.api.get_me()
            project = self.api.get_project(self.project_id)
            self.project_name = project["name"]
            self.dbok = True
            for ac in self.actions:
                ac.setEnabled(True)
        except ApiAuthError:
            self.dbok = False
            self.settings.setValue("token", "")
            self.api.token = None
            for ac in self.actions[1:]:
                ac.setDisabled(True)
            self.bar.pushWarning(
                "WebSDB", self.tr("Session expired, please connect again")
            )
        except ApiConnectionError:
            self.dbok = False
            for ac in self.actions[1:]:
                ac.setDisabled(True)
            self.bar.pushWarning("WebSDB", self.tr("Cannot reach server"))
        except (ApiError, ValueError):
            self.dbok = False
            for ac in self.actions[1:]:
                ac.setDisabled(True)
            self.bar.pushWarning("WebSDB", self.tr("Not connected to a project"))

    def _handle_api_error(self, err):
        """Shared error -> message-bar-warning mapping for API calls made outside
        check_connection (read_sites/read_structures/import_from_layer/site edit)."""
        if isinstance(err, ApiAuthError):
            self.settings.setValue("token", "")
            self.api.token = None
            self.dbok = False
            for ac in self.actions[1:]:
                ac.setDisabled(True)
            self.bar.pushWarning(
                "WebSDB", self.tr("Session expired, please connect again")
            )
        elif isinstance(err, ApiConnectionError):
            self.bar.pushWarning("WebSDB", self.tr("Cannot reach server"))
        else:
            self.bar.pushWarning("WebSDB", str(err))

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate("WebSDB", message)

    def res_path(self, path):
        return os.path.join(self.plugin_dir, path)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a searchPath
            path registered via QDir.addSearchPath (e.g. 'icons:bar.png') or a
            normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToDatabaseMenu(self.menu, action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = "icons:icon_sdb.png"
        self.add_action(
            icon_path,
            text=self.tr("Connect to websdb server..."),
            callback=self.sdb_open,
            add_to_toolbar=False,
            parent=self.iface.mainWindow(),
        )

        icon_path = "icons:icon_discon.png"
        self.add_action(
            icon_path,
            text=self.tr("Disconnect"),
            callback=self.sdb_disconnect,
            add_to_toolbar=False,
            parent=self.iface.mainWindow(),
        )

        icon_path = "icons:icon_lyr.png"
        self.add_action(
            icon_path,
            text=self.tr("Create/Update sites..."),
            callback=self.import_from_layer,
            add_to_toolbar=False,
            parent=self.iface.mainWindow(),
        )

        icon_path = "icons:icon_opt.png"
        self.add_action(
            icon_path,
            text=self.tr("Read SDB options"),
            callback=self.set_options,
            add_to_menu=False,
            parent=self.iface.mainWindow(),
        )

        icon_path = "icons:icon_loc.png"
        self.add_action(
            icon_path,
            text=self.tr("Read sites from project"),
            callback=self.read_sites,
            add_to_menu=False,
            parent=self.iface.mainWindow(),
        )

        icon_path = "icons:icon_str.png"
        self.add_action(
            icon_path,
            text=self.tr("Read structures from project"),
            callback=self.read_structures,
            add_to_menu=False,
            parent=self.iface.mainWindow(),
        )

        icon_path = "icons:icon_net.png"
        self.add_action(
            icon_path,
            text=self.tr("Plot structures"),
            callback=self.plot_structures,
            add_to_menu=False,
            parent=self.iface.mainWindow(),
        )

        # Nothing is connected yet at startup - only Connect (index 0) stays
        # enabled so the user can log in; everything after it requires an
        # active project connection.
        self.dbok = False
        for ac in self.actions[1:]:
            ac.setDisabled(True)

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginDatabaseMenu(self.tr("&WebSDB"), action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        if hasattr(self, "toolbar"):
            del self.toolbar
        # remove svg path
        websdb_svg_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "svg"
        )
        svg_paths = QgsSettings().value("svg/searchPathsForSVG")
        if svg_paths:
            if websdb_svg_path in svg_paths:
                svg_paths.remove(websdb_svg_path)
                QgsSettings().setValue("svg/searchPathsForSVG", svg_paths)

    def calc_gc(self, point=None):
        """Calculate Grid convergence for project CRS"""
        crsSrc = QgsProject.instance().crs()
        crsDst = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        xform = QgsCoordinateTransform(crsSrc, crsDst, QgsProject.instance())

        if point is None:
            point = self.iface.mapCanvas().extent().center()
        point_ll = xform.transform(point, QgsCoordinateTransform.ForwardTransform)

        if point_ll.y() < 89.9:
            point_ll_shift = QgsPointXY(point_ll.x(), point_ll.y() + 0.01)
            point_north = xform.transform(
                point_ll_shift, QgsCoordinateTransform.ReverseTransform
            )
            gc = point.azimuth(point_north)
        else:
            point_ll_shift = QgsPointXY(point_ll.x(), point_ll.y() - 0.01)
            point_north = xform.transform(
                point_ll_shift, QgsCoordinateTransform.ReverseTransform
            )
            gc = point_north.azimuth(point)
        return gc

    def calc_md(self, point=None, time=date.today()):
        """Calculate magnetic declination uising Christopher Weiss geomag library.

        Adapted from the geomagc software and World Magnetic Model of the NOAA
        Satellite and Information Service, National Geophysical Data Center
        http://www.ngdc.noaa.gov/geomag/WMM/DoDWMM.shtml
        """
        crsSrc = QgsProject.instance().crs()
        crsDst = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        xform = QgsCoordinateTransform(crsSrc, crsDst, QgsProject.instance())

        if point is None:
            point = self.iface.mapCanvas().extent().center()
        point_ll = xform.transform(point, QgsCoordinateTransform.ForwardTransform)

        mag = GM.GeoMag(point_ll.y(), point_ll.x(), time=time)
        return mag.dec

    def sanitize(self, text):
        rtext = ""
        if text is not None:
            rtext = str(text).replace("\r\n", " ").replace("\n", " ")
        return rtext

    # -- "measured date" (magnetic declination survey date), local-only ----------
    # websdb-app has no per-project metadata store, so this is kept client-side,
    # keyed by server+project so switching projects in one QGIS session can't leak
    # one project's survey date into another's.

    def _measured_date_key(self):
        return f"{self.api.base_url}|{self.project_id}"

    def _measured_date(self):
        raw = self.settings.value("measured_dates", "", type=str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        value = data.get(self._measured_date_key())
        if value:
            try:
                return datetime.strptime(value, "%d.%m.%Y %H:%M").date()
            except ValueError:
                pass
        return date.today()

    def set_measured_date(self, dt_str):
        raw = self.settings.value("measured_dates", "", type=str)
        try:
            data = json.loads(raw) if raw else {}
        except ValueError:
            data = {}
        data[self._measured_date_key()] = dt_str
        self.settings.setValue("measured_dates", json.dumps(data))

    def sdb_open(self):
        """Log in, pick a project, and connect to it immediately."""
        if self.open_dlg.exec():
            self.project_id = self.open_dlg.project_id
            self.project_name = self.open_dlg.project_name
            self.check_connection()

    def sdb_disconnect(self):
        """Drop the active project connection (available from the menu only)."""
        self.dbok = False
        self.api.token = None
        self.settings.setValue("token", "")
        for ac in self.actions[1:]:
            ac.setDisabled(True)

    def set_options(self):
        """Set plugin options"""
        # show the dialog
        self.options_dlg.show()
        # populate dialog
        self.options_dlg.angle_gc.setText(self.settings.value("angle_gc", type=str))
        self.options_dlg.angle_md.setText(self.settings.value("angle_md", type=str))
        self.options_dlg.offset.setText(self.settings.value("offset", type=str))
        self.options_dlg.linmulti.setText(self.settings.value("linmulti", type=str))
        self.options_dlg.corr_gc_auto.setChecked(
            self.settings.value("auto_gc", type=bool)
        )
        self.options_dlg.corr_md_auto.setChecked(
            self.settings.value("auto_md", type=bool)
        )
        # set magnetic declination calendar (no server-side timestamp anymore -
        # defaults to today if nothing has been stored for this project yet)
        md_time = self._measured_date()
        self.options_dlg.dateEdit.setDate(
            QDate(md_time.year, md_time.month, md_time.day)
        )
        # Run the dialog event loop
        self.options_dlg.exec()

    def create_layer(self, name, fields):
        """Create temporary point layer (websdb-app coordinates are always WGS84)"""
        crs = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        lyr_fields = QgsFields()
        for key in fields:
            lyr_fields.append(QgsField(key, fields[key]))
        layer = QgsMemoryProviderUtils.createMemoryLayer(
            name, lyr_fields, QgsWkbTypes.Point, crs
        )
        return layer

    def read_sites(self):
        """Read sites from the connected websdb project"""
        if self.sites_layer not in QgsProject.instance().mapLayers().values():
            QgsApplication.instance().setOverrideCursor(
                QCursor(Qt.CursorShape.WaitCursor)
            )
            try:
                sites = self.api.list_sites(self.project_id)
            except (ApiAuthError, ApiConnectionError, ApiError) as err:
                restore_cursor()
                self._handle_api_error(err)
                return

            layer = self.create_layer("Sites", site_fields)
            provider = layer.dataProvider()
            layer.startEditing()
            skipped = 0
            for site in sites:
                if site.get("lon") is None or site.get("lat") is None:
                    skipped += 1
                    continue
                feature = QgsFeature()
                feature.setGeometry(
                    QgsGeometry.fromPointXY(QgsPointXY(site["lon"], site["lat"]))
                )
                feature.setAttributes(
                    [site["id"], site["name"], self.sanitize(site.get("description"))]
                )
                provider.addFeatures([feature])

            layer.commitChanges()
            # Style layer
            layer.loadNamedStyle(self.res_path("styles/sites.qml"))
            layer.triggerRepaint()
            # add to project
            QgsProject.instance().addMapLayer(layer)
            # store pointer
            self.sites_layer = layer
            restore_cursor()

            if layer.featureCount() > 0:
                message = "{} ".format(layer.featureCount()) + self.tr(
                    "sites read successfully"
                )
                if skipped:
                    message += " ({} {})".format(
                        skipped, self.tr("skipped, missing coordinates")
                    )
                self.bar.pushSuccess("WebSDB", message)
            else:
                self.bar.pushWarning(
                    "WebSDB", self.tr("There are no sites in database")
                )
        else:
            self.bar.pushWarning("WebSDB", self.tr("Sites layer already exists."))

    def read_structures(self):
        """Read structures from the connected websdb project"""
        # check selection in site layer
        if self.sites_layer not in QgsProject.instance().mapLayers().values():
            selected_enable = False
        else:
            selected_enable = self.sites_layer.selectedFeatureCount() > 0
        # show the dialog
        self.structures_dlg.show()
        # populate dialog
        try:
            structypes = self.api.list_structypes(self.project_id)
            units = self.api.list_units(self.project_id)
            tags = self.api.list_tags(self.project_id)
        except (ApiAuthError, ApiConnectionError, ApiError) as err:
            self._handle_api_error(err)
            return

        self.structures_dlg.comboStructure.clear()
        self.structures_dlg.comboStructure.addItem(self.tr("Any"), None)
        for structype in structypes:
            self.structures_dlg.comboStructure.addItem(structype["name"], structype["id"])
        self.structures_dlg.comboUnit.clear()
        self.structures_dlg.comboUnit.addItem(self.tr("Any"), None)
        for unit in units:
            self.structures_dlg.comboUnit.addItem(unit["name"], unit["id"])
        self.structures_dlg.radioFoliation.setChecked(True)
        self.structures_dlg.checkAverage.setChecked(False)
        self.structures_dlg.checkSelected.setEnabled(selected_enable)
        self.structures_dlg.checkSelected.setChecked(selected_enable)
        self.structures_dlg.listTags.clear()
        for tag in tags:
            self.structures_dlg.listTags.addItem(tag["name"])
        # Run the dialog event loop
        result = self.structures_dlg.exec()
        if not result:
            return

        QgsApplication.instance().setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            structype_id = self.structures_dlg.comboStructure.currentData()
            unit_id = self.structures_dlg.comboUnit.currentData()
            datatype = (
                "Foliation" if self.structures_dlg.radioFoliation.isChecked() else "Lineation"
            )
            selected_tags = [
                item.text() for item in self.structures_dlg.listTags.selectedItems()
            ]

            rocks = self.api.list_rocks(self.project_id)
            rock_map = resolve_rock_map(rocks)
            sites = self.api.list_sites(self.project_id)
            site_map = {site["id"]: site for site in sites}
            geodata_rows = self.api.list_geodata(self.project_id, structype_id=structype_id)

            site_ids = None
            if selected_enable and self.structures_dlg.checkSelected.isChecked():
                selected_names = {f["name"] for f in self.sites_layer.selectedFeatures()}
                site_ids = {
                    sid for sid, s in site_map.items() if s["name"] in selected_names
                }

            rows = filter_geodata(
                geodata_rows,
                rock_map,
                datatype=datatype,
                unit_id=unit_id,
                tags=selected_tags,
                site_ids=site_ids,
            )
        except (ApiAuthError, ApiConnectionError, ApiError) as err:
            restore_cursor()
            self._handle_api_error(err)
            return

        if not rows:
            restore_cursor()
            self.bar.pushSuccess(
                "WebSDB", self.tr("No structures found. Choose different criteria")
            )
            return

        unit_names = {unit["id"]: unit["name"] for unit in units}
        structype_names = {st["id"]: st["name"] for st in structypes}
        group_label = structype_names.get(structype_id) if structype_id else self.tr("Any")

        # geometry/rotation math: websdb-app sites are always WGS84
        crsSrc = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        crsDst = QgsProject.instance().crs()
        xform = QgsCoordinateTransform(crsSrc, crsDst, QgsProject.instance())
        md_time = self._measured_date()
        average = self.structures_dlg.checkAverage.isChecked()

        any_layer_created = False
        for group_datatype, group_rows in group_by_datatype(rows).items():
            is_planar = group_datatype == "Foliation"
            layer_name = f"{group_label} ({group_datatype})"
            if average:
                layer_name += " " + self.tr("averaged")

            layer = self.create_layer(layer_name, structure_fields)
            provider = layer.dataProvider()
            layer.startEditing()
            layer._is_planar = is_planar

            off_coef = (
                1.0 if is_planar else self.settings.value("linmulti", type=float)
            )

            by_site = {}
            for row in group_rows:
                by_site.setdefault(row["site_id"], []).append(row)

            out_rows = []
            if average:
                for site_id, site_rows in by_site.items():
                    azi = [r["azimuth"] for r in site_rows]
                    inc = [r["inclination"] for r in site_rows]
                    if is_planar:
                        g = folset.from_array(azi, inc)
                        dd = g.ortensor().eigenfols()[0].geo
                    else:
                        g = linset.from_array(azi, inc)
                        dd = g.ortensor().eigenlins()[0].geo
                    first = site_rows[0]
                    out_rows.append(
                        {
                            "site_id": site_id,
                            "azimuth": float(dd[0]),
                            "inclination": float(dd[1]),
                            "rock": first["rock"],
                            "unit": unit_names.get(first["unit_id"], ""),
                            "structype": structype_names.get(first["structype_id"], ""),
                            "tags": "",
                            "description": self.tr("Averaged from {} data").format(
                                len(site_rows)
                            ),
                            "pair_id": None,
                        }
                    )
            else:
                for row in group_rows:
                    out_rows.append(
                        {
                            "site_id": row["site_id"],
                            "azimuth": row["azimuth"],
                            "inclination": row["inclination"],
                            "rock": row["rock"],
                            "unit": unit_names.get(row["unit_id"], ""),
                            "structype": structype_names.get(row["structype_id"], ""),
                            "tags": ", ".join(row["tags"]),
                            "description": self.sanitize(row["description"]),
                            "pair_id": row["pair_id"],
                        }
                    )

            for rec in out_rows:
                site = site_map.get(rec["site_id"])
                if site is None or site.get("lon") is None or site.get("lat") is None:
                    continue
                feature = QgsFeature()
                point = QgsPointXY(site["lon"], site["lat"])
                feature.setGeometry(QgsGeometry.fromPointXY(point))
                # do possible azimuth corrections in canvas crs
                point_canvas = xform.transform(
                    point, QgsCoordinateTransform.ForwardTransform
                )
                delta = 0
                delta += (
                    self.calc_gc(point=point_canvas)
                    if self.settings.value("auto_gc", type=bool)
                    else self.settings.value("angle_gc", type=float)
                )
                delta += (
                    self.calc_md(point=point_canvas, time=md_time)
                    if self.settings.value("auto_md", type=bool)
                    else self.settings.value("angle_md", type=float)
                )
                rotation = rec["azimuth"] + delta
                # calculate label offset
                offx = (
                    off_coef
                    * self.settings.value("offset", type=float)
                    * sin(rotation * pi / 180.0)
                )
                offy = (
                    -off_coef
                    * self.settings.value("offset", type=float)
                    * cos(rotation * pi / 180.0)
                )
                atts = [
                    site["name"],
                    rec["unit"],
                    rec["azimuth"],
                    rec["inclination"],
                    rec["structype"],
                    rec["tags"],
                    rec["description"],
                    1 if is_planar else 0,
                    rotation,
                    int(round(rec["inclination"])),
                    "{},{}".format(offx, offy),
                    rec["rock"],
                    rec["pair_id"],
                ]
                feature.setAttributes(atts)
                provider.addFeatures([feature])

            layer.commitChanges()
            if layer.featureCount() > 0:
                any_layer_created = True
                # Style layer
                if is_planar:
                    layer.loadNamedStyle(self.res_path("styles/planar.qml"))
                else:
                    layer.loadNamedStyle(self.res_path("styles/linear.qml"))
                layer.triggerRepaint()
                # add to project
                QgsProject.instance().addMapLayer(layer)
                self.bar.pushSuccess(
                    "WebSDB",
                    "{} ".format(layer.featureCount())
                    + self.tr("structures read successfully"),
                )

        restore_cursor()
        if not any_layer_created:
            self.bar.pushSuccess(
                "WebSDB", self.tr("No structures found. Choose different criteria")
            )

    def _build_sites_geojson(self, layer, site_field, desc_field):
        """Build a WGS84 GeoJSON FeatureCollection from a QGIS point layer."""
        crsSrc = layer.crs()
        crsDst = QgsCoordinateReferenceSystem.fromEpsgId(4326)
        xform = QgsCoordinateTransform(crsSrc, crsDst, QgsProject.instance())
        features = []
        for feature in layer.getFeatures():
            point = feature.geometry().asPoint()
            point_wgs84 = xform.transform(point, QgsCoordinateTransform.ForwardTransform)
            name = str(feature[site_field])
            desc = self.sanitize(str(feature[desc_field])) if desc_field else ""
            features.append(
                build_geojson_feature(name, point_wgs84.x(), point_wgs84.y(), desc)
            )
        return {"type": "FeatureCollection", "features": features}

    def import_from_layer(self):
        """Create/update sites in the connected project from a QGIS point layer."""
        layers = QgsProject.instance().mapLayers().values()
        if len(layers) == 0:
            self.bar.pushWarning("WebSDB", self.tr("No layer in project."))
            return

        dlg = WebSDBImportLayer(self)
        if not dlg.exec():
            return

        QgsApplication.instance().setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            layer = dlg.layerCombo.currentLayer()
            site_field = dlg.siteCombo.currentField()
            desc_field = dlg.descCombo.currentField()
            update_mode = dlg.radioUpdate.isChecked()

            feature_collection = self._build_sites_geojson(layer, site_field, desc_field)
            description_field = "description" if desc_field else ""

            self.api.import_sites_geojson(
                self.project_id,
                feature_collection,
                name_field="name",
                description_field=description_field,
                update_existing=update_mode,
                add_new=not update_mode,
            )

            restore_cursor()
            self.bar.pushSuccess(
                "WebSDB",
                self.tr("Existing sites successfully updated")
                if update_mode
                else self.tr("New sites successfully created"),
            )
        except (ApiAuthError, ApiConnectionError, ApiError) as err:
            restore_cursor()
            self._handle_api_error(err)

    def plot_structures(self):
        """Select database and set plugin options"""
        layers = self.iface.layerTreeView().selectedLayers()
        self.plot_dlg.tabWidget.clear()
        self.plot_dlg.data_layers = []
        idx = 0
        for layer in layers:
            if hasattr(layer, "_is_planar"):
                self.plot_dlg.data_layers.append((idx, layer))
                if layer._is_planar:
                    w = uic.loadUi(
                        os.path.join(os.path.dirname(__file__), "ui/widget_planar.ui")
                    )
                else:
                    w = uic.loadUi(
                        os.path.join(os.path.dirname(__file__), "ui/widget_linear.ui")
                    )
                self.plot_dlg.tabWidget.addTab(w, layer.name())
                idx += 1
        if idx > 0:
            # show the dialog
            self.plot_dlg.show()
            # prepare stereo net
            self.plot_dlg.plotnet()
            # Run the dialog event loop
            self.plot_dlg.exec()
