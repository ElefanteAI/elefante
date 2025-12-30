#!/bin/bash
# Elefante Automated Deployment Script
# This script automates the deployment process as much as possible

set -e  # Exit on error

echo "============================================================"
echo "ELEFANTE AUTOMATED DEPLOYMENT"
echo "============================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}[OK] $1${NC}"
}

print_error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

print_info() {
    echo "[INFO] $1"
}

# Check if Python is installed
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    print_error "Python is not installed. Please install Python 3.9 or higher."
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
    PIP_CMD=pip3
else
    PYTHON_CMD=python
    PIP_CMD=pip
fi

print_success "Python found: $($PYTHON_CMD --version)"

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

print_success "Python version OK: $PYTHON_VERSION"
echo ""

# Step 1: Install dependencies
echo "============================================================"
echo "STEP 1: Installing Dependencies"
echo "============================================================"
print_info "This may take 5-10 minutes on first run..."
echo ""

$PIP_CMD install --upgrade pip > /dev/null 2>&1
print_success "pip upgraded"

if $PIP_CMD install -r requirements.txt; then
    print_success "All dependencies installed successfully"
else
    print_error "Failed to install dependencies"
    print_info "Try manually: $PIP_CMD install -r requirements.txt"
    exit 1
fi
echo ""

# Step 2: Initialize databases
echo "============================================================"
echo "STEP 2: Initializing Databases"
echo "============================================================"
echo ""

if $PYTHON_CMD scripts/init_databases.py; then
    print_success "Databases initialized successfully"
else
    print_error "Database initialization failed"
    exit 1
fi
echo ""

# Step 3: Run health check
echo "============================================================"
echo "STEP 3: Running Health Check"
echo "============================================================"
echo ""

if $PYTHON_CMD scripts/health_check.py; then
    print_success "Health check passed"
else
    print_error "Health check failed"
    exit 1
fi
echo ""

# Step 4: Run end-to-end tests
echo "============================================================"
echo "STEP 4: Running End-to-End Tests"
echo "============================================================"
echo ""

if $PYTHON_CMD scripts/test_end_to_end.py; then
    print_success "All tests passed!"
else
    print_error "Tests failed"
    exit 1
fi
echo ""

# Step 5: GitHub setup (interactive)
echo "============================================================"
echo "STEP 5: GitHub Setup (Optional)"
echo "============================================================"
echo ""

if git remote get-url origin > /dev/null 2>&1; then
    print_success "Git remote already configured"
    REMOTE_URL=$(git remote get-url origin)
    print_info "Remote URL: $REMOTE_URL"
    echo ""
    
    read -p "Push to GitHub now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if git push -u origin main; then
            print_success "Code pushed to GitHub successfully"
        else
            print_warning "Push failed. You may need to authenticate or create the repo first."
        fi
    else
        print_info "Skipping GitHub push. You can push later with: git push -u origin main"
    fi
else
    print_warning "No Git remote configured"
    echo ""
    print_info "To push to GitHub:"
    echo "  1. Create a repository at https://github.com/new"
    echo "  2. Run: git remote add origin https://github.com/YOUR_USERNAME/elefante.git"
    echo "  3. Run: git push -u origin main"
fi
echo ""

# Final summary
echo "============================================================"
echo "DEPLOYMENT COMPLETE!"
echo "============================================================"
echo ""
print_success "Elefante is ready to use!"
echo ""
echo "Next steps:"
echo "  1. Start MCP server: $PYTHON_CMD -m src.mcp.server"
echo "  2. Configure your IDE (see DEPLOYMENT_GUIDE.md)"
echo "  3. Start using persistent AI memory!"
echo ""
echo "Documentation:"
echo "  - README.md - Quick start guide"
echo "  - ARCHITECTURE.md - System design"
echo "  - DEPLOYMENT_GUIDE.md - Detailed deployment steps"
echo ""
print_success "Happy memory building! "
echo ""

