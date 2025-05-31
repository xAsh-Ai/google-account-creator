#!/bin/bash

# Google Account Creator Setup Script
#
# This script sets up the Google Account Creator environment
# for development or production use.
#
# Usage:
#   ./scripts/setup.sh [--production] [--docker] [--help]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Variables
PRODUCTION=false
USE_DOCKER=false
PYTHON_VERSION="3.10"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --production)
            PRODUCTION=true
            shift
            ;;
        --docker)
            USE_DOCKER=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

show_help() {
    echo "Google Account Creator Setup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --production    Setup for production environment"
    echo "  --docker        Use Docker for setup"
    echo "  --help, -h      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Development setup"
    echo "  $0 --production       # Production setup"
    echo "  $0 --docker           # Docker-based setup"
}

# Check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
    else
        log_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    log_info "Operating System: $OS"
    
    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        PYTHON_CMD="python"
    else
        log_error "Python not found. Please install Python $PYTHON_VERSION or higher."
        exit 1
    fi
    
    PYTHON_VER=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
    log_info "Python version: $PYTHON_VER"
    
    # Check if Python version is sufficient
    if ! $PYTHON_CMD -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null; then
        log_error "Python $PYTHON_VERSION or higher is required. Found: $PYTHON_VER"
        exit 1
    fi
    
    # Check Git
    if ! command -v git &> /dev/null; then
        log_error "Git is required but not installed."
        exit 1
    fi
    log_info "Git: $(git --version)"
    
    # Check Docker (if needed)
    if [[ "$USE_DOCKER" == true ]]; then
        if ! command -v docker &> /dev/null; then
            log_error "Docker is required but not installed."
            exit 1
        fi
        if ! command -v docker-compose &> /dev/null; then
            log_error "Docker Compose is required but not installed."
            exit 1
        fi
        log_info "Docker: $(docker --version)"
        log_info "Docker Compose: $(docker-compose --version)"
    fi
    
    # Check ADB
    if command -v adb &> /dev/null; then
        log_info "ADB: $(adb version | head -1)"
    else
        log_warn "ADB not found. Please install Android SDK for device management."
    fi
}

