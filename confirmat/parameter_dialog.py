# Выбор толщины, отступа и параметра количества конфирматов.
import tkinter as tk
from tkinter import ttk
from common.constants import PARAMETERS

DEFAULT_THICKNESS_PARAMS = ("Толщина_каркаса_МДФ", "Толщина_каркаса_ШПОН", "Толщина_каркаса")
DEFAULT_FRAME_EDGE_OFFSET_PARAMS = (PARAMETERS.edge_offset,)
DEFAULT_CONFIRMAT_COUNT_PARAMS = ("Количество_конфирматов", "Конфирмат_количество")


def choose_workflow_parameters(inventor):
    selected = {
        "thickness": None,
        "frame_edge_offset": None,
        "confirmat_count_param": None,
    }
    names = all_parameter_names(inventor)
    thickness_options = thickness_parameter_options(names)
    offset_options = frame_edge_offset_parameter_options(names)
    count_options = confirmat_count_parameter_options(names)

    root = tk.Tk()
    root.title(
        "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043f\u0430\u0440\u0430\u043c\u0435\u0442\u0440\u044b \u043f\u0440\u0438\u0441\u0430\u0434\u043a\u0438"
    )
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


def thickness_parameter_options(names):
    thickness_names = [
        name for name in names if "\u0442\u043e\u043b\u0449\u0438\u043d\u0430" in name.lower()
    ]
    return unique_names((*DEFAULT_THICKNESS_PARAMS, *sorted(thickness_names)))


def frame_edge_offset_parameter_options(names):
    offset_names = [
        name for name in names if "\u043e\u0442\u0441\u0442\u0443\u043f" in name.lower()
    ]
    return unique_names((*DEFAULT_FRAME_EDGE_OFFSET_PARAMS, *sorted(offset_names)))


def confirmat_count_parameter_options(names):
    count_names = [
        name
        for name in names
        if (
            "\u043a\u043e\u043d\u0444\u0438\u0440\u043c\u0430\u0442" in name.lower()
            or "\u043a\u043e\u043b" in name.lower()
        )
    ]
    return unique_names((*DEFAULT_CONFIRMAT_COUNT_PARAMS, *sorted(count_names)))


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
