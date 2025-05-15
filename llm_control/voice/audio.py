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

# Try to import the model manager
try:
    from llm_control.voice.model_manager import WhisperModelManager
    USE_MODEL_MANAGER = True
    logger.info("Using WhisperModelManager for transcription")
except ImportError:
    USE_MODEL_MANAGER = False
    logger.warning("WhisperModelManager not available, falling back to direct loading")

# Constants
DEFAULT_LANGUAGE = os.environ.get("DEFAULT_LANGUAGE", "es")
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "medium")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# Flag to track low GPU memory state
_low_gpu_memory = False

logger.debug(f"Audio module initialized with:")
logger.debug(f"- DEFAULT_LANGUAGE: {DEFAULT_LANGUAGE}")
logger.debug(f"- WHISPER_MODEL_SIZE: {WHISPER_MODEL_SIZE}")
logger.debug(f"- OLLAMA_MODEL: {OLLAMA_MODEL}")
logger.debug(f"- OLLAMA_HOST: {OLLAMA_HOST}")

def transcribe_audio(
    audio_data, 
    language=None, 
    model_size='medium', 
    fallback_to_cpu=True, 
    translate=False
):
    """
    Transcribe audio data using Whisper ASR model.
    
    Args:
        audio_data: Audio data bytes
        language: Language code (optional, model will auto-detect if not provided)
        model_size: Size of the Whisper model to use (tiny, base, small, medium, large)
        fallback_to_cpu: Whether to fall back to CPU if GPU fails
        translate: Whether to translate to English
        
    Returns:
        Dictionary with transcription results
    """
    import gc
    import tempfile
    import os
    import time
    import numpy as np
    
    # Import whisper here to avoid early loading
    try:
        from llm_control.voice.model_manager import WhisperModelManager
    except ImportError:
        try:
            import whisper
            logger.warning("WhisperModelManager not found, falling back to direct Whisper import")
        except ImportError:
            logger.error("Failed to import whisper module")
            return {"error": "Whisper is not installed. Install with 'pip install -U openai-whisper'"}
    
    # Set up a temp file to store the audio data
    temp_file = None
    
    try:
        # Track memory before starting
        try:
            import torch
            if torch.cuda.is_available():
                before_mem = torch.cuda.memory_allocated() / (1024 ** 3)
                logger.info(f"CUDA memory before transcription: {before_mem:.2f} GiB")
        except Exception as e:
            logger.warning(f"Failed to check initial CUDA memory: {e}")
        
        # Initialize the result dictionary
        result = {
            "text": None,
            "language": None,
            "time_to_transcribe": None,
            "model_size": model_size,
            "detected_language": None,
            "device": None,
            "timestamp": time.time(),
            "error": None
        }
        
        # Save the audio data to a temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_file = f.name
            logger.debug(f"Saved {len(audio_data)} bytes of audio data to {temp_file}")
        
        # Check if we have enough GPU memory (cache the result)
        global _low_gpu_memory
        use_gpu = not _low_gpu_memory
        use_cpu = not use_gpu
        
        # Try to load the whisper model - use WhisperModelManager if available
        load_start_time = time.time()
        
        try:
            # First try to load with GPU if we think we have enough memory
            device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
            result["device"] = device
            logger.info(f"Using device {device} for Whisper model (model_size={model_size})")
            
            try:
                if 'WhisperModelManager' in locals() or 'WhisperModelManager' in globals():
                    model = WhisperModelManager.get_model(model_size)
                    logger.info("Successfully loaded Whisper model from WhisperModelManager")
                else:
                    model = whisper.load_model(model_size, device=device)
                    logger.info("Successfully loaded Whisper model directly")
                
                load_time = time.time() - load_start_time
                logger.info(f"Loaded Whisper model in {load_time:.2f} seconds on {device}")
            except RuntimeError as e:
                if "CUDA out of memory" in str(e) and fallback_to_cpu:
                    # Set the flag to avoid future GPU attempts
                    _low_gpu_memory = True
                    use_cpu = True
                    logger.warning(f"CUDA out of memory when loading Whisper model. Falling back to CPU.")
                    device = "cpu"
                    result["device"] = device
                    
                    try:
                        if 'WhisperModelManager' in locals() or 'WhisperModelManager' in globals():
                            # Force reload on CPU
                            WhisperModelManager.release_model()
                            torch.cuda.empty_cache()
                            gc.collect()
                            
                            # Reload with CPU
                            with torch.device("cpu"):
                                model = WhisperModelManager.get_model(model_size)
                        else:
                            model = whisper.load_model(model_size, device=device)
                        
                        load_time = time.time() - load_start_time
                        logger.info(f"Loaded Whisper model on CPU in {load_time:.2f} seconds after GPU failure")
                    except Exception as e2:
                        logger.error(f"Failed to load Whisper model on CPU after GPU failure: {e2}")
                        result["error"] = f"Failed to load model on CPU: {e2}"
                        return result
                else:
                    # Some other error occurred
                    logger.error(f"Error loading Whisper model: {e}")
                    result["error"] = f"Failed to load model: {e}"
                    return result
            except Exception as e:
                logger.error(f"Error loading Whisper model: {e}")
                result["error"] = f"Error loading model: {e}"
                return result
            
            # Start transcription
            transcribe_start_time = time.time()
            
            try:
                # Transcribe
                transcribe_options = {}
                
                # Add language if specified
                if language:
                    transcribe_options["language"] = language
                
                # Add translation flag if requested
                if translate:
                    transcribe_options["task"] = "translate"
                
                # Run transcription
                logger.debug(f"Starting transcription with options: {transcribe_options}")
                transcription = model.transcribe(temp_file, **transcribe_options)
                
                # Update result
                if transcription:
                    result["text"] = transcription.get("text", "").strip()
                    result["detected_language"] = transcription.get("language", None)
                    result["language"] = language or result["detected_language"]
                    
                    # Calculate time
                    transcribe_time = time.time() - transcribe_start_time
                    result["time_to_transcribe"] = transcribe_time
                    logger.info(f"Transcription completed in {transcribe_time:.2f} seconds")
                    
                    # Log detected language
                    if result["detected_language"]:
                        logger.info(f"Detected language: {result['detected_language']}")
                else:
                    result["error"] = "Transcription failed to return any results"
                    logger.error("Transcription failed to return any results")
            
            except Exception as e:
                logger.error(f"Error during transcription: {e}")
                result["error"] = f"Error during transcription: {e}"
            
            # Attempt to free memory
            if device == "cuda" and torch.cuda.is_available():
                try:
                    after_transcription_mem = torch.cuda.memory_allocated() / (1024 ** 3)
                    logger.info(f"CUDA memory after transcription (before cleanup): {after_transcription_mem:.2f} GiB")
                    
                    # Don't delete the model if using the manager
                    if 'WhisperModelManager' not in globals() and 'model' in locals():
                        # Only delete model if it's a direct Whisper model
                        del model
                    
                    # Free CUDA memory
                    torch.cuda.empty_cache()
                    gc.collect()
                    
                    # Log memory after cleanup
                    after_cleanup_mem = torch.cuda.memory_allocated() / (1024 ** 3)
                    logger.info(f"CUDA memory after cleanup: {after_cleanup_mem:.2f} GiB")
                    logger.info(f"Memory freed: {after_transcription_mem - after_cleanup_mem:.2f} GiB")
                except Exception as e:
                    logger.warning(f"Error during memory cleanup: {e}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error in transcription process: {e}")
            result["error"] = f"Error in transcription process: {e}"
            return result
    
    finally:
        # Clean up temp file
        if temp_file and os.path.exists(temp_file):
            try:
                os.unlink(temp_file)
                logger.debug(f"Removed temporary audio file: {temp_file}")
            except Exception as e:
                logger.warning(f"Error removing temporary audio file: {e}")
        
        # Force garbage collection at the end
        gc.collect()
        if 'torch' in locals() and torch.cuda.is_available():
            torch.cuda.empty_cache()

def translate_text(text, model=OLLAMA_MODEL, ollama_host=OLLAMA_HOST) -> Optional[str]:
    """
    Translate text using the Ollama LLM.
    
    Args:
        text: Text to translate
        model: Ollama model to use
        ollama_host: Ollama API host
        
    Returns:
        Translated text or None if translation failed
    """
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
