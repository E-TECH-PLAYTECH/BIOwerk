@echo off
:: BIOwerk Windows Installer Batch Script
:: This acts as a user-friendly installer without requiring PowerShell execution policy changes

setlocal enabledelayedexpansion

title BIOwerk Installer v1.0.0

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo ============================================================
    echo   ADMINISTRATOR PRIVILEGES REQUIRED
    echo ============================================================
    echo.
    echo This installer requires administrator privileges.
    echo Please right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

cls
echo ============================================================
echo   BIOwerk Windows Installer v1.0.0
echo ============================================================
echo.
echo Welcome to BIOwerk Setup!
echo.
echo This will install BIOwerk - Bio-Themed Agentic AI Office Suite
echo.
pause

:: Check if Docker is installed
echo.
echo [1/6] Checking Docker Desktop...
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo Docker Desktop is not installed!
    echo.
    echo BIOwerk requires Docker Desktop to run.
    echo Please install Docker Desktop from:
    echo   https://www.docker.com/products/docker-desktop
    echo.
    set /p CONTINUE="Continue installation anyway? (Y/N): "
    if /i not "!CONTINUE!"=="Y" (
        echo Installation cancelled.
        pause
        exit /b 1
    )
) else (
    echo Docker Desktop is installed.
)

:: Check if Docker is running
docker info >nul 2>&1
if %errorLevel% neq 0 (
    echo.
    echo WARNING: Docker Desktop is not running.
    echo Please start Docker Desktop and run this installer again.
    echo.
    set /p START_DOCKER="Would you like to start Docker Desktop now? (Y/N): "
    if /i "!START_DOCKER!"=="Y" (
        echo Starting Docker Desktop...
        start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
        echo.
        echo Please wait for Docker to start completely, then
        pause
    ) else (
        echo Installation cancelled.
        pause
        exit /b 1
    )
)

:: Set installation directory
set "DEFAULT_INSTALL_DIR=%ProgramFiles%\BIOwerk"
echo.
echo [2/6] Setting installation directory...
echo Default installation directory: %DEFAULT_INSTALL_DIR%
echo.
set /p CUSTOM_DIR="Press Enter to accept, or type a new path: "

if "!CUSTOM_DIR!"=="" (
    set "INSTALL_DIR=%DEFAULT_INSTALL_DIR%"
) else (
    set "INSTALL_DIR=!CUSTOM_DIR!"
)

echo Installing to: !INSTALL_DIR!

:: Create installation directory
echo.
echo [3/6] Creating installation directory...
if not exist "!INSTALL_DIR!" (
    mkdir "!INSTALL_DIR!"
    if %errorLevel% neq 0 (
        echo ERROR: Could not create directory: !INSTALL_DIR!
        pause
        exit /b 1
    )
)
echo Directory created: !INSTALL_DIR!

:: Copy application files
echo.
echo [4/6] Copying application files...
echo This may take a moment...

:: Check if we're in the extracted installer directory
if exist "app\" (
    echo Copying from app directory...
    xcopy /E /I /Y /Q "app\*" "!INSTALL_DIR!\" >nul
) else (
    :: We're in the root distribution directory
    cd /d "%~dp0..\.."
    echo Copying from source directory...

    :: Copy main files
    for %%F in (*.yml *.ini *.txt *.md *.toml *.cfg *.example *.sh) do (
        if exist "%%F" copy /Y "%%F" "!INSTALL_DIR!\" >nul 2>&1
    )

    :: Copy directories
    for %%D in (services matrix mesh scripts docs k8s alembic helm monitoring pgbouncer) do (
        if exist "%%D\" (
            echo   Copying %%D...
            xcopy /E /I /Y /Q "%%D" "!INSTALL_DIR!\%%D\" >nul
        )
    )
)

:: Create .env from example
if not exist "!INSTALL_DIR!\.env" (
    if exist "!INSTALL_DIR!\.env.example" (
        copy "!INSTALL_DIR!\.env.example" "!INSTALL_DIR!\.env" >nul
        echo Created .env configuration file
    )
)

:: Create launcher script
echo.
echo [5/6] Creating launcher and shortcuts...

set "LAUNCHER=!INSTALL_DIR!\biowerk-launcher.bat"

