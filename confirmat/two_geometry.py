"""Два центра с минимальным отступом и расстоянием, кратным 32 мм."""
import math

from common.constants import GRID_STEP_CM


def two_point_distance(length, minimum_offset):
    if not all(math.isfinite(value) for value in (length, minimum_offset)) or minimum_offset < 0:
        raise ValueError("Минимальный отступ должен быть конечным неотрицательным числом.")
    steps = (length - 2 * minimum_offset) / GRID_STEP_CM
    # При вычитании сантиметров точные 32 мм могут стать 31.99999999999999 мм.
    nearest = round(steps)
    if math.isclose(steps, nearest, rel_tol=0, abs_tol=1e-12):
        steps = nearest
    distance = math.floor(steps) * GRID_STEP_CM
    if distance < GRID_STEP_CM:
        raise ValueError("Недостаточно места для двух конфирматов с выбранным отступом и шагом 32 мм.")
    return distance


def create_two_points(inventor, sketch, axes, index, edge_offset, runtime_names, *, edge_offset_param, control_line=None):
    axis, symmetry, center, length, ux, uy, nx, ny = axes
    cx, cy = center.X, center.Y
    distance = two_point_distance(length, edge_offset)
    left, right = [
        inventor.add_sketch_point(
            sketch, inventor.create_point2d(cx + ux * position, cy + uy * position)
        ) for position in (-distance / 2, distance / 2)
    ]
    for point in (left, right):
        inventor.add_coincident_constraint(sketch, point, axis, ignore_errors=False)
    inventor.add_symmetry_constraint(sketch, left, right, symmetry, ignore_errors=False)
    reference = control_line if control_line is not None else axis
    long_dim = inventor.add_aligned_dimension(
        sketch, reference.StartSketchPoint, reference.EndSketchPoint,
        inventor.create_point2d(cx + nx * 4, cy + ny * 4), True,
    )
    long_name = (runtime_names.parameter(f"Long_edge_{index}") if runtime_names is not None
                 else inventor.unique_parameter_name(f"Long_edge_{index}", inventor.parameters))
    long_dim.Parameter.Name = long_name
    distance_dim = inventor.add_aligned_dimension(
        sketch, left, right, inventor.create_point2d(cx + nx * 2, cy + ny * 2),
    )
    distance_dim.Parameter.Expression = f"floor(({long_name} - 2 * {edge_offset_param}) / 32 mm) * 32 mm"
    # Общий формат построителя; дополнительных точек здесь не создаём.
    return left, right, left, right, None, distance / 2
