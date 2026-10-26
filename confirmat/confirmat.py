from common.inventor_service_path import ensure_inventor_service_path
from common.settings import load_settings

ensure_inventor_service_path()

from inventor_service.settings import configure_settings
from workflows import confirmat as _confirmat

# Текущий выбор толщины хранится отдельно от постоянных имён PARAMETERS.
frame_thickness_param = _confirmat.frame_thickness_param
_ORIGINAL_ADD_COUNTERBORE_HOLES = _confirmat.add_counterbore_holes
K_EQUAL_TO_COMPARISON_TYPE = 60417
_LAST_CREATED_FEATURES = []


def _add_counterbore_holes_with_fallback(
    inventor,
    points,
    hole_diameter,
    hole_depth,
    direction,
    cbore_diameter,
    cbore_depth,
    name,
):
    global _LAST_CREATED_FEATURES
    _LAST_CREATED_FEATURES = []

    try:
        feature = _ORIGINAL_ADD_COUNTERBORE_HOLES(
            inventor,
            points,
            hole_diameter,
            hole_depth,
            direction,
            cbore_diameter,
            cbore_depth,
            name,
        )
        _LAST_CREATED_FEATURES = [feature]
        return feature
    except Exception as exc:
        print("  counterbore API failed, trying separate hole features:", exc)

    inner_feature = inventor.add_holes(
        points,
        diameter=hole_diameter,
        depth=hole_depth,
        direction=direction,
        name=f"{name} inner",
    )
    outer_feature = inventor.add_holes(
        points,
        diameter=cbore_diameter,
        depth=cbore_depth,
        direction=direction,
        name=f"{name} outer",
    )
    _LAST_CREATED_FEATURES = [
        feature for feature in (inner_feature, outer_feature) if feature is not None
    ]
    return outer_feature or inner_feature


def _settings_with_runtime_parameters(settings, parameter_names):
    linked = settings.setdefault("linked_parameters", [])
    available = {
        item.get("source_name", item.get("name"))
        for item in linked
        if item.get("source_name") or item.get("name")
    }
    for name in parameter_names:
        if name and name not in available:
            linked.append({"name": name, "source_name": name})
            available.add(name)
    return settings


def _sync_settings():
    settings = load_settings()
    settings = _settings_with_runtime_parameters(
        settings,
        (frame_thickness_param,),
    )
    configure_settings(settings)
    _confirmat.frame_thickness_param = frame_thickness_param
    _confirmat.add_counterbore_holes = _add_counterbore_holes_with_fallback


def _set_feature_suppressed(feature, suppressed):
    if feature is None:
        return False

    try:
        feature.Suppressed = suppressed
        return True
    except Exception:
        pass

    try:
        if suppressed:
            feature.Suppress()
        else:
            feature.Unsuppress()
        return True
    except Exception as exc:
        print("  center feature suppress state failed:", exc)
        return False


def _set_feature_suppression_condition(
    inventor,
    feature,
    parameter_name,
    expression,
):
    if feature is None or not parameter_name:
        return False

    try:
        parameter = inventor.parameter(parameter_name)
        feature.SetSuppressionCondition(
            parameter,
            K_EQUAL_TO_COMPARISON_TYPE,
            expression,
        )
        print(
            "  center feature suppression condition:",
            parameter_name,
            "==",
            expression,
        )
        return True
    except Exception as exc:
        print("  center feature suppression condition failed:", exc)
        return False


def _set_features_suppression_condition(
    inventor,
    features,
    parameter_name,
    expression,
):
    changed = 0

    for feature in features:
        if _set_feature_suppression_condition(
            inventor,
            feature,
            parameter_name,
            expression,
        ):
            changed += 1

    return changed > 0


def _set_features_suppressed(features, suppressed):
    changed = 0

    for feature in features:
        if _set_feature_suppressed(feature, suppressed):
            changed += 1

    return changed > 0


def _confirmat_points_by_face(inventor, sketch, sketch_faces, face_label):
    result = []

    for face_index, face in enumerate(sketch_faces, start=1):
        points = _confirmat.confirmat_points_for_sketch(
            inventor,
            sketch,
            [face],
            include_center=True,
            face_label=face_label,
        )
        print(f"  face {face_index} confirmat points:", len(points))
        if len(points) < 3:
            continue

        result.append(points)

    return result


def create_confirmat_edges_and_center_features(
    inventor,
    sketches=None,
    faces=None,
    face_label="selected",
    direction=None,
    center_suppressed=False,
    center_suppression_parameter=None,
    center_suppression_value=2,
):
    _sync_settings()

    colored_faces = faces or inventor.colored_faces("yellow")
    sketches = sketches or _confirmat.find_confirmat_sketches_on_faces(
        inventor,
        colored_faces,
        face_label,
    )
    edge_outer = _confirmat.confirmat_hole("outer_2pcs") or _confirmat.confirmat_hole("outer")
    edge_inner = _confirmat.confirmat_hole("inner_2pcs") or _confirmat.confirmat_hole("inner")
    center_outer = _confirmat.confirmat_hole("outer_3pcs") or edge_outer
    center_inner = _confirmat.confirmat_hole("inner_3pcs") or edge_inner
    created = 0
    edge_points = []
    center_points = []

    print("Confirmat edge/center sketches found:", len(sketches))

    plane_offsets = _confirmat.sketch_plane_offsets(inventor)
    for sketch in sketches:
        print("Sketch:", sketch.Name)
        print(
            "  sketch lines/points/dims:",
            inventor.sketch_line_count(sketch),
            inventor.sketch_point_count(sketch),
            inventor.sketch_dimension_count(sketch),
        )
        _confirmat.try_share_sketch(sketch)

        sketch_faces = _confirmat.faces_on_sketch_plane(
            sketch,
            colored_faces,
            plane_offsets,
        )
        print(f"  {face_label} faces on sketch plane:", len(sketch_faces))

        for face_points in _confirmat_points_by_face(
            inventor,
            sketch,
            sketch_faces,
            face_label,
        ):
            edge_points.extend([face_points[0], face_points[-1]])
            center_points.append(face_points[1])

        _confirmat.try_share_sketch(sketch)

    edge_points = inventor.unique_points(edge_points)
    center_points = inventor.unique_points(center_points)
    print("Total edge confirmat points:", len(edge_points))
    print("Total center confirmat points:", len(center_points))

    if edge_points:
        try:
            _confirmat.add_confirmat_counterbore(
                inventor,
                edge_points,
                edge_outer,
                edge_inner,
                "Confirmat 2pcs edge counterbore",
                direction=direction,
            )
            created += 1
            print("  created one edge confirmat feature for all edge points")
        except Exception as exc:
            print("  edge confirmat counterbore failed:", exc)

    if center_points:
        try:
            center_feature = _confirmat.add_confirmat_counterbore(
                inventor,
                center_points,
                center_outer,
                center_inner,
                "Confirmat center counterbore",
                direction=direction,
            )
            center_features = _LAST_CREATED_FEATURES or [center_feature]
            if center_suppression_parameter and _set_features_suppression_condition(
                inventor,
                center_features,
                center_suppression_parameter,
                center_suppression_value,
            ):
                pass
            elif _set_features_suppressed(center_features, center_suppressed):
                state = "suppressed" if center_suppressed else "visible"
                print("  center confirmat feature state:", state)
            created += 1
            print("  created one center confirmat feature for all center points")
        except Exception as exc:
            print("  center confirmat counterbore failed:", exc)

    print(f"{face_label.capitalize()} faces appearance reset skipped")
    inventor.update()
    return created
