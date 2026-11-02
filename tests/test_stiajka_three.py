import importlib
import unittest
from unittest.mock import Mock, patch

from stiajka.three_geometry import three_tie_span, create_three_points


class StiajkaThreeTests(unittest.TestCase):
    def test_exact_span_and_equal_spacing_without_grid_rounding(self):
        span = three_tie_span(60.7, 5.05)
        positions = (-span / 2, 0, span / 2)
        self.assertAlmostEqual(60.7 / 2 + positions[0], 5.05)
        self.assertAlmostEqual(60.7 / 2 - positions[2], 5.05)
        self.assertAlmostEqual(positions[1] - positions[0], positions[2] - positions[1])
        self.assertAlmostEqual(span, 50.6)

    def test_overlapping_dowels_and_invalid_offsets_are_rejected(self):
        for length, offset in ((10.4, 2), (10, 2), (60, -1), (60, float('nan'))):
            with self.subTest(length=length, offset=offset), self.assertRaises(ValueError):
                three_tie_span(length, offset)

    def test_launcher_uses_three_centers_on_both_faces_before_drilling(self):
        launcher = importlib.import_module('05_stiajka_3inch')
        inventor = Mock()
        first, second = object(), object()
        middle = object()
        job = dict(colored_face=first, outer_points=[object(), object()],
                   inner_points=[object(), object()], center_point=middle)
        second_points = [object(), object(), object()]
        targets = {id(first): dict(owner_body='owner', neighbor_body='neighbor')}
        state = dict(second_ready=False)

        def build_first(*args, **kwargs):
            self.assertIs(kwargs['point_builder'].func, create_three_points)
            kwargs['point_jobs'].append(job)
            return [object()]

        def build_second(*args, **kwargs):
            self.assertTrue(kwargs['three_ties'])
            state['second_ready'] = True
            return object(), second_points

        def create_first(*args, **kwargs):
            self.assertTrue(state['second_ready'])
            self.assertEqual(len(kwargs['point_jobs'][0]['outer_points']), 3)
            self.assertIs(kwargs['point_jobs'][0]['outer_points'][2], middle)
            return 4

        with patch.object(launcher.create_sketches, 'create_sketches_for_faces', side_effect=build_first), patch.object(
            launcher, 'create_offset_drilling_sketch', side_effect=build_second,
        ), patch.object(launcher, 'body_targets', return_value=targets), patch.object(
            launcher.stiajka_module, 'create_stiajka_features', side_effect=create_first,
        ), patch.object(launcher.stiajka_module, 'create_second_face_stiajka_holes', return_value=1) as cups, patch.object(
            launcher, 'TimedHoleBuilder',
        ):
            launcher.create_drilling(inventor, [(first, second)], 'edge', 'offset', 3.4, 5,
                                     {}, [((0, 0, 0), (1, 0, 0))], Mock(), [object()])
        self.assertIs(cups.call_args.args[1], second_points)
        inventor.update.assert_called_once()


if __name__ == '__main__':
    unittest.main()
