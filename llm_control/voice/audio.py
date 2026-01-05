"""
Audio processing module for voice control.

This module handles audio transcription and translation.
"""

import os
import sys
import tempfile
import logging
import requests
import time
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger("voice-control-audio")

# Import from our modules
from llm_control.voice.utils import clean_llm_response, DEBUG, is_debug_mode
from llm_control.voice.prompts import TRANSLATION_PROMPT

# Configuration getter functions (read dynamically from environment)
def get_default_language():
    return os.environ.get("DEFAULT_LANGUAGE", "es")

def get_whisper_model_size():
    return os.environ.get("WHISPER_MODEL_SIZE", "large")

def get_ollama_model():
    return os.environ.get("OLLAMA_MODEL", "gemma3:12b")

def get_ollama_host():
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")

logger.debug(f"Audio module configuration getters initialized (values read dynamically from environment)")

# Global variable to store the Whisper model
_whisper_model = None
_current_model_size = None

def initialize_whisper_model(model_size=None):
    if model_size is None:
        model_size = get_whisper_model_size()
    """
    Initialize the Whisper model once at startup.
    Reinitializes if model_size changes.
    
    Args:
        model_size: Whisper model size to load
        
    Returns:
        The loaded model, or None if initialization failed
    """
    global _whisper_model, _current_model_size
    
    # If model is already initialized with the same size, return it
    if _whisper_model is not None and _current_model_size == model_size:
        logger.debug(f"Whisper model already initialized with size: {model_size}")
        return _whisper_model
    
    # If model size changed, clear the old model
    if _whisper_model is not None and _current_model_size != model_size:
        logger.info(f"Whisper model size changed from {_current_model_size} to {model_size}, reinitializing...")
        # Clear the old model to free memory
        _whisper_model = None
        import gc
        gc.collect()
        # Clear CUDA cache if available
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA cache after unloading old model")
        except Exception:
            pass
    
    try:
        import whisper
        import torch
        
        # Clear CUDA cache before loading new model (helps with OOM recovery)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.debug("Cleared CUDA cache before loading model")
        
        logger.info(f"Initializing Whisper model with size: {model_size}")
        start_time = time.time()
        _whisper_model = whisper.load_model(model_size)
        _current_model_size = model_size  # Store the current model size
        load_time = time.time() - start_time
        logger.info(f"Whisper model initialized in {load_time:.2f} seconds")
        
        # Log CUDA availability and memory usage
        if hasattr(torch, 'cuda') and torch.cuda.is_available():
            logger.info(f"CUDA is available. Using device: {torch.cuda.get_device_name(0)}")
            # Log memory usage to help diagnose VRAM issues
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            logger.info(f"GPU memory: {allocated:.2f}GB allocated, {reserved:.2f}GB reserved")
        else:
            logger.info("CUDA is not available. Using CPU.")
            
        return _whisper_model
        
    except Exception as e:
        logger.error(f"Error initializing Whisper model: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        # Clear CUDA cache on failure to help recovery
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.debug("Cleared CUDA cache after model loading failure")
        except Exception:
            pass
        return None

# NOTE: Whisper model initialization is now done in run_server() AFTER 
# environment variables are set from command-line arguments.
# This prevents loading the wrong model size (e.g., "large" default) 
# before the user's configured size is available.

def transcribe_audio(audio_data, model_size=None, language=None) -> Dict[str, Any]:
    if model_size is None:
        model_size = get_whisper_model_size()
    if language is None:
        language = get_default_language()
    """
    Transcribe audio data using Whisper.
    
    Args:
        audio_data: Audio data as bytes
        model_size: Whisper model size
        language: Language code
        
    Returns:
        Dictionary with transcription results
    """
    logger.debug(f"Transcribing audio with Whisper model size: {model_size}, language: {language}")
    logger.debug(f"Audio data size: {len(audio_data) if audio_data else 0} bytes")
    
    global _whisper_model
    
    try:
        import whisper
        import numpy as np
        import torch
        
        # Create a temporary file for the audio data
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(audio_data)
            logger.debug(f"Wrote audio data to temporary file: {temp_filename}")
        
        try:
            # Use the pre-initialized model or initialize it if needed
            model = _whisper_model
            
            # If the model is not initialized or a different size is requested, initialize it
            if model is None or (hasattr(model, 'model_size') and model.model_size != model_size):
                logger.debug(f"Initializing Whisper model on-demand with size: {model_size}")
                start_time = time.time()
                model = whisper.load_model(model_size)
                load_time = time.time() - start_time
                logger.debug(f"Loaded Whisper model in {load_time:.2f} seconds")
                
                # Update the global model if it's the standard size
                if model_size == get_whisper_model_size():
                    _whisper_model = model
            
            # Transcribe the audio
            logger.debug(f"Starting transcription...")
            start_time = time.time()
            result = model.transcribe(
                temp_filename,
                language=language if language != "auto" else None,
                fp16=torch.cuda.is_available()
            )
            transcription_time = time.time() - start_time
            logger.debug(f"Transcription completed in {transcription_time:.2f} seconds")
            
            text = result.get("text", "").strip()
            logger.debug(f"Transcription result: '{text[:100]}{'...' if len(text) > 100 else ''}'")
            
            # Add detailed debug info
            if DEBUG:
                segments = result.get("segments", [])
                logger.debug(f"Transcription has {len(segments)} segments")
                for i, segment in enumerate(segments[:3]):  # Log first 3 segments
                    logger.debug(f"Segment {i}: start={segment.get('start')}, end={segment.get('end')}, text='{segment.get('text')}'")
                if len(segments) > 3:
                    logger.debug(f"... and {len(segments) - 3} more segments")
            
            return {
                "text": text,
                "language": result.get("language", language),
                "segments": result.get("segments", [])
            }
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "error": f"Error transcribing audio: {str(e)}",
                "text": ""
            }
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_filename)
                logger.debug(f"Removed temporary file: {temp_filename}")
            except:
                logger.warning(f"Failed to remove temporary file: {temp_filename}")
                pass
    
    except ImportError as e:
        logger.error(f"Failed to import required module: {str(e)}")
        return {
            "error": f"Required module not installed: {str(e)}",
            "text": ""
        }
    except Exception as e:
        logger.error(f"Error setting up transcription: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "error": f"Error setting up transcription: {str(e)}",
            "text": ""
        }

