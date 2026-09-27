from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

COMMANDS = {
    "sketches": {
        "title": "Создать эскизы",
        "script": "00_createSketches.py",
    },
    "confirmat3": {
        "title": "Конфирмат 3",
        "script": "03_confirmat_3штКаркас_на_Красн.py",
    },
    "confirmat2": {
        "title": "Конфирмат 2",
        "script": "02_confirmat_2штКаркас_на_Жел.py",
    },
    "stiajka_frame": {
        "title": "Стяжка каркас",
        "script": "01_stiajkaКаркас_на_Зел.py",
    },
    "stiajka_drawer": {
        "title": "Стяжка ящик",
        "script": "01_stiajkaЯщик_на_Син.py",
    },
}


def print_commands() -> None:
    print("Available commands:")
    for name, command in COMMANDS.items():
        print(f"  {name:<14} {command['title']} -> {command['script']}")


def run_command(name: str) -> int:
    command = COMMANDS.get(name)
    if command is None:
        print(f"Unknown command: {name}")
        print_commands()
        return 2

    script_path = PROJECT_ROOT / command["script"]
    if not script_path.exists():
        print(f"Script not found: {script_path}")
        return 2

    print(f"Running: {command['title']}")
    print(f"Script: {script_path}")
    print()

    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
    )
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Launcher for Inventor furniture drilling scripts.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        help="Command name. Use --list to show available commands.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Show available commands.",
    )
    args = parser.parse_args()

    if args.list or not args.command:
        print_commands()
        return 0

    return run_command(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
