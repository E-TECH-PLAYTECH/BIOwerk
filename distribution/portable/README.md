# BIOwerk Portable Installation

This directory contains scripts to create and install BIOwerk as a portable application without requiring Docker.

## Overview

The portable installation allows you to run BIOwerk on any system with Python 3.10+ without needing Docker or complex dependencies. It's perfect for:

- **Quick testing and evaluation**
- **Development environments without Docker**
- **Lightweight deployments**
- **CI/CD environments**
- **Restricted environments where Docker isn't available**

## Building Portable Archives

### From the Distribution Root

```bash
cd distribution
./build-all.sh --portable-only
```

Or build everything including portable:

```bash
cd distribution
VERSION=1.0.0 ./build-all.sh
```

### From This Directory

**Linux/macOS:**
```bash
./build-portable.sh
```

**Windows:**
```powershell
.\build-portable.ps1
```

This will create:
- `biowerk-portable-{version}.tar.gz` (for Linux/macOS)
- `biowerk-portable-{version}.zip` (for all platforms)
- Checksum files (SHA256, MD5)

## Installation

### Linux/macOS

1. Extract the archive:
   ```bash
   tar -xzf biowerk-portable-1.0.0.tar.gz
   cd biowerk-portable-1.0.0
   ```

2. Run the installation script:
   ```bash
   ./install.sh
   ```

3. Or use quick-start (installs and starts in one command):
   ```bash
   ./quick-start.sh
   ```

### Windows

1. Extract the ZIP archive

2. Open PowerShell in the extracted directory

3. Run the installation script:
   ```powershell
   .\install.ps1
   ```

4. Or use quick-start:
   ```powershell
   .\quick-start.ps1
   ```

## Custom Installation Directory

By default, BIOwerk installs to:
- **Linux/macOS**: `~/.biowerk`
- **Windows**: `%USERPROFILE%\.biowerk`

To specify a custom location:

**Linux/macOS:**
```bash
export BIOWERK_INSTALL_DIR=/opt/biowerk
./install.sh
```

**Windows:**
```powershell
$env:BIOWERK_INSTALL_DIR = "C:\biowerk"
.\install.ps1
```

## What Gets Installed

The installation script:

1. **Checks requirements**: Python 3.10+, pip, venv
2. **Creates installation directory**: Copies all BIOwerk files
3. **Sets up virtual environment**: Isolates Python dependencies
4. **Installs dependencies**: All required Python packages
5. **Creates configuration**: `.env` file with default settings
6. **Creates launcher scripts**:
   - `biowerk-start.sh` / `biowerk-start.ps1` - Start services
   - `biowerk-stop.sh` / `biowerk-stop.ps1` - Stop services
   - `biowerk-status.sh` / `biowerk-status.ps1` - Check status
   - `uninstall.sh` / `uninstall.ps1` - Remove installation

## Usage

### Starting BIOwerk

**Linux/macOS:**
```bash
cd ~/.biowerk
./biowerk-start.sh
```

**Windows:**
```powershell
cd $env:USERPROFILE\.biowerk
.\biowerk-start.ps1
```

### Checking Status

```bash
./biowerk-status.sh
```

### Stopping BIOwerk

```bash
./biowerk-stop.sh
```

### Uninstalling

```bash
./uninstall.sh
```

## Accessing the Services

Once started, services are available at:

- **API Gateway**: http://localhost:8080
- **API Documentation**: http://localhost:8080/docs
- **Alternative Docs**: http://localhost:8080/redoc

Individual services:
- **Nucleus** (Orchestrator): http://localhost:8001
- **Osteon** (Document Writer): http://localhost:8002
- **Myocyte** (Analysis): http://localhost:8003
- **Synapse** (Visualization): http://localhost:8004
- **Circadian** (Scheduler): http://localhost:8005
- **Chaperone** (Format Adapter): http://localhost:8006

## Configuration

Edit `.env` in your installation directory to configure:

```bash
# Database (SQLite by default, can use PostgreSQL/MongoDB)
DATABASE_URL=sqlite:///~/.biowerk/data/biowerk.db

# LLM Configuration
OPENAI_API_KEY=your-key-here
ANTHROPIC_API_KEY=your-key-here
USE_LOCAL_LLM=true

# Service Ports (change if conflicts occur)
MESH_PORT=8080
NUCLEUS_PORT=8001
# ... etc
```

## Limitations

The portable installation has some differences from the Docker version:

### What's Included
- ✅ All Python services and microservices
- ✅ SQLite database (lightweight)
- ✅ File-based caching
- ✅ Local LLM support (via Ollama if installed)
- ✅ All core functionality

