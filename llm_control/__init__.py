import os
import logging

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
