#!/usr/bin/env python3
"""
Utility script to check GPU processes and optionally kill competing processes.
Use with caution as it will terminate other processes using the GPU.
"""

import os
import sys
import argparse
import logging
import time
import signal
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("gpu-process-manager")

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

def kill_process(pid: int, force: bool = False) -> bool:
    """
    Kill a process by PID
    
    Args:
        pid: Process ID to kill
        force: Whether to use SIGKILL (force kill)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        import psutil
        
        # Check if process exists
        if not psutil.pid_exists(pid):
            logger.warning(f"Process {pid} does not exist")
            return False
        
        # Get process info
        process = psutil.Process(pid)
        logger.info(f"Killing process {pid} ({process.name()}) with {'SIGKILL' if force else 'SIGTERM'}")
        
        # Kill the process
        if force:
            process.kill()  # SIGKILL
        else:
            process.terminate()  # SIGTERM
            
        # Wait for process to exit
        try:
            process.wait(timeout=5)
            logger.info(f"Process {pid} killed successfully")
            return True
        except psutil.TimeoutExpired:
            if not force:
                logger.warning(f"Process {pid} did not exit after SIGTERM, sending SIGKILL")
                process.kill()
                process.wait(timeout=5)
                logger.info(f"Process {pid} killed successfully with SIGKILL")
            else:
                logger.error(f"Process {pid} did not exit even after SIGKILL")
                return False
            
        return True
        
    except Exception as e:
        logger.error(f"Error killing process {pid}: {str(e)}")
        return False

def kill_competing_processes(force: bool = False, exclude_pids: List[int] = None) -> Dict[str, Any]:
    """
    Kill all competing processes using GPU
    
    Args:
        force: Whether to use SIGKILL (force kill)
        exclude_pids: List of PIDs to exclude from killing
        
    Returns:
        Dictionary with information about killed processes
    """
    result = {
        "success": False,
        "killed_processes": [],
        "failed_processes": [],
        "error": None
    }
    
    exclude_pids = exclude_pids or []
    
    try:
        # Check GPU processes
        gpu_processes = check_gpu_processes()
        
        if not gpu_processes["success"]:
            result["error"] = gpu_processes["error"]
            return result
        
        competing_processes = gpu_processes["competing_processes"]
        
        if not competing_processes:
            logger.info("No competing processes to kill")
            result["success"] = True
            return result
        
        # Kill each competing process
        killed_processes = []
        failed_processes = []
        
        for process in competing_processes:
            pid = process["pid"]
            
            # Skip excluded PIDs
            if pid in exclude_pids:
                logger.info(f"Skipping excluded process {pid} ({process['name']})")
                continue
            
            # Try to kill the process
            if kill_process(pid, force):
                killed_processes.append(process)
            else:
                failed_processes.append(process)
        
        # Update result
        result["success"] = True
        result["killed_processes"] = killed_processes
        result["failed_processes"] = failed_processes
        
        # Log summary
        logger.info(f"Killed {len(killed_processes)} competing processes, {len(failed_processes)} failed")
        
        return result
        
    except Exception as e:
        logger.error(f"Error killing competing processes: {str(e)}")
        result["error"] = str(e)
        return result

def check_gpu_memory() -> Dict[str, Any]:
    """
    Check GPU memory usage
    
    Returns:
        Dictionary with GPU memory information
    """
    result = {
        "success": False,
        "error": None
    }
    
    try:
        # Try to import torch
        import torch
        
        if not torch.cuda.is_available():
            result["error"] = "CUDA not available"
            return result
        
        # Get memory information
        device = torch.cuda.current_device()
        total_memory = torch.cuda.get_device_properties(device).total_memory
        allocated_memory = torch.cuda.memory_allocated(device)
        reserved_memory = torch.cuda.memory_reserved(device)
        free_memory = total_memory - allocated_memory
        
        # Convert to GB for readability
        total_memory_gb = total_memory / (1024**3)
        allocated_memory_gb = allocated_memory / (1024**3)
        reserved_memory_gb = reserved_memory / (1024**3)
        free_memory_gb = free_memory / (1024**3)
        
        # Create result
        result["success"] = True
        result["total_memory_gb"] = total_memory_gb
        result["allocated_memory_gb"] = allocated_memory_gb
        result["reserved_memory_gb"] = reserved_memory_gb
        result["free_memory_gb"] = free_memory_gb
        result["free_percent"] = (free_memory / total_memory) * 100
        
        # Log information
        logger.info(f"GPU memory: {allocated_memory_gb:.2f}GB used / {total_memory_gb:.2f}GB total ({result['free_percent']:.2f}% free)")
        
        return result
        
    except ImportError:
        result["error"] = "PyTorch not installed"
        return result
    except Exception as e:
        logger.error(f"Error checking GPU memory: {str(e)}")
        result["error"] = str(e)
        return result

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Utility to manage GPU processes")
    
    parser.add_argument("--check", action="store_true", help="Check GPU processes")
    parser.add_argument("--kill", action="store_true", help="Kill competing GPU processes")
    parser.add_argument("--force", action="store_true", help="Force kill processes (SIGKILL)")
    parser.add_argument("--exclude", type=int, nargs="+", help="Process IDs to exclude from killing")
    parser.add_argument("--memory", action="store_true", help="Check GPU memory")
    
    args = parser.parse_args()
    
    # Default to check if no arguments provided
    if not any([args.check, args.kill, args.memory]):
        args.check = True
    
    # Check GPU processes
    if args.check:
        check_gpu_processes()
    
    # Check GPU memory
    if args.memory:
        check_gpu_memory()
    
    # Kill competing processes
    if args.kill:
        exclude_pids = args.exclude or []
        
        logger.warning("About to kill competing GPU processes")
        if exclude_pids:
            logger.info(f"Excluding PIDs: {exclude_pids}")
        
        if args.force:
            logger.warning("Using force kill (SIGKILL)")
        
        # Ask for confirmation
        if sys.stdout.isatty():  # Only ask if running in terminal
            confirmation = input("Are you sure? (y/n): ")
            if confirmation.lower() != 'y':
                logger.info("Aborted by user")
                return
        
        # Kill processes
        result = kill_competing_processes(args.force, exclude_pids)
        
        # Check GPU memory after killing
        if result["success"] and result["killed_processes"]:
            time.sleep(1)  # Wait for resources to be freed
            check_gpu_memory()

if __name__ == "__main__":
    main() 