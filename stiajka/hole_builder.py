"""Создание отверстий 05 с быстрым подбором имён и замерами COM-этапов."""
from contextlib import contextmanager
from time import perf_counter
from dataclasses import dataclass

from common.drilling_runtime import NameAllocator
from common.inventor_service_path import ensure_inventor_service_path

ensure_inventor_service_path()
from inventor_service.config import resolve_parameter_expression


@contextmanager
def timed_stage(operation, stage):
    started = perf_counter()
    try:
        yield
    finally:
        print(f"    {operation} — {stage}: {perf_counter() - started:.2f}s", flush=True)


@dataclass(frozen=True)
class PreparedHolePoints:
    owner: object
    points: tuple
    collection: object

    def __len__(self):
        return len(self.points)


class TimedHoleBuilder:
    def __init__(self, inventor, known_bodies=None):
        self.inventor = inventor
        self.component = inventor.comp
        self.features = self.component.Features.HoleFeatures
        self.allocate_name = NameAllocator(self.features).take
        self.body_indices = {}
        self.body_refs = dict(known_bodies or {})
        self.prepared_points = {}
        self.body_collections = {}

    def prepare_points(self, points):
        if isinstance(points, PreparedHolePoints):
            if points.owner is not self:
                raise ValueError("Центры отверстий подготовлены другим построителем.")
            return points
        raw = tuple(points)
        key = tuple(id(point) for point in raw)
        if key not in self.prepared_points:
            unique = self.inventor.unique_points(raw)
            self.inventor.mark_as_hole_centers(unique)
            prepared = PreparedHolePoints(self, tuple(unique), self.inventor.object_collection(unique))
            # Удерживать исходные объекты, чтобы их id не переиспользовались.
            self.prepared_points[key] = (raw, prepared)
        return self.prepared_points[key][1]

    def body_for_name(self, name):
        body = self.body_refs.get(name)
        if body is not None:
            try:
                if body.Name == name:
                    return body
            except Exception:
                pass
            self.body_refs.pop(name, None)
        # SurfaceBodies.Item принимает только числовой индекс.
        # Проверять имя после перестроения, чтобы не использовать устаревший индекс.
        bodies = self.component.SurfaceBodies
        index = self.body_indices.get(name)
        if index is not None:
            try:
                body = bodies.Item(index)
                if body.Name == name:
                    self.body_refs[name] = body
                    return body
            except Exception:
                pass
        for index in range(1, bodies.Count + 1):
            body = bodies.Item(index)
            body_name = body.Name
            self.body_indices[body_name] = index
            if body_name == name:
                self.body_refs[name] = body
                return body
        raise AffectedBodyError(f"Целевое тело '{name}' больше не найдено в детали.")

    def __call__(self, points, diameter, depth, direction, name=None,
                 flat_bottom=True, affect_all_bodies=True, affected_body=None):
        operation = name or "Отверстия"
        with timed_stage(operation, "подготовка точек и размещения"):
            selected_bodies = None
            if affected_body is not None:
                # Получать актуальную ссылку после предыдущих перестроений модели.
                body = self.body_for_name(affected_body)
                key = id(body)
                if key not in self.body_collections:
                    self.body_collections[key] = (body, self.inventor.object_collection([body]))
                selected_bodies = self.body_collections[key][1]
            prepared = self.prepare_points(points)
            # Определение размещения создаётся заново для каждой операции.
            placement = self.features.CreateSketchPlacementDefinition(
                prepared.collection
            )
            diameter_expression = resolve_parameter_expression(diameter)
            depth_expression = resolve_parameter_expression(depth)
            extent_direction = self.inventor.hole_direction(direction)
        with timed_stage(operation, "создание операции Inventor"):
            feature = self.features.AddDrilledByDistanceExtent(
                placement, diameter_expression, depth_expression, extent_direction, flat_bottom,
            )
        # После создания нельзя запускать повторное сверление из-за ошибки имени
        # или назначения тел: это дублировало бы уже созданную операцию.
        if name:
            with timed_stage(operation, "подбор и назначение имени"):
                try:
                    feature.Name = self.allocate_name(name)
                except Exception as exc:
                    print(f"    Не удалось назначить имя {name}: {exc}", flush=True)
        if selected_bodies is not None:
            with timed_stage(operation, f"назначение одного тела '{affected_body}'"):
                try:
                    feature.SetAffectedBodies(selected_bodies)
                except Exception as exc:
                    try:
                        feature.Delete()
                    except Exception as delete_error:
                        raise AffectedBodyError(
                            f"Не удалось ограничить '{operation}' телом '{affected_body}' "
                            f"и удалить неограниченную операцию: {delete_error}"
                        ) from exc
                    raise AffectedBodyError(
                        f"Не удалось ограничить '{operation}' телом '{affected_body}'. "
                        "Созданная операция удалена."
                    ) from exc
        elif affect_all_bodies:
            with timed_stage(operation, "назначение затрагиваемых тел"):
                try:
                    self.inventor.set_all_bodies_affected(feature, self.component)
                except Exception as exc:
                    print(f"    Не удалось назначить затрагиваемые тела {operation}: {exc}", flush=True)
        return feature


class AffectedBodyError(RuntimeError):
    """Остановить присадку без пакетного повторения неограниченных операций."""
