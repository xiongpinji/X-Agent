/**
 * Cross-platform packaging script (`npm run package`).
 *
 * Builds x-agent-extension.zip with the files needed to load/publish the
 * extension. The original script used `zip`, which does not exist on
 * Windows; this script uses PowerShell's Compress-Archive on Windows and
 * falls back to the `zip` CLI elsewhere.
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const root = __dirname ? path.resolve(__dirname, '..') : process.cwd();
const outName = 'x-agent-extension.zip';
const outFile = path.join(root, outName);

// Deterministic include list - keeps webstore uploads clean.
const includeFiles = [
  'manifest.json',
  'background.js',
  'content.js',
  'injected.js',
  'mcp-client.js',
  'api-client.js',
  'storage-manager.js',
  'tab-group-manager.js',
  'popup.html',
  'popup.css',
  'popup.js',
  'options.html',
  'options.js'
];
const includeDirs = ['images'];

function fail(message) {
  console.error(`[package] ${message}`);
  process.exit(1);
}

for (const rel of [...includeFiles, ...includeDirs]) {
  if (!fs.existsSync(path.join(root, rel))) {
    fail(`Required file/directory missing: ${rel}`);
  }
}

if (fs.existsSync(outFile)) {
  fs.unlinkSync(outFile);
}

if (process.platform === 'win32') {
  const paths = [...includeFiles, ...includeDirs].join("','");
  const script = `Compress-Archive -Path '${paths}' -DestinationPath '${outName}' -Force`;
  execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', script], {
    cwd: root,
    stdio: 'inherit'
  });
} else {
  execFileSync('zip', ['-r', outName, ...includeFiles, ...includeDirs], {
    cwd: root,
    stdio: 'inherit'
  });
}

const size = fs.statSync(outFile).size;
console.log(`[package] Created ${outName} (${(size / 1024).toFixed(1)} KB) at ${outFile}`);
