# Estrategias de Portabilidad - Simple Computer Use Desktop

## 🎯 Resumen Ejecutivo

**Recomendación Principal**: **Estrategia Híbrida** - Usar **Electron Builder** para la GUI + **Docker opcional** para el servidor Python.

## 📊 Comparación de Estrategias

| Estrategia | Facilidad | Mantenimiento | Performance | Recomendación |
|------------|-----------|---------------|-------------|---------------|
| **Electron Builder** | 🟢 Alta | 🟢 Fácil | 🟢 Excelente | ⭐⭐⭐⭐⭐ |
| **Docker (GUI + Server)** | 🔴 Baja | 🟡 Media | 🔴 Mala | ⭐ |
| **Docker (Solo Server)** | 🟡 Media | 🟢 Fácil | 🟡 Buena | ⭐⭐⭐⭐ |
| **Abstracción de Plataforma** | 🟡 Media | 🟡 Media | 🟢 Excelente | ⭐⭐⭐ |
| **WSL2 (Solo Windows)** | 🟢 Alta | 🟢 Fácil | 🟡 Buena | ⭐⭐⭐ |

---

## 🏆 Estrategia Recomendada: Electron Builder + Docker Opcional

### ✅ Ventajas

1. **Electron Builder ya está configurado** en `package.json`
2. **Empaqueta todo nativo** - mejor performance que Docker
3. **Una sola build** genera ejecutables para Windows/Mac/Linux
4. **Incluye todas las dependencias** - no requiere instalación manual
5. **Docker opcional** para el servidor Python si hay problemas de dependencias

### 📋 Plan de Implementación

#### Fase 1: Abstracción de Plataforma (2-3 días)

Crear módulo `platform-utils.js` que abstraiga operaciones específicas:

```javascript
// gui-electron/platform/index.js
const platform = process.platform;

let platformUtils;
if (platform === 'win32') {
  platformUtils = require('./windows');
} else if (platform === 'darwin') {
  platformUtils = require('./macos');
} else {
  platformUtils = require('./linux');
}

module.exports = platformUtils;
```

**Funciones a abstraer**:
- `installStartupService()` - Task Scheduler (Windows) / Launch Agents (Mac) / systemd (Linux)
- `getProcessUsingPort()` - netstat (Windows) / lsof (Mac/Linux)
- `killProcess()` - taskkill (Windows) / kill (Mac/Linux)
- `findPythonExecutable()` - detectar rutas según plataforma
- `installDesktopApp()` - shortcuts (Windows) / .app bundle (Mac) / .desktop (Linux)

#### Fase 2: Adaptar Código Existente (1-2 días)

Reemplazar llamadas directas con abstracciones:

```javascript
// Antes:
if (process.platform !== 'linux') {
  return { success: false, error: 'Only Linux' };
}
execSync('systemctl --user ...');

// Después:
const platformUtils = require('./platform');
return platformUtils.installStartupService();
```

#### Fase 3: Configurar Electron Builder (1 día)

Ya está configurado, solo ajustar:

```json
{
  "build": {
    "win": {
      "target": "nsis",
      "icon": "assets/icon.ico"
    },
    "mac": {
      "target": "dmg",
      "icon": "assets/icon.icns"
    },
    "linux": {
      "target": ["AppImage", "deb"],
      "icon": "assets/icon.png"
    }
  }
}
```

#### Fase 4: Build y Testing (1-2 días)

```bash
# Build para todas las plataformas
npm run build

# O para plataforma específica
npm run build -- --win
npm run build -- --mac
npm run build -- --linux
```

---

## 🐳 Estrategia Alternativa: Docker (Solo para Servidor Python)

### Cuándo Usar Docker

✅ **Usar Docker si**:
- Hay problemas con dependencias de Python en Windows/Mac
- Se quiere garantizar consistencia del entorno Python
- Se prefiere aislar el servidor del sistema

❌ **No usar Docker para**:
- La aplicación Electron (problemas de GUI, overhead innecesario)
- Desarrollo diario (más lento)

### Implementación

#### Opción A: Docker Compose (Recomendado)

```yaml
# docker-compose.yml (ya existe, adaptar)
version: '3.8'
services:
  voice-server:
    build: .
    ports:
      - "5000:5000"
    environment:
      - OLLAMA_HOST=http://host.docker.internal:11434
    volumes:
      - ./screenshots:/app/screenshots
    # No necesita X server si solo sirve API
```

