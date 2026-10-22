from dataclasses import dataclass
from time import perf_counter

from common.constants import (
    DRILLING_SKETCH_PREFIX,
    EDGE_OFFSET_DRAWER_PARAM,
    EDGE_OFFSET_FRAME_PARAM,
    GRID_STEP_CM,
    POINT_DISTANCE_PARAM,
)
from common.inventor_service_path import ensure_inventor_service_path
from common.settings import drawer_edge_max_cm, hole_direction, setting

ensure_inventor_service_path()

from workflows import confirmat as _confirmat


STIAJKA_CUP_SKETCH_PREFIX = "StiajkaCupSketch"
STIAJKA_CUP_SKETCH_RGB = (0, 180, 255)
STIAJKA_CUP_DRAWER_EDGE_MAX_CM = 30.0


@dataclass
class StiajkaCupSketchJob:
    index: int
    front_face: object
    end_face: object


@dataclass
class StiajkaPlan:
    end_faces: list
    front_faces: list
    cup_jobs: list
    skipped_front_faces: int = 0


def stiajka_setting(*keys, default=None):
    return setting("stiajka", *keys, default=default)


def stiajka_parameter(name, default):
    return stiajka_setting("parameters", name, default=default)


def stiajka_hole(name):
    return stiajka_setting(name, default={})


def stiajka_direction(hole_settings):
    return hole_direction(hole_settings.get("direction", "positive"))


def unique_names(names):
    result = []
    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def stiajka_required_parameter_names():
    names = [
        stiajka_parameter("diameter", "Стяжка_D"),
        stiajka_parameter("depth", "Стяжка_h"),
        stiajka_parameter("offset", "Стяжка_отступ"),
    ]
    for key in ("outer_main", "outer_secondary", "inner_short", "inner_long"):
        settings = stiajka_hole(key)
        names.append(settings.get("diameter"))
        names.append(settings.get("depth"))
    cup = stiajka_hole("cup")
    names.append(cup.get("diameter_parameter"))
    names.append(cup.get("depth_parameter"))
    return unique_names(names)


def log_elapsed(label, started):
    elapsed = perf_counter() - started
    print(f"  {label}: {elapsed:.2f}s", flush=True)
    return perf_counter()


def edge_offset_param_for_length(long_edge_length):
    if long_edge_length <= drawer_edge_max_cm():
        return EDGE_OFFSET_DRAWER_PARAM
    return EDGE_OFFSET_FRAME_PARAM


def cup_edge_offset_param_for_length(long_edge_length):
    if long_edge_length <= STIAJKA_CUP_DRAWER_EDGE_MAX_CM:
        return EDGE_OFFSET_DRAWER_PARAM
    return EDGE_OFFSET_FRAME_PARAM


def split_stiajka_faces(inventor, faces):
    groups = inventor.group_faces_by_plane(faces)
    if not groups:
        return None, None

    end_group_index, end_faces = max(
        enumerate(groups),
        key=lambda item: (
            inventor.adjacent_face_count(
                item[1],
                [
                    face
                    for group_index, group in enumerate(groups)
                    if group_index != item[0]
                    for face in group
                ],
            ),
            -inventor.faces_area(item[1]),
        ),
    )
    front_faces = [
        face
        for group_index, group in enumerate(groups)
        if group_index != end_group_index
        for face in group
    ]
    print(
        "Stiajka end plane:",
        f"faces={len(end_faces)}",
        f"area={inventor.faces_area(end_faces):.4f}",
    )
    print(
        "Stiajka front planes:",
        f"planes={len(groups) - 1}",
        f"faces={len(front_faces)}",
        f"area={inventor.faces_area(front_faces):.4f}",
    )
    return end_faces, front_faces


def matching_end_face(inventor, front_face, end_faces):
    candidates = [
        end_face
        for end_face in end_faces
        if shared_face_edge(inventor, front_face, end_face) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda face: inventor.face_area(face) or 0)


