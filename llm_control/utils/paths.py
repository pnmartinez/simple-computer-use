"""
Path constants for the LLM Control package.

This module contains paths and directories used throughout the LLM Control package.
"""

import os

# Paths for model caching
MODEL_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".llm-pc-control", "models")
OCR_CACHE_DIR = os.path.join(MODEL_CACHE_DIR, "ocr")
YOLO_CACHE_DIR = os.path.join(MODEL_CACHE_DIR, "yolo")
PHI3_CACHE_DIR = os.path.join(MODEL_CACHE_DIR, "phi3")

# Create cache directories if they don't exist
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
os.makedirs(OCR_CACHE_DIR, exist_ok=True)
os.makedirs(YOLO_CACHE_DIR, exist_ok=True)
os.makedirs(PHI3_CACHE_DIR, exist_ok=True)

# Model URLs for downloading
YOLO_MODEL_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8m.pt"
# Fallback YOLO URL in case the primary URL fails
YOLO_MODEL_FALLBACK_URL = "https://github.com/ultralytics/ultralytics/releases/download/v8.0.0/yolov8m.pt"

# Phi-3 Vision model files
PHI3_BASE_URL = "https://huggingface.co/microsoft/Phi-3-vision-128k-instruct"
PHI3_FILES = {
    "model-00001-of-00002.safetensors": f"{PHI3_BASE_URL}/model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors": f"{PHI3_BASE_URL}/model-00002-of-00002.safetensors",
    "model.safetensors.index.json": f"{PHI3_BASE_URL}/model.safetensors.index.json",
    "config.json": f"{PHI3_BASE_URL}/config.json",
    "tokenizer.json": f"{PHI3_BASE_URL}/tokenizer.json",
    "tokenizer_config.json": f"{PHI3_BASE_URL}/tokenizer_config.json",
    "special_tokens_map.json": f"{PHI3_BASE_URL}/special_tokens_map.json",
    "preprocessor_config.json": f"{PHI3_BASE_URL}/preprocessor_config.json"
} 