**Modificar Electron para conectar a Docker**:

```javascript
// main.js
async function startServer(config) {
  // Opción: usar Docker si está disponible
  if (config.useDocker) {
    return startServerDocker(config);
  }
  // Opción normal: proceso local
  return startServerLocal(config);
}
```

#### Opción B: Docker como Fallback

```javascript
// main.js
async function startServer(config) {
  try {
    // Intentar proceso local primero
    return await startServerLocal(config);
  } catch (error) {
    console.log('Local server failed, trying Docker...');
    // Fallback a Docker
    return await startServerDocker(config);
  }
}
```

---

## 🔧 Estrategia 3: Abstracción Completa de Plataforma

### Implementación Detallada

#### 1. Estructura de Archivos

```
gui-electron/
├── platform/
│   ├── index.js          # Router principal
│   ├── linux.js          # Implementación Linux
│   ├── windows.js        # Implementación Windows
│   └── macos.js          # Implementación macOS
```

#### 2. Ejemplo: `platform/windows.js`

```javascript
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

module.exports = {
  // Startup Service
  installStartupService() {
    const projectRoot = path.resolve(__dirname, '..', '..');
    const electronPath = require('electron');
    const scriptPath = path.join(projectRoot, 'gui-electron', 'start-gui-electron.bat');
    
    // Crear script batch
    const batContent = `@echo off
cd /d "${projectRoot}\\gui-electron"
"${electronPath}" .
`;
    fs.writeFileSync(scriptPath, batContent);
    
    // Crear tarea programada con Task Scheduler
    const taskName = 'SimpleComputerUseDesktop';
    const command = `schtasks /create /tn "${taskName}" /tr "${scriptPath}" /sc onlogon /ru "${os.userInfo().username}" /f`;
    
    try {
      execSync(command, { stdio: 'ignore' });
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  // Process Management
  getProcessUsingPort(port) {
    try {
      // netstat -ano | findstr :5000
      const result = execSync(`netstat -ano | findstr :${port}`, {
        encoding: 'utf8',
        stdio: 'pipe'
      });
      
      const lines = result.trim().split('\n');
      for (const line of lines) {
        if (line.includes('LISTENING')) {
          const parts = line.trim().split(/\s+/);
          const pid = parts[parts.length - 1];
          
          // tasklist /FI "PID eq 1234"
          const taskResult = execSync(`tasklist /FI "PID eq ${pid}" /FO CSV /NH`, {
            encoding: 'utf8',
            stdio: 'pipe'
          });
          
          const taskParts = taskResult.split(',');
          return {
            success: true,
            process: {
              pid: pid,
              name: taskParts[0]?.replace(/"/g, '') || 'unknown',
              command: taskParts[0]?.replace(/"/g, '') || 'unknown'
            }
          };
        }
      }
      return { success: false, error: 'No process found' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  killProcess(pid) {
    return new Promise((resolve) => {
      try {
        // taskkill /PID 1234 /T (graceful)
        execSync(`taskkill /PID ${pid} /T`, { stdio: 'ignore' });
        
        setTimeout(() => {
          try {
            // Verificar si aún existe
            execSync(`tasklist /FI "PID eq ${pid}"`, { stdio: 'ignore' });
            // Force kill
            execSync(`taskkill /PID ${pid} /F /T`, { stdio: 'ignore' });
          } catch (e) {
            // Proceso ya terminó
          }
          resolve({ success: true });
        }, 500);
      } catch (error) {
        resolve({ success: false, error: error.message });
      }
    });
  },
  
  // Python Detection
  findPythonExecutable() {
    const projectRoot = path.resolve(__dirname, '..', '..');
    const venvPython = path.join(projectRoot, 'venv-py312', 'Scripts', 'python.exe');
    
    if (fs.existsSync(venvPython)) {
      return venvPython;
    }
    
    // Buscar Python en PATH
    try {
      const result = execSync('where python', { encoding: 'utf8' }).trim();
      if (result) return 'python';
    } catch (e) {
      // Continuar
    }
    
    try {
      const result = execSync('where python3', { encoding: 'utf8' }).trim();
      if (result) return 'python3';
    } catch (e) {
      // Continuar
    }
    
    return 'python'; // Fallback
  },
  
  // Desktop Installation
  installDesktopApp() {
    return new Promise((resolve) => {
      try {
        const projectRoot = path.resolve(__dirname, '..', '..');
        const electronPath = require('electron');
        const startScript = path.join(projectRoot, 'gui-electron', 'start-gui-electron.bat');
        const shortcutPath = path.join(
          os.homedir(),
          'AppData',
          'Roaming',
          'Microsoft',
          'Windows',
          'Start Menu',
          'Programs',
          'Simple Computer Use Desktop.lnk'
        );
        
        // Crear shortcut usando PowerShell
        const psScript = `
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("${shortcutPath}")
$Shortcut.TargetPath = "${electronPath}"
$Shortcut.WorkingDirectory = "${path.join(projectRoot, 'gui-electron')}"
$Shortcut.IconLocation = "${path.join(projectRoot, 'gui-electron', 'ic_launcher-playstore.png')}"
$Shortcut.Save()
`;
        
        execSync(`powershell -Command "${psScript}"`, { stdio: 'ignore' });
        resolve({ success: true, message: 'Application installed to Start Menu' });
      } catch (error) {
        resolve({ success: false, error: error.message });
      }
    });
  }
};
```

