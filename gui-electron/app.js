let currentConfig = null;
let serverRunning = false;
let statusCheckInterval = null;

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
        debug: false
    };
}

function setupEventListeners() {
    document.getElementById('start-btn').addEventListener('click', startServer);
    document.getElementById('stop-btn').addEventListener('click', stopServer);
}

function setupServerEventListeners() {
    window.electronAPI.onServerLog((data) => {
        addLogEntry(data);
    });
    window.electronAPI.onServerStopped((code) => {
        handleServerStopped(code);
    });
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

function updateServerStatus(status) {
    const indicator = document.getElementById('status-indicator');
    indicator.className = `status-indicator status-${status}`;
    indicator.textContent = status === 'stopped' ? '● Stopped' : 
                           status === 'starting' ? '● Starting...' : 
                           status === 'running' ? '● Running' : '● Error';
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
            }
        } catch (error) {
            if (serverRunning) updateServerStatus('starting');
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
            alert('Configuration saved successfully!');
        }
    } catch (error) {
        console.error('Error saving config:', error);
    }
}

async function checkInitialServerStatus() {
    const running = await window.electronAPI.isServerRunning();
    if (running) {
        serverRunning = true;
        updateServerStatus('running');
        updateButtons();
        startStatusMonitoring();
    }
}
