import unittest
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, Mock, PropertyMock, call, patch

from confirmat import confirmat as holes
from confirmat.parameters import ensure_unitless_keep_parameter, resolve_confirmat_count
from confirmat.parameter_dialog import all_parameter_names
from confirmat.runtime import ConfirmatRuntime


class ConfirmatOptimizedTests(unittest.TestCase):
    def test_launcher_passes_created_points_and_updates_only_after_holes(self):
        spec = importlib.util.spec_from_file_location("confirmat_launcher", Path(__file__).resolve().parents[1] / "02_confirmat.py")
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        inventor = MagicMock()
        sketch = object()
        job = dict(sketch=sketch, outer_points=[object(), object()], center_point=object())

        def build(*args, **kwargs):
            self.assertFalse(kwargs["compact_points"])
            kwargs["point_jobs"].append(job)
            return [sketch]

        def holes_created(*args, **kwargs):
            self.assertEqual(kwargs["point_jobs"], [job])
            self.assertFalse(kwargs["update_document"])
            inventor.update.assert_not_called()
            return 2

        with patch.object(launcher, "selected_inventor_context", return_value=(inventor, [object()])), patch.object(
            launcher, "ConfirmatRuntime", return_value=inventor
        ), patch.object(launcher, "choose_workflow_parameters", return_value=("thickness", "offset", "count")), patch.object(
            launcher, "use_material_thickness"
        ), patch.object(launcher, "confirmat_parameter_names", return_value=()), patch.object(
            launcher, "resolve_confirmat_count", return_value="2"
        ), patch.object(launcher, "ensure_unitless_keep_parameter"), patch.object(launcher, "DrillingNames"), patch.object(
            launcher.create_sketches, "ensure_parameters", return_value=True
        ), patch.object(launcher.create_sketches, "create_sketches_for_faces", side_effect=build), patch.object(
            launcher.confirmat_module, "create_confirmat_edges_and_center_features", side_effect=holes_created
        ):
            launcher.main()
        inventor.update.assert_called_once_with()
        inventor.screen_updates_suspended.return_value.__exit__.assert_called_once()

    def test_created_centers_drive_edge_and_suppressed_center_holes_without_rescanning(self):
        inventor = Mock()
        inventor.unique_points.side_effect = lambda points: points
        left, right, center = object(), object(), object()
        sketch = NS(Shared=False)
        feature = Mock()
        with patch.object(holes, "_sync_settings"), patch.object(holes, "_LAST_CREATED_FEATURES", []), patch.object(
            holes._confirmat, "add_confirmat_counterbore", return_value=feature
        ) as create:
            count = holes.create_confirmat_edges_and_center_features(
                inventor, sketches=[sketch], faces=[object()],
                point_jobs=[dict(sketch=sketch, outer_points=[left, right], center_point=center)],
                center_suppression_parameter="count", center_suppression_value=2,
                update_document=False,
            )
        self.assertEqual(count, 2)
        self.assertEqual(create.call_args_list[0].args[1], [left, right])
        self.assertEqual(create.call_args_list[1].args[1], [center])
        feature.SetSuppressionCondition.assert_called_once_with(inventor.parameter.return_value, 60417, 2)
        self.assertTrue(sketch.Shared)
        inventor.sketch_points.assert_not_called()
        inventor.sketch_lines.assert_not_called()
        inventor.update.assert_not_called()

    def test_empty_direct_jobs_do_not_fall_back_to_model_scan(self):
        inventor = Mock()
        inventor.unique_points.side_effect = lambda points: points
        with patch.object(holes, "_sync_settings"), patch.object(holes._confirmat, "add_confirmat_counterbore") as create:
            count = holes.create_confirmat_edges_and_center_features(
                inventor, sketches=[NS(Shared=False)], faces=[object()], point_jobs=[], update_document=False,
            )
        self.assertEqual(count, 0)
        create.assert_not_called()
        inventor.sketch_points.assert_not_called()

    def test_count_value_does_not_read_expression_but_invalid_value_uses_fallback(self):
        inventor = Mock()
        inventor.parameter_value.return_value = 3
        self.assertEqual(resolve_confirmat_count(inventor, "count"), "3")
        inventor.parameter_expression.assert_not_called()
        inventor.parameter_value.return_value = "invalid"
        inventor.parameter_expression.return_value = "2 ul"
        self.assertEqual(resolve_confirmat_count(inventor, "count"), "2")

    def test_initial_parameter_list_reuses_objects_and_does_not_read_model_parameters(self):
        parameter = NS(Name="thickness", Value=1.6)

        class Inventor:
            parameters = NS(Item=Mock())
            user_parameters = NS(Count=1, Item=lambda i: parameter)

            @property
            def model_parameters(self):
                raise AssertionError("Model collection should load only on request")

        runtime = ConfirmatRuntime(Inventor())
        self.assertEqual(all_parameter_names(runtime, include_model=False, parameter_cache=runtime.parameter_session), ("thickness",))
        self.assertEqual(runtime.missing_parameters(["thickness"]), [])
        self.assertEqual(runtime.parameter_value("thickness"), 1.6)
        runtime.inventor.parameters.Item.assert_not_called()

    def test_unitless_keep_does_not_rewrite_unchanged_expression(self):
        parameter = Mock()
        expression = PropertyMock(return_value="count*0")
        type(parameter).Expression = expression
        inventor = Mock()
        inventor.parameter.side_effect = [NS(Name="count", Units="ul"), parameter]
        self.assertIs(ensure_unitless_keep_parameter(inventor, "Keep", ["count"]), parameter)
        self.assertEqual(expression.call_args_list, [call()])
        inventor.ensure_user_parameter.assert_not_called()


if __name__ == "__main__":
    unittest.main()
