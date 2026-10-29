# Выбор параметра и назначение размеров длины выбранным линиям 2D-эскиза.
import math
import tkinter as tk
from tkinter import ttk

import pythoncom

from common.constants import ALIGNED_DIM, PARAMETERS

# ObjectTypeEnum и DimensionOrientationEnum API Inventor.
PLANAR_SKETCH = 83924736
SKETCH_LINE = 83896064
TWO_POINT_DIMENSION = 83905792
HORIZONTAL_DIM = 19201
VERTICAL_DIM = 19202


def same_entity(first, second):
    """Сравнить COM-объекты по IUnknown, а не по координатам или Python id."""
    if first is second:
        return True
    return first._oleobj_.QueryInterface(pythoncom.IID_IUnknown) == second._oleobj_.QueryInterface(
        pythoncom.IID_IUnknown
    )


def selected_sketch_lines(app, document):
    sketch = app.ActiveEditObject
    if sketch is None or int(sketch.Type) != PLANAR_SKETCH:
        raise ValueError("Откройте 2D-эскиз для редактирования и выделите нужные отрезки.")
    lines = []
    ignored = 0
    selection = document.SelectSet
    for index in range(1, selection.Count + 1):
        entity = selection.Item(index)
        if int(entity.Type) != SKETCH_LINE or not same_entity(entity.Parent, sketch):
            ignored += 1
            continue
        if not any(same_entity(entity, line) for line in lines):
            lines.append(entity)
    if not lines:
        raise ValueError("Выделите отрезки активного эскиза, затем запустите правило ещё раз.")
    for index, line in enumerate(lines, start=1):
        if line.Reference or line.HasReferenceComponent:
            raise ValueError(
                f"Отрезок {index} — зависимая проекция. Его длиной управляет исходная геометрия."
            )
    return sketch, lines, ignored


def line_dimension(sketch, line):
    """Найти размер между концами линии, управляющий её полной длиной."""
    start, end = line.StartSketchPoint, line.EndSketchPoint
    a, b = start.Geometry, end.Geometry
    horizontal = abs(a.Y - b.Y) < 1e-8
    vertical = abs(a.X - b.X) < 1e-8
    matches = []
    dimensions = sketch.DimensionConstraints
    for index in range(1, dimensions.Count + 1):
        dimension = dimensions.Item(index)
        if int(dimension.Type) != TWO_POINT_DIMENSION:
            continue
        first, second = dimension.PointOne, dimension.PointTwo
        if not (
            (same_entity(first, start) and same_entity(second, end))
            or (same_entity(first, end) and same_entity(second, start))
        ):
            continue
        orientation = int(dimension.Orientation)
        if (
            orientation == int(ALIGNED_DIM)
            or (horizontal and orientation == HORIZONTAL_DIM)
            or (vertical and orientation == VERTICAL_DIM)
        ):
            matches.append(dimension)
    driving = [dimension for dimension in matches if not dimension.Driven]
    candidates = driving or matches
    if len(candidates) > 1:
        raise ValueError("Между концами отрезка несколько размеров; уточните зависимости в эскизе.")
    return candidates[0] if candidates else None


def length_parameters(document, sketch, lines):
    # Не предлагать размеры выбранных линий: ссылка на себя создаст цикл.
    excluded = set()
    for line in lines:
        dimension = line_dimension(sketch, line)
        if dimension is not None:
            excluded.add(dimension.Parameter.Name)
    parameters = document.ComponentDefinition.Parameters
    names = set()
    for collection in (parameters.UserParameters, parameters.ModelParameters):
        for index in range(1, collection.Count + 1):
            parameter = collection.Item(index)
            try:
                document.UnitsOfMeasure.ConvertUnits(1, parameter.Units, "cm")
                positive = float(parameter.Value) > 0
            except Exception:
                continue  # Текст, углы и безразмерные параметры не задают длину.
            if positive and parameter.Name not in excluded:
                names.add(parameter.Name)
    return sorted(names, key=lambda name: (name != PARAMETERS.frame_thickness, name.casefold()))


