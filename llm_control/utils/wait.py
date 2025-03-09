import time
import logging
import numpy as np
from PIL import Image
import cv2
from skimage.metrics import structural_similarity
import os

from llm_control.ui_detection import take_screenshot

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def calculate_image_similarity(img1_path, img2_path):
    """
    Calculate visual similarity between two images (0.0 to 1.0)
    
    Args:
        img1_path: Path to first image
        img2_path: Path to second image
        
    Returns:
        Float representing similarity (0.0 to 1.0, where 1.0 is identical)
    """
    logger.debug(f"Comparing images: {img1_path} and {img2_path}")
    
    # Validate inputs first
    if not isinstance(img1_path, str) or not isinstance(img2_path, str):
        logger.error(f"Invalid input types: img1_path={type(img1_path)}, img2_path={type(img2_path)}")
        return 0.0
    
    # Check if files exist
    if not os.path.exists(img1_path):
        logger.error(f"First image path does not exist: {img1_path}")
        return 0.0
    if not os.path.exists(img2_path):
        logger.error(f"Second image path does not exist: {img2_path}")
        return 0.0
    
    try:
        # Load images from paths
        logger.debug(f"Loading image 1: {img1_path}")
        img1 = Image.open(img1_path)
        
        logger.debug(f"Loading image 2: {img2_path}")
        img2 = Image.open(img2_path)
        
        # Get image dimensions for debugging
        img1_size = img1.size
        img2_size = img2.size
        logger.debug(f"Image 1 size: {img1_size}, Image 2 size: {img2_size}")
        
        # Convert PIL images to numpy arrays
        img1_array = np.array(img1)
        img2_array = np.array(img2)
        
        # Ensure images are the same size
        if img1_array.shape != img2_array.shape:
            logger.warning(f"Images are different sizes: {img1_array.shape} vs {img2_array.shape}, resizing")
            img2 = img2.resize(img1.size)
            img2_array = np.array(img2)
        
        # Convert to grayscale for more efficient comparison
        if len(img1_array.shape) == 3 and img1_array.shape[2] >= 3:
            logger.debug("Converting color images to grayscale")
            gray1 = cv2.cvtColor(img1_array, cv2.COLOR_RGB2GRAY)
            gray2 = cv2.cvtColor(img2_array, cv2.COLOR_RGB2GRAY)
        else:
            # Images are already grayscale
            logger.debug("Images already in grayscale")
            gray1 = img1_array
            gray2 = img2_array
        
        # Calculate structural similarity index
        logger.debug("Calculating structural similarity")
        score, _ = structural_similarity(gray1, gray2, full=True)
        logger.debug(f"Similarity score: {score:.4f}")
        return score
    except Exception as e:
        logger.error(f"Error calculating image similarity: {type(e)}")
        logger.error(f"Error details: {str(e)}")
        
        # Print more details about what happened
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Fall back to a basic default
        return 0.0

def wait_for_visual_stability(timeout=10, stability_threshold=0.999, 
                              check_interval=0.3, consecutive_stable=5):
    """
    Wait until the screen stops changing significantly (becomes visually stable)
    
    Args:
        timeout: Maximum time to wait in seconds
        stability_threshold: Similarity threshold to consider stable (0.0 to 1.0)
        check_interval: Time between checks in seconds
        consecutive_stable: Number of consecutive stable checks required
        
    Returns:
        Boolean indicating whether stability was achieved
    """
    # Take initial screenshot
    try:
        previous_screenshot = take_screenshot()  # This returns a file path
    except Exception as e:
        logger.error(f"Failed to take initial screenshot: {str(e)}")
        time.sleep(1.0)  # Fallback delay
        return False
    
    start_time = time.time()
    stable_count = 0
    error_count = 0
    max_errors = 3  # Maximum number of consecutive errors before giving up
    
    print(f"🔍 Waiting for visual stability (threshold: {stability_threshold:.2f})")
    logger.info(f"Waiting for visual stability (threshold: {stability_threshold:.2f})")
    
    while time.time() - start_time < timeout:
        time.sleep(check_interval)
        
        try:
            # Take new screenshot
            current_screenshot = take_screenshot()  # This returns a file path
            
            # Compare current screenshot with previous one to detect changes
            similarity = calculate_image_similarity(previous_screenshot, current_screenshot)
            
            # Reset error count on successful comparison
            error_count = 0
            
            logger.debug(f"Screenshot similarity: {similarity:.4f}")
            
            if similarity >= stability_threshold:
                stable_count += 1
                print(f"  Stable check {stable_count}/{consecutive_stable} (similarity: {similarity:.4f})")
                
                if stable_count >= consecutive_stable:
                    elapsed = time.time() - start_time
                    print(f"✓ Screen became stable after {elapsed:.2f}s")
                    logger.info(f"Screen became stable after {elapsed:.2f}s")
                    return True
            else:
                stable_count = 0
                print(f"  Screen still changing (similarity: {similarity:.4f})")
                
            previous_screenshot = current_screenshot
            
        except Exception as e:
            error_count += 1
            logger.error(f"Error during visual stability check: {str(e)}")
            
            if error_count >= max_errors:
                logger.error(f"Too many consecutive errors ({max_errors}), aborting stability detection")
                print(f"⚠ Aborting stability detection due to repeated errors")
                return False
            
            # Continue the loop despite errors
    
    print(f"⚠ Timed out waiting for visual stability after {timeout}s")
    logger.warning(f"Timed out waiting for visual stability after {timeout}s")
    return False

