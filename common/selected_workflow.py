import ctypes
import runpy
import sys
from contextlib import contextmanager
from pathlib import Path

from common.inventor_connection import get_inventor_service


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CREATE_SKETCHES_SCRIPT = PROJECT_ROOT / "00_createSketches.py"


def show_message(title, text):
    ctypes.windll.user32.MessageBoxW(0, text, title, 0x40)


def selected_context(operation_label):
    inventor, faces = selected_inventor_context(operation_label)
    return inventor, faces


def selected_inventor_context(operation_label):
    inventor = get_inventor_service()
    faces = inventor.selected_faces(debug=True)

    if not faces:
        message = f"Select one or more faces before running {operation_label}."
        show_message("No selected faces", message)
        print(message, flush=True)
        return inventor, []

    print(f"Selected {operation_label} faces:", len(faces), flush=True)
    return inventor, faces


def run_create_sketches(*args):
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(CREATE_SKETCHES_SCRIPT), *args]
        runpy.run_path(str(CREATE_SKETCHES_SCRIPT), run_name="__main__")
    finally:
        sys.argv = old_argv


@contextmanager
def screen_updates_suspended(inv):
    with inv.screen_updates_suspended():
        yield


def hide_sketches(sketches, label):
    hidden = 0
    inventor = get_inventor_service()

    for sketch in sketches:
        if inventor.set_sketch_visible(sketch, False) is None:
            name = inventor.safe_getattr(sketch, "Name", "<unknown>")
            print("Sketch visibility hide failed:", name)
            continue

        hidden += 1

    print(f"{label} sketches hidden:", hidden)
