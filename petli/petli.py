"""Эскиз и отверстия петель в активной многотельной .ipt-детали."""
import math
from time import perf_counter

from common.cached_sketch import CachedSketchService
from common.drilling_runtime import DrillingNames
from common.reference_edge import snapshot_lines
from common.runtime_service import RuntimeService
from common.selected_workflow import selected_inventor_context
from petli.layout import PILOT_INSET, PILOT_SPACING, calculate_layout, pilot_positions
from petli.side_sketch import build_side_sketch
from petli.runtime import prepare_centers
from stiajka.hole_builder import TimedHoleBuilder, timed_stage
from stiajka.offset_sketch import plane_intersection_model_line
from stiajka.parameters import ParameterSession


DIAMETER = "Петля_D_присадки"
DEPTH = "Стяжкаh_резьбаШтока_Петля"
PILOT_DIAMETER = "Наколка_D"
PILOT_DEPTH = "Наколка_Глубина"
REQUIRED_PARAMETERS = (DIAMETER, DEPTH, PILOT_DIAMETER, PILOT_DEPTH)


def inward_direction(inventor, sketch, face):
    # Положительное направление HoleFeatures совпадает с нормалью эскиза.
    origin, x, y = (sketch.SketchToModelSpace(inventor.create_point2d(*p))
                    for p in ((0, 0), (1, 0), (0, 1)))
    u = (x.X - origin.X, x.Y - origin.Y, x.Z - origin.Z)
    v = (y.X - origin.X, y.Y - origin.Y, y.Z - origin.Z)
    normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    outward = inventor.plane_geometry(face).Normal
    sign = -1 if face.IsParamReversed else 1
    dot = sign * (normal[0] * outward.X + normal[1] * outward.Y + normal[2] * outward.Z)
    return "negative" if dot > 0 else "positive"


def build_sketch(inventor, facade, side, diameter, names, pilot_diameter):
    edges = inventor.face_edges(facade)
    if len(edges) != 4 or any(edge.GeometryType not in (5122, 5123) for edge in edges):
        raise ValueError("Выберите плоскую прямоугольную грань фасада без вырезов.")
    point, direction = plane_intersection_model_line(inventor, facade, side)
    if point is None:
        raise ValueError("Фасад и боковина не должны быть параллельны.")
    n1, n2 = inventor.plane_geometry(facade).Normal, inventor.plane_geometry(side).Normal
    if abs(n1.X * n2.X + n1.Y * n2.Y + n1.Z * n2.Z) > 1e-5:
        raise ValueError("Плоскости фасада и боковины должны быть перпендикулярны.")
    sketch = inventor.add_sketch(facade)
    sketch.Name = names.sketch("Petli")
    inventor = CachedSketchService(inventor, sketch)
    with inventor.deferred_sketch_updates(sketch):
        contour = [inventor.project_entity_to_sketch(sketch, edge, construction=True) for edge in edges]
        geometries = snapshot_lines(contour)
        segments = [(geometries[id(line)].start, geometries[id(line)].end) for line in contour]
        p = inventor.model_to_sketch_point(sketch, inventor.create_point3d(*point))
        q = inventor.model_to_sketch_point(sketch, inventor.create_point3d(
            *(point[i] + direction[i] for i in range(3))))
        layout = calculate_layout(segments, (p.X, p.Y), (q.X - p.X, q.Y - p.Y), diameter)
        pilot_positions(layout, diameter, pilot_diameter)
        # Рёбра, перпендикулярные эскизу, вырождаются в точки и могут не проецироваться.
        if not inventor.project_face_edges(sketch, side, ignore_errors=True):
            raise ValueError("Не удалось спроецировать боковину на фасад.")
        reference = contour[layout.edge_index]
        reference_start = geometries[id(reference)].start_point
        reference_end = geometries[id(reference)].end_point
        a, u, n = layout.start, layout.along, layout.inward

        def at(t, offset=2.2):
            return inventor.create_point2d(a[0] + t * u[0] + offset * n[0],
                                          a[1] + t * u[1] + offset * n[1])

        def dimension(first, second, text, expression=None, driven=False):
            result = inventor.add_aligned_dimension(sketch, first, second, text, driven)
            if expression is not None:
                result.Parameter.Expression = expression
            return result

        control = dimension(reference_start, reference_end, at(layout.length / 2, -3), driven=True)
        length_name = names.parameter("Petli_Length")
        control.Parameter.Name = length_name
        offset = inventor.add_sketch_line(sketch, reference_start, at(0), construction=True)
        inventor.add_perpendicular_constraint(sketch, offset, reference, ignore_errors=False)
        offset_start, offset_end = offset.StartSketchPoint, offset.EndSketchPoint
        dimension(offset_start, offset_end, at(-2, 1.1), "22 mm")
        axis = inventor.add_sketch_line(sketch, offset_end, at(layout.length), construction=True)
        inventor.add_parallel_constraint(sketch, axis, reference, ignore_errors=False)
        axis_start, axis_end = axis.StartSketchPoint, axis.EndSketchPoint
        dimension(axis_start, axis_end, at(layout.length / 2, 4), length_name)
        points = []
        pilot_points = []
        for i, distance in enumerate(layout.distances):
            center = inventor.add_sketch_point(sketch, at(distance), hole_center=True)
            inventor.add_coincident_constraint(sketch, center, axis, ignore_errors=False)
            expression = f"100 mm + ({length_name} - 200 mm) * {i} / {len(layout.distances) - 1}"
            dimension(axis_start, center, at(distance / 2, 5 + i), expression)
            points.append(center)
            # Наколки симметричны чашке вдоль кромки, а их ряд смещён внутрь фасада.
            pilot_offset = 2.2 + PILOT_INSET
            anchor = inventor.add_sketch_line(sketch, center, at(distance, pilot_offset), construction=True)
            inventor.add_perpendicular_constraint(sketch, anchor, axis, ignore_errors=False)
            anchor_start, anchor_end = anchor.StartSketchPoint, anchor.EndSketchPoint
            dimension(anchor_start, anchor_end,
                      at(distance + 1, pilot_offset / 2 + 1.1), "9.5 mm")
            row = inventor.add_sketch_line(
                sketch, at(distance - PILOT_SPACING / 2, pilot_offset),
                at(distance + PILOT_SPACING / 2, pilot_offset), construction=True)
            inventor.add_parallel_constraint(sketch, row, axis, ignore_errors=False)
            inventor.add_midpoint_constraint(sketch, anchor_end, row, ignore_errors=False)
            row_start, row_end = row.StartSketchPoint, row.EndSketchPoint
            dimension(row_start, row_end, at(distance, pilot_offset + 1), "45 mm")
            row_start.HoleCenter = row_end.HoleCenter = True
            pilot_points.extend((row_start, row_end))
    sketch.Solve()
    return sketch, points, pilot_points, layout


