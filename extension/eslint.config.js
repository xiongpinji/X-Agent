const eslint = require('@eslint/js')
const globals = require('globals')

module.exports = [
  { ignores: ['coverage/**', 'dist/**', 'node_modules/**'] },
  eslint.configs.recommended,
  {
    files: ['**/*.js'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'commonjs',
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.jest,
        chrome: 'readonly',
      },
    },
  },
]
