#!/usr/bin/env python3
"""
Build script for creating BIOwerk Windows .exe installer
Creates a lightweight installer that downloads/extracts files during installation
"""

import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path


def create_lightweight_installer():
    """Create a lightweight installer that embeds the ZIP archive"""

    print("Creating lightweight BIOwerk installer...")

    script_dir = Path(__file__).parent
    biowerk_root = script_dir.parent.parent
    dist_dir = script_dir.parent / "output" / "windows"
    dist_dir.mkdir(parents=True, exist_ok=True)

    # Create a simple installer script that will be compiled
    installer_script = script_dir / "biowerk_simple_installer.py"

    installer_code = '''#!/usr/bin/env python3
"""
BIOwerk Simple Windows Installer
Embedded installer with application files
"""

import os
import sys
import shutil
import zipfile
import subprocess
import tempfile
from pathlib import Path
import base64
import io

# The application ZIP is embedded as base64 at the end of this script
# This will be replaced during build

def check_admin():
    """Check if running as admin"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def check_docker():
    """Check Docker installation"""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def main():
    print("=" * 60)
    print("  BIOwerk Windows Installer v1.0.0")
    print("=" * 60)
    print()

    if not check_admin():
        print("WARNING: Not running as administrator!")
        print("Please run this installer as Administrator for full functionality.")
        input("Press Enter to continue anyway, or Ctrl+C to exit...")
        print()

    print("[1/5] Checking requirements...")

    if not check_docker():
        print("Docker is not installed!")
        print("Please install Docker Desktop from:")
        print("https://www.docker.com/products/docker-desktop")
        print()
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            sys.exit(1)

    install_dir = Path(os.environ.get('ProgramFiles', 'C:\\\\Program Files')) / "BIOwerk"
    print(f"\\n[2/5] Installation directory: {install_dir}")

    response = input("Change installation directory? (y/n): ")
    if response.lower() == 'y':
        new_dir = input("Enter directory path: ").strip()
        if new_dir:
            install_dir = Path(new_dir)

    print(f"\\n[3/5] Creating directory: {install_dir}")
    install_dir.mkdir(parents=True, exist_ok=True)

    # Extract embedded archive
    print("[4/5] Extracting application files...")
    print("This may take a moment...")

    # Look for the ZIP file in the same directory as the exe
    exe_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    zip_path = exe_dir / "biowerk-app.zip"

    if not zip_path.exists():
        # Try to find it in the distribution output
        alt_path = exe_dir / ".." / ".." / "output" / "windows" / "biowerk-1.0.0-windows.zip"
        if Path(alt_path).exists():
            zip_path = Path(alt_path).resolve()

    if zip_path.exists():
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            for i, member in enumerate(members):
                if i % 100 == 0:
                    print(f"  Extracted {i}/{len(members)} files...")
                zip_ref.extract(member, install_dir.parent)

        # Move files from subdirectory if needed
        extracted_dir = install_dir.parent / "biowerk-1.0.0"
        if extracted_dir.exists():
            app_dir = extracted_dir / "app"
            if app_dir.exists():
                for item in app_dir.iterdir():
                    dest = install_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.move(str(item), str(dest))
                    else:
                        shutil.move(str(item), str(dest))
                shutil.rmtree(extracted_dir)
    else:
        print(f"ERROR: Could not find application archive!")
        print(f"Looked for: {zip_path}")
        input("Press Enter to exit...")
        sys.exit(1)

    print("  Extraction complete!")

    # Create .env from example
    env_file = install_dir / ".env"
    env_example = install_dir / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy2(env_example, env_file)
        print("  Created .env configuration file")

    # Create launcher
    print("\\n[5/5] Creating shortcuts...")
    launcher_bat = install_dir / "biowerk-launcher.bat"
    launcher_content = f"""@echo off
cd /d "{install_dir}"
echo Starting BIOwerk...
docker compose up -d
timeout /t 5 /nobreak >nul
start http://localhost:8080/docs
echo BIOwerk is running at http://localhost:8080
pause
"""
    launcher_bat.write_text(launcher_content)

    # Create desktop shortcut
    desktop = Path.home() / "Desktop" / "BIOwerk.lnk"
    ps_cmd = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{desktop}")
$Shortcut.TargetPath = "{launcher_bat}"
$Shortcut.WorkingDirectory = "{install_dir}"
$Shortcut.Description = "BIOwerk"
$Shortcut.Save()
"""
    try:
        subprocess.run(['powershell', '-Command', ps_cmd], capture_output=True, timeout=10)
        print("  Created desktop shortcut")
    except:
        print("  Could not create desktop shortcut")

    print()
    print("=" * 60)
    print("  Installation Complete!")
    print("=" * 60)
    print()
    print(f"Installation directory: {install_dir}")
    print("Desktop shortcut: BIOwerk")
    print()
    print("To start BIOwerk:")
    print("  - Double-click the BIOwerk desktop shortcut")
    print(f"  - Or run: {launcher_bat}")
    print()
    print("API Documentation: http://localhost:8080/docs")
    print("Grafana Dashboard: http://localhost:3000")
    print()
    input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\\nInstallation cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\\nERROR: {e}")
        import traceback
        traceback.print_exc()
        input("Press Enter to exit...")
        sys.exit(1)
'''

    installer_script.write_text(installer_code)
    print(f"✓ Created installer script: {installer_script}")

    # Create PyInstaller spec for simple installer
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{installer_script.name}'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BIOwerk-Setup-1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Console application for progress output
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''

    spec_file = script_dir / "biowerk_simple_installer.spec"
    spec_file.write_text(spec_content)
    print(f"✓ Created PyInstaller spec: {spec_file}")

    return installer_script, spec_file


