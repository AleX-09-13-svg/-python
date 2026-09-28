import ctypes
from dataclasses import dataclass
from time import perf_counter

from common.constants import (
    DRAWER_SKETCH_PREFIX,
    DRILLING_SKETCH_PREFIX,
    EDGE_OFFSET_DRAWER_PARAM,
    EDGE_OFFSET_FRAME_PARAM,
    GRID_STEP_CM,
    POINT_DISTANCE_PARAM,
)
from common.face_utils import (
    get_blue_faces,
    get_green_faces,
    group_faces_by_plane,
    reset_faces_to_feature_appearance,
    set_sketch_color_rgb,
    sketch_on_face_plane,
)
from common.inventor_connection import get_inventor
from common.settings import (
    dimension_orientation,
    drawer_edge_max_cm,
    hole_direction,
    setting,
)
from common.sketch_geometry import (
    add_aligned_dimension,
    get_parameter_value,
    hide_sketch_dimensions,
    project_face_edges,
    sketch_has_geometry_for_face,
    unique_parameter_name,
)
from confirmat.confirmat import same_plane_entity
from confirmat.confirmat import (
    add_holes,
    construction_axes_data,
    face_bounds_cache,
    sketch_points_data,
    unique_points,
)

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


def stiajka_dimension(name):
    return dimension_orientation(name)


def stiajka_hole(name):
    return stiajka_setting(name, default={})


def stiajka_direction(hole_settings):
    direction_name = hole_settings.get("direction", "positive")
    return hole_direction(direction_name)


def opposite_hole_direction(direction):
    positive = hole_direction("positive")
    negative = hole_direction("negative")

    if direction == positive:
        return negative
    if direction == negative:
        return positive

    return direction


def log_elapsed(label, started):
    elapsed = perf_counter() - started
    print(f"  {label}: {elapsed:.2f}s", flush=True)
    return perf_counter()


def solve_sketch(sketch):
    for method_name in ("Solve", "Update"):
        try:
            getattr(sketch, method_name)()
            print(f"  side sketch {method_name.lower()} ok")
            return True
        except Exception:
            continue

    return False


def fix_sketch_entity(sketch, entity):
    try:
        sketch.GeometricConstraints.AddGround(entity)
        return True
    except Exception:
        pass

    for attr in ("Grounded", "Fixed"):
        try:
            setattr(entity, attr, True)
            return True
        except Exception:
            continue

    return False


def fix_sketch_points(sketch, points):
    fixed = 0

    for point in points:
        if fix_sketch_entity(sketch, point):
            fixed += 1

    print(f"  side sketch fixed points: {fixed}/{len(points)}")
    return fixed


def show_message(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)


def missing_parameters(parameters, names):
    missing = []

    for name in names:
        try:
            parameters.Item(name)
        except Exception:
            missing.append(name)

    return missing


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
        stiajka_parameter("diameter", "\u0421\u0442\u044f\u0436\u043a\u0430_D"),
        stiajka_parameter("depth", "\u0421\u0442\u044f\u0436\u043a\u0430_h"),
        stiajka_parameter("offset", "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f"),
    ]

    for key in ("outer_main", "outer_secondary", "inner_short", "inner_long"):
        settings = stiajka_hole(key)
        names.append(settings.get("diameter"))
        names.append(settings.get("depth"))

    cup = stiajka_hole("cup")
    names.append(cup.get("diameter_parameter"))
    names.append(cup.get("depth_parameter"))

    return unique_names(names)


def face_area(face):
    try:
        return face.Evaluator.Area
    except Exception:
        pass

    try:
        points = [vertex.Point for vertex in face.Vertices]
        xs = [point.X for point in points]
        ys = [point.Y for point in points]
        zs = [point.Z for point in points]
        lengths = sorted(
            (
                max(xs) - min(xs),
                max(ys) - min(ys),
                max(zs) - min(zs),
            ),
            reverse=True,
        )
        return lengths[0] * lengths[1]
    except Exception:
        return 0


def faces_area(faces):
    return sum(face_area(face) for face in faces)


def adjacent_face_count(faces, other_faces):
    count = 0

    for face in faces:
        for other_face in other_faces:
            if shared_face_edge(face, other_face) is not None:
                count += 1
                break

    return count