def choose_length_parameter(names, line_count):
    result = None
    root = tk.Tk()
    root.title("Размер выбранных отрезков")
    root.geometry("620x155+80+80")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill=tk.BOTH, expand=True)
    ttk.Label(frame, text=f"Параметр длины для всех выбранных отрезков ({line_count}):").pack(
        anchor=tk.W
    )
    value = tk.StringVar(value=names[0])
    combo = ttk.Combobox(frame, textvariable=value, values=names, state="readonly")
    combo.pack(fill=tk.X, pady=(8, 12))
    combo.focus_set()

    def accept():
        nonlocal result
        result = value.get()
        root.destroy()

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X)
    ttk.Button(buttons, text="Применить", command=accept).pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Отмена", command=root.destroy).pack(side=tk.RIGHT, padx=(0, 8))
    root.bind("<Return>", lambda event: accept())
    root.bind("<Escape>", lambda event: root.destroy())
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    return result


def apply_line_parameter(inventor, document, sketch, lines, parameter_name):
    source = document.ComponentDefinition.Parameters.Item(parameter_name)
    document.UnitsOfMeasure.ConvertUnits(1, source.Units, "cm")
    if float(source.Value) <= 0:
        raise ValueError("Параметр длины должен быть больше нуля.")
    expression = source.Name
    created = updated = 0
    errors = []
    for index, line in enumerate(lines, start=1):
        transaction = None
        try:
            # Отдельная транзакция: ошибка этой линии не отменяет предыдущие.
            transaction = inventor.app.TransactionManager.StartTransaction(
                document, f"Параметр длины отрезка {index}"
            )
            dimension = line_dimension(sketch, line)
            is_new = dimension is None
            if is_new:
                start, end = line.StartSketchPoint, line.EndSketchPoint
                a, b = start.Geometry, end.Geometry
                dx, dy = b.X - a.X, b.Y - a.Y
                length = math.hypot(dx, dy)
                if length <= 1e-10:
                    raise ValueError("Нельзя задать длину нулевого отрезка.")
                offset = max(length * 0.3, 0.5)  # Сантиметры Inventor.
                text = inventor.create_point2d(
                    (a.X + b.X) / 2 - dy / length * offset,
                    (a.Y + b.Y) / 2 + dx / length * offset,
                )
                dimension = inventor.add_aligned_dimension(sketch, start, end, text)
            else:
                if dimension.Parameter.Name == expression:
                    raise ValueError("Нельзя привязать размер к самому себе.")
                if dimension.Driven:
                    dimension.Driven = False
            dimension.Parameter.Expression = expression
            sketch.Solve()
            # Оставить эскиз и назначенные размеры видимыми.
            sketch.Visible = True
            sketch.DimensionsVisible = True
            transaction.End()
        except Exception as exc:
            if transaction is not None:
                try:
                    transaction.Abort()
                except Exception as abort_exc:
                    raise RuntimeError(
                        f"Ошибка отрезка {index}: {exc}. Не удалось отменить его изменения: {abort_exc}"
                    ) from exc
            message = f"Отрезок {index}: {exc}"
            errors.append(message)
            print(f"ПРОПУЩЕН — {message}", flush=True)
            continue
        # Сообщать об успехе только после пересчёта и завершения транзакции.
        created += int(is_new)
        updated += int(not is_new)
        print(f"Сохранено: отрезок {index}/{len(lines)} = {expression}", flush=True)

    if created or updated:
        try:
            inventor.update()
        except Exception as exc:
            print(
                f"Размеры назначены, но обновление документа завершилось ошибкой: {exc}",
                flush=True,
            )
    # Обновление детали может менять видимость использованного эскиза.
    sketch.Visible = True
    sketch.DimensionsVisible = True
    return created, updated, errors
