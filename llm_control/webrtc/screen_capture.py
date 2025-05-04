"""
Screen capture module for WebRTC.

This module provides a media track class that captures the screen
and makes it available for WebRTC streaming.
"""

import asyncio
import fractions
import logging
import time
import threading
from typing import Dict, Optional, List
from queue import Queue, Empty, Full

# aiortc imports
from av import VideoFrame
from aiortc.mediastreams import MediaStreamTrack

# Screen capture import
from mss import mss
import numpy as np
import cv2 # Add OpenCV import

# Configure logging
logger = logging.getLogger("webrtc-screen-capture")

class ScreenCaptureTrack(MediaStreamTrack):
    """
    A video track that captures the screen.
    
    This uses the mss library which is efficient for screen capture.
    It produces video frames suitable for sending over WebRTC.
    """
    kind = "video"
    
    def __init__(self, 
                 fps: int = 10, 
                 width: int = 480,  # Ensure multiple of 16
                 height: int = 272, # Ensure multiple of 16
                 monitor: Optional[int] = None,
                 quality_degradation: bool = True):
        """
        Initialize the screen capture track.
        
        Args:
            fps: Frames per second to target
            width: Output width of the video (must be multiple of 16)
            height: Output height of the video (must be multiple of 16)
            monitor: Monitor number to capture (None for entire screen)
            quality_degradation: Whether to lower quality if needed to maintain FPS
        """
        super().__init__()
        
        # Ensure initial dimensions are multiples of 16
        assert width % 16 == 0, "Width must be a multiple of 16"
        assert height % 16 == 0, "Height must be a multiple of 16"
        
        # Initialize with conservative settings
        self.fps = fps
        self.width = width
        self.height = height
        self.monitor = monitor
        self.quality_degradation = quality_degradation
        
        # Dynamic quality adjustment
        self.current_width = width
        self.current_height = height
        
        # Frame timing - Use a simple frame counter for monotonic PTS
        self.frame_interval = 1 / fps
        # self.last_frame_time = time.time() # Removed
        # self.last_pts = 0 # Removed
        self._pts = 0 # Frame counter for PTS
        self._time_base = fractions.Fraction(1, 1_000_000) # Keep high precision timebase for now
        # Using fps directly for timebase might cause issues if frame delivery isn't perfect
        # self._time_base = fractions.Fraction(1, fps)
        
        # Get monitor list in main thread
        # (but don't keep the MSS instance for thread safety)
        try:
            with mss() as temp_sct:
                monitors = temp_sct.monitors
                # Select monitor
                if monitor is None:
                    # Try to get primary monitor (typically index 1)
                    if len(monitors) > 1:
                        logger.info("Using primary monitor for faster capture")
                        self.monitor_info = monitors[1].copy()
                    else:
                        self.monitor_info = monitors[0].copy()
                else:
                    # Specific monitor
                    if 0 <= monitor < len(monitors):
                        self.monitor_info = monitors[monitor].copy()
                    else:
                        # Fallback
                        logger.warning(f"Monitor {monitor} not found. Using default.")
                        if len(monitors) > 1:
                            self.monitor_info = monitors[1].copy()
                        else:
                            self.monitor_info = monitors[0].copy()
            
            logger.info(f"Using monitor: {self.monitor_info}")
        except Exception as e:
            logger.error(f"Error initializing monitor info: {str(e)}")
            # Create a default monitor info that should work on most systems
            self.monitor_info = {'left': 0, 'top': 0, 'width': 1920, 'height': 1080}
            logger.info(f"Using fallback monitor config: {self.monitor_info}")
        
        # Video reformatter (for resizing frames) - REMOVED
        # self.reformatter = VideoReformatter()
        
        # Performance tracking
        self.frame_times: List[float] = []
        self.MAX_FRAME_TIMES = 10  # Track last 10 frames for FPS calculation
        
        # Frame queue for threaded capture - large size for robust mobile buffering
        # At 10 FPS, 100 frames = 10 seconds of buffering
        self.frame_queue = Queue(maxsize=100)  # Increased to 100 for maximum buffering
        self.running = True
        
        # Start capture thread
        self.capture_thread = threading.Thread(target=self._capture_thread, daemon=True)
        self.capture_thread.start()
        
        logger.info(f"ScreenCaptureTrack initialized: {width}x{height} @ {fps}fps")
    
    def _capture_thread(self):
        """Background thread that captures frames continuously."""
        last_capture = 0
        frames_produced = 0
        frames_dropped = 0
        
        # Create MSS instance inside the thread
        try:
            sct = mss()
            logger.info("MSS capture initialized in thread")
        except Exception as e:
            logger.error(f"Failed to initialize MSS in thread: {str(e)}")
            return
        
        while self.running:
            try:
                now = time.time()
                elapsed = now - last_capture
                
                # Maintain frame rate with more precise sleep
                if elapsed < self.frame_interval:
                    sleep_time = self.frame_interval - elapsed
                    if sleep_time > 0.001:  # Only sleep if significant time remains
                        time.sleep(sleep_time)
                    now = time.time()
                
                # Capture screen using thread-local MSS instance
                screenshot = sct.grab(self.monitor_info)
                
                # Convert to numpy array (BGRA format from MSS)
                img = np.array(screenshot, copy=False) 
                
                # --- Resize FIRST if necessary ---
                h, w, _ = img.shape
                if w != self.current_width or h != self.current_height:
                    logger.debug(f"Resizing frame from {w}x{h} to {self.current_width}x{self.current_height}")
                    img = cv2.resize(img, (self.current_width, self.current_height),
                                     interpolation=cv2.INTER_AREA)
                    # Sanity assert – remove in prod
                    assert img.shape[0] == self.current_height and img.shape[1] == self.current_width, "cv2.resize did not produce expected dimensions"
                    assert img.shape[0] % 16 == 0 and img.shape[1] % 16 == 0, f"Resized dimensions {img.shape[1]}x{img.shape[0]} are not 16-aligned"
                
                # --- Create VideoFrame (No padding needed now) ---
                frame = VideoFrame.from_ndarray(img, format="bgra")

                # --- Set Monotonic PTS using frame counter ---
                frame.pts = self._pts
                frame.time_base = self._time_base
                self._pts += 1 # Increment frame counter
                
                # --- Add to queue (non-blocking) ---
                try:
                    self.frame_queue.put_nowait(frame)
                    frames_produced += 1
                except Full:
                    # Queue full, drop frame
                    frames_dropped += 1
                    if frames_dropped % 10 == 0:  # Log every 10 dropped frames
                        logger.warning(f"Frame queue full, dropping frame. Stats: produced={frames_produced}, dropped={frames_dropped}")
                    pass
                
                last_capture = time.time()
                
                # Simple performance monitoring
                capture_time = time.time() - last_capture
                if len(self.frame_times) >= self.MAX_FRAME_TIMES:
                    self.frame_times.pop(0)
                self.frame_times.append(capture_time)
                
                # Adjust quality every 60 frames
                frame_count = len(self.frame_times)
                if frame_count == self.MAX_FRAME_TIMES and frame_count % 60 == 0:
                    avg_time = sum(self.frame_times) / frame_count
                    current_fps = 1 / avg_time if avg_time > 0 else 0
                    
                    if self.quality_degradation and current_fps < self.fps * 0.9:
                        # Calculate new dimensions, rounded down to multiple of 16
                        new_width  = int(self.current_width  * 0.7) // 16 * 16
                        new_height = int(self.current_height * 0.7) // 16 * 16
                        
                        # Keep at least 240x176 (16-aligned minimum)
                        if new_width >= 240 and new_height >= 176:
                            logger.warning(f"Reducing resolution to {new_width}x{new_height} due to low FPS ({current_fps:.1f} < {self.fps * 0.9:.1f})")
                            self.current_width = new_width
                            self.current_height = new_height
                            self.frame_times = [] # Reset frame times after change
                        else:
                            logger.warning(f"Cannot reduce resolution further ({self.current_width}x{self.current_height}), FPS might remain low.")
                
            except Exception as e:
                logger.error(f"Error in capture thread: {str(e)}")
                time.sleep(0.1)  # Avoid tight loop on error
    
    async def recv(self):
        """
        Get the next frame from the capture queue.
        
        This is called by aiortc to get the next frame to send.
        """
        try:
            # Get frame from queue with timeout
            frame = None
            try:
                # Try once with a short timeout
                frame = self.frame_queue.get(timeout=0.2)
            except Empty:
                logger.warning("Frame queue empty, creating emergency frame")
                # Create a colored emergency frame (red background with text)
                emergency_frame = VideoFrame(width=self.current_width, height=self.current_height)
                # Fill with red (or gray if we want less alarming)
                if hasattr(emergency_frame, 'planes') and emergency_frame.planes:
                    try:
                        # Try to fill with gray color (less alarming than red)
                        arr = np.full((self.current_height, self.current_width, 3), 
                                     [128, 128, 128], dtype=np.uint8)  # Medium gray
                        emergency_frame = VideoFrame.from_ndarray(arr, format='rgb24')
                    except Exception as plane_err:
                        logger.error(f"Could not set emergency frame color: {plane_err}")
                
                emergency_frame.pts = int(time.time() * 1000000)
                emergency_frame.time_base = fractions.Fraction(1, 1000000)
                return emergency_frame
            
            return frame
            
        except Exception as e:
            logger.error(f"Error getting frame: {str(e)}")
            # Return an emergency black frame on error
            try:
                emergency_frame = VideoFrame(width=self.current_width, height=self.current_height)
                emergency_frame.pts = int(time.time() * 1000000)
                emergency_frame.time_base = fractions.Fraction(1, 1000000)
                return emergency_frame
            except Exception as frame_err:
                logger.error(f"Could not create emergency frame: {frame_err}")
                # Last resort - create minimal frame
                return VideoFrame(width=320, height=240)
    
    def stop(self):
        """Stop the capture thread."""
        self.running = False
        if hasattr(self, 'capture_thread') and self.capture_thread.is_alive():
            try:
                self.capture_thread.join(timeout=1.0)
            except Exception as e:
                logger.error(f"Error stopping capture thread: {e}")
        super().stop() 