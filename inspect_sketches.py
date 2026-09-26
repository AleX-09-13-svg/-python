import pythoncom
from win32com.client import dynamic


inv = dynamic.Dispatch(
    pythoncom.GetActiveObject("Inventor.Application").QueryInterface(
        pythoncom.IID_IDispatch
    )
)
doc = inv.ActiveDocument
comp = doc.ComponentDefinition

print("Document:", doc.DisplayName)
print("Sketches:", comp.Sketches.Count)

start = max(1, comp.Sketches.Count - 1)

for i in range(start, comp.Sketches.Count + 1):
    if i > comp.Sketches.Count:
        print(f"Sketch {i}: not found")
        continue

    sk = comp.Sketches.Item(i)
    print()
    print(f"Sketch {i}: {sk.Name}")
    print("  Lines:", sk.SketchLines.Count)
    print("  Points:", sk.SketchPoints.Count)
    print("  Dimensions:", sk.DimensionConstraints.Count)
    print("  Geometric constraints:", sk.GeometricConstraints.Count)

    for j in range(1, sk.SketchPoints.Count + 1):
        point = sk.SketchPoints.Item(j)
        geo = point.Geometry
        print(f"    Point {j}: X={geo.X:.4f}, Y={geo.Y:.4f}")

    for j in range(1, sk.SketchLines.Count + 1):
        line = sk.SketchLines.Item(j)
        p1 = line.StartSketchPoint.Geometry
        p2 = line.EndSketchPoint.Geometry
        construction = getattr(line, "Construction", False)
        print(
            f"    Line {j}: "
            f"({p1.X:.4f}, {p1.Y:.4f}) -> ({p2.X:.4f}, {p2.Y:.4f}), "
            f"construction={construction}"
        )

    for j in range(1, sk.DimensionConstraints.Count + 1):
        dim = sk.DimensionConstraints.Item(j)
        try:
            param = dim.Parameter
            print(
                f"    Dim {j}: "
                f"name={param.Name}, expression={param.Expression}, value={param.Value}"
            )
        except Exception as exc:
            print(f"    Dim {j}: error={exc}")
