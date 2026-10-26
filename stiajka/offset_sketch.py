# Геометрия второго эскиза: пересечение плоскостей, смещённая ось, точки и размеры.
from common.constants import DRILLING_SKETCH_PREFIX, GRID_STEP_CM, PARAMETERS
import common.create_sketches as create_sketches


def create_offset_drilling_sketch(
    inventor,
    face,
    reference_face,
    index,
    offset_param,
    edge_offset_param,
    offset_value,
    edge_offset_value,
):
    # Найти направление пересечения плоскостей.
    intersection_point, intersection_direction = plane_intersection_model_line(
        inventor, face, reference_face
    )
    if intersection_point is None:
        return None
    sketch = inventor.add_sketch(face)
    sketch.Name = inventor.unique_sketch_name(f"{DRILLING_SKETCH_PREFIX}_{index}")
    inventor.set_sketch_color_rgb(sketch, create_sketches.SKETCH_YELLOW_RGB, include_entities=False)
    with inventor.deferred_sketch_updates(sketch):
        inventor.project_face_edges(sketch, face, ignore_errors=False)
        start = inventor.model_to_sketch_point(sketch, inventor.create_point3d(*intersection_point))
        end = inventor.model_to_sketch_point(
            sketch,
            inventor.create_point3d(
                intersection_point[0] + intersection_direction[0],
                intersection_point[1] + intersection_direction[1],
                intersection_point[2] + intersection_direction[2],
            ),
        )
        direction_length = inventor.distance_2d(start, end)
        if direction_length == 0:
            return None
        ux = (end.X - start.X) / direction_length
        uy = (end.Y - start.Y) / direction_length
        nx = -uy
        ny = ux
        # Вершины и их координаты получить один раз; центр вычислить по тем же вершинам.
        face_points = [
            (point.X, point.Y) for point in inventor.face_vertex_points_in_sketch(face, sketch)
        ]
        if not face_points:
            raise ValueError("Face has no vertices")
        center_x = sum(x for x, y in face_points) / len(face_points)
        center_y = sum(y for x, y in face_points) / len(face_points)
        if (center_x - start.X) * nx + (center_y - start.Y) * ny < 0:
            nx = -nx
            ny = -ny
        # Сместить ось к центру грани на значение параметра offset_param.
        base = inventor.create_point2d(start.X + nx * offset_value, start.Y + ny * offset_value)
        distances = [(x - base.X) * ux + (y - base.Y) * uy for x, y in face_points]
        min_distance = min(distances)
        max_distance = max(distances)
        length = max_distance - min_distance
        if length <= 0:
            return None
        reference_line, left_side, right_side = second_sketch_reference_lines(
            inventor, sketch, start, ux, uy, min_distance, max_distance
        )

        # Координаты точки на смещённой оси по расстоянию вдоль неё.
        def point_on_axis(distance):
            return inventor.create_point2d(base.X + ux * distance, base.Y + uy * distance)

        midpoint = point_on_axis((min_distance + max_distance) / 2)
        offset_start = point_on_axis(min_distance)
        offset_end = point_on_axis(max_distance)
        # Построить ось и привязать её к проекциям рёбер.
        axis = inventor.add_sketch_line(sketch, offset_start, offset_end, construction=True)
        inventor.add_parallel_constraint(sketch, axis, reference_line, ignore_errors=False)
        inventor.add_coincident_constraint(
            sketch, axis.StartSketchPoint, left_side, ignore_errors=False
        )
        inventor.add_coincident_constraint(
            sketch, axis.EndSketchPoint, right_side, ignore_errors=False
        )
        # Закрепить смещение перпендикулярным вспомогательным отрезком.
        offset_anchor = inventor.add_sketch_line(
            sketch,
            inventor.create_point2d(midpoint.X - nx * offset_value, midpoint.Y - ny * offset_value),
            midpoint,
            construction=True,
        )
        inventor.add_coincident_constraint(
            sketch, offset_anchor.StartSketchPoint, reference_line, ignore_errors=False
        )
        inventor.add_coincident_constraint(
            sketch, offset_anchor.EndSketchPoint, axis, ignore_errors=False
        )
        inventor.add_perpendicular_constraint(sketch, offset_anchor, axis, ignore_errors=False)
        # Провести ось симметрии через середину основной оси.
        symmetry_axis = inventor.add_sketch_line(
            sketch,
            midpoint,
            inventor.create_point2d(midpoint.X + nx, midpoint.Y + ny),
            construction=True,
        )
        inventor.add_perpendicular_constraint(sketch, axis, symmetry_axis, ignore_errors=False)
        inventor.add_midpoint_constraint(
            sketch, symmetry_axis.StartSketchPoint, axis, ignore_errors=False
        )
        inventor.add_coincident_constraint(
            sketch, offset_anchor.EndSketchPoint, symmetry_axis, ignore_errors=False
        )
        point_distance_value = int((length - edge_offset_value * 2) / GRID_STEP_CM) * GRID_STEP_CM
        point_distance_value = max(point_distance_value, GRID_STEP_CM * 2)
        # Создать пять точек с расстоянием, кратным 32 мм, и наложить зависимости.
        points = inventor.create_drilling_points(sketch, midpoint, ux, uy, point_distance_value)
        inventor.constrain_drilling_points(sketch, axis, symmetry_axis, points)
        left_outer, right_outer, left_inner, _, _, outer = points
        # Добавить размеры и связать их с параметрами модели.
        long_dim = inventor.add_aligned_dimension(
            sketch,
            axis.StartSketchPoint,
            axis.EndSketchPoint,
            inventor.create_point2d(midpoint.X + nx * 4, midpoint.Y + ny * 4),
            True,
        )
        point_distance_dim = inventor.add_aligned_dimension(
            sketch,
            right_outer,
            left_outer,
            inventor.create_point2d(midpoint.X + nx * 2, midpoint.Y + ny * 2),
        )
        inset_dim = inventor.add_aligned_dimension(
            sketch,
            left_outer,
            left_inner,
            inventor.create_point2d(
                midpoint.X - ux * (outer - 1.6) + nx * 2,
                midpoint.Y - uy * (outer - 1.6) + ny * 2,
            ),
        )
        offset_dim = inventor.add_aligned_dimension(
            sketch,
            offset_anchor.StartSketchPoint,
            offset_anchor.EndSketchPoint,
            inventor.create_point2d(
                midpoint.X - nx * offset_value / 2 + ux * 2,
                midpoint.Y - ny * offset_value / 2 + uy * 2,
            ),
        )
        long_dim.Parameter.Name = inventor.unique_parameter_name(
            f"Long_edge_{index}", inventor.parameters
        )
        point_distance_dim.Parameter.Name = inventor.unique_parameter_name(
            PARAMETERS.point_distance, inventor.parameters
        )
        point_distance_dim.Parameter.Expression = (
            f"floor(({long_dim.Parameter.Name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
        )
        inset_dim.Parameter.Expression = "32 mm"
        offset_dim.Parameter.Expression = offset_param
    inventor.hide_sketch_dimensions(sketch)
    return (sketch, (left_outer, right_outer))


