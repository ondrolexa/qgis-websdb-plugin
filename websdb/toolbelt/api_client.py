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

"""Synchronous HTTP client for the websdb-app REST API.

Uses QgsBlockingNetworkRequest (bundled with PyQGIS) rather than a third-party
HTTP library, and blocks the calling thread - this matches the plugin's
existing style of blocking, dialog.exec()-driven modal flows.
"""

import json

from qgis.core import QgsBlockingNetworkRequest
from qgis.PyQt.QtCore import QByteArray, QUrl, QUrlQuery
from qgis.PyQt.QtNetwork import QHttpMultiPart, QHttpPart, QNetworkRequest

from websdb.api_response import ApiConnectionError, interpret_response

#: default page size used when looping paginated list endpoints
PAGE_LIMIT = 1000


class ApiClient:
    """Thin client for the websdb-app REST API."""

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.token = None

    # -- low level --------------------------------------------------------

    def _build_url(self, path, params=None):
        url = QUrl(f"{self.base_url}{path}")
        if params:
            query = QUrlQuery()
            for key, value in params.items():
                if value is None:
                    continue
                if isinstance(value, (list, tuple, set)):
                    for item in value:
                        query.addQueryItem(key, str(item))
                else:
                    query.addQueryItem(key, str(value))
            url.setQuery(query)
        return url

    def _build_multipart(self, form_data, files):
        multipart = QHttpMultiPart(QHttpMultiPart.ContentType.FormDataType)
        for field_name, value in (form_data or {}).items():
            if value is None:
                continue
            part = QHttpPart()
            part.setHeader(
                QNetworkRequest.KnownHeaders.ContentDispositionHeader,
                f'form-data; name="{field_name}"',
            )
            part.setBody(str(value).encode("utf-8"))
            multipart.append(part)
        for field_name, (filename, content, content_type) in (files or {}).items():
            part = QHttpPart()
            part.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, content_type)
            part.setHeader(
                QNetworkRequest.KnownHeaders.ContentDispositionHeader,
                f'form-data; name="{field_name}"; filename="{filename}"',
            )
            part.setBody(content)
            multipart.append(part)
        return multipart

    def _request(
        self, method, path, params=None, json_body=None, form_data=None, files=None
    ):
        request = QNetworkRequest(self._build_url(path, params))
        if self.token:
            request.setRawHeader(
                b"Authorization", f"Bearer {self.token}".encode("utf-8")
            )

        data = None
        multipart = None
        if files is not None:
            multipart = self._build_multipart(form_data, files)
        elif json_body is not None:
            request.setHeader(
                QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
            )
            data = QByteArray(json.dumps(json_body).encode("utf-8"))
        elif form_data is not None:
            request.setHeader(
                QNetworkRequest.KnownHeaders.ContentTypeHeader,
                "application/x-www-form-urlencoded",
            )
            encoded = "&".join(
                f"{k}={v}" for k, v in form_data.items() if v is not None
            )
            data = QByteArray(encoded.encode("utf-8"))

        breq = QgsBlockingNetworkRequest()
        method = method.upper()
        if method == "GET":
            breq.get(request)
        elif method == "POST":
            breq.post(
                request, multipart if multipart is not None else (data or QByteArray())
            )
        elif method == "PUT":
            breq.put(request, data or QByteArray())
        elif method == "DELETE":
            breq.deleteResource(request)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        # keep multipart alive until the (synchronous, already-finished) request completes
        del multipart

        reply = breq.reply()
        status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        if status_code is None:
            raise ApiConnectionError(breq.errorMessage() or "Could not reach server")

        return interpret_response(status_code, bytes(reply.content()))

    def _list_all(self, path, params=None):
        """Loop a paginated list endpoint (limit/offset) until a short page comes back."""
        results = []
        offset = 0
        base_params = dict(params or {})
        while True:
            page_params = dict(base_params, limit=PAGE_LIMIT, offset=offset)
            page = self._request("GET", path, params=page_params) or []
            results.extend(page)
            if len(page) < PAGE_LIMIT:
                break
            offset += PAGE_LIMIT
        return results

    # -- auth ---------------------------------------------------------------

    def login(self, username, password):
        result = self._request(
            "POST", "/api/login", json_body={"username": username, "password": password}
        )
        self.token = result["access_token"]

    def get_me(self):
        return self._request("GET", "/api/me")

    # -- projects -------------------------------------------------------------

    def list_projects(self):
        return self._request("GET", "/api/projects") or []

    def get_project(self, project_id):
        return self._request("GET", f"/api/projects/{project_id}")

    def create_project(self, name, description=None):
        return self._request(
            "POST",
            "/api/projects",
            json_body={"name": name, "description": description},
        )

    # -- sites ------------------------------------------------------------

    def list_sites(self, project_id):
        return self._list_all(f"/api/projects/{project_id}/sites")

    def update_site(self, site_id, **fields):
        return self._request("PUT", f"/api/sites/{site_id}", json_body=fields)

    def import_sites_geojson(
        self,
        project_id,
        feature_collection,
        name_field,
        description_field="",
        update_existing=False,
        add_new=False,
    ):
        payload = json.dumps(feature_collection).encode("utf-8")
        return self._request(
            "POST",
            f"/api/projects/{project_id}/sites/import",
            form_data={
                "name_field": name_field,
                "description_field": description_field,
                "update_existing": "true" if update_existing else "false",
                "add_new": "true" if add_new else "false",
            },
            files={"file": ("sites.geojson", payload, "application/geo+json")},
        )

    # -- rocks ------------------------------------------------------------

    def list_rocks(self, project_id):
        return self._list_all(f"/api/projects/{project_id}/rocks")

    def create_rock(self, project_id, site_id, name, unit_id=None):
        return self._request(
            "POST",
            f"/api/projects/{project_id}/rocks",
            json_body={"site_id": site_id, "name": name, "unit_id": unit_id},
        )

    def update_rock(self, rock_id, **fields):
        return self._request("PUT", f"/api/rocks/{rock_id}", json_body=fields)

    # -- units --------------------------------------------------------------

    def list_units(self, project_id):
        return self._list_all(f"/api/projects/{project_id}/units")

    def create_unit(self, project_id, name, description=None):
        return self._request(
            "POST",
            f"/api/projects/{project_id}/units",
            json_body={"name": name, "description": description},
        )

    # -- structypes -----------------------------------------------------------

    def list_structypes(self, project_id):
        return self._list_all(f"/api/projects/{project_id}/structypes")

    # -- geodata --------------------------------------------------------------

    def list_geodata(self, project_id, structype_id=None):
        params = {"structype_id": structype_id} if structype_id else None
        return self._list_all(f"/api/projects/{project_id}/geodata", params=params)

    # -- tags ---------------------------------------------------------------

    def list_tags(self, project_id):
        return self._request("GET", f"/api/projects/{project_id}/tags") or []
