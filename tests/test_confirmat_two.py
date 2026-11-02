import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import MagicMock, Mock, patch

from confirmat.two_geometry import two_point_distance, create_two_points
from confirmat import confirmat as holes


class ConfirmatTwoTests(unittest.TestCase):
    def test_grid_preserves_minimum_offset_and_maximizes_distance(self):
        for length, offset in ((60.7, 5), (60, 5.05), (13.2, 5), (32, 0)):
            with self.subTest(length=length, offset=offset):
                distance = two_point_distance(length, offset)
                actual_offset = (length - distance) / 2
                self.assertAlmostEqual(distance / 3.2, round(distance / 3.2))
                self.assertGreaterEqual(actual_offset + 1e-9, offset)
                self.assertLess(actual_offset - offset, 1.6 + 1e-9)
        self.assertAlmostEqual(two_point_distance(60.7, 5), 48)

    def test_short_faces_and_invalid_offsets_are_rejected(self):
        for length, offset in ((13, 5), (20, -1), (20, float('nan')), (float('inf'), 0)):
            with self.subTest(length=length, offset=offset), self.assertRaises(ValueError):
                two_point_distance(length, offset)

    def test_only_two_points_are_created_and_dimensions_reference_minimum_parameter(self):
        inventor = Mock()
        inventor.create_point2d.side_effect = lambda x, y: NS(X=x, Y=y)
        inventor.add_sketch_point.side_effect = lambda sketch, point: NS(Geometry=point)
        dimensions = [NS(Parameter=NS()), NS(Parameter=NS())]
        inventor.add_aligned_dimension.side_effect = dimensions
        names = Mock()
        names.parameter.return_value = 'Long_edge_1'
        axis = NS(StartSketchPoint=object(), EndSketchPoint=object())
        points = create_two_points(
            inventor, object(), (axis, object(), NS(X=2, Y=30.35), 60.7, 0, 1, -1, 0),
            1, 5, names, edge_offset_param='MinimumOffset',
        )
        inventor.add_sketch_point.assert_called()
        self.assertEqual(inventor.add_sketch_point.call_count, 2)
        self.assertAlmostEqual(points[0].Geometry.Y, 6.35)
        self.assertAlmostEqual(points[1].Geometry.Y, 54.35)
        self.assertIsNone(points[4])
        self.assertEqual(dimensions[1].Parameter.Expression,
                         'floor((Long_edge_1 - 2 * MinimumOffset) / 32 mm) * 32 mm')

    def test_only_outer_points_are_used_for_holes(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        points = [object(), object()]
        with patch.object(holes, '_sync_settings'), patch.object(
            holes._confirmat, 'add_confirmat_counterbore',
        ) as create:
            count = holes.create_confirmat_two_features(
                inventor, [NS(Shared=False)], [object()],
                [dict(outer_points=points, inner_points=[object()], center_point=object())],
                update_document=False,
            )
        self.assertEqual(count, 1)
        self.assertEqual(create.call_args.args[1], points)
        inventor.update.assert_not_called()

    def test_launcher_selects_two_point_mode_and_passes_created_jobs_to_holes(self):
        spec = importlib.util.spec_from_file_location(
            'confirmat_two_launcher', Path(__file__).resolve().parents[1] / '02_confirmat_2inch.py',
        )
        launcher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(launcher)
        inventor = MagicMock()
        inventor.parameter_value.return_value = 5
        sketch = object()
        job = dict(outer_points=[object(), object()], center_point=None)

        def build(*args, **kwargs):
            self.assertIs(kwargs['point_builder'].func, create_two_points)
            kwargs['point_jobs'].append(job)
            return [sketch]

        with patch.object(launcher, 'selected_inventor_context', return_value=(inventor, [object()])), patch.object(
            launcher, 'ConfirmatRuntime', return_value=inventor,
        ), patch.object(launcher, 'choose_workflow_parameters', return_value=('Thickness', 'MinimumOffset')) as dialog, patch.object(
            launcher, 'use_material_thickness',
        ), patch.object(launcher, 'confirmat_parameter_names', return_value=()), patch.object(
            launcher.create_sketches, 'ensure_parameters', return_value=True,
        ), patch.object(launcher.create_sketches, 'create_sketches_for_faces', side_effect=build), patch.object(
            launcher.confirmat_module, 'create_confirmat_two_features', return_value=1,
        ) as create:
            launcher.main()
        self.assertTrue(dialog.call_args.kwargs['two_confirmats'])
        self.assertEqual(create.call_args.kwargs['point_jobs'], [job])
        inventor.ensure_keep_parameter.assert_called_once_with('Keep_Excel_Params', ('Thickness', 'MinimumOffset'))
        inventor.update.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
