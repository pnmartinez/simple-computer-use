let currentConfig = null;
let serverRunning = false;
let statusCheckInterval = null;
let portInUseState = false;
let serverFullyStarted = false;
let systemInfo = {};

// Voice recording state
let mediaRecorder = null;
let audioChunks = [];
let audioStream = null;
let isRecording = false;
let recordingState = 'idle'; // 'idle', 'recording', 'processing', 'error'

// Función para esperar a que electronAPI esté disponible
function waitForElectronAPI(maxWait = 3000) {
    return new Promise((resolve, reject) => {
        // Si ya está disponible, resolver inmediatamente
        if (window.electronAPI) {
            resolve();
            return;
        }

        const startTime = Date.now();
        const checkInterval = 50; // Verificar cada 50ms
        let loadingIndicator = null;

        // Crear indicador de carga sutil
        const createLoadingIndicator = () => {
            if (loadingIndicator) return;
            
            loadingIndicator = document.createElement('div');
            loadingIndicator.id = 'loading-indicator';
            loadingIndicator.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.3);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            `;
            
            const spinner = document.createElement('div');
            spinner.style.cssText = `
                background: white;
                padding: 20px 30px;
                border-radius: 8px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                text-align: center;
            `;
            
            spinner.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <div style="border: 3px solid #f3f3f3; border-top: 3px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                </div>
                <div style="color: #2c3e50; font-size: 14px;">Cargando aplicación...</div>
            `;
            
            // Agregar animación CSS si no existe
            if (!document.getElementById('loading-spinner-style')) {
                const style = document.createElement('style');
                style.id = 'loading-spinner-style';
                style.textContent = `
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                `;
                document.head.appendChild(style);
            }
            
            loadingIndicator.appendChild(spinner);
            document.body.appendChild(loadingIndicator);
        };

        const check = () => {
            if (window.electronAPI) {
                // Remover indicador de carga
                if (loadingIndicator && loadingIndicator.parentNode) {
                    loadingIndicator.parentNode.removeChild(loadingIndicator);
                }
                resolve();
                return;
            }

            const elapsed = Date.now() - startTime;
            
            // Mostrar indicador después de 100ms para evitar parpadeo
            if (elapsed > 100 && !loadingIndicator) {
                createLoadingIndicator();
            }

            if (elapsed >= maxWait) {
                // Remover indicador de carga
                if (loadingIndicator && loadingIndicator.parentNode) {
                    loadingIndicator.parentNode.removeChild(loadingIndicator);
                }
                reject(new Error(`electronAPI no está disponible después de ${maxWait}ms. El preload script puede no haberse cargado correctamente.`));
                return;
            }

            setTimeout(check, checkInterval);
        };

        check();
    });
}

// Dark Mode Management
function initDarkMode() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    
    if (!themeToggle || !themeIcon) return;
    
    // Get saved theme or detect system preference
    const savedTheme = localStorage.getItem('theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const initialTheme = savedTheme || (systemPrefersDark ? 'dark' : 'light');
    
    // Apply initial theme
    document.documentElement.setAttribute('data-theme', initialTheme);
    updateThemeIcon(initialTheme, themeIcon);
    
    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            const newTheme = e.matches ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            updateThemeIcon(newTheme, themeIcon);
        }
    });
    
    // Toggle theme on button click
    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        updateThemeIcon(newTheme, themeIcon);
    });
}

function updateThemeIcon(theme, iconElement) {
    if (!iconElement) return;
    iconElement.textContent = theme === 'dark' ? '☀️' : '🌙';
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        // Esperar a que electronAPI esté disponible
        await waitForElectronAPI(3000);
        
        // Inicializar dark mode
        initDarkMode();
        
        // Inicializar la aplicación
        await loadConfiguration();
        setupEventListeners();
        setupServerEventListeners();
        setupTabs();
        setupVoiceCommandButton();
        setupTitleBarControls();
        checkInitialServerStatus();
        checkDesktopAppStatus();
    } catch (error) {
        console.error('Error al inicializar la aplicación:', error);
        // Solo mostrar error si realmente falló después de esperar
        document.body.innerHTML = `
            <div style="padding: 20px; font-family: Arial, sans-serif;">
                <h1 style="color: #e74c3c;">Error de Carga</h1>
                <p>No se pudo cargar la API de Electron. Por favor, verifica que el preload script esté configurado correctamente.</p>
                <p style="color: #7f8c8d; font-size: 12px;">Error: ${error.message}</p>
                <p style="margin-top: 20px;">
                    <button onclick="location.reload()" style="padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        Recargar Aplicación
                    </button>
                </p>
            </div>
        `;
    }
});

async function loadConfiguration() {
    try {
        if (!window.electronAPI || !window.electronAPI.loadConfig) {
            throw new Error('electronAPI.loadConfig no está disponible');
        }
        currentConfig = await window.electronAPI.loadConfig();
        populateConfigForm(currentConfig);
        
        // Check if startup service is installed and update checkbox accordingly
        if (window.electronAPI.isStartupServiceInstalled) {
            const isInstalled = await window.electronAPI.isStartupServiceInstalled();
            if (isInstalled && !currentConfig.start_on_boot) {
                // Service is installed but config doesn't reflect it - update config
                currentConfig.start_on_boot = true;
                document.getElementById('start-on-boot').checked = true;
            }
        }
    } catch (error) {
        console.error('Error loading config:', error);
        throw error; // Re-lanzar para que el manejo de errores global lo capture
    }
}

function populateConfigForm(config) {
    document.getElementById('host').value = config.host || '0.0.0.0';
    document.getElementById('port').value = config.port || 5000;
    document.getElementById('ssl').checked = config.ssl !== undefined ? config.ssl : true;
    document.getElementById('ssl-cert').value = config.ssl_cert || '';
    document.getElementById('ssl-key').value = config.ssl_key || '';
    document.getElementById('whisper-model').value = config.whisper_model || 'large';
    document.getElementById('ollama-model').value = config.ollama_model || 'gemma3:12b';
    document.getElementById('ollama-host').value = config.ollama_host || 'http://localhost:11434';
    document.getElementById('language').value = config.language || 'es';
    document.getElementById('translation-enabled').checked = config.translation_enabled !== undefined ? config.translation_enabled : false;
    document.getElementById('screenshots-enabled').checked = config.screenshots_enabled !== undefined ? config.screenshots_enabled : true;
    document.getElementById('screenshot-dir').value = config.screenshot_dir || './screenshots';
    document.getElementById('debug').checked = config.debug !== undefined ? config.debug : false;
    document.getElementById('failsafe-enabled').checked = config.failsafe_enabled !== undefined ? config.failsafe_enabled : false;
    document.getElementById('start-on-boot').checked = config.start_on_boot || false;
}

