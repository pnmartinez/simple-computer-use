"""
Wait utilities for LLM Control.

This module provides functions for smart waiting between actions,
such as waiting for the screen to stabilize after a click.
"""

import time
import logging
from typing import Dict, Any, Optional

# Import from our dedicated screenshot module to avoid circular imports
from llm_control.screenshot import take_screenshot

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def wait_for_visual_stability(max_wait: float = 5.0, 
                              check_interval: float = 0.5, 
                              similarity_threshold: float = 0.95) -> bool:
    """
    Wait for the screen to visually stabilize (stop changing).
    
    Args:
        max_wait: Maximum time to wait in seconds
        check_interval: How often to check for stability
        similarity_threshold: Threshold for considering images similar (0-1)
        
    Returns:
        True if the screen stabilized, False if timed out
    """
    logger.info(f"Waiting for visual stability (max: {max_wait}s, threshold: {similarity_threshold})")
    
    try:
        import numpy as np
        from PIL import Image
        import imagehash
        
        start_time = time.time()
        last_screenshot = None
        last_hash = None
        elapsed = 0
        
        while elapsed < max_wait:
            # Take a screenshot
            screenshot_info = take_screenshot()
            if not screenshot_info.get("success", False):
                logger.error("Failed to take screenshot for visual stability check")
                return False
            
            screenshot_path = screenshot_info.get("path")
            current_screenshot = Image.open(screenshot_path)
            
            # Convert to grayscale to reduce noise
            current_screenshot = current_screenshot.convert('L')
            
            # Calculate perceptual hash
            current_hash = imagehash.phash(current_screenshot)
            
            # If we have a previous screenshot, compare them
            if last_hash is not None:
                # Calculate image hash difference (0 is identical, higher is more different)
                hash_diff = current_hash - last_hash
                
                # Convert to similarity (0-1 scale, 1 is identical)
                similarity = 1.0 - (hash_diff / 64.0)  # phash returns 64-bit hash
                
                logger.debug(f"Screen similarity: {similarity:.4f}")
                
                # If similarity is above threshold, consider stable
                if similarity >= similarity_threshold:
                    logger.info(f"Screen stabilized after {elapsed:.2f}s")
                    return True
            
            # Update last screenshot
            last_screenshot = current_screenshot
            last_hash = current_hash
            
            # Wait before checking again
            time.sleep(check_interval)
            elapsed = time.time() - start_time
        
        logger.warning(f"Timed out waiting for visual stability after {max_wait}s")
        return False
    
    except Exception as e:
        logger.error(f"Error in visual stability check: {str(e)}")
        return False

def wait_based_on_action(action: Dict[str, Any]) -> bool:
    """
    Wait an appropriate amount of time based on the action type.
    
    Args:
        action: Dictionary with action metadata
        
    Returns:
        True if waited successfully, False otherwise
    """
    description = action.get("description", "").lower()
    code = action.get("code", "").lower()
    
    try:
        # Determine the type of action
        if "click" in description or "click" in code:
            logger.info("Detected click action, waiting for visual stability")
            return wait_for_visual_stability(max_wait=3.0)
        
        elif "type" in description or "write" in code or "type" in code:
            # For typing, wait a small fixed amount
            logger.info("Detected typing action, waiting fixed time")
            time.sleep(0.5)
            return True
        
        elif "press" in description or "key" in code:
            # For key press, wait a small fixed amount
            logger.info("Detected key press action, waiting fixed time")
            time.sleep(0.3)
            return True
        
        elif "move" in description or "move" in code:
            # For mouse movement, short wait
            logger.info("Detected mouse movement, waiting short time")
            time.sleep(0.2)
            return True
        
        elif "scroll" in description or "scroll" in code:
            # For scrolling, wait for stability
            logger.info("Detected scroll action, waiting for visual stability")
            return wait_for_visual_stability(max_wait=2.0)
        
        else:
            # Default for other actions
            logger.info("Using default wait for unrecognized action type")
            time.sleep(0.5)
            return True
    
    except Exception as e:
        logger.error(f"Error in action-based waiting: {str(e)}")
        # Fall back to a default wait on error
        time.sleep(0.5)
        return False

def test_visual_stability():
    """
    Test function to demonstrate visual stability detection.
    
    This function takes a series of screenshots and shows the similarity
    between consecutive frames to demonstrate how stability detection works.
    """
    print("\n=== Visual Stability Detection Test ===")
    print("Taking a series of screenshots to demonstrate stability detection...")
    print("Move windows or change your screen to see how stability is detected.")
    print("Press Ctrl+C to stop the test.")
    
    try:
        screenshots = []
        num_frames = 10
        
        # Take initial screenshot
        print("\nCapturing initial screenshot...")
        screenshots.append(take_screenshot())
        
        # Take additional screenshots with delay
        for i in range(1, num_frames):
            print(f"\nWaiting {0.5}s before next capture...")
            time.sleep(0.5)
            
            print(f"Capturing screenshot {i+1}/{num_frames}...")
            screenshots.append(take_screenshot())
            
            # Calculate similarity with previous frame
            similarity = calculate_image_similarity(screenshots[i-1], screenshots[i])
            print(f"Similarity with previous frame: {similarity:.4f}")
            
            if similarity >= 0.98:
                print("✓ Screen stable (no significant changes detected)")
            else:
                print("⚠ Screen changing (significant changes detected)")
        
        print("\n=== Test Complete ===")
        print("Visual stability detection works by comparing consecutive screenshots.")
        print("When similarity stays high for multiple checks, the screen is considered stable.")
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"\nError during test: {str(e)}")
    
    print("\nTest complete!")

if __name__ == "__main__":
    # If this module is run directly, run the test
    test_visual_stability() 