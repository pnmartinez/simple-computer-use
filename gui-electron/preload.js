const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
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
  
  // Remove listeners
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});
