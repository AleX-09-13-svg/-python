"""Операции одного эскиза с кэшем COM-коллекций на время построения."""
import math

from common.constants import ALIGNED_DIM, GRID_STEP_CM
from common.reference_edge import snapshot_lines


class CachedSketchService:
    def __init__(self, inventor, sketch):
        self.inventor = inventor
        self.sketch = sketch
        self.collections = {}
        self.geometries = {}

    def __getattr__(self, name):
        return getattr(self.inventor, name)

    def collection(self, sketch, name):
        if sketch is not self.sketch:
            raise ValueError("Кэш коллекций относится к другому эскизу.")
        if name not in self.collections:
            self.collections[name] = getattr(sketch, name)
        return self.collections[name]

    def add_sketch_point(self, sketch, point, hole_center=False):
        result = self.collection(sketch, "SketchPoints").Add(point, hole_center)
        if hole_center:
            try:
                result.HoleCenter = True
            except Exception:
                pass
        return result

    def add_sketch_line(self, sketch, start, end, construction=False):
        result = self.collection(sketch, "SketchLines").AddByTwoPoints(start, end)
        try:
            result.Construction = construction
        except Exception:
            pass
        return result

    def constraint(self, sketch, method, *args, ignore_errors=True):
        try:
            return getattr(self.collection(sketch, "GeometricConstraints"), method)(*args)
        except Exception:
            if not ignore_errors:
                raise
            return None

    def add_midpoint_constraint(self, sketch, point, line, ignore_errors=True):
        return self.constraint(sketch, "AddMidpoint", point, line, ignore_errors=ignore_errors)

    def add_coincident_constraint(self, sketch, first, second, ignore_errors=True):
        return self.constraint(sketch, "AddCoincident", first, second, ignore_errors=ignore_errors)

    def add_perpendicular_constraint(self, sketch, first, second, ignore_errors=True):
        return self.constraint(sketch, "AddPerpendicular", first, second, ignore_errors=ignore_errors)

    def add_parallel_constraint(self, sketch, first, second, ignore_errors=True):
        return self.constraint(sketch, "AddParallel", first, second, ignore_errors=ignore_errors)

    def add_symmetry_constraint(self, sketch, first, second, axis, ignore_errors=True):
        return self.constraint(sketch, "AddSymmetry", first, second, axis, ignore_errors=ignore_errors)

    def add_aligned_dimension(self, sketch, first, second, text_point, driven=False):
        return self.collection(sketch, "DimensionConstraints").AddTwoPointDistance(
            first, second, ALIGNED_DIM, text_point, driven,
        )

    def create_construction_axes(self, sketch, short1, short2):
        centers = []
        for line in (short1, short2):
            data = self.geometries.get(id(line))
            if data is None:
                data = snapshot_lines([line])[id(line)]
            centers.append(tuple((a + b) / 2 for a, b in zip(data.start, data.end)))
        (x1, y1), (x2, y2) = centers
        distance = math.hypot(x2 - x1, y2 - y1)
        if distance == 0:
            raise ValueError("Нельзя построить ось между совпадающими серединами рёбер.")
        ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
        nx, ny = -uy, ux
        axis = self.add_sketch_line(
            sketch, self.create_point2d(x1, y1), self.create_point2d(x2, y2), construction=True,
        )
        self.add_midpoint_constraint(sketch, axis.StartSketchPoint, short1)
        self.add_midpoint_constraint(sketch, axis.EndSketchPoint, short2)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        center = self.create_point2d(cx, cy)
        symmetry = self.add_sketch_line(
            sketch, self.create_point2d(cx - nx, cy - ny),
            self.create_point2d(cx + nx, cy + ny), construction=True,
        )
        self.add_perpendicular_constraint(sketch, axis, symmetry)
        self.add_midpoint_constraint(sketch, symmetry.StartSketchPoint, axis)
        return axis, symmetry, center, distance, ux, uy, nx, ny

    def create_drilling_points(self, sketch, center, ux, uy, distance, center_xy=None):
        cx, cy = center_xy if center_xy is not None else (center.X, center.Y)
        outer = distance / 2
        inner = outer - GRID_STEP_CM
        points = [self.add_sketch_point(
            sketch, self.create_point2d(cx + ux * position, cy + uy * position),
        ) for position in (-outer, outer, -inner, inner)]
        return (*points, self.add_sketch_point(sketch, center), outer)

    def constrain_drilling_points(self, sketch, axis, symmetry, points):
        left, right, left_inner, right_inner, center, _ = points
        for point in (left, right, left_inner, right_inner, center):
            self.add_coincident_constraint(sketch, point, axis)
        self.add_coincident_constraint(sketch, center, symmetry)
        self.add_symmetry_constraint(sketch, left, right, symmetry)
        self.add_symmetry_constraint(sketch, left_inner, right_inner, symmetry)
