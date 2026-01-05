/**
 * Script to download Ollama binaries for packaging
 */

const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const OLLAMA_VERSION = 'v0.13.5'; // Latest stable version
const BASE_URL = `https://github.com/ollama/ollama/releases/download/${OLLAMA_VERSION}`;

const PLATFORMS = {
  'linux-x64': {
    archive: 'ollama-linux-amd64.tgz',
    binary: 'ollama',
    output: 'ollama',
    executable: true
  },
  'win32-x64': {
    archive: 'ollama-windows-amd64.zip',
    binary: 'ollama.exe',
    output: 'ollama.exe',
    executable: false
  },
  'darwin-x64': {
    archive: 'ollama-darwin.tgz',
    binary: 'ollama',
    output: 'ollama',
    executable: true
  },
  'darwin-arm64': {
    archive: 'ollama-darwin.tgz',
    binary: 'ollama',
    output: 'ollama',
    executable: true
  }
};

function downloadFile(url, outputPath) {
  return new Promise((resolve, reject) => {
    console.log(`Downloading ${url}...`);
    const file = fs.createWriteStream(outputPath);
    
    https.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        // Follow redirect
        return downloadFile(response.headers.location, outputPath)
          .then(resolve)
          .catch(reject);
      }
      
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }
      
      response.pipe(file);
      
      file.on('finish', () => {
        file.close();
        console.log(`✓ Downloaded to ${outputPath}`);
        resolve();
      });
    }).on('error', (err) => {
      fs.unlinkSync(outputPath);
      reject(err);
    });
  });
}

function getCurrentPlatform() {
  // Map Node.js platform to our platform keys
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
  
  // Default to linux-x64 if unknown
  console.warn(`Unknown platform/arch: ${platform}/${arch}, defaulting to linux-x64`);
  return 'linux-x64';
}

async function downloadOllamaBinaries() {
  const resourcesDir = path.join(__dirname, '..', '..', 'resources', 'ollama');
  
  // Create resources directory if it doesn't exist
  if (!fs.existsSync(resourcesDir)) {
    fs.mkdirSync(resourcesDir, { recursive: true });
  }
  
  // Determine which platform to download based on build platform
  const currentPlatform = getCurrentPlatform();
  const platformsToDownload = process.env.DOWNLOAD_ALL_PLATFORMS === 'true' 
    ? Object.keys(PLATFORMS)  // Download all if explicitly requested
    : [currentPlatform];  // Only download current platform
  
  console.log(`Downloading Ollama binaries for: ${platformsToDownload.join(', ')}\n`);
  
  for (const platform of platformsToDownload) {
    if (!PLATFORMS[platform]) {
      console.warn(`⚠ Unknown platform: ${platform}, skipping...`);
      continue;
    }
    
    const config = PLATFORMS[platform];
    const platformDir = path.join(resourcesDir, platform);
    
    if (!fs.existsSync(platformDir)) {
      fs.mkdirSync(platformDir, { recursive: true });
    }
    
    const archiveUrl = `${BASE_URL}/${config.archive}`;
    const archivePath = path.join(platformDir, config.archive);
    const outputPath = path.join(platformDir, config.output);
    const versionFile = path.join(platformDir, '.ollama-version');
    const tempExtractDir = path.join(platformDir, 'temp_extract');
    
    // Check if binary already exists and is the correct version
    if (fs.existsSync(outputPath) && fs.existsSync(versionFile)) {
      const cachedVersion = fs.readFileSync(versionFile, 'utf8').trim();
      if (cachedVersion === OLLAMA_VERSION) {
        console.log(`✓ Ollama ${OLLAMA_VERSION} for ${platform} already cached, skipping download`);
        continue;
      } else {
        console.log(`⟳ Ollama version changed (${cachedVersion} → ${OLLAMA_VERSION}), re-downloading for ${platform}`);
      }
    }
    
    try {
      // Download archive
      console.log(`Downloading ${config.archive}...`);
      await downloadFile(archiveUrl, archivePath);
      
      // Extract archive
      console.log(`Extracting ${config.archive}...`);
      if (fs.existsSync(tempExtractDir)) {
        fs.rmSync(tempExtractDir, { recursive: true, force: true });
      }
      fs.mkdirSync(tempExtractDir, { recursive: true });
      
      if (config.archive.endsWith('.tgz')) {
        // Extract .tgz file
        execSync(`tar -xzf "${archivePath}" -C "${tempExtractDir}"`, { stdio: 'inherit' });
      } else if (config.archive.endsWith('.zip')) {
        // Extract .zip file (Windows)
        execSync(`unzip -q "${archivePath}" -d "${tempExtractDir}"`, { stdio: 'inherit' });
      }
      
      // Find and copy the binary
      const binaryPath = path.join(tempExtractDir, config.binary);
      if (!fs.existsSync(binaryPath)) {
        // Try to find it in subdirectories
        const findBinary = (dir) => {
          const files = fs.readdirSync(dir);
          for (const file of files) {
            const fullPath = path.join(dir, file);
            const stat = fs.statSync(fullPath);
            if (stat.isDirectory()) {
              const found = findBinary(fullPath);
              if (found) return found;
            } else if (file === config.binary || (config.binary === 'ollama' && file === 'ollama')) {
              return fullPath;
            }
          }
          return null;
        };
        
        const foundBinary = findBinary(tempExtractDir);
        if (foundBinary) {
          fs.copyFileSync(foundBinary, outputPath);
        } else {
          throw new Error(`Binary ${config.binary} not found in archive`);
        }
      } else {
        fs.copyFileSync(binaryPath, outputPath);
      }
      
      // Make executable on Unix systems
      if (config.executable && process.platform !== 'win32') {
        fs.chmodSync(outputPath, 0o755);
      }
      
      // Clean up
      fs.rmSync(tempExtractDir, { recursive: true, force: true });
      fs.unlinkSync(archivePath);
      
      // Write version file for caching
      fs.writeFileSync(versionFile, OLLAMA_VERSION);
      
      console.log(`✓ Extracted ${config.output} to ${outputPath}`);
    } catch (error) {
      console.error(`✗ Failed to download/extract ${platform}: ${error.message}`);
      // Clean up on error
      if (fs.existsSync(tempExtractDir)) {
        fs.rmSync(tempExtractDir, { recursive: true, force: true });
      }
      if (fs.existsSync(archivePath)) {
        fs.unlinkSync(archivePath).catch(() => {});
      }
      // Continue with other platforms
    }
  }
  
  console.log('\n✓ Ollama binaries download complete!');
}

// Run if called directly
if (require.main === module) {
  downloadOllamaBinaries().catch(console.error);
}

module.exports = { downloadOllamaBinaries };

