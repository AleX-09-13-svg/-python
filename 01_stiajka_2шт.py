from contextlib import contextmanager
from common.constants import DRILLING_SKETCH_PREFIX
from common.create_sketches import create_sketches_for_faces, ensure_sketch_parameters
from common.selected_workflow import hide_sketches, selected_context
from stiajka.stiajka import create_stiajka_features, find_stiajka_sketches_on_faces
from time import perf_counter


def log_elapsed(label, started):
    elapsed = perf_counter() - started
    print(f"{label}: {elapsed:.2f}s")
    return perf_counter()


@contextmanager
def screen_updates_suspended(inv):
    previous_screen_updating = None
    previous_silent_operation = None
    screen_updating_changed = False
    silent_operation_changed = False

    try:
        previous_screen_updating = inv.ScreenUpdating
        inv.ScreenUpdating = False
        screen_updating_changed = True
    except Exception:
        pass

    try:
        previous_silent_operation = inv.SilentOperation
        inv.SilentOperation = True
        silent_operation_changed = True
    except Exception:
        pass

    try:
        yield
    finally:
        if silent_operation_changed:
            try:
                inv.SilentOperation = previous_silent_operation
            except Exception:
                pass

        if screen_updating_changed:
            try:
                inv.ScreenUpdating = previous_screen_updating
            except Exception:
                pass


def main():
    started = perf_counter()
    doc, comp, faces = selected_context("Stiajka 2pcs")
    if not faces:
        return
    if not ensure_sketch_parameters(comp):
        return
    started = log_elapsed("Selected context", started)

    with screen_updates_suspended(doc.Parent):
        create_sketches_for_faces(
            doc.Parent,
            doc,
            faces,
            DRILLING_SKETCH_PREFIX,
            None,
            "Drilling",
            "Selected drilling",
        )
        started = log_elapsed("Create sketches", started)

        sketches = find_stiajka_sketches_on_faces(comp, faces, DRILLING_SKETCH_PREFIX)
        started = log_elapsed("Find stiajka sketches", started)
        print("Selected stiajka sketches found:", len(sketches))
        created = create_stiajka_features(
            doc,
            sketches=sketches,
            colored_faces=faces,
            update_document=False,
        )
        started = log_elapsed("Create stiajka features", started)
        hide_sketches(sketches, "Stiajka")
        log_elapsed("Hide sketches", started)
    print("Stiajka features created:", created)


if __name__ == "__main__":
    main()
