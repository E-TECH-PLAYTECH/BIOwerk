# Assets Directory

This directory contains icons and resources for the BIOwerk desktop application.

## Required Files

### Icons

You need to provide the following icon files:

1. **icon.icns** - macOS application icon
   - Format: Apple Icon Image (.icns)
   - Size: 512x512 base image
   - Contains multiple resolutions

2. **icon.ico** - Windows application icon
   - Format: Windows Icon (.ico)
   - Size: 256x256 base image
   - Contains multiple resolutions (256, 128, 64, 48, 32, 16)

3. **icon.png** - Linux application icon
   - Format: PNG
   - Size: 512x512 pixels
   - Transparent background recommended

4. **tray-icon.png** - System tray icon
   - Format: PNG
   - Size: 32x32 pixels
   - Should work on both light and dark backgrounds

### Creating Icons

#### From PNG Source

If you have a source PNG (512x512), you can generate all formats:

**macOS (.icns):**
```bash
# Create iconset directory
mkdir icon.iconset

# Generate all required sizes
sips -z 16 16     icon.png --out icon.iconset/icon_16x16.png
sips -z 32 32     icon.png --out icon.iconset/icon_16x16@2x.png
sips -z 32 32     icon.png --out icon.iconset/icon_32x32.png
sips -z 64 64     icon.png --out icon.iconset/icon_32x32@2x.png
sips -z 128 128   icon.png --out icon.iconset/icon_128x128.png
sips -z 256 256   icon.png --out icon.iconset/icon_128x128@2x.png
sips -z 256 256   icon.png --out icon.iconset/icon_256x256.png
sips -z 512 512   icon.png --out icon.iconset/icon_256x256@2x.png
sips -z 512 512   icon.png --out icon.iconset/icon_512x512.png
cp icon.png icon.iconset/icon_512x512@2x.png

# Convert to .icns
iconutil -c icns icon.iconset
```

**Windows (.ico) - Requires ImageMagick:**
```bash
convert icon.png -define icon:auto-resize=256,128,64,48,32,16 icon.ico
```

Or use online converters:
- https://convertio.co/png-ico/
- https://icoconvert.com/

**Linux (.png):**
Just use your source PNG at 512x512.

#### Design Guidelines

**General:**
- Use simple, recognizable shapes
- Avoid fine details (won't show at small sizes)
- Use high contrast
- Test on both light and dark backgrounds

**Color Scheme:**
- BIOwerk theme: Green (#4CAF50) with dark backgrounds
- Bio/DNA theme: Consider double helix, cell, molecular structures
- Professional and modern look

**Suggested Icon Concepts:**
1. DNA double helix
2. Cell with nucleus
3. Molecular structure
4. "B" lettermark with bio elements
5. Abstract geometric with biology theme

### Placeholder Icons

For development/testing, you can use these temporary icons:

**Create simple colored squares:**
```bash
# macOS/Linux
convert -size 512x512 xc:#4CAF50 -pointsize 200 -fill white -gravity center -annotate +0+0 "B" icon.png

# System tray (smaller)
convert -size 32x32 xc:#4CAF50 -pointsize 16 -fill white -gravity center -annotate +0+0 "B" tray-icon.png
```

**Or download open-source icons:**
- https://iconmonstr.com/
- https://thenounproject.com/
- https://www.flaticon.com/

## entitlements.mac.plist

This file is required for macOS code signing and defines the permissions the app needs:
- JIT compilation (for Node.js)
- Network access (for API calls)
- Automation (for opening URLs)

You generally don't need to modify this unless adding features that require additional permissions.

## Future Assets

You may want to add:
- **dmg-background.png** - Custom DMG installer background (800x400)
- **splash.png** - Splash screen while loading
- **about.html** - Custom about page
- **screenshots/** - App screenshots for marketing

## License

Icons should be either:
1. Created by you/your team
2. Licensed for commercial use
3. Open source with appropriate attribution

Document the source and license of all icons used.
