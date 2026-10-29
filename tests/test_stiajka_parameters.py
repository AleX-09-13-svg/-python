import contextlib
import io
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, PropertyMock, patch, call

from stiajka.parameter_dialog import frame_edge_offset_parameter_options, choose_frame_edge_offset_parameter
from stiajka.parameters import ParameterSession


class ParameterTests(unittest.TestCase):
    def setUp(self):
        self.inventor = Mock()
        self.config = {"linked_parameters": [{"name": "offset_alias", "source_name": "offset"}]}
        config_patch = patch("stiajka.parameters.service_settings", return_value=self.config)
        config_patch.start()
        self.addCleanup(config_patch.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def test_alias_check_and_repeated_value_read_use_one_com_lookup(self):
        parameter = Mock()
        value = PropertyMock(return_value=3.4)
        type(parameter).Value = value
        self.inventor.parameters.Item.return_value = parameter
        session = ParameterSession(self.inventor)
        self.assertEqual(session.missing_parameters(["offset_alias", "offset"]), [])
        self.assertEqual(session.parameter_value("offset_alias"), 3.4)
        self.assertEqual(session.parameter_value("offset"), 3.4)
        self.inventor.parameters.Item.assert_called_once_with("offset")
        value.assert_called_once()

    def test_parameters_read_for_options_are_reused_for_validation(self):
        parameter = NS(Name="Отступ_каркаса", Value=2.0)
        self.inventor.user_parameters = NS(Count=1, Item=Mock(return_value=parameter))
        session = ParameterSession(self.inventor)
        options = frame_edge_offset_parameter_options(self.inventor, parameter_cache=session)
        self.assertIn(parameter.Name, options)
        self.assertEqual(session.missing_parameters([parameter.Name]), [])
        self.assertEqual(session.parameter_value(parameter.Name), 2.0)
        self.inventor.parameters.Item.assert_not_called()

    def test_initial_options_do_not_access_model_parameter_collection(self):
        class Inventor:
            user_parameters = NS(Count=0)

            @property
            def model_parameters(self):
                raise AssertionError("Model parameters must only load on request")

        self.assertTrue(frame_edge_offset_parameter_options(Inventor()))

    def test_model_parameters_are_available_when_requested(self):
        user = NS(Name="Отступ_пользовательский")
        model = NS(Name="Отступ_модели")
        self.inventor.user_parameters = NS(Count=1, Item=lambda i: user)
        self.inventor.model_parameters = NS(Count=1, Item=Mock(return_value=model))
        options = frame_edge_offset_parameter_options(self.inventor, include_model=True)
        self.assertIn(user.Name, options)
        self.assertIn(model.Name, options)
        self.inventor.model_parameters.Item.assert_called_once_with(1)

    def test_missing_parameter_is_probed_once_per_session(self):
        self.inventor.parameters.Item.side_effect = KeyError("missing")
        session = ParameterSession(self.inventor)
        self.assertEqual(session.missing_parameters(["missing"]), ["missing"])
        self.assertEqual(session.parameter_value("missing", 10), 10)
        self.inventor.parameters.Item.assert_called_once_with("missing")

    def test_unchanged_keep_expression_is_not_written(self):
        parameter = Mock()
        expression = PropertyMock(return_value="offset*0 + other * 0")
        type(parameter).Expression = expression
        self.inventor.parameters.Item.return_value = parameter
        session = ParameterSession(self.inventor)
        self.assertFalse(session.ensure_keep_parameter("Keep_Excel_Params", ["offset_alias", "other"]))
        self.assertEqual(expression.call_args_list, [call()])
        self.inventor.parameters.UserParameters.AddByExpression.assert_not_called()

    def test_changed_keep_expression_is_written_and_new_parameter_is_not_created(self):
        parameter = Mock()
        expression = PropertyMock(return_value="old * 0")
        type(parameter).Expression = expression
        self.inventor.parameters.Item.return_value = parameter
        session = ParameterSession(self.inventor)
        self.assertTrue(session.ensure_keep_parameter("Keep_Excel_Params", ["offset_alias"]))
        self.assertEqual(expression.call_args_list[-1], call("offset * 0"))
        self.inventor.parameters.UserParameters.AddByExpression.assert_not_called()

    def test_missing_keep_parameter_is_created_with_same_units_and_cached(self):
        self.inventor.parameters.Item.side_effect = KeyError("missing")
        session = ParameterSession(self.inventor)
        self.assertTrue(session.ensure_keep_parameter("Keep_Excel_Params", ["offset_alias"]))
        self.inventor.parameters.UserParameters.AddByExpression.assert_called_once_with(
            "Keep_Excel_Params", "offset * 0", "mm",
        )
        self.assertIs(session.parameter("Keep_Excel_Params"),
                      self.inventor.parameters.UserParameters.AddByExpression.return_value)

    def test_cache_does_not_survive_a_new_run(self):
        self.inventor.parameters.Item.return_value = NS(Value=2.0)
        self.assertEqual(ParameterSession(self.inventor).parameter_value("offset"), 2.0)
        self.inventor.parameters.Item.return_value = NS(Value=5.0)
        self.assertEqual(ParameterSession(self.inventor).parameter_value("offset"), 5.0)
        self.assertEqual(self.inventor.parameters.Item.call_count, 2)

    def test_dialog_loads_model_parameters_only_on_button_and_preserves_selection(self):
        user = NS(Name="Отступ_пользовательский")
        model = NS(Name="Отступ_модели")
        self.inventor.user_parameters = NS(Count=1, Item=lambda i: user)
        model_collection = NS(Count=1, Item=Mock(return_value=model))
        model_property = PropertyMock(return_value=model_collection)
        type(self.inventor).model_parameters = model_property
        root, combo = Mock(), Mock()
        buttons = {}
        selected_value = {"value": ""}

        def string_var(value):
            selected_value["value"] = value
            return NS(get=lambda: selected_value["value"])

        def button(parent, text, command):
            widget = Mock()
            buttons[text] = (command, widget)
            return widget

        def interact():
            model_property.assert_not_called()
            selected_value["value"] = user.Name
            buttons["Загрузить параметры модели"][0]()
            self.assertIn(model.Name, combo.config.call_args.kwargs["values"])
            self.assertEqual(selected_value["value"], user.Name)
            buttons["OK"][0]()

        root.mainloop.side_effect = interact
        with patch("stiajka.parameter_dialog.tk.Tk", return_value=root), \
             patch("stiajka.parameter_dialog.tk.StringVar", side_effect=string_var), \
             patch("stiajka.parameter_dialog.ttk.Frame"), \
             patch("stiajka.parameter_dialog.ttk.Label"), \
             patch("stiajka.parameter_dialog.ttk.Combobox", return_value=combo), \
             patch("stiajka.parameter_dialog.ttk.Button", side_effect=button):
            result = choose_frame_edge_offset_parameter(self.inventor)
        self.assertEqual(result, user.Name)
        model_property.assert_called_once()
        buttons["Загрузить параметры модели"][1].config.assert_called_once_with(state="disabled")


if __name__ == "__main__":
    unittest.main()
