# Выбор толщины и фиксированного отступа двух пар конфирматов.
import tkinter as tk
from tkinter import ttk
from common.constants import PARAMETERS
from stiajka.parameter_dialog import parameter_collection_names as cached_parameter_names

DEFAULT_THICKNESS_PARAMS = ("Толщина_каркаса_МДФ", "Толщина_каркаса_ШПОН", "Толщина_каркаса")
DEFAULT_FRAME_EDGE_OFFSET_PARAMS = (PARAMETERS.edge_offset,)
DEFAULT_CONFIRMAT_COUNT_PARAMS = ("Количество_конфирматов", "Конфирмат_количество")


def user_parameter_options(names, preferred):
    """Все существующие пользовательские параметры; подходящие — первыми."""
    available = set(names)
    return unique_names((*[name for name in preferred if name in available], *sorted(names)))


def choose_workflow_parameters(inventor, parameter_cache=None, *, two_confirmats=False):
    from tkinter import messagebox

    selected = [None, None]
    names = all_parameter_names(inventor, include_model=False, parameter_cache=parameter_cache)
    thickness_options = user_parameter_options(names, thickness_parameter_options(names))
    offset_options = user_parameter_options(names, frame_edge_offset_parameter_options(names))
    root = tk.Tk()
    root.title("Конфирматы — 2 шт., шаг 32 мм" if two_confirmats
               else "Конфирматы — две пары по 96 мм и один по центру")
    root.geometry("680x280+80+80")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(frame, text="Параметр толщины материала:").pack(anchor=tk.W)
    thickness_value = tk.StringVar(value=thickness_options[0] if thickness_options else "")
    thickness_combo = ttk.Combobox(frame, textvariable=thickness_value,
                                  values=thickness_options, state="readonly")
    thickness_combo.pack(fill=tk.X, pady=(6, 10))
    offset_label = ("Пользовательский параметр минимального отступа от края до центра:"
                    if two_confirmats else "Пользовательский параметр отступа от края до ближайшего центра:")
    ttk.Label(frame, text=offset_label).pack(anchor=tk.W)
    offset_value = tk.StringVar(value=offset_options[0] if offset_options else "")
    offset_combo = ttk.Combobox(frame, textvariable=offset_value,
                               values=offset_options, state="readonly")
    offset_combo.pack(fill=tk.X, pady=(6, 10))
    description = ("Два конфирмата симметрично; расстояние между центрами кратно 32 мм."
                   if two_confirmats else "Всего 5 конфирматов: две пары по 96 мм и один по центру.")
    hint = ("Фактический отступ с каждого края не меньше выбранного минимума."
            if two_confirmats else "Расстояние между парами определяется длиной грани.")
    ttk.Label(frame, text=description).pack(anchor=tk.W)
    ttk.Label(frame, text=hint).pack(anchor=tk.W, pady=(0, 12))
    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)

    def accept():
        thickness = thickness_value.get().strip()
        if thickness not in names:
            messagebox.showerror("Параметры присадки", "Выберите параметр толщины материала.", parent=root)
            return
        offset = offset_value.get().strip()
        if offset not in names:
            messagebox.showerror("Параметры присадки", "Выберите пользовательский параметр отступа.", parent=root)
            offset_combo.focus_set()
            return
        selected[:] = [thickness, offset]
        root.destroy()

    ttk.Button(buttons, text="OK", command=accept).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Отмена", command=root.destroy).pack(side=tk.RIGHT, padx=(0, 8))
    thickness_combo.focus_set()
    thickness_combo.selection_range(0, tk.END)
    root.bind("<Return>", lambda event: accept())
    root.bind("<Escape>", lambda event: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return tuple(selected)


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


def all_parameter_names(inventor, include_model=True, parameter_cache=None):
    names = []

    collections = [getattr(inventor, "user_parameters", None)]
    if include_model:
        collections.append(getattr(inventor, "model_parameters", None))
    for collection in collections:
        if collection is not None:
            names.extend(cached_parameter_names(collection, parameter_cache))

    return unique_names(names)
