# Окно выбора параметра отступа и получение списка параметров модели.
import tkinter as tk
from tkinter import ttk
from time import perf_counter
from common.constants import PARAMETERS

DEFAULT_FRAME_EDGE_OFFSET_PARAMS = (PARAMETERS.edge_offset,)


def choose_frame_edge_offset_parameter(inventor, parameter_cache=None):
    options = frame_edge_offset_parameter_options(inventor, parameter_cache=parameter_cache)
    selected = {"frame_edge_offset": None}
    root = tk.Tk()
    root.title("Выберите параметр отступа каркаса")
    root.geometry("620x180+80+80")
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
    status = ttk.Label(frame, text="Показаны пользовательские параметры отступа.")
    status.pack(anchor=tk.W, pady=(0, 8))
    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)

    def accept():
        selected["frame_edge_offset"] = value.get().strip()
        root.destroy()

    def cancel():
        root.destroy()

    def load_model_parameters():
        model_button.config(state=tk.DISABLED)
        status.config(text="Загрузка параметров модели…")
        root.update_idletasks()
        started = perf_counter()
        model_names = parameter_collection_names(
            getattr(inventor, "model_parameters", None), parameter_cache,
        )
        extra = sorted(name for name in model_names if "отступ" in name.lower())
        combo.config(values=unique_names((*options, *extra)))
        status.config(text="Параметры модели загружены.")
        print(f"05: Чтение параметров модели: {perf_counter() - started:.2f}s; "
              f"имён: {len(model_names)}", flush=True)

    model_button = ttk.Button(buttons, text="Загрузить параметры модели", command=load_model_parameters)
    model_button.pack(side=tk.LEFT)
    ttk.Button(buttons, text="OK", command=accept).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Отмена", command=cancel).pack(side=tk.RIGHT, padx=(0, 8))
    root.bind("<Return>", lambda event: accept())
    root.bind("<Escape>", lambda event: cancel())
    root.protocol("WM_DELETE_WINDOW", cancel)
    root.mainloop()
    return selected["frame_edge_offset"]


def frame_edge_offset_parameter_options(inventor, include_model=False, parameter_cache=None):
    started = perf_counter()
    names = all_parameter_names(inventor, include_model, parameter_cache)
    offset_names = [name for name in names if "отступ" in name.lower()]
    print(f"05: Чтение списка параметров: {perf_counter() - started:.2f}s; "
          f"имён: {len(names)}", flush=True)
    return unique_names((*DEFAULT_FRAME_EDGE_OFFSET_PARAMS, *sorted(offset_names)))


def all_parameter_names(inventor, include_model=True, parameter_cache=None):
    names = []
    collections = [getattr(inventor, "user_parameters", None)]
    if include_model:
        collections.append(getattr(inventor, "model_parameters", None))
    for collection in collections:
        if collection is not None:
            names.extend(parameter_collection_names(collection, parameter_cache))
    return unique_names(names)


def parameter_collection_names(collection, parameter_cache=None):
    names = []
    try:
        count = collection.Count
    except Exception:
        return names
    for index in range(1, count + 1):
        try:
            parameter = collection.Item(index)
            name = parameter.Name
            names.append(name)
            if parameter_cache is not None:
                parameter_cache.remember(name, parameter)
        except Exception:
            continue
    return names


def unique_names(names):
    return tuple((name for name in dict.fromkeys(names) if name))
