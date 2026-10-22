import sys
import json
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk
from math import sqrt

from common.constants import (
    DRILLING_SKETCH_PREFIX,
    GRID_STEP_CM,
    POINT_DISTANCE_PARAM,
)
import common.create_sketches as create_sketches
from common.selected_workflow import (
    hide_sketches,
    selected_inventor_context,
)
import stiajka.stiajka as stiajka_module
from time import perf_counter


LOG_PATH = Path(__file__).resolve().with_suffix(".log")
PART_CONFIG_PATH = (
    Path(__file__).resolve().parents[1]
    / "01_inventor_service"
    / "service"
    / "infa"
    / "part_config.example.json"
)
DEFAULT_FRAME_EDGE_OFFSET_PARAMS = (
    "\u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439_\u043e\u0442\u0441\u0442\u0443\u043f_\u043f\u0440\u0438\u0441\u0430\u0434\u043a\u0438_\u043e\u0442_\u043a\u0440\u043e\u043c\u043a\u0438_\u041a\u0430\u0440\u043a\u0430\u0441",
)


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            try:
                stream.write(text)
                stream.flush()
            except Exception:
                pass

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass


def log_elapsed(label, started):
    elapsed = perf_counter() - started
    print(f"{label}: {elapsed:.2f}s")
    return perf_counter()


def unique_names(names):
    return tuple(name for name in dict.fromkeys(names) if name)


def parameter_collection_names(collection):
    names = []

    try:
        count = collection.Count
    except Exception:
        return names

    for index in range(1, count + 1):
        try:
            names.append(collection.Item(index).Name)
        except Exception:
            continue

    return names


def all_parameter_names(inventor):
    names = []

    for collection in (
        getattr(inventor, "user_parameters", None),
        getattr(inventor, "model_parameters", None),
    ):
        if collection is not None:
            names.extend(parameter_collection_names(collection))

    return unique_names(names)


def library_parameter_names():
    try:
        config = json.loads(PART_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print("Part config JSON not available:", PART_CONFIG_PATH, exc)
        return ()

    names = []
    for item in config.get("linked_parameters", []):
        source_name = item.get("source_name")
        if source_name:
            names.append(source_name)
        elif item.get("name"):
            names.append(item["name"])

    return unique_names(names)


def frame_edge_offset_parameter_options(inventor):
    names = all_parameter_names(inventor)
    offset_names = [
        name
        for name in names
        if "\u043e\u0442\u0441\u0442\u0443\u043f" in name.lower()
    ]
    return unique_names((*DEFAULT_FRAME_EDGE_OFFSET_PARAMS, *sorted(offset_names)))


def choose_frame_edge_offset_parameter(inventor):
    options = frame_edge_offset_parameter_options(inventor)
    selected = {"frame_edge_offset": None}

    root = tk.Tk()
    root.title(
        "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440 \u043e\u0442\u0441\u0442\u0443\u043f\u0430 \u043a\u0430\u0440\u043a\u0430\u0441\u0430"
    )
    root.geometry("560x140+80+80")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    label = ttk.Label(
        frame,
        text="\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440 \u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439_\u043e\u0442\u0441\u0442\u0443\u043f_\u043f\u0440\u0438\u0441\u0430\u0434\u043a\u0438_\u043e\u0442_\u043a\u0440\u043e\u043c\u043a\u0438_\u041a\u0430\u0440\u043a\u0430\u0441:",
    )
    label.pack(anchor=tk.W)

    value = tk.StringVar(value=options[0] if options else "")
    combo = ttk.Combobox(
        frame,
        textvariable=value,
        values=options,
        state="readonly",
    )
    combo.pack(fill=tk.X, pady=(6, 12))
    combo.focus_set()
    combo.selection_range(0, tk.END)

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)

    def accept():
        selected["frame_edge_offset"] = value.get().strip()
        root.destroy()

    def cancel():
        root.destroy()

    ttk.Button(buttons, text="OK", command=accept).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="\u041e\u0442\u043c\u0435\u043d\u0430", command=cancel).pack(
        side=tk.RIGHT,
        padx=(0, 8),
    )

    root.bind("<Return>", lambda event: accept())
    root.bind("<Escape>", lambda event: cancel())
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return selected["frame_edge_offset"]


def faces_by_area(inventor, faces):
    areas = []
    for index, face in enumerate(faces, start=1):
        area = inventor.face_area(face) or 0
        areas.append((area, face))
        print(f"Selected face {index} area: {area:.4f}")

    sorted_faces = sorted(areas, key=lambda item: item[0])
    print(f"Using first selected face area: {sorted_faces[0][0]:.4f}")
    print(f"Using second selected face area: {sorted_faces[1][0]:.4f}")
    return [face for _, face in sorted_faces]


