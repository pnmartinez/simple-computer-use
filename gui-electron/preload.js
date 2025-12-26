const { contextBridge, ipcRenderer } = require('electron');

// Log para verificar que el preload se está ejecutando
console.log('[Preload] Preload script cargado correctamente');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
try {
  contextBridge.exposeInMainWorld('electronAPI', {
  // Config management
  loadConfig: () => ipcRenderer.invoke('load-config'),
  saveConfig: (config) => ipcRenderer.invoke('save-config', config),
  
  // Server control
  startServer: (config) => ipcRenderer.invoke('start-server', config),
  stopServer: () => ipcRenderer.invoke('stop-server'),
  isServerRunning: () => ipcRenderer.invoke('is-server-running'),
  getServerConfig: () => ipcRenderer.invoke('get-server-config'),
  
  // File dialogs
  browseFile: (options) => ipcRenderer.invoke('browse-file', options),
  browseDirectory: () => ipcRenderer.invoke('browse-directory'),
  
  // Server events
  onServerLog: (callback) => {
    ipcRenderer.on('server-log', (event, data) => callback(data));
  },
  onServerStopped: (callback) => {
    ipcRenderer.on('server-stopped', (event, code) => callback(code));
  },
  onServerStarted: (callback) => {
    ipcRenderer.on('server-started', () => callback());
  },
  
  // Startup service management
  installStartupService: () => ipcRenderer.invoke('install-startup-service'),
  uninstallStartupService: () => ipcRenderer.invoke('uninstall-startup-service'),
  isStartupServiceInstalled: () => ipcRenderer.invoke('is-startup-service-installed'),
  
  // Desktop application installation
  installDesktopApp: () => ipcRenderer.invoke('install-desktop-app'),
  isDesktopAppInstalled: () => ipcRenderer.invoke('is-desktop-app-installed'),
  
  // Port checking
  isPortInUse: (port) => ipcRenderer.invoke('is-port-in-use', port),
  getProcessUsingPort: (port) => ipcRenderer.invoke('get-process-using-port', port),
  killProcess: (pid) => ipcRenderer.invoke('kill-process', pid),
  
  // Window control
  windowMinimize: () => ipcRenderer.invoke('window-minimize'),
  windowMaximize: () => ipcRenderer.invoke('window-maximize'),
  windowClose: () => ipcRenderer.invoke('window-close'),
  windowIsMaximized: () => ipcRenderer.invoke('window-is-maximized'),
  
  // Remove listeners
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});
  console.log('[Preload] electronAPI expuesto correctamente');
} catch (error) {
  console.error('[Preload] Error al exponer electronAPI:', error);
}
