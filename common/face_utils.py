def appearance_text(face):
    parts = []
    objects = [face]

    try:
        objects.append(face.Parent)
    except Exception:
        pass

    for obj in objects:
        if obj is None:
            continue

        try:
            appearance = obj.Appearance
        except Exception:
            continue

        for attr in ("DisplayName", "Name"):
            try:
                parts.append(getattr(appearance, attr))
            except Exception:
                pass

    return " ".join(parts).lower()


def appearance_key(face):
    parts = []
    objects = [face]

    try:
        objects.append(face.Parent)
    except Exception:
        pass

    for obj in objects:
        if obj is None:
            continue

        try:
            appearance = obj.Appearance
        except Exception:
            continue

        for attr in ("InternalName", "DisplayName", "Name"):
            try:
                parts.append(str(getattr(appearance, attr)))
            except Exception:
                pass

        if parts:
            break

    return "|".join(parts).lower()


def face_color(face):
    try:
        appearance = face.Appearance
    except Exception:
        try:
            appearance = face.Parent.Appearance
        except Exception:
            return None

    for name in (
        "generic_diffuse",
        "plasticvinyl_color",
        "metal_color",
        "ceramic_color",
        "masonrycmu_color",
    ):
        try:
            return appearance.Item(name).Value
        except Exception:
            pass

    for index in range(1, appearance.Count + 1):
        try:
            value = appearance.Item(index).Value
            if all(hasattr(value, attr) for attr in ("Red", "Green", "Blue")):
                return value
        except Exception:
            pass

    return None


def color_rgb(color):
    if color is None:
        return None

    try:
        return int(color.Red), int(color.Green), int(color.Blue)
    except Exception:
        return None


def detected_face_rgb(face):
    try:
        text = appearance_text(face)
    except Exception:
        return None

    if "red" in text or "\u043a\u0440\u0430\u0441" in text:
        return 255, 0, 0
    if "green" in text or "\u0437\u0435\u043b\u0435\u043d" in text or "\u0437\u0435\u043b\u0451\u043d" in text:
        return 0, 180, 0
    if "yellow" in text or "\u0436\u0435\u043b\u0442" in text or "\u0436\u0451\u043b\u0442" in text:
        return 255, 220, 0
    if "blue" in text or "\u0441\u0438\u043d" in text or "\u0433\u043e\u043b\u0443\u0431" in text:
        return 0, 80, 255

    return None


def face_color_rgb(face):
    return detected_face_rgb(face) or color_rgb(face_color(face))


def create_rgb_color(rgb, transient_objects=None):
    if rgb is None or transient_objects is None:
        return None

    try:
        return transient_objects.CreateColor(rgb[0], rgb[1], rgb[2])
    except Exception:
        return None


def clone_color(color, transient_objects=None):
    if color is None or transient_objects is None:
        return color

    try:
        return transient_objects.CreateColor(color.Red, color.Green, color.Blue)
    except Exception:
        return color


def same_color(color1, color2, tol=2):
    rgb1 = color_rgb(color1)
    rgb2 = color_rgb(color2)

    if rgb1 is None or rgb2 is None:
        return False

    try:
        return (
            abs(rgb1[0] - rgb2[0]) <= tol
            and abs(rgb1[1] - rgb2[1]) <= tol
            and abs(rgb1[2] - rgb2[2]) <= tol
        )
    except Exception:
        return False


def sketch_color_matches_face(sketch, face):
    try:
        sketch_rgb = color_rgb(sketch.Color)
        face_rgb = face_color_rgb(face)
        return sketch_rgb is not None and sketch_rgb == face_rgb
    except Exception:
        return False


def set_sketch_color_from_face(sketch, face, transient_objects=None):
    rgb = face_color_rgb(face)
    color = create_rgb_color(rgb, transient_objects) or face_color(face)
    return set_sketch_color(sketch, color, transient_objects)


def set_sketch_color_rgb(sketch, rgb, transient_objects=None):
    color = create_rgb_color(rgb, transient_objects)
    return set_sketch_color(sketch, color, transient_objects)