function getConfigFromForm() {
    return {
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value) || 5000,
        ssl: document.getElementById('ssl').checked,
        ssl_cert: document.getElementById('ssl-cert').value.trim(),
        ssl_key: document.getElementById('ssl-key').value.trim(),
        whisper_model: document.getElementById('whisper-model').value,
        ollama_model: document.getElementById('ollama-model').value,
        ollama_host: document.getElementById('ollama-host').value,
        language: document.getElementById('language').value.trim() || 'es',
        translation_enabled: document.getElementById('translation-enabled').checked,
        screenshots_enabled: document.getElementById('screenshots-enabled').checked,
        screenshot_dir: document.getElementById('screenshot-dir').value.trim() || './screenshots',
        debug: document.getElementById('debug').checked,
        failsafe_enabled: document.getElementById('failsafe-enabled').checked,
        start_on_boot: document.getElementById('start-on-boot').checked
    };
}

function setupEventListeners() {
    document.getElementById('start-btn').addEventListener('click', startServer);
    document.getElementById('stop-btn').addEventListener('click', stopServer);
}

function setupServerEventListeners() {
    window.electronAPI.onServerLog((data) => {
        addLogEntry(data);
        // Extract system info from all logs (not just startup)
        extractSystemInfo(data);
        // Check if server has fully started by analyzing logs
        checkServerStartupComplete(data);
    });
    window.electronAPI.onServerStopped((code) => {
        handleServerStopped(code);
    });
}

function extractSystemInfo(logData) {
    const logText = logData.toString();
    const logLines = logText.split('\n');
    
    // Extract information from log lines
    for (const line of logLines) {
        // Server version - multiple patterns
        if (!systemInfo.serverVersion) {
            if (/voice control server.*v[\d.]+/i.test(line)) {
                const match = line.match(/voice control server.*v([\d.]+)/i);
                if (match) {
                    systemInfo.serverVersion = match[1];
                }
            }
        }
        
        // Listening address - multiple patterns
        if (!systemInfo.listeningAddress) {
            if (/listening on:/i.test(line)) {
                const match = line.match(/listening on:\s*(https?:\/\/[^\s]+)/i);
                if (match) {
                    systemInfo.listeningAddress = match[1];
                }
            } else if (/running on/i.test(line) && /http/i.test(line)) {
                const match = line.match(/(https?:\/\/[^\s]+)/i);
                if (match) {
                    systemInfo.listeningAddress = match[1];
                }
            }
        }
        
        // Debug mode
        if (!systemInfo.debugMode) {
            if (/debug mode:/i.test(line)) {
                const match = line.match(/debug mode:\s*(on|off)/i);
                if (match) {
                    systemInfo.debugMode = match[1].toUpperCase();
                }
            }
        }
        
        // Default language
        if (!systemInfo.defaultLanguage) {
            if (/default language:/i.test(line)) {
                const match = line.match(/default language:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.defaultLanguage = match[1].trim();
                }
            }
        }
        
        // Whisper model
        if (!systemInfo.whisperModel) {
            if (/using whisper model:/i.test(line)) {
                const match = line.match(/using whisper model:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.whisperModel = match[1].trim();
                }
            }
        }
        
        // Ollama model
        if (!systemInfo.ollamaModel) {
            if (/using ollama model:/i.test(line)) {
                const match = line.match(/using ollama model:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.ollamaModel = match[1].trim();
                }
            }
        }
        
        // Screenshot directory
        if (!systemInfo.screenshotDir) {
            if (/screenshot directory:/i.test(line)) {
                const match = line.match(/screenshot directory:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.screenshotDir = match[1].trim();
                }
            }
        }
        
        // Screenshot max age
        if (!systemInfo.screenshotMaxAge) {
            if (/screenshot max age/i.test(line)) {
                const match = line.match(/screenshot max age[^:]*:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.screenshotMaxAge = match[1].trim();
                }
            }
        }
        
        // Screenshot max count
        if (!systemInfo.screenshotMaxCount) {
            if (/screenshot max count/i.test(line)) {
                const match = line.match(/screenshot max count[^:]*:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.screenshotMaxCount = match[1].trim();
                }
            }
        }
        
        // Command history file
        if (!systemInfo.commandHistoryFile) {
            if (/command history file:/i.test(line)) {
                const match = line.match(/command history file:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.commandHistoryFile = match[1].trim();
                }
            }
        }
        
        // PyAutoGUI failsafe
        if (!systemInfo.failsafe) {
            if (/pyautogui failsafe:/i.test(line)) {
                const match = line.match(/pyautogui failsafe:\s*(enabled|disabled)/i);
                if (match) {
                    systemInfo.failsafe = match[1].toUpperCase();
                }
            }
        }
        
        // Vision captioning
        if (!systemInfo.visionCaptioning) {
            if (/vision captioning:/i.test(line)) {
                const match = line.match(/vision captioning:\s*(enabled|disabled)/i);
                if (match) {
                    systemInfo.visionCaptioning = match[1].toUpperCase();
                }
            }
        }
        
        // GPU information
        if (!systemInfo.gpu) {
            if (/gpu:/i.test(line)) {
                const match = line.match(/gpu:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.gpu = match[1].trim();
                }
            }
        }
        
        // Whisper model initialization time
        if (!systemInfo.whisperInitTime) {
            if (/whisper model initialized in/i.test(line)) {
                const match = line.match(/whisper model initialized in\s*([\d.]+)\s*seconds/i);
                if (match) {
                    systemInfo.whisperInitTime = `${match[1]} seconds`;
                }
            }
        }
        
        // CUDA device
        if (!systemInfo.cudaDevice) {
            if (/cuda is available/i.test(line)) {
                const match = line.match(/using device:\s*([^\n]+)/i);
                if (match) {
                    systemInfo.cudaDevice = match[1].trim();
                }
            } else if (/cuda is not available/i.test(line)) {
                systemInfo.cudaDevice = 'Not available';
            }
        }
    }
}

