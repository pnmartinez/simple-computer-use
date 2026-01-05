"""
Ollama utility functions for model checking and error handling.
"""

import logging
import requests
from typing import Optional, Tuple

logger = logging.getLogger("llm-pc-control")


def check_ollama_model(model: str, host: str = "http://localhost:11434", timeout: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Check if an Ollama model is available.
    
    Args:
        model: The model name to check (e.g., "llama3.1:8b")
        host: The Ollama API host (default: "http://localhost:11434")
        timeout: Request timeout in seconds (default: 5)
        
    Returns:
        Tuple of (is_available, error_message)
        - is_available: True if model exists, False otherwise
        - error_message: None if available, error description if not
    """
    try:
        # Check if Ollama server is running
        try:
            response = requests.get(f"{host}/api/tags", timeout=timeout)
            if response.status_code != 200:
                return False, f"Ollama server not responding at {host}"
        except requests.exceptions.RequestException as e:
            return False, f"Ollama server not available at {host}: {str(e)}"
        
        # Get list of available models
        response = requests.get(f"{host}/api/tags", timeout=timeout)
        if response.status_code != 200:
            return False, f"Failed to query Ollama models: HTTP {response.status_code}"
        
        models_data = response.json()
        available_models = [model_info.get("name", "") for model_info in models_data.get("models", [])]
        
        # Check if the requested model is in the list (exact match required)
        if model in available_models:
            return True, None
        
        # If user specified model without tag (e.g., "llama3.1"), check if any version exists
        # and match the default (":latest" tag)
        if ":" not in model:
            # Check for exact match with :latest tag
            if f"{model}:latest" in available_models:
                return True, None
        
        return False, None
        
    except Exception as e:
        logger.error(f"Error checking Ollama model: {str(e)}")
        return False, f"Error checking model availability: {str(e)}"


def get_model_not_found_message(model: str) -> str:
    """
    Generate a helpful error message when a model is not found.
    
    Args:
        model: The model name that was not found
        
    Returns:
        A formatted error message with instructions
    """
    return f"Ollama model '{model}' not found. Run: ollama pull {model}"


def check_ollama_model_with_message(model: str, host: str = "http://localhost:11434", timeout: int = 5) -> Tuple[bool, Optional[str]]:
    """
    Check if an Ollama model is available and return a user-friendly message if not.
    
    Args:
        model: The model name to check (e.g., "llama3.1:8b")
        host: The Ollama API host (default: "http://localhost:11434")
        timeout: Request timeout in seconds (default: 5)
        
    Returns:
        Tuple of (is_available, message)
        - is_available: True if model exists, False otherwise
        - message: Success message or error message with pull instructions
    """
    is_available, error = check_ollama_model(model, host, timeout)
    
    if is_available:
        return True, f"Model '{model}' is available"
    else:
        if error and "not available" in error.lower() or "not responding" in error.lower():
            # Server issue, return the error
            return False, error
        else:
            # Model not found, return helpful message
            return False, get_model_not_found_message(model)

