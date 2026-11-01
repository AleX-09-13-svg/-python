"""Привязка монтажных отверстий боковины к центрам чашек фасада."""
from common.cached_sketch import CachedSketchService
from common.reference_edge import snapshot_lines
from petli.layout import rectangle_frame, side_hole_rows
from stiajka.offset_sketch import plane_intersection_model_line


def build_side_sketch(inventor, facade, side, cup_points, diameter, names):
    edges = inventor.face_edges(side)
    if len(edges) != 4 or any(edge.GeometryType not in (5122, 5123) for edge in edges):
        raise ValueError("Для присадки петель выберите прямоугольную пласть боковины без вырезов.")
    origin, direction = plane_intersection_model_line(inventor, side, facade)
    if origin is None:
        raise ValueError("Фасад и боковина не должны быть параллельны.")
    sketch = inventor.add_sketch(side)
    sketch.Name = names.sketch("Petli_Side")
    inventor = CachedSketchService(inventor, sketch)
    with inventor.deferred_sketch_updates(sketch):
        # Проекции фактических рёбер боковины задают базу отступов, включая зазор до фасада.
        contour = [inventor.project_entity_to_sketch(sketch, edge, construction=True) for edge in edges]
        geometries = snapshot_lines(contour)
        segments = [(geometries[id(line)].start, geometries[id(line)].end) for line in contour]
        p = inventor.model_to_sketch_point(sketch, inventor.create_point3d(*origin))
        q = inventor.model_to_sketch_point(sketch, inventor.create_point3d(
            *(origin[i] + direction[i] for i in range(3))))
        frame = rectangle_frame(segments, (p.X, p.Y), (q.X - p.X, q.Y - p.Y))
        reference = contour[frame.edge_index]
        # Ассоциативная проекция точек первого эскиза сохраняет высоту каждой петли.
        projections = [inventor.project_entity_to_sketch(sketch, center) for center in cup_points]
        coordinates = [p.Geometry for p in projections]
        rows = side_hole_rows(frame, [(p.X, p.Y) for p in coordinates], diameter)
        points = []
        for projection, (front_xy, first_xy, second_xy) in zip(projections, rows, strict=True):
            row = inventor.add_sketch_line(sketch, projection, inventor.create_point2d(*second_xy), construction=True)
            inventor.add_perpendicular_constraint(sketch, row, reference, ignore_errors=False)
            front = inventor.add_sketch_point(sketch, inventor.create_point2d(*front_xy))
            inventor.add_coincident_constraint(sketch, front, row, ignore_errors=False)
            inventor.add_coincident_constraint(sketch, front, reference, ignore_errors=False)
            first = inventor.add_sketch_point(sketch, inventor.create_point2d(*first_xy), hole_center=True)
            inventor.add_coincident_constraint(sketch, first, row, ignore_errors=False)
            second = row.EndSketchPoint
            second.HoleCenter = True
            for a, b, xy_a, xy_b, expression in ((front, first, front_xy, first_xy, "20 mm"),
                                                (first, second, first_xy, second_xy, "32 mm")):
                mid = ((xy_a[0] + xy_b[0]) / 2, (xy_a[1] + xy_b[1]) / 2)
                text = inventor.create_point2d(mid[0] + frame.along[0], mid[1] + frame.along[1])
                dimension = inventor.add_aligned_dimension(sketch, a, b, text)
                dimension.Parameter.Expression = expression
            points.extend((first, second))
    sketch.Solve()
    return sketch, points
