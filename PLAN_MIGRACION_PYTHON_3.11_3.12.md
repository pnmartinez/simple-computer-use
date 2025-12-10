# Plan de Migración a Python 3.11/3.12

## 📋 Resumen Ejecutivo

Este documento detalla el plan para migrar el proyecto **LLM PC Control** de Python 3.8+ a Python 3.11 o 3.12, asegurando la compatibilidad de todas las dependencias.

**Versión objetivo recomendada: Python 3.11** (mayor estabilidad y compatibilidad con dependencias actuales)
**Versión alternativa: Python 3.12** (mejores rendimientos, pero requiere más actualizaciones)

---

## 🔍 Análisis de Compatibilidad de Dependencias

### ✅ Dependencias Compatibles (Sin Cambios Necesarios)

| Dependencia | Versión Actual | Estado Python 3.11 | Estado Python 3.12 | Notas |
|------------|----------------|-------------------|-------------------|-------|
| `flask` | 2.3.3 | ✅ Compatible | ✅ Compatible | Actualizar a 3.0.x recomendado |
| `flask-cors` | 6.0.0 | ✅ Compatible | ✅ Compatible | - |
| `flask-socketio` | 5.3.4 | ✅ Compatible | ✅ Compatible | - |
| `requests` | 2.32.4 | ✅ Compatible | ✅ Compatible | - |
| `PyAutoGUI` | 0.9.54 | ✅ Compatible | ✅ Compatible | - |
| `sounddevice` | 0.4.6 | ✅ Compatible | ✅ Compatible | - |
| `soundfile` | 0.12.1 | ✅ Compatible | ✅ Compatible | - |
| `pillow` | 10.3.0 | ✅ Compatible | ✅ Compatible | - |
| `pydub` | 0.25.1 | ✅ Compatible | ✅ Compatible | - |
| `python-dotenv` | 1.0.0 | ✅ Compatible | ✅ Compatible | - |
| `imagehash` | 4.3.1 | ✅ Compatible | ✅ Compatible | - |
| `scikit-image` | 0.20.0 | ✅ Compatible | ✅ Compatible | - |
| `ultralytics` | 8.0.196 | ✅ Compatible | ✅ Compatible | - |
| `huggingface_hub` | >=0.16.4,<1.0 | ✅ Compatible | ✅ Compatible | - |
| `safetensors` | 0.3.3 | ✅ Compatible | ✅ Compatible | - |
| `ollama` | 0.1.6 | ✅ Compatible | ✅ Compatible | - |
| `autopep8` | 2.0.4 | ✅ Compatible | ✅ Compatible | - |
| `matplotlib` | >=3.5.0 | ✅ Compatible | ✅ Compatible | - |
| `tqdm` | >=4.65.0 | ✅ Compatible | ✅ Compatible | - |
| `cryptography` | >=42.0.0 | ✅ Compatible | ✅ Compatible | - |
| `netifaces` | >=0.11.0 | ✅ Compatible | ✅ Compatible | - |
| `python-socketio` | >=5.0.0 | ✅ Compatible | ✅ Compatible | - |
| `eventlet` | >=0.33.0 | ✅ Compatible | ✅ Compatible | - |
| `qrcode[pil]` | >=7.4.2 | ✅ Compatible | ✅ Compatible | - |
| `ipaddress` | >=1.0.23 | ✅ Compatible | ✅ Compatible | - |
| `psutil` | >=5.9.0 | ✅ Compatible | ✅ Compatible | - |

### ⚠️ Dependencias que Requieren Actualización

