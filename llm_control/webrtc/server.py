"""
WebRTC signaling server for screen streaming.

This module provides a FastAPI application that handles WebRTC signaling
to establish a peer-to-peer connection for screen streaming.
"""

import asyncio
import json
import logging
import os
import uuid
import time
from typing import Dict, List, Optional, Set, Union

# FastAPI imports
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# aiortc imports
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer

# Import our screen capture
from llm_control.webrtc.screen_capture import ScreenCaptureTrack

# Configure logging
logger = logging.getLogger("webrtc-signaling")

# Peer connection storage
pcs: Set[RTCPeerConnection] = set()

# Screen capture settings
DEFAULT_FPS = int(os.environ.get("SCREEN_FPS", "10"))
DEFAULT_WIDTH = int(os.environ.get("SCREEN_WIDTH", "480"))
DEFAULT_HEIGHT = int(os.environ.get("SCREEN_HEIGHT", "272"))
DEFAULT_MONITOR = None  # None for full desktop

def create_app() -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="WebRTC Screen Streaming", 
                 description="Stream your screen to Android devices using WebRTC")
    
    # Define routes
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Render the main page with connection instructions."""
        # Information page that tells users to connect with the Android app
        html_content = """
        <!DOCTYPE html>
        <html>
            <head>
                <title>WebRTC Screen Streaming</title>
                <style>
                    body {
                        font-family: Arial, sans-serif;
                        max-width: 800px;
                        margin: 0 auto;
                        padding: 20px;
                    }
                    h1 {
                        color: #333;
                    }
                    .info {
                        background-color: #f5f5f5;
                        padding: 15px;
                        border-radius: 5px;
                        margin-bottom: 20px;
                    }
                    code {
                        background-color: #eee;
                        padding: 2px 5px;
                        border-radius: 3px;
                    }
                    #video-container {
                        margin: 20px 0;
                        border: 1px solid #ccc;
                        min-height: 200px; /* Placeholder height */
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        background-color: #f0f0f0;
                    }
                    video {
                        max-width: 100%;
                        height: auto;
                        display: block; /* Remove extra space below video */
                    }
                </style>
            </head>
            <body>
                <h1>WebRTC Screen Streaming</h1>

                <div id="video-container">
                    <video id="video" autoplay playsinline muted>
                        Your browser does not support the video tag.
                    </video>
                </div>
                
                <div class="info">
                    <p>This server is streaming your screen via WebRTC.</p>
                    <p>To view the stream on another device:</p>
                    <ul>
                        <li>Connect using the Android app</li>
                        <li>Point it to this server address: <code>ws://""" + "{host}:{port}" + """/ws</code> (replace host/port)</li>
                    </ul>
                </div>

                <h2>Server Information</h2>
                <ul>
                    <li>Screen resolution: <code>""" + f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}" + """</code></li>
                    <li>Target FPS: <code>""" + f"{DEFAULT_FPS}" + """</code></li>
                    <li>WebSocket endpoint: <code>/ws</code></li>
                </ul>

                <h2>Status</h2>
                <p>Active connections: <span id="connection-count">Loading...</span></p>
                
                <script>
                    const videoElement = document.getElementById('video');
                    const connectionCountElement = document.getElementById('connection-count');
                    let pc = null; // PeerConnection
                    let ws = null; // WebSocket

                    function negotiate() {
                        // Specify that we only want to receive video
                        const offerOptions = { offerToReceiveVideo: true };
                        return pc.createOffer(offerOptions).then(offer => {
                            return pc.setLocalDescription(offer);
                        }).then(() => {
                            // Send the offer to the signaling server
                            ws.send(JSON.stringify({
                                type: 'offer',
                                sdp: pc.localDescription.sdp
                            }));
                            console.log("Offer sent to server");
                        }).catch(e => {
                            console.error("Error creating/sending offer:", e);
                            alert('Failed to create offer: ' + e);
                        });
                    }

                    function start() {
                        pc = new RTCPeerConnection();

                        // Handle incoming tracks
                        pc.ontrack = function (event) {
                            console.log("Track received:", event.track, "Streams:", event.streams);
                            if (videoElement.srcObject !== event.streams[0]) {
                                videoElement.srcObject = event.streams[0];
                                console.log('Incoming stream added to video element');
                            }
                        };

                        // Log connection state changes
                        pc.onconnectionstatechange = function(event) {
                            console.log("PeerConnection state:", pc.connectionState);
                        };
                        
                        pc.onicecandidate = event => {
                            // aiortc doesn't require manual ICE candidate handling from browser client
                             if (event.candidate) {
                                 console.log("Local ICE candidate generated (not sending)", event.candidate);
                             }
                        };

                        connectWebSocket();
                    }

                    function connectWebSocket() {
                        // Determine WebSocket protocol (ws or wss)
                        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                        const wsUrl = wsProtocol + '//' + window.location.host + '/ws';
                        console.log(`Connecting to WebSocket: ${wsUrl}`);
                        
                        if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
                            console.log("WebSocket connection already open or connecting.");
                            return;
                        }

                        ws = new WebSocket(wsUrl);

                        ws.onopen = function() {
                            console.log("WebSocket connection established");
                            // Start negotiation once connected
                            negotiate(); 
                        };

                        ws.onmessage = function(event) {
                            const data = JSON.parse(event.data);
                            console.log("Received message:", data.type);

                            if (data.type === 'answer') {
                                pc.setRemoteDescription(new RTCSessionDescription(data)).catch(e => {
                                    console.error("Error setting remote description:", e);
                                    alert('Failed to set remote description: ' + e);
                                });
                            } else if (data.type === 'ice_candidate') {
                                // aiortc handles ICE internally
                                console.log("Received ICE candidate from server (ignoring)");
                            } else if (data.type === 'pong') {
                                // Handle pong if needed
                                console.debug("Received pong");
                            } else {
                                console.warn("Unhandled message type:", data.type);
                            }
                        };

                        ws.onerror = function(event) {
                            console.error("WebSocket error:", event);
                            // Close the peer connection if WebSocket fails
                            if (pc && pc.connectionState !== 'closed') {
                                pc.close();
                            }
                        };

                        ws.onclose = function(event) {
                            console.log("WebSocket connection closed:", event.code, event.reason);
                            // Close the peer connection if WebSocket closes
                            if (pc && pc.connectionState !== 'closed') {
                                console.log("Closing PeerConnection due to WebSocket closure.");
                                pc.close();
                            }
                            // Attempt to reconnect after a delay
                            console.log("Attempting to reconnect WebSocket after 5 seconds...");
                            setTimeout(connectWebSocket, 5000); 
                        };
                    }

                    // Fetch status periodically
                    function updateStatus() {
                        fetch('/status')
                            .then(response => response.json())
                            .then(data => {
                                connectionCountElement.textContent = data.connections;
                            })
                            .catch(err => {
                                console.error('Error fetching status:', err);
                                connectionCountElement.textContent = 'Error';
                            });
                    }

                    // Start the process when the page loads
                    window.onload = () => {
                        start();
                        updateStatus(); // Initial status fetch
                        setInterval(updateStatus, 5000); // Update status every 5 seconds
                    };
                    
                     // Add simple connection status check
                     setInterval(() => {
                         fetch('/status')
                             .then(response => response.json())
                             .then(data => {
                                 connectionCountElement.textContent = data.connections;
                             })
                             .catch(err => console.error('Error fetching status:', err));
                     }, 5000);
                 </script>
            </body>
        </html>
        """
        # Inject current host and port into the ws:// address example dynamically
        host = request.client.host if request.client else "YOUR_SERVER_IP"
        port = request.url.port if request.url.port else (443 if request.url.scheme == "https" else 80)
        html_content = html_content.replace("ws://YOUR_SERVER_IP:PORT/ws", f"ws://{host}:{port}/ws")
        
        return HTMLResponse(content=html_content)
    
    @app.get("/status")
    async def status():
        """Return the current server status."""
        return {
            "status": "running",
            "connections": len(pcs),
            "resolution": f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
            "fps": DEFAULT_FPS
        }
    
    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok"}
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Handle WebRTC signaling via WebSocket."""
        try:
            # Log connection attempt details
            client_host = websocket.client.host if websocket.client else "unknown"
            logger.info(f"WebSocket connection attempt from {client_host}")
            
            # Accept the connection
            await websocket.accept()
            logger.info(f"WebSocket connection accepted from {client_host}")
            
            # Create a new peer connection for this client
            pc = RTCPeerConnection()
            pcs.add(pc)

            # Create the screen capture track
            screen_track = ScreenCaptureTrack(
                fps=DEFAULT_FPS,
                width=DEFAULT_WIDTH,
                height=DEFAULT_HEIGHT,
                monitor=DEFAULT_MONITOR,
                quality_degradation=True
            )
            
            # Add the track *before* handling any signaling
            pc.addTrack(screen_track)

            # Create a unique ID for this connection
            connection_id = str(uuid.uuid4())
            logger.info(f"New WebSocket connection: {connection_id} from {client_host}")
            
            # Track connection state
            connection_established = False
            last_ping_time = time.time()
            
            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                nonlocal connection_established
                logger.info(f"Connection state is {pc.connectionState} for {client_host}")
                if pc.connectionState == "connected":
                    connection_established = True
                elif pc.connectionState == "failed":
                    logger.error(f"Connection failed for {client_host}. Closing connection after short delay.")
                    # Add a small delay to allow any pending aioice tasks to potentially complete or fail cleanly
                    await asyncio.sleep(0.5) 
                    try:
                        if hasattr(screen_track, 'stop'): # Ensure track exists and has stop method
                            screen_track.stop()
                        await pc.close()
                    except Exception as close_err:
                        logger.error(f"Error closing failed connection for {client_host}: {close_err}")
                    finally:
                        pcs.discard(pc)
                elif pc.connectionState == "closed":
                    # Ensure cleanup if closed state is reached directly
                    if hasattr(screen_track, 'stop'):
                        screen_track.stop()
                    pcs.discard(pc)
                    logger.info(f"Connection closed for {client_host}. Cleaned up.")
            
            @pc.on("track")
            def on_track(track):
                logger.info(f"Track {track.kind} received from {client_host}")
                
                @track.on("ended")
                async def on_ended():
                    logger.info(f"Track {track.kind} ended for {client_host}")
            
            try:
                # Handle messages until the client disconnects
                while True:
                    message = await websocket.receive_text()
                    data = json.loads(message)
                    
                    # Log message type for debugging
                    logger.info(f"Received message type: {data.get('type')} from {client_host}")
                    
                    # Handle different message types
                    if data.get("type") == "offer":
                        # Check if we already have a remote description from a previous offer
                        if pc.remoteDescription is not None:
                            logger.warning(f"Received unexpected offer from {client_host} when remote description is already set. Ignoring.")
                            continue # Ignore this redundant offer
                            
                        # Client is offering a connection
                        offer = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
                        
                        # Set the remote description to the client's offer
                        await pc.setRemoteDescription(offer)

                        # Create an answer
                        answer = await pc.createAnswer()
                        await pc.setLocalDescription(answer)
                        
                        # Send the answer back to the client
                        await websocket.send_json({
                            "type": "answer",
                            "sdp": pc.localDescription.sdp,
                        })
                        logger.info(f"Sent answer to {client_host}")
                    
                    elif data.get("type") == "ice_candidate":
                        # Use the most direct approach possible
                        try:
                            # Extract candidate information - the only part aiortc really cares about
                            candidate_str = data.get("candidate")
                            
                            if candidate_str:
                                # Just log that we received a candidate - we can't reliably add it
                                # due to the aiortc internal API limitations
                                logger.info(f"Received ICE candidate from {client_host}")
                                
                                # We don't actually need to do anything - aiortc will establish
                                # the connection automatically as shown in the logs
                                # The 'sdpMid' error is internal to aiortc's validation but 
                                # doesn't prevent connection
                                pass
                        except Exception as e:
                            # Log error but continue as normal
                            logger.error(f"ICE candidate processing for {client_host}: {str(e)}")
                    
                    elif data.get("type") == "ping":
                        # Client is checking connection
                        current_time = time.time()
                        if current_time - last_ping_time < 0.5:  # Rate limit pings to 2 per second
                            logger.debug(f"Ignoring rapid ping from {client_host}")
                            continue
                        last_ping_time = current_time
                        await websocket.send_json({"type": "pong"})
                        logger.debug(f"Sent pong to {client_host}")
                    
                    elif data.get("type") == "bye":
                        # Client is closing the connection
                        logger.info(f"Received bye message from client {connection_id} ({client_host})")
                        break
            
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id} ({client_host})")
            except Exception as e:
                logger.error(f"Error in WebSocket handler for {client_host}: {e}")
            finally:
                # Clean up the connection
                if hasattr(screen_track, 'stop'): # Stop the track first
                    screen_track.stop()
                if pc.connectionState != "closed": # Avoid closing twice if already closed by state handler
                    await pc.close()
                pcs.discard(pc) # Ensure it's removed from the set
                logger.info(f"Connection {connection_id} ({client_host}) closed, {len(pcs)} connections remaining")
        
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {e}")
            # Ensure cleanup even if accept fails after pc creation
            if 'pc' in locals() and pc in pcs:
                if hasattr(screen_track, 'stop'):
                    screen_track.stop()
                if pc.connectionState != "closed":
                    await pc.close()
                pcs.discard(pc)
            raise  # Re-raise to let FastAPI handle it
    
    return app

