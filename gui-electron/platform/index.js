/**
 * Platform utilities router
 * Automatically loads the correct platform implementation
 */

const platform = process.platform;

let platformUtils;

if (platform === 'win32') {
  platformUtils = require('./windows');
} else if (platform === 'darwin') {
  platformUtils = require('./macos');
} else {
  // Default to Linux (also handles other Unix-like systems)
  platformUtils = require('./linux');
}

module.exports = platformUtils;