| Dependencia | Versión Actual | Versión Recomendada 3.11 | Versión Recomendada 3.12 | Razón |
|------------|----------------|-------------------------|-------------------------|-------|
| `numpy` | 1.24.3 | 1.26.4 | 1.26.4+ | Python 3.12 requiere numpy >= 1.26.0 |
| `opencv-python` | 4.8.1.78 | 4.9.0.80 | 4.9.0.80+ | Mejor compatibilidad con numpy 1.26+ |
| `torch` | 2.6.0 | 2.6.0+ | 2.6.0+ | Verificar compatibilidad con numpy 1.26 |
| `torchaudio` | 2.6.0 | 2.6.0+ | 2.6.0+ | - |
| `torchvision` | 0.21.0 | 0.21.0+ | 0.21.0+ | - |
| `transformers` | >=4.34.0 | >=4.40.0 | >=4.40.0 | Mejor soporte para Python 3.12 |
| `openai-whisper` | (sin versión) | latest | latest | Verificar compatibilidad |
| `easyocr` | 1.7.1 | 1.7.1+ | 1.7.1+ | Verificar con numpy 1.26 |
| `paddleocr` | 2.6.0.1 | 2.6.0.1+ | 2.6.0.1+ | Verificar compatibilidad |
| `paddlepaddle` | 2.6.1 | 2.6.1+ | 2.6.1+ | **CRÍTICO**: Verificar compatibilidad |

### 🔴 Dependencias Problemáticas (Requieren Atención Especial)

#### 1. `pyaudio` (0.2.13)
**Problema**: Puede tener problemas de compilación en Python 3.11/3.12
**Solución**:
- Opción A: Usar `pipwin` o instalar desde wheel precompilado
- Opción B: Considerar `sounddevice` como alternativa (ya está en el proyecto)
- Opción C: Usar `pyaudio` desde conda-forge si es posible

**Recomendación**: Mantener versión actual, pero preparar fallback a `sounddevice`

#### 2. `paddlepaddle` (2.6.1)
**Problema**: Puede tener problemas de compatibilidad con Python 3.12
**Solución**:
- Verificar documentación oficial de PaddlePaddle
- Considerar usar solo en Python 3.11 si hay problemas
- Alternativa: Usar solo EasyOCR si PaddleOCR falla

**Recomendación**: Probar primero en Python 3.11, luego en 3.12

#### 3. `numpy` (1.24.3 → 1.26.4)
**Problema**: Cambio mayor de versión puede romper compatibilidad
**Solución**:
- Actualizar gradualmente
- Probar todas las funcionalidades que usan numpy
- Verificar que torch, opencv, etc. funcionen con numpy 1.26

---

## 📝 Plan de Migración Paso a Paso

### Fase 1: Preparación y Análisis (1-2 días)

#### 1.1 Crear rama de migración
```bash
git checkout -b migration/python-3.11
```

#### 1.2 Documentar estado actual
```bash
# Generar lista completa de dependencias instaladas
pip freeze > requirements-current.txt

# Verificar versión actual de Python
python --version

# Verificar compatibilidad básica
python -c "import sys; print(f'Python {sys.version}')"
```

#### 1.3 Crear entorno de prueba
```bash
# Instalar Python 3.11 (o 3.12)
# En Ubuntu/Debian:
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Crear entorno virtual de prueba
python3.11 -m venv venv-test-3.11
source venv-test-3.11/bin/activate
```

### Fase 2: Actualización de Dependencias (2-3 días)

#### 2.1 Crear requirements.txt actualizado

**Archivo: `requirements-py311.txt`** (nuevo archivo para Python 3.11)

```txt
# Core dependencies
flask>=2.3.3,<4.0.0
flask-cors>=6.0.0
flask-socketio>=5.3.4
requests>=2.32.4
pyaudio>=0.2.13
PyAutoGUI>=0.9.54
sounddevice>=0.4.6
soundfile>=0.12.1
numpy>=1.26.0,<2.0.0  # Actualizado para Python 3.11/3.12
pillow>=10.3.0
pydub>=0.25.1
python-dotenv>=1.0.0
opencv-python>=4.9.0.80  # Actualizado para mejor compatibilidad

# Speech recognition dependencies
openai-whisper>=20231117
transformers>=4.40.0
torch>=2.6.0
torchaudio>=2.6.0
torchvision>=0.21.0

# UI detection dependencies
easyocr>=1.7.1
imagehash>=4.3.1
scikit-image>=0.20.0
paddleocr>=2.6.0.1
paddlepaddle>=2.6.1
ultralytics>=8.0.196
huggingface_hub>=0.16.4,<1.0
safetensors>=0.3.3

# LLM integration
ollama>=0.1.6

# Additional utilities
autopep8>=2.0.4
matplotlib>=3.5.0
tqdm>=4.65.0
cryptography>=42.0.0
netifaces>=0.11.0
python-socketio>=5.0.0
eventlet>=0.33.0
qrcode[pil]>=7.4.2
ipaddress>=1.0.23
psutil>=5.9.0
```

