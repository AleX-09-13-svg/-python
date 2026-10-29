import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

from common.cached_sketch import CachedSketchService


class CachedSketchTests(unittest.TestCase):
    def setUp(self):
        self.inventor = Mock()
        self.inventor.create_point2d.side_effect = lambda x, y: NS(X=x, Y=y)
        self.collections = {name: Mock() for name in (
            "SketchPoints", "SketchLines", "GeometricConstraints", "DimensionConstraints",
        )}
        self.reads = []
        collections, reads = self.collections, self.reads

        class Sketch:
            def __getattr__(self, name):
                reads.append(name)
                return collections[name]

        self.sketch = Sketch()
        self.service = CachedSketchService(self.inventor, self.sketch)
        self.collections["SketchPoints"].Add.side_effect = lambda p, hole_center: NS(Geometry=p)
        self.collections["SketchLines"].AddByTwoPoints.side_effect = lambda a, b: NS(
            StartSketchPoint=NS(Geometry=a), EndSketchPoint=NS(Geometry=b),
        )

    def test_each_collection_is_requested_once_for_many_operations(self):
        a, b = NS(X=0, Y=0), NS(X=12, Y=0)
        for _ in range(3):
            self.service.add_sketch_point(self.sketch, a)
            line = self.service.add_sketch_line(self.sketch, a, b, construction=True)
            self.service.add_parallel_constraint(self.sketch, line, line)
            self.service.add_aligned_dimension(self.sketch, line.StartSketchPoint,
                                               line.EndSketchPoint, a, driven=True)
        self.assertEqual(len(self.reads), 4)
        self.assertEqual(set(self.reads), set(self.collections))
        self.assertTrue(line.Construction)
        self.assertTrue(self.collections["DimensionConstraints"].AddTwoPointDistance.call_args.args[-1])

    def test_constraint_error_policy_is_preserved(self):
        self.collections["GeometricConstraints"].AddParallel.side_effect = RuntimeError("constraint failed")
        self.assertIsNone(self.service.add_parallel_constraint(self.sketch, object(), object()))
        with self.assertRaisesRegex(RuntimeError, "constraint failed"):
            self.service.add_parallel_constraint(self.sketch, object(), object(), ignore_errors=False)
        self.assertEqual(self.reads, ["GeometricConstraints"])

    def test_cache_cannot_be_used_for_another_sketch(self):
        with self.assertRaises(ValueError):
            self.service.add_sketch_point(object(), NS(X=0, Y=0))

    def test_long_layout_uses_cached_center_and_preserves_all_five_points(self):
        class Center:
            @property
            def X(self):
                raise AssertionError("Center X must not be queried again")

            @property
            def Y(self):
                raise AssertionError("Center Y must not be queried again")

        center = Center()
        points = self.service.create_drilling_points(self.sketch, center, 1, 0, 19.2,
                                                     center_xy=(10.0, 2.0))
        self.assertEqual([round(p.Geometry.X, 6) for p in points[:4]], [0.4, 19.6, 3.6, 16.4])
        self.assertIs(points[4].Geometry, center)
        self.assertEqual(points[5], 9.6)
        self.service.constrain_drilling_points(self.sketch, object(), object(), points)
        self.assertEqual(self.collections["GeometricConstraints"].AddCoincident.call_count, 6)
        self.assertEqual(self.collections["GeometricConstraints"].AddSymmetry.call_count, 2)
        self.assertEqual(self.reads.count("SketchPoints"), 1)
        self.assertEqual(self.reads.count("GeometricConstraints"), 1)


if __name__ == "__main__":
    unittest.main()
