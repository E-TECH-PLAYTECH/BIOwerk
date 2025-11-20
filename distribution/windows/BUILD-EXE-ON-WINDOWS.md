# Building a True Windows .exe Installer

This guide explains how to build a true Windows .exe installer on a Windows machine.

## Why Build on Windows?

PyInstaller and similar tools create executables for the platform they run on. Since the build server is Linux, it cannot create Windows .exe files directly. To create a Windows .exe, you need to build on Windows.

## Prerequisites

1. **Windows 10/11** (64-bit)
2. **Python 3.10 or higher** - https://www.python.org/downloads/
3. **Git** (optional) - https://git-scm.com/download/win

## Method 1: Using PyInstaller (Recommended)

### Step 1: Install Python and PyInstaller

```powershell
# Open PowerShell as Administrator

# Install PyInstaller
pip install pyinstaller
```

### Step 2: Get the Source Code

```powershell
# Clone the repository
git clone https://github.com/E-TECH-PLAYTECH/BIOwerk.git
cd BIOwerk\distribution\windows

# Or download and extract the ZIP
```

### Step 3: Build the .exe

```powershell
# Run the build script
python build_exe.py
```

This will create:
- `dist\BIOwerk-Setup-1.0.0.exe` - The installer executable

### Step 4: Test the Installer

```powershell
# Run the installer
.\dist\BIOwerk-Setup-1.0.0.exe
```

---

## Method 2: Using Inno Setup (Professional Installer)

Inno Setup creates professional Windows installers with advanced features.

### Step 1: Install Inno Setup

Download and install from: https://jrsoftware.org/isdl.php

### Step 2: Create Inno Setup Script

Create `biowerk-setup.iss`:

```ini
[Setup]
AppName=BIOwerk
AppVersion=1.0.0
AppPublisher=E-TECH PLAYTECH
AppPublisherURL=https://github.com/E-TECH-PLAYTECH/BIOwerk
DefaultDirName={autopf}\BIOwerk
DefaultGroupName=BIOwerk
OutputBaseFilename=BIOwerk-Installer-1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".git\*,distribution\*,tests\*,__pycache__\*,*.pyc"

[Icons]
Name: "{group}\BIOwerk"; Filename: "{app}\biowerk-launcher.bat"; WorkingDir: "{app}"
Name: "{autodesktop}\BIOwerk"; Filename: "{app}\biowerk-launcher.bat"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\biowerk-launcher.bat"; Description: "{cm:LaunchProgram,BIOwerk}"; Flags: nowait postinstall skipifsilent
```

### Step 3: Compile the Installer

1. Open Inno Setup Compiler
2. File → Open → Select `biowerk-setup.iss`
3. Build → Compile
4. Output will be in `Output\BIOwerk-Installer-1.0.0.exe`

---

## Method 3: Using NSIS (Nullsoft Scriptable Install System)

NSIS is used by many popular applications.

### Step 1: Install NSIS

Download from: https://nsis.sourceforge.io/Download

### Step 2: Create NSIS Script

Create `biowerk-installer.nsi`:

```nsis
; BIOwerk NSIS Installer Script

!define APP_NAME "BIOwerk"
!define APP_VERSION "1.0.0"
!define APP_PUBLISHER "E-TECH PLAYTECH"
!define APP_EXE "biowerk-launcher.bat"

; Include Modern UI
!include "MUI2.nsh"

; General
Name "${APP_NAME}"
OutFile "BIOwerk-Setup-${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES\${APP_NAME}"
RequestExecutionLevel admin

; Interface Settings
!define MUI_ABORTWARNING
!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\modern-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\modern-uninstall.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Installer Sections
Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy files (exclude certain directories)
    File /r /x .git /x distribution /x tests /x __pycache__ "..\..\*.*"

    ; Create shortcuts
    CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
    CreateDirectory "$SMPROGRAMS\${APP_NAME}"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateShortcut "$SMPROGRAMS\${APP_NAME}\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    ; Registry entries for Add/Remove Programs
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                     "DisplayName" "${APP_NAME}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" \
                     "UninstallString" "$INSTDIR\Uninstall.exe"
SectionEnd

; Uninstaller Section
Section "Uninstall"
    ; Stop services
    ExecWait 'docker compose down -v' $0

    ; Remove files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    Delete "$DESKTOP\${APP_NAME}.lnk"
    RMDir /r "$SMPROGRAMS\${APP_NAME}"

    ; Remove registry entries
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
SectionEnd
```