#### 2.2 Instalar dependencias en orden

```bash
# 1. Actualizar pip y herramientas base
pip install --upgrade pip setuptools wheel

# 2. Instalar numpy primero (dependencia crítica)
pip install "numpy>=1.26.0,<2.0.0"

# 3. Instalar PyTorch (verificar compatibilidad con numpy)
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu118

# 4. Instalar dependencias de visión
pip install opencv-python>=4.9.0.80 pillow>=10.3.0

# 5. Instalar dependencias de audio (pyaudio puede fallar)
pip install pyaudio || echo "PyAudio falló, usar sounddevice como alternativa"

# 6. Instalar dependencias de ML/AI
pip install transformers>=4.40.0 openai-whisper

# 7. Instalar dependencias de UI detection
pip install easyocr ultralytics

# 8. Instalar PaddlePaddle (puede ser problemático)
pip install paddlepaddle>=2.6.1 paddleocr>=2.6.0.1 || echo "PaddlePaddle puede requerir instalación especial"

# 9. Instalar dependencias restantes
pip install -r requirements-py311.txt
```

#### 2.3 Manejar dependencias problemáticas

**Para pyaudio:**
```bash
# Opción 1: Instalar desde wheel precompilado
pip install pipwin
pipwin install pyaudio

# Opción 2: Instalar dependencias del sistema primero
sudo apt-get install portaudio19-dev python3-pyaudio

# Opción 3: Usar sounddevice (ya está en el proyecto)
# Modificar código para usar sounddevice si pyaudio falla
```

**Para paddlepaddle:**
```bash
# Verificar versión compatible
python -c "import sys; print(sys.version)"

# Instalar según documentación oficial
# https://www.paddlepaddle.org.cn/install/quick?docurl=/documentation/docs/zh/install/pip/linux-pip.html
pip install paddlepaddle-gpu==2.6.1 -i https://pypi.tuna.tsinghua.edu.cn/simple
# O versión CPU:
pip install paddlepaddle==2.6.1 -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Fase 3: Actualización de Código (1-2 días)

#### 3.1 Actualizar archivos de configuración

**setup.py:**
```python
python_requires=">=3.11,<3.13"  # Cambiar de >=3.8
```

**README.md:**
- Actualizar requisitos: "Python 3.11 or higher"
- Actualizar ejemplos de instalación

**Dockerfile:**
```dockerfile
# Cambiar de python3 a python3.11
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-pip python3.11-venv python3.11-dev \
    ...
```

#### 3.2 Verificar código para deprecaciones

**Cambios en Python 3.11/3.12:**
- `collections.abc` en lugar de `collections` (si se usa)
- `typing` mejorado (opcional, pero recomendado)
- Verificar uso de `asyncio` (mejoras en 3.11)

**Buscar en el código:**
```bash
# Buscar posibles problemas
grep -r "collections\." llm_control/
grep -r "from collections import" llm_control/
grep -r "import asyncio" llm_control/
```

#### 3.3 Actualizar scripts de inicio

Verificar que todos los scripts usen `python3.11` o `python3` según corresponda.

### Fase 4: Pruebas (2-3 días)

#### 4.1 Pruebas básicas de importación

```bash
# Script de verificación
python3.11 -c "
import sys
print(f'Python version: {sys.version}')

# Test imports críticos
try:
    import torch
    print(f'✅ PyTorch {torch.__version__}')
except ImportError as e:
    print(f'❌ PyTorch: {e}')

try:
    import numpy as np
    print(f'✅ NumPy {np.__version__}')
except ImportError as e:
    print(f'❌ NumPy: {e}')

try:
    import cv2
    print(f'✅ OpenCV {cv2.__version__}')