def main():
    started = perf_counter()
    inventor, faces = selected_inventor_context("07 Petli: фасад, затем боковина")
    if len(faces) != 2:
        raise ValueError("Выберите ровно две плоские грани: сначала фасад, затем боковину (Ctrl).")
    inventor = RuntimeService(inventor)
    document = inventor.active_document
    if int(document.DocumentType) != 12290:
        raise ValueError("Откройте .ipt-деталь с телами фасада и боковины.")
    if not all(inventor.is_planar_face(face) for face in faces):
        raise ValueError("Обе выбранные грани должны быть плоскими.")
    parameters = ParameterSession(inventor)
    missing = parameters.missing_parameters(REQUIRED_PARAMETERS)
    if missing:
        raise ValueError("В детали отсутствуют параметры: " + ", ".join(missing))
    units_of_measure = document.UnitsOfMeasure
    checked_units = set()
    for name in REQUIRED_PARAMETERS:
        try:
            units = parameters.parameter(name).Units
            if units not in checked_units:
                units_of_measure.ConvertUnits(1, units, "cm")
                checked_units.add(units)
        except Exception as exc:
            raise ValueError(f"Параметр {name} должен иметь единицы длины.") from exc
    diameter, depth, pilot_diameter, pilot_depth = (parameters.parameter_value(name) for name in REQUIRED_PARAMETERS)
    if not all(isinstance(value, (float, int)) and math.isfinite(value) and value > 0
               for value in (diameter, depth, pilot_diameter, pilot_depth)):
        raise ValueError("Диаметр и глубина отверстия должны быть положительными длинами.")
    facade, side = faces
    body = facade.Parent
    if not body.IsSolid:
        raise ValueError("Фасад должен принадлежать твёрдому телу.")
    body_name = body.Name
    side_body = side.Parent
    if not side_body.IsSolid:
        raise ValueError("Боковина должна принадлежать твёрдому телу.")
    side_body_name = side_body.Name
    names = DrillingNames(inventor)
    transaction = inventor.app.TransactionManager.StartTransaction(document, "07 Петли")
    try:
        with inventor.screen_updates_suspended():
            with timed_stage("07", "эскиз фасада"):
                sketch, points, pilot_points, layout = build_sketch(inventor, facade, side, diameter, names, pilot_diameter)
            direction = inward_direction(inventor, sketch, facade)
            direction = "positive" if direction == "negative" else "negative"
            # Оба эскиза и направления подготовить до сверления: ссылки граней могут измениться.
            with timed_stage("07", "эскиз боковины"):
                side_sketch, side_points = build_side_sketch(inventor, facade, side, points, pilot_diameter, names)
            side_direction = inward_direction(inventor, side_sketch, side)
            side_direction = "positive" if side_direction == "negative" else "negative"
            creator = TimedHoleBuilder(inventor, known_bodies={body_name: body, side_body_name: side_body})
            # Все три коллекции собрать до первого изменения топологии отверстиями.
            cup_centers = prepare_centers(creator, points, "Petli_Holes")
            pilot_centers = prepare_centers(creator, pilot_points, "Petli_Nakolki")
            side_centers = prepare_centers(creator, side_points, "Petli_Side_Nakolki")
            creator(cup_centers, DIAMETER, DEPTH, direction, name="Petli_Holes",
                    flat_bottom=True, affect_all_bodies=False, affected_body=body_name)
            creator(pilot_centers, PILOT_DIAMETER, PILOT_DEPTH, direction, name="Petli_Nakolki",
                    flat_bottom=True, affect_all_bodies=False, affected_body=body_name)
            creator(side_centers, PILOT_DIAMETER, PILOT_DEPTH, side_direction, name="Petli_Side_Nakolki",
                    flat_bottom=True, affect_all_bodies=False, affected_body=side_body_name)
            inventor.set_sketch_visible(sketch, False)
            inventor.set_sketch_visible(side_sketch, False)
            with timed_stage("07", "обновление документа"):
                inventor.update()
        transaction.End()
    except Exception:
        transaction.Abort()
        raise
    print(f"07: Готово. Размер фасада вдоль боковины: {layout.length * 10:g} мм; "
          f"петель: {len(points)}; наколок фасада: {len(pilot_points)}; "
          f"наколок боковины: {len(side_points)}.", flush=True)
    print(f"07: Общее время: {perf_counter() - started:.2f}s", flush=True)
