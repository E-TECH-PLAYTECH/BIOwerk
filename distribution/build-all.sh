#!/bin/bash
# Build all distribution packages for BIOwerk

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION="${VERSION:-1.0.0}"
DIST_OUTPUT="$SCRIPT_DIR/output"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Clean previous builds
clean_build() {
    log "Cleaning previous builds..."
    rm -rf "$DIST_OUTPUT"
    mkdir -p "$DIST_OUTPUT"/{macos,linux,windows,electron,portable}
}

# Build Electron app for all platforms
build_electron() {
    log "Building Electron launcher for all platforms..."

    cd "$SCRIPT_DIR/electron-launcher"

    # Check if node_modules exists, install if not
    if [ ! -d "node_modules" ]; then
        info "Installing dependencies..."
        npm install
    fi

    # Build for all platforms
    info "Building for macOS..."
    npm run build:mac || warn "macOS build failed (may require macOS to build)"

    info "Building for Windows..."
    npm run build:win || warn "Windows build failed"

    info "Building for Linux..."
    npm run build:linux || warn "Linux build failed"

    # Copy builds to output directory
    if [ -d "dist" ]; then
        cp -r dist/* "$DIST_OUTPUT/electron/" 2>/dev/null || true
        log "Electron builds copied to $DIST_OUTPUT/electron/"
    fi

    cd "$SCRIPT_DIR"
}

# Build macOS DMG
build_macos_dmg() {
    log "Building macOS DMG..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        cd "$SCRIPT_DIR/macos"
        bash create-dmg.sh

        # Copy to output
        if [ -d "dist" ]; then
            cp dist/*.dmg "$DIST_OUTPUT/macos/" 2>/dev/null || true
            log "macOS DMG copied to $DIST_OUTPUT/macos/"
        fi

        cd "$SCRIPT_DIR"
    else
        warn "macOS DMG build skipped (requires macOS)"
    fi
}

# Package Linux installer
package_linux() {
    log "Packaging Linux installer..."

    mkdir -p "$DIST_OUTPUT/linux/biowerk-${VERSION}"

    # Copy installer script
    cp "$SCRIPT_DIR/linux/install.sh" "$DIST_OUTPUT/linux/biowerk-${VERSION}/"

    # Copy application files
    rsync -av --exclude='.git' --exclude='distribution' --exclude='tests' \
        "$PROJECT_ROOT/" "$DIST_OUTPUT/linux/biowerk-${VERSION}/app/"

    # Create tarball
    cd "$DIST_OUTPUT/linux"
    tar -czf "biowerk-${VERSION}-linux.tar.gz" "biowerk-${VERSION}"
    rm -rf "biowerk-${VERSION}"

    log "Linux package created: $DIST_OUTPUT/linux/biowerk-${VERSION}-linux.tar.gz"
    cd "$SCRIPT_DIR"
}

# Package Windows installer
package_windows() {
    log "Packaging Windows installer..."

    mkdir -p "$DIST_OUTPUT/windows/biowerk-${VERSION}"

    # Copy installer script
    cp "$SCRIPT_DIR/windows/install.ps1" "$DIST_OUTPUT/windows/biowerk-${VERSION}/"

    # Copy application files
    rsync -av --exclude='.git' --exclude='distribution' --exclude='tests' \
        "$PROJECT_ROOT/" "$DIST_OUTPUT/windows/biowerk-${VERSION}/app/"

    # Create zip
    cd "$DIST_OUTPUT/windows"
    zip -r "biowerk-${VERSION}-windows.zip" "biowerk-${VERSION}"
    rm -rf "biowerk-${VERSION}"

    log "Windows package created: $DIST_OUTPUT/windows/biowerk-${VERSION}-windows.zip"
    cd "$SCRIPT_DIR"
}

# Build portable archives
build_portable() {
    log "Building portable archives..."

    cd "$SCRIPT_DIR/portable"

    # Export VERSION for portable build script
    export VERSION

    bash build-portable.sh

    log "Portable archives created"
    cd "$SCRIPT_DIR"
}

# Create release notes
create_release_notes() {
    log "Creating release notes..."

    cat > "$DIST_OUTPUT/RELEASE_NOTES.md" <<EOF
# BIOwerk v${VERSION} - Release Notes

## Installation

### Portable Installation (Recommended for Quick Setup)

Works on all platforms without Docker:

1. Download \`biowerk-portable-${VERSION}.tar.gz\` (Linux/macOS) or \`biowerk-portable-${VERSION}.zip\` (Windows)
2. Extract the archive
3. Run installation script:
   - **Linux/macOS**: \`./install.sh\`
   - **Windows**: \`.\install.ps1\`
4. Start BIOwerk:
   - **Linux/macOS**: \`cd ~/.biowerk && ./biowerk-start.sh\`
   - **Windows**: \`cd \$env:USERPROFILE\.biowerk && .\biowerk-start.ps1\`

### macOS
1. Download \`biowerk-${VERSION}.dmg\`
2. Open the DMG file
3. Drag BIOwerk.app to Applications folder
4. Launch BIOwerk from Applications

**Alternative:** Use the Electron app from \`electron/\` directory

### Linux
1. Download \`biowerk-${VERSION}-linux.tar.gz\`
2. Extract: \`tar -xzf biowerk-${VERSION}-linux.tar.gz\`
3. Run: \`cd biowerk-${VERSION} && sudo bash install.sh\`

**Alternative:** Use the Electron AppImage from \`electron/\` directory

### Windows
1. Download \`biowerk-${VERSION}-windows.zip\`
2. Extract the ZIP file
3. Right-click \`install.ps1\` and select "Run with PowerShell as Administrator"

**Alternative:** Use the Electron installer from \`electron/\` directory

## What's Included

- **Mesh Gateway** - Unified API surface
- **Osteon** - Document writer agent
- **Myocyte** - Analysis/Spreadsheet agent
- **Synapse** - Presentation/Visualization agent
- **Circadian** - Scheduler/Workflow agent
- **Nucleus** - Director/orchestrator
- **Chaperone** - Format adapter
- **GDPR Service** - Compliance and data management
- **Monitoring Stack** - Prometheus, Grafana, Loki
- **Backup Service** - Automated backup and disaster recovery

## Requirements

- **Docker Desktop** (will be installed automatically if missing)
- **macOS**: 10.15 or later
- **Linux**: Ubuntu 20.04+, Debian 10+, Fedora 35+, CentOS 8+, Arch Linux
- **Windows**: Windows 10/11 (64-bit)

## First-Time Setup

1. Launch BIOwerk
2. Wait for Docker to start (if not already running)
3. The application will create a default \`.env\` configuration file
4. Edit the configuration if needed (API keys, database passwords, etc.)
5. Restart the application

## Access Points

- **API Documentation**: http://localhost:8080/docs
- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

## Configuration

Edit the \`.env\` file in the installation directory:
- **Database**: PostgreSQL credentials
- **API Keys**: LLM provider keys (OpenAI, Anthropic, DeepSeek)
- **Security**: JWT secrets, encryption keys
- **Monitoring**: Alert configurations

## Support

- **Documentation**: https://github.com/E-TECH-PLAYTECH/BIOwerk
- **Issues**: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues

## Version

Build: ${VERSION}
Date: $(date +%Y-%m-%d)
EOF

    log "Release notes created: $DIST_OUTPUT/RELEASE_NOTES.md"
}

# Create checksums
create_checksums() {
    log "Creating checksums..."

    cd "$DIST_OUTPUT"

    # Find all distribution files
    find . -type f \( -name "*.dmg" -o -name "*.tar.gz" -o -name "*.zip" -o -name "*.exe" -o -name "*.AppImage" -o -name "*.deb" -o -name "*.rpm" \) -exec shasum -a 256 {} \; > SHA256SUMS.txt

    log "Checksums created: $DIST_OUTPUT/SHA256SUMS.txt"
    cd "$SCRIPT_DIR"
}

# Main build flow
main() {
    echo "========================================"
    echo "   BIOwerk Distribution Builder"
    echo "   Version: $VERSION"
    echo "========================================"
    echo ""

    # Clean previous builds
    clean_build

    # Build Electron apps (cross-platform)
    build_electron

    # Build platform-specific packages
    build_macos_dmg
    package_linux
    package_windows

    # Build portable archives
    build_portable

    # Create release artifacts
    create_release_notes
    create_checksums

    echo ""
    echo "========================================"
    echo "   Build Complete! 🎉"
    echo "========================================"
    echo ""
    info "Distribution packages created in: $DIST_OUTPUT"
    echo ""
    info "Contents:"
    ls -lh "$DIST_OUTPUT"
    echo ""

    # Show file sizes
    info "Package sizes:"
    find "$DIST_OUTPUT" -type f \( -name "*.dmg" -o -name "*.tar.gz" -o -name "*.zip" \) -exec du -h {} \;
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --version)
            VERSION="$2"
            shift 2
            ;;
        --electron-only)
            ELECTRON_ONLY=true
            shift
            ;;
        --portable-only)
            PORTABLE_ONLY=true
            shift
            ;;
        --clean)
            clean_build
            exit 0
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --version VERSION    Set build version (default: 1.0.0)"
            echo "  --electron-only      Build only Electron apps"
            echo "  --portable-only      Build only portable archives"
            echo "  --clean              Clean build directories and exit"
            echo "  --help               Show this help message"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Run main build
if [ "$ELECTRON_ONLY" = true ]; then
    clean_build
    build_electron
elif [ "$PORTABLE_ONLY" = true ]; then
    clean_build
    build_portable
else
    main
fi
