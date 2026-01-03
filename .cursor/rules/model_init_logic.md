# Model Initialization Logic

This document summarizes where and how different ML models are loaded in the codebase.

## 1. Whisper (Audio Transcription)
- **Location**: `llm_control/voice/audio.py`
- **Function**: `transcribe_audio()`
- **Key Loading Code**: `model = whisper.load_model(model_size)`
- **Model Size Config**: Environment variable `WHISPER_MODEL_SIZE`
- **Potential Memory Issue**: Model might not be properly released after use

## 2. Ollama (Language Models)
- **Locations**:
  - `llm_control/llm/intent_detection.py` - for extracting target text
  - `llm_control/llm/text_extraction.py` - for extracting text to type
  - `llm_control/voice/audio.py` - for translating text
- **Model Config**: Environment variable `OLLAMA_MODEL` (default: "llama3.1")
- **Loading Method**: Via API calls to Ollama server
- **Potential Memory Issue**: Multiple calls to Ollama without proper session management

## 3. YOLO (Object Detection)
- **Location**: `llm_control/ui_detection/element_finder.py`
- **Function**: `get_ui_detector()`
- **Model File**: `yolov8m.pt` stored in `YOLO_CACHE_DIR`
- **Loading Code**: `_ui_detector = YOLO(yolo_path)`
- **Potential Memory Issue**: Global model instance might persist and consume memory

## 4. EasyOCR (Optical Character Recognition)
- **Location**: `llm_control/ui_detection/ocr.py`
- **Function**: `get_easyocr_reader()`
- **Initialization**: `_easyocr_reader = easyocr.Reader(['en'], gpu=gpu, model_storage_directory=OCR_CACHE_DIR)`
- **Potential Memory Issue**: Global instance without proper unloading

## 5. PHI-3 Vision (Image Analysis)
- **Location**: `llm_control/ui_detection/element_finder.py`
- **Function**: `get_phi3_vision()`
- **Loading Method**: HuggingFace transformers library
- **Storage**: Model files stored in `PHI3_CACHE_DIR`
- **Potential Memory Issue**: Large model loaded into memory without proper cleanup

## 6. BLIP2 (Image Captioning)
- **Location**: `llm_control/ui_detection/element_finder.py`
- **Function**: `get_caption_model_processor()`
- **Loading Method**: HuggingFace transformers library
- **Potential Memory Issue**: Model loaded but not unloaded properly

## Memory Leak Analysis
The memory leak issue likely stems from models not being properly unloaded or released after use. In particular, the PyTorch models (Whisper, YOLO, BLIP2, PHI-3) may not be properly releasing GPU memory when they're no longer needed, causing memory consumption to increase over time with repeated model loadings. 