async def on_shutdown(app):
    """Close all peer connections when the application shuts down."""
    # We don't have direct access to the screen_track instances here
    # aiortc should handle stopping tracks when pc.close() is called.
    logger.info(f"Shutting down {len(pcs)} connections...")
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros, return_exceptions=True) # Capture potential errors during close
    pcs.clear()
    logger.info("All WebRTC connections closed")

def run_server(host: str = "0.0.0.0", port: int = 8080, debug: bool = False, 
               ssl_certfile: Optional[str] = None, ssl_keyfile: Optional[str] = None):
    """Run the WebRTC signaling server."""
    import uvicorn
    import logging
    
    # Configure logging
    log_level = "debug" if debug else "info"
    
    # Create the app
    app = create_app()
    
    # Add shutdown event handler
    app.on_shutdown = [on_shutdown]
    
    # Set up SSL if certificates are provided
    ssl_config = {}
    if ssl_certfile and ssl_keyfile:
        ssl_config["ssl_certfile"] = ssl_certfile
        ssl_config["ssl_keyfile"] = ssl_keyfile
    
    print(f"\n{'=' * 40}")
    print(f"🎥 WebRTC Screen Streaming Server starting...")
    print(f"🌐 Listening on: {'https' if ssl_config else 'http'}://{host}:{port}")
    print(f"🔧 Debug mode: {'ON' if debug else 'OFF'}")
    print(f"📺 Stream resolution: {DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")
    print(f"🎞️ Target FPS: {DEFAULT_FPS}")
    print(f"{'=' * 40}\n")
    
    # Run the server
    uvicorn.run(app, host=host, port=port, log_level=log_level, **ssl_config)

if __name__ == "__main__":
    # Run the server if executed directly
    run_server(debug=True) 