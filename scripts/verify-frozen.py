"""Drive a packaged EXE/.app, with no imports from the application source."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

executable = Path(sys.argv[1]).resolve()
fixture = Path(__file__).resolve().parent.parent / "tests/fixtures/russian.wav"
with tempfile.TemporaryDirectory(prefix="mini-frozen-") as directory:
    for offline in (False, True):
        report = Path(directory) / f"report-{offline}.json"
        environment = os.environ.copy()
        if offline:
            environment["HF_HUB_OFFLINE"] = "1"
        process = subprocess.run(
            [str(executable), "--self-test", str(fixture), str(report)],
            cwd=directory, timeout=900, env=environment,
        )
        result = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        if process.returncode or not result.get("gui") or not result.get("cpu") or not result.get("transcript"):
            raise SystemExit(f"Frozen self-test failed ({process.returncode}, offline={offline}): {result}")
        print(json.dumps({"offline": offline, **result}, ensure_ascii=False, indent=2))
