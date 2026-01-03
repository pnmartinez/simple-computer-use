#!/bin/bash
# Script automatizado para subir archivos grandes
# Intenta instalar Git LFS y luego sube los archivos automáticamente

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BRANCH=$(git branch --show-current)
REMOTE="origin"

echo "=== Script de Subida Automática de Archivos Grandes ==="
echo "Rama: $BRANCH"
echo "Remoto: $REMOTE"
echo ""

# Función para instalar Git LFS
install_git_lfs() {
    echo "Intentando instalar Git LFS..."
    
    # Método 1: apt-get (requiere sudo)
    if command -v apt-get &> /dev/null; then
        echo "Instalando Git LFS con apt-get..."
        sudo apt-get update && sudo apt-get install -y git-lfs
        return $?
    fi
    
    # Método 2: Descargar binario directamente
    echo "Descargando Git LFS binario..."
    GIT_LFS_VERSION="3.5.1"
    ARCH=$(uname -m)
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    
    if [ "$OS" = "linux" ]; then
        if [ "$ARCH" = "x86_64" ]; then
            ARCH="amd64"
        fi
        URL="https://github.com/git-lfs/git-lfs/releases/download/v${GIT_LFS_VERSION}/git-lfs-${OS}-${ARCH}-v${GIT_LFS_VERSION}.tar.gz"
        
        echo "Descargando desde: $URL"
        mkdir -p /tmp/git-lfs-install
        cd /tmp/git-lfs-install
        curl -L "$URL" -o git-lfs.tar.gz
        tar -xzf git-lfs.tar.gz
        sudo ./install.sh || {
            echo "Instalación automática falló. Por favor instala Git LFS manualmente:"
            echo "  sudo apt-get install git-lfs"
            return 1
        }
        cd "$PROJECT_ROOT"
        return 0
    fi
    
    return 1
}

# Verificar/instalar Git LFS
if ! command -v git-lfs &> /dev/null && ! git lfs version &> /dev/null; then
    echo "Git LFS no está instalado. Intentando instalar..."
    if ! install_git_lfs; then
        echo ""
        echo "ERROR: No se pudo instalar Git LFS automáticamente."
        echo "Por favor instálalo manualmente con:"
        echo "  sudo apt-get install git-lfs"
        echo ""
        echo "Luego ejecuta este script nuevamente."
        exit 1
    fi
fi

# Inicializar Git LFS
echo "Inicializando Git LFS..."
git lfs install --skip-repo || git lfs install

echo ""
echo "=== Verificando archivos grandes ==="

APPIMAGE="gui-electron/dist/Simple Computer Use Desktop-1.0.0.AppImage"
PYTHON_BACKEND="resources/python-backend/simple-computer-use-server"

# Verificar que los archivos existen
FILES_EXIST=true
if [ ! -f "$APPIMAGE" ]; then
    echo "ADVERTENCIA: No se encontró el AppImage: $APPIMAGE"
    FILES_EXIST=false
else
    SIZE=$(du -h "$APPIMAGE" | cut -f1)
    echo "✓ AppImage encontrado: $APPIMAGE ($SIZE)"
fi

if [ ! -d "$PYTHON_BACKEND" ]; then
    echo "ADVERTENCIA: No se encontró el directorio del backend: $PYTHON_BACKEND"
    FILES_EXIST=false
else
    SIZE=$(du -sh "$PYTHON_BACKEND" | cut -f1)
    echo "✓ Backend Python encontrado: $PYTHON_BACKEND ($SIZE)"
fi

if [ "$FILES_EXIST" = false ]; then
    echo ""
    echo "ERROR: Algunos archivos no se encontraron. Abortando."
    exit 1
fi

echo ""
echo "=== Agregando archivos a Git LFS ==="

# Agregar .gitattributes primero
if [ -f ".gitattributes" ]; then
    echo "Agregando .gitattributes..."
    git add .gitattributes
fi

# Agregar archivos grandes
if [ -f "$APPIMAGE" ]; then
    echo "Agregando AppImage a Git LFS..."
    git add "$APPIMAGE"
fi

if [ -d "$PYTHON_BACKEND" ]; then
    echo "Agregando backend Python a Git LFS..."
    git add "$PYTHON_BACKEND"
fi

echo ""
echo "=== Estado de Git ==="
git status --short

echo ""
echo "=== Haciendo commit ==="
git commit -m "Add large distribution files (AppImage and Python backend)" || {
    echo "ADVERTENCIA: No se pudo hacer commit. Puede que no haya cambios o ya esté hecho."
}

echo ""
echo "=== Haciendo push a $REMOTE/$BRANCH ==="
echo "NOTA: Esto puede tardar varios minutos debido al tamaño de los archivos (~11.7GB)"
git push "$REMOTE" "$BRANCH" || {
    echo ""
    echo "ERROR: No se pudo hacer push. Verifica:"
    echo "  1. Que tengas permisos de escritura en el repositorio"
    echo "  2. Que tu conexión a internet sea estable"
    echo "  3. Que Git LFS esté correctamente configurado"
    echo ""
    echo "Puedes intentar manualmente con:"
    echo "  git push $REMOTE $BRANCH"
    exit 1
}

echo ""
echo "=== ¡Subida completada! ==="
echo "Los archivos grandes han sido subidos usando Git LFS."
echo "Puedes verificar con: git lfs ls-files"

