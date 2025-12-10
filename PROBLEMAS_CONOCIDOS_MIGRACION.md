# Problemas Conocidos y Soluciones - Migración Python 3.11/3.12

Este documento lista los problemas conocidos durante la migración y sus soluciones.

## 🔴 Problemas Críticos

### 1. PaddlePaddle no compatible con Python 3.12

**Síntoma:**
```
ERROR: Could not find a version that satisfies the requirement paddlepaddle==2.6.1
```

**Causa:**
PaddlePaddle 2.6.1 puede no tener soporte oficial para Python 3.12.

**Soluciones:**

**Opción A: Usar Python 3.11** (Recomendado)
```bash
# Migrar a Python 3.11 en lugar de 3.12
./scripts/migration/migrate_venv.sh 3.11 venv venv-py311 requirements-py311.txt
```

**Opción B: Hacer PaddleOCR opcional**
```python
# En llm_control/ui_detection/ocr.py
try:
    from paddleocr import PaddleOCR
    PADDLE_AVAILABLE = True
except ImportError:
    PADDLE_AVAILABLE = False
    logger.warning("PaddleOCR no disponible, usando solo EasyOCR")
```

**Opción C: Instalar desde fuente alternativa**
```bash
pip install paddlepaddle==2.6.1 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. PyAudio falla en compilación

**Síntoma:**
```
error: command 'gcc' failed with exit status 1
ERROR: Failed building wheel for pyaudio
```

**Causa:**
PyAudio requiere compilación y dependencias del sistema.

**Soluciones:**

**Opción A: Instalar dependencias del sistema** (Recomendado)
```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev python3-pyaudio

# Luego instalar con pip
pip install pyaudio
```

**Opción B: Usar pipwin**
```bash
pip install pipwin
pipwin install pyaudio
```

**Opción C: Usar sounddevice como alternativa**
El proyecto ya incluye `sounddevice` como alternativa. Modificar código para usar `sounddevice` si `pyaudio` no está disponible.

### 3. NumPy 1.26 rompe código existente

**Síntoma:**
```
TypeError: numpy.ndarray size changed, may indicate binary incompatibility
```

**Causa:**
Cambio mayor de versión de NumPy puede causar incompatibilidades binarias.

**Soluciones:**

**Opción A: Actualizar todas las dependencias**
```bash
# Asegurar que todas las dependencias estén actualizadas
pip install --upgrade numpy opencv-python torch torchvision torchaudio
```

**Opción B: Reinstalar dependencias que usan NumPy**
```bash
pip uninstall numpy opencv-python torch torchvision torchaudio
pip install numpy>=1.26.0
pip install opencv-python torch torchvision torchaudio
```

**Opción C: Usar NumPy 1.25 como compromiso** (Solo Python 3.11)
```bash
pip install "numpy>=1.25.0,<1.26.0"
```

## ⚠️ Problemas Menores

### 4. PyTorch requiere reinstalación

**Síntoma:**
```
ImportError: numpy.core.multiarray failed to import
```

**Solución:**
```bash
# Reinstalar PyTorch después de actualizar NumPy
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### 5. OpenCV no encuentra NumPy

**Síntoma:**
```
ImportError: numpy is required for loading cv2
```

**Solución:**
```bash
# Instalar NumPy primero, luego OpenCV
pip install "numpy>=1.26.0"
pip install opencv-python
```

### 6. Transformers requiere versión más reciente

**Síntoma:**
```
ModuleNotFoundError: No module named 'transformers.models'
```

**Solución:**
```bash
pip install --upgrade transformers>=4.40.0
```

### 7. EasyOCR falla con NumPy 1.26

**Síntoma:**
```
RuntimeError: NumPy version mismatch
```

**Solución:**
```bash
# Actualizar EasyOCR
pip install --upgrade easyocr>=1.7.1
```

## 🔧 Problemas de Instalación

### 8. Error al instalar desde requirements.txt

**Síntoma:**
```
ERROR: Could not find a version that satisfies the requirement
```

**Solución:**
Instalar dependencias en orden específico:
```bash
# 1. NumPy primero
pip install "numpy>=1.26.0,<2.0.0"

# 2. OpenCV y Pillow
pip install "opencv-python>=4.9.0" "pillow>=10.3.0"

# 3. PyTorch
pip install torch torchvision torchaudio

# 4. Resto
pip install -r requirements-py311.txt
```

### 9. Problemas con pip/setuptools

**Síntoma:**
```
ERROR: pip's dependency resolver does not currently take into account
```

**Solución:**
```bash
# Actualizar pip y setuptools
pip install --upgrade pip setuptools wheel
```

## 🐛 Problemas de Ejecución

### 10. Error al importar módulos del proyecto

**Síntoma:**
```
ModuleNotFoundError: No module named 'llm_control'
```

**Solución:**
```bash
# Instalar el proyecto en modo desarrollo
pip install -e .

# O agregar al PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 11. Error de CUDA con PyTorch

**Síntoma:**
```
RuntimeError: CUDA error: no kernel image is available
```

**Solución:**
```bash
# Instalar versión CPU de PyTorch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# O instalar versión CUDA correcta para tu GPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 📝 Verificación Post-Migración

Después de resolver problemas, verificar:

```bash
# 1. Verificar imports
python scripts/migration/test_imports.py

# 2. Probar servidor
python -m llm_control voice-server --help

# 3. Probar detección UI
python -c "from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo; print('OK')"
```

## 🔗 Recursos Adicionales

- [Plan de Migración Completo](../PLAN_MIGRACION_PYTHON_3.11_3.12.md)
- [Resumen Ejecutivo](../MIGRACION_RESUMEN.md)
- [Documentación NumPy 1.26](https://numpy.org/devdocs/release/1.26.0-notes.html)
- [PyTorch Installation Guide](https://pytorch.org/get-started/locally/)

## 📞 Reportar Problemas

Si encuentras un problema no listado aquí:
1. Verificar que sigues el plan de migración
2. Revisar logs de error completos
3. Verificar versiones de dependencias
4. Documentar el problema y solución encontrada


