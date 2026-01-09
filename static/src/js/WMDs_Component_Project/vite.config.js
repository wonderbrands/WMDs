import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: () => false
        }
      }
    })
  ],

  // 🔑 FIX: stub Node globals
  define: {
    'process.env': {}
  },

  build: {
    target: 'es2017',
    cssCodeSplit: false,
    sourcemap: false,

    lib: {
      entry: path.resolve(__dirname, 'src/main.js'),
      name: 'OdooVueApp',
      formats: ['iife'],
      fileName: () => 'odoo_vue_app.js'
    },

    rollupOptions: {
      output: {
        inlineDynamicImports: true
      },

      onwarn(warning, warn) {
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

  resolve: {
    extensions: ['.js', '.vue', '.json'],
    alias: {
      '@': '/src'
    }
  },

  logLevel: 'info',

  server: {
    hmr: {
      overlay: true
    }
  },

  envPrefix: 'VITE_'
})