def create_selected_stiajka_plan(inventor, faces):
    end_faces, front_faces = split_stiajka_faces(inventor, faces)
    if not end_faces:
        return None

    cup_jobs = []
    skipped_front_faces = 0
    for index, front_face in enumerate(front_faces, start=1):
        end_face = matching_end_face(inventor, front_face, end_faces)
        if end_face is None:
            skipped_front_faces += 1
            continue
        cup_jobs.append(StiajkaCupSketchJob(index, front_face, end_face))

    print(
        "Stiajka plan:",
        f"end_faces={len(end_faces)}",
        f"front_faces={len(front_faces)}",
        f"cup_jobs={len(cup_jobs)}",
        f"skipped_front_faces={skipped_front_faces}",
    )
    return StiajkaPlan(end_faces, front_faces, cup_jobs, skipped_front_faces)


def shared_face_edge(inventor, face1, face2):
    edge = inventor.shared_face_edge(face1, face2)
    if edge is not None:
        return edge

    candidates = []
    for front_edge in inventor.face_edges(face1):
        for end_edge in inventor.face_edges(face2):
            try:
                if point_to_edge_distance2(front_edge.StartVertex.Point, end_edge) < 0.0001:
                    candidates.append(front_edge)
                    break
            except Exception:
                continue
    if not candidates:
        return None
    return max(candidates, key=edge_length2)


def edge_end_points(edge):
    try:
        return edge.StartVertex.Point, edge.StopVertex.Point
    except Exception:
        return edge.Vertices.Item(1).Point, edge.Vertices.Item(2).Point


def edge_length2(edge):
    start, end = edge_end_points(edge)
    return (end.X - start.X) ** 2 + (end.Y - start.Y) ** 2 + (end.Z - start.Z) ** 2


def point_to_segment_distance2(point, start, end):
    dx = end.X - start.X
    dy = end.Y - start.Y
    dz = end.Z - start.Z
    length2 = dx * dx + dy * dy + dz * dz
    if length2 == 0:
        return (
            (point.X - start.X) ** 2
            + (point.Y - start.Y) ** 2
            + (point.Z - start.Z) ** 2
        )

    t = (
        (point.X - start.X) * dx
        + (point.Y - start.Y) * dy
        + (point.Z - start.Z) * dz
    ) / length2
    t = max(0, min(1, t))
    x = start.X + dx * t
    y = start.Y + dy * t
    z = start.Z + dz * t
    return (point.X - x) ** 2 + (point.Y - y) ** 2 + (point.Z - z) ** 2


def point_to_edge_distance2(point, edge):
    start, end = edge_end_points(edge)
    return point_to_segment_distance2(point, start, end)


def vector_length2d(dx, dy):
    return (dx * dx + dy * dy) ** 0.5


def point_distance_along_edge(point, edge_start, edge_end):
    dx = edge_end.X - edge_start.X
    dy = edge_end.Y - edge_start.Y
    dz = edge_end.Z - edge_start.Z
    length2 = dx * dx + dy * dy + dz * dz
    if length2 == 0:
        return 0
    t = (
        (point.X - edge_start.X) * dx
        + (point.Y - edge_start.Y) * dy
        + (point.Z - edge_start.Z) * dz
    ) / length2
    t = max(0, min(1, t))
    return (length2**0.5) * t


def axis_stiajka_points(axis_data):
    points = axis_data["points"]
    if len(points) < 5:
        return [], []
    return [points[0][1], points[-1][1]], [points[1][1], points[-2][1]]


