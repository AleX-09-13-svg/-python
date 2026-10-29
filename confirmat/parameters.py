# Подготовка параметров конфирмата и сохранение ссылок на параметры детали.
from common.settings import load_settings
import re
import confirmat.confirmat as confirmat_module

KEEP_EXCEL_UNITLESS_PARAMS_NAME = "Keep_Excel_Params_Unitless"


def use_material_thickness(thickness_param):
    confirmat_module.frame_thickness_param = thickness_param
    settings = load_settings()["confirmat"]
    settings["outer_2pcs"]["depth"] = thickness_param
    settings["outer_3pcs"]["depth"] = thickness_param


def is_parameter_name(value):
    if not isinstance(value, str):
        return False

    text = value.strip()
    if not text:
        return False

    if any(char.isdigit() for char in text):
        return False

    return True


def confirmat_parameter_names():
    settings = load_settings()["confirmat"]
    names = []

    for section_name in ("outer_2pcs", "inner_2pcs", "outer_3pcs", "inner_3pcs"):
        section = settings.get(section_name, {})
        for key in ("diameter", "depth"):
            value = section.get(key)
            if is_parameter_name(value):
                names.append(value)

    return tuple(dict.fromkeys(names))


def resolve_confirmat_count(inventor, count_param):
    value = inventor.parameter_value(count_param, None)
    # Выражение читать только если числовое значение не удалось распознать.
    expression = ""
    def candidates():
        nonlocal expression
        yield value
        expression = inventor.parameter_expression(count_param, "")
        yield expression

    for candidate in candidates():
        if candidate is None:
            continue

        text = str(candidate).strip().lower()
        if text.startswith("2"):
            return "2"
        if text.startswith("3"):
            return "3"

        try:
            rounded = str(int(round(float(candidate))))
        except (TypeError, ValueError):
            continue

        if rounded in ("2", "3"):
            return rounded

    print(
        "Confirmat count parameter must have value 2 or 3:",
        count_param,
        "value=",
        value,
        "expression=",
        expression,
    )
    return None


def ensure_unitless_keep_parameter(inventor, name, referenced_parameter_names):
    # Использовать реальные имена и единицы параметров детали.
    # Умножение размерного параметра на 0 не убирает его единицы.
    terms = []
    sources = []
    for parameter_name in referenced_parameter_names:
        source = inventor.parameter(parameter_name)
        source_name = source.Name
        units = str(source.Units).strip()
        sources.append(f"{source_name} [{units}]")
        if units.lower() in ("text", "boolean"):
            raise ValueError(
                f"Параметр количества должен быть числовым: {source_name} [{units}]"
            )
        if not units or units.lower() == "ul":
            terms.append(f"{source_name} * 0")
        else:
            # Деление на единицу той же размерности даёт безразмерную ссылку.
            terms.append(f"({source_name} / (1 {units})) * 0")

    expression = " + ".join(terms) or "0"
    try:
        # 11265 — UnitsTypeEnum.kUnitlessUnits в API Inventor.
        try:
            parameter = inventor.parameter(name)
        except Exception:
            parameter = None
        if parameter is None:
            parameter = inventor.ensure_user_parameter(name, expression, units=11265)
        if re.sub(r"\s+", "", parameter.Expression) != re.sub(r"\s+", "", expression):
            parameter.Expression = expression
    except Exception as exc:
        raise RuntimeError(
            f"Не удалось задать {name}: {expression}. "
            f"Исходные параметры: {', '.join(sources) or 'нет'}."
        ) from exc
    return parameter
