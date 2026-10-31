# Стяжки — iLogic

Добавьте полный путь к этой папке в «Сервис → Параметры → Конфигурация iLogic →
Внешние папки правил». Папка `ilogic/Confirmat`, добавленная для конфирматов,
не заменяет эту настройку: для стяжек добавляется отдельная папка `ilogic/Stiajka`.

Три точки запуска:

| Правило | Раскладка |
| --- | --- |
| `Stiajka_1_inch.iLogicVb` | Одна стяжка и один шкант по центру |
| `Stiajka_2_inch.iLogicVb` | Две крайние стяжки, расстояние кратно 32 мм |
| `Stiajka_4_inch.iLogicVb` | Четыре стяжки с равномерным шагом |

Все три правила перенесены из `scripts/Создание присадки`: замените пути в
браузере внешних правил или в своих правилах запуска. Запускайте `.iLogicVb`
как обычные правила iLogic, без включения Straight VB code для главного правила.
Файлы `.vb` подключаются через `AddVbFile` как Straight VB code; отдельно их
запускать не нужно. При переносе копируйте всю папку.

## Модули

| Файл | Назначение |
| --- | --- |
| `StiajkaContext.vb` | Общие поля, PairJob, Projection, ошибки, имена и журнал |
| `StiajkaConfig.vb` | JSON, сопоставление имён параметров, выражения Keep |
| `StiajkaSelection.vb` | Выбор пар граней, общее ребро, поиск соседнего тела |
| `StiajkaSketches.vb` | Общие операции с эскизами и геометрией |
| `StiajkaHoles.vb` | Пакеты отверстий, чашки и затрагиваемые тела |
| `StiajkaDialog.vb` | Выбор отступа для вариантов 2 и 4 |
| `Stiajka_1_Layout.vb` | Раскладка, размеры и проверки для одной стяжки |
| `Stiajka_2_Layout.vb` | Раскладка, размеры и проверки для двух стяжек |
| `Stiajka_4_Layout.vb` | Раскладка, размеры и проверки для четырёх стяжек |

Модули — части одного класса `ThisRule` (`Partial Public Class ThisRule`).
Каждое главное правило подключает общие части и только свой файл раскладки;
остальные варианты не компилируются вместе с ним. Заголовки окон, имена эскизов,
порядок построения и имена журналов сохранены.

Общий `PairJob.FirstAxisDirection` используется только вариантом 1.
Константы `Prefix`, `TieCount` и подписи окна находятся в соответствующих
главных правилах. Константа `ProjectRoot` — в `StiajkaContext.vb`.

Настройки читаются из прежнего JSON библиотеки
`../01_inventor_service/service/excel_parameters/part_config.example.json`
относительно корня Python-проекта. Необязательный `settings.json` из корня
проекта читается первым; библиотечный JSON имеет приоритет. Python не запускается.

## Проверка

Из корня проекта:

```powershell
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_1_inch.iLogicVb" --smoke
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_2_inch.iLogicVb" --smoke
python -X utf8 -B scripts/validate_ilogic_native.py --rule "ilogic/Stiajka/Stiajka_4_inch.iLogicVb" --smoke
```

Проверка компилирует все подключённые файлы против API установленного Inventor
2023 и проверяет настройки и расчёты без запуска модели. Поиск файлов средствами
самого iLogic и построение отверстий проверяются отдельно в Inventor.

Подробности: [одна стяжка](../../docs/stiajka_1_ilogic.md),
[две стяжки](../../docs/05_stiajka_ilogic.md),
[четыре стяжки](../../docs/stiajka_4_ilogic.md).
