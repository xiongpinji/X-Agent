// mobile/scripts/patch-expo-cli-externals.js
// postinstall 补丁：修复 @expo/cli@0.17.x (Expo SDK 50) 在 Windows + Node>=22 下的
// expo export 崩溃问题。
//
// 背景：Node 22+ 的 module.builtinModules 包含 'node:sea' / 'node:sqlite' / 'node:test'
// 等带前缀条目，@expo/cli 的 externals.js 直接把它当作 .expo/metro/externals 下的
// 目录名。冒号在 Windows 文件系统中是非法字符，mkdir 直接抛 ENOENT，导致
// `expo export` / `expo start` 无法启动 Metro。
// 补丁将目录名中的 'node:' 前缀剥掉（仅影响 shim 目录名，不影响模块解析）。
// 该补丁幂等：已打补丁或版本不符时直接跳过。

const fs = require('fs');
const path = require('path');

const target = path.join(
  __dirname,
  '..',
  'node_modules',
  '@expo',
  'cli',
  'build',
  'src',
  'start',
  'server',
  'metro',
  'externals.js'
);

if (!fs.existsSync(target)) {
  console.log('[patch-expo-cli-externals] externals.js not found, skip');
  process.exit(0);
}

const original = fs.readFileSync(target, 'utf8');

const needle = 'for (const moduleId of NODE_STDLIB_MODULES){';
const replacement =
  'for (const rawModuleId of NODE_STDLIB_MODULES){' +
  '\n        const moduleId = rawModuleId.replace(/^node:/, "");';

if (original.includes(replacement)) {
  console.log('[patch-expo-cli-externals] already patched, skip');
  process.exit(0);
}

if (!original.includes(needle)) {
  console.log(
    '[patch-expo-cli-externals] pattern not found (different @expo/cli version?), skip'
  );
  process.exit(0);
}

fs.writeFileSync(target, original.replace(needle, replacement));
console.log('[patch-expo-cli-externals] patched @expo/cli externals.js');
