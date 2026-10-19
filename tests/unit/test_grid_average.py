#! python3  # noqa E265

"""
Usage from the repo root folder:

.. code-block:: bash
    # for whole tests
    python -m unittest tests.unit.test_grid_average
    # for specific test
    python -m unittest tests.unit.test_grid_average.TestBoundingBox.test_bounding_box
"""

# standard library
import os
import subprocess
import sys
import unittest

# 3rd party
import numpy as np

try:
    from scipy.spatial.transform import Rotation as SciRot
except ImportError:
    SciRot = None

# project
from websdb.grid_average import (
    bounding_box,
    build_grid_axes,
    interpolate_grid,
    matrices_to_quats,
    preset_grid_size,
    quat_to_matrix,
    weighted_quat_mean,
)


class TestBoundingBox(unittest.TestCase):
    def test_bounding_box(self):
        self.assertEqual(bounding_box([(0, 0), (10, 5), (-2, 8)]), (-2, 10, 0, 8))


class TestPresetGridSize(unittest.TestCase):
    def test_normal_bbox(self):
        # area=6400, target_cells=6400 -> preset = 1.0
        self.assertAlmostEqual(preset_grid_size(0, 80, 0, 80), 1.0)

    def test_zero_height_falls_back_to_width_span(self):
        size = preset_grid_size(0, 80, 5, 5)
        self.assertAlmostEqual(size, 80 / (6400**0.5))

    def test_fully_degenerate_bbox_uses_fixed_fallback(self):
        self.assertEqual(preset_grid_size(3, 3, 3, 3, fallback=2.5), 2.5)


class TestBuildGridAxes(unittest.TestCase):
    def test_axes_cover_bbox_extended_by_half_cell(self):
        xs, ys = build_grid_axes(0, 20, 0, 10, grid_size=5)
        # extended bbox: x in [-2.5, 22.5], y in [-2.5, 12.5]
        self.assertAlmostEqual(xs[0], -2.5)
        self.assertAlmostEqual(ys[0], -2.5)
        self.assertGreaterEqual(xs[-1], 22.5)
        self.assertGreaterEqual(ys[-1], 12.5)
        # regular step
        self.assertAlmostEqual(xs[1] - xs[0], 5)
        self.assertAlmostEqual(ys[1] - ys[0], 5)


class TestInterpolateGrid(unittest.TestCase):
    def test_empty_points_returns_empty(self):
        self.assertEqual(
            interpolate_grid([], True, grid_size=10.0, weigth_limit=0.5), []
        )

    def test_single_planar_point_reproduces_itself_everywhere(self):
        points = [(0.0, 0.0, 30.0, 40.0)]
        results = interpolate_grid(points, True, grid_size=10.0, weigth_limit=0.5)
        self.assertGreater(len(results), 0)
        for rec in results:
            self.assertAlmostEqual(rec["azi"], 30.0, places=3)
            self.assertAlmostEqual(rec["inc"], 40.0, places=3)

    def test_single_linear_point_reproduces_itself_everywhere(self):
        points = [(0.0, 0.0, 120.0, 15.0)]
        results = interpolate_grid(points, False, grid_size=10.0, weigth_limit=0.5)
        self.assertGreater(len(results), 0)
        for rec in results:
            self.assertAlmostEqual(rec["azi"], 120.0, places=3)
            self.assertAlmostEqual(rec["inc"], 15.0, places=3)

    def test_two_identical_orientations_still_recover_same_value(self):
        points = [(0.0, 0.0, 30.0, 40.0), (5.0, 0.0, 30.0, 40.0)]
        results = interpolate_grid(points, True, grid_size=10.0, weigth_limit=0.5)
        self.assertGreater(len(results), 0)
        for rec in results:
            self.assertAlmostEqual(rec["azi"], 30.0, places=2)
            self.assertAlmostEqual(rec["inc"], 40.0, places=2)

    def test_weigth_limit_above_achievable_weight_yields_empty(self):
        points = [(0.0, 0.0, 30.0, 40.0)]
        results = interpolate_grid(points, True, grid_size=10.0, weigth_limit=999.0)
        self.assertEqual(results, [])

    def test_zero_grid_size_returns_empty(self):
        points = [(0.0, 0.0, 30.0, 40.0)]
        self.assertEqual(
            interpolate_grid(points, True, grid_size=0, weigth_limit=0.5), []
        )


class TestQuaternionMean(unittest.TestCase):
    def test_roundtrip_matrix_quat_matrix(self):
        rng = np.random.default_rng(0)
        q = rng.normal(size=(200, 4))
        q /= np.linalg.norm(q, axis=1)[:, None]
        mats = np.array([quat_to_matrix(x) for x in q])
        back = np.array([quat_to_matrix(x) for x in matrices_to_quats(mats)])
        np.testing.assert_allclose(back, mats, atol=1e-12)

    def test_mean_ignores_quaternion_sign(self):
        q = matrices_to_quats([np.eye(3), np.eye(3)])
        q[1] *= -1
        mean = quat_to_matrix(weighted_quat_mean(q, np.array([1.0, 1.0])))
        np.testing.assert_allclose(mean, np.eye(3), atol=1e-12)

    @unittest.skipIf(SciRot is None, "scipy not installed")
    def test_matches_scipy_weighted_mean(self):
        rots = SciRot.random(50, random_state=1)
        w = np.random.default_rng(2).random(50)
        ours = quat_to_matrix(
            weighted_quat_mean(matrices_to_quats(rots.as_matrix()), w)
        )
        np.testing.assert_allclose(ours, rots.mean(weights=w).as_matrix(), atol=1e-10)


class TestWithoutScipy(unittest.TestCase):
    """The plugin's apsg paths must work when scipy isn't installed in QGIS."""

    def test_plugin_paths_import_and_run_without_scipy(self):
        code = """
import sys
sys.modules["scipy"] = None  # makes any ``import scipy...`` raise ImportError
import matplotlib
matplotlib.use("Agg")
from websdb.grid_average import interpolate_grid
from apsg import StereoNet, fol, folset, lin, linset
g = folset([fol(30, 40), fol(35, 45), fol(25, 50)])
g.ortensor().eigenfols()
linset([lin(120, 15), lin(125, 20)]).ortensor().eigenlins()
net = StereoNet()
net.init_figure()
net.contour(g, method="kamb", levels=5, sigma=1)
net.great_circle(*g.ortensor().eigenfols())
net._render()
res = interpolate_grid(
    [(0.0, 0.0, 30.0, 40.0), (5.0, 0.0, 60.0, 20.0)], True, 10.0, 0.5
)
assert res
"""
        repo = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=repo, capture_output=True, text=True
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()
