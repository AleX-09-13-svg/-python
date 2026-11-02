import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from confirmat.pair_geometry import pair_positions, create_pair_points
from confirmat.parameter_dialog import user_parameter_options, thickness_parameter_options
from confirmat import confirmat as holes


class ConfirmatPairTests(unittest.TestCase):
    def test_exact_offsets_and_spacing_on_length_outside_32mm_grid(self):
        length, offset = 60.7, 5.0
        positions = pair_positions(length, offset)
        self.assertAlmostEqual(positions[0] + length / 2, offset)
        self.assertAlmostEqual(length / 2 - positions[3], offset)
        self.assertAlmostEqual(positions[1] - positions[0], 9.6)
        self.assertAlmostEqual(positions[3] - positions[2], 9.6)
        self.assertAlmostEqual(positions[2] - positions[1], 31.5)

    def test_short_faces_and_invalid_offsets_are_rejected(self):
        for length, offset in ((29.2, 5), (20, 5), (60, -1), (60, float('nan'))):
            with self.subTest(length=length, offset=offset), self.assertRaises(ValueError):
                pair_positions(length, offset)

    def test_options_include_only_existing_user_parameters_and_allow_custom_names(self):
        names = ('CustomThickness', 'CustomOffset', 'Толщина_каркаса')
        options = user_parameter_options(names, thickness_parameter_options(names))
        self.assertEqual(options[0], 'Толщина_каркаса')
        self.assertEqual(set(options), set(names))
        self.assertEqual(user_parameter_options((), thickness_parameter_options(())), ())

    def test_rotated_axis_and_parametric_dimensions_preserve_two_pairs(self):
        inventor = Mock()
        inventor.create_point2d.side_effect = lambda x, y: NS(X=x, Y=y)
        inventor.add_sketch_point.side_effect = lambda sketch, point: NS(Geometry=point)
        dimensions = [NS(Parameter=NS()) for _ in range(3)]
        inventor.add_aligned_dimension.side_effect = dimensions
        names = Mock()
        names.parameter.return_value = 'Long_edge_1'
        axis = NS(StartSketchPoint=object(), EndSketchPoint=object())
        sketch, symmetry = object(), object()
        points = create_pair_points(
            inventor, sketch, (axis, symmetry, NS(X=2, Y=30.35), 60.7, 0, 1, -1, 0),
            1, 5.05, names, edge_offset_param='PairOffset',
        )
        self.assertAlmostEqual(points[4].Geometry.X, 2)
        self.assertAlmostEqual(points[4].Geometry.Y, 30.35)
        inventor.add_coincident_constraint.assert_any_call(sketch, points[4], axis, ignore_errors=False)
        inventor.add_coincident_constraint.assert_any_call(sketch, points[4], symmetry, ignore_errors=False)
        left, right, left_inner, right_inner = points[:4]
        for point in points[:4]:
            self.assertAlmostEqual(point.Geometry.X, 2)
        self.assertAlmostEqual(left.Geometry.Y, 5.05)
        self.assertAlmostEqual(right.Geometry.Y, 55.65)
        self.assertAlmostEqual(left_inner.Geometry.Y - left.Geometry.Y, 9.6)
        self.assertAlmostEqual(right.Geometry.Y - right_inner.Geometry.Y, 9.6)
        self.assertEqual(dimensions[1].Parameter.Expression, 'Long_edge_1 - 2 * PairOffset')
        self.assertEqual(dimensions[2].Parameter.Expression, '96 mm')
        self.assertEqual(inventor.add_coincident_constraint.call_count, 6)
        self.assertEqual(inventor.add_symmetry_constraint.call_count, 2)

    def test_all_five_points_create_holes_without_center_suppression(self):
        inventor = Mock()
        inventor.unique_points.side_effect = list
        points = [object() for _ in range(5)]
        feature = Mock()
        with patch.object(holes, '_sync_settings'), patch.object(
            holes._confirmat, 'add_confirmat_counterbore', return_value=feature,
        ) as create:
            result = holes.create_confirmat_pair_features(
                inventor, sketches=[NS(Shared=False)], faces=[object()],
                point_jobs=[dict(outer_points=points[:2], inner_points=points[2:4], center_point=points[4])],
                update_document=False,
            )
        self.assertEqual(result, 1)
        self.assertEqual(create.call_args.args[1], points)
        feature.SetSuppressionCondition.assert_not_called()
        inventor.update.assert_not_called()


if __name__ == '__main__':
    unittest.main()
