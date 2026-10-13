import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import ttk

from common.constants import DRILLING_SKETCH_PREFIX
import common.create_sketches as create_sketches
from common.selected_workflow import hide_sketches, selected_inventor_context
from common.settings import load_settings
import confirmat.confirmat as confirmat_module


DEFAULT_THICKNESS_PARAMS = (
    "\u0422\u043e\u043b\u0449\u0438\u043d\u0430_\u043a\u0430\u0440\u043a\u0430\u0441\u0430_\u041c\u0414\u0424",
    "\u0422\u043e\u043b\u0449\u0438\u043d\u0430_\u043a\u0430\u0440\u043a\u0430\u0441\u0430_\u0428\u041f\u041e\u041d",
    "\u0422\u043e\u043b\u0449\u0438\u043d\u0430_\u043a\u0430\u0440\u043a\u0430\u0441\u0430",
)
DEFAULT_FRAME_EDGE_OFFSET_PARAMS = (
    "\u041c\u0438\u043d\u0438\u043c\u0430\u043b\u044c\u043d\u044b\u0439_\u043e\u0442\u0441\u0442\u0443\u043f_\u043f\u0440\u0438\u0441\u0430\u0434\u043a\u0438_\u043e\u0442_\u043a\u0440\u043e\u043c\u043a\u0438_\u041a\u0430\u0440\u043a\u0430\u0441",
)
DEFAULT_CONFIRMAT_COUNT_PARAMS = (
    "\u041a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e_\u043a\u043e\u043d\u0444\u0438\u0440\u043c\u0430\u0442\u043e\u0432",
    "\u041a\u043e\u043d\u0444\u0438\u0440\u043c\u0430\u0442_\u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u043e",
)


LOG_PATH = Path(__file__).resolve().with_suffix(".log")
KEEP_EXCEL_UNITLESS_PARAMS_NAME = "Keep_Excel_Params_Unitless"


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for stream in self.streams:
            try:
                stream.write(text)
                stream.flush()
            except Exception:
                pass

    def flush(self):
        for stream in self.streams:
            try:
                stream.flush()
            except Exception:
                pass


def unique_names(names):
    return tuple(name for name in dict.fromkeys(names) if name)


def parameter_collection_names(collection):
    names = []

    try:
        count = collection.Count
    except Exception:
        return names

    for index in range(1, count + 1):
        try:
            names.append(collection.Item(index).Name)
        except Exception:
            continue

    return names


def all_parameter_names(inventor):
    names = []

    for collection in (
        getattr(inventor, "user_parameters", None),
        getattr(inventor, "model_parameters", None),
    ):
        if collection is not None:
            names.extend(parameter_collection_names(collection))

    return unique_names(names)


def thickness_parameter_options(inventor):
    names = all_parameter_names(inventor)
    thickness_names = [
        name
        for name in names
        if "\u0442\u043e\u043b\u0449\u0438\u043d\u0430" in name.lower()
    ]
    return unique_names((*DEFAULT_THICKNESS_PARAMS, *sorted(thickness_names)))


def frame_edge_offset_parameter_options(inventor):
    names = all_parameter_names(inventor)
    offset_names = [
        name
        for name in names
        if "\u043e\u0442\u0441\u0442\u0443\u043f" in name.lower()
    ]
    return unique_names((*DEFAULT_FRAME_EDGE_OFFSET_PARAMS, *sorted(offset_names)))


def confirmat_count_parameter_options(inventor):
    names = all_parameter_names(inventor)
    count_names = [
        name
        for name in names
        if (
            "\u043a\u043e\u043d\u0444\u0438\u0440\u043c\u0430\u0442" in name.lower()
            or "\u043a\u043e\u043b" in name.lower()
        )
    ]
    return unique_names((*DEFAULT_CONFIRMAT_COUNT_PARAMS, *sorted(count_names)))


