import ctypes
import sys
from contextlib import contextmanager

from common.constants import (
    DRAWER_SKETCH_PREFIX,
    DRILLING_SKETCH_PREFIX,
    EDGE_OFFSET_DRAWER_PARAM,
    EDGE_OFFSET_FRAME_PARAM,
    FRAME_THICKNESS_PARAM,
)
from common.face_utils import (
    group_faces_by_plane,
    plane_geometry,
    set_sketch_color_rgb,
    selected_faces,
)
from common.inventor_connection import get_inventor
from common.sketch_geometry import hide_sketch_dimensions
from sketch.drilling_sketch import create_drilling_sketch

SKETCH_YELLOW_RGB = (255, 220, 0)
NO_UPDATE_ARG = "--no-update"
KEEP_EXCEL_PARAMS_NAME = "Keep_Excel_Params"


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


def user_parameters(component_definition):
    return component_definition.Parameters.UserParameters


def ensure_parameters(component_definition, names):
    missing = missing_parameters(component_definition.Parameters, names)
    if not missing:
        return True

    message = "Create or import parameters:\n\n" + "\n".join(missing)
    show_message("Missing parameters", message)
    print(message)
    return False


def parameter_expressions(component_definition, names):
    expressions = {}
    parameters = component_definition.Parameters

    for name in names:
        try:
            expressions[name] = parameters.Item(name).Expression
        except Exception:
            pass

    return expressions


def ensure_keep_excel_parameters(component_definition, names):
    expression = " + ".join(names)
    parameters = user_parameters(component_definition)

    try:
        keep_parameter = parameters.Item(KEEP_EXCEL_PARAMS_NAME)
    except Exception:
        try:
            keep_parameter = parameters.AddByExpression(
                KEEP_EXCEL_PARAMS_NAME,
                expression,
                "mm",
            )
        except Exception as exc:
            print("Keep Excel parameter create failed:", exc)
            return False

    try:
        keep_parameter.Expression = expression
    except Exception as exc:
        print("Keep Excel parameter update failed:", exc)
        return False

    return True


def restore_missing_parameters(component_definition, expressions):
    all_parameters = component_definition.Parameters
    parameters = user_parameters(component_definition)
    restored = False

    for name, expression in expressions.items():
        try:
            all_parameters.Item(name)
            continue
        except Exception:
            pass

        try:
            parameters.AddByExpression(name, expression, "mm")
            print("Restored missing parameter:", name)
            restored = True
        except Exception as exc:
            print("Parameter restore failed:", name, exc)

    return restored


def unique_sketch_name(sketches, base):
    name = base
    index = 1

    while True:
        exists = False
        try:
            sketches.Item(name)
        except Exception:
            try:
                count = sketches.Count
            except Exception:
                return name

            for item_index in range(1, count + 1):
                try:
                    if sketches.Item(item_index).Name == name:
                        exists = True
                        break
                except Exception:
                    continue
        else:
            exists = True

        if not exists:
            return name

        index += 1
        name = f"{base}_{index}"


def same_offset_plane_entity(entity, face, offset_value, tol=0.001):
    try:
        entity_plane = plane_geometry(entity)
        face_plane = plane_geometry(face)
        entity_point = entity_plane.RootPoint
        face_point = face_plane.RootPoint
        face_normal = face_plane.Normal
        entity_normal = entity_plane.Normal
    except Exception:
        return False

    dot = (
        face_normal.X * entity_normal.X
        + face_normal.Y * entity_normal.Y
        + face_normal.Z * entity_normal.Z
    )
    dist = (
        (entity_point.X - face_point.X) * face_normal.X
        + (entity_point.Y - face_point.Y) * face_normal.Y
        + (entity_point.Z - face_point.Z) * face_normal.Z
    )

    return abs(abs(dot) - 1) <= tol and abs(dist - offset_value) <= tol


def sketch_on_offset_face_plane(sketches, face, prefix, offset_value):
    for index in range(1, sketches.Count + 1):
        sketch = sketches.Item(index)
        try:
            if not sketch.Name.startswith(prefix):
                continue
            if same_offset_plane_entity(sketch.PlanarEntity, face, offset_value):
                return sketch
        except Exception:
            continue

    return None


def offset_work_plane(comp, face, plane_name, offset_param, offset_value):
    work_plane = comp.WorkPlanes.AddByPlaneAndOffset(face, offset_param)
    work_plane.Name = unique_sketch_name(comp.WorkPlanes, plane_name)

    try:
        work_plane.Visible = False
    except Exception:
        pass

    return work_plane


