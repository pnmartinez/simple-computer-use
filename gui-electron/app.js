let currentConfig = null;
let serverRunning = false;
let statusCheckInterval = null;
let portInUseState = false;
let serverFullyStarted = false;

document.addEventListener('DOMContentLoaded', async () => {
    await loadConfiguration();
    setupEventListeners();
    setupServerEventListeners();
    setupTabs();
    checkInitialServerStatus();
});

async function loadConfiguration() {
    try {
        currentConfig = await window.electronAPI.loadConfig();
        populateConfigForm(currentConfig);
        
        // Check if startup service is installed and update checkbox accordingly
        const isInstalled = await window.electronAPI.isStartupServiceInstalled();
        if (isInstalled && !currentConfig.start_on_boot) {
            // Service is installed but config doesn't reflect it - update config
            currentConfig.start_on_boot = true;
            document.getElementById('start-on-boot').checked = true;
        }
    } catch (error) {
        console.error('Error loading config:', error);
    }
}

function populateConfigForm(config) {
    document.getElementById('host').value = config.host || '0.0.0.0';
    document.getElementById('port').value = config.port || 5000;
    document.getElementById('whisper-model').value = config.whisper_model || 'large';
    document.getElementById('ollama-model').value = config.ollama_model || 'gemma3:12b';
    document.getElementById('ollama-host').value = config.ollama_host || 'http://localhost:11434';
    document.getElementById('start-on-boot').checked = config.start_on_boot || false;
}

function getConfigFromForm() {
    return {
        host: document.getElementById('host').value,
        port: parseInt(document.getElementById('port').value) || 5000,
        whisper_model: document.getElementById('whisper-model').value,
        ollama_model: document.getElementById('ollama-model').value,
        ollama_host: document.getElementById('ollama-host').value,
        ssl: true,  // SSL enabled - matches start-llm-control.sh
        translation_enabled: false,  // Disabled - matches --disable-translation
        screenshots_enabled: true,
        failsafe_enabled: false,
        debug: false,
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
        });
    });
}

async function startServer() {
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
            alert(`Failed to start server: ${result.error}`);
        }
    } catch (error) {
        console.error('Error starting server:', error);
        alert(`Error: ${error.message}`);
    }
}

async function stopServer() {
    try {
        const result = await window.electronAPI.stopServer();
        if (result.success) {
            serverRunning = false;
            updateServerStatus('stopped');
            updateButtons();
            stopStatusMonitoring();
            addLogEntry('Server stopped.\n');
        } else {
            alert(`Failed to stop server: ${result.error}`);
        }
    } catch (error) {
        console.error('Error stopping server:', error);
    }
}

function updateServerStatus(status, customText = null) {
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
        indicator.textContent = customText;
    } else {
        indicator.textContent = status === 'stopped' ? '● Stopped' : 
                               status === 'starting' ? '● Starting...' : 
                               status === 'running' ? '● Running' : 
                               status === 'port-in-use' ? '● Port in use' : 
                               '● Error';
    }
}

function updateButtons() {
    document.getElementById('start-btn').disabled = serverRunning;
    document.getElementById('stop-btn').disabled = !serverRunning;
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
                const protocol = config.ssl ? 'https' : 'http';
                const host = config.host === '0.0.0.0' ? 'localhost' : config.host;
                const url = `${protocol}://${host}:${config.port}/health`;
                const response = await fetch(url, { method: 'GET', signal: AbortSignal.timeout(2000) });
                if (response.ok) {
                    updateServerStatus('running');
                } else {
                    updateServerStatus('error');
                    serverFullyStarted = false; // Reset if health check fails
                }
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

async function checkInitialServerStatus() {
    // First check if port is in use by another process
    const config = currentConfig || await window.electronAPI.loadConfig();
    const port = config?.port || 5000;
    const portInUse = await window.electronAPI.isPortInUse(port);
    
    if (portInUse) {
        // Port is in use by another process
        updateServerStatus('port-in-use', `● Port ${port} in use (click to view)`);
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
