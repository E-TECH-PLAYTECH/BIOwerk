#!/bin/bash
set -e

# BIOwerk Portable Installation Script
# This script installs BIOwerk from a portable archive

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIOWERK_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INSTALL_DIR="${BIOWERK_INSTALL_DIR:-$HOME/.biowerk}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  BIOwerk Portable Installation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print status messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check for required commands
check_requirements() {
    print_status "Checking system requirements..."

    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed. Please install Python 3.10 or higher."
        exit 1
    fi

    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        print_error "Python 3.10 or higher is required. Found: $PYTHON_VERSION"
        exit 1
    fi

    print_status "Python $PYTHON_VERSION found"

    # Check for pip
    if ! python3 -m pip --version &> /dev/null; then
        print_error "pip is not installed. Please install pip."
        exit 1
    fi

    # Check for venv
    if ! python3 -m venv --help &> /dev/null; then
        print_warning "python3-venv not found. Attempting to install..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y python3-venv
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3-venv
        else
            print_error "Could not install python3-venv. Please install it manually."
            exit 1
        fi
    fi
}

# Create installation directory
create_install_dir() {
    print_status "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"

    # Copy files
    print_status "Copying BIOwerk files..."
    if command -v rsync &> /dev/null; then
        rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
            --exclude='.pytest_cache' --exclude='venv' --exclude='node_modules' \
            "$BIOWERK_ROOT/" "$INSTALL_DIR/"
    else
        # Fallback to cp
        cp -r "$BIOWERK_ROOT/"* "$INSTALL_DIR/" 2>/dev/null || true
        # Clean up unwanted directories
        rm -rf "$INSTALL_DIR/.git" "$INSTALL_DIR/venv" "$INSTALL_DIR/node_modules" 2>/dev/null || true
        find "$INSTALL_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find "$INSTALL_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    fi
}

# Create virtual environment
create_virtualenv() {
    print_status "Creating Python virtual environment..."
    cd "$INSTALL_DIR"
    python3 -m venv venv

    print_status "Activating virtual environment..."
    source venv/bin/activate

    print_status "Upgrading pip..."
    pip install --upgrade pip setuptools wheel

    print_status "Installing BIOwerk dependencies..."
    pip install -r requirements.txt

    print_status "Installing BIOwerk in development mode..."
    pip install -e .
}

# Create configuration files
create_config() {
    print_status "Creating configuration files..."

    # Create data directories
    mkdir -p "$INSTALL_DIR/data/postgres"
    mkdir -p "$INSTALL_DIR/data/mongodb"
    mkdir -p "$INSTALL_DIR/data/redis"
    mkdir -p "$INSTALL_DIR/logs"

    # Create .env file if it doesn't exist
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        cat > "$INSTALL_DIR/.env" << 'EOF'
# BIOwerk Configuration
BIOWERK_ENV=development
LOG_LEVEL=INFO

# Database Configuration
DATABASE_URL=sqlite:///$INSTALL_DIR/data/biowerk.db
MONGODB_URL=mongodb://localhost:27017/biowerk
REDIS_URL=redis://localhost:6379/0

# LLM Configuration
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
USE_LOCAL_LLM=true
OLLAMA_BASE_URL=http://localhost:11434

# Service Ports
MESH_PORT=8080
NUCLEUS_PORT=8001
OSTEON_PORT=8002
MYOCYTE_PORT=8003
SYNAPSE_PORT=8004
CIRCADIAN_PORT=8005
CHAPERONE_PORT=8006

# Security
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
JWT_SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')

# Monitoring
ENABLE_METRICS=true
ENABLE_TRACING=false
EOF
        print_status "Created .env configuration file"
    else
        print_warning ".env file already exists, skipping..."
    fi
}

