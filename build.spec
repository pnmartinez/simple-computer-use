# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Simple Computer Use Desktop voice server

import sys
import os

# Get the project root directory
block_cipher = None

# Get project root - use current working directory (should be project root when running pyinstaller)
project_root = os.getcwd()

# Collect all data files from llm_control package
datas = []

# Add llm_control package data
llm_control_path = os.path.join(project_root, 'llm_control')
if os.path.exists(llm_control_path):
    datas.append((llm_control_path, 'llm_control'))

# Add Whisper assets (mel_filters.npz, tiktoken files, etc.)
try:
    import whisper
    whisper_path = os.path.dirname(whisper.__file__)
    whisper_assets = os.path.join(whisper_path, 'assets')
    if os.path.exists(whisper_assets):
        datas.append((whisper_assets, 'whisper/assets'))
        print(f"Added Whisper assets from: {whisper_assets}")
    else:
        print(f"Warning: Whisper assets directory not found at: {whisper_assets}")
except ImportError:
    print("Warning: Could not import whisper to find assets directory")
except Exception as e:
    print(f"Warning: Error adding Whisper assets: {e}")

# Note: EasyOCR and Ultralytics are now included in the build for reliable UI element detection.
# Their models are downloaded at runtime and stored in user cache directories (~/.llm-pc-control/models/).
# Only include static assets that are required at import time.

# Exclude cache files and directories
import shutil
def clean_cache_files():
    """Remove __pycache__ directories and .pyc files before building"""
    for root, dirs, files in os.walk(project_root):
        # Remove __pycache__ directories
        if '__pycache__' in dirs:
            cache_dir = os.path.join(root, '__pycache__')
            try:
                shutil.rmtree(cache_dir)
                print(f"Removed cache directory: {cache_dir}")
            except Exception as e:
                print(f"Warning: Could not remove {cache_dir}: {e}")
        # Remove .pyc files
        for file in files:
            if file.endswith('.pyc'):
                pyc_file = os.path.join(root, file)
                try:
                    os.remove(pyc_file)
                    print(f"Removed cache file: {pyc_file}")
                except Exception as e:
                    print(f"Warning: Could not remove {pyc_file}: {e}")

# Clean cache files before building
try:
    clean_cache_files()
except Exception as e:
    print(f"Warning: Error cleaning cache files: {e}")

# Collect hidden imports (modules that PyInstaller might miss)
hiddenimports = [
    # llm_control modules
    'llm_control',
    'llm_control.voice',
    'llm_control.voice.server',
    'llm_control.voice.commands',
    'llm_control.voice.utils',
    'llm_control.voice.audio',
    'llm_control.voice.screenshots',
    'llm_control.llm',
    'llm_control.llm.intent_detection',
    'llm_control.llm.text_extraction',
    'llm_control.llm.simple_executor',
    'llm_control.ui_detection',
    'llm_control.ui_detection.element_finder',
    'llm_control.ui_detection.ocr',
    'llm_control.command_processing',
    'llm_control.command_processing.executor',
    'llm_control.command_processing.finder',
    'llm_control.command_processing.parser',
    'llm_control.command_processing.history',
    'llm_control.favorites',
    'llm_control.favorites.utils',
    'llm_control.utils',
    'llm_control.utils.dependencies',
    'llm_control.utils.download',
    'llm_control.utils.gpu_utils',
    'llm_control.utils.pyautogui_extensions',
    'llm_control.utils.wait',
    # Flask and web server
    'flask',
    'flask_cors',
    'flask_socketio',
    'werkzeug',
    'werkzeug.serving',
    'werkzeug.middleware',
    'werkzeug.security',
    # SocketIO dependencies
    'socketio',
    'engineio',
    'eventlet',
    # Speech recognition
    'whisper',
    # PyTorch and ML
    'torch',
    'torch.nn',
    'torch.optim',
    'torch.cuda',
    'torch.distributed',
    # Note: torchaudio and torchvision are optional dependencies
    # They will be included if installed, but are not required for core functionality
    # 'torchaudio',  # Removed - not used directly
    # 'torchvision',  # Removed - not used directly
    # 'torchvision.transforms',  # Removed - not used directly
    # 'torchvision.models',  # Removed - not used directly
    'transformers',
    'transformers.tokenization_utils',
    'transformers.modeling_utils',
    'transformers.configuration_utils',
    'tokenizers',
    # UI detection
    'easyocr',  # Included in build for reliable UI element detection
    'ultralytics',  # Included in build for YOLO-based UI element detection
    # LLM integration
    'ollama',
    # HuggingFace
    'huggingface_hub',
    'safetensors',
    # GUI automation
    'pyautogui',
    # Note: mouseinfo is optional - it requires tkinter which is a system dependency
    # We include it but handle gracefully if tkinter is not available
    'mouseinfo',
    'tkinter',  # Add tkinter to hiddenimports (will be available if system has python3-tk)
    'Xlib',
    'Xlib.display',
    'Xlib.protocol',
    # Image processing
    'PIL',
    'PIL.Image',
    'cv2',
    'numpy',
    # 'scipy',  # Removed - not used directly
    'sklearn',
    'sklearn.datasets',
    'imagehash',
    'skimage',
    # Audio processing
    'pydub',
    # Utilities
    'requests',
    'psutil',
    'tqdm',
    'cryptography',
    'netifaces',
    'qrcode',
    'dotenv',
    'python_dotenv',
    # Package management
    'pkg_resources',
    'importlib',
    'importlib.util',
    'importlib.metadata',
]

# Entry point - use relative path
entry_point = 'llm_control/__main__.py'

a = Analysis(
    [entry_point],
    pathex=[project_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'tensorflow', 'tensorflow.*', 'tf', 'tf.*'],  # Exclude unused/optional packages: matplotlib (optional), tensorflow (not used)
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Post-process to remove TensorFlow from collected datas
tensorflow_items = []
for item in a.datas:
    if isinstance(item, tuple) and len(item) == 2:
        src, dst = item
        if 'tensorflow' in str(src).lower():
            tensorflow_items.append(item)
for item in tensorflow_items:
    if item in a.datas:
        a.datas.remove(item)
        print(f"Removed TensorFlow data: {item}")

# PYZ compression: PyInstaller uses zlib compression by default
# Note: PyInstaller doesn't support LZMA directly, but UPX compression
# on binaries provides significant size reduction
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use onedir instead of onefile to avoid size limits
# This creates a directory with the executable and dependencies
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='simple-computer-use-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression to reduce binary size
    console=True,  # Keep console for server logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,  # Enable UPX compression to reduce binary size
    upx_exclude=[],  # Exclude specific binaries from UPX if needed
    name='simple-computer-use-server',
)