# Setup virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."
    
    cd "$PROJECT_ROOT"
    
    if [[ -d "venv" ]]; then
        log_warn "Virtual environment already exists. Removing old environment..."
        rm -rf venv
    fi
    
    $PYTHON_CMD -m venv venv
    
    # Activate virtual environment
    if [[ "$OS" == "windows" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    log_info "Virtual environment created successfully"
}

# Install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."
    
    cd "$PROJECT_ROOT"
    
    # Activate virtual environment
    if [[ "$OS" == "windows" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    
    # Install requirements
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
        log_info "Production dependencies installed"
    else
        log_error "requirements.txt not found"
        exit 1
    fi
    
    # Install development dependencies
    if [[ "$PRODUCTION" == false ]] && [[ -f "requirements-dev.txt" ]]; then
        pip install -r requirements-dev.txt
        log_info "Development dependencies installed"
    fi
    
    # Install pre-commit hooks for development
    if [[ "$PRODUCTION" == false ]] && command -v pre-commit &> /dev/null; then
        pre-commit install
        log_info "Pre-commit hooks installed"
    fi
}

# Setup configuration
setup_configuration() {
    log_info "Setting up configuration..."
    
    cd "$PROJECT_ROOT"
    
    # Create .env file
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_info "Created .env file from template"
        else
            log_warn "No .env.example found. Creating basic .env file..."
            cat > .env << EOF
# Google Account Creator Environment Variables
LOG_LEVEL=INFO
DEBUG=false
ENVIRONMENT=${PRODUCTION:+production}${PRODUCTION:-development}
WEB_PORT=8080
WEB_HOST=0.0.0.0
MAX_DEVICES=5
SCREENSHOTS_ENABLED=true

# Database
REDIS_PASSWORD=defaultpass
POSTGRES_DB=google_accounts
POSTGRES_USER=postgres
POSTGRES_PASSWORD=defaultpass

# API Keys (replace with actual values)
# ANTHROPIC_API_KEY=your_anthropic_key
# OPENAI_API_KEY=your_openai_key
# TWILIO_ACCOUNT_SID=your_twilio_sid
# TWILIO_AUTH_TOKEN=your_twilio_token
# FIVESIM_API_KEY=your_5sim_key
EOF
        fi
    else
        log_info "Using existing .env file"
    fi
    
    # Set production environment if needed
    if [[ "$PRODUCTION" == true ]]; then
        sed -i.bak 's/DEBUG=true/DEBUG=false/' .env
        sed -i.bak 's/ENVIRONMENT=development/ENVIRONMENT=production/' .env
        log_info "Configuration set for production environment"
    fi
    
    # Create necessary directories
    mkdir -p data logs screenshots config
    mkdir -p data/accounts data/analytics
    
    # Set permissions
    chmod 755 data logs screenshots config
    
    log_info "Configuration setup completed"
}

# Initialize application
initialize_application() {
    log_info "Initializing application..."
    
    cd "$PROJECT_ROOT"
    
    # Activate virtual environment
    if [[ "$OS" == "windows" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    
    # Initialize configuration
    $PYTHON_CMD -c "
try:
    from core.configuration_manager import ConfigurationManager
    config = ConfigurationManager()
    config.initialize_default_config()
    print('✅ Configuration initialized successfully')
except Exception as e:
    print(f'❌ Configuration initialization failed: {e}')
    exit(1)
" || {
        log_warn "Configuration initialization failed. This is normal for first-time setup."
    }
    
    log_info "Application initialization completed"
}

# Docker setup
setup_docker() {
    log_info "Setting up Docker environment..."
    
    cd "$PROJECT_ROOT"
    
    # Build Docker image
    ./scripts/docker_setup.sh build
    
    log_info "Docker setup completed"
}

# Validate installation
validate_installation() {
    log_info "Validating installation..."
    
    cd "$PROJECT_ROOT"
    
    # Activate virtual environment
    if [[ "$USE_DOCKER" == false ]]; then
        if [[ "$OS" == "windows" ]]; then
            source venv/Scripts/activate
        else
            source venv/bin/activate
        fi
    fi
    
    # Test Python imports
    if [[ "$USE_DOCKER" == false ]]; then
        log_debug "Testing Python imports..."
        $PYTHON_CMD -c "
import sys
print(f'Python version: {sys.version}')

# Test core imports
try:
    import asyncio
    import aiofiles
    import requests
    import selenium
    import easyocr
    import psutil
    print('✅ Core dependencies imported successfully')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)

# Test project imports
try:
    from core.logger import get_logger
    print('✅ Project modules imported successfully')
except ImportError as e:
    print(f'⚠️  Project import warning: {e}')
"
    fi
    
    # Test configuration
    if [[ -f ".env" ]]; then
        log_info "✅ Configuration file exists"
    else
        log_error "❌ Configuration file missing"
        return 1
    fi
    
    # Test directories
    for dir in data logs screenshots config; do
        if [[ -d "$dir" ]]; then
            log_debug "✅ Directory $dir exists"
        else
            log_error "❌ Directory $dir missing"
            return 1
        fi
    done
    
    log_info "✅ Installation validation completed successfully"
}

# Display next steps
show_next_steps() {
    echo ""
    log_info "🎉 Setup completed successfully!"
    echo ""
    echo "📋 Next Steps:"
    echo ""
    
    if [[ "$USE_DOCKER" == true ]]; then
        echo "1. Configure your API keys in .env file"
        echo "2. Run the application:"
        echo "   ./scripts/docker_setup.sh run"
        echo ""
        echo "3. Access the web dashboard:"
        echo "   http://localhost:8080"
    else
        echo "1. Configure your API keys in .env file"
        echo "2. Activate the virtual environment:"
        if [[ "$OS" == "windows" ]]; then
            echo "   venv\\Scripts\\activate"
        else
            echo "   source venv/bin/activate"
        fi
        echo ""
        echo "3. Run the application:"
        echo "   python main.py"
        echo ""
        echo "4. Access the web dashboard:"
        echo "   http://localhost:8080"
    fi
    
    echo ""
    echo "📚 Documentation:"
    echo "   - README.md - Getting started guide"
    echo "   - docs/api.md - API documentation"
    echo "   - docs/architecture.md - System architecture"
    echo "   - CONTRIBUTING.md - Development guidelines"
    echo ""
    echo "🆘 Need help?"
    echo "   - Create an issue: https://github.com/your-org/google-account-creator/issues"
    echo "   - Join Discord: https://discord.gg/google-account-creator"
    echo ""
}

# Main execution
main() {
    echo "🚀 Google Account Creator Setup"
    echo "================================"
    echo ""
    
    log_info "Starting setup process..."
    log_info "Production mode: $PRODUCTION"
    log_info "Docker mode: $USE_DOCKER"
    echo ""
    
    check_requirements
    echo ""
    
    if [[ "$USE_DOCKER" == true ]]; then
        setup_docker
    else
        setup_venv
        echo ""
        install_dependencies
        echo ""
    fi
    
    setup_configuration
    echo ""
    
    if [[ "$USE_DOCKER" == false ]]; then
        initialize_application
        echo ""
    fi
    
    validate_installation
    echo ""
    
    show_next_steps
}

# Run main function
main "$@" 