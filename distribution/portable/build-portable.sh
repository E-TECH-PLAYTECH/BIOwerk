#!/bin/bash
set -e

# BIOwerk Portable Archive Builder
# Creates distributable ZIP and TAR.GZ archives for portable installation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIOWERK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/../output"
VERSION="${VERSION:-$(cat $BIOWERK_ROOT/VERSION 2>/dev/null || echo "1.0.0")}"
BUILD_DIR="$SCRIPT_DIR/build"
PORTABLE_NAME="biowerk-portable-$VERSION"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}  BIOwerk Portable Archive Builder${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""
echo -e "${BLUE}Version: $VERSION${NC}"
echo ""

# Clean previous builds
if [ -d "$BUILD_DIR" ]; then
    echo "Cleaning previous build..."
    rm -rf "$BUILD_DIR"
fi

mkdir -p "$BUILD_DIR/$PORTABLE_NAME"
mkdir -p "$OUTPUT_DIR"

echo -e "${GREEN}[1/6]${NC} Copying source files..."
# Copy essential files
if command -v rsync &> /dev/null; then
    rsync -a \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.pytest_cache' \
        --exclude='venv' \
        --exclude='node_modules' \
        --exclude='dist' \
        --exclude='build' \
        --exclude='.mypy_cache' \
        --exclude='.coverage' \
        --exclude='htmlcov' \
        --exclude='*.egg-info' \
        --exclude='data' \
        --exclude='logs' \
        --exclude='distribution/output' \
        "$BIOWERK_ROOT/" "$BUILD_DIR/$PORTABLE_NAME/"
else
    # Fallback to cp with find for exclusions
    echo "rsync not found, using cp..."
    cd "$BIOWERK_ROOT"
    find . -type f \
        ! -path './.git/*' \
        ! -path './__pycache__/*' \
        ! -name '*.pyc' \
        ! -path './.pytest_cache/*' \
        ! -path './venv/*' \
        ! -path './node_modules/*' \
        ! -path './dist/*' \
        ! -path './build/*' \
        ! -path './.mypy_cache/*' \
        ! -path './.coverage/*' \
        ! -path './htmlcov/*' \
        ! -path './*.egg-info/*' \
        ! -path './data/*' \
        ! -path './logs/*' \
        ! -path './distribution/output/*' \
        ! -path './distribution/portable/build/*' \
        | while read file; do
            dir="$BUILD_DIR/$PORTABLE_NAME/$(dirname "$file")"
            mkdir -p "$dir"
            cp "$file" "$dir/"
        done
    cd "$SCRIPT_DIR"
fi

echo -e "${GREEN}[2/6]${NC} Copying installation scripts..."
# Copy installation scripts to root of portable archive
cp "$SCRIPT_DIR/install.sh" "$BUILD_DIR/$PORTABLE_NAME/"
cp "$SCRIPT_DIR/install.ps1" "$BUILD_DIR/$PORTABLE_NAME/"
chmod +x "$BUILD_DIR/$PORTABLE_NAME/install.sh"

echo -e "${GREEN}[3/6]${NC} Creating README..."
cat > "$BUILD_DIR/$PORTABLE_NAME/README.md" << 'EOF'
# BIOwerk Portable Installation

This is a portable distribution of BIOwerk that can be installed without Docker.

## System Requirements

- **Python**: 3.10 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 2GB minimum
- **OS**: Linux, macOS, or Windows

## Quick Start

### Linux / macOS

1. Extract this archive
2. Open a terminal in the extracted directory
3. Run the installation script:
   ```bash
   ./install.sh
   ```
4. Follow the on-screen instructions
5. Start BIOwerk:
   ```bash
   cd ~/.biowerk
   ./biowerk-start.sh
   ```

### Windows

1. Extract this archive
2. Open PowerShell in the extracted directory
3. Run the installation script:
   ```powershell
   .\install.ps1
   ```
4. Follow the on-screen instructions
5. Start BIOwerk:
   ```powershell
   cd $env:USERPROFILE\.biowerk
   .\biowerk-start.ps1
   ```

## Custom Installation Location

By default, BIOwerk installs to `~/.biowerk` (or `%USERPROFILE%\.biowerk` on Windows).

To install to a custom location, set the `BIOWERK_INSTALL_DIR` environment variable:

**Linux/macOS:**
```bash
export BIOWERK_INSTALL_DIR=/opt/biowerk
./install.sh
```

**Windows:**
```powershell
$env:BIOWERK_INSTALL_DIR = "C:\biowerk"
.\install.ps1
```

## Usage

After installation, you'll have the following commands:

- `biowerk-start.sh` / `biowerk-start.ps1` - Start all services
- `biowerk-stop.sh` / `biowerk-stop.ps1` - Stop all services
- `biowerk-status.sh` / `biowerk-status.ps1` - Check service status
- `uninstall.sh` / `uninstall.ps1` - Uninstall BIOwerk

## Accessing the API

Once started, the API will be available at:
- API Gateway: http://localhost:8080
- Interactive Documentation: http://localhost:8080/docs
- Alternative Docs: http://localhost:8080/redoc

## Configuration

Configuration is stored in the `.env` file in your installation directory. You can edit this file to:

- Configure database connections
- Set API keys for OpenAI/Anthropic
- Adjust service ports
- Enable/disable features

## Troubleshooting

### Services won't start

Check the logs in the `logs/` directory in your installation directory:
```bash
tail -f ~/.biowerk/logs/*.log
```

### Port conflicts

If ports 8080-8006 are already in use, edit the `.env` file to change the port numbers.

### Python version issues

Ensure you have Python 3.10 or higher:
```bash
python3 --version
```

## Documentation

Full documentation is available in the `docs/` directory or online at:
https://github.com/E-TECH-PLAYTECH/BIOwerk

## Support

For issues and questions:
- GitHub Issues: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues
- Documentation: See the `docs/` directory

## License

See LICENSE file for details.
EOF

echo -e "${GREEN}[4/6]${NC} Creating quick-start script..."
cat > "$BUILD_DIR/$PORTABLE_NAME/quick-start.sh" << 'EOF'
#!/bin/bash
# Quick Start Script - Installs and starts BIOwerk in one command

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================="
echo "  BIOwerk Quick Start"
echo "======================================="
echo ""
echo "This will install BIOwerk and start all services."
echo ""

# Run installation
./install.sh

# Get install directory
INSTALL_DIR="${BIOWERK_INSTALL_DIR:-$HOME/.biowerk}"

# Start services
if [ -f "$INSTALL_DIR/biowerk-start.sh" ]; then
    echo ""
    echo "Starting BIOwerk services..."
    cd "$INSTALL_DIR"
    ./biowerk-start.sh
else
    echo "Installation may have failed. Please check the output above."
    exit 1
fi
EOF

chmod +x "$BUILD_DIR/$PORTABLE_NAME/quick-start.sh"

cat > "$BUILD_DIR/$PORTABLE_NAME/quick-start.ps1" << 'EOF'
# Quick Start Script for Windows - Installs and starts BIOwerk in one command

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

Write-Host "======================================="
Write-Host "  BIOwerk Quick Start"
Write-Host "======================================="
Write-Host ""
Write-Host "This will install BIOwerk and start all services."
Write-Host ""

# Run installation
& ".\install.ps1"

# Get install directory
$INSTALL_DIR = if ($env:BIOWERK_INSTALL_DIR) { $env:BIOWERK_INSTALL_DIR } else { Join-Path $env:USERPROFILE ".biowerk" }

# Start services
$startScript = Join-Path $INSTALL_DIR "biowerk-start.ps1"
if (Test-Path $startScript) {
    Write-Host ""
    Write-Host "Starting BIOwerk services..."
    Set-Location $INSTALL_DIR
    & $startScript
} else {
    Write-Host "Installation may have failed. Please check the output above." -ForegroundColor Red
    exit 1
}
EOF

echo -e "${GREEN}[5/6]${NC} Creating archives..."

# Create tar.gz archive
cd "$BUILD_DIR"
echo "Creating $PORTABLE_NAME.tar.gz..."
tar -czf "$OUTPUT_DIR/$PORTABLE_NAME.tar.gz" "$PORTABLE_NAME"

# Create zip archive
echo "Creating $PORTABLE_NAME.zip..."
zip -q -r "$OUTPUT_DIR/$PORTABLE_NAME.zip" "$PORTABLE_NAME"

echo -e "${GREEN}[6/6]${NC} Generating checksums..."
cd "$OUTPUT_DIR"

# Generate SHA256 checksums
sha256sum "$PORTABLE_NAME.tar.gz" > "$PORTABLE_NAME.tar.gz.sha256"
sha256sum "$PORTABLE_NAME.zip" > "$PORTABLE_NAME.zip.sha256"

# Generate MD5 checksums
md5sum "$PORTABLE_NAME.tar.gz" > "$PORTABLE_NAME.tar.gz.md5"
md5sum "$PORTABLE_NAME.zip" > "$PORTABLE_NAME.zip.md5"

# Create checksums file
cat > "CHECKSUMS-$VERSION.txt" << EOF
BIOwerk Portable $VERSION - Checksums
Generated: $(date)

SHA256:
$(cat $PORTABLE_NAME.tar.gz.sha256)
$(cat $PORTABLE_NAME.zip.sha256)

MD5:
$(cat $PORTABLE_NAME.tar.gz.md5)
$(cat $PORTABLE_NAME.zip.md5)
EOF

# Get file sizes
TAR_SIZE=$(ls -lh "$PORTABLE_NAME.tar.gz" | awk '{print $5}')
ZIP_SIZE=$(ls -lh "$PORTABLE_NAME.zip" | awk '{print $5}')

# Clean build directory
echo "Cleaning build directory..."
rm -rf "$BUILD_DIR"

echo ""
echo -e "${GREEN}=======================================${NC}"
echo -e "${GREEN}  Build Complete!${NC}"
echo -e "${GREEN}=======================================${NC}"
echo ""
echo "Portable archives created:"
echo "  • $PORTABLE_NAME.tar.gz ($TAR_SIZE)"
echo "  • $PORTABLE_NAME.zip ($ZIP_SIZE)"
echo ""
echo "Output directory: $OUTPUT_DIR"
echo ""
echo "Checksums:"
echo "  • CHECKSUMS-$VERSION.txt"
echo "  • *.sha256 files"
echo "  • *.md5 files"
echo ""
echo "To test the installation:"
echo "  tar -xzf $OUTPUT_DIR/$PORTABLE_NAME.tar.gz"
echo "  cd $PORTABLE_NAME"
echo "  ./install.sh"
echo ""
