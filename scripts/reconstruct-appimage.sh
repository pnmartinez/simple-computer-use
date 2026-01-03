#!/bin/bash
# Script para reconstruir el AppImage desde las partes divididas

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_ROOT/gui-electron/dist"
APPIMAGE_NAME="Simple Computer Use Desktop-1.0.0.AppImage"
APPIMAGE_PATH="$DIST_DIR/$APPIMAGE_NAME"

echo "=== Reconstruyendo AppImage desde partes ==="
echo ""

# Verificar que las partes existan
PARTS=("$DIST_DIR/$APPIMAGE_NAME.part"*)
if [ ! -f "${PARTS[0]}" ]; then
    echo "ERROR: No se encontraron las partes del AppImage en:"
    echo "  $DIST_DIR"
    echo ""
    echo "Las partes deben tener el formato: $APPIMAGE_NAME.part*"
    exit 1
fi

# Contar partes
PART_COUNT=${#PARTS[@]}
echo "Encontradas $PART_COUNT partes:"
for part in "${PARTS[@]}"; do
    SIZE=$(du -h "$part" | cut -f1)
    echo "  - $(basename "$part") ($SIZE)"
done

echo ""
echo "Reconstruyendo AppImage..."

# Reconstruir concatenando las partes
cat "$DIST_DIR/$APPIMAGE_NAME.part"* > "$APPIMAGE_PATH"

# Hacer ejecutable
chmod +x "$APPIMAGE_PATH"

# Verificar tamaño
RECONSTRUCTED_SIZE=$(du -h "$APPIMAGE_PATH" | cut -f1)
echo "✓ AppImage reconstruido: $APPIMAGE_PATH ($RECONSTRUCTED_SIZE)"

# Verificar integridad básica (que sea un ejecutable ELF)
if file "$APPIMAGE_PATH" | grep -q "ELF"; then
    echo "✓ Verificación: El archivo es un ejecutable ELF válido"
else
    echo "⚠ ADVERTENCIA: El archivo reconstruido no parece ser un ejecutable ELF válido"
fi

echo ""
echo "=== ¡Reconstrucción completada! ==="
echo "El AppImage está listo en: $APPIMAGE_PATH"

