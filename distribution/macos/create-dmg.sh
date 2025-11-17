#!/bin/bash
# Script to create macOS DMG installer for BIOwerk

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_NAME="BIOwerk"
VERSION="${VERSION:-1.0.0}"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
APP_BUNDLE="${APP_NAME}.app"
BUILD_DIR="$SCRIPT_DIR/build"
DIST_DIR="$SCRIPT_DIR/dist"

echo "Building BIOwerk DMG installer v${VERSION}..."

# Clean previous builds
rm -rf "$BUILD_DIR" "$DIST_DIR"
mkdir -p "$BUILD_DIR" "$DIST_DIR"

# Create .app bundle structure
echo "Creating .app bundle..."
mkdir -p "$BUILD_DIR/$APP_BUNDLE/Contents/"{MacOS,Resources,SharedSupport}

# Copy application files
echo "Copying application files..."
cp -r "$PROJECT_ROOT"/* "$BUILD_DIR/$APP_BUNDLE/Contents/SharedSupport/" 2>/dev/null || true

# Exclude unwanted directories
rm -rf "$BUILD_DIR/$APP_BUNDLE/Contents/SharedSupport/"{.git,distribution,tests}

# Create Info.plist
cat > "$BUILD_DIR/$APP_BUNDLE/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>BIOwerk</string>
    <key>CFBundleExecutable</key>
    <string>BIOwerk</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.etech.biowerk</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>BIOwerk</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>VERSION_PLACEHOLDER</string>
    <key>CFBundleVersion</key>
    <string>VERSION_PLACEHOLDER</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
</dict>
</plist>
EOF

# Replace version placeholder
sed -i '' "s/VERSION_PLACEHOLDER/$VERSION/g" "$BUILD_DIR/$APP_BUNDLE/Contents/Info.plist" 2>/dev/null || \
sed -i "s/VERSION_PLACEHOLDER/$VERSION/g" "$BUILD_DIR/$APP_BUNDLE/Contents/Info.plist"

# Create launcher script
cat > "$BUILD_DIR/$APP_BUNDLE/Contents/MacOS/BIOwerk" <<'EOFLAUNCH'
#!/bin/bash
# BIOwerk Launcher

RESOURCES_DIR="$(cd "$(dirname "$0")/../SharedSupport" && pwd)"
cd "$RESOURCES_DIR"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    osascript -e 'display dialog "Docker is not installed. Please install Docker Desktop from https://docker.com" buttons {"OK"} default button 1 with title "BIOwerk" with icon caution'
    open "https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    osascript -e 'display dialog "Docker is not running. Please start Docker Desktop and try again." buttons {"OK"} default button 1 with title "BIOwerk" with icon caution'
    open -a "Docker"
    exit 1
fi

# Check for .env file
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        osascript -e 'display dialog "Configuration file created. Please edit .env file in the BIOwerk directory with your settings, then restart the application." buttons {"OK"} default button 1 with title "BIOwerk" with icon note'
        open -a TextEdit .env
        exit 0
    fi
fi

# Launch the control panel in default browser
osascript -e 'display notification "Starting BIOwerk services..." with title "BIOwerk"'

# Start services in background
docker compose up -d &> /tmp/biowerk-startup.log

# Wait for services to be ready
sleep 10

# Open web interface
open "http://localhost:8080/docs"
open "http://localhost:3000"  # Grafana

osascript -e 'display notification "BIOwerk is running! Access the API at http://localhost:8080" with title "BIOwerk"'
EOFLAUNCH

chmod +x "$BUILD_DIR/$APP_BUNDLE/Contents/MacOS/BIOwerk"

# Create app icon (placeholder - should be replaced with actual icon)
cat > "$BUILD_DIR/$APP_BUNDLE/Contents/Resources/AppIcon.icns" <<'EOFICON'
# Placeholder icon file
# Replace with actual .icns file
EOFICON

# Create README for the DMG
cat > "$BUILD_DIR/README.txt" <<'EOFREADME'
BIOwerk - Bio-Themed Agentic Office Suite

Installation:
1. Drag BIOwerk.app to your Applications folder
2. Install Docker Desktop if not already installed (https://docker.com)
3. Double-click BIOwerk.app to launch

First-time setup:
- The application will create a .env configuration file
- Edit the configuration file with your settings
- Restart the application

Usage:
- API Documentation: http://localhost:8080/docs
- Monitoring Dashboard: http://localhost:3000 (Grafana)
- Default credentials are in the .env file

For more information, visit: https://github.com/E-TECH-PLAYTECH/BIOwerk
EOFREADME

# Create DMG using hdiutil
echo "Creating DMG..."

# Create temporary DMG
hdiutil create -volname "$APP_NAME" -srcfolder "$BUILD_DIR" -ov -format UDRW "$BUILD_DIR/temp.dmg"

# Mount the DMG
device=$(hdiutil attach -readwrite -noverify -noautoopen "$BUILD_DIR/temp.dmg" | egrep '^/dev/' | sed 1q | awk '{print $1}')
volume="/Volumes/$APP_NAME"

# Wait for mount
sleep 2

# Create symbolic link to Applications
ln -s /Applications "$volume/Applications"

# Set custom background (optional, requires background image)
# mkdir "$volume/.background"
# cp "$SCRIPT_DIR/dmg-background.png" "$volume/.background/background.png"

# Set DMG window appearance
echo '
   tell application "Finder"
     tell disk "'$APP_NAME'"
           open
           set current view of container window to icon view
           set toolbar visible of container window to false
           set statusbar visible of container window to false
           set the bounds of container window to {100, 100, 800, 500}
           set viewOptions to the icon view options of container window
           set arrangement of viewOptions to not arranged
           set icon size of viewOptions to 128
           set position of item "'$APP_BUNDLE'" of container window to {180, 180}
           set position of item "Applications" of container window to {480, 180}
           set position of item "README.txt" of container window to {330, 350}
           close
           open
           update without registering applications
           delay 2
     end tell
   end tell
' | osascript || true

# Unmount
sync
hdiutil detach "$device"

# Convert to compressed DMG
hdiutil convert "$BUILD_DIR/temp.dmg" -format UDZO -o "$DIST_DIR/$DMG_NAME"

# Cleanup
rm -f "$BUILD_DIR/temp.dmg"

echo "✅ DMG created: $DIST_DIR/$DMG_NAME"
echo "Size: $(du -h "$DIST_DIR/$DMG_NAME" | cut -f1)"
