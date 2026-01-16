#!/bin/bash
# Script para ejecutar los tests del proyecto

set -e

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Ejecutando Tests - LLM Control${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Verificar que estamos en el directorio raíz
if [ ! -f "setup.py" ]; then
    echo "Error: Este script debe ejecutarse desde la raíz del proyecto"
    exit 1
fi

# Activar venv si existe
if [ -d "venv-py312" ]; then
    echo "Activando entorno virtual..."
    source venv-py312/bin/activate
elif [ -d "venv" ]; then
    echo "Activando entorno virtual..."
    source venv/bin/activate
fi

# Ejecutar tests
echo -e "${GREEN}Ejecutando tests...${NC}"
echo ""

# Intentar usar pytest si está disponible, sino usar unittest
if command -v pytest &> /dev/null; then
    echo "Usando pytest..."
    python -m pytest tests/ -v --tb=short
else
    echo "Usando unittest (pytest no disponible)..."
    python -m unittest discover tests/ -v
fi

echo ""
echo -e "${GREEN}Tests completados!${NC}"
