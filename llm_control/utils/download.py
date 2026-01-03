import os
import requests
import logging
from tqdm import tqdm
from pathlib import Path

from llm_control import (
    MODEL_CACHE_DIR, YOLO_MODEL_URL, YOLO_MODEL_FALLBACK_URL, 
    YOLO_CACHE_DIR, PHI3_CACHE_DIR, PHI3_FILES,
    ICON_DETECT_MODEL_REPO, ICON_DETECT_MODEL_FILE, ICON_DETECT_MODEL_URL
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

def download_from_huggingface(repo_id, filename, destination, description=None):
    """Download a file from HuggingFace using huggingface_hub"""
    if os.path.exists(destination):
        logger.info(f"File already exists: {destination}")
        return destination
    
    try:
        from huggingface_hub import hf_hub_download
        logger.info(f"Downloading {description or filename} from HuggingFace: {repo_id}")
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=os.path.dirname(destination),
            local_dir_use_symlinks=False
        )
        
        # If downloaded to a subdirectory, move to destination
        if downloaded_path != destination:
            import shutil
            if os.path.exists(destination):
                os.remove(destination)
            shutil.move(downloaded_path, destination)
        
        logger.info(f"Download complete: {destination}")
        return destination
    except ImportError:
        logger.warning("huggingface_hub not available, trying direct URL download...")
        # Fallback to direct URL download
        return download_file(ICON_DETECT_MODEL_URL, destination, description)
    except Exception as e:
        logger.warning(f"Failed to download from HuggingFace: {e}, trying direct URL...")
        # Fallback to direct URL download
        try:
            return download_file(ICON_DETECT_MODEL_URL, destination, description)
        except Exception as url_error:
            logger.error(f"Failed to download from direct URL: {url_error}")
            raise

def download_models_if_needed():
    """Download models if they don't already exist"""
    logger.info("Checking for required models...")
    
    # Create cache directories if they don't exist
    os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
    os.makedirs(YOLO_CACHE_DIR, exist_ok=True)
    os.makedirs(PHI3_CACHE_DIR, exist_ok=True)
    
    # Priority 1: Download OmniParser icon_detect.pt from HuggingFace (specialized UI detector)
    icon_detect_path = os.path.join(YOLO_CACHE_DIR, "icon_detect.pt")
    if not os.path.exists(icon_detect_path):
        logger.info("OmniParser icon_detect model not found. Downloading from HuggingFace...")
        try:
            download_from_huggingface(
                ICON_DETECT_MODEL_REPO,
                ICON_DETECT_MODEL_FILE,
                icon_detect_path,
                "OmniParser icon_detect model"
            )
        except Exception as e:
            logger.warning(f"Failed to download OmniParser model: {e}")
            logger.info("Will use YOLOv8 as fallback")
    else:
        logger.info("OmniParser icon_detect model already exists.")
    
    # Priority 2: Download YOLOv8 model as fallback if icon_detect is not available
    yolo_model_path = os.path.join(YOLO_CACHE_DIR, "yolov8m.pt")
    if not os.path.exists(yolo_model_path):
        logger.info("YOLOv8 model not found. Downloading...")
        try:
            download_file(
                YOLO_MODEL_URL,
                yolo_model_path,
                "YOLOv8 model"
            )
        except Exception as e:
            logger.warning(f"Error downloading from primary URL: {e}. Trying fallback URL...")
            try:
                download_file(
                    YOLO_MODEL_FALLBACK_URL,
                    yolo_model_path,
                    "YOLOv8 model (fallback)"
                )
            except Exception as fallback_error:
                logger.error(f"Failed to download YOLOv8 model: {fallback_error}")
    else:
        logger.info("YOLOv8 model already exists.")
    
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
