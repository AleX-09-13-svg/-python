# Основной алгоритм присадки стяжки по парам выбранных граней.
from common.constants import DRILLING_SKETCH_PREFIX
import common.create_sketches as create_sketches
from common.selected_workflow import selected_inventor_context
from stiajka.parameter_dialog import choose_frame_edge_offset_parameter, unique_names
from stiajka.offset_sketch import create_offset_drilling_sketch
import stiajka.stiajka as stiajka_module


def main():
    # 1. Получить выбранные грани.
    print("05: Подключение к Inventor", flush=True)
    inventor, faces = selected_inventor_context("Stiajka 2pcs")
    if not faces:
        return
    # 2. Выбрать отступ и проверить необходимые параметры.
    print("05: Выбор параметра отступа", flush=True)
    frame_edge_offset_param = choose_frame_edge_offset_parameter(inventor)
    if not frame_edge_offset_param:
        return
    stiajka_offset_param = stiajka_module.stiajka_parameter("offset", "Стяжка_отступ")
    required_parameters = (
        frame_edge_offset_param,
        stiajka_offset_param,
        *stiajka_module.stiajka_required_parameter_names(),
    )
    required_parameters = unique_names(required_parameters)
    if not create_sketches.ensure_parameters(inventor, required_parameters):
        return
    inventor.ensure_keep_parameter("Keep_Excel_Params", required_parameters)
    # 3. Сформировать пары: меньшая и большая грани.
    face_pairs = selected_face_pairs(inventor, faces)
    if not face_pairs:
        return
    # Общие значения прочитать один раз для всех вторых граней.
    offset_value = inventor.parameter_value(
        stiajka_offset_param, stiajka_module.stiajka_setting("side_offset", default=3.4)
    )
    edge_offset_value = inventor.parameter_value(frame_edge_offset_param, 10)
    cup_settings = stiajka_module.stiajka_hole("Chashka stiajki")
    hole_settings = dict(
        diameter=stiajka_module.stiajka_parameter("diameter", "Стяжка_D"),
        depth=stiajka_module.stiajka_parameter("depth", "Стяжка_h"),
        direction=stiajka_module.stiajka_direction(cup_settings),
        name=cup_settings.get("feature_name", "Stiajka cup"),
    )
    first_faces = [pair[0] for pair in face_pairs]
    # 4. Создать новые первые эскизы: оси, пять точек и размеры.
    print("05: Построение первых эскизов", flush=True)
    first_sketches = create_sketches.create_sketches_for_faces(
        inventor,
        None,
        first_faces,
        DRILLING_SKETCH_PREFIX,
        frame_edge_offset_param,
        "Drilling",
        "Selected first face drilling",
        reuse_existing=False,
    )
    # 5. Создать отверстия стяжки и шкантов на первых гранях.
    print("05: Создание отверстий на первых гранях", flush=True)
    created = stiajka_module.create_stiajka_features(
        inventor,
        sketches=first_sketches,
        colored_faces=first_faces,
        update_document=False,
    )
    if created:
        for sketch in first_sketches:
            inventor.set_sketch_visible(sketch, False)
    # 6. Построить второй эскиз каждой пары и создать отверстия по крайним точкам.
    for index, (first_face, second_face) in enumerate(face_pairs, start=2):
        print("05: Построение второго эскиза", flush=True)
        second_result = create_offset_drilling_sketch(
            inventor,
            second_face,
            first_face,
            index,
            stiajka_offset_param,
            frame_edge_offset_param,
            offset_value,
            edge_offset_value,
        )
        if second_result is None:
            continue
        second_sketch, second_outer_points = second_result
        print("05: Создание отверстий на второй грани", flush=True)
        current_second_created = stiajka_module.create_second_face_stiajka_holes(
            inventor, second_outer_points, hole_settings
        )
        if current_second_created:
            inventor.set_sketch_visible(second_sketch, False)
    # 7. Обновить модель.
    print("05: Обновление документа", flush=True)
    inventor.update()
    print("05: Готово", flush=True)


def selected_face_pairs(inventor, faces):
    if len(faces) == 2:
        return [faces_by_area(inventor, faces)]
    groups = {}
    for face in faces:
        groups.setdefault(face_body_key(face), []).append(face)
    pairs = []
    for group in groups.values():
        if len(group) != 2:
            return None
        pairs.append(faces_by_area(inventor, group))
    if not pairs:
        return None
    return pairs


def faces_by_area(inventor, faces):
    return sorted(faces, key=lambda face: inventor.face_area(face) or 0)


def face_body_key(face):
    body = getattr(face, "Parent", None)
    if body is None:
        return ("face", id(face))
    name = getattr(body, "Name", None)
    try:
        box = body.RangeBox
        bounds = (
            round(box.MinPoint.X, 6),
            round(box.MinPoint.Y, 6),
            round(box.MinPoint.Z, 6),
            round(box.MaxPoint.X, 6),
            round(box.MaxPoint.Y, 6),
            round(box.MaxPoint.Z, 6),
        )
    except Exception:
        bounds = (id(body),)
    return (name, bounds)


if __name__ == "__main__":
    main()
