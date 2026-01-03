# Implementación: Electron Builder con Ollama Empaquetado

## Resumen

Esta guía muestra cómo empaquetar Ollama junto con tu aplicación Electron, replicando la funcionalidad de Docker pero como aplicación nativa.

## Arquitectura

```
Instalador Electron Builder
├── Electron App (GUI)
├── Python Backend (PyInstaller)
├── Ollama (binario)
└── Scripts de gestión
```

## Paso 1: Preparar Binarios de Ollama

### Descargar Binarios Oficiales

Ollama proporciona binarios para cada plataforma:
- Linux: https://github.com/ollama/ollama/releases
- Windows: https://github.com/ollama/ollama/releases
- macOS: https://github.com/ollama/ollama/releases

### Estructura de Directorios

```
resources/
├── ollama/
│   ├── linux-x64/
│   │   └── ollama
│   ├── win32-x64/
│   │   └── ollama.exe
│   └── darwin-x64/
│       └── ollama
└── python-backend/
    └── (se generará con PyInstaller)
```

## Paso 2: Configurar electron-builder

### Actualizar `package.json`

```json
{
  "build": {
    "appId": "com.llmcontrol.gui",
    "productName": "LLM Control",
    "directories": {
      "output": "dist",
      "buildResources": "build"
    },
    "files": [
      "**/*",
      "!node_modules/**/*",
      "node_modules/electron/**/*",
      "node_modules/axios/**/*",
      "!resources/ollama/**/*"
    ],
    "extraResources": [
      {
        "from": "resources/ollama/${arch}",
        "to": "ollama",
        "filter": ["**/*"]
      },
      {
        "from": "resources/python-backend",
        "to": "python-backend",
        "filter": ["**/*"]
      }
    ],
    "linux": {
      "target": [
        {
          "target": "AppImage",
          "arch": ["x64"]
        },
        {
          "target": "deb",
          "arch": ["x64"]
        }
      ],
      "category": "Utility"
    },
    "win": {
      "target": [
        {
          "target": "nsis",
          "arch": ["x64"]
        }
      ]
    },
    "mac": {
      "target": [
        {
          "target": "dmg",
          "arch": ["x64", "arm64"]
        }
      ]
    }
  }
}
```

## Paso 3: Modificar main.js para Gestionar Ollama

### Agregar Funciones de Gestión de Ollama

