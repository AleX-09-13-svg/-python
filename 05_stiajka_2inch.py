# Основной алгоритм присадки стяжки по парам выбранных граней.
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from time import perf_counter

from common.constants import DRILLING_SKETCH_PREFIX
import common.create_sketches as create_sketches
from common.drilling_runtime import DrillingNames
from common.reference_edge import shared_intersection_edge, FaceEdgeCache
from common.runtime_service import RuntimeService
from common.selected_workflow import selected_inventor_context
from stiajka.parameter_dialog import choose_frame_edge_offset_parameter, unique_names
from stiajka.parameters import ParameterSession
from stiajka.offset_sketch import create_offset_drilling_sketch, plane_intersection_model_line
import stiajka.stiajka as stiajka_module
from stiajka.hole_builder import TimedHoleBuilder
from stiajka.body_targets import body_targets


def main():
    # 1. Получить выбранные грани.
    print("05: Подключение к Inventor", flush=True)
    inventor, faces = selected_inventor_context("Stiajka 2pcs")
    if not faces:
        raise ValueError("Выберите узкую грань и пласть для каждой стяжки.")
    inventor = RuntimeService(inventor)
    face_pairs = selected_face_pairs(inventor, faces)
    if not face_pairs:
        raise ValueError("Выберите по две грани каждого тела: узкую грань и пласть.")
    intersections = []
    shared_edges = []
    edge_cache = FaceEdgeCache(inventor)
    for first_face, second_face in face_pairs:
        intersection = plane_intersection_model_line(inventor, second_face, first_face)
        point, _ = intersection
        if point is None:
            raise ValueError("Грани пары параллельны. Выберите узкую грань и пласть.")
        intersections.append(intersection)
        shared_edges.append(shared_intersection_edge(
            inventor, first_face, second_face, intersection, edge_cache=edge_cache,
        ))
    # 2. Выбрать отступ и проверить необходимые параметры.
    print("05: Выбор параметра отступа", flush=True)
    started = perf_counter()
    parameter_cache = ParameterSession(inventor)
    stiajka_module.log_elapsed("Инициализация параметров", started)
    frame_edge_offset_param = choose_frame_edge_offset_parameter(inventor, parameter_cache)
    if not frame_edge_offset_param:
        return
    stiajka_offset_param = stiajka_module.stiajka_parameter("offset", "Стяжка_отступ")
    required_parameters = (
        frame_edge_offset_param,
        stiajka_offset_param,
        *stiajka_module.stiajka_required_parameter_names(),
    )
    required_parameters = unique_names(required_parameters)
    started = perf_counter()
    if not create_sketches.ensure_parameters(parameter_cache, required_parameters):
        raise ValueError("В детали отсутствуют необходимые параметры присадки.")
    started = stiajka_module.log_elapsed("Проверка необходимых параметров", started)
    changed = parameter_cache.ensure_keep_parameter("Keep_Excel_Params", required_parameters)
    started = stiajka_module.log_elapsed("Подготовка Keep_Excel_Params", started)
    print("05: Keep_Excel_Params: " + ("обновлён" if changed else "без изменений"), flush=True)
    # Общие значения прочитать один раз для всех эскизов.
    offset_value = parameter_cache.parameter_value(
        stiajka_offset_param, stiajka_module.stiajka_setting("side_offset", default=3.4)
    )
    edge_offset_value = parameter_cache.parameter_value(frame_edge_offset_param, 10)
    stiajka_module.log_elapsed("Чтение значений отступов", started)
    cup_settings = stiajka_module.stiajka_hole("Chashka stiajki")
    hole_settings = dict(
        diameter=stiajka_module.stiajka_parameter("diameter", "Стяжка_D"),
        depth=stiajka_module.stiajka_parameter("depth", "Стяжка_h"),
        direction=stiajka_module.stiajka_direction(cup_settings),
        name=cup_settings.get("feature_name", "Stiajka cup"),
    )
    started = perf_counter()
    names = DrillingNames(inventor)
    with inventor.screen_updates_suspended():
        create_drilling(
            inventor, face_pairs, frame_edge_offset_param, stiajka_offset_param,
            offset_value, edge_offset_value, hole_settings, intersections, names, shared_edges, edge_cache,
        )
    stiajka_module.log_elapsed("05: Общее время построения", started)
    print("05: Готово", flush=True)


