#! python3  # noqa E265

"""
    Usage from the repo root folder:

    .. code-block:: bash
        # for whole tests
        python -m unittest tests.unit.test_data_mapping
        # for specific test
        python -m unittest tests.unit.test_data_mapping.TestFilterGeodata.test_excludes_fault
"""

# standard library
import unittest

# project
from websdb.data_mapping import (
    build_geojson_feature,
    filter_geodata,
    group_by_datatype,
    resolve_rock_map,
)

ROCKS = [
    {"id": 10, "site_id": 1, "name": "Default", "unit_id": 100},
    {"id": 11, "site_id": 2, "name": "Default", "unit_id": 200},
    {"id": 12, "site_id": 2, "name": "Sample B", "unit_id": None},
]


def geodata(id_, rock_id, datatype, azimuth=10.0, inclination=20.0, tags=None, pair_id=None,
            structype_id=5):
    return {
        "id": id_,
        "rock_id": rock_id,
        "structype_id": structype_id,
        "pair_id": pair_id,
        "description": f"row {id_}",
        "value": {
            "datatype": datatype,
            "args": [azimuth, inclination],
            "kwargs": {"tags": tags or []},
        },
    }


class TestResolveRockMap(unittest.TestCase):
    def test_basic(self):
        rock_map = resolve_rock_map(ROCKS)
        self.assertEqual(
            rock_map[10], {"site_id": 1, "name": "Default", "unit_id": 100}
        )
        self.assertEqual(
            rock_map[12], {"site_id": 2, "name": "Sample B", "unit_id": None}
        )
        self.assertEqual(len(rock_map), 3)

    def test_empty(self):
        self.assertEqual(resolve_rock_map([]), {})


class TestFilterGeodata(unittest.TestCase):
    def setUp(self):
        self.rock_map = resolve_rock_map(ROCKS)
        self.rows = [
            geodata(1, rock_id=10, datatype="Foliation"),
            geodata(2, rock_id=10, datatype="Lineation", pair_id=1),
            geodata(3, rock_id=11, datatype="Foliation", tags=["overturned"]),
            geodata(4, rock_id=12, datatype="Foliation"),
            geodata(5, rock_id=99, datatype="Foliation"),  # orphan rock, must be dropped
            geodata(6, rock_id=10, datatype="Fault"),
        ]

    def test_excludes_fault(self):
        rows = filter_geodata(self.rows, self.rock_map)
        datatypes = {row["datatype"] for row in rows}
        self.assertNotIn("Fault", datatypes)

    def test_excludes_fault_even_with_explicit_any_and_no_other_filters(self):
        # "Any" is represented as datatype=None - must still never include Fault.
        rows = filter_geodata(self.rows, self.rock_map, datatype=None)
        self.assertTrue(all(row["datatype"] != "Fault" for row in rows))

    def test_drops_rows_with_unknown_rock(self):
        rows = filter_geodata(self.rows, self.rock_map)
        self.assertNotIn(5, {row["id"] for row in rows})

    def test_datatype_filter(self):
        rows = filter_geodata(self.rows, self.rock_map, datatype="Foliation")
        self.assertEqual({row["id"] for row in rows}, {1, 3, 4})

    def test_unit_id_none_includes_rocks_with_and_without_unit(self):
        rows = filter_geodata(self.rows, self.rock_map, unit_id=None)
        site_ids = {row["site_id"] for row in rows}
        self.assertEqual(site_ids, {1, 2})

    def test_unit_id_restricts_to_matching_rock_unit(self):
        rows = filter_geodata(self.rows, self.rock_map, unit_id=100)
        self.assertEqual({row["id"] for row in rows}, {1, 2})

    def test_unit_id_excludes_rocks_with_no_unit(self):
        # rock 12 has unit_id=None, must not match an explicit unit filter
        rows = filter_geodata(self.rows, self.rock_map, unit_id=200)
        self.assertEqual({row["id"] for row in rows}, {3})

    def test_tags_filter_requires_all_tags(self):
        rows = filter_geodata(self.rows, self.rock_map, tags=["overturned"])
        self.assertEqual({row["id"] for row in rows}, {3})

    def test_site_ids_filter(self):
        rows = filter_geodata(self.rows, self.rock_map, site_ids=[1])
        self.assertEqual({row["id"] for row in rows}, {1, 2})

    def test_row_shape_carries_rock_and_pair_id(self):
        rows = filter_geodata(self.rows, self.rock_map, datatype="Lineation")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["rock"], "Default")
        self.assertEqual(row["pair_id"], 1)
        self.assertEqual(row["azimuth"], 10.0)
        self.assertEqual(row["inclination"], 20.0)


class TestGroupByDatatype(unittest.TestCase):
    def test_groups(self):
        rows = [
            {"datatype": "Foliation", "id": 1},
            {"datatype": "Lineation", "id": 2},
            {"datatype": "Foliation", "id": 3},
        ]
        groups = group_by_datatype(rows)
        self.assertEqual({row["id"] for row in groups["Foliation"]}, {1, 3})
        self.assertEqual({row["id"] for row in groups["Lineation"]}, {2})

    def test_empty(self):
        self.assertEqual(group_by_datatype([]), {})


class TestBuildGeojsonFeature(unittest.TestCase):
    def test_shape(self):
        feature = build_geojson_feature("LX001", 13.318356, 50.075535, "A site")
        self.assertEqual(feature["type"], "Feature")
        self.assertEqual(feature["properties"], {"name": "LX001", "description": "A site"})
        self.assertEqual(feature["geometry"], {
            "type": "Point",
            "coordinates": [13.318356, 50.075535],
        })

    def test_none_description_becomes_empty_string(self):
        feature = build_geojson_feature("LX002", 1.0, 2.0, None)
        self.assertEqual(feature["properties"]["description"], "")


if __name__ == "__main__":
    unittest.main()
