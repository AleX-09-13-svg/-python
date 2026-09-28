from common.constants import DRILLING_SKETCH_PREFIX, FRAME_THICKNESS_PARAM
from common.face_utils import (
    get_red_faces,
    get_yellow_faces,
    reset_faces_to_feature_appearance,
)
from common.settings import hole_direction, setting
from common.sketch_geometry import distance, get_parameter_value

FEATURE_NAME_COUNTERS = {}


def confirmat_setting(*keys, default=None):
    return setting("confirmat", *keys, default=default)


def confirmat_hole(name):
    return confirmat_setting(name, default={})


def confirmat_direction(name):
    return hole_direction(name)


def confirmat_hole_direction(hole_settings, default):
    return confirmat_direction(hole_settings.get("direction", default))


def log(*args):
    if confirmat_setting("debug", default=False):
        print(*args)


def find_confirmat_sketches(component_definition):
    red_faces = get_red_faces(component_definition)
    return find_confirmat_sketches_on_faces(component_definition, red_faces, "red")


def find_confirmat_sketches_on_faces(component_definition, faces, label):
    sketches = []
    plane_offsets = sketch_plane_offsets(component_definition)

    for index in range(1, component_definition.Sketches.Count + 1):
        sketch = component_definition.Sketches.Item(index)
        is_ours = is_generated_drilling_sketch(sketch) or has_drilling_dimensions(
            sketch
        )
        if is_ours and sketch_on_face_plane(sketch, faces, plane_offsets):
            log(f"Selected {label} confirmat sketch:", sketch.Name)
            sketches.append(sketch)

    return sketches


def is_generated_drilling_sketch(sketch):
    try:
        return sketch.Name.startswith(DRILLING_SKETCH_PREFIX)
    except Exception:
        return False


def sketch_on_red_face_plane(sketch, red_faces):
    return sketch_on_face_plane(sketch, red_faces)


def sketch_plane_offsets(component_definition):
    offset = get_parameter_value(component_definition.Parameters, FRAME_THICKNESS_PARAM, 0)
    offsets = [0]

    try:
        if abs(offset) > 0.001:
            offsets.append(offset)
    except Exception:
        pass

    return offsets


def sketch_on_face_plane(sketch, faces, offsets=None):
    try:
        sketch_plane = sketch.PlanarEntity
    except Exception:
        return False

    offsets = offsets or [0]
    for face in faces:
        try:
            if same_plane_entity(sketch_plane, face, offsets):
                return True
        except Exception:
            continue

    return False


def red_faces_on_sketch_plane(sketch, red_faces):
    return faces_on_sketch_plane(sketch, red_faces)


def faces_on_sketch_plane(sketch, faces, offsets=None):
    try:
        sketch_plane = sketch.PlanarEntity
    except Exception:
        return []

    offsets = offsets or [0]
    result = []
    for face in faces:
        try:
            if same_plane_entity(sketch_plane, face, offsets):
                result.append(face)
        except Exception:
            continue

    return result


def same_plane_entity(entity1, entity2, offsets=None, tol=0.001):
    g1 = plane_geometry(entity1)
    g2 = plane_geometry(entity2)
    n1 = g1.Normal
    n2 = g2.Normal
    p1 = g1.RootPoint
    p2 = g2.RootPoint
    dot = n1.X * n2.X + n1.Y * n2.Y + n1.Z * n2.Z
    dist = (p2.X - p1.X) * n1.X + (p2.Y - p1.Y) * n1.Y + (p2.Z - p1.Z) * n1.Z

    if abs(abs(dot) - 1) > tol:
        return False

    for offset in offsets or [0]:
        try:
            if abs(abs(dist) - abs(offset)) <= tol:
                return True
        except Exception:
            continue

    return False


def plane_geometry(entity):
    try:
        return entity.Geometry
    except Exception:
        return entity.Plane