def plane_intersection_model_line(inventor, face, reference_face):
    face_plane = inventor.plane_geometry(face)
    reference_plane = inventor.plane_geometry(reference_face)
    n1 = point_tuple(reference_plane.Normal)
    n2 = point_tuple(face_plane.Normal)
    p1 = point_tuple(reference_plane.RootPoint)
    p2 = point_tuple(face_plane.RootPoint)
    direction = vector_cross(n1, n2)
    direction_length2 = vector_dot(direction, direction)
    if direction_length2 < 1e-08:
        return (None, None)
    c1 = vector_dot(n1, p1)
    c2 = vector_dot(n2, p2)
    n2_cross_d = vector_cross(n2, direction)
    d_cross_n1 = vector_cross(direction, n1)
    point = tuple(
        (
            (c1 * n2_cross_d[index] + c2 * d_cross_n1[index]) / direction_length2
            for index in range(3)
        )
    )
    return (point, direction)


def second_sketch_reference_lines(inventor, sketch, start, ux, uy, min_distance, max_distance):
    """Find projected boundary lines for the offset and the two ends of the axis."""
    reference = left = right = None
    tolerance = 1e-05
    for line in inventor.sketch_lines(sketch, construction=False):
        a = line.StartSketchPoint.Geometry
        b = line.EndSketchPoint.Geometry
        along = [(p.X - start.X) * ux + (p.Y - start.Y) * uy for p in (a, b)]
        across = [-(p.X - start.X) * uy + (p.Y - start.Y) * ux for p in (a, b)]
        if (
            max((abs(value) for value in across)) < tolerance
            and abs(along[1] - along[0]) > tolerance
        ):
            reference = line
        if max((abs(value - min_distance) for value in along)) < tolerance:
            left = line
        if max((abs(value - max_distance) for value in along)) < tolerance:
            right = line
    if reference is None or left is None or right is None:
        raise ValueError("Cannot bind second sketch: intersection edge or side edges not found.")
    return (reference, left, right)


def vector_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vector_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def point_tuple(point):
    return (point.X, point.Y, point.Z)
