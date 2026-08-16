module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true,
  },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:@typescript-eslint/recommended',
    // P1-23: WCAG 2.1 AA 基础无障碍检查
    'plugin:jsx-a11y/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh', 'jsx-a11y'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
    'react/react-in-jsx-scope': 'off',
    // TypeScript interfaces already validate props; runtime propTypes are redundant.
    'react/prop-types': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': [
      'error',
      {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
      },
    ],
  },
  overrides: [
    {
      files: ['src/**/*.test.{ts,tsx}', 'src/**/__tests__/**/*.{ts,tsx}', 'src/**/*.d.ts'],
      rules: {
        // Test doubles and ambient declarations intentionally model untyped browser/API boundaries.
        '@typescript-eslint/no-explicit-any': 'off',
      },
    },
    {
      files: ['src/**/context.tsx', 'src/**/*Context.tsx'],
      rules: {
        // Context modules intentionally colocate providers, hooks, and typed context values.
        'react-refresh/only-export-components': 'off',
      },
    },
  ],
  settings: {
    react: {
      version: 'detect',
    },
  },
}
