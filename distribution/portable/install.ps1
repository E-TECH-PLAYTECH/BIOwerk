# BIOwerk Portable Installation Script for Windows
# This script installs BIOwerk from a portable archive

$ErrorActionPreference = "Stop"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BIOWERK_ROOT = Resolve-Path (Join-Path $SCRIPT_DIR "../..")
$INSTALL_DIR = if ($env:BIOWERK_INSTALL_DIR) { $env:BIOWERK_INSTALL_DIR } else { Join-Path $env:USERPROFILE ".biowerk" }

# Colors for output
function Write-Status {
    param([string]$Message)
    Write-Host "[✓] $Message" -ForegroundColor Green
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[✗] $Message" -ForegroundColor Red
}

Write-Host "========================================" -ForegroundColor Blue
Write-Host "  BIOwerk Portable Installation" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

# Check for required commands
function Check-Requirements {
    Write-Status "Checking system requirements..."

    # Check Python version
    try {
        $pythonVersion = & python --version 2>&1
        if ($pythonVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]

            if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
                Write-Error-Custom "Python 3.10 or higher is required. Found: $pythonVersion"
                exit 1
            }
            Write-Status "Python $pythonVersion found"
        }
    } catch {
        Write-Error-Custom "Python 3 is not installed. Please install Python 3.10 or higher."
        Write-Host "Download from: https://www.python.org/downloads/"
        exit 1
    }

    # Check for pip
    try {
        & python -m pip --version | Out-Null
    } catch {
        Write-Error-Custom "pip is not installed. Please install pip."
        exit 1
    }
}

# Create installation directory
function Create-InstallDir {
    Write-Status "Creating installation directory: $INSTALL_DIR"
    New-Item -ItemType Directory -Force -Path $INSTALL_DIR | Out-Null

    # Copy files
    Write-Status "Copying BIOwerk files..."
    $excludeDirs = @('.git', '__pycache__', '.pytest_cache', 'venv', 'node_modules')

    Get-ChildItem -Path $BIOWERK_ROOT -Recurse | Where-Object {
        $relativePath = $_.FullName.Substring($BIOWERK_ROOT.Path.Length)
        $shouldExclude = $false
        foreach ($exclude in $excludeDirs) {
            if ($relativePath -like "*\$exclude\*" -or $relativePath -like "*\$exclude") {
                $shouldExclude = $true
                break
            }
        }
        -not $shouldExclude -and ($_.Extension -ne '.pyc')
    } | ForEach-Object {
        $targetPath = Join-Path $INSTALL_DIR ($_.FullName.Substring($BIOWERK_ROOT.Path.Length))
        $targetDir = Split-Path -Parent $targetPath
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        }
        if (-not $_.PSIsContainer) {
            Copy-Item $_.FullName -Destination $targetPath -Force
        }
    }
}

# Create virtual environment
function Create-VirtualEnv {
    Write-Status "Creating Python virtual environment..."
    Set-Location $INSTALL_DIR
    & python -m venv venv

    Write-Status "Activating virtual environment..."
    $venvActivate = Join-Path $INSTALL_DIR "venv\Scripts\Activate.ps1"
    & $venvActivate

    Write-Status "Upgrading pip..."
    & python -m pip install --upgrade pip setuptools wheel

    Write-Status "Installing BIOwerk dependencies..."
    & pip install -r requirements.txt

    Write-Status "Installing BIOwerk in development mode..."
    & pip install -e .
}

# Create configuration files
function Create-Config {
    Write-Status "Creating configuration files..."

    # Create data directories
    New-Item -ItemType Directory -Force -Path (Join-Path $INSTALL_DIR "data\postgres") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $INSTALL_DIR "data\mongodb") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $INSTALL_DIR "data\redis") | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $INSTALL_DIR "logs") | Out-Null

    # Create .env file if it doesn't exist
    $envFile = Join-Path $INSTALL_DIR ".env"
    if (-not (Test-Path $envFile)) {
        $secretKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
        $jwtKey = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

        @"
# BIOwerk Configuration
BIOWERK_ENV=development
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=sqlite:///$INSTALL_DIR/data/biowerk.db
MONGODB_URL=mongodb://localhost:27017/biowerk
REDIS_URL=redis://localhost:6379/0

# LLM Configuration
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://localhost:11434

# Service Ports
MESH_PORT=8080
NUCLEUS_PORT=8001
OSTEON_PORT=8002
MYOCYTE_PORT=8003
SYNAPSE_PORT=8004
CIRCADIAN_PORT=8005
CHAPERONE_PORT=8006

# Security
SECRET_KEY=$secretKey
JWT_SECRET_KEY=$jwtKey

# Monitoring
ENABLE_METRICS=true
ENABLE_TRACING=false
"@ | Out-File -FilePath $envFile -Encoding UTF8
        Write-Status "Created .env configuration file"
    } else {
        Write-Warning-Custom ".env file already exists, skipping..."
    }
}

