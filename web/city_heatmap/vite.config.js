import { defineConfig } from 'vite';

export default defineConfig({
  server: {
    host: '127.0.0.1',
    port: 9530,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9531',
        changeOrigin: true,
      },
      '/socket.io': {
        target: 'http://127.0.0.1:9531',
        changeOrigin: true,
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});
