import os
import torch
import re
import logging
import shutil
from PIL import Image
import numpy as np
from pathlib import Path
import cv2  # Add cv2 import for color analysis

from llm_control import YOLO_CACHE_DIR, PHI3_CACHE_DIR, _ui_detector, _phi3_vision
from llm_control.utils.dependencies import check_and_install_package
from llm_control.utils.download import download_file
from llm_control import YOLO_MODEL_URL, YOLO_MODEL_FALLBACK_URL, PHI3_FILES
from llm_control.ui_detection.ocr import detect_text_regions

# Get the package logger
logger = logging.getLogger("llm-pc-control")

# Global variable for BLIP2 model
_blip2_model = None

def get_caption_model_processor(model_name="blip2", model_name_or_path="Salesforce/blip2-opt-2.7b", device=None):
    """Get or initialize BLIP2 model for image captioning.
    
    Args:
        model_name: Model type to use ('blip2' or 'florence2')
        model_name_or_path: HuggingFace model path
        device: Device to use ('cuda' or 'cpu')
        
    Returns:
        Dictionary with model and processor
    """
    global _blip2_model
    
    if _blip2_model is not None:
        return _blip2_model
        
    if not device:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
    try:
        # Check for required dependencies first
        if not check_and_install_package("transformers"):
            logger.warning("Transformers installation failed, model won't be available")
            return None
            
        if not check_and_install_package("accelerate"):
            logger.warning("Accelerate installation failed, model won't be available")
            return None
            
        if model_name == "blip2":
            from transformers import Blip2Processor, Blip2ForConditionalGeneration
            
            logger.info(f"Loading BLIP2 model from {model_name_or_path}")
            
            # Load processor first
            processor = Blip2Processor.from_pretrained(model_name_or_path)
            
            # Configure model loading
            model_kwargs = {
                "torch_dtype": torch.float32 if device == 'cpu' else torch.float16,
                "low_cpu_mem_usage": True
            }
            
            # Only use device_map on CUDA
            if device != 'cpu':
                model_kwargs["device_map"] = "auto"
            
            # Load model
            model = Blip2ForConditionalGeneration.from_pretrained(
                model_name_or_path,
                **model_kwargs
            )
            
            # Move to device if CPU
            if device == 'cpu':
                model = model.to(device)
                
            _blip2_model = {'model': model, 'processor': processor}
            logger.info("Successfully loaded BLIP2 model")
            return _blip2_model
            
        elif model_name == "florence2":
            from transformers import AutoProcessor, AutoModelForCausalLM
            
            logger.info(f"Loading Florence2 model from {model_name_or_path}")
            processor = AutoProcessor.from_pretrained("microsoft/Florence-2-base", trust_remote_code=True)
            
            # Configure model loading
            model_kwargs = {
                "torch_dtype": torch.float32 if device == 'cpu' else torch.float16,
                "trust_remote_code": True,
                "low_cpu_mem_usage": True
            }
            
            # Only use device_map on CUDA
            if device != 'cpu':
                model_kwargs["device_map"] = "auto"
            
            # Load model
            model = AutoModelForCausalLM.from_pretrained(
                model_name_or_path,
                **model_kwargs
            )
            
            # Move to device if CPU
            if device == 'cpu':
                model = model.to(device)
                
            _blip2_model = {'model': model, 'processor': processor}
            logger.info("Successfully loaded Florence2 model")
            return _blip2_model
            
    except Exception as e:
        logger.error(f"Error loading caption model: {e}")
        return None

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
        # Check for required dependencies first
        if not check_and_install_package("transformers"):
            logger.warning("Transformers installation failed, Phi-3 Vision won't be available")
            return None
            
        if not check_and_install_package("safetensors"):
            logger.warning("Safetensors installation failed, Phi-3 Vision won't be available")
            return None
            
        if not check_and_install_package("huggingface_hub"):
            logger.warning("huggingface_hub installation failed, Phi-3 Vision won't be available")
            return None
            
        if not check_and_install_package("accelerate"):
            logger.warning("Accelerate installation failed, Phi-3 Vision won't be available")
            return None
        
        # Try to import flash-attn directly - it's optional
        has_flash_attn = False
        try:
            import flash_attn
            has_flash_attn = True
            logger.info("FlashAttention2 is available")
        except ImportError:
            logger.info("FlashAttention2 not available, will use standard attention")
        
        try:
            # Import required libraries
            from transformers import AutoModelForCausalLM, AutoTokenizer, AutoProcessor
            
            # Check if all model files exist
            all_files_exist = check_phi3_model_files()
            
            if all_files_exist:
                logger.info(f"Loading Phi-3 Vision model from {PHI3_CACHE_DIR}")
                try:
                    # Load model and tokenizer with appropriate config based on flash-attn availability
                    model_kwargs = {
                        "device_map": "auto",
                        "torch_dtype": torch.bfloat16,
                        "trust_remote_code": True,
                        "local_files_only": True,
                        "low_cpu_mem_usage": True,
                        "use_flash_attention_2": True,  # Explicitly disable by default
                        "attn_implementation": "eager"  # Use eager implementation
                    }
                    
                    # Only enable FlashAttention2 if available and explicitly requested
                    if has_flash_attn and os.environ.get("USE_FLASH_ATTENTION", "").lower() == "true":
                        model_kwargs["use_flash_attention_2"] = True
                        model_kwargs.pop("attn_implementation", None)  # Remove eager implementation
                        logger.info("Using FlashAttention2 for Phi-3 Vision model")
                    
                    # Load tokenizer first
                    tokenizer = AutoTokenizer.from_pretrained(
                        PHI3_CACHE_DIR,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    
                    # Load model with config
                    model = AutoModelForCausalLM.from_pretrained(
                        PHI3_CACHE_DIR,
                        **model_kwargs
                    )
                    
                    # Load processor
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
                    return _phi3_vision
                    
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
                        
                        # Set flag to download again
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
                    
                    # Load the model with appropriate config based on flash-attn availability
                    model_kwargs = {
                        "device_map": "auto",
                        "torch_dtype": torch.bfloat16,
                        "trust_remote_code": True,
                        "local_files_only": True,
                        "low_cpu_mem_usage": True,
                        "use_flash_attention_2": False,  # Explicitly disable by default
                        "attn_implementation": "eager"  # Use eager implementation
                    }
                    
                    # Only enable FlashAttention2 if available and explicitly requested
                    if has_flash_attn and os.environ.get("USE_FLASH_ATTENTION", "").lower() == "true":
                        model_kwargs["use_flash_attention_2"] = True
                        model_kwargs.pop("attn_implementation", None)  # Remove eager implementation
                        logger.info("Using FlashAttention2 for Phi-3 Vision model")
                    
                    # Load tokenizer first
                    tokenizer = AutoTokenizer.from_pretrained(
                        PHI3_CACHE_DIR,
                        trust_remote_code=True,
                        local_files_only=True
                    )
                    
                    # Load model with config
                    model = AutoModelForCausalLM.from_pretrained(
                        PHI3_CACHE_DIR,
                        **model_kwargs
                    )
                    
                    # Load processor
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
                    return None
            else:
                logger.info("Phi-3 Vision model not found and download not requested")
                return None
        except Exception as e:
            logger.warning(f"Error loading Phi-3 Vision model: {e}")
            return None
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
            # Construct prompt with proper image tag format
            prompt = "Below is an image of a UI element. Describe what you see, focusing on its type and function.\n<image>image1</image>\n"
            
            # Process image and text together
            inputs = processor(
                text=prompt,
                images=[image],  # Pass as list since we're using image tags
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

def detect_ui_elements(image_path, use_ocr_fallback=True):
    """Detect UI elements like buttons, input fields, etc."""
    ui_elements = []
    
    # First try dedicated UI detector if available
    detector = get_ui_detector()
    if detector:
        try:
            ui_elements = detect_ui_elements_with_yolo(image_path)
        except Exception as e:
            logger.warning(f"UI detector error: {e}")
    
    # Fallback: Use text detection as proxy for UI elements - only if specifically allowed
    if not ui_elements and use_ocr_fallback:
        logger.info("No UI elements detected with YOLO, using OCR as fallback")
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

def get_ui_description(image_path, steps_with_targets, ocr_found_targets=False):
    """Get a comprehensive description of UI elements in the image"""
    # Get targets that require OCR
    targets_in_steps = [step['target'] for step in steps_with_targets if step.get('target') and step.get('needs_ocr', False)]
    
    # If no targets need OCR, avoid unnecessary OCR processing
    if not targets_in_steps:
        logger.info("No OCR targets needed, skipping OCR text detection")
        text_regions = []
        ocr_found_targets = True  # No targets to find, so technically they're "found"
    else:
        # Detect text using OCR since we need it
        logger.info(f"Detecting text regions for {len(targets_in_steps)} OCR targets")
        text_regions = detect_text_regions(image_path)
        
        # Check if OCR found all the targets
        text_region_texts = [region['text'].lower() for region in text_regions]
        ocr_found_targets = all(
            any(target.lower() in text for text in text_region_texts)
            for target in targets_in_steps
        )
    
    # Detect UI elements with YOLO (may use OCR as fallback if YOLO detection fails)
    # Only run YOLO if we have targets that need OCR
    if targets_in_steps:
        ui_elements = detect_ui_elements(image_path, use_ocr_fallback=True)
    else:
        # When no OCR targets are needed, disable OCR fallback to avoid unnecessary OCR
        ui_elements = detect_ui_elements(image_path, use_ocr_fallback=False)
        logger.info("Using YOLO detection only (disabling OCR fallback) as no OCR targets needed")
    
    # Load image for captioning - only if needed
    if (targets_in_steps or ui_elements) and isinstance(image_path, str):
        image = Image.open(image_path)
        # Convert to numpy array for color analysis
        np_image = np.array(image)
    elif (targets_in_steps or ui_elements):
        image = Image.fromarray(image_path)
        np_image = image_path if isinstance(image_path, np.ndarray) else np.array(image)
    else:
        # Placeholder for when we don't need the image
        image = None
        np_image = None
    
    # Combine unique elements
    all_elements = ui_elements.copy()
    
    # Add text regions not already included in UI elements
    if text_regions:
        ui_texts = [elem['text'].lower() for elem in ui_elements if 'text' in elem]
        for region in text_regions:
            if region['text'].lower() not in ui_texts:
                all_elements.append({
                    'type': 'text',
                    'text': region['text'],
                    'bbox': region['bbox'],
                    'confidence': region['confidence']
                })
    
    # Skip the rest of processing if no UI elements or OCR targets
    if not all_elements:
        logger.info("No UI elements or OCR targets found, returning minimal UI description")
        return {
            'elements': [],
            'summary': 'No UI elements detected - OCR skipped or no targets found'
        }
    
    # Get captions for elements without text, of type icon, with square-ish bounding boxes and vivid colors
    elements_without_text = []
    for elem in all_elements:
        if ('text' not in elem or not elem['text']) and elem.get('type') in ['icon', 'UI element']:
            try:
                # Check if the bounding box is approximately square
                if 'bbox' in elem and len(elem['bbox']) == 4:
                    x1, y1, x2, y2 = elem['bbox']
                    width = abs(x2 - x1)
                    height = abs(y2 - y1)
                    
                    # Element is considered square-ish if the aspect ratio is between 0.7 and 1.3
                    if width > 0 and height > 0:
                        aspect_ratio = width / height
                        if 0.7 <= aspect_ratio <= 1.3:
                            # Add element without doing color analysis
                            # Color analysis will be done later to avoid crashes
                            elements_without_text.append(elem)
            except Exception as e:
                logger.warning(f"Error processing element bbox: {e}")

    # Now process colors for the filtered elements
    elements_with_vivid_colors = []
    if np_image is not None and elements_without_text:
        for elem in elements_without_text:
            try:
                # Extract the region of interest
                x1, y1, x2, y2 = [int(coord) for coord in elem['bbox']]
                
                # Ensure coordinates are within image bounds
                img_height, img_width = np_image.shape[:2]
                x1 = max(0, min(x1, img_width-1))
                x2 = max(0, min(x2, img_width))
                y1 = max(0, min(y1, img_height-1))
                y2 = max(0, min(y2, img_height))
                
                # Skip if invalid coordinates
                if x1 >= x2 or y1 >= y2:
                    continue
                    
                roi = np_image[y1:y2, x1:x2]
                
                if roi.size > 0 and roi.ndim == 3:  # Ensure valid image with color channels
                    # Convert to HSV for better color analysis
                    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_RGB2HSV)
                    
                    # Calculate average saturation and value (brightness)
                    avg_saturation = np.mean(hsv_roi[:, :, 1])
                    avg_value = np.mean(hsv_roi[:, :, 2])
                    
                    # Calculate color variance (higher variance = more colorful)
                    color_variance = np.std(roi.reshape(-1, 3), axis=0).mean()
                    
                    # Check if the ROI has vivid colors (high saturation and brightness)
                    # Use less strict thresholds to ensure we get some results
                    if avg_saturation > 50 and avg_value > 70 and color_variance > 20:
                        elements_with_vivid_colors.append(elem)
                        elem['color_metrics'] = {
                            'saturation': float(avg_saturation),
                            'brightness': float(avg_value),
                            'variance': float(color_variance)
                        }
            except Exception as e:
                logger.warning(f"Error analyzing colors for element: {e}")
    
    # Use the elements with vivid colors for further processing
    elements_without_text = elements_with_vivid_colors
    
    # Determine if we should use vision captioning
    # 1. Override with ocr_found_targets parameter if explicitly set to True
    # 2. Otherwise, determine based on whether OCR found text matches and sufficient elements
    should_use_vision_captioning = not ocr_found_targets
    
    if elements_without_text and should_use_vision_captioning and image is not None:
        try:
            # Extract bounding boxes
            boxes = [elem['bbox'] for elem in elements_without_text]
            ocr_boxes = [elem['bbox'] for elem in all_elements if 'text' in elem and elem['text']]
            
            # Get captions - passing OCR target information
            captions = get_parsed_content_icon_phi3v(boxes, ocr_boxes, image, None, ocr_found_targets=ocr_found_targets)
            
            # Add captions to elements
            for elem, caption in zip(elements_without_text, captions):
                elem['text'] = caption
                elem['caption_source'] = 'vision'  # Mark the source as vision model
        except Exception as e:
            logger.error(f"Error getting captions for elements: {e}")
            # Add placeholder captions if captioning fails
            for elem in elements_without_text:
                elem['text'] = f"{elem.get('type', 'UI')} element"
                elem['caption_source'] = 'fallback'
    else:
        # If not using vision captioning, set generic text for elements without text
        for elem in elements_without_text:
            elem['text'] = f"{elem.get('type', 'UI')} element"
            elem['caption_source'] = 'default'
            
        if elements_without_text:
            logger.info(f"Skipping vision captioning for {len(elements_without_text)} elements - OCR found sufficient results")
    
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
            caption_source = elem.get('caption_source', '')
            if caption_source:
                description.append(f"  {i+1}. {text} (caption from {caption_source})")
            else:
                description.append(f"  {i+1}. {text}")
        if len(elements) > 5:
            description.append(f"  ... and {len(elements)-5} more")
    
    return {
        'elements': all_elements,
        'summary': '\n'.join(description)
    }

def get_parsed_content_icon_phi3v(boxes, ocr_bbox, image_source, caption_model_processor, ocr_found_targets=False):
    """Get parsed content for icons using BLIP2 or Phi-3 Vision model.
    
    Args:
        boxes: List of bounding boxes for UI elements
        ocr_bbox: List of OCR bounding boxes to avoid
        image_source: Source image (PIL Image or numpy array)
        caption_model_processor: Dictionary containing model and processor
        ocr_found_targets: Flag indicating if OCR already found relevant targets
        
    Returns:
        List of captions for each box
    """
    # Skip vision captioning if OCR found targets
    if ocr_found_targets:
        logger.info("OCR found relevant targets, skipping vision captioning")
        return [f"UI element {i+1}" for i in range(len(boxes))]
        
    # Also check environment variable for vision captioning - default is False
    if os.environ.get("VISION_CAPTIONING", "").lower() != "true":
        logger.info("Vision captioning is disabled. Set VISION_CAPTIONING=true to enable.")
        return [f"UI element {i+1}" for i in range(len(boxes))]

    if not boxes:
        return []

    # Convert image to numpy if needed
    if isinstance(image_source, Image.Image):
        image_source = np.array(image_source)

    # Get image dimensions
    h, w = image_source.shape[:2]
    logger.info(f"Source image dimensions: {w}x{h}")

    # Filter boxes based on OCR regions if needed
    non_ocr_boxes = boxes

    logger.info(f"Processing {len(non_ocr_boxes)} boxes")

    # Create cropped directory if it doesn't exist
    cropped_dir = "cropped"
    os.makedirs(cropped_dir, exist_ok=True)
    
    # Crop images for each box
    cropped_images = []
    cropped_paths = []
    for i, box in enumerate(non_ocr_boxes):
        try:
            x1, y1, x2, y2 = box
            # Convert to float first to handle both string and float inputs
            x1, y1, x2, y2 = float(x1), float(y1), float(x2), float(y2)
            
            # Scale coordinates if they are normalized
            if max(x1, y1, x2, y2) <= 1.0:
                x1, x2 = int(x1 * w), int(x2 * w)
                y1, y2 = int(y1 * h), int(y2 * h)
            else:
                # Round to integers if they're absolute coordinates
                x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Ensure coordinates are within image bounds
            x1 = max(0, min(x1, w-1))
            x2 = max(0, min(x2, w))
            y1 = max(0, min(y1, h-1))
            y2 = max(0, min(y2, h))
            
            # Ensure we have a valid crop region
            if x2 <= x1 or y2 <= y1:
                logger.warning(f"Invalid crop dimensions after adjustment - box {i}: {x1},{y1},{x2},{y2}")
                continue
                
            logger.info(f"Cropping box {i}: {x1},{y1},{x2},{y2}")
            cropped_image = image_source[y1:y2, x1:x2]
            
            # Ensure we have a valid image with all 3 channels
            if cropped_image.size > 0 and len(cropped_image.shape) == 3 and cropped_image.shape[2] == 3:
                pil_image = Image.fromarray(cropped_image)
                # Ensure minimum size
                if pil_image.size[0] >= 4 and pil_image.size[1] >= 4:
                    # Save cropped image to disk
                    crop_path = os.path.join(cropped_dir, f"crop_{i}.png")
                    pil_image.save(crop_path)
                    logger.info(f"Saved cropped image to {crop_path}")
                    
                    cropped_images.append(pil_image)
                    cropped_paths.append(crop_path)
                    logger.info(f"Successfully cropped image {i} with size {pil_image.size}")
                else:
                    logger.warning(f"Cropped image {i} too small: {pil_image.size}")
            else:
                logger.warning(f"Invalid crop result for box {i}: shape={cropped_image.shape}")
        except Exception as e:
            logger.error(f"Error cropping image for box {i} {box}: {e}")
            continue

    if not cropped_images:
        logger.warning("No valid cropped images to process")
        return []

    logger.info(f"Successfully cropped {len(cropped_images)} valid images")

    # Try to use Ollama with gemma3:12b for captioning
    try:
        # Check for required dependencies
        if not check_and_install_package("ollama"):
            logger.warning("Ollama installation failed, image captioning won't be available")
            return ["UI element"] * len(cropped_images)

        import ollama
        import base64
        from io import BytesIO
        from pathlib import Path

        # Get model name from environment variables or use default
        OLLAMA_MODEL = 'gemma3:12b'# os.getenv('OLLAMA_MODEL', 'gemma3:12b')
        OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

        # Configure ollama client
        ollama.host = OLLAMA_HOST
        
        # Prepare for batch processing
        generated_texts = []
        
        logger.info(f"Using Ollama with model {OLLAMA_MODEL} for UI element captioning")
        print(f"🖼️ Generating captions for {len(cropped_images)} UI elements using {OLLAMA_MODEL}...")
            
        for img_path in cropped_paths:
            try:
                # Read the image file as binary data
                # with open(img_path, 'rb') as img_file:
                #     img_data = img_file.read()
                
                # Convert image to base64 for Ollama
                #img_base64 = base64.b64encode(img_data).decode('utf-8')
                
                try:
                    # Use the correct approach as per Gemma 3 documentation - images at top level
                    response = ollama.generate(
                        model='gemma3:12b',#OLLAMA_MODEL,
                        prompt="What's this? Provide a description without leading or trailing text.",
                        images= [img_path], #[img_base64],  # Pass base64 encoded image data at top level
                        options={"temperature": 0.1}  # Lower temperature for more consistent output
                    )
                    
                    # Extract the caption from the response
                    caption = response['response'].strip()
                    
                    # Clean up the caption
                    # Remove any explanatory text, markdown, etc.
                    caption = re.sub(r'```.*?```', '', caption, flags=re.DOTALL)  # Remove code blocks
                    caption = re.sub(r'\n+', ' ', caption)  # Replace newlines with spaces
                    
                    # Extract the most relevant part if response is too long
                    if len(caption) > 100:
                        # Try to find a concise description
                        lines = caption.split('.')
                        if len(lines) > 1:
                            caption = lines[0].strip()
                    
                    # # Handle cases where the model says it can't see an image
                    # if "no image" in caption.lower() or "cannot see" in caption.lower():
                    #     logger.warning(f"Model reports it cannot see the image: {caption}")
                    #     print(f"⚠️ Model cannot see image {img_path}, trying alternative method...")
                        
                    #     # Try alternative method: pass the image path directly
                    #     try:
                    #         # Use the direct image path approach
                    #         inline_response = ollama.run(
                    #             model=OLLAMA_MODEL,
                    #             prompt=f"Describe this UI element in a few words: {img_path}"
                    #         )
                    #         caption = inline_response.strip()
                    #     except Exception as run_error:
                    #         logger.warning(f"Error with direct path method: {run_error}")
                            
                    #         # Try alternative with the raw API
                    #         try:
                    #             import requests
                    #             response = requests.post(
                    #                 f"{OLLAMA_HOST}/api/generate",
                    #                 json={
                    #                     "model": OLLAMA_MODEL,
                    #                     "prompt": "Describe this UI element in a few words, focusing on its type and function.",
                    #                     "images": [img_base64]
                    #                 }
                    #             )
                    #             if response.status_code == 200:
                    #                 caption = response.json().get('response', '')
                    #             else:
                    #                 logger.warning(f"API error: {response.status_code}, {response.text}")
                    #         except Exception as api_error:
                    #             logger.warning(f"API request error: {api_error}")
                        
                    #     caption = re.sub(r'```.*?```', '', caption, flags=re.DOTALL)
                    #     caption = re.sub(r'\n+', ' ', caption)
                        
                    #     if len(caption) > 100:
                    #         lines = caption.split('.')
                    #         if len(lines) > 1:
                    #             caption = lines[0].strip()
                    
                    # # If still couldn't get a proper caption
                    # if "no image" in caption.lower() or "cannot see" in caption.lower() or not caption:
                    #     caption = f"UI element {Path(img_path).stem}"
                    
                    logger.info(f"Generated caption: {caption}")
                    generated_texts.append(caption)
                    
                    # Use a sanitized version of the caption for the filename
                    safe_caption = re.sub(r'[^\w\s-]', '', caption)[:50].strip()  # Remove special chars and limit length
                    safe_caption = re.sub(r'\s+', '_', safe_caption)  # Replace spaces with underscores
                    
                    if not safe_caption:  # If nothing left after sanitizing
                        safe_caption = f"element_{Path(img_path).stem}"
                    
                    # Save a copy of the image with caption in filename
                    caption_filename = os.path.join(os.path.dirname(img_path), f"{safe_caption}.jpg")
                    shutil.copy2(img_path, caption_filename)
                    logger.info(f"Saved captioned image to {caption_filename}")
                except Exception as ollama_error:
                    logger.warning(f"Error using Ollama for this image: {str(ollama_error)}")
                    caption = f"UI element {Path(img_path).stem}"
                    generated_texts.append(caption)
            except Exception as e:
                logger.error(f"Error generating caption for image {img_path}: {str(e)}")
                generated_texts.append(f"UI element {Path(img_path).stem}")  # Fallback caption with safe filename
        
        logger.info(f"Total generated captions: {len(generated_texts)}")
        return generated_texts

    except Exception as e:
        logger.error(f"Error using Ollama for image captioning: {e}")
        
    # Try BLIP2 as fallback if Ollama fails
    blip2 = get_caption_model_processor()
    if blip2:
        try:
            captions = []
            for image in cropped_images:
                inputs = blip2['processor'](
                    images=image,
                    text="Describe this UI element in a few words, focusing on its type and function.",
                    return_tensors="pt"
                ).to(blip2['model'].device)

                with torch.no_grad():
                    outputs = blip2['model'].generate(
                        **inputs,
                        max_new_tokens=50,
                        do_sample=False
                    )

                caption = blip2['processor'].decode(outputs[0], skip_special_tokens=True)
                captions.append(caption)
            return captions
        except Exception as e:
            logger.error(f"Error using BLIP2: {e}")

    # Final fallback - generic captions
    return ["UI element"] * len(cropped_images)
