"""Выберите фасад и боковину в Inventor, затем запустите скрипт."""
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from petli.petli import main


class Output:
    def __init__(self, stream, log):
        self.stream, self.log = stream, log

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
            print(f"Запуск 07. Журнал: {path}", flush=True)
            try:
                main()
            except Exception:
                traceback.print_exc()
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
