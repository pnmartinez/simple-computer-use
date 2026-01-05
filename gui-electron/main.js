const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const os = require('os');

let mainWindow;
let serverProcess = null;
let ollamaProcess = null;
let serverConfig = null;
let tray = null;
let isQuitting = false;

// Check if running in packaged mode
const isPackaged = app.isPackaged || process.env.ELECTRON_IS_PACKAGED === 'true';

// #region agent log
// Log AppImage detection at startup
if (isPackaged) {
  const isAppImage = !!process.env.APPIMAGE;
  const appDir = process.env.APPDIR;
  fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:16',message:'App startup packaged detection',data:{isPackaged,isAppImage,APPIMAGE:process.env.APPIMAGE,APPDIR:process.env.APPDIR,resourcesPath:process.resourcesPath,platform:process.platform,arch:process.arch,execPath:process.execPath,__dirname},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
}
// #endregion

function notifyServerStarted() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }

  const sendStarted = () => {
    if (!mainWindow || mainWindow.isDestroyed()) {
      return;
    }
    mainWindow.webContents.send('server-started');
  };

  if (mainWindow.webContents.isLoading()) {
    mainWindow.webContents.once('did-finish-load', sendStarted);
  } else {
    sendStarted();
  }
}

// Load configuration
function loadConfig() {
  const configPath = path.join(os.homedir(), '.simple-computer-use-desktop-config.json');
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch (error) {
    console.error('Error loading config:', error);
  }
  return getDefaultConfig();
}

// Save configuration
function saveConfig(config) {
  const configPath = path.join(os.homedir(), '.simple-computer-use-desktop-config.json');
  try {
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
    return true;
  } catch (error) {
    console.error('Error saving config:', error);
    return false;
  }
}

// Get default configuration
// Based on start-llm-control.sh (systemd service)
function getDefaultConfig() {
  // Use writable directory for screenshots in packaged mode
  const defaultScreenshotDir = isPackaged 
    ? path.join(os.homedir(), '.llm-control', 'screenshots')
    : './screenshots';
  
  return {
    host: '0.0.0.0',
    port: 5000,
    ssl: true,  // SSL enabled - matches start-llm-control.sh
    ssl_cert: '',
    ssl_key: '',
    whisper_model: 'large',  // Matches start-llm-control.sh
    ollama_model: 'gemma3:12b',  // Matches start-llm-control.sh (not llama3.1)
    ollama_host: 'http://localhost:11434',
    language: 'es',
    translation_enabled: false,  // Disabled - matches --disable-translation
    screenshots_enabled: true,
    screenshot_dir: defaultScreenshotDir,
    failsafe_enabled: false,
    debug: false
  };
}

// Get Ollama binary path
function getOllamaPath() {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:88',message:'getOllamaPath entry',data:{isPackaged,platform:process.platform,arch:process.arch,APPIMAGE:process.env.APPIMAGE,APPDIR:process.env.APPDIR,resourcesPath:process.resourcesPath,__dirname},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  if (isPackaged) {
    // In packaged mode, use bundled Ollama
    // #region agent log
    const isAppImage = !!process.env.APPIMAGE;
    const appDir = process.env.APPDIR;
    // #endregion
    // AppImage-specific path resolution
    let resourcesPath;
    if (isAppImage && appDir) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:95',message:'AppImage detected',data:{APPIMAGE:process.env.APPIMAGE,APPDIR:process.env.APPDIR},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      // In AppImage, resources are at $APPDIR/resources/
      resourcesPath = path.join(appDir, 'resources');
    } else {
      resourcesPath = process.resourcesPath || path.join(__dirname, '..', 'resources');
    }
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:102',message:'resourcesPath resolved',data:{resourcesPath,exists:fs.existsSync(resourcesPath),isAppImage},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    const platform = process.platform;
    const arch = process.arch;
    
    let platformDir;
    if (platform === 'win32') {
      platformDir = 'win32-x64';
    } else if (platform === 'darwin') {
      platformDir = arch === 'arm64' ? 'darwin-arm64' : 'darwin-x64';
    } else {
      platformDir = 'linux-x64';
    }
    
    const ollamaBinary = platform === 'win32' ? 'ollama.exe' : 'ollama';
    // electron-builder puts resources in ollama/${platformDir}/
    const ollamaPath = path.join(resourcesPath, 'ollama', platformDir, ollamaBinary);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:115',message:'ollamaPath primary check',data:{ollamaPath,exists:fs.existsSync(ollamaPath),platformDir},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    if (fs.existsSync(ollamaPath)) {
      // #region agent log
      try{const stats=fs.statSync(ollamaPath);fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:118',message:'ollamaPath found',data:{ollamaPath,isFile:stats.isFile(),mode:stats.mode.toString(8),executable:(stats.mode&0o111)!==0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});}catch(e){}
      // #endregion
      return ollamaPath;
    }
    
    // Try alternative path structure (if platformDir structure doesn't exist)
    const altPath = path.join(resourcesPath, 'ollama', ollamaBinary);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:123',message:'ollamaPath alt check',data:{altPath,exists:fs.existsSync(altPath)},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    if (fs.existsSync(altPath)) {
      // #region agent log
      try{const stats=fs.statSync(altPath);fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:126',message:'ollamaPath alt found',data:{altPath,isFile:stats.isFile(),mode:stats.mode.toString(8),executable:(stats.mode&0o111)!==0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});}catch(e){}
      // #endregion
      return altPath;
    }
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:130',message:'ollamaPath not found, listing resources',data:{resourcesPath,ollamaDir:path.join(resourcesPath,'ollama'),ollamaDirExists:fs.existsSync(path.join(resourcesPath,'ollama')),list:fs.existsSync(path.join(resourcesPath,'ollama'))?fs.readdirSync(path.join(resourcesPath,'ollama')).join(','):'N/A'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
  }
  
  // Fallback to system Ollama
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:135',message:'getOllamaPath fallback to system',data:{},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  return 'ollama';
}

// Check if Ollama is running
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

