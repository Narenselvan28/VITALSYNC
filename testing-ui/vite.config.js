import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  server: {
    port: 2134,
    strictPort: true,
    host: true,
  },
  preview: {
    port: 2134,
    strictPort: true,
    host: true,
  },
});
