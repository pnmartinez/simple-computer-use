/**
 * Script to analyze AppImage size and provide recommendations
 * 
 * NOTE: AppImage files are already compressed internally using squashfs.
 * Compressing them further with xz/lzma provides minimal benefit (<1% reduction)
 * because the data is already compressed.
 * 
 * Real size reduction must happen BEFORE creating the AppImage by:
 * 1. Removing optional components (easyocr, ultralytics) - DONE
 * 2. Removing unused dependencies (tensorflow) - DONE
 * 3. Using CPU-only builds (removes NVIDIA libs ~2.7GB) - NOT an option per user
 * 4. Optimizing PyInstaller build further
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

function analyzeAppImageSize() {
  const projectRoot = path.join(__dirname, '..', '..');
  const distDir = path.join(projectRoot, 'gui-electron', 'dist');
  
  console.log('=== AppImage Size Analysis ===\n');
  
  // Find AppImage file
  const appImageFiles = fs.readdirSync(distDir)
    .filter(file => file.endsWith('.AppImage') && !file.endsWith('.AppImage.xz'));
  
  if (appImageFiles.length === 0) {
    console.warn('⚠ No AppImage files found');
    return false;
  }
  
  for (const appImageFile of appImageFiles) {
    const appImagePath = path.join(distDir, appImageFile);
    const stats = fs.statSync(appImagePath);
    const sizeMB = (stats.size / (1024 * 1024)).toFixed(2);
    const sizeGB = (stats.size / (1024 * 1024 * 1024)).toFixed(2);
    
    console.log(`File: ${appImageFile}`);
    console.log(`  Size: ${sizeMB} MB (${sizeGB} GB)\n`);
    
    // Check unpacked size
    const unpackedDir = path.join(distDir, 'linux-unpacked');
    if (fs.existsSync(unpackedDir)) {
      try {
        const unpackedSize = execSync(`du -sb "${unpackedDir}"`, { encoding: 'utf8' }).trim().split('\t')[0];
        const unpackedMB = (parseInt(unpackedSize) / (1024 * 1024)).toFixed(2);
        const unpackedGB = (parseInt(unpackedSize) / (1024 * 1024 * 1024)).toFixed(2);
        const compressionRatio = ((1 - stats.size / parseInt(unpackedSize)) * 100).toFixed(1);
        
        console.log(`Unpacked size: ${unpackedMB} MB (${unpackedGB} GB)`);
        console.log(`AppImage compression: ${compressionRatio}% (squashfs)\n`);
      } catch (e) {
        // Ignore
      }
    }
    
    // Explain why further compression doesn't help
    console.log('⚠ NOTE: AppImage files use squashfs compression internally.');
    console.log('   Compressing with xz/lzma provides minimal benefit (<1%)');
    console.log('   because the data is already compressed.\n');
    
    console.log('📊 Size Reduction Strategies:');
    console.log('   ✓ Removed easyocr/ultralytics (optional components)');
    console.log('   ✓ Removed tensorflow (unused)');
    console.log('   ✓ Optimized Ollama (single platform)');
    console.log('   ⚠ NVIDIA libraries: 2.7 GB (required for GPU support)');
    console.log('   ⚠ PyTorch: 1.5 GB (required for Whisper)');
    console.log('   ⚠ Other CUDA libs: ~1 GB (required for GPU)\n');
    
    console.log('💡 To reduce further:');
    console.log('   - Create CPU-only variant (removes ~3.7 GB NVIDIA/CUDA)');
    console.log('   - Use lighter ML models');
    console.log('   - Split into core + optional components\n');
  }
  
  return true;
}

// Legacy function name for compatibility
function compressAppImage() {
  console.log('⚠ WARNING: Compressing AppImage provides minimal benefit (<1%)');
  console.log('   because AppImage already uses squashfs compression.\n');
  return analyzeAppImageSize();
}

// Run if called directly
if (require.main === module) {
  const success = compressAppImage();
  process.exit(success ? 0 : 1);
}

module.exports = { compressAppImage };

