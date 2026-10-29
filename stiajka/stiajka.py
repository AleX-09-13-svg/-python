# Настройки стяжки и создание отверстий для сценария 05_stiajka.py.
from time import perf_counter

from common.constants import DRILLING_SKETCH_PREFIX
from common.settings import hole_direction, setting
from workflows import confirmat as _confirmat
from stiajka.hole_builder import AffectedBodyError, TimedHoleBuilder


def stiajka_setting(*keys, default=None):
    return setting("stiajka", *keys, default=default)


def stiajka_parameter(name, default):
    return stiajka_setting("parameters", name, default=default)


def stiajka_hole(name):
    return stiajka_setting(name, default={})


def stiajka_direction(hole_settings):
    return hole_direction(hole_settings.get("direction", "positive"))


def unique_names(names):
    result = []
    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def stiajka_required_parameter_names():
    names = [
        stiajka_parameter("diameter", "Стяжка_D"),
        stiajka_parameter("depth", "Стяжка_h"),
        stiajka_parameter("offset", "Стяжка_отступ"),
    ]
    for key in ("Otv_stijki_v_torec", "Otv_stijki_v_bokoviny", "shkant_v_plast", "shkant_v_torets"):
        settings = stiajka_hole(key)
        names.append(settings.get("diameter"))
        names.append(settings.get("depth"))
    cup = stiajka_hole("Chashka stiajki")
    names.append(cup.get("diameter_parameter"))
    names.append(cup.get("depth_parameter"))
    return unique_names(names)


def log_elapsed(label, started):
    elapsed = perf_counter() - started
    print(f"  {label}: {elapsed:.2f}s", flush=True)
    return perf_counter()


def axis_stiajka_points(axis_data):
    points = axis_data["points"]
    if len(points) < 5:
        return ([], [])
    return ([points[0][1], points[-1][1]], [points[1][1], points[-2][1]])


def faces_on_sketch_plane(inventor, sketch, faces):
    try:
        sketch_plane = sketch.PlanarEntity
    except Exception:
        return []
    result = []
    for face in faces:
        try:
            if inventor.same_plane_entity(sketch_plane, face):
                result.append(face)
        except Exception:
            continue
    return result


def point_inside_sketch_bounds(x, y, bounds, tol=0.01):
    min_x, max_x, min_y, max_y = bounds
    return min_x - tol <= x <= max_x + tol and min_y - tol <= y <= max_y + tol


def colored_face_for_axis(inventor, sketch, axis_data, faces):
    for face in faces:
        try:
            bounds = inventor.face_bounds_in_sketch(face, sketch)
        except Exception:
            continue
        if point_inside_sketch_bounds(axis_data["mid_x"], axis_data["mid_y"], bounds):
            return face
    return None


def create_hole_batch(
    inventor,
    jobs,
    points_key,
    settings_key,
    default_diameter,
    default_depth,
    default_name,
    label,
    success_key=None,
    strict=False,
    hole_creator=None,
    affected_body=None,
):
    body_key = ("neighbor_body" if settings_key in ("Otv_stijki_v_bokoviny", "shkant_v_plast")
                else "owner_body")
    if affected_body is None and any(body_key in job for job in jobs):
        if hole_creator is None or not all(job.get(body_key) for job in jobs):
            raise ValueError("Не для всех отверстий определено единственное целевое тело.")
        groups = {}
        for job in jobs:
            groups.setdefault((job[body_key], id(job.get("sketch"))), []).append(job)
        return sum(create_hole_batch(
            inventor, group, points_key, settings_key, default_diameter, default_depth,
            default_name, label, success_key=success_key, strict=strict,
            hole_creator=hole_creator, affected_body=body,
        ) for (body, _), group in groups.items())
    settings = stiajka_hole(settings_key)
    add_holes = hole_creator if hole_creator is not None else inventor.add_holes
    body_options = {"affected_body": affected_body} if affected_body is not None else {}
    started = perf_counter()
    raw_points = (point for job in jobs for point in job[points_key])
    points = (hole_creator.prepare_points(raw_points) if isinstance(hole_creator, TimedHoleBuilder)
              else inventor.unique_points(raw_points))
    if not points:
        return 0
    try:
        add_holes(
            points,
            diameter=settings.get("diameter", default_diameter),
            depth=settings.get("depth", default_depth),
            direction=stiajka_direction(settings),
            name=settings.get("feature_name", default_name),
            **body_options,
        )
        if success_key:
            for job in jobs:
                job[success_key] = True
        print(f"  created {label} batch, points={len(points)}")
        log_elapsed(f"{label} batch elapsed", started)
        return 1
    except Exception as exc:
        if isinstance(exc, AffectedBodyError):
            raise
        print(f"  {label} batch failed:", exc)
        if len(jobs) == 1:
            log_elapsed(f"{label} elapsed", started)
            if strict:
                raise RuntimeError(f"Не созданы отверстия {label}: {exc}") from exc
            return 0
    created = 0
    errors = []
    for job in jobs:
        try:
            add_holes(
                job[points_key],
                diameter=settings.get("diameter", default_diameter),
                depth=settings.get("depth", default_depth),
                direction=stiajka_direction(settings),
                name=settings.get("feature_name", default_name),
                **body_options,
            )
            if success_key:
                job[success_key] = True
            created += 1
            print(f"  created {label}")
        except Exception as exc:
            if isinstance(exc, AffectedBodyError):
                raise
            print(f"  {label} failed:", exc)
            errors.append(str(exc))
    log_elapsed(f"{label} fallback elapsed", started)
    if strict and errors:
        raise RuntimeError(f"Не созданы отверстия {label}: " + "; ".join(errors))
    return created


