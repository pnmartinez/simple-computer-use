#!/usr/bin/env python3
"""
Test script for visual command execution with YOLOv8 target detection.

This script demonstrates how the system can identify UI elements on screen
and execute commands like "click on Firefox" by finding the element visually.
"""

import os
import sys
import logging
import argparse
import time
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Get the logger
logger = logging.getLogger("visual-command-test")

try:
    from llm_control.llm.simple_executor import execute_command_with_llm, find_visual_target
    print("Successfully imported from llm_control package!")
except ImportError:
    print("Could not import from llm_control package. Make sure it's installed.")
    sys.exit(1)

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import pyautogui
        print("✅ PyAutoGUI is installed")
    except ImportError:
        print("❌ PyAutoGUI is not installed. Install with: pip install pyautogui")
        return False
    
    try:
        import requests
        print("✅ Requests is installed")
    except ImportError:
        print("❌ Requests is not installed. Install with: pip install requests")
        return False
    
    try:
        import torch
        print(f"✅ PyTorch is installed (version {torch.__version__})")
        
        if torch.cuda.is_available():
            device = torch.cuda.get_device_name(0)
            print(f"   CUDA is available (device: {device})")
        else:
            print("   CUDA is not available, using CPU")
    except ImportError:
        print("ℹ️ PyTorch is not installed. YOLOv8 detection may not work.")
    
    try:
        from ultralytics import YOLO
        print("✅ YOLOv8 (ultralytics) is installed")
    except ImportError:
        print("ℹ️ YOLOv8 is not installed. Visual detection may not work.")
    
    try:
        from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo
        print("✅ UI element detection module is available")
        
        return True
    except ImportError:
        print("ℹ️ UI element detection module not found. Visual detection may not work.")
        
        # Script can still run with basic functionality
        return True

def test_find_visual_target(target_text):
    """Test the find_visual_target function with a specified target"""
    print(f"\n📦 Testing visual target detection for: '{target_text}'")
    print("-" * 60)
    
    # Give user time to prepare screen
    for i in range(3, 0, -1):
        print(f"Finding target in {i}...")
        time.sleep(1)
    
    # Attempt to find the target
    result = find_visual_target(target_text)
    
    if result.get("success", False):
        if result.get("found", False):
            print(f"✅ Target found: '{target_text}'")
            print(f"   Coordinates: {result.get('coordinates')}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
            print(f"   Element type: {result.get('element_type', 'unknown')}")
            if result.get("text"):
                print(f"   Text: {result.get('text')}")
        else:
            print(f"⚠️ Target not found: '{target_text}'")
            print(f"   Error: {result.get('error')}")
    else:
        print(f"❌ Detection failed: {result.get('error')}")
    
    print("-" * 60)
    return result

def test_visual_command(command, model="llama3.1", dry_run=False, save_screenshot=True):
    """Test executing a command with visual targeting"""
    print(f"\n🎯 Testing visual command: '{command}'")
    print("-" * 60)
    
    # Give user time to prepare screen
    for i in range(3, 0, -1):
        print(f"Executing in {i}...")
        time.sleep(1)
    
    # Execute the command
    result = execute_command_with_llm(
        command=command,
        model=model,
        dry_run=dry_run,
        capture_screenshot=True
    )
    
    if result.get("success", False):
        print(f"✅ Command executed successfully: '{command}'")
        
        if dry_run:
            print("\nGenerated Code:")
            print("=" * 40)
            print(result.get("code", ""))
            print("=" * 40)
        
        # Handle screenshot if present
        screenshot_data = result.get("screenshot")
        if screenshot_data and save_screenshot:
            try:
                import base64
                from datetime import datetime
                
                # Create a timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"command_result_{timestamp}.png"
                
                # Decode and save screenshot
                with open(filename, "wb") as f:
                    f.write(base64.b64decode(screenshot_data))
                
                print(f"📸 Screenshot saved to: {filename}")
            except Exception as e:
                print(f"❌ Failed to save screenshot: {str(e)}")
    else:
        print(f"❌ Command execution failed: {result.get('error')}")
    
    print("-" * 60)
    return result

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Test visual command execution with YOLOv8"
    )
    
    parser.add_argument(
        "--target",
        type=str,
        help="Test finding a specific visual target (e.g., 'Firefox')"
    )
    
    parser.add_argument(
        "--command",
        type=str,
        help="Execute a command with visual targeting (e.g., 'click on Firefox')"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="llama3.1",
        help="Ollama model to use (default: llama3.1)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate code but don't execute it"
    )
    
    parser.add_argument(
        "--check-deps",
        action="store_true",
        help="Check dependencies and exit"
    )
    
    parser.add_argument(
        "--no-screenshot",
        action="store_true",
        help="Disable saving of result screenshots"
    )
    
    parser.add_argument(
        "--screenshot-dir",
        type=str,
        default=".",
        help="Directory to save screenshots (default: current directory)"
    )
    
    return parser.parse_args()

def main():
    """Main entry point"""
    args = parse_args()
    
    print("Visual Command Testing Tool")
    print("=" * 60)
    
    # Check dependencies
    if args.check_deps or args.target or args.command:
        if not check_dependencies():
            print("\n❌ Critical dependencies missing. Please install them and try again.")
            sys.exit(1)
    
    # Just checking dependencies
    if args.check_deps:
        print("\n✅ All critical dependencies are installed.")
        sys.exit(0)
    
    # Test finding a specific target
    if args.target:
        test_find_visual_target(args.target)
    
    # Test executing a command
    if args.command:
        # Create screenshot directory if it doesn't exist
        if not args.no_screenshot and args.screenshot_dir != "." and not os.path.exists(args.screenshot_dir):
            os.makedirs(args.screenshot_dir)
            print(f"Created directory for screenshots: {args.screenshot_dir}")
        
        # Change working directory temporarily if saving screenshots to another directory
        original_dir = os.getcwd()
        if not args.no_screenshot and args.screenshot_dir != ".":
            os.chdir(args.screenshot_dir)
        
        try:
            test_visual_command(
                command=args.command, 
                model=args.model, 
                dry_run=args.dry_run,
                save_screenshot=not args.no_screenshot
            )
        finally:
            # Restore original directory
            if not args.no_screenshot and args.screenshot_dir != ".":
                os.chdir(original_dir)
    
    # If no specific action requested, show examples
    if not (args.target or args.command or args.check_deps):
        print("\nExamples:")
        print("  Find a target: python test_visual_command.py --target 'Firefox'")
        print("  Execute a command: python test_visual_command.py --command 'click on Firefox'")
        print("  Dry run: python test_visual_command.py --command 'click on Firefox' --dry-run")
        print("  Without screenshots: python test_visual_command.py --command 'click on Firefox' --no-screenshot")
        print("  Save screenshots elsewhere: python test_visual_command.py --command 'click on Firefox' --screenshot-dir './screenshots'")
        print("  Check dependencies: python test_visual_command.py --check-deps")

if __name__ == "__main__":
    main() 