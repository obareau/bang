#!/bin/bash
# BANG! Qt6 — Build a standalone binary with Nuitka.
#
# IMPORTANT: this only builds for the OS it runs ON — Nuitka (like PyInstaller)
# compiles native binaries, it does not cross-compile. To get Mac + Windows +
# Linux builds you must run this script on each OS (or use the GitHub Actions
# workflow at .github/workflows/build.yml, which does exactly that on hosted
# macOS/Windows/Linux runners — see that file for the automated version of
# what this script does manually).
#
# Linux note: the produced --onefile binary is a normal ELF executable linked
# against whatever shared libs are on the BUILD machine. To run on both Ubuntu
# and Arch-based distros (Garuda) reliably, prefer the AppImage packaging step
# below (bundles Qt/PySide6/libfluidsynth so the target system's package
# versions don't matter) — plain --onefile works too as long as the target
# has a reasonably close glibc version.

set -e

echo "🎵 BANG! Qt6 Standalone Builder"
echo "================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
OUTPUT_NAME="bang-qt"
VERSION="2.0-qt6"

# All local flat modules the app imports (kept in sync with the repo — see
# the "Modules" section of README/CLAUDE.md if you add new ones).
LOCAL_MODULES=(
    bang_engine babka pattern_lib bang_session live_clock
    generator_panel voice_rack_widget dna_grid_widget pianoroll
    midi_routing osc_debugger nts1_panel microfreak_panel
    ratchet_engine p_locks midi_cc_router
    sequencer_panel song_panel presets_lib presets_panel
    midi_activity_widget strudel_export synth_preview
    ableton_osc ableton_panel
)

# Platform detection
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"; PKG_FORMAT="AppImage"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"; PKG_FORMAT="app bundle + DMG"
else
    PLATFORM="windows"; PKG_FORMAT="exe"
fi

echo "Platform: $PLATFORM ($PKG_FORMAT)"
echo ""

echo "1️⃣ Checking dependencies..."
command -v uv >/dev/null || { echo "❌ uv not found: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
echo "✓ uv $(uv --version)"
echo ""

echo "2️⃣ Creating build environment..."
if [ ! -d "$BUILD_DIR/venv" ]; then
    uv venv "$BUILD_DIR/venv"
fi
# shellcheck disable=SC1091
source "$BUILD_DIR/venv/bin/activate"
uv pip install nuitka PySide6 mido python-osc python-rtmidi numpy pyfluidsynth
if [ "$PLATFORM" = "linux" ]; then
    uv pip install patchelf  # Nuitka standalone mode needs it; PyPI wheel bundles the binary
fi
echo "✓ Environment ready"
echo ""

echo "3️⃣ Compiling with Nuitka..."
NUITKA_ARGS=(
    --onefile
    --standalone
    --plugin-enable=pyside6
    --follow-imports
    --output-dir="$BUILD_DIR/dist"
    --output-filename="$OUTPUT_NAME"
    --remove-output
    --assume-yes-for-downloads
)
for mod in "${LOCAL_MODULES[@]}"; do
    NUITKA_ARGS+=(--include-module="$mod")
done
# mido loads its MIDI backend dynamically (importlib, not a static import) —
# Nuitka's analysis can't see it, so it must be listed explicitly or the
# packaged binary crashes with "No module named 'mido.backends.rtmidi'" the
# instant anything calls mido.get_output_names()/open_output().
NUITKA_ARGS+=(--include-module=mido.backends.rtmidi)
NUITKA_ARGS+=(--include-module=mido.backends.rtmidi_python)

if [ "$PLATFORM" = "windows" ]; then
    NUITKA_ARGS+=(--windows-console-mode=disable)
    [ -f "$SCRIPT_DIR/bang.ico" ] && NUITKA_ARGS+=(--windows-icon-from-ico="$SCRIPT_DIR/bang.ico")
elif [ "$PLATFORM" = "macos" ]; then
    NUITKA_ARGS+=(--macos-create-app-bundle)
    [ -f "$SCRIPT_DIR/bang.icns" ] && NUITKA_ARGS+=(--macos-app-icon="$SCRIPT_DIR/bang.icns")
fi

cd "$SCRIPT_DIR"
python -m nuitka "${NUITKA_ARGS[@]}" qt_app.py
echo "✓ Compilation complete"
echo ""

echo "4️⃣ Packaging..."
case "$PLATFORM" in
    linux)
        BIN="$BUILD_DIR/dist/$OUTPUT_NAME"
        chmod +x "$BIN"
        if command -v linuxdeploy >/dev/null; then
            echo "Building AppImage via linuxdeploy (portable across Ubuntu/Arch/Garuda)..."
            APPDIR="$BUILD_DIR/AppDir"
            rm -rf "$APPDIR" && mkdir -p "$APPDIR/usr/bin"
            cp "$BIN" "$APPDIR/usr/bin/$OUTPUT_NAME"
            linuxdeploy --appdir "$APPDIR" --executable "$APPDIR/usr/bin/$OUTPUT_NAME" \
                --desktop-file="$SCRIPT_DIR/bang.desktop" --output appimage \
                2>/dev/null || echo "⚠️ linuxdeploy step failed, falling back to plain binary"
            mv ./*.AppImage "$BUILD_DIR/dist/${OUTPUT_NAME}-${VERSION}.AppImage" 2>/dev/null || true
        else
            echo "ℹ️ linuxdeploy not found — shipping a plain onefile binary instead."
            echo "   For a portable AppImage: https://github.com/linuxdeploy/linuxdeploy (AppImage release)"
        fi
        echo "✓ Binary: $BIN"
        ;;
    macos)
        echo "✓ App bundle: $BUILD_DIR/dist/qt_app.app (rename/codesign as needed)"
        ;;
    windows)
        echo "✓ Executable: $BUILD_DIR/dist/$OUTPUT_NAME.exe"
        ;;
esac

echo ""
echo "✅ Build complete!"
ls -lh "$BUILD_DIR/dist/" 2>/dev/null
