import ctypes
import runpy
import sys
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
