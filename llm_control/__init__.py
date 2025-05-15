"""
LLM Control Package.

This package provides functionality for controlling a computer using natural language
commands and large language models.
"""

from typing import Dict, Any, List, Optional, Union

# Version information
__version__ = "1.0.0"

# We are no longer importing the constants from command_processing here
# Instead they will be directly imported where needed

# Voice control imports
from llm_control.voice.server import app as voice_app
from llm_control.voice.server import run_server as run_voice_server
from llm_control.voice.audio import transcribe_audio, translate_text
from llm_control.voice.commands import (
    validate_pyautogui_cmd, 
    split_command_into_steps, 
    identify_ocr_targets,
    generate_pyautogui_actions
)
from llm_control.voice.screenshots import (
    capture_screenshot,
    capture_with_highlight,
    get_latest_screenshots,
    list_all_screenshots
)
from llm_control.voice.utils import (
    get_screenshot_dir,
    error_response,
    test_cuda_availability
)

# WebRTC screen streaming imports
try:
    from llm_control.webrtc.server import create_app as create_webrtc_app
    from llm_control.webrtc.server import run_server as run_webrtc_server
    from llm_control.webrtc.screen_capture import ScreenCaptureTrack
    
    HAS_WEBRTC = True
except ImportError:
    HAS_WEBRTC = False

__all__ = [
    # Package information
    "__version__",
    
    # Voice control
    "voice_app", "run_voice_server",
    "transcribe_audio", "translate_text",
    "validate_pyautogui_cmd", "split_command_into_steps", 
    "identify_ocr_targets", "generate_pyautogui_actions",
    "capture_screenshot", "capture_with_highlight",
    "get_latest_screenshots", "list_all_screenshots",
    "get_screenshot_dir", "error_response", "test_cuda_availability",
    
    # WebRTC screen streaming
    "HAS_WEBRTC",
]

# Add WebRTC exports conditionally
if HAS_WEBRTC:
    __all__.extend([
        "create_webrtc_app", "run_webrtc_server", "ScreenCaptureTrack"
    ])

import os
import logging

# Setup logging
logger = logging.getLogger("llm-pc-control")
