# Guía de Build y Distribución

Esta guía explica cómo construir la distribución completa de LLM Control que incluye:
- ✅ Frontend Electron (GUI)
- ✅ Backend Python empaquetado
- ✅ Ollama empaquetado

## Requisitos Previos

### Para Desarrollo
- Node.js 18+ y npm
- Python 3.11 o 3.12
- pip

### Para Build
- Node.js 18+ y npm
- Python 3.11 o 3.12 con todas las dependencias instaladas
- PyInstaller: `pip install pyinstaller`
- electron-builder: se instala automáticamente

## Proceso de Build Completo

### Opción 1: Build Automático (Recomendado)

```bash
# Desde la raíz del proyecto
npm run build:all
```

Este comando:
1. Descarga los binarios de Ollama para todas las plataformas
2. Empaqueta el backend Python con PyInstaller
3. Construye la aplicación Electron con todos los recursos

### Opción 2: Build Paso a Paso

```bash
# 1. Descargar binarios de Ollama
npm run build:ollama

# 2. Empaquetar backend Python
npm run build:python

# 3. Construir aplicación Electron
npm run build:electron
```

### Build para Plataforma Específica

```bash
# Linux
npm run build:electron:linux

# Windows
npm run build:electron:win

# macOS
npm run build:electron:mac
```

## Estructura de Recursos

Después del build, la estructura será:

```
resources/
├── ollama/
│   ├── linux-x64/
│   │   └── ollama
│   ├── win32-x64/
│   │   └── ollama.exe
│   ├── darwin-x64/
│   │   └── ollama
│   └── darwin-arm64/
│       └── ollama
└── python-backend/
    ├── llm-control-server (Linux/macOS)
    └── llm-control-server.exe (Windows)
```

## Archivos de Salida

Los instaladores se generan en:
- `gui-electron/dist/` - Instaladores finales

Formatos generados:
- **Linux**: AppImage y .deb
- **Windows**: .exe (NSIS installer)
- **macOS**: .dmg

## Verificación

Después del build, puedes verificar que todo está incluido:

1. **Ollama**: Los binarios deben estar en `resources/ollama/`
2. **Python**: El ejecutable debe estar en `resources/python-backend/`
3. **Electron**: Los instaladores deben estar en `gui-electron/dist/`

## Desarrollo vs Producción

La aplicación detecta automáticamente si está en modo empaquetado:

- **Desarrollo**: Usa Python del sistema/venv y Ollama del sistema
- **Producción**: Usa los binarios empaquetados

## Solución de Problemas

### PyInstaller no encuentra módulos

Si PyInstaller falla al encontrar módulos, edita `build.spec` y agrega los módulos faltantes a `hiddenimports`.

### Ollama no se descarga

Verifica tu conexión a internet y que GitHub Releases esté accesible. Puedes descargar manualmente los binarios desde:
https://github.com/ollama/ollama/releases

### Electron Builder falla

Asegúrate de que:
- `resources/ollama/` contiene los binarios
- `resources/python-backend/` contiene el ejecutable Python
- Tienes permisos de escritura en `gui-electron/dist/`

## Notas Importantes

- **Tamaño del instalador**: Será grande (~500MB-1GB) porque incluye Python, dependencias y Ollama
- **Modelos de Ollama**: NO se empaquetan, se descargan en runtime con `ollama pull`
- **GPU**: Ollama puede usar GPU si está disponible (igual que en Docker)

## Próximos Pasos

Después del build exitoso:
1. Prueba el instalador en una máquina limpia
2. Verifica que Ollama se inicia correctamente
3. Verifica que el servidor Python funciona
4. Distribuye el instalador a los usuarios

