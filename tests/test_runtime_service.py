import unittest
from unittest.mock import Mock, PropertyMock, call

from common.runtime_service import RuntimeService


class RuntimeServiceTests(unittest.TestCase):
    def test_factories_are_read_once_and_collections_are_created_separately(self):
        inventor, geometry, objects = Mock(), Mock(), Mock()
        geometry_property = PropertyMock(return_value=geometry)
        objects_property = PropertyMock(return_value=objects)
        type(inventor).transient_geometry = geometry_property
        type(inventor).transient_objects = objects_property
        collections = [Mock(), Mock()]
        objects.CreateObjectCollection.side_effect = collections
        runtime = RuntimeService(inventor)
        runtime.create_point2d(1, 2)
        runtime.create_point2d(3, 4)
        runtime.create_point3d(5, 6, 7)
        self.assertEqual(geometry.CreatePoint2d.call_args_list, [call(1, 2), call(3, 4)])
        geometry.CreatePoint.assert_called_once_with(5, 6, 7)
        first, second = object(), object()
        self.assertIs(runtime.object_collection([first]), collections[0])
        self.assertIs(runtime.object_collection([second]), collections[1])
        collections[0].Add.assert_called_once_with(first)
        collections[1].Add.assert_called_once_with(second)
        geometry_property.assert_called_once()
        objects_property.assert_called_once()

    def test_other_operations_delegate_to_original_service(self):
        inventor = Mock()
        runtime = RuntimeService(inventor)
        runtime.update()
        inventor.update.assert_called_once()
