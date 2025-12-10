#!/usr/bin/env python3
"""
Script para probar imports críticos después de la migración a Python 3.11/3.12
"""

import sys
import importlib

def test_import(module_name, version_attr=None, min_version=None):
    """Test import de un módulo y opcionalmente verificar versión"""
    try:
        module = importlib.import_module(module_name)
        if version_attr:
            version = getattr(module, version_attr, "unknown")
            print(f"✅ {module_name} {version}")
            
            if min_version and version != "unknown":
                # Comparación simple de versiones (mayor o igual)
                try:
                    from packaging import version as pkg_version
                    if pkg_version.parse(version) < pkg_version.parse(min_version):
                        print(f"   ⚠️  Versión {version} es menor que {min_version} recomendada")
                except ImportError:
                    pass  # No se puede verificar versión sin packaging
        else:
            print(f"✅ {module_name}")
        return True
    except ImportError as e:
        print(f"❌ {module_name}: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {module_name}: {e}")
        return False

def main():
    print("=" * 60)
    print(f"Verificando imports en Python {sys.version}")
    print("=" * 60)
    print()
    
    errors = []
    warnings = []
    
    # Core dependencies
    print("📦 Core Dependencies:")
    if not test_import("flask", "__version__", "2.3.3"):
        errors.append("flask")
    if not test_import("flask_cors"):
        errors.append("flask_cors")
    if not test_import("flask_socketio"):
        errors.append("flask_socketio")
    if not test_import("requests", "__version__"):
        errors.append("requests")
    if not test_import("pyautogui", "__version__"):
        errors.append("pyautogui")
    if not test_import("PIL", "__version__"):
        errors.append("PIL (Pillow)")
    if not test_import("cv2", "__version__"):
        errors.append("opencv-python")
    if not test_import("numpy", "__version__", "1.26.0"):
        errors.append("numpy")
    else:
        import numpy as np
        if np.__version__.startswith("1.24") or np.__version__.startswith("1.25"):
            warnings.append("numpy < 1.26 puede tener problemas con Python 3.12")
    
    print()
    
    # Audio dependencies
    print("🎤 Audio Dependencies:")
    pyaudio_ok = test_import("pyaudio")
    sounddevice_ok = test_import("sounddevice", "__version__")
    if not pyaudio_ok and not sounddevice_ok:
        errors.append("pyaudio o sounddevice (al menos uno requerido)")
    elif not pyaudio_ok:
        warnings.append("pyaudio no disponible, usando sounddevice")
    
    print()
    
    # ML/AI dependencies
    print("🤖 ML/AI Dependencies:")
    torch_ok = test_import("torch", "__version__")
    if torch_ok:
        test_import("torchaudio", "__version__")
        test_import("torchvision", "__version__")
    else:
        warnings.append("PyTorch no instalado (opcional para algunas funciones)")
    
    transformers_ok = test_import("transformers", "__version__", "4.40.0")
    if not transformers_ok:
        warnings.append("transformers no instalado")
    
    try:
        import whisper
        print("✅ whisper")
    except ImportError:
        warnings.append("whisper no instalado")
    
    print()
    
    # UI Detection dependencies
    print("👁️  UI Detection Dependencies:")
    test_import("easyocr")
    test_import("ultralytics", "__version__")
    
    # PaddlePaddle (puede ser problemático)
    paddle_ok = test_import("paddle")
    if not paddle_ok:
        warnings.append("PaddlePaddle no instalado (PaddleOCR puede no funcionar)")
    else:
        test_import("paddleocr")
    
    print()
    
    # LLM integration
    print("🧠 LLM Integration:")
    test_import("ollama")
    
    print()
    
    # Project modules
    print("📁 Project Modules:")
    try:
        from llm_control import __version__
        print(f"✅ llm_control")
    except ImportError as e:
        errors.append(f"llm_control: {e}")
        print(f"❌ llm_control: {e}")
    
    try:
        from llm_control.voice import server
        print("✅ llm_control.voice.server")
    except ImportError as e:
        errors.append(f"llm_control.voice.server: {e}")
        print(f"❌ llm_control.voice.server: {e}")
    
    try:
        from llm_control.ui_detection import element_finder
        print("✅ llm_control.ui_detection.element_finder")
    except ImportError as e:
        warnings.append(f"llm_control.ui_detection.element_finder: {e}")
        print(f"⚠️  llm_control.ui_detection.element_finder: {e}")
    
    try:
        from llm_control.command_processing import executor
        print("✅ llm_control.command_processing.executor")
    except ImportError as e:
        errors.append(f"llm_control.command_processing.executor: {e}")
        print(f"❌ llm_control.command_processing.executor: {e}")
    
    print()
    print("=" * 60)
    
    if errors:
        print("❌ ERRORES ENCONTRADOS:")
        for error in errors:
            print(f"  - {error}")
        print()
        return 1
    
    if warnings:
        print("⚠️  ADVERTENCIAS:")
        for warning in warnings:
            print(f"  - {warning}")
        print()
        print("✅ Imports críticos verificados (algunas advertencias)")
        return 0
    
    print("✅ Todos los imports verificados exitosamente")
    return 0

if __name__ == "__main__":
    sys.exit(main())


