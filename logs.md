for server to start...
Server starting...
Structured logs will be saved to: /home/nava/.llm-control/structured_logs/structured_events_20260101.jsonl
2026-01-01 19:57:33,781 - voice-control-audio - INFO - Initializing Whisper model with size: large
2026-01-01 19:57:41,477 - voice-control-audio - INFO - Whisper model initialized in 7.70 seconds
2026-01-01 19:57:41,477 - voice-control-audio - INFO - CUDA is available. Using device: NVIDIA GeForce RTX 4070 Ti SUPER
{"timestamp": "2026-01-01 19:57:41,648", "level": "ERROR", "logger": "llm-pc-control", "message": "Error adding PyAutoGUI extensions: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'"}
{"timestamp": "2026-01-01 19:57:41,648", "level": "WARNING", "logger": "llm-pc-control", "message": "Failed to add PyAutoGUI extensions. Some commands may not work properly."}
{"timestamp": "2026-01-01 19:57:41,651", "level": "ERROR", "logger": "llm-pc-control", "message": "Error adding PyAutoGUI extensions: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'"}
{"timestamp": "2026-01-01 19:57:41,831", "level": "ERROR", "logger": "llm-pc-control", "message": "Error adding PyAutoGUI extensions: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'"}
{"timestamp": "2026-01-01 19:57:41,835", "level": "INFO", "logger": "llm-pc-control", "message": "Using self-signed certificate for HTTPS"}
📦 Package 'ultralytics' not found. Installing...
✅ Successfully installed ultralytics
{"timestamp": "2026-01-01 19:57:42,379", "level": "WARNING", "logger": "llm-pc-control", "message": "Error loading UI detector: No module named 'matplotlib'"}
2026-01-01 19:57:42,379 - voice-control-server - WARNING - UI detector initialization failed
{"timestamp": "2026-01-01 19:57:42,382", "level": "ERROR", "logger": "llm-pc-control", "message": "Error adding PyAutoGUI extensions: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'"}
2026-01-01 19:57:42,382 - voice-control-utils - INFO - Testing CUDA availability...
2026-01-01 19:57:42,382 - voice-control-utils - INFO - PyTorch version: 2.2.0+cu121
2026-01-01 19:57:42,382 - voice-control-utils - INFO - CUDA available: True
2026-01-01 19:57:42,382 - voice-control-utils - INFO - CUDA version: 12.1
2026-01-01 19:57:42,382 - voice-control-utils - INFO - CUDA device count: 1
2026-01-01 19:57:42,382 - voice-control-utils - INFO - Current CUDA device: 0
2026-01-01 19:57:42,382 - voice-control-utils - INFO - CUDA device properties:
2026-01-01 19:57:42,382 - voice-control-utils - INFO -   Device 0: _CudaDeviceProperties(name='NVIDIA GeForce RTX 4070 Ti SUPER', major=8, minor=9, total_memory=15934MB, multi_processor_count=66)
2026-01-01 19:57:42,382 - voice-control-server - INFO - Pre-initializing Whisper model...
2026-01-01 19:57:42,383 - voice-control-server - INFO - Running background screenshot cleanup with max_age_days=1, max_count=10

========================================
🎤 Voice Control Server v1.0 starting...
🌐 Listening on: https://0.0.0.0:5000
🔧 Debug mode: OFF
🗣️ Default language: es
🤖 Using Whisper model: large
🦙 Using Ollama model: llama3.1
📸 Screenshot directory: /home/nava/.llm-control/screenshots
📸 Screenshot max age (days): 1
📸 Screenshot max count: 10
📜 Command history file: /home/nava/.llm-control/history/command_history.csv
⚠️ PyAutoGUI failsafe: DISABLED
🖼️ Vision captioning: DISABLED
🎮 GPU: Available - NVIDIA GeForce RTX 4070 Ti SUPER
========================================