def drilling_sketch_outer_model_points_on_face(inventor, face):
    points = []
    for sketch in inventor.sketches_by_prefix(DRILLING_SKETCH_PREFIX):
        try:
            if not inventor.same_plane_entity(sketch.PlanarEntity, face):
                continue
        except Exception:
            continue

        face_bounds = _confirmat.face_bounds_cache(inventor, sketch, [face])
        axes = _confirmat.construction_axes_data(
            inventor,
            sketch,
            _confirmat.sketch_points_data(sketch, inventor),
            face_bounds or None,
        )
        for axis in axes:
            outer_points, _ = axis_stiajka_points(axis)
            for point in outer_points:
                try:
                    points.append(sketch.SketchToModelSpace(point.Geometry))
                except Exception:
                    continue
    return points


def cup_distances_from_outer_points(inventor, end_face, shared_edge, length):
    edge_start, edge_end = edge_end_points(shared_edge)
    distances = [
        point_distance_along_edge(point, edge_start, edge_end)
        for point in drilling_sketch_outer_model_points_on_face(inventor, end_face)
    ]
    distances = sorted({round(distance, 6) for distance in distances})
    if len(distances) < 2:
        return None
    return max(0, min(length, distances[0])), max(0, min(length, distances[-1]))


def front_reference_edge_near_outer_points(inventor, front_face, end_face, fallback_edge):
    points = drilling_sketch_outer_model_points_on_face(inventor, end_face)
    if not points:
        return fallback_edge

    best_edge = fallback_edge
    best_score = None
    for edge in inventor.face_edges(front_face):
        try:
            score = sum(point_to_edge_distance2(point, edge) for point in points)
        except Exception:
            continue
        if best_score is None or score < best_score:
            best_edge = edge
            best_score = score
    return best_edge


def unique_parameter_name(inventor, base):
    try:
        return inventor.unique_parameter_name(base, inventor.parameters)
    except Exception:
        name = base
        index = 1
        while True:
            try:
                inventor.parameters.Item(name)
                index += 1
                name = f"{base}_{index}"
            except Exception:
                return name


def add_stiajka_cup_sketch_dimensions(
    inventor,
    sketch,
    reference_line,
    offset_line,
    cup_points,
    index,
    offset_expression,
):
    start = reference_line.StartSketchPoint.Geometry
    end = reference_line.EndSketchPoint.Geometry
    dx = end.X - start.X
    dy = end.Y - start.Y
    length = vector_length2d(dx, dy)
    if length == 0:
        return

    nx = -dy / length
    ny = dx / length
    center = inventor.create_point2d((start.X + end.X) / 2, (start.Y + end.Y) / 2)

    long_dim = inventor.add_aligned_dimension(
        sketch,
        reference_line.StartSketchPoint,
        reference_line.EndSketchPoint,
        inventor.create_point2d(center.X + nx * 2, center.Y + ny * 2),
        True,
    )
    long_dim.Parameter.Name = unique_parameter_name(inventor, f"Long_edge_{index}")

    point_distance_dim = inventor.add_aligned_dimension(
        sketch,
        cup_points[0],
        cup_points[1],
        inventor.create_point2d(center.X + nx * 4, center.Y + ny * 4),
    )
    point_distance_dim.Parameter.Name = unique_parameter_name(inventor, POINT_DISTANCE_PARAM)
    edge_offset_param = cup_edge_offset_param_for_length(length)
    point_distance_dim.Parameter.Expression = (
        f"floor(({long_dim.Parameter.Name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
    )

    offset_dim = inventor.add_aligned_dimension(
        sketch,
        reference_line.StartSketchPoint,
        offset_line.StartSketchPoint,
        inventor.create_point2d(
            (
                reference_line.StartSketchPoint.Geometry.X
                + offset_line.StartSketchPoint.Geometry.X
            )
            / 2,
            (
                reference_line.StartSketchPoint.Geometry.Y
                + offset_line.StartSketchPoint.Geometry.Y
            )
            / 2,
        ),
    )
    offset_dim.Parameter.Expression = offset_expression

    anchor = offset_line.StartSketchPoint.Geometry
    point = cup_points[0].Geometry
    anchor_dim = inventor.add_aligned_dimension(
        sketch,
        offset_line.StartSketchPoint,
        cup_points[0],
        inventor.create_point2d(
            (anchor.X + point.X) / 2 + nx * 6,
            (anchor.Y + point.Y) / 2 + ny * 6,
        ),
    )
    anchor_dim.Parameter.Expression = (
        f"({long_dim.Parameter.Name} - {point_distance_dim.Parameter.Name}) / 2"
    )


