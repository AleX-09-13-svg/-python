# Основной алгоритм присадки конфирматов по выбранным граням.
from common.constants import DRILLING_SKETCH_PREFIX
import common.create_sketches as create_sketches
from common.selected_workflow import selected_inventor_context
from common.drilling_runtime import DrillingNames
from confirmat.runtime import ConfirmatRuntime
from time import perf_counter
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
    inventor = ConfirmatRuntime(inventor)

    # 2. Выбрать толщину, отступ и параметр количества.
    (
        thickness_param,
        frame_edge_offset_param,
        confirmat_count_param,
    ) = choose_workflow_parameters(inventor, inventor.parameter_session)
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

    # 3. Проверить выбранные параметры и параметры отверстий один раз.
    base_required_parameters = (
        frame_edge_offset_param,
        thickness_param,
        confirmat_count_param,
    )
    required_parameters = tuple(dict.fromkeys((
        *base_required_parameters,
        *confirmat_parameter_names(),
    )))
    if not create_sketches.ensure_parameters(inventor, required_parameters):
        return

    confirmat_count = resolve_confirmat_count(inventor, confirmat_count_param)
    if confirmat_count not in ("2", "3"):
        return

    print("Confirmat count:", confirmat_count)

    # Сохранить ссылки на размерные и безразмерные параметры детали.
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

    edge_offset_value = inventor.parameter_value(frame_edge_offset_param, 10)
    names = DrillingNames(inventor)
    started = total = perf_counter()
    with inventor.screen_updates_suspended():
        # 6. Создать новые эскизы на плоскостях, смещённых на выбранную толщину.
        print("02: Построение новых эскизов", flush=True)
        point_jobs = []
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
            point_jobs=point_jobs,
            compact_points=False,
            edge_offset_value=edge_offset_value,
            runtime_names=names,
            direct_projection=True,
            use_cached_operations=True,
        )
        if len(point_jobs) != len(faces):
            raise RuntimeError("Не на всех выбранных гранях построены точки присадки.")
        started = log_elapsed("Sketches", started)

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
            point_jobs=point_jobs,
            update_document=False,
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
        started = log_elapsed("Holes", started)
        inventor.update()
        log_elapsed("Document update", started)
    log_elapsed("Total build", total)


def log_elapsed(label, started):
    print(f"02: {label}: {perf_counter() - started:.2f}s", flush=True)
    return perf_counter()


if __name__ == "__main__":
    main()
