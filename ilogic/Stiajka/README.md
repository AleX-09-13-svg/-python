# Стяжки — iLogic

Добавьте полный путь к этой папке в «Сервис → Параметры → Конфигурация iLogic →
Внешние папки правил». Папка `ilogic/Confirmat`, добавленная для конфирматов,
не заменяет эту настройку: для стяжек добавляется отдельная папка `ilogic/Stiajka`.

Пять точек запуска:

| Правило | Раскладка |
| --- | --- |
| `Stiajka_1_inch.iLogicVb` | Пара «стяжка + шкант» симметрично вокруг середины ребра; между центрами 32 мм |
| `Stiajka_2_inch_fixCentr.iLogicVb` | Две крайние стяжки, расстояние кратно 32 мм |
| `Stiajka_2_inch_fixKrai.iLogicVb` | Две стяжки с точным отступом от каждого края, без округления пролёта |
| `Stiajka_3_inch_fixKrai.iLogicVb` | Три выбранные грани, средняя стяжка по сетке 32 мм от стороны третьей грани; четыре шканта |
| `Stiajka_4_inch_fixKrai.iLogicVb` | Четыре стяжки: крайние промежутки округлены вниз к 32 мм, средний — остаток |

Правила 1, 2 и 4 перенесены из `scripts/Создание присадки`: замените пути в
браузере внешних правил или в своих правилах запуска. Запускайте `.iLogicVb`
как обычные правила iLogic, без включения Straight VB code для главного правила.
Вспомогательные файлы находятся в подпапке `Modules`; `AddVbFile` указывает пути
`Modules\имя.vb`. В каталоги внешних правил добавляется родительская папка.
Файлы `.vb` подключаются через `AddVbFile` как Straight VB code; отдельно их
запускать не нужно. При переносе копируйте всю папку.

## Модули

| Файл | Назначение |
| --- | --- |
| `Modules/StiajkaContext.vb` | Общие поля, PairJob, Projection, ошибки, имена и журнал |
| `Modules/StiajkaConfig.vb` | Встроенные настройки, имена параметров, выражения Keep |
| `Modules/StiajkaSelection.vb` | Выбор пар граней, общее ребро, поиск соседнего тела |
| `Modules/StiajkaSketches.vb` | Общие операции с эскизами и геометрией |
| `Modules/StiajkaHoles.vb` | Пакеты отверстий, чашки и затрагиваемые тела |
| `Modules/StiajkaDialog.vb` | Выбор отступа для вариантов 2 и 4 |
| `Modules/Stiajka_1_Layout.vb` | Раскладка, размеры и проверки для одной стяжки |
| `Modules/Stiajka_2_Layout.vb` | Раскладка, размеры и проверки для двух стяжек |
| `Modules/Stiajka_2_fixKrai_Layout.vb` | Две стяжки с точными крайними отступами |
| `Modules/Stiajka_2_fixKrai_Dialog.vb` | Выбор пользовательского параметра точного отступа для двух стяжек |
| `Modules/Stiajka_3_Layout.vb` | Три стяжки, четыре шканта, три чашки и проверки пересечений |
| `Modules/Stiajka_3_Dialog.vb` | Выбор пользовательского параметра точного отступа |
| `Modules/Stiajka_3_Selection.vb` | Выбор троек граней и определение базовой стороны по третьей грани |
| `Modules/Stiajka_4_Layout.vb` | Раскладка, размеры и проверки для четырёх стяжек |

Модули — части одного класса `ThisRule` (`Partial Public Class ThisRule`).
Каждое главное правило подключает общие части и только свой файл раскладки;
остальные варианты не компилируются вместе с ним. Заголовки окон, имена эскизов,
порядок построения и имена журналов сохранены.

Общий `PairJob.FirstAxisDirection` используется только вариантом 1.
Константы `Prefix`, `TieCount` и подписи окна находятся в соответствующих
главных правилах. Константа `ProjectRoot` — в `Modules/StiajkaContext.vb`.

Правила работают без JSON и Python. Имена параметров и направления операций
заданы в `Modules/StiajkaConfig.vb`; значения размеров берутся из открытой детали.
Изменения внешнего JSON на правила не влияют. `ProjectRoot` используется для журнала.

## Проверка

Из корня проекта:

```powershell
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_1_inch.iLogicVb" --smoke
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_2_inch_fixCentr.iLogicVb" --smoke
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_2_inch_fixKrai.iLogicVb" --smoke
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_3_inch_fixKrai.iLogicVb" --smoke
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_4_inch_fixKrai.iLogicVb" --smoke
```

Проверка компилирует все подключённые файлы против API установленного Inventor
2023 и проверяет настройки и расчёты без запуска модели. Поиск файлов средствами
самого iLogic и построение отверстий проверяются отдельно в Inventor.

Подробности: [одна стяжка](../../docs/stiajka_1_ilogic.md),
[две стяжки](../../docs/05_stiajka_ilogic.md),
[три стяжки](../../docs/stiajka_3_ilogic.md),
[четыре стяжки](../../docs/stiajka_4_ilogic.md).
