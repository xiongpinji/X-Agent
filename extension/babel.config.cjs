/**
 * Babel config for Jest.
 * The extension sources are ES modules (MV3 service worker "type": "module"),
 * but Jest runs tests in CJS mode - transform ESM syntax down to CJS.
 * Only used by the test toolchain; Chrome loads the raw ESM files.
 */
module.exports = {
  presets: [
    [
      '@babel/preset-env',
      {
        targets: { node: 'current' },
        modules: 'commonjs'
      }
    ]
  ]
};
