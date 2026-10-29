# Геометрия второго эскиза: пересечение плоскостей, смещённая ось, точки и размеры.
from common.constants import DRILLING_SKETCH_PREFIX, PARAMETERS
import common.create_sketches as create_sketches
from common.reference_edge import snapshot_lines
from common.cached_sketch import CachedSketchService
import math


def create_offset_drilling_sketch(
    inventor,
    face,
    reference_face,
    index,
    offset_param,
    edge_offset_param,
    offset_value,
    edge_offset_value,
    intersection_line=None,
    runtime_names=None,
    control_edge=None,
    use_cached_operations=False,
    edge_cache=None,
):
    # Найти направление пересечения плоскостей.
    if intersection_line is None:
        intersection_line = plane_intersection_model_line(inventor, face, reference_face)
    intersection_point, intersection_direction = intersection_line
    if intersection_point is None:
        return None
    sketch = inventor.add_sketch(face)
    base_name = f"{DRILLING_SKETCH_PREFIX}_{index}"
    sketch.Name = (runtime_names.sketch(base_name) if runtime_names is not None
                   else inventor.unique_sketch_name(base_name))
    inventor.set_sketch_color_rgb(sketch, create_sketches.SKETCH_YELLOW_RGB, include_entities=False)
    if use_cached_operations:
        inventor = CachedSketchService(inventor, sketch)
    with inventor.deferred_sketch_updates(sketch):
        projected_lines = reference_line = None
        if control_edge is None:
            inventor.project_face_edges(sketch, face, ignore_errors=False)
        else:
            projected_lines, reference_line = create_sketches.project_new_face_lines(
                inventor, sketch, face, control_edge, edge_cache=edge_cache,
            )
        geometries = snapshot_lines(projected_lines) if projected_lines is not None else None
        start = inventor.model_to_sketch_point(sketch, inventor.create_point3d(*intersection_point))
        end = inventor.model_to_sketch_point(
            sketch,
            inventor.create_point3d(
                intersection_point[0] + intersection_direction[0],
                intersection_point[1] + intersection_direction[1],
                intersection_point[2] + intersection_direction[2],
            ),
        )
        start_x, start_y = start.X, start.Y
        end_x, end_y = end.X, end.Y
        direction_length = math.hypot(end_x - start_x, end_y - start_y)
        if direction_length == 0:
            return None
        ux = (end_x - start_x) / direction_length
        uy = (end_y - start_y) / direction_length
        nx = -uy
        ny = ux
        face_points = None
        if use_cached_operations and reference_line is not None:
            # Достаточно одной внутренней точки, чтобы выбрать сторону от ребра.
            inside = inventor.model_to_sketch_point(sketch, face.PointOnFace)
            center_x, center_y = inside.X, inside.Y
        else:
            face_points = [
                (point.X, point.Y) for point in inventor.face_vertex_points_in_sketch(face, sketch)
            ]
            if not face_points:
                raise ValueError("Face has no vertices")
            center_x = sum(x for x, y in face_points) / len(face_points)
            center_y = sum(y for x, y in face_points) / len(face_points)
        if (center_x - start_x) * nx + (center_y - start_y) * ny < 0:
            nx = -nx
            ny = -ny
        # Сместить ось к центру грани на значение параметра offset_param.
        base_x = start_x + nx * offset_value
        base_y = start_y + ny * offset_value
        if reference_line is None:
            reference_points = face_points
        else:
            reference_data = geometries[id(reference_line)]
            reference_points = [reference_data.start, reference_data.end]
        distances = [(x - base_x) * ux + (y - base_y) * uy for x, y in reference_points]
        min_distance = min(distances)
        max_distance = max(distances)
        length = max_distance - min_distance
        if length <= 0:
            return None
        reference_line, left_side, right_side = second_sketch_reference_lines(
            inventor, sketch, start, ux, uy, min_distance, max_distance,
            lines=projected_lines, reference_line=reference_line,
            geometries=geometries,
        )

        # Координаты точки на смещённой оси по расстоянию вдоль неё.
        def point_on_axis(distance):
            return inventor.create_point2d(base_x + ux * distance, base_y + uy * distance)

        middle_distance = (min_distance + max_distance) / 2
        mid_x = base_x + ux * middle_distance
        mid_y = base_y + uy * middle_distance
        midpoint = inventor.create_point2d(mid_x, mid_y)
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
            inventor.create_point2d(mid_x - nx * offset_value, mid_y - ny * offset_value),
            midpoint,
            construction=True,
        )
        inventor.add_coincident_constraint(
            sketch, offset_anchor.StartSketchPoint, reference_line, ignore_errors=False
        )
        inventor.add_midpoint_constraint(
            sketch, offset_anchor.EndSketchPoint, axis, ignore_errors=False
        )
        inventor.add_perpendicular_constraint(sketch, offset_anchor, axis, ignore_errors=False)
        # Одна линия управляет отступом и служит осью симметрии точек.
        symmetry_axis = offset_anchor
        point_distance_value = create_sketches.drilling_point_distance(length, edge_offset_value)
        # На второй плоскости нужны только два центра отверстий чашек.
        outer = point_distance_value / 2
        left_outer = inventor.add_sketch_point(
            sketch, inventor.create_point2d(mid_x - ux * outer, mid_y - uy * outer)
        )
        right_outer = inventor.add_sketch_point(
            sketch, inventor.create_point2d(mid_x + ux * outer, mid_y + uy * outer)
        )
        for point in (left_outer, right_outer):
            inventor.add_coincident_constraint(sketch, point, axis)
        inventor.add_symmetry_constraint(sketch, left_outer, right_outer, symmetry_axis)
        # Добавить размеры и связать их с параметрами модели.
        long_dim = inventor.add_aligned_dimension(
            sketch,
            reference_line.StartSketchPoint,
            reference_line.EndSketchPoint,
            inventor.create_point2d(mid_x + nx * 4, mid_y + ny * 4),
            True,
        )
        point_distance_dim = inventor.add_aligned_dimension(
            sketch,
            right_outer,
            left_outer,
            inventor.create_point2d(mid_x + nx * 2, mid_y + ny * 2),
        )
        offset_dim = inventor.add_aligned_dimension(
            sketch,
            offset_anchor.StartSketchPoint,
            offset_anchor.EndSketchPoint,
            inventor.create_point2d(
                mid_x - nx * offset_value / 2 + ux * 2,
                mid_y - ny * offset_value / 2 + uy * 2,
            ),
        )
        long_parameter = long_dim.Parameter
        distance_parameter = point_distance_dim.Parameter
        if runtime_names is None:
            long_name = inventor.unique_parameter_name(f"Long_edge_{index}", inventor.parameters)
            distance_name = inventor.unique_parameter_name(PARAMETERS.point_distance, inventor.parameters)
        else:
            long_name = runtime_names.parameter(f"Long_edge_{index}")
            distance_name = runtime_names.parameter(PARAMETERS.point_distance)
        long_parameter.Name = long_name
        distance_parameter.Name = distance_name
        distance_parameter.Expression = (
            f"floor(({long_name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
        )
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