def set_sketch_color(sketch, color, transient_objects=None):
    if color is None:
        return False

    color = clone_color(color, transient_objects)
    changed = False

    try:
        sketch.Color = color
    except Exception:
        pass
    else:
        changed = True

    for collection_name in ("SketchLines", "SketchCircles", "SketchArcs", "SketchEllipses"):
        try:
            collection = getattr(sketch, collection_name)
        except Exception:
            continue

        try:
            count = collection.Count
        except Exception:
            continue

        for index in range(1, count + 1):
            try:
                collection.Item(index).OverrideColor = color
            except Exception:
                pass
            else:
                changed = True

    return changed


K_FEATURE_APPEARANCE = 100610


def unique_faces(faces):
    result = []
    seen = set()

    for face in faces:
        try:
            key = face.ReferenceKey
        except Exception:
            key = id(face)

        if key in seen:
            continue

        seen.add(key)
        result.append(face)

    return result


def reset_faces_to_feature_appearance(faces, label="faces"):
    reset_count = 0

    for face in unique_faces(faces):
        try:
            face.AppearanceSourceType = K_FEATURE_APPEARANCE
        except Exception as exc:
            print(f"  {label} appearance reset failed:", exc)
            continue

        reset_count += 1

    return reset_count


def reset_faces_to_default_appearance(faces):
    return reset_faces_to_feature_appearance(faces)


def sketch_on_face_plane_with_color(sketches, face, prefix):
    empty_sketch = None

    for index in range(1, sketches.Count + 1):
        sketch = sketches.Item(index)
        try:
            if not sketch.Name.startswith(prefix):
                continue
            if not same_plane_entity(sketch.PlanarEntity, face):
                continue
        except Exception:
            continue

        if sketch_color_matches_face(sketch, face):
            return sketch

        try:
            is_empty = sketch.SketchLines.Count == 0 and sketch.SketchPoints.Count == 0
        except Exception:
            is_empty = False

        if is_empty and empty_sketch is None:
            empty_sketch = sketch

    return empty_sketch


def is_red(face):
    try:
        color = appearance_text(face)
        return "red" in color or "\u043a\u0440\u0430\u0441" in color
    except Exception:
        return False


def is_green(face):
    try:
        color = appearance_text(face)
        return "green" in color or "\u0437\u0435\u043b\u0435\u043d" in color or "\u0437\u0435\u043b\u0451\u043d" in color
    except Exception:
        return False


def is_yellow(face):
    try:
        color = appearance_text(face)
        return "yellow" in color or "\u0436\u0435\u043b\u0442" in color or "\u0436\u0451\u043b\u0442" in color
    except Exception:
        return False


def is_blue(face):
    try:
        color = appearance_text(face)
        return "blue" in color or "\u0441\u0438\u043d" in color or "\u0433\u043e\u043b\u0443\u0431" in color
    except Exception:
        return False


def is_drilling_face(face):
    return is_red(face) or is_green(face) or is_yellow(face)


def same_plane(face1, face2, tol=0.001):
    g1 = face1.Geometry
    g2 = face2.Geometry
    n1 = g1.Normal
    n2 = g2.Normal
    p1 = g1.RootPoint
    p2 = g2.RootPoint
    dot = n1.X * n2.X + n1.Y * n2.Y + n1.Z * n2.Z
    dist = (p2.X - p1.X) * n1.X + (p2.Y - p1.Y) * n1.Y + (p2.Z - p1.Z) * n1.Z
    return abs(abs(dot) - 1) <= tol and abs(dist) < tol


def plane_geometry(entity):
    try:
        return entity.Geometry
    except Exception:
        return entity.Plane


def same_plane_entity(entity1, entity2, tol=0.001):
    g1 = plane_geometry(entity1)
    g2 = plane_geometry(entity2)
    n1 = g1.Normal
    n2 = g2.Normal
    p1 = g1.RootPoint
    p2 = g2.RootPoint
    dot = n1.X * n2.X + n1.Y * n2.Y + n1.Z * n2.Z
    dist = (p2.X - p1.X) * n1.X + (p2.Y - p1.Y) * n1.Y + (p2.Z - p1.Z) * n1.Z
    return abs(abs(dot) - 1) <= tol and abs(dist) < tol


def sketch_exists_on_face_plane(sketches, face, prefix):
    return sketch_on_face_plane(sketches, face, prefix) is not None


