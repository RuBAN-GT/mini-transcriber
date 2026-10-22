#!/usr/bin/env bash
# A standalone LGPL FFmpeg: no GPL codecs, external libraries or network input.
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
version=7.1.2
sha=089bc60fb59d6aecc5d994ff530fd0dcb3ee39aa55867849a2bbc4e555f9c304
mkdir -p vendor/ffmpeg vendor/ffmpeg-source vendor/build
archive="$root/vendor/ffmpeg-source/ffmpeg-$version.tar.xz"
if [[ ! -f "$archive" ]]; then
    curl --fail --location --retry 3 --retry-all-errors "https://ffmpeg.org/releases/ffmpeg-$version.tar.xz" -o "$archive.part"
    mv "$archive.part" "$archive"
fi
if command -v sha256sum >/dev/null; then
    echo "$sha  $archive" | sha256sum -c -
else
    echo "$sha  $archive" | shasum -a 256 -c -
fi
tar -xf "$archive" -C vendor/build
cd "vendor/build/ffmpeg-$version"
flags=(--disable-autodetect --disable-gpl --disable-nonfree --disable-version3
       --disable-network --disable-doc --disable-debug --disable-ffplay --disable-ffprobe
       --disable-avdevice --disable-postproc --disable-x86asm --disable-shared --enable-static)
if [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]]; then
    flags+=(--extra-ldflags=-static)
    jobs="${NUMBER_OF_PROCESSORS:-2}"
    binary=ffmpeg.exe
else
    jobs="$(sysctl -n hw.ncpu)"
    binary=ffmpeg
    if [[ "$(uname -m)" == arm64 ]]; then target=14.0; else target=15.0; fi
    flags+=("--extra-cflags=-mmacosx-version-min=$target" "--extra-ldflags=-mmacosx-version-min=$target")
fi
printf 'FFmpeg %s\nSource SHA-256: %s\nConfigure: ' "$version" "$sha" > "$root/vendor/ffmpeg-source/BUILD.txt"
printf '%q ' "${flags[@]}" >> "$root/vendor/ffmpeg-source/BUILD.txt"
printf '\n' >> "$root/vendor/ffmpeg-source/BUILD.txt"
./configure "${flags[@]}" > "$root/vendor/ffmpeg-source/configure.log" 2>&1
make -j "$jobs" > "$root/vendor/ffmpeg-source/make.log" 2>&1
cp "$binary" "$root/vendor/ffmpeg/$binary"
cp COPYING.LGPLv2.1 "$root/vendor/ffmpeg-source/"
cp "$root/scripts/build-ffmpeg.sh" "$root/vendor/ffmpeg-source/"
"$root/vendor/ffmpeg/$binary" -L > "$root/vendor/ffmpeg-source/LICENSE.txt" 2>&1
if grep -q 'enable-gpl\|enable-nonfree\|enable-version3' "$root/vendor/ffmpeg-source/LICENSE.txt"; then
    echo 'Unexpected FFmpeg license configuration' >&2
    exit 1
fi
echo "Built standalone LGPL FFmpeg: vendor/ffmpeg/$binary"