def choose_workflow_parameters(inventor):
    selected = {
        "thickness": None,
        "frame_edge_offset": None,
        "confirmat_count_param": None,
    }
    thickness_options = thickness_parameter_options(inventor)
    offset_options = frame_edge_offset_parameter_options(inventor)
    count_options = confirmat_count_parameter_options(inventor)

    root = tk.Tk()
    root.title("\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u043f\u0440\u0438\u0441\u0430\u0434\u043a\u0438")
    root.geometry("560x250+80+80")
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    thickness_label = ttk.Label(
        frame,
        text="\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440 \u0442\u043e\u043b\u0449\u0438\u043d\u044b \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u0430:",
    )
    thickness_label.pack(anchor=tk.W)

    thickness_value = tk.StringVar(
        value=thickness_options[0] if thickness_options else "",
    )
    thickness_combo = ttk.Combobox(
        frame,
        textvariable=thickness_value,
        values=thickness_options,
        state="normal",
    )
    thickness_combo.pack(fill=tk.X, pady=(6, 10))

    offset_label = ttk.Label(
        frame,
        text="\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440 \u043e\u0442\u0441\u0442\u0443\u043f\u0430 \u043e\u0442 \u043a\u0440\u043e\u043c\u043a\u0438 \u043a\u0430\u0440\u043a\u0430\u0441\u0430:",
    )
    offset_label.pack(anchor=tk.W)

    offset_value = tk.StringVar(value=offset_options[0] if offset_options else "")
    offset_combo = ttk.Combobox(
        frame,
        textvariable=offset_value,
        values=offset_options,
        state="normal",
    )
    offset_combo.pack(fill=tk.X, pady=(6, 12))

    count_label = ttk.Label(
        frame,
        text="\u041f\u0430\u0440\u0430\u043c\u0435\u0442\u0440 \u043a\u043e\u043b\u0438\u0447\u0435\u0441\u0442\u0432\u0430 \u043a\u043e\u043d\u0444\u0438\u0440\u043c\u0430\u0442\u043e\u0432:",
    )
    count_label.pack(anchor=tk.W)

    count_value = tk.StringVar(value=count_options[0] if count_options else "")
    count_combo = ttk.Combobox(
        frame,
        textvariable=count_value,
        values=count_options,
        state="normal",
    )
    count_combo.pack(fill=tk.X, pady=(6, 12))
    thickness_combo.focus_set()
    thickness_combo.selection_range(0, tk.END)

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)

    def accept():
        selected["thickness"] = thickness_value.get().strip()
        selected["frame_edge_offset"] = offset_value.get().strip()
        selected["confirmat_count_param"] = count_value.get().strip()
        root.destroy()

    def cancel():
        root.destroy()

    ok_button = ttk.Button(buttons, text="OK", command=accept)
    ok_button.pack(side=tk.RIGHT)
    cancel_button = ttk.Button(buttons, text="\u041e\u0442\u043c\u0435\u043d\u0430", command=cancel)
    cancel_button.pack(side=tk.RIGHT, padx=(0, 8))

    root.bind("<Return>", lambda event: accept())
    root.bind("<Escape>", lambda event: cancel())
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()

    return (
        selected["thickness"],
        selected["frame_edge_offset"],
        selected["confirmat_count_param"],
    )


def use_material_thickness(thickness_param):
    create_sketches.FRAME_THICKNESS_PARAM = thickness_param
    confirmat_module.FRAME_THICKNESS_PARAM = thickness_param
    settings = load_settings()["confirmat"]
    settings["outer_2pcs"]["depth"] = thickness_param
    settings["outer_3pcs"]["depth"] = thickness_param


def use_frame_edge_offset(edge_offset_param):
    create_sketches.EDGE_OFFSET_FRAME_PARAM = edge_offset_param


def is_parameter_name(value):
    if not isinstance(value, str):
        return False

    text = value.strip()
    if not text:
        return False

    if any(char.isdigit() for char in text):
        return False

    return True


def confirmat_parameter_names(confirmat_count=None):
    settings = load_settings()["confirmat"]
    names = []

    for section_name in ("outer_2pcs", "inner_2pcs", "outer_3pcs", "inner_3pcs"):
        section = settings.get(section_name, {})
        for key in ("diameter", "depth"):
            value = section.get(key)
            if is_parameter_name(value):
                names.append(value)

    return tuple(dict.fromkeys(names))


