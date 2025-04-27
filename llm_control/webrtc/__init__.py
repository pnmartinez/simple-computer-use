"""
WebRTC Screen Streaming Package.

This package provides functionality for streaming the screen from a Debian server
to an Android client using WebRTC technology.
"""

from llm_control.webrtc.server import create_app, run_server
from llm_control.webrtc.screen_capture import ScreenCaptureTrack

__all__ = [
    # Server
    'create_app', 'run_server',
    
    # Media
    'ScreenCaptureTrack',
] 