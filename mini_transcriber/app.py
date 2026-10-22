"""Small native desktop window; worker threads never access Tk widgets."""

from __future__ import annotations

import os
from pathlib import Path
from queue import Empty, Full, Queue
import subprocess
import sys
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .core import Cancelled, transcribe


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.source: Path | None = None
        self.result: Path | None = None
        self.busy = False
        self.closing = False
        self.cancel = Event()
        self.events: Queue = Queue()
        self.progress_events: Queue = Queue(maxsize=1)
        root.title("Mini Transcriber")
        root.geometry("600x390")
        root.minsize(580, 390)
        root.protocol("WM_DELETE_WINDOW", self.close)

        # Quiet, native Windows controls; a single left-aligned vertical flow.
        panel = ttk.Frame(root, padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Из записи — в текст", font=("Segoe UI", 19, "bold")).pack(anchor="w")
        ttk.Label(panel, text="Русская речь · Аудио и видео · Локально на компьютере").pack(anchor="w", pady=(6, 18))
        self.pick = ttk.Button(panel, text="Выбрать файл…", command=self.choose)
        self.pick.pack(anchor="w")
        self.filename = ttk.Label(panel, text="Файл не выбран", wraplength=510)
        self.filename.pack(anchor="w", pady=(8, 16), fill="x")
        self.status = ttk.Label(panel, text="При первом запуске потребуется скачать модель.", wraplength=510)
        self.status.pack(anchor="w", fill="x")
        self.bar = ttk.Progressbar(panel, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=(10, 18))
        actions = ttk.Frame(panel)
        actions.pack(fill="x")
        self.start_button = ttk.Button(actions, text="Расшифровать", command=self.start, state="disabled")
        self.start_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Отменить", command=self.request_cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.open_button = ttk.Button(actions, text="Открыть текст", command=self.open_result, state="disabled")
        self.open_button.pack(side="right")
        ttk.Label(panel, text="TXT сохранится рядом с записью. Готовые файлы не перезаписываются.", wraplength=510).pack(anchor="w", pady=(16, 0))
        root.after(100, self.poll)

    def choose(self):
        filename = filedialog.askopenfilename(
            title="Выберите аудио или видео",
            filetypes=[("Аудио и видео", "*.wav *.mp3 *.ogg *.opus *.m4a *.aac *.flac *.mp4 *.mkv *.mov *.webm *.avi *.wma"), ("Все файлы", "*.*")],
        )
        if filename:
            self.source = Path(filename)
            self.filename.configure(text=str(self.source))
            self.start_button.configure(state="normal")
            self.result = None
            self.open_button.configure(state="disabled")
            self.bar["value"] = 0
            self.status.configure(text="Готово к распознаванию.")

    def start(self):
        if self.busy or self.source is None:
            return
        self.busy = True
        self.result = None
        self.cancel.clear()
        self.pick.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        Thread(target=self.work, args=(self.source,), daemon=True).start()

    def work(self, source):
        # Coalesce frequent download updates: at most one progress event in flight.
        def report(progress):
            try:
                self.progress_events.put_nowait(progress)
            except Full:
                pass
        try:
            result = transcribe(source, report, self.cancel)
            self.events.put(("done", result))
        except Cancelled:
            self.events.put(("cancelled", None))
        except Exception as error:
            self.events.put(("error", str(error)))

    def poll(self):
        try:
            progress = self.progress_events.get_nowait()
        except Empty:
            progress = None
        if progress is not None:
            if not self.cancel.is_set():
                self.status.configure(text=progress.message)
                self.bar.stop()
                if progress.percent is None:
                    self.bar.configure(mode="indeterminate")
                    self.bar.start(12)
                else:
                    self.bar.configure(mode="determinate", value=progress.percent)
        try:
            kind, value = self.events.get_nowait()
        except Empty:
            pass
        else:
            while not self.progress_events.empty():
                self.progress_events.get_nowait()
            self.busy = False
            self.bar.stop()
            self.bar.configure(mode="determinate", value=100 if kind == "done" else 0)
            self.pick.configure(state="normal")
            self.start_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            if self.closing:
                self.root.destroy()
                return
            if kind == "done":
                self.result = value
                self.status.configure(text=f"Сохранено: {value.name}")
                self.open_button.configure(state="normal")
            elif kind == "cancelled":
                self.status.configure(text="Отменено. Результат не сохранён.")
            else:
                self.status.configure(text="Не удалось расшифровать запись.")
                messagebox.showerror("Не удалось расшифровать", str(value), parent=self.root)
        self.root.after(100, self.poll)

    def request_cancel(self):
        self.cancel.set()
        self.cancel_button.configure(state="disabled")
        self.status.configure(text="Отмена… Ожидание завершения текущего фрагмента или сетевого запроса.")

    def close(self):
        if not self.busy:
            self.root.destroy()
        elif not self.closing and messagebox.askyesno("Закрыть приложение?", "Отменить обработку и закрыть окно?", parent=self.root):
            self.closing = True
            self.request_cancel()

    def open_result(self):
        if self.result is None:
            return
        try:
            if sys.platform == "win32":
                os.startfile(str(self.result))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(self.result)])
        except OSError as error:
            messagebox.showerror("Не удалось открыть текст", str(error), parent=self.root)


def main():
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
