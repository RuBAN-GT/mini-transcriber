import array
from contextlib import contextmanager
from pathlib import Path
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import wave

from mini_transcriber import core


def make_wav(path, seconds=1, rate=16000):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * (seconds * rate))


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.cancel = Event()

    def test_utf8_result_and_no_overwrite(self):
        source = self.root / "Русская запись.mp3"
        source.write_bytes(b"original")
        first = core.save_text(source, "Привет, мир!")
        second = core.save_text(source, "Другой текст")
        self.assertEqual(first.name, "Русская запись.txt")
        self.assertEqual(second.name, "Русская запись (2).txt")
        self.assertEqual(first.read_text(encoding="utf-8"), "Привет, мир!\n")
        self.assertEqual(source.read_bytes(), b"original")

    def test_frozen_ffmpeg_must_be_bundled(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", str(self.root), create=True), patch("shutil.which") as which:
            with self.assertRaisesRegex(RuntimeError, "FFmpeg не найден"):
                core.ffmpeg_path()
            which.assert_not_called()

    def test_frozen_ffmpeg_path(self):
        name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
        binary = self.root / "ffmpeg" / name
        binary.parent.mkdir()
        binary.touch()
        with patch.object(sys, "_MEIPASS", str(self.root), create=True):
            self.assertEqual(core.ffmpeg_path(), str(binary))

    def test_text_source_does_not_overwrite_itself(self):
        source = self.root / "record.txt"
        source.write_text("original")
        self.assertEqual(core.save_text(source, "new").name, "record (2).txt")
        self.assertEqual(source.read_text(), "original")

    def test_missing_file(self):
        with self.assertRaisesRegex(RuntimeError, "не найден"):
            core.transcribe(self.root / "missing.wav", lambda _: None, self.cancel)

    def test_reject_text(self):
        source = self.root / "notes.txt"
        source.touch()
        with self.assertRaisesRegex(RuntimeError, "аудио или видео"):
            core.transcribe(source, lambda _: None, self.cancel)

    def test_cancel_before_work(self):
        source = self.root / "record.wav"
        source.touch()
        self.cancel.set()
        with self.assertRaises(core.Cancelled):
            core.transcribe(source, lambda _: None, self.cancel)
        self.assertFalse(source.with_suffix(".txt").exists())

    def test_cached_model_avoids_network(self):
        model = self.root / "model.gguf"
        model.touch()
        with patch("huggingface_hub.try_to_load_from_cache", return_value=str(model)), patch("huggingface_hub.hf_hub_download") as download:
            self.assertEqual(core.ensure_model(lambda _: None, self.cancel), model)
            download.assert_not_called()

    def test_download_reports_progress_without_stderr(self):
        reports = []

        def download(**kwargs):
            self.assertEqual(kwargs["revision"], core.MODEL_REVISION)
            with kwargs["tqdm_class"](total=10) as bar:
                bar.update(10)
            return str(self.root / "model.gguf")

        with patch("huggingface_hub.try_to_load_from_cache", return_value=None), patch("huggingface_hub.hf_hub_download", side_effect=download), patch.object(sys, "stderr", None):
            core.ensure_model(reports.append, self.cancel)
        self.assertEqual(reports[-1].percent, 100)

    def test_download_cancellation(self):
        def download(**kwargs):
            with kwargs["tqdm_class"](total=10) as bar:
                self.cancel.set()
                bar.update(1)
        with patch("huggingface_hub.try_to_load_from_cache", return_value=None), patch("huggingface_hub.hf_hub_download", side_effect=download):
            with self.assertRaises(core.Cancelled):
                core.ensure_model(lambda _: None, self.cancel)

    @contextmanager
    def engine(self, run):
        session = MagicMock()
        session.run.side_effect = run
        model = MagicMock()
        model.session.return_value.__enter__.return_value = session
        model.__enter__.return_value = model
        constructor = MagicMock(return_value=model)
        with patch.dict(sys.modules, {"transcribe_cpp": SimpleNamespace(Model=constructor)}):
            yield constructor, session

    def test_long_audio_is_chunked_and_cpu_is_explicit(self):
        wav = self.root / "long.wav"
        make_wav(wav, seconds=51)
        reports = []
        lengths = []

        def run(pcm, **kwargs):
            self.assertIsInstance(pcm, array.array)
            self.assertEqual(pcm.typecode, "f")
            self.assertEqual(kwargs, {"language": "ru"})
            lengths.append(len(pcm))
            return SimpleNamespace(text=" Текст ")

        with self.engine(run) as (constructor, session):
            text = core.recognize(wav, self.root / "model.gguf", reports.append, self.cancel)
        constructor.assert_called_once_with(str(self.root / "model.gguf"), backend="cpu")
        self.assertEqual(lengths, [400000, 400000, 16000])
        self.assertEqual(text, "Текст\nТекст\nТекст")
        self.assertEqual(reports[-1].percent, 100)
        self.assertEqual(session.run.call_count, 3)

    def test_cancel_after_inference_discards_text(self):
        wav = self.root / "audio.wav"
        make_wav(wav)

        def run(*args, **kwargs):
            self.cancel.set()
            return SimpleNamespace(text="text")

        with self.engine(run), self.assertRaises(core.Cancelled):
            core.recognize(wav, self.root / "model.gguf", lambda _: None, self.cancel)

    def test_no_speech_is_not_saved_as_success(self):
        wav = self.root / "audio.wav"
        make_wav(wav)
        with self.engine(lambda *a, **k: SimpleNamespace(text="")), self.assertRaisesRegex(RuntimeError, "Речь не распознана"):
            core.recognize(wav, self.root / "model.gguf", lambda _: None, self.cancel)

    def test_invalid_wav(self):
        wav = self.root / "audio.wav"
        make_wav(wav, rate=8000)
        with self.engine(None), self.assertRaisesRegex(RuntimeError, "16 кГц"):
            core.recognize(wav, self.root / "model.gguf", lambda _: None, self.cancel)

    def test_empty_wav(self):
        wav = self.root / "audio.wav"
        make_wav(wav, seconds=0)
        with self.engine(None), self.assertRaisesRegex(RuntimeError, "нет аудиоданных"):
            core.recognize(wav, self.root / "model.gguf", lambda _: None, self.cancel)

    def test_real_ffmpeg_with_unicode_and_spaces(self):
        source = self.root / "Запись с пробелами.wav"
        make_wav(source, rate=8000)
        target = self.root / "converted.wav"
        core.convert_audio(source, target, self.cancel)
        with wave.open(str(target)) as wav:
            self.assertEqual((wav.getnchannels(), wav.getframerate(), wav.getsampwidth()), (1, 16000, 2))

    def test_real_ffmpeg_bad_input(self):
        source = self.root / "broken.mp4"
        source.write_bytes(b"not media")
        with self.assertRaisesRegex(RuntimeError, "Не удалось прочитать аудио"):
            core.convert_audio(source, self.root / "out.wav", self.cancel)

    def test_ffmpeg_cancel_terminates_child(self):
        process = MagicMock()
        process.poll.return_value = None
        self.cancel.set()
        # Cancellation after Popen, not before it.
        def spawn(*args, **kwargs):
            self.cancel.set()
            return process
        self.cancel.clear()
        with patch.object(core, "ffmpeg_path", return_value="ffmpeg"), patch("subprocess.Popen", side_effect=spawn), self.assertRaises(core.Cancelled):
            core.convert_audio(self.root / "in.wav", self.root / "out.wav", self.cancel)
        process.terminate.assert_called_once()
        process.wait.assert_called_once_with(timeout=3)

    def test_pipeline_cleans_temp_and_saves_text(self):
        source = self.root / "record.mp3"
        source.touch()
        temp_paths = []

        def convert(source, target, cancel):
            temp_paths.append(target)
            make_wav(target)

        with patch.object(core, "convert_audio", side_effect=convert), patch.object(core, "ensure_model", return_value=self.root / "model.gguf"), patch.object(core, "recognize", return_value="Результат"):
            result = core.transcribe(source, lambda _: None, self.cancel)
        self.assertEqual(result.read_text(encoding="utf-8"), "Результат\n")
        self.assertFalse(temp_paths[0].parent.exists())

    def test_pipeline_failure_cleans_temp_and_no_output(self):
        source = self.root / "record.mp3"
        source.touch()
        temp_paths = []

        def fail(source, target, cancel):
            temp_paths.append(target)
            raise RuntimeError("conversion failed")

        with patch.object(core, "convert_audio", side_effect=fail), self.assertRaisesRegex(RuntimeError, "conversion failed"):
            core.transcribe(source, lambda _: None, self.cancel)
        self.assertFalse(temp_paths[0].parent.exists())
        self.assertFalse(source.with_suffix(".txt").exists())


if __name__ == "__main__":
    unittest.main()
