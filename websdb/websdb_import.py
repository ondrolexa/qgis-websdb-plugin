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

import os

from qgis.core import Qgis, QgsProject
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui/websdb_importlayer.ui")
)


class WebSDBImportLayer(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, websdb, parent=None):
        """Constructor."""
        super(WebSDBImportLayer, self).__init__(
            parent, Qt.WindowType.WindowStaysOnTopHint
        )
        self.setupUi(self)
        self.layerCombo = QgsMapLayerComboBox()
        self.websdb = websdb
        if websdb.sites_layer in QgsProject.instance().mapLayers().values():
            self.layerCombo.setLayer(websdb.sites_layer)
        self.layerCombo.setFilters(Qgis.LayerFilter.PointLayer)
        self.horizontalLayoutLayer.addWidget(self.layerCombo)
        self.siteCombo = QgsFieldComboBox()
        self.siteCombo.setFilters(Qgis.FieldProxyModelFilter.String)
        self.siteCombo.setAllowEmptyFieldName(False)
        self.verticalLayoutRequired.addWidget(self.siteCombo)
        self.descCombo = QgsFieldComboBox()
        self.descCombo.setFilters(Qgis.FieldProxyModelFilter.String)
        self.descCombo.setAllowEmptyFieldName(True)
        self.verticalLayoutOtional.addWidget(self.descCombo)
        self.layer_changed()
        self.layerCombo.layerChanged.connect(self.layer_changed)

    def layer_changed(self):
        layer = self.layerCombo.currentLayer()
        self.siteCombo.setLayer(layer)
        self.siteCombo.setField("name")
        self.descCombo.setLayer(layer)
        self.descCombo.setField("description")

    def accept(self):
        layer = self.layerCombo.currentLayer()
        if layer is None:
            return
        if self.siteCombo.currentField() == "":
            QtWidgets.QMessageBox.warning(
                self, "Import from layer", "Site name cannot be empty!"
            )
            return
        QtWidgets.QDialog.accept(self)