@contextmanager
def screen_updates_suspended(inv):
    previous = None
    changed = False

    try:
        previous = inv.ScreenUpdating
        inv.ScreenUpdating = False
        changed = True
    except Exception:
        pass

    try:
        yield
    finally:
        if changed:
            try:
                inv.ScreenUpdating = previous
            except Exception:
                pass


@contextmanager
def sketch_updates_deferred(sketch):
    previous = None
    changed = False

    try:
        previous = sketch.DeferUpdates
        sketch.DeferUpdates = True
        changed = True
    except Exception:
        pass

    try:
        yield
    finally:
        if changed:
            try:
                sketch.DeferUpdates = previous
            except Exception:
                pass


def create_sketches_for_faces(
    inv,
    doc,
    faces,
    sketch_prefix,
    edge_offset_param,
    sketch_label,
    face_label,
):
    comp = doc.ComponentDefinition
    groups = group_faces_by_plane(faces)
    frame_thickness_value = comp.Parameters.Item(FRAME_THICKNESS_PARAM).Value

    print(f"{face_label} faces:", len(faces))
    print(f"{sketch_label} sketch planes:", len(groups))

    count = 0
    created_sketches = 0
    sketches = []

    for group_index, group in enumerate(groups, start=1):
        offset_plane_name = f"{sketch_prefix}_OffsetPlane_{group_index}"
        sketch_plane = offset_work_plane(
            comp,
            group[0],
            offset_plane_name,
            FRAME_THICKNESS_PARAM,
            frame_thickness_value,
        )
        sketch = comp.Sketches.Add(sketch_plane)
        set_sketch_color_rgb(
            sketch,
            SKETCH_YELLOW_RGB,
            inv.TransientObjects,
            include_entities=False,
        )
        sketch.Name = unique_sketch_name(
            comp.Sketches,
            f"{sketch_prefix}_{group_index}",
        )
        created_sketches += 1
        sketches.append(sketch)

        if set_sketch_color_rgb(
            sketch,
            SKETCH_YELLOW_RGB,
            inv.TransientObjects,
            include_entities=False,
        ):
            print(f"  {sketch_label} sketch color set:", sketch.Name)
        else:
            print(f"  {sketch_label} sketch color not set:", sketch.Name)

        with sketch_updates_deferred(sketch):
            for face in group:
                if create_drilling_sketch(
                    sketch,
                    face,
                    count + 1,
                    inv,
                    comp,
                    edge_offset_param,
                ):
                    count += 1

        hide_sketch_dimensions(sketch)

    print(f"{sketch_label} faces processed:", count)
    print(f"{sketch_label} sketches created:", created_sketches)
    return sketches


def sketch_mode():
    for arg in sys.argv[1:]:
        value = arg.strip().lower()
        if value.startswith("--"):
            continue
        return value

    return "drilling"


def should_update_document():
    return NO_UPDATE_ARG not in [arg.strip().lower() for arg in sys.argv[1:]]


def main():
    inv = get_inventor()
    doc = inv.ActiveDocument
    comp = doc.ComponentDefinition
    required_parameters = (
        EDGE_OFFSET_FRAME_PARAM,
        EDGE_OFFSET_DRAWER_PARAM,
        FRAME_THICKNESS_PARAM,
    )

    if not ensure_parameters(
        comp,
        required_parameters,
    ):
        return

    selected = selected_faces(doc, debug=True)
    if not selected:
        message = "Select one or more faces before running this script."
        show_message("No selected faces", message)
        print(message)
        return

    ensure_keep_excel_parameters(comp, required_parameters)
    protected_parameter_expressions = parameter_expressions(comp, required_parameters)

    mode = sketch_mode()
    print("Selected faces:", len(selected))
    print("Sketch mode:", mode)

    with screen_updates_suspended(inv):
        if mode == "drawer":
            create_sketches_for_faces(
                inv,
                doc,
                selected,
                DRAWER_SKETCH_PREFIX,
                None,
                "Drawer",
                "Selected drawer",
            )
        else:
            create_sketches_for_faces(
                inv,
                doc,
                selected,
                DRILLING_SKETCH_PREFIX,
                None,
                "Drilling",
                "Selected drilling",
            )

    if should_update_document():
        doc.Update()
        if restore_missing_parameters(
            comp,
            protected_parameter_expressions,
        ):
            doc.Update()


if __name__ == "__main__":
    main()
