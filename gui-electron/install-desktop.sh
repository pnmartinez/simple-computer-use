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
    
    # Try to find an icon (ucomo de transversal multiplataforma es esta aplicacion tal como esta disenadase the logo if available)
    ICON_PATH=""
    ICON_DIR="$HOME/.local/share/icons"
    ICON_NAME="simple-computer-use-desktop"
    
    # Create icons directory if it doesn't exist
    mkdir -p "$ICON_DIR"
    
    # Install icon to standard location
    if [ -f "$SCRIPT_DIR/ic_launcher-playstore.png" ]; then
        # Remove old icon if exists
        rm -f "$ICON_DIR/${ICON_NAME}.png" "$ICON_DIR/${ICON_NAME}.svg"
        # Copy icon to standard location
        cp "$SCRIPT_DIR/ic_launcher-playstore.png" "$ICON_DIR/${ICON_NAME}.png"
        # Use absolute path for the icon
        ICON_PATH="$ICON_DIR/${ICON_NAME}.png"
        echo "✓ Icon installed to: $ICON_PATH"
    elif [ -f "$SCRIPT_DIR/icon.png" ]; then
        rm -f "$ICON_DIR/${ICON_NAME}.png" "$ICON_DIR/${ICON_NAME}.svg"
        cp "$SCRIPT_DIR/icon.png" "$ICON_DIR/${ICON_NAME}.png"
        ICON_PATH="$ICON_DIR/${ICON_NAME}.png"
        echo "✓ Icon installed to: $ICON_PATH"
    elif [ -f "$SCRIPT_DIR/icon.svg" ]; then
        rm -f "$ICON_DIR/${ICON_NAME}.png" "$ICON_DIR/${ICON_NAME}.svg"
        cp "$SCRIPT_DIR/icon.svg" "$ICON_DIR/${ICON_NAME}.svg"
        ICON_PATH="$ICON_DIR/${ICON_NAME}.svg"
        echo "✓ Icon installed to: $ICON_PATH"
    else
        # Use a system icon as fallback
        ICON_PATH="application-x-executable"
        echo "⚠ No icon found, using system default"
    fi
    
    # Update icon path in desktop file
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
    
    # Update icon cache (for GTK-based desktop environments)
    if command -v gtk-update-icon-cache &> /dev/null; then
        gtk-update-icon-cache -f -t "$ICON_DIR" 2>/dev/null || true
    fi
    
    # Also try update-icon-caches for KDE
    if command -v kbuildsycoca4 &> /dev/null; then
        kbuildsycoca4 2>/dev/null || true
    fi
    
    echo "✓ Desktop entry installed to: $INSTALLED_FILE"
    echo "✓ Simple Computer Use Desktop should now appear in your applications menu"
    echo ""
    if [ "$ICON_PATH" != "application-x-executable" ]; then
        echo "Note: If the icon doesn't appear immediately, you may need to:"
        echo "  - Log out and log back in, or"
        echo "  - Restart your desktop environment"
    fi
    echo ""
    echo "To uninstall, run: rm $INSTALLED_FILE"
else
    echo "Error: Desktop file not found: $DESKTOP_FILE"
    exit 1
fi

