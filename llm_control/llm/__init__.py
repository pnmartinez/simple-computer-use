import logging
from llm_control.llm.text_extraction import extract_text_to_type_with_llm, ensure_text_is_safe_for_typewrite
from llm_control.llm.intent_detection import extract_target_text_with_llm

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'extract_text_to_type_with_llm',
    'ensure_text_is_safe_for_typewrite',
    'extract_target_text_with_llm'
]
