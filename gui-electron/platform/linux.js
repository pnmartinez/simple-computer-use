/**
 * Linux platform implementation
 * Contains all Linux-specific functionality
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

// Import service management functions from main.js
// These will be moved here in the refactoring
function getServiceName() {
  return 'simple-computer-use-desktop.service';
}

function getServicePath() {
  return path.join(os.homedir(), '.config', 'systemd', 'user', getServiceName());
}

module.exports = {
  // Startup Service Management
  installStartupService() {
    // TODO: Move implementation from main.js
    // This is a placeholder - actual implementation should be moved here
    return { success: false, error: 'Not yet implemented - use main.js' };
  },
  
  uninstallStartupService() {
    // TODO: Move implementation from main.js
    return { success: false, error: 'Not yet implemented - use main.js' };
  },
  
  isStartupServiceInstalled() {
    // TODO: Move implementation from main.js
    return false;
  },
  
  // Process Management
  getProcessUsingPort(port) {
    // TODO: Move implementation from main.js (lsof/fuser)
    return { success: false, error: 'Not yet implemented - use main.js' };
  },
  
  killProcess(pid) {
    // TODO: Move implementation from main.js (kill)
    return Promise.resolve({ success: false, error: 'Not yet implemented - use main.js' });
  },
  
  // Python Detection
  findPythonExecutable() {
    // TODO: Move implementation from main.js
    const projectRoot = path.resolve(__dirname, '..', '..');
    const venvPython = path.join(projectRoot, 'venv-py312', 'bin', 'python');
    
    if (fs.existsSync(venvPython)) {
      return venvPython;
    }
    
    // Fallback to system Python
    const pythonCommands = ['python3', 'python'];
    for (const cmd of pythonCommands) {
      try {
        const result = execSync(`which ${cmd}`, { encoding: 'utf8' }).trim();
        if (result) return cmd;
      } catch (e) {
        // Continue
      }
    }
    return 'python3';
  },
  
  // Desktop Application Installation
  installDesktopApp() {
    // TODO: Move implementation from main.js (.desktop files)
    return Promise.resolve({ success: false, error: 'Not yet implemented - use main.js' });
  },
  
  isDesktopAppInstalled() {
    // TODO: Move implementation from main.js
    return false;
  },
  
  // Platform info
  getPlatformName() {
    return 'Linux';
  },
  
  getPlatformSpecificPaths() {
    return {
      configDir: path.join(os.homedir(), '.config'),
      applicationsDir: path.join(os.homedir(), '.local', 'share', 'applications'),
      systemdUserDir: path.join(os.homedir(), '.config', 'systemd', 'user')
    };
  }
};

