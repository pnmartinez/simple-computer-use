#!/usr/bin/env python3
"""
Test script for the visual stability waiting functionality.
This allows testing the wait mechanism without running the full application.
"""

import os
import sys
import time
import argparse

# Add the parent directory to the path to allow importing the package
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import required modules
from llm_control.utils.wait import wait_for_visual_stability, test_visual_stability
from llm_control.utils.dependencies import check_and_install_dependencies

def main():
    """Main entry point for the test script"""
    parser = argparse.ArgumentParser(description="Test the visual stability waiting functionality")
    parser.add_argument("--demo", action="store_true", help="Run demo mode with multiple screenshots")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout for stability detection in seconds")
    parser.add_argument("--threshold", type=float, default=0.98, help="Similarity threshold (0.0-1.0)")
    parser.add_argument("--interval", type=float, default=0.3, help="Check interval in seconds")
    parser.add_argument("--stable-count", type=int, default=3, help="Required consecutive stable checks")
    
    args = parser.parse_args()
    
    # Ensure dependencies are installed
    check_and_install_dependencies()
    
    # Run test based on mode
    if args.demo:
        # Run the demo that shows screenshot comparison
        test_visual_stability()
    else:
        # Run actual visual stability wait
        print(f"Starting visual stability detection:")
        print(f"- Timeout: {args.timeout}s")
        print(f"- Threshold: {args.threshold}")
        print(f"- Check interval: {args.interval}s")
        print(f"- Required stable checks: {args.stable_count}")
        print("\nChange your screen now to see how stability is detected.")
        print("If you keep your screen stable, detection should complete quickly.")
        print("Press Ctrl+C to stop the test.\n")
        
        try:
            start_time = time.time()
            result = wait_for_visual_stability(
                timeout=args.timeout,
                stability_threshold=args.threshold,
                check_interval=args.interval,
                consecutive_stable=args.stable_count
            )
            elapsed = time.time() - start_time
            
            if result:
                print(f"\n✅ Screen stability detected after {elapsed:.2f}s")
            else:
                print(f"\n⚠ Timed out after {args.timeout}s without detecting stability")
                
        except KeyboardInterrupt:
            print("\nTest interrupted by user.")
        except Exception as e:
            print(f"\nError during test: {str(e)}")
    
    print("\nTest complete!")

if __name__ == "__main__":
    main() 