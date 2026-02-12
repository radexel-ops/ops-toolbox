#!/bin/bash
#
# VibeOps Deployment Script
#
# Usage:
#   ./deploy.sh setup     - Initial server setup
#   ./deploy.sh deploy    - Deploy/update application
#   ./deploy.sh start     - Start all services
#   ./deploy.sh stop      - Stop all services
#   ./deploy.sh status    - Check service status
#   ./deploy.sh logs      - View logs
#
# Requirements:
#   - Ubuntu 24.04 LTS
#   - Root or sudo access
#   - Internet connection
#

set -e

# ============================================================
# Configuration
# ============================================================
APP_USER="vibeops"
APP_DIR="/home/${APP_USER}/vibeops"
VENV_DIR="${APP_DIR}/venv"
REPO_URL="https://github.com/oliai-bot/ai-infinite-chat.git"
BRANCH="main"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ============================================================
# Initial Setup (run once)
# ============================================================
setup_server() {
    log_info "Starting server setup..."

    # Update system
    log_info "Updating system packages..."
    apt update && apt upgrade -y

    # Install required packages
    log_info "Installing required packages..."
    apt install -y \
        python3.12 \
        python3.12-venv \
        python3-pip \
        nginx \
        tmux \
        git \
        curl \
        wget \
        htop \
        ufw \
        sqlite3

    # Install Node.js (for Claude Code CLI)
    log_info "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y nodejs

    # Create application user
    if ! id "${APP_USER}" &>/dev/null; then
        log_info "Creating user ${APP_USER}..."
        useradd -m -s /bin/bash ${APP_USER}
    fi

    # Setup firewall
    log_info "Configuring firewall..."
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw --force enable

    # Create directory structure
    log_info "Creating directory structure..."
    mkdir -p ${APP_DIR}
    mkdir -p ${APP_DIR}/logs
    mkdir -p ${APP_DIR}/data
    chown -R ${APP_USER}:${APP_USER} /home/${APP_USER}

    log_info "Server setup complete!"
    log_info "Next steps:"
    echo "  1. Clone the repository: git clone ${REPO_URL} ${APP_DIR}/repo"
    echo "  2. Copy .env.example to .env and configure"
    echo "  3. Run: ./deploy.sh deploy"
    echo "  4. Install Claude Code CLI as ${APP_USER} user:"
    echo "     sudo -u ${APP_USER} npm install -g @anthropic-ai/claude-code"
}

# ============================================================
# Deploy Application
# ============================================================
deploy_app() {
    log_info "Deploying application..."

    # Check if repo exists
    if [ ! -d "${APP_DIR}/rpa/RDXL_OPS" ]; then
        log_error "Repository not found. Clone it first:"
        echo "  git clone ${REPO_URL} ${APP_DIR}"
        exit 1
    fi

    cd ${APP_DIR}/rpa/RDXL_OPS

    # Pull latest changes
    log_info "Pulling latest changes..."
    sudo -u ${APP_USER} git pull origin ${BRANCH}

    # Setup Python virtual environment
    if [ ! -d "${APP_DIR}/rpa/RDXL_OPS/venv" ]; then
        log_info "Creating Python virtual environment..."
        sudo -u ${APP_USER} python3.12 -m venv ${APP_DIR}/rpa/RDXL_OPS/venv
    fi

    # Install dependencies
    log_info "Installing Python dependencies..."
    sudo -u ${APP_USER} ${APP_DIR}/rpa/RDXL_OPS/venv/bin/pip install --upgrade pip
    sudo -u ${APP_USER} ${APP_DIR}/rpa/RDXL_OPS/venv/bin/pip install -r backend/requirements.txt

    # Copy systemd service files
    log_info "Installing systemd services..."
    cp ${APP_DIR}/rpa/RDXL_OPS/systemd/vibeops-api.service /etc/systemd/system/
    cp ${APP_DIR}/rpa/RDXL_OPS/systemd/vibeops-tmux.service /etc/systemd/system/
    systemctl daemon-reload

    # Copy nginx config
    log_info "Configuring Nginx..."
    cp ${APP_DIR}/rpa/RDXL_OPS/nginx/vibeops.conf /etc/nginx/sites-available/vibeops
    ln -sf /etc/nginx/sites-available/vibeops /etc/nginx/sites-enabled/
    rm -f /etc/nginx/sites-enabled/default
    nginx -t && systemctl reload nginx

    # Enable services
    systemctl enable vibeops-api
    systemctl enable vibeops-tmux

    log_info "Deployment complete!"
    log_info "Run './deploy.sh start' to start services"
}

# ============================================================
# Service Management
# ============================================================
start_services() {
    log_info "Starting services..."
    systemctl start vibeops-tmux
    sleep 2
    systemctl start vibeops-api
    systemctl status vibeops-api --no-pager
    log_info "Services started!"
}

stop_services() {
    log_info "Stopping services..."
    systemctl stop vibeops-api
    systemctl stop vibeops-tmux
    log_info "Services stopped!"
}

restart_services() {
    stop_services
    sleep 2
    start_services
}

status_services() {
    echo "=== VibeOps API ==="
    systemctl status vibeops-api --no-pager || true
    echo ""
    echo "=== VibeOps Tmux ==="
    systemctl status vibeops-tmux --no-pager || true
    echo ""
    echo "=== Nginx ==="
    systemctl status nginx --no-pager || true
}

view_logs() {
    echo "=== Recent API Logs ==="
    journalctl -u vibeops-api -n 50 --no-pager
}

# ============================================================
# Claude Code Setup
# ============================================================
setup_claude() {
    log_info "Setting up Claude Code CLI..."

    # Install Claude Code CLI
    sudo -u ${APP_USER} npm install -g @anthropic-ai/claude-code

    log_info "Claude Code CLI installed!"
    log_info "Now login as ${APP_USER} and run: claude auth login"
}

# ============================================================
# Quick Health Check
# ============================================================
health_check() {
    echo "Checking health endpoint..."
    curl -s http://localhost:8000/health | python3 -m json.tool || echo "API not responding"
}

# ============================================================
# Main
# ============================================================
case "$1" in
    setup)
        setup_server
        ;;
    deploy)
        deploy_app
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        status_services
        ;;
    logs)
        view_logs
        ;;
    health)
        health_check
        ;;
    claude)
        setup_claude
        ;;
    *)
        echo "VibeOps Deployment Script"
        echo ""
        echo "Usage: $0 {setup|deploy|start|stop|restart|status|logs|health|claude}"
        echo ""
        echo "Commands:"
        echo "  setup    - Initial server setup (run once)"
        echo "  deploy   - Deploy/update application"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Check service status"
        echo "  logs     - View recent logs"
        echo "  health   - Quick health check"
        echo "  claude   - Install Claude Code CLI"
        exit 1
        ;;
esac
