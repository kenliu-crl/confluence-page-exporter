#!/bin/bash
# Setup script for Confluence Page Exporter
# Creates a virtual environment and installs dependencies

# Exit on error
set -e

# Configuration
VENV_NAME=".venv"
REQUIREMENTS_FILE="requirements.txt"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up virtual environment for Confluence Page Exporter...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install Python 3 and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_NAME" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_NAME"
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_NAME/bin/activate"

# Check if requirements file exists
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "Installing dependencies from $REQUIREMENTS_FILE..."
    pip install -r "$REQUIREMENTS_FILE"
else
    echo "Installing required packages..."
    pip install requests beautifulsoup4 html2text python-dotenv
fi

# Update pip and setuptools
echo "Updating pip and setuptools..."
pip install --upgrade pip setuptools

# Create .env file template if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file template..."
    cat > .env << EOL
# Confluence API Configuration
CONFLUENCE_BASE_URL=
CONFLUENCE_USERNAME=
CONFLUENCE_API_TOKEN=
EOL
    echo -e "${YELLOW}Please edit the .env file with your Confluence credentials.${NC}"
fi

# Make the exporter script executable
if [ -f "confluence-page-exporter.py" ]; then
    chmod +x confluence-page-exporter.py
fi

echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source $VENV_NAME/bin/activate"
echo ""
echo "To run the exporter script:"
echo "  python confluence-page-exporter.py [CONFLUENCE_PAGE_URL]"
echo ""
echo "To deactivate the virtual environment when done:"
echo "  deactivate"
