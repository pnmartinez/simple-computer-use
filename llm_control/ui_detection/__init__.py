import logging
import tempfile
import pyautogui
from PIL import Image

from llm_control.ui_detection.ocr import detect_text_regions
from llm_control.ui_detection.element_finder import (
    detect_ui_elements, detect_ui_elements_with_yolo, 
    analyze_image_with_phi3, get_ui_description
)
from llm_control.ui_detection.visualization import visualize_detections

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Export the main functions
__all__ = [
    'take_screenshot',
    'enhanced_screenshot_processing',
    'detect_text_regions',
    'detect_ui_elements',
    'detect_ui_elements_with_yolo',
    'analyze_image_with_phi3',
    'get_ui_description',
    'visualize_detections'
]

def take_screenshot():
    """Take a screenshot and return the path to the image file"""
    # Create temporary file to store the screenshot
    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    temp_file.close()
    
    # Take screenshot and save it
    screenshot = pyautogui.screenshot()
    screenshot.save(temp_file.name)
    
    logger.info(f"Screenshot saved to {temp_file.name}")
    return temp_file.name

def enhanced_screenshot_processing(screenshot_path, debug_visualize=False, use_yolo=False, use_phi3=False):
    """Process screenshot with enhanced vision techniques"""
    print("\n=== Starting Enhanced Screenshot Processing ===")
    
    # Get basic UI elements from OCR
    print("🔍 Detecting text regions with OCR...")
    text_regions = detect_text_regions(screenshot_path)
    ui_elements = detect_ui_elements(screenshot_path)
    print(f"📋 Found {len(text_regions)} text regions and {len(ui_elements)} basic UI elements")
    
    # If YOLO detection is requested, use it
    yolo_elements = []
    if use_yolo:
        print("🖱️ Detecting UI elements with YOLO...")
        yolo_elements = detect_ui_elements_with_yolo(screenshot_path)
        print(f"🎯 YOLO detected {len(yolo_elements)} UI elements (buttons, inputs, icons, etc.)")
        ui_elements.extend(yolo_elements)
    
    # Combine unique elements (avoid duplicates)
    all_elements = ui_elements.copy()
    
    # Add text regions not already included in UI elements
    ui_texts = [elem['text'].lower() for elem in ui_elements if 'text' in elem]
    for region in text_regions:
        if region['text'].lower() not in ui_texts:
            all_elements.append({
                'type': 'text',
                'text': region['text'],
                'bbox': region['bbox'],
                'confidence': region['confidence']
            })
    
    # Use Phi-3 Vision for enhanced understanding if requested
    screen_description = None
    if use_phi3:
        print("🧠 Analyzing screen with Phi-3 Vision for comprehensive understanding...")
        
        # Analyze whole screen
        screen_analysis = analyze_image_with_phi3(screenshot_path)
        if screen_analysis:
            screen_description = screen_analysis["description"]
            print("✅ Generated overall screen description with Phi-3 Vision")
            
        # Analyze individual UI elements detected by YOLO (prioritize these)
        print("🔎 Analyzing individual UI elements with Phi-3 Vision...")
        analyzed_count = 0
        
        # First analyze YOLO-detected elements (they're more visually distinct)
        for elem in yolo_elements:
            if elem.get('type') != 'text' and 'text' not in elem:
                # Open image and crop to element
                try:
                    image = Image.open(screenshot_path)
                    bbox = elem['bbox']
                    elem_img = image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
                    
                    # Analyze with Phi-3
                    analysis = analyze_image_with_phi3(elem_img)
                    if analysis:
                        elem['description'] = analysis["description"]
                        analyzed_count += 1
                except Exception as e:
                    logger.error(f"Error analyzing element with Phi-3: {e}")
        
        # Then analyze other elements without text
        for elem in all_elements:
            if elem not in yolo_elements and elem.get('type') != 'text' and 'text' not in elem and 'description' not in elem:
                # Open image and crop to element
                try:
                    image = Image.open(screenshot_path)
                    bbox = elem['bbox']
                    elem_img = image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
                    
                    # Analyze with Phi-3
                    analysis = analyze_image_with_phi3(elem_img)
                    if analysis:
                        elem['description'] = analysis["description"]
                        analyzed_count += 1
                except Exception as e:
                    logger.error(f"Error analyzing element with Phi-3: {e}")
        
        print(f"✅ Analyzed {analyzed_count} UI elements with Phi-3 Vision")
    
    # Create a comprehensive description
    description = []
    description.append(f"Found {len(all_elements)} UI elements:")
    
    # Group by type
    by_type = {}
    for elem in all_elements:
        elem_type = elem.get('type', 'unknown')
        if elem_type not in by_type:
            by_type[elem_type] = []
        by_type[elem_type].append(elem)
    
    # Generate description by type
    for elem_type, elements in by_type.items():
        description.append(f"- {len(elements)} {elem_type}s:")
        for i, elem in enumerate(elements[:5]):  # Limit to 5 per type
            text = elem.get('text', elem.get('description', ''))
            description.append(f"  {i+1}. {text}")
        if len(elements) > 5:
            description.append(f"  ... and {len(elements)-5} more")
    
    # Add screen description from Phi-3 if available
    if screen_description:
        description.append("\nOverall screen description:")
        description.append(screen_description)
    
    # Generate visualization if in debug mode
    visualization_path = None
    if debug_visualize:
        print("🎨 Generating visualization of detected elements...")
        visualization_path = visualize_detections(screenshot_path, all_elements)
        logger.info(f"Created visualization: {visualization_path}")
    
    print("=== Enhanced Screenshot Processing Complete ===\n")
    
    return {
        'screenshot_path': screenshot_path,
        'visualization_path': visualization_path,
        'ui_description': {
            'elements': all_elements,
            'summary': '\n'.join(description)
        },
        'screen_description': screen_description
    }
