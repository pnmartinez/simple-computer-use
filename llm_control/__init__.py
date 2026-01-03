import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logger = logging.getLogger("llm-pc-control")

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

# UI Detector Model - Prioritize HuggingFace OmniParser model
# Primary: OmniParser icon_detect.pt from HuggingFace (specialized for UI element detection)
ICON_DETECT_MODEL_REPO = "microsoft/OmniParser-v2.0"
ICON_DETECT_MODEL_FILE = "icon_detect/model.pt"
ICON_DETECT_MODEL_URL = f"https://huggingface.co/{ICON_DETECT_MODEL_REPO}/resolve/main/{ICON_DETECT_MODEL_FILE}"

# Fallback: Standard YOLOv8 model
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

# Global instances of models and resources
_easyocr_reader = None
_paddle_ocr = None
_ui_detector = None
_phi3_vision = None

# Common constants for command processing
KEY_MAPPING = {
    # English keys
    'enter': 'enter', 'return': 'enter',
    'tab': 'tab',
    'esc': 'escape', 'escape': 'escape',
    'space': 'space', 'spacebar': 'space',
    'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
    'backspace': 'backspace', 'delete': 'delete',
    'home': 'home', 'end': 'end',
    'pageup': 'pageup', 'pagedown': 'pagedown',
    'ctrl': 'ctrl', 'control': 'ctrl',
    'alt': 'alt', 'option': 'alt',
    'shift': 'shift',
    'win': 'win', 'command': 'command', 'cmd': 'command',
    
    # Spanish key mappings
    'intro': 'enter', 'entrar': 'enter', 'ingresar': 'enter',
    'tabulador': 'tab', 'tabulación': 'tab',
    'escape': 'escape', 'salir': 'escape',
    'espacio': 'space', 'barra': 'space', 'barra espaciadora': 'space',
    'arriba': 'up', 'subir': 'up',
    'abajo': 'down', 'bajar': 'down',
    'izquierda': 'left',
    'derecha': 'right',
    'retroceso': 'backspace', 'borrar': 'backspace',
    'suprimir': 'delete', 'eliminar': 'delete',
    'inicio': 'home',
    'fin': 'end',
    'página arriba': 'pageup', 'subir página': 'pageup',
    'página abajo': 'pagedown', 'bajar página': 'pagedown',
    'control': 'ctrl',
    'alternativa': 'alt', 'alt': 'alt',
    'mayúscula': 'shift', 'mayúsculas': 'shift', 'shift': 'shift',
    'windows': 'win', 'ventana': 'win', 'cmd': 'command'
}

# Regular expression patterns for command parsing
# Updated to include Spanish verbs
KEY_COMMAND_PATTERN = r'(press|hit|push|stroke|pulsa|presiona|oprime|teclea|presionar|oprimir|teclear)\s+(?:\"([^\"]+)\"|\'([^\']+)\'|(\w+(?:[-+\s]\w+)*))'
TYPING_COMMAND_PATTERNS = ['type ', 'typing ', 'write ', 'enter ', 'escribe ', 'escribir ', 'teclea ', 'teclear ', 'ingresa ', 'ingresar ']
REFERENCE_WORDS = ["it", "that", "this", "lo", "la", "le", "eso", "esto", "éste", "ésta", "aquel", "aquella"]
ACTION_VERBS = [
    # English verbs
    'click', 'type', 'move', 'press', 'hit', 'right', 'double', 'drag', 'scroll', 'wait',
    # Spanish verbs
    'clic', 'hacer clic', 'pulsa', 'presiona', 'escribe', 'escribir', 'teclea', 'teclear', 
    'mover', 'mueve', 'presionar', 'doble', 'doble clic', 'arrastrar', 'arrastra', 
    'desplazar', 'desplazamiento', 'esperar', 'espera'
]
STEP_SEPARATORS = [
    # English separators
    ', then ', ', and ', '; then ', '; and ',  # Complex separators
    ', ', '; ',  # Simple separators
    # Spanish separators
    ', luego ', ', después ', ', y ', '; luego ', '; después ', '; y ',
    ', entonces ', '; entonces '
]

