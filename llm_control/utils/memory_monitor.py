"""
Memory monitoring module.

This module provides utilities for monitoring and managing memory usage.
"""

import os
import gc
import logging
import traceback
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger("memory-monitor")

def log_memory_usage(tag: str = "") -> Dict[str, float]:
    """
    Log current memory usage of the process.
    
    Args:
        tag: Optional tag for the log message (e.g., "before_processing")
        
    Returns:
        Dictionary containing memory usage information
    """
    try:
        # Import psutil here to avoid forcing it as a dependency
        import psutil
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        # Convert to GB for readability
        memory_usage = {
            "rss_gb": memory_info.rss / (1024 ** 3),
            "vms_gb": memory_info.vms / (1024 ** 3),
        }
        
        # Add CUDA information if available
        try:
            import torch
            if torch.cuda.is_available():
                memory_usage["cuda_allocated_gb"] = torch.cuda.memory_allocated() / (1024 ** 3)
                memory_usage["cuda_reserved_gb"] = torch.cuda.memory_reserved() / (1024 ** 3)
                memory_usage["cuda_max_gb"] = torch.cuda.max_memory_allocated() / (1024 ** 3)
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error getting CUDA memory info: {e}")
        
        # Log the memory usage
        tag_str = f" [{tag}]" if tag else ""
        logger.info(f"Memory usage{tag_str}: RSS={memory_usage['rss_gb']:.2f}GB, VMS={memory_usage['vms_gb']:.2f}GB")
        
        # Log CUDA info if available
        if "cuda_allocated_gb" in memory_usage:
            logger.info(f"CUDA memory{tag_str}: Allocated={memory_usage['cuda_allocated_gb']:.2f}GB, Reserved={memory_usage['cuda_reserved_gb']:.2f}GB, Max={memory_usage['cuda_max_gb']:.2f}GB")
        
        return memory_usage
        
    except ImportError:
        logger.warning("psutil not installed, cannot monitor memory usage")
        return {"error": "psutil not installed"}
    except Exception as e:
        logger.error(f"Error logging memory usage: {e}")
        return {"error": str(e)}

