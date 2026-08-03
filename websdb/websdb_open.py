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

from websdb.api_response import ApiAuthError, ApiConnectionError, ApiError

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ui/websdb_open.ui")
)

PAGE_LOGIN = 0
PAGE_PROJECT = 1


class WebSDBOpenDialog(QtWidgets.QDialog, FORM_CLASS):
    """Login + project-picker dialog, replacing the old local-file browser."""

    def __init__(self, websdb, parent=None):
        """Constructor."""
        super(WebSDBOpenDialog, self).__init__(
            parent, Qt.WindowType.WindowStaysOnTopHint
        )
        self.setupUi(self)
        self.websdb = websdb
        self.settings = self.websdb.settings

        self.project_id = None
        self.project_name = None

        self.serverUrl.setText(
            self.settings.value("server_url", "http://localhost:8080", type=str)
        )
        self.username.setText(self.settings.value("username", "", type=str))

        self.btnLogin.clicked.connect(self.do_login)
        self.btnLogout.clicked.connect(self.do_logout)
        self.projectTable.itemSelectionChanged.connect(self._update_ok_enabled)
        self.buttonBox.accepted.connect(self.on_ok_clicked)

        self.stackedWidget.setCurrentIndex(PAGE_LOGIN)
        self._update_ok_enabled()

    def exec(self):
        """Always start from a fresh login page - the dialog instance is reused
        across sdb_open() calls, so without this a reopen (e.g. after Disconnect)
        would just redisplay whatever page/project list was left over from the
        previous session instead of prompting for credentials again."""
        self.stackedWidget.setCurrentIndex(PAGE_LOGIN)
        self.password.clear()
        self.loginError.setText("")
        self.projectTable.clearSelection()
        self._update_ok_enabled()
        return super(WebSDBOpenDialog, self).exec()

    def _update_ok_enabled(self):
        if self.stackedWidget.currentIndex() == PAGE_LOGIN:
            enabled = True
        else:
            enabled = len(self.projectTable.selectedItems()) > 0
        self.buttonBox.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setEnabled(
            enabled
        )

    def on_ok_clicked(self):
        if self.stackedWidget.currentIndex() == PAGE_LOGIN:
            self.do_login()
        else:
            self.finish_accept()

    def do_logout(self):
        self.websdb.api.token = None
        self.stackedWidget.setCurrentIndex(PAGE_LOGIN)
        self._update_ok_enabled()

    def do_login(self):
        self.loginError.setText("")
        url = self.serverUrl.text().strip().rstrip("/")
        username = self.username.text().strip()
        password = self.password.text()
        if not url or not username or not password:
            self.loginError.setText(
                self.websdb.tr("Server URL, username and password are required.")
            )
            return

        self.websdb.api.base_url = url
        try:
            self.websdb.api.login(username, password)
            projects = self.websdb.api.list_projects()
        except ApiAuthError:
            self.loginError.setText(self.websdb.tr("Invalid username or password."))
            return
        except ApiConnectionError:
            self.loginError.setText(self.websdb.tr("Could not reach server."))
            return
        except ApiError as err:
            self.loginError.setText(str(err))
            return

        self._populate_projects(projects)
        self.stackedWidget.setCurrentIndex(PAGE_PROJECT)
        self._update_ok_enabled()

    def _populate_projects(self, projects):
        self.projectTable.clear()
        self.projectTable.setColumnCount(4)
        self.projectTable.setHorizontalHeaderLabels(
            ["Name", "Role", "Owner", "Description"]
        )
        self.projectTable.setRowCount(len(projects))
        for row, project in enumerate(projects):
            name_item = QtWidgets.QTableWidgetItem(project.get("name", ""))
            name_item.setData(Qt.ItemDataRole.UserRole, project)
            self.projectTable.setItem(row, 0, name_item)
            self.projectTable.setItem(
                row, 1, QtWidgets.QTableWidgetItem(project.get("role") or "superuser")
            )
            self.projectTable.setItem(
                row, 2, QtWidgets.QTableWidgetItem(project.get("owner_username") or "")
            )
            self.projectTable.setItem(
                row, 3, QtWidgets.QTableWidgetItem(project.get("description") or "")
            )
        self.projectTable.horizontalHeader().setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.projectTable.resizeColumnsToContents()

    def finish_accept(self):
        selected = self.projectTable.selectedItems()
        if not selected:
            return
        project = self.projectTable.item(selected[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        self.project_id = project["id"]
        self.project_name = project["name"]

        self.settings.setValue("server_url", self.websdb.api.base_url)
        self.settings.setValue("username", self.username.text().strip())
        self.settings.setValue("token", self.websdb.api.token)
        self.settings.setValue("project_id", self.project_id)
        self.settings.setValue("project_name", self.project_name)
        super(WebSDBOpenDialog, self).accept()