def face_body_key(face):
    body = getattr(face, "Parent", None)
    if body is None:
        return ("face", id(face))

    name = getattr(body, "Name", None)
    try:
        box = body.RangeBox
        bounds = (
            round(box.MinPoint.X, 6),
            round(box.MinPoint.Y, 6),
            round(box.MinPoint.Z, 6),
            round(box.MaxPoint.X, 6),
            round(box.MaxPoint.Y, 6),
            round(box.MaxPoint.Z, 6),
        )
    except Exception:
        bounds = (id(body),)

    return name, bounds


def selected_face_pairs(inventor, faces):
    if len(faces) == 2:
        return [faces_by_area(inventor, faces)]

    groups = {}
    for face in faces:
        groups.setdefault(face_body_key(face), []).append(face)

    pairs = []
    for group_index, group in enumerate(groups.values(), start=1):
        if len(group) != 2:
            print(
                "For multi-body stiajka select exactly two faces on each body; "
                f"group {group_index} has {len(group)} face(s)."
            )
            return None

        print(f"Selected body group {group_index}:")
        pairs.append(faces_by_area(inventor, group))

    if not pairs:
        return None

    print("Selected stiajka body pairs:", len(pairs))
    return pairs


def shared_intersection_edge(inventor, face, reference_face):
    reference_edge_keys = {
        inventor.face_key(edge)
        for edge in inventor.face_edges(reference_face)
    }
    edges = [
        edge
        for edge in inventor.face_edges(face)
        if inventor.face_key(edge) in reference_edge_keys
    ]
    if not edges:
        return stiajka_module.shared_face_edge(inventor, face, reference_face)

    return min(edges, key=stiajka_module.edge_length2)


def vector_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vector_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def vector_length(vector):
    return sqrt(vector_dot(vector, vector))


def point_tuple(point):
    return point.X, point.Y, point.Z


def normal_tuple(normal):
    return normal.X, normal.Y, normal.Z


def plane_intersection_model_line(inventor, face, reference_face):
    face_plane = inventor.plane_geometry(face)
    reference_plane = inventor.plane_geometry(reference_face)
    n1 = normal_tuple(reference_plane.Normal)
    n2 = normal_tuple(face_plane.Normal)
    p1 = point_tuple(reference_plane.RootPoint)
    p2 = point_tuple(face_plane.RootPoint)
    direction = vector_cross(n1, n2)
    direction_length2 = vector_dot(direction, direction)
    if direction_length2 < 1e-8:
        return None, None

    c1 = vector_dot(n1, p1)
    c2 = vector_dot(n2, p2)
    n2_cross_d = vector_cross(n2, direction)
    d_cross_n1 = vector_cross(direction, n1)
    point = tuple(
        (c1 * n2_cross_d[index] + c2 * d_cross_n1[index]) / direction_length2
        for index in range(3)
    )
    return point, direction


def second_sketch_reference_lines(inventor, sketch, start, ux, uy, min_distance, max_distance):
    """Find projected boundary lines for the offset and the two ends of the axis."""
    reference = left = right = None
    tolerance = 1e-5
    for line in inventor.sketch_lines(sketch, construction=False):
        a = line.StartSketchPoint.Geometry
        b = line.EndSketchPoint.Geometry
        along = [(p.X - start.X) * ux + (p.Y - start.Y) * uy for p in (a, b)]
        across = [-(p.X - start.X) * uy + (p.Y - start.Y) * ux for p in (a, b)]
        if max(abs(value) for value in across) < tolerance and abs(along[1] - along[0]) > tolerance:
            reference = line
        if max(abs(value - min_distance) for value in along) < tolerance:
            left = line
        if max(abs(value - max_distance) for value in along) < tolerance:
            right = line
    if reference is None or left is None or right is None:
        raise ValueError("Cannot bind second sketch: intersection edge or side edges not found.")
    return reference, left, right


