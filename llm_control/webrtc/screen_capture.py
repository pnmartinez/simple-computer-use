"""
Screen capture module for WebRTC.

This module provides a media track class that captures the screen
and makes it available for WebRTC streaming.
"""

import asyncio
import fractions
import logging
import time
from typing import Dict, Optional, List

# aiortc imports
from av import VideoFrame
from av.video.reformatter import VideoReformatter
from aiortc.mediastreams import MediaStreamTrack

# Screen capture import
from mss import mss
import numpy as np

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
                 fps: int = 30, 
                 width: int = 1280, 
                 height: int = 720,
                 monitor: Optional[int] = None,
                 quality_degradation: bool = True):
        """
        Initialize the screen capture track.
        
        Args:
            fps: Frames per second to target
            width: Output width of the video
            height: Output height of the video
            monitor: Monitor number to capture (None for entire screen)
            quality_degradation: Whether to lower quality if needed to maintain FPS
        """
        super().__init__()
        
        self.fps = fps
        self.width = width
        self.height = height
        self.monitor = monitor
        self.quality_degradation = quality_degradation
        
        # Frame timing
        self.frame_interval = 1 / fps
        self.last_frame_time = time.time()
        
        # Screen capture
        self.sct = mss()
        self.monitor_info = self._get_monitor_info(monitor)
        logger.info(f"Using monitor: {self.monitor_info}")
        
        # Video reformatter (for resizing frames)
        self.reformatter = VideoReformatter()
        
        # Performance tracking
        self.frame_times: List[float] = []
        self.MAX_FRAME_TIMES = 30  # Track last 30 frames for FPS calculation
        
        # Dynamic quality adjustment
        self.current_width = width
        self.current_height = height
        
        logger.info(f"ScreenCaptureTrack initialized: {width}x{height} @ {fps}fps")
    
    def _get_monitor_info(self, monitor_num: Optional[int]) -> Dict:
        """Get information about the monitor to capture."""
        monitors = self.sct.monitors
        
        # Default to entire screen (monitor 0)
        if monitor_num is None or monitor_num >= len(monitors):
            return monitors[0]
        
        # Specific monitor
        return monitors[monitor_num]
    
    async def recv(self):
        """
        Capture and return a video frame.
        
        This is called by aiortc to get the next frame to send.
        """
        # Control the frame rate
        now = time.time()
        elapsed = now - self.last_frame_time
        
        if elapsed < self.frame_interval:
            # Wait until it's time for the next frame
            await asyncio.sleep(self.frame_interval - elapsed)
            now = time.time()
        
        # Capture screen frame
        frame_start = time.time()
        screenshot = self.sct.grab(self.monitor_info)
        
        # Convert to a numpy array
        img = np.array(screenshot)
        
        # Performance tracking
        self.frame_times.append(time.time() - frame_start)
        if len(self.frame_times) > self.MAX_FRAME_TIMES:
            self.frame_times.pop(0)
        
        avg_frame_time = sum(self.frame_times) / len(self.frame_times)
        current_fps = 1 / avg_frame_time if avg_frame_time > 0 else 0
        
        # Dynamic quality adjustment if enabled and struggling with FPS
        if self.quality_degradation and current_fps < self.fps * 0.8 and len(self.frame_times) >= 5:
            # If we're below 80% of target FPS, reduce resolution by 10%
            new_width = int(self.current_width * 0.9)
            new_height = int(self.current_height * 0.9)
            
            # Don't go below 640x360
            if new_width >= 640 and new_height >= 360:
                logger.warning(f"Reducing resolution to {new_width}x{new_height} to maintain FPS. Current: {current_fps:.1f}fps")
                self.current_width = new_width
                self.current_height = new_height
                
                # Reset performance tracking after adjustment
                self.frame_times = []
        
        # Create a video frame from the numpy array
        frame = VideoFrame.from_ndarray(img, format="bgra")
        
        # Resize frame if needed
        if frame.width != self.current_width or frame.height != self.current_height:
            frame = self.reformatter.reformat(frame, 
                                             width=self.current_width, 
                                             height=self.current_height)
        
        # Set frame timing information
        frame.pts = int(now * 1000000)  # microseconds
        frame.time_base = fractions.Fraction(1, 1000000)
        
        # Update timing for next frame
        self.last_frame_time = now
        
        return frame 