def create_stiajka_features(
    inventor, sketches=None, colored_faces=None, update_document=True,
    point_jobs=None, strict=False,
    hole_creator=None,
):
    if sketches is None:
        sketches = inventor.sketches_by_prefix(DRILLING_SKETCH_PREFIX)
    if colored_faces is None:
        colored_faces = inventor.colored_faces("blue")
    created = 0
    print("Stiajka sketches found:", len(sketches))
    all_axis_jobs = list(point_jobs) if point_jobs is not None else []
    for sketch in sketches:
        if point_jobs is not None:
            inventor.try_share_sketch(sketch)
            continue
        print("Sketch:", sketch.Name)
        inventor.try_share_sketch(sketch)
        sketch_colored_faces = faces_on_sketch_plane(inventor, sketch, colored_faces)
        print("  colored faces on sketch plane:", len(sketch_colored_faces))
        face_bounds = _confirmat.face_bounds_cache(inventor, sketch, sketch_colored_faces)
        axes = _confirmat.construction_axes_data(
            inventor, sketch, _confirmat.sketch_points_data(sketch, inventor), face_bounds or None
        )
        print("  construction axes:", len(axes))
        for axis in axes:
            axis_colored_face = colored_face_for_axis(inventor, sketch, axis, sketch_colored_faces)
            if axis_colored_face is None:
                try:
                    axis_colored_face = sketch.PlanarEntity
                    print("  axis colored face not found, using sketch plane")
                except Exception:
                    pass
            outer_points, inner_points = axis_stiajka_points(axis)
            outer_points = inventor.unique_points(outer_points)
            inner_points = inventor.unique_points(inner_points)
            if len(outer_points) != 2 or len(inner_points) != 2:
                continue
            all_axis_jobs.append(
                {
                    "colored_face": axis_colored_face,
                    "outer_points": outer_points,
                    "inner_points": inner_points,
                    "outer_main_created": False,
                }
            )
    if strict and not all_axis_jobs:
        raise RuntimeError("В новых эскизах не найдены точки присадки стяжки.")
    if all_axis_jobs:
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "outer_points",
            "Otv_stijki_v_torec",
            "8 mm",
            "34 mm",
            "Stiajka outer 8x34",
            "outer 8x34",
            success_key="outer_main_created",
            strict=strict,
            hole_creator=hole_creator,
        )
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "outer_points",
            "Otv_stijki_v_bokoviny",
            "5 mm",
            "13 mm",
            "Stiajka outer 5x13",
            "outer 5x13",
            strict=strict,
            hole_creator=hole_creator,
        )
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "inner_points",
            "shkant_v_plast",
            "8 mm",
            "10 mm",
            "Shkant 8x10",
            "inner 8x10",
            strict=strict,
            hole_creator=hole_creator,
        )
        created += create_hole_batch(
            inventor,
            all_axis_jobs,
            "inner_points",
            "shkant_v_torets",
            "8 mm",
            "20 mm",
            "Shkant 8x20",
            "inner 8x20",
            strict=strict,
            hole_creator=hole_creator,
        )
    if update_document:
        inventor.update()
    else:
        print("  document update skipped")
    return created


def create_second_face_stiajka_holes(inventor, outer_points, hole_settings, hole_creator=None):
    if not outer_points:
        return 0
    add_holes = hole_creator if hole_creator is not None else inventor.add_holes
    add_holes(outer_points, **hole_settings)
    return 1
