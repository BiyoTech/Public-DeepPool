import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import vueTsEslintConfig from '@vue/eslint-config-typescript'
import prettierConfig from '@vue/eslint-config-prettier'

export default [
  // Base JS recommended rules
  js.configs.recommended,

  // Vue 3 essential rules
  ...pluginVue.configs['flat/essential'],

  // TypeScript support for Vue
  ...vueTsEslintConfig(),

  // Prettier integration (must be last to override formatting rules)
  prettierConfig,

  // Project-specific overrides
  {
    files: ['src/**/*.{ts,vue}'],
    rules: {
      // Allow unused vars prefixed with underscore
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
      // Allow explicit any during migration phase
      '@typescript-eslint/no-explicit-any': 'warn',
      // Vue specific
      'vue/multi-word-component-names': 'off',
      'vue/no-v-html': 'off',
    },
  },

  // Ignore patterns
  {
    ignores: ['dist/**', 'node_modules/**', '*.config.js', '*.config.ts'],
  },
]
