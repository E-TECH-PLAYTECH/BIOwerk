#!/usr/bin/env python3
"""
BIOwerk Windows Installer - Graphical Installation Wizard
Creates a user-friendly installer with GUI for Windows platforms.
"""

import os
import sys
import shutil
import subprocess
import zipfile
import tempfile
import urllib.request
from pathlib import Path
import json

# Try to import tkinter for GUI
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    HAS_GUI = True
except ImportError:
    HAS_GUI = False
    print("GUI not available, falling back to console mode")


class BIOwerkInstaller:
    """BIOwerk Installation Wizard"""

    def __init__(self):
        self.version = "1.0.0"
        self.install_dir = Path(os.environ.get('ProgramFiles', 'C:\\Program Files')) / "BIOwerk"
        self.portable_mode = False
        self.install_docker = False

    def check_admin(self):
        """Check if running with admin privileges"""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def check_docker_installed(self):
        """Check if Docker Desktop is installed"""
        try:
            result = subprocess.run(
                ['docker', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def check_docker_running(self):
        """Check if Docker is running"""
        try:
            result = subprocess.run(
                ['docker', 'info'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

    def check_python(self):
        """Check if Python 3.10+ is installed"""
        try:
            result = subprocess.run(
                ['python', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version_str = result.stdout.strip().split()[1]
                major, minor = map(int, version_str.split('.')[:2])
                return (major, minor) >= (3, 10)
        except:
            pass
        return False

    def download_docker_desktop(self, progress_callback=None):
        """Download Docker Desktop installer"""
        url = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
        temp_dir = Path(tempfile.gettempdir())
        installer_path = temp_dir / "DockerDesktopInstaller.exe"

        if progress_callback:
            progress_callback("Downloading Docker Desktop...")

        try:
            urllib.request.urlretrieve(url, installer_path)
            return installer_path
        except Exception as e:
            return None

    def install_docker_desktop(self, installer_path, progress_callback=None):
        """Install Docker Desktop"""
        if progress_callback:
            progress_callback("Installing Docker Desktop... This may take several minutes.")

        try:
            subprocess.run(
                [str(installer_path), 'install', '--quiet'],
                check=True,
                timeout=600
            )
            return True
        except:
            return False

    def extract_application_files(self, progress_callback=None):
        """Extract BIOwerk application files"""
        if progress_callback:
            progress_callback("Extracting application files...")

        # Create installation directory
        self.install_dir.mkdir(parents=True, exist_ok=True)

        # In a real installer, the ZIP would be embedded in the .exe
        # For now, we'll look for it in the same directory
        script_dir = Path(__file__).parent
        app_archive = script_dir / "biowerk-app.zip"

        if app_archive.exists():
            with zipfile.ZipFile(app_archive, 'r') as zip_ref:
                zip_ref.extractall(self.install_dir)
        else:
            # Copy files from parent directory
            source_dir = script_dir.parent.parent
            ignore_patterns = shutil.ignore_patterns(
                '.git', '__pycache__', '*.pyc', '.pytest_cache',
                'venv', 'node_modules', 'distribution', 'tests'
            )

            for item in source_dir.iterdir():
                if item.name not in ['.git', 'distribution', 'tests', '__pycache__']:
                    dest = self.install_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest, ignore=ignore_patterns)
                    else:
                        shutil.copy2(item, dest)

        return True

    def create_env_file(self):
        """Create default .env file"""
        env_file = self.install_dir / ".env"
        env_example = self.install_dir / ".env.example"

        if not env_file.exists() and env_example.exists():
            shutil.copy2(env_example, env_file)

    def create_shortcuts(self, progress_callback=None):
        """Create desktop and start menu shortcuts"""
        if progress_callback:
            progress_callback("Creating shortcuts...")

        launcher_bat = self.install_dir / "biowerk-launcher.bat"

        # Create launcher batch file
        launcher_content = f"""@echo off
cd /d "{self.install_dir}"

echo Checking Docker...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is not running. Please start Docker Desktop.
    pause
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
echo API: http://localhost:8080
echo Grafana: http://localhost:3000
pause
"""
        launcher_bat.write_text(launcher_content)

        # Create shortcuts using PowerShell
        desktop = Path.home() / "Desktop"
        start_menu = Path(os.environ.get('ProgramData', 'C:\\ProgramData')) / "Microsoft" / "Windows" / "Start Menu" / "Programs"

        for shortcut_dir in [desktop, start_menu]:
            shortcut_path = shortcut_dir / "BIOwerk.lnk"
            ps_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
$Shortcut.TargetPath = "{launcher_bat}"
$Shortcut.WorkingDirectory = "{self.install_dir}"
$Shortcut.Description = "BIOwerk - Bio-Themed Agentic Office Suite"
$Shortcut.Save()
"""
            try:
                subprocess.run(
                    ['powershell', '-Command', ps_script],
                    capture_output=True,
                    timeout=10
                )
            except:
                pass

    def create_uninstaller(self):
        """Create uninstaller script"""
        uninstaller_path = self.install_dir / "uninstall.ps1"

        uninstaller_content = f"""# BIOwerk Uninstaller
#Requires -RunAsAdministrator

Write-Host "Uninstalling BIOwerk..." -ForegroundColor Yellow

# Stop services
Set-Location "{self.install_dir}"
docker compose down -v

# Remove installation directory
Remove-Item -Path "{self.install_dir}" -Recurse -Force -ErrorAction SilentlyContinue

# Remove shortcuts
Remove-Item -Path "$env:USERPROFILE\\Desktop\\BIOwerk.lnk" -ErrorAction SilentlyContinue
Remove-Item -Path "$env:ProgramData\\Microsoft\\Windows\\Start Menu\\Programs\\BIOwerk.lnk" -ErrorAction SilentlyContinue

Write-Host "BIOwerk uninstalled successfully!" -ForegroundColor Green
Read-Host "Press Enter to exit"
"""
        uninstaller_path.write_text(uninstaller_content)

    def run_console_install(self):
        """Run console-based installation"""
        print("=" * 60)
        print(f"  BIOwerk Windows Installer v{self.version}")
        print("=" * 60)
        print()

        # Check admin
        if not self.check_admin():
            print("WARNING: Not running as administrator.")
            print("Some features may not work correctly.")
            print()

        # Check Docker
        print("[1/6] Checking Docker...")
        if not self.check_docker_installed():
            response = input("Docker is not installed. Install it? (y/n): ")
            if response.lower() == 'y':
                print("Please download and install Docker Desktop manually from:")
                print("https://www.docker.com/products/docker-desktop")
                input("Press Enter when Docker is installed...")

        if not self.check_docker_running():
            print("Docker is not running. Please start Docker Desktop.")
            input("Press Enter when Docker is running...")

        # Get install directory
        print()
        print(f"[2/6] Installation directory: {self.install_dir}")
        response = input("Change installation directory? (y/n): ")
        if response.lower() == 'y':
            new_dir = input("Enter new directory: ")
            self.install_dir = Path(new_dir)

        # Extract files
        print()
        print("[3/6] Extracting application files...")
        self.extract_application_files()

        # Create env file
        print("[4/6] Creating configuration...")
        self.create_env_file()

        # Create shortcuts
        print("[5/6] Creating shortcuts...")
        self.create_shortcuts()

        # Create uninstaller
        print("[6/6] Creating uninstaller...")
        self.create_uninstaller()

        print()
        print("=" * 60)
        print("  Installation Complete!")
        print("=" * 60)
        print()
        print("To start BIOwerk:")
        print("  - Double-click the 'BIOwerk' shortcut on your desktop")
        print("  - Or find 'BIOwerk' in the Start Menu")
        print()
        print(f"Configuration: {self.install_dir / '.env'}")
        print(f"To uninstall: Run {self.install_dir / 'uninstall.ps1'} as Administrator")
        print()
        input("Press Enter to exit...")

    def run_gui_install(self):
        """Run GUI-based installation"""
        root = tk.Tk()
        root.title(f"BIOwerk Installer v{self.version}")
        root.geometry("600x500")
        root.resizable(False, False)

        # Variables
        install_dir_var = tk.StringVar(value=str(self.install_dir))
        install_docker_var = tk.BooleanVar(value=False)

        # Header
        header_frame = tk.Frame(root, bg="#2c3e50", height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        title_label = tk.Label(
            header_frame,
            text="BIOwerk Installation Wizard",
            font=("Arial", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=20)

        # Content
        content_frame = tk.Frame(root, padx=30, pady=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Welcome message
        welcome_text = f"""Welcome to BIOwerk v{self.version} Setup

This wizard will guide you through the installation of BIOwerk,
a bio-themed agentic AI office suite.

Click Next to continue."""

        welcome_label = tk.Label(
            content_frame,
            text=welcome_text,
            justify=tk.LEFT,
            wraplength=500
        )
        welcome_label.pack(pady=20)

        # Installation directory
        dir_frame = tk.LabelFrame(content_frame, text="Installation Directory", padx=10, pady=10)
        dir_frame.pack(fill=tk.X, pady=10)

        dir_entry = tk.Entry(dir_frame, textvariable=install_dir_var, width=50)
        dir_entry.pack(side=tk.LEFT, padx=5)

        def browse_directory():
            directory = filedialog.askdirectory(initialdir=str(self.install_dir))
            if directory:
                install_dir_var.set(directory)

        browse_button = tk.Button(dir_frame, text="Browse...", command=browse_directory)
        browse_button.pack(side=tk.LEFT)

        # Options
        options_frame = tk.LabelFrame(content_frame, text="Options", padx=10, pady=10)
        options_frame.pack(fill=tk.X, pady=10)

        docker_check = tk.Checkbutton(
            options_frame,
            text="Install Docker Desktop (if not already installed)",
            variable=install_docker_var
        )
        docker_check.pack(anchor=tk.W)

        # Progress
        progress_frame = tk.Frame(content_frame)
        progress_frame.pack(fill=tk.X, pady=20)

        progress_label = tk.Label(progress_frame, text="", fg="blue")
        progress_label.pack()

        progress_bar = ttk.Progressbar(
            progress_frame,
            mode='indeterminate',
            length=500
        )

        # Buttons
        button_frame = tk.Frame(root, pady=10)
        button_frame.pack(fill=tk.X)

        def start_installation():
            self.install_dir = Path(install_dir_var.get())
            self.install_docker = install_docker_var.get()

            # Disable buttons
            install_button.config(state=tk.DISABLED)
            cancel_button.config(state=tk.DISABLED)

            # Show progress
            progress_bar.pack()
            progress_bar.start()

            def update_progress(message):
                progress_label.config(text=message)
                root.update()

            try:
                # Check Docker
                if self.install_docker and not self.check_docker_installed():
                    update_progress("Docker installation not supported in GUI mode yet.")
                    messagebox.showwarning(
                        "Docker Required",
                        "Please install Docker Desktop manually from:\n"
                        "https://www.docker.com/products/docker-desktop\n\n"
                        "Then run this installer again."
                    )
                    root.destroy()
                    return

                # Extract files
                update_progress("Extracting application files...")
                self.extract_application_files(update_progress)

                # Create env
                update_progress("Creating configuration...")
                self.create_env_file()

                # Create shortcuts
                update_progress("Creating shortcuts...")
                self.create_shortcuts(update_progress)

                # Create uninstaller
                update_progress("Creating uninstaller...")
                self.create_uninstaller()

                progress_bar.stop()
                progress_bar.pack_forget()

                messagebox.showinfo(
                    "Installation Complete",
                    f"BIOwerk has been successfully installed!\n\n"
                    f"Installation directory: {self.install_dir}\n\n"
                    f"You can start BIOwerk from:\n"
                    f"  - Desktop shortcut\n"
                    f"  - Start Menu\n\n"
                    f"API Documentation: http://localhost:8080/docs\n"
                    f"Grafana Dashboard: http://localhost:3000"
                )

                root.destroy()

            except Exception as e:
                progress_bar.stop()
                progress_bar.pack_forget()
                messagebox.showerror("Installation Error", f"Installation failed:\n\n{str(e)}")
                install_button.config(state=tk.NORMAL)
                cancel_button.config(state=tk.NORMAL)

        install_button = tk.Button(
            button_frame,
            text="Install",
            command=start_installation,
            width=15,
            bg="#27ae60",
            fg="white",
            font=("Arial", 10, "bold")
        )
        install_button.pack(side=tk.RIGHT, padx=10)

        cancel_button = tk.Button(
            button_frame,
            text="Cancel",
            command=root.destroy,
            width=15
        )
        cancel_button.pack(side=tk.RIGHT)

        root.mainloop()

    def run(self):
        """Run the installer"""
        if HAS_GUI and sys.platform == 'win32':
            try:
                self.run_gui_install()
            except Exception as e:
                print(f"GUI failed: {e}")
                print("Falling back to console mode...")
                self.run_console_install()
        else:
            self.run_console_install()


if __name__ == "__main__":
    installer = BIOwerkInstaller()
    installer.run()
