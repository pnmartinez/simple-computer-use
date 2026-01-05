/**
 * Main build script - orchestrates all build steps
 */

const { downloadOllamaBinaries } = require('./download-ollama');
const { buildPythonBackend } = require('./build-python');
const { compressAppImage } = require('./compress-dist');
const { execSync } = require('child_process');
const path = require('path');

function getCurrentPlatform() {
  const platform = process.platform;
  const arch = process.arch;
  
  if (platform === 'linux' && arch === 'x64') {
    return 'linux-x64';
  } else if (platform === 'win32' && arch === 'x64') {
    return 'win32-x64';
  } else if (platform === 'darwin' && arch === 'x64') {
    return 'darwin-x64';
  } else if (platform === 'darwin' && arch === 'arm64') {
    return 'darwin-arm64';
  }
  
  return 'linux-x64'; // Default
}

function cleanUnusedOllamaPlatforms() {
  const fs = require('fs');
  const resourcesDir = path.join(__dirname, '..', '..', 'resources', 'ollama');
  const currentPlatform = getCurrentPlatform();
  const allPlatforms = ['linux-x64', 'win32-x64', 'darwin-x64', 'darwin-arm64'];
  
  console.log(`Cleaning unused Ollama platforms (keeping only ${currentPlatform})...`);
  
  for (const platform of allPlatforms) {
    if (platform !== currentPlatform) {
      const platformDir = path.join(resourcesDir, platform);
      if (fs.existsSync(platformDir)) {
        try {
          fs.rmSync(platformDir, { recursive: true, force: true });
          console.log(`  ✓ Removed ${platform}`);
        } catch (error) {
          console.warn(`  ⚠ Could not remove ${platform}: ${error.message}`);
        }
      }
    }
  }
}

async function buildAll() {
  console.log('========================================');
  console.log('Building Simple Computer Use Desktop');
  console.log('========================================\n');
  
  try {
    // Step 1: Download Ollama binaries
    console.log('Step 1: Downloading Ollama binaries...');
    await downloadOllamaBinaries();
    console.log('');
    
    // Step 1.5: Clean unused Ollama platforms to reduce size
    console.log('Step 1.5: Cleaning unused Ollama platforms...');
    cleanUnusedOllamaPlatforms();
    console.log('');
    
    // Step 2: Build Python backend
    console.log('Step 2: Building Python backend...');
    const pythonSuccess = buildPythonBackend();
    if (!pythonSuccess) {
      throw new Error('Python backend build failed');
    }
    console.log('');
    
    // Step 3: Build Electron app
    console.log('Step 3: Building Electron application...');
    const guiDir = path.join(__dirname, '..', '..', 'gui-electron');
    execSync('npm run build', {
      cwd: guiDir,
      stdio: 'inherit'
    });
    console.log('');
    
    console.log('');
    
    // Step 4 (Optional): Compress AppImage with xz for maximum compression
    if (process.env.COMPRESS_DIST === 'true') {
      console.log('Step 4: Compressing AppImage with xz (maximum compression)...');
      compressAppImage();
      console.log('');
    }
    
    console.log('========================================');
    console.log('✓ Build complete!');
    console.log('========================================');
    console.log('\nDistribution files are in: gui-electron/dist/');
    if (process.env.COMPRESS_DIST === 'true') {
      console.log('Compressed files (.xz) are also available for smaller download size.');
      console.log('Note: Compressed files must be decompressed before use: xz -d file.AppImage.xz');
    }
    
  } catch (error) {
    console.error('\n✗ Build failed:', error.message);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  buildAll();
}

module.exports = { buildAll };

