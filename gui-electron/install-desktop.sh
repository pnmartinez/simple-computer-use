#!/bin/bash

# Script to install Simple Computer Use Desktop as a desktop application
# This will create a .desktop file in ~/.local/share/applications/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DESKTOP_FILE="$SCRIPT_DIR/simple-computer-use-desktop.desktop"
INSTALL_DIR="$HOME/.local/share/applications"
INSTALLED_FILE="$INSTALL_DIR/simple-computer-use-desktop.desktop"

echo "Installing Simple Computer Use Desktop to applications menu..."

# Create applications directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Read the desktop file and replace the Exec path with absolute path
if [ -f "$DESKTOP_FILE" ]; then
    # Create a temporary desktop file with absolute paths
    TEMP_FILE=$(mktemp)
    
    # Replace the Exec path with absolute path
    sed "s|Exec=.*|Exec=$SCRIPT_DIR/start-gui-electron.sh|g" "$DESKTOP_FILE" > "$TEMP_FILE"
    
    # Try to find an icon (use the logo if available)
    ICON_PATH=""
    if [ -f "$SCRIPT_DIR/ic_launcher-playstore.png" ]; then
        ICON_PATH="$SCRIPT_DIR/ic_launcher-playstore.png"
    elif [ -f "$SCRIPT_DIR/icon.png" ]; then
        ICON_PATH="$SCRIPT_DIR/icon.png"
    elif [ -f "$SCRIPT_DIR/icon.svg" ]; then
        ICON_PATH="$SCRIPT_DIR/icon.svg"
    else
        # Use a system icon
        ICON_PATH="application-x-executable"
    fi
    
    # Update icon path
    sed -i "s|Icon=.*|Icon=$ICON_PATH|g" "$TEMP_FILE"
    
    # Copy to applications directory
    cp "$TEMP_FILE" "$INSTALLED_FILE"
    rm "$TEMP_FILE"
    
    # Make it executable (though .desktop files don't need to be executable)
    chmod 644 "$INSTALLED_FILE"
    
    # Update desktop database
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$INSTALL_DIR" 2>/dev/null
    fi
    
    echo "✓ Desktop entry installed to: $INSTALLED_FILE"
    echo "✓ Simple Computer Use Desktop should now appear in your applications menu"
    echo ""
    echo "To uninstall, run: rm $INSTALLED_FILE"
else
    echo "Error: Desktop file not found: $DESKTOP_FILE"
    exit 1
fi

