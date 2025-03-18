"""
UI Detection module for LLM Control.

This module provides functionality for detecting UI elements on screen,
including text detection, icon recognition, and OCR.
"""

import os
import logging

# Import from our dedicated screenshot module to avoid circular imports
from llm_control.screenshot import take_screenshot, enhanced_screenshot_processing

# Each submodule will be imported as needed to avoid circular imports
# We won't import OCR and element_finder here - they'll be imported when needed

# Get the package logger
logger = logging.getLogger("llm-pc-control")

__all__ = ['take_screenshot', 'enhanced_screenshot_processing']