```javascript
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let ollamaProcess = null;
let serverProcess = null;

// Obtener ruta del binario Ollama según la plataforma
function getOllamaPath() {
  const platform = process.platform;
  const arch = process.arch;
  const resourcesPath = process.resourcesPath || path.join(__dirname, '..', 'resources');
  
  let ollamaBinary;
  if (platform === 'win32') {
    ollamaBinary = 'ollama.exe';
  } else {
    ollamaBinary = 'ollama';
  }
  
  const ollamaPath = path.join(resourcesPath, 'ollama', ollamaBinary);
  
  // En desarrollo, usar Ollama del sistema si existe
  if (!fs.existsSync(ollamaPath) && process.env.NODE_ENV === 'development') {
    return 'ollama'; // Usar del PATH
  }
  
  return ollamaPath;
}

// Verificar si Ollama está corriendo
async function isOllamaRunning() {
  try {
    const response = await fetch('http://localhost:11434/api/version', {
      method: 'GET',
      signal: AbortSignal.timeout(2000)
    });
    return response.ok;
  } catch (error) {
    return false;
  }
}

// Iniciar Ollama empaquetado
async function startOllama() {
  if (ollamaProcess) {
    return { success: true, message: 'Ollama ya está corriendo' };
  }
  
  // Verificar si ya está corriendo
  if (await isOllamaRunning()) {
    return { success: true, message: 'Ollama ya está corriendo en el sistema' };
  }
  
  try {
    const ollamaPath = getOllamaPath();
    const ollamaDir = path.dirname(ollamaPath);
    
    // Hacer ejecutable en Linux/macOS
    if (process.platform !== 'win32') {
      fs.chmodSync(ollamaPath, 0o755);
    }
    
    console.log(`Iniciando Ollama desde: ${ollamaPath}`);
    
    ollamaProcess = spawn(ollamaPath, ['serve'], {
      cwd: ollamaDir,
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        OLLAMA_HOST: '0.0.0.0:11434'
      }
    });
    
    ollamaProcess.stdout.on('data', (data) => {
      console.log(`[Ollama] ${data.toString()}`);
    });
    
    ollamaProcess.stderr.on('data', (data) => {
      console.error(`[Ollama Error] ${data.toString()}`);
    });
    
    ollamaProcess.on('exit', (code) => {
      console.log(`Ollama process exited with code ${code}`);
      ollamaProcess = null;
    });
    
    // Esperar a que Ollama esté listo
    let attempts = 0;
    const maxAttempts = 30;
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      if (await isOllamaRunning()) {
        return { success: true, message: 'Ollama iniciado correctamente' };
      }
      attempts++;
    }
    
    return { success: false, error: 'Ollama no respondió a tiempo' };
    
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Detener Ollama
function stopOllama() {
  if (!ollamaProcess) {
    return { success: true, message: 'Ollama no está corriendo' };
  }
  
  try {
    ollamaProcess.kill('SIGTERM');
    
    // Esperar un poco y forzar si es necesario
    setTimeout(() => {
      if (ollamaProcess && ollamaProcess.exitCode === null) {
        ollamaProcess.kill('SIGKILL');
      }
    }, 3000);
    
    ollamaProcess = null;
    return { success: true, message: 'Ollama detenido' };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Verificar modelo de Ollama
async function checkOllamaModel(modelName = 'llama3.1') {
  try {
    const response = await fetch('http://localhost:11434/api/tags');
    const data = await response.json();
    const models = data.models || [];
    return models.some(m => m.name.includes(modelName));
  } catch (error) {
    return false;
  }
}

// Descargar modelo si no existe
async function pullOllamaModel(modelName = 'llama3.1') {
  const ollamaPath = getOllamaPath();
  
  return new Promise((resolve) => {
    const pullProcess = spawn(ollamaPath, ['pull', modelName], {
      stdio: 'inherit'
    });
    
    pullProcess.on('exit', (code) => {
      resolve(code === 0);
    });
  });
}

// IPC Handlers
ipcMain.handle('start-ollama', async () => {
  return await startOllama();
});

ipcMain.handle('stop-ollama', () => {
  return stopOllama();
});

ipcMain.handle('is-ollama-running', async () => {
  return await isOllamaRunning();
});

ipcMain.handle('check-ollama-model', async (event, modelName) => {
  return await checkOllamaModel(modelName);
});

ipcMain.handle('pull-ollama-model', async (event, modelName) => {
  return await pullOllamaModel(modelName);
});

// Iniciar Ollama automáticamente al iniciar la app
app.whenReady().then(async () => {
  // Esperar un poco antes de iniciar Ollama
  setTimeout(async () => {
    const result = await startOllama();
    if (result.success) {
      console.log('Ollama iniciado automáticamente');
    } else {
      console.warn('No se pudo iniciar Ollama automáticamente:', result.error);
    }
  }, 2000);
});

// Detener Ollama al cerrar la app
app.on('before-quit', () => {
  stopOllama();
  if (serverProcess) {
    serverProcess.kill();
  }
});
```

## Paso 4: Actualizar startServer en main.js

Modificar la función `startServer` para usar Ollama empaquetado:

```javascript
async function startServer(config) {
  // Asegurarse de que Ollama está corriendo
  if (!await isOllamaRunning()) {
    const ollamaResult = await startOllama();
    if (!ollamaResult.success) {
      return { 
        success: false, 
        error: `No se pudo iniciar Ollama: ${ollamaResult.error}` 
      };
    }
  }
  
  // Verificar modelo
  const modelExists = await checkOllamaModel(config.ollama_model || 'llama3.1');
  if (!modelExists) {
    // Opcional: ofrecer descargar el modelo
    console.warn(`Modelo ${config.ollama_model} no encontrado`);
  }
  
  // Continuar con el inicio del servidor Python como antes
  // ... resto del código existente
}
```

