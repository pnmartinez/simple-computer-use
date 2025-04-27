#!/bin/bash
# Test script for WebRTC screen streaming functionality

set -e  # Exit on any error

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Default values
SERVER_HOST="0.0.0.0"
SERVER_PORT=8080
TEST_TIMEOUT=30
TEST_URL="ws://localhost:8080/ws"
SAVE_FRAMES=false
NO_DISPLAY=false
DEBUG=false

# Display help information
show_help() {
    echo "Usage: $0 [options]"
    echo
    echo "This script runs the WebRTC server and test client for testing screen streaming."
    echo
    echo "Options:"
    echo "  -h, --help                Show this help message"
    echo "  --host HOST               Host to bind the server to (default: 0.0.0.0)"
    echo "  --port PORT               Port to bind the server to (default: 8080)"
    echo "  --url URL                 WebSocket URL for the test client (default: ws://localhost:8080/ws)"
    echo "  --timeout SECONDS         Test timeout in seconds (default: 30)"
    echo "  --save-frames             Save received video frames to disk"
    echo "  --no-display              Don't display video frames (headless mode)"
    echo "  --debug                   Enable debug logging"
    echo "  --server-only             Run only the server, not the test client"
    echo "  --client-only             Run only the test client, not the server"
    echo
    echo "Examples:"
    echo "  $0                        # Run with default settings"
    echo "  $0 --port 9090            # Run server on port 9090"
    echo "  $0 --debug --save-frames  # Run with debug logging and save frames"
    echo "  $0 --client-only --url ws://192.168.1.100:8080/ws  # Connect to a remote server"
    echo
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --host)
            SERVER_HOST="$2"
            shift 2
            ;;
        --port)
            SERVER_PORT="$2"
            shift 2
            ;;
        --url)
            TEST_URL="$2"
            shift 2
            ;;
        --timeout)
            TEST_TIMEOUT="$2"
            shift 2
            ;;
        --save-frames)
            SAVE_FRAMES=true
            shift
            ;;
        --no-display)
            NO_DISPLAY=true
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --server-only)
            SERVER_ONLY=true
            shift
            ;;
        --client-only)
            CLIENT_ONLY=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Cannot specify both server-only and client-only
if [[ "$SERVER_ONLY" == true && "$CLIENT_ONLY" == true ]]; then
    echo -e "${RED}Error: Cannot specify both --server-only and --client-only${NC}"
    exit 1
fi

# Set up debug flag
DEBUG_FLAG=""
if [[ "$DEBUG" == true ]]; then
    DEBUG_FLAG="--debug"
fi

# Make sure scripts directory exists
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPTS_DIR")"

echo -e "${GREEN}Running WebRTC tests from:${NC} $PROJECT_ROOT"

# Check Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed. Please install it first.${NC}"
    exit 1
fi

# Check if the WebRTC server module is available
if ! python3 -c "import llm_control.webrtc" 2>/dev/null; then
    echo -e "${YELLOW}Warning: WebRTC module not found in Python path.${NC}"
    echo -e "${YELLOW}Installing the package in development mode...${NC}"
    
    # Check pip is installed
    if ! command -v pip3 &> /dev/null; then
        echo -e "${RED}Error: pip3 is not installed. Please install it first.${NC}"
        exit 1
    fi
    
    # Install the package in development mode
    (cd "$PROJECT_ROOT" && pip3 install -e .)
    
    # Check if installation was successful
    if ! python3 -c "import llm_control.webrtc" 2>/dev/null; then
        echo -e "${RED}Error: Failed to install the package. Please check the installation.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Package installed successfully.${NC}"
fi

# Make the test script executable
chmod +x "$SCRIPTS_DIR/test_webrtc_server.py"

# Function to run the server
run_server() {
    echo -e "${GREEN}Starting WebRTC server on ${SERVER_HOST}:${SERVER_PORT}...${NC}"
    python3 -m llm_control webrtc-server --host "$SERVER_HOST" --port "$SERVER_PORT" $DEBUG_FLAG
}

# Function to run the test client
run_test_client() {
    echo -e "${GREEN}Starting WebRTC test client connecting to ${TEST_URL}...${NC}"
    
    # Build the command with appropriate flags
    CMD="$SCRIPTS_DIR/test_webrtc_server.py --url $TEST_URL --timeout $TEST_TIMEOUT $DEBUG_FLAG"
    
    if [[ "$SAVE_FRAMES" == true ]]; then
        CMD="$CMD --save-frames"
    fi
    
    if [[ "$NO_DISPLAY" == true ]]; then
        CMD="$CMD --no-display"
    fi
    
    python3 $CMD
}

# Run the appropriate components based on flags
if [[ "$CLIENT_ONLY" == true ]]; then
    # Run only the test client
    run_test_client
elif [[ "$SERVER_ONLY" == true ]]; then
    # Run only the server
    run_server
else
    # Run both server and client
    # Start the server in the background
    run_server &
    SERVER_PID=$!
    
    # Wait for the server to start
    echo -e "${YELLOW}Waiting for server to start...${NC}"
    sleep 3
    
    # Run the test client
    run_test_client
    TEST_RESULT=$?
    
    # Stop the server
    echo -e "${YELLOW}Stopping server...${NC}"
    kill $SERVER_PID 2>/dev/null || true
    wait $SERVER_PID 2>/dev/null || true
    
    # Exit with the test result
    if [[ $TEST_RESULT -eq 0 ]]; then
        echo -e "${GREEN}WebRTC test completed successfully.${NC}"
        exit 0
    else
        echo -e "${RED}WebRTC test failed.${NC}"
        exit 1
    fi
fi 