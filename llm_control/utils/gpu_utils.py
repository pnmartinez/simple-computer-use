import os
import logging
import subprocess
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("llm-pc-control")

def check_gpu_info() -> Dict[str, Any]:
    """
    Check GPU information and memory usage
    
    Returns:
        Dictionary with GPU information
    """
    try:
        import torch
        
        if not torch.cuda.is_available():
            return {
                "available": False,
                "message": "CUDA not available",
                "device_count": 0
            }
        
        # Get basic information
        device_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)
        
        # Get memory information
        total_memory = torch.cuda.get_device_properties(current_device).total_memory
        allocated_memory = torch.cuda.memory_allocated(current_device)
        reserved_memory = torch.cuda.memory_reserved(current_device)
        free_memory = total_memory - allocated_memory
        
        # Convert to GB for readability
        total_memory_gb = total_memory / (1024**3)
        allocated_memory_gb = allocated_memory / (1024**3)
        reserved_memory_gb = reserved_memory / (1024**3)
        free_memory_gb = free_memory / (1024**3)
        
        return {
            "available": True,
            "device_count": device_count,
            "current_device": current_device,
            "device_name": device_name,
            "total_memory_gb": total_memory_gb,
            "allocated_memory_gb": allocated_memory_gb,
            "reserved_memory_gb": reserved_memory_gb,
            "free_memory_gb": free_memory_gb,
            "free_percent": (free_memory / total_memory) * 100
        }
    except ImportError:
        return {
            "available": False,
            "message": "PyTorch not installed",
            "device_count": 0
        }
    except Exception as e:
        return {
            "available": False,
            "message": f"Error checking GPU: {str(e)}",
            "device_count": 0
        }

def clear_gpu_memory() -> bool:
    """
    Attempt to clear GPU memory
    
    Returns:
        True if successful, False otherwise
    """
    try:
        import torch
        
        if not torch.cuda.is_available():
            logger.warning("CUDA not available, nothing to clear")
            return False
        
        # Get initial memory info
        before = check_gpu_info()
        logger.info(f"Before clearing: {before['allocated_memory_gb']:.2f}GB allocated, {before['free_memory_gb']:.2f}GB free")
        
        # Empty the cache
        torch.cuda.empty_cache()
        
        # Run garbage collection
        import gc
        gc.collect()
        
        # Get new memory info
        after = check_gpu_info()
        logger.info(f"After clearing: {after['allocated_memory_gb']:.2f}GB allocated, {after['free_memory_gb']:.2f}GB free")
        logger.info(f"Freed {after['free_memory_gb'] - before['free_memory_gb']:.2f}GB of GPU memory")
        
        return True
    except Exception as e:
        logger.error(f"Error clearing GPU memory: {str(e)}")
        return False

def optimize_gpu_memory() -> None:
    """Configure PyTorch for optimal memory usage"""
    try:
        # Set environment variables for better memory management
        os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
        
        # Try to import torch and configure settings
        import torch
        
        if torch.cuda.is_available():
            # Enable memory efficient attention if using transformers
            try:
                import transformers
                transformers.utils.logging.set_verbosity_error()
                torch.backends.cuda.matmul.allow_tf32 = True
                logger.info("Configured transformers for memory efficiency")
            except ImportError:
                pass
                
            logger.info("GPU memory optimization configured")
        else:
            logger.info("CUDA not available, no GPU optimization needed")
    except ImportError:
        logger.warning("PyTorch not installed, skipping GPU memory optimization")
    except Exception as e:
        logger.error(f"Error configuring GPU memory optimization: {str(e)}")

def choose_device_for_model(model_name: str, min_memory_gb: float = 2.0) -> str:
    """
    Choose appropriate device (cuda/cpu) based on available memory
    
    Args:
        model_name: Name of the model (for logging)
        min_memory_gb: Minimum required free memory in GB
        
    Returns:
        "cuda" if GPU has enough memory, "cpu" otherwise
    """
    try:
        import torch
        
        if not torch.cuda.is_available():
            logger.info(f"CUDA not available, using CPU for {model_name}")
            return "cpu"
        
        # Check GPU memory
        gpu_info = check_gpu_info()
        free_memory_gb = gpu_info.get("free_memory_gb", 0)
        
        if free_memory_gb >= min_memory_gb:
            logger.info(f"Using GPU for {model_name} (free memory: {free_memory_gb:.2f}GB)")
            return "cuda"
        else:
            logger.warning(f"Insufficient GPU memory for {model_name} (needs {min_memory_gb}GB, free: {free_memory_gb:.2f}GB)")
            logger.info(f"Falling back to CPU for {model_name}")
            return "cpu"
    except Exception as e:
        logger.error(f"Error choosing device: {str(e)}")
        return "cpu"  # Default to CPU on error 