def create_stiajka_cup_sketch(
    inventor,
    front_face,
    end_face,
    index=1,
    sketch=None,
    reuse_existing=True,
):
    if sketch is None and reuse_existing:
        sketch = inventor.sketch_on_face_plane(front_face, prefix=STIAJKA_CUP_SKETCH_PREFIX)
    if sketch is None:
        sketch = inventor.add_sketch(front_face)
        sketch.Name = inventor.unique_sketch_name(f"{STIAJKA_CUP_SKETCH_PREFIX}_{index}")
    else:
        print("Using existing stiajka cup sketch:", sketch.Name)
        if inventor.sketch_has_geometry_for_face(sketch, front_face):
            print("  stiajka cup face geometry already exists, skipped")
            return sketch

    inventor.set_sketch_color_rgb(sketch, STIAJKA_CUP_SKETCH_RGB, include_entities=False)
    shared_edge = shared_face_edge(inventor, front_face, end_face)
    if shared_edge is None:
        raise RuntimeError("selected faces do not share an edge")

    reference_edge = front_reference_edge_near_outer_points(
        inventor,
        front_face,
        end_face,
        shared_edge,
    )
    inventor.project_face_edges(sketch, front_face)
    reference_line = inventor.project_entity_to_sketch(
        sketch,
        reference_edge,
        construction=True,
        ignore_errors=False,
    )

    start = reference_line.StartSketchPoint.Geometry
    end = reference_line.EndSketchPoint.Geometry
    dx = end.X - start.X
    dy = end.Y - start.Y
    length = vector_length2d(dx, dy)
    if length == 0:
        raise RuntimeError("reference edge has zero length in sketch")

    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    midpoint = inventor.create_point2d((start.X + end.X) / 2, (start.Y + end.Y) / 2)
    face_center = inventor.face_center_in_sketch(front_face, sketch)
    outer_side = (face_center.X - midpoint.X) * nx + (face_center.Y - midpoint.Y) * ny
    if outer_side < 0:
        nx = -nx
        ny = -ny

    offset_parameter = stiajka_parameter("offset", "Стяжка_отступ")
    offset_value = inventor.parameter_value(
        offset_parameter,
        stiajka_setting("side_offset", default=3.4),
    )
    edge_offset_param = cup_edge_offset_param_for_length(length)
    edge_offset_value = inventor.parameter_value(edge_offset_param, 10)
    point_distances = cup_distances_from_outer_points(
        inventor,
        end_face,
        reference_edge,
        length,
    )
    if point_distances is None:
        point_distance_value = int((length - edge_offset_value * 2) / GRID_STEP_CM) * GRID_STEP_CM
        point_distance_value = max(point_distance_value, GRID_STEP_CM * 2)
        edge_offset = (length - point_distance_value) / 2
        point1_distance = edge_offset
        point2_distance = edge_offset + point_distance_value
    else:
        point1_distance, point2_distance = point_distances

    if point1_distance > point2_distance:
        point1_distance, point2_distance = point2_distance, point1_distance

    line_start = inventor.create_point2d(start.X + nx * offset_value, start.Y + ny * offset_value)
    line_end = inventor.create_point2d(end.X + nx * offset_value, end.Y + ny * offset_value)
    offset_line = inventor.add_sketch_line(sketch, line_start, line_end, construction=True)
    inventor.add_parallel_constraint(sketch, offset_line, reference_line)

    point1 = inventor.add_sketch_point(
        sketch,
        inventor.create_point2d(
            start.X + ux * point1_distance + nx * offset_value,
            start.Y + uy * point1_distance + ny * offset_value,
        ),
        hole_center=True,
    )
    point2 = inventor.add_sketch_point(
        sketch,
        inventor.create_point2d(
            start.X + ux * point2_distance + nx * offset_value,
            start.Y + uy * point2_distance + ny * offset_value,
        ),
        hole_center=True,
    )
    for point in (point1, point2):
        inventor.add_coincident_constraint(sketch, point, offset_line)

    add_stiajka_cup_sketch_dimensions(
        inventor,
        sketch,
        reference_line,
        offset_line,
        (point1, point2),
        index,
        offset_parameter,
    )
    inventor.hide_sketch_dimensions(sketch)
    print("  created stiajka cup sketch:", sketch.Name)
    return sketch


