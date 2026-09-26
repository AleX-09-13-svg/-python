from stiajka.stiajka import main as _stiajka_main


if __name__ == "__main__":
    _stiajka_main()
    raise SystemExit


import ctypes

from common.constants import DRAWER_SKETCH_PREFIX, DRILLING_SKETCH_PREFIX, POINT_DISTANCE_PARAM
from common.face_utils import get_blue_faces, get_green_faces, reset_faces_to_feature_appearance
from common.inventor_connection import get_inventor
from common.sketch_geometry import get_parameter_value
from confirmat.confirmat import same_plane_entity
from confirmat.confirmat import (
    NEGATIVE_DIRECTION,
    POSITIVE_DIRECTION,
    add_holes,
    construction_axes_data,
    sketch_points_data,
    unique_points,
)

STIAJKA_DIAMETER_PARAM = "\u0421\u0442\u044f\u0436\u043a\u0430_D"
STIAJKA_DEPTH_PARAM = "\u0421\u0442\u044f\u0436\u043a\u0430_h"
STIAJKA_OFFSET_PARAM = "\u0421\u0442\u044f\u0436\u043a\u0430_\u043e\u0442\u0441\u0442\u0443\u043f"
SIDE_OFFSET = 3.4
HORIZONTAL_DIM = 19201
VERTICAL_DIM = 19202
ALIGNED_DIM = 19203


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
    sketches = []

    for index in range(1, component_definition.Sketches.Count + 1):
        sketch = component_definition.Sketches.Item(index)
        try:
            if not sketch.Name.startswith(DRILLING_SKETCH_PREFIX):
                continue
        except Exception:
            continue

        try:
            sketch_plane = sketch.PlanarEntity
        except Exception:
            continue

        for face in green_faces:
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


def project_point_to_face_plane(tg, point, face):
    geometry = face.Geometry
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


def side_hole_model_points(drawer_sketch, blue_face, outer_points, tg, side_offset):
    blue_normal = blue_face.Geometry.Normal
    model_points = []

    for sketch_point in outer_points:
        point = drawer_sketch.SketchToModelSpace(sketch_point.Geometry)
        model_points.append(
            tg.CreatePoint(
                point.X - blue_normal.X * side_offset,
                point.Y - blue_normal.Y * side_offset,
                point.Z - blue_normal.Z * side_offset,
            )
        )

    return model_points


def candidate_side_faces(component_definition, blue_face):
    x1, x2, y1, y2, z1, z2 = face_model_bounds(blue_face)
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


def find_side_face(component_definition, blue_face, model_points, tg):
    for face in candidate_side_faces(component_definition, blue_face):
        try:
            bounds = face_model_bounds(face)
            projected = [
                project_point_to_face_plane(
                    tg,
                    point,
                    face,
                )
                for point in model_points
            ]
            if all(point_inside_model_bounds(point, bounds) for point in projected):
                return face
        except Exception:
            continue

    return None


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
        HORIZONTAL_DIM,
        tg.CreatePoint2d((line_start.X + top.X) / 2, top.Y + 2),
        STIAJKA_OFFSET_PARAM,
    )
    add_two_point_dimension(
        sketch,
        base_line.EndSketchPoint,
        bottom_point,
        HORIZONTAL_DIM,
        tg.CreatePoint2d((line_end.X + bottom.X) / 2, bottom.Y - 2),
        STIAJKA_OFFSET_PARAM,
    )
    add_two_point_dimension(
        sketch,
        top_point,
        bottom_point,
        ALIGNED_DIM,
        tg.CreatePoint2d(text_x, (top.Y + bottom.Y) / 2),
        distance_expression,
    )
    top_offset = add_two_point_dimension(
        sketch,
        base_line.StartSketchPoint,
        top_point,
        VERTICAL_DIM,
        tg.CreatePoint2d(text_x + 2, (line_start.Y + top.Y) / 2),
    )
    add_two_point_dimension(
        sketch,
        bottom_point,
        base_line.EndSketchPoint,
        VERTICAL_DIM,
        tg.CreatePoint2d(text_x + 2, (bottom.Y + line_end.Y) / 2),
        top_offset.Parameter.Name,
    )


def side_face_bounds_in_sketch(sketch, face):
    points = [sketch.ModelToSketchSpace(vertex.Point) for vertex in face.Vertices]
    xs = [point.X for point in points]
    ys = [point.Y for point in points]
    return min(xs), max(xs), min(ys), max(ys)


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
        ALIGNED_DIM,
        tg.CreatePoint2d(x, y),
        distance_expression,
    )


