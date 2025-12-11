#!/bin/bash

# Script to start Simple Computer Use Desktop (Electron)
# This script should be used when installing as a desktop application

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if node_modules exists, if not, install dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Start the Electron application with dev tools enabled
NODE_ENV=development npm start -- --dev