# Command history for tracking context between steps
command_history = {
    'last_ui_element': None,  # Last UI element that was targeted
    'last_coordinates': None,  # Last (x, y) coordinates that were targeted
    'last_command': None,      # Last command that was executed
    'steps': []                # List of all executed steps
}

# Structured logging support
STRUCTURED_USAGE_LOGS = os.environ.get("STRUCTURED_USAGE_LOGS", "false").lower() in {"1", "true", "yes", "on"}
# Alias for easier imports
STRUCTURED_USAGE_LOGS_ENABLED = STRUCTURED_USAGE_LOGS
_structured_logging_configured = False


def is_packaged():
    """
    Detect if running from packaged executable (PyInstaller, AppImage, etc.).
    
    This function provides cross-platform detection of packaged mode:
    - PyInstaller: sets sys.frozen
    - AppImage (Linux): mounts at /tmp/.mount_*
    - Windows executable: has sys._MEIPASS
    - macOS app bundle: executable path contains .app/Contents
    
    Returns:
        bool: True if running from packaged executable, False otherwise
    """
    # PyInstaller sets sys.frozen
    if hasattr(sys, 'frozen') and sys.frozen:
        return True
    
    # AppImage detection (Linux) - mounts at /tmp/.mount_*
    try:
        cwd = os.getcwd()
        if '/.mount_' in cwd:
            return True
    except (OSError, AttributeError):
        pass
    
    # Windows executable detection (PyInstaller)
    if sys.platform == 'win32' and hasattr(sys, '_MEIPASS'):
        return True
    
    # macOS app bundle detection
    if sys.platform == 'darwin':
        try:
            executable_path = os.path.abspath(sys.executable)
            if '.app/Contents' in executable_path:
                return True
        except (OSError, AttributeError):
            pass
    
    return False


class StructuredJSONFormatter(logging.Formatter):
    """Simple JSON formatter used when structured usage logs are enabled."""

    def format(self, record):
        log_record = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        structured_data = getattr(record, "structured_data", None)
        if structured_data:
            log_record["data"] = structured_data

        return json.dumps(log_record, ensure_ascii=False)


def configure_structured_logging(logger_name="llm-pc-control"):
    """Configure JSON logging when structured usage logs are requested."""
    global _structured_logging_configured

    if not STRUCTURED_USAGE_LOGS or _structured_logging_configured:
        return

    target_logger = logging.getLogger(logger_name)
    
    # Determine log file path
    if os.environ.get("STRUCTURED_LOGS_DIR"):
        log_dir = os.environ.get("STRUCTURED_LOGS_DIR")
    else:
        # Use is_packaged() for cross-platform detection
        if is_packaged():
            # Running from packaged executable
            # Use user's home directory for logs
            log_dir = os.path.join(os.path.expanduser("~"), ".llm-control", "structured_logs")
        else:
            # Development mode: use current working directory
            cwd = os.getcwd()
            log_dir = os.path.join(cwd, "structured_logs")
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Create log file with date-based name
    log_filename = f"structured_events_{datetime.now().strftime('%Y%m%d')}.jsonl"
    log_filepath = os.path.join(log_dir, log_filename)

    # Create formatter
    formatter = StructuredJSONFormatter()
    
    # Add stream handler (stdout) if not present
    if not any(isinstance(h, logging.StreamHandler) for h in target_logger.handlers):
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        target_logger.addHandler(stream_handler)
    
    # Add file handler for structured logs
    try:
        file_handler = logging.FileHandler(log_filepath, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)  # Only log INFO and above to file
        target_logger.addHandler(file_handler)
        # Use print to avoid circular logging during configuration
        print(f"Structured logs will be saved to: {log_filepath}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Could not create file handler for structured logs: {e}", file=sys.stderr)

    # Apply formatter to all handlers
    for handler in target_logger.handlers:
        if not handler.formatter:
            handler.setFormatter(formatter)

    target_logger.setLevel(logging.INFO)
    target_logger.propagate = False
    _structured_logging_configured = True


def structured_usage_log(event_type, **fields):
    """Emit a structured usage log entry if instrumentation is enabled."""
    if not STRUCTURED_USAGE_LOGS:
        return

    payload = {"event": event_type, **fields}
    logger.info(event_type, extra={"structured_data": payload})


# Configure logging immediately if the flag is enabled
configure_structured_logging()
