import ctypes
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

from common.face_utils import selected_faces
from common.inventor_connection import get_inventor


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREATE_SKETCHES_SCRIPT = PROJECT_ROOT / "00_createSketches.py"


def show_message(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)


def selected_context(operation_label):
    inv = get_inventor()
    doc = inv.ActiveDocument
    faces = selected_faces(doc, debug=True)

    if not faces:
        message = f"Select one or more faces before running {operation_label}."
        show_message("No selected faces", message)
        print(message)
        return None, None, []

    print(f"Selected {operation_label} faces:", len(faces))
    return doc, doc.ComponentDefinition, faces


def run_create_sketches(*args):
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(CREATE_SKETCHES_SCRIPT), *args]
        runpy.run_path(str(CREATE_SKETCHES_SCRIPT), run_name="__main__")
    finally:
        sys.argv = old_argv


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


def hide_sketches(sketches, label):
    hidden = 0

    for sketch in sketches:
        try:
            sketch.Visible = False
        except Exception as exc:
            try:
                name = sketch.Name
            except Exception:
                name = "<unknown>"
            print("Sketch visibility hide failed:", name, exc)
            continue

        hidden += 1

    print(f"{label} sketches hidden:", hidden)
