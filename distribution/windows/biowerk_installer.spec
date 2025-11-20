# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for BIOwerk Windows Installer
This creates a single-file executable installer
"""

block_cipher = None

# Collect all BIOwerk application files
import os
from pathlib import Path

biowerk_root = Path('..', '..').resolve()

# Files to include
datas = [
    (str(biowerk_root / '.env.example'), '.'),
    (str(biowerk_root / 'docker-compose.yml'), '.'),
    (str(biowerk_root / 'requirements.txt'), '.'),
    (str(biowerk_root / 'requirements-dev.txt'), '.'),
    (str(biowerk_root / 'README.md'), '.'),
]

# Directories to include
for dir_name in ['services', 'matrix', 'mesh', 'scripts', 'docs', 'k8s', 'alembic']:
    src_dir = biowerk_root / dir_name
    if src_dir.exists():
        datas.append((str(src_dir), dir_name))

a = Analysis(
    ['biowerk_installer.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
    ],
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
    name='BIOwerk-Installer-1.0.0',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed application
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path if you have one
    version_file=None,
)
