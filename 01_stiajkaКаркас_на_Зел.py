from common.face_utils import get_green_faces, reset_faces_to_feature_appearance
from common.inventor_connection import get_inventor
from stiajka.stiajka import create_stiajka_features, find_stiajka_sketches_on_green_faces


def main():
    inv = get_inventor()
    doc = inv.ActiveDocument
    comp = doc.ComponentDefinition
    green_faces_before = get_green_faces(comp)
    sketches = find_stiajka_sketches_on_green_faces(comp)
    print("Green stiajka sketches found:", len(sketches))
    created = create_stiajka_features(doc, sketches, green_faces_before)
    green_faces_after = get_green_faces(comp)
    reset_count = reset_faces_to_feature_appearance(
        green_faces_before + green_faces_after,
        "green face",
    )
    print("Green faces reset to feature appearance:", reset_count)
    doc.Update()
    print("Stiajka frame features created:", created)


if __name__ == "__main__":
    main()
