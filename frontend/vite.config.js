import { defineConfig } from 'vite';

export default defineConfig({
  base: '/',
  build: {
    outDir: '../src/xhs_local/frontier/static',
    emptyOutDir: true,
    target: 'es2022',
    sourcemap: false,
    rollupOptions: { output: { manualChunks: { globe: ['three', 'd3-geo', 'topojson-client', 'world-atlas/countries-110m.json'] } } }
  },
  server: { proxy: { '/api': { target: 'http://127.0.0.1:18088', changeOrigin: false }, '/health': { target: 'http://127.0.0.1:18088' } } }
});
