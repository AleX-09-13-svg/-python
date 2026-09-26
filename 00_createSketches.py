import ctypes

from common.constants import (
    DRAWER_SKETCH_PREFIX,
    DRILLING_SKETCH_PREFIX,
    EDGE_OFFSET_DRAWER_PARAM,
    EDGE_OFFSET_FRAME_PARAM,
)
from common.face_utils import (
    get_blue_faces,
    get_drilling_faces,
    get_red_faces,
    get_yellow_faces,
    group_faces_by_plane_and_appearance,
    is_green,
    set_sketch_color_from_face,
    sketch_on_face_plane_with_color,
)
from common.inventor_connection import get_inventor
from common.sketch_geometry import hide_sketch_dimensions, sketch_has_geometry_for_face
from sketch.drilling_sketch import create_drilling_sketch


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


def ensure_parameters(component_definition, names):
    missing = missing_parameters(component_definition.Parameters, names)
    if not missing:
        return True

    message = "Create user parameters:\n\n" + "\n".join(missing)
    show_message("Missing parameters", message)
    print(message)
    return False


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


def green_face_count(component_definition):
    return sum(
        1
        for body in component_definition.SurfaceBodies
        for face in body.Faces
        if is_green(face)
    )


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
    groups = group_faces_by_plane_and_appearance(faces)

    print(f"{face_label} faces:", len(faces))
    print(f"{sketch_label} sketch planes:", len(groups))

    count = 0
    created_sketches = 0
    reused_sketches = 0
    skipped_faces = 0

    for group_index, group in enumerate(groups, start=1):
        sketch = sketch_on_face_plane_with_color(comp.Sketches, group[0], sketch_prefix)
        if sketch is None:
            sketch = comp.Sketches.Add(group[0])
            set_sketch_color_from_face(sketch, group[0], inv.TransientObjects)
            sketch.Name = unique_sketch_name(
                comp.Sketches,
                f"{sketch_prefix}_{group_index}",
            )
            created_sketches += 1
        else:
            reused_sketches += 1
            print(f"Using existing {sketch_label} sketch on plane:", sketch.Name)

        if set_sketch_color_from_face(sketch, group[0], inv.TransientObjects):
            print(f"  {sketch_label} sketch color set:", sketch.Name)
        else:
            print(f"  {sketch_label} sketch color not set:", sketch.Name)
        hide_sketch_dimensions(sketch)

        for face in group:
            if sketch_has_geometry_for_face(sketch, face):
                skipped_faces += 1
                print(f"  {sketch_label} face geometry already exists, skipped")
                continue

            if create_drilling_sketch(
                sketch,
                face,
                count + 1,
                inv,
                comp,
                edge_offset_param,
            ):
                set_sketch_color_from_face(sketch, face, inv.TransientObjects)
                hide_sketch_dimensions(sketch)
                count += 1

    print(f"{sketch_label} faces processed:", count)
    print(f"{sketch_label} sketches created:", created_sketches)
    print(f"{sketch_label} sketches reused:", reused_sketches)
    print(f"{sketch_label} faces skipped:", skipped_faces)


def main():
    inv = get_inventor()
    doc = inv.ActiveDocument
    comp = doc.ComponentDefinition

    if not ensure_parameters(
        comp,
        (EDGE_OFFSET_FRAME_PARAM, EDGE_OFFSET_DRAWER_PARAM),
    ):
        return

    drilling_faces = get_drilling_faces(comp)
    blue_faces = get_blue_faces(comp)

    print("Red faces:", len(get_red_faces(comp)))
    print("Green faces:", green_face_count(comp))
    print("Yellow faces:", len(get_yellow_faces(comp)))
    print("Drilling faces:", len(drilling_faces))

    create_sketches_for_faces(
        inv,
        doc,
        drilling_faces,
        DRILLING_SKETCH_PREFIX,
        EDGE_OFFSET_FRAME_PARAM,
        "Drilling",
        "Frame drilling",
    )

    create_sketches_for_faces(
        inv,
        doc,
        blue_faces,
        DRAWER_SKETCH_PREFIX,
        EDGE_OFFSET_DRAWER_PARAM,
        "Drawer",
        "Blue drawer",
    )

    doc.Update()


if __name__ == "__main__":
    main()