(
echo @echo off
echo cd /d "!INSTALL_DIR!"
echo.
echo echo ============================================================
echo echo   Starting BIOwerk Services
echo echo ============================================================
echo echo.
echo.
echo echo Checking Docker...
echo docker info ^>nul 2^>^&1
echo if %%errorlevel%% neq 0 ^(
echo     echo Docker is not running!
echo     echo Please start Docker Desktop and try again.
echo     pause
echo     exit /b 1
echo ^)
echo.
echo echo Starting services...
echo docker compose up -d
echo.
echo echo Waiting for services to initialize...
echo timeout /t 10 /nobreak ^>nul
echo.
echo echo Opening web interfaces...
echo start http://localhost:8080/docs
echo timeout /t 2 /nobreak ^>nul
echo start http://localhost:3000
echo.
echo echo ============================================================
echo echo   BIOwerk is now running!
echo echo ============================================================
echo echo.
echo echo   API Gateway:        http://localhost:8080
echo echo   API Documentation:  http://localhost:8080/docs
echo echo   Grafana Dashboard:  http://localhost:3000 ^(admin/admin^)
echo echo   Prometheus:         http://localhost:9090
echo echo.
echo echo To stop services: docker compose down
echo echo.
echo pause
) > "!LAUNCHER!"

:: Create desktop shortcut using PowerShell
echo Creating desktop shortcut...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\BIOwerk.lnk'); $Shortcut.TargetPath = '!LAUNCHER!'; $Shortcut.WorkingDirectory = '!INSTALL_DIR!'; $Shortcut.Description = 'BIOwerk - Bio-Themed Agentic AI Office Suite'; $Shortcut.Save()" >nul 2>&1

:: Create Start Menu shortcut
echo Creating Start Menu shortcut...
powershell -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%ProgramData%\Microsoft\Windows\Start Menu\Programs\BIOwerk.lnk'); $Shortcut.TargetPath = '!LAUNCHER!'; $Shortcut.WorkingDirectory = '!INSTALL_DIR!'; $Shortcut.Description = 'BIOwerk - Bio-Themed Agentic AI Office Suite'; $Shortcut.Save()" >nul 2>&1

:: Create uninstaller
echo.
echo [6/6] Creating uninstaller...

set "UNINSTALLER=!INSTALL_DIR!\uninstall.bat"

(
echo @echo off
echo title BIOwerk Uninstaller
echo.
echo echo ============================================================
echo echo   BIOwerk Uninstaller
echo echo ============================================================
echo echo.
echo echo This will remove BIOwerk from your system.
echo echo.
echo set /p CONFIRM="Are you sure you want to uninstall? (Y/N): "
echo if /i not "%%CONFIRM%%"=="Y" (
echo     echo Uninstall cancelled.
echo     pause
echo     exit /b 0
echo )
echo.
echo echo Stopping services...
echo cd /d "!INSTALL_DIR!"
echo docker compose down -v
echo.
echo echo Removing installation directory...
echo cd /d "%%TEMP%%"
echo rmdir /s /q "!INSTALL_DIR!"
echo.
echo echo Removing shortcuts...
echo del "%%USERPROFILE%%\Desktop\BIOwerk.lnk" 2^>nul
echo del "%%ProgramData%%\Microsoft\Windows\Start Menu\Programs\BIOwerk.lnk" 2^>nul
echo.
echo echo ============================================================
echo echo   BIOwerk has been uninstalled
echo echo ============================================================
echo echo.
echo pause
) > "!UNINSTALLER!"

:: Installation complete
cls
echo ============================================================
echo   Installation Complete!
echo ============================================================
echo.
echo BIOwerk has been successfully installed to:
echo   !INSTALL_DIR!
echo.
echo Shortcuts created:
echo   - Desktop: BIOwerk
echo   - Start Menu: BIOwerk
echo.
echo To start BIOwerk:
echo   1. Double-click the BIOwerk shortcut on your desktop
echo   2. Or run: !LAUNCHER!
echo.
echo After starting, access BIOwerk at:
echo   - API Gateway: http://localhost:8080
echo   - API Documentation: http://localhost:8080/docs
echo   - Grafana Dashboard: http://localhost:3000 (admin/admin)
echo.
echo Configuration file: !INSTALL_DIR!\.env
echo To uninstall: Run !UNINSTALLER!
echo.
echo ============================================================
echo.
set /p LAUNCH="Would you like to start BIOwerk now? (Y/N): "
if /i "!LAUNCH!"=="Y" (
    start "" "!LAUNCHER!"
)

echo.
echo Thank you for installing BIOwerk!
echo.
pause

endlocal
