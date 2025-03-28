import os
import torch
import re
import logging
from PIL import Image

from llm_control import YOLO_CACHE_DIR, PHI3_CACHE_DIR, _ui_detector, _phi3_vision
from llm_control.utils.dependencies import check_and_install_package
from llm_control.utils.download import download_file
from llm_control import YOLO_MODEL_URL, YOLO_MODEL_FALLBACK_URL, PHI3_FILES
from llm_control.ui_detection.ocr import detect_text_regions

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def get_center_point(bbox):
    """Get center point of a bounding box in xyxy format"""
    if len(bbox) == 4:  # xyxy format
        x_min, y_min, x_max, y_max = bbox
        return ((x_min + x_max) / 2, (y_min + y_max) / 2)
    else:
        raise ValueError(f"Unsupported bbox format: {bbox}")

def get_ui_detector(device=None, download_if_missing=True):
    """Get UI element detector model (detects buttons, input fields, etc.)"""
    global _ui_detector
    if _ui_detector is None:
        # First, check if ultralytics is installed
        if not check_and_install_package("ultralytics", downgrade_conflicts=True):
            logger.warning("Ultralytics installation failed, YOLO detection won't be available")
            return None
            
        try:
            # Import required libraries
            from ultralytics import YOLO
            
            # Try to load specialized UI element detector if available
            # from https://huggingface.co/microsoft/OmniParser-v2.0/blob/main/icon_detect/model.pt
            # This could be a custom YOLO or other object detection model
            detector_path = os.path.join(YOLO_CACHE_DIR, "icon_detect.pt")
            yolo_path = os.path.join(YOLO_CACHE_DIR, "yolov8m.pt")
            
            # First priority: use specialized UI detector if available
            if os.path.exists(detector_path):
                logger.info(f"Loading specialized UI detector from {detector_path}")
                if device is None:
                    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
                    try:
                        _ui_detector = YOLO(detector_path)
                        # _ui_detector = torch.load(detector_path, map_location=device)
                        # _ui_detector.eval()
                    except Exception as e:
                        print("Failed to load specialized UI detector, trying YOLOv8...")
                        _ui_detector = YOLO(detector_path)
            # Second priority: use general YOLOv8 model
            elif os.path.exists(yolo_path):
                logger.info(f"Loading YOLOv8 model from {yolo_path}")
                _ui_detector = YOLO(yolo_path)
                logger.info("YOLOv8 model loaded successfully")
            # Download YOLOv8 if requested
            elif download_if_missing:
                logger.info("UI detector model not found, downloading YOLOv8...")
                try:
                    # Try to download YOLOv8 model from primary URL
                    try:
                        download_file(YOLO_MODEL_URL, yolo_path, "YOLOv8 model")
                    except Exception as download_error:
                        logger.warning(f"Failed to download from primary URL: {download_error}")
                        print(f"⚠️ Primary YOLO download failed, trying fallback URL...")
                        # Try fallback URL
                        download_file(YOLO_MODEL_FALLBACK_URL, yolo_path, "YOLOv8 model (fallback)")
                    
                    # Load the downloaded model
                    _ui_detector = YOLO(yolo_path)
                    logger.info("Successfully loaded YOLOv8 model")
                except Exception as e:
                    logger.error(f"Error downloading YOLOv8 model: {e}")
            else:
                logger.info("UI detector model not found and download not requested")
                # Will use OCR for UI element detection
        except Exception as e:
            logger.warning(f"Error loading UI detector: {e}")
    return _ui_detector

def check_phi3_model_files():
    """Check if Phi-3 model files exist in the cache directory"""
    # Essential files that must be present for the model to work
    essential_files = [
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "special_tokens_map.json",
        "preprocessor_config.json"
    ]
    
    # Weight files - we need either the split files or the combined model.safetensors
    weight_files_options = [
        ["model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors", "model.safetensors.index.json"],
        ["model.safetensors"],
        ["pytorch_model.bin"]  # For older format
    ]
    
    # Check for essential files
    has_essential_files = all(os.path.exists(os.path.join(PHI3_CACHE_DIR, f)) for f in essential_files)
    if not has_essential_files:
        logger.warning("Missing essential Phi-3 model configuration files")
        return False
    
    # Check for weight files (any of the options)
    has_weights = False
    for weight_option in weight_files_options:
        if all(os.path.exists(os.path.join(PHI3_CACHE_DIR, f)) for f in weight_option):
            has_weights = True
            break
    
    if not has_weights:
        logger.warning("No valid Phi-3 model weight files found")
        return False
    
    return True

