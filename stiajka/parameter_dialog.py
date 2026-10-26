# Окно выбора параметра отступа и получение списка параметров модели.
import tkinter as tk
from tkinter import ttk
from common.constants import PARAMETERS

DEFAULT_FRAME_EDGE_OFFSET_PARAMS = (PARAMETERS.edge_offset,)


def choose_frame_edge_offset_parameter(inventor):
    options = frame_edge_offset_parameter_options(inventor)
    selected = {"frame_edge_offset": None}
    root = tk.Tk()
    root.title("Выберите параметр отступа каркаса")
    root.geometry("560x140+80+80")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    label = ttk.Label(frame, text="Параметр Минимальный_отступ_присадки_от_кромки_Каркас:")
    label.pack(anchor=tk.W)
    value = tk.StringVar(value=options[0] if options else "")
    combo = ttk.Combobox(frame, textvariable=value, values=options, state="readonly")
    combo.pack(fill=tk.X, pady=(6, 12))
    combo.focus_set()
    combo.selection_range(0, tk.END)
    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)

    def accept():
        selected["frame_edge_offset"] = value.get().strip()
        root.destroy()

    def cancel():
        root.destroy()

    ttk.Button(buttons, text="OK", command=accept).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Отмена", command=cancel).pack(side=tk.RIGHT, padx=(0, 8))
    root.bind("<Return>", lambda event: accept())
    root.bind("<Escape>", lambda event: cancel())
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return selected["frame_edge_offset"]


def frame_edge_offset_parameter_options(inventor):
    names = all_parameter_names(inventor)
    offset_names = [name for name in names if "отступ" in name.lower()]
    return unique_names((*DEFAULT_FRAME_EDGE_OFFSET_PARAMS, *sorted(offset_names)))


def all_parameter_names(inventor):
    names = []
    for collection in (
        getattr(inventor, "user_parameters", None),
        getattr(inventor, "model_parameters", None),
    ):
        if collection is not None:
            names.extend(parameter_collection_names(collection))
    return unique_names(names)


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


def unique_names(names):
    return tuple((name for name in dict.fromkeys(names) if name))
