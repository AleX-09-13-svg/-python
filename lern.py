from typing import Iterable, cast

import pythoncom
from win32com.client import CastTo, gencache


from inventor_types import (
    Face,
    InventorApplication,
    ObjectCollection,
    PartDocument,
    Point2d,
    Sketch,
    TransientGeometry,
)

HOLE_DIAMETER = "5 mm"
HOLE_DEPTH = "10 mm"
INVERT_HOLE_DIRECTION = False
POSITIVE_EXTENT_DIRECTION = 20993
NEGATIVE_EXTENT_DIRECTION = 20994


def get_inventor() -> InventorApplication:
    return cast(
        InventorApplication,
        gencache.EnsureDispatch(
            pythoncom.GetActiveObject("Inventor.Application").QueryInterface(
                pythoncom.IID_IDispatch
            )
        ),
    )


def get_hole_direction() -> int:
    if INVERT_HOLE_DIRECTION:
        return POSITIVE_EXTENT_DIRECTION

    return NEGATIVE_EXTENT_DIRECTION


def selected_face(doc: PartDocument) -> Face:
    return doc.SelectSet.Item(1)


def face_center_in_sketch(
    sketch: Sketch,
    face: Face,
    tg: TransientGeometry,
) -> Point2d:
    points = [sketch.ModelToSketchSpace(vertex.Point) for vertex in face.Vertices]
    return tg.CreatePoint2d(
        sum(point.X for point in points) / len(points),
        sum(point.Y for point in points) / len(points),
    )


def object_collection(
    inv: InventorApplication,
    objects: Iterable[object],
) -> ObjectCollection:
    collection = inv.TransientObjects.CreateObjectCollection()
    for obj in objects:
        collection.Add(obj)
    return collection


def main():
    inv = get_inventor()

    doc = cast(PartDocument, CastTo(inv.ActiveDocument, "PartDocument"))
    comp = doc.ComponentDefinition
    face = selected_face(doc)

    sketch = comp.Sketches.Add(face)
    sketch.Name = "LearnCenterHoleSketch"

    center = face_center_in_sketch(sketch, face, inv.TransientGeometry)
    point = sketch.SketchPoints.Add(center, False)
    point.HoleCenter = True

    hole_features = comp.Features.HoleFeatures
    placement = hole_features.CreateSketchPlacementDefinition(
        object_collection(inv, [point])
    )
    hole = hole_features.AddDrilledByDistanceExtent(
        placement,
        HOLE_DIAMETER,
        HOLE_DEPTH,
        get_hole_direction(),
        True,
    )
    hole.Name = "Learn center hole"

    doc.Update()
    print("Created sketch point and hole on selected face.")


if __name__ == "__main__":
    main()