def get_phi3_vision(download_if_missing=True):
    """Get or initialize Phi-3 Vision model for image captions/descriptions"""
    global _phi3_vision
    if _phi3_vision is None:
        # Check if transformers is installed
        if not check_and_install_package("transformers"):
            logger.warning("Transformers installation failed, Phi-3 Vision won't be available")
            return None
            
        # Check if safetensors is installed
        if not check_and_install_package("safetensors"):
            logger.warning("Safetensors installation failed, Phi-3 Vision won't be available")
            return None
            
        # Check if huggingface_hub is installed
        if not check_and_install_package("huggingface_hub"):
            logger.warning("huggingface_hub installation failed, Phi-3 Vision won't be available")
            return None
        
        try:
            # Import required libraries
            from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
            
            # Check if all model files exist
            all_files_exist = check_phi3_model_files()
            
            if all_files_exist:
                logger.info(f"Loading Phi-3 Vision model from {PHI3_CACHE_DIR}")
                try:
                    # Load model and tokenizer
                    tokenizer = AutoTokenizer.from_pretrained(
                        PHI3_CACHE_DIR,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    model = AutoModelForCausalLM.from_pretrained(
                        PHI3_CACHE_DIR,
                        device_map="auto",
                        torch_dtype=torch.bfloat16,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    processor = AutoProcessor.from_pretrained(
                        PHI3_CACHE_DIR,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    
                    _phi3_vision = {
                        "model": model,
                        "tokenizer": tokenizer,
                        "processor": processor
                    }
                    logger.info("Successfully loaded Phi-3 Vision model")
                except Exception as e:
                    logger.warning(f"Error loading Phi-3 Vision model: {e}")
                    
                    # If HeaderTooLarge error, clean the cache and try to re-download
                    if "HeaderTooLarge" in str(e):
                        logger.warning("HeaderTooLarge error detected, cleaning cache and trying again...")
                        print("Detected corrupted model files. Cleaning cache and re-downloading...")
                        
                        # Clean the cache by removing the problematic files
                        import shutil
                        shutil.rmtree(PHI3_CACHE_DIR)
                        os.makedirs(PHI3_CACHE_DIR, exist_ok=True)
                        
                        # Set flag to download againdsad
                        all_files_exist = False
            
            if not all_files_exist and download_if_missing:
                logger.info("Phi-3 Vision model not found or corrupted, downloading...")
                print("Downloading Phi-3 Vision model... (This is a large download of several GB)")
                
                try:
                    # Use huggingface_hub's snapshot_download to download the entire model
                    from huggingface_hub import snapshot_download
                    
                    print("Downloading Phi-3 Vision model from Hugging Face Hub...")
                    # Download the model to a temporary directory first
                    download_path = snapshot_download(
                        repo_id="microsoft/Phi-3-vision-128k-instruct",
                        local_dir=PHI3_CACHE_DIR,
                        local_dir_use_symlinks=False  # Ensure actual files are downloaded
                    )
                    
                    print(f"Phi-3 Vision model downloaded to: {download_path}")
                    
                    # Load the model from the download path
                    tokenizer = AutoTokenizer.from_pretrained(
                        PHI3_CACHE_DIR,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    model = AutoModelForCausalLM.from_pretrained(
                        PHI3_CACHE_DIR,
                        device_map="auto",
                        torch_dtype=torch.bfloat16,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    processor = AutoProcessor.from_pretrained(
                        PHI3_CACHE_DIR,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    
                    _phi3_vision = {
                        "model": model,
                        "tokenizer": tokenizer,
                        "processor": processor
                    }
                    logger.info("Successfully downloaded and initialized Phi-3 Vision model")
                    return _phi3_vision
                    
                except Exception as e:
                    logger.error(f"Error downloading/loading Phi-3 Vision model: {e}")
                    print(f"❌ Failed to download/load Phi-3 Vision model: {e}")
                    
                    # If still getting HeaderTooLarge, give specific advice
                    if "HeaderTooLarge" in str(e):
                        print("\n❗ The 'HeaderTooLarge' error persists. This likely indicates:")
                        print("   1. Corrupted or incomplete downloads")
                        print("   2. Insufficient memory to load the model")
                        print("   3. Incompatible model version")
                        print("\nTry manually clearing the cache and ensuring you have enough system memory:")
                        print(f"   rm -rf {PHI3_CACHE_DIR}/*")
                        print("   # Ensure you have at least 16GB of available RAM")
            else:
                logger.info("Phi-3 Vision model not found and download not requested")
        except Exception as e:
            logger.warning(f"Error loading Phi-3 Vision model: {e}")
    return _phi3_vision

def analyze_image_with_phi3(image_path, region=None):
    """Analyze image or image region with Phi-3 Vision model"""
    phi3 = get_phi3_vision(download_if_missing=True)
    if not phi3:
        logger.warning("Phi-3 Vision model not available")
        return None
    
    try:
        # Open the image
        if isinstance(image_path, str):
            image = Image.open(image_path)
        else:
            image = image_path
        
        # Crop to region if specified
        if region:
            if isinstance(region, list) and len(region) == 4:
                x1, y1, x2, y2 = region
                image = image.crop((x1, y1, x2, y2))
        
        # Process image with Phi-3 Vision
        model = phi3["model"]
        tokenizer = phi3["tokenizer"]
        processor = phi3["processor"]
        
        # Convert image to appropriate format
        try:
            # Use the correct prompt format with <image> tags for Phi-3 Vision
            prompt = "<image>\nDescribe this UI element or screen region in detail. Focus on identifying UI components, text, buttons, and their visual characteristics."
            
            inputs = processor(
                text=prompt,
                images=image,
                return_tensors="pt"
            ).to(model.device)
            
            # Generate description
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=512,
                    do_sample=False
                )
            
            # Decode output
            description = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove the prompt from the response if present
            if description.startswith(prompt):
                description = description[len(prompt):].strip()
            
            # Return results
            return {
                "description": description
            }
        except Exception as processor_error:
            logger.error(f"Error processing image with Phi-3 Vision: {processor_error}")
            # More specific error handling for common issues
            if "RepositoryNotFoundError" in str(processor_error) or "401 Client Error" in str(processor_error):
                print("Error: Repository path issue detected. The model may not be correctly loaded.")
                print(f"Try clearing the cache: rm -rf {PHI3_CACHE_DIR}/*")
                print("Then run the application with: python main.py --download-models --use-phi3 --clear-cache")
            return None
        
    except Exception as e:
        logger.error(f"Error analyzing image with Phi-3 Vision: {e}")
        return None

def detect_ui_elements(image_path):
    """Detect UI elements like buttons, input fields, etc."""
    ui_elements = []
    
    # First try dedicated UI detector if available
    detector = get_ui_detector()
    if detector:
        try:
            ui_elements = detect_ui_elements_with_yolo(image_path)
            print(f"UI elements: {ui_elements}")
        except Exception as e:
            logger.warning(f"UI detector error: {e}")
    
    # Fallback: Use text detection as proxy for UI elements
    if not ui_elements:
        text_regions = detect_text_regions(image_path)
        for region in text_regions:
            # Try to classify UI elements based on text content
            text = region['text'].lower()
            bbox = region['bbox']
            element_type = 'unknown'
            
            # Simple heuristic classification based on text
            if re.search(r'(submit|login|sign in|sign up|ok|cancel|yes|no|send|search|next|prev|back|continue)', text):
                element_type = 'button'
            elif re.search(r'(username|email|password|search)', text):
                element_type = 'input_field'
            elif re.search(r'(menu|file|edit|view|help|tools|options)', text):
                element_type = 'menu_item'
            elif re.search(r'(check|enable|disable|toggle)', text):
                element_type = 'checkbox'
            
            ui_elements.append({
                'type': element_type,
                'text': region['text'],
                'bbox': bbox,
                'confidence': region['confidence']
            })
    
    return ui_elements

def detect_ui_elements_with_yolo(image_path):
    """Detect UI elements using YOLO model"""
    ui_elements = []
    
    # Get YOLO detector
    detector = get_ui_detector(download_if_missing=True)
    if not detector:
        logger.warning("YOLO detector not available")
        return []
    
    try:
        # Run YOLO detection
        results = detector(image_path)
        
        # Process results
        for result in results:
            boxes = result.boxes
            for i, box in enumerate(boxes):
                # Get coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Get class and confidence
                cls = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                
                # Class mapping (depends on your YOLO model's classes)
                class_names = result.names
                class_name = class_names.get(cls, "unknown")
                
                # Map YOLO classes to UI element types
                element_type = "unknown"
                if class_name in ["button", "btn"]:
                    element_type = "button"
                elif class_name in ["input", "text_field", "textbox"]:
                    element_type = "input_field"
                elif class_name in ["menu", "dropdown"]:
                    element_type = "menu_item"
                elif class_name in ["checkbox", "check"]:
                    element_type = "checkbox"
                elif class_name in ["icon"]:
                    element_type = "icon"
                else:
                    element_type = class_name
                
                ui_elements.append({
                    "type": element_type,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": conf,
                    "yolo_class": class_name,
                    "yolo_class_id": cls
                })
        
        logger.info(f"YOLO detection found {len(ui_elements)} UI elements")
    
    except Exception as e:
        logger.error(f"Error in YOLO detection: {e}")
    
    return ui_elements

def get_ui_description(image_path):
    """Get a comprehensive description of UI elements in the image"""
    # Detect UI elements and text
    ui_elements = detect_ui_elements(image_path)
    text_regions = detect_text_regions(image_path)
    
    # Combine unique elements
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
            text = elem.get('text', '')
            description.append(f"  {i+1}. {text}")
        if len(elements) > 5:
            description.append(f"  ... and {len(elements)-5} more")
    
    return {
        'elements': all_elements,
        'summary': '\n'.join(description)
    }

def get_parsed_content_icon_phi3v(boxes, ocr_bbox, image_source, caption_model_processor):
    """Get parsed content for icons using Phi-3 Vision model"""
    # Implementation for extracting image captions using Phi-3 Vision
    # This would use the loaded Phi-3 model to analyze image regions
    # For now, return a placeholder
    return ["Button" for _ in range(len(boxes))]
