# Platform Abstraction Module

Este módulo proporciona una abstracción multiplataforma para operaciones específicas del sistema operativo.

## Estructura

```
platform/
├── index.js      # Router principal - carga la implementación correcta
├── linux.js      # Implementación para Linux
├── windows.js    # Implementación para Windows
└── macos.js      # Implementación para macOS
```

## Uso

```javascript
const platformUtils = require('./platform');

// Todas las funciones funcionan en cualquier plataforma
platformUtils.installStartupService();
platformUtils.getProcessUsingPort(5000);
platformUtils.findPythonExecutable();
```

## Funciones Disponibles

### Startup Service Management
- `installStartupService()` - Instala servicio de inicio automático
- `uninstallStartupService()` - Desinstala servicio de inicio automático
- `isStartupServiceInstalled()` - Verifica si está instalado

### Process Management
- `getProcessUsingPort(port)` - Obtiene información del proceso usando un puerto
- `killProcess(pid)` - Mata un proceso por PID

### Python Detection
- `findPythonExecutable()` - Encuentra el ejecutable de Python correcto

### Desktop Application
- `installDesktopApp()` - Instala la aplicación en el menú de aplicaciones
- `isDesktopAppInstalled()` - Verifica si está instalada

### Platform Info
- `getPlatformName()` - Nombre de la plataforma
- `getPlatformSpecificPaths()` - Rutas específicas de la plataforma

## Estado de Implementación

- ✅ **Windows**: Completamente implementado
- ✅ **macOS**: Completamente implementado
- ⚠️ **Linux**: Placeholder - necesita mover código de `main.js`

## Próximos Pasos

1. Mover implementaciones de Linux desde `main.js` a `linux.js`
2. Actualizar `main.js` para usar `platformUtils` en lugar de código directo
3. Testing en todas las plataformas