# Create launcher scripts
create_launchers() {
    print_status "Creating launcher scripts..."

    # Create start script
    cat > "$INSTALL_DIR/biowerk-start.sh" << 'EOF'
#!/bin/bash
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

# Load environment
set -a
source .env
set +a

# Activate virtual environment
source venv/bin/activate

# Start services
echo "Starting BIOwerk services..."

# Start services in background with logging
python -m matrix.database init &
sleep 2

python -m services.nucleus.main > logs/nucleus.log 2>&1 &
echo $! > logs/nucleus.pid

python -m services.osteon.main > logs/osteon.log 2>&1 &
echo $! > logs/osteon.pid

python -m services.myocyte.main > logs/myocyte.log 2>&1 &
echo $! > logs/myocyte.pid

python -m services.synapse.main > logs/synapse.log 2>&1 &
echo $! > logs/synapse.pid

python -m services.circadian.main > logs/circadian.log 2>&1 &
echo $! > logs/circadian.pid

python -m services.chaperone.main > logs/chaperone.log 2>&1 &
echo $! > logs/chaperone.pid

python -m mesh.main > logs/mesh.log 2>&1 &
echo $! > logs/mesh.pid

echo "BIOwerk services started!"
echo "API Gateway: http://localhost:8080/docs"
echo "Logs directory: $INSTALL_DIR/logs"
echo ""
echo "To stop services, run: ./biowerk-stop.sh"
EOF

    chmod +x "$INSTALL_DIR/biowerk-start.sh"

    # Create stop script
    cat > "$INSTALL_DIR/biowerk-stop.sh" << 'EOF'
#!/bin/bash
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

echo "Stopping BIOwerk services..."

for pidfile in logs/*.pid; do
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if ps -p $pid > /dev/null; then
            kill $pid
            echo "Stopped process $pid"
        fi
        rm "$pidfile"
    fi
done

echo "BIOwerk services stopped!"
EOF

    chmod +x "$INSTALL_DIR/biowerk-stop.sh"

    # Create status script
    cat > "$INSTALL_DIR/biowerk-status.sh" << 'EOF'
#!/bin/bash
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$INSTALL_DIR"

echo "BIOwerk Service Status:"
echo "======================"

services=("nucleus" "osteon" "myocyte" "synapse" "circadian" "chaperone" "mesh")

for service in "${services[@]}"; do
    pidfile="logs/${service}.pid"
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if ps -p $pid > /dev/null; then
            echo "✓ $service (PID: $pid) - RUNNING"
        else
            echo "✗ $service - STOPPED (stale PID file)"
        fi
    else
        echo "✗ $service - STOPPED"
    fi
done
EOF

    chmod +x "$INSTALL_DIR/biowerk-status.sh"

    print_status "Launcher scripts created"
}

# Create uninstall script
create_uninstall_script() {
    cat > "$INSTALL_DIR/uninstall.sh" << EOF
#!/bin/bash
echo "Uninstalling BIOwerk from: $INSTALL_DIR"
read -p "Are you sure? This will delete all data! (yes/no): " confirm

if [ "\$confirm" = "yes" ]; then
    # Stop services
    if [ -f "$INSTALL_DIR/biowerk-stop.sh" ]; then
        "$INSTALL_DIR/biowerk-stop.sh"
    fi

    # Remove installation directory
    rm -rf "$INSTALL_DIR"
    echo "BIOwerk uninstalled successfully!"
else
    echo "Uninstall cancelled."
fi
EOF

    chmod +x "$INSTALL_DIR/uninstall.sh"
}

# Main installation process
main() {
    echo -e "${BLUE}Installation directory: $INSTALL_DIR${NC}"
    echo ""

    check_requirements
    create_install_dir
    create_virtualenv
    create_config
    create_launchers
    create_uninstall_script

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "BIOwerk has been installed to: $INSTALL_DIR"
    echo ""
    echo "To start BIOwerk:"
    echo "  cd $INSTALL_DIR"
    echo "  ./biowerk-start.sh"
    echo ""
    echo "To check status:"
    echo "  ./biowerk-status.sh"
    echo ""
    echo "To stop BIOwerk:"
    echo "  ./biowerk-stop.sh"
    echo ""
    echo "API Documentation will be available at:"
    echo "  http://localhost:8080/docs"
    echo ""
}

# Run installation
main
