"""
UI Detection module for LLM Control.

This module provides functionality for detecting UI elements on screen,
including text detection, icon recognition, and OCR.
"""

import os
import logging

# Global instances of models and resources
_ui_detector = None
_phi3_vision = None

# We'll avoid importing from screenshot.py directly to prevent circular imports
# Instead, we'll declare these functions here and implement them elsewhere

def take_screenshot(*args, **kwargs):
    """
    Delegated function that will be replaced at runtime.
    This avoids circular imports by providing a function stub.
    """
    from llm_control.screenshot import take_screenshot as _take_screenshot
    return _take_screenshot(*args, **kwargs)

def enhanced_screenshot_processing(*args, **kwargs):
    """
    Delegated function that will be replaced at runtime.
    This avoids circular imports by providing a function stub.
    """
    from llm_control.screenshot import enhanced_screenshot_processing as _enhanced_screenshot_processing
    return _enhanced_screenshot_processing(*args, **kwargs)

# Export element_finder functions
from llm_control.ui_detection.element_finder import (
    detect_ui_elements_with_yolo,
    detect_text_regions,
    get_ui_description
)

# Each submodule will be imported as needed to avoid circular imports
# We won't import OCR and element_finder here - they'll be imported when needed

# Get the package logger
logger = logging.getLogger("llm-pc-control")

__all__ = [
    'take_screenshot', 
    'enhanced_screenshot_processing',
    'detect_ui_elements_with_yolo',
    'detect_text_regions',
    'get_ui_description'
]
