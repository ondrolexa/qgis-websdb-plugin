#! python3  # noqa E265

"""
    Usage from the repo root folder:

    .. code-block:: bash
        # for whole tests
        python -m unittest tests.unit.test_api_response
        # for specific test
        python -m unittest tests.unit.test_api_response.TestInterpretResponse.test_success_json
"""

# standard library
import json
import unittest

# project
from websdb.api_response import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    extract_detail,
    interpret_response,
)


class TestExtractDetail(unittest.TestCase):
    """Test extract_detail()."""

    def test_string_detail(self):
        body = json.dumps({"detail": "Invalid username or password"}).encode("utf-8")
        self.assertEqual(extract_detail(body), "Invalid username or password")

    def test_validation_error_list_detail(self):
        body = json.dumps(
            {
                "detail": [
                    {"loc": ["body", "name"], "msg": "field required"},
                    {"loc": ["body", "lon"], "msg": "value is not a valid float"},
                ]
            }
        ).encode("utf-8")
        self.assertEqual(
            extract_detail(body), "field required; value is not a valid float"
        )

    def test_empty_content(self):
        self.assertIsNone(extract_detail(b""))
        self.assertIsNone(extract_detail(None))

    def test_non_dict_body(self):
        self.assertIsNone(extract_detail(json.dumps([1, 2, 3]).encode("utf-8")))

    def test_invalid_json(self):
        self.assertIsNone(extract_detail(b"not json"))


class TestInterpretResponse(unittest.TestCase):
    """Test interpret_response()."""

    def test_success_json(self):
        body = json.dumps({"id": 1, "name": "Erzgebirge"}).encode("utf-8")
        self.assertEqual(interpret_response(200, body), {"id": 1, "name": "Erzgebirge"})

    def test_success_list(self):
        body = json.dumps([{"id": 1}, {"id": 2}]).encode("utf-8")
        self.assertEqual(interpret_response(200, body), [{"id": 1}, {"id": 2}])

    def test_no_content_204(self):
        self.assertIsNone(interpret_response(204, b""))

    def test_no_status_code_raises_connection_error(self):
        with self.assertRaises(ApiConnectionError):
            interpret_response(None, b"")

    def test_401_raises_auth_error(self):
        body = json.dumps({"detail": "Not authenticated"}).encode("utf-8")
        with self.assertRaises(ApiAuthError) as ctx:
            interpret_response(401, body)
        self.assertEqual(str(ctx.exception), "Not authenticated")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_404_raises_api_error_with_status_code(self):
        body = json.dumps({"detail": "Project not found"}).encode("utf-8")
        with self.assertRaises(ApiError) as ctx:
            interpret_response(404, body)
        self.assertEqual(str(ctx.exception), "Project not found")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_500_without_detail_falls_back_to_generic_message(self):
        with self.assertRaises(ApiError) as ctx:
            interpret_response(500, b"")
        self.assertIn("500", str(ctx.exception))

    def test_malformed_json_on_success_status_raises_api_error(self):
        with self.assertRaises(ApiError):
            interpret_response(200, b"{not valid json")

    def test_auth_error_is_an_api_error(self):
        self.assertTrue(issubclass(ApiAuthError, ApiError))
        self.assertTrue(issubclass(ApiConnectionError, ApiError))


if __name__ == "__main__":
    unittest.main()
