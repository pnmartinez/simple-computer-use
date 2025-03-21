"""
Voice Control Package.

This package provides functionality for processing voice commands and controlling
the desktop with natural language.
"""

from llm_control.voice.server import app, run_server
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

__all__ = [
    # Server
    'app', 'run_server',
    
    # Audio
    'transcribe_audio', 'translate_text',
    
    # Commands
    'validate_pyautogui_cmd', 'split_command_into_steps', 
    'identify_ocr_targets', 'generate_pyautogui_actions',
    
    # Screenshots
    'capture_screenshot', 'capture_with_highlight',
    'get_latest_screenshots', 'list_all_screenshots',
    
    # Utils
    'get_screenshot_dir', 'error_response', 'test_cuda_availability'
]
