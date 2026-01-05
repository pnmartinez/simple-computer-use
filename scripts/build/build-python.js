/**
 * Script to build Python backend with PyInstaller
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

function buildPythonBackend() {
  const projectRoot = path.join(__dirname, '..', '..');
  const distDir = path.join(projectRoot, 'dist', 'python-backend');
  const resourcesDir = path.join(projectRoot, 'resources', 'python-backend');
  
  console.log('Building Python backend with PyInstaller...\n');
  
  try {
    // Check if PyInstaller is installed
    try {
      execSync('pyinstaller --version', { stdio: 'ignore' });
    } catch (error) {
      console.error('✗ PyInstaller not found. Installing...');
      execSync('pip install pyinstaller', { 
        cwd: projectRoot,
        stdio: 'inherit'
      });
    }
    
    // Clean previous builds
    if (fs.existsSync(path.join(projectRoot, 'build'))) {
      console.log('Cleaning previous build...');
      fs.rmSync(path.join(projectRoot, 'build'), { recursive: true, force: true });
    }
    
    if (fs.existsSync(path.join(projectRoot, 'dist', 'simple-computer-use-server'))) {
      fs.rmSync(path.join(projectRoot, 'dist', 'simple-computer-use-server'), { recursive: true, force: true });
    }
    
    // Build with PyInstaller
    console.log('Running PyInstaller...');
    execSync('pyinstaller build.spec --clean', {
      cwd: projectRoot,
      stdio: 'inherit'
    });
    
    // Create resources directory
    if (!fs.existsSync(resourcesDir)) {
      fs.mkdirSync(resourcesDir, { recursive: true });
    }
    
    // Copy executable or directory to resources
    const executableName = process.platform === 'win32' 
      ? 'simple-computer-use-server.exe' 
      : 'simple-computer-use-server';
    
    // Try directory structure first (onedir mode)
    const sourceDir = path.join(projectRoot, 'dist', 'simple-computer-use-server');
    const destDir = path.join(resourcesDir, 'simple-computer-use-server');
    
    // Try direct executable (onefile mode)
    const sourcePath = path.join(projectRoot, 'dist', executableName);
    const destPath = path.join(resourcesDir, executableName);
    
    if (fs.existsSync(sourceDir) && fs.statSync(sourceDir).isDirectory()) {
      // Copy entire directory (onedir mode)
      const { execSync } = require('child_process');
      execSync(`cp -r "${sourceDir}" "${resourcesDir}/"`, { stdio: 'inherit' });
      
      // Make executable
      const execPath = path.join(destDir, executableName);
      if (fs.existsSync(execPath) && process.platform !== 'win32') {
        fs.chmodSync(execPath, 0o755);
      }
      
      console.log(`✓ Python backend built (directory): ${destDir}`);
    } else if (fs.existsSync(sourcePath)) {
      // Copy single executable (onefile mode)
      fs.copyFileSync(sourcePath, destPath);
      
      // Make executable on Unix
      if (process.platform !== 'win32') {
        fs.chmodSync(destPath, 0o755);
      }
      
      console.log(`✓ Python backend built (single file): ${destPath}`);
    } else {
      throw new Error(`Executable not found at ${sourceDir} or ${sourcePath}`);
    }
    
    console.log('\n✓ Python backend build complete!');
    return true;
  } catch (error) {
    console.error('\n✗ Python backend build failed:', error.message);
    return false;
  }
}

// Run if called directly
if (require.main === module) {
  const success = buildPythonBackend();
  process.exit(success ? 0 : 1);
}

module.exports = { buildPythonBackend };

