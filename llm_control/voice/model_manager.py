"""
Model manager for voice services.

This module provides singleton managers for models to efficiently manage memory usage.
"""

import os
import gc
import logging
import threading
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger("voice-model-manager")

# Import optional dependencies
try:
    import torch
except ImportError:
    logger.warning("PyTorch not available. Some features will be disabled.")

# Global variables for model instances and locks
_whisper_model = None
_whisper_model_size = None
_whisper_lock = threading.RLock()
_model_usage_count = 0
_max_usage_before_reload = 2  # Reduced from 5 to 2 to prevent memory build-up

class WhisperModelManager:
    """
    Singleton manager for Whisper model.
    Ensures the model is loaded only once and properly managed for memory efficiency.
    """
    
    @staticmethod
    def get_model(model_size: str) -> Any:
        """
        Get the Whisper model instance.
        
        Args:
            model_size: Size of the Whisper model to load
            
        Returns:
            Whisper model instance
        """
        global _whisper_model, _whisper_model_size, _model_usage_count
        
        with _whisper_lock:
            # Import whisper here to avoid early loading
            try:
                import whisper
            except ImportError:
                logger.error("Failed to import whisper module")
                raise ImportError("Whisper is not installed. Install with 'pip install -U openai-whisper'")
            
            # Check if we need to reload the model
            if (_whisper_model is None or 
                _whisper_model_size != model_size or 
                _model_usage_count >= _max_usage_before_reload):
                
                # Clear existing model if it exists
                if _whisper_model is not None:
                    WhisperModelManager.release_model()
                
                # Clear GPU cache before loading new model
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    gc.collect()
                
                logger.info(f"Loading Whisper model: {model_size} (new instance)")
                _whisper_model = whisper.load_model(model_size)
                _whisper_model_size = model_size
                _model_usage_count = 0
                
            # Increment usage count
            _model_usage_count += 1
            logger.debug(f"Model usage count: {_model_usage_count}/{_max_usage_before_reload}")
            
            return _whisper_model
    
    @staticmethod
    def release_model() -> None:
        """
        Release the Whisper model from memory
        """
        global _whisper_model, _whisper_model_size
        
        with _whisper_lock:
            if _whisper_model is not None:
                logger.info("Releasing Whisper model from memory")
                try:
                    # Get memory before release for logging
                    if torch.cuda.is_available():
                        before_mem = torch.cuda.memory_allocated() / (1024 ** 3)
                    
                    # Delete model and clear references
                    del _whisper_model
                    _whisper_model = None
                    _whisper_model_size = None
                    
                    # Clean up CUDA memory
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        after_mem = torch.cuda.memory_allocated() / (1024 ** 3)
                        logger.info(f"CUDA memory freed: {before_mem - after_mem:.2f}GB")
                    
                    # Force garbage collection
                    gc.collect()
                    gc.collect()  # Run twice to ensure cyclic references are cleared
                    
                    logger.info("Successfully released Whisper model")
                except Exception as e:
                    logger.error(f"Error releasing Whisper model: {e}")
    
    @staticmethod
    def is_model_loaded() -> bool:
        """
        Check if the Whisper model is currently loaded
        
        Returns:
            True if model is loaded, False otherwise
        """
        return _whisper_model is not None
    
    @staticmethod
    def get_model_size() -> Optional[str]:
        """
        Get the size of the currently loaded model
        
        Returns:
            Model size string or None if no model is loaded
        """
        return _whisper_model_size 