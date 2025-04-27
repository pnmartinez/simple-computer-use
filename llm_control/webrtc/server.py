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
DEFAULT_FPS = int(os.environ.get("SCREEN_FPS", "30"))
DEFAULT_WIDTH = int(os.environ.get("SCREEN_WIDTH", "1280"))
DEFAULT_HEIGHT = int(os.environ.get("SCREEN_HEIGHT", "720"))
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
                    .qr-placeholder {
                        background-color: #ddd;
                        height: 200px;
                        width: 200px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 20px 0;
                    }
                </style>
            </head>
            <body>
                <h1>WebRTC Screen Streaming</h1>
                <div class="info">
                    <p>This server is streaming your screen via WebRTC.</p>
                    <p>To view the stream:</p>
                    <ul>
                        <li>Connect using the Android app</li>
                        <li>Point it to this server address: <code>ws://YOUR_SERVER_IP:PORT/ws</code></li>
                    </ul>
                </div>
                
                <h2>Server Information</h2>
                <ul>
                    <li>Screen resolution: <code>""" + f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}" + """</code></li>
                    <li>Target FPS: <code>""" + f"{DEFAULT_FPS}" + """</code></li>
                    <li>WebSocket endpoint: <code>/ws</code></li>
                </ul>
                
                <h2>Status</h2>
                <p>Active connections: <span id="connection-count">0</span></p>
                
                <script>
                    // Add simple connection status check
                    setInterval(() => {
                        fetch('/status')
                            .then(response => response.json())
                            .then(data => {
                                document.getElementById('connection-count').textContent = data.connections;
                            })
                            .catch(err => console.error('Error fetching status:', err));
                    }, 5000);
                </script>
            </body>
        </html>
        """
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
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Handle WebRTC signaling via WebSocket."""
        await websocket.accept()
        
        # Create a new peer connection for this client
        pc = RTCPeerConnection()
        pcs.add(pc)
        
        # Create a unique ID for this connection
        connection_id = str(uuid.uuid4())
        logger.info(f"New WebSocket connection: {connection_id}")
        
        # Create the screen capture track
        screen_track = ScreenCaptureTrack(
            fps=DEFAULT_FPS,
            width=DEFAULT_WIDTH,
            height=DEFAULT_HEIGHT,
            monitor=DEFAULT_MONITOR,
            quality_degradation=True
        )
        
        # Add the track to the peer connection
        pc.addTrack(screen_track)
        
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state is {pc.connectionState}")
            if pc.connectionState == "failed":
                await pc.close()
                pcs.discard(pc)
        
        @pc.on("track")
        def on_track(track):
            logger.info(f"Track {track.kind} received")
            
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track {track.kind} ended")
        
        try:
            # Handle messages until the client disconnects
            while True:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # Handle different message types
                if data.get("type") == "offer":
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
                
                elif data.get("type") == "ice_candidate":
                    # Handle ICE candidate from client
                    candidate = data.get("candidate")
                    sdp_mid = data.get("sdpMid")
                    sdp_m_line_index = data.get("sdpMLineIndex")
                    
                    if candidate and sdp_mid is not None and sdp_m_line_index is not None:
                        await pc.addIceCandidate({
                            "candidate": candidate,
                            "sdpMid": sdp_mid,
                            "sdpMLineIndex": sdp_m_line_index
                        })
                
                elif data.get("type") == "ping":
                    # Client is checking connection
                    await websocket.send_json({"type": "pong"})
                
                elif data.get("type") == "bye":
                    # Client is closing the connection
                    logger.info(f"Received bye message from client {connection_id}")
                    break
        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: {connection_id}")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}")
        finally:
            # Clean up the connection
            await pc.close()
            pcs.discard(pc)
            logger.info(f"Connection {connection_id} closed, {len(pcs)} connections remaining")
    
    return app

async def on_shutdown(app):
    """Close all peer connections when the application shuts down."""
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
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