function checkServerStartupComplete(logData) {
    if (!serverRunning || serverFullyStarted) {
        return;
    }
    
    // Extract system information from logs
    extractSystemInfo(logData);
    
    const logText = logData.toString().toLowerCase();
    
    // Check for patterns that indicate the server has fully started
    // The server prints a banner with system information when ready
    const startupPatterns = [
        /listening on:/i,  // "Listening on: http://..."
        /using whisper model:/i,  // "Using Whisper model: ..."
        /using ollama model:/i,  // "Using Ollama model: ..."
        /gpu:.*available/i,  // "GPU: Available - ..." or "GPU: Not available"
        /voice control server.*starting/i,  // "Voice Control Server v1.0 starting..."
        /running on.*http/i,  // Flask "Running on http://..."
        /whisper model initialized/i  // "Whisper model initialized in X seconds"
    ];
    
    // Check if we see multiple indicators that the server is ready
    let indicatorsFound = 0;
    for (const pattern of startupPatterns) {
        if (pattern.test(logText)) {
            indicatorsFound++;
        }
    }
    
    // If we see at least 2 indicators (especially "Listening on" or "Running on"), server is ready
    if (indicatorsFound >= 2 || /running on.*http/i.test(logText) || /listening on:/i.test(logText)) {
        // Also check for the GPU/model info to be sure
        if (logText.includes('gpu:') || logText.includes('whisper model') || logText.includes('ollama model')) {
            serverFullyStarted = true;
            updateServerStatus('running');
            addLogEntry('✓ Server fully started and ready\n');
            // Display system info when server is ready
            displaySystemInfo();
        }
    }
}

function setupTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            tabButtons.forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
            
            // Load history when switching to history tab
            if (targetTab === 'history') {
                loadHistory();
            }
            // Display system info when switching to system-info tab
            if (targetTab === 'system-info') {
                displaySystemInfo();
            }
        });
    });
}

async function startServer() {
    const startBtn = document.getElementById('start-btn');
    const originalText = startBtn.textContent;
    
    // Show loading state
    startBtn.classList.add('loading');
    startBtn.disabled = true;
    
    const config = getConfigFromForm();
    try {
        await window.electronAPI.saveConfig(config);
        currentConfig = config;
        const result = await window.electronAPI.startServer(config);
        if (result.success) {
            serverRunning = true;
            serverFullyStarted = false; // Reset flag when starting
            updateServerStatus('starting');
            updateButtons();
            startStatusMonitoring();
            addLogEntry('Server starting...\n');
        } else {
            // Remove loading state on error
            startBtn.classList.remove('loading');
            startBtn.disabled = false;
            alert(`Failed to start server: ${result.error}`);
        }
    } catch (error) {
        // Remove loading state on error
        startBtn.classList.remove('loading');
        startBtn.disabled = false;
        console.error('Error starting server:', error);
        alert(`Error: ${error.message}`);
    }
}

async function stopServer() {
    const stopBtn = document.getElementById('stop-btn');
    const originalText = stopBtn.textContent;
    
    // Show loading state
    stopBtn.classList.add('loading');
    stopBtn.disabled = true;
    
    try {
        const result = await window.electronAPI.stopServer();
        if (result.success) {
            serverRunning = false;
            updateServerStatus('stopped');
            updateButtons();
            stopStatusMonitoring();
            addLogEntry('Server stopped.\n');
        } else {
            // Remove loading state on error
            stopBtn.classList.remove('loading');
            stopBtn.disabled = false;
            alert(`Failed to stop server: ${result.error}`);
        }
    } catch (error) {
        // Remove loading state on error
        stopBtn.classList.remove('loading');
        stopBtn.disabled = false;
        console.error('Error stopping server:', error);
    }
}

function updateServerStatus(status, customText = null) {
    // Remove the bullet point (●) as it's now added via CSS ::before
    const indicator = document.getElementById('status-indicator');
    indicator.className = `status-indicator status-${status}`;
    
    // Make clickable if port is in use
    if (status === 'port-in-use') {
        indicator.style.cursor = 'pointer';
        indicator.title = 'Click to view process using this port';
        portInUseState = true;
    } else {
        indicator.style.cursor = 'default';
        indicator.title = '';
        portInUseState = false;
    }
    
    if (customText) {
        // Remove bullet point if present (now handled by CSS)
        indicator.textContent = customText.replace(/^●\s*/, '');
    } else {
        indicator.textContent = status === 'stopped' ? 'Stopped' : 
                               status === 'starting' ? 'Starting...' : 
                               status === 'running' ? 'Running' : 
                               status === 'port-in-use' ? 'Port in use' : 
                               'Error';
    }
}

function updateButtons() {
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const voiceBtn = document.getElementById('voice-command-btn');
    
    // Remove loading states when updating buttons
    startBtn.classList.remove('loading');
    stopBtn.classList.remove('loading');
    
    startBtn.disabled = serverRunning;
    stopBtn.disabled = !serverRunning;
    
    // Disable voice button if server is not running (unless already recording/processing)
    if (voiceBtn && recordingState === 'idle') {
        voiceBtn.disabled = !serverRunning && !serverFullyStarted;
        if (!serverRunning && !serverFullyStarted) {
            voiceBtn.style.opacity = '0.5';
            voiceBtn.style.cursor = 'not-allowed';
        } else {
            voiceBtn.style.opacity = '';
            voiceBtn.style.cursor = '';
        }
    }
}

