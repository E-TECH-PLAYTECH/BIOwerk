#!/bin/bash
# BIOwerk Linux Installer
# Supports: Ubuntu, Debian, Fedora, CentOS, Arch Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.biowerk}"
VERSION="${VERSION:-1.0.0}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
    else
        DISTRO="unknown"
    fi
    echo "$DISTRO"
}

# Check if Docker is installed
check_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker is already installed: $(docker --version)"
        return 0
    else
        log_warn "Docker is not installed"
        return 1
    fi
}

# Install Docker
install_docker() {
    log_info "Installing Docker..."
    DISTRO=$(detect_distro)

    case $DISTRO in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y \
                ca-certificates \
                curl \
                gnupg \
                lsb-release

            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$DISTRO/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

            echo \
              "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO \
              $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            ;;

        fedora)
            sudo dnf -y install dnf-plugins-core
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
            sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo systemctl start docker
            sudo systemctl enable docker
            ;;

        centos|rhel)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
            sudo systemctl start docker
            sudo systemctl enable docker
            ;;

        arch)
            sudo pacman -Sy --noconfirm docker docker-compose
            sudo systemctl start docker
            sudo systemctl enable docker
            ;;

        *)
            log_error "Unsupported distribution: $DISTRO"
            log_info "Please install Docker manually from https://docker.com"
            exit 1
            ;;
    esac

    # Add user to docker group
    sudo usermod -aG docker $USER
    log_info "Docker installed successfully!"
    log_warn "You may need to log out and back in for group changes to take effect"
}

# Install BIOwerk
install_biowerk() {
    log_info "Installing BIOwerk to $INSTALL_DIR..."

    # Create installation directory
    mkdir -p "$INSTALL_DIR"

    # Copy files
    if [ -d "$SCRIPT_DIR/../../" ]; then
        log_info "Copying application files..."
        cp -r "$SCRIPT_DIR/../../"/* "$INSTALL_DIR/" 2>/dev/null || true
        rm -rf "$INSTALL_DIR"/{.git,distribution,tests}
    fi

    # Create .env file if it doesn't exist
    if [ ! -f "$INSTALL_DIR/.env" ] && [ -f "$INSTALL_DIR/.env.example" ]; then
        log_info "Creating default configuration..."
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    fi

    # Create desktop entry
    log_info "Creating desktop entry..."
    mkdir -p "$HOME/.local/share/applications"
    cat > "$HOME/.local/share/applications/biowerk.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=BIOwerk
Comment=Bio-Themed Agentic Office Suite
Exec=$INSTALL_DIR/biowerk-launcher.sh
Icon=$INSTALL_DIR/assets/icon.png
Terminal=false
Categories=Development;Utility;
EOF

    # Create launcher script
    cat > "$INSTALL_DIR/biowerk-launcher.sh" <<'EOFLAUNCH'
#!/bin/bash
BIOWERK_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BIOWERK_DIR"

# Check if Docker is running
if ! docker info &> /dev/null; then
    zenity --error --text="Docker is not running. Please start Docker and try again." 2>/dev/null || \
    notify-send "BIOwerk" "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Start services
notify-send "BIOwerk" "Starting services..."
docker compose up -d

# Wait for services
sleep 5

# Open browser
xdg-open "http://localhost:8080/docs" &
xdg-open "http://localhost:3000" &

notify-send "BIOwerk" "Services started! Access API at http://localhost:8080"
EOFLAUNCH

    chmod +x "$INSTALL_DIR/biowerk-launcher.sh"

    # Create CLI command
    log_info "Creating CLI command..."
    sudo ln -sf "$INSTALL_DIR/biowerk-launcher.sh" /usr/local/bin/biowerk 2>/dev/null || \
        ln -sf "$INSTALL_DIR/biowerk-launcher.sh" "$HOME/.local/bin/biowerk"

    log_info "✅ BIOwerk installed successfully!"
}

# Create uninstaller
create_uninstaller() {
    cat > "$INSTALL_DIR/uninstall.sh" <<'EOFUNINSTALL'
#!/bin/bash
BIOWERK_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Uninstalling BIOwerk..."

# Stop services
cd "$BIOWERK_DIR"
docker compose down

# Remove files
rm -rf "$BIOWERK_DIR"

# Remove desktop entry
rm -f "$HOME/.local/share/applications/biowerk.desktop"

# Remove CLI command
sudo rm -f /usr/local/bin/biowerk 2>/dev/null || rm -f "$HOME/.local/bin/biowerk"

echo "✅ BIOwerk uninstalled successfully!"
EOFUNINSTALL

    chmod +x "$INSTALL_DIR/uninstall.sh"
}

# Main installation flow
main() {
    echo "========================================"
    echo "   BIOwerk Linux Installer v${VERSION}"
    echo "========================================"
    echo ""

    # Check for Docker
    if ! check_docker; then
        read -p "Would you like to install Docker? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_docker
        else
            log_error "Docker is required. Please install Docker and run this script again."
            exit 1
        fi
    fi

    # Install BIOwerk
    install_biowerk

    # Create uninstaller
    create_uninstaller

    echo ""
    echo "========================================"
    echo "   Installation Complete! 🎉"
    echo "========================================"
    echo ""
    echo "To start BIOwerk:"
    echo "  - Run 'biowerk' from terminal"
    echo "  - Or find 'BIOwerk' in your applications menu"
    echo ""
    echo "Configuration: $INSTALL_DIR/.env"
    echo "To uninstall: $INSTALL_DIR/uninstall.sh"
    echo ""
}

main
