# BIOwerk - Distribution Guide

> **Easy installation for end users - Double-click or drag-and-drop!**

BIOwerk is now available as a distributable desktop application with easy installation for macOS, Windows, and Linux.

## 🎯 For End Users

### macOS Installation

**Option 1: DMG Installer (Recommended)**
1. Download `BIOwerk-{version}.dmg` from releases
2. Double-click the DMG file
3. Drag BIOwerk icon to Applications folder
4. Launch BIOwerk from Applications

**Option 2: Direct App**
1. Download the `.app` file
2. Move to Applications folder
3. Double-click to launch

### Windows Installation

**Option 1: Electron Installer (Recommended)**
1. Download `BIOwerk-Setup-{version}.exe`
2. Double-click the installer
3. Follow installation wizard
4. Launch from Start Menu or Desktop shortcut

**Option 2: Manual Installation**
1. Download `biowerk-{version}-windows.zip`
2. Extract the ZIP file
3. Right-click `install.ps1` → "Run with PowerShell as Administrator"
4. Follow the prompts

### Linux Installation

**Option 1: AppImage (Recommended)**
1. Download `BIOwerk-{version}.AppImage`
2. Make executable: `chmod +x BIOwerk-{version}.AppImage`
3. Double-click or run: `./BIOwerk-{version}.AppImage`

**Option 2: Package Manager**
```bash
# Debian/Ubuntu
sudo dpkg -i biowerk_{version}_amd64.deb

# Fedora/RHEL
sudo rpm -i biowerk-{version}.x86_64.rpm

# Snap
sudo snap install biowerk_{version}_amd64.snap --classic
```

**Option 3: Manual Installation**
```bash
tar -xzf biowerk-{version}-linux.tar.gz
cd biowerk-{version}
sudo bash install.sh
```

## 🚀 First Time Setup

After installation:

1. **Launch BIOwerk** from your applications menu or desktop
2. **Docker Check**: The app will check if Docker is installed
   - If not installed, it will offer to install it automatically
   - Or download from: https://docker.com
3. **Configuration**: A default `.env` file will be created
   - Edit if you need to customize settings (API keys, passwords, etc.)
4. **Start Services**: Click "Start Services" in the control panel
5. **Access**: Services will be available at:
   - API Documentation: http://localhost:8080/docs
   - Monitoring Dashboard: http://localhost:3000

## ✨ Features

The desktop launcher provides:

- **Visual Control Panel**: Start/stop services with one click
- **Service Monitoring**: Real-time status of all microservices
- **System Tray**: Quick access from menu bar/taskbar
- **Log Viewer**: See what's happening in real-time
- **Quick Links**: One-click access to dashboards and API docs
- **Configuration Editor**: Easy access to settings

## 🔧 Configuration

Configuration file location:
- **macOS**: `/Applications/BIOwerk.app/Contents/SharedSupport/.env`
- **Windows**: `C:\Program Files\BIOwerk\.env`
- **Linux**: `~/.biowerk/.env` or `/opt/biowerk/.env`

Key settings:
```bash
# Database
POSTGRES_PASSWORD=your_secure_password
MONGO_INITDB_ROOT_PASSWORD=your_secure_password

# LLM Providers (choose one or more)
LLM_PROVIDER=ollama  # or openai, anthropic, deepseek
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key

# Security
JWT_SECRET_KEY=your_jwt_secret
ENCRYPTION_MASTER_KEY=your_encryption_key

# Monitoring
GRAFANA_ADMIN_PASSWORD=your_grafana_password
```

## 📊 Accessing Services

Once running, access:

| Service | URL | Description |
|---------|-----|-------------|
| **Mesh Gateway** | http://localhost:8080/docs | Main API documentation |
| **Grafana** | http://localhost:3000 | Monitoring dashboards |
| **Prometheus** | http://localhost:9090 | Metrics database |
| **Osteon Writer** | http://localhost:8001 | Document agent |
| **Myocyte Analysis** | http://localhost:8002 | Spreadsheet agent |
| **Synapse Presentation** | http://localhost:8003 | Visualization agent |

## 🛠️ Troubleshooting

### Docker Not Found
- **macOS**: Install Docker Desktop from https://docker.com
- **Windows**: Install Docker Desktop from https://docker.com
- **Linux**: Installer will offer to install Docker automatically

### Services Won't Start
1. Check Docker is running
2. Check `.env` file has required passwords set
3. View logs in the "Logs" tab of the control panel
4. Ensure ports 8080, 3000, 5432, 27017, 6379 are not in use

### Configuration Issues
Click "Settings" → "Open .env File" in the control panel to edit configuration

### Port Conflicts
If default ports are in use, edit `.env` and change port mappings

## 🗑️ Uninstallation

### macOS
1. Quit BIOwerk
2. Stop services: `docker compose down`
3. Delete `/Applications/BIOwerk.app`
4. Delete data: `docker volume prune`

Or run: `/Applications/BIOwerk.app/Contents/SharedSupport/uninstall.sh`

### Windows
1. Quit BIOwerk
2. Run `C:\Program Files\BIOwerk\uninstall.ps1` as Administrator
3. Or uninstall via "Add/Remove Programs"

### Linux
```bash
# If installed via package manager
sudo apt remove biowerk    # Debian/Ubuntu
sudo rpm -e biowerk         # Fedora/RHEL
sudo snap remove biowerk    # Snap

# If installed via script
~/.biowerk/uninstall.sh
# or
/opt/biowerk/uninstall.sh
```

## 📖 Documentation

Full documentation available at:
- **GitHub**: https://github.com/E-TECH-PLAYTECH/BIOwerk
- **API Docs**: http://localhost:8080/docs (when running)

## 🆘 Support

Need help?
1. Check the logs in the control panel
2. Open an issue: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues
3. Read the README: https://github.com/E-TECH-PLAYTECH/BIOwerk

## 🔄 Updates

To update BIOwerk:
1. Download the latest version
2. Stop services in the control panel
3. Install the new version (will replace the old one)
4. Start services

Your data and configuration will be preserved.

## 📋 Requirements

**Minimum System Requirements:**
- **CPU**: 2 cores (4 recommended)
- **RAM**: 4GB (8GB recommended)
- **Disk**: 10GB free space
- **OS**:
  - macOS 10.15 or later
  - Windows 10/11 (64-bit)
  - Linux kernel 4.4+ (Ubuntu 20.04+, Debian 10+, Fedora 35+)

**Software Requirements:**
- Docker Desktop (will be installed if missing)
- Modern web browser for accessing dashboards

## 🎓 Quick Start Guide

1. **Install** using your platform's method above
2. **Launch** BIOwerk from applications
3. **Start** services via the control panel
4. **Explore** the API at http://localhost:8080/docs
5. **Monitor** at http://localhost:3000
6. **Build** your first document with Osteon:
   ```bash
   curl -X POST http://localhost:8080/v1/osteon/draft \
     -H 'Content-Type: application/json' \
     -d '{"topic": "Machine Learning Basics", "style": "educational"}'
   ```

Enjoy using BIOwerk! 🧬
