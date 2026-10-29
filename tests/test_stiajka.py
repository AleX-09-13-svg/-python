import contextlib
import importlib
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from common.create_sketches import drilling_point_distance, create_sketches_for_faces
from common.drilling_runtime import DrillingNames, NameAllocator
from stiajka.stiajka import create_hole_batch, create_stiajka_features
from stiajka.offset_sketch import create_offset_drilling_sketch


workflow = importlib.import_module("05_stiajka")


class StiajkaTests(unittest.TestCase):
    def setUp(self):
        self.parameter_cache = Mock()
        self.parameter_cache.parameter_value.return_value = 3.4
        self.parameter_cache.ensure_keep_parameter.return_value = False
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def test_new_points_are_forwarded_without_scanning_sketch(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        points = [object() for _ in range(4)]
        jobs = [{"outer_points": points[:2], "inner_points": points[2:]}]
        created = create_stiajka_features(
            inventor, sketches=[object()], colored_faces=[], point_jobs=jobs,
            strict=True, update_document=False,
        )
        self.assertEqual(created, 4)
        self.assertEqual(inventor.add_holes.call_count, 4)
        self.assertEqual(inventor.add_holes.call_args_list[0].args[0], points[:2])
        self.assertEqual(inventor.add_holes.call_args_list[2].args[0], points[2:])
        inventor.sketch_points.assert_not_called()
        inventor.sketches_by_prefix.assert_not_called()

    def test_failed_holes_raise_instead_of_reporting_success(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        inventor.add_holes.side_effect = RuntimeError("COM hole failed")
        with self.assertRaisesRegex(RuntimeError, "COM hole failed"):
            create_stiajka_features(
                inventor, sketches=[], colored_faces=[], strict=True,
                point_jobs=[{"outer_points": [object(), object()],
                             "inner_points": [object(), object()]}],
            )
        inventor.update.assert_not_called()

    def test_empty_explicit_sketch_list_does_not_use_old_sketches(self):
        inventor = Mock()
        with self.assertRaises(RuntimeError):
            create_stiajka_features(inventor, sketches=[], colored_faces=[], strict=True)
        inventor.sketches_by_prefix.assert_not_called()

    def test_sketch_builder_collects_exact_created_points(self):
        inventor = Mock()
        face, sketch = object(), SimpleNamespace(Name="new")
        points = tuple(object() for _ in range(6))
        inventor.group_faces_by_plane.return_value = [[face]]
        inventor.add_sketch.return_value = sketch
        inventor.unique_sketch_name.return_value = "new"
        inventor.sketch_has_geometry_for_face.return_value = False
        inventor.sketch_lines.return_value = []
        inventor.deferred_sketch_updates.return_value = contextlib.nullcontext()
        jobs = []
        with patch("common.create_sketches._create_drilling_sketch_fixed", return_value=points):
            create_sketches_for_faces(
                inventor, None, [face], "DrillingSketch", "edge", "test", "test",
                reuse_existing=False, point_jobs=jobs,
            )
        self.assertEqual(jobs[0]["outer_points"], list(points[:2]))
        self.assertEqual(jobs[0]["inner_points"], list(points[2:4]))
        self.assertIs(jobs[0]["sketch"], sketch)

    def test_spacing_allows_64_mm_and_rejects_smaller_layouts(self):
        for length, offset in [(8, 3), (20, -1)]:
            with self.subTest(length=length, offset=offset), self.assertRaises(ValueError):
                drilling_point_distance(length, offset)
        self.assertAlmostEqual(drilling_point_distance(40, 5), 28.8)
        self.assertAlmostEqual(drilling_point_distance(12, 2), 6.4)
        self.assertAlmostEqual(drilling_point_distance(12.8, 3.2), 6.4)

    def test_120_mm_face_creates_two_outer_and_one_dowel_center(self):
        self.check_first_sketch()

    def test_direct_first_sketch_preserves_centers_without_geometry_rescan(self):
        self.check_first_sketch(direct=True)

    def check_first_sketch(self, direct=False):
        inventor = Mock()
        face = object()
        sketch = SimpleNamespace(Name="new")
        center = SimpleNamespace(X=6.0, Y=0.8)
        axis = SimpleNamespace(StartSketchPoint=object(), EndSketchPoint=object())
        inventor.group_faces_by_plane.return_value = [[face]]
        inventor.add_sketch.return_value = sketch
        inventor.sketch_has_geometry_for_face.return_value = False
        inventor.sketch_lines.return_value = []
        inventor.sketch_lines_for_face.return_value = [object() for _ in range(4)]
        inventor.line_length_squared.side_effect = lambda line: 2.56
        inventor.create_construction_axes.return_value = (
            axis, object(), center, 12.0, 1.0, 0.0, 0.0, 1.0,
        )
        inventor.parameter_value.return_value = 2.0
        inventor.create_point2d.side_effect = lambda x, y: SimpleNamespace(X=x, Y=y)
        inventor.add_sketch_point.side_effect = lambda sketch, geo: SimpleNamespace(Geometry=geo)
        inventor.add_aligned_dimension.side_effect = lambda *args: SimpleNamespace(Parameter=SimpleNamespace())
        inventor.unique_parameter_name.side_effect = lambda name, params: name
        inventor.deferred_sketch_updates.return_value = contextlib.nullcontext()
        inventor.unique_points.side_effect = lambda points: list({id(p): p for p in points}.values())
        names = None
        if direct:
            inventor.face_edges.return_value = [SimpleNamespace(GeometryType=5123) for _ in range(4)]
            inventor.project_entity_to_sketch.side_effect = [object() for _ in range(4)]
            inventor.sketch_has_geometry_for_face.side_effect = AssertionError("geometry rescan")
            inventor.sketch_lines_for_face.side_effect = AssertionError("line rescan")
            inventor.parameters.Item.side_effect = KeyError("not found")
            inventor.comp.Sketches.Item.side_effect = KeyError("not found")
            names = DrillingNames(inventor)
        jobs = []
        sketches = create_sketches_for_faces(
            inventor, None, [face], "DrillingSketch", "edge", "test", "test",
            reuse_existing=False, point_jobs=jobs,
            edge_offset_value=2.0,
            direct_projection=direct, runtime_names=names,
        )
        self.assertEqual(inventor.add_sketch_point.call_count, 3)
        inventor.parameter_value.assert_not_called()
        self.assertEqual(inventor.add_aligned_dimension.call_count, 2)
        self.assertEqual(len(jobs[0]["inner_points"]), 1)
        self.assertAlmostEqual(jobs[0]["outer_points"][0].Geometry.X, 2.8)
        self.assertAlmostEqual(jobs[0]["outer_points"][1].Geometry.X, 9.2)
        self.assertAlmostEqual(jobs[0]["inner_points"][0].Geometry.X, 6.0)
        create_stiajka_features(
            inventor, sketches=sketches, colored_faces=[face], point_jobs=jobs,
            strict=True, update_document=False,
        )
        self.assertEqual([len(call.args[0]) for call in inventor.add_holes.call_args_list], [2, 2, 1, 1])
        if direct:
            self.assertEqual(inventor.project_entity_to_sketch.call_count, 4)
            inventor.project_face_edges.assert_not_called()
            inventor.sketch_line_count.assert_not_called()
            inventor.unique_sketch_name.assert_not_called()
            inventor.unique_parameter_name.assert_not_called()

    def test_name_allocator_preserves_existing_names_and_reserves_new_ones(self):
        existing = {"DrillingSketch_1", "DrillingSketch_1_1"}
        collection = Mock()

        def item(name):
            if name in existing:
                return object()
            raise KeyError(name)

        collection.Item.side_effect = item
        allocate = NameAllocator(collection).take
        self.assertEqual(allocate("DrillingSketch_1"), "DrillingSketch_1_2")
        self.assertEqual(allocate("DrillingSketch_1"), "DrillingSketch_1_3")
        self.assertEqual(allocate("DrillingSketch_1_2"), "DrillingSketch_1_2_1")
        self.assertEqual([call.args[0] for call in collection.Item.call_args_list], [
            "DrillingSketch_1", "DrillingSketch_1_1", "DrillingSketch_1_2",
            "DrillingSketch_1_3", "DrillingSketch_1_2_1",
        ])

    def test_two_faces_must_belong_to_same_body(self):
        inventor = Mock()
        a, b = SimpleNamespace(Name="A"), SimpleNamespace(Name="B")
        faces = [SimpleNamespace(Parent=a), SimpleNamespace(Parent=b)]
        self.assertIsNone(workflow.selected_face_pairs(inventor, faces))

    def test_second_sketch_uses_construction_projection_edges(self):
        self.check_second_sketch(12.0)

    def test_long_second_sketch_uses_two_points_and_cached_intersection(self):
        self.check_second_sketch(40.0, cached=True)

    def check_second_sketch(self, length, cached=False):
        inventor = Mock()
        face, reference_face = object(), object()
        sketch = SimpleNamespace(Name="second")

        def point(x, y, z=0):
            return SimpleNamespace(X=x, Y=y, Z=z)

        def line(a, b):
            return SimpleNamespace(
                StartSketchPoint=SimpleNamespace(Geometry=a),
                EndSketchPoint=SimpleNamespace(Geometry=b), Construction=True,
            )

        vertices = [point(0, 0), point(length, 0), point(length, 30), point(0, 30)]
        edges = [line(vertices[i], vertices[(i + 1) % 4]) for i in range(4)]
        inventor.plane_geometry.side_effect = lambda f: SimpleNamespace(
            Normal=point(0, 0, 1) if f is face else point(0, 1, 0), RootPoint=point(0, 0),
        )
        inventor.add_sketch.return_value = sketch
        inventor.unique_sketch_name.return_value = "second"
        inventor.deferred_sketch_updates.return_value = contextlib.nullcontext()
        inventor.create_point3d.side_effect = point
        inventor.create_point2d.side_effect = point
        inventor.model_to_sketch_point.side_effect = lambda sketch, p: p
        inventor.distance_2d.return_value = 1.0
        inventor.face_vertex_points_in_sketch.return_value = vertices
        inventor.sketch_lines.side_effect = lambda sketch, construction=None: edges if construction is None else []
        inventor.add_sketch_line.side_effect = lambda sketch, a, b, **kw: line(a, b)
        inventor.add_sketch_point.side_effect = lambda sketch, p: SimpleNamespace(Geometry=p)
        dimensions = []

        def dimension(*args):
            result = SimpleNamespace(Parameter=SimpleNamespace())
            dimensions.append(result)
            return result

        inventor.add_aligned_dimension.side_effect = dimension
        inventor.unique_parameter_name.side_effect = lambda name, params: name
        result = create_offset_drilling_sketch(
            inventor, face, reference_face, 2, "offset", "edge", 3.4, 2.0,
            intersection_line=((0, 0, 0), (1, 0, 0)) if cached else None,
        )
        self.assertIs(result[0], sketch)
        self.assertEqual(len(result[1]), 2)
        outer = drilling_point_distance(length, 2.0) / 2
        self.assertAlmostEqual(result[1][0].Geometry.X, length / 2 - outer)
        self.assertAlmostEqual(result[1][1].Geometry.X, length / 2 + outer)
        self.assertAlmostEqual(result[1][0].Geometry.Y, 3.4)
        self.assertEqual(len(dimensions), 3)
        self.assertEqual(dimensions[-1].Parameter.Expression, "offset")
        self.assertEqual(dimensions[1].Parameter.Expression,
                         "floor((Long_edge_2 - edge * 2) / 32 mm) * 32 mm")
        self.assertEqual(inventor.add_sketch_point.call_count, 2)
        inventor.add_symmetry_constraint.assert_called_once()
        self.assertEqual(inventor.add_sketch_line.call_count, 2)
        offset_line = inventor.add_midpoint_constraint.call_args.args[1]
        symmetry_line = inventor.add_symmetry_constraint.call_args.args[3]
        self.assertIs(offset_line, symmetry_line.EndSketchPoint)
        self.assertEqual(inventor.add_perpendicular_constraint.call_count, 1)
        if cached:
            inventor.plane_geometry.assert_not_called()
        inventor.sketch_lines.assert_called_once_with(sketch)

    def test_failed_second_sketch_stops_before_any_holes(self):
        inventor = Mock()
        screen = Mock()
        screen.__enter__ = Mock()
        screen.__exit__ = Mock(return_value=False)
        inventor.screen_updates_suspended.return_value = screen
        faces = [object(), object()]
        inventor.parameter_value.return_value = 3.4
        job = {"outer_points": [object(), object()], "inner_points": [object(), object()]}

        def build(*args, **kwargs):
            kwargs["point_jobs"].append(job)
            return ["new sketch"]

        with patch.object(workflow, "selected_inventor_context", return_value=(inventor, faces)), \
             patch.object(workflow, "ParameterSession", return_value=self.parameter_cache), \
             patch.object(workflow, "selected_face_pairs", return_value=[faces]), \
             patch.object(workflow, "shared_intersection_edge", return_value=object()), \
             patch.object(workflow, "plane_intersection_model_line", return_value=((0, 0, 0), (1, 0, 0))), \
             patch.object(workflow, "choose_frame_edge_offset_parameter", return_value="edge"), \
             patch.object(workflow.create_sketches, "ensure_parameters", return_value=True), \
             patch.object(workflow.create_sketches, "create_sketches_for_faces", side_effect=build), \
             patch.object(workflow.stiajka_module, "create_stiajka_features", return_value=4) as holes, \
             patch.object(workflow, "create_offset_drilling_sketch", return_value=None):
            with self.assertRaises(RuntimeError):
                workflow.main()
        holes.assert_not_called()
        inventor.update.assert_not_called()
        screen.__exit__.assert_called_once()
        self.assertIs(screen.__exit__.call_args.args[0], RuntimeError)

    def test_all_second_sketches_are_built_before_holes_invalidate_faces(self):
        inventor = Mock()
        inventor.screen_updates_suspended.side_effect = contextlib.nullcontext
        faces = [object() for _ in range(4)]
        pairs = [faces[:2], faces[2:]]
        inventor.parameter_value.return_value = 3.4
        state = {"faces_valid": True, "second_sketches": 0}
        jobs = [{"outer_points": [object(), object()], "inner_points": [object()],
                 "colored_face": pair[0]} for pair in pairs]
        targets = {id(pair[0]): {"owner_body": f"owner {i}", "neighbor_body": f"neighbor {i}"}
                   for i, pair in enumerate(pairs)}
        second_results = [(object(), [object(), object()]) for _ in pairs]

        def build_first(*args, **kwargs):
            kwargs["point_jobs"].extend(jobs)
            state["names"] = kwargs["runtime_names"]
            self.assertTrue(kwargs["direct_projection"])
            self.assertTrue(kwargs["use_cached_operations"])
            return ["first 1", "first 2"]

        def build_second(*args, **kwargs):
            # Имитировать Item.Geometry / Item.Plane после перестроения тела.
            if not state["faces_valid"]:
                raise AttributeError("Item.Plane")
            index = state["second_sketches"]
            self.assertEqual(kwargs["intersection_line"], ((0, 0, 0), (1, 0, 0)))
            self.assertIs(kwargs["runtime_names"], state["names"])
            self.assertTrue(kwargs["use_cached_operations"])
            state["second_sketches"] += 1
            return second_results[index]

        def first_holes(*args, **kwargs):
            self.assertEqual(state["second_sketches"], 2)
            self.assertEqual(kwargs["point_jobs"], jobs)
            self.assertTrue(kwargs["strict"])
            state["hole_creator"] = kwargs["hole_creator"]
            state["faces_valid"] = False
            return 4

        with patch.object(workflow, "selected_inventor_context", return_value=(inventor, faces)), \
             patch.object(workflow, "ParameterSession", return_value=self.parameter_cache), \
             patch.object(workflow, "selected_face_pairs", return_value=pairs), \
             patch.object(workflow, "shared_intersection_edge", return_value=object()), \
             patch.object(workflow, "body_targets", return_value=targets), \
             patch.object(workflow, "plane_intersection_model_line", return_value=((0, 0, 0), (1, 0, 0))), \
             patch.object(workflow, "choose_frame_edge_offset_parameter", return_value="edge"), \
             patch.object(workflow.create_sketches, "ensure_parameters", return_value=True), \
             patch.object(workflow.create_sketches, "create_sketches_for_faces", side_effect=build_first), \
             patch.object(workflow, "create_offset_drilling_sketch", side_effect=build_second), \
             patch.object(workflow.stiajka_module, "create_stiajka_features", side_effect=first_holes), \
             patch.object(workflow.stiajka_module, "create_second_face_stiajka_holes", return_value=1) as holes:
            workflow.main()
        self.assertEqual(holes.call_count, 2)
        for call, result in zip(holes.call_args_list, second_results):
            self.assertIs(call.args[1], result[1])
            self.assertIs(call.kwargs["hole_creator"], state["hole_creator"])
        self.assertEqual([call.args[2]["affected_body"] for call in holes.call_args_list],
                         ["owner 0", "owner 1"])
        inventor.update.assert_called_once()

    def test_one_job_does_not_retry_identical_failed_hole_operation(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        inventor.add_holes.side_effect = RuntimeError("single job failed")
        with self.assertRaisesRegex(RuntimeError, "single job failed"):
            create_stiajka_features(
                inventor, sketches=[], colored_faces=[], strict=True,
                point_jobs=[{"outer_points": [object(), object()], "inner_points": [object()]}],
            )
        inventor.add_holes.assert_called_once()

    def test_multiple_jobs_still_fall_back_to_separate_holes(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        inventor.add_holes.side_effect = [RuntimeError("batch failed"), object(), object()]
        jobs = [{"outer_points": [object(), object()]} for _ in range(2)]
        created = create_hole_batch(
            inventor, jobs, "outer_points", "Otv_stijki_v_torec",
            "8 mm", "34 mm", "test", "test", strict=True,
        )
        self.assertEqual(created, 2)
        self.assertEqual(inventor.add_holes.call_count, 3)
        self.assertIs(inventor.add_holes.call_args_list[1].args[0], jobs[0]["outer_points"])
        self.assertIs(inventor.add_holes.call_args_list[2].args[0], jobs[1]["outer_points"])

    def test_launcher_logs_exception_and_returns_failure(self):
        log = io.StringIO()
        with patch("pathlib.Path.open", return_value=contextlib.nullcontext(log)), \
             contextlib.redirect_stderr(io.StringIO()), \
             patch.object(workflow, "main", side_effect=RuntimeError("hole failure")):
            self.assertEqual(workflow.run(), 1)
        self.assertIn("RuntimeError: hole failure", log.getvalue())
        self.assertIn("Traceback", log.getvalue())


if __name__ == "__main__":
    unittest.main()
