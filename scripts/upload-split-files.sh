#!/bin/bash
# Script para dividir y subir archivos grandes como GitHub Release
# Divide archivos >2GB en partes de 1.5GB

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Subida de Archivos Grandes (Divididos) vía GitHub Release ==="
echo ""

# Verificar GitHub CLI
if ! command -v gh &> /dev/null; then
    echo "ERROR: GitHub CLI (gh) no está instalado."
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo "ERROR: No estás autenticado con GitHub CLI."
    exit 1
fi

APPIMAGE="gui-electron/dist/Simple Computer Use Desktop-1.0.0.AppImage"
PYTHON_BACKEND="resources/python-backend/simple-computer-use-server"

# Verificar archivos
if [ ! -f "$APPIMAGE" ]; then
    echo "ERROR: No se encontró el AppImage"
    exit 1
fi

if [ ! -d "$PYTHON_BACKEND" ]; then
    echo "ERROR: No se encontró el directorio del backend"
    exit 1
fi

# Obtener información del repositorio
REPO=$(git remote get-url origin | sed -E 's/.*github.com[:/]([^/]+\/[^/]+)(\.git)?$/\1/')
VERSION=$(date +%Y%m%d-%H%M%S)
TAG="dist-files-$VERSION"
TEMP_DIR="/tmp/dist-upload-$$"
mkdir -p "$TEMP_DIR"

# Función para dividir archivo
split_file() {
    local file="$1"
    local name="$2"
    local chunk_size="1500M"  # 1.5GB por parte
    
    echo "Dividiendo $name en partes de 1.5GB..."
    split -b "$chunk_size" -d "$file" "$TEMP_DIR/${name}.part"
    
    local parts=($(ls "$TEMP_DIR/${name}.part"* 2>/dev/null | sort))
    echo "✓ Creadas ${#parts[@]} partes"
    echo "${parts[@]}"
}

# Dividir AppImage si es necesario
APPIMAGE_BYTES=$(stat -c%s "$APPIMAGE" 2>/dev/null || stat -f%z "$APPIMAGE" 2>/dev/null)
MAX_SIZE=$((1500 * 1024 * 1024))  # 1.5GB

if [ "$APPIMAGE_BYTES" -gt "$MAX_SIZE" ]; then
    echo "El AppImage es muy grande, dividiéndolo..."
    APPIMAGE_PARTS=($(split_file "$APPIMAGE" "appimage"))
else
    echo "El AppImage es pequeño enough, copiando..."
    cp "$APPIMAGE" "$TEMP_DIR/appimage"
    APPIMAGE_PARTS=("$TEMP_DIR/appimage")
fi

# Comprimir y dividir backend Python
echo ""
echo "Comprimiendo backend Python..."
BACKEND_TAR="$TEMP_DIR/backend.tar.gz"
tar -czf "$BACKEND_TAR" -C "$(dirname "$PYTHON_BACKEND")" "$(basename "$PYTHON_BACKEND")" || {
    echo "ERROR: No se pudo comprimir el backend"
    exit 1
}

BACKEND_BYTES=$(stat -c%s "$BACKEND_TAR" 2>/dev/null || stat -f%z "$BACKEND_TAR" 2>/dev/null)
if [ "$BACKEND_BYTES" -gt "$MAX_SIZE" ]; then
    echo "El backend comprimido es muy grande, dividiéndolo..."
    BACKEND_PARTS=($(split_file "$BACKEND_TAR" "backend"))
else
    BACKEND_PARTS=("$BACKEND_TAR")
fi

# Crear release
echo ""
echo "Creando release: $TAG"
gh release create "$TAG" \
    --title "Distribution Files - $VERSION" \
    --notes "Archivos de distribución divididos en partes.

**Instrucciones para reconstruir:**

1. Descarga todas las partes del AppImage (appimage.part*) y backend (backend.part*)
2. Para el AppImage:
   \`\`\`bash
   cat appimage.part* > Simple\ Computer\ Use\ Desktop-1.0.0.AppImage
   chmod +x Simple\ Computer\ Use\ Desktop-1.0.0.AppImage
   \`\`\`
3. Para el backend:
   \`\`\`bash
   cat backend.part* > backend.tar.gz
   tar -xzf backend.tar.gz
   \`\`\`

**Nota**: Asegúrate de descargar TODAS las partes antes de reconstruir." \
    --draft \
    || {
    echo "ERROR: No se pudo crear el release"
    rm -rf "$TEMP_DIR"
    exit 1
}

# Subir todas las partes
echo ""
echo "Subiendo archivos..."
for part in "${APPIMAGE_PARTS[@]}" "${BACKEND_PARTS[@]}"; do
    filename=$(basename "$part")
    echo "  Subiendo $filename..."
    gh release upload "$TAG" "$part" --clobber || {
        echo "ERROR: No se pudo subir $filename"
        rm -rf "$TEMP_DIR"
        exit 1
    }
done

# Publicar release
echo ""
echo "Publicando release..."
gh release edit "$TAG" --draft=false

echo ""
echo "=== ¡Subida completada! ==="
echo "Release: https://github.com/$REPO/releases/tag/$TAG"
echo ""
echo "Total de partes subidas: $((${#APPIMAGE_PARTS[@]} + ${#BACKEND_PARTS[@]}))"

# Limpiar
rm -rf "$TEMP_DIR"

