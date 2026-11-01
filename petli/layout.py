"""Расчёт в сантиметрах (внутренние единицы Inventor)."""
import math
from dataclasses import dataclass, replace


PILOT_SPACING = 4.5  # 45 мм между центрами наколок.
PILOT_INSET = 0.95  # 9.5 мм от центра чашки вглубь фасада.


@dataclass(frozen=True)
class Layout:
    edge_index: int
    start: tuple
    along: tuple
    inward: tuple
    length: float
    width: float
    distances: tuple


def hinge_count(height_mm):
    if not math.isfinite(height_mm) or height_mm <= 0:
        raise ValueError("Размер фасада должен быть положительным.")
    return 2 if height_mm < 1000 else 3 if height_mm < 1600 else 4 if height_mm < 2000 else 5


def pilot_positions(layout, cup_diameter, pilot_diameter):
    """Координаты наколок вдоль кромки и от неё, с проверкой размещения."""
    if not math.isfinite(pilot_diameter) or pilot_diameter <= 0:
        raise ValueError("Диаметр наколки должен быть положительным.")
    offset = 2.2 + PILOT_INSET
    positions = tuple((t + sign * PILOT_SPACING / 2, offset)
                      for t in layout.distances for sign in (-1, 1))
    radius = pilot_diameter / 2
    for index, (t, across) in enumerate(positions):
        if radius > min(t, layout.length - t, across, layout.width - across):
            raise ValueError("Отверстия наколки выходят за границы фасада.")
        if any(math.hypot(t - center, across - 2.2) <= radius + cup_diameter / 2
               for center in layout.distances):
            raise ValueError("Отверстия наколки пересекаются с чашками петель.")
        if any(math.dist((t, across), other) <= pilot_diameter for other in positions[:index]):
            raise ValueError("Отверстия наколки пересекаются между собой.")
    return positions


def rectangle_frame(segments, side_start, side_direction):
    """Выбрать кромку прямоугольника, ближайшую к следу плоскости боковины."""
    tolerance = 1e-5
    if len(segments) != 4:
        raise ValueError("Для 07 нужен прямоугольный фасад без вырезов.")
    norm = math.hypot(*side_direction)
    if norm < tolerance:
        raise ValueError("Не удалось определить направление боковины.")
    u = tuple(v / norm for v in side_direction)
    n = (-u[1], u[0])

    def dot(p, axis):
        return sum(p[i] * axis[i] for i in range(2))

    corners = []
    for a, b in segments:
        if math.dist(a, b) < tolerance:
            raise ValueError("Нулевое ребро фасада.")
        for p in (a, b):
            if not any(math.dist(p, q) < tolerance for q in corners):
                corners.append(p)
    if len(corners) != 4:
        raise ValueError("Контур фасада должен иметь четыре угла.")
    along = [dot(p, u) for p in corners]
    across = [dot(p, n) for p in corners]
    lo, hi = min(along), max(along)
    left, right = min(across), max(across)
    if hi - lo < tolerance or right - left < tolerance:
        raise ValueError("Вырожденный контур фасада.")
    for p in corners:
        if (min(abs(dot(p, u) - v) for v in (lo, hi)) > tolerance or
                min(abs(dot(p, n) - v) for v in (left, right)) > tolerance):
            raise ValueError("Кромки фасада должны быть параллельны и перпендикулярны боковине.")
    candidates = []
    center = tuple(sum(p[i] for p in corners) / 4 for i in range(2))
    for index, (a, b) in enumerate(segments):
        da, db = dot(a, u) - dot(b, u), dot(a, n) - dot(b, n)
        if abs(da) > tolerance and abs(db) > tolerance:
            raise ValueError("Контур фасада должен быть прямоугольным.")
        if abs(db) < tolerance:
            candidates.append((abs(dot(a, n) - dot(side_start, n)), index))
    candidates.sort()
    if len(candidates) != 2 or abs(candidates[0][0] - candidates[1][0]) < tolerance:
        raise ValueError("Боковина не определяет однозначно сторону петель.")
    index = candidates[0][1]
    a, b = segments[index]
    length = math.dist(a, b)
    axis = tuple((b[i] - a[i]) / length for i in range(2))
    inward = (-axis[1], axis[0])
    if dot(tuple(center[i] - a[i] for i in range(2)), inward) < 0:
        inward = tuple(-v for v in inward)
    width = right - left
    return Layout(index, a, axis, inward, length, width, ())


def calculate_layout(segments, side_start, side_direction, diameter):
    frame = rectangle_frame(segments, side_start, side_direction)
    length, width = frame.length, frame.width
    count = hinge_count(length * 10)
    if not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("Диаметр петли должен быть положительным.")
    step = (length - 20) / (count - 1)
    if length <= 20 or step <= diameter or diameter / 2 > min(2.2, width - 2.2, 10):
        raise ValueError("На фасаде недостаточно места для отверстий с отступами 100 и 22 мм.")
    return replace(frame, distances=tuple(10 + i * step for i in range(count)))


def side_hole_rows(frame, projected_centers, diameter):
    """Точка на переднем ребре, центр в 20 мм и центр в 52 мм для каждой петли."""
    if not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("Диаметр наколки должен быть положительным.")
    rows, centers = [], []
    for p in projected_centers:
        t = sum((p[i] - frame.start[i]) * frame.along[i] for i in range(2))
        if diameter / 2 > min(t, frame.length - t, 2, frame.width - 5.2):
            raise ValueError("Отверстия на боковине выходят за её границы: нужны отступы 20 и 52 мм.")
        row = tuple(tuple(frame.start[i] + frame.along[i] * t + frame.inward[i] * offset
                          for i in range(2)) for offset in (0, 2, 5.2))
        for point in row[1:]:
            if any(math.dist(point, other) <= diameter for other in centers):
                raise ValueError("Отверстия на боковине пересекаются между собой.")
            centers.append(point)
        rows.append(row)
    return rows
