import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'node:path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: process.env.NODE_ENV === 'production' ? '/static/react-app/' : '/',
  build: {
    outDir: resolve(import.meta.dirname, '../static/react-app'),
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/alumno': 'http://127.0.0.1:5000',
      '/static': 'http://127.0.0.1:5000',
    },
  },
});
