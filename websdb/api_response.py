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

"""Pure, QGIS-independent websdb-app API response handling.

Deliberately kept at the top of the package (not under toolbelt/, whose
__init__.py eagerly imports qgis.core via log_handler/preferences) and free of
any qgis import itself, so this logic is importable and testable in
tests/unit without a QGIS install. api_client.py (which does need qgis.core
for the actual networking) imports from here rather than duplicating it.
"""

import json


class ApiError(Exception):
    """Generic websdb-app API error."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class ApiAuthError(ApiError):
    """Raised on a 401 response - caller should clear the stored token and
    re-prompt login."""


class ApiConnectionError(ApiError):
    """Raised when the server could not be reached at all (DNS/timeout/refused/TLS)."""


def extract_detail(content_bytes):
    """Best-effort extraction of a human-readable message from a FastAPI
    JSON error body (``{"detail": "..."}`` or the 422 validation-error shape
    ``{"detail": [{"loc": [...], "msg": "..."}, ...]}``)."""
    if not content_bytes:
        return None
    try:
        body = json.loads(content_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    detail = body.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        messages = [
            item.get("msg")
            for item in detail
            if isinstance(item, dict) and item.get("msg")
        ]
        if messages:
            return "; ".join(messages)
    return None


def interpret_response(status_code, content_bytes):
    """Turn an HTTP status code + raw response body into either the parsed
    JSON payload (on success) or a raised ApiError/ApiAuthError/ApiConnectionError.
    """
    if status_code is None:
        raise ApiConnectionError("No response from server")

    if status_code == 401:
        raise ApiAuthError(
            extract_detail(content_bytes) or "Not authenticated", status_code
        )

    if status_code >= 400:
        message = (
            extract_detail(content_bytes) or f"Request failed (HTTP {status_code})"
        )
        raise ApiError(message, status_code)

    if not content_bytes:
        return None

    try:
        return json.loads(content_bytes.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as err:
        raise ApiError(f"Could not parse server response: {err}", status_code)
