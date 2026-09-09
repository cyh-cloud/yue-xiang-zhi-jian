import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { build, createServer, preview } from 'vite'

const mode = process.argv[2] ?? 'dev'

const config = {
  configFile: false,
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('../src', import.meta.url))
    }
  },
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true
      }
    }
  },
  build: {
    emptyOutDir: false
  }
}

if (mode === 'dev') {
  const server = await createServer(config)
  await server.listen()
} else if (mode === 'build') {
  await build(config)
} else if (mode === 'preview') {
  const server = await preview(config)
} else {
  throw new Error(`Unknown Vite mode: ${mode}`)
}
