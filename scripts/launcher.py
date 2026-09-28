from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

COMMANDS = {
    "sketches": {
        "title": "Create sketches",
        "script": "00_createSketches.py",
    },
    "stiajka": {
        "title": "Stiajka 2pcs",
        "script": "04_stiajka_2\u0448\u0442.py",
    },
    "confirmat2": {
        "title": "Confirmat 2pcs Bok16",
        "script": "02_confirmat_2\u0448\u0442_Bok16.py",
    },
    "confirmat3": {
        "title": "Confirmat 3pcs Bok16",
        "script": "03_confirmat_3\u0448\u0442_Bok16.py",
    },
    "confirmat2_bok16": {
        "title": "Confirmat 2pcs Bok16",
        "script": "02_confirmat_2\u0448\u0442_Bok16.py",
    },
    "confirmat3_bok16": {
        "title": "Confirmat 3pcs Bok16",
        "script": "03_confirmat_3\u0448\u0442_Bok16.py",
    },
    "confirmat2_bok17": {
        "title": "Confirmat 2pcs Bok17",
        "script": "22_confirmat_2\u0448\u0442_Bok17.py",
    },
    "confirmat3_bok17": {
        "title": "Confirmat 3pcs Bok17",
        "script": "33_confirmat_3\u0448\u0442_Bok17.py",
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
