let currentConfig = null;
let serverRunning = false;
let statusCheckInterval = null;
let portInUseState = false;
let serverFullyStarted = false;

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
        // Check if server has fully started by analyzing logs
        checkServerStartupComplete(data);
    });
    window.electronAPI.onServerStopped((code) => {
        handleServerStopped(code);
    });
}

function checkServerStartupComplete(logData) {
    if (!serverRunning || serverFullyStarted) {
        return;
    }
    
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
    
    // Remove loading states when updating buttons
    startBtn.classList.remove('loading');
    stopBtn.classList.remove('loading');
    
    startBtn.disabled = serverRunning;
    stopBtn.disabled = !serverRunning;
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
                
                const isLocalhost = config.host === '0.0.0.0' || config.host === 'localhost' || config.host === '127.0.0.1';
                let protocol = config.ssl ? 'https' : 'http';
                const host = config.host === '0.0.0.0' ? 'localhost' : config.host;
                let url = `${protocol}://${host}:${config.port}/health`;
                
                try {
                    const response = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(2000) });
                    if (response.ok) {
                        updateServerStatus('running');
                        return;
                    }
                } catch (error) {
                    // If HTTPS failed and we're on localhost, try HTTP as fallback
                    if (config.ssl && isLocalhost && (error.message.includes('SSL') || error.message.includes('certificate') || error.message.includes('Failed to fetch'))) {
                        protocol = 'http';
                        url = `http://${host}:${config.port}/health`;
                        try {
                            const httpResponse = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(2000) });
                            if (httpResponse.ok) {
                                updateServerStatus('running');
                                return;
                            }
                        } catch (httpError) {
                            // Both failed, continue to error status
                        }
                    }
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
    }, 2000);
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
    updateServerStatus('stopped');
    updateButtons();
    stopStatusMonitoring();
    addLogEntry(`Server stopped with code ${code}\n`);
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
    
    if (portInUse) {
        // Port is in use by another process
        updateServerStatus('port-in-use', `Port ${port} in use (click to view)`);
        // Add click listener
        const indicator = document.getElementById('status-indicator');
        indicator.onclick = showPortInUseDialog;
        return;
    }
    
    // Remove click listener if port is not in use
    const indicator = document.getElementById('status-indicator');
    indicator.onclick = null;
    
    // Check if our server is running
    const running = await window.electronAPI.isServerRunning();
    if (running) {
        serverRunning = true;
        updateServerStatus('running');
        updateButtons();
        startStatusMonitoring();
    } else {
        updateServerStatus('stopped');
    }
}