def translate_text(text, model=None, ollama_host=None) -> Optional[str]:
    """
    Translate text using the Ollama LLM.
    
    Args:
        text: Text to translate
        model: Ollama model to use
        ollama_host: Ollama API host
        
    Returns:
        Translated text or None if translation failed
    """
    if model is None:
        model = get_ollama_model()
    if ollama_host is None:
        ollama_host = get_ollama_host()
    logger.debug(f"Translating text with model: {model}")
    logger.debug(f"Text to translate (first 100 chars): '{text[:100]}{'...' if len(text) > 100 else ''}'")
    
    if not text or not text.strip():
        logger.warning("Empty text provided for translation")
        return None
    
    try:
        # Prepare the prompt for translation using the template from prompts.py
        prompt = TRANSLATION_PROMPT.format(text=text)
        
        logger.debug(f"Sending translation request to Ollama API at {ollama_host}")
        
        # Make API request to Ollama
        start_time = time.time()
        response = requests.post(
            f"{ollama_host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.1  # Use low temperature for more deterministic translation
            },
            timeout=30
        )
        
        request_time = time.time() - start_time
        logger.debug(f"Ollama API request completed in {request_time:.2f} seconds with status code: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Error from Ollama API: {response.status_code}")
            logger.error(f"Response content: {response.text[:500]}")
            return None
        
        # Parse response
        result = response.json()
        translated_text = result["response"].strip()
        logger.debug(f"Raw translation from Ollama: '{translated_text[:100]}{'...' if len(translated_text) > 100 else ''}'")
        
        # Clean the response
        cleaned_text = clean_llm_response(translated_text)
        logger.debug(f"Cleaned translation: '{cleaned_text[:100]}{'...' if len(cleaned_text) > 100 else ''}'")
        
        return cleaned_text
    
    except Exception as e:
        logger.error(f"Error translating text: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None