# Create launcher scripts
function Create-Launchers {
    Write-Status "Creating launcher scripts..."

    # Create start script
    $startScript = Join-Path $INSTALL_DIR "biowerk-start.ps1"
    @'
# BIOwerk Start Script
$INSTALL_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $INSTALL_DIR

# Load environment variables
Get-Content .env | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

# Activate virtual environment
& "venv\Scripts\Activate.ps1"

Write-Host "Starting BIOwerk services..."

# Start services
$services = @("nucleus", "osteon", "myocyte", "synapse", "circadian", "chaperone", "mesh")

foreach ($service in $services) {
    $logFile = "logs\$service.log"
    $pidFile = "logs\$service.pid"

    if ($service -eq "mesh") {
        $module = "mesh.main"
    } else {
        $module = "services.$service.main"
    }

    $process = Start-Process -FilePath "python" -ArgumentList "-m", $module `
        -RedirectStandardOutput $logFile `
        -RedirectStandardError $logFile `
        -PassThru -WindowStyle Hidden

    $process.Id | Out-File $pidFile
    Write-Host "Started $service (PID: $($process.Id))"
}

Write-Host ""
Write-Host "BIOwerk services started!" -ForegroundColor Green
Write-Host "API Gateway: http://localhost:8080/docs"
Write-Host "Logs directory: $INSTALL_DIR\logs"
Write-Host ""
Write-Host "To stop services, run: .\biowerk-stop.ps1"
'@ | Out-File -FilePath $startScript -Encoding UTF8

    # Create stop script
    $stopScript = Join-Path $INSTALL_DIR "biowerk-stop.ps1"
    @'
# BIOwerk Stop Script
$INSTALL_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $INSTALL_DIR

Write-Host "Stopping BIOwerk services..."

Get-ChildItem "logs\*.pid" | ForEach-Object {
    $pid = Get-Content $_.FullName
    try {
        Stop-Process -Id $pid -Force
        Write-Host "Stopped process $pid"
    } catch {
        Write-Host "Process $pid not found (may have already stopped)"
    }
    Remove-Item $_.FullName
}

Write-Host "BIOwerk services stopped!" -ForegroundColor Green
'@ | Out-File -FilePath $stopScript -Encoding UTF8

    # Create status script
    $statusScript = Join-Path $INSTALL_DIR "biowerk-status.ps1"
    @'
# BIOwerk Status Script
$INSTALL_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $INSTALL_DIR

Write-Host "BIOwerk Service Status:"
Write-Host "======================"

$services = @("nucleus", "osteon", "myocyte", "synapse", "circadian", "chaperone", "mesh")

foreach ($service in $services) {
    $pidFile = "logs\$service.pid"
    if (Test-Path $pidFile) {
        $pid = Get-Content $pidFile
        try {
            $process = Get-Process -Id $pid -ErrorAction Stop
            Write-Host "✓ $service (PID: $pid) - RUNNING" -ForegroundColor Green
        } catch {
            Write-Host "✗ $service - STOPPED (stale PID file)" -ForegroundColor Red
        }
    } else {
        Write-Host "✗ $service - STOPPED" -ForegroundColor Red
    }
}
'@ | Out-File -FilePath $statusScript -Encoding UTF8

    Write-Status "Launcher scripts created"
}

# Create uninstall script
function Create-UninstallScript {
    $uninstallScript = Join-Path $INSTALL_DIR "uninstall.ps1"
    @"
# BIOwerk Uninstall Script
Write-Host "Uninstalling BIOwerk from: $INSTALL_DIR" -ForegroundColor Yellow
`$confirm = Read-Host "Are you sure? This will delete all data! (yes/no)"

if (`$confirm -eq "yes") {
    # Stop services
    `$stopScript = Join-Path "$INSTALL_DIR" "biowerk-stop.ps1"
    if (Test-Path `$stopScript) {
        & `$stopScript
    }

    # Remove installation directory
    Remove-Item -Path "$INSTALL_DIR" -Recurse -Force
    Write-Host "BIOwerk uninstalled successfully!" -ForegroundColor Green
} else {
    Write-Host "Uninstall cancelled."
}
"@ | Out-File -FilePath $uninstallScript -Encoding UTF8
}

# Main installation process
function Main {
    Write-Host "Installation directory: $INSTALL_DIR" -ForegroundColor Blue
    Write-Host ""

    Check-Requirements
    Create-InstallDir
    Create-VirtualEnv
    Create-Config
    Create-Launchers
    Create-UninstallScript

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Installation Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "BIOwerk has been installed to: $INSTALL_DIR"
    Write-Host ""
    Write-Host "To start BIOwerk:"
    Write-Host "  cd $INSTALL_DIR"
    Write-Host "  .\biowerk-start.ps1"
    Write-Host ""
    Write-Host "To check status:"
    Write-Host "  .\biowerk-status.ps1"
    Write-Host ""
    Write-Host "To stop BIOwerk:"
    Write-Host "  .\biowerk-stop.ps1"
    Write-Host ""
    Write-Host "API Documentation will be available at:"
    Write-Host "  http://localhost:8080/docs"
    Write-Host ""
}

# Run installation
Main