## Paso 5: Script de Build

### Crear `scripts/build.js`

```javascript
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const https = require('https');

// Descargar binarios de Ollama
async function downloadOllamaBinaries() {
  const version = 'v0.1.0'; // Versión de Ollama a usar
  const platforms = {
    'linux-x64': `ollama-linux-amd64`,
    'win32-x64': `ollama-windows-amd64.exe`,
    'darwin-x64': `ollama-darwin-amd64`,
    'darwin-arm64': `ollama-darwin-arm64`
  };
  
  const resourcesDir = path.join(__dirname, '..', 'resources', 'ollama');
  
  for (const [platform, binaryName] of Object.entries(platforms)) {
    const platformDir = path.join(resourcesDir, platform);
    if (!fs.existsSync(platformDir)) {
      fs.mkdirSync(platformDir, { recursive: true });
    }
    
    const url = `https://github.com/ollama/ollama/releases/download/${version}/${binaryName}`;
    const outputPath = path.join(platformDir, platform.includes('win') ? 'ollama.exe' : 'ollama');
    
    console.log(`Descargando Ollama para ${platform}...`);
    // Implementar descarga (usar axios o similar)
  }
}

// Build con PyInstaller
function buildPythonBackend() {
  console.log('Empaquetando backend Python...');
  execSync('pyinstaller --onefile --name llm-control-server llm_control/__main__.py', {
    cwd: path.join(__dirname, '..'),
    stdio: 'inherit'
  });
  
  // Mover a resources
  const distPath = path.join(__dirname, '..', 'dist', 'llm-control-server');
  const resourcesPath = path.join(__dirname, '..', 'resources', 'python-backend');
  if (!fs.existsSync(resourcesPath)) {
    fs.mkdirSync(resourcesPath, { recursive: true });
  }
  fs.copyFileSync(distPath, path.join(resourcesPath, 'llm-control-server'));
}

// Build Electron
function buildElectron() {
  console.log('Construyendo aplicación Electron...');
  execSync('npm run build', {
    cwd: path.join(__dirname, '..', 'gui-electron'),
    stdio: 'inherit'
  });
}

// Ejecutar todo
async function build() {
  try {
    await downloadOllamaBinaries();
    buildPythonBackend();
    buildElectron();
    console.log('✅ Build completado');
  } catch (error) {
    console.error('❌ Error en build:', error);
    process.exit(1);
  }
}

build();
```

## Paso 6: Actualizar package.json Scripts

```json
{
  "scripts": {
    "build": "node scripts/build.js",
    "build:linux": "electron-builder --linux",
    "build:win": "electron-builder --win",
    "build:mac": "electron-builder --mac",
    "build:all": "npm run build:linux && npm run build:win && npm run build:mac"
  }
}
```

## Resultado Final

Con esta implementación:

1. ✅ **Ollama está empaquetado** - No requiere instalación separada
2. ✅ **Python está empaquetado** - No requiere Python en el sistema
3. ✅ **Todo funciona como Docker** - Pero como aplicación nativa
4. ✅ **Experiencia de usuario perfecta** - Un solo instalador, todo incluido

## Ventajas sobre Docker

- ✅ No requiere Docker instalado
- ✅ Instalación más simple (doble clic)
- ✅ Mejor integración con el sistema
- ✅ Actualizaciones automáticas opcionales
- ✅ Mismo resultado: todo empaquetado y funcionando

## Notas

- Los modelos de Ollama se descargan en runtime (no se empaquetan)
- Ollama puede usar GPU si está disponible (igual que en Docker)
- El tamaño del instalador será grande (~500MB-1GB) pero todo está incluido