// Start Ollama (packaged or system)
async function startOllama() {
  if (ollamaProcess) {
    return { success: true, message: 'Ollama ya está corriendo' };
  }
  
  // Check if already running
  if (await isOllamaRunning()) {
    // Ollama is already running, ensure the default model is available
    const config = serverConfig || getDefaultConfig();
        const defaultModel = config.ollama_model || 'gemma3:12b';
    
    console.log(`Verificando modelo por defecto: ${defaultModel}`);
    const modelResult = await ensureOllamaModel(defaultModel);
    
    if (!modelResult.success) {
      console.warn(`Advertencia: No se pudo descargar el modelo ${defaultModel}: ${modelResult.error}`);
      console.warn('El usuario puede descargarlo manualmente más tarde');
    }
    
    return { 
      success: true, 
      message: 'Ollama ya está corriendo en el sistema' + (modelResult.success ? ` (modelo ${defaultModel} disponible)` : ` (modelo ${defaultModel} no disponible)`)
    };
  }
  
  try {
    const ollamaPath = getOllamaPath();
    const ollamaDir = path.dirname(ollamaPath);
    
    // Make executable on Unix
    if (process.platform !== 'win32' && fs.existsSync(ollamaPath)) {
      try {
        fs.chmodSync(ollamaPath, 0o755);
      } catch (e) {
        // Ignore chmod errors
      }
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
    
    // Wait for Ollama to be ready
    let attempts = 0;
    const maxAttempts = 30;
    
    while (attempts < maxAttempts) {
      await new Promise(resolve => setTimeout(resolve, 1000));
      if (await isOllamaRunning()) {
        // Ollama is running, now ensure the default model is available
        const config = serverConfig || getDefaultConfig();
        const defaultModel = config.ollama_model || 'gemma3:12b';
        
        console.log(`Verificando modelo por defecto: ${defaultModel}`);
        const modelResult = await ensureOllamaModel(defaultModel);
        
        if (!modelResult.success) {
          console.warn(`Advertencia: No se pudo descargar el modelo ${defaultModel}: ${modelResult.error}`);
          console.warn('El usuario puede descargarlo manualmente más tarde');
          // Don't fail the start, just warn - user can pull manually later
        }
        
        return { 
          success: true, 
          message: 'Ollama iniciado correctamente' + (modelResult.success ? ` (modelo ${defaultModel} disponible)` : ` (modelo ${defaultModel} no disponible)`)
        };
      }
      attempts++;
    }
    
    return { success: false, error: 'Ollama no respondió a tiempo' };
    
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Stop Ollama
function stopOllama() {
  if (!ollamaProcess) {
    return { success: true, message: 'Ollama no está corriendo' };
  }
  
  try {
    ollamaProcess.kill('SIGTERM');
    
    // Wait a bit and force if necessary
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

// Check if an Ollama model exists
async function checkOllamaModel(modelName) {
  try {
    const response = await fetch('http://localhost:11434/api/tags', {
      method: 'GET',
      signal: AbortSignal.timeout(5000)
    });
    
    if (!response.ok) {
      return false;
    }
    
    const data = await response.json();
    const models = data.models || [];
    
    // Check if model exists (exact match or starts with model name)
    return models.some(m => {
      const name = m.name || '';
      return name === modelName || name.startsWith(modelName + ':');
    });
  } catch (error) {
    console.error(`Error checking Ollama model: ${error.message}`);
    return false;
  }
}

// Pull an Ollama model
async function pullOllamaModel(modelName, ollamaPath) {
  return new Promise((resolve) => {
    console.log(`Descargando modelo Ollama: ${modelName}...`);
    
    // Notify GUI that pull is starting
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('ollama-pull-start', { model: modelName });
    }
    
    const pullProcess = spawn(ollamaPath, ['pull', modelName], {
      stdio: ['ignore', 'pipe', 'pipe']
    });
    
    let output = '';
    let errorOutput = '';
    let lastProgress = { percent: 0, status: 'Iniciando descarga...' };
    
    // Parse progress from Ollama output
    function parseProgress(text) {
      const lines = text.split('\n').filter(l => l.trim());
      let percent = 0;
      let status = '';
      
      for (const line of lines) {
        // Match patterns like "downloading xxxx [====>] 50.0%"
        const percentMatch = line.match(/(\d+\.?\d*)%/);
        if (percentMatch) {
          percent = parseFloat(percentMatch[1]);
        }
        
        // Match status messages
        if (line.includes('pulling manifest')) {
          status = 'Descargando manifest...';
        } else if (line.includes('pulling')) {
          const pullMatch = line.match(/pulling\s+([^\s]+)/);
          if (pullMatch) {
            status = `Descargando ${pullMatch[1]}...`;
          }
        } else if (line.includes('downloading')) {
          const downloadMatch = line.match(/downloading\s+([^\s]+)/);
          if (downloadMatch) {
            status = `Descargando ${downloadMatch[1]}...`;
          }
        } else if (line.includes('verifying')) {
          status = 'Verificando descarga...';
        } else if (line.includes('writing')) {
          status = 'Escribiendo archivos...';
        } else if (line.includes('success')) {
          status = 'Descarga completada';
        }
      }
      
      return { percent, status: status || lastProgress.status };
    }
    
    pullProcess.stdout.on('data', (data) => {
      const text = data.toString();
      output += text;
      console.log(`[Ollama Pull] ${text.trim()}`);
      
      // Parse and send progress updates
      const progress = parseProgress(text);
      if (progress.percent > lastProgress.percent || progress.status !== lastProgress.status) {
        lastProgress = progress;
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('ollama-pull-progress', {
            model: modelName,
            percent: progress.percent,
            status: progress.status,
            message: text.trim()
          });
        }
      }
    });
    
    pullProcess.stderr.on('data', (data) => {
      const text = data.toString();
      errorOutput += text;
      console.error(`[Ollama Pull Error] ${text.trim()}`);
      
      // Ollama also sends progress to stderr
      const progress = parseProgress(text);
      if (progress.percent > lastProgress.percent || progress.status !== lastProgress.status) {
        lastProgress = progress;
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('ollama-pull-progress', {
            model: modelName,
            percent: progress.percent,
            status: progress.status,
            message: text.trim()
          });
        }
      }
    });
    
    pullProcess.on('exit', (code) => {
      if (code === 0) {
        console.log(`✓ Modelo ${modelName} descargado correctamente`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('ollama-pull-complete', {
            model: modelName,
            success: true,
            message: `Modelo ${modelName} descargado correctamente`
          });
        }
        resolve({ success: true, message: `Modelo ${modelName} descargado correctamente` });
      } else {
        const errorMsg = errorOutput || `Código de salida: ${code}`;
        console.error(`✗ Error al descargar modelo ${modelName}: ${errorMsg}`);
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('ollama-pull-complete', {
            model: modelName,
            success: false,
            error: errorMsg
          });
        }
        resolve({ success: false, error: errorMsg });
      }
    });
    
    pullProcess.on('error', (error) => {
      console.error(`✗ Error al ejecutar ollama pull: ${error.message}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('ollama-pull-complete', {
          model: modelName,
          success: false,
          error: error.message
        });
      }
      resolve({ success: false, error: error.message });
    });
  });
}

// Ensure an Ollama model is available (check and pull if needed)
async function ensureOllamaModel(modelName) {
  if (!modelName) {
    return { success: false, error: 'Nombre de modelo no especificado' };
  }
  
  // Check if model exists
  const exists = await checkOllamaModel(modelName);
  
  if (exists) {
    console.log(`✓ Modelo ${modelName} ya está disponible`);
    return { success: true, message: `Modelo ${modelName} ya está disponible` };
  }
  
  // Model doesn't exist, try to pull it
  const ollamaPath = getOllamaPath();
  
  if (!fs.existsSync(ollamaPath)) {
    return { success: false, error: `Binario de Ollama no encontrado en: ${ollamaPath}` };
  }
  
  // Make executable on Unix
  if (process.platform !== 'win32') {
    try {
      fs.chmodSync(ollamaPath, 0o755);
    } catch (e) {
      // Ignore chmod errors
    }
  }
  
  console.log(`Modelo ${modelName} no encontrado, descargando...`);
  return await pullOllamaModel(modelName, ollamaPath);
}

// Find Python executable
// Priority: packaged > venv-py312 > system python
function findPythonExecutable() {
  // #region agent log
  fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:361',message:'findPythonExecutable entry',data:{isPackaged,APPIMAGE:process.env.APPIMAGE,APPDIR:process.env.APPDIR,resourcesPath:process.resourcesPath},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
  // #endregion
  if (isPackaged) {
    // In packaged mode, use bundled Python executable
    // process.resourcesPath works cross-platform (Linux, Windows, macOS)
    // #region agent log
    const isAppImage = !!process.env.APPIMAGE;
    const appDir = process.env.APPDIR;
    // #endregion
    // AppImage-specific path resolution
    let resourcesPath;
    if (isAppImage && appDir) {
      // #region agent log
      fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:371',message:'AppImage detected in findPython',data:{APPIMAGE:process.env.APPIMAGE,APPDIR:process.env.APPDIR},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'B'})}).catch(()=>{});
      // #endregion
      // In AppImage, resources are at $APPDIR/resources/
      resourcesPath = path.join(appDir, 'resources');
    } else {
      resourcesPath = process.resourcesPath;
      // Fallback for cross-platform compatibility
      if (!resourcesPath) {
        // Try app.getAppPath() if available (Electron API)
        try {
          const { app } = require('electron');
          resourcesPath = app.getAppPath();
        } catch (e) {
          // Final fallback
          resourcesPath = path.join(__dirname, '..', 'resources');
        }
      }
    }
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:388',message:'python resourcesPath resolved',data:{resourcesPath,exists:fs.existsSync(resourcesPath),isAppImage},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'A'})}).catch(()=>{});
    // #endregion
    
    const pythonBinary = process.platform === 'win32' 
      ? 'simple-computer-use-server.exe' 
      : 'simple-computer-use-server';
    // Try directory structure first (onedir mode)
    const pythonDir = path.join(resourcesPath, 'python-backend', 'simple-computer-use-server');
    const pythonPathInDir = path.join(pythonDir, pythonBinary);
    // Try direct executable (onefile mode)
    const pythonPath = path.join(resourcesPath, 'python-backend', pythonBinary);
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:397',message:'python paths check',data:{pythonPathInDir,existsInDir:fs.existsSync(pythonPathInDir),pythonPath,exists:fs.existsSync(pythonPath),pythonBackendDir:path.join(resourcesPath,'python-backend'),pythonBackendExists:fs.existsSync(path.join(resourcesPath,'python-backend')),list:fs.existsSync(path.join(resourcesPath,'python-backend'))?fs.readdirSync(path.join(resourcesPath,'python-backend')).join(','):'N/A'},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'C'})}).catch(()=>{});
    // #endregion
    
    // Prefer directory structure (onedir)
    if (fs.existsSync(pythonPathInDir)) {
      // #region agent log
      try{const stats=fs.statSync(pythonPathInDir);fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:400',message:'pythonPathInDir found',data:{pythonPathInDir,isFile:stats.isFile(),mode:stats.mode.toString(8),executable:(stats.mode&0o111)!==0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});}catch(e){}
      // #endregion
      if (process.platform !== 'win32') {
        try {
          fs.chmodSync(pythonPathInDir, 0o755);
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:405',message:'pythonPathInDir chmod applied',data:{pythonPathInDir},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
          // #endregion
        } catch (e) {
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:408',message:'pythonPathInDir chmod failed',data:{pythonPathInDir,error:e.message},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
          // #endregion
        }
      }
      return pythonPathInDir;
    }
    
    // Fallback to direct executable
    if (fs.existsSync(pythonPath)) {
      // #region agent log
      try{const stats=fs.statSync(pythonPath);fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:415',message:'pythonPath found',data:{pythonPath,isFile:stats.isFile(),mode:stats.mode.toString(8),executable:(stats.mode&0o111)!==0},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});}catch(e){}
      // #endregion
      if (process.platform !== 'win32') {
        try {
          fs.chmodSync(pythonPath, 0o755);
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:420',message:'pythonPath chmod applied',data:{pythonPath},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
          // #endregion
        } catch (e) {
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:423',message:'pythonPath chmod failed',data:{pythonPath,error:e.message},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'D'})}).catch(()=>{});
          // #endregion
        }
      }
      return pythonPath;
    }
    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/4b6cf5b3-8ac5-4053-9840-3da344c30971',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:'main.js:429',message:'python executable not found in packaged mode',data:{resourcesPath,pythonBackendDir:path.join(resourcesPath,'python-backend')},timestamp:Date.now(),sessionId:'debug-session',runId:'run1',hypothesisId:'E'})}).catch(()=>{});
    // #endregion
  }
  
  // Development mode: try venv first
  const projectRoot = path.resolve(__dirname, '..');
  const venvPython = path.join(projectRoot, 'venv-py312', 'bin', 'python');
  
  if (fs.existsSync(venvPython)) {
    try {
      require('child_process').execSync(`"${venvPython}" --version`, { encoding: 'utf8' });
      return venvPython;
    } catch (e) {
      console.warn('venv-py312 Python found but not working, trying system Python');
    }
  }
  
  // Fallback: system Python
  const pythonCommands = ['python3', 'python'];
  for (const cmd of pythonCommands) {
    try {
      const result = require('child_process').execSync(`which ${cmd}`, { encoding: 'utf8' }).trim();
      if (result) return cmd;
    } catch (e) {
      // Continue to next
    }
  }
  return 'python3'; // Default fallback
}

// Check if port is in use
function isPortInUse(port) {
  try {
    const net = require('net');
    return new Promise((resolve) => {
      const server = net.createServer();
      server.listen(port, () => {
        server.once('close', () => resolve(false));
        server.close();
      });
      server.on('error', () => resolve(true));
    });
  } catch (e) {
    return Promise.resolve(false);
  }
}

// Start server
async function startServer(config) {
  // If server is already running, stop it first to ensure clean restart with new config
  if (serverProcess) {
    console.log('Server is already running, stopping it first to apply new configuration...');
    await stopServer();
    // Wait a bit to ensure the process is fully terminated
    await new Promise(resolve => setTimeout(resolve, 1500));
  }
  if (serverProcess) {
    return { success: false, error: 'Server is already running' };
  }
  
  // Check if port is already in use
  const portInUse = await isPortInUse(config.port || 5000);
  if (portInUse) {
    return { 
      success: false, 
      error: `Port ${config.port || 5000} is already in use. Please stop the existing server or use a different port.` 
    };
  }

  try {
    // Ensure Ollama is running
    if (!await isOllamaRunning()) {
      console.log('Ollama no está corriendo, iniciando...');
      const ollamaResult = await startOllama();
      if (!ollamaResult.success) {
        console.warn(`No se pudo iniciar Ollama: ${ollamaResult.error}`);
        // Continue anyway, user might have Ollama running externally
      }
    }
    
    const pythonCmd = findPythonExecutable();
    // Get project root (parent of gui-electron directory)
    const projectRoot = path.resolve(__dirname, '..');
    
    // Prepare environment variables (same as start-llm-control.sh)
    const env = Object.assign({}, process.env);
    env.STRUCTURED_USAGE_LOGS = 'true';
    
    // Detect and set XAUTHORITY if not already set
    if (!env.XAUTHORITY) {
      const userId = process.getuid ? process.getuid() : (process.env.USER_ID || '1000');
      const xauthPaths = [
        path.join(os.homedir(), '.Xauthority'),
        `/run/user/${userId}/gdm/Xauthority`,
        `/run/user/${userId}/.Xauthority`,
        `/var/run/gdm3/${userId}/.Xauthority`
      ];
      
      for (const xauthPath of xauthPaths) {
        if (fs.existsSync(xauthPath)) {
          env.XAUTHORITY = xauthPath;
          console.log(`Found XAUTHORITY at: ${xauthPath}`);
          break;
        }
      }
    }
    
    // Create symlink/copy of XAUTHORITY to ~/.Xauthority for Xlib compatibility
    // Xlib hardcodes ~/.Xauthority and doesn't respect XAUTHORITY env var
    if (env.XAUTHORITY) {
      const homeXauth = path.join(os.homedir(), '.Xauthority');
      const xauthSource = env.XAUTHORITY;
      
      // Only create symlink if source is not already ~/.Xauthority
      if (xauthSource !== homeXauth) {
        try {
          // Remove existing file/symlink if it exists
          if (fs.existsSync(homeXauth)) {
            const stats = fs.lstatSync(homeXauth);
            if (stats.isSymbolicLink()) {
              fs.unlinkSync(homeXauth);
            } else {
              // If it's a regular file, back it up and replace
              fs.renameSync(homeXauth, `${homeXauth}.backup`);
            }
          }
          
          // Create symlink to the actual XAUTHORITY file
          fs.symlinkSync(xauthSource, homeXauth);
          console.log(`Created XAUTHORITY symlink: ${homeXauth} -> ${xauthSource}`);
        } catch (error) {
          // If symlink fails, try copying the file instead
          try {
            fs.copyFileSync(xauthSource, homeXauth);
            fs.chmodSync(homeXauth, 0o600); // Set proper permissions
            console.log(`Copied XAUTHORITY file: ${homeXauth} <- ${xauthSource}`);
          } catch (copyError) {
            console.warn(`Failed to create XAUTHORITY symlink/copy: ${copyError.message}`);
          }
        }
      }
    }
    
    // Ensure DISPLAY is set if not already set
    if (!env.DISPLAY) {
      // Try common display values
      const commonDisplays = [':0', ':1', ':10'];
      for (const display of commonDisplays) {
        env.DISPLAY = display;
        break; // Use first one as default
      }
    }
    
    // Set writable directories for packaged mode
    if (isPackaged) {
      const logDir = path.join(os.homedir(), '.llm-control', 'structured_logs');
      env.STRUCTURED_LOGS_DIR = logDir;
      
      // Set screenshot directory if not explicitly configured or is default
      if (!config.screenshot_dir || config.screenshot_dir === './screenshots') {
        const screenshotDir = path.join(os.homedir(), '.llm-control', 'screenshots');
        env.SCREENSHOT_DIR = screenshotDir;
        // Override config to use writable directory
        config.screenshot_dir = screenshotDir;
      }
      
      // Set history directory for packaged mode
      const historyDir = path.join(os.homedir(), '.llm-control', 'history');
      env.HISTORY_DIR = historyDir;
    }
    
    // If using venv, ensure PATH includes venv bin
    if (pythonCmd.includes('venv-py312')) {
      const venvBin = path.join(projectRoot, 'venv-py312', 'bin');
      env.PATH = `${venvBin}:${env.PATH}`;
    }
    
    // Build arguments
    let args;
    if (isPackaged && pythonCmd.includes('simple-computer-use-server')) {
      // Packaged mode: use direct executable with arguments
      args = [
        'voice-server',
        '--host', config.host || '0.0.0.0',
        '--port', String(config.port || 5000)
      ];
    } else {
      // Development mode: use python -m
      args = [
        '-m', 'llm_control', 'voice-server',
        '--host', config.host || '0.0.0.0',
        '--port', String(config.port || 5000)
      ];
    }

    if (config.ssl) {
      args.push('--ssl');
    }
    if (config.ssl_cert && config.ssl_key) {
      args.push('--ssl-cert', config.ssl_cert);
      args.push('--ssl-key', config.ssl_key);
    }
    if (config.whisper_model) {
      args.push('--whisper-model', config.whisper_model);
    }
    if (config.ollama_model) {
      args.push('--ollama-model', config.ollama_model);
    }
    if (config.ollama_host) {
      args.push('--ollama-host', config.ollama_host);
    }
    if (!config.translation_enabled) {
      args.push('--disable-translation');
    }
    if (config.language) {
      args.push('--language', config.language);
    }
    if (!config.screenshots_enabled) {
      args.push('--disable-screenshots');
    }
    if (config.failsafe_enabled) {
      args.push('--enable-failsafe');
    }
    // Only pass screenshot-dir if explicitly set (not default)
    // In packaged mode, we use SCREENSHOT_DIR env var instead
    if (config.screenshot_dir && (!isPackaged || config.screenshot_dir !== './screenshots')) {
      args.push('--screenshot-dir', config.screenshot_dir);
    }
    if (config.debug) {
      args.push('--debug');
    }

    serverProcess = spawn(pythonCmd, args, {
      cwd: projectRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
      env: env
    });

    serverConfig = config;
    notifyServerStarted();

    // Handle stdout
    serverProcess.stdout.on('data', (data) => {
      if (mainWindow) {
        mainWindow.webContents.send('server-log', data.toString());
      }
    });

    // Handle stderr
    serverProcess.stderr.on('data', (data) => {
      if (mainWindow) {
        mainWindow.webContents.send('server-log', data.toString());
      }
    });

    // Handle process exit
    serverProcess.on('exit', (code) => {
      const proc = serverProcess;
      serverProcess = null;
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('server-stopped', code);
      }
      console.log(`Server process exited with code ${code}`);
    });
    
    // Handle process errors
    serverProcess.on('error', (error) => {
      console.error('Server process error:', error);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('server-log', `ERROR: ${error.message}\n`);
      }
    });

    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Stop server
function stopServer() {
  if (!serverProcess) {
    return { success: false, error: 'Server is not running' };
  }

  return new Promise((resolve) => {
    try {
      const proc = serverProcess;
      serverProcess = null; // Clear reference immediately
      
      // Try graceful shutdown first
      proc.kill('SIGTERM');
      
      let killed = false;
      
      // Wait for process to exit (max 3 seconds)
      const timeout = setTimeout(() => {
        if (!killed && proc && proc.exitCode === null) {
          console.log('Process did not terminate gracefully, forcing kill...');
          try {
            proc.kill('SIGKILL');
          } catch (e) {
            console.error('Error killing process:', e);
          }
          killed = true;
          resolve({ success: true });
        }
      }, 3000);
      
      // Handle process exit
      proc.on('exit', (code) => {
        if (!killed) {
          clearTimeout(timeout);
          killed = true;
          console.log(`Server process exited with code ${code}`);
          resolve({ success: true });
        }
      });
      
      // If process already exited
      if (proc.exitCode !== null) {
        clearTimeout(timeout);
        if (!killed) {
          killed = true;
          resolve({ success: true });
        }
      }
    } catch (error) {
      console.error('Error stopping server:', error);
      resolve({ success: false, error: error.message });
    }
  });
}

// Check if server is running
function isServerRunning() {
  return serverProcess !== null && serverProcess.exitCode === null;
}

// Apply circular mask to an image
function applyCircularMask(image, size) {
  try {
    const img = image.resize({ width: size, height: size });
    const imgData = img.toBitmap();
    const channels = 4; // RGBA
    const centerX = size / 2;
    const centerY = size / 2;
    const radius = size / 2;
    
    // Create a new buffer with circular mask
    const newData = Buffer.from(imgData);
    
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const dx = x - centerX;
        const dy = y - centerY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        
        const index = (y * size + x) * channels;
        
        // If pixel is outside the circle, make it transparent
        if (distance > radius) {
          newData[index + 3] = 0; // Set alpha to 0 (transparent)
        }
      }
    }
    
    return nativeImage.createFromBuffer(newData, {
      width: size,
      height: size
    });
  } catch (error) {
    console.error('Error applying circular mask:', error);
    return image;
  }
}

// System tray functions
function createTray() {
  // Try to load the logo image for the tray icon
  let trayIcon;
  
  try {
    const logoPath = path.join(__dirname, 'ic_launcher-playstore.png');
    if (fs.existsSync(logoPath)) {
      const originalIcon = nativeImage.createFromPath(logoPath);
      // Resize to appropriate tray icon size (usually 16-22px)
      if (!originalIcon.isEmpty()) {
        const traySize = 22;
        trayIcon = applyCircularMask(originalIcon, traySize);
      }
    }
    
    // If logo doesn't work, create a simple colored circle
    if (!trayIcon || trayIcon.isEmpty()) {
      const size = 22;
      const channels = 4; // RGBA
      const data = Buffer.alloc(size * size * channels);
      const centerX = size / 2;
      const centerY = size / 2;
      const radius = size / 2;
      
      // Fill with a light blue color (RGBA) in a circular shape
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const dx = x - centerX;
          const dy = y - centerY;
          const distance = Math.sqrt(dx * dx + dy * dy);
          const index = (y * size + x) * channels;
          
          if (distance <= radius) {
            data[index] = 52;     // R
            data[index + 1] = 152; // G
            data[index + 2] = 219; // B
            data[index + 3] = 255; // A (opaque)
          } else {
            // Transparent outside circle
            data[index] = 0;
            data[index + 1] = 0;
            data[index + 2] = 0;
            data[index + 3] = 0;
          }
        }
      }
      
      trayIcon = nativeImage.createFromBuffer(data, {
        width: size,
        height: size
      });
    }
  } catch (error) {
    console.error('Error creating tray icon:', error);
    // Fallback: create a minimal circular icon
    const size = 22;
    const channels = 4;
    const data = Buffer.alloc(size * size * channels);
    const centerX = size / 2;
    const centerY = size / 2;
    const radius = size / 2;
    
    // Fill with gray in a circular shape
    for (let y = 0; y < size; y++) {
      for (let x = 0; x < size; x++) {
        const dx = x - centerX;
        const dy = y - centerY;
        const distance = Math.sqrt(dx * dx + dy * dy);
        const index = (y * size + x) * channels;
        
        if (distance <= radius) {
          data[index] = 128;     // R
          data[index + 1] = 128; // G
          data[index + 2] = 128; // B
          data[index + 3] = 255; // A
        } else {
          // Transparent outside circle
          data[index] = 0;
          data[index + 1] = 0;
          data[index + 2] = 0;
          data[index + 3] = 0;
        }
      }
    }
    
    trayIcon = nativeImage.createFromBuffer(data, {
      width: size,
      height: size
    });
  }
  
  tray = new Tray(trayIcon);
  
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Window',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
        }
      }
    },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);
  
  tray.setToolTip('Simple Computer Use Desktop');
  tray.setContextMenu(contextMenu);
  
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
      }
    }
  });
}

// Systemd service management
function getServiceName() {
  return 'simple-computer-use-desktop.service';
}

function getServicePath() {
  return path.join(os.homedir(), '.config', 'systemd', 'user', getServiceName());
}

// Detect if running from AppImage
function isRunningFromAppImage() {
  return !!(process.env.APPIMAGE && isPackaged);
}

// Get persistent path for wrapper script
function getWrapperScriptPath() {
  const persistentDir = path.join(os.homedir(), '.local', 'share', 'simple-computer-use-desktop');
  return path.join(persistentDir, 'start-gui-service.sh');
}

function getServiceContent() {
  const isAppImage = isRunningFromAppImage();
  const wrapperScriptPath = getWrapperScriptPath();
  
  let wrapperScript;
  let workingDirectory;
  let appImagePath;
  
  if (isAppImage) {
    // Running from AppImage - use persistent AppImage path
    appImagePath = process.env.APPIMAGE;
    workingDirectory = path.dirname(appImagePath);
    
    // Create wrapper script that executes the AppImage directly
    wrapperScript = `#!/bin/bash
set -e

# Function to wait for X server to be ready
wait_for_x() {
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        # Try to detect DISPLAY
        if [ -z "$DISPLAY" ]; then
            # Try common display values
            for display in ":0" ":1" ":10"; do
                if xset -q -display "$display" >/dev/null 2>&1; then
                    export DISPLAY="$display"
                    break
                fi
            done
        fi
        
        # Check if X server is accessible
        if [ -n "$DISPLAY" ] && xset -q >/dev/null 2>&1; then
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 1
    done
    
    echo "ERROR: X server not available after $max_attempts attempts" >&2
    return 1
}

# Detect XAUTHORITY dynamically
if [ -z "$XAUTHORITY" ]; then
    # Try common XAUTHORITY locations
    for xauth_path in \\
        "$HOME/.Xauthority" \\
        "/run/user/$(id -u)/gdm/Xauthority" \\
        "/run/user/$(id -u)/.Xauthority" \\
        "/var/run/gdm3/\$(id -u)/.Xauthority"; do
        if [ -f "$xauth_path" ]; then
            export XAUTHORITY="$xauth_path"
            break
        fi
    done
fi

# Wait for X server to be ready
wait_for_x || exit 1

# Set service environment variable
export SYSTEMD_SERVICE=1

# Execute AppImage
exec "${appImagePath}"
`;
  } else {
    // Running from source code - use project paths
    const projectRoot = path.resolve(__dirname, '..');
    const guiElectronDir = __dirname;
    workingDirectory = projectRoot;
    
    // Find electron executable
    let electronPath = process.execPath;
    
    // If running from npm/node_modules, try to find the actual electron binary
    if (electronPath.includes('node_modules')) {
      const possiblePaths = [
        path.join(guiElectronDir, 'node_modules', '.bin', 'electron'),
        path.join(projectRoot, 'node_modules', '.bin', 'electron'),
        '/usr/bin/electron',
        '/usr/local/bin/electron'
      ];
      
      for (const possiblePath of possiblePaths) {
        if (fs.existsSync(possiblePath)) {
          electronPath = possiblePath;
          break;
        }
      }
    }
    
    // Create wrapper script for source code execution
    wrapperScript = `#!/bin/bash
set -e

cd "${projectRoot}"
cd gui-electron

# Function to wait for X server to be ready
wait_for_x() {
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        # Try to detect DISPLAY
        if [ -z "$DISPLAY" ]; then
            # Try common display values
            for display in ":0" ":1" ":10"; do
                if xset -q -display "$display" >/dev/null 2>&1; then
                    export DISPLAY="$display"
                    break
                fi
            done
        fi
        
        # Check if X server is accessible
        if [ -n "$DISPLAY" ] && xset -q >/dev/null 2>&1; then
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 1
    done
    
    echo "ERROR: X server not available after $max_attempts attempts" >&2
    return 1
}

# Detect XAUTHORITY dynamically
if [ -z "$XAUTHORITY" ]; then
    # Try common XAUTHORITY locations
    for xauth_path in \\
        "$HOME/.Xauthority" \\
        "/run/user/$(id -u)/gdm/Xauthority" \\
        "/run/user/$(id -u)/.Xauthority" \\
        "/var/run/gdm3/\$(id -u)/.Xauthority"; do
        if [ -f "$xauth_path" ]; then
            export XAUTHORITY="$xauth_path"
            break
        fi
    done
fi

# Wait for X server to be ready
wait_for_x || exit 1

# Set service environment variable
export SYSTEMD_SERVICE=1

# Start Electron
exec "${electronPath}" .
`;
  }
  
  // Ensure persistent directory exists
  const persistentDir = path.dirname(wrapperScriptPath);
  if (!fs.existsSync(persistentDir)) {
    fs.mkdirSync(persistentDir, { recursive: true });
  }
  
  // Write wrapper script to persistent location
  try {
    fs.writeFileSync(wrapperScriptPath, wrapperScript, { mode: 0o755 });
  } catch (error) {
    console.error('Error creating wrapper script:', error);
  }
  
  return `[Unit]
Description=Simple Computer Use Desktop
After=graphical-session.target
Requires=graphical-session.target

[Service]
Type=simple
WorkingDirectory=${workingDirectory}
ExecStart=${wrapperScriptPath}
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal
Environment="SYSTEMD_SERVICE=1"

[Install]
WantedBy=graphical-session.target
`;
}

function installStartupService() {
  try {
    if (process.platform !== 'linux') {
      return { success: false, error: 'Startup service is only supported on Linux' };
    }
    
    const servicePath = getServicePath();
    const serviceDir = path.dirname(servicePath);
    const wrapperScriptPath = getWrapperScriptPath();
    const persistentDir = path.dirname(wrapperScriptPath);
    
    // Create service directory if it doesn't exist
    if (!fs.existsSync(serviceDir)) {
      fs.mkdirSync(serviceDir, { recursive: true });
    }
    
    // Create persistent directory for wrapper script if it doesn't exist
    if (!fs.existsSync(persistentDir)) {
      fs.mkdirSync(persistentDir, { recursive: true });
    }
    
    // Write service file (this also creates the wrapper script)
    fs.writeFileSync(servicePath, getServiceContent(), { mode: 0o644 });
    
    // Reload systemd and enable service
    try {
      execSync('systemctl --user daemon-reload', { stdio: 'ignore' });
      execSync(`systemctl --user enable ${getServiceName()}`, { stdio: 'ignore' });
      return { success: true };
    } catch (error) {
      return { success: false, error: `Failed to enable service: ${error.message}` };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}

function uninstallStartupService() {
  try {
    if (process.platform !== 'linux') {
      return { success: false, error: 'Startup service is only supported on Linux' };
    }
    
    const servicePath = getServicePath();
    const wrapperScriptPath = getWrapperScriptPath();
    
    // Disable and stop service
    try {
      execSync(`systemctl --user disable ${getServiceName()}`, { stdio: 'ignore' });
      execSync(`systemctl --user stop ${getServiceName()}`, { stdio: 'ignore' });
    } catch (error) {
      // Service might not exist, continue
    }
    
    // Remove service file
    if (fs.existsSync(servicePath)) {
      fs.unlinkSync(servicePath);
    }
    
    // Remove wrapper script from persistent location
    if (fs.existsSync(wrapperScriptPath)) {
      fs.unlinkSync(wrapperScriptPath);
    }
    
    // Also try to remove old wrapper script from project directory (for backward compatibility)
    const oldWrapperScriptPath = path.join(__dirname, 'start-gui-service.sh');
    if (fs.existsSync(oldWrapperScriptPath)) {
      try {
        fs.unlinkSync(oldWrapperScriptPath);
      } catch (error) {
        // Ignore errors when removing old script
      }
    }
    
    // Reload systemd
    try {
      execSync('systemctl --user daemon-reload', { stdio: 'ignore' });
    } catch (error) {
      // Ignore errors
    }
    
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

function isStartupServiceInstalled() {
  try {
    if (process.platform !== 'linux') {
      return false;
    }
    
    const servicePath = getServicePath();
    if (!fs.existsSync(servicePath)) {
      return false;
    }
    
    // Check if service is enabled
    try {
      const result = execSync(`systemctl --user is-enabled ${getServiceName()}`, { 
        encoding: 'utf8',
        stdio: 'pipe'
      });
      return result.trim() === 'enabled';
    } catch (error) {
      return false;
    }
  } catch (error) {
    return false;
  }
}

// Create a window icon (reusable function)
function createWindowIcon() {
  try {
    // Try to load the logo image
    const logoPath = path.join(__dirname, 'ic_launcher-playstore.png');
    if (fs.existsSync(logoPath)) {
      const icon = nativeImage.createFromPath(logoPath);
      if (!icon.isEmpty()) {
        return icon;
      }
    }
    
    // Fallback: Create a simple 32x32 icon for the window
    const size = 32;
    const channels = 4; // RGBA
    const data = Buffer.alloc(size * size * channels);
    
    // Fill with a light blue color (RGBA)
    for (let i = 0; i < size * size; i++) {
      const offset = i * channels;
      data[offset] = 52;     // R
      data[offset + 1] = 152; // G
      data[offset + 2] = 219; // B
      data[offset + 3] = 255; // A (opaque)
    }
    
    return nativeImage.createFromBuffer(data, {
      width: size,
      height: size
    });
  } catch (error) {
    console.error('Error creating window icon:', error);
    return null;
  }
}

// Create main window
function createWindow() {
  const windowIcon = createWindowIcon();
  
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    frame: false, // Remove native frame for custom title bar
    transparent: true, // Enable transparency for rounded corners
    backgroundColor: '#00000000', // Transparent background
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true // Keep web security enabled but handle SSL differently
    },
    show: false,
    icon: windowIcon || undefined // Only set if icon was created successfully
  });

  // Verificar que el preload existe
  const preloadPath = path.join(__dirname, 'preload.js');
  if (!fs.existsSync(preloadPath)) {
    console.error('ERROR: preload.js no encontrado en:', preloadPath);
  } else {
    console.log('Preload encontrado en:', preloadPath);
  }

  mainWindow.loadFile('index.html');

  // Abrir herramientas de desarrollador solo en modo desarrollo explícito
  // También se puede abrir manualmente con Ctrl+Shift+I o F12
  if (process.env.NODE_ENV === 'development' || process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  // Manejar errores de carga de página (solo loguear, no abrir DevTools automáticamente)
  mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription, validatedURL) => {
    console.error('Error al cargar la página:', errorCode, errorDescription, validatedURL);
    // No abrir DevTools automáticamente - el usuario puede abrirlas manualmente si lo necesita
  });

  // Manejar errores de consola del renderer
  mainWindow.webContents.on('console-message', (event, level, message, line, sourceId) => {
    if (level >= 2) { // 0=debug, 1=log, 2=info, 3=warning, 4=error
      console.log(`[Renderer ${level}]`, message);
    }
  });

  mainWindow.once('ready-to-show', () => {
    // Always hide window when running as systemd service
    if (process.env.SYSTEMD_SERVICE) {
      // Running as service, always start minimized to tray
      mainWindow.hide();
    } else {
      // Normal mode, show window
      mainWindow.show();
    }
  });

  // Handle window close - minimize to tray instead of closing
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
      
      // Note: displayBalloon is Windows-only, so we skip it on Linux
      // The tray icon itself is sufficient indication
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC handlers
ipcMain.handle('load-config', () => {
  return loadConfig();
});

ipcMain.handle('save-config', (event, config) => {
  return saveConfig(config);
});

ipcMain.handle('start-server', async (event, config) => {
  return await startServer(config);
});

ipcMain.handle('stop-server', async () => {
  return await stopServer();
});

ipcMain.handle('is-server-running', () => {
  return isServerRunning();
});

ipcMain.handle('get-server-config', () => {
  return serverConfig;
});

ipcMain.handle('browse-file', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, options);
  return result;
});

ipcMain.handle('browse-directory', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory']
  });
  return result;
});

ipcMain.handle('install-startup-service', () => {
  return installStartupService();
});

ipcMain.handle('uninstall-startup-service', () => {
  return uninstallStartupService();
});

ipcMain.handle('is-startup-service-installed', () => {
  return isStartupServiceInstalled();
});

ipcMain.handle('is-port-in-use', async (event, port) => {
  return await isPortInUse(port || 5000);
});

// Get process information using a port
function getProcessUsingPort(port) {
  try {
    if (process.platform !== 'linux') {
      return { success: false, error: 'This feature is only available on Linux' };
    }
    
    // Try using lsof first
    try {
      const result = execSync(`lsof -i :${port} -t -sTCP:LISTEN`, { 
        encoding: 'utf8',
        stdio: 'pipe'
      });
      const pid = result.trim();
      
      if (!pid) {
        return { success: false, error: 'No process found using this port' };
      }
      
      // Get process details
      try {
        const psResult = execSync(`ps -p ${pid} -o pid,comm,cmd --no-headers`, {
          encoding: 'utf8',
          stdio: 'pipe'
        });
        const parts = psResult.trim().split(/\s+/, 3);
        const processInfo = {
          pid: parts[0],
          name: parts[1] || 'unknown',
          command: parts[2] || 'unknown'
        };
        
        return { success: true, process: processInfo };
      } catch (e) {
        return { success: true, process: { pid: pid, name: 'unknown', command: 'unknown' } };
      }
    } catch (e) {
      // Try using fuser as fallback
      try {
        const result = execSync(`fuser ${port}/tcp 2>/dev/null`, {
          encoding: 'utf8',
          stdio: 'pipe'
        });
        const pid = result.trim().split(/\s+/)[0];
        
        if (pid) {
          try {
            const psResult = execSync(`ps -p ${pid} -o pid,comm,cmd --no-headers`, {
              encoding: 'utf8',
              stdio: 'pipe'
            });
            const parts = psResult.trim().split(/\s+/, 3);
            return {
              success: true,
              process: {
                pid: parts[0],
                name: parts[1] || 'unknown',
                command: parts[2] || 'unknown'
              }
            };
          } catch (e2) {
            return { success: true, process: { pid: pid, name: 'unknown', command: 'unknown' } };
          }
        }
      } catch (e2) {
        return { success: false, error: 'Could not find process using this port' };
      }
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// Kill process by PID
function killProcess(pid) {
  return new Promise((resolve) => {
    try {
      if (process.platform !== 'linux') {
        resolve({ success: false, error: 'This feature is only available on Linux' });
        return;
      }
      
      // Try graceful kill first (SIGTERM)
      try {
        execSync(`kill ${pid}`, { stdio: 'ignore' });
        
        // Wait a bit and check if process still exists
        setTimeout(() => {
          try {
            // Check if process exists (kill -0 returns 0 if process exists)
            execSync(`kill -0 ${pid} 2>/dev/null`, { stdio: 'ignore' });
            // Process still exists, force kill
            execSync(`kill -9 ${pid}`, { stdio: 'ignore' });
            resolve({ success: true });
          } catch (e) {
            // Process already dead, good
            resolve({ success: true });
          }
        }, 500);
      } catch (error) {
        // Try force kill
        try {
          execSync(`kill -9 ${pid}`, { stdio: 'ignore' });
          resolve({ success: true });
        } catch (e2) {
          resolve({ success: false, error: `Failed to kill process: ${e2.message}` });
        }
      }
    } catch (error) {
      resolve({ success: false, error: error.message });
    }
  });
}

ipcMain.handle('get-process-using-port', (event, port) => {
  return getProcessUsingPort(port || 5000);
});

ipcMain.handle('kill-process', (event, pid) => {
  return killProcess(pid);
});

// Window control handlers
ipcMain.handle('window-minimize', () => {
  if (mainWindow) {
    mainWindow.minimize();
    return { success: true };
  }
  return { success: false, error: 'Window not available' };
});

ipcMain.handle('window-maximize', () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
    return { success: true, isMaximized: mainWindow.isMaximized() };
  }
  return { success: false, error: 'Window not available' };
});

ipcMain.handle('window-close', () => {
  if (mainWindow) {
    mainWindow.close();
    return { success: true };
  }
  return { success: false, error: 'Window not available' };
});

ipcMain.handle('window-is-maximized', () => {
  if (mainWindow) {
    return mainWindow.isMaximized();
  }
  return false;
});

// Desktop application installation
function installDesktopApp() {
  return new Promise((resolve) => {
    try {
      if (process.platform !== 'linux') {
        resolve({ success: false, error: 'Desktop installation is only supported on Linux' });
        return;
      }
      
      const guiElectronDir = __dirname;
      const installScript = path.join(guiElectronDir, 'install-desktop.sh');
      
      if (!fs.existsSync(installScript)) {
        resolve({ success: false, error: 'Installation script not found' });
        return;
      }
      
      // Make sure script is executable
      try {
        fs.chmodSync(installScript, 0o755);
      } catch (e) {
        // Ignore chmod errors
      }
      
      // Execute the installation script
      try {
        const result = execSync(`bash "${installScript}"`, {
          encoding: 'utf8',
          stdio: 'pipe',
          cwd: guiElectronDir
        });
        
        resolve({ 
          success: true, 
          message: 'Application installed successfully to applications menu',
          output: result
        });
      } catch (error) {
        resolve({ 
          success: false, 
          error: error.message || 'Installation failed',
          output: error.stdout || error.stderr || ''
        });
      }
    } catch (error) {
      resolve({ success: false, error: error.message });
    }
  });
}

function isDesktopAppInstalled() {
  try {
    if (process.platform !== 'linux') {
      return false;
    }
    
    const desktopFile = path.join(os.homedir(), '.local', 'share', 'applications', 'simple-computer-use-desktop.desktop');
    return fs.existsSync(desktopFile);
  } catch (error) {
    return false;
  }
}

ipcMain.handle('install-desktop-app', () => {
  return installDesktopApp();
});

ipcMain.handle('is-desktop-app-installed', () => {
  return isDesktopAppInstalled();
});

// Handle certificate errors for self-signed certificates (localhost only)
// This must be registered before app.whenReady() to apply to all connections
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
  // Only allow self-signed certificates for localhost
  if (url.includes('localhost') || url.includes('127.0.0.1') || url.includes('0.0.0.0')) {
    event.preventDefault();
    callback(true); // Accept the certificate
  } else {
    callback(false); // Reject for other hosts
  }
});

// Single instance lock - prevent multiple instances
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  // Another instance is already running
  console.log('Another instance is already running. Exiting...');
  app.quit();
  process.exit(0);
} else {
  // This is the first instance - handle second instance attempts
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // Someone tried to run a second instance, focus our window instead
    console.log('Second instance attempted - focusing existing window');
    
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.show();
      mainWindow.focus();
    } else {
      // Window doesn't exist, create it
      createWindow();
    }
  });
}

// Kill duplicate instances
function killDuplicateInstances() {
  try {
    if (process.platform !== 'linux') {
      return; // Only for Linux
    }
    
    const currentPid = process.pid;
    const projectRoot = path.resolve(__dirname, '..');
    const guiElectronDir = __dirname;
    
    // Find all electron processes related to this application
    try {
      // Get all electron processes
      const psOutput = execSync('ps aux | grep -E "electron.*gui-electron|electron.*simple-computer-use" | grep -v grep', {
        encoding: 'utf8',
        stdio: 'pipe'
      });
      
      if (!psOutput || !psOutput.trim()) {
        return; // No other instances found
      }
      
      const lines = psOutput.trim().split('\n');
      let killedCount = 0;
      
      for (const line of lines) {
        if (!line.trim()) continue;
        
        // Extract PID (second column in ps aux output)
        const parts = line.trim().split(/\s+/);
        if (parts.length < 2) continue;
        
        const pid = parseInt(parts[1]);
        
        // Skip current process
        if (pid === currentPid || isNaN(pid)) {
          continue;
        }
        
        // Check if this process is related to our app
        const processCmd = line.toLowerCase();
        if (processCmd.includes('gui-electron') || 
            processCmd.includes('simple-computer-use') ||
            processCmd.includes('simple-computer-use-server')) {
          
          try {
            // Try graceful kill first
            execSync(`kill ${pid}`, { stdio: 'ignore' });
            
            // Wait a bit and force kill if still running
            setTimeout(() => {
              try {
                execSync(`kill -0 ${pid} 2>/dev/null`, { stdio: 'ignore' });
                // Process still exists, force kill
                execSync(`kill -9 ${pid}`, { stdio: 'ignore' });
                console.log(`Force killed duplicate instance PID: ${pid}`);
              } catch (e) {
                // Process already dead, good
              }
            }, 500);
            
            killedCount++;
            console.log(`Killed duplicate instance PID: ${pid}`);
          } catch (error) {
            // Process might already be dead or we don't have permission
            console.warn(`Could not kill process ${pid}: ${error.message}`);
          }
        }
      }
      
      if (killedCount > 0) {
        console.log(`Cleaned up ${killedCount} duplicate instance(s)`);
      }
    } catch (error) {
      // No other processes found or error executing ps
      if (error.code !== 1) { // Exit code 1 means no matches found, which is fine
        console.warn('Error checking for duplicate instances:', error.message);
      }
    }
  } catch (error) {
    console.error('Error in killDuplicateInstances:', error);
  }
}

// App event handlers
app.whenReady().then(async () => {
  // Kill any duplicate instances before creating window
  killDuplicateInstances();
  
  createWindow();
  createTray();

  // If running as systemd service, automatically start the server
  if (process.env.SYSTEMD_SERVICE) {
    console.log('Running as systemd service - auto-starting server...');
    try {
      // Load configuration (or use defaults)
      const config = loadConfig();
      // Wait a bit for window to be ready
      await new Promise(resolve => setTimeout(resolve, 1000));
      // Start server automatically
      const result = await startServer(config);
      if (result.success) {
        console.log('Server started successfully as service');
      } else {
        console.error('Failed to start server as service:', result.error);
      }
    } catch (error) {
      console.error('Error auto-starting server as service:', error);
    }
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    } else if (mainWindow) {
      mainWindow.show();
    }
  });
});

app.on('window-all-closed', async () => {
  // Don't quit if we have a tray icon - just hide the window
  if (tray && !isQuitting) {
    return;
  }
  
  if (serverProcess) {
    console.log('Window closed, stopping server...');
    await stopServer();
    // Wait a bit for process to fully terminate
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  
  // Only quit if explicitly requested (isQuitting) or on macOS
  if (isQuitting || process.platform === 'darwin') {
    app.quit();
  }
});

app.on('before-quit', async (event) => {
  isQuitting = true;
  
  if (serverProcess) {
    console.log('App quitting, stopping server...');
    event.preventDefault(); // Prevent immediate quit
    await stopServer();
    // Wait for process to fully terminate
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Stop Ollama if we started it
  if (ollamaProcess) {
    console.log('App quitting, stopping Ollama...');
    stopOllama();
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  
  // Clean up tray
  if (tray) {
    tray.destroy();
    tray = null;
  }
  
  app.quit(); // Now quit
});
