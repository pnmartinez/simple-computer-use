/**
 * macOS platform implementation
 * Contains all macOS-specific functionality
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

module.exports = {
  // Startup Service Management (Launch Agents)
  installStartupService() {
    try {
      const projectRoot = path.resolve(__dirname, '..', '..');
      const electronPath = require('electron');
      const launchAgentDir = path.join(os.homedir(), 'Library', 'LaunchAgents');
      const plistPath = path.join(launchAgentDir, 'com.simplecomputeruse.desktop.plist');
      
      // Create LaunchAgents directory if it doesn't exist
      if (!fs.existsSync(launchAgentDir)) {
        fs.mkdirSync(launchAgentDir, { recursive: true });
      }
      
      // Create plist file
      const plistContent = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.simplecomputeruse.desktop</string>
    <key>ProgramArguments</key>
    <array>
        <string>${electronPath}</string>
        <string>${path.join(projectRoot, 'gui-electron')}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>${path.join(os.homedir(), 'Library', 'Logs', 'simple-computer-use-desktop.log')}</string>
    <key>StandardErrorPath</key>
    <string>${path.join(os.homedir(), 'Library', 'Logs', 'simple-computer-use-desktop.error.log')}</string>
</dict>
</plist>`;
      
      fs.writeFileSync(plistPath, plistContent);
      
      // Load the launch agent
      try {
        execSync(`launchctl load "${plistPath}"`, { stdio: 'ignore' });
        return { success: true };
      } catch (error) {
        return { success: false, error: `Failed to load launch agent: ${error.message}` };
      }
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  uninstallStartupService() {
    try {
      const plistPath = path.join(os.homedir(), 'Library', 'LaunchAgents', 'com.simplecomputeruse.desktop.plist');
      
      // Unload the launch agent
      try {
        if (fs.existsSync(plistPath)) {
          execSync(`launchctl unload "${plistPath}"`, { stdio: 'ignore' });
        }
      } catch (error) {
        // Agent might not be loaded, continue
      }
      
      // Remove plist file
      if (fs.existsSync(plistPath)) {
        fs.unlinkSync(plistPath);
      }
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  isStartupServiceInstalled() {
    try {
      const plistPath = path.join(os.homedir(), 'Library', 'LaunchAgents', 'com.simplecomputeruse.desktop.plist');
      if (!fs.existsSync(plistPath)) {
        return false;
      }
      
      // Check if it's loaded
      const result = execSync('launchctl list | grep com.simplecomputeruse.desktop', {
        encoding: 'utf8',
        stdio: 'pipe'
      });
      return result.trim().length > 0;
    } catch (error) {
      return false;
    }
  },
  
  // Process Management (similar to Linux)
  getProcessUsingPort(port) {
    try {
      // lsof is available on macOS
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
        const psResult = execSync(`ps -p ${pid} -o pid,comm,command -c`, {
          encoding: 'utf8',
          stdio: 'pipe'
        });
        const lines = psResult.trim().split('\n');
        if (lines.length > 1) {
          const parts = lines[1].trim().split(/\s+/);
          return {
            success: true,
            process: {
              pid: parts[0],
              name: parts[1] || 'unknown',
              command: parts.slice(2).join(' ') || 'unknown'
            }
          };
        }
      } catch (e) {
        // Continue with just PID
      }
      
      return {
        success: true,
        process: {
          pid: pid,
          name: 'unknown',
          command: 'unknown'
        }
      };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  killProcess(pid) {
    return new Promise((resolve) => {
      try {
        // Try graceful kill first (SIGTERM)
        execSync(`kill ${pid}`, { stdio: 'ignore' });
        
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
          resolve({ success: false, error: error.message });
        }
      }
    });
  },
  
  // Python Detection (similar to Linux)
  findPythonExecutable() {
    const projectRoot = path.resolve(__dirname, '..', '..');
    const venvPython = path.join(projectRoot, 'venv-py312', 'bin', 'python');
    
    // First try: venv-py312
    if (fs.existsSync(venvPython)) {
      try {
        execSync(`"${venvPython}" --version`, { encoding: 'utf8', stdio: 'ignore' });
        return venvPython;
      } catch (e) {
        console.warn('venv-py312 Python found but not working, trying system Python');
      }
    }
    
    // Fallback: system Python
    const pythonCommands = ['python3', 'python'];
    for (const cmd of pythonCommands) {
      try {
        const result = execSync(`which ${cmd}`, { encoding: 'utf8' }).trim();
        if (result) return cmd;
      } catch (e) {
        // Continue to next
      }
    }
    return 'python3'; // Default fallback
  },
  
  // Desktop Application Installation (Application Bundle or alias)
  installDesktopApp() {
    return new Promise((resolve) => {
      try {
        const projectRoot = path.resolve(__dirname, '..', '..');
        const applicationsDir = path.join(os.homedir(), 'Applications');
        
        // Create Applications directory if it doesn't exist
        if (!fs.existsSync(applicationsDir)) {
          fs.mkdirSync(applicationsDir, { recursive: true });
        }
        
        // For now, create an alias (simpler than full .app bundle)
        // In production, you might want to use electron-builder to create a proper .app
        const aliasPath = path.join(applicationsDir, 'Simple Computer Use Desktop');
        
        // Create a shell script that launches Electron
        const electronPath = require('electron');
        const scriptContent = `#!/bin/bash
cd "${path.join(projectRoot, 'gui-electron')}"
"${electronPath}" .
`;
        
        fs.writeFileSync(aliasPath, scriptContent);
        fs.chmodSync(aliasPath, 0o755);
        
        resolve({
          success: true,
          message: 'Application installed to Applications folder',
          output: `Application launcher created at: ${aliasPath}`
        });
      } catch (error) {
        resolve({ success: false, error: error.message });
      }
    });
  },
  
  isDesktopAppInstalled() {
    try {
      const aliasPath = path.join(os.homedir(), 'Applications', 'Simple Computer Use Desktop');
      return fs.existsSync(aliasPath);
    } catch (error) {
      return false;
    }
  },
  
  // Platform info
  getPlatformName() {
    return 'macOS';
  },
  
  getPlatformSpecificPaths() {
    return {
      configDir: path.join(os.homedir(), 'Library', 'Application Support'),
      applicationsDir: path.join(os.homedir(), 'Applications'),
      systemdUserDir: path.join(os.homedir(), 'Library', 'LaunchAgents')
    };
  }
};

