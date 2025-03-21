"""
LLM module for text extraction and intent detection.

This module provides functions for:
1. Extracting text to type from user commands
2. Detecting intent from user commands
3. Executing commands with LLM processing
"""

import logging
from llm_control.llm.text_extraction import extract_text_to_type_with_llm, ensure_text_is_safe_for_typewrite
from llm_control.llm.intent_detection import extract_target_text_with_llm

# Import simple_executor directly only if import succeeds
try:
    from llm_control.llm.simple_executor import execute_command_with_llm
except ImportError:
    # Define a stub function if we can't import
    def execute_command_with_llm(*args, **kwargs):
        return {
            "success": False,
            "error": "simple_executor module not available"
        }

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'extract_text_to_type_with_llm',
    'ensure_text_is_safe_for_typewrite',
    'extract_target_text_with_llm',
    'execute_command_with_llm'
]