def create_side_sketch(
    component_definition,
    inv,
    drawer_sketch,
    blue_face,
    outer_points,
    outer_hole_feature,
):
    side_offset = get_parameter_value(
        component_definition.Parameters,
        STIAJKA_OFFSET_PARAM,
        SIDE_OFFSET,
    )
    model_points = side_hole_model_points(
        drawer_sketch,
        blue_face,
        outer_points,
        inv.TransientGeometry,
        side_offset,
    )
    side_face = find_side_face(
        component_definition,
        blue_face,
        model_points,
        inv.TransientGeometry,
    )

    if side_face is None:
        return None, []

    sketch = component_definition.Sketches.Add(side_face)
    sketch.Name = unique_sketch_name(component_definition.Sketches, "StiajkaSideSketch")
    projected_lines = project_hole_end_lines(sketch, outer_hole_feature)

    sketch_coords = [
        sketch.ModelToSketchSpace(
            project_point_to_face_plane(inv.TransientGeometry, model_point, side_face)
        )
        for model_point in model_points
    ]
    sketch_points = []
    for sketch_coord in sketch_coords:
        projected_line = nearest_line(projected_lines, sketch_coord)
        if projected_line is not None:
            mid_x, mid_y = line_midpoint_xy(projected_line)
            sketch_point = sketch.SketchPoints.Add(
                inv.TransientGeometry.CreatePoint2d(mid_x, mid_y),
                True,
            )
            sketch.GeometricConstraints.AddMidpoint(sketch_point, projected_line)
        else:
            sketch_point = sketch.SketchPoints.Add(sketch_coord, True)

        sketch_point.HoleCenter = True
        sketch_points.append(sketch_point)

    if not projected_lines:
        x1, x2, y1, y2 = side_face_bounds_in_sketch(sketch, side_face)
        reference_x = sketch_coords[0].X - side_offset
        if abs(reference_x - x2) < abs(reference_x - x1):
            reference_x = x2
        else:
            reference_x = x1

        base_line = sketch.SketchLines.AddByTwoPoints(
            inv.TransientGeometry.CreatePoint2d(reference_x, y2),
            inv.TransientGeometry.CreatePoint2d(reference_x, y1),
        )
        add_side_sketch_dimensions(
            sketch,
            inv.TransientGeometry,
            base_line,
            sketch_points,
            point_distance_parameter_name(drawer_sketch),
        )

    return sketch, sketch_points


def create_stiajka_features(part_document, sketches=None):
    inv = part_document.Parent
    component_definition = part_document.ComponentDefinition
    if sketches is None:
        sketches = find_stiajka_sketches(component_definition)
    created = 0

    missing = missing_parameters(
        component_definition.Parameters,
        (STIAJKA_DIAMETER_PARAM, STIAJKA_DEPTH_PARAM, STIAJKA_OFFSET_PARAM),
    )
    if missing:
        message = "Создайте пользовательские параметры:\n\n" + "\n".join(missing)
        show_message("Нет параметров", message)
        print(message)
        return 0

    print("Stiajka sketches found:", len(sketches))

    for sketch in sketches:
        print("Sketch:", sketch.Name)
        try:
            blue_face = sketch.PlanarEntity
        except Exception as exc:
            print("  skipped, no planar face:", exc)
            continue

        axes = construction_axes_data(sketch, sketch_points_data(sketch))
        print("  construction axes:", len(axes))

        for axis in axes:
            outer_points, inner_points = axis_stiajka_points(axis)
            outer_points = unique_points(outer_points)
            inner_points = unique_points(inner_points)

            if len(outer_points) != 2 or len(inner_points) != 2:
                continue

            outer_hole_feature = None
            try:
                outer_hole_feature = add_holes(
                    component_definition,
                    inv,
                    outer_points,
                    "8 mm",
                    "34 mm",
                    POSITIVE_DIRECTION,
                    "Stiajka outer 8x34",
                )
                created += 1
                print("  created outer 8x34")
            except Exception as exc:
                print("  outer 8x34 failed:", exc)

            try:
                add_holes(
                    component_definition,
                    inv,
                    outer_points,
                    "5 mm",
                    "13 mm",
                    NEGATIVE_DIRECTION,
                    "Stiajka outer 5x13",
                )
                created += 1
                print("  created outer 5x13")
            except Exception as exc:
                print("  outer 5x13 failed:", exc)

            try:
                add_holes(
                    component_definition,
                    inv,
                    inner_points,
                    "8 mm",
                    "10 mm",
                    NEGATIVE_DIRECTION,
                    "Stiajka inner 8x10",
                )
                created += 1
                print("  created inner 8x10")
            except Exception as exc:
                print("  inner 8x10 failed:", exc)

            try:
                add_holes(
                    component_definition,
                    inv,
                    inner_points,
                    "8 mm",
                    "20 mm",
                    POSITIVE_DIRECTION,
                    "Stiajka inner 8x20",
                )
                created += 1
                print("  created inner 8x20")
            except Exception as exc:
                print("  inner 8x20 failed:", exc)

            if outer_hole_feature is None:
                print("  side sketch skipped, no outer 8x34 feature")
                continue

            side_sketch, side_points = create_side_sketch(
                component_definition,
                inv,
                sketch,
                blue_face,
                outer_points,
                outer_hole_feature,
            )
            if not side_points:
                print("  side sketch failed")
                continue

            try:
                add_holes(
                    component_definition,
                    inv,
                    side_points,
                    STIAJKA_DIAMETER_PARAM,
                    STIAJKA_DEPTH_PARAM,
                    POSITIVE_DIRECTION,
                    "Stiajka cup",
                )
                created += 1
                print("  created cup")
            except Exception as exc:
                print("  cup failed:", exc)

    part_document.Update()
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
