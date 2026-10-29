import contextlib
import io
import math
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

from common.create_sketches import create_sketches_for_faces, project_new_face_lines
from common.drilling_runtime import DrillingNames
from common.reference_edge import shared_intersection_edge, snapshot_lines, end_lines_for_reference, FaceEdgeCache
from stiajka.offset_sketch import create_offset_drilling_sketch
from inventor_service.part.component_definition.sketches.drilling import PartDrillingSketchMethods


def point(x, y, z=0):
    return NS(X=x, Y=y, Z=z)


def edge(a, b):
    return NS(StartVertex=NS(Point=a), StopVertex=NS(Point=b), GeometryType=5123)


def line(a, b):
    return NS(StartSketchPoint=NS(Geometry=a), EndSketchPoint=NS(Geometry=b))


class ReferenceEdgeTests(unittest.TestCase):
    def test_source_edges_are_not_read_again_during_projection(self):
        locked = False

        class SourceEdge:
            def __init__(self, a, b):
                self.a, self.b = a, b

            @property
            def GeometryType(self):
                if locked:
                    raise AssertionError("Curve type was already read")
                return 5123

            @property
            def StartVertex(self):
                if locked:
                    raise AssertionError("Start point was already read")
                return NS(Point=self.a)

            @property
            def StopVertex(self):
                if locked:
                    raise AssertionError("End point was already read")
                return NS(Point=self.b)

        first, second = object(), object()
        common = SourceEdge(point(0, 0), point(12, 0))
        first_edges = [common, SourceEdge(point(12, 0), point(12, 1.6)),
                       SourceEdge(point(12, 1.6), point(0, 1.6)), SourceEdge(point(0, 1.6), point(0, 0))]
        second_edges = [common, SourceEdge(point(12, 0), point(12, 0, 30)),
                        SourceEdge(point(12, 0, 30), point(0, 0, 30)), SourceEdge(point(0, 0, 30), point(0, 0))]
        inventor = Mock()
        inventor.face_edges.side_effect = lambda face: first_edges if face is first else second_edges
        inventor.project_entity_to_sketch.side_effect = lambda *args, **kwargs: object()
        cache = FaceEdgeCache(inventor)
        selected = shared_intersection_edge(inventor, first, second, ((0, 0, 0), (1, 0, 0)),
                                            edge_cache=cache)
        locked = True
        with contextlib.redirect_stdout(io.StringIO()):
            for face in (first, second):
                lines, control = project_new_face_lines(inventor, object(), face, selected, edge_cache=cache)
                self.assertEqual(len(lines), 4)
                self.assertIs(control, lines[0])
        self.assertEqual(inventor.face_edges.call_count, 2)
        self.assertEqual(inventor.project_entity_to_sketch.call_count, 8)

    def test_edge_selection_reuses_numeric_coordinates_without_repeated_com_reads(self):
        reads = []

        class CountedPoint:
            def __init__(self, x, y):
                self.xy = (x, y)

            @property
            def X(self):
                reads.append("X")
                return self.xy[0]

            @property
            def Y(self):
                reads.append("Y")
                return self.xy[1]

        vertices = [CountedPoint(0, 0), CountedPoint(12, 0),
                    CountedPoint(12, 1.6), CountedPoint(0, 1.6)]
        lines = [line(vertices[i], vertices[(i + 1) % 4]) for i in range(4)]
        geometries = snapshot_lines(lines)
        self.assertEqual(len(reads), 16)
        for _ in range(3):
            ends = end_lines_for_reference(lines[0], lines, geometries=geometries)
            self.assertIs(ends[0], lines[3])
            self.assertIs(ends[1], lines[1])
            self.assertEqual(geometries[id(lines[0])].length_squared, 144)
        self.assertEqual(len(reads), 16)

    def test_both_control_dimensions_follow_shared_edge_instead_of_face_extents(self):
        self.check_pair(cached=False)

    def test_cached_operations_preserve_dimensions_and_hole_centers(self):
        self.check_pair(cached=True)

    def test_cached_inside_point_selects_opposite_side_of_shared_edge(self):
        self.check_pair(cached=True, second_sign=-1)

    def check_pair(self, cached, second_sign=1):
        # Первая грань 120x160 мм, вторая шириной 200 мм.
        # Общее ребро 120 мм занимает только часть нижнего контура второй грани.
        first = NS(PointOnFace=point(10, 8))
        second = NS(PointOnFace=point(10, 0, 15 * second_sign))
        a, b = point(4, 0), point(16, 0)
        common = edge(a, b)
        first_edges = [common, edge(b, point(16, 16)),
                       edge(point(16, 16), point(4, 16)), edge(point(4, 16), a)]
        second_vertices = [point(0, 0), a, b, point(20, 0),
                           point(20, 0, 30 * second_sign), point(0, 0, 30 * second_sign)]
        second_edges = [edge(p, q) for p, q in zip(
            second_vertices, second_vertices[1:] + second_vertices[:1],
        )]
        inventor = Mock()
        inventor.face_edges.side_effect = lambda face: first_edges if face is first else second_edges
        intersection = ((0, 0, 0), (1, 0, 0))
        edge_cache = FaceEdgeCache(inventor)
        selected = shared_intersection_edge(inventor, first, second, intersection, edge_cache=edge_cache)
        self.assertIs(selected, common)
        inventor.parameters.Item.side_effect = KeyError("missing")
        inventor.comp.Sketches.Item.side_effect = KeyError("missing")
        names = DrillingNames(inventor)
        inventor.group_faces_by_plane.return_value = [[first]]
        sketches = []

        def new_sketch(face):
            sketch = NS(Name="new", face=face, SketchLines=Mock(), SketchPoints=Mock(),
                        GeometricConstraints=Mock(), DimensionConstraints=Mock())
            sketch.SketchLines.AddByTwoPoints.side_effect = line
            sketch.SketchPoints.Add.side_effect = lambda p, hole_center: NS(Geometry=p)
            sketch.DimensionConstraints.AddTwoPointDistance.side_effect = (
                lambda a, b, aligned, text, driven: dimension(sketch, a, b, text, driven)
            )
            sketches.append(sketch)
            return sketch

        inventor.add_sketch.side_effect = new_sketch
        inventor.deferred_sketch_updates.side_effect = lambda sketch: contextlib.nullcontext()
        inventor.create_point2d.side_effect = point
        inventor.create_point3d.side_effect = point

        def project(sketch, p):
            return point(p.X, p.Y if sketch.face is first else p.Z)

        inventor.project_entity_to_sketch.side_effect = lambda sketch, e, **kw: line(
            project(sketch, e.StartVertex.Point), project(sketch, e.StopVertex.Point),
        )
        inventor.model_to_sketch_point.side_effect = project
        inventor.face_vertex_points_in_sketch.side_effect = lambda face, sketch: [
            project(sketch, e.StartVertex.Point) for e in inventor.face_edges(face)
        ]
        inventor.add_sketch_line.side_effect = lambda sketch, a, b, **kw: line(a, b)
        inventor.add_sketch_point.side_effect = lambda sketch, p: NS(Geometry=p)
        inventor.line_length_squared.side_effect = lambda line: (
            (line.EndSketchPoint.Geometry.X - line.StartSketchPoint.Geometry.X) ** 2
            + (line.EndSketchPoint.Geometry.Y - line.StartSketchPoint.Geometry.Y) ** 2
        )
        inventor.line_midpoint.side_effect = lambda line: point(
            (line.StartSketchPoint.Geometry.X + line.EndSketchPoint.Geometry.X) / 2,
            (line.StartSketchPoint.Geometry.Y + line.EndSketchPoint.Geometry.Y) / 2,
        )
        inventor.distance_2d.side_effect = lambda a, b: math.hypot(b.X - a.X, b.Y - a.Y)
        inventor.create_construction_axes.side_effect = lambda *args: (
            PartDrillingSketchMethods.create_construction_axes(inventor, *args)
        )
        dimensions = []

        def dimension(sketch, a, b, text, driven=False):
            result = NS(Parameter=NS(), value=math.hypot(
                b.Geometry.X - a.Geometry.X, b.Geometry.Y - a.Geometry.Y,
            ), driven=driven, sketch=sketch)
            dimensions.append(result)
            return result

        inventor.add_aligned_dimension.side_effect = dimension
        jobs = []
        with contextlib.redirect_stdout(io.StringIO()):
            create_sketches_for_faces(
                inventor, None, [first], "DrillingSketch", "edge", "test", "test",
                reuse_existing=False, point_jobs=jobs, edge_offset_value=2,
                runtime_names=names, direct_projection=True, reference_edges={id(first): selected},
                use_cached_operations=cached,
                edge_cache=edge_cache,
            )
            second_sketch, second_points = create_offset_drilling_sketch(
                inventor, second, first, 2, "offset", "edge", 3.4, 2,
                intersection_line=intersection, runtime_names=names, control_edge=selected,
                use_cached_operations=cached,
                edge_cache=edge_cache,
            )
        controls = [d for d in dimensions if d.driven]
        self.assertEqual([d.value for d in controls], [12, 12])
        self.assertNotEqual(controls[0].Parameter.Name, controls[1].Parameter.Name)
        # Совпадают и продольные координаты центров, хотя габариты граней различаются.
        self.assertEqual([round(p.Geometry.X, 6) for p in jobs[0]["outer_points"]], [6.8, 13.2])
        self.assertEqual([round(p.Geometry.X, 6) for p in second_points], [6.8, 13.2])
        self.assertEqual([round(p.Geometry.Y, 6) for p in second_points], [3.4 * second_sign] * 2)
        inventor.sketch_lines.assert_not_called()
        inventor.line_length_squared.assert_not_called()
        inventor.add_side_plane_reference_line.assert_not_called()
        if cached:
            self.assertEqual(inventor.face_edges.call_count, 2)
            inventor.create_construction_axes.assert_not_called()
            inventor.add_sketch_point.assert_not_called()
            inventor.add_aligned_dimension.assert_not_called()
            inventor.face_vertex_points_in_sketch.assert_not_called()
            self.assertEqual(sketches[0].SketchPoints.Add.call_count, 3)
            self.assertEqual(sketches[1].SketchPoints.Add.call_count, 2)
            self.assertEqual(sketches[0].DimensionConstraints.AddTwoPointDistance.call_count, 2)
            self.assertEqual(sketches[1].DimensionConstraints.AddTwoPointDistance.call_count, 3)

    def test_shared_edge_accepts_reversed_endpoints(self):
        inventor = Mock()
        first, second = object(), object()
        original = edge(point(0, 0), point(12, 0))
        reversed_edge = edge(point(12, 0), point(0, 0))
        inventor.face_edges.side_effect = lambda face: [original] if face is first else [reversed_edge]
        self.assertIs(shared_intersection_edge(
            inventor, first, second, ((0, 0, 0), (1, 0, 0)),
        ), original)

    def test_parallel_edges_at_other_locations_do_not_count_as_shared(self):
        inventor = Mock()
        first, second = object(), object()
        inventor.face_edges.side_effect = lambda face: [
            edge(point(0, 1), point(12, 1)) if face is first else edge(point(0, 0), point(12, 0))
        ]
        with self.assertRaises(ValueError):
            shared_intersection_edge(inventor, first, second, ((0, 0, 0), (1, 0, 0)))


if __name__ == "__main__":
    unittest.main()
