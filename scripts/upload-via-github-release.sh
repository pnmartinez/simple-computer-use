#!/bin/bash
# Script para subir archivos grandes como GitHub Release
# Alternativa a Git LFS cuando no está disponible

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Subida de Archivos Grandes vía GitHub Release ==="
echo ""

# Verificar GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "ERROR: GitHub CLI (gh) no está instalado."
    echo "Instálalo con: sudo apt-get install gh"
    exit 1
fi

# Verificar autenticación
if ! gh auth status &> /dev/null; then
    echo "ERROR: No estás autenticado con GitHub CLI."
    echo "Ejecuta: gh auth login"
    exit 1
fi

APPIMAGE="gui-electron/dist/Simple Computer Use Desktop-1.0.0.AppImage"
PYTHON_BACKEND="resources/python-backend/simple-computer-use-server"

# Verificar archivos
if [ ! -f "$APPIMAGE" ]; then
    echo "ERROR: No se encontró el AppImage: $APPIMAGE"
    exit 1
fi

if [ ! -d "$PYTHON_BACKEND" ]; then
    echo "ERROR: No se encontró el directorio del backend: $PYTHON_BACKEND"
    exit 1
fi

APPIMAGE_SIZE=$(du -h "$APPIMAGE" | cut -f1)
BACKEND_SIZE=$(du -sh "$PYTHON_BACKEND" | cut -f1)

echo "Archivos encontrados:"
echo "  - AppImage: $APPIMAGE ($APPIMAGE_SIZE)"
echo "  - Backend Python: $PYTHON_BACKEND ($BACKEND_SIZE)"
echo ""

# Verificar límite de GitHub (2GB por archivo)
APPIMAGE_BYTES=$(stat -c%s "$APPIMAGE" 2>/dev/null || stat -f%z "$APPIMAGE" 2>/dev/null)
MAX_SIZE=$((2 * 1024 * 1024 * 1024))  # 2GB en bytes

if [ "$APPIMAGE_BYTES" -gt "$MAX_SIZE" ]; then
    echo "ADVERTENCIA: El AppImage ($APPIMAGE_SIZE) excede el límite de 2GB de GitHub Releases."
    echo "Comprimiendo AppImage..."
    APPIMAGE_ZIP="/tmp/$(basename "$APPIMAGE").tar.gz"
    tar -czf "$APPIMAGE_ZIP" -C "$(dirname "$APPIMAGE")" "$(basename "$APPIMAGE")"
    APPIMAGE_ZIP_SIZE=$(du -h "$APPIMAGE_ZIP" | cut -f1)
    APPIMAGE_ZIP_BYTES=$(stat -c%s "$APPIMAGE_ZIP" 2>/dev/null || stat -f%z "$APPIMAGE_ZIP" 2>/dev/null)
    
    if [ "$APPIMAGE_ZIP_BYTES" -gt "$MAX_SIZE" ]; then
        echo "ERROR: Incluso comprimido ($APPIMAGE_ZIP_SIZE), el archivo excede 2GB."
        echo "GitHub Releases no puede manejar archivos tan grandes."
        echo ""
        echo "Opciones:"
        echo "1. Instalar Git LFS: sudo apt-get install git-lfs"
        echo "2. Usar un servicio de almacenamiento externo (S3, Google Cloud, etc.)"
        echo "3. Dividir el archivo en partes más pequeñas"
        rm -f "$APPIMAGE_ZIP"
        exit 1
    fi
    
    APPIMAGE="$APPIMAGE_ZIP"
    echo "✓ AppImage comprimido: $APPIMAGE ($APPIMAGE_ZIP_SIZE)"
    echo ""
fi

# Obtener información del repositorio
REPO=$(git remote get-url origin | sed -E 's/.*github.com[:/]([^/]+\/[^/]+)(\.git)?$/\1/')
echo "Repositorio: $REPO"
echo ""

# Crear release
VERSION=$(date +%Y%m%d-%H%M%S)
TAG="v$VERSION"
RELEASE_NAME="Distribution Files - $VERSION"

echo "Creando release: $TAG"
echo "Nombre: $RELEASE_NAME"
echo ""

# Crear release (draft primero) - sin archivos primero
gh release create "$TAG" \
    --title "$RELEASE_NAME" \
    --notes "Archivos de distribución grandes:
- AppImage: Simple Computer Use Desktop (puede estar comprimido)
- Python Backend: Servidor empaquetado con PyInstaller

**Nota**: Estos archivos son grandes. 
Para usarlos, descarga y extrae los archivos según corresponda." \
    --draft \
    || {
    echo "ERROR: No se pudo crear el release."
    exit 1
}

# Subir AppImage (puede estar comprimido)
echo "Subiendo AppImage..."
gh release upload "$TAG" "$APPIMAGE" --clobber || {
    echo "ERROR: No se pudo subir el AppImage."
    exit 1
}

echo ""
echo "=== Comprimiendo backend Python ==="
BACKEND_ZIP="/tmp/simple-computer-use-server-${VERSION}.tar.gz"
echo "Creando archivo comprimido: $BACKEND_ZIP"
tar -czf "$BACKEND_ZIP" -C "$(dirname "$PYTHON_BACKEND")" "$(basename "$PYTHON_BACKEND")" || {
    echo "ERROR: No se pudo comprimir el backend."
    exit 1
}

ZIP_SIZE=$(du -h "$BACKEND_ZIP" | cut -f1)
echo "✓ Comprimido: $BACKEND_ZIP ($ZIP_SIZE)"
echo ""

echo "=== Subiendo archivos al release ==="
gh release upload "$TAG" "$BACKEND_ZIP" --clobber || {
    echo "ERROR: No se pudo subir el backend comprimido."
    exit 1
}

echo ""
echo "=== Publicando release ==="
gh release edit "$TAG" --draft=false || {
    echo "ADVERTENCIA: No se pudo publicar el release. Puede que ya esté publicado."
}

echo ""
echo "=== ¡Subida completada! ==="
echo "Release creado: https://github.com/$REPO/releases/tag/$TAG"
echo ""
echo "Para descargar los archivos:"
echo "  gh release download $TAG"
echo ""
echo "O desde el navegador:"
echo "  https://github.com/$REPO/releases"

# Limpiar archivos temporales
rm -f "$BACKEND_ZIP"
if [ -n "$APPIMAGE_ZIP" ] && [ -f "$APPIMAGE_ZIP" ]; then
    rm -f "$APPIMAGE_ZIP"
fi

