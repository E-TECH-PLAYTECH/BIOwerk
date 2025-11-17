# BIOwerk Portable Archive Builder for Windows
# Creates distributable ZIP archives for portable installation

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BIOWERK_ROOT = Resolve-Path (Join-Path $SCRIPT_DIR "../..")
$OUTPUT_DIR = Join-Path $SCRIPT_DIR "..\output"
$VERSION = if ($env:VERSION) { $env:VERSION } else {
    if (Test-Path "$BIOWERK_ROOT\VERSION") {
        Get-Content "$BIOWERK_ROOT\VERSION" -Raw
    } else {
        "1.0.0"
    }
}
$VERSION = $VERSION.Trim()
$BUILD_DIR = Join-Path $SCRIPT_DIR "build"
$PORTABLE_NAME = "biowerk-portable-$VERSION"

Write-Host "=======================================" -ForegroundColor Blue
Write-Host "  BIOwerk Portable Archive Builder" -ForegroundColor Blue
Write-Host "=======================================" -ForegroundColor Blue
Write-Host ""
Write-Host "Version: $VERSION" -ForegroundColor Blue
Write-Host ""

# Clean previous builds
if (Test-Path $BUILD_DIR) {
    Write-Host "Cleaning previous build..."
    Remove-Item -Path $BUILD_DIR -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $BUILD_DIR $PORTABLE_NAME) | Out-Null
New-Item -ItemType Directory -Force -Path $OUTPUT_DIR | Out-Null

Write-Host "[1/6] Copying source files..." -ForegroundColor Green

# Patterns to exclude
$excludePatterns = @(
    '.git', '__pycache__', '*.pyc', '.pytest_cache', 'venv', 'node_modules',
    'dist', 'build', '.mypy_cache', '.coverage', 'htmlcov', '*.egg-info',
    'data', 'logs', 'distribution\output'
)

# Copy files with exclusions
Get-ChildItem -Path $BIOWERK_ROOT -Recurse | Where-Object {
    $item = $_
    $relativePath = $item.FullName.Substring($BIOWERK_ROOT.Path.Length)
    $shouldExclude = $false

    foreach ($pattern in $excludePatterns) {
        if ($pattern.StartsWith('*.')) {
            # File extension pattern
            if ($item.Extension -eq $pattern.Substring(1)) {
                $shouldExclude = $true
                break
            }
        } else {
            # Directory or file name pattern
            if ($relativePath -like "*\$pattern\*" -or $relativePath -like "*\$pattern" -or $relativePath -eq "\$pattern") {
                $shouldExclude = $true
                break
            }
        }
    }

    -not $shouldExclude
} | ForEach-Object {
    $targetPath = Join-Path (Join-Path $BUILD_DIR $PORTABLE_NAME) ($_.FullName.Substring($BIOWERK_ROOT.Path.Length))
    $targetDir = Split-Path -Parent $targetPath

    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
    }

    if (-not $_.PSIsContainer) {
        Copy-Item $_.FullName -Destination $targetPath -Force
    }
}

Write-Host "[2/6] Copying installation scripts..." -ForegroundColor Green
# Copy installation scripts to root
Copy-Item (Join-Path $SCRIPT_DIR "install.sh") (Join-Path (Join-Path $BUILD_DIR $PORTABLE_NAME) "install.sh")
Copy-Item (Join-Path $SCRIPT_DIR "install.ps1") (Join-Path (Join-Path $BUILD_DIR $PORTABLE_NAME) "install.ps1")

Write-Host "[3/6] Creating README..." -ForegroundColor Green
$readmeContent = @'
# BIOwerk Portable Installation

This is a portable distribution of BIOwerk that can be installed without Docker.

## System Requirements

- **Python**: 3.10 or higher
- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 2GB minimum
- **OS**: Linux, macOS, or Windows

## Quick Start

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

## Custom Installation Location

By default, BIOwerk installs to `%USERPROFILE%\.biowerk` (Windows) or `~/.biowerk` (Linux/macOS).

To install to a custom location, set the `BIOWERK_INSTALL_DIR` environment variable:

