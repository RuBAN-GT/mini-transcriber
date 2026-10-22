"""PyInstaller entry point (absolute import also works when frozen)."""

import json
import os
from pathlib import Path
import sys

if __name__ == "__main__":
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    diagnostic = len(sys.argv) == 3 and sys.argv[1] == "--check-runtime"
    smoke = len(sys.argv) == 4 and sys.argv[1] == "--self-test"
    if diagnostic or smoke:
        from mini_transcriber.diagnostics import check_runtime, self_test

        try:
            result = self_test(sys.argv[2]) if smoke else check_runtime()
        except Exception as error:
            Path(sys.argv[-1]).write_text(json.dumps({"error": str(error)}), encoding="utf-8")
            raise SystemExit(1)
        Path(sys.argv[-1]).write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    else:
        from mini_transcriber.app import main

        main()
