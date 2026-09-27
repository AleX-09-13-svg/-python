from common.constants import DRILLING_SKETCH_PREFIX
from common.selected_workflow import hide_sketches, run_create_sketches, selected_context
from stiajka.stiajka import create_stiajka_features, find_stiajka_sketches_on_faces


def main():
    doc, comp, faces = selected_context("Stiajka 2pcs")
    if not faces:
        return

    run_create_sketches()
    doc.Update()

    sketches = find_stiajka_sketches_on_faces(comp, faces, DRILLING_SKETCH_PREFIX)
    print("Selected stiajka sketches found:", len(sketches))
    created = create_stiajka_features(doc, sketches=sketches, colored_faces=faces)
    hide_sketches(sketches, "Stiajka")
    doc.Update()
    print("Stiajka features created:", created)


if __name__ == "__main__":
    main()