// Check server health by making an HTTP/HTTPS request to /health endpoint
async function checkServerHealth(config) {
    if (!config) {
        config = currentConfig || await window.electronAPI.loadConfig();
    }
    if (!config) {
        return false;
    }
    
    const isLocalhost = config.host === '0.0.0.0' || config.host === 'localhost' || config.host === '127.0.0.1';
    let protocol = config.ssl ? 'https' : 'http';
    const host = config.host === '0.0.0.0' ? 'localhost' : config.host;
    let url = `${protocol}://${host}:${config.port}/health`;
    
    try {
        const response = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(2000) });
        if (response.ok) {
            return true;
        }
    } catch (error) {
        // If HTTPS failed and we're on localhost, try HTTP as fallback
        if (config.ssl && isLocalhost && (error.message.includes('SSL') || error.message.includes('certificate') || error.message.includes('Failed to fetch'))) {
            protocol = 'http';
            url = `http://${host}:${config.port}/health`;
            try {
                const httpResponse = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(2000) });
                if (httpResponse.ok) {
                    return true;
                }
            } catch (httpError) {
                // Both failed
            }
        }
    }
    
    return false;
}

function startStatusMonitoring() {
    if (statusCheckInterval) clearInterval(statusCheckInterval);
    statusCheckInterval = setInterval(async () => {
        if (!serverRunning) {
            clearInterval(statusCheckInterval);
            return;
        }
        
        // If we've already detected the server is fully started via logs, just verify with health check
        if (serverFullyStarted) {
            try {
                const config = currentConfig || await window.electronAPI.getServerConfig();
                if (!config) return;
                
                const isHealthy = await checkServerHealth(config);
                if (isHealthy) {
                    updateServerStatus('running');
                    return;
                }
                
                // If we get here, health check failed
                updateServerStatus('error');
                serverFullyStarted = false; // Reset if health check fails
            } catch (error) {
                // If health check fails but we thought it was started, keep checking
                // Don't change status immediately, wait a bit more
            }
        } else {
            // Server not fully started yet, keep status as "starting"
            // The log analysis will change it to "running" when ready
            updateServerStatus('starting');
        }
    }, 20000);
}

function stopStatusMonitoring() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

