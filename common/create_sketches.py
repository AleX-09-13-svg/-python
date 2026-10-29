import math
import sys
from time import perf_counter
from common.reference_edge import edge_endpoints, same_point, end_lines_for_reference, snapshot_lines
from common.cached_sketch import CachedSketchService

from common.constants import (
    PARAMETERS,
    DRILLING_SKETCH_PREFIX,
    GRID_STEP_CM,
)


KEEP_EXCEL_PARAMS_NAME = "Keep_Excel_Params"
NO_UPDATE_ARG = "--no-update"
SKETCH_YELLOW_RGB = (255, 220, 0)


def log_stage(label, started):
    print(f"    {label}: {perf_counter() - started:.2f}s", flush=True)
    return perf_counter()


def project_new_face_lines(inventor, sketch, face, control_edge=None, edge_cache=None):
    """Получить созданные проекции напрямую, без обхода всего эскиза."""
    started = perf_counter()
    lines = []
    control_line = None
    if edge_cache is None:
        control_points = edge_endpoints(control_edge) if control_edge is not None else None
        records = ((edge, edge.GeometryType, None) for edge in inventor.face_edges(face))
    else:
        control_points = edge_cache.endpoints(control_edge) if control_edge is not None else None
        records = ((r.edge, r.kind, r.endpoints) for r in edge_cache.face(face))
    for edge, kind, endpoints in records:
        projected = inventor.project_entity_to_sketch(sketch, edge, ignore_errors=False)
        # Типы прямого ребра уже используются в библиотеке Inventor Service.
        if kind in (5122, 5123):
            if projected is None:
                raise RuntimeError("Не удалось спроецировать прямое ребро грани.")
            lines.append(projected)
            if control_points is not None:
                a, b = endpoints if endpoints is not None else edge_endpoints(edge)
                c, d = control_points
                if ((same_point(a, c) and same_point(b, d)) or
                        (same_point(a, d) and same_point(b, c))):
                    control_line = projected
    if control_edge is not None and control_line is None:
        raise ValueError("В проекциях первой грани не найдено общее ребро.")
    log_stage("Проекция рёбер", started)
    return lines, control_line


def drilling_point_distance(length, edge_offset):
    distance = math.floor((length - edge_offset * 2) / GRID_STEP_CM) * GRID_STEP_CM
    if edge_offset < 0 or distance < GRID_STEP_CM * 2:
        raise ValueError(
            "Недостаточно места для присадки: "
            f"длина {length * 10:g} мм, отступ {edge_offset * 10:g} мм. "
            "Расстояние между крайними точками должно быть не меньше 64 мм."
        )
    return distance


def create_constrained_drilling_points(inventor, sketch, center, ux, uy, distance,
                                      axis, symmetry_axis, compact=False, center_xy=None):
    cx, cy = center_xy if center_xy is not None else (center.X, center.Y)
    if compact and distance < GRID_STEP_CM * 3:
        # Два внутренних отверстия со шагом 32 мм попадают в один центр.
        # Создаём один объект точки, без дублирующих зависимостей и размеров.
        outer = distance / 2
        left = inventor.add_sketch_point(
            sketch, inventor.create_point2d(cx - ux * outer, cy - uy * outer)
        )
        right = inventor.add_sketch_point(
            sketch, inventor.create_point2d(cx + ux * outer, cy + uy * outer)
        )
        middle = inventor.add_sketch_point(sketch, center)
        for point in (left, right, middle):
            inventor.add_coincident_constraint(sketch, point, axis)
        inventor.add_coincident_constraint(sketch, middle, symmetry_axis)
        inventor.add_symmetry_constraint(sketch, left, right, symmetry_axis)
        print("    Компактная присадка: две стяжки и один центральный шкант", flush=True)
        return left, right, middle, middle, middle, outer
    if isinstance(inventor, CachedSketchService):
        points = inventor.create_drilling_points(sketch, center, ux, uy, distance, center_xy=(cx, cy))
    else:
        points = inventor.create_drilling_points(sketch, center, ux, uy, distance)
    inventor.constrain_drilling_points(sketch, axis, symmetry_axis, points)
    return points


def should_update_document():
    return NO_UPDATE_ARG not in [arg.strip().lower() for arg in sys.argv[1:]]


def ensure_parameters(inventor, names):
    missing = inventor.missing_parameters(names)
    if not missing:
        return True

    message = "Missing Inventor parameters:\n" + "\n".join(missing)
    show_message = getattr(inventor, "show_message", None)
    if show_message is not None:
        show_message("Missing parameters", message, icon="warning")

    print(message)
    return False


def ensure_sketch_parameters(inventor):
    return ensure_parameters(
        inventor,
        (
            PARAMETERS.edge_offset,
        ),
    )


def edge_offset_param_for_length(long_edge_length):
    return PARAMETERS.edge_offset


def _line_length_squared(inventor, line):
    try:
        return inventor.line_length_squared(line)
    except AttributeError:
        start = line.StartSketchPoint.Geometry
        end = line.EndSketchPoint.Geometry
        dx = end.X - start.X
        dy = end.Y - start.Y
        return dx * dx + dy * dy


