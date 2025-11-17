# BIOwerk Distribution & Packaging

This directory contains all the tools and scripts needed to build distributable packages of BIOwerk for macOS, Windows, and Linux.

## 📦 Distribution Options

BIOwerk can be distributed in three ways:

1. **Electron Desktop App** - Cross-platform GUI launcher (recommended)
2. **Platform-Specific Installers** - Native installers for each OS
3. **Docker Compose** - Traditional deployment (for servers)

## 🚀 Quick Start - Build All Packages

```bash
# Build all distribution packages
cd distribution
./build-all.sh

# Build with specific version
VERSION=1.2.3 ./build-all.sh

# Build only Electron apps
./build-all.sh --electron-only
```

Output will be in `distribution/output/`

## 📋 What Gets Built

### Electron Desktop Launcher (All Platforms)
- **macOS**: `.dmg` and `.app` bundle
- **Windows**: `.exe` installer and portable version
- **Linux**: `.AppImage`, `.deb`, `.rpm`, `.snap`

Features:
- System tray integration
- Service status monitoring
- One-click start/stop
- Log viewer
- Quick links to dashboards
- Auto-detection and installation of Docker

### Native Installers

#### macOS DMG
- Drag-to-Applications installer
- Double-click to launch
- Automatic Docker detection
- Desktop notifications

#### Windows Installer
- PowerShell-based installer
- Desktop and Start Menu shortcuts
- Automatic Docker Desktop installation
- System PATH integration

#### Linux Installer
- Bash script installer
- Supports: Ubuntu, Debian, Fedora, CentOS, Arch
- Desktop entry creation
- CLI command (`biowerk`)

## 🔨 Building Individual Packages

### Electron App (Cross-Platform)

```bash
cd distribution/electron-launcher

# Install dependencies
npm install

# Build for current platform
npm run build

# Build for specific platform
npm run build:mac      # macOS
npm run build:win      # Windows
npm run build:linux    # Linux

# Build for all platforms
npm run build:all
```

Requirements:
- Node.js 18+
- npm 9+

### macOS DMG

```bash
cd distribution/macos
./create-dmg.sh

# With specific version
VERSION=1.2.3 ./create-dmg.sh
```

Requirements:
- macOS 10.15+
- Xcode Command Line Tools
- `hdiutil` (included in macOS)

Output: `distribution/macos/dist/BIOwerk-{version}.dmg`

### Linux Packages

```bash
cd distribution/linux

# The installer is ready to use
# Package it with the app:
tar -czf biowerk-installer-linux.tar.gz install.sh ../..
```

Supported distributions:
- Ubuntu 20.04+
- Debian 10+
- Fedora 35+
- CentOS 8+
- Arch Linux

### Windows Packages

```powershell
cd distribution\windows

# The installer is ready to use
# Package it with the app:
Compress-Archive -Path install.ps1,..\..\* -DestinationPath biowerk-installer-windows.zip
```

Requirements:
- PowerShell 5.1+
- Administrator privileges

## 📥 Installation Instructions

### End Users - macOS

1. Download `BIOwerk-{version}.dmg`
2. Open the DMG file
3. Drag BIOwerk to Applications folder
4. Launch BIOwerk from Applications
5. First launch will:
   - Check for Docker (install if needed)
   - Create configuration file
   - Start services

**Alternative:** Download the Electron `.app` and double-click

### End Users - Windows

**Option 1: Electron Installer (Recommended)**
1. Download `BIOwerk-Setup-{version}.exe`
2. Double-click to install
3. Launch from Start Menu or Desktop

**Option 2: PowerShell Installer**
1. Download `biowerk-{version}-windows.zip`
2. Extract to a folder
3. Right-click `install.ps1`
4. Select "Run with PowerShell as Administrator"
5. Follow the prompts

### End Users - Linux

**Option 1: Electron AppImage (Recommended)**
1. Download `BIOwerk-{version}.AppImage`
2. Make executable: `chmod +x BIOwerk-{version}.AppImage`
3. Double-click or run: `./BIOwerk-{version}.AppImage`

**Option 2: Native Installer**
1. Download `biowerk-{version}-linux.tar.gz`
2. Extract: `tar -xzf biowerk-{version}-linux.tar.gz`
3. Run installer: `cd biowerk-{version} && sudo bash install.sh`
4. Launch: `biowerk` or find in Applications menu

**Option 3: Package Manager**
```bash
# Debian/Ubuntu
sudo dpkg -i biowerk_{version}_amd64.deb

# Fedora/CentOS
sudo rpm -i biowerk-{version}.x86_64.rpm

# Snap
sudo snap install biowerk_{version}_amd64.snap --classic
```

## 🎨 Customization

### App Icons

Replace these files before building:
- `electron-launcher/assets/icon.icns` (macOS, 512x512)
- `electron-launcher/assets/icon.ico` (Windows, 256x256)
- `electron-launcher/assets/icon.png` (Linux, 512x512)
- `electron-launcher/assets/tray-icon.png` (System tray, 32x32)