### Step 3: Compile

Right-click `biowerk-installer.nsi` → Compile NSIS Script

---

## Method 4: Using Batch to EXE Converter

For a quick solution without Python:

### Option A: Bat To Exe Converter

1. Download: https://bat-to-exe-converter.en.softonic.com/
2. Open the tool
3. Load `SETUP.bat`
4. Configure options:
   - Architecture: x64
   - Include files: Check all application files
   - Icon: Select custom icon (optional)
5. Click "Compile"

### Option B: Advanced BAT to EXE Converter

1. Download: http://www.battoexeconverter.com/
2. Load `SETUP.bat`
3. Set options:
   - 64-bit: Yes
   - Invisible application: No
   - Embed files: Select ZIP archive
4. Convert

---

## Method 5: Using Electron Builder (GUI Installer)

The repository already has an Electron-based installer configured.

### Step 1: Install Node.js

Download from: https://nodejs.org/ (LTS version)

### Step 2: Build Electron App

```powershell
cd distribution\electron-launcher

# Install dependencies
npm install

# Build for Windows
npm run build:win
```

This creates:
- `dist\BIOwerk-Setup-1.0.0.exe` - NSIS installer
- `dist\BIOwerk-1.0.0.exe` - Portable executable

---

## Comparison of Methods

| Method | Pros | Cons | Size |
|--------|------|------|------|
| **PyInstaller** | Easy, Python-based | Requires Python | ~7-10 MB |
| **Inno Setup** | Professional, small | Requires manual script | ~5-8 MB |
| **NSIS** | Industry standard | Complex scripting | ~5-8 MB |
| **Bat to EXE** | Very simple | Limited features | ~2-5 MB |
| **Electron** | Modern GUI | Large size | ~50-100 MB |

---

## Recommended Approach

For the best result, we recommend:

1. **For developers**: Use PyInstaller (easy and automated)
2. **For distribution**: Use Inno Setup or NSIS (professional installers)
3. **For GUI launcher**: Use Electron Builder (modern, cross-platform)

---

## Testing the Installer

After building:

1. **Test on a clean Windows VM**
2. **Verify Docker detection works**
3. **Check shortcuts are created**
4. **Test the uninstaller**
5. **Scan with antivirus** (some AVs flag PyInstaller exes)

---

## Signing the Installer (Optional but Recommended)

To avoid Windows SmartScreen warnings:

1. Get a code signing certificate
2. Sign the .exe:

```powershell
# Using SignTool from Windows SDK
signtool sign /f certificate.pfx /p password /t http://timestamp.digicert.com BIOwerk-Setup-1.0.0.exe
```

---

## Alternative: Provide the Batch Installer

Instead of a .exe, you can provide:

1. **SETUP.bat** - Users can right-click → "Run as administrator"
2. **Benefits**:
   - No compilation needed
   - No antivirus false positives
   - Users can inspect the code
   - Smaller download

---

## Quick Start for Users (No Build Required)

If you don't want to build an .exe, users can:

1. Download `biowerk-1.0.0-windows.zip`
2. Extract the archive
3. Right-click `SETUP.bat`
4. Select "Run as administrator"

This provides the same functionality as an .exe installer!

---

## Need Help?

- **GitHub Issues**: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues
- **Documentation**: See `docs/` directory

---

**Note**: The `SETUP.bat` file in this directory provides a full installation experience without requiring compilation. Consider providing this as the primary installation method, with .exe as an optional alternative.
