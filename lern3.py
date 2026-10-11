from typing import cast  #  для IDE и автодополнения
from inventor_types import PartDocument

import pythoncom
from win32com.client import CastTo, gencache

from inventor_types import PartDocument

inv_unknown = pythoncom.GetActiveObject("Inventor.Application")
inv_dispatch = inv_unknown.QueryInterface(pythoncom.IID_IDispatch)
inv = gencache.EnsureDispatch(inv_dispatch)

active_doc = cast(PartDocument, CastTo(inv.ActiveDocument, "PartDocument"))
face = active_doc.SelectSet.Item(1)  # получили выделение
comp = active_doc.ComponentDefinition  # получили главный компонент детали
sketch = comp.Sketches.Add(face)  # создали новый эскиз
vertex = face.Vertices  # получили вершины грани
print(vertex.Count)  # количество вершин


points = []
for vertex in face.Vertices:
    p3d = vertex.Point
    p2d = sketch.ModelToSketchSpace(p3d)
    points.append(p2d)