#!/usr/bin/env python3
"""
Memory monitoring script.

This script monitors memory usage over time and detects potential memory leaks.
"""

import os
import time
import argparse
import csv
from datetime import datetime

try:
    import psutil
except ImportError:
    print("Error: psutil is required. Install with: pip install psutil")
    exit(1)

try:
    import torch
except ImportError:
    torch = None
    print("Warning: PyTorch not found, CUDA memory monitoring disabled")

def get_process_by_name(name):
    """Find process by name"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        # Check if process name contains the given name string
        if name.lower() in proc.info['name'].lower():
            return proc
        # Check in command line arguments
        elif proc.info['cmdline']:
            cmdline = ' '.join(proc.info['cmdline']).lower()
            if name.lower() in cmdline:
                return proc
    return None

def get_memory_usage(process=None):
    """Get memory usage information"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'system_total_gb': psutil.virtual_memory().total / (1024**3),
        'system_used_gb': psutil.virtual_memory().used / (1024**3),
        'system_free_gb': psutil.virtual_memory().available / (1024**3),
        'system_percent': psutil.virtual_memory().percent
    }
    
    # Add process-specific info if provided
    if process:
        try:
            # Update process info
            process.cpu_percent()
            mem_info = process.memory_info()
            
            data.update({
                'process_rss_gb': mem_info.rss / (1024**3),
                'process_vms_gb': mem_info.vms / (1024**3),
                'process_cpu_percent': process.cpu_percent(),
                'process_memory_percent': process.memory_percent()
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print("Process no longer exists or cannot be accessed")
            return None
    
    # Add CUDA memory info if available
    if torch and hasattr(torch, 'cuda') and torch.cuda.is_available():
        data.update({
            'cuda_allocated_gb': torch.cuda.memory_allocated() / (1024**3),
            'cuda_reserved_gb': torch.cuda.memory_reserved() / (1024**3),
            'cuda_max_gb': torch.cuda.max_memory_allocated() / (1024**3)
        })
    
    return data

def print_memory_info(data, previous_data=None):
    """Print memory usage information"""
    print(f"\n=== Memory Usage at {data['timestamp']} ===")
    print(f"System: {data['system_used_gb']:.2f}GB used / {data['system_total_gb']:.2f}GB total ({data['system_percent']}%)")
    
    if 'process_rss_gb' in data:
        print(f"Process: {data['process_rss_gb']:.2f}GB RSS, {data['process_vms_gb']:.2f}GB VMS")
        print(f"CPU: {data['process_cpu_percent']:.1f}%, Memory: {data['process_memory_percent']:.1f}%")
        
        # Calculate memory change if previous data exists
        if previous_data and 'process_rss_gb' in previous_data:
            memory_change = data['process_rss_gb'] - previous_data['process_rss_gb']
            if abs(memory_change) > 0.05:  # Only show significant changes
                direction = "+" if memory_change > 0 else ""
                print(f"Memory Change: {direction}{memory_change:.2f}GB since last check")
    
    if 'cuda_allocated_gb' in data:
        print(f"CUDA: {data['cuda_allocated_gb']:.2f}GB allocated, {data['cuda_reserved_gb']:.2f}GB reserved")
        
        # Calculate CUDA change if previous data exists
        if previous_data and 'cuda_allocated_gb' in previous_data:
            cuda_change = data['cuda_allocated_gb'] - previous_data['cuda_allocated_gb']
            if abs(cuda_change) > 0.05:  # Only show significant changes
                direction = "+" if cuda_change > 0 else ""
                print(f"CUDA Change: {direction}{cuda_change:.2f}GB since last check")

def write_to_csv(data, filename):
    """Write memory data to CSV file"""
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=data.keys())
        
        if not file_exists:
            writer.writeheader()
        
        writer.writerow(data)

def monitor_memory(process_name=None, interval=5, output=None, duration=None):
    """Monitor memory usage over time"""
    process = None
    count = 0
    start_time = time.time()
    previous_data = None
    
    # Find process if name provided
    if process_name:
        process = get_process_by_name(process_name)
        if not process:
            print(f"Process '{process_name}' not found. Monitoring system memory only.")
    
    try:
        while True:
            # Check if duration limit reached
            if duration and (time.time() - start_time) > duration:
                print(f"Duration limit of {duration} seconds reached.")
                break
                
            # Get memory data
            data = get_memory_usage(process)
            
            if data:
                # Print to console
                print_memory_info(data, previous_data)
                
                # Write to CSV if output file specified
                if output:
                    write_to_csv(data, output)
                
                previous_data = data
            else:
                print("Failed to get memory data, process may have terminated.")
                break
            
            count += 1
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    
    print(f"Collected {count} memory snapshots over {time.time() - start_time:.1f} seconds.")
    if output:
        print(f"Data saved to {output}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor memory usage and detect potential memory leaks")
    parser.add_argument("-p", "--process", help="Process name to monitor (optional)")
    parser.add_argument("-i", "--interval", type=float, default=5, help="Monitoring interval in seconds (default: 5)")
    parser.add_argument("-o", "--output", help="Output CSV file (optional)")
    parser.add_argument("-d", "--duration", type=int, help="Duration to monitor in seconds (optional)")
    args = parser.parse_args()
    
    monitor_memory(
        process_name=args.process,
        interval=args.interval,
        output=args.output,
        duration=args.duration
    ) 