"""Кэш COM-объектов и параметров на время запуска конфирмата."""
from common.runtime_service import RuntimeService
from stiajka.parameters import ParameterSession


class ConfirmatRuntime(RuntimeService):
    def __init__(self, inventor):
        super().__init__(inventor)
        self.parameter_session = ParameterSession(inventor)

    def parameter(self, name):
        return self.parameter_session.parameter(name)

    def parameter_value(self, name, default=None):
        return self.parameter_session.parameter_value(name, default)

    def parameter_expression(self, name, default=""):
        parameter = self.parameter(name)
        return parameter.Expression if parameter is not None else default

    def missing_parameters(self, names):
        return self.parameter_session.missing_parameters(names)

    def ensure_keep_parameter(self, name, names):
        return self.parameter_session.ensure_keep_parameter(name, names)