#### 3. Ejemplo: `platform/linux.js` (Ya existe, solo mover código)

```javascript
// Mover código actual de main.js aquí
module.exports = {
  installStartupService: function() { /* código actual */ },
  getProcessUsingPort: function() { /* código actual */ },
  // ... etc
};
```

#### 4. Uso en `main.js`

```javascript
const platformUtils = require('./platform');

// Reemplazar todas las llamadas
ipcMain.handle('install-startup-service', () => {
  return platformUtils.installStartupService();
});

ipcMain.handle('get-process-using-port', (event, port) => {
  return platformUtils.getProcessUsingPort(port);
});
```

---

## 🚀 Estrategia 4: WSL2 (Solo para Windows)

### Cuándo Usar

✅ **Usar WSL2 si**:
- Solo necesitas soporte Windows
- Quieres mantener código Linux sin cambios
- No te importa el overhead de WSL2

### Implementación

```javascript
// main.js
function findPythonExecutable() {
  if (process.platform === 'win32') {
    // Intentar WSL2 primero
    try {
      execSync('wsl --list --quiet', { stdio: 'ignore' });
      // WSL2 disponible, usar wsl python
      return 'wsl python3';
    } catch (e) {
      // WSL2 no disponible, usar Windows Python
    }
  }
  // ... resto del código
}
```

**Ventaja**: Código Linux funciona sin cambios  
**Desventaja**: Requiere WSL2 instalado, más lento

---

## 📝 Plan de Acción Recomendado

### Opción 1: Rápida (1 semana)
1. ✅ Usar **Electron Builder** (ya configurado)
2. ✅ Crear abstracción mínima de plataforma (solo funciones críticas)
3. ✅ Implementar versiones Windows de funciones clave
4. ✅ Build y test

### Opción 2: Completa (2-3 semanas)
1. ✅ Crear módulo completo `platform/`
2. ✅ Implementar todas las funciones para Windows/Mac
3. ✅ Agregar Docker como opción para servidor Python
4. ✅ Testing exhaustivo en todas las plataformas
5. ✅ Documentación y CI/CD

### Opción 3: Híbrida (Recomendada - 1-2 semanas)
1. ✅ **Electron Builder** para distribución
2. ✅ **Abstracción de plataforma** para funciones críticas
3. ✅ **Docker opcional** para servidor Python (si hay problemas)
4. ✅ Testing en Windows/Mac

---

## 🎯 Conclusión

**La manera más fácil**: **Electron Builder + Abstracción de Plataforma**

- ✅ Ya tienes Electron Builder configurado
- ✅ Solo necesitas adaptar ~5-6 funciones
- ✅ Una vez hecho, funciona en todas las plataformas
- ✅ Performance nativa (mejor que Docker)
- ✅ Distribución fácil (un ejecutable por plataforma)

**Docker es útil como complemento** para el servidor Python si hay problemas de dependencias, pero **no para la GUI Electron**.

