"""Имена новых объектов в пределах одного запуска присадки."""


class NameAllocator:
    def __init__(self, collection):
        self.collection = collection
        self.reserved = set()
        self.next_index = {}

    def take(self, base):
        index = self.next_index.get(base, 0)
        while True:
            name = base if index == 0 else f"{base}_{index}"
            index += 1
            if name in self.reserved:
                continue
            try:
                self.collection.Item(name)
            except Exception:
                self.reserved.add(name)
                self.next_index[base] = index
                return name


class DrillingNames:
    def __init__(self, inventor):
        self.sketch = NameAllocator(inventor.comp.Sketches).take
        self.parameter = NameAllocator(inventor.parameters).take
