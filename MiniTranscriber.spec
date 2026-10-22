from pathlib import Path
import platform
import sys
import sysconfig
from PyInstaller.utils.hooks import collect_all, collect_entry_point, copy_metadata

# Providers are loaded through importlib.metadata entry points, not static imports.
datas, hiddenimports = collect_entry_point("transcribe_cpp.native")
binaries = []
for package in ("transcribe_cpp", "transcribe_cpp_native"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports
for distribution in ("transcribe-cpp", "transcribe-cpp-native", "huggingface-hub", "tqdm"):
    datas += copy_metadata(distribution, recursive=True)
datas += [("README.md", "."), ("THIRD_PARTY.md", ".")]
datas += [("licenses", "licenses/runtime")]
python_license = next((p for p in (
    Path(sys.base_prefix) / "LICENSE.txt",
    Path(sysconfig.get_path("stdlib")) / "LICENSE.txt",
    Path(sys.base_prefix) / "Resources" / "English.lproj" / "License.rtf",
) if p.is_file()), None)
if python_license is None:
    raise SystemExit("Python distribution license not found")
datas += [(str(python_license), "licenses/python")]
ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
ffmpeg = Path("vendor/ffmpeg") / ffmpeg_name
if not ffmpeg.is_file():
    raise SystemExit("Build FFmpeg first: bash scripts/build-ffmpeg.sh")
binaries += [(str(ffmpeg), "ffmpeg")]
datas += [("vendor/ffmpeg-source", "licenses/ffmpeg")]

a = Analysis(
    ["launcher.py"], pathex=[], binaries=binaries, datas=datas,
    hiddenimports=hiddenimports, hookspath=[], runtime_hooks=[], excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="MiniTranscriber",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="MiniTranscriber")
if sys.platform == "darwin":
    app = BUNDLE(
        coll, name="MiniTranscriber.app", bundle_identifier="dev.ruban.mini-transcriber",
        info_plist={"CFBundleDisplayName": "Mini Transcriber", "CFBundleShortVersionString": "0.1.0",
                    "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "14.0" if platform.machine() == "arm64" else "15.0"},
    )
