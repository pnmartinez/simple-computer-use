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
        self._pts = 0 # Frame counter for PTS
        self._time_base = fractions.Fraction(1, 1_000_000) # Keep high precision timebase for now
        
        # Track last frame delivery time to throttle consumption
        self.last_frame_delivery = time.time()
        
        # Statistics tracking
        self.frames_produced = 0
        self.frames_dropped = 0
        self.frames_skipped = 0  # New counter for skipped frames
        
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
        
        # Performance tracking
        self.frame_times: List[float] = []
        self.MAX_FRAME_TIMES = 10  # Track last 10 frames for FPS calculation
        
        # Modify the initial queue size based on connection state
        self.frame_queue = Queue(maxsize=5)  # Start with larger buffer
        
        # For frame skipping, we'll keep the latest frame outside the queue
        self.latest_frame = None
        self.latest_frame_lock = threading.Lock()
        
        # For Firefox stuttering prevention - note we can't directly set key_frame
        # on VideoFrame objects, but we can track when to signal for keyframes
        self.last_keyframe_time = time.time()
        self.force_keyframe = False  # Flag for signaling keyframe at encoder level
        
        # Performance option for hardware acceleration
        self.use_hw_accel = False  # Can be made configurable
        
        self.running = True
        
        # Start capture thread
        self.capture_thread = threading.Thread(target=self._capture_thread, daemon=True)
        self.capture_thread.start()
        
        logger.info(f"ScreenCaptureTrack initialized: {width}x{height} @ {fps}fps with frame skipping")
    
    def _capture_thread(self):
        """Background thread that captures frames continuously."""
        last_capture = 0
        
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
                
                # Check if keyframe should be forced (for Firefox compatibility)
                current_time = time.time()
                if current_time - self.last_keyframe_time > 5:  # Every 5 seconds
                    self.force_keyframe = True
                    self.last_keyframe_time = current_time
                    logger.debug("Requesting keyframe (for streaming stability)")
                
                # Capture screen using thread-local MSS instance
                capture_start = time.time()
                screenshot = sct.grab(self.monitor_info)
                capture_time = time.time() - capture_start
                
                # Convert to numpy array (BGRA format from MSS)
                array_start = time.time()
                img = np.array(screenshot, copy=False) 
                array_time = time.time() - array_start
                
                # --- Resize FIRST if necessary ---
                resize_start = time.time()
                h, w, _ = img.shape
                if w != self.current_width or h != self.current_height:
                    logger.debug(f"Resizing frame from {w}x{h} to {self.current_width}x{self.current_height}")
                    img = cv2.resize(img, (self.current_width, self.current_height),
                                     interpolation=cv2.INTER_AREA)
                    # Sanity assert – remove in prod
                    assert img.shape[0] == self.current_height and img.shape[1] == self.current_width, "cv2.resize did not produce expected dimensions"
                    assert img.shape[0] % 16 == 0 and img.shape[1] % 16 == 0, f"Resized dimensions {img.shape[1]}x{img.shape[0]} are not 16-aligned"
                resize_time = time.time() - resize_start
                
                # --- Create VideoFrame (No padding needed now) ---
                frame_start = time.time()
                if self.use_hw_accel and hasattr(VideoFrame, 'from_ndarray_with_hwaccel'):
                    frame = VideoFrame.from_ndarray_with_hwaccel(img, format="bgra")
                else:
                    frame = VideoFrame.from_ndarray(img, format="bgra")
                frame_time = time.time() - frame_start

                # --- Set Monotonic PTS using frame counter ---
                frame.pts = self._pts
                frame.time_base = self._time_base
                self._pts += 1 # Increment frame counter
                
                # Log individual processing times for profiling
                logger.debug(f"PROFILE - Screen capture: {capture_time*1000:.2f}ms")
                logger.debug(f"PROFILE - NumPy array conversion: {array_time*1000:.2f}ms")
                logger.debug(f"PROFILE - Resize operation: {resize_time*1000:.2f}ms")
                logger.debug(f"PROFILE - VideoFrame creation: {frame_time*1000:.2f}ms")
                
                # --- Always update latest frame ---
                with self.latest_frame_lock:
                    self.latest_frame = frame
                
                # --- Try to add to queue if not full ---
                queue_start = time.time()
                queue_size = self.frame_queue.qsize()
                try:
                    # Only add to queue if it's not too full
                    if queue_size < self.frame_queue.maxsize:
                        self.frame_queue.put_nowait(frame)
                        self.frames_produced += 1
                        logger.debug(f"Frame added to queue. Current size: {self.frame_queue.qsize()}/{self.frame_queue.maxsize}")
                    else:
                        # Queue is full, this means we're falling behind
                        # We'll skip this frame (the latest_frame reference is still updated)
                        self.frames_skipped += 1
                        if self.frames_skipped % 10 == 0:  # Log every 10 skipped frames
                            logger.warning(f"Queue full, frame skipped. Stats: produced={self.frames_produced}, skipped={self.frames_skipped}")
                except Full:
                    # Should never happen since we check qsize first
                    self.frames_skipped += 1
                    logger.warning(f"Unexpected queue full error. Frame skipped.")
                    pass
                
                queue_time = time.time() - queue_start
                logger.debug(f"PROFILE - Queue operation: {queue_time*1000:.2f}ms")
                
                process_time = time.time() - now  # Processing time
                last_capture = time.time() 
                logger.debug(f"PROFILE - Processing time: {process_time*1000:.2f}ms for frame {self._pts-1}")
                
                # Track frame intervals instead of processing time for FPS calculation
                if hasattr(self, 'last_frame_timestamp'):
                    frame_interval = last_capture - self.last_frame_timestamp
                    if len(self.frame_times) >= self.MAX_FRAME_TIMES:
                        self.frame_times.pop(0)
                    self.frame_times.append(frame_interval)
                self.last_frame_timestamp = last_capture
                
                # Adjust quality every 60 frames
                frame_count = len(self.frame_times)
                if frame_count == self.MAX_FRAME_TIMES and (self._pts % 60 == 0):
                    avg_time = sum(self.frame_times) / frame_count
                    current_fps = 1 / avg_time if avg_time > 0 else 0
                    
                    # Log skipped frames statistics
                    log_msg = f"Performance stats: FPS={current_fps:.1f}, produced={self.frames_produced}, skipped={self.frames_skipped}"
                    if self.frames_skipped > 0:
                        logger.warning(log_msg)
                    else:
                        logger.info(log_msg)
                    
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
        Get the next frame from the capture queue or the latest frame if queue is empty.
        
        This is called by aiortc to get the next frame to send.
        Throttled to match the target FPS rate and implements frame skipping
        to reduce latency when falling behind.
        """
        try:
            # Check if we need to request a keyframe
            # In aiortc, this is handled by setting a flag that the encoder will check
            need_keyframe = False
            if self.force_keyframe:
                need_keyframe = True
                self.force_keyframe = False
                # This will be picked up by RTCRtpSender and trigger PLI/FIR
                self._queue_keyframe = True
            
            # Throttle consumption to match frame rate
            now = time.time()
            time_since_last_frame = now - self.last_frame_delivery
            
            # If we're being called too frequently, delay to match target framerate
            if time_since_last_frame < self.frame_interval:
                # Sleep for the remaining time in the frame interval
                delay = self.frame_interval - time_since_last_frame
                # Only sleep if the delay is significant
                if delay > 0.001:
                    await asyncio.sleep(delay)
            
            # Try to get a frame from the queue first
            try:
                # Short timeout since we have a fallback
                frame = self.frame_queue.get(timeout=0.05)
                self.last_frame_delivery = time.time()
                logger.debug(f"Retrieved frame from queue. Queue size: {self.frame_queue.qsize()}/{self.frame_queue.maxsize}")
                
                # Log keyframe request if needed
                if need_keyframe:
                    logger.info("Keyframe requested to help prevent freezing")
                
                return frame
            except Empty:
                # Queue is empty, use the latest frame if available
                with self.latest_frame_lock:
                    if self.latest_frame is not None:
                        self.last_frame_delivery = time.time()
                        logger.debug("Queue empty, using latest frame directly (frame skipping)")
                        return self.latest_frame
                
                # If we're here, we have no frames at all
                logger.warning("No frames available (both queue and latest frame). Creating emergency frame.")
                self.last_frame_delivery = time.time()
                
                # Create an emergency frame
                emergency_frame = VideoFrame(width=self.current_width, height=self.current_height)
                if hasattr(emergency_frame, 'planes') and emergency_frame.planes:
                    try:
                        # Gray color for emergency frame
                        arr = np.full((self.current_height, self.current_width, 3), 
                                     [128, 128, 128], dtype=np.uint8)  # Medium gray
                        emergency_frame = VideoFrame.from_ndarray(arr, format='rgb24')
                    except Exception as plane_err:
                        logger.error(f"Could not set emergency frame color: {plane_err}")
                
                emergency_frame.pts = int(time.time() * 1000000)
                emergency_frame.time_base = fractions.Fraction(1, 1000000)
                
                # Force keyframe when recovering from emergency
                self._queue_keyframe = True
                
                return emergency_frame
            
        except Exception as e:
            logger.error(f"Error getting frame: {str(e)}")
            self.last_frame_delivery = time.time()
            
            # Return an emergency frame on error
            try:
                emergency_frame = VideoFrame(width=self.current_width, height=self.current_height)
                emergency_frame.pts = int(time.time() * 1000000)
                emergency_frame.time_base = fractions.Fraction(1, 1000000)
                
                # Force keyframe when recovering from error
                self._queue_keyframe = True
                
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