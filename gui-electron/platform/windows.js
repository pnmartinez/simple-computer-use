/**
 * Windows platform implementation
 * Contains all Windows-specific functionality
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

module.exports = {
  // Startup Service Management (Task Scheduler)
  installStartupService() {
    try {
      const projectRoot = path.resolve(__dirname, '..', '..');
      const electronPath = require('electron');
      const scriptPath = path.join(projectRoot, 'gui-electron', 'start-gui-electron.bat');
      
      // Create batch script to start Electron
      const batContent = `@echo off
cd /d "${projectRoot}\\gui-electron"
"${electronPath}" .
`;
      fs.writeFileSync(scriptPath, batContent);
      
      // Create scheduled task using Task Scheduler
      const taskName = 'SimpleComputerUseDesktop';
      const username = os.userInfo().username;
      const command = `schtasks /create /tn "${taskName}" /tr "\\"${scriptPath}\\"" /sc onlogon /ru "${username}" /f`;
      
      try {
        execSync(command, { stdio: 'ignore' });
        return { success: true };
      } catch (error) {
        return { success: false, error: `Failed to create scheduled task: ${error.message}` };
      }
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  uninstallStartupService() {
    try {
      const taskName = 'SimpleComputerUseDesktop';
      
      // Delete scheduled task
      try {
        execSync(`schtasks /delete /tn "${taskName}" /f`, { stdio: 'ignore' });
      } catch (error) {
        // Task might not exist, continue
      }
      
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  isStartupServiceInstalled() {
    try {
      const taskName = 'SimpleComputerUseDesktop';
      const result = execSync(`schtasks /query /tn "${taskName}"`, {
        encoding: 'utf8',
        stdio: 'pipe'
      });
      return result.includes(taskName);
    } catch (error) {
      return false;
    }
  },
  
  // Process Management
  getProcessUsingPort(port) {
    try {
      // netstat -ano | findstr :5000
      const result = execSync(`netstat -ano | findstr :${port}`, {
        encoding: 'utf8',
        stdio: 'pipe'
      });
      
      const lines = result.trim().split('\n').filter(line => line.trim());
      for (const line of lines) {
        if (line.includes('LISTENING')) {
          const parts = line.trim().split(/\s+/);
          const pid = parts[parts.length - 1];
          
          if (!pid || isNaN(parseInt(pid))) continue;
          
          // tasklist /FI "PID eq 1234"
          try {
            const taskResult = execSync(`tasklist /FI "PID eq ${pid}" /FO CSV /NH`, {
              encoding: 'utf8',
              stdio: 'pipe'
            });
            
            if (taskResult.trim()) {
              const taskParts = taskResult.split(',');
              const name = taskParts[0]?.replace(/"/g, '') || 'unknown';
              
              return {
                success: true,
                process: {
                  pid: pid,
                  name: name,
                  command: name
                }
              };
            }
          } catch (e) {
            // Process might have exited
          }
          
          return {
            success: true,
            process: {
              pid: pid,
              name: 'unknown',
              command: 'unknown'
            }
          };
        }
      }
      return { success: false, error: 'No process found using this port' };
    } catch (error) {
      return { success: false, error: error.message };
    }
  },
  
  killProcess(pid) {
    return new Promise((resolve) => {
      try {
        // taskkill /PID 1234 /T (graceful termination)
        execSync(`taskkill /PID ${pid} /T`, { stdio: 'ignore' });
        
        setTimeout(() => {
          try {
            // Check if process still exists
            execSync(`tasklist /FI "PID eq ${pid}"`, { stdio: 'ignore' });
            // Process still exists, force kill
            execSync(`taskkill /PID ${pid} /F /T`, { stdio: 'ignore' });
          } catch (e) {
            // Process already terminated
          }
          resolve({ success: true });
        }, 500);
      } catch (error) {
        // Try force kill
        try {
          execSync(`taskkill /PID ${pid} /F /T`, { stdio: 'ignore' });
          resolve({ success: true });
        } catch (e2) {
          resolve({ success: false, error: error.message });
        }
      }
    });
  },
  
  // Python Detection
  findPythonExecutable() {
    const projectRoot = path.resolve(__dirname, '..', '..');
    const venvPython = path.join(projectRoot, 'venv-py312', 'Scripts', 'python.exe');
    
    // First try: venv-py312 (Windows path)
    if (fs.existsSync(venvPython)) {
      try {
        execSync(`"${venvPython}" --version`, { encoding: 'utf8', stdio: 'ignore' });
        return venvPython;
      } catch (e) {
        console.warn('venv-py312 Python found but not working, trying system Python');
      }
    }
    
    // Fallback: system Python
    const pythonCommands = ['python', 'python3', 'py'];
    for (const cmd of pythonCommands) {
      try {
        // Use 'where' command (Windows equivalent of 'which')
        const result = execSync(`where ${cmd}`, { encoding: 'utf8', stdio: 'pipe' }).trim();
        if (result && result.split('\n').length > 0) {
          return cmd;
        }
      } catch (e) {
        // Continue to next
      }
    }
    return 'python'; // Default fallback
  },
  
  // Desktop Application Installation (Start Menu shortcut)
  installDesktopApp() {
    return new Promise((resolve) => {
      try {
        const projectRoot = path.resolve(__dirname, '..', '..');
        const electronPath = require('electron');
        const startScript = path.join(projectRoot, 'gui-electron', 'start-gui-electron.bat');
        const shortcutPath = path.join(
          os.homedir(),
          'AppData',
          'Roaming',
          'Microsoft',
          'Windows',
          'Start Menu',
          'Programs',
          'Simple Computer Use Desktop.lnk'
        );
        
        // Create start script if it doesn't exist
        if (!fs.existsSync(startScript)) {
          const batContent = `@echo off
cd /d "${projectRoot}\\gui-electron"
"${electronPath}" .
`;
          fs.writeFileSync(startScript, batContent);
        }
        
        // Create shortcut using PowerShell
        const psScript = `
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("${shortcutPath.replace(/\\/g, '\\\\')}")
$Shortcut.TargetPath = "${electronPath.replace(/\\/g, '\\\\')}"
$Shortcut.WorkingDirectory = "${path.join(projectRoot, 'gui-electron').replace(/\\/g, '\\\\')}"
$IconPath = "${path.join(projectRoot, 'gui-electron', 'ic_launcher-playstore.png').replace(/\\/g, '\\\\')}"
if (Test-Path "$IconPath") {
    $Shortcut.IconLocation = "$IconPath"
}
$Shortcut.Description = "Simple Computer Use Desktop"
$Shortcut.Save()
`;
        
        execSync(`powershell -Command "${psScript}"`, { stdio: 'ignore' });
        resolve({ 
          success: true, 
          message: 'Application installed to Start Menu',
          output: `Shortcut created at: ${shortcutPath}`
        });
      } catch (error) {
        resolve({ success: false, error: error.message });
      }
    });
  },
  
  isDesktopAppInstalled() {
    try {
      const shortcutPath = path.join(
        os.homedir(),
        'AppData',
        'Roaming',
        'Microsoft',
        'Windows',
        'Start Menu',
        'Programs',
        'Simple Computer Use Desktop.lnk'
      );
      return fs.existsSync(shortcutPath);
    } catch (error) {
      return false;
    }
  },
  
  // Platform info
  getPlatformName() {
    return 'Windows';
  },
  
  getPlatformSpecificPaths() {
    return {
      configDir: path.join(os.homedir(), 'AppData', 'Roaming'),
      applicationsDir: path.join(os.homedir(), 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
      systemdUserDir: null // Not applicable on Windows
    };
  }
};