def force_memory_cleanup(threshold_gb: float = 10.0) -> Dict[str, Any]:
    """
    Force memory cleanup if usage exceeds threshold.
    
    Args:
        threshold_gb: Memory threshold in GB
        
    Returns:
        Dictionary with cleanup results
    """
    result = {
        "cleaned": False,
        "error": None,
        "freed_gb": 0.0
    }
    
    try:
        # Import psutil here to avoid forcing it as a dependency
        import psutil
        process = psutil.Process(os.getpid())
        
        # Check current memory usage
        before_cleanup = process.memory_info()
        before_rss_gb = before_cleanup.rss / (1024 ** 3)
        
        # Only clean if above threshold
        if before_rss_gb <= threshold_gb:
            logger.debug(f"Memory usage ({before_rss_gb:.2f}GB) below threshold ({threshold_gb:.2f}GB), no cleanup needed")
            result["cleaned"] = False
            result["before_rss_gb"] = before_rss_gb
            return result
        
        logger.warning(f"Memory usage ({before_rss_gb:.2f}GB) exceeds threshold ({threshold_gb:.2f}GB), forcing cleanup...")
        
        # Clean PyTorch CUDA memory
        try:
            import torch
            if torch.cuda.is_available():
                before_cuda = torch.cuda.memory_allocated() / (1024 ** 3)
                
                # First level cleanup - empty cache
                torch.cuda.empty_cache()
                
                # Second level cleanup - move tensors to CPU
                for obj in gc.get_objects():
                    try:
                        if torch.is_tensor(obj) and obj.is_cuda:
                            logger.debug(f"Moving CUDA tensor to CPU: {type(obj)}")
                            obj.data = obj.data.cpu()
                            del obj
                    except Exception as tensor_err:
                        logger.debug(f"Error moving tensor: {tensor_err}")
                
                # Run GC and empty cache again
                gc.collect()
                torch.cuda.empty_cache()
                
                # Try to reset CUDA stats
                try:
                    torch.cuda.reset_peak_memory_stats()
                    if hasattr(torch.cuda, 'reset_accumulated_memory_stats'):
                        torch.cuda.reset_accumulated_memory_stats()
                except Exception as reset_err:
                    logger.debug(f"Error resetting CUDA stats: {reset_err}")
                
                after_cuda = torch.cuda.memory_allocated() / (1024 ** 3)
                logger.info(f"CUDA memory: {before_cuda:.2f}GB -> {after_cuda:.2f}GB (freed {before_cuda - after_cuda:.2f}GB)")
                result["cuda_freed_gb"] = before_cuda - after_cuda
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Error cleaning CUDA memory: {e}")
        
        # Release Whisper model if it exists
        try:
            from llm_control.voice.model_manager import WhisperModelManager
            if WhisperModelManager.is_model_loaded():
                logger.info("Releasing Whisper model during memory cleanup")
                WhisperModelManager.release_model()
                result["whisper_model_released"] = True
        except ImportError:
            logger.debug("Whisper model manager not available")
        except Exception as e:
            logger.warning(f"Error releasing Whisper model: {e}")
            result["whisper_model_released"] = False
        
        # Release UI models if they exist
        try:
            from llm_control.ui_detection.element_finder import release_ui_models
            release_ui_models()
            logger.info("Released UI models")
            result["ui_models_released"] = True
        except ImportError:
            logger.debug("UI model release function not available")
        except Exception as e:
            logger.warning(f"Error releasing UI models: {e}")
            result["ui_models_released"] = False
        
        # Force garbage collection multiple times
        gc.collect()
        gc.collect()
        logger.info("Ran multiple garbage collection passes")
        
        # Check final memory usage
        after_cleanup = process.memory_info()
        after_rss_gb = after_cleanup.rss / (1024 ** 3)
        freed_gb = before_rss_gb - after_rss_gb
        
        logger.info(f"Memory after cleanup: {after_rss_gb:.2f}GB (freed {freed_gb:.2f}GB)")
        
        # If we didn't free much memory, try even more aggressive cleanup
        if freed_gb < 0.5 and before_rss_gb > threshold_gb:
            logger.warning("Initial cleanup ineffective, attempting extreme measures")
            
            # Try to restart/reload some internal services
            try:
                # Import and use GPU utility functions
                from llm_control.utils.gpu_utils import clear_gpu_memory
                clear_gpu_memory(force_free=True)
            except Exception as gpu_err:
                logger.warning(f"Error in force GPU cleanup: {gpu_err}")
            
            # Run another round of garbage collection
            gc.collect()
            gc.collect()
            
            # Check if we freed more memory
            extreme_cleanup = process.memory_info()
            extreme_rss_gb = extreme_cleanup.rss / (1024 ** 3)
            extra_freed_gb = after_rss_gb - extreme_rss_gb
            
            logger.info(f"Memory after extreme cleanup: {extreme_rss_gb:.2f}GB (additional {extra_freed_gb:.2f}GB freed)")
            after_rss_gb = extreme_rss_gb
            freed_gb += extra_freed_gb
        
        result["cleaned"] = True
        result["before_rss_gb"] = before_rss_gb
        result["after_rss_gb"] = after_rss_gb
        result["freed_gb"] = freed_gb
        
        return result
        
    except ImportError:
        error_msg = "psutil not installed, cannot monitor memory usage"
        logger.warning(error_msg)
        result["error"] = error_msg
        return result
    except Exception as e:
        error_msg = f"Error during memory cleanup: {e}"
        logger.error(error_msg)
        logger.error(traceback.format_exc())
        result["error"] = error_msg
        return result

def check_memory_threshold(threshold_gb: float = 10.0, force_cleanup: bool = True) -> Dict[str, Any]:
    """
    Check if memory usage exceeds threshold and optionally trigger cleanup.
    
    Args:
        threshold_gb: Memory threshold in GB
        force_cleanup: If True, force cleanup when threshold is exceeded
    
    Returns:
        Dictionary with check results and cleanup info if performed
    """
    result = {
        "exceeded": False,
        "cleanup_performed": False
    }
    
    try:
        # Import psutil here to avoid forcing it as a dependency
        import psutil
        process = psutil.Process(os.getpid())
        
        # Check current memory usage
        memory_info = process.memory_info()
        memory_usage_gb = memory_info.rss / (1024 ** 3)
        result["memory_usage_gb"] = memory_usage_gb
        
        # Check if threshold is exceeded
        if memory_usage_gb > threshold_gb:
            logger.warning(f"Memory usage ({memory_usage_gb:.2f}GB) exceeds threshold ({threshold_gb:.2f}GB)")
            result["exceeded"] = True
            
            # Force cleanup if requested
            if force_cleanup:
                cleanup_result = force_memory_cleanup(threshold_gb)
                result["cleanup_performed"] = True
                result["cleanup_result"] = cleanup_result
        else:
            logger.debug(f"Memory usage ({memory_usage_gb:.2f}GB) below threshold ({threshold_gb:.2f}GB)")
        
        return result
    
    except ImportError:
        error_msg = "psutil not installed, cannot monitor memory usage"
        logger.warning(error_msg)
        result["error"] = error_msg
        return result
    except Exception as e:
        error_msg = f"Error checking memory threshold: {e}"
        logger.error(error_msg)
        result["error"] = error_msg
        return result 