# Компоненты сторонних разработчиков

Mini Transcriber использует следующие компоненты. Их лицензии не заменяются
условиями приложения; уведомления из пакетов необходимо сохранять при распространении.

- transcribe.cpp / Python bindings / native provider 0.2.3 — MIT.
  https://github.com/handy-computer/transcribe.cpp
  Включает ggml и другие компоненты; см. THIRD-PARTY-LICENSES.md upstream.
- FFmpeg 7.1.2 — собственная сборка LGPL-2.1-or-later, отдельный исполняемый
  файл, без GPL/nonfree/version3, внешних codec-библиотек и сетевых протоколов.
  https://ffmpeg.org/legal.html
  В `licenses/ffmpeg` ресурсов приложения находятся точный исходный архив,
  полный текст LGPL, SHA-256, configure flags и рецепт сборки.
  FFmpeg не связан с приложением как библиотека; вызывается отдельным процессом.
  Сборка без изменений исходников: https://ffmpeg.org/releases/ffmpeg-7.1.2.tar.xz
- huggingface-hub — Apache-2.0. https://github.com/huggingface/huggingface_hub
- tqdm — MPL-2.0 / MIT, в зависимости от файла. https://github.com/tqdm/tqdm
- Python и Tcl/Tk — собственные разрешительные лицензии.
- PyInstaller — GPL с исключением для собранных приложений.
  https://pyinstaller.org/en/stable/license.html

Модель GigaAM скачивается отдельно, не входит в EXE. Условия модели:
https://huggingface.co/handy-computer/gigaam-v3-e2e-ctc-gguf
Исходная модель: https://github.com/salute-developers/GigaAM

Полные уведомления Python-зависимостей сохраняются в `.dist-info/licenses`
в ресурсах приложения, нативных библиотек — в metadata пакета
`transcribe_cpp_native`. Не удаляйте их при передаче архива.
На Windows ресурсы находятся в `_internal`, на macOS — внутри `.app/Contents`.