function handleServerStopped(code) {
    serverRunning = false;
    serverFullyStarted = false; // Reset flag when stopped
    systemInfo = {}; // Clear system info when server stops
    
    // Stop voice recording if active
    if (isRecording) {
        stopVoiceRecording();
    }
    if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop());
        audioStream = null;
    }
    
    updateServerStatus('stopped');
    updateButtons();
    stopStatusMonitoring();
    addLogEntry(`Server stopped with code ${code}\n`);
    // Clear system info display
    const container = document.getElementById('system-info-container');
    if (container) {
        container.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">ℹ️</div>
                <h3>No System Information Available</h3>
                <p>Start the server to view system information.</p>
            </div>
        `;
    }
    // Reset voice button state
    setRecordingState('idle');
    updateVoiceStatus('', '');
}

function addLogEntry(text) {
    const logsContainer = document.getElementById('logs-container');
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = text;
    logsContainer.appendChild(entry);
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

function clearLogs() {
    document.getElementById('logs-container').innerHTML = '';
    addLogEntry('=== Logs cleared ===\n');
}

async function saveConfig() {
    const config = getConfigFromForm();
    try {
        const result = await window.electronAPI.saveConfig(config);
        if (result) {
            currentConfig = config;
            
            // Handle startup service installation/removal
            if (config.start_on_boot) {
                const serviceResult = await window.electronAPI.installStartupService();
                if (serviceResult.success) {
                    alert('Configuration saved successfully!\nStartup service installed. The GUI will start automatically on system boot.');
                } else {
                    alert(`Configuration saved, but failed to install startup service:\n${serviceResult.error}`);
                }
            } else {
                const serviceResult = await window.electronAPI.uninstallStartupService();
                if (serviceResult.success) {
                    alert('Configuration saved successfully!\nStartup service removed.');
                } else {
                    alert(`Configuration saved, but failed to remove startup service:\n${serviceResult.error}`);
                }
            }
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert(`Error saving configuration: ${error.message}`);
    }
}

async function showPortInUseDialog() {
    const config = currentConfig || await window.electronAPI.loadConfig();
    const port = config?.port || 5000;
    
    try {
        const result = await window.electronAPI.getProcessUsingPort(port);
        
        if (result.success && result.process) {
            const process = result.process;
            const message = `Port ${port} is being used by:\n\n` +
                          `PID: ${process.pid}\n` +
                          `Name: ${process.name}\n` +
                          `Command: ${process.command}\n\n` +
                          `Do you want to kill this process?`;
            
            if (confirm(message)) {
                const killResult = await window.electronAPI.killProcess(process.pid);
                if (killResult.success) {
                    alert('Process killed successfully. You can now start the server.');
                    // Recheck status
                    setTimeout(() => checkInitialServerStatus(), 1000);
                } else {
                    alert(`Failed to kill process: ${killResult.error}`);
                }
            }
        } else {
            alert(`Could not get process information: ${result.error || 'Unknown error'}`);
        }
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

async function loadHistory() {
    const historyContainer = document.getElementById('history-container');
    
    // Check if server is running
    if (!serverRunning && !serverFullyStarted) {
        historyContainer.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">⚠️</div>
                <h3>Server Not Running</h3>
                <p>Start the server to view command history.</p>
            </div>
        `;
        return;
    }
    
    try {
        const config = currentConfig || await window.electronAPI.loadConfig();
        if (!config) {
            historyContainer.innerHTML = '<p style="color: #e74c3c;">Configuration not available.</p>';
            return;
        }
        
        // For localhost, prefer HTTP if SSL causes issues, otherwise use configured protocol
        const isLocalhost = config.host === '0.0.0.0' || config.host === 'localhost' || config.host === '127.0.0.1';
        let protocol = config.ssl ? 'https' : 'http';
        const host = config.host === '0.0.0.0' ? 'localhost' : config.host;
        
        // Try HTTPS first if SSL is enabled, fallback to HTTP for localhost if it fails
        let url = `${protocol}://${host}:${config.port}/command-history?limit=50&date_filter=all`;
        
        historyContainer.innerHTML = '<div class="history-loading">Loading history...</div>';
        
        // First verify server is accessible with a health check
        let healthCheckPassed = false;
        let healthError = null;
        
        try {
            const healthUrl = `${protocol}://${host}:${config.port}/health`;
            const healthResponse = await fetch(healthUrl, { 
                method: 'GET',
                signal: AbortSignal.timeout(3000)
            });
            
            if (healthResponse.ok) {
                healthCheckPassed = true;
            } else {
                healthError = new Error(`Server health check failed: ${healthResponse.status}`);
            }
        } catch (error) {
            healthError = error;
            // If HTTPS failed and we're on localhost, try HTTP as fallback
            if (config.ssl && isLocalhost && (error.message.includes('SSL') || error.message.includes('certificate') || error.message.includes('Failed to fetch'))) {
                console.warn('HTTPS failed, trying HTTP fallback for localhost');
                protocol = 'http';
                const httpHealthUrl = `http://${host}:${config.port}/health`;
                try {
                    const httpHealthResponse = await fetch(httpHealthUrl, { 
                        method: 'GET',
                        signal: AbortSignal.timeout(3000)
                    });
                    if (httpHealthResponse.ok) {
                        healthCheckPassed = true;
                        healthError = null;
                    }
                } catch (httpError) {
                    // Both failed
                    healthError = httpError;
                }
            }
        }
        
        if (!healthCheckPassed) {
            console.error('Health check failed:', healthError);
            historyContainer.innerHTML = `
                <div class="history-empty-state">
                    <div class="history-empty-state-icon">⚠️</div>
                    <h3>Connection Error</h3>
                    <p>Cannot connect to server. Make sure the server is running and accessible.</p>
                    <p style="font-size: var(--text-xs); color: var(--text-tertiary); margin-top: var(--space-2);">Error: ${healthError?.message || 'Unknown error'}</p>
                </div>
            `;
            return;
        }
        
        // Update URL if we switched to HTTP
        url = `${protocol}://${host}:${config.port}/command-history?limit=50&date_filter=all`;
        
        // Now fetch history
        const response = await fetch(url, { 
            method: 'GET',
            signal: AbortSignal.timeout(10000),
            headers: {
                'Accept': 'application/json'
            }
        });
        
        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }
        
        const data = await response.json();
        
        if (data.status === 'success') {
            if (data.history && data.history.length > 0) {
                displayHistory(data.history);
            } else {
                historyContainer.innerHTML = '<p>No command history found.</p>';
            }
        } else if (data.status === 'error') {
            throw new Error(data.error || 'Unknown error from server');
        } else {
            throw new Error('Unexpected response format from server');
        }
    } catch (error) {
        console.error('Error loading history:', error);
        let errorMessage = error.message || 'Unknown error';
        
        // Provide more helpful error messages
        if (errorMessage.includes('Failed to fetch') || errorMessage.includes('NetworkError')) {
            errorMessage = 'Failed to connect to server. Check if the server is running and the port is correct.';
        } else if (errorMessage.includes('timeout')) {
            errorMessage = 'Request timed out. The server may be slow or unresponsive.';
        } else if (errorMessage.includes('SSL') || errorMessage.includes('certificate')) {
            errorMessage = 'SSL certificate error. The server may be using a self-signed certificate.';
        }
        
        historyContainer.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">⚠️</div>
                <h3>Error Loading History</h3>
                <p>${errorMessage}</p>
            </div>
        `;
    }
}

function displayHistory(history) {
    const historyContainer = document.getElementById('history-container');
    
    if (!history || history.length === 0) {
        historyContainer.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">📜</div>
                <h3>No History Available</h3>
                <p>No command history found. Commands will appear here after execution.</p>
            </div>
        `;
        return;
    }
    
    // Sort by timestamp (newest first)
    const sortedHistory = [...history].sort((a, b) => {
        const dateA = new Date(a.timestamp || 0);
        const dateB = new Date(b.timestamp || 0);
        return dateB - dateA;
    });
    
    let html = '<div class="history-table-container">';
    html += '<table class="history-table">';
    html += '<thead><tr><th>Date/Time</th><th>Command</th><th>Status</th><th>Steps</th></tr></thead>';
    html += '<tbody>';
    
    sortedHistory.forEach(entry => {
        const timestamp = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Unknown';
        const command = entry.command || 'N/A';
        const success = entry.success !== undefined ? entry.success : true;
        const steps = entry.steps ? entry.steps.length : 0;
        const statusClass = success ? 'status-success' : 'status-error';
        const statusText = success ? '✓ Success' : '✗ Failed';
        
        html += `<tr>`;
        html += `<td>${timestamp}</td>`;
        html += `<td><code>${escapeHtml(command)}</code></td>`;
        html += `<td><span class="${statusClass}">${statusText}</span></td>`;
        html += `<td>${steps}</td>`;
        html += `</tr>`;
    });
    
    html += '</tbody></table>';
    html += '</div>';
    html += `<div style="margin-top: var(--space-4); padding: var(--space-3); background: var(--bg-elevated); border-radius: var(--radius-md); font-size: var(--text-sm); color: var(--text-secondary);">`;
    html += `<strong>Total:</strong> ${sortedHistory.length} ${sortedHistory.length === 1 ? 'entry' : 'entries'}`;
    html += `</div>`;
    
    historyContainer.innerHTML = html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function installDesktopApp() {
    const statusDiv = document.getElementById('install-desktop-status');
    const installBtn = document.getElementById('install-desktop-btn');
    
    // Check if already installed
    const isInstalled = await window.electronAPI.isDesktopAppInstalled();
    if (isInstalled) {
        if (confirm('Application is already installed. Reinstall?')) {
            // Continue with installation
        } else {
            return;
        }
    }
    
    installBtn.disabled = true;
    statusDiv.innerHTML = '<span style="color: #f39c12;">Installing...</span>';
    
    try {
        const result = await window.electronAPI.installDesktopApp();
        
        if (result.success) {
            statusDiv.innerHTML = '<span style="color: #27ae60;">✓ ' + (result.message || 'Application installed successfully!') + '</span>';
            installBtn.textContent = '✓ Installed';
            installBtn.disabled = true;
            
            // Show additional info if available
            if (result.output) {
                console.log('Installation output:', result.output);
            }
        } else {
            statusDiv.innerHTML = '<span style="color: #e74c3c;">✗ Error: ' + (result.error || 'Installation failed') + '</span>';
            installBtn.disabled = false;
            
            if (result.output) {
                console.error('Installation error output:', result.output);
            }
        }
    } catch (error) {
        console.error('Error installing desktop app:', error);
        statusDiv.innerHTML = '<span style="color: #e74c3c;">✗ Error: ' + error.message + '</span>';
        installBtn.disabled = false;
    }
}

