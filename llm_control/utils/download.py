import os
import requests
import logging
from tqdm import tqdm
from pathlib import Path

from llm_control import (
    MODEL_CACHE_DIR, YOLO_MODEL_URL, YOLO_MODEL_FALLBACK_URL, 
    YOLO_CACHE_DIR, PHI3_CACHE_DIR, PHI3_FILES
)

# Get the package logger
logger = logging.getLogger("llm-pc-control")

def download_file(url, destination, description=None):
    """Download a file with progress bar"""
    if os.path.exists(destination):
        logger.info(f"File already exists: {destination}")
        return destination
    
    logger.info(f"Downloading {description or url} to {destination}")
    
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 Kibibyte
    
    desc = description or os.path.basename(destination)
    with tqdm(total=total_size, unit='iB', unit_scale=True, desc=desc) as progress_bar:
        with open(destination, 'wb') as file:
            for data in response.iter_content(block_size):
                progress_bar.update(len(data))
                file.write(data)
    
    logger.info(f"Download complete: {destination}")
    return destination

def download_models_if_needed():
    """Download models if they don't already exist"""
    logger.info("Checking for required models...")
    
    # Create cache directories if they don't exist
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    os.makedirs(YOLO_CACHE_DIR, exist_ok=True)
    os.makedirs(PHI3_CACHE_DIR, exist_ok=True)
    
    # Download YOLO model if needed
    yolo_model_path = os.path.join(YOLO_CACHE_DIR, "yolov8m.pt")
    if not os.path.exists(yolo_model_path):
        logger.info("YOLO model not found. Downloading...")
        try:
            download_file(
                YOLO_MODEL_URL,
                yolo_model_path,
                "YOLO v8 model"
            )
        except Exception as e:
            logger.warning(f"Error downloading from primary URL: {e}. Trying fallback URL...")
            download_file(
                YOLO_MODEL_FALLBACK_URL,
                yolo_model_path,
                "YOLO v8 model (fallback)"
            )
    else:
        logger.info("YOLO model already exists.")
    
    # Download Phi-3 Vision model files if needed
    missing_phi3_files = False
    for filename, url in PHI3_FILES.items():
        file_path = os.path.join(PHI3_CACHE_DIR, filename)
        if not os.path.exists(file_path):
            missing_phi3_files = True
            break
    
    if missing_phi3_files:
        logger.info("Phi-3 Vision model files not found. Downloading...")
        for filename, url in PHI3_FILES.items():
            file_path = os.path.join(PHI3_CACHE_DIR, filename)
            try:
                download_file(
                    url,
                    file_path,
                    f"Phi-3 Vision: {filename}"
                )
            except Exception as e:
                logger.error(f"Error downloading {filename}: {e}")
    else:
        logger.info("Phi-3 Vision model files already exist.")
    
    logger.info("Model check complete.")