def build_exe():
    """Build the .exe using PyInstaller"""

    print("\nBuilding Windows .exe installer with PyInstaller...")

    script_dir = Path(__file__).parent
    installer_script, spec_file = create_lightweight_installer()

    # Build the exe
    cmd = [
        'pyinstaller',
        '--clean',
        '--noconfirm',
        str(spec_file)
    ]

    print(f"\nRunning: {' '.join(cmd)}")
    print("This may take a few minutes...\n")

    result = subprocess.run(cmd, cwd=script_dir)

    if result.returncode == 0:
        # Find the generated exe
        dist_dir = script_dir / "dist"
        exe_files = list(dist_dir.glob("*.exe"))

        if exe_files:
            exe_file = exe_files[0]
            print(f"\n✓ Successfully created: {exe_file}")
            print(f"  Size: {exe_file.stat().st_size / 1024 / 1024:.1f} MB")

            # Copy to output directory
            output_dir = script_dir.parent / "output" / "windows"
            output_dir.mkdir(parents=True, exist_ok=True)

            output_exe = output_dir / exe_file.name
            shutil.copy2(exe_file, output_exe)
            print(f"  Copied to: {output_exe}")

            # Also copy the ZIP file so it's in the same directory
            zip_file = output_dir / "biowerk-1.0.0-windows.zip"
            if zip_file.exists():
                app_zip = output_dir / "biowerk-app.zip"
                shutil.copy2(zip_file, app_zip)
                print(f"  Copied archive: {app_zip}")

            return output_exe
        else:
            print("\nERROR: Could not find generated .exe file")
            return None
    else:
        print("\nERROR: PyInstaller build failed")
        return None


if __name__ == "__main__":
    try:
        exe_path = build_exe()

        if exe_path:
            print("\n" + "=" * 60)
            print("  Build Complete!")
            print("=" * 60)
            print(f"\nInstaller: {exe_path}")
            print("\nTo use:")
            print("  1. Copy both files to target machine:")
            print(f"     - {exe_path.name}")
            print(f"     - biowerk-app.zip (or biowerk-1.0.0-windows.zip)")
            print("  2. Run the .exe as Administrator")
            print("  3. Follow the installation prompts")
        else:
            print("\nBuild failed!")
            sys.exit(1)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
