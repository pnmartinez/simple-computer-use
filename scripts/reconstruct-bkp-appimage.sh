#!/bin/bash
# Script para reconstruir el archivo BKP-Simple Computer Use Desktop-1.0.0.AppImage
# a partir de las partes divididas

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

DIST_DIR="gui-electron/dist"
APPIMAGE_NAME="BKP-Simple Computer Use Desktop-1.0.0.AppImage"
APPIMAGE_PATH="$DIST_DIR/$APPIMAGE_NAME"
PARTS_PATTERN="$DIST_DIR/${APPIMAGE_NAME}.part*"

echo "=== Reconstrucción de AppImage BKP ==="
echo ""

# Verificar que existan las partes
PARTS=($(ls $PARTS_PATTERN 2>/dev/null | sort))
if [ ${#PARTS[@]} -eq 0 ]; then
    echo "ERROR: No se encontraron partes del archivo en $DIST_DIR"
    echo "Busca archivos que coincidan con: ${APPIMAGE_NAME}.part*"
    exit 1
fi

echo "Partes encontradas: ${#PARTS[@]}"
for part in "${PARTS[@]}"; do
    size=$(du -h "$part" | cut -f1)
    echo "  - $(basename "$part") ($size)"
done

echo ""
echo "Reconstruyendo $APPIMAGE_NAME..."

# Eliminar el archivo original si existe
if [ -f "$APPIMAGE_PATH" ]; then
    echo "Eliminando archivo original existente..."
    rm -f "$APPIMAGE_PATH"
fi

# Combinar todas las partes
cat "${PARTS[@]}" > "$APPIMAGE_PATH"

# Dar permisos de ejecución
chmod +x "$APPIMAGE_PATH"

# Verificar el tamaño
ORIGINAL_SIZE=$(du -h "$APPIMAGE_PATH" | cut -f1)
echo ""
echo "✓ Archivo reconstruido: $APPIMAGE_PATH"
echo "  Tamaño: $ORIGINAL_SIZE"

# Verificar integridad básica (el archivo debe ser > 0)
if [ ! -s "$APPIMAGE_PATH" ]; then
    echo "ERROR: El archivo reconstruido está vacío"
    exit 1
fi

echo ""
echo "=== ¡Reconstrucción completada! ==="
echo "Puedes ejecutar el AppImage con:"
echo "  $APPIMAGE_PATH"

