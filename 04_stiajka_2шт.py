from common.constants import DRILLING_SKETCH_PREFIX
from common.create_sketches import (
    create_sketches_for_faces,
    ensure_parameters,
    ensure_sketch_parameters,
)
from common.selected_workflow import (
    hide_sketches,
    selected_context,
)
from stiajka.stiajka import (
    cup_edge_offset_param_for_length,
    create_selected_cup_sketches,
    create_stiajka_features,
    split_stiajka_faces,
    stiajka_required_parameter_names,
)
from time import perf_counter


def log_elapsed(label, started):
    elapsed = perf_counter() - started
    print(f"{label}: {elapsed:.2f}s")
    return perf_counter()


def main():
    started = perf_counter()
    doc, comp, faces = selected_context("Stiajka 2pcs")
    if not faces:
        return
    if not ensure_sketch_parameters(comp):
        return
    if not ensure_parameters(comp, stiajka_required_parameter_names()):
        return
    started = log_elapsed("Selected context", started)
    end_faces, front_faces = split_stiajka_faces(faces)
    if not end_faces:
        print("Select end faces in one plane and one or more front faces.")
        return

    sketch_result = create_sketches_for_faces(
        doc.Parent,
        doc,
        end_faces,
        DRILLING_SKETCH_PREFIX,
        cup_edge_offset_param_for_length,
        "Drilling",
        "Selected end drilling",
        reuse_existing=False,
    )
    started = log_elapsed("Create sketches", started)

    cup_sketches = create_selected_cup_sketches(
        comp,
        doc.Parent,
        front_faces,
        end_faces,
        reuse_existing=False,
    )
    started = log_elapsed("Create cup sketches", started)

    sketches = sketch_result["sketches"]
    print("Selected stiajka sketches found:", len(sketches))
    created = create_stiajka_features(
        doc,
        sketches=sketches,
        colored_faces=end_faces,
        cup_sketches=cup_sketches,
        update_document=False,
    )
    started = log_elapsed("Create stiajka features", started)

    hide_sketches(sketches, "Stiajka")
    hide_sketches(cup_sketches, "Stiajka cup")
    doc.Update()
    log_elapsed("Hide sketches and update", started)
    print("Stiajka features created:", created)


if __name__ == "__main__":
    main()