def cup_sketch_on_face_plane(inventor, sketches, face):
    for sketch in sketches:
        try:
            if inventor.same_plane_entity(sketch.PlanarEntity, face):
                return sketch
        except Exception:
            continue
    return None


def create_cup_sketches_for_plan(inventor, plan, reuse_existing=True):
    sketches = []
    sketch_names = set()
    for job in plan.cup_jobs:
        sketch = cup_sketch_on_face_plane(inventor, sketches, job.front_face)
        sketch = create_stiajka_cup_sketch(
            inventor,
            job.front_face,
            job.end_face,
            job.index,
            sketch=sketch,
            reuse_existing=reuse_existing,
        )
        sketch_name = getattr(sketch, "Name", id(sketch))
        if sketch_name in sketch_names:
            continue
        sketch_names.add(sketch_name)
        sketches.append(sketch)
    return sketches


def faces_on_sketch_plane(inventor, sketch, faces):
    try:
        sketch_plane = sketch.PlanarEntity
    except Exception:
        return []
    result = []
    for face in faces:
        try:
            if inventor.same_plane_entity(sketch_plane, face):
                result.append(face)
        except Exception:
            continue
    return result


def point_inside_sketch_bounds(x, y, bounds, tol=0.01):
    min_x, max_x, min_y, max_y = bounds
    return min_x - tol <= x <= max_x + tol and min_y - tol <= y <= max_y + tol


def colored_face_for_axis(inventor, sketch, axis_data, faces):
    for face in faces:
        try:
            bounds = inventor.face_bounds_in_sketch(face, sketch)
        except Exception:
            continue
        if point_inside_sketch_bounds(axis_data["mid_x"], axis_data["mid_y"], bounds):
            return face
    return None


def create_hole_batch(
    inventor,
    jobs,
    points_key,
    settings_key,
    default_diameter,
    default_depth,
    default_name,
    label,
    success_key=None,
):
    settings = stiajka_hole(settings_key)
    points = inventor.unique_points(point for job in jobs for point in job[points_key])
    if not points:
        return 0

    started = perf_counter()
    try:
        inventor.add_holes(
            points,
            diameter=settings.get("diameter", default_diameter),
            depth=settings.get("depth", default_depth),
            direction=stiajka_direction(settings),
            name=settings.get("feature_name", default_name),
        )
        if success_key:
            for job in jobs:
                job[success_key] = True
        print(f"  created {label} batch, points={len(points)}")
        log_elapsed(f"{label} batch elapsed", started)
        return 1
    except Exception as exc:
        print(f"  {label} batch failed:", exc)

    created = 0
    for job in jobs:
        try:
            inventor.add_holes(
                job[points_key],
                diameter=settings.get("diameter", default_diameter),
                depth=settings.get("depth", default_depth),
                direction=stiajka_direction(settings),
                name=settings.get("feature_name", default_name),
            )
            if success_key:
                job[success_key] = True
            created += 1
            print(f"  created {label}")
        except Exception as exc:
            print(f"  {label} failed:", exc)
    log_elapsed(f"{label} fallback elapsed", started)
    return created


