"""Transcription pipeline, independent of the GUI; heavyweight imports are lazy."""

from __future__ import annotations

import array
from dataclasses import dataclass
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from threading import Event
from typing import Callable
import wave

MODEL_REPO = "handy-computer/gigaam-v3-e2e-ctc-gguf"
MODEL_FILE = "gigaam-v3-e2e-ctc-Q8_0.gguf"
MODEL_REVISION = "075dff81f843cf23d22b4ce943ffdc4dd8650cd7"
SAMPLE_RATE = 16000
CHUNK_SECONDS = 25


@dataclass(frozen=True)
class Progress:
    message: str
    percent: float | None = None


class Cancelled(Exception):
    """The user requested cancellation."""


def check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise Cancelled()


def ensure_model(report: Callable[[Progress], None], cancel: Event) -> Path:
    from huggingface_hub import hf_hub_download, try_to_load_from_cache
    from tqdm.auto import tqdm

    check_cancel(cancel)
    cached = try_to_load_from_cache(MODEL_REPO, MODEL_FILE, revision=MODEL_REVISION)
    if isinstance(cached, str) and Path(cached).is_file():
        return Path(cached)

    class DownloadProgress(tqdm):
        def __init__(self, *args, **kwargs):
            # Windowed EXEs have no stderr; never attach tqdm to a console.
            kwargs["file"] = io.StringIO()
            super().__init__(*args, **kwargs)
            self.notify()

        def notify(self):
            check_cancel(cancel)
            percent = min(100, 100 * self.n / self.total) if self.total else None
            report(Progress("Скачивание модели…", percent))

        def update(self, n=1):
            result = super().update(n)
            self.notify()
            return result

    # Keep download progress on the Python/tqdm path, including in a frozen EXE.
    # Set before importing huggingface_hub in the application entry point too.
    report(Progress("Первый запуск: скачивание модели. Нужен интернет…"))
    path = hf_hub_download(
        repo_id=MODEL_REPO, filename=MODEL_FILE, revision=MODEL_REVISION,
        tqdm_class=DownloadProgress,
    )
    check_cancel(cancel)
    return Path(path)


def ffmpeg_path() -> str:
    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    bundled = root / "ffmpeg" / name
    development = root / "vendor" / "ffmpeg" / name
    if bundled.is_file():
        return str(bundled)
    if not getattr(sys, "frozen", False):
        if development.is_file():
            return str(development)
        installed = shutil.which("ffmpeg")
        if installed:
            return installed
    raise RuntimeError("FFmpeg не найден. Распакуйте архив приложения целиком.")


def convert_audio(source: Path, target: Path, cancel: Event) -> None:

    check_cancel(cancel)
    command = [
        ffmpeg_path(), "-nostdin", "-hide_banner", "-loglevel", "error",
        "-y", "-i", str(source), "-map", "0:a:0", "-vn", "-ac", "1",
        "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(target),
    ]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    # A file instead of PIPE prevents deadlock on verbose decoder errors.
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=errors, creationflags=flags,
        )
        try:
            while True:
                check_cancel(cancel)
                try:
                    code = process.wait(timeout=0.2)
                    break
                except subprocess.TimeoutExpired:
                    pass
            if code:
                errors.seek(max(0, errors.tell() - 4000))
                detail = errors.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(f"Не удалось прочитать аудио.\n{detail}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    check_cancel(cancel)


def recognize(wav_path: Path, model_path: Path, report: Callable[[Progress], None], cancel: Event) -> str:
    import transcribe_cpp

    check_cancel(cancel)
    report(Progress("Загрузка модели в память…"))
    with wave.open(str(wav_path), "rb") as wav:
        if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 2, SAMPLE_RATE):
            raise RuntimeError("Ожидался WAV: 16 кГц, моно, PCM 16 бит.")
        total = wav.getnframes()
        if not total:
            raise RuntimeError("В файле нет аудиоданных.")
        parts = []
        processed = 0
        # Explicit CPU policy: no GPU or driver configuration required.
        with transcribe_cpp.Model(str(model_path), backend="cpu") as model:
            with model.session() as session:
                while True:
                    check_cancel(cancel)
                    frames = wav.readframes(CHUNK_SECONDS * SAMPLE_RATE)
                    if not frames:
                        break
                    samples = array.array("h")
                    samples.frombytes(frames)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    pcm = array.array("f", (value / 32768.0 for value in samples))
                    text = session.run(pcm, language="ru").text.strip()
                    check_cancel(cancel)
                    if text:
                        parts.append(text)
                    processed += len(samples)
                    report(Progress("Распознавание речи…", min(100, 100 * processed / total)))
    text = "\n".join(parts)
    if not text:
        raise RuntimeError("Речь не распознана. Проверьте, что в записи слышна русская речь.")
    return text


def save_text(source: Path, text: str) -> Path:
    """Reserve a new filename exclusively; never overwrite existing user files."""
    index = 1
    while True:
        suffix = "" if index == 1 else f" ({index})"
        target = source.with_name(f"{source.stem}{suffix}.txt")
        try:
            stream = target.open("x", encoding="utf-8", newline="\n")
        except FileExistsError:
            index += 1
            continue
        try:
            with stream:
                stream.write(text + "\n")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return target


def transcribe(source: Path, report: Callable[[Progress], None], cancel: Event) -> Path:
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    source = source.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError("Выбранный файл не найден.")
    if source.suffix.lower() in {".txt", ".gguf"}:
        raise RuntimeError("Выберите аудио или видео, а не текст или модель.")
    check_cancel(cancel)
    with tempfile.TemporaryDirectory(prefix="mini-transcriber-") as directory:
        wav = Path(directory) / "audio.wav"
        report(Progress("Подготовка аудио…"))
        convert_audio(source, wav, cancel)
        model = ensure_model(report, cancel)
        text = recognize(wav, model, report, cancel)
    check_cancel(cancel)
    report(Progress("Сохранение текста…"))
    return save_text(source, text)
