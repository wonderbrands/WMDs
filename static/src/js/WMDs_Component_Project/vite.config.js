import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue({
      // Fail on template warnings (unknown components, etc.)
      template: {
        compilerOptions: {
          isCustomElement: () => false
        }
      }
    })
  ],

  // Treat warnings as errors
  build: {
    rollupOptions: {
      onwarn(warning, warn) {
        // Promote common "silent" issues to errors
        const fatalWarnings = [
          'UNRESOLVED_IMPORT',
          'MISSING_EXPORT',
          'NON_EXISTENT_EXPORT'
        ]

        if (fatalWarnings.includes(warning.code)) {
          throw new Error(warning.message)
        }

        warn(warning)
      }
    }
  },

  // Force strict dependency resolution
  resolve: {
    extensions: ['.js', '.vue', '.json'],
    alias: {
      '@': '/src'
    }
  },

  // Show full stack traces
  logLevel: 'info',

  // Strict dev server behavior
  server: {
    hmr: {
      overlay: true
    }
  },

  // Fail on env mistakes
  envPrefix: 'VITE_'
})
