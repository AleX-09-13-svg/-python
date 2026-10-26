# Основной алгоритм присадки конфирматов по выбранным граням.
from common.constants import DRILLING_SKETCH_PREFIX
import common.create_sketches as create_sketches
from common.selected_workflow import selected_inventor_context
from confirmat.parameter_dialog import choose_workflow_parameters
from confirmat.parameters import (
    KEEP_EXCEL_UNITLESS_PARAMS_NAME,
    use_material_thickness,
    confirmat_parameter_names,
    resolve_confirmat_count,
    ensure_unitless_keep_parameter,
)
import confirmat.confirmat as confirmat_module


def main():
    # 1. Получить выбранные грани.
    print("02: Подключение к Inventor", flush=True)
    inventor, faces = selected_inventor_context("Confirmat 2pcs")
    if not faces:
        return

    # 2. Выбрать толщину, отступ и параметр количества.
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

    if not confirmat_count_param:
        print("Confirmat count parameter was not selected")
        return

    print("Confirmat count parameter:", confirmat_count_param)

    # 3. Проверить выбранные параметры и определить количество: 2 или 3.
    base_required_parameters = (
        frame_edge_offset_param,
        thickness_param,
        confirmat_count_param,
    )
    if not create_sketches.ensure_parameters(inventor, base_required_parameters):
        return

    confirmat_count = resolve_confirmat_count(inventor, confirmat_count_param)
    if confirmat_count not in ("2", "3"):
        return

    print("Confirmat count:", confirmat_count)

    # 4. Проверить параметры отверстий из настроек библиотеки.
    required_parameters = (
        *base_required_parameters,
        *confirmat_parameter_names(),
    )
    if not create_sketches.ensure_parameters(inventor, required_parameters):
        return

    # 5. Сохранить ссылки на размерные и безразмерные параметры детали.
    keep_parameters = tuple(
        parameter for parameter in required_parameters if parameter != confirmat_count_param
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

    # 6. Создать новые эскизы на плоскостях, смещённых на выбранную толщину.
    print("02: Построение новых эскизов", flush=True)
    sketches = create_sketches.create_sketches_for_faces(
        inventor,
        None,
        faces,
        DRILLING_SKETCH_PREFIX,
        frame_edge_offset_param,
        "Drilling",
        "Selected drilling",
        use_offset_plane=True,
        offset_param=thickness_param,
        reuse_existing=False,
    )
    if create_sketches.should_update_document():
        inventor.update()

    # 7. Создать крайние и центральные отверстия; задать условие подавления центра.
    print("02: Создание отверстий конфирмата", flush=True)
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

    # 8. Скрыть использованные эскизы, если созданы операции отверстий.
    if created:
        for sketch in sketches:
            inventor.set_sketch_visible(sketch, False)
    else:
        print(
            f"Confirmat {confirmat_count}pcs sketches left visible because "
            "no hole features were created"
        )
    print(f"Confirmat {confirmat_count}pcs hole features created:", created)


if __name__ == "__main__":
    main()
