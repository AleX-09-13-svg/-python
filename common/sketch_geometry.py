from common.constants import ALIGNED_DIM


def unique_parameter_name(parameters, base):
    name = base
    index = 1
    while True:
        try:
            parameters.Item(name)
            index += 1
            name = f"{base}_{index}"
        except Exception:
            return name


def get_parameter_value(parameters, name, default_value):
    try:
        return parameters.Item(name).Value
    except Exception:
        return default_value


def ensure_user_parameter(parameters, name, expression):
    try:
        parameter = parameters.Item(name)
    except Exception:
        parameter = parameters.UserParameters.AddByExpression(name, expression, "mm")

    parameter.Expression = expression
    return parameter


def distance(point1, point2):
    return ((point1.X - point2.X) ** 2 + (point1.Y - point2.Y) ** 2) ** 0.5


def line_length(line):
    return distance(line.StartSketchPoint.Geometry, line.EndSketchPoint.Geometry)


def line_length2(line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    dx = end.X - start.X
    dy = end.Y - start.Y
    return dx * dx + dy * dy


def line_midpoint(tg, line):
    start = line.StartSketchPoint.Geometry
    end = line.EndSketchPoint.Geometry
    return tg.CreatePoint2d((start.X + end.X) / 2, (start.Y + end.Y) / 2)


def add_aligned_dimension(sk, point1, point2, text_point, driven=False):
    return sk.DimensionConstraints.AddTwoPointDistance(
        point1,
        point2,
        ALIGNED_DIM,
        text_point,
        driven,
    )


def hide_sketch_dimensions(sketch):
    try:
        sketch.DimensionsVisible = False
        return True
    except Exception:
        return False


def project_face_edges(sk, face):
    before = sk.SketchLines.Count
    for edge in face.Edges:
        try:
            sk.AddByProjectingEntity(edge)
        except Exception:
            pass

    return before


def face_bounds_in_sketch(sk, face):
    pts = [sk.ModelToSketchSpace(v.Point) for v in face.Vertices]
    xs = [p.X for p in pts]
    ys = [p.Y for p in pts]
    return min(xs), max(xs), min(ys), max(ys)


def sketch_lines_for_face(sk, face, first_new_line, tol=0.01):
    x1, x2, y1, y2 = face_bounds_in_sketch(sk, face)

    def inside(point):
        return x1 - tol <= point.X <= x2 + tol and y1 - tol <= point.Y <= y2 + tol

    lines = []
    for i in range(first_new_line + 1, sk.SketchLines.Count + 1):
        line = sk.SketchLines.Item(i)
        if not line.Construction:
            lines.append(line)

    if len(lines) < 2:
        lines = []
        for i in range(1, sk.SketchLines.Count + 1):
            line = sk.SketchLines.Item(i)
            if line.Construction:
                continue
            if inside(line.StartSketchPoint.Geometry) and inside(line.EndSketchPoint.Geometry):
                lines.append(line)

    return lines


def sketch_has_geometry_for_face(sk, face, tol=0.01):
    try:
        x1, x2, y1, y2 = face_bounds_in_sketch(sk, face)
    except Exception:
        return False

    def inside(point):
        return x1 - tol <= point.X <= x2 + tol and y1 - tol <= point.Y <= y2 + tol

    inside_lines = 0
    for index in range(1, sk.SketchLines.Count + 1):
        line = sk.SketchLines.Item(index)
        try:
            if line.Construction:
                continue
            if inside(line.StartSketchPoint.Geometry) and inside(line.EndSketchPoint.Geometry):
                inside_lines += 1
                if inside_lines >= 2:
                    return True
        except Exception:
            continue

    return False
