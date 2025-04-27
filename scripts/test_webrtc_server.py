#!/usr/bin/env python3
"""
Test script for WebRTC screen streaming server.

This script connects to the WebRTC server, establishes a connection,
and verifies that screen capture is working correctly.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("webrtc-test")

try:
    import cv2
    import numpy as np
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
    from aiortc.contrib.media import MediaPlayer, MediaRecorder, MediaBlackhole
    import websockets
except ImportError as e:
    logger.error(f"Required dependencies not found: {e}")
    logger.error("Please install them with: pip install aiortc websockets opencv-python numpy")
    sys.exit(1)

# Class to receive and process video frames
class VideoFrameProcessor:
    def __init__(self, save_path=None, show_video=True):
        self.frame_count = 0
        self.save_path = save_path
        self.show_video = show_video
        
        # Create output directory if saving frames
        if save_path:
            os.makedirs(save_path, exist_ok=True)
            logger.info(f"Saving frames to {save_path}")
        
        # FPS calculation
        self.start_time = None
        self.last_frame_time = None
        self.fps_counter = 0
        self.fps = 0
    
    async def process_track(self, track):
        logger.info(f"Started processing track: {track.kind}")
        self.start_time = asyncio.get_event_loop().time()
        
        while True:
            try:
                frame = await track.recv()
                self.frame_count += 1
                
                # Calculate FPS
                now = asyncio.get_event_loop().time()
                if self.last_frame_time:
                    self.fps_counter += 1
                    if self.fps_counter >= 30:  # Update FPS every 30 frames
                        elapsed = now - self.start_time
                        self.fps = self.fps_counter / elapsed if elapsed > 0 else 0
                        logger.info(f"Current FPS: {self.fps:.1f}")
                        self.fps_counter = 0
                        self.start_time = now
                self.last_frame_time = now
                
                # Convert frame to numpy array for OpenCV
                if hasattr(frame, 'to_ndarray'):
                    img = frame.to_ndarray(format="bgr24")
                    
                    # Add frame info text
                    cv2.putText(
                        img, 
                        f"Frame: {self.frame_count}, FPS: {self.fps:.1f}", 
                        (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 
                        1, 
                        (0, 255, 0), 
                        2
                    )
                    
                    # Save frame if requested
                    if self.save_path:
                        frame_path = os.path.join(self.save_path, f"frame_{self.frame_count:04d}.jpg")
                        cv2.imwrite(frame_path, img)
                    
                    # Display frame if requested
                    if self.show_video:
                        cv2.imshow("WebRTC Test", img)
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q') or key == 27:  # 'q' or ESC to quit
                            logger.info("User requested exit")
                            return
            except Exception as e:
                logger.error(f"Error processing frame: {e}")
                break
        
        logger.info(f"Stopped processing track after {self.frame_count} frames")
        if self.show_video:
            cv2.destroyAllWindows()

async def run_test(server_url, timeout=30, save_frames=False, show_video=True):
    """Connect to the WebRTC server and test the connection."""
    logger.info(f"Connecting to WebRTC server at {server_url}")
    
    # Create peer connection
    pc = RTCPeerConnection()
    
    # Variables to track connection state
    connected = False
    connection_failed = False
    
    # Set up connection state change handler
    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        nonlocal connected, connection_failed
        logger.info(f"Connection state changed to: {pc.connectionState}")
        
        if pc.connectionState == "connected":
            connected = True
        elif pc.connectionState == "failed":
            connection_failed = True
    
    # Set up track handler
    frame_processor = VideoFrameProcessor(
        save_path="webrtc_test_frames" if save_frames else None,
        show_video=show_video
    )
    
    @pc.on("track")
    async def on_track(track):
        logger.info(f"Track received: {track.kind}")
        
        if track.kind == "video":
            await frame_processor.process_track(track)
    
    # Connect to signaling server
    async with websockets.connect(server_url) as ws:
        logger.info("Connected to signaling server")
        
        # Create offer
        offer = await pc.createOffer()
        await pc.setLocalDescription(offer)
        
        # Send offer to server
        message = json.dumps({
            "type": "offer",
            "sdp": pc.localDescription.sdp,
        })
        await ws.send(message)
        logger.info("Sent offer to server")
        
        # Wait for answer
        try:
            # Set timeout for the entire connection attempt
            answer_data = await asyncio.wait_for(ws.recv(), timeout=timeout)
            answer_json = json.loads(answer_data)
            
            if answer_json["type"] == "answer":
                # Set remote description from answer
                answer = RTCSessionDescription(sdp=answer_json["sdp"], type=answer_json["type"])
                await pc.setRemoteDescription(answer)
                logger.info("Received and set remote description")
                
                # Process ICE candidates if any
                while True:
                    try:
                        # Short timeout for additional messages like ICE candidates
                        message = await asyncio.wait_for(ws.recv(), timeout=5)
                        data = json.loads(message)
                        
                        if data.get("type") == "ice_candidate":
                            candidate = data.get("candidate")
                            sdp_mid = data.get("sdpMid")
                            sdp_m_line_index = data.get("sdpMLineIndex")
                            
                            if candidate and sdp_mid is not None and sdp_m_line_index is not None:
                                await pc.addIceCandidate({
                                    "candidate": candidate,
                                    "sdpMid": sdp_mid,
                                    "sdpMLineIndex": sdp_m_line_index
                                })
                                logger.info("Added ICE candidate from server")
                    except asyncio.TimeoutError:
                        # No more messages, continue with connection
                        break
                    except Exception as e:
                        logger.warning(f"Error processing message: {e}")
                        break
            else:
                logger.error(f"Unexpected message type: {answer_json['type']}")
        
        except asyncio.TimeoutError:
            logger.error(f"Timed out waiting for server response after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Error during signaling: {e}")
            return False
        
        # Wait for track processing to complete
        try:
            # Wait for the connection to establish or fail
            for _ in range(timeout * 2):  # Check every 500ms
                if connected:
                    logger.info("Connection established successfully")
                    break
                if connection_failed:
                    logger.error("Connection failed")
                    return False
                await asyncio.sleep(0.5)
            
            if not connected:
                logger.warning("Connection didn't reach 'connected' state, but continuing...")
            
            # Wait for user to close the window or timeout
            await asyncio.sleep(timeout)
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        finally:
            # Close peer connection
            await pc.close()
            logger.info("Connection closed")
    
    # Return success if we processed at least some frames
    return frame_processor.frame_count > 0

def main():
    parser = argparse.ArgumentParser(description="Test WebRTC Screen Streaming Server")
    
    parser.add_argument("--url", type=str, default="ws://localhost:8080/ws",
                       help="WebSocket URL of the WebRTC server (default: ws://localhost:8080/ws)")
    parser.add_argument("--timeout", type=int, default=60,
                       help="Test timeout in seconds (default: 60)")
    parser.add_argument("--save-frames", action="store_true",
                       help="Save received video frames to disk")
    parser.add_argument("--no-display", action="store_true",
                       help="Don't display video frames (headless mode)")
    parser.add_argument("--debug", action="store_true",
                       help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    # Run the test
    try:
        success = asyncio.run(run_test(
            server_url=args.url,
            timeout=args.timeout,
            save_frames=args.save_frames,
            show_video=not args.no_display
        ))
        
        if success:
            logger.info("Test completed successfully")
            sys.exit(0)
        else:
            logger.error("Test failed")
            sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error running test: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 