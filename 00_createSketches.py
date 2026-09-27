import ctypes
import sys

from common.constants import (
    DRAWER_SKETCH_PREFIX,
    DRILLING_SKETCH_PREFIX,
    EDGE_OFFSET_DRAWER_PARAM,
    EDGE_OFFSET_FRAME_PARAM,
)
from common.face_utils import (
    group_faces_by_plane,
    set_sketch_color_rgb,
    selected_faces,
    sketch_on_face_plane,
)
from common.inventor_connection import get_inventor
from common.sketch_geometry import hide_sketch_dimensions, sketch_has_geometry_for_face
from sketch.drilling_sketch import create_drilling_sketch

SKETCH_YELLOW_RGB = (255, 220, 0)


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

    print(f"{face_label} faces:", len(faces))
    print(f"{sketch_label} sketch planes:", len(groups))

    count = 0
    created_sketches = 0
    reused_sketches = 0
    skipped_faces = 0

    for group_index, group in enumerate(groups, start=1):
        sketch = sketch_on_face_plane(comp.Sketches, group[0], sketch_prefix)
        if sketch is None:
            sketch = comp.Sketches.Add(group[0])
            set_sketch_color_rgb(sketch, SKETCH_YELLOW_RGB, inv.TransientObjects)
            sketch.Name = unique_sketch_name(
                comp.Sketches,
                f"{sketch_prefix}_{group_index}",
            )
            created_sketches += 1
        else:
            reused_sketches += 1
            print(f"Using existing {sketch_label} sketch on plane:", sketch.Name)

        if set_sketch_color_rgb(sketch, SKETCH_YELLOW_RGB, inv.TransientObjects):
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
                hide_sketch_dimensions(sketch)
                count += 1

        set_sketch_color_rgb(sketch, SKETCH_YELLOW_RGB, inv.TransientObjects)
        hide_sketch_dimensions(sketch)

    print(f"{sketch_label} faces processed:", count)
    print(f"{sketch_label} sketches created:", created_sketches)
    print(f"{sketch_label} sketches reused:", reused_sketches)
    print(f"{sketch_label} faces skipped:", skipped_faces)


def sketch_mode():
    if len(sys.argv) > 1:
        return sys.argv[1].strip().lower()

    return "drilling"


def main():
    inv = get_inventor()
    doc = inv.ActiveDocument
    comp = doc.ComponentDefinition

    if not ensure_parameters(
        comp,
        (EDGE_OFFSET_FRAME_PARAM, EDGE_OFFSET_DRAWER_PARAM),
    ):
        return

    selected = selected_faces(doc, debug=True)
    if not selected:
        message = "Select one or more faces before running this script."
        show_message("No selected faces", message)
        print(message)
        return

    mode = sketch_mode()
    print("Selected faces:", len(selected))
    print("Sketch mode:", mode)

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

    doc.Update()


if __name__ == "__main__":
    main()
