import json
from functools import lru_cache
from pathlib import Path


SETTINGS_PATH = Path(__file__).resolve().parent.parent / "settings.json"
DEFAULT_HOLE_DIRECTIONS = {
    "positive": 20993,
    "negative": 20994,
}
DEFAULT_DIMENSION_ORIENTATIONS = {
    "horizontal": 19201,
    "vertical": 19202,
    "aligned": 19203,
}
DEFAULT_DRAWER_EDGE_MAX_CM = 60.0


@lru_cache(maxsize=1)
def load_settings():
    with SETTINGS_PATH.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def setting(*keys, default=None):
    value = load_settings()

    for key in keys:
        try:
            value = value[key]
        except (KeyError, TypeError):
            return default

    return value


def hole_direction(name):
    return setting(
        "inventor_api",
        "hole_direction",
        name,
        default=DEFAULT_HOLE_DIRECTIONS.get(name),
    )


def dimension_orientation(name):
    return setting(
        "inventor_api",
        "dimension_orientation",
        name,
        default=DEFAULT_DIMENSION_ORIENTATIONS.get(name),
    )


def drawer_edge_max_cm():
    return setting(
        "drilling",
        "drawer_edge_max_cm",
        default=DEFAULT_DRAWER_EDGE_MAX_CM,
    )