def wait_based_on_action(action, use_visual_stability=True):
    """
    Smart wait based on the action type
    
    Args:
        action: The action dictionary containing metadata
        use_visual_stability: Whether to use visual stability for appropriate actions
        
    Returns:
        Boolean indicating success of wait mechanism
    """
    description = action.get('description', '').lower()
    explanation = action.get('explanation', '').lower()
    code = action.get('code', '')
    
    # Determine action type more precisely
    if code.strip().startswith('#') or not code.strip():
        # Skip waiting for comments or empty code
        action_type = 'no_action'
    elif 'open' in description:
        action_type = 'open_app'
    elif 'click' in description:
        # Only use visual stability for clicks that might cause major UI changes
        # like clicking on buttons, links or menu items
        if any(term in description.lower() for term in ['button', 'link', 'menu', 'icon']):
            action_type = 'major_click'
        else:
            action_type = 'click'
    elif 'type' in description:
        action_type = 'type'
    elif 'scroll' in description:
        action_type = 'scroll'
    elif 'press' in description:
        # Special case for Enter and Tab keys which often trigger UI changes
        if any(key in description.lower() for key in ['enter', 'return', 'tab']):
            action_type = 'navigation_key'
        else:
            action_type = 'keyboard'
    else:
        action_type = 'unknown'
    
    logger.debug(f"Action type determined as: {action_type}")
    
    # Skip waiting for no-op actions
    if action_type == 'no_action':
        print(f"⏭️ No waiting needed for this action")
        return True
    
    # For app opening and major UI changes, use visual stability if enabled
    if use_visual_stability and action_type in ['open_app', 'major_click', 'navigation_key']:
        try:
            if action_type == 'open_app':
                # Longer timeout for app opening
                print(f"🔍 Using visual stability detection for app opening (timeout: 15s)")
                return wait_for_visual_stability(timeout=15, stability_threshold=0.99)
            elif action_type == 'major_click':
                # Standard timeout for major clicks
                print(f"🔍 Using visual stability detection for UI interaction (timeout: 8s)")
                return wait_for_visual_stability(timeout=8, stability_threshold=0.98)
            else:
                # Shorter timeout for navigation keys
                print(f"🔍 Using visual stability detection for navigation key (timeout: 5s)")
                return wait_for_visual_stability(timeout=10, stability_threshold=0.98)
        except Exception as e:
            # If visual stability detection fails, fall back to fixed delay
            logger.error(f"Visual stability detection failed: {str(e)}. Using fallback.")
            # Use fallback delays
            fallback_times = {
                'open_app': 3.0,
                'major_click': 1.5,
                'navigation_key': 1.0
            }
            wait_time = fallback_times.get(action_type, 1.0)
            print(f"⏱️ Fallback: Waiting {wait_time:.1f}s for {action_type} action")
            time.sleep(wait_time)
            return False
    else:
        # Default wait times for different action types
        wait_times = {
            'open_app': 3.0,
            'major_click': 1.5,
            'click': 0.8,
            'type': 0.3,
            'scroll': 0.5,
            'navigation_key': 1.0,
            'keyboard': 0.3,
            'unknown': 0.5,
            'no_action': 0.0
        }
        
        wait_time = wait_times.get(action_type, 0.5)
        print(f"⏱️ Waiting {wait_time:.1f}s for {action_type} action")
        time.sleep(wait_time)
        return True

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