except ImportError as e:
    print(f'❌ OpenCV: {e}')

try:
    import flask
    print(f'✅ Flask {flask.__version__}')
except ImportError as e:
    print(f'❌ Flask: {e}')

try:
    import pyautogui
    print(f'✅ PyAutoGUI {pyautogui.__version__}')
except ImportError as e:
    print(f'❌ PyAutoGUI: {e}')

try:
    import whisper
    print(f'✅ Whisper installed')
except ImportError as e:
    print(f'❌ Whisper: {e}')

try:
    import paddle
    print(f'✅ PaddlePaddle {paddle.__version__}')
except ImportError as e:
    print(f'❌ PaddlePaddle: {e}')
"
```

#### 4.2 Pruebas funcionales

```bash
# 1. Probar servidor de voz
python3.11 -m llm_control voice-server --help

# 2. Probar detección de UI
python3.11 -c "from llm_control.ui_detection.element_finder import detect_ui_elements_with_yolo; print('UI detection OK')"

# 3. Probar procesamiento de comandos
python3.11 -c "from llm_control.command_processing.executor import process_single_step; print('Command processing OK')"

# 4. Probar captura de pantalla
python3.11 -c "from llm_control.voice.screenshots import capture_screenshot; print('Screenshots OK')"
```

#### 4.3 Pruebas de integración

- Probar comando de voz completo
- Probar detección de UI con YOLO
- Probar OCR (EasyOCR y PaddleOCR)
- Probar transcripción con Whisper
- Probar ejecución de comandos PyAutoGUI

### Fase 5: Actualización de Docker (1 día)

#### 5.1 Actualizar Dockerfile

```dockerfile
FROM ubuntu:22.04

# Instalar Python 3.11
RUN apt-get update && apt-get install -y \
    software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y \
    python3.11 python3.11-pip python3.11-venv python3.11-dev \
    ...
```

#### 5.2 Actualizar docker-compose.yml

Verificar que use la imagen correcta con Python 3.11.

### Fase 6: Documentación y Despliegue (1 día)

#### 6.1 Actualizar documentación
- README.md
- INSTALL.md (si existe)
- Comentarios en código

#### 6.2 Crear guía de migración para usuarios
- Documentar cambios necesarios
- Proporcionar script de migración

---

## 🛠️ Scripts de Ayuda

### Script 1: Verificar Compatibilidad

```bash
#!/bin/bash
# verify_python_compatibility.sh

PYTHON_VERSION=$1
if [ -z "$PYTHON_VERSION" ]; then
    PYTHON_VERSION="3.11"
fi

echo "Verificando compatibilidad con Python $PYTHON_VERSION..."

python$PYTHON_VERSION -m venv /tmp/test-venv-$PYTHON_VERSION
source /tmp/test-venv-$PYTHON_VERSION/bin/activate

pip install --upgrade pip

echo "Instalando dependencias críticas..."
pip install "numpy>=1.26.0" "opencv-python>=4.9.0" "pillow>=10.3.0"

echo "Probando imports..."
python$PYTHON_VERSION << EOF
import sys
print(f"Python: {sys.version}")

try:
    import numpy as np
    print(f"✅ NumPy {np.__version__}")
except Exception as e:
    print(f"❌ NumPy: {e}")

try:
    import cv2
    print(f"✅ OpenCV {cv2.__version__}")
except Exception as e:
    print(f"❌ OpenCV: {e}")

try:
    import PIL
    print(f"✅ Pillow {PIL.__version__}")
except Exception as e:
    print(f"❌ Pillow: {e}")
EOF

deactivate
rm -rf /tmp/test-venv-$PYTHON_VERSION
```

### Script 2: Migrar Entorno Virtual

```bash
#!/bin/bash
# migrate_venv.sh

OLD_PYTHON="python3.8"
NEW_PYTHON="python3.11"
VENV_DIR="venv"

echo "Migrando entorno virtual de $OLD_PYTHON a $NEW_PYTHON..."

# 1. Guardar dependencias actuales
source $VENV_DIR/bin/activate
pip freeze > requirements-old.txt
deactivate

