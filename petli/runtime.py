"""Подготовка уже проверенных центров 07 без повторного обхода геометрии COM."""
from stiajka.hole_builder import PreparedHolePoints, timed_stage


def prepare_centers(builder, points, label):
    """Только уникальные, уже помеченные центры, созданные построителями 07.

    Расстояния и пересечения проверены layout до создания операций.
    Общий построитель отверстий сохраняет полную проверку для остальных команд.
    """
    with timed_stage(label, "сбор центров без повторного чтения геометрии"):
        points = tuple(points)
        return PreparedHolePoints(builder, points, builder.inventor.object_collection(points))
