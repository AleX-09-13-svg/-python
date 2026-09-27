from common.constants import DRILLING_SKETCH_PREFIX
from common.create_sketches import create_sketches_for_faces, ensure_sketch_parameters
from common.selected_workflow import hide_sketches, selected_context
from confirmat.confirmat import create_confirmat_features, find_confirmat_sketches_on_faces


def main():
    doc, comp, faces = selected_context("Confirmat 3pcs")
    if not faces:
        return
    if not ensure_sketch_parameters(comp):
        return

    create_sketches_for_faces(
        doc.Parent,
        doc,
        faces,
        DRILLING_SKETCH_PREFIX,
        None,
        "Drilling",
        "Selected drilling",
    )

    sketches = find_confirmat_sketches_on_faces(comp, faces, "selected")
    created = create_confirmat_features(
        doc,
        sketches=sketches,
        faces=faces,
        face_label="selected",
    )
    hide_sketches(sketches, "Confirmat 3pcs")
    print("Confirmat 3pcs hole features created:", created)


if __name__ == "__main__":
    main()
