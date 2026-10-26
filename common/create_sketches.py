import sys

from common.constants import (
    PARAMETERS,
    DRILLING_SKETCH_PREFIX,
    GRID_STEP_CM,
)


KEEP_EXCEL_PARAMS_NAME = "Keep_Excel_Params"
NO_UPDATE_ARG = "--no-update"
SKETCH_YELLOW_RGB = (255, 220, 0)


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
):
    print(
        f"  build drilling geometry: sketch={getattr(sketch, 'Name', '<unknown>')}, "
        f"project_edges={project_edges}",
        flush=True,
    )
    first_new_line = inventor.sketch_line_count(sketch)
    print("    lines before projection:", first_new_line, flush=True)
    if project_edges:
        inventor.project_face_edges(sketch, face)

    print("    lines after projection:", inventor.sketch_line_count(sketch), flush=True)
    lines = inventor.sketch_lines_for_face(sketch, face, first_new_line)
    print("    new face lines found:", len(lines), flush=True)
    if len(lines) < 2:
        lines = inventor.sketch_lines_for_face(sketch, face, 0)
        print("    all face lines found:", len(lines), flush=True)

    if len(lines) < 2:
        print("    skipped: less than 2 face lines", flush=True)
        return False

    short1, short2 = sorted(lines, key=lambda line: _line_length_squared(inventor, line))[:2]
    print(
        "    short edge lengths:",
        round(_line_length_squared(inventor, short1) ** 0.5, 4),
        round(_line_length_squared(inventor, short2) ** 0.5, 4),
        flush=True,
    )
    axes = inventor.create_construction_axes(sketch, short1, short2)
    _, _, _, long_edge_length, _, _, _, _ = axes
    print("    long edge length:", round(long_edge_length, 4), flush=True)

    if callable(edge_offset_param):
        edge_offset_param = edge_offset_param(long_edge_length)
    elif edge_offset_param is None:
        edge_offset_param = edge_offset_param_for_length(long_edge_length)

    edge_offset_value = inventor.parameter_value(edge_offset_param, 10)
    print(
        "    edge offset:",
        edge_offset_param,
        "=",
        round(edge_offset_value, 4) if isinstance(edge_offset_value, (int, float)) else edge_offset_value,
        flush=True,
    )
    point_distance_value = (
        int((long_edge_length - edge_offset_value * 2) / GRID_STEP_CM)
        * GRID_STEP_CM
    )
    point_distance_value = max(point_distance_value, GRID_STEP_CM * 2)
    print("    point distance:", round(point_distance_value, 4), flush=True)

    points = inventor.create_drilling_points(
        sketch,
        axes[2],
        axes[4],
        axes[5],
        point_distance_value,
    )
    inventor.constrain_drilling_points(sketch, axes[0], axes[1], points)
    inventor.add_side_plane_reference_line(sketch, axes[0], lines)

    axis, _, center, _, ux, uy, nx, ny = axes
    left_outer, right_outer, left_inner, _, _, outer = points
    long_dim = inventor.add_aligned_dimension(
        sketch,
        axis.StartSketchPoint,
        axis.EndSketchPoint,
        inventor.create_point2d(center.X + nx * 4, center.Y + ny * 4),
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

    long_dim.Parameter.Name = inventor.unique_parameter_name(
        f"Long_edge_{index}",
        inventor.parameters,
    )
    point_distance_dim.Parameter.Name = inventor.unique_parameter_name(
        PARAMETERS.point_distance,
        inventor.parameters,
    )
    point_distance_dim.Parameter.Expression = (
        f"floor(({long_dim.Parameter.Name} - {edge_offset_param} * 2) / 32 mm) * 32 mm"
    )
    inset_dim.Parameter.Expression = "32 mm"

    print("    drilling geometry created", flush=True)
    return True


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
):
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
        offset_value = inventor.parameter_value(offset_param, 0)
        if not reuse_existing:
            sketch = None
        elif use_offset_plane:
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
                sketch.Name = inventor.unique_sketch_name(f"{sketch_prefix}_{group_index}")
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
        with inventor.deferred_sketch_updates(sketch):
            for face in group:
                has_geometry = inventor.sketch_has_geometry_for_face(sketch, face)
                has_axes = _sketch_has_drilling_axes(inventor, sketch)
                print(
                    f"  face state: has_geometry={has_geometry}, has_drilling_axes={has_axes}",
                    flush=True,
                )
                if has_geometry and has_axes:
                    skipped_faces += 1
                    print(f"  {sketch_label} face geometry already exists, skipped")
                    continue

                if _create_drilling_sketch_fixed(
                    inventor,
                    sketch,
                    face,
                    count + 1,
                    edge_offset_param,
                    project_edges=not has_geometry,
                ):
                    count += 1
                    group_processed += 1

        if group_processed:
            inventor.hide_sketch_dimensions(sketch)

    print(f"{sketch_label} faces processed:", count)
    print(f"{sketch_label} sketches created:", created_sketches)
    print(f"{sketch_label} sketches reused:", reused_sketches)
    print(f"{sketch_label} faces skipped:", skipped_faces)

    return sketches