def _sketch_has_drilling_axes(inventor, sketch):
    return len(inventor.sketch_lines(sketch, construction=True)) >= 2


def _offset_sketch_on_face_plane(inventor, face, sketch_prefix, offset_value):
    return inventor.sketch_on_face_plane(
        face,
        prefix=sketch_prefix,
        offsets=[offset_value],
    )


def _add_offset_sketch(inventor, face, sketch_prefix, group_index, offset_param):
    offset_value = inventor.parameter_value(offset_param, 0)
    plane_name = f"{sketch_prefix}_OffsetPlane_{group_index}"
    sketch_name = f"{sketch_prefix}_{group_index}"
    print(
        f"  creating offset sketch plane: {plane_name}, "
        f"offset={offset_param} ({offset_value})",
        flush=True,
    )
    work_plane = inventor.add_offset_work_plane(
        face,
        offset_param,
        name=plane_name,
        visible=False,
    )
    sketch = inventor.add_sketch(work_plane)
    sketch.Name = inventor.unique_sketch_name(sketch_name)
    return sketch


def _create_drilling_sketch_fixed(
    inventor,
    sketch,
    face,
    index,
    edge_offset_param,
    project_edges=True,
    compact_points=False,
    edge_offset_value=None,
    projected_lines=None,
    runtime_names=None,
    control_line=None,
    add_side_reference=True,
):
    print(
        f"  build drilling geometry: sketch={getattr(sketch, 'Name', '<unknown>')}, "
        f"project_edges={project_edges}",
        flush=True,
    )
    started = perf_counter()
    if projected_lines is not None:
        lines = projected_lines
    else:
        first_new_line = inventor.sketch_line_count(sketch)
        print("    lines before projection:", first_new_line, flush=True)
        if project_edges:
            inventor.project_face_edges(sketch, face)
        lines = inventor.sketch_lines_for_face(sketch, face, first_new_line)
        if len(lines) < 2:
            lines = inventor.sketch_lines_for_face(sketch, face, 0)
    print("    face lines found:", len(lines), flush=True)

    if len(lines) < 2:
        print("    skipped: less than 2 face lines", flush=True)
        return False

    control_length = None
    if control_line is None:
        lengths = sorted(
            ((_line_length_squared(inventor, line), line) for line in lines),
            key=lambda item: item[0],
        )
        (short1_length2, short1), (short2_length2, short2) = lengths[:2]
    else:
        geometries = snapshot_lines(lines)
        short1, short2 = end_lines_for_reference(control_line, lines, geometries=geometries)
        short1_length2 = geometries[id(short1)].length_squared
        short2_length2 = geometries[id(short2)].length_squared
        control_length = geometries[id(control_line)].length_squared ** 0.5
        if isinstance(inventor, CachedSketchService):
            inventor.geometries.update(geometries)
    print(
        "    short edge lengths:",
        round(short1_length2 ** 0.5, 4),
        round(short2_length2 ** 0.5, 4),
        flush=True,
    )
    started = log_stage("Подготовка геометрии", started)
    axes = inventor.create_construction_axes(sketch, short1, short2)
    cx, cy = axes[2].X, axes[2].Y
    _, _, _, long_edge_length, _, _, _, _ = axes
    if control_length is not None:
        long_edge_length = control_length
    print("    long edge length:", round(long_edge_length, 4), flush=True)
    started = log_stage("Построение осей", started)

    if callable(edge_offset_param):
        edge_offset_param = edge_offset_param(long_edge_length)
    elif edge_offset_param is None:
        edge_offset_param = edge_offset_param_for_length(long_edge_length)

    if edge_offset_value is None:
        edge_offset_value = inventor.parameter_value(edge_offset_param, 10)
    print(
        "    edge offset:",
        edge_offset_param,
        "=",
        round(edge_offset_value, 4) if isinstance(edge_offset_value, (int, float)) else edge_offset_value,
        flush=True,
    )
    point_distance_value = drilling_point_distance(long_edge_length, edge_offset_value)
    print("    point distance:", round(point_distance_value, 4), flush=True)

    points = create_constrained_drilling_points(
        inventor,
        sketch,
        axes[2],
        axes[4],
        axes[5],
        point_distance_value,
        axes[0],
        axes[1],
        compact=compact_points,
        center_xy=(cx, cy),
    )
    if add_side_reference:
        inventor.add_side_plane_reference_line(sketch, axes[0], lines)
    started = log_stage("Точки и зависимости", started)

    axis, _, center, _, ux, uy, nx, ny = axes
    left_outer, right_outer, left_inner, _, _, outer = points
    long_dim = inventor.add_aligned_dimension(
        sketch,
        (control_line if control_line is not None else axis).StartSketchPoint,
        (control_line if control_line is not None else axis).EndSketchPoint,
        inventor.create_point2d(cx + nx * 4, cy + ny * 4),
        True,
    )
    point_distance_dim = inventor.add_aligned_dimension(
        sketch,
        right_outer,
        left_outer,
        inventor.create_point2d(cx + nx * 2, cy + ny * 2),
    )
    if left_inner is not points[4]:
        inset_dim = inventor.add_aligned_dimension(
            sketch,
            left_outer,
            left_inner,
            inventor.create_point2d(
                cx - ux * (outer - 1.6) + nx * 2,
                cy - uy * (outer - 1.6) + ny * 2,
            ),
        )
        inset_dim.Parameter.Expression = "32 mm"

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
    log_stage("Размеры и имена параметров", started)

    print("    drilling geometry created", flush=True)
    return points