def has_drilling_dimensions(sketch):
    for index in range(1, sketch.DimensionConstraints.Count + 1):
        try:
            name = sketch.DimensionConstraints.Item(index).Parameter.Name
        except Exception:
            continue

        if name.startswith("Long_edge_"):
            return True

    return False


def line_length(line):
    return distance(line.StartSketchPoint.Geometry, line.EndSketchPoint.Geometry)


def line_data(line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    dx = end.X - start.X
    dy = end.Y - start.Y
    return {
        "line": line,
        "x1": start.X,
        "y1": start.Y,
        "x2": end.X,
        "y2": end.Y,
        "dx": dx,
        "dy": dy,
        "length2": dx * dx + dy * dy,
        "mid_x": (start.X + end.X) / 2,
        "mid_y": (start.Y + end.Y) / 2,
    }


def line_midpoint(line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    return (start.X + end.X) / 2, (start.Y + end.Y) / 2


def face_bounds_in_sketch(sketch, face):
    points = [sketch.ModelToSketchSpace(vertex.Point) for vertex in face.Vertices]
    xs = [point.X for point in points]
    ys = [point.Y for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def point_inside_bounds(x, y, bounds, tol=0.01):
    x1, x2, y1, y2 = bounds
    return x1 - tol <= x <= x2 + tol and y1 - tol <= y <= y2 + tol


def axis_on_red_face(sketch, axis, red_faces):
    return axis_on_faces(sketch, axis, red_faces)


def axis_on_faces(sketch, axis, faces):
    mid_x, mid_y = line_midpoint(axis)

    for face in faces:
        try:
            if point_inside_bounds(mid_x, mid_y, face_bounds_in_sketch(sketch, face)):
                return True
        except Exception:
            continue

    return False


def axis_data_on_bounds(axis_data, face_bounds):
    return any(
        point_inside_bounds(axis_data["mid_x"], axis_data["mid_y"], bounds)
        for bounds in face_bounds
    )


def point_on_line(point, line, tol=0.001):
    p = point.Geometry
    a = line.StartSketchPoint.Geometry
    b = line.EndSketchPoint.Geometry
    dx = b.X - a.X
    dy = b.Y - a.Y
    length2 = dx * dx + dy * dy

    if length2 == 0:
        return False, 0

    t = ((p.X - a.X) * dx + (p.Y - a.Y) * dy) / length2
    if t <= tol or t >= 1 - tol:
        return False, t

    closest_x = a.X + dx * t
    closest_y = a.Y + dy * t
    offset = ((p.X - closest_x) ** 2 + (p.Y - closest_y) ** 2) ** 0.5
    return offset <= tol, t


def cached_point_on_axis(point_data, axis_data, tol=0.001):
    length2 = axis_data["length2"]

    if length2 == 0:
        return False, 0

    t = (
        (point_data["x"] - axis_data["x1"]) * axis_data["dx"]
        + (point_data["y"] - axis_data["y1"]) * axis_data["dy"]
    ) / length2
    if t <= tol or t >= 1 - tol:
        return False, t

    closest_x = axis_data["x1"] + axis_data["dx"] * t
    closest_y = axis_data["y1"] + axis_data["dy"] * t
    offset = (
        (point_data["x"] - closest_x) ** 2 + (point_data["y"] - closest_y) ** 2
    ) ** 0.5
    return offset <= tol, t


def sketch_points_data(sketch):
    points = []

    for index in range(1, sketch.SketchPoints.Count + 1):
        point = sketch.SketchPoints.Item(index)
        geo = point.Geometry
        points.append({"point": point, "x": geo.X, "y": geo.Y})

    return points


def points_on_axis(sketch, axis):
    points = []

    for index in range(1, sketch.SketchPoints.Count + 1):
        point = sketch.SketchPoints.Item(index)
        on_line, position = point_on_line(point, axis)
        if on_line:
            points.append((position, point))

    points.sort(key=lambda item: item[0])
    return points


def cached_points_on_axis(points_data, axis_data):
    points = []

    for point_data in points_data:
        on_line, position = cached_point_on_axis(point_data, axis_data)
        if on_line:
            points.append((position, point_data["point"]))

    points.sort(key=lambda item: item[0])
    return points


def construction_axes(sketch):
    axes = []

    for index in range(1, sketch.SketchLines.Count + 1):
        line = sketch.SketchLines.Item(index)
        if not line.Construction:
            continue

        if len(points_on_axis(sketch, line)) >= 5:
            axes.append(line)

    return axes


def construction_axes_data(sketch, points_data, face_bounds=None):
    axes = []

    for index in range(1, sketch.SketchLines.Count + 1):
        line = sketch.SketchLines.Item(index)
        if not line.Construction:
            continue

        data = line_data(line)
        if face_bounds and not axis_data_on_bounds(data, face_bounds):
            continue

        axis_points = cached_points_on_axis(points_data, data)
        if len(axis_points) >= 5:
            data["points"] = axis_points
            axes.append(data)

    return axes


def confirmat_points_from_axis_points(points, include_center=True):
    if len(points) < 3:
        return []

    left_outer = points[0][1]
    right_outer = points[-1][1]

    if not include_center:
        return [left_outer, right_outer]

    center = min(points, key=lambda item: abs(item[0] - 0.5))[1]
    return [left_outer, center, right_outer]


def confirmat_points_on_axis(sketch, axis, include_center=True):
    points = points_on_axis(sketch, axis)
    return confirmat_points_from_axis_points(points, include_center)


def face_bounds_cache(sketch, faces):
    bounds = []

    for face in faces:
        try:
            bounds.append(face_bounds_in_sketch(sketch, face))
        except Exception:
            continue

    return bounds


def mark_as_hole_centers(points):
    for point in points:
        try:
            point.HoleCenter = True
        except Exception:
            pass


def object_collection(inv, objects):
    collection = inv.TransientObjects.CreateObjectCollection()
    for obj in objects:
        collection.Add(obj)
    return collection


def all_surface_bodies(component_definition, inv):
    bodies = inv.TransientObjects.CreateObjectCollection()

    for index in range(1, component_definition.SurfaceBodies.Count + 1):
        bodies.Add(component_definition.SurfaceBodies.Item(index))

    return bodies


def set_all_bodies_affected(feature, component_definition, inv):
    try:
        if component_definition.SurfaceBodies.Count <= 1:
            return
    except Exception:
        pass

    try:
        feature.SetAffectedBodies(component_definition.SurfaceBodies)
        log("  affected bodies:", component_definition.SurfaceBodies.Count)
    except Exception as exc:
        try:
            feature.SetAffectedBodies(all_surface_bodies(component_definition, inv))
            log("  affected bodies:", component_definition.SurfaceBodies.Count)
        except Exception as fallback_exc:
            print("  SetAffectedBodies failed:", exc, fallback_exc)


def unique_points(points):
    result = []
    seen = set()

    for point in points:
        geo = point.Geometry
        key = (round(geo.X, 6), round(geo.Y, 6))
        if key in seen:
            continue

        seen.add(key)
        result.append(point)

    return result


def unique_feature_name(features, base):
    name = base
    index = 1

    while True:
        try:
            features.Item(name)
            index += 1
            name = f"{base} {index}"
        except Exception:
            return name


def fast_feature_name(base):
    count = FEATURE_NAME_COUNTERS.get(base, 0) + 1
    FEATURE_NAME_COUNTERS[base] = count
    if count == 1:
        return base

    return f"{base} {count}"


def add_holes(component_definition, inv, points, diameter, depth, direction, name):
    print(
        f"  creating hole feature: {name}, points={len(points)}, "
        f"diameter={diameter}, depth={depth}, direction={direction}",
        flush=True,
    )
    mark_as_hole_centers(points)
    hole_features = component_definition.Features.HoleFeatures
    placement = hole_features.CreateSketchPlacementDefinition(
        object_collection(inv, points)
    )
    feature = hole_features.AddDrilledByDistanceExtent(
        placement,
        diameter,
        depth,
        direction,
        True,
    )
    try:
        feature.Name = unique_feature_name(hole_features, name)
    except Exception:
        pass
    set_all_bodies_affected(feature, component_definition, inv)
    return feature


def add_counterbore_holes(
    component_definition,
    inv,
    points,
    hole_diameter,
    hole_depth,
    direction,
    cbore_diameter,
    cbore_depth,
    name,
):
    print(
        f"  creating counterbore hole feature: {name}, points={len(points)}, "
        f"hole_diameter={hole_diameter}, hole_depth={hole_depth}, "
        f"cbore_diameter={cbore_diameter}, cbore_depth={cbore_depth}, "
        f"direction={direction}",
        flush=True,
    )
    mark_as_hole_centers(points)
    hole_features = component_definition.Features.HoleFeatures
    placement = hole_features.CreateSketchPlacementDefinition(
        object_collection(inv, points)
    )

    try:
        feature = hole_features.AddCBoreByDistanceExtent2(
            placement,
            hole_diameter,
            hole_depth,
            direction,
            cbore_diameter,
            cbore_depth,
        )
    except Exception:
        feature = hole_features.AddCBoreByDistanceExtent(
            placement,
            hole_diameter,
            hole_depth,
            direction,
            cbore_diameter,
            cbore_depth,
            True,
        )

    try:
        feature.Name = unique_feature_name(hole_features, name)
    except Exception:
        pass
    set_all_bodies_affected(feature, component_definition, inv)
    return feature


def add_confirmat_counterbore(
    component_definition,
    inv,
    points,
    outer,
    inner,
    default_name,
    direction=None,
):
    return add_counterbore_holes(
        component_definition,
        inv,
        points,
        inner.get("diameter", "M_Конфирмат_D_вТорец"),
        inner.get("depth", "M_Конфирмат_глубина"),
        direction if direction is not None else confirmat_hole_direction(outer, "positive"),
        outer.get("diameter", "M_Конфирмат_D_вПласть"),
        outer.get("depth", FRAME_THICKNESS_PARAM),
        outer.get("feature_name", default_name),
    )


def try_share_sketch(sketch):
    try:
        sketch.Shared = True
    except Exception:
        pass


def confirmat_points_for_sketch(sketch, faces, include_center=True, face_label="red"):
    sketch_points = []
    face_bounds = face_bounds_cache(sketch, faces)
    points_data = sketch_points_data(sketch)
    axes = construction_axes_data(sketch, points_data, face_bounds)

    log("  construction axes:", len(axes))

    for axis in axes:
        if not axis_data_on_bounds(axis, face_bounds):
            log(
                f"  skipped axis outside {face_label} face:",
                round(axis["length2"] ** 0.5, 4),
            )
            continue

        points = confirmat_points_from_axis_points(axis["points"], include_center)
        log(
            "  axis length:",
            round(axis["length2"] ** 0.5, 4),
            "confirmat points:",
            len(points),
        )
        expected_count = 3 if include_center else 2
        if len(points) == expected_count:
            sketch_points.extend(points)

    return unique_points(sketch_points)


def create_confirmat_features(
    part_document,
    sketches=None,
    faces=None,
    face_label="red",
    direction=None,
):
    inv = part_document.Parent
    component_definition = part_document.ComponentDefinition
    colored_faces = faces or get_red_faces(component_definition)
    colored_faces_before = colored_faces[:]
    sketches = sketches or find_confirmat_sketches_on_faces(
        component_definition,
        colored_faces,
        face_label,
    )
    outer = confirmat_hole("outer_3pcs") or confirmat_hole("outer")
    inner = confirmat_hole("inner_3pcs") or confirmat_hole("inner")
    created = 0
    print("Confirmat sketches found:", len(sketches))

    for sketch in sketches:
        print("Sketch:", sketch.Name)
        print(
            "  sketch lines/points/dims:",
            sketch.SketchLines.Count,
            sketch.SketchPoints.Count,
            sketch.DimensionConstraints.Count,
        )
        try_share_sketch(sketch)

        sketch_colored_faces = faces_on_sketch_plane(
            sketch,
            colored_faces,
            sketch_plane_offsets(component_definition),
        )
        print(f"  {face_label} faces on sketch plane:", len(sketch_colored_faces))

        sketch_points = confirmat_points_for_sketch(
            sketch,
            sketch_colored_faces,
            face_label=face_label,
        )
        print("  total confirmat points:", len(sketch_points))
        if not sketch_points:
            continue

        try:
            add_confirmat_counterbore(
                component_definition,
                inv,
                sketch_points,
                outer,
                inner,
                "Confirmat counterbore",
                direction=direction,
            )
            created += 1
            try_share_sketch(sketch)
            print("  created confirmat counterbore")
        except Exception as exc:
            print("  confirmat counterbore failed:", exc)

    if faces is None:
        colored_faces_after = get_red_faces(component_definition)
        reset_count = reset_faces_to_feature_appearance(
            colored_faces_before + colored_faces_after,
            f"{face_label} face",
        )
        print(f"{face_label.capitalize()} faces reset to feature appearance:", reset_count)
    else:
        print(f"{face_label.capitalize()} faces appearance reset skipped")

    part_document.Update()
    return created


def create_confirmat_2_features(
    part_document,
    sketches=None,
    faces=None,
    face_label="yellow",
    direction=None,
):
    inv = part_document.Parent
    component_definition = part_document.ComponentDefinition
    colored_faces = faces or get_yellow_faces(component_definition)
    colored_faces_before = colored_faces[:]
    sketches = sketches or find_confirmat_sketches_on_faces(
        component_definition,
        colored_faces,
        face_label,
    )
    outer = confirmat_hole("outer_2pcs") or confirmat_hole("outer")
    inner = confirmat_hole("inner_2pcs") or confirmat_hole("inner")
    created = 0
    print("Confirmat 2pcs sketches found:", len(sketches))

    for sketch in sketches:
        print("Sketch:", sketch.Name)
        print(
            "  sketch lines/points/dims:",
            sketch.SketchLines.Count,
            sketch.SketchPoints.Count,
            sketch.DimensionConstraints.Count,
        )
        try_share_sketch(sketch)

        sketch_colored_faces = faces_on_sketch_plane(
            sketch,
            colored_faces,
            sketch_plane_offsets(component_definition),
        )
        print(f"  {face_label} faces on sketch plane:", len(sketch_colored_faces))

        sketch_points = confirmat_points_for_sketch(
            sketch,
            sketch_colored_faces,
            include_center=False,
            face_label=face_label,
        )
        print("  total confirmat points:", len(sketch_points))
        if not sketch_points:
            continue

        try:
            add_confirmat_counterbore(
                component_definition,
                inv,
                sketch_points,
                outer,
                inner,
                "Confirmat 2pcs counterbore",
                direction=direction,
            )
            created += 1
            try_share_sketch(sketch)
            print("  created 2pcs counterbore")
        except Exception as exc:
            print("  2pcs counterbore failed:", exc)

    if faces is None:
        colored_faces_after = get_yellow_faces(component_definition)
        reset_count = reset_faces_to_feature_appearance(
            colored_faces_before + colored_faces_after,
            f"{face_label} face",
        )
        print(f"{face_label.capitalize()} faces reset to feature appearance:", reset_count)
    else:
        print(f"{face_label.capitalize()} faces appearance reset skipped")

    part_document.Update()
    return created
