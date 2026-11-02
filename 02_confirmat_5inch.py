# Основной алгоритм присадки конфирматов по выбранным граням.
from common.constants import DRILLING_SKETCH_PREFIX
import common.create_sketches as create_sketches
from common.selected_workflow import selected_inventor_context
from common.drilling_runtime import DrillingNames
from confirmat.runtime import ConfirmatRuntime
from time import perf_counter
from functools import partial
from confirmat.parameter_dialog import choose_workflow_parameters
from confirmat.parameters import (
    use_material_thickness,
    confirmat_parameter_names,
)
import confirmat.confirmat as confirmat_module
from confirmat.pair_geometry import create_pair_points


def main():
    # 1. Получить выбранные грани.
    print("02: Подключение к Inventor", flush=True)
    inventor, faces = selected_inventor_context("Confirmat 5pcs (2 pairs, 96 mm + center)")
    if not faces:
        return
    inventor = ConfirmatRuntime(inventor)

    # 2. Выбрать пользовательские параметры толщины и отступа.
    thickness_param, edge_offset_param = choose_workflow_parameters(inventor, inventor.parameter_session)
    if not thickness_param or not edge_offset_param:
        return
    use_material_thickness(thickness_param)
    print("Material thickness parameter:", thickness_param)
    print("Pair edge offset parameter:", edge_offset_param)
    required_parameters = tuple(dict.fromkeys((thickness_param, edge_offset_param, *confirmat_parameter_names())))
    if not create_sketches.ensure_parameters(inventor, required_parameters):
        return
    inventor.ensure_keep_parameter(create_sketches.KEEP_EXCEL_PARAMS_NAME, required_parameters)
    edge_offset_value = inventor.parameter_value(edge_offset_param)  # Сантиметры.
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
            edge_offset_param,
            "Drilling",
            "Selected drilling",
            use_offset_plane=True,
            offset_param=thickness_param,
            reuse_existing=False,
            point_jobs=point_jobs,
            compact_points=False,
            point_builder=partial(create_pair_points, edge_offset_param=edge_offset_param),
            edge_offset_value=edge_offset_value,
            runtime_names=names,
            direct_projection=True,
            use_cached_operations=True,
        )
        if len(point_jobs) != len(faces):
            raise RuntimeError("Не на всех выбранных гранях построены точки присадки.")
        started = log_elapsed("Sketches", started)

        # 7. Создать две пары и одно центральное отверстие на каждой грани.
        print("02: Создание отверстий конфирмата", flush=True)
        created = confirmat_module.create_confirmat_pair_features(
            inventor,
            sketches=sketches,
            faces=faces,
            face_label="selected",
            direction="positive",
            point_jobs=point_jobs,
            update_document=False,
        )

        # 8. Скрыть использованные эскизы, если созданы операции отверстий.
        if created:
            for sketch in sketches:
                inventor.set_sketch_visible(sketch, False)
        else:
            print(
                "Confirmat 5pcs sketches left visible because "
                "no hole features were created"
            )
        print("Confirmat 5pcs hole features created:", created)
        started = log_elapsed("Holes", started)
        inventor.update()
        log_elapsed("Document update", started)
    log_elapsed("Total build", total)


def log_elapsed(label, started):
    print(f"02: {label}: {perf_counter() - started:.2f}s", flush=True)
    return perf_counter()


if __name__ == "__main__":
    main()