def second_sketch_reference_lines(inventor, sketch, start, ux, uy, min_distance, max_distance,
                                  lines=None, reference_line=None, geometries=None):
    """Find projected boundary lines for the offset and the two ends of the axis."""
    reference = reference_line
    left = right = None
    tolerance = 1e-04  # см: допуск 0.001 мм на преобразование координат.
    # На этом этапе в эскизе есть только проекции. Inventor может пометить
    # проекционные линии Construction=True; они также годятся для привязки.
    if lines is None:
        lines = inventor.sketch_lines(sketch)
    if geometries is None:
        geometries = snapshot_lines(lines)
    start_x, start_y = start.X, start.Y
    print("    second sketch projected lines:", len(lines), flush=True)
    projected_spans = []
    for line in lines:
        data = geometries[id(line)]
        a, b = data.start, data.end
        along = [(p[0] - start_x) * ux + (p[1] - start_y) * uy for p in (a, b)]
        across = [-(p[0] - start_x) * uy + (p[1] - start_y) * ux for p in (a, b)]
        projected_spans.append((along, across))
        if (
            max((abs(value) for value in across)) < tolerance
            and abs(along[1] - along[0]) > tolerance
        ):
            if reference_line is None:
                reference = line
        if max((abs(value - min_distance) for value in along)) < tolerance:
            left = line
        if max((abs(value - max_distance) for value in along)) < tolerance:
            right = line
    if reference_line is not None:
        # У широкой грани общее ребро может занимать лишь часть контура.
        # Привязать концы оси к перпендикулярам через концы именно этого ребра.
        endpoints = (reference.StartSketchPoint, reference.EndSketchPoint)
        endpoints = sorted(endpoints, key=lambda p: (p.Geometry.X - start.X) * ux
                           + (p.Geometry.Y - start.Y) * uy)

        def end_reference(point):
            geometry = point.Geometry
            line = inventor.add_sketch_line(
                sketch, geometry,
                inventor.create_point2d(geometry.X - uy, geometry.Y + ux),
                construction=True,
            )
            inventor.add_coincident_constraint(sketch, line.StartSketchPoint, point, ignore_errors=False)
            inventor.add_perpendicular_constraint(sketch, line, reference, ignore_errors=False)
            return line

        if left is None:
            left = end_reference(endpoints[0])
        if right is None:
            right = end_reference(endpoints[1])
    if reference is None or left is None or right is None:
        print(
            "    second sketch expected end positions:", min_distance, max_distance,
            "projected spans (along, across):", projected_spans, flush=True,
        )
        missing = []
        if reference is None:
            missing.append("ребро пересечения выбранных плоскостей")
        if left is None:
            missing.append("левое торцевое ребро")
        if right is None:
            missing.append("правое торцевое ребро")
        raise ValueError(
            "Не удалось привязать второй эскиз: не найдены " + ", ".join(missing)
            + f". Проекционных отрезков: {len(lines)}."
        )
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
