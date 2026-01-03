#!/bin/bash
# Script para subir archivos grandes usando Git LFS

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Configurando Git LFS ==="

# Verificar si Git LFS está instalado
if ! command -v git-lfs &> /dev/null; then
    echo "ERROR: Git LFS no está instalado."
    echo "Por favor instálalo con:"
    echo "  sudo apt-get install git-lfs  # Ubuntu/Debian"
    echo "  brew install git-lfs          # macOS"
    echo "  choco install git-lfs         # Windows (Chocolatey)"
    exit 1
fi

# Inicializar Git LFS si no está inicializado
if ! git lfs version &> /dev/null; then
    echo "Inicializando Git LFS..."
    git lfs install
fi

echo ""
echo "=== Verificando archivos grandes ==="

APPIMAGE="gui-electron/dist/Simple Computer Use Desktop-1.0.0.AppImage"
PYTHON_BACKEND="resources/python-backend/simple-computer-use-server"

# Verificar que los archivos existen
if [ ! -f "$APPIMAGE" ]; then
    echo "ADVERTENCIA: No se encontró el AppImage: $APPIMAGE"
else
    SIZE=$(du -h "$APPIMAGE" | cut -f1)
    echo "✓ AppImage encontrado: $APPIMAGE ($SIZE)"
fi

if [ ! -d "$PYTHON_BACKEND" ]; then
    echo "ADVERTENCIA: No se encontró el directorio del backend: $PYTHON_BACKEND"
else
    SIZE=$(du -sh "$PYTHON_BACKEND" | cut -f1)
    echo "✓ Backend Python encontrado: $PYTHON_BACKEND ($SIZE)"
fi

echo ""
echo "=== Agregando archivos a Git LFS ==="

# Agregar archivos específicos
if [ -f "$APPIMAGE" ]; then
    echo "Agregando AppImage a Git LFS..."
    git add "$APPIMAGE"
fi

if [ -d "$PYTHON_BACKEND" ]; then
    echo "Agregando backend Python a Git LFS..."
    git add "$PYTHON_BACKEND"
fi

# Agregar .gitattributes si no está en el repositorio
if ! git ls-files --error-unmatch .gitattributes &> /dev/null; then
    echo "Agregando .gitattributes..."
    git add .gitattributes
fi

echo ""
echo "=== Estado de Git ==="
git status

echo ""
echo "=== Próximos pasos ==="
echo "1. Revisa los archivos que se van a subir arriba"
echo "2. Si todo está correcto, ejecuta:"
echo "   git commit -m 'Add large distribution files (AppImage and Python backend)'"
echo "   git push origin <branch-name>"
echo ""
echo "NOTA: La primera vez que subas archivos grandes, Git LFS puede tardar varios minutos."

