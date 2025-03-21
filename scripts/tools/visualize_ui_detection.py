#!/usr/bin/env python3
"""
UI Detection Visualization Tool

This script takes a screenshot and visualizes UI detection results,
highlighting the top matches for a specified target text.
"""

import os
import sys
import logging
import argparse
import tempfile
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("ui-detection-visualizer")

def take_screenshot() -> str:
    """Take a screenshot and return the path to the saved image file."""
    try:
        from llm_control.screenshot import take_screenshot as lc_take_screenshot
        
        screenshot_info = lc_take_screenshot()
        if screenshot_info.get("success", False):
            return screenshot_info["path"]
        else:
            logger.error(f"Failed to take screenshot: {screenshot_info.get('error', 'Unknown error')}")
            sys.exit(1)
    except ImportError:
        try:
            import pyautogui
            import tempfile
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            screenshot.save(temp_file.name)
            
            return temp_file.name
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            sys.exit(1)

def find_ui_elements(screenshot_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Find UI elements in the screenshot using OCR and YOLO."""
    ui_elements = []
    text_regions = []
    
    try:
        # Try to import from llm_control first
        try:
            from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo, detect_text_regions
            
            # Detect UI elements with YOLO
            ui_elements = detect_ui_elements_with_yolo(screenshot_path)
            
            # Detect text regions with OCR
            text_regions = detect_text_regions(screenshot_path)
            
        except ImportError as e:
            logger.error(f"Error importing UI detection modules: {str(e)}")
            logger.error("Make sure llm_control package is installed with UI detection dependencies:")
            logger.error("pip install -e .[ui]")
            return [], []
    
    except Exception as e:
        logger.error(f"Error detecting UI elements: {str(e)}")
        return [], []
    
    return ui_elements, text_regions

def find_matches_for_target(target_text: str, ui_elements: List[Dict[str, Any]], 
                            text_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Find potential matches for the specified target text."""
    # Combine UI elements and text regions
    all_ui_elements = ui_elements + text_regions
    
    # Normalize the target text for comparison
    normalized_target = target_text.lower()
    
    # Find potential matches and their confidence scores
    matches = []
    
    # Search in UI elements
    for elem in all_ui_elements:
        if 'text' in elem and elem['text']:
            # Normalize element text
            elem_text = elem['text'].lower()
            
            # Calculate a simple score based on substring matching
            if normalized_target == elem_text:
                # Exact match
                score = 1.0
            elif normalized_target in elem_text:
                # Substring match - score based on relative length
                score = len(normalized_target) / len(elem_text)
            elif elem_text in normalized_target:
                # Element text is substring of target
                score = len(elem_text) / len(normalized_target)
            else:
                # Partial word matching for more fuzzy matches
                target_words = normalized_target.split()
                elem_words = elem_text.split()
                common_words = set(target_words) & set(elem_words)
                
                if common_words:
                    score = len(common_words) / max(len(target_words), len(elem_words))
                else:
                    # No word match
                    score = 0.0
            
            # Only add if there's some match
            if score > 0.0:
                match_info = {
                    'text': elem['text'],
                    'bbox': elem.get('bbox', [0, 0, 0, 0]),
                    'confidence': score,
                    'type': elem.get('type', 'text')
                }
                matches.append(match_info)
    
    # Sort matches by confidence (highest first)
    matches.sort(key=lambda x: x['confidence'], reverse=True)
    
    return matches

def visualize_matches(screenshot_path: str, matches: List[Dict[str, Any]], target_text: str, 
                      output_path: Optional[str] = None) -> str:
    """Create a visualization of the matches on the screenshot."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import datetime
        
        # Load the screenshot
        image = Image.open(screenshot_path)
        draw = ImageDraw.Draw(image)
        
        # Try to load a font
        try:
            # Try to get a nice font if available
            font = ImageFont.truetype("Arial", 20)
            small_font = ImageFont.truetype("Arial", 14)
        except IOError:
            # Fallback to default font
            font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Colors for different confidence levels
        colors = {
            'high': (0, 255, 0, 128),    # Green for high confidence (>0.8)
            'medium': (255, 255, 0, 128), # Yellow for medium confidence (0.5-0.8)
            'low': (255, 0, 0, 128),     # Red for low confidence (<0.5)
            'text': (255, 255, 255, 255) # White for text
        }
        
        # Draw title and target info
        title = f"UI Detection Results for Target: '{target_text}'"
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Draw background for title
        title_bg = (0, 0, 0, 180)
        draw.rectangle([(0, 0), (image.width, 60)], fill=title_bg)
        
        # Draw title text
        draw.text((10, 10), title, fill=colors['text'], font=font)
        draw.text((10, 35), f"Time: {timestamp} | Found {len(matches)} matches", 
                  fill=colors['text'], font=small_font)
        
        # Draw each match with appropriate color based on confidence
        for i, match in enumerate(matches[:10]):  # Limit to top 10 matches
            confidence = match.get('confidence', 0.0)
            bbox = match.get('bbox', [0, 0, 0, 0])
            text = match.get('text', '')
            match_type = match.get('type', 'unknown')
            
            # Choose color based on confidence
            if confidence >= 0.8:
                color = colors['high']
            elif confidence >= 0.5:
                color = colors['medium']
            else:
                color = colors['low']
            
            # Draw rectangle around the match
            draw.rectangle(bbox, outline=color, width=3)
            
            # Draw label with confidence and rank
            label = f"#{i+1}: '{text}' ({confidence:.2f})"
            text_bg = (0, 0, 0, 180)
            
            # Calculate label position (above the bbox if possible)
            label_x = bbox[0]
            label_y = max(bbox[1] - 25, 70)  # At least below the title bar
            
            # Draw background for label
            label_width = len(label) * 8  # Approximate width
            draw.rectangle([(label_x, label_y), (label_x + label_width, label_y + 20)], 
                          fill=text_bg)
            
            # Draw label text
            draw.text((label_x, label_y), label, fill=color, font=small_font)
        
        # Save the visualization
        if output_path:
            result_path = output_path
        else:
            result_path = tempfile.mktemp(suffix="_ui_detection.png")
        
        image.save(result_path)
        logger.info(f"Saved visualization to: {result_path}")
        return result_path
    
    except Exception as e:
        logger.error(f"Error creating visualization: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return screenshot_path

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Visualize UI detection results for a target")
    
    parser.add_argument(
        "target_text",
        type=str,
        help="The target text to search for in UI elements"
    )
    
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output path for the visualization image",
        default=None
    )
    
    parser.add_argument(
        "--screenshot",
        "-s",
        type=str,
        help="Path to an existing screenshot (if not provided, a new one will be taken)",
        default=None
    )
    
    parser.add_argument(
        "--top",
        "-n",
        type=int,
        help="Number of top matches to highlight",
        default=5
    )
    
    args = parser.parse_args()
    
    # Take or load screenshot
    if args.screenshot:
        if not os.path.exists(args.screenshot):
            logger.error(f"Screenshot file not found: {args.screenshot}")
            sys.exit(1)
        screenshot_path = args.screenshot
        logger.info(f"Using existing screenshot: {screenshot_path}")
    else:
        logger.info("Taking a new screenshot...")
        screenshot_path = take_screenshot()
        logger.info(f"Screenshot saved to: {screenshot_path}")
    
    # Find UI elements
    logger.info("Detecting UI elements...")
    ui_elements, text_regions = find_ui_elements(screenshot_path)
    logger.info(f"Found {len(ui_elements)} UI elements and {len(text_regions)} text regions")
    
    # Find matches for the target
    logger.info(f"Finding matches for target: '{args.target_text}'")
    matches = find_matches_for_target(args.target_text, ui_elements, text_regions)
    
    # Log the matches
    logger.info(f"Found {len(matches)} potential matches for target: '{args.target_text}'")
    
    # Log the top N matches
    top_n = min(args.top, len(matches))
    for i, match in enumerate(matches[:top_n]):
        logger.info(f"Match #{i+1}: '{match['text']}' at confidence {match['confidence']:.2f}, type: {match['type']}")
    
    # Create visualization
    if matches:
        logger.info("Creating visualization...")
        visualization_path = visualize_matches(screenshot_path, matches, args.target_text, args.output)
        
        # Try to open the image
        try:
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                os.startfile(visualization_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", visualization_path])
            else:  # Linux
                subprocess.run(["xdg-open", visualization_path])
            
            logger.info(f"Opened visualization: {visualization_path}")
        except Exception as e:
            logger.warning(f"Could not automatically open the visualization: {str(e)}")
            logger.info(f"Please open manually: {visualization_path}")
    else:
        logger.warning(f"No matches found for target: '{args.target_text}'")
    
    # Clean up if using a temporary screenshot
    if not args.screenshot and args.output:
        try:
            os.unlink(screenshot_path)
        except (OSError, PermissionError):
            pass

if __name__ == "__main__":
    main() 