async function checkDesktopAppStatus() {
    try {
        const isInstalled = await window.electronAPI.isDesktopAppInstalled();
        const installBtn = document.getElementById('install-desktop-btn');
        const statusDiv = document.getElementById('install-desktop-status');
        
        if (isInstalled) {
            installBtn.textContent = '✓ Already Installed';
            installBtn.disabled = true;
            statusDiv.innerHTML = '<span style="color: #27ae60;">Application is installed in your applications menu</span>';
        }
    } catch (error) {
        console.error('Error checking desktop app status:', error);
    }
}

async function browseSSLFile(type) {
    try {
        const result = await window.electronAPI.browseFile({
            properties: ['openFile'],
            filters: [
                { name: 'Certificate/Key Files', extensions: ['pem', 'crt', 'key', 'cert'] },
                { name: 'All Files', extensions: ['*'] }
            ],
            title: type === 'cert' ? 'Select SSL Certificate File' : 'Select SSL Private Key File'
        });
        
        if (!result.canceled && result.filePaths && result.filePaths.length > 0) {
            const filePath = result.filePaths[0];
            if (type === 'cert') {
                document.getElementById('ssl-cert').value = filePath;
            } else {
                document.getElementById('ssl-key').value = filePath;
            }
        }
    } catch (error) {
        console.error('Error browsing SSL file:', error);
        alert(`Error: ${error.message}`);
    }
}

async function browseDirectory(fieldId) {
    try {
        const result = await window.electronAPI.browseDirectory();
        
        if (!result.canceled && result.filePaths && result.filePaths.length > 0) {
            document.getElementById(fieldId).value = result.filePaths[0];
        }
    } catch (error) {
        console.error('Error browsing directory:', error);
        alert(`Error: ${error.message}`);
    }
}

async function checkInitialServerStatus() {
    // First check if port is in use by another process
    const config = currentConfig || await window.electronAPI.loadConfig();
    const port = config?.port || 5000;
    const portInUse = await window.electronAPI.isPortInUse(port);
    
    // Remove click listener initially
    const indicator = document.getElementById('status-indicator');
    indicator.onclick = null;
    
    // If port is in use, check if it's our server by doing a health check
    if (portInUse) {
        try {
            const isHealthy = await checkServerHealth(config);
            if (isHealthy) {
                // Port is in use and health check passed - our server is running
                serverRunning = true;
                updateServerStatus('running');
                updateButtons();
                startStatusMonitoring();
                return;
            } else {
                // Port is in use but health check failed - another process is using the port
                updateServerStatus('port-in-use', `Port ${port} in use (click to view)`);
                indicator.onclick = showPortInUseDialog;
                return;
            }
        } catch (error) {
            // Health check failed, assume port is in use by another process
            updateServerStatus('port-in-use', `Port ${port} in use (click to view)`);
            indicator.onclick = showPortInUseDialog;
            return;
        }
    }
    
    // Port is not in use, but check if our server process is running (might be starting)
    const running = await window.electronAPI.isServerRunning();
    if (running) {
        serverRunning = true;
        updateServerStatus('starting'); // Server process exists but might not be ready yet
        updateButtons();
        startStatusMonitoring();
    } else {
        // Also do a health check as a fallback (in case server was started externally)
        try {
            const isHealthy = await checkServerHealth(config);
            if (isHealthy) {
                serverRunning = true;
                updateServerStatus('running');
                updateButtons();
                startStatusMonitoring();
            } else {
                updateServerStatus('stopped');
            }
        } catch (error) {
            updateServerStatus('stopped');
        }
    }
}

function toggleConfigSection(header) {
    const section = header.closest('.config-section');
    if (section) {
        section.classList.toggle('collapsed');
    }
}