def create_drilling(
    inventor, face_pairs, frame_edge_offset_param, stiajka_offset_param,
    offset_value, edge_offset_value, hole_settings, intersections, names, shared_edges,
    edge_cache=None,
):
    first_faces = [pair[0] for pair in face_pairs]
    # 4. Создать новые первые эскизы: оси, пять точек и размеры.
    print("05: Построение первых эскизов", flush=True)
    started = perf_counter()
    point_jobs = []
    first_sketches = create_sketches.create_sketches_for_faces(
        inventor,
        None,
        first_faces,
        DRILLING_SKETCH_PREFIX,
        frame_edge_offset_param,
        "Drilling",
        "Selected first face drilling",
        reuse_existing=False,
        point_jobs=point_jobs,
        edge_offset_value=edge_offset_value,
        runtime_names=names,
        direct_projection=True,
        use_cached_operations=True,
        edge_cache=edge_cache,
        reference_edges={id(pair[0]): edge for pair, edge in zip(face_pairs, shared_edges, strict=True)},
    )
    if len(point_jobs) != len(first_faces):
        raise RuntimeError("Не удалось построить точки присадки на всех выбранных узких гранях.")
    started = stiajka_module.log_elapsed("Первые эскизы", started)
    # 5. Подготовить ВСЕ вторые эскизы до изменения топологии отверстиями.
    # После add_holes исходные COM-ссылки на выбранные грани могут стать недействительными.
    second_results = []
    for index, ((first_face, second_face), intersection, shared_edge) in enumerate(
        zip(face_pairs, intersections, shared_edges, strict=True), start=2,
    ):
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
            intersection_line=intersection,
            runtime_names=names,
            control_edge=shared_edge,
            use_cached_operations=True,
            edge_cache=edge_cache,
        )
        if second_result is None:
            raise RuntimeError(f"Не удалось построить эскиз на второй грани пары {index - 1}.")
        second_results.append(second_result)
    started = stiajka_module.log_elapsed("Вторые эскизы", started)
    known_bodies = {}
    targets = body_targets(inventor, face_pairs, point_jobs, body_cache=known_bodies)
    for job in point_jobs:
        job.update(targets[id(job["colored_face"])])
    started = stiajka_module.log_elapsed("Поиск соседних тел", started)
    # 6. Все обращения к выбранным граням завершены; создавать отверстия по точкам эскизов.
    print("05: Создание отверстий на первых гранях", flush=True)
    hole_creator = TimedHoleBuilder(inventor, known_bodies=known_bodies)
    created = stiajka_module.create_stiajka_features(
        inventor,
        sketches=first_sketches,
        colored_faces=first_faces,
        update_document=False,
        point_jobs=point_jobs,
        strict=True,
        hole_creator=hole_creator,
    )
    if created:
        for sketch in first_sketches:
            inventor.set_sketch_visible(sketch, False)
    for (first_face, _), second_result in zip(face_pairs, second_results, strict=True):
        second_sketch, second_outer_points = second_result
        print("05: Создание отверстий на второй грани", flush=True)
        current_second_created = stiajka_module.create_second_face_stiajka_holes(
            inventor, second_outer_points,
            {**hole_settings, "affected_body": targets[id(first_face)]["owner_body"]},
            hole_creator=hole_creator,
        )
        if current_second_created:
            inventor.set_sketch_visible(second_sketch, False)
    started = stiajka_module.log_elapsed("Все отверстия", started)
    # 7. Обновить модель.
    print("05: Обновление документа", flush=True)
    inventor.update()
    stiajka_module.log_elapsed("Обновление документа", started)


def selected_face_pairs(inventor, faces):
    if len(faces) == 2:
        if face_body_key(faces[0]) != face_body_key(faces[1]):
            return None
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
        minimum = box.MinPoint
        maximum = box.MaxPoint
        bounds = (
            round(minimum.X, 6),
            round(minimum.Y, 6),
            round(minimum.Z, 6),
            round(maximum.X, 6),
            round(maximum.Y, 6),
            round(maximum.Z, 6),
        )
    except Exception:
        bounds = (id(body),)
    return (name, bounds)


class Output:
    def __init__(self, stream, log):
        self.stream = stream
        self.log = log

    def write(self, text):
        self.log.write(text)
        self.log.flush()
        if self.stream is not None:
            try:
                self.stream.write(text)
                self.stream.flush()
            except (OSError, UnicodeError):
                pass
        return len(text)

    def flush(self):
        self.log.flush()


def run():
    path = Path(__file__).resolve().with_suffix(".log")
    with path.open("w", encoding="utf-8") as log:
        with redirect_stdout(Output(sys.stdout, log)), redirect_stderr(Output(sys.stderr, log)):
            print(f"Запуск 05. Журнал: {path}", flush=True)
            try:
                main()
            except Exception:
                traceback.print_exc()
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
