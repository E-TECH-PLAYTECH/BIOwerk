#!/usr/bin/env bash
set -euo pipefail

# BIOwerk unified installer and operator helper
# Provides repeatable installation, startup, health, and log tooling for production-grade usage.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

print_header() {
  local title="$1"
  printf "\n==============================\n%s\n==============================\n" "$title"
}

usage() {
  cat <<'USAGE'
BIOwerk control script

Usage: ./scripts/biowerkctl.sh <command> [options]

Commands:
  install [--dev] [--force-venv]   Create .venv and install dependencies (add --dev for dev extras)
  docker-up                        Start full stack with docker-compose
  docker-down                      Stop docker-compose stack
  docker-rebuild                   Rebuild all docker images and restart
  docker-logs [service]            Follow docker-compose logs (optionally scoped to a service)
  health-check                     Run packaged health checks against running services
  clean                            Remove .venv and build artifacts
  help                             Show this help text

Examples:
  ./scripts/biowerkctl.sh install --dev
  ./scripts/biowerkctl.sh docker-up
  ./scripts/biowerkctl.sh docker-logs mesh
  ./scripts/biowerkctl.sh health-check
USAGE
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: required command '$cmd' not found. Please install it first." >&2
    exit 1
  fi
}

create_venv() {
  local with_dev="$1"
  local force_venv="$2"
  local venv_path="$REPO_ROOT/.venv"

  if [[ -d "$venv_path" && "$force_venv" != "1" ]]; then
    echo "Existing virtual environment found at $venv_path (use --force-venv to recreate)."
  else
    print_header "Creating virtual environment"
    rm -rf "$venv_path"
    python3 -m venv "$venv_path"
  fi

  # shellcheck disable=SC1090
  source "$venv_path/bin/activate"
  print_header "Installing Python dependencies"
  pip install --upgrade pip setuptools wheel
  pip install -r "$REPO_ROOT/requirements.txt"
  if [[ "$with_dev" == "1" ]]; then
    pip install -r "$REPO_ROOT/requirements-dev.txt"
  fi
}

run_docker_compose() {
  require_cmd docker-compose
  (cd "$REPO_ROOT" && "$@")
}

run_health_checks() {
  if [[ ! -x "$REPO_ROOT/scripts/health_check.sh" ]]; then
    echo "Making health_check.sh executable"
    chmod +x "$REPO_ROOT/scripts/health_check.sh"
  fi
  "$REPO_ROOT/scripts/health_check.sh"
}

clean_artifacts() {
  print_header "Removing virtual environment and build artifacts"
  rm -rf "$REPO_ROOT/.venv" "$REPO_ROOT/build" "$REPO_ROOT/dist" "$REPO_ROOT/.pytest_cache" "$REPO_ROOT/.mypy_cache"
  find "$REPO_ROOT" -type d -name "__pycache__" -exec rm -rf {} +
  find "$REPO_ROOT" -type f -name "*.pyc" -delete
}

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  install)
    with_dev=0
    force_venv=0
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --dev)
          with_dev=1
          shift
          ;;
        --force-venv)
          force_venv=1
          shift
          ;;
        *)
          echo "Unknown option: $1" >&2
          usage
          exit 1
          ;;
      esac
    done
    require_cmd python3
    create_venv "$with_dev" "$force_venv"
    print_header "Installation complete"
    ;;
  docker-up)
    run_docker_compose docker-compose up -d
    ;;
  docker-down)
    run_docker_compose docker-compose down
    ;;
  docker-rebuild)
    run_docker_compose docker-compose down
    run_docker_compose docker-compose build --no-cache
    run_docker_compose docker-compose up -d
    ;;
  docker-logs)
    require_cmd docker-compose
    if [[ $# -gt 0 ]]; then
      run_docker_compose docker-compose logs -f "$1"
    else
      run_docker_compose docker-compose logs -f
    fi
    ;;
  health-check)
    run_health_checks
    ;;
  clean)
    clean_artifacts
    ;;
  help|*)
    usage
    ;;
 esac
