# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for llm-control voice server

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

# Note: Most packages (EasyOCR, Transformers, Ultralytics) download models at runtime
# and store them in user cache directories, so we don't need to include them in the package.
# Only include static assets that are required at import time.

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
    'torchaudio',
    'torchvision',
    'torchvision.transforms',
    'torchvision.models',
    'transformers',
    'transformers.tokenization_utils',
    'transformers.modeling_utils',
    'transformers.configuration_utils',
    'tokenizers',
    # UI detection
    'easyocr',
    'ultralytics',
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
    'scipy',
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
    excludes=['matplotlib'],  # tkinter removed from excludes - needed by mouseinfo (optional but shouldn't cause failure)
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Use onedir instead of onefile to avoid size limits
# This creates a directory with the executable and dependencies
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='llm-control-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name='llm-control-server',
)