Create icons from PNG:
```bash
# macOS
iconutil -c icns icon.iconset

# Windows (requires ImageMagick)
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

### DMG Background

Replace `distribution/macos/dmg-background.png` with custom 800x400 image.

### Branding

Edit these files:
- `electron-launcher/index.html` - UI text and styling
- `electron-launcher/package.json` - App metadata
- `macos/create-dmg.sh` - DMG window layout
- `windows/install.ps1` - Installer messages

## 🔐 Code Signing & Notarization

### macOS

1. Get Apple Developer certificate
2. Set environment variables:
   ```bash
   export CSC_LINK=path/to/certificate.p12
   export CSC_KEY_PASSWORD=your_password
   export APPLE_ID=your@apple.id
   export APPLE_ID_PASSWORD=app-specific-password
   ```
3. Build will automatically sign and notarize

### Windows

1. Get code signing certificate
2. Set environment variables:
   ```powershell
   $env:CSC_LINK = "path\to\certificate.pfx"
   $env:CSC_KEY_PASSWORD = "your_password"
   ```
3. Build will automatically sign

## 📊 Build Artifacts Structure

```
distribution/output/
├── electron/
│   ├── BIOwerk-{version}.dmg           # macOS DMG
│   ├── BIOwerk-{version}.app           # macOS app
│   ├── BIOwerk-Setup-{version}.exe     # Windows installer
│   ├── BIOwerk-{version}.exe           # Windows portable
│   ├── BIOwerk-{version}.AppImage      # Linux AppImage
│   ├── biowerk_{version}_amd64.deb     # Debian/Ubuntu
│   ├── biowerk-{version}.x86_64.rpm    # Fedora/CentOS
│   └── biowerk_{version}_amd64.snap    # Snap
├── macos/
│   └── BIOwerk-{version}.dmg           # Native macOS DMG
├── linux/
│   └── biowerk-{version}-linux.tar.gz  # Linux installer
├── windows/
│   └── biowerk-{version}-windows.zip   # Windows installer
├── RELEASE_NOTES.md                     # Release documentation
└── SHA256SUMS.txt                       # Checksums
```

## 🧪 Testing Installers

### macOS
```bash
# Mount DMG
hdiutil attach output/macos/BIOwerk-1.0.0.dmg

# Test installation
cp -r /Volumes/BIOwerk/BIOwerk.app /Applications/

# Launch
open /Applications/BIOwerk.app
```

### Linux
```bash
# Test AppImage
chmod +x output/electron/BIOwerk-1.0.0.AppImage
./output/electron/BIOwerk-1.0.0.AppImage

# Test installer
cd output/linux
tar -xzf biowerk-1.0.0-linux.tar.gz
cd biowerk-1.0.0
sudo bash install.sh
```

### Windows
```powershell
# Test installer
.\output\electron\BIOwerk-Setup-1.0.0.exe

# Test portable
.\output\electron\BIOwerk-1.0.0.exe
```

## 🐛 Troubleshooting

### Build Fails - Missing Dependencies

**macOS:**
```bash
xcode-select --install
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install rpm fakeroot dpkg

# Fedora
sudo dnf install rpm-build dpkg
```

**Windows:**
Install Node.js from https://nodejs.org

### Electron Build Fails on Cross-Platform

Some platforms require native build:
- macOS DMG: Must build on macOS
- Windows installer: Can build on Linux/macOS with wine
- Linux packages: Can build on any platform

### Docker Not Detected After Install

User needs to:
1. Start Docker Desktop
2. Wait for it to be fully running
3. Restart BIOwerk

### App Won't Open - Security Warning (macOS)

If not code-signed:
```bash
xattr -cr /Applications/BIOwerk.app
```

Or: System Preferences → Security & Privacy → Allow

## 📚 Additional Resources

- [Electron Builder Docs](https://www.electron.build/)
- [macOS Packaging Guide](https://developer.apple.com/library/archive/documentation/CoreFoundation/Conceptual/CFBundles/BundleTypes/BundleTypes.html)
- [Windows Installer Best Practices](https://docs.microsoft.com/en-us/windows/win32/msi/installer-best-practices)
- [Linux Desktop Entry Spec](https://specifications.freedesktop.org/desktop-entry-spec/latest/)

## 🤝 Contributing

To improve the distribution system:

1. Test on your platform
2. Report issues
3. Submit PRs with improvements
4. Add support for more package formats

## 📝 Release Checklist

Before releasing:

- [ ] Update version in `package.json`
- [ ] Update version in `pyproject.toml`
- [ ] Update CHANGELOG
- [ ] Test installers on all platforms
- [ ] Generate release notes
- [ ] Create checksums
- [ ] Tag release in git
- [ ] Upload to GitHub Releases
- [ ] Update documentation

## 🔄 Automated Releases

For CI/CD integration:

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [macos-latest, windows-latest, ubuntu-latest]
    steps:
      - uses: actions/checkout@v3
      - name: Build
        run: cd distribution && ./build-all.sh
      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: ${{ matrix.os }}-build
          path: distribution/output/
```

## 📞 Support

For distribution/packaging issues:
- Open an issue on GitHub
- Include platform and error logs
- Attach build output if applicable