function displaySystemInfo() {
    const container = document.getElementById('system-info-container');
    
    if (!serverRunning && !serverFullyStarted) {
        container.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">ℹ️</div>
                <h3>Server Not Running</h3>
                <p>Start the server to view system information.</p>
            </div>
        `;
        return;
    }
    
    if (Object.keys(systemInfo).length === 0) {
        container.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">⏳</div>
                <h3>System Information Loading</h3>
                <p>Waiting for server to provide system information...</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="system-info-grid">';
    
    // Server Information Section
    html += '<div class="system-info-section">';
    html += '<h3>🖥️ Server Information</h3>';
    html += '<div class="system-info-list">';
    if (systemInfo.serverVersion) {
        html += `<div class="system-info-item"><span class="info-label">Server Version:</span><span class="info-value">v${systemInfo.serverVersion}</span></div>`;
    }
    if (systemInfo.listeningAddress) {
        html += `<div class="system-info-item"><span class="info-label">Listening Address:</span><span class="info-value">${escapeHtml(systemInfo.listeningAddress)}</span></div>`;
    }
    if (systemInfo.debugMode) {
        html += `<div class="system-info-item"><span class="info-label">Debug Mode:</span><span class="info-value">${systemInfo.debugMode}</span></div>`;
    }
    if (systemInfo.defaultLanguage) {
        html += `<div class="system-info-item"><span class="info-label">Default Language:</span><span class="info-value">${escapeHtml(systemInfo.defaultLanguage)}</span></div>`;
    }
    html += '</div></div>';
    
    // AI Models Section
    html += '<div class="system-info-section">';
    html += '<h3>🤖 AI Models</h3>';
    html += '<div class="system-info-list">';
    if (systemInfo.whisperModel) {
        html += `<div class="system-info-item"><span class="info-label">Whisper Model:</span><span class="info-value">${escapeHtml(systemInfo.whisperModel)}</span></div>`;
    }
    if (systemInfo.whisperInitTime) {
        html += `<div class="system-info-item"><span class="info-label">Whisper Init Time:</span><span class="info-value">${escapeHtml(systemInfo.whisperInitTime)}</span></div>`;
    }
    if (systemInfo.ollamaModel) {
        html += `<div class="system-info-item"><span class="info-label">Ollama Model:</span><span class="info-value">${escapeHtml(systemInfo.ollamaModel)}</span></div>`;
    }
    html += '</div></div>';
    
    // Hardware Section
    html += '<div class="system-info-section">';
    html += '<h3>💻 Hardware</h3>';
    html += '<div class="system-info-list">';
    if (systemInfo.gpu) {
        html += `<div class="system-info-item"><span class="info-label">GPU:</span><span class="info-value">${escapeHtml(systemInfo.gpu)}</span></div>`;
    }
    if (systemInfo.cudaDevice) {
        html += `<div class="system-info-item"><span class="info-label">CUDA Device:</span><span class="info-value">${escapeHtml(systemInfo.cudaDevice)}</span></div>`;
    }
    html += '</div></div>';
    
    // Configuration Section
    html += '<div class="system-info-section">';
    html += '<h3>⚙️ Configuration</h3>';
    html += '<div class="system-info-list">';
    if (systemInfo.screenshotDir) {
        html += `<div class="system-info-item"><span class="info-label">Screenshot Directory:</span><span class="info-value">${escapeHtml(systemInfo.screenshotDir)}</span></div>`;
    }
    if (systemInfo.screenshotMaxAge) {
        html += `<div class="system-info-item"><span class="info-label">Screenshot Max Age:</span><span class="info-value">${escapeHtml(systemInfo.screenshotMaxAge)}</span></div>`;
    }
    if (systemInfo.screenshotMaxCount) {
        html += `<div class="system-info-item"><span class="info-label">Screenshot Max Count:</span><span class="info-value">${escapeHtml(systemInfo.screenshotMaxCount)}</span></div>`;
    }
    if (systemInfo.commandHistoryFile) {
        html += `<div class="system-info-item"><span class="info-label">Command History File:</span><span class="info-value">${escapeHtml(systemInfo.commandHistoryFile)}</span></div>`;
    }
    if (systemInfo.failsafe) {
        html += `<div class="system-info-item"><span class="info-label">PyAutoGUI Failsafe:</span><span class="info-value">${systemInfo.failsafe}</span></div>`;
    }
    if (systemInfo.visionCaptioning) {
        html += `<div class="system-info-item"><span class="info-label">Vision Captioning:</span><span class="info-value">${systemInfo.visionCaptioning}</span></div>`;
    }
    html += '</div></div>';
    
    html += '</div>';
    
    container.innerHTML = html;
}

function refreshSystemInfo() {
    systemInfo = {};
    displaySystemInfo();
}

// ============================================
// VOICE COMMAND FUNCTIONALITY
// ============================================

function setupVoiceCommandButton() {
    const voiceBtn = document.getElementById('voice-command-btn');
    if (!voiceBtn) return;
    
    // Mouse events
    voiceBtn.addEventListener('mousedown', handleVoiceButtonPress);
    voiceBtn.addEventListener('mouseup', handleVoiceButtonRelease);
    voiceBtn.addEventListener('mouseleave', handleVoiceButtonRelease);
    
    // Touch events for mobile
    voiceBtn.addEventListener('touchstart', (e) => {
        e.preventDefault();
        handleVoiceButtonPress();
    });
    voiceBtn.addEventListener('touchend', (e) => {
        e.preventDefault();
        handleVoiceButtonRelease();
    });
    voiceBtn.addEventListener('touchcancel', (e) => {
        e.preventDefault();
        handleVoiceButtonRelease();
    });
}

async function requestMicrophonePermission() {
    try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            throw new Error('MediaDevices API not available');
        }
        
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            } 
        });
        
        return stream;
    } catch (error) {
        console.error('Error requesting microphone permission:', error);
        updateVoiceStatus('error', 'Microphone access denied. Please enable microphone permissions.');
        throw error;
    }
}

async function startVoiceRecording() {
    if (isRecording) return;
    
    try {
        // Request microphone permission and get stream
        audioStream = await requestMicrophonePermission();
        
        // Check MediaRecorder support
        if (!window.MediaRecorder) {
            throw new Error('MediaRecorder API not supported');
        }
        
        // Determine MIME type
        let mimeType = 'audio/webm';
        if (!MediaRecorder.isTypeSupported('audio/webm')) {
            if (MediaRecorder.isTypeSupported('audio/mp4')) {
                mimeType = 'audio/mp4';
            } else if (MediaRecorder.isTypeSupported('audio/wav')) {
                mimeType = 'audio/wav';
            } else {
                mimeType = ''; // Use default
            }
        }
        
        // Create MediaRecorder
        const options = { mimeType: mimeType };
        mediaRecorder = new MediaRecorder(audioStream, options);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };
        
        mediaRecorder.onstop = async () => {
            // Stop all tracks
            if (audioStream) {
                audioStream.getTracks().forEach(track => track.stop());
                audioStream = null;
            }
            
            // Create blob from chunks
            if (audioChunks.length > 0) {
                const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/webm' });
                await sendVoiceCommand(audioBlob);
            } else {
                updateVoiceStatus('error', 'No audio recorded');
                setRecordingState('idle');
            }
        };
        
        mediaRecorder.onerror = (event) => {
            console.error('MediaRecorder error:', event.error);
            updateVoiceStatus('error', 'Recording error occurred');
            stopVoiceRecording();
        };
        
        // Start recording
        mediaRecorder.start();
        isRecording = true;
        setRecordingState('recording');
        updateVoiceStatus('recording', 'Recording... Release to send');
        
    } catch (error) {
        console.error('Error starting voice recording:', error);
        updateVoiceStatus('error', error.message || 'Failed to start recording');
        setRecordingState('idle');
        isRecording = false;
    }
}

function stopVoiceRecording() {
    if (!isRecording || !mediaRecorder) return;
    
    try {
        if (mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
        }
        isRecording = false;
        setRecordingState('processing');
        updateVoiceStatus('processing', 'Processing...');
    } catch (error) {
        console.error('Error stopping voice recording:', error);
        updateVoiceStatus('error', 'Error stopping recording');
        setRecordingState('idle');
        isRecording = false;
    }
}

async function sendVoiceCommand(audioBlob) {
    if (!serverRunning && !serverFullyStarted) {
        updateVoiceStatus('error', 'Server is not running');
        setRecordingState('idle');
        return;
    }
    
    try {
        const config = currentConfig || await window.electronAPI.loadConfig();
        if (!config) {
            updateVoiceStatus('error', 'Configuration not available');
            setRecordingState('idle');
            return;
        }
        
        // Build URL
        const isLocalhost = config.host === '0.0.0.0' || config.host === 'localhost' || config.host === '127.0.0.1';
        let protocol = config.ssl ? 'https' : 'http';
        const host = config.host === '0.0.0.0' ? 'localhost' : config.host;
        let url = `${protocol}://${host}:${config.port}/voice-command`;
        
        // Create FormData
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('language', config.language || 'es');
        formData.append('model', config.whisper_model || 'large');
        formData.append('capture_screenshot', config.screenshots_enabled !== false ? 'true' : 'false');
        
        // Send request
        updateVoiceStatus('processing', 'Sending command...');
        
        let response;
        try {
            response = await fetch(url, {
                method: 'POST',
                body: formData,
                signal: AbortSignal.timeout(60000) // 60 second timeout
            });
        } catch (error) {
            // If HTTPS failed and we're on localhost, try HTTP as fallback
            if (config.ssl && isLocalhost && (error.message.includes('SSL') || error.message.includes('certificate') || error.message.includes('Failed to fetch'))) {
                protocol = 'http';
                url = `http://${host}:${config.port}/voice-command`;
                response = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    signal: AbortSignal.timeout(60000)
                });
            } else {
                throw error;
            }
        }
        
        if (!response.ok) {
            const errorText = await response.text().catch(() => 'Unknown error');
            throw new Error(`Server error: ${response.status} - ${errorText}`);
        }
        
        const result = await response.json();
        
        // Show success message
        if (result.transcription && result.transcription.text) {
            updateVoiceStatus('success', `Command: "${result.transcription.text}"`);
        } else if (result.success) {
            updateVoiceStatus('success', 'Command executed successfully');
        } else {
            updateVoiceStatus('error', result.error || 'Command execution failed');
        }
        
        // Add log entry
        if (result.transcription && result.transcription.text) {
            addLogEntry(`🎤 Voice command: "${result.transcription.text}"\n`);
        }
        
        // Reset after 3 seconds
        setTimeout(() => {
            setRecordingState('idle');
            updateVoiceStatus('', '');
        }, 3000);
        
    } catch (error) {
        console.error('Error sending voice command:', error);
        updateVoiceStatus('error', error.message || 'Failed to send voice command');
        setRecordingState('idle');
        
        // Reset after 3 seconds
        setTimeout(() => {
            setRecordingState('idle');
            updateVoiceStatus('', '');
        }, 3000);
    }
}

