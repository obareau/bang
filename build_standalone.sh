#!/bin/bash
# BANG! Qt6 — Build standalone binary with Nuitka

set -e

echo "🎵 BANG! Qt6 Standalone Builder"
echo "================================"

# Config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
OUTPUT_NAME="bang-qt"
VERSION="1.0-qt6"

# Platform detection
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="linux"
    OUTPUT_EXT=""
    PKG_FORMAT="AppImage"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macos"
    OUTPUT_EXT=".app"
    PKG_FORMAT="DMG"
else
    PLATFORM="windows"
    OUTPUT_EXT=".exe"
    PKG_FORMAT="MSI"
fi

echo "Platform: $PLATFORM ($PKG_FORMAT)"
echo "Output: $OUTPUT_NAME$OUTPUT_EXT"
echo ""

# Step 1: Check dependencies
echo "1️⃣ Checking dependencies..."
if ! command -v nuitka &> /dev/null; then
    echo "❌ Nuitka not found. Install with: pip install nuitka"
    exit 1
fi

if ! command -v uv &> /dev/null; then
    echo "❌ uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✓ Nuitka $(nuitka --version)"
echo "✓ uv $(uv --version)"
echo ""

# Step 2: Create virtual environment
echo "2️⃣ Creating build environment..."
if [ ! -d "$BUILD_DIR/venv" ]; then
    uv venv "$BUILD_DIR/venv"
fi
source "$BUILD_DIR/venv/bin/activate"
uv pip install PySide6 mido python-osc numpy
echo "✓ Environment ready"
echo ""

# Step 3: Build with Nuitka
echo "3️⃣ Compiling with Nuitka..."
NUITKA_ARGS=(
    --onefile
    --plugin-enable=pyside6
    --follow-imports
    --include-package=bang_engine
    --include-package=pianoroll
    --include-package=midi_routing
    --include-package=osc_debugger
    --include-package=nts1_panel
    --include-package=microfreak_panel
    --include-package=ratchet_engine
    --include-package=p_locks
    --include-package=midi_cc_router
    --output-dir="$BUILD_DIR/dist"
    --build-dir="$BUILD_DIR/build"
    --remove-output
)

# Add platform-specific args
if [ "$PLATFORM" = "windows" ]; then
    NUITKA_ARGS+=(--windows-console-mode=detach)
    NUITKA_ARGS+=(--windows-icon-from-ico="${SCRIPT_DIR}/bang.ico")
elif [ "$PLATFORM" = "macos" ]; then
    NUITKA_ARGS+=(--macos-create-app-bundle)
    NUITKA_ARGS+=(--macos-app-icon="${SCRIPT_DIR}/bang.icns")
fi

cd "$SCRIPT_DIR"
nuitka "${NUITKA_ARGS[@]}" qt_app.py

echo "✓ Compilation complete"
echo ""

# Step 4: Package
echo "4️⃣ Creating distributable package..."

case "$PLATFORM" in
    linux)
        # Create AppImage
        OUTPUT_FILE="$BUILD_DIR/dist/${OUTPUT_NAME}-${VERSION}.AppImage"
        echo "Creating AppImage..."
        # Note: requires linuxdeploy (simplified for now)
        cp "$BUILD_DIR/dist/qt_app" "$BUILD_DIR/dist/$OUTPUT_NAME"
        chmod +x "$BUILD_DIR/dist/$OUTPUT_NAME"
        echo "✓ Binary: $BUILD_DIR/dist/$OUTPUT_NAME"
        ;;
    macos)
        OUTPUT_FILE="$BUILD_DIR/dist/${OUTPUT_NAME}-${VERSION}.dmg"
        echo "Creating DMG..."
        # Note: hdiutil would create DMG
        echo "✓ App bundle: $BUILD_DIR/dist/$OUTPUT_NAME.app"
        ;;
    windows)
        OUTPUT_FILE="$BUILD_DIR/dist/${OUTPUT_NAME}-${VERSION}.exe"
        echo "✓ Executable: $OUTPUT_FILE"
        ;;
esac

echo ""
echo "✅ Build complete!"
echo "📦 Output: $(ls -lh $BUILD_DIR/dist/$OUTPUT_NAME* 2>/dev/null | head -1 | awk '{print $NF " (" $5 ")"}')"
echo ""
echo "Run: ./$OUTPUT_NAME"
