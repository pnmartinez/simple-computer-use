#!/usr/bin/env python3
"""
Utility script to check GPU memory usage and clear memory if needed.
This is useful for recovering from CUDA Out of Memory errors.
"""

import os
import sys
import argparse
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Get the logger
logger = logging.getLogger("gpu-memory-util")

def check_torch_available():
    """Check if PyTorch is available with CUDA support"""
    try:
        import torch
        logger.info(f"PyTorch version: {torch.__version__}")
        
        if torch.cuda.is_available():
            device_count = torch.cuda.device_count()
            logger.info(f"CUDA is available with {device_count} device(s)")
            
            # Print device information
            for i in range(device_count):
                device_name = torch.cuda.get_device_name(i)
                logger.info(f"Device {i}: {device_name}")
            
            return True
        else:
            logger.warning("CUDA is not available")
            return False
    except ImportError:
        logger.error("PyTorch is not installed")
        print("\nTo install PyTorch, run:")
        print("pip install torch")
        return False

def check_gpu_memory():
    """Check GPU memory usage"""
    try:
        import torch
        
        if not torch.cuda.is_available():
            logger.warning("CUDA is not available")
            return False
        
        # Print memory usage for each device
        device_count = torch.cuda.device_count()
        for i in range(device_count):
            # Get memory information
            total_memory = torch.cuda.get_device_properties(i).total_memory
            allocated_memory = torch.cuda.memory_allocated(i)
            reserved_memory = torch.cuda.memory_reserved(i)
            free_memory = total_memory - allocated_memory
            
            # Convert to GB for readability
            total_memory_gb = total_memory / (1024**3)
            allocated_memory_gb = allocated_memory / (1024**3)
            reserved_memory_gb = reserved_memory / (1024**3)
            free_memory_gb = free_memory / (1024**3)
            
            device_name = torch.cuda.get_device_name(i)
            print(f"\nDevice {i}: {device_name}")
            print(f"  Total memory:    {total_memory_gb:.2f} GB")
            print(f"  Allocated memory: {allocated_memory_gb:.2f} GB")
            print(f"  Reserved memory:  {reserved_memory_gb:.2f} GB")
            print(f"  Free memory:     {free_memory_gb:.2f} GB")
            print(f"  Free percentage: {(free_memory / total_memory) * 100:.2f}%")
        
        return True
    except Exception as e:
        logger.error(f"Error checking GPU memory: {str(e)}")
        return False

def clear_gpu_memory():
    """Clear GPU memory by emptying the cache"""
    try:
        import torch
        import gc
        
        if not torch.cuda.is_available():
            logger.warning("CUDA is not available")
            return False
        
        # Print memory usage before clearing
        logger.info("Memory usage before clearing:")
        check_gpu_memory()
        
        # Empty the cache
        logger.info("\nClearing GPU memory...")
        torch.cuda.empty_cache()
        
        # Run garbage collection
        gc.collect()
        
        # Print memory usage after clearing
        logger.info("\nMemory usage after clearing:")
        check_gpu_memory()
        
        return True
    except Exception as e:
        logger.error(f"Error clearing GPU memory: {str(e)}")
        return False

def attempt_force_clear():
    """Attempt a forced memory clear by invoking a separate process"""
    try:
        import subprocess
        
        logger.info("\nAttempting forced memory clear...")
        
        # Create a script to clear memory in a new process
        script = """
import torch
import gc
if torch.cuda.is_available():
    torch.cuda.empty_cache()
    gc.collect()
    print("Memory cleared")
else:
    print("CUDA not available")
"""
        # Execute the script in a new process
        subprocess.run([sys.executable, "-c", script], check=True)
        
        # Check memory again
        logger.info("\nMemory after forced clear:")
        check_gpu_memory()
        
        return True
    except Exception as e:
        logger.error(f"Error performing forced memory clear: {str(e)}")
        return False

def list_gpu_processes():
    """List processes using the GPU"""
    try:
        import subprocess
        
        logger.info("\nProcesses using GPU:")
        
        try:
            # Try using nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv"],
                capture_output=True,
                text=True,
                check=True
            )
            print(result.stdout)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("nvidia-smi command failed or is not available")
            
            # Try a more basic approach on Linux
            if sys.platform.startswith('linux'):
                try:
                    logger.info("Using lsof to find processes accessing NVIDIA devices:")
                    subprocess.run(
                        ["lsof", "/dev/nvidia*"],
                        check=False
                    )
                except FileNotFoundError:
                    logger.warning("lsof command is not available")
            
        return True
    except Exception as e:
        logger.error(f"Error listing GPU processes: {str(e)}")
        return False

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Utility to check GPU memory usage and clear memory if needed"
    )
    
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check GPU memory usage"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear GPU memory"
    )
    
    parser.add_argument(
        "--force-clear",
        action="store_true",
        help="Attempt a more aggressive memory clear"
    )
    
    parser.add_argument(
        "--list-processes",
        action="store_true",
        help="List processes using the GPU"
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks and clearing operations"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    # Check if PyTorch is available
    if not check_torch_available():
        return
    
    # If no specific arguments provided, or --all is specified, run everything
    run_all = args.all or not (args.check or args.clear or args.force_clear or args.list_processes)
    
    # Check GPU memory
    if args.check or run_all:
        check_gpu_memory()
    
    # List processes using GPU
    if args.list_processes or run_all:
        list_gpu_processes()
    
    # Clear GPU memory
    if args.clear or run_all:
        clear_gpu_memory()
    
    # Force clear GPU memory
    if args.force_clear or run_all:
        attempt_force_clear()

if __name__ == "__main__":
    main() 