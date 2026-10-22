# Mini Transcriber

Минимальный локальный транскрибатор русской речи для **Windows x64 и macOS**
(Apple Silicon / Intel). Один движок: transcribe.cpp + GigaAM v3 E2E-CTC Q8_0.
Без MLX, MCP, микрофона, аккаунта и настройки видеокарты.

## Запуск готового приложения

Архивы находятся в [Releases](https://github.com/RuBAN-GT/mini-transcriber/releases).
Репозиторий публичный: готовый ZIP можно скачать по ссылке или передать
получателю отдельно, GitHub-аккаунт для запуска не нужен.

- **Windows 10/11 Intel/AMD x64:** распакуйте весь `MiniTranscriber-windows-x64.zip`
  и запустите `MiniTranscriber.exe`. Не вынимайте один EXE из папки.
- **Mac Apple Silicon (M1 и новее):** `MiniTranscriber-macos-arm64.zip`.
- **Mac Intel:** `MiniTranscriber-macos-x64.zip`.
  На Mac распакуйте архив и перенесите `.app` в «Программы».

Python и установка FFmpeg не нужны. Сборки **не подписаны / не notarized**:
SmartScreen или Gatekeeper могут заблокировать первый запуск. На Mac после
попытки запуска используйте «Системные настройки → Конфиденциальность
и безопасность → Всё равно открыть», только если доверяете источнику архива.
Не отключайте защиту системы глобально. На управляемом компьютере может
потребоваться помощь администратора.

Выберите аудио/видео → «Расшифровать» → «Открыть текст».
UTF-8 TXT сохраняется рядом с записью. Исходник не изменяется. Если TXT уже
есть, создаётся `имя (2).txt`, затем `(3)` и т. д.

Первое распознавание скачивает модель **272 МБ** с Hugging Face. Далее полный
кэш позволяет работать без интернета. Аудио и текст не отправляются в облако.
Кэш: `~/.cache/huggingface/hub` (Windows: `%USERPROFILE%\.cache\huggingface\hub`)
или путь из `HF_HOME`.

## Ограничения

- Русская речь, CPU. Скорость зависит от компьютера, не обещаем реального времени.
- Без спикеров, таймкодов, перевода, микрофона и пакетной обработки.
- Распознавание по 25 секунд: слово на границе фрагментов может пострадать.
- Отмена ожидает текущий фрагмент или сетевой запрос. 25 секунд — длина аудио,
  а не гарантированное время ожидания.
- Временный WAV занимает примерно 115 МБ на час. Нужны место под модель,
  свободное место во временной папке и право записи рядом с исходным файлом.
- Форматы читает FFmpeg: MP3, WAV, OGG, M4A, FLAC, MP4, MKV и другие.
  Не все существующие кодеки поддерживаются. Файл без аудио выдаёт ошибку.
- CI проверяет Windows Server 2022, macOS 14 arm64 и macOS 15 Intel.
  Все версии ОС и всё разнообразие компьютеров этим не покрываются.

## Из исходников

Нужен Python 3.11+ с Tcl/Tk и FFmpeg в PATH (на Mac: `brew install ffmpeg
python-tk@3.11`). Или сначала соберите наш FFmpeg по инструкции ниже.

```sh
python -m venv .venv
# Windows: .venv\Scripts\python.exe; macOS: .venv/bin/python
.venv/bin/python -m pip install .
.venv/bin/python -m mini_transcriber
```

## Сборка

Для локальной сборки потребуются C-компилятор, make, curl и tar/xz.
На Mac — Xcode Command Line Tools; на Windows — MSYS2 MINGW64 с GCC.
FFmpeg собирается без GPL/nonfree-компонентов и сторонних кодек-библиотек;
точный исходный архив и рецепт включаются в приложение для соблюдения LGPL.

```sh
# macOS, активированное Python-окружение
bash scripts/build-ffmpeg.sh
bash scripts/build-macos.sh
```

```powershell
# Windows: сначала в MSYS2 MINGW64
# bash scripts/build-ffmpeg.sh
# Затем в PowerShell с Python x64:
py -3.11 -m venv .venv
$env:PATH = "$PWD\.venv\Scripts;$env:PATH"
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

Результат: `dist/MiniTranscriber.app` или папка `dist/MiniTranscriber/` с EXE.
Mac-архив создавайте через `ditto -c -k --sequesterRsrc --keepParent` для
сохранения symlinks и структуры `.app`.

## CI и релизы

`.github/workflows/build.yml` собирает три платформы и проверяет каждый
**упакованный** executable: загрузку DLL/dylib, FFmpeg, скачивание модели,
настоящее распознавание синтетической русской речи, UTF-8 и кириллицу в пути,
открытие/закрытие окна. Тест запускается из отдельной временной папки,
без импорта исходников приложения.

ZIP доступен в артефактах workflow. Тег `v*` публикует все три архива в Releases
только после успешных проверок всех платформ. Используются бесплатные
стандартные runners для публичного репозитория, без платных runners.

```sh
python -m unittest discover -s tests -v
python scripts/check-runtime.py
python scripts/verify-frozen.py dist/MiniTranscriber.app/Contents/MacOS/MiniTranscriber
```

Условия компонентов и расположение полных лицензий: [THIRD_PARTY.md](THIRD_PARTY.md).
