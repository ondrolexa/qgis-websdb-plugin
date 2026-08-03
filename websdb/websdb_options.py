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

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import Qt

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui/websdb_options.ui")
)


class WebSDBOptionsDialog(QtWidgets.QDialog, FORM_CLASS):
    def __init__(self, websdb, parent=None):
        """Constructor."""
        super(WebSDBOptionsDialog, self).__init__(
            parent, Qt.WindowType.WindowStaysOnTopHint
        )
        self.setupUi(self)
        self.btn_calc_md.clicked.connect(self.calc_md)
        self.btn_calc_gc.clicked.connect(self.calc_gc)
        self.btn_store.clicked.connect(self.store_date)
        self.websdb = websdb
        self.settings = self.websdb.settings

    def accept(self):
        try:
            self.settings.setValue("angle_gc", float(self.angle_gc.text()))
            self.settings.setValue("angle_md", float(self.angle_md.text()))
            self.settings.setValue("offset", float(self.offset.text()))
            self.settings.setValue("linmulti", float(self.linmulti.text()))
            self.settings.setValue("auto_gc", bool(self.corr_gc_auto.isChecked()))
            self.settings.setValue("auto_md", bool(self.corr_md_auto.isChecked()))
            super(WebSDBOptionsDialog, self).accept()
        except Exception:
            QtWidgets.QMessageBox.warning(
                self, "Warning", self.websdb.tr("Check option values.")
            )

    def calc_gc(self):
        """Calculate Grid convergence at map canvas centre"""
        gc = self.websdb.calc_gc()
        self.angle_gc.setText("{:g}".format(gc))

    def calc_md(self):
        dec = self.websdb.calc_md(time=self.dateEdit.date().toPyDate())
        self.angle_md.setText("{:g}".format(dec))

    def store_date(self):
        self.websdb.set_measured_date(
            self.dateEdit.date().toPyDate().strftime("%d.%m.%Y %H:%M")
        )
        self.websdb.iface.messageBar().pushSuccess(
            "WebSDB", self.websdb.tr("Date stored for this project.")
        )
