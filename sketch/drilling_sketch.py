from common.constants import (
    EDGE_OFFSET_DRAWER_PARAM,
    EDGE_OFFSET_FRAME_PARAM,
    EDGE_OFFSET_PARAM,
    GRID_STEP_CM,
    POINT_DISTANCE_PARAM,
)
from common.sketch_geometry import (
    add_aligned_dimension,
    distance,
    get_parameter_value,
    line_length2,
    line_midpoint,
    project_face_edges,
    sketch_lines_for_face,
    unique_parameter_name,
)
from common.settings import drawer_edge_max_cm


def edge_offset_param_for_length(long_edge_length):
    if long_edge_length <= drawer_edge_max_cm():
        return EDGE_OFFSET_DRAWER_PARAM

    return EDGE_OFFSET_FRAME_PARAM


def create_construction_axes(sk, tg, short1, short2):
    c1 = line_midpoint(tg, short1)
    c2 = line_midpoint(tg, short2)
    d = distance(c1, c2)
    ux = (c2.X - c1.X) / d
    uy = (c2.Y - c1.Y) / d
    nx = -uy
    ny = ux

    axis = sk.SketchLines.AddByTwoPoints(c1, c2)
    axis.Construction = True
    sk.GeometricConstraints.AddMidpoint(axis.StartSketchPoint, short1)
    sk.GeometricConstraints.AddMidpoint(axis.EndSketchPoint, short2)

    center = tg.CreatePoint2d((c1.X + c2.X) / 2, (c1.Y + c2.Y) / 2)
    symmetry_axis = sk.SketchLines.AddByTwoPoints(
        tg.CreatePoint2d(center.X - nx, center.Y - ny),
        tg.CreatePoint2d(center.X + nx, center.Y + ny),
    )
    symmetry_axis.Construction = True
    sk.GeometricConstraints.AddPerpendicular(axis, symmetry_axis)
    sk.GeometricConstraints.AddMidpoint(symmetry_axis.StartSketchPoint, axis)

    return axis, symmetry_axis, center, d, ux, uy, nx, ny


def create_drilling_points(sk, tg, center, ux, uy, point_distance_value):
    outer = point_distance_value / 2
    inner = outer - GRID_STEP_CM

    left_outer = sk.SketchPoints.Add(tg.CreatePoint2d(center.X - ux * outer, center.Y - uy * outer), False)
    right_outer = sk.SketchPoints.Add(tg.CreatePoint2d(center.X + ux * outer, center.Y + uy * outer), False)
    left_inner = sk.SketchPoints.Add(tg.CreatePoint2d(center.X - ux * inner, center.Y - uy * inner), False)
    right_inner = sk.SketchPoints.Add(tg.CreatePoint2d(center.X + ux * inner, center.Y + uy * inner), False)
    center_point = sk.SketchPoints.Add(center, False)

    return left_outer, right_outer, left_inner, right_inner, center_point, outer


def constrain_drilling_points(sk, axis, symmetry_axis, points):
    left_outer, right_outer, left_inner, right_inner, center_point, _ = points

    for point in (left_outer, right_outer, left_inner, right_inner, center_point):
        sk.GeometricConstraints.AddCoincident(point, axis)

    sk.GeometricConstraints.AddCoincident(center_point, symmetry_axis)
    sk.GeometricConstraints.AddSymmetry(left_outer, right_outer, symmetry_axis)
    sk.GeometricConstraints.AddSymmetry(left_inner, right_inner, symmetry_axis)


def closest_point_on_line(tg, point, line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    dx = end.X - start.X
    dy = end.Y - start.Y
    length2 = dx * dx + dy * dy

    if length2 == 0:
        return tg.CreatePoint2d(start.X, start.Y)

    t = ((point.X - start.X) * dx + (point.Y - start.Y) * dy) / length2
    t = max(0, min(1, t))
    return tg.CreatePoint2d(start.X + dx * t, start.Y + dy * t)


def add_side_plane_reference_line(sk, tg, axis, lines):
    long_edges = sorted(lines, key=line_length2, reverse=True)[:2]
    if not long_edges:
        return None

    start = axis.StartSketchPoint.Geometry
    end = axis.EndSketchPoint.Geometry
    reference = tg.CreatePoint2d((start.X + end.X) / 2, (start.Y + end.Y) / 2)
    target = min(
        long_edges,
        key=lambda line: closest_point_on_line(tg, reference, line).Y,
    )
    end_point = closest_point_on_line(tg, reference, target)
    line = sk.SketchLines.AddByTwoPoints(reference, end_point)
    line.Construction = True

    try:
        sk.GeometricConstraints.AddPerpendicular(line, axis)
    except Exception:
        pass

    return line


def add_drilling_dimensions(sk, tg, parameters, axes, points, index, edge_offset_param):
    axis, _, center, _, ux, uy, nx, ny = axes
    left_outer, right_outer, left_inner, _, _, outer = points

    long_dim = add_aligned_dimension(
        sk,
        axis.StartSketchPoint,
        axis.EndSketchPoint,
        tg.CreatePoint2d(center.X + nx * 4, center.Y + ny * 4),
        True,
    )
    point_distance_dim = add_aligned_dimension(
        sk,
        right_outer,
        left_outer,
        tg.CreatePoint2d(center.X + nx * 2, center.Y + ny * 2),
    )
    inset_dim = add_aligned_dimension(
        sk,
        left_outer,
        left_inner,
        tg.CreatePoint2d(center.X - ux * (outer - 1.6) + nx * 2, center.Y - uy * (outer - 1.6) + ny * 2),
    )

    long_dim.Parameter.Name = unique_parameter_name(parameters, f"Long_edge_{index}")
    point_distance_dim.Parameter.Name = unique_parameter_name(parameters, POINT_DISTANCE_PARAM)
    point_distance_dim.Parameter.Expression = (
        f"floor(({long_dim.Parameter.Name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
    )
    inset_dim.Parameter.Expression = "32 mm"


def create_drilling_sketch(sk, face, index, inv, comp, edge_offset_param=EDGE_OFFSET_PARAM):
    tg = inv.TransientGeometry
    first_new_line = project_face_edges(sk, face)
    lines = sketch_lines_for_face(sk, face, first_new_line)

    if len(lines) < 2:
        return False

    short1, short2 = sorted(lines, key=line_length2)[:2]
    axes = create_construction_axes(sk, tg, short1, short2)
    _, _, center, long_edge_length, ux, uy, _, _ = axes
    if callable(edge_offset_param):
        edge_offset_param = edge_offset_param(long_edge_length)
    elif edge_offset_param is None:
        edge_offset_param = edge_offset_param_for_length(long_edge_length)

    edge_offset_value = get_parameter_value(comp.Parameters, edge_offset_param, 10)
    point_distance_value = int((long_edge_length - edge_offset_value * 2) / GRID_STEP_CM) * GRID_STEP_CM
    point_distance_value = max(point_distance_value, GRID_STEP_CM * 2)

    points = create_drilling_points(sk, tg, center, ux, uy, point_distance_value)
    constrain_drilling_points(sk, axes[0], axes[1], points)
    add_side_plane_reference_line(sk, tg, axes[0], lines)
    add_drilling_dimensions(sk, tg, comp.Parameters, axes, points, index, edge_offset_param)

    return True
