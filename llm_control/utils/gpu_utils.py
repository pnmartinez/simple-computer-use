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

def clear_gpu_memory(force_free=False) -> bool:
    """
    Attempt to clear GPU memory
    
    Args:
        force_free: If True, use more aggressive memory clearing techniques
    
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
        
        if force_free:
            # Get memory after first clearing attempt
            after_first = check_gpu_info()
            
            # Try more aggressive approach regardless of how much was freed
            logger.info("Using aggressive memory clearing techniques")
            
            # Move any existing tensors to CPU and delete them
            for obj in gc.get_objects():
                try:
                    if torch.is_tensor(obj) and obj.is_cuda:
                        logger.debug(f"Moving CUDA tensor to CPU: {type(obj)} of size {obj.size()}")
                        obj.data = obj.data.cpu()
                        del obj
                except Exception as tensor_err:
                    logger.debug(f"Error moving tensor: {tensor_err}")
                    pass
            
            # Run GC again
            gc.collect()
            torch.cuda.empty_cache()
            
            # Try to reset CUDA device if possible
            try:
                torch.cuda.reset_peak_memory_stats()
                if hasattr(torch.cuda, 'reset_accumulated_memory_stats'):
                    torch.cuda.reset_accumulated_memory_stats()
                logger.info("Reset CUDA memory stats")
            except Exception as reset_err:
                logger.debug(f"Error resetting CUDA stats: {reset_err}")
                pass
            
            # Sometimes we need to explicitly free all modules
            try:
                # Clean up global variables that might hold tensors
                for name in list(globals().keys()):
                    if isinstance(globals()[name], torch.nn.Module):
                        logger.debug(f"Clearing global PyTorch module: {name}")
                        del globals()[name]
            except Exception as global_err:
                logger.debug(f"Error clearing global modules: {global_err}")
                pass
            
            # Run additional garbage collection
            gc.collect()
            torch.cuda.empty_cache()
        
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

def check_gpu_processes() -> Dict[str, Any]:
    """
    Check which processes are using GPU memory
    
    Returns:
        Dictionary with information about GPU processes
    """
    result = {
        "success": False,
        "processes": [],
        "error": None
    }
    
    try:
        # Try using nvidia-smi via subprocess
        import subprocess
        
        try:
            # Get list of processes using GPU
            cmd = ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"]
            output = subprocess.check_output(cmd, universal_newlines=True)
            
            # Parse the output
            processes = []
            for line in output.strip().split('\n'):
                if line.strip():
                    parts = line.split(', ')
                    if len(parts) >= 3:
                        pid = int(parts[0])
                        name = parts[1]
                        memory = parts[2]
                        
                        # Get additional process info if possible
                        try:
                            import psutil
                            process = psutil.Process(pid)
                            processes.append({
                                "pid": pid,
                                "name": name,
                                "memory_used": memory,
                                "command": " ".join(process.cmdline()[:3]) + "..." if len(process.cmdline()) > 3 else " ".join(process.cmdline()),
                                "username": process.username(),
                                "create_time": process.create_time()
                            })
                        except:
                            processes.append({
                                "pid": pid,
                                "name": name,
                                "memory_used": memory
                            })
            
            # Check for competing processes (not our own)
            import os
            current_pid = os.getpid()
            competing_processes = [p for p in processes if p["pid"] != current_pid]
            
            # Create result
            result["success"] = True
            result["processes"] = processes
            result["competing_processes"] = competing_processes
            result["has_competing_processes"] = len(competing_processes) > 0
            
            # Log information
            logger.info(f"Found {len(processes)} processes using GPU")
            if competing_processes:
                logger.warning(f"Found {len(competing_processes)} competing processes using GPU memory")
                for proc in competing_processes:
                    logger.warning(f"  GPU process: {proc['name']} (PID {proc['pid']}) using {proc['memory_used']}")
            
            return result
        except subprocess.CalledProcessError:
            logger.warning("nvidia-smi command failed")
            result["error"] = "nvidia-smi command failed"
        except FileNotFoundError:
            logger.warning("nvidia-smi not found")
            result["error"] = "nvidia-smi not found"
            
    except Exception as e:
        logger.error(f"Error checking GPU processes: {str(e)}")
        result["error"] = str(e)
    
    return result 