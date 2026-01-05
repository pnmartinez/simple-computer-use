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
            
            const loadingText = typeof t !== 'undefined' ? t('errors.loading') : 'Loading application...';
            spinner.innerHTML = `
                <div style="margin-bottom: 10px;">
                    <div style="border: 3px solid #f3f3f3; border-top: 3px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                </div>
                <div style="color: #2c3e50; font-size: 14px;">${loadingText}</div>
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
                const errorMsg = typeof t !== 'undefined' 
                    ? t('errors.electronAPINotAvailable', { maxWait })
                    : `electronAPI is not available after ${maxWait}ms. The preload script may not have loaded correctly.`;
                reject(new Error(errorMsg));
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
        // Initialize i18n first
        await init();
        applyTranslations();
        
        // Setup language selector
        setupLanguageSelector();
        
        // Listen for language changes
        window.addEventListener('languageChanged', () => {
            applyTranslations();
            // Re-apply dynamic content that was generated
            if (serverRunning || serverFullyStarted) {
                updateServerStatus(serverRunning ? (serverFullyStarted ? 'running' : 'starting') : 'stopped');
            }
        });
        
        // Esperar a que electronAPI esté disponible
        await waitForElectronAPI(3000);
        
        // Inicializar dark mode
        initDarkMode();
        
        // Inicializar la aplicación
        await loadConfiguration();
        setupEventListeners();
        setupServerEventListeners();
        setupOllamaPullProgress();
        setupTabs();
        setupVoiceCommandButton();
        setupTitleBarControls();
        checkInitialServerStatus();
        checkDesktopAppStatus();
    } catch (error) {
        console.error('Error al inicializar la aplicación:', error);
        // Solo mostrar error si realmente falló después de esperar
        const errorTitle = t ? t('errors.loadError') : 'Load Error';
        const errorDesc = t ? t('errors.loadErrorDesc') : 'Could not load Electron API. Please verify that the preload script is configured correctly.';
        const reloadText = t ? t('errors.reloadApp') : 'Reload Application';
        document.body.innerHTML = `
            <div style="padding: 20px; font-family: Arial, sans-serif;">
                <h1 style="color: #e74c3c;">${errorTitle}</h1>
                <p>${errorDesc}</p>
                <p style="color: #7f8c8d; font-size: 12px;">Error: ${error.message}</p>
                <p style="margin-top: 20px;">
                    <button onclick="location.reload()" style="padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
                        ${reloadText}
                    </button>
                </p>
            </div>
        `;
    }
});

function setupLanguageSelector() {
    const selector = document.getElementById('language-selector');
    if (!selector) return;
    
    // Set current language
    const currentLang = getCurrentLanguage();
    selector.value = currentLang;
    
    // Update option texts
    const options = selector.querySelectorAll('option');
    options.forEach(option => {
        if (option.hasAttribute('data-i18n')) {
            const key = option.getAttribute('data-i18n');
            option.textContent = t(key);
        }
    });
    
    // Handle language change
    selector.addEventListener('change', async (e) => {
        const newLang = e.target.value;
        await setLanguage(newLang);
        
        // Save language preference to config file
        if (window.electronAPI && window.electronAPI.saveConfig) {
            const config = currentConfig || await window.electronAPI.loadConfig();
            if (config) {
                config.preferredLanguage = newLang;
                await window.electronAPI.saveConfig(config);
                currentConfig = config;
            }
        }
        
        // Update option texts after language change
        options.forEach(option => {
            if (option.hasAttribute('data-i18n')) {
                const key = option.getAttribute('data-i18n');
                option.textContent = t(key);
            }
        });
    });
}

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
        if (!serverRunning) {
            serverRunning = true;
            serverFullyStarted = false;
            updateServerStatus('starting');
            updateButtons();
            startStatusMonitoring();
        }
        addLogEntry(data);
        // Extract system info from all logs (not just startup)
        extractSystemInfo(data);
        // Check if server has fully started by analyzing logs
        checkServerStartupComplete(data);
    });
    window.electronAPI.onServerStopped((code) => {
        handleServerStopped(code);
    });
    window.electronAPI.onServerStarted(() => {
        if (!serverRunning) {
            serverRunning = true;
            serverFullyStarted = false;
            updateServerStatus('starting');
            updateButtons();
            startStatusMonitoring();
        }
    });
}

function setupOllamaPullProgress() {
    const modal = document.getElementById('ollama-pull-modal');
    const modelNameEl = document.getElementById('ollama-pull-model-name');
    const statusEl = document.getElementById('ollama-pull-status');
    const progressFillEl = document.getElementById('ollama-pull-progress-fill');
    const progressTextEl = document.getElementById('ollama-pull-progress-text');
    const messageEl = document.getElementById('ollama-pull-message');
    
    // Handle pull start
    window.electronAPI.onOllamaPullStart((data) => {
        if (modal && modelNameEl && statusEl && progressFillEl && progressTextEl) {
            modal.style.display = 'flex';
            modelNameEl.textContent = data.model || 'gemma3:12b';
            statusEl.textContent = t('ollama.starting');
            progressFillEl.style.width = '0%';
            progressTextEl.textContent = '0%';
            messageEl.textContent = '';
        }
    });
    
    // Handle pull progress
    window.electronAPI.onOllamaPullProgress((data) => {
        if (modal && statusEl && progressFillEl && progressTextEl && messageEl) {
            // Update progress bar
            const percent = Math.min(100, Math.max(0, data.percent || 0));
            progressFillEl.style.width = `${percent}%`;
            progressTextEl.textContent = `${percent.toFixed(1)}%`;
            
            // Update status
            if (data.status) {
                statusEl.textContent = data.status;
            }
            
            // Update message (show last few lines)
            if (data.message) {
                const lines = data.message.split('\n').filter(l => l.trim());
                if (lines.length > 0) {
                    const lastLine = lines[lines.length - 1];
                    messageEl.textContent = lastLine.substring(0, 100); // Limit length
                }
            }
        }
    });
    
    // Handle pull complete
    window.electronAPI.onOllamaPullComplete((data) => {
        if (modal && statusEl && progressFillEl && progressTextEl) {
            if (data.success) {
                statusEl.textContent = t('ollama.completed');
                progressFillEl.style.width = '100%';
                progressTextEl.textContent = '100%';
                messageEl.textContent = data.message || t('ollama.modelDownloaded');
                
                // Hide modal after 2 seconds
                setTimeout(() => {
                    if (modal) {
                        modal.style.display = 'none';
                    }
                }, 2000);
            } else {
                statusEl.textContent = t('ollama.error');
                statusEl.style.color = 'var(--color-error)';
                messageEl.textContent = data.error || t('errors.unknown');
                messageEl.style.color = 'var(--color-error)';
                
                // Hide modal after 5 seconds on error
                setTimeout(() => {
                    if (modal) {
                        modal.style.display = 'none';
                        statusEl.style.color = ''; // Reset color
                        messageEl.style.color = ''; // Reset color
                    }
                }, 5000);
            }
        }
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
            addLogEntry(t('status.serverReady') + '\n');
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
    // If server is already running, stop it first to ensure clean restart with new config
    if (serverRunning) {
        console.log('Server is running, stopping it first to apply new configuration...');
        await stopServer();
        // Wait a bit to ensure the process is fully terminated
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
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
            addLogEntry(t('status.starting') + '...\n');
        } else {
            // Remove loading state on error
            startBtn.classList.remove('loading');
            startBtn.disabled = false;
            alert(`${t('errors.failedToStart')} ${result.error}`);
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
            addLogEntry(t('status.stopped') + '.\n');
        } else {
            // Remove loading state on error
            stopBtn.classList.remove('loading');
            stopBtn.disabled = false;
            alert(`${t('errors.failedToStop')} ${result.error}`);
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
        indicator.title = t('errors.clickToViewProcess');
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
        indicator.textContent = status === 'stopped' ? t('status.stopped') : 
                               status === 'starting' ? t('status.starting') : 
                               status === 'running' ? t('status.running') : 
                               status === 'port-in-use' ? t('status.portInUse') : 
                               t('status.error');
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
                <h3>${t('systemInfo.notAvailable')}</h3>
                <p>${t('systemInfo.notAvailableDesc')}</p>
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
    addLogEntry(t('logs.cleared') + '\n');
}

async function saveConfig() {
    const config = getConfigFromForm();
    const wasRunning = serverRunning;
    
    try {
        const result = await window.electronAPI.saveConfig(config);
        if (result) {
            currentConfig = config;
            
            // Handle startup service installation/removal
            let serviceMessage = '';
            if (config.start_on_boot) {
                const serviceResult = await window.electronAPI.installStartupService();
                if (serviceResult.success) {
                    serviceMessage = '\n' + t('errors.startupServiceInstalled');
                } else {
                    serviceMessage = '\n' + t('errors.startupServiceFailed') + ' ' + serviceResult.error;
                }
            } else {
                const serviceResult = await window.electronAPI.uninstallStartupService();
                if (serviceResult.success) {
                    serviceMessage = '\n' + t('errors.startupServiceRemoved');
                } else {
                    serviceMessage = '\n' + t('errors.startupServiceRemoveFailed') + ' ' + serviceResult.error;
                }
            }
            
            // If server is running, restart it to apply new configuration
            if (wasRunning) {
                console.log('Server is running, restarting to apply new configuration...');
                addLogEntry(t('errors.configSavedRestarting') + '\n');
                
                // Stop the server first
                await stopServer();
                // Wait a bit to ensure the process is fully terminated
                await new Promise(resolve => setTimeout(resolve, 1500));
                
                // Start the server with new configuration
                const startResult = await window.electronAPI.startServer(config);
                if (startResult.success) {
                    serverRunning = true;
                    serverFullyStarted = false;
                    updateServerStatus('starting');
                    updateButtons();
                    startStatusMonitoring();
                    addLogEntry(t('status.serverRestarting') + '\n');
                    alert(t('errors.configSavedRestart') + serviceMessage);
                } else {
                    alert(t('errors.configSavedNoRestart') + ':\n' + startResult.error + serviceMessage);
                }
            } else {
                // Server not running, just save config
                alert(t('errors.configSaved') + serviceMessage + '\n\n' + t('errors.configSavedNote'));
            }
        }
    } catch (error) {
        console.error('Error saving config:', error);
        alert(t('errors.errorSaving') + ' ' + error.message);
    }
}

async function showPortInUseDialog() {
    const config = currentConfig || await window.electronAPI.loadConfig();
    const port = config?.port || 5000;
    
    try {
        const result = await window.electronAPI.getProcessUsingPort(port);
        
        if (result.success && result.process) {
            const process = result.process;
            const message = t('errors.portInUse', { port }) + ':\n\n' +
                          `PID: ${process.pid}\n` +
                          `Name: ${process.name}\n` +
                          `Command: ${process.command}\n\n` +
                          t('errors.killProcess');
            
            if (confirm(message)) {
                const killResult = await window.electronAPI.killProcess(process.pid);
                if (killResult.success) {
                    alert(t('errors.processKilled'));
                    // Recheck status
                    setTimeout(() => checkInitialServerStatus(), 1000);
                } else {
                    alert(t('errors.killFailed') + ' ' + killResult.error);
                }
            }
        } else {
            alert(t('errors.processInfoError') + ' ' + (result.error || t('errors.unknown')));
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
                <h3>${t('history.serverNotRunning')}</h3>
                <p>${t('history.serverNotRunningDesc')}</p>
            </div>
        `;
        return;
    }
    
    try {
        const config = currentConfig || await window.electronAPI.loadConfig();
        if (!config) {
            historyContainer.innerHTML = `<p style="color: #e74c3c;">${t('errors.configNotAvailable')}</p>`;
            return;
        }
        
        // For localhost, prefer HTTP if SSL causes issues, otherwise use configured protocol
        const isLocalhost = config.host === '0.0.0.0' || config.host === 'localhost' || config.host === '127.0.0.1';
        let protocol = config.ssl ? 'https' : 'http';
        const host = config.host === '0.0.0.0' ? 'localhost' : config.host;
        
        // Try HTTPS first if SSL is enabled, fallback to HTTP for localhost if it fails
        let url = `${protocol}://${host}:${config.port}/command-history?limit=50&date_filter=all`;
        
        historyContainer.innerHTML = `<div class="history-loading">${t('history.loading')}</div>`;
        
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
                    <h3>${t('history.connectionError')}</h3>
                    <p>${t('history.connectionErrorDesc')}</p>
                    <p style="font-size: var(--text-xs); color: var(--text-tertiary); margin-top: var(--space-2);">${t('errors.errorStarting')} ${healthError?.message || t('errors.unknown')}</p>
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
                historyContainer.innerHTML = `<p>${t('history.noHistoryFound')}</p>`;
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
            errorMessage = t('errors.connectionError');
        } else if (errorMessage.includes('timeout')) {
            errorMessage = t('errors.timeout');
        } else if (errorMessage.includes('SSL') || errorMessage.includes('certificate')) {
            errorMessage = t('errors.sslError');
        }
        
        historyContainer.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">⚠️</div>
                <h3>${t('history.errorLoading')}</h3>
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
                <h3>${t('history.noHistory')}</h3>
                <p>${t('history.noHistoryFound')}</p>
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
    html += `<thead><tr><th>${t('history.tableDate')}</th><th>${t('history.tableCommand')}</th><th>${t('history.tableStatus')}</th><th>${t('history.tableSteps')}</th></tr></thead>`;
    html += '<tbody>';
    
    sortedHistory.forEach(entry => {
        const timestamp = entry.timestamp ? new Date(entry.timestamp).toLocaleString() : 'Unknown';
        const command = entry.command || 'N/A';
        const success = entry.success !== undefined ? entry.success : true;
        const steps = entry.steps ? entry.steps.length : 0;
        const statusClass = success ? 'status-success' : 'status-error';
        const statusText = success ? t('history.statusSuccess') : t('history.statusFailed');
        
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
    html += `<strong>${t('history.totalEntries')}</strong> ${sortedHistory.length} ${sortedHistory.length === 1 ? t('history.entry') : t('history.entries')}`;
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
            if (confirm(t('errors.alreadyInstalled'))) {
            // Continue with installation
        } else {
            return;
        }
    }
    
    installBtn.disabled = true;
    statusDiv.innerHTML = `<span style="color: #f39c12;">${t('errors.installing')}</span>`;
    
    try {
        const result = await window.electronAPI.installDesktopApp();
        
        if (result.success) {
            statusDiv.innerHTML = `<span style="color: #27ae60;">✓ ${result.message || t('errors.desktopInstallSuccess')}</span>`;
            installBtn.textContent = t('buttons.installed');
            installBtn.disabled = true;
            
            // Show additional info if available
            if (result.output) {
                console.log('Installation output:', result.output);
            }
        } else {
            statusDiv.innerHTML = `<span style="color: #e74c3c;">✗ ${t('errors.desktopInstallFailed')} ${result.error || t('errors.unknown')}</span>`;
            installBtn.disabled = false;
            
            if (result.output) {
                console.error('Installation error output:', result.output);
            }
        }
    } catch (error) {
        console.error('Error installing desktop app:', error);
        statusDiv.innerHTML = `<span style="color: #e74c3c;">✗ ${t('errors.desktopInstallError')} ${error.message}</span>`;
        installBtn.disabled = false;
    }
}