# 2. Eliminar entorno antiguo
rm -rf $VENV_DIR

# 3. Crear nuevo entorno
$NEW_PYTHON -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 4. Actualizar pip
pip install --upgrade pip setuptools wheel

# 5. Instalar dependencias actualizadas
pip install -r requirements-py311.txt

echo "✅ Migración completada"
echo "Recuerda probar: python -m llm_control voice-server --help"
```

---

## ⚠️ Riesgos y Mitigaciones

### Riesgo 1: PaddlePaddle no compatible
**Mitigación**: 
- Usar solo EasyOCR como alternativa
- Hacer PaddleOCR opcional en el código

### Riesgo 2: PyAudio falla en compilación
**Mitigación**:
- Usar `sounddevice` como alternativa
- Proporcionar instrucciones de instalación específicas

### Riesgo 3: NumPy 1.26 rompe código existente
**Mitigación**:
- Probar exhaustivamente todas las funcionalidades
- Mantener numpy 1.24.3 como fallback temporal

### Riesgo 4: PyTorch incompatibilidad
**Mitigación**:
- Verificar versión compatible de PyTorch con numpy 1.26
- Considerar actualizar PyTorch si es necesario

---

## 📊 Checklist de Migración

### Pre-migración
- [ ] Crear rama de migración
- [ ] Documentar estado actual
- [ ] Crear entorno de prueba
- [ ] Backup de código y datos

### Migración de Dependencias
- [ ] Actualizar requirements.txt
- [ ] Instalar numpy 1.26+
- [ ] Instalar PyTorch compatible
- [ ] Resolver problemas con pyaudio
- [ ] Resolver problemas con paddlepaddle
- [ ] Verificar todas las dependencias

### Migración de Código
- [ ] Actualizar setup.py
- [ ] Actualizar README.md
- [ ] Actualizar Dockerfile
- [ ] Actualizar scripts de inicio
- [ ] Verificar código para deprecaciones

### Pruebas
- [ ] Pruebas de importación
- [ ] Pruebas funcionales básicas
- [ ] Pruebas de integración
- [ ] Pruebas de rendimiento
- [ ] Pruebas en Docker

### Documentación
- [ ] Actualizar README
- [ ] Crear guía de migración
- [ ] Actualizar changelog
- [ ] Documentar problemas conocidos

### Despliegue
- [ ] Probar en entorno de desarrollo
- [ ] Probar en entorno de staging
- [ ] Desplegar en producción
- [ ] Monitorear errores post-migración

---

## 🎯 Recomendación Final

**Migrar primero a Python 3.11** por las siguientes razones:
1. Mayor estabilidad y compatibilidad con dependencias actuales
2. Mejoras de rendimiento significativas vs 3.8
3. Menos riesgo de incompatibilidades
4. Mejor soporte de la comunidad para dependencias ML

**Considerar Python 3.12** después de estabilizar 3.11, si:
- Todas las dependencias son compatibles
- Se necesita el máximo rendimiento
- Se está dispuesto a resolver problemas adicionales

---

## 📅 Estimación de Tiempo

- **Fase 1 (Preparación)**: 1-2 días
- **Fase 2 (Dependencias)**: 2-3 días
- **Fase 3 (Código)**: 1-2 días
- **Fase 4 (Pruebas)**: 2-3 días
- **Fase 5 (Docker)**: 1 día
- **Fase 6 (Documentación)**: 1 día

**Total estimado: 8-12 días** (dependiendo de problemas encontrados)

---

## 📚 Referencias

- [Python 3.11 Release Notes](https://docs.python.org/3.11/whatsnew/3.11.html)
- [Python 3.12 Release Notes](https://docs.python.org/3.12/whatsnew/3.12.html)
- [NumPy Compatibility](https://numpy.org/devdocs/release/)
- [PyTorch Compatibility](https://pytorch.org/get-started/locally/)
- [PaddlePaddle Installation](https://www.paddlepaddle.org.cn/install/quick)

---

**Última actualización**: 2025-01-XX
**Versión del plan**: 1.0