def create_sketches_for_faces(
    inventor,
    component_definition,
    faces,
    sketch_prefix,
    edge_offset_param,
    sketch_label,
    face_label,
    use_offset_plane=False,
    offset_param=PARAMETERS.frame_thickness,
    reuse_existing=True,
    point_jobs=None,
    edge_offset_value=None,
    runtime_names=None,
    direct_projection=False,
    reference_edges=None,
    use_cached_operations=False,
    edge_cache=None,
):
    if direct_projection and reuse_existing:
        raise ValueError("Прямая проекция доступна только для новых эскизов.")
    if edge_offset_param is None:
        edge_offset_param = edge_offset_param_for_length

    groups = inventor.group_faces_by_plane(faces)

    print(f"{face_label} faces:", len(faces))
    print(f"{sketch_label} sketch planes:", len(groups))

    count = 0
    created_sketches = 0
    reused_sketches = 0
    skipped_faces = 0
    sketches = []

    for group_index, group in enumerate(groups, start=1):
        if not reuse_existing:
            sketch = None
        elif use_offset_plane:
            offset_value = inventor.parameter_value(offset_param, 0)
            sketch = _offset_sketch_on_face_plane(
                inventor,
                group[0],
                sketch_prefix,
                offset_value,
            )
        else:
            sketch = inventor.sketch_on_face_plane(group[0], prefix=sketch_prefix)

        if sketch is None:
            if use_offset_plane:
                sketch = _add_offset_sketch(
                    inventor,
                    group[0],
                    sketch_prefix,
                    group_index,
                    offset_param,
                )
            else:
                sketch = inventor.add_sketch(group[0])
                base_name = f"{sketch_prefix}_{group_index}"
                sketch.Name = (runtime_names.sketch(base_name) if runtime_names is not None
                               else inventor.unique_sketch_name(base_name))
            created_sketches += 1
        else:
            reused_sketches += 1
            print(f"Using existing {sketch_label} sketch on plane:", sketch.Name)

        sketches.append(sketch)

        if inventor.set_sketch_color_rgb(
            sketch,
            SKETCH_YELLOW_RGB,
            include_entities=False,
        ):
            print(f"  {sketch_label} sketch color set:", sketch.Name)
        else:
            print(f"  {sketch_label} sketch color not set:", sketch.Name)

        group_processed = 0
        sketch_service = CachedSketchService(inventor, sketch) if use_cached_operations else inventor
        with inventor.deferred_sketch_updates(sketch):
            for face in group:
                has_geometry = (False if direct_projection else
                                inventor.sketch_has_geometry_for_face(sketch, face))
                has_axes = has_geometry and _sketch_has_drilling_axes(inventor, sketch)
                print(
                    f"  face state: has_geometry={has_geometry}, has_drilling_axes={has_axes}",
                    flush=True,
                )
                if has_geometry and has_axes:
                    skipped_faces += 1
                    print(f"  {sketch_label} face geometry already exists, skipped")
                    continue

                projected_lines = control_line = None
                if direct_projection:
                    control_edge = reference_edges.get(id(face)) if reference_edges else None
                    projected_lines, control_line = project_new_face_lines(
                        inventor, sketch, face, control_edge, edge_cache=edge_cache,
                    )
                points = _create_drilling_sketch_fixed(
                    sketch_service,
                    sketch,
                    face,
                    count + 1,
                    edge_offset_param,
                    project_edges=not has_geometry,
                    compact_points=point_jobs is not None,
                    edge_offset_value=edge_offset_value,
                    projected_lines=projected_lines,
                    runtime_names=runtime_names,
                    control_line=control_line,
                    add_side_reference=not direct_projection,
                )
                if points:
                    count += 1
                    group_processed += 1
                    if point_jobs is not None:
                        point_jobs.append({
                            "sketch": sketch,
                            "colored_face": face,
                            "outer_points": [points[0], points[1]],
                            "inner_points": ([points[2]] if points[2] is points[3]
                                             else [points[2], points[3]]),
                        })

            solve_started = perf_counter()
        log_stage("Обновление решателя эскиза", solve_started)
        if group_processed:
            inventor.hide_sketch_dimensions(sketch)

    print(f"{sketch_label} faces processed:", count)
    print(f"{sketch_label} sketches created:", created_sketches)
    print(f"{sketch_label} sketches reused:", reused_sketches)
    print(f"{sketch_label} faces skipped:", skipped_faces)

    return sketches