def split_stiajka_faces(faces):
    groups = group_faces_by_plane(faces)
    if len(groups) < 2:
        return None, None

    end_group_index, end_faces = max(
        enumerate(groups),
        key=lambda item: (
            adjacent_face_count(
                item[1],
                [
                    face
                    for group_index, group in enumerate(groups)
                    if group_index != item[0]
                    for face in group
                ],
            ),
            -faces_area(item[1]),
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
        f"area={faces_area(end_faces):.4f}",
    )
    print(
        "Stiajka front planes:",
        f"planes={len(groups) - 1}",
        f"faces={len(front_faces)}",
        f"area={faces_area(front_faces):.4f}",
    )

    return end_faces, front_faces


def matching_end_face(front_face, end_faces):
    candidates = [
        end_face
        for end_face in end_faces
        if shared_face_edge(front_face, end_face) is not None
    ]
    if not candidates:
        return None

    return max(candidates, key=face_area)


def create_selected_stiajka_plan(faces):
    end_faces, front_faces = split_stiajka_faces(faces)
    if not end_faces:
        return None

    cup_jobs = []
    skipped_front_faces = 0

    for index, front_face in enumerate(front_faces, start=1):
        end_face = matching_end_face(front_face, end_faces)
        if end_face is None:
            skipped_front_faces += 1
            continue

        cup_jobs.append(
            StiajkaCupSketchJob(
                index=index,
                front_face=front_face,
                end_face=end_face,
            )
        )

    print(
        "Stiajka plan:",
        f"end_faces={len(end_faces)}",
        f"front_faces={len(front_faces)}",
        f"cup_jobs={len(cup_jobs)}",
        f"skipped_front_faces={skipped_front_faces}",
    )
    return StiajkaPlan(
        end_faces=end_faces,
        front_faces=front_faces,
        cup_jobs=cup_jobs,
        skipped_front_faces=skipped_front_faces,
    )


def cup_sketch_on_face_plane(sketches, face):
    for sketch in sketches:
        try:
            if same_plane_entity(sketch.PlanarEntity, face):
                return sketch
        except Exception:
            continue

    return None


def create_cup_sketches_for_plan(comp, inv, plan, reuse_existing=True):
    sketches = []
    sketch_names = set()

    for job in plan.cup_jobs:
        sketch = cup_sketch_on_face_plane(sketches, job.front_face)
        sketch = create_stiajka_cup_sketch(
            comp,
            inv,
            job.front_face,
            job.end_face,
            job.index,
            sketch=sketch,
            reuse_existing=reuse_existing,
        )
        try:
            sketch_name = sketch.Name
        except Exception:
            sketch_name = id(sketch)

        if sketch_name not in sketch_names:
            sketch_names.add(sketch_name)
            sketches.append(sketch)

    return sketches


def create_selected_cup_sketches(comp, inv, front_faces, end_faces, reuse_existing=True):
    cup_jobs = []

    for index, front_face in enumerate(front_faces, start=1):
        end_face = matching_end_face(front_face, end_faces)
        if end_face is None:
            print(f"  front face {index}: no shared end face, skipped")
            continue

        cup_jobs.append(
            StiajkaCupSketchJob(
                index=index,
                front_face=front_face,
                end_face=end_face,
            )
        )

    return create_cup_sketches_for_plan(
        comp,
        inv,
        StiajkaPlan(
            end_faces=end_faces,
            front_faces=front_faces,
            cup_jobs=cup_jobs,
        ),
        reuse_existing=reuse_existing,
    )


def unique_sketch_name(sketches, base):
    name = base
    index = 1

    while True:
        try:
            sketches.Item(name)
            index += 1
            name = f"{base}_{index}"
        except Exception:
            return name


def find_stiajka_sketches(component_definition):
    sketches = []

    for index in range(1, component_definition.Sketches.Count + 1):
        sketch = component_definition.Sketches.Item(index)
        try:
            if sketch.Name.startswith(DRAWER_SKETCH_PREFIX):
                sketches.append(sketch)
        except Exception:
            continue

    return sketches


def find_stiajka_sketches_on_green_faces(component_definition):
    green_faces = get_green_faces(component_definition)
    return find_stiajka_sketches_on_faces(
        component_definition,
        green_faces,
        DRILLING_SKETCH_PREFIX,
    )


def find_stiajka_sketches_on_faces(
    component_definition,
    faces,
    sketch_prefix=DRILLING_SKETCH_PREFIX,
):
    sketches = []

    for index in range(1, component_definition.Sketches.Count + 1):
        sketch = component_definition.Sketches.Item(index)
        try:
            if not sketch.Name.startswith(sketch_prefix):
                continue
        except Exception:
            continue

        try:
            sketch_plane = sketch.PlanarEntity
        except Exception:
            continue

        for face in faces:
            try:
                if same_plane_entity(sketch_plane, face):
                    sketches.append(sketch)
                    break
            except Exception:
                continue

    return sketches


def axis_stiajka_points(axis_data):
    points = axis_data["points"]

    if len(points) < 5:
        return [], []

    outer_points = [points[0][1], points[-1][1]]
    inner_points = [points[1][1], points[-2][1]]
    return outer_points, inner_points


def face_model_bounds(face):
    points = [vertex.Point for vertex in face.Vertices]
    xs = [point.X for point in points]
    ys = [point.Y for point in points]
    zs = [point.Z for point in points]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def point_inside_model_bounds(point, bounds, tol=0.01):
    x1, x2, y1, y2, z1, z2 = bounds
    return (
        x1 - tol <= point.X <= x2 + tol
        and y1 - tol <= point.Y <= y2 + tol
        and z1 - tol <= point.Z <= z2 + tol
    )


def planar_geometry(entity):
    try:
        return entity.Geometry
    except Exception:
        return entity.Plane


def project_point_to_face_plane(tg, point, face):
    geometry = planar_geometry(face)
    normal = geometry.Normal
    root = geometry.RootPoint
    distance = (
        (point.X - root.X) * normal.X
        + (point.Y - root.Y) * normal.Y
        + (point.Z - root.Z) * normal.Z
    )
    return tg.CreatePoint(
        point.X - normal.X * distance,
        point.Y - normal.Y * distance,
        point.Z - normal.Z * distance,
    )


def side_hole_model_points(drawer_sketch, colored_face, outer_points, tg, side_offset):
    face_normal = colored_face.Geometry.Normal
    model_points = []

    for sketch_point in outer_points:
        point = drawer_sketch.SketchToModelSpace(sketch_point.Geometry)
        model_points.append(
            tg.CreatePoint(
                point.X - face_normal.X * side_offset,
                point.Y - face_normal.Y * side_offset,
                point.Z - face_normal.Z * side_offset,
            )
        )

    return model_points


def sketch_points_to_model(sketch, points):
    return [sketch.SketchToModelSpace(point.Geometry) for point in points]


def offset_points_from_face(tg, face, points, offset):
    normal = face.Geometry.Normal
    return [
        tg.CreatePoint(
            point.X - normal.X * offset,
            point.Y - normal.Y * offset,
            point.Z - normal.Z * offset,
        )
        for point in points
    ]


def face_key(face):
    try:
        return bytes(face.ReferenceKey)
    except Exception:
        return id(face)


def adjacent_faces(face):
    faces = []
    seen = {face_key(face)}

    try:
        edges = face.Edges
        edge_count = edges.Count
    except Exception:
        return faces

    for edge_index in range(1, edge_count + 1):
        try:
            edge_faces = edges.Item(edge_index).Faces
            face_count = edge_faces.Count
        except Exception:
            continue

        for face_index in range(1, face_count + 1):
            try:
                candidate = edge_faces.Item(face_index)
                key = face_key(candidate)
            except Exception:
                continue

            if key in seen:
                continue

            seen.add(key)
            faces.append(candidate)

    return faces


def candidate_side_faces(component_definition, colored_face):
    x1, x2, y1, y2, z1, z2 = face_model_bounds(colored_face)
    target_y = min(y1, y2)
    faces = []

    for body_index in range(1, component_definition.SurfaceBodies.Count + 1):
        body = component_definition.SurfaceBodies.Item(body_index)
        for face_index in range(1, body.Faces.Count + 1):
            face = body.Faces.Item(face_index)
            try:
                geometry = face.Geometry
                normal = geometry.Normal
                root = geometry.RootPoint
                if abs(abs(normal.Y) - 1) > 0.001:
                    continue
                if abs(root.Y - target_y) > 0.001:
                    continue
                faces.append(face)
            except Exception:
                continue

    return faces


def best_side_face(candidates, model_points, tg):
    best = None
    best_score = None

    for face in candidates:
        try:
            bounds = face_model_bounds(face)
            projected = [
                project_point_to_face_plane(tg, point, face)
                for point in model_points
            ]
            misses = sum(
                not point_inside_model_bounds(point, bounds)
                for point in projected
            )
            normal = face.Geometry.Normal
            score = (
                misses,
                -abs(normal.Y),
                sum(
                    abs((point.X - bounds[0]) * (point.X - bounds[1]))
                    + abs((point.Y - bounds[2]) * (point.Y - bounds[3]))
                    + abs((point.Z - bounds[4]) * (point.Z - bounds[5]))
                    for point in projected
                ),
            )
        except Exception:
            continue

        if misses == 0:
            return face

        if best_score is None or score < best_score:
            best_score = score
            best = face

    return best


def find_side_face(component_definition, colored_face, model_points, tg):
    started = perf_counter()
    candidates = adjacent_faces(colored_face)
    face = best_side_face(candidates, model_points, tg)
    if face is not None:
        log_elapsed(f"side face adjacent search ({len(candidates)} candidates)", started)
        return face

    candidates = candidate_side_faces(component_definition, colored_face)
    face = best_side_face(candidates, model_points, tg)
    log_elapsed(f"side face fallback search ({len(candidates)} candidates)", started)
    return face


def point_distance_parameter_name(sketch):
    for index in range(1, sketch.DimensionConstraints.Count + 1):
        try:
            name = sketch.DimensionConstraints.Item(index).Parameter.Name
        except Exception:
            continue

        if name.startswith(POINT_DISTANCE_PARAM):
            return name

    return POINT_DISTANCE_PARAM


def add_two_point_dimension(sketch, point1, point2, orientation, text_point, expression=None):
    dimension = sketch.DimensionConstraints.AddTwoPointDistance(
        point1,
        point2,
        orientation,
        text_point,
        False,
    )
    if expression:
        dimension.Parameter.Expression = expression
    return dimension


def add_side_sketch_dimensions(sketch, tg, base_line, cup_points, distance_expression):
    top_point, bottom_point = sorted(
        cup_points,
        key=lambda point: point.Geometry.Y,
        reverse=True,
    )
    top = top_point.Geometry
    bottom = bottom_point.Geometry
    line_start = base_line.StartSketchPoint.Geometry
    line_end = base_line.EndSketchPoint.Geometry
    text_x = top.X + 2

    add_two_point_dimension(
        sketch,
        base_line.StartSketchPoint,
        top_point,
        stiajka_dimension("horizontal"),
        tg.CreatePoint2d((line_start.X + top.X) / 2, top.Y + 2),
        stiajka_parameter("offset", "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f"),
    )
    add_two_point_dimension(
        sketch,
        base_line.EndSketchPoint,
        bottom_point,
        stiajka_dimension("horizontal"),
        tg.CreatePoint2d((line_end.X + bottom.X) / 2, bottom.Y - 2),
        stiajka_parameter("offset", "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f"),
    )
    add_two_point_dimension(
        sketch,
        top_point,
        bottom_point,
        stiajka_dimension("aligned"),
        tg.CreatePoint2d(text_x, (top.Y + bottom.Y) / 2),
        distance_expression,
    )
    top_offset = add_two_point_dimension(
        sketch,
        base_line.StartSketchPoint,
        top_point,
        stiajka_dimension("vertical"),
        tg.CreatePoint2d(text_x + 2, (line_start.Y + top.Y) / 2),
    )
    add_two_point_dimension(
        sketch,
        bottom_point,
        base_line.EndSketchPoint,
        stiajka_dimension("vertical"),
        tg.CreatePoint2d(text_x + 2, (bottom.Y + line_end.Y) / 2),
        top_offset.Parameter.Name,
    )


def side_face_bounds_in_sketch(sketch, face):
    points = [sketch.ModelToSketchSpace(vertex.Point) for vertex in face.Vertices]
    xs = [point.X for point in points]
    ys = [point.Y for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def point_inside_sketch_bounds(x, y, bounds, tol=0.01):
    x1, x2, y1, y2 = bounds
    return x1 - tol <= x <= x2 + tol and y1 - tol <= y <= y2 + tol


def faces_on_sketch_plane(sketch, faces):
    try:
        sketch_plane = sketch.PlanarEntity
    except Exception:
        return []

    result = []
    for face in faces:
        try:
            if same_plane_entity(sketch_plane, face):
                result.append(face)
        except Exception:
            continue

    return result


def colored_face_for_axis(sketch, axis_data, faces):
    for face in faces:
        try:
            bounds = side_face_bounds_in_sketch(sketch, face)
        except Exception:
            continue

        if point_inside_sketch_bounds(axis_data["mid_x"], axis_data["mid_y"], bounds):
            return face

    return None


def line_midpoint_xy(line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    return (start.X + end.X) / 2, (start.Y + end.Y) / 2


def line_length_xy(line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    return ((end.X - start.X) ** 2 + (end.Y - start.Y) ** 2) ** 0.5


def project_hole_end_lines(sketch, hole_feature):
    before = sketch.SketchLines.Count

    try:
        faces = hole_feature.Faces
    except Exception:
        return []

    for face_index in range(1, faces.Count + 1):
        face = faces.Item(face_index)
        try:
            edges = face.Edges
        except Exception:
            continue

        for edge_index in range(1, edges.Count + 1):
            try:
                sketch.AddByProjectingEntity(edges.Item(edge_index))
            except Exception:
                continue

    lines = []
    seen = set()
    for index in range(before + 1, sketch.SketchLines.Count + 1):
        line = sketch.SketchLines.Item(index)
        if line_length_xy(line) < 0.01:
            continue

        mid_x, mid_y = line_midpoint_xy(line)
        key = (round(mid_x, 4), round(mid_y, 4))
        if key in seen:
            continue

        seen.add(key)
        lines.append(line)

    return lines


def nearest_line(lines, point):
    if not lines:
        return None

    return min(
        lines,
        key=lambda line: (
            (line_midpoint_xy(line)[0] - point.X) ** 2
            + (line_midpoint_xy(line)[1] - point.Y) ** 2
        ),
    )


def add_cup_distance_dimension(sketch, tg, cup_points, distance_expression):
    if len(cup_points) != 2:
        return

    point1, point2 = sorted(cup_points, key=lambda point: point.Geometry.Y)
    x = point1.Geometry.X + 2
    y = (point1.Geometry.Y + point2.Geometry.Y) / 2
    add_two_point_dimension(
        sketch,
        point1,
        point2,
        stiajka_dimension("aligned"),
        tg.CreatePoint2d(x, y),
        distance_expression,
    )


def edge_length2(edge):
    try:
        p1 = edge.StartVertex.Point
        p2 = edge.StopVertex.Point
    except Exception:
        p1 = edge.Vertices.Item(1).Point
        p2 = edge.Vertices.Item(2).Point

    dx = p2.X - p1.X
    dy = p2.Y - p1.Y
    dz = p2.Z - p1.Z
    return dx * dx + dy * dy + dz * dz


def edge_end_points(edge):
    try:
        return edge.StartVertex.Point, edge.StopVertex.Point
    except Exception:
        return edge.Vertices.Item(1).Point, edge.Vertices.Item(2).Point


def point_to_edge_distance2(point, edge):
    start, end = edge_end_points(edge)
    return point_to_segment_distance2(point, start, end)


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


def edge_average_z(edge):
    start, end = edge_end_points(edge)
    return (start.Z + end.Z) / 2


def model_points_center(tg, points):
    count = len(points)
    return tg.CreatePoint(
        sum(point.X for point in points) / count,
        sum(point.Y for point in points) / count,
        sum(point.Z for point in points) / count,
    )


def point_key(point):
    return round(point.X, 5), round(point.Y, 5), round(point.Z, 5)


def model_distance2(point1, point2):
    return (
        (point1.X - point2.X) ** 2
        + (point1.Y - point2.Y) ** 2
        + (point1.Z - point2.Z) ** 2
    )


def geometry_center(geometry):
    for attr in ("Center", "CenterPoint", "BasePoint", "Origin"):
        try:
            point = getattr(geometry, attr)
            if all(hasattr(point, name) for name in ("X", "Y", "Z")):
                return point
        except Exception:
            continue

    return None


def hole_feature_center_candidates(hole_feature):
    candidates = []
    seen = set()

    try:
        faces = hole_feature.Faces
        face_count = faces.Count
    except Exception:
        return candidates

    for face_index in range(1, face_count + 1):
        try:
            face = faces.Item(face_index)
            edges = face.Edges
            edge_count = edges.Count
        except Exception:
            continue

        for edge_index in range(1, edge_count + 1):
            try:
                center = geometry_center(edges.Item(edge_index).Geometry)
            except Exception:
                center = None

            if center is None:
                continue

            key = point_key(center)
            if key in seen:
                continue

            seen.add(key)
            candidates.append(center)

    return candidates


def projected_hole_centers(hole_feature, reference_points):
    candidates = hole_feature_center_candidates(hole_feature)
    points = []
    used = set()

    for reference in reference_points:
        best_index = None
        best_distance = None

        for index, candidate in enumerate(candidates):
            if index in used:
                continue

            distance2 = model_distance2(reference, candidate)
            if best_distance is None or distance2 < best_distance:
                best_distance = distance2
                best_index = index

        if best_index is None:
            continue

        used.add(best_index)
        points.append(candidates[best_index])

    return points


def shortest_face_edge(face):
    edges = []

    for index in range(1, face.Edges.Count + 1):
        try:
            edges.append(face.Edges.Item(index))
        except Exception:
            continue

    if not edges:
        return None

    return min(edges, key=edge_length2)


def side_plane_edge(colored_face, model_points, tg):
    edge_data = []

    for index in range(1, colored_face.Edges.Count + 1):
        try:
            edge = colored_face.Edges.Item(index)
            start, end = edge_end_points(edge)
            dx = end.X - start.X
            dy = end.Y - start.Y
            dz = end.Z - start.Z
            edge_data.append(
                {
                    "edge": edge,
                    "start": start,
                    "end": end,
                    "length2": dx * dx + dy * dy + dz * dz,
                    "z": (start.Z + end.Z) / 2,
                }
            )
        except Exception:
            continue

    if not edge_data:
        return None

    max_length2 = max(data["length2"] for data in edge_data)
    long_edges = [data for data in edge_data if data["length2"] >= max_length2 * 0.95]
    min_z = min(data["z"] for data in long_edges)
    lower_edges = [data for data in long_edges if abs(data["z"] - min_z) <= 0.001]
    reference = model_points_center(tg, model_points)
    data = min(
        lower_edges,
        key=lambda item: point_to_segment_distance2(
            reference,
            item["start"],
            item["end"],
        ),
    )
    print(f"  side plane lower edge z: {data['z']:.4f}")
    return data["edge"]


def face_average_z(face):
    x1, x2, y1, y2, z1, z2 = face_model_bounds(face)
    return (z1 + z2) / 2


def face_normal_z_score(face):
    try:
        return abs(face.Geometry.Normal.Z)
    except Exception:
        return 0


def lower_adjacent_face(colored_face, model_points, tg):
    candidates = adjacent_faces(colored_face)
    if not candidates:
        return None

    horizontal = [
        face
        for face in candidates
        if face_normal_z_score(face) >= 0.9
    ]
    candidates = horizontal or candidates
    reference = model_points_center(tg, model_points)

    def score(face):
        try:
            projected = project_point_to_face_plane(tg, reference, face)
            bounds = face_model_bounds(face)
            outside = not point_inside_model_bounds(projected, bounds, tol=0.1)
            return outside, face_average_z(face), model_distance2(reference, projected)
        except Exception:
            return True, 1e9, 1e9

    face = min(candidates, key=score)
    print(f"  side lower face z: {face_average_z(face):.4f}")
    return face


def lower_face_from_edge(edge, colored_face):
    candidates = []

    try:
        faces = edge.Faces
        face_count = faces.Count
    except Exception:
        return None

    for index in range(1, face_count + 1):
        try:
            face = faces.Item(index)
        except Exception:
            continue

        candidates.append(face)

    if not candidates:
        return None

    horizontal = [
        face
        for face in candidates
        if face_normal_z_score(face) >= 0.9
    ]
    face = min(horizontal or candidates, key=face_average_z)
    print(f"  side lower edge face z: {face_average_z(face):.4f}")
    return face


def create_perpendicular_side_work_plane(
    component_definition,
    colored_face,
    model_points,
    tg,
):
    started = perf_counter()
    edge = side_plane_edge(colored_face, model_points, tg)
    started = log_elapsed("side edge select elapsed", started)
    if edge is None:
        return None, None

    face = lower_face_from_edge(edge, colored_face)
    started = log_elapsed("side edge face elapsed", started)
    if face is None:
        face = lower_adjacent_face(colored_face, model_points, tg)
        log_elapsed("side adjacent face elapsed", started)
    if face is not None:
        return face, edge

    try:
        work_plane = component_definition.WorkPlanes.AddByLinePlaneAndAngle(
            edge,
            colored_face,
            "90 deg",
            True,
        )
    except Exception as exc:
        print("  side work plane failed:", exc)
        return None, None

    try:
        work_plane.Visible = False
    except Exception:
        pass

    return work_plane, edge


def closest_point_on_sketch_line(tg, point, line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    dx = end.X - start.X
    dy = end.Y - start.Y
    length2 = dx * dx + dy * dy

    if length2 == 0:
        return tg.CreatePoint2d(start.X, start.Y)

    t = ((point.X - start.X) * dx + (point.Y - start.Y) * dy) / length2
    return tg.CreatePoint2d(start.X + dx * t, start.Y + dy * t)


def add_offset_dimensions_from_edge(sketch, tg, edge, points, projected_center_points):
    if edge is None:
        return 0

    try:
        projected = sketch.AddByProjectingEntity(edge)
        projected.Construction = True
    except Exception as exc:
        print("  side offset edge projection failed:", exc)
        return 0

    created = 0
    zero_created = 0
    offset_expression = stiajka_parameter("offset", "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f")

    for point, projected_center in zip(points, projected_center_points):
        try:
            point_geo = point.Geometry
            foot = closest_point_on_sketch_line(tg, point_geo, projected)
            helper = sketch.SketchLines.AddByTwoPoints(foot, point)
            helper.Construction = True
            sketch.GeometricConstraints.AddPerpendicular(helper, projected)
            try:
                sketch.GeometricConstraints.AddCoincident(
                    helper.StartSketchPoint,
                    projected,
                )
            except Exception:
                pass

            dimension = sketch.DimensionConstraints.AddTwoPointDistance(
                helper.StartSketchPoint,
                helper.EndSketchPoint,
                stiajka_dimension("aligned"),
                tg.CreatePoint2d(
                    (foot.X + point_geo.X) / 2,
                    (foot.Y + point_geo.Y) / 2,
                ),
                False,
            )
            dimension.Parameter.Expression = offset_expression
            created += 1

            try:
                zero_dimension = sketch.DimensionConstraints.AddTwoPointDistance(
                    projected_center,
                    helper.StartSketchPoint,
                    stiajka_dimension("aligned"),
                    tg.CreatePoint2d(foot.X - 1, foot.Y),
                    False,
                )
                zero_dimension.Parameter.Expression = "0 mm"
                zero_created += 1
            except Exception as exc:
                print("  side zero dimension failed:", exc)
        except Exception as exc:
            print("  side offset dimension failed:", exc)

    print(f"  side offset dimensions: {created}/{len(points)}")
    print(f"  side zero dimensions: {zero_created}/{len(points)}")
    return created


def add_projected_center_point(sketch, center_coord, source_point):
    try:
        projected = sketch.AddByProjectingEntity(source_point)
        return projected
    except Exception:
        return sketch.SketchPoints.Add(center_coord, False)


def edge_offset_param_for_length(long_edge_length):
    if long_edge_length <= drawer_edge_max_cm():
        return EDGE_OFFSET_DRAWER_PARAM

    return EDGE_OFFSET_FRAME_PARAM


def cup_edge_offset_param_for_length(long_edge_length):
    if long_edge_length <= STIAJKA_CUP_DRAWER_EDGE_MAX_CM:
        return EDGE_OFFSET_DRAWER_PARAM

    return EDGE_OFFSET_FRAME_PARAM


def vector_length2d(dx, dy):
    return (dx * dx + dy * dy) ** 0.5


def face_center_in_sketch(sketch, face, tg):
    points = [sketch.ModelToSketchSpace(vertex.Point) for vertex in face.Vertices]
    return tg.CreatePoint2d(
        sum(point.X for point in points) / len(points),
        sum(point.Y for point in points) / len(points),
    )


def drilling_sketch_outer_model_points_on_face(component_definition, face):
    points = []

    for index in range(1, component_definition.Sketches.Count + 1):
        sketch = component_definition.Sketches.Item(index)
        try:
            if not sketch.Name.startswith(DRILLING_SKETCH_PREFIX):
                continue
            if not same_plane_entity(sketch.PlanarEntity, face):
                continue
        except Exception:
            continue

        face_bounds = face_bounds_cache(sketch, [face])
        axes = construction_axes_data(
            sketch,
            sketch_points_data(sketch),
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


def cup_distances_from_outer_points(component_definition, end_face, shared_edge, length):
    edge_start, edge_end = edge_end_points(shared_edge)
    distances = [
        point_distance_along_edge(point, edge_start, edge_end)
        for point in drilling_sketch_outer_model_points_on_face(component_definition, end_face)
    ]
    distances = sorted({round(distance, 6) for distance in distances})
    if len(distances) < 2:
        return None

    return max(0, min(length, distances[0])), max(0, min(length, distances[-1]))


def front_reference_edge_near_outer_points(
    component_definition,
    front_face,
    end_face,
    fallback_edge,
):
    points = drilling_sketch_outer_model_points_on_face(component_definition, end_face)
    if not points:
        return fallback_edge

    best_edge = fallback_edge
    best_score = None

    try:
        count = front_face.Edges.Count
    except Exception:
        return fallback_edge

    for index in range(1, count + 1):
        try:
            edge = front_face.Edges.Item(index)
            score = sum(point_to_edge_distance2(point, edge) for point in points)
        except Exception:
            continue

        if best_score is None or score < best_score:
            best_edge = edge
            best_score = score

    return best_edge


def shared_face_edge(face1, face2):
    try:
        face2_edges = {
            face_key(face2.Edges.Item(index)): face2.Edges.Item(index)
            for index in range(1, face2.Edges.Count + 1)
        }
    except Exception:
        return None

    for index in range(1, face1.Edges.Count + 1):
        try:
            edge = face1.Edges.Item(index)
            key = face_key(edge)
        except Exception:
            continue

        if key in face2_edges:
            return edge

    candidates = []
    for front_index in range(1, face1.Edges.Count + 1):
        try:
            front_edge = face1.Edges.Item(front_index)
        except Exception:
            continue

        for end_index in range(1, face2.Edges.Count + 1):
            try:
                end_edge = face2.Edges.Item(end_index)
            except Exception:
                continue

            try:
                if point_to_edge_distance2(front_edge.StartVertex.Point, end_edge) < 0.0001:
                    candidates.append(front_edge)
                    break
            except Exception:
                continue

    if not candidates:
        return None

    return max(candidates, key=edge_length2)


def add_stiajka_cup_sketch_dimensions(
    sketch,
    tg,
    parameters,
    reference_line,
    offset_line,
    cup_points,
    point_distance_value,
    index,
    offset_expression=None,
    point_distance_expression=None,
    anchor_point=None,
    anchor_offset_expression=None,
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
    center = tg.CreatePoint2d((start.X + end.X) / 2, (start.Y + end.Y) / 2)

    long_dim = add_aligned_dimension(
        sketch,
        reference_line.StartSketchPoint,
        reference_line.EndSketchPoint,
        tg.CreatePoint2d(center.X + nx * 2, center.Y + ny * 2),
        True,
    )
    long_dim.Parameter.Name = unique_parameter_name(parameters, f"Long_edge_{index}")

    point_distance_dim = add_aligned_dimension(
        sketch,
        cup_points[0],
        cup_points[1],
        tg.CreatePoint2d(center.X + nx * 4, center.Y + ny * 4),
    )
    point_distance_dim.Parameter.Name = unique_parameter_name(parameters, POINT_DISTANCE_PARAM)
    edge_offset_param = cup_edge_offset_param_for_length(length)
    point_distance_dim.Parameter.Expression = point_distance_expression or (
        f"floor(({long_dim.Parameter.Name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
    )

    offset_dim = add_aligned_dimension(
        sketch,
        reference_line.StartSketchPoint,
        offset_line.StartSketchPoint,
        tg.CreatePoint2d(
            (reference_line.StartSketchPoint.Geometry.X + offset_line.StartSketchPoint.Geometry.X) / 2,
            (reference_line.StartSketchPoint.Geometry.Y + offset_line.StartSketchPoint.Geometry.Y) / 2,
        ),
    )
    offset_dim.Parameter.Expression = offset_expression or stiajka_parameter(
        "offset",
        "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f",
    )

    if anchor_point is not None:
        anchor = anchor_point.Geometry
        point = cup_points[0].Geometry
        anchor_offset_dim = add_aligned_dimension(
            sketch,
            anchor_point,
            cup_points[0],
            tg.CreatePoint2d(
                (anchor.X + point.X) / 2 + nx * 6,
                (anchor.Y + point.Y) / 2 + ny * 6,
            ),
        )
        anchor_offset_dim.Parameter.Expression = anchor_offset_expression or (
            f"({long_dim.Parameter.Name} - {point_distance_dim.Parameter.Name}) / 2"
        )


def cup_sketch_has_face_geometry(sketch, face):
    try:
        return sketch_has_geometry_for_face(sketch, face)
    except Exception:
        return False


def create_stiajka_cup_sketch(
    component_definition,
    inv,
    front_face,
    end_face,
    index=1,
    sketch=None,
    reuse_existing=True,
):
    if sketch is None and reuse_existing:
        sketch = sketch_on_face_plane(
            component_definition.Sketches,
            front_face,
            STIAJKA_CUP_SKETCH_PREFIX,
        )
    if sketch is None:
        sketch = component_definition.Sketches.Add(front_face)
        sketch.Name = unique_sketch_name(
            component_definition.Sketches,
            f"{STIAJKA_CUP_SKETCH_PREFIX}_{index}",
        )
    else:
        print("Using existing stiajka cup sketch:", sketch.Name)
        if cup_sketch_has_face_geometry(sketch, front_face):
            print("  stiajka cup face geometry already exists, skipped")
            return sketch

    set_sketch_color_rgb(
        sketch,
        STIAJKA_CUP_SKETCH_RGB,
        inv.TransientObjects,
        include_entities=False,
    )

    tg = inv.TransientGeometry
    shared_edge = shared_face_edge(front_face, end_face)
    if shared_edge is None:
        raise RuntimeError("selected faces do not share an edge")
    reference_edge = front_reference_edge_near_outer_points(
        component_definition,
        front_face,
        end_face,
        shared_edge,
    )

    project_face_edges(sketch, front_face)
    reference_line = sketch.AddByProjectingEntity(reference_edge)
    reference_line.Construction = True

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
    midpoint = tg.CreatePoint2d((start.X + end.X) / 2, (start.Y + end.Y) / 2)
    face_center = face_center_in_sketch(sketch, front_face, tg)
    outer_side = (
        (face_center.X - midpoint.X) * nx
        + (face_center.Y - midpoint.Y) * ny
    )
    if outer_side < 0:
        nx = -nx
        ny = -ny

    offset_parameter = stiajka_parameter(
        "offset",
        "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f",
    )
    offset_value = get_parameter_value(
        component_definition.Parameters,
        offset_parameter,
        stiajka_setting("side_offset", default=3.4),
    )
    offset_expression = offset_parameter
    edge_offset_param = cup_edge_offset_param_for_length(length)
    edge_offset_value = get_parameter_value(component_definition.Parameters, edge_offset_param, 10)
    point_distances = cup_distances_from_outer_points(
        component_definition,
        end_face,
        reference_edge,
        length,
    )
    if point_distances is None:
        point_distance_value = int((length - edge_offset_value * 2) / GRID_STEP_CM) * GRID_STEP_CM
        point_distance_value = max(point_distance_value, GRID_STEP_CM * 2)
        equal_edge_offset_value = (length - point_distance_value) / 2
        point1_distance = equal_edge_offset_value
        point2_distance = equal_edge_offset_value + point_distance_value
    else:
        point1_distance, point2_distance = point_distances
        point_distance_value = abs(point2_distance - point1_distance)

    if point1_distance > point2_distance:
        point1_distance, point2_distance = point2_distance, point1_distance

    point_distance_expression = None

    line_start = tg.CreatePoint2d(start.X + nx * offset_value, start.Y + ny * offset_value)
    line_end = tg.CreatePoint2d(end.X + nx * offset_value, end.Y + ny * offset_value)
    offset_line = sketch.SketchLines.AddByTwoPoints(line_start, line_end)
    offset_line.Construction = True
    sketch.GeometricConstraints.AddParallel(offset_line, reference_line)

    anchor_point = offset_line.StartSketchPoint

    point1 = sketch.SketchPoints.Add(
        tg.CreatePoint2d(
            start.X + ux * point1_distance + nx * offset_value,
            start.Y + uy * point1_distance + ny * offset_value,
        ),
        False,
    )
    point2 = sketch.SketchPoints.Add(
        tg.CreatePoint2d(
            start.X + ux * point2_distance + nx * offset_value,
            start.Y + uy * point2_distance + ny * offset_value,
        ),
        False,
    )
    for point in (point1, point2):
        point.HoleCenter = True
        sketch.GeometricConstraints.AddCoincident(point, offset_line)

    add_stiajka_cup_sketch_dimensions(
        sketch,
        tg,
        component_definition.Parameters,
        reference_line,
        offset_line,
        (point1, point2),
        point_distance_value,
        index,
        offset_expression,
        point_distance_expression,
        anchor_point,
        None,
    )
    hide_sketch_dimensions(sketch)
    print("  created stiajka cup sketch:", sketch.Name)
    return sketch


def create_stiajka_cup_sketches(
    component_definition,
    inv,
    front_faces,
    end_face,
):
    sketches = []
    for index, front_face in enumerate(front_faces, start=1):
        sketches.append(
            create_stiajka_cup_sketch(
                component_definition,
                inv,
                front_face,
                end_face,
                index,
            )
        )

    return sketches


def create_side_sketch(
    component_definition,
    inv,
    drawer_sketch,
    colored_face,
    outer_points,
    outer_hole_feature=None,
    plane_mode="edge",
):
    side_offset = get_parameter_value(
        component_definition.Parameters,
        stiajka_parameter("offset", "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f"),
        stiajka_setting("side_offset", default=3.4),
    )
    center_points = sketch_points_to_model(drawer_sketch, outer_points)
    model_points = offset_points_from_face(
        inv.TransientGeometry,
        colored_face,
        center_points,
        side_offset,
    )
    print(f"  using outer sketch centers offset by {side_offset} cm")
    side_started = perf_counter()
    side_edge = None

    if plane_mode == "face":
        sketch_plane = find_side_face(
            component_definition,
            colored_face,
            model_points,
            inv.TransientGeometry,
        )
    else:
        sketch_plane, side_edge = create_perpendicular_side_work_plane(
            component_definition,
            colored_face,
            model_points,
            inv.TransientGeometry,
        )

    side_started = log_elapsed("side plane elapsed", side_started)
    if sketch_plane is None:
        return None, []

    sketch = component_definition.Sketches.Add(sketch_plane)
    sketch.Name = unique_sketch_name(component_definition.Sketches, "StiajkaSideSketch")
    defer_updates = False
    try:
        sketch.DeferUpdates = True
        defer_updates = True
    except Exception:
        pass

    try:
        side_started = perf_counter()
        sketch_coords = [
            sketch.ModelToSketchSpace(
                project_point_to_face_plane(inv.TransientGeometry, model_point, sketch_plane)
            )
            for model_point in model_points
        ]
        center_coords = [
            sketch.ModelToSketchSpace(
                project_point_to_face_plane(inv.TransientGeometry, center_point, sketch_plane)
            )
            for center_point in center_points
        ]
        side_started = log_elapsed("side point projection elapsed", side_started)

        side_started = perf_counter()
        projected_center_points = [
            add_projected_center_point(sketch, center_coord, source_point)
            for center_coord, source_point in zip(center_coords, outer_points)
        ]
        sketch_points = []
        for sketch_coord in sketch_coords:
            sketch_point = sketch.SketchPoints.Add(sketch_coord, True)
            sketch_point.HoleCenter = True
            sketch_points.append(sketch_point)
        side_started = log_elapsed("side point creation elapsed", side_started)

        side_started = perf_counter()
        if add_offset_dimensions_from_edge(
            sketch,
            inv.TransientGeometry,
            side_edge,
            sketch_points,
            projected_center_points,
        ) != len(sketch_points):
            fix_sketch_points(sketch, sketch_points)
        log_elapsed("side dimensions elapsed", side_started)
        return sketch, sketch_points

    finally:
        if defer_updates:
            try:
                side_started = perf_counter()
                sketch.DeferUpdates = False
                log_elapsed("side defer update elapsed", side_started)
            except Exception:
                pass


def create_cup_holes(component_definition, inv, side_points):
    cup = stiajka_hole("cup")
    direction = stiajka_direction(cup)
    diameter = cup.get(
        "diameter_parameter",
        stiajka_parameter("diameter", "\u0421\u0442\u044f\u0436\u043a\u0430_D"),
    )
    depth = cup.get(
        "depth_parameter",
        stiajka_parameter("depth", "\u0421\u0442\u044f\u0436\u043a\u0430_h"),
    )
    feature_name = cup.get("feature_name", "Stiajka cup")

    try:
        add_holes(
            component_definition,
            inv,
            side_points,
            diameter,
            depth,
            direction,
            feature_name,
        )
        print(f"  created cup feature with points: {len(side_points)}")
    except Exception as exc:
        raise RuntimeError(f"cup feature failed for points: {len(side_points)}") from exc

    return 1


def cup_hole_center_points(sketch):
    points = []

    for index in range(1, sketch.SketchPoints.Count + 1):
        point = sketch.SketchPoints.Item(index)
        try:
            if point.HoleCenter:
                points.append(point)
        except Exception:
            continue

    return unique_points(points)


def create_hole_batch(
    component_definition,
    inv,
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
    points = unique_points(
        point
        for job in jobs
        for point in job[points_key]
    )
    if not points:
        return 0

    started = perf_counter()
    try:
        add_holes(
            component_definition,
            inv,
            points,
            settings.get("diameter", default_diameter),
            settings.get("depth", default_depth),
            stiajka_direction(settings),
            settings.get("feature_name", default_name),
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
            add_holes(
                component_definition,
                inv,
                job[points_key],
                settings.get("diameter", default_diameter),
                settings.get("depth", default_depth),
                stiajka_direction(settings),
                settings.get("feature_name", default_name),
            )
            if success_key:
                job[success_key] = True
            created += 1
            print(f"  created {label}")
        except Exception as exc:
            print(f"  {label} failed:", exc)

    log_elapsed(f"{label} fallback elapsed", started)
    return created


def create_stiajka_features(
    part_document,
    sketches=None,
    colored_faces=None,
    cup_sketches=None,
    update_document=True,
):
    inv = part_document.Parent
    component_definition = part_document.ComponentDefinition
    if sketches is None:
        sketches = find_stiajka_sketches(component_definition)
    if colored_faces is None:
        colored_faces = get_blue_faces(component_definition)
    created = 0

    missing = missing_parameters(
        component_definition.Parameters,
        stiajka_required_parameter_names(),
    )
    if missing:
        message = "Создайте пользовательские параметры:\n\n" + "\n".join(missing)
        show_message("Нет параметров", message)
        print(message)
        return 0

    print("Stiajka sketches found:", len(sketches))
    if cup_sketches is not None:
        print("Stiajka cup sketches found:", len(cup_sketches))

    for sketch in sketches:
        print("Sketch:", sketch.Name)
        try:
            sketch_face = sketch.PlanarEntity
        except Exception as exc:
            print("  skipped, no planar face:", exc)
            continue

        sketch_colored_faces = faces_on_sketch_plane(sketch, colored_faces)
        print("  colored faces on sketch plane:", len(sketch_colored_faces))

        face_bounds = face_bounds_cache(sketch, sketch_colored_faces)
        axes = construction_axes_data(
            sketch,
            sketch_points_data(sketch),
            face_bounds or None,
        )
        print("  construction axes:", len(axes))

        axis_jobs = []

        for axis in axes:
            axis_colored_face = colored_face_for_axis(
                sketch,
                axis,
                sketch_colored_faces,
            )
            if axis_colored_face is None:
                axis_colored_face = sketch_face
                print("  axis colored face not found, using sketch plane")

            outer_points, inner_points = axis_stiajka_points(axis)
            outer_points = unique_points(outer_points)
            inner_points = unique_points(inner_points)

            if len(outer_points) != 2 or len(inner_points) != 2:
                continue

            axis_jobs.append(
                {
                    "colored_face": axis_colored_face,
                    "outer_points": outer_points,
                    "inner_points": inner_points,
                    "outer_main_created": False,
                }
            )

        if not axis_jobs:
            continue

        batch_started = perf_counter()
        created += create_hole_batch(
            component_definition,
            inv,
            axis_jobs,
            "outer_points",
            "outer_main",
            "8 mm",
            "34 mm",
            "Stiajka outer 8x34",
            "outer 8x34",
            success_key="outer_main_created",
        )
        created += create_hole_batch(
            component_definition,
            inv,
            axis_jobs,
            "outer_points",
            "outer_secondary",
            "5 mm",
            "13 mm",
            "Stiajka outer 5x13",
            "outer 5x13",
        )
        created += create_hole_batch(
            component_definition,
            inv,
            axis_jobs,
            "inner_points",
            "inner_short",
            "8 mm",
            "10 mm",
            "Stiajka inner 8x10",
            "inner 8x10",
        )
        created += create_hole_batch(
            component_definition,
            inv,
            axis_jobs,
            "inner_points",
            "inner_long",
            "8 mm",
            "20 mm",
            "Stiajka inner 8x20",
            "inner 8x20",
        )
        log_elapsed("normal stiajka batches elapsed", batch_started)

        if cup_sketches is not None:
            continue

        for job in axis_jobs:
            axis_started = perf_counter()
            if not job["outer_main_created"]:
                print("  side sketch skipped, no outer 8x34 feature")
                continue

            side_sketch, side_points = create_side_sketch(
                component_definition,
                inv,
                sketch,
                job["colored_face"],
                job["outer_points"],
            )
            axis_started = log_elapsed("side sketch elapsed", axis_started)
            if not side_points:
                print("  side sketch failed")
                continue

            solve_sketch(side_sketch)
            try:
                created += create_cup_holes(component_definition, inv, side_points)
                print("  created cup")
                axis_started = log_elapsed("cup elapsed", axis_started)
            except Exception as exc:
                print("  cup failed:", exc)
                print("  retrying cup on adjacent side face")
                retry_started = perf_counter()
                try:
                    retry_sketch, retry_points = create_side_sketch(
                        component_definition,
                        inv,
                        sketch,
                        job["colored_face"],
                        job["outer_points"],
                        plane_mode="face",
                    )
                    log_elapsed("cup retry side sketch elapsed", retry_started)
                    if not retry_points:
                        raise RuntimeError("fallback side sketch has no points")

                    solve_sketch(retry_sketch)
                    created += create_cup_holes(component_definition, inv, retry_points)
                    print("  created cup after retry")
                    axis_started = log_elapsed("cup retry elapsed", axis_started)
                except Exception as retry_exc:
                    print("  cup retry failed:", retry_exc)

    if cup_sketches is not None:
        for cup_sketch in cup_sketches:
            cup_points = cup_hole_center_points(cup_sketch)
            print(f"  cup sketch hole centers: {len(cup_points)}")
            if not cup_points:
                continue

            try:
                created += create_cup_holes(component_definition, inv, cup_points)
                print("  created cup from selected front face")
            except Exception as exc:
                print("  selected front face cup failed:", exc)

    if update_document:
        update_started = perf_counter()
        part_document.Update()
        log_elapsed("document update elapsed", update_started)
    else:
        print("  document update skipped")

    return created


def main():
    inv = get_inventor()
    doc = inv.ActiveDocument
    blue_faces_before = get_blue_faces(doc.ComponentDefinition)
    created = create_stiajka_features(doc)
    blue_faces_after = get_blue_faces(doc.ComponentDefinition)
    reset_count = reset_faces_to_feature_appearance(
        blue_faces_before + blue_faces_after,
        "blue face",
    )
    print("Blue faces reset to feature appearance:", reset_count)
    doc.Update()
    print("Stiajka features created:", created)


if __name__ == "__main__":
    main()
