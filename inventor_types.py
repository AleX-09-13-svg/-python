from typing import Iterator, Protocol


class Point2d(Protocol):
    X: float
    Y: float


class Point3d(Protocol):
    X: float
    Y: float
    Z: float


class TransientGeometry(Protocol):
    def CreatePoint2d(self, x: float, y: float) -> Point2d: ...


class ObjectCollection(Protocol):
    Count: int

    def Add(self, obj: object) -> None: ...
    def Clear(self) -> None: ...
    def Item(self, index: int) -> object: ...


class TransientObjects(Protocol):
    def CreateObjectCollection(self) -> ObjectCollection: ...
    def CreateColor(self, red: int, green: int, blue: int) -> object: ...


class Vertex(Protocol):
    Point: Point3d  # 3D-точка вершины.
    Edges: object  # Ребра, соединенные с вершиной.
    Faces: object  # Грани, соединенные с вершиной.
    Parent: object  # Родительское тело SurfaceBody.
    Type: int  # Внутренний тип объекта Inventor.
    TransientKey: int  # Временный ключ объекта.
    AttributeSets: object  # Пользовательские атрибуты объекта.
    AssociativeID: int  # Ассоциативный идентификатор.
    IsTolerant: bool  # Является ли вершина tolerant-вершиной.
    Tolerance: float  # Допуск вершины.
    Application: object  # Сылка на приложение Inventor.

    def GetPoint(self, point: object) -> None: ...  # Получить координаты вершины.
    def GetReferenceKey(
        self, reference_key: object, key_context: int = 0
    ) -> None: ...  # Получить устойчивый ключ ссылки на объект.
    def GetSourceVertex(
        self, get_leaf_source: bool = True
    ) -> "Vertex": ...  # Получить исходную вершину для override-геометрии.


class Vertices(Protocol):  # набор вершин грани
    Count: int  # Количество вершин в коллекции.
    Type: int  # Внутренний тип объекта Inventor.

    def Item(
        self, index: int
    ) -> Vertex: ...  # Получить вершину по индексу Inventor, обычно с 1.
    def __call__(self, index: int) -> Vertex: ...  # То же, что Item(index).
    def __iter__(self) -> Iterator[Vertex]: ...  # Перебор вершин через for.
    def __len__(self) -> int: ...  # Позволяет использовать len(vertices).


class Face(Protocol):
    Vertices: Vertices  # Вершины грани.
    Edges: object  # Ребра грани.
    EdgeLoops: object  # Замкнутые контуры ребер грани.
    PointOnFace: Point3d  # Точка, которая точно лежит на грани.
    SurfaceType: int  # Тип поверхности: плоскость, цилиндр, конус и т.д.
    Geometry: object  # Геометрическое описание поверхности.
    Evaluator: object  # Объект для геометрических вычислений по поверхности.


class SelectSet(Protocol):
    Count: int

    def Item(self, index: int) -> Face: ...
    def Clear(self) -> None: ...
    def Select(self, obj: object) -> None: ...


class SketchPoint(Protocol):
    HoleCenter: bool


class SketchPoints(Protocol):
    def Add(self, point: Point2d, hole_center: bool) -> SketchPoint: ...


class Sketch(Protocol):
    Name: str
    SketchPoints: SketchPoints

    def ModelToSketchSpace(self, point: Point3d) -> Point2d: ...
    def Solve(self) -> None: ...


class Sketches(Protocol):
    def Add(self, face: Face) -> Sketch: ...


class HolePlacementDefinition(Protocol):
    pass


class HoleFeature(Protocol):
    Name: str


class HoleFeatures(Protocol):
    def CreateSketchPlacementDefinition(
        self,
        sketch_points: ObjectCollection,
    ) -> HolePlacementDefinition: ...

    def AddDrilledByDistanceExtent(
        self,
        placement: HolePlacementDefinition,
        diameter: str,
        depth: str,
        direction: int,
        flat_bottom: bool,
    ) -> HoleFeature: ...


class Features(Protocol):
    HoleFeatures: HoleFeatures


class ComponentDefinition(Protocol):
    Sketches: Sketches
    Features: Features


class PartDocument(Protocol):
    DisplayName: str
    FullFileName: str
    ComponentDefinition: ComponentDefinition
    SelectSet: SelectSet

    def Save(self) -> None: ...
    def SaveAs(self, file_name: str, save_copy_as: bool) -> None: ...
    def Update(self) -> None: ...


class Documents(Protocol):
    Count: int

    def Add(
        self,
        document_type: int,
        template_file_name: str = "",
        create_visible: bool = True,
    ) -> object: ...
    def CloseAll(self, unreferenced_only: bool = False) -> None: ...
    def Item(self, index_or_name: object) -> object: ...
    def Open(self, full_document_name: str, open_visible: bool = True) -> object: ...


class CommandManager(Protocol):
    def Pick(self, selection_filter: int, prompt_text: str = "") -> object: ...


class Transaction(Protocol):
    def Abort(self) -> None: ...
    def End(self) -> None: ...


class TransactionManager(Protocol):
    def StartTransaction(self, document: object, display_name: str) -> Transaction: ...


class InventorApplication(Protocol):
    @property
    def ActiveDocument(self) -> PartDocument: ...

    @property
    def Caption(self) -> str: ...

    @property
    def CommandManager(self) -> CommandManager: ...

    @property
    def Documents(self) -> Documents: ...

    @property
    def SilentOperation(self) -> bool: ...

    @SilentOperation.setter
    def SilentOperation(self, value: bool) -> None: ...

    @property
    def TransientGeometry(self) -> TransientGeometry: ...

    @property
    def TransientObjects(self) -> TransientObjects: ...

    @property
    def TransactionManager(self) -> TransactionManager: ...

    @property
    def Visible(self) -> bool: ...

    @Visible.setter
    def Visible(self, value: bool) -> None: ...

    def Quit(self) -> None: ...
