const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

let mainWindow;
let serverProcess = null;
let serverConfig = null;

// Load configuration
function loadConfig() {
  const configPath = path.join(os.homedir(), '.llm-control-gui-config.json');
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
  const configPath = path.join(os.homedir(), '.llm-control-gui-config.json');
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

// Create main window
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    titleBarStyle: 'default',
    show: false
  });

  mainWindow.loadFile('index.html');

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
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

// App event handlers
app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', async () => {
  if (serverProcess) {
    console.log('Window closed, stopping server...');
    await stopServer();
    // Wait a bit for process to fully terminate
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', async (event) => {
  if (serverProcess) {
    console.log('App quitting, stopping server...');
    event.preventDefault(); // Prevent immediate quit
    await stopServer();
    // Wait for process to fully terminate
    await new Promise(resolve => setTimeout(resolve, 1000));
    app.quit(); // Now quit
  }
});

