#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pip install -e '.[build]'
python -m unittest discover -s tests -v
python scripts/check-runtime.py
python -m PyInstaller --noconfirm MiniTranscriber.spec
python scripts/verify-frozen.py dist/MiniTranscriber.app/Contents/MacOS/MiniTranscriber
echo 'Built and verified: dist/MiniTranscriber.app'