def sketch_on_face_plane(sketches, face, prefix):
    for index in range(1, sketches.Count + 1):
        sketch = sketches.Item(index)
        try:
            if not sketch.Name.startswith(prefix):
                continue
            if same_plane_entity(sketch.PlanarEntity, face):
                return sketch
        except Exception:
            continue

    return None


def get_red_faces(comp):
    return [face for body in comp.SurfaceBodies for face in body.Faces if is_red(face)]


def get_yellow_faces(comp):
    return [face for body in comp.SurfaceBodies for face in body.Faces if is_yellow(face)]


def get_green_faces(comp):
    return [face for body in comp.SurfaceBodies for face in body.Faces if is_green(face)]


def get_blue_faces(comp):
    return [face for body in comp.SurfaceBodies for face in body.Faces if is_blue(face)]


def get_drilling_faces(comp):
    return [
        face
        for body in comp.SurfaceBodies
        for face in body.Faces
        if is_drilling_face(face)
    ]


def collect_colored_faces(comp):
    faces = {
        "red": [],
        "green": [],
        "yellow": [],
        "blue": [],
    }

    for body in comp.SurfaceBodies:
        for face in body.Faces:
            try:
                text = appearance_text(face)
            except Exception:
                continue

            if "red" in text or "\u043a\u0440\u0430\u0441" in text:
                faces["red"].append(face)
            if "green" in text or "\u0437\u0435\u043b\u0435\u043d" in text or "\u0437\u0435\u043b\u0451\u043d" in text:
                faces["green"].append(face)
            if "yellow" in text or "\u0436\u0435\u043b\u0442" in text or "\u0436\u0451\u043b\u0442" in text:
                faces["yellow"].append(face)
            if "blue" in text or "\u0441\u0438\u043d" in text or "\u0433\u043e\u043b\u0443\u0431" in text:
                faces["blue"].append(face)

    faces["drilling"] = faces["red"] + faces["green"] + faces["yellow"]
    return faces


def selection_object_label(obj):
    labels = []

    for attr in ("Type", "ObjectType", "DisplayName", "Name"):
        try:
            labels.append(f"{attr}={getattr(obj, attr)}")
        except Exception:
            pass

    try:
        labels.append(f"class={obj.__class__.__name__}")
    except Exception:
        pass

    return ", ".join(labels) or "unknown object"


def is_face_like(obj):
    try:
        obj.Geometry
        obj.Edges.Count
        obj.Vertices.Count
    except Exception:
        return False

    return True


def face_from_selection_object(obj):
    if is_face_like(obj):
        return obj

    for attr in ("NativeObject", "ContainingFace"):
        try:
            candidate = getattr(obj, attr)
        except Exception:
            continue

        if is_face_like(candidate):
            return candidate

    return None


def selected_faces(document, debug=False):
    faces = []

    try:
        select_set = document.SelectSet
    except Exception as exc:
        if debug:
            print("Selection read failed:", exc)
        return faces

    try:
        count = select_set.Count
    except Exception as exc:
        if debug:
            print("Selection count failed:", exc)
        return faces

    if debug:
        print("Selected objects:", count)

    for index in range(1, count + 1):
        try:
            selected = select_set.Item(index)
        except Exception as exc:
            if debug:
                print(f"  selection {index} read failed:", exc)
            continue

        face = face_from_selection_object(selected)
        if face is None:
            if debug:
                print(f"  selection {index} skipped:", selection_object_label(selected))
            continue

        if debug:
            try:
                text = appearance_text(face)
            except Exception:
                text = ""
            print(f"  selection {index} face:", text or "no appearance text")

        faces.append(face)

    return unique_faces(faces)


def group_faces_by_plane(faces):
    groups = []

    for face in faces:
        for group in groups:
            if same_plane(group[0], face):
                group.append(face)
                break
        else:
            groups.append([face])

    return groups


def group_faces_by_plane_and_appearance(faces):
    groups = []

    for face in faces:
        key = appearance_key(face)

        for group in groups:
            if group["key"] == key and same_plane(group["faces"][0], face):
                group["faces"].append(face)
                break
        else:
            groups.append({"key": key, "faces": [face]})

    return [group["faces"] for group in groups]
