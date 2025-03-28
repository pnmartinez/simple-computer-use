import os
import cv2
import numpy as np
from PIL import Image
import logging

from llm_control import OCR_CACHE_DIR, _easyocr_reader, _paddle_ocr
from llm_control.utils.dependencies import check_and_install_package
from llm_control.utils.gpu_utils import check_gpu_info

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def get_easyocr_reader(gpu=None):
    """Get or initialize EasyOCR reader instance with model caching"""
    global _easyocr_reader
    if _easyocr_reader is None:
        # Check if easyocr is installed
        if not check_and_install_package("easyocr"):
            logger.warning("EasyOCR installation failed")
            return None
            
        try:
            import easyocr
            # Set download directory to our cache
            os.environ["EASYOCR_DOWNLOAD_DIR"] = OCR_CACHE_DIR
            
            # Check GPU availability if not explicitly specified
            if gpu is None:
                gpu_info = check_gpu_info()
                gpu = gpu_info.get("available", False)
                if gpu:
                    logger.info(f"EasyOCR: GPU detected ({gpu_info.get('device_name')})")
                else:
                    logger.info("No GPU detected, using CPU for EasyOCR")
            
            logger.info(f"Initializing EasyOCR (models will be cached in {OCR_CACHE_DIR})")
            _easyocr_reader = easyocr.Reader(['en'], gpu=gpu, model_storage_directory=OCR_CACHE_DIR)
        except ImportError:
            logger.warning("EasyOCR not installed. Install with: pip install easyocr")
            return None
    return _easyocr_reader

def get_paddle_ocr():
    """Get or initialize PaddleOCR instance with model caching"""
    global _paddle_ocr
    if _paddle_ocr is None:
        # Check if paddleocr is installed
        if not check_and_install_package("paddleocr"):
            logger.warning("PaddleOCR installation failed")
            return None
            
        try:
            from paddleocr import PaddleOCR
            logger.info(f"Initializing PaddleOCR (models will be cached in {OCR_CACHE_DIR})")
            # Use our cache directory for model downloads
            _paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, 
                                    model_dir=OCR_CACHE_DIR)
        except ImportError:
            logger.warning("PaddleOCR not installed. Install with: pip install paddleocr")
            return None
    return _paddle_ocr

def detect_text_regions(image_path, min_confidence=0.4):
    """Detect text regions in image using multiple OCR engines for redundancy.
    
    Currently supported OCR engines:
    - EasyOCR (primary engine)
    - PaddleOCR (backup engine, currently disabled)
    
    Args:
        image_path: Path to image file or cv2 image array
        min_confidence: Minimum confidence threshold for detected text (0.0-1.0)
        
    Returns:
        List of dictionaries containing detected text regions with:
        - text: The detected text string
        - confidence: Detection confidence score
        - bbox: Bounding box coordinates [x_min, y_min, x_max, y_max]
        - bbox_type: Format of bbox coordinates ('xyxy')
        - source: Name of OCR engine that detected the text
    """
    results = []
    
    # Convert image path to cv2 format if needed
    if isinstance(image_path, str):
        image = cv2.imread(image_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.open(image_path)
        image_size = pil_image.size
    else:
        # Assume it's already an image
        image = image_path
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        image_size = (image.shape[1], image.shape[0])
    
    # Try EasyOCR first
    reader = get_easyocr_reader()
    if reader:
        try:
            easy_results = reader.readtext(image_rgb)
            for bbox, text, confidence in easy_results:
                if confidence >= min_confidence:
                    x_min = min([p[0] for p in bbox])
                    y_min = min([p[1] for p in bbox])
                    x_max = max([p[0] for p in bbox])
                    y_max = max([p[1] for p in bbox])
                    
                    results.append({
                        'text': text,
                        'confidence': confidence,
                        'bbox': [x_min, y_min, x_max, y_max],
                        'bbox_type': 'xyxy',
                        'source': 'easyocr'
                    })
            logger.debug(f"EasyOCR found {len(results)} text regions")
        except Exception as e:
            logger.warning(f"EasyOCR error: {e}")
    
    # Try PaddleOCR as backup
    # ocr = get_paddle_ocr()
    # if ocr and not results:  # Only use PaddleOCR if EasyOCR failed or found nothing
    #     try:
    #         paddle_results = ocr.ocr(image_path)
            
    #         # Handle both old and new API versions
    #         if isinstance(paddle_results, tuple):
    #             paddle_results = paddle_results[0]
            
    #         for line in paddle_results:
    #             if isinstance(line, list) and len(line) >= 2:
    #                 if isinstance(line[1], tuple) and len(line[1]) >= 2:
    #                     bbox = line[0]
    #                     text, confidence = line[1]
                        
    #                     if confidence >= min_confidence:
    #                         # Convert points to xyxy format
    #                         x_min = min([p[0] for p in bbox])
    #                         y_min = min([p[1] for p in bbox])
    #                         x_max = max([p[0] for p in bbox])
    #                         y_max = max([p[1] for p in bbox])
                            
    #                         results.append({
    #                             'text': text,
    #                             'confidence': confidence,
    #                             'bbox': [x_min, y_min, x_max, y_max],
    #                             'bbox_type': 'xyxy',
    #                             'source': 'paddleocr'
    #                         })
    #         logger.debug(f"PaddleOCR found {len(results)} text regions")
    #     except Exception as e:
    #         logger.warning(f"PaddleOCR error: {e}")
    
    return results
