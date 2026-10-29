# Назначить один параметр длины всем выбранным отрезкам активного эскиза.
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from common.inventor_connection import get_inventor_service
from sketch.line_parameter import (
    apply_line_parameter,
    choose_length_parameter,
    length_parameters,
    selected_sketch_lines,
)


def main():
    inventor = get_inventor_service()
    document = inventor.active_document
    if int(document.DocumentType) != 12290:  # kPartDocumentObject
        raise ValueError("Откройте деталь и редактируйте её 2D-эскиз.")
    # Сохранить выбранные линии до открытия окна.
    sketch, lines, ignored = selected_sketch_lines(inventor.app, document)
    options = length_parameters(document, sketch, lines)
    if not options:
        raise ValueError("В детали нет подходящих положительных параметров длины.")
    name = choose_length_parameter(options, len(lines))
    if name is None:
        return
    print(f"Параметр: {name}. Выбрано отрезков: {len(lines)}.", flush=True)
    created, updated, errors = apply_line_parameter(inventor, document, sketch, lines, name)
    print(
        f"Завершено. Создано размеров: {created}; изменено: {updated}; "
        f"пропущено из-за ошибок: {len(errors)}.",
        flush=True,
    )
    if ignored:
        print(f"Других выбранных объектов пропущено: {ignored}.", flush=True)


class Output:
    """Писать в журнал и доступное окно лаунчера."""

    def __init__(self, stream, log):
        self.stream = stream
        self.log = log

    def write(self, text):
        self.log.write(text)
        self.log.flush()
        if self.stream is not None:
            try:
                self.stream.write(text)
                self.stream.flush()
            except (OSError, UnicodeError):
                pass
        return len(text)

    def flush(self):
        self.log.flush()


def run():
    path = Path(__file__).resolve().with_suffix(".log")
    with path.open("w", encoding="utf-8") as log:
        with redirect_stdout(Output(sys.stdout, log)), redirect_stderr(Output(sys.stderr, log)):
            print(f"Запуск 06. Журнал: {path}", flush=True)
            try:
                main()
            except Exception:
                traceback.print_exc()
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
