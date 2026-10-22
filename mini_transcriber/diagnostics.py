"""Exercise resources that static freezing cannot reliably discover."""

import subprocess
import sys


def check_runtime() -> dict:
    import transcribe_cpp
    from .core import ffmpeg_path

    devices = transcribe_cpp.backends()
    if not any(device.device_type == "cpu" for device in devices):
        raise RuntimeError("CPU backend not found")
    ffmpeg = ffmpeg_path()
    subprocess.run(
        [ffmpeg, "-version"], check=True, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    return {"native_version": transcribe_cpp.native_version(),
            "library": str(transcribe_cpp.library_path()), "ffmpeg": ffmpeg, "cpu": True}


def self_test(audio) -> dict:
    """Run a real model, then create and close the real GUI on the main thread."""
    from pathlib import Path
    import shutil
    import tempfile
    from threading import Event
    import tkinter as tk

    from .app import App
    from .core import transcribe

    result = check_runtime()
    with tempfile.TemporaryDirectory(prefix="mini-smoke-") as directory:
        source = Path(directory) / "Проверка с пробелами.wav"
        shutil.copyfile(audio, source)
        output = transcribe(source, lambda progress: None, Event())
        text = output.read_text(encoding="utf-8").strip()
        if "проверка" not in text.lower() or "речи" not in text.lower():
            raise RuntimeError(f"Unexpected transcription: {text!r}")
        result["transcript"] = text
    root = tk.Tk()
    try:
        app = App(root)
        root.update()
        if not app.start_button.instate(["disabled"]):
            raise RuntimeError("Incorrect initial GUI state")
        result["gui"] = bool(root.winfo_exists())
    finally:
        root.destroy()
    return result