function handleVoiceButtonPress() {
    if (recordingState === 'processing' || recordingState === 'recording') {
        return;
    }
    
    if (!serverRunning && !serverFullyStarted) {
        updateVoiceStatus('error', 'Server is not running');
        return;
    }
    
    startVoiceRecording();
}

function handleVoiceButtonRelease() {
    if (isRecording && mediaRecorder && mediaRecorder.state === 'recording') {
        stopVoiceRecording();
    }
}

function setRecordingState(state) {
    recordingState = state;
    const voiceBtn = document.getElementById('voice-command-btn');
    if (!voiceBtn) return;
    
    // Remove all state classes
    voiceBtn.classList.remove('recording', 'processing', 'error');
    voiceBtn.disabled = false;
    
    // Add current state class
    if (state === 'recording') {
        voiceBtn.classList.add('recording');
    } else if (state === 'processing') {
        voiceBtn.classList.add('processing');
        voiceBtn.disabled = true;
    } else if (state === 'error') {
        voiceBtn.classList.add('error');
    }
}

function updateVoiceStatus(type, message) {
    const statusEl = document.getElementById('voice-status');
    if (!statusEl) return;
    
    // Remove all status classes
    statusEl.classList.remove('show', 'success', 'error', 'processing');
    
    if (message) {
        statusEl.textContent = message;
        statusEl.classList.add('show');
        if (type) {
            statusEl.classList.add(type);
        }
    } else {
        statusEl.textContent = '';
    }
}

// ============================================
// TITLE BAR CONTROLS
// ============================================

function setupTitleBarControls() {
    const minimizeBtn = document.getElementById('title-bar-minimize');
    const maximizeBtn = document.getElementById('title-bar-maximize');
    const closeBtn = document.getElementById('title-bar-close');
    
    if (minimizeBtn) {
        minimizeBtn.addEventListener('click', async () => {
            await window.electronAPI.windowMinimize();
        });
    }
    
    if (maximizeBtn) {
        maximizeBtn.addEventListener('click', async () => {
            const result = await window.electronAPI.windowMaximize();
            updateMaximizeButton(result.isMaximized);
        });
        
        // Update button icon on window state change
        updateMaximizeButton();
    }
    
    if (closeBtn) {
        closeBtn.addEventListener('click', async () => {
            await window.electronAPI.windowClose();
        });
    }
}

async function updateMaximizeButton(isMaximized) {
    const maximizeBtn = document.getElementById('title-bar-maximize');
    if (!maximizeBtn) return;
    
    // Get current state if not provided
    if (isMaximized === undefined) {
        isMaximized = await window.electronAPI.windowIsMaximized();
    }
    
    // Update icon: □ for maximize, ❐ for restore
    if (isMaximized) {
        maximizeBtn.querySelector('span').textContent = '❐';
        maximizeBtn.setAttribute('aria-label', 'Restore');
    } else {
        maximizeBtn.querySelector('span').textContent = '□';
        maximizeBtn.setAttribute('aria-label', 'Maximize');
    }
}

// Update maximize button when window state changes
if (window.electronAPI) {
    // Listen for window state changes (if available)
    // Note: Electron doesn't expose this directly, so we'll update on user interaction
}
