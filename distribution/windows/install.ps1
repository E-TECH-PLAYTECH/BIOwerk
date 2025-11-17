# BIOwerk Windows Installer
# Requires PowerShell 5.1 or later

#Requires -RunAsAdministrator

param(
    [string]$InstallDir = "$env:ProgramFiles\BIOwerk",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check if Docker is installed
function Test-DockerInstalled {
    try {
        $dockerVersion = docker --version
        Write-Info "Docker is already installed: $dockerVersion"
        return $true
    }
    catch {
        Write-Warning "Docker is not installed"
        return $false
    }
}

# Install Docker Desktop
function Install-Docker {
    Write-Info "Downloading Docker Desktop..."

    $dockerInstallerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    $dockerInstallerPath = "$env:TEMP\DockerDesktopInstaller.exe"

    try {
        Invoke-WebRequest -Uri $dockerInstallerUrl -OutFile $dockerInstallerPath -UseBasicParsing

        Write-Info "Installing Docker Desktop... This may take several minutes."
        Start-Process -FilePath $dockerInstallerPath -ArgumentList "install", "--quiet" -Wait

        Remove-Item $dockerInstallerPath -Force

        Write-Success "Docker Desktop installed successfully!"
        Write-Warning "Please start Docker Desktop and run this installer again."
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"

        exit 0
    }
    catch {
        Write-Error "Failed to install Docker: $_"
        Write-Info "Please download and install Docker Desktop manually from:"
        Write-Info "https://www.docker.com/products/docker-desktop"
        exit 1
    }
}

# Check if Docker is running
function Test-DockerRunning {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        Write-Warning "Docker is not running"
        return $false
    }
}

# Install BIOwerk
function Install-BIOwerk {
    Write-Info "Installing BIOwerk to $InstallDir..."

    # Create installation directory
    if (!(Test-Path $InstallDir)) {
        New-Item -ItemType Directory -Path $InstallDir | Out-Null
    }

    # Copy files
    $sourceDir = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    if (Test-Path $sourceDir) {
        Write-Info "Copying application files..."

        # Copy all files except git, distribution, and tests
        Get-ChildItem -Path $sourceDir -Exclude ".git", "distribution", "tests" |
            Copy-Item -Destination $InstallDir -Recurse -Force
    }

    # Create .env file if it doesn't exist
    $envFile = Join-Path $InstallDir ".env"
    $envExample = Join-Path $InstallDir ".env.example"

    if (!(Test-Path $envFile) -and (Test-Path $envExample)) {
        Write-Info "Creating default configuration..."
        Copy-Item $envExample $envFile
    }

    # Create launcher script
    $launcherScript = @'
@echo off
cd /d "%~dp0"

echo Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is not running. Please start Docker Desktop.
    msg "%username%" "Docker is not running. Please start Docker Desktop and try again."
    exit /b 1
)

echo Starting BIOwerk services...
docker compose up -d

echo Waiting for services to start...
timeout /t 10 /nobreak >nul

echo Opening web interfaces...
start http://localhost:8080/docs
start http://localhost:3000

echo BIOwerk is running!
msg "%username%" "BIOwerk is running! Access API at http://localhost:8080"
'@

    $launcherPath = Join-Path $InstallDir "biowerk-launcher.bat"
    $launcherScript | Out-File -FilePath $launcherPath -Encoding ASCII

    # Create desktop shortcut
    $WshShell = New-Object -ComObject WScript.Shell
    $desktopPath = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktopPath "BIOwerk.lnk"
    $shortcut = $WshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $launcherPath
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "BIOwerk - Bio-Themed Agentic Office Suite"
    $shortcut.Save()

    # Create Start Menu shortcut
    $startMenuPath = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
    $startMenuShortcut = Join-Path $startMenuPath "BIOwerk.lnk"
    $shortcut = $WshShell.CreateShortcut($startMenuShortcut)
    $shortcut.TargetPath = $launcherPath
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "BIOwerk - Bio-Themed Agentic Office Suite"
    $shortcut.Save()

    # Add to PATH
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if ($currentPath -notlike "*$InstallDir*") {
        [Environment]::SetEnvironmentVariable("Path", "$currentPath;$InstallDir", "Machine")
        Write-Info "Added BIOwerk to system PATH"
    }

    Write-Success "BIOwerk installed successfully!"
}

# Create uninstaller
function Create-Uninstaller {
    $uninstallerScript = @"
# BIOwerk Uninstaller
#Requires -RunAsAdministrator

Write-Host "Uninstalling BIOwerk..." -ForegroundColor Yellow

# Stop services
Set-Location "$InstallDir"
docker compose down

# Remove installation directory
Remove-Item -Path "$InstallDir" -Recurse -Force

# Remove shortcuts
Remove-Item -Path "$env:USERPROFILE\Desktop\BIOwerk.lnk" -ErrorAction SilentlyContinue
Remove-Item -Path "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\BIOwerk.lnk" -ErrorAction SilentlyContinue

# Remove from PATH
`$currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
`$newPath = `$currentPath -replace [regex]::Escape(";$InstallDir"), ""
[Environment]::SetEnvironmentVariable("Path", `$newPath, "Machine")

Write-Host "BIOwerk uninstalled successfully!" -ForegroundColor Green
Read-Host "Press Enter to exit"
"@

    $uninstallerPath = Join-Path $InstallDir "uninstall.ps1"
    $uninstallerScript | Out-File -FilePath $uninstallerPath -Encoding UTF8

    Write-Info "Created uninstaller at: $uninstallerPath"
}

# Main installation flow
function Main {
    Write-Host "========================================"
    Write-Host "  BIOwerk Windows Installer v$Version"
    Write-Host "========================================"
    Write-Host ""

    # Check for Docker
    if (!(Test-DockerInstalled)) {
        $response = Read-Host "Would you like to install Docker Desktop? (y/n)"
        if ($response -eq "y" -or $response -eq "Y") {
            Install-Docker
        }
        else {
            Write-Error "Docker is required. Please install Docker and run this script again."
            exit 1
        }
    }

    # Check if Docker is running
    if (!(Test-DockerRunning)) {
        Write-Warning "Docker Desktop is installed but not running."
        Write-Info "Please start Docker Desktop and run this installer again."
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        exit 0
    }

    # Install BIOwerk
    Install-BIOwerk

    # Create uninstaller
    Create-Uninstaller

    Write-Host ""
    Write-Host "========================================"
    Write-Host "   Installation Complete! 🎉"
    Write-Host "========================================"
    Write-Host ""
    Write-Host "To start BIOwerk:"
    Write-Host "  - Double-click the 'BIOwerk' shortcut on your desktop"
    Write-Host "  - Or find 'BIOwerk' in the Start Menu"
    Write-Host "  - Or run 'biowerk-launcher.bat' from command line"
    Write-Host ""
    Write-Host "Configuration: $InstallDir\.env"
    Write-Host "To uninstall: Run $InstallDir\uninstall.ps1 as Administrator"
    Write-Host ""

    Read-Host "Press Enter to exit"
}

# Run main installation
try {
    Main
}
catch {
    Write-Error "Installation failed: $_"
    Read-Host "Press Enter to exit"
    exit 1
}
