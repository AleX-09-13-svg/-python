"""Три стяжки с точным отступом и равными промежутками, два шканта."""
import math

from common.constants import GRID_STEP_CM


def three_tie_span(length, edge_offset):
    if not all(math.isfinite(value) for value in (length, edge_offset)) or edge_offset < 0:
        raise ValueError("Отступ должен быть конечным неотрицательным числом.")
    span = length - 2 * edge_offset
    if span <= 2 * GRID_STEP_CM + 1e-6:
        raise ValueError(
            "Недостаточно места для трёх стяжек и двух шкантов: "
            "расстояние между крайними стяжками должно быть больше 64 мм."
        )
    return span


def create_three_points(inventor, sketch, axes, index, edge_offset, runtime_names, *,
                        edge_offset_param, control_line=None):
    axis, symmetry, center, length, ux, uy, nx, ny = axes
    cx, cy = center.X, center.Y
    outer = three_tie_span(length, edge_offset) / 2
    inner = outer - GRID_STEP_CM
    left, right, left_dowel, right_dowel, middle = [
        inventor.add_sketch_point(
            sketch, inventor.create_point2d(cx + ux * position, cy + uy * position)
        ) for position in (-outer, outer, -inner, inner, 0)
    ]
    for point in (left, right, left_dowel, right_dowel, middle):
        inventor.add_coincident_constraint(sketch, point, axis, ignore_errors=False)
    inventor.add_coincident_constraint(sketch, middle, symmetry, ignore_errors=False)
    inventor.add_symmetry_constraint(sketch, left, right, symmetry, ignore_errors=False)
    inventor.add_symmetry_constraint(sketch, left_dowel, right_dowel, symmetry, ignore_errors=False)
    reference = control_line if control_line is not None else axis
    long_dim = inventor.add_aligned_dimension(
        sketch, reference.StartSketchPoint, reference.EndSketchPoint,
        inventor.create_point2d(cx + nx * 4, cy + ny * 4), True,
    )
    long_name = (runtime_names.parameter(f"Long_edge_{index}") if runtime_names is not None
                 else inventor.unique_parameter_name(f"Long_edge_{index}", inventor.parameters))
    long_dim.Parameter.Name = long_name
    span_dim = inventor.add_aligned_dimension(
        sketch, left, right, inventor.create_point2d(cx + nx * 2, cy + ny * 2),
    )
    span_dim.Parameter.Expression = f"{long_name} - 2 * {edge_offset_param}"
    dowel_dim = inventor.add_aligned_dimension(
        sketch, left, left_dowel,
        inventor.create_point2d(cx - ux * (outer - 1.6) + nx * 3, cy - uy * (outer - 1.6) + ny * 3),
    )
    dowel_dim.Parameter.Expression = "32 mm"
    return left, right, left_dowel, right_dowel, middle, outer