**Windows:**
```powershell
$env:BIOWERK_INSTALL_DIR = "C:\biowerk"
.\install.ps1
```

**Linux/macOS:**
```bash
export BIOWERK_INSTALL_DIR=/opt/biowerk
./install.sh
```

## Usage

After installation, you'll have the following commands:

- `biowerk-start.ps1` / `biowerk-start.sh` - Start all services
- `biowerk-stop.ps1` / `biowerk-stop.sh` - Stop all services
- `biowerk-status.ps1` / `biowerk-status.sh` - Check service status
- `uninstall.ps1` / `uninstall.sh` - Uninstall BIOwerk

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

Check the logs in the `logs\` directory in your installation directory.

### Port conflicts

If ports 8080-8006 are already in use, edit the `.env` file to change the port numbers.

### Python version issues

Ensure you have Python 3.10 or higher:
```
python --version
```

## Documentation

Full documentation is available in the `docs\` directory or online at:
https://github.com/E-TECH-PLAYTECH/BIOwerk

## Support

For issues and questions:
- GitHub Issues: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues
- Documentation: See the `docs\` directory

## License

See LICENSE file for details.
'@

$readmeContent | Out-File -FilePath (Join-Path (Join-Path $BUILD_DIR $PORTABLE_NAME) "README.md") -Encoding UTF8

Write-Host "[4/6] Creating quick-start scripts..." -ForegroundColor Green

$quickStartPs1 = @'
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
'@

$quickStartPs1 | Out-File -FilePath (Join-Path (Join-Path $BUILD_DIR $PORTABLE_NAME) "quick-start.ps1") -Encoding UTF8

Write-Host "[5/6] Creating ZIP archive..." -ForegroundColor Green

$zipPath = Join-Path $OUTPUT_DIR "$PORTABLE_NAME.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath
}

# Use .NET compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    (Join-Path $BUILD_DIR $PORTABLE_NAME),
    $zipPath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)

Write-Host "[6/6] Generating checksums..." -ForegroundColor Green

# Generate SHA256 checksum
$sha256 = Get-FileHash -Path $zipPath -Algorithm SHA256
$sha256.Hash + "  " + (Split-Path -Leaf $zipPath) | Out-File -FilePath "$zipPath.sha256" -Encoding ASCII

# Generate MD5 checksum
$md5 = Get-FileHash -Path $zipPath -Algorithm MD5
$md5.Hash + "  " + (Split-Path -Leaf $zipPath) | Out-File -FilePath "$zipPath.md5" -Encoding ASCII

# Create checksums file
$checksumFile = Join-Path $OUTPUT_DIR "CHECKSUMS-$VERSION.txt"
@"
BIOwerk Portable $VERSION - Checksums
Generated: $(Get-Date)

SHA256:
$($sha256.Hash)  $PORTABLE_NAME.zip

MD5:
$($md5.Hash)  $PORTABLE_NAME.zip
"@ | Out-File -FilePath $checksumFile -Encoding UTF8

# Get file size
$zipSize = (Get-Item $zipPath).Length / 1MB
$zipSizeFormatted = "{0:N2} MB" -f $zipSize

# Clean build directory
Write-Host "Cleaning build directory..."
Remove-Item -Path $BUILD_DIR -Recurse -Force

Write-Host ""
Write-Host "=======================================" -ForegroundColor Green
Write-Host "  Build Complete!" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green
Write-Host ""
Write-Host "Portable archive created:"
Write-Host "  • $PORTABLE_NAME.zip ($zipSizeFormatted)"
Write-Host ""
Write-Host "Output directory: $OUTPUT_DIR"
Write-Host ""
Write-Host "Checksums:"
Write-Host "  • CHECKSUMS-$VERSION.txt"
Write-Host "  • *.sha256 file"
Write-Host "  • *.md5 file"
Write-Host ""
Write-Host "To test the installation:"
Write-Host "  Expand-Archive $zipPath -DestinationPath ."
Write-Host "  cd $PORTABLE_NAME"
Write-Host "  .\install.ps1"
Write-Host ""
