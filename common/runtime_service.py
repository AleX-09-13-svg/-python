"""Служебные COM-объекты Inventor в пределах одного запуска команды."""


class RuntimeService:
    def __init__(self, inventor):
        self.inventor = inventor
        self._geometry = None
        self._objects = None

    def __getattr__(self, name):
        return getattr(self.inventor, name)

    @property
    def transient_geometry(self):
        if self._geometry is None:
            self._geometry = self.inventor.transient_geometry
        return self._geometry

    @property
    def transient_objects(self):
        if self._objects is None:
            self._objects = self.inventor.transient_objects
        return self._objects

    def create_point2d(self, x, y):
        return self.transient_geometry.CreatePoint2d(x, y)

    def create_point3d(self, x, y, z):
        return self.transient_geometry.CreatePoint(x, y, z)

    def object_collection(self, objects):
        result = self.transient_objects.CreateObjectCollection()
        for obj in objects:
            result.Add(obj)
        return result