def resolve_confirmat_count(inventor, count_param):
    value = inventor.parameter_value(count_param, None)
    expression = inventor.parameter_expression(count_param, "")

    candidates = (value, expression)
    for candidate in candidates:
        if candidate is None:
            continue

        text = str(candidate).strip().lower()
        if text.startswith("2"):
            return "2"
        if text.startswith("3"):
            return "3"

        try:
            rounded = str(int(round(float(candidate))))
        except (TypeError, ValueError):
            continue

        if rounded in ("2", "3"):
            return rounded

    print(
        "Confirmat count parameter must have value 2 or 3:",
        count_param,
        "value=",
        value,
        "expression=",
        expression,
    )
    return None


def ensure_unitless_keep_parameter(inventor, name, referenced_parameter_names):
    expression = " + ".join(f"{param} * 0" for param in referenced_parameter_names)
    if not expression:
        expression = "0"

    parameter = inventor.ensure_user_parameter(name, expression, units="ul")
    parameter.Expression = expression
    return parameter


def main():
    inventor, faces = selected_inventor_context("Confirmat 2pcs")
    if not faces:
        return

    (
        thickness_param,
        frame_edge_offset_param,
        confirmat_count_param,
    ) = choose_workflow_parameters(inventor)
    if not thickness_param:
        print("Material thickness parameter was not selected")
        return

    print("Material thickness parameter:", thickness_param)
    use_material_thickness(thickness_param)

    if not frame_edge_offset_param:
        print("Frame edge offset parameter was not selected")
        return

    print("Frame edge offset parameter:", frame_edge_offset_param)
    use_frame_edge_offset(frame_edge_offset_param)

    if not confirmat_count_param:
        print("Confirmat count parameter was not selected")
        return

    print("Confirmat count parameter:", confirmat_count_param)

    base_required_parameters = (
        create_sketches.EDGE_OFFSET_FRAME_PARAM,
        create_sketches.EDGE_OFFSET_DRAWER_PARAM,
        create_sketches.FRAME_THICKNESS_PARAM,
        confirmat_count_param,
    )
    if not create_sketches.ensure_parameters(inventor, base_required_parameters):
        return

    confirmat_count = resolve_confirmat_count(inventor, confirmat_count_param)
    if confirmat_count not in ("2", "3"):
        return

    print("Confirmat count:", confirmat_count)

    required_parameters = (
        *base_required_parameters,
        *confirmat_parameter_names(),
    )
    if not create_sketches.ensure_parameters(inventor, required_parameters):
        return

    keep_parameters = tuple(
        parameter
        for parameter in required_parameters
        if parameter != confirmat_count_param
    )
    inventor.ensure_keep_parameter(
        create_sketches.KEEP_EXCEL_PARAMS_NAME,
        keep_parameters,
    )
    ensure_unitless_keep_parameter(
        inventor,
        KEEP_EXCEL_UNITLESS_PARAMS_NAME,
        (confirmat_count_param,),
    )

    sketches = create_sketches.create_sketches_for_faces(
        inventor,
        None,
        faces,
        DRILLING_SKETCH_PREFIX,
        None,
        "Drilling",
        "Selected drilling",
        use_offset_plane=True,
        offset_param=thickness_param,
    )
    if create_sketches.should_update_document():
        inventor.update()

    created = confirmat_module.create_confirmat_edges_and_center_features(
        inventor,
        sketches=sketches,
        faces=faces,
        face_label="selected",
        direction="positive",
        center_suppressed=confirmat_count == "2",
        center_suppression_parameter=confirmat_count_param,
        center_suppression_value=2,
    )

    if created:
        hide_sketches(sketches, f"Confirmat {confirmat_count}pcs")
    else:
        print(
            f"Confirmat {confirmat_count}pcs sketches left visible because "
            "no hole features were created"
        )
    print(f"Confirmat {confirmat_count}pcs hole features created:", created)


if __name__ == "__main__":
    with LOG_PATH.open("w", encoding="utf-8") as log:
        sys.stdout = Tee(sys.__stdout__, log)
        sys.stderr = Tee(sys.__stderr__, log)
        print("Running:", Path(__file__).name, flush=True)
        print("Log:", LOG_PATH, flush=True)
        try:
            main()
        except Exception:
            traceback.print_exc()
            raise
