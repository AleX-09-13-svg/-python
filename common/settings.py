import json
from functools import lru_cache
from pathlib import Path

from common.inventor_service_path import ensure_inventor_service_path


SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"
LIBRARY_SETTINGS_PATH = (
    Path(__file__).resolve().parents[2]
    / "01_inventor_service"
    / "service"
    / "infa"
    / "part_config.example.json"
)
DEFAULT_DRAWER_EDGE_MAX_CM = 60.0


@lru_cache(maxsize=1)
def load_settings():
    local_settings = load_local_settings()

    if LIBRARY_SETTINGS_PATH.exists():
        with LIBRARY_SETTINGS_PATH.open("r", encoding="utf-8-sig") as file:
            library_settings = resolve_library_parameter_names(json.load(file))
        return merge_dict(local_settings, library_settings)

    return local_settings


def load_local_settings():
    if not SETTINGS_PATH.exists():
        return {}

    with SETTINGS_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def merge_dict(base, override):
    result = dict(base)

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = merge_dict(result[key], value)
        else:
            result[key] = value

    return result


def library_parameter_name_map(settings):
    result = {}
    for item in settings.get("linked_parameters", []):
        name = item.get("name")
        source_name = item.get("source_name")
        if name and source_name:
            result[name] = source_name
    return result


def resolve_library_parameter_names(settings):
    name_map = library_parameter_name_map(settings)

    def resolve(value):
        if isinstance(value, str):
            return name_map.get(value, value)
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, dict):
            return {key: resolve(item) for key, item in value.items()}
        return value

    return resolve(settings)


def setting(*keys, default=None):
    value = load_settings()

    for key in keys:
        try:
            value = value[key]
        except (KeyError, TypeError):
            return default

    return value


def hole_direction(name):
    ensure_inventor_service_path()
    from inventor_service import Inventor

    return Inventor.hole_direction(name)


def dimension_orientation(name):
    ensure_inventor_service_path()
    from inventor_service import Inventor

    return Inventor.dimension_orientation(name)


def drawer_edge_max_cm():
    return setting(
        "drilling",
        "drawer_edge_max_cm",
        default=DEFAULT_DRAWER_EDGE_MAX_CM,
    )