### What's Not Included
- ❌ PostgreSQL (use SQLite or external PostgreSQL)
- ❌ MongoDB (optional, can connect to external)
- ❌ Redis (optional, file-based caching used instead)
- ❌ Prometheus/Grafana (monitoring stack)
- ❌ Automatic service orchestration

### External Dependencies (Optional)

You can optionally install and configure:

1. **PostgreSQL** - For production databases
   ```bash
   # Linux (Ubuntu/Debian)
   sudo apt-get install postgresql

   # Update .env
   DATABASE_URL=postgresql://user:pass@localhost/biowerk
   ```

2. **MongoDB** - For document storage
   ```bash
   # Update .env
   MONGODB_URL=mongodb://localhost:27017/biowerk
   ```

3. **Redis** - For caching and rate limiting
   ```bash
   # Update .env
   REDIS_URL=redis://localhost:6379/0
   ```

4. **Ollama** - For local LLM models
   ```bash
   # Install from: https://ollama.ai
   ollama pull llama2
   ```

## Troubleshooting

### Services Won't Start

Check logs in `logs/` directory:
```bash
tail -f ~/.biowerk/logs/*.log
```

Common issues:
- **Port conflicts**: Edit `.env` to change ports
- **Missing dependencies**: Re-run installation
- **Permission errors**: Check file permissions

### Python Version Issues

Verify Python version:
```bash
python3 --version  # Should be 3.10 or higher
```

On some systems you may need to install:
```bash
# Ubuntu/Debian
sudo apt-get install python3.10 python3.10-venv python3-pip

# Fedora/CentOS
sudo dnf install python3.10 python3-pip

# macOS
brew install python@3.10
```

### Import Errors

If you see import errors, ensure the virtual environment is activated and dependencies are installed:

```bash
cd ~/.biowerk
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\Activate.ps1  # Windows

pip install -r requirements.txt
pip install -e .
```

### Database Errors

If using SQLite and getting database lock errors:
- SQLite has limited concurrent access
- Consider switching to PostgreSQL for multi-user scenarios
- Edit `DATABASE_URL` in `.env`

## Performance Considerations

### Memory Usage

- **Minimum**: 4GB RAM (services run sequentially)
- **Recommended**: 8GB+ RAM (all services run simultaneously)
- **Optimal**: 16GB+ RAM (with LLM models loaded)

### CPU Usage

- Each service runs in a separate Python process
- LLM inference is CPU-intensive without GPU
- Consider using cloud LLM APIs (OpenAI, Anthropic) for better performance

### Disk Space

- **Base installation**: ~500MB
- **With virtual environment**: ~1GB
- **Plus logs and data**: ~2GB total (grows over time)

## Development

The portable installation is also great for development:

```bash
cd ~/.biowerk

# Activate virtual environment
source venv/bin/activate

# Run a single service for development
python -m services.osteon.main

# Run tests
pytest tests/

# Check code quality
make check-all
```

## Comparison: Portable vs Docker

| Feature | Portable | Docker |
|---------|----------|--------|
| **Setup Time** | ~5 min | ~10 min |
| **Disk Space** | ~2GB | ~5GB |
| **Memory Usage** | ~2-4GB | ~4-8GB |
| **Complexity** | Low | Medium |
| **Isolation** | Python venv | Full containers |
| **Monitoring** | Basic | Full stack (Grafana/Prometheus) |
| **Databases** | SQLite | PostgreSQL + MongoDB + Redis |
| **Production Ready** | Testing/Dev | Yes |
| **Updates** | Manual | `docker-compose pull` |

## When to Use Portable vs Docker

### Use Portable For:
- Quick testing and evaluation
- Development without Docker
- Lightweight single-user deployments
- Learning and experimentation
- CI/CD testing environments
- Resource-constrained systems

### Use Docker For:
- Production deployments
- Multi-user environments
- When you need full monitoring stack
- Horizontal scaling
- Microservices orchestration
- Team development with consistent environments

## Additional Resources

- **Main Documentation**: `../../README.md`
- **Distribution Guide**: `../README.md`
- **API Documentation**: Available at http://localhost:8080/docs after starting
- **GitHub Repository**: https://github.com/E-TECH-PLAYTECH/BIOwerk

## Support

For issues or questions:

1. Check the logs: `~/.biowerk/logs/`
2. Review the `.env` configuration
3. Check GitHub Issues: https://github.com/E-TECH-PLAYTECH/BIOwerk/issues
4. See main documentation in the repository

## License

Same as main BIOwerk project. See `../../LICENSE` for details.
