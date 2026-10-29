"""Кэш объектов и значений параметров только на время одного запуска 05."""
import re

from common.inventor_service_path import ensure_inventor_service_path

ensure_inventor_service_path()
from inventor_service.config import resolve_parameter_expression, resolve_parameter_name
from inventor_service.settings import service_settings


class ParameterSession:
    def __init__(self, inventor):
        self.inventor = inventor
        self.parameters = inventor.parameters
        self.config = service_settings()
        self.objects = {}
        self.values = {}

    def remember(self, name, parameter):
        self.objects[name] = parameter

    def parameter(self, name):
        name = resolve_parameter_name(name, self.config)
        if name not in self.objects:
            try:
                self.objects[name] = self.parameters.Item(name)
            except Exception:
                self.objects[name] = None
        return self.objects[name]

    def missing_parameters(self, names):
        return [name for name in names if self.parameter(name) is None]

    def parameter_value(self, name, default=None):
        resolved = resolve_parameter_name(name, self.config)
        if resolved not in self.values:
            parameter = self.parameter(name)
            if parameter is None:
                return default
            try:
                self.values[resolved] = parameter.Value
            except Exception:
                return default
        return self.values[resolved]

    def ensure_keep_parameter(self, name, referenced_names):
        expression = " + ".join(f"{param} * 0" for param in referenced_names) or "0"
        expression = resolve_parameter_expression(expression, self.config)
        resolved = resolve_parameter_name(name, self.config)
        parameter = self.parameter(name)
        if parameter is None:
            parameter = self.parameters.UserParameters.AddByExpression(resolved, expression, "mm")
            self.remember(resolved, parameter)
            return True
        # Не вызывать пересчёт Inventor записью уже установленной формулы.
        if re.sub(r"\s+", "", parameter.Expression) == re.sub(r"\s+", "", expression):
            return False
        parameter.Expression = expression
        self.values.pop(resolved, None)
        return True

    def show_message(self, *args, **kwargs):
        show = getattr(self.inventor, "show_message", None)
        if show is not None:
            show(*args, **kwargs)
