# BIOwerk Electron Launcher

Cross-platform desktop application for managing BIOwerk services.

## Features

- **Visual Control Panel**: Start/stop/restart services
- **System Tray Integration**: Quick access from menu bar/taskbar
- **Service Monitoring**: Real-time health checks for all microservices
- **Log Viewer**: Stream logs from any service
- **Quick Links**: One-click access to dashboards and API docs
- **Configuration Management**: Easy access to settings
- **Docker Integration**: Automatic detection and setup

## Development

### Prerequisites

- Node.js 18+
- npm 9+
- Docker Desktop

### Setup

```bash
# Install dependencies
npm install

# Run in development mode
npm start
```

### Building

```bash
# Build for current platform
npm run build

# Build for specific platform
npm run build:mac      # macOS (requires macOS)
npm run build:win      # Windows
npm run build:linux    # Linux

# Build for all platforms
npm run build:all
```

### Project Structure

```
electron-launcher/
├── main.js              # Electron main process
├── index.html           # UI interface
├── package.json         # Dependencies and build config
├── assets/              # Icons and resources
│   ├── icon.icns        # macOS icon
│   ├── icon.ico         # Windows icon
│   ├── icon.png         # Linux icon
│   ├── tray-icon.png    # System tray icon
│   └── entitlements.mac.plist  # macOS entitlements
└── dist/                # Built applications (generated)
```

## Technologies

- **Electron**: Cross-platform desktop framework
- **Node.js**: Backend runtime
- **Docker**: Container management
- **Axios**: HTTP client for health checks

## Architecture

The launcher consists of:

1. **Main Process** (`main.js`):
   - Window management
   - System tray
   - IPC handlers
   - Docker integration

2. **Renderer Process** (`index.html`):
   - User interface
   - Service status display
   - Log viewer
   - Navigation

3. **IPC Communication**:
   - `start-services`: Start Docker Compose
   - `stop-services`: Stop all services
   - `restart-services`: Restart services
   - `check-status`: Check service health
   - `view-logs`: Stream service logs
   - `open-url`: Open external URLs
   - `open-config`: Open .env file

## Customization

### Changing Colors/Themes

Edit the `<style>` section in `index.html`:
```css
background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%);
```

### Adding Services

Update `servicesStatus` object in `main.js`:
```javascript
servicesStatus = {
  myservice: {
    name: 'My Service',
    url: 'http://localhost:9000/health',
    status: 'stopped'
  }
}
```

### Custom Icons

Replace files in `assets/` directory:
- `icon.icns` - macOS (512x512, .icns format)
- `icon.ico` - Windows (256x256, .ico format)
- `icon.png` - Linux (512x512, PNG)
- `tray-icon.png` - System tray (32x32, PNG)

Generate icons:
```bash
# macOS .icns from PNG
iconutil -c icns icon.iconset

# Windows .ico from PNG (requires ImageMagick)
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

## Troubleshooting

### Build Fails

**Missing dependencies:**
```bash
npm install
```

**Cross-platform build issues:**
Some targets require building on the native platform:
- macOS DMG requires macOS
- Windows requires Windows (or wine on Linux/macOS)

### App Won't Start

**Docker not found:**
Install Docker Desktop from https://docker.com

**Port conflicts:**
Check that ports 8080, 3000, 5432, 27017, 6379 are available

**Permissions:**
On Linux, ensure user is in `docker` group:
```bash
sudo usermod -aG docker $USER
```

### Development Mode Issues

**Hot reload not working:**
Restart with `npm start`

**Console errors:**
Open DevTools: View → Toggle Developer Tools

## Packaging Options

Configure in `package.json` under `build`:

```json
{
  "build": {
    "appId": "com.etech.biowerk",
    "productName": "BIOwerk",
    "dmg": { ... },
    "win": { ... },
    "linux": { ... }
  }
}
```

See [electron-builder docs](https://www.electron.build/) for all options.

## Code Signing

### macOS

Set environment variables:
```bash
export CSC_LINK=path/to/certificate.p12
export CSC_KEY_PASSWORD=password
export APPLE_ID=your@apple.id
export APPLE_ID_PASSWORD=app-specific-password
```

### Windows

Set environment variables:
```powershell
$env:CSC_LINK = "path\to\certificate.pfx"
$env:CSC_KEY_PASSWORD = "password"
```

## License

Proprietary - E-TECH PLAYTECH

## Support

For issues and questions:
- GitHub Issues: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues
- Documentation: ../README.md
