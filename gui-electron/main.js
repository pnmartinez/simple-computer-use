const { app, BrowserWindow, ipcMain, dialog, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const os = require('os');

let mainWindow;
let serverProcess = null;
let serverConfig = null;
let tray = null;
let isQuitting = false;

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
// Based on /home/nava/start-llm-control.sh (systemd service)
function getDefaultConfig() {
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
    screenshot_dir: './screenshots',
    failsafe_enabled: false,
    debug: false
  };
}

// Find Python executable
// Priority: venv-py312 (same as start-llm-control.sh) > system python
function findPythonExecutable() {
  const projectRoot = path.resolve(__dirname, '..');
  const venvPython = path.join(projectRoot, 'venv-py312', 'bin', 'python');
  
  // First try: venv-py312 (same as start-llm-control.sh)
  if (fs.existsSync(venvPython)) {
    try {
      // Verify it works
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
    const pythonCmd = findPythonExecutable();
    // Get project root (parent of gui-electron directory)
    const projectRoot = path.resolve(__dirname, '..');
    
    // Prepare environment variables (same as start-llm-control.sh)
    const env = Object.assign({}, process.env);
    env.STRUCTURED_USAGE_LOGS = 'true';
    
    // If using venv, ensure PATH includes venv bin
    if (pythonCmd.includes('venv-py312')) {
      const venvBin = path.join(projectRoot, 'venv-py312', 'bin');
      env.PATH = `${venvBin}:${env.PATH}`;
    }
    
    const args = [
      '-m', 'llm_control', 'voice-server',
      '--host', config.host || '0.0.0.0',
      '--port', String(config.port || 5000)
    ];

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
    if (config.screenshot_dir) {
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

function getServiceContent() {
  const projectRoot = path.resolve(__dirname, '..');
  const guiElectronDir = __dirname;
  
  // Create a wrapper script path
  const wrapperScriptPath = path.join(guiElectronDir, 'start-gui-service.sh');
  
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
  
  // Create wrapper script with dynamic X server detection
  const wrapperScript = `#!/bin/bash
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
  
  // Write wrapper script
  try {
    fs.writeFileSync(wrapperScriptPath, wrapperScript, { mode: 0o755 });
  } catch (error) {
    console.error('Error creating wrapper script:', error);
  }
  
  // Get XAUTHORITY path for service file (fallback, but script will detect dynamically)
  const xauthPath = process.env.XAUTHORITY || path.join(os.homedir(), '.Xauthority');
  
  return `[Unit]
Description=Simple Computer Use Desktop
After=graphical.target
Requires=graphical.target

[Service]
Type=simple
WorkingDirectory=${projectRoot}
ExecStart=${wrapperScriptPath}
Restart=on-failure
RestartSec=30
StartLimitIntervalSec=300
StartLimitBurst=5
StandardOutput=journal
StandardError=journal
Environment="SYSTEMD_SERVICE=1"

[Install]
WantedBy=graphical.target
`;
}

function installStartupService() {
  try {
    if (process.platform !== 'linux') {
      return { success: false, error: 'Startup service is only supported on Linux' };
    }
    
    const servicePath = getServicePath();
    const serviceDir = path.dirname(servicePath);
    
    // Create directory if it doesn't exist
    if (!fs.existsSync(serviceDir)) {
      fs.mkdirSync(serviceDir, { recursive: true });
    }
    
    // Write service file
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
    const wrapperScriptPath = path.join(__dirname, 'start-gui-service.sh');
    
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
    
    // Remove wrapper script
    if (fs.existsSync(wrapperScriptPath)) {
      fs.unlinkSync(wrapperScriptPath);
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
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true // Keep web security enabled but handle SSL differently
    },
    titleBarStyle: 'default',
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
            processCmd.includes('llm-control')) {
          
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
app.whenReady().then(() => {
  // Kill any duplicate instances before creating window
  killDuplicateInstances();
  
  createWindow();
  createTray();

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
    app.quit(); // Now quit
  }
  
  // Clean up tray
  if (tray) {
    tray.destroy();
    tray = null;
  }
});

