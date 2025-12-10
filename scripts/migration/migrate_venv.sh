#!/bin/bash
# migrate_venv.sh
# Script para migrar un entorno virtual a Python 3.11/3.12

set -e

NEW_PYTHON_VERSION=${1:-"3.11"}
OLD_VENV_DIR=${2:-"venv"}
NEW_VENV_DIR=${3:-"venv-py${NEW_PYTHON_VERSION}"}
REQUIREMENTS_FILE=${4:-"requirements-py311.txt"}

echo "=========================================="
echo "Migración de Entorno Virtual"
echo "=========================================="
echo "Versión Python objetivo: ${NEW_PYTHON_VERSION}"
echo "Entorno antiguo: ${OLD_VENV_DIR}"
echo "Entorno nuevo: ${NEW_VENV_DIR}"
echo "Archivo de dependencias: ${REQUIREMENTS_FILE}"
echo ""

# Verificar que Python está instalado
if ! command -v "python${NEW_PYTHON_VERSION}" &> /dev/null; then
    echo "❌ Python ${NEW_PYTHON_VERSION} no está instalado"
    echo "Instalar con: sudo apt install python${NEW_PYTHON_VERSION} python${NEW_PYTHON_VERSION}-venv python${NEW_PYTHON_VERSION}-dev"
    exit 1
fi

# Guardar dependencias del entorno antiguo si existe
if [ -d "$OLD_VENV_DIR" ]; then
    echo "📦 Guardando dependencias del entorno antiguo..."
    source "$OLD_VENV_DIR/bin/activate" 2>/dev/null || true
    pip freeze > "requirements-old-$(date +%Y%m%d).txt" 2>/dev/null || true
    deactivate 2>/dev/null || true
    echo "✅ Dependencias guardadas en requirements-old-$(date +%Y%m%d).txt"
else
    echo "⚠️  Entorno antiguo no encontrado, continuando sin backup"
fi

# Verificar que existe el archivo de dependencias
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "❌ Archivo de dependencias no encontrado: ${REQUIREMENTS_FILE}"
    echo "Usar: requirements-py311.txt o especificar con 4to argumento"
    exit 1
fi

# Eliminar entorno nuevo si existe
if [ -d "$NEW_VENV_DIR" ]; then
    echo "🗑️  Eliminando entorno existente..."
    rm -rf "$NEW_VENV_DIR"
fi

# Crear nuevo entorno
echo ""
echo "🔨 Creando nuevo entorno virtual con Python ${NEW_PYTHON_VERSION}..."
"python${NEW_PYTHON_VERSION}" -m venv "$NEW_VENV_DIR"
source "$NEW_VENV_DIR/bin/activate"

# Actualizar herramientas base
echo "📦 Actualizando pip, setuptools, wheel..."
pip install --upgrade pip setuptools wheel --quiet

# Instalar dependencias en orden específico
echo ""
echo "📦 Instalando dependencias (esto puede tardar varios minutos)..."

# 1. NumPy primero (dependencia crítica)
echo "  → Instalando NumPy..."
pip install --quiet "numpy>=1.26.0,<2.0.0" || {
    echo "❌ Error instalando NumPy"
    exit 1
}

# 2. OpenCV y Pillow
echo "  → Instalando OpenCV y Pillow..."
pip install --quiet "opencv-python>=4.9.0" "pillow>=10.3.0" || {
    echo "⚠️  Advertencia: Problemas con OpenCV/Pillow"
}

# 3. PyTorch (opcional, puede tardar mucho)
echo "  → Instalando PyTorch (esto puede tardar)..."
pip install --quiet torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu118 || {
    echo "⚠️  Advertencia: PyTorch puede requerir instalación manual"
    echo "   Instalar con: pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu118"
}

# 4. PyAudio (puede fallar)
echo "  → Instalando PyAudio..."
pip install --quiet "pyaudio>=0.2.13" || {
    echo "⚠️  Advertencia: PyAudio falló, intentando alternativas..."
    # Intentar con pipwin si está disponible
    pip install --quiet pipwin 2>/dev/null && pipwin install pyaudio || {
        echo "   PyAudio no se pudo instalar. Usar sounddevice como alternativa."
    }
}

# 5. Resto de dependencias
echo "  → Instalando dependencias restantes..."
pip install --quiet -r "$REQUIREMENTS_FILE" || {
    echo "⚠️  Algunas dependencias pueden haber fallado"
    echo "   Revisar errores arriba"
}

# Verificar instalación
echo ""
echo "🔍 Verificando instalación..."
python << 'PYTHON_EOF'
import sys
print(f"Python: {sys.version}")

errors = []
try:
    import numpy as np
    print(f"✅ NumPy {np.__version__}")
except Exception as e:
    errors.append(f"NumPy: {e}")
    print(f"❌ NumPy: {e}")

try:
    import flask
    print(f"✅ Flask {flask.__version__}")
except Exception as e:
    errors.append(f"Flask: {e}")
    print(f"❌ Flask: {e}")

try:
    import pyautogui
    print(f"✅ PyAutoGUI {pyautogui.__version__}")
except Exception as e:
    errors.append(f"PyAutoGUI: {e}")
    print(f"❌ PyAutoGUI: {e}")

if errors:
    print("\n⚠️  Se encontraron errores en dependencias críticas")
    sys.exit(1)
else:
    print("\n✅ Dependencias críticas verificadas")
PYTHON_EOF

RESULT=$?

deactivate

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Migración completada exitosamente"
    echo "=========================================="
    echo ""
    echo "Para activar el nuevo entorno:"
    echo "  source ${NEW_VENV_DIR}/bin/activate"
    echo ""
    echo "Para probar el servidor:"
    echo "  python -m llm_control voice-server --help"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "⚠️  Migración completada con advertencias"
    echo "=========================================="
    echo "Revisar errores arriba y instalar dependencias faltantes manualmente"
fi


