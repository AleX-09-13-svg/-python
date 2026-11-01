import contextlib
import io
import math
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, call, patch

from petli.layout import calculate_layout, hinge_count, pilot_positions, rectangle_frame, side_hole_rows
from petli.petli import DIAMETER, DEPTH, PILOT_DIAMETER, PILOT_DEPTH, build_sketch, inward_direction, main
from petli.side_sketch import build_side_sketch
from petli.runtime import prepare_centers
from stiajka.hole_builder import TimedHoleBuilder


def rectangle(width=60, height=180):
    corners = [(0, 0), (width, 0), (width, height), (0, height)]
    return [(corners[i], corners[(i + 1) % 4]) for i in range(4)]


class LayoutTests(unittest.TestCase):
    def test_side_offsets_follow_actual_edge_with_facade_gap(self):
        for facade_x, expected_x in [(-1, (2, 5.2)), (61, (58, 54.8))]:
            frame = rectangle_frame(rectangle(), (facade_x, 0), (0, 1))
            rows = side_hole_rows(frame, [(facade_x, 15), (facade_x, 140)], 0.2)
            for row, height in zip(rows, (15, 140)):
                for point, x in zip(row[1:], expected_x):
                    self.assertAlmostEqual(point[0], x)
                    self.assertAlmostEqual(point[1], height)
                self.assertAlmostEqual(math.dist(row[0], row[1]), 2)
                self.assertAlmostEqual(math.dist(row[1], row[2]), 3.2)

    def test_side_offsets_rotate_with_geometry(self):
        def transform(p):
            return (p[0] * 0.6 - p[1] * 0.8 + 13, p[0] * 0.8 + p[1] * 0.6 - 9)
        segments = [(transform(a), transform(b)) for a, b in rectangle()]
        frame = rectangle_frame(segments, transform((-1, 0)), (-0.8, 0.6))
        row = side_hole_rows(frame, [transform((-1, 15))], 0.2)[0]
        for actual, expected in zip(row, [transform((0, 15)), transform((2, 15)), transform((5.2, 15))]):
            self.assertAlmostEqual(math.dist(actual, expected), 0)

    def test_side_rejects_insufficient_depth_height_and_overlapping_holes(self):
        for width, centers, diameter in [(5.2, [(-1, 15)], 0.2),
                                         (60, [(-1, 0.05)], 0.2),
                                         (60, [(-1, 15), (-1, 15.1)], 0.2),
                                         (60, [(-1, 15)], 0)]:
            frame = rectangle_frame(rectangle(width=width), (-1, 0), (0, 1))
            with self.subTest(width=width, centers=centers), self.assertRaises(ValueError):
                side_hole_rows(frame, centers, diameter)

    def test_pilot_pattern_is_45_by_9_5_mm_for_both_sides(self):
        for side in (-0.2, 60.2):
            layout = calculate_layout(rectangle(), (side, 0), (0, 1), 3.5)
            positions = pilot_positions(layout, 3.5, 0.2)
            self.assertEqual(len(positions), 2 * len(layout.distances))
            for i, center in enumerate(layout.distances):
                left, right = positions[2 * i:2 * i + 2]
                self.assertAlmostEqual(right[0] - left[0], 4.5)
                self.assertAlmostEqual((left[0] + right[0]) / 2, center)
                self.assertAlmostEqual(left[1] - 2.2, 0.95)
                self.assertEqual(left[1], right[1])

    def test_pilot_holes_reject_outside_and_overlapping_patterns(self):
        layout = calculate_layout(rectangle(), (0, 0), (0, 1), 3.5)
        for diameter in (0, float("nan"), 2):
            with self.subTest(diameter=diameter), self.assertRaises(ValueError):
                pilot_positions(layout, 3.5, diameter)
        narrow = calculate_layout(rectangle(width=4), (0, 0), (0, 1), 3.5)
        with self.assertRaisesRegex(ValueError, "границы"):
            pilot_positions(narrow, 3.5, 1.8)
        short = calculate_layout(rectangle(height=24.5), (0, 0), (0, 1), 3.5)
        with self.assertRaisesRegex(ValueError, "между собой"):
            pilot_positions(short, 3.5, 0.2)

    def test_boundaries(self):
        for height, count in [(999.999, 2), (1000, 3), (1599.999, 3),
                              (1600, 4), (1999.999, 4), (2000, 5), (2500, 5)]:
            with self.subTest(height=height):
                self.assertEqual(hinge_count(height), count)

    def test_both_sides_and_clearances(self):
        for side, edge, expected_x in [(-0.2, 3, 2.2), (60.2, 1, 57.8)]:
            layout = calculate_layout(rectangle(), (side, -20), (0, 4), 3.5)
            self.assertEqual(layout.edge_index, edge)
            self.assertEqual(len(layout.distances), 4)
            self.assertEqual(layout.distances[0], 10)
            self.assertEqual(layout.distances[-1], 170)
            for i, t in enumerate(layout.distances):
                x = layout.start[0] + t * layout.along[0] + 2.2 * layout.inward[0]
                self.assertAlmostEqual(x, expected_x)
                if i:
                    self.assertAlmostEqual(t - layout.distances[i - 1], 160 / 3)

    def test_rotation_translation_and_reversed_edges(self):
        angle = 0.83
        def transform(p):
            return (p[0] * math.cos(angle) - p[1] * math.sin(angle) + 17,
                    p[0] * math.sin(angle) + p[1] * math.cos(angle) - 42)
        segments = [(transform(b), transform(a)) for a, b in rectangle()]
        direction = (-math.sin(angle), math.cos(angle))
        layout = calculate_layout(segments, transform((-0.5, 0)), direction, 3.5)
        self.assertEqual(layout.edge_index, 3)
        self.assertAlmostEqual(layout.length, 180)
        self.assertAlmostEqual(layout.width, 60)
        self.assertEqual(len(layout.distances), 4)

    def test_height_follows_side_instead_of_largest_dimension(self):
        layout = calculate_layout(rectangle(180, 60), (0, 0), (0, 1), 3.5)
        self.assertEqual(layout.length, 60)
        self.assertEqual(len(layout.distances), 2)

    def test_rejects_ambiguous_or_invalid_geometry(self):
        for segments, start, direction, diameter in [
            (rectangle(), (30, 0), (0, 1), 3.5),
            (rectangle(), (0, 0), (0, 0), 3.5),
            (rectangle(height=20), (0, 0), (0, 1), 3.5),
            (rectangle(width=3), (0, 0), (0, 1), 3.5),
            (rectangle(), (0, 0), (0, 1), 5),
            (rectangle(), (0, 0), (0, 1), float("nan")),
            (rectangle()[:3], (0, 0), (0, 1), 3.5),
            ([((0, 0), (60, 0)), ((60, 0), (70, 180)),
              ((70, 180), (10, 180)), ((10, 180), (0, 0))], (0, 0), (0, 1), 3.5),
        ]:
            with self.subTest(segments=segments, start=start, diameter=diameter):
                with self.assertRaises(ValueError):
                    calculate_layout(segments, start, direction, diameter)


