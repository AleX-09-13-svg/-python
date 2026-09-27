from common.selected_workflow import hide_sketches, run_create_sketches, selected_context
from confirmat.confirmat import (
    create_confirmat_2_features,
    find_confirmat_sketches_on_faces,
)


def main():
    doc, comp, faces = selected_context("Confirmat 2pcs")
    if not faces:
        return

    run_create_sketches()
    doc.Update()

    sketches = find_confirmat_sketches_on_faces(comp, faces, "selected")
    created = create_confirmat_2_features(
        doc,
        sketches=sketches,
        faces=faces,
        face_label="selected",
    )
    hide_sketches(sketches, "Confirmat 2pcs")
    doc.Update()
    print("Confirmat 2pcs hole features created:", created)


if __name__ == "__main__":
    main()