def cup_hole_center_points(inventor, sketch):
    return inventor.unique_points(inventor.sketch_points(sketch, hole_center=True))


def create_cup_holes(inventor, points):
    cup = stiajka_hole("cup")
    if not points:
        return 0
    inventor.add_holes(
        points,
        diameter=cup.get("diameter_parameter", stiajka_parameter("diameter", "Стяжка_D")),
        depth=cup.get("depth_parameter", stiajka_parameter("depth", "Стяжка_h")),
        direction=stiajka_direction(cup),
        name=cup.get("feature_name", "Stiajka cup"),
    )
    print(f"  created cup feature with points: {len(points)}")
    return 1


def create_stiajka_features(
    inventor,
    sketches=None,
    colored_faces=None,
    cup_sketches=None,
    update_document=True,
):
    sketches = sketches or inventor.sketches_by_prefix(DRILLING_SKETCH_PREFIX)
    colored_faces = colored_faces or inventor.colored_faces("blue")
    created = 0

    print("Stiajka sketches found:", len(sketches))
    if cup_sketches is not None:
        print("Stiajka cup sketches found:", len(cup_sketches))

    all_axis_jobs = []
    for sketch in sketches:
        print("Sketch:", sketch.Name)
        inventor.try_share_sketch(sketch)
        sketch_colored_faces = faces_on_sketch_plane(inventor, sketch, colored_faces)
        print("  colored faces on sketch plane:", len(sketch_colored_faces))

        face_bounds = _confirmat.face_bounds_cache(inventor, sketch, sketch_colored_faces)
        axes = _confirmat.construction_axes_data(
            inventor,
            sketch,
            _confirmat.sketch_points_data(sketch, inventor),
            face_bounds or None,
        )
        print("  construction axes:", len(axes))

        for axis in axes:
            axis_colored_face = colored_face_for_axis(
                inventor,
                sketch,
                axis,
                sketch_colored_faces,
            )
            if axis_colored_face is None:
                try:
                    axis_colored_face = sketch.PlanarEntity
                    print("  axis colored face not found, using sketch plane")
                except Exception:
                    pass

            outer_points, inner_points = axis_stiajka_points(axis)
            outer_points = inventor.unique_points(outer_points)
            inner_points = inventor.unique_points(inner_points)
            if len(outer_points) != 2 or len(inner_points) != 2:
                continue

            all_axis_jobs.append(
                {
                    "colored_face": axis_colored_face,
                    "outer_points": outer_points,
                    "inner_points": inner_points,
                    "outer_main_created": False,
                }
            )

    if all_axis_jobs:
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "outer_points",
            "outer_main",
            "8 mm",
            "34 mm",
            "Stiajka outer 8x34",
            "outer 8x34",
            success_key="outer_main_created",
        )
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "outer_points",
            "outer_secondary",
            "5 mm",
            "13 mm",
            "Stiajka outer 5x13",
            "outer 5x13",
        )
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "inner_points",
            "inner_short",
            "8 mm",
            "10 mm",
            "Shkant 8x10",
            "inner 8x10",
        )
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "inner_points",
            "inner_long",
            "8 mm",
            "20 mm",
            "Shkant 8x20",
            "inner 8x20",
        )

    if cup_sketches is not None:
        cup_points = []
        for cup_sketch in cup_sketches:
            sketch_points = cup_hole_center_points(inventor, cup_sketch)
            print(f"  cup sketch hole centers: {len(sketch_points)}")
            cup_points.extend(sketch_points)

        cup_points = inventor.unique_points(cup_points)
        if cup_points:
            try:
                created += create_cup_holes(inventor, cup_points)
                print("  created one cup feature for selected front faces")
            except Exception as exc:
                print("  selected front face cup failed:", exc)

    if update_document:
        inventor.update()
    else:
        print("  document update skipped")
    return created
