"""Две зеркальные пары с шагом 96 мм и один центральный конфирмат."""
import math

PAIR_SPACING_CM = 9.6  # Внутренние единицы Inventor — сантиметры.


def pair_positions(length, edge_offset):
    if not all(math.isfinite(value) for value in (length, edge_offset)) or edge_offset < 0:
        raise ValueError("Отступ должен быть конечным неотрицательным числом.")
    if length - 2 * edge_offset - 2 * PAIR_SPACING_CM <= 1e-6:
        raise ValueError(
            f"Недостаточно места для двух пар конфирматов: длина {length * 10:g} мм. "
            f"При отступе {edge_offset * 10:g} мм длина должна быть больше "
            f"{(2 * edge_offset + 2 * PAIR_SPACING_CM) * 10:g} мм."
        )
    outer = length / 2 - edge_offset
    return -outer, -outer + PAIR_SPACING_CM, outer - PAIR_SPACING_CM, outer


def create_pair_points(inventor, sketch, axes, index, edge_offset, runtime_names, *, edge_offset_param, control_line=None):
    axis, symmetry, center, length, ux, uy, nx, ny = axes
    cx, cy = center.X, center.Y
    positions = pair_positions(length, edge_offset)
    left, left_inner, right_inner, right = [
        inventor.add_sketch_point(
            sketch, inventor.create_point2d(cx + ux * position, cy + uy * position)
        ) for position in positions
    ]
    for point in (left, left_inner, right_inner, right):
        inventor.add_coincident_constraint(sketch, point, axis, ignore_errors=False)
    inventor.add_symmetry_constraint(sketch, left, right, symmetry, ignore_errors=False)
    inventor.add_symmetry_constraint(sketch, left_inner, right_inner, symmetry, ignore_errors=False)
    middle = inventor.add_sketch_point(sketch, center)
    inventor.add_coincident_constraint(sketch, middle, axis, ignore_errors=False)
    inventor.add_coincident_constraint(sketch, middle, symmetry, ignore_errors=False)

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
    distance_dim.Parameter.Expression = f"{long_name} - 2 * {edge_offset_param}"
    spacing_dim = inventor.add_aligned_dimension(
        sketch, left, left_inner,
        inventor.create_point2d(cx + ux * positions[0] + nx * 3, cy + uy * positions[0] + ny * 3),
    )
    spacing_dim.Parameter.Expression = "96 mm"
    # Формат общего построителя: крайние, внутренние, центр, полуразмер.
    return left, right, left_inner, right_inner, middle, length / 2 - edge_offset
