"""Общее прямое ребро выбранных граней — база парных эскизов."""
import math
from dataclasses import dataclass


def coordinates(point):
    return (point.X, point.Y, point.Z)


def edge_endpoints(edge):
    return coordinates(edge.StartVertex.Point), coordinates(edge.StopVertex.Point)


def same_point(a, b, tolerance=1e-5):
    return sum((x - y) ** 2 for x, y in zip(a, b)) <= tolerance ** 2


@dataclass(frozen=True)
class EdgeGeometry:
    edge: object
    kind: int
    endpoints: object


class FaceEdgeCache:
    def __init__(self, inventor):
        self.inventor = inventor
        self.faces = {}
        self.edges = {}

    def face(self, face):
        key = id(face)
        if key not in self.faces:
            records = []
            for edge in self.inventor.face_edges(face):
                kind = edge.GeometryType
                endpoints = edge_endpoints(edge) if kind in (5122, 5123) else None
                record = EdgeGeometry(edge, kind, endpoints)
                records.append(record)
                self.edges[id(edge)] = record
            self.faces[key] = (face, records)
        return self.faces[key][1]

    def endpoints(self, edge):
        record = self.edges.get(id(edge))
        return record.endpoints if record is not None else edge_endpoints(edge)


def shared_intersection_edge(inventor, first_face, second_face, intersection, edge_cache=None):
    origin, direction = intersection
    norm2 = sum(value * value for value in direction)
    if norm2 < 1e-8:
        raise ValueError("Выбранные плоскости не имеют однозначной линии пересечения.")
    cache = edge_cache if edge_cache is not None else FaceEdgeCache(inventor)
    second_edges = [record.endpoints for record in cache.face(second_face)
                    if record.endpoints is not None]
    candidates = []
    for record in cache.face(first_face):
        if record.endpoints is None:
            continue
        a, b = record.endpoints
        if same_point(a, b):
            continue
        on_intersection = True
        for point in (a, b):
            delta = tuple(x - y for x, y in zip(point, origin))
            along = sum(x * y for x, y in zip(delta, direction)) / norm2
            nearest = tuple(o + along * d for o, d in zip(origin, direction))
            if not same_point(point, nearest):
                on_intersection = False
                break
        if on_intersection and any(
            (same_point(a, c) and same_point(b, d)) or
            (same_point(a, d) and same_point(b, c)) for c, d in second_edges
        ):
            candidates.append(record.edge)
    if len(candidates) != 1:
        raise ValueError(
            "Для пары граней требуется одно общее прямое ребро на пересечении плоскостей. "
            f"Найдено: {len(candidates)}."
        )
    return candidates[0]


@dataclass(frozen=True)
class LineGeometry:
    start_point: object
    end_point: object
    start: tuple
    end: tuple

    @property
    def length_squared(self):
        return sum((b - a) ** 2 for a, b in zip(self.start, self.end))


def snapshot_lines(lines):
    result = {}
    for line in lines:
        if id(line) in result:
            continue
        a, b = line.StartSketchPoint, line.EndSketchPoint
        p, q = a.Geometry, b.Geometry
        result[id(line)] = LineGeometry(a, b, (p.X, p.Y), (q.X, q.Y))
    return result


def end_lines_for_reference(reference, lines, tolerance=1e-5, geometries=None):
    """Смежные с общим ребром стороны вместо выбора двух самых коротких."""
    if geometries is None:
        geometries = snapshot_lines([*lines, reference])
    a, b = geometries[id(reference)].start, geometries[id(reference)].end
    found = []
    for endpoint in (a, b):
        candidates = []
        for line in lines:
            data = geometries[id(line)]
            p, q = data.start, data.end
            cross = (q[0] - p[0]) * (b[1] - a[1]) - (q[1] - p[1]) * (b[0] - a[0])
            if abs(cross) <= tolerance:
                continue
            if any(math.hypot(point[0] - endpoint[0], point[1] - endpoint[1]) <= tolerance
                   for point in (p, q)):
                candidates.append(line)
        if len(candidates) != 1:
            raise ValueError("Не удалось однозначно определить боковые рёбра у концов общего ребра.")
        found.append(candidates[0])
    return found
