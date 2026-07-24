import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Dev: Vite serves the SPA and proxies API + WebSocket to the Litestar backend on :8080.
// Build: output straight into the backend's static dir so it ships as one process.
export default defineConfig({
  plugins: [svelte()],
  server: {
    // Bind to all interfaces so a phone/laptop on the LAN can reach the headless Pi.
    host: true,
    proxy: {
      '/api': { target: 'http://localhost:8080', changeOrigin: true, ws: true },
    },
  },
  build: {
    outDir: '../backend/app/static',
    emptyOutDir: true,
  },
})