class WorkflowTests(unittest.TestCase):
    def test_prepared_centers_skip_geometry_reads_and_keep_builder_ownership(self):
        class Center:
            @property
            def Geometry(self):
                raise AssertionError("Координаты уже проверены; повторный COM-запрос не нужен")
        inv = Mock()
        inv.object_collection.side_effect = tuple
        points = [Center(), Center()]
        with contextlib.redirect_stdout(io.StringIO()):
            builder = TimedHoleBuilder(inv)
            prepared = prepare_centers(builder, points, "07")
            self.assertIs(builder.prepare_points(prepared), prepared)
            builder(prepared, "2 mm", "3 mm", "positive", affect_all_bodies=False)
        self.assertIs(prepared.owner, builder)
        self.assertEqual(prepared.collection, tuple(points))
        inv.unique_points.assert_not_called()
        inv.mark_as_hole_centers.assert_not_called()
        inv.object_collection.assert_called_once()
        inv.comp.Features.HoleFeatures.CreateSketchPlacementDefinition.assert_called_once_with(tuple(points))
        with self.assertRaises(ValueError):
            TimedHoleBuilder(inv).prepare_points(prepared)

    def test_cached_facade_sketch_keeps_pattern_and_marks_all_centers(self):
        inv = Mock()
        point = lambda x, y: NS(X=x, Y=y)
        sketch_point = lambda p: p if hasattr(p, "Geometry") else NS(Geometry=p)
        def line(a, b):
            return NS(StartSketchPoint=sketch_point(a), EndSketchPoint=sketch_point(b), GeometryType=5123)
        edges = [line(point(*a), point(*b)) for a, b in rectangle(height=120)]
        inv.face_edges.return_value = edges
        inv.deferred_sketch_updates.return_value = contextlib.nullcontext()
        inv.create_point2d.side_effect = point
        inv.create_point3d.side_effect = lambda x, y, z: NS(X=x, Y=y, Z=z)
        inv.model_to_sketch_point.side_effect = lambda sketch, p: p
        inv.project_entity_to_sketch.side_effect = lambda sketch, entity, **kwargs: entity
        facade, side = Mock(), Mock()
        inv.plane_geometry.side_effect = lambda face: NS(Normal=NS(X=0, Y=0, Z=1)) if face is facade else NS(Normal=NS(X=1, Y=0, Z=0))
        sketch = inv.add_sketch.return_value
        sketch.SketchLines.AddByTwoPoints.side_effect = line
        sketch.SketchPoints.Add.side_effect = lambda p, hole_center: NS(Geometry=p, HoleCenter=hole_center)
        dimensions = []
        def dimension(*args):
            result = NS(Parameter=NS(Expression=None))
            dimensions.append(result)
            return result
        sketch.DimensionConstraints.AddTwoPointDistance.side_effect = dimension
        names = Mock()
        names.parameter.return_value = "Petli_Length"
        with patch("petli.petli.plane_intersection_model_line", return_value=((0, 0, 0), (0, 1, 0))):
            _, cups, pilots, layout = build_sketch(inv, facade, side, 3.5, names, 0.2)
        self.assertEqual(len(cups), 3)
        self.assertEqual(len(pilots), 6)
        for index, cup in enumerate(cups):
            self.assertAlmostEqual(cup.Geometry.X, 2.2)
            self.assertAlmostEqual(cup.Geometry.Y, 110 - index * 50)
        for center in cups + pilots:
            self.assertTrue(center.HoleCenter)
        for i in range(3):
            a, b = pilots[2 * i:2 * i + 2]
            self.assertAlmostEqual(a.Geometry.X, 3.15)
            self.assertAlmostEqual(abs(a.Geometry.Y - b.Geometry.Y), 4.5)
        self.assertEqual([d.Parameter.Expression for d in dimensions].count("45 mm"), 3)
        self.assertEqual([d.Parameter.Expression for d in dimensions].count("9.5 mm"), 3)
        inv.add_sketch_point.assert_not_called()
        inv.add_sketch_line.assert_not_called()
        inv.add_aligned_dimension.assert_not_called()
        sketch.Solve.assert_called_once()

    def test_side_sketch_projects_cups_and_constrains_20_and_32_mm(self):
        for facade_x, expected_x in [(-1, (2, 5.2)), (61, (58, 54.8))]:
            with self.subTest(facade_x=facade_x):
                inv = Mock()
                point = lambda x, y: NS(X=x, Y=y)
                sketch_point = lambda p: p if hasattr(p, "Geometry") else NS(Geometry=p)
                def line(a, b):
                    return NS(StartSketchPoint=sketch_point(a), EndSketchPoint=sketch_point(b), GeometryType=5123)
                edges = [line(point(*a), point(*b)) for a, b in rectangle()]
                inv.face_edges.return_value = edges
                inv.deferred_sketch_updates.return_value = contextlib.nullcontext()
                inv.create_point2d.side_effect = point
                inv.create_point3d.side_effect = lambda x, y, z: NS(X=x, Y=y, Z=z)
                inv.model_to_sketch_point.side_effect = lambda sketch, p: p
                inv.project_entity_to_sketch.side_effect = lambda sketch, entity, **kwargs: entity
                sketch = inv.add_sketch.return_value
                sketch.SketchLines.AddByTwoPoints.side_effect = line
                sketch.SketchPoints.Add.side_effect = lambda p, hole_center: NS(Geometry=p, HoleCenter=hole_center)
                dimensions = []
                def dimension(*args):
                    result = NS(Parameter=NS(Expression=None))
                    dimensions.append(result)
                    return result
                sketch.DimensionConstraints.AddTwoPointDistance.side_effect = dimension
                cups = [sketch_point(point(facade_x, t)) for t in (15, 140)]
                with patch("petli.side_sketch.plane_intersection_model_line",
                           return_value=((facade_x, 0, 0), (0, 1, 0))):
                    sketch, centers = build_side_sketch(inv, Mock(), Mock(), cups, 0.2, Mock())
                self.assertEqual(len(centers), 4)
                for i, center in enumerate(centers):
                    self.assertAlmostEqual(center.Geometry.X, expected_x[i % 2])
                    self.assertAlmostEqual(center.Geometry.Y, (15, 140)[i // 2])
                for cup in cups:
                    inv.project_entity_to_sketch.assert_any_call(sketch, cup)
                self.assertEqual([d.Parameter.Expression for d in dimensions], ["20 mm", "32 mm"] * 2)
                self.assertTrue(all(p.HoleCenter for p in centers))
                sketch.Solve.assert_called_once()

    def test_drilling_direction_accounts_for_face_and_sketch_orientation(self):
        inv = Mock()
        inv.create_point2d.side_effect = lambda x, y: (x, y)
        inv.plane_geometry.return_value.Normal = NS(X=0, Y=0, Z=1)
        for reversed_face in (False, True):
            for flip in (1, -1):
                sketch = Mock()
                sketch.SketchToModelSpace.side_effect = lambda p: NS(X=p[0], Y=flip * p[1], Z=0)
                expected = "negative" if (flip == 1) != reversed_face else "positive"
                self.assertEqual(inward_direction(inv, sketch, NS(IsParamReversed=reversed_face)), expected)

    def test_scopes_holes_to_facade_and_rolls_back_failure(self):
        for fail in (None, "cup", "pilot", "side", "side_sketch"):
            with self.subTest(fail=fail), contextlib.ExitStack() as stack:
                stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
                inv = Mock()
                inv.active_document.DocumentType = 12290
                inv.screen_updates_suspended.return_value = contextlib.nullcontext()
                facade, side = Mock(), Mock()
                facade.Parent.Name = "Facade"
                side.Parent.Name = "Side"
                stack.enter_context(patch("petli.petli.selected_inventor_context", return_value=(inv, [facade, side])))
                params = stack.enter_context(patch("petli.petli.ParameterSession")).return_value
                params.missing_parameters.return_value = []
                params.parameter_value.side_effect = [3.5, 1.3, 0.2, 0.3]
                sketch, points = Mock(), [Mock(), Mock()]
                pilot_points = [Mock() for _ in range(4)]
                builder_sketch = stack.enter_context(patch("petli.petli.build_sketch", return_value=(sketch, points, pilot_points, NS(length=90))))
                side_sketch, side_points = Mock(), [Mock() for _ in range(4)]
                build_side = stack.enter_context(patch("petli.petli.build_side_sketch", return_value=(side_sketch, side_points)))
                if fail == "side_sketch":
                    build_side.side_effect = RuntimeError("hole failed")
                stack.enter_context(patch("petli.petli.inward_direction", side_effect=["negative", "positive"]))
                builder = stack.enter_context(patch("petli.petli.TimedHoleBuilder")).return_value
                prep = stack.enter_context(patch("petli.petli.prepare_centers", side_effect=lambda builder, points, label: points))
                if fail:
                    if fail != "side_sketch":
                        builder.side_effect = [Mock()] * {"cup": 0, "pilot": 1, "side": 2}[fail] + [RuntimeError("hole failed")]
                    with self.assertRaisesRegex(RuntimeError, "hole failed"):
                        main()
                    inv.app.TransactionManager.StartTransaction.return_value.Abort.assert_called_once()
                    inv.app.TransactionManager.StartTransaction.return_value.End.assert_not_called()
                else:
                    main()
                    inv.app.TransactionManager.StartTransaction.return_value.End.assert_called_once()
                    inv.app.TransactionManager.StartTransaction.return_value.Abort.assert_not_called()
                self.assertIs(builder_sketch.call_args.args[1], facade)
                self.assertIs(builder_sketch.call_args.args[2], side)
                if fail == "side_sketch":
                    builder.assert_not_called()
                    prep.assert_not_called()
                    continue
                self.assertEqual(prep.call_args_list, [call(builder, points, "Petli_Holes"),
                                                       call(builder, pilot_points, "Petli_Nakolki"),
                                                       call(builder, side_points, "Petli_Side_Nakolki")])
                expected = [call(points, DIAMETER, DEPTH, "positive", name="Petli_Holes",
                                 flat_bottom=True, affect_all_bodies=False, affected_body="Facade")]
                if fail != "cup":
                    expected.append(call(pilot_points, PILOT_DIAMETER, PILOT_DEPTH, "positive", name="Petli_Nakolki",
                                         flat_bottom=True, affect_all_bodies=False, affected_body="Facade"))
                if fail not in ("cup", "pilot"):
                    expected.append(call(side_points, PILOT_DIAMETER, PILOT_DEPTH, "negative", name="Petli_Side_Nakolki",
                                         flat_bottom=True, affect_all_bodies=False, affected_body="Side"))
                self.assertEqual(builder.call_args_list, expected)
                if not fail:
                    inv.set_sketch_visible.assert_any_call(side_sketch, False)


if __name__ == "__main__":
    unittest.main()