async function checkDesktopAppStatus() {
    try {
        const isInstalled = await window.electronAPI.isDesktopAppInstalled();
        const installBtn = document.getElementById('install-desktop-btn');
        const statusDiv = document.getElementById('install-desktop-status');
        
        if (isInstalled) {
            installBtn.textContent = t('buttons.alreadyInstalled');
            installBtn.disabled = true;
            statusDiv.innerHTML = `<span style="color: #27ae60;">${t('config.installDesktopStatus')}</span>`;
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
            title: type === 'cert' ? t('config.sslCert') : t('config.sslKey')
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
                <h3>${t('systemInfo.serverNotRunning')}</h3>
                <p>${t('systemInfo.serverNotRunningDesc')}</p>
            </div>
        `;
        return;
    }
    
    if (Object.keys(systemInfo).length === 0) {
        container.innerHTML = `
            <div class="history-empty-state">
                <div class="history-empty-state-icon">⏳</div>
                <h3>${t('systemInfo.loading')}</h3>
                <p>${t('systemInfo.loadingDesc')}</p>
            </div>
        `;
        return;
    }
    
    let html = '<div class="system-info-grid">';
    
    // Server Information Section
    html += '<div class="system-info-section">';
    html += `<h3>${t('systemInfo.serverInfo')}</h3>`;
    html += '<div class="system-info-list">';
    if (systemInfo.serverVersion) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.serverVersion')}</span><span class="info-value">v${systemInfo.serverVersion}</span></div>`;
    }
    if (systemInfo.listeningAddress) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.listeningAddress')}</span><span class="info-value">${escapeHtml(systemInfo.listeningAddress)}</span></div>`;
    }
    if (systemInfo.debugMode) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.debugMode')}</span><span class="info-value">${systemInfo.debugMode}</span></div>`;
    }
    if (systemInfo.defaultLanguage) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.defaultLanguage')}</span><span class="info-value">${escapeHtml(systemInfo.defaultLanguage)}</span></div>`;
    }
    html += '</div></div>';
    
    // AI Models Section
    html += '<div class="system-info-section">';
    html += `<h3>${t('systemInfo.aiModels')}</h3>`;
    html += '<div class="system-info-list">';
    if (systemInfo.whisperModel) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.whisperModel')}</span><span class="info-value">${escapeHtml(systemInfo.whisperModel)}</span></div>`;
    }
    if (systemInfo.whisperInitTime) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.whisperInitTime')}</span><span class="info-value">${escapeHtml(systemInfo.whisperInitTime)}</span></div>`;
    }
    if (systemInfo.ollamaModel) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.ollamaModel')}</span><span class="info-value">${escapeHtml(systemInfo.ollamaModel)}</span></div>`;
    }
    html += '</div></div>';
    
    // Hardware Section
    html += '<div class="system-info-section">';
    html += `<h3>${t('systemInfo.hardware')}</h3>`;
    html += '<div class="system-info-list">';
    if (systemInfo.gpu) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.gpu')}</span><span class="info-value">${escapeHtml(systemInfo.gpu)}</span></div>`;
    }
    if (systemInfo.cudaDevice) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.cudaDevice')}</span><span class="info-value">${escapeHtml(systemInfo.cudaDevice)}</span></div>`;
    }
    html += '</div></div>';
    
    // Configuration Section
    html += '<div class="system-info-section">';
    html += `<h3>${t('systemInfo.configuration')}</h3>`;
    html += '<div class="system-info-list">';
    if (systemInfo.screenshotDir) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.screenshotDir')}</span><span class="info-value">${escapeHtml(systemInfo.screenshotDir)}</span></div>`;
    }
    if (systemInfo.screenshotMaxAge) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.screenshotMaxAge')}</span><span class="info-value">${escapeHtml(systemInfo.screenshotMaxAge)}</span></div>`;
    }
    if (systemInfo.screenshotMaxCount) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.screenshotMaxCount')}</span><span class="info-value">${escapeHtml(systemInfo.screenshotMaxCount)}</span></div>`;
    }
    if (systemInfo.commandHistoryFile) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.commandHistoryFile')}</span><span class="info-value">${escapeHtml(systemInfo.commandHistoryFile)}</span></div>`;
    }
    if (systemInfo.failsafe) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.failsafe')}</span><span class="info-value">${systemInfo.failsafe}</span></div>`;
    }
    if (systemInfo.visionCaptioning) {
        html += `<div class="system-info-item"><span class="info-label">${t('systemInfo.visionCaptioning')}</span><span class="info-value">${systemInfo.visionCaptioning}</span></div>`;
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
        updateVoiceStatus('error', t('voice.microphoneDenied'));
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
                updateVoiceStatus('error', t('voice.noAudio'));
                setRecordingState('idle');
            }
        };
        
        mediaRecorder.onerror = (event) => {
            console.error('MediaRecorder error:', event.error);
            updateVoiceStatus('error', t('voice.recordingError'));
            stopVoiceRecording();
        };
        
        // Start recording
        mediaRecorder.start();
        isRecording = true;
        setRecordingState('recording');
        updateVoiceStatus('recording', t('voice.recording') + ' ' + t('voice.releaseToSend'));
        
    } catch (error) {
        console.error('Error starting voice recording:', error);
        updateVoiceStatus('error', error.message || t('voice.failedToStart'));
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
        updateVoiceStatus('processing', t('voice.processing'));
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
            updateVoiceStatus('error', t('errors.configNotAvailable'));
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
        updateVoiceStatus('processing', t('voice.sending'));
        
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
            updateVoiceStatus('success', `${t('voice.command')}: "${result.transcription.text}"`);
        } else if (result.success) {
            updateVoiceStatus('success', t('voice.commandExecuted'));
        } else {
            updateVoiceStatus('error', result.error || t('voice.commandFailed'));
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
        updateVoiceStatus('error', error.message || t('voice.failedToSend'));
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
