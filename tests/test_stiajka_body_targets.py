import contextlib
import io
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock

from stiajka.body_targets import body_targets
from stiajka.hole_builder import AffectedBodyError, TimedHoleBuilder
from stiajka.stiajka import create_hole_batch, create_stiajka_features


def point(x, y, z=0):
    return NS(X=x, Y=y, Z=z)


def collection(items):
    return NS(Count=len(items), Item=lambda index: items[index - 1])


def body(name, matches=True):
    face = Mock()
    face.matches = matches
    face.GetClosestPointTo.side_effect = lambda p: p
    result = NS(Name=name, IsSolid=True, Faces=collection([face]), test_face=face,
                LocateUsingPoint=Mock(return_value=face),
                RangeBox=NS(MinPoint=point(0, 0, -10), MaxPoint=point(10, 10, 0)))
    face.SurfaceBody = result
    return result


class BodyTargetTests(unittest.TestCase):
    def setUp(self):
        self.inventor = Mock()
        self.owner = body("owner")
        self.first = NS(SurfaceBody=self.owner)
        sketch = Mock()
        sketch.SketchToModelSpace.side_effect = lambda p: p
        self.jobs = [{"colored_face": self.first, "sketch": sketch,
                      "outer_points": [NS(Geometry=point(2, 2)), NS(Geometry=point(8, 2))],
                      "inner_points": [NS(Geometry=point(5, 2))]}]
        self.inventor.same_plane_entity.side_effect = lambda first, candidate, **kw: candidate.matches
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def targets(self, *others):
        self.inventor.comp.FindUsingPoint.return_value = collection(
            [self.first, *(other.test_face for other in others)],
        )
        return body_targets(self.inventor, [(self.first, object())], self.jobs)

    def test_chooses_neighbor_and_excludes_owner_and_different_plane(self):
        neighbor, other = body("neighbor"), body("other", matches=False)
        self.assertEqual(self.targets(other, neighbor)[id(self.first)],
                         {"owner_body": "owner", "neighbor_body": "neighbor"})
        other.Faces.Item(1).GetClosestPointTo.assert_not_called()

    def test_same_plane_without_coverage_of_all_centers_is_rejected(self):
        neighbor = body("neighbor")
        neighbor.Faces.Item(1).GetClosestPointTo.side_effect = (
            lambda p: point(7, p.Y, p.Z) if p.X == 8 else p
        )
        with self.assertRaisesRegex(ValueError, "Найдено: 0"):
            self.targets(neighbor)

    def test_multiple_neighbors_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Найдено: 2"):
            self.targets(body("left"), body("right"))

    def test_surface_body_is_not_selected_as_neighbor(self):
        surface = body("surface")
        surface.IsSolid = False
        with self.assertRaises(ValueError):
            self.targets(surface)

    def test_locates_one_face_without_enumerating_body_faces(self):
        neighbor = body("neighbor")

        class NoEnumeration:
            @property
            def Count(self):
                raise AssertionError("Full face enumeration must not run")

        neighbor.Faces = NoEnumeration()
        self.targets(neighbor)
        query = self.inventor.comp.FindUsingPoint.call_args
        self.assertIs(query.args[0], self.jobs[0]["outer_points"][0].Geometry)
        self.assertEqual(query.args[1], (15877,))
        self.assertEqual(query.args[2:], (1e-5, False))
        self.inventor.comp.FindUsingPoint.assert_called_once()
        neighbor.LocateUsingPoint.assert_not_called()
        self.owner.LocateUsingPoint.assert_not_called()

    def test_locate_returns_none_then_finds_face_at_next_center(self):
        neighbor = body("neighbor")
        face = neighbor.Faces.Item(1)
        self.inventor.comp.FindUsingPoint.side_effect = [collection([]), collection([face])]
        self.assertEqual(self.targets(neighbor)[id(self.first)]["neighbor_body"], "neighbor")
        self.assertEqual(self.inventor.comp.FindUsingPoint.call_count, 2)

    def test_empty_global_search_does_not_select_unverified_body(self):
        neighbor = body("neighbor")
        neighbor.RangeBox = NS(MinPoint=point(20, 20, -10), MaxPoint=point(30, 30, 0))
        self.inventor.comp.FindUsingPoint.side_effect = lambda *args: collection([])
        with self.assertRaises(ValueError):
            self.targets(neighbor)
        neighbor.LocateUsingPoint.assert_not_called()

    def test_point_lookup_error_does_not_pick_an_unverified_neighbor(self):
        neighbor = body("neighbor")
        self.inventor.comp.FindUsingPoint.side_effect = RuntimeError("no entity at point")
        with self.assertRaisesRegex(ValueError, "Найдено: 0"):
            self.targets(neighbor)

    def test_body_bounds_are_not_read_for_multiple_face_pairs(self):
        original = body("neighbor")

        class CachedBoundsBody:
            Name = original.Name
            IsSolid = True
            LocateUsingPoint = original.LocateUsingPoint
            reads = 0

            @property
            def RangeBox(self):
                self.reads += 1
                return original.RangeBox

        neighbor = CachedBoundsBody()
        second_first = NS(SurfaceBody=self.owner)
        jobs = [self.jobs[0], {**self.jobs[0], "colored_face": second_first}]
        self.inventor.comp.SurfaceBodies = collection([self.owner, neighbor])
        self.inventor.comp.FindUsingPoint.return_value = collection([original.test_face])
        result = body_targets(
            self.inventor, [(self.first, object()), (second_first, object())], jobs,
        )
        self.assertEqual(len(result), 2)
        self.assertEqual(neighbor.reads, 0)
        self.assertEqual(self.inventor.comp.FindUsingPoint.call_count, 2)
        original.LocateUsingPoint.assert_not_called()

    def test_global_search_does_not_request_body_collection(self):
        neighbor = body("neighbor")

        class Component:
            FindUsingPoint = Mock(return_value=collection([neighbor.test_face]))

            @property
            def SurfaceBodies(self):
                raise AssertionError("Enumerating all bodies is forbidden")

        self.inventor.comp = Component()
        result = body_targets(self.inventor, [(self.first, object())], self.jobs)
        self.assertEqual(result[id(self.first)]["neighbor_body"], "neighbor")

    def test_verified_body_references_are_passed_to_hole_builder_cache(self):
        neighbor = body("neighbor")
        self.inventor.comp.FindUsingPoint.return_value = collection([neighbor.test_face])
        references = {}
        result = body_targets(self.inventor, [(self.first, object())], self.jobs, body_cache=references)
        self.assertIs(references[result[id(self.first)]["owner_body"]], self.owner)
        self.assertIs(references[result[id(self.first)]["neighbor_body"]], neighbor)

    def test_filter_is_a_sequence_for_generated_pywin32_safearray_wrapper(self):
        neighbor = body("neighbor")

        def generated_find_using_point(sample, object_types, tolerance, visible_only):
            # Генерируемые pywin32-методы принимают последовательность для
            # аргумента SAFEARRAY, а не готовый VARIANT с таким массивом.
            if not isinstance(object_types, (tuple, list)):
                raise TypeError("Objects for SAFEARRAYS must be sequences (of sequences), or a buffer object.")
            self.assertEqual(object_types, (15877,))
            return collection([neighbor.test_face])

        self.inventor.comp.FindUsingPoint.side_effect = generated_find_using_point
        result = self.targets(neighbor)
        self.assertEqual(result[id(self.first)]["neighbor_body"], "neighbor")

    def test_hole_groups_route_each_operation_to_one_correct_body(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        creator = Mock()
        jobs = [{"outer_points": [object(), object()], "inner_points": [object()],
                 "owner_body": owner, "neighbor_body": neighbor}
                for owner, neighbor in [("A", "B"), ("C", "D")]]
        result = create_stiajka_features(
            inventor, sketches=[], colored_faces=[], point_jobs=jobs,
            update_document=False, strict=True, hole_creator=creator,
        )
        self.assertEqual(result, 8)
        self.assertEqual([c.kwargs["affected_body"] for c in creator.call_args_list],
                         ["A", "C", "B", "D", "B", "D", "A", "C"])
        inventor.add_holes.assert_not_called()

    def test_builder_assigns_only_one_live_body_without_all_bodies_call(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        inventor.object_collection.side_effect = list
        features = inventor.comp.Features.HoleFeatures
        features.Item.side_effect = KeyError("missing")
        selected = NS(Name="neighbor")
        bodies = Mock()
        bodies.Count = 2
        bodies.Item.side_effect = lambda index: [NS(Name="other"), selected][index - 1]
        inventor.comp.SurfaceBodies = bodies
        builder = TimedHoleBuilder(inventor)
        feature = builder([object()], "8 mm", "13 mm", 1, "test", affected_body="neighbor")
        self.assertEqual([c.args[0] for c in bodies.Item.call_args_list], [1, 2])
        feature.SetAffectedBodies.assert_called_once_with([selected])
        inventor.set_all_bodies_affected.assert_not_called()

    def test_failed_body_restriction_deletes_feature_and_stops_without_retry(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        inventor.object_collection.side_effect = list
        features = inventor.comp.Features.HoleFeatures
        features.Item.side_effect = KeyError("missing")
        feature = features.AddDrilledByDistanceExtent.return_value
        feature.SetAffectedBodies.side_effect = RuntimeError("restriction failed")
        inventor.comp.SurfaceBodies = collection([NS(Name="neighbor")])
        builder = TimedHoleBuilder(inventor)
        jobs = [{"outer_points": [object()], "neighbor_body": "neighbor"} for _ in range(2)]
        with self.assertRaises(AffectedBodyError):
            create_hole_batch(
                inventor, jobs, "outer_points", "shkant_v_plast", "8 mm", "10 mm",
                "test", "test", strict=True, hole_creator=builder,
            )
        features.AddDrilledByDistanceExtent.assert_called_once()
        feature.Delete.assert_called_once()
        inventor.set_all_bodies_affected.assert_not_called()

    def test_body_lookup_rebinds_by_numeric_index_after_body_order_changes(self):
        inventor = Mock()
        a, b = NS(Name="A"), NS(Name="B")
        current = [a, b]
        inventor.comp.SurfaceBodies = NS(Count=2, Item=lambda index: current[index - 1])
        builder = TimedHoleBuilder(inventor)
        self.assertIs(builder.body_for_name("B"), b)
        current[:] = [b, a]
        self.assertIs(builder.body_for_name("B"), b)
        with self.assertRaises(AffectedBodyError):
            builder.body_for_name("missing")


if __name__ == "__main__":
    unittest.main()
