import contextlib
import io
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from stiajka.hole_builder import TimedHoleBuilder
from stiajka.stiajka import create_hole_batch, create_second_face_stiajka_holes


class HoleBuilderTests(unittest.TestCase):
    def setUp(self):
        self.inventor = Mock()
        self.inventor.unique_points.side_effect = list
        self.inventor.object_collection.side_effect = lambda points: points
        self.inventor.hole_direction.side_effect = lambda value: value
        self.features = self.inventor.comp.Features.HoleFeatures
        self.features.Item.side_effect = KeyError("missing")
        self.features.AddDrilledByDistanceExtent.side_effect = lambda *args: NS(Name="automatic")
        self.builder = TimedHoleBuilder(self.inventor)
        self.log = io.StringIO()
        output = contextlib.redirect_stdout(self.log)
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_preserves_hole_settings_and_profiles_all_stages(self):
        points = [object(), object()]
        with patch("stiajka.hole_builder.resolve_parameter_expression", side_effect=lambda s: "resolved:" + s):
            feature = self.builder(points, "diameter", "depth", "negative", "Stiajka cup")
        self.inventor.mark_as_hole_centers.assert_called_once_with(points)
        self.features.CreateSketchPlacementDefinition.assert_called_once_with(points)
        self.features.AddDrilledByDistanceExtent.assert_called_once_with(
            self.features.CreateSketchPlacementDefinition.return_value,
            "resolved:diameter", "resolved:depth", "negative", True,
        )
        self.assertEqual(feature.Name, "Stiajka cup")
        self.inventor.set_all_bodies_affected.assert_called_once_with(feature, self.inventor.comp)
        self.inventor.unique_feature_name.assert_not_called()
        for stage in ("подготовка точек и размещения", "создание операции Inventor",
                      "подбор и назначение имени", "назначение затрагиваемых тел"):
            self.assertIn(stage, self.log.getvalue())

    def test_repeated_names_skip_existing_and_reserved_names_without_enumeration(self):
        def item(name):
            if name in ("Cup", "Cup_1"):
                return object()
            raise KeyError(name)

        self.features.Item.side_effect = item
        first = self.builder([object()], "8 mm", "13 mm", 1, "Cup")
        second = self.builder([object()], "8 mm", "13 mm", 1, "Cup")
        self.assertEqual([first.Name, second.Name], ["Cup_2", "Cup_3"])
        self.assertEqual([call.args[0] for call in self.features.Item.call_args_list],
                         ["Cup", "Cup_1", "Cup_2", "Cup_3"])
        self.inventor.unique_feature_name.assert_not_called()

    def test_creation_failure_propagates_without_postprocessing(self):
        self.features.AddDrilledByDistanceExtent.side_effect = RuntimeError("creation failed")
        with self.assertRaisesRegex(RuntimeError, "creation failed"):
            self.builder([object()], "8 mm", "13 mm", 1, "Cup")
        self.features.Item.assert_not_called()
        self.inventor.set_all_bodies_affected.assert_not_called()
        self.assertIn("создание операции Inventor", self.log.getvalue())

    def test_postprocessing_failure_does_not_repeat_existing_hole(self):
        class Feature:
            @property
            def Name(self):
                return "automatic"

            @Name.setter
            def Name(self, value):
                raise RuntimeError("rename failed")

        self.features.AddDrilledByDistanceExtent.side_effect = lambda *args: Feature()
        self.inventor.set_all_bodies_affected.side_effect = RuntimeError("bodies failed")
        jobs = [{"outer_points": [object(), object()]} for _ in range(2)]
        result = create_hole_batch(
            self.inventor, jobs, "outer_points", "Otv_stijki_v_torec",
            "8 mm", "34 mm", "test", "test", strict=True, hole_creator=self.builder,
        )
        self.assertEqual(result, 1)
        self.features.AddDrilledByDistanceExtent.assert_called_once()
        self.assertIn("rename failed", self.log.getvalue())
        self.assertIn("bodies failed", self.log.getvalue())

    def test_second_face_uses_same_builder_and_respects_body_and_bottom_flags(self):
        points = [object(), object()]
        result = create_second_face_stiajka_holes(
            self.inventor, points,
            dict(diameter="15 mm", depth="13 mm", direction=1, name="Cup",
                 flat_bottom=False, affect_all_bodies=False),
            hole_creator=self.builder,
        )
        self.assertEqual(result, 1)
        self.inventor.add_holes.assert_not_called()
        self.assertFalse(self.features.AddDrilledByDistanceExtent.call_args.args[-1])
        self.inventor.set_all_bodies_affected.assert_not_called()

    def test_repeated_centers_are_prepared_once_but_placement_is_always_new(self):
        points = [object(), object()]
        first_placement, second_placement = object(), object()
        self.features.CreateSketchPlacementDefinition.side_effect = [first_placement, second_placement]
        self.builder(points, "8 mm", "13 mm", 1, "first", affect_all_bodies=False)
        self.builder(list(points), "5 mm", "10 mm", -1, "second", affect_all_bodies=False)
        self.inventor.unique_points.assert_called_once()
        self.inventor.mark_as_hole_centers.assert_called_once()
        self.inventor.object_collection.assert_called_once()
        self.assertEqual(self.features.CreateSketchPlacementDefinition.call_count, 2)
        calls = self.features.AddDrilledByDistanceExtent.call_args_list
        self.assertIs(calls[0].args[0], first_placement)
        self.assertIs(calls[1].args[0], second_placement)

    def test_known_body_reference_avoids_enumerating_bodies(self):
        selected = NS(Name="neighbor")

        class NoBodies:
            @property
            def Count(self):
                raise AssertionError("Body enumeration must not run")

        self.inventor.comp.SurfaceBodies = NoBodies()
        builder = TimedHoleBuilder(self.inventor, known_bodies={"neighbor": selected})
        self.assertIs(builder.body_for_name("neighbor"), selected)

    def test_stale_known_body_reference_is_replaced_by_current_body(self):
        class StaleBody:
            @property
            def Name(self):
                raise RuntimeError("stale reference")

        current = NS(Name="neighbor")
        self.inventor.comp.SurfaceBodies = NS(Count=1, Item=lambda i: current)
        builder = TimedHoleBuilder(self.inventor, known_bodies={"neighbor": StaleBody()})
        self.assertIs(builder.body_for_name("neighbor"), current)
        self.assertIs(builder.body_refs["neighbor"], current)

    def test_prepared_centers_cannot_be_reused_by_another_builder(self):
        prepared = self.builder.prepare_points([object()])
        other = TimedHoleBuilder(self.inventor)
        with self.assertRaises(ValueError):
            other.prepare_points(prepared)


if __name__ == "__main__":
    unittest.main()
