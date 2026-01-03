#!/bin/bash
set -e

cd "/home/nava/Descargas/llm-control"
cd gui-electron

# Function to wait for X server to be ready
wait_for_x() {
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        # Try to detect DISPLAY
        if [ -z "$DISPLAY" ]; then
            # Try common display values
            for display in ":0" ":1" ":10"; do
                if xset -q -display "$display" >/dev/null 2>&1; then
                    export DISPLAY="$display"
                    break
                fi
            done
        fi
        
        # Check if X server is accessible
        if [ -n "$DISPLAY" ] && xset -q >/dev/null 2>&1; then
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 1
    done
    
    echo "ERROR: X server not available after $max_attempts attempts" >&2
    return 1
}

# Detect XAUTHORITY dynamically
if [ -z "$XAUTHORITY" ]; then
    # Try common XAUTHORITY locations
    for xauth_path in \
        "$HOME/.Xauthority" \
        "/run/user/$(id -u)/gdm/Xauthority" \
        "/run/user/$(id -u)/.Xauthority" \
        "/var/run/gdm3/$(id -u)/.Xauthority"; do
        if [ -f "$xauth_path" ]; then
            export XAUTHORITY="$xauth_path"
            break
        fi
    done
fi

# Wait for X server to be ready
wait_for_x || exit 1

# Set service environment variable
export SYSTEMD_SERVICE=1

# Start Electron
exec "/home/nava/Descargas/llm-control/gui-electron/node_modules/.bin/electron" .
