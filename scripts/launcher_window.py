from __future__ import annotations

import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter.scrolledtext import ScrolledText


PROJECT_ROOT = Path(__file__).resolve().parent.parent

COMMANDS = {
    "sketches": ("Создать эскизы", "00_createSketches.py"),
    "confirmat3": ("Конфирмат 3", "03_confirmat_3штКаркас_на_Красн.py"),
    "confirmat2": ("Конфирмат 2", "02_confirmat_2штКаркас_на_Жел.py"),
    "stiajka_frame": ("Стяжка каркас", "01_stiajkaКаркас_на_Зел.py"),
    "stiajka_drawer": ("Стяжка ящик", "01_stiajkaЯщик_на_Син.py"),
}


class LauncherWindow:
    def __init__(self, command_name: str):
        self.command_name = command_name
        self.output_queue: queue.Queue[str | None] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None

        self.root = tk.Tk()
        self.root.title("Inventor scripts")
        self.root.geometry("520x220+20+20")
        self.root.minsize(420, 160)

        self.text = ScrolledText(self.root, wrap=tk.WORD, font=("Consolas", 9))
        self.text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))

        self.close_button = tk.Button(
            self.root,
            text="Закрыть",
            command=self.root.destroy,
            state=tk.DISABLED,
        )
        self.close_button.pack(anchor=tk.E, padx=8, pady=(0, 8))

    def write(self, text: str) -> None:
        self.text.insert(tk.END, text)
        self.text.see(tk.END)

    def start(self) -> None:
        threading.Thread(target=self.run_command, daemon=True).start()
        self.root.after(100, self.poll_output)
        self.root.mainloop()

    def run_command(self) -> None:
        command = COMMANDS.get(self.command_name)
        if command is None:
            self.output_queue.put(f"Unknown command: {self.command_name}\n")
            self.output_queue.put(None)
            return

        title, script_name = command
        script_path = PROJECT_ROOT / script_name
        if not script_path.exists():
            self.output_queue.put(f"Script not found:\n{script_path}\n")
            self.output_queue.put(None)
            return

        self.output_queue.put(f"Running: {title}\n")
        self.output_queue.put(f"Script: {script_path}\n\n")

        self.process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        assert self.process.stdout is not None
        for line in self.process.stdout:
            self.output_queue.put(line)

        return_code = self.process.wait()
        self.output_queue.put(f"\nFinished with code {return_code}\n")
        self.output_queue.put(None)

    def poll_output(self) -> None:
        while True:
            try:
                item = self.output_queue.get_nowait()
            except queue.Empty:
                break

            if item is None:
                self.close_button.config(state=tk.NORMAL)
                return

            self.write(item)

        self.root.after(100, self.poll_output)


def main() -> int:
    command_name = sys.argv[1] if len(sys.argv) > 1 else "sketches"
    LauncherWindow(command_name).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
