#!/bin/bash
# Run UI detection visualization in a Docker container

set -e  # Exit on error

# Check if Docker is running and containers are up
if ! docker ps | grep -q "voice-control-server"; then
    echo "Error: Voice Control Server container is not running."
    echo "Please start it first with: ../tools/start-voice-control.sh"
    exit 1
fi

# Check if Ollama is running locally (needed for LLM features)
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "Warning: Ollama service is not running on localhost:11434."
    echo "Please start Ollama with: ollama serve"
    echo "The Voice Control Server needs Ollama for LLM-based detection features."
    echo ""
fi

# Explain what this script does
echo "=========================================================="
echo "    Voice Control Server - UI Detection Visualization     "
echo "=========================================================="
echo ""
echo "This script helps debug UI element detection by:"
echo "1. Taking a screenshot of the host's screen"
echo "2. Running UI detection on the screenshot"
echo "3. Visualizing the detected UI elements"
echo "4. Saving the result to disk and displaying it"
echo ""

# Create output directory if it doesn't exist
mkdir -p ./data/visualization

# Take a screenshot of the host's screen
echo "Taking screenshot of your current screen..."
if command -v scrot &> /dev/null; then
    scrot -o ./data/visualization/screenshot.png
elif command -v import &> /dev/null; then
    import -window root ./data/visualization/screenshot.png
else
    echo "Error: No screenshot tool found. Please install 'scrot' or 'imagemagick'."
    echo "   Ubuntu/Debian: sudo apt-get install scrot"
    echo "   Fedora: sudo dnf install scrot"
    echo "   Arch: sudo pacman -S scrot"
    exit 1
fi

echo "Screenshot saved to ./data/visualization/screenshot.png"

# Run the visualization script in the Docker container
echo "Running UI detection and visualization..."
docker exec -i voice-control-server python3 /app/visualize_ui_detection.py \
    --input /app/data/visualization/screenshot.png \
    --output /app/data/visualization/detection_result.png

echo "Visualization complete!"
echo "Results saved to: ./data/visualization/detection_result.png"

# Display the result if a display tool is available
if command -v xdg-open &> /dev/null; then
    echo "Opening the visualization result..."
    xdg-open ./data/visualization/detection_result.png
elif command -v open &> /dev/null; then
    echo "Opening the visualization result..."
    open ./data/visualization/detection_result.png
else
    echo "Unable to automatically open the result image."
    echo "Please manually open: ./data/visualization/detection_result.png"
fi

echo ""
echo "=========================================================="
echo "If you see no elements detected, check the following:"
echo "1. Run the diagnostics: ./docker-diagnose-ui.sh"
echo "2. Verify Ollama is running: curl http://localhost:11434/api/tags"
echo "3. Check if required LLM models are available: ollama list"
echo "==========================================================" 