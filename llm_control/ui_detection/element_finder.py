import os
import torch
import re
import logging
from PIL import Image
import numpy as np

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

def detect_ui_elements(image_path):
    """Detect UI elements like buttons, input fields, etc."""
    ui_elements = []
    
    # First try dedicated UI detector if available
    detector = get_ui_detector()
    if detector:
        try:
            ui_elements = detect_ui_elements_with_yolo(image_path)
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
    
    # Load image for captioning
    if isinstance(image_path, str):
        image = Image.open(image_path)
    else:
        image = Image.fromarray(image_path)
    
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
    
    # TODO: Phi3 captioning is slooow, commenting out for now

    # Get captions for elements without text
    # elements_without_text = [elem for elem in all_elements if ('text' not in elem or not elem['text']) and elem.get('type') == 'icon']
    # print(f"\n\nelements_without_text: {elements_without_text}\n\n")
    # if elements_without_text:
    #     try:
    #         # Extract bounding boxes
    #         boxes = [elem['bbox'] for elem in elements_without_text]
    #         ocr_boxes = [elem['bbox'] for elem in all_elements if 'text' in elem and elem['text']]
            
    #         # Get captions
    #         captions = get_parsed_content_icon_phi3v(boxes, ocr_boxes, image, None)
            
    #         # Add captions to elements
    #         for elem, caption in zip(elements_without_text, captions):
    #             elem['text'] = caption
    #             elem['caption_source'] = 'blip2'  # or 'phi3' depending on which was used
    #     except Exception as e:
    #         logger.error(f"Error getting captions for elements: {e}")
    #         # Add placeholder captions if captioning fails
    #         for elem in elements_without_text:
    #             elem['text'] = f"{elem.get('type', 'UI')} element"
    #             elem['caption_source'] = 'fallback'
    
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

def get_parsed_content_icon_phi3v(boxes, ocr_bbox, image_source, caption_model_processor):
    """Get parsed content for icons using BLIP2 or Phi-3 Vision model.
    
    Args:
        boxes: List of bounding boxes for UI elements
        ocr_bbox: List of OCR bounding boxes to avoid
        image_source: Source image (PIL Image or numpy array)
        caption_model_processor: Dictionary containing model and processor
        
    Returns:
        List of captions for each box
    """
    if not boxes:
        return []

    # Convert image to numpy if needed
    if isinstance(image_source, Image.Image):
        image_source = np.array(image_source)

    # Get image dimensions
    h, w = image_source.shape[:2]
    logger.info(f"Source image dimensions: {w}x{h}")

    # Filter boxes based on OCR regions if needed
    # if ocr_bbox:
    #     non_ocr_boxes = boxes[len(ocr_bbox):]
    # else:
    non_ocr_boxes = boxes

    logger.info(f"Processing {len(non_ocr_boxes)} boxes")

    # Crop images for each box
    cropped_images = []
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
                    cropped_images.append(pil_image)
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

    # Try to use Phi-3 Vision first
    phi3 = get_phi3_vision()
    if phi3:
        try:
            model = phi3['model']
            processor = phi3['processor']
            device = model.device

            # Prepare chat template prompt
            messages = [{"role": "user", "content": "<|image_1|>\nsuggest a caption for this icon or UI element. You can use the name of the program or a one sentence description of what it represents."}]
            prompt = processor.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            logger.info(f"Using prompt template: {prompt}")

            batch_size = 3 # Process 3 images at a time
            generated_texts = []

            for i in range(0, len(cropped_images), batch_size):
                batch_images = cropped_images[i:i+batch_size]
                logger.info(f"Processing batch {i//batch_size + 1} with {len(batch_images)} images")
                
                # Process images first
                image_inputs = []
                for img in batch_images:
                    try:
                        processed = processor.image_processor(img, return_tensors="pt")
                        image_inputs.append(processed)
                        logger.info(f"Processed image shape: {processed['pixel_values'].shape}")
                    except Exception as e:
                        logger.error(f"Error processing image: {e}")
                        continue

                if not image_inputs:
                    logger.warning("No valid processed images in batch")
                    continue

                # Prepare inputs dictionary
                inputs = {'input_ids': [], 'attention_mask': [], 'pixel_values': [], 'image_sizes': []}
                texts = [prompt] * len(image_inputs)
                
                # Process each image in batch
                for j, (img_input, txt) in enumerate(zip(image_inputs, texts)):
                    try:
                        input = processor._convert_images_texts_to_inputs(img_input, txt, return_tensors="pt")
                        inputs['input_ids'].append(input['input_ids'])
                        inputs['attention_mask'].append(input['attention_mask'])
                        inputs['pixel_values'].append(input['pixel_values'])
                        inputs['image_sizes'].append(input['image_sizes'])
                    except Exception as e:
                        logger.error(f"Error converting inputs for image {j}: {e}")
                        continue

                if not inputs['input_ids']:
                    logger.warning("No valid inputs after processing")
                    continue

                # Pad sequences to max length
                max_len = max([x.shape[1] for x in inputs['input_ids']])
                for j, v in enumerate(inputs['input_ids']):
                    pad_length = max_len - v.shape[1]
                    if pad_length > 0:
                        inputs['input_ids'][j] = torch.cat([
                            processor.tokenizer.pad_token_id * torch.ones(1, pad_length, dtype=torch.long),
                            v
                        ], dim=1)
                        inputs['attention_mask'][j] = torch.cat([
                            torch.zeros(1, pad_length, dtype=torch.long),
                            inputs['attention_mask'][j]
                        ], dim=1)

                # Concatenate and move to device
                try:
                    inputs_cat = {k: torch.cat(v).to(device) for k, v in inputs.items()}
                    logger.info(f"Input shapes - ids: {inputs_cat['input_ids'].shape}, "
                              f"mask: {inputs_cat['attention_mask'].shape}, "
                              f"pixels: {inputs_cat['pixel_values'].shape}")

                    # Generate captions
                    generation_args = {
                        "max_new_tokens": 25,
                        "temperature": 0.01,
                        "do_sample": False,
                    }
                    
                    generate_ids = model.generate(
                        **inputs_cat,
                        eos_token_id=processor.tokenizer.eos_token_id,
                        **generation_args
                    )
                    logger.info(f"Generated ids shape: {generate_ids.shape}")

                    # Remove input tokens and decode
                    generate_ids = generate_ids[:, inputs_cat['input_ids'].shape[1]:]
                    response = processor.batch_decode(
                        generate_ids,
                        skip_special_tokens=True,
                        clean_up_tokenization_spaces=False
                    )
                    response = [res.strip('\n').strip() for res in response]
                    logger.info(f"Batch responses: {response}")
                    generated_texts.extend(response)

                except Exception as e:
                    logger.error(f"Error in generation step: {e}")
                    continue

            logger.info(f"Total generated texts: {len(generated_texts)}")
            return generated_texts

        except Exception as e:
            logger.error(f"Error using Phi-3 Vision: {e}")

    # Fallback to BLIP2 if Phi-3 fails
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