2026-01-01 19:57:42,383 - voice-control-server - INFO - Screenshot settings - Directory: /home/nava/.llm-control/screenshots, Max age: 1 days, Max count: 10
✓ Server fully started and ready
2026-01-01 19:57:42,383 - voice-control-utils - INFO - Cleaning up old screenshots (max_age_days=1, max_count=10)
2026-01-01 19:57:42,383 - voice-control-utils - INFO - No screenshots found to clean up
2026-01-01 19:57:42,383 - voice-control-server - INFO - Background cleanup completed: 0 old screenshots removed
2026-01-01 19:57:42,383 - voice-control-server - INFO - Total screenshots after background cleanup: 0
 * Serving Flask app 'llm_control.voice.server'
 * Debug mode: off
2026-01-01 19:57:42,464 - werkzeug - INFO - [31m[1mWARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.[0m
 * Running on all addresses (0.0.0.0)
 * Running on https://127.0.0.1:5000
 * Running on https://192.168.1.177:5000
2026-01-01 19:57:42,464 - werkzeug - INFO - [33mPress CTRL+C to quit[0m
2026-01-01 19:57:50,774 - werkzeug - INFO - 127.0.0.1 - - [01/Jan/2026 19:57:50] "GET /health HTTP/1.1" 200 -
2026-01-01 19:58:10,769 - werkzeug - INFO - 127.0.0.1 - - [01/Jan/2026 19:58:10] "GET /health HTTP/1.1" 200 -
2026-01-01 19:58:30,769 - werkzeug - INFO - 127.0.0.1 - - [01/Jan/2026 19:58:30] "GET /health HTTP/1.1" 200 -
2026-01-01 19:58:50,768 - werkzeug - INFO - 127.0.0.1 - - [01/Jan/2026 19:58:50] "GET /health HTTP/1.1" 200 -
2026-01-01 19:59:10,769 - werkzeug - INFO - 127.0.0.1 - - [01/Jan/2026 19:59:10] "GET /health HTTP/1.1" 200 -
2026-01-01 19:59:12,948 - voice-control-screenshots - ERROR - Error capturing screenshot: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'
2026-01-01 19:59:12,949 - voice-control-screenshots - ERROR - Traceback (most recent call last):
  File "Xlib/xauth.py", line 43, in __init__
FileNotFoundError: [Errno 2] No such file or directory: '/home/nava/.Xauthority'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "llm_control/voice/screenshots.py", line 33, in capture_screenshot
    import pyautogui
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "PyInstaller/loader/pyimod02_importers.py", line 457, in exec_module
  File "pyautogui/__init__.py", line 246, in <module>
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "PyInstaller/loader/pyimod02_importers.py", line 457, in exec_module
  File "mouseinfo/__init__.py", line 223, in <module>
  File "Xlib/display.py", line 80, in __init__
  File "Xlib/display.py", line 62, in __init__
  File "Xlib/protocol/display.py", line 60, in __init__
  File "Xlib/support/connect.py", line 91, in get_auth
  File "Xlib/support/unix_connect.py", line 103, in new_get_auth
  File "Xlib/xauth.py", line 45, in __init__
Xlib.error.XauthError: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'

2026-01-01 19:59:12,949 - werkzeug - INFO - 100.87.170.116 - - [01/Jan/2026 19:59:12] "[35m[1mPOST /screenshot/capture?format=json HTTP/1.1[0m" 500 -
2026-01-01 19:59:14,120 - voice-control-screenshots - ERROR - Error capturing screenshot: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'
2026-01-01 19:59:14,121 - voice-control-screenshots - ERROR - Traceback (most recent call last):
  File "Xlib/xauth.py", line 43, in __init__
FileNotFoundError: [Errno 2] No such file or directory: '/home/nava/.Xauthority'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "llm_control/voice/screenshots.py", line 33, in capture_screenshot
    import pyautogui
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "PyInstaller/loader/pyimod02_importers.py", line 457, in exec_module
  File "pyautogui/__init__.py", line 246, in <module>
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "PyInstaller/loader/pyimod02_importers.py", line 457, in exec_module
  File "mouseinfo/__init__.py", line 223, in <module>
  File "Xlib/display.py", line 80, in __init__
  File "Xlib/display.py", line 62, in __init__
  File "Xlib/protocol/display.py", line 60, in __init__
  File "Xlib/support/connect.py", line 91, in get_auth
  File "Xlib/support/unix_connect.py", line 103, in new_get_auth
  File "Xlib/xauth.py", line 45, in __init__
Xlib.error.XauthError: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'

2026-01-01 19:59:14,121 - werkzeug - INFO - 100.87.170.116 - - [01/Jan/2026 19:59:14] "[35m[1mPOST /screenshot/capture?format=json HTTP/1.1[0m" 500 -
2026-01-01 19:59:21,968 - voice-control-server - INFO - Received voice-command request
2026-01-01 19:59:22,026 - voice-control-server - INFO - Processing voice command with language: es, model: large
2026-01-01 19:59:22,150 - voice-control-audio - ERROR - Error transcribing audio: [Errno 2] No such file or directory: '/tmp/.mount_LLM Coj1Jx6A/resources/python-backend/llm-control-server/_internal/whisper/assets/mel_filters.npz'
2026-01-01 19:59:22,150 - voice-control-audio - ERROR - Traceback (most recent call last):
  File "llm_control/voice/audio.py", line 130, in transcribe_audio
    result = model.transcribe(
             ^^^^^^^^^^^^^^^^^
  File "whisper/transcribe.py", line 133, in transcribe
  File "whisper/audio.py", line 151, in log_mel_spectrogram
  File "whisper/audio.py", line 106, in mel_filters
  File "numpy/lib/npyio.py", line 427, in load
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/.mount_LLM Coj1Jx6A/resources/python-backend/llm-control-server/_internal/whisper/assets/mel_filters.npz'

2026-01-01 19:59:22,150 - voice-control-server - ERROR - Transcription error: Error transcribing audio: [Errno 2] No such file or directory: '/tmp/.mount_LLM Coj1Jx6A/resources/python-backend/llm-control-server/_internal/whisper/assets/mel_filters.npz'
2026-01-01 19:59:22,151 - werkzeug - INFO - 100.87.170.116 - - [01/Jan/2026 19:59:22] "[35m[1mPOST /voice-command HTTP/1.1[0m" 500 -
2026-01-01 19:59:22,597 - voice-control-screenshots - ERROR - Error capturing screenshot: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'
2026-01-01 19:59:22,598 - voice-control-screenshots - ERROR - Traceback (most recent call last):
  File "Xlib/xauth.py", line 43, in __init__
FileNotFoundError: [Errno 2] No such file or directory: '/home/nava/.Xauthority'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "llm_control/voice/screenshots.py", line 33, in capture_screenshot
    import pyautogui
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "PyInstaller/loader/pyimod02_importers.py", line 457, in exec_module
  File "pyautogui/__init__.py", line 246, in <module>
  File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
  File "PyInstaller/loader/pyimod02_importers.py", line 457, in exec_module
  File "mouseinfo/__init__.py", line 223, in <module>
  File "Xlib/display.py", line 80, in __init__
  File "Xlib/display.py", line 62, in __init__
  File "Xlib/protocol/display.py", line 60, in __init__
  File "Xlib/support/connect.py", line 91, in get_auth
  File "Xlib/support/unix_connect.py", line 103, in new_get_auth
  File "Xlib/xauth.py", line 45, in __init__
Xlib.error.XauthError: ~/.Xauthority: [Errno 2] No such file or directory: '/home/nava/.Xauthority'

2026-01-01 19:59:22,599 - werkzeug - INFO - 100.87.170.116 - - [01/Jan/2026 19:59:22] "[35m[1mPOST /screenshot/capture?format=json HTTP/1.1[0m" 500 -
Server stopped with code null
Server stopped