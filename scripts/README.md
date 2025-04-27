# Scripts Directory

This directory contains various utility scripts organized into subdirectories:

- `docker/`: Scripts related to Docker setup and execution
- `setup/`: Installation and environment setup scripts
- `tools/`: Utility scripts for various tasks

See the README in each subdirectory for more details.

# WebRTC Screen Streaming Test Tools

This directory contains tools for testing the WebRTC screen streaming functionality implemented in the `llm_control` package.

## Available Scripts

- `test_webrtc_server.py`: Python script that connects to a running WebRTC server and tests the screen capture functionality.
- `run_webrtc_tests.sh`: Shell script that automates running both the server and test client together.

## Requirements

To use these test tools, you need:

- Python 3.6 or higher
- Required Python packages:
  - aiortc
  - websockets
  - opencv-python
  - numpy
- For the shell script:
  - Bash shell environment

Most dependencies should be installed automatically when you install the `llm_control` package with development dependencies.

## Test Client Usage

The test client connects to a running WebRTC server, establishes a connection, and verifies that screen capture is working correctly.

```bash
# Basic usage
python3 test_webrtc_server.py

# Connect to a specific server
python3 test_webrtc_server.py --url ws://192.168.1.100:8080/ws

# Save received frames to disk
python3 test_webrtc_server.py --save-frames

# Increase timeout (useful for slow networks)
python3 test_webrtc_server.py --timeout 60

# Run in headless mode (no GUI)
python3 test_webrtc_server.py --no-display

# Show more detailed logs
python3 test_webrtc_server.py --debug
```

## Automated Test Script

The shell script automates running both the server and test client together.

```bash
# Make the script executable
chmod +x run_webrtc_tests.sh

# Basic usage (runs server and test client)
./run_webrtc_tests.sh

# Run with custom server port
./run_webrtc_tests.sh --port 9090

# Run with debug logging
./run_webrtc_tests.sh --debug

# Save received frames to disk
./run_webrtc_tests.sh --save-frames

# Run server only
./run_webrtc_tests.sh --server-only

# Run client only (to connect to an existing server)
./run_webrtc_tests.sh --client-only --url ws://192.168.1.100:8080/ws
```

## Troubleshooting

If you encounter issues:

1. Make sure all dependencies are installed:
   ```bash
   pip install aiortc websockets opencv-python numpy
   ```

2. Check that the server is running and accessible:
   ```bash
   # Run the server only
   ./run_webrtc_tests.sh --server-only
   ```

3. Verify that the WebSocket URL is correct:
   ```bash
   # Use the proper IP address instead of localhost if testing from another device
   ./run_webrtc_tests.sh --url ws://192.168.1.100:8080/ws
   ```

4. Enable debug logging for more information:
   ```bash
   ./run_webrtc_tests.sh --debug
   ```

5. If the test client connects but you don't see any video, try running in no-display mode and saving frames to check if data is being received:
   ```bash
   ./run_webrtc_tests.sh --no-display --save-frames
   ```

## Example Use Cases

1. **Development Testing**:
   ```bash
   ./run_webrtc_tests.sh --debug
   ```
   This runs both server and client with debugging enabled to validate your implementation.

2. **Performance Testing**:
   ```bash
   ./run_webrtc_tests.sh --save-frames
   ```
   This saves received frames so you can analyze the quality and frame rate.

3. **Integration Testing**:
   ```bash
   # Start your server manually
   python -m llm_control webrtc-server
   
   # Then run only the test client
   ./run_webrtc_tests.sh --client-only
   ```
   This validates that your server works with a standard WebRTC client.

4. **Headless Testing**:
   ```bash
   ./run_webrtc_tests.sh --no-display
   ```
   This runs the test without showing the video frames, useful for CI/CD environments. 