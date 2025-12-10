#!/bin/bash
# verify_python_compatibility.sh
# Script para verificar compatibilidad de dependencias con Python 3.11/3.12

set -e

PYTHON_VERSION=${1:-"3.11"}
VENV_DIR="/tmp/test-venv-python${PYTHON_VERSION}"

echo "=========================================="
echo "Verificando compatibilidad con Python ${PYTHON_VERSION}"
echo "=========================================="

# Verificar que Python está instalado
if ! command -v "python${PYTHON_VERSION}" &> /dev/null; then
    echo "❌ Python ${PYTHON_VERSION} no está instalado"
    echo "Instalar con: sudo apt install python${PYTHON_VERSION} python${PYTHON_VERSION}-venv python${PYTHON_VERSION}-dev"
    exit 1
fi

echo "✅ Python ${PYTHON_VERSION} encontrado"
"python${PYTHON_VERSION}" --version

# Crear entorno virtual temporal
echo ""
echo "Creando entorno virtual temporal..."
rm -rf "$VENV_DIR"
"python${PYTHON_VERSION}" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Actualizar pip
echo "Actualizando pip..."
pip install --upgrade pip setuptools wheel --quiet

# Instalar dependencias críticas
echo ""
echo "Instalando dependencias críticas..."
pip install --quiet "numpy>=1.26.0" "opencv-python>=4.9.0" "pillow>=10.3.0"

# Probar imports
echo ""
echo "Probando imports críticos..."
"python${PYTHON_VERSION}" << 'PYTHON_EOF'
import sys
print(f"Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

errors = []
warnings = []

# Test NumPy
try:
    import numpy as np
    print(f"✅ NumPy {np.__version__}")
    if np.__version__.startswith("1.24") or np.__version__.startswith("1.25"):
        warnings.append("NumPy < 1.26 puede tener problemas con Python 3.12")
except Exception as e:
    errors.append(f"NumPy: {e}")
    print(f"❌ NumPy: {e}")

# Test OpenCV
try:
    import cv2
    print(f"✅ OpenCV {cv2.__version__}")
except Exception as e:
    errors.append(f"OpenCV: {e}")
    print(f"❌ OpenCV: {e}")

# Test Pillow
try:
    import PIL
    print(f"✅ Pillow {PIL.__version__}")
except Exception as e:
    errors.append(f"Pillow: {e}")
    print(f"❌ Pillow: {e}")

# Test PyTorch (opcional, puede tardar)
try:
    import torch
    print(f"✅ PyTorch {torch.__version__}")
except ImportError:
    warnings.append("PyTorch no instalado (opcional para esta prueba)")
except Exception as e:
    warnings.append(f"PyTorch: {e}")

# Test Flask
try:
    import flask
    print(f"✅ Flask {flask.__version__}")
except Exception as e:
    errors.append(f"Flask: {e}")
    print(f"❌ Flask: {e}")

# Resumen
print("\n" + "="*50)
if errors:
    print("❌ ERRORES ENCONTRADOS:")
    for error in errors:
        print(f"  - {error}")
    sys.exit(1)
elif warnings:
    print("⚠️  ADVERTENCIAS:")
    for warning in warnings:
        print(f"  - {warning}")
    print("\n✅ Compatibilidad básica verificada")
else:
    print("✅ Todas las dependencias críticas son compatibles")
PYTHON_EOF

RESULT=$?

# Limpiar
echo ""
echo "Limpiando entorno temporal..."
deactivate 2>/dev/null || true
rm -rf "$VENV_DIR"

if [ $RESULT -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ Verificación completada exitosamente"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "❌ Se encontraron problemas de compatibilidad"
    echo "=========================================="
    exit 1
fi