def create_offset_drilling_sketch(
    inventor,
    face,
    reference_face,
    index,
    offset_param,
    edge_offset_param,
):
    intersection_point, intersection_direction = plane_intersection_model_line(
        inventor,
        face,
        reference_face,
    )
    if intersection_point is None:
        print("Selected faces planes are parallel; cannot build intersection direction.")
        return None

    sketch = inventor.add_sketch(face)
    sketch.Name = inventor.unique_sketch_name(f"{DRILLING_SKETCH_PREFIX}_{index}")
    inventor.set_sketch_color_rgb(
        sketch,
        create_sketches.SKETCH_YELLOW_RGB,
        include_entities=False,
    )

    offset_value = inventor.parameter_value(
        offset_param,
        stiajka_module.stiajka_setting("side_offset", default=3.4),
    )
    with inventor.deferred_sketch_updates(sketch):
        inventor.project_face_edges(sketch, face, ignore_errors=False)
        intersection_start = inventor.model_to_sketch_point(
            sketch,
            inventor.create_point3d(*intersection_point),
        )
        intersection_end = inventor.model_to_sketch_point(
            sketch,
            inventor.create_point3d(
                intersection_point[0] + intersection_direction[0],
                intersection_point[1] + intersection_direction[1],
                intersection_point[2] + intersection_direction[2],
            ),
        )

        start = intersection_start
        end = intersection_end
        direction_length = inventor.distance_2d(start, end)
        if direction_length == 0:
            print("Selected faces intersection has zero length in the second sketch.")
            return None

        ux = (end.X - start.X) / direction_length
        uy = (end.Y - start.Y) / direction_length
        nx = -uy
        ny = ux
        face_center = inventor.face_center_in_sketch(face, sketch)
        if (face_center.X - start.X) * nx + (face_center.Y - start.Y) * ny < 0:
            nx = -nx
            ny = -ny

        base = inventor.create_point2d(
            start.X + nx * offset_value,
            start.Y + ny * offset_value,
        )
        face_points = inventor.face_vertex_points_in_sketch(face, sketch)
        distances = [
            (point.X - base.X) * ux + (point.Y - base.Y) * uy
            for point in face_points
        ]
        min_distance = min(distances)
        max_distance = max(distances)
        length = max_distance - min_distance
        if length <= 0:
            print("Second face span along intersection direction is zero.")
            return None

        reference_line, left_side, right_side = second_sketch_reference_lines(
            inventor, sketch, start, ux, uy, min_distance, max_distance,
        )
        midpoint = inventor.create_point2d(
            base.X + ux * ((min_distance + max_distance) / 2),
            base.Y + uy * ((min_distance + max_distance) / 2),
        )
        offset_start = inventor.create_point2d(
            base.X + ux * min_distance,
            base.Y + uy * min_distance,
        )
        offset_end = inventor.create_point2d(
            base.X + ux * max_distance,
            base.Y + uy * max_distance,
        )
        axis = inventor.add_sketch_line(
            sketch,
            offset_start,
            offset_end,
            construction=True,
        )
        inventor.add_parallel_constraint(sketch, axis, reference_line, ignore_errors=False)
        inventor.add_coincident_constraint(
            sketch, axis.StartSketchPoint, left_side, ignore_errors=False,
        )
        inventor.add_coincident_constraint(
            sketch, axis.EndSketchPoint, right_side, ignore_errors=False,
        )
        print(
            "Second sketch drilling point axis is parallel to selected faces intersection line."
        )

        offset_anchor = inventor.add_sketch_line(
            sketch,
            inventor.create_point2d(
                midpoint.X - nx * offset_value,
                midpoint.Y - ny * offset_value,
            ),
            midpoint,
            construction=True,
        )
        inventor.add_coincident_constraint(
            sketch, offset_anchor.StartSketchPoint, reference_line, ignore_errors=False,
        )
        inventor.add_coincident_constraint(
            sketch,
            offset_anchor.EndSketchPoint,
            axis,
            ignore_errors=False,
        )
        inventor.add_perpendicular_constraint(sketch, offset_anchor, axis, ignore_errors=False)

        center = midpoint
        symmetry_axis = inventor.add_sketch_line(
            sketch,
            center,
            inventor.create_point2d(center.X + nx, center.Y + ny),
            construction=True,
        )
        inventor.add_perpendicular_constraint(sketch, axis, symmetry_axis, ignore_errors=False)
        inventor.add_midpoint_constraint(
            sketch, symmetry_axis.StartSketchPoint, axis, ignore_errors=False,
        )
        inventor.add_coincident_constraint(
            sketch, offset_anchor.EndSketchPoint, symmetry_axis, ignore_errors=False,
        )

        edge_offset_value = inventor.parameter_value(edge_offset_param, 10)
        print("Second sketch edge offset:", edge_offset_param, "=", edge_offset_value)
        point_distance_value = (
            int((length - edge_offset_value * 2) / GRID_STEP_CM) * GRID_STEP_CM
        )
        point_distance_value = max(point_distance_value, GRID_STEP_CM * 2)
        points = inventor.create_drilling_points(
            sketch,
            center,
            ux,
            uy,
            point_distance_value,
        )
        inventor.constrain_drilling_points(sketch, axis, symmetry_axis, points)

        left_outer, right_outer, left_inner, _, _, outer = points
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
            inventor.create_point2d(center.X + nx * 2, center.Y + ny * 2),
        )
        inset_dim = inventor.add_aligned_dimension(
            sketch,
            left_outer,
            left_inner,
            inventor.create_point2d(
                center.X - ux * (outer - 1.6) + nx * 2,
                center.Y - uy * (outer - 1.6) + ny * 2,
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
            f"Long_edge_{index}",
            inventor.parameters,
        )
        point_distance_dim.Parameter.Name = inventor.unique_parameter_name(
            POINT_DISTANCE_PARAM,
            inventor.parameters,
        )
        point_distance_dim.Parameter.Expression = (
            f"floor(({long_dim.Parameter.Name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
        )
        inset_dim.Parameter.Expression = "32 mm"
        offset_dim.Parameter.Expression = offset_param

    inventor.hide_sketch_dimensions(sketch)
    print(
        "Created second face drilling sketch with offset:",
        sketch.Name,
        offset_param,
    )
    return sketch, (left_outer, right_outer)


def create_second_face_stiajka_holes(inventor, outer_points):
    if not outer_points:
        return 0

    cup_settings = stiajka_module.stiajka_hole("cup")
    diameter_param = stiajka_module.stiajka_parameter("diameter", "Стяжка_D")
    depth_param = stiajka_module.stiajka_parameter("depth", "Стяжка_h")
    inventor.add_holes(
        outer_points,
        diameter=diameter_param,
        depth=depth_param,
        direction=stiajka_module.stiajka_direction(cup_settings),
        name=cup_settings.get("feature_name", "Stiajka cup"),
    )
    print(
        "Second face stiajka holes created:",
        len(outer_points),
        diameter_param,
        depth_param,
    )
    return 1


def main():
    started = perf_counter()
    inventor, faces = selected_inventor_context("Stiajka 2pcs")
    if not faces:
        return

    frame_edge_offset_param = choose_frame_edge_offset_parameter(inventor)
    if not frame_edge_offset_param:
        print("Frame edge offset parameter was not selected")
        return

    print("Frame edge offset parameter:", frame_edge_offset_param)
    stiajka_offset_param = stiajka_module.stiajka_parameter("offset", "Стяжка_отступ")

    required_parameters = (
        frame_edge_offset_param,
        stiajka_offset_param,
        *stiajka_module.stiajka_required_parameter_names(),
    )
    required_parameters = unique_names(required_parameters)
    if not create_sketches.ensure_parameters(inventor, required_parameters):
        return

    inventor.ensure_keep_parameter("Keep_Excel_Params", required_parameters)
    started = log_elapsed("Selected context", started)

    face_pairs = selected_face_pairs(inventor, faces)
    if not face_pairs:
        print("Select two faces, or two faces on each selected body, for this step.")
        return

    first_faces = [pair[0] for pair in face_pairs]

    first_sketches = create_sketches.create_sketches_for_faces(
        inventor,
        None,
        first_faces,
        DRILLING_SKETCH_PREFIX,
        frame_edge_offset_param,
        "Drilling",
        "Selected first face drilling",
        reuse_existing=True,
    )
    started = log_elapsed("Create first sketch", started)

    created = stiajka_module.create_stiajka_features(
        inventor,
        sketches=first_sketches,
        colored_faces=first_faces,
        cup_sketches=None,
        update_document=False,
    )
    started = log_elapsed("Create first face stiajka features", started)

    if created:
        hide_sketches(first_sketches, "Stiajka first face")
    else:
        print("First face stiajka sketch left visible because no hole features were created")

    second_created = 0
    for index, (first_face, second_face) in enumerate(face_pairs, start=2):
        second_result = create_offset_drilling_sketch(
            inventor,
            second_face,
            first_face,
            index,
            stiajka_offset_param,
            frame_edge_offset_param,
        )
        if second_result is None:
            continue

        second_sketch, second_outer_points = second_result
        current_second_created = create_second_face_stiajka_holes(
            inventor,
            second_outer_points,
        )
        second_created += current_second_created
        if current_second_created:
            hide_sketches([second_sketch], "Stiajka second face")
    started = log_elapsed("Create second face stiajka holes", started)

    inventor.update()
    log_elapsed("Update document", started)
    print("First face stiajka features created:", created)
    print("Second face stiajka features created:", second_created)


if __name__ == "__main__":
    with LOG_PATH.open("w", encoding="utf-8") as log:
        sys.stdout = Tee(sys.__stdout__, log)
        sys.stderr = Tee(sys.__stderr__, log)
        print("Running:", Path(__file__).name, flush=True)
        print("Log:", LOG_PATH, flush=True)
        try:
            main()
        except Exception:
            traceback.print_exc()
            raise
