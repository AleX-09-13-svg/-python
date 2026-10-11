# Учебный пример:
# создание отверстия на выбранной плоской грани детали Autodesk Inventor.
#
# Перед запуском:
# 1. Открой деталь в Inventor.
# 2. Выбери плоскую грань, на которой нужно сделать отверстие.
# 3. Запусти этот Python-скрипт.


# 1) Импорт библиотек
import pythoncom
import win32com.client.dynamic

# 2) Настройки скрипта
HOLE_DIAMETER = "5 mm"
HOLE_DEPTH = "10 mm"

# Направление отверстия.
# Если отверстие строится не в ту сторону, поменяй False на True.
INVERT_HOLE_DIRECTION = False

# Константы Inventor для направления выдавливания/отверстия
POSITIVE_EXTENT_DIRECTION = 20993
NEGATIVE_EXTENT_DIRECTION = 20994


# 3) Подключение к уже запущенному Autodesk Inventor
def get_inventor():
    inventor_unknown = pythoncom.GetActiveObject("Inventor.Application")
    inventor_dispatch = inventor_unknown.QueryInterface(pythoncom.IID_IDispatch)
    return win32com.client.dynamic.Dispatch(inventor_dispatch)


# 4) Проверка, что в Inventor открыт документ
def get_active_document(inv):
    if inv.Documents.Count == 0:
        raise RuntimeError("Нет открытых документов в Inventor.")

    return inv.ActiveDocument


# 5) Получение выбранной грани
def get_selected_face(doc):
    if doc.SelectSet.Count == 0:
        raise RuntimeError("Сначала выбери плоскую грань детали в Inventor.")

    return doc.SelectSet.Item(1)


# 6) Выбор направления отверстия
def get_hole_direction():
    if INVERT_HOLE_DIRECTION:
        return POSITIVE_EXTENT_DIRECTION

    return NEGATIVE_EXTENT_DIRECTION


# 7) Создание коллекции объектов Inventor
def create_object_collection(inv, objects):
    collection = inv.TransientObjects.CreateObjectCollection()

    for obj in objects:
        collection.Add(obj)

    return collection


# 8) Поиск центра выбранной грани в координатах эскиза
def get_face_center_in_sketch(sketch, face, transient_geometry):
    sketch_points = []

    for vertex in face.Vertices:
        point_3d = vertex.Point
        point_2d = sketch.ModelToSketchSpace(point_3d)
        sketch_points.append(point_2d)

    if len(sketch_points) == 0:
        raise RuntimeError("Не удалось найти вершины выбранной грани.")

    center_x = sum(point.X for point in sketch_points) / len(sketch_points)
    center_y = sum(point.Y for point in sketch_points) / len(sketch_points)

    return transient_geometry.CreatePoint2d(center_x, center_y)


# 9) Основная логика: создание эскиза, точки и отверстия
def create_hole_on_selected_face(inv, doc):
    comp_def = doc.ComponentDefinition
    face = get_selected_face(doc)

    # 9.1) Создаем эскиз на выбранной грани
    sketch = comp_def.Sketches.Add(face)
    sketch.Name = "Учебный эскиз отверстия"

    # 9.2) Находим центр выбранной грани
    center_2d = get_face_center_in_sketch(sketch, face, inv.TransientGeometry)

    # 9.3) Создаем точку эскиза
    sketch_point = sketch.SketchPoints.Add(center_2d, False)

    # 9.4) Делаем точку центром отверстия
    sketch_point.HoleCenter = True

    # 9.5) Создаем описание размещения отверстия
    hole_centers = create_object_collection(inv, [sketch_point])
    hole_features = comp_def.Features.HoleFeatures
    placement = hole_features.CreateSketchPlacementDefinition(hole_centers)

    # 9.6) Создаем отверстие заданного диаметра и глубины
    hole = hole_features.AddDrilledByDistanceExtent(
        placement,
        HOLE_DIAMETER,
        HOLE_DEPTH,
        get_hole_direction(),
        True,
    )
    hole.Name = "Учебное отверстие"

    # 9.7) Обновляем документ
    doc.Update()

    return hole


# 10) Точка входа в программу
def main():
    inv = get_inventor()
    doc = get_active_document(inv)

    print("Inventor:", inv.Caption)
    print("Документ:", doc.DisplayName)

    create_hole_on_selected_face(inv, doc)

    print("Готово: отверстие создано на выбранной грани.")


# 11) Запуск скрипта только при прямом запуске файла
if __name__ == "__main